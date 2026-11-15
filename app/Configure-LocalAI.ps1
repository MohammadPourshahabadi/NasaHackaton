ï»¿param([switch]$SkipPull)
$ErrorActionPreference = 'Stop'
$root = Join-Path $PSScriptRoot 'LocalModels'
if (-not (Test-Path -LiteralPath $root)) {
    $parent = Join-Path (Split-Path $PSScriptRoot -Parent) 'LocalModels'
    if (Test-Path -LiteralPath $parent) { $root = $parent }
}
$portable = Get-ChildItem -LiteralPath (Join-Path $root 'Ollama') -Filter ollama.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
$installed = Join-Path $env:LOCALAPPDATA 'Programs/Ollama/ollama.exe'
$command = Get-Command ollama.exe -ErrorAction SilentlyContinue
$exe = if ($portable) { $portable.FullName } elseif (Test-Path -LiteralPath $installed) { $installed } elseif ($command) { $command.Source }
if (!$exe) { throw 'Ollama is missing. Install Ollama or extract the official portable Windows runtime into LocalModels/Ollama.' }
$env:OLLAMA_MODELS = Join-Path $root 'weights'
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NO_CLOUD = '1'
New-Item -ItemType Directory -Path $env:OLLAMA_MODELS -Force | Out-Null
try {
    Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 | Out-Null
} catch {
    Start-Process -FilePath $exe -ArgumentList 'serve' -WindowStyle Hidden
    $ready = $false
    for ($i = 0; $i -lt 15; $i++) {
        try {
            Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 | Out-Null
            $ready = $true
            break
        } catch { Start-Sleep -Seconds 1 }
    }
    if (!$ready) { throw 'Ollama did not start on 127.0.0.1:11434.' }
    if (!$SkipPull) {
        foreach ($model in 'llama3.2:3b', 'gemma3:4b') {
            & $exe pull $model
            if ($LASTEXITCODE) { throw "$model download failed ($LASTEXITCODE)." }
        }
    }
    return
}
$tags = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags'
$missing = @('llama3.2:3b', 'gemma3:4b') | Where-Object { $tags.models.name -notcontains $_ }
if (!$missing) { Write-Host 'Llama 3.2 (text) and Gemma 3 (images) are ready.' }
elseif (!$SkipPull) { throw 'An existing Ollama service is running. Quit it first so this script can place the weights on D:.' }
