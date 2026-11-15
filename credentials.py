"""Local Windows credential storage for Aboard."""
import ctypes as c
from ctypes import wintypes as w
from pathlib import Path
import os


class Blob(c.Structure):
    _fields_ = [('length', w.DWORD), ('data', c.POINTER(c.c_ubyte))]


def transform(data, encrypt):
    raw = (c.c_ubyte * len(data)).from_buffer_copy(data)
    source, result = Blob(len(data), raw), Blob()
    crypt = c.WinDLL('crypt32', use_last_error=True)
    func = crypt.CryptProtectData if encrypt else crypt.CryptUnprotectData
    func.argtypes = [c.POINTER(Blob), c.c_void_p, c.c_void_p, c.c_void_p, c.c_void_p, w.DWORD, c.POINTER(Blob)]
    if not func(c.byref(source), None, None, None, None, 1, c.byref(result)):
        raise c.WinError(c.get_last_error())
    kernel = c.WinDLL('kernel32')
    kernel.LocalFree.argtypes = [c.c_void_p]
    try:
        return c.string_at(result.data, result.length)
    finally:
        kernel.LocalFree(result.data)


def read_key(home):
    configured = os.environ.get('GROQ_API_KEY')
    if configured:
        return configured
    path = Path(home) / 'groq.dpapi'
    if not path.is_file() and os.environ.get('ABOARD_LAUNCH_DIR'):
        path = Path(os.environ['ABOARD_LAUNCH_DIR']) / 'groq.dpapi'
    return transform(path.read_bytes(), False).decode() if path.is_file() else ''


def save_key(home, key):
    Path(home).mkdir(parents=True, exist_ok=True)
    (Path(home) / 'groq.dpapi').write_bytes(transform(key.strip().encode(), True))
