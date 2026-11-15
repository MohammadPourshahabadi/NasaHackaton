"""Run local Windows speech sessions without blocking the Tk event loop."""

import base64
import json
import os
from pathlib import Path
import subprocess
import threading


_SCRIPT = r"""
$ErrorActionPreference = 'Stop'

function Write-Result($value) {
    $json = ConvertTo-Json -InputObject $value -Compress -Depth 5
    $bytes = [Text.Encoding]::UTF8.GetBytes($json)
    [Console]::WriteLine([Convert]::ToBase64String($bytes))
}

function Wait-WinRT($operation, [Type]$resultType, [int]$milliseconds) {
    $task = $script:asTask.MakeGenericMethod($resultType).Invoke($null, @($operation))
    if (!$task.Wait($milliseconds)) { throw [TimeoutException]::new('Local speech operation timed out.') }
    return $task.Result
}

function Enable-WinRT {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $script:asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and
                       $_.GetParameters().Count -eq 1 -and
                       $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } |
        Select-Object -First 1
}

function Speak-WinRT($job) {
    Enable-WinRT
    $voiceType = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime]
    $resultType = [Windows.Media.SpeechSynthesis.SpeechSynthesisStream, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime]
    $voices = @($voiceType::AllVoices | Where-Object { $_.Language -eq 'en-US' })
    $speaker = $voiceType::new()
    try {
        if ($voices.Count -gt 0) { $speaker.Voice = $voices[0] }
        $stream = Wait-WinRT ($speaker.SynthesizeTextToStreamAsync([string]$job.text)) $resultType 12000
        $input = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($stream.GetInputStreamAt(0))
        try {
            if ($job.output) {
                $file = [IO.File]::Create($job.output)
                try { $input.CopyTo($file) }
                finally { $file.Dispose() }
            } else {
                $memory = [IO.MemoryStream]::new()
                try {
                    $input.CopyTo($memory)
                    $memory.Position = 0
                    $player = [System.Media.SoundPlayer]::new($memory)
                    try { $player.PlaySync() }
                    finally { $player.Dispose() }
                } finally { $memory.Dispose() }
            }
        } finally { $input.Dispose() }
    } finally { $speaker.Dispose() }
}

function Listen-WinRT($job) {
    Enable-WinRT
    $recognizerType = [Windows.Media.SpeechRecognition.SpeechRecognizer, Windows.Media.SpeechRecognition, ContentType=WindowsRuntime]
    $constraintType = [Windows.Media.SpeechRecognition.SpeechRecognitionListConstraint, Windows.Media.SpeechRecognition, ContentType=WindowsRuntime]
    $compileType = [Windows.Media.SpeechRecognition.SpeechRecognitionCompilationResult, Windows.Media.SpeechRecognition, ContentType=WindowsRuntime]
    $resultType = [Windows.Media.SpeechRecognition.SpeechRecognitionResult, Windows.Media.SpeechRecognition, ContentType=WindowsRuntime]
    $languages = @($recognizerType::SupportedGrammarLanguages)
    $english = @($languages | Where-Object { $_.LanguageTag -eq 'en-US' })
    if ($english.Count -eq 0) {
        $english = @($languages | Where-Object { $_.LanguageTag -like 'en-*' })
    }
    if ($english.Count -eq 0) { throw 'No English offline speech pack is available.' }
    if (!$job.choices) { throw 'No offline command grammar was supplied.' }
    $recognizer = $recognizerType::new($english[0])
    try {
        $constraint = $constraintType::new([string[]]$job.choices)
        $collectionType = $recognizerType.GetProperty('Constraints').PropertyType
        $null = $collectionType.GetMethod('Insert').Invoke($recognizer.Constraints, @([int]0, $constraint))
        $compiled = Wait-WinRT ($recognizer.CompileConstraintsAsync()) $compileType 8000
        if ($compiled.Status.ToString() -ne 'Success') { throw "Unable to prepare offline command speech: $($compiled.Status)." }
        $recognizer.Timeouts.InitialSilenceTimeout = [TimeSpan]::FromSeconds([double]$job.timeout)
        $recognizer.Timeouts.EndSilenceTimeout = [TimeSpan]::FromMilliseconds(550)
        $recognizer.Timeouts.BabbleTimeout = [TimeSpan]::FromSeconds(4)
        $result = Wait-WinRT ($recognizer.RecognizeAsync()) $resultType ([int](1000 * ([double]$job.timeout + 5)))
        if ($result.Status.ToString() -eq 'Success' -and $result.Confidence.ToString() -ne 'Rejected') {
            return [string]$result.Text
        }
    } finally { $recognizer.Dispose() }
}

$stage = 'load'
try {
    $encoded = [Console]::ReadLine()
    $bytes = [Convert]::FromBase64String($encoded)
    $job = [Text.Encoding]::UTF8.GetString($bytes) | ConvertFrom-Json
    Add-Type -AssemblyName System.Speech

    if ($job.action -eq 'probe') {
        $recognizers = @([System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() |
            ForEach-Object { $_.Culture.Name })
        $voices = @()
        try {
            $speaker = [System.Speech.Synthesis.SpeechSynthesizer]::new()
            try { $voices = @($speaker.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }) }
            finally { $speaker.Dispose() }
        } catch { }
        $grammarType = [Windows.Media.SpeechRecognition.SpeechRecognizer, Windows.Media.SpeechRecognition, ContentType=WindowsRuntime]
        $speakerType = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime]
        $command_languages = @($grammarType::SupportedGrammarLanguages | ForEach-Object { $_.LanguageTag })
        $modern_voices = @($speakerType::AllVoices | ForEach-Object { $_.DisplayName })
        Write-Result @{ recognizers = $recognizers; voices = $voices; command_languages = $command_languages; modern_voices = $modern_voices }
        exit
    }

    if ($job.action -eq 'speak') {
        $stage = 'speaker'
        try {
            $speaker = [System.Speech.Synthesis.SpeechSynthesizer]::new()
            try {
                $voices = @($speaker.GetInstalledVoices() | Where-Object { $_.Enabled })
                if ($voices.Count -eq 0) { throw 'No Windows desktop speech output voice is available.' }
                $english = @($voices | Where-Object { $_.VoiceInfo.Culture.TwoLetterISOLanguageName -eq 'en' })
                if ($english.Count -gt 0 -and $speaker.Voice.Culture.TwoLetterISOLanguageName -ne 'en') {
                    $speaker.SelectVoice($english[0].VoiceInfo.Name)
                }
                $speaker.Rate = -1
                if ($job.output) { $speaker.SetOutputToWaveFile($job.output) }
                $speaker.Speak([string]$job.text)
            } finally { $speaker.Dispose() }
        } catch { Speak-WinRT $job }
        Write-Result @{ ok = $true }
        exit
    }

    $stage = 'recognizer'
    $installed = @([System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers())
    $preferred = @($installed | Where-Object { $_.Culture.Name -eq 'en-US' })
    if ($preferred.Count -eq 0) {
        $preferred = @($installed | Where-Object { $_.Culture.TwoLetterISOLanguageName -eq 'en' })
    }
    if ($preferred.Count -eq 0) {
        $stage = 'microphone'
        $text = Listen-WinRT $job
        Write-Result @{ text = $text }
        exit
    }
    $info = $preferred[0]
    $engine = [System.Speech.Recognition.SpeechRecognitionEngine]::new($info)
    try {
        if ($job.choices -and $info.Culture.TwoLetterISOLanguageName -eq 'en') {
            $choices = [System.Speech.Recognition.Choices]::new([string[]]$job.choices)
            $builder = [System.Speech.Recognition.GrammarBuilder]::new($choices)
            $builder.Culture = $info.Culture
            $grammar = [System.Speech.Recognition.Grammar]::new($builder)
            $engine.LoadGrammar($grammar)
        }
        if (!$job.commands_only -or $engine.Grammars.Count -eq 0) {
            try {
                $engine.LoadGrammar([System.Speech.Recognition.DictationGrammar]::new())
            } catch {
                if ($engine.Grammars.Count -eq 0) { throw }
            }
        }
        $stage = 'microphone'
        if ($job.audio) { $engine.SetInputToWaveFile($job.audio) }
        else { $engine.SetInputToDefaultAudioDevice() }
        $engine.BabbleTimeout = [TimeSpan]::FromSeconds(4)
        $engine.EndSilenceTimeout = [TimeSpan]::FromMilliseconds(550)
        $engine.EndSilenceTimeoutAmbiguous = [TimeSpan]::FromMilliseconds(700)
        $stage = 'recognition'
        $result = $engine.Recognize([TimeSpan]::FromSeconds([double]$job.timeout))
        if ($result -and $result.Confidence -ge 0.28) {
            Write-Result @{ text = $result.Text }
        } else {
            Write-Result @{ text = $null }
        }
    } finally { $engine.Dispose() }
} catch {
    $messages = @{
        load = 'Windows Speech could not start. You can type your reply.'
        speaker = 'Windows could not play speech. Check the output device and voice in Windows Settings.'
        recognizer = 'The Windows speech recognizer could not start. Check the English speech pack in Windows Settings.'
        microphone = 'Windows could not open the microphone. Check Sound input and microphone privacy settings.'
        recognition = 'Speech recognition did not finish. Try the microphone again, or type your reply.'
    }
    Write-Result @{ error = $messages[$stage]; detail = $_.Exception.GetBaseException().Message }
}
"""

_COMMAND = base64.b64encode(_SCRIPT.encode("utf-16-le")).decode("ascii")


class WindowsVoice:
    """Callbacks arrive on a worker thread. A new session supersedes the previous one."""

    def __init__(self):
        self._lock = threading.Lock()
        self._job = 0
        self._process = None
        self._closed = False

    def listen(self, callback, *, timeout=7, choices=(), commands_only=False):
        """Call callback(transcript, error). Silence produces (None, None)."""
        timeout = max(1.0, min(float(timeout), 20.0))
        self._start(
            {"action": "listen", "timeout": timeout, "choices": list(choices),
             "commands_only": commands_only},
            timeout + 14,
            lambda value: callback(
                value["text"] if isinstance(value.get("text"), str) else None,
                value.get("error"),
            ),
        )

    def speak(self, text, callback=None):
        """Speak through Windows, then optionally call callback(error)."""
        self._start(
            {"action": "speak", "text": str(text)[:1500]},
            60,
            (lambda value: callback(value.get("error"))) if callback else None,
        )

    def _cancel_locked(self):
        self._job += 1
        if self._process:
            try:
                self._process.kill()
            except OSError:
                pass
            self._process = None

    def stop(self):
        """Release microphone or stop speech, suppressing unfinished results."""
        with self._lock:
            self._cancel_locked()

    def close(self):
        with self._lock:
            self._closed = True
            self._cancel_locked()

    def _start(self, payload, deadline, callback):
        with self._lock:
            if self._closed:
                return
            self._cancel_locked()
            job = self._job
        threading.Thread(target=self._run, args=(job, payload, deadline, callback), daemon=True).start()

    def _run(self, job, payload, deadline, callback):
        with self._lock:
            if job != self._job:
                return
            self._process = None
            try:
                self._process = process = _open()
            except OSError:
                process = None

        if process is None:
            response = {"error": "Local Windows Speech is unavailable. You can type your reply."}
        else:
            response = _exchange(process, payload, deadline)

        with self._lock:
            if job != self._job:
                return
            self._process = None
        if callback:
            callback(response)


def _open():
    if os.name != "nt":
        raise OSError("Windows Speech requires Windows.")
    windows = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    powershell = windows / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    return subprocess.Popen(
        [str(powershell), "-NoProfile", "-NoLogo", "-NonInteractive", "-STA", "-EncodedCommand", _COMMAND],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def _exchange(process, payload, deadline):
    request = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")) + b"\n"
    try:
        stdout, _stderr = process.communicate(request, timeout=deadline)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        return {"error": "Windows Speech timed out. Try the microphone again, or type your reply."}
    except OSError:
        return {"error": "Windows Speech stopped."}
    for line in reversed(stdout.splitlines()):
        try:
            value = json.loads(base64.b64decode(line, validate=True))
        except (ValueError, UnicodeError):
            continue
        if isinstance(value, dict):
            return value
    return {"error": "Windows Speech did not return a result. You can type your reply."}


if __name__ == "__main__":
    print(json.dumps(_exchange(_open(), {"action": "probe"}, 8), indent=2))
