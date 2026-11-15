"""Capture a short microphone turn as a WAV in memory with Windows WinMM."""

from array import array
from collections import deque
import ctypes as ct
from ctypes import wintypes as wt
from io import BytesIO
from math import sqrt
from threading import Event, Lock
from time import monotonic
import wave


WAVE_MAPPER = 0xFFFFFFFF
WAVE_FORMAT_PCM = 1
WAVERR_BADFORMAT = 32
WHDR_DONE = 1
CHUNK_SECONDS = 0.1
INPUT_LOCK = Lock()


class WaveFormat(ct.Structure):
    _pack_ = 1
    _fields_ = [
        ('format_tag', wt.WORD), ('channels', wt.WORD), ('samples_per_sec', wt.DWORD),
        ('avg_bytes_per_sec', wt.DWORD), ('block_align', wt.WORD), ('bits_per_sample', wt.WORD),
        ('extra_size', wt.WORD),
    ]


class WaveHeader(ct.Structure):
    _fields_ = [
        ('data', ct.c_void_p), ('length', wt.DWORD), ('bytes_recorded', wt.DWORD),
        ('user', ct.c_size_t), ('flags', wt.DWORD), ('loops', wt.DWORD),
        ('next', ct.c_void_p), ('reserved', ct.c_size_t),
    ]


class InputCaps(ct.Structure):
    _fields_ = [('manufacturer', wt.WORD), ('product', wt.WORD), ('version', wt.DWORD),
                ('name', wt.WCHAR * 32), ('formats', wt.DWORD), ('channels', wt.WORD), ('reserved', wt.WORD)]


def winmm():
    if not hasattr(ct, 'WinDLL'):
        raise OSError('Microphone recording requires Windows.')
    api = ct.WinDLL('winmm')
    signatures = {
        'waveInGetNumDevs': [],
        'waveInGetDevCapsW': [ct.c_size_t, ct.POINTER(InputCaps), wt.UINT],
        'waveInOpen': [ct.POINTER(wt.HANDLE), wt.UINT, ct.POINTER(WaveFormat),
                       ct.c_size_t, ct.c_size_t, wt.DWORD],
        'waveInGetErrorTextW': [wt.UINT, wt.LPWSTR, wt.UINT],
        'waveInStart': [wt.HANDLE],
        'waveInReset': [wt.HANDLE],
        'waveInClose': [wt.HANDLE],
        'waveInPrepareHeader': [wt.HANDLE, ct.POINTER(WaveHeader), wt.UINT],
        'waveInAddBuffer': [wt.HANDLE, ct.POINTER(WaveHeader), wt.UINT],
        'waveInUnprepareHeader': [wt.HANDLE, ct.POINTER(WaveHeader), wt.UINT],
    }
    for name, args in signatures.items():
        function = getattr(api, name)
        function.argtypes = args
        function.restype = wt.UINT
    return api


def check(api, code, description):
    if code:
        message = ct.create_unicode_buffer(256)
        api.waveInGetErrorTextW(code, message, len(message))
        detail = message.value or f'Windows error {code}'
        raise OSError(f'{description}. Check the default Windows microphone and app access. ({detail})')


def input_devices():
    api = winmm()
    devices = {'Windows default': WAVE_MAPPER}
    for index in range(api.waveInGetNumDevs()):
        caps = InputCaps()
        if api.waveInGetDevCapsW(index, ct.byref(caps), ct.sizeof(caps)) == 0:
            devices[f'{caps.name} ({index + 1})'] = index
    return devices


def open_input(api, device):
    handle = wt.HANDLE()
    for rate in (16000, 48000, 44100):
        format_ = WaveFormat(WAVE_FORMAT_PCM, 1, rate, rate * 2, 2, 16, 0)
        code = api.waveInOpen(ct.byref(handle), device, ct.byref(format_), 0, 0, 0)
        if code != WAVERR_BADFORMAT:
            break
    check(api, code, 'Cannot open the microphone')
    return handle, rate


def rms(chunk):
    samples = array('h', chunk)
    if not samples:
        return 0
    mean = sum(samples) / len(samples)
    return sqrt(sum((value - mean) ** 2 for value in samples) / len(samples))


class Turn:
    """Trim leading silence and finish after a pause, using a coarse energy gate."""

    def __init__(self):
        self.pre_roll = deque(maxlen=4)
        self.frames = []
        self.noise_floor = 35.0
        self.hot_chunks = 0
        self.quiet_chunks = 0

    def add(self, chunk):
        level = rms(chunk)
        if not self.frames:
            self.pre_roll.append(chunk)
            threshold = max(35.0, self.noise_floor * 2.2)
            if level >= threshold:
                self.hot_chunks += 1
            else:
                self.noise_floor = self.noise_floor * 0.86 + level * 0.14
                self.hot_chunks = 0
            if self.hot_chunks >= 2:
                self.frames.extend(self.pre_roll)
            return False

        self.frames.append(chunk)
        threshold = max(24.0, self.noise_floor * 1.6)
        self.quiet_chunks = 0 if level >= threshold else self.quiet_chunks + 1
        return self.quiet_chunks >= 9

    def as_wave(self, rate):
        if not self.frames:
            return None
        buffer = BytesIO()
        with wave.open(buffer, 'wb') as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(rate)
            output.writeframes(b''.join(self.frames))
        return buffer.getvalue()


def capture(timeout, cancel, finish, auto_pause, device, on_level, on_ready):
    api = winmm()
    handle, rate = open_input(api, device)
    buffers = deque()
    prepared = []
    header_size = ct.sizeof(WaveHeader)
    chunk_size = int(rate * CHUNK_SECONDS) * 2
    try:
        for _ in range(4):
            data = ct.create_string_buffer(chunk_size)
            header = WaveHeader(ct.addressof(data), chunk_size)
            check(api, api.waveInPrepareHeader(handle, ct.byref(header), header_size),
                  'Cannot prepare the microphone buffer')
            buffer = (data, header)
            prepared.append(buffer)
            buffers.append(buffer)
            check(api, api.waveInAddBuffer(handle, ct.byref(header), header_size),
                  'Cannot queue the microphone buffer')
        check(api, api.waveInStart(handle), 'Cannot start microphone recording')
        if on_ready:
            on_ready()
        turn = Turn()
        manual_audio = []
        deadline = monotonic() + timeout
        while not cancel.is_set() and not (finish and finish.is_set()) and monotonic() < deadline:
            data, header = buffers[0]
            if not header.flags & WHDR_DONE:
                cancel.wait(0.02)
                continue
            buffers.rotate(-1)
            byte_count = min(header.bytes_recorded, chunk_size) & ~1
            header.bytes_recorded = 0
            if byte_count:
                chunk = data.raw[:byte_count]
                if on_level:
                    on_level(rms(chunk))
                if finish is not None:
                    manual_audio.append(chunk)
                if auto_pause and turn.add(chunk):
                    break
            check(api, api.waveInAddBuffer(handle, ct.byref(header), header_size),
                  'Cannot continue microphone recording')
        if cancel.is_set():
            return None
        if finish is not None and (finish.is_set() or not auto_pause or not turn.frames):
            # Reset returns queued buffers, including the partial buffer at the moment of Stop.
            check(api, api.waveInReset(handle), 'Cannot finish microphone recording')
            for data, header in buffers:
                byte_count = min(header.bytes_recorded, chunk_size) & ~1
                if byte_count:
                    manual_audio.append(data.raw[:byte_count])
            turn.frames = manual_audio
        # Allow quiet speech through. Only reject a too-short recording or a flat input signal.
        if not turn.frames or sum(map(len, turn.frames)) < rate // 5:
            return None
        peak = max(rms(chunk) for chunk in turn.frames)
        if peak < 1:
            return None
        if peak < 400:
            gain = min(16, 400 / peak)
            turn.frames = [array('h', (max(-32768, min(32767, round(sample * gain)))
                                       for sample in array('h', chunk))).tobytes() for chunk in turn.frames]
        return turn.as_wave(rate)
    finally:
        api.waveInReset(handle)
        for _, header in prepared:
            api.waveInUnprepareHeader(handle, ct.byref(header), header_size)
        api.waveInClose(handle)


def record_wave(timeout=8, cancel=None, finish=None, auto_pause=True, device=WAVE_MAPPER, on_level=None, on_ready=None):
    """Return an in-memory WAV. A finish event saves audio, a cancel event discards it."""
    timeout = float(timeout)
    if not 0 < timeout <= 20:
        raise ValueError('Microphone timeout must be between 0 and 20 seconds.')
    cancel = cancel if cancel is not None else Event()
    while not cancel.is_set():
        if INPUT_LOCK.acquire(timeout=0.05):
            try:
                return (None if cancel.is_set() or (finish and finish.is_set())
                        else capture(timeout, cancel, finish, auto_pause, device, on_level, on_ready))
            finally:
                INPUT_LOCK.release()
    return None
