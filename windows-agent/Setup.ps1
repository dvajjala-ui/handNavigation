param([switch]$InstallOllama,[string]$Model='qwen3.5:4b')
$ErrorActionPreference='Stop'
$AgentRoot=$PSScriptRoot
$AgentPython=Join-Path $AgentRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $AgentPython)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.12 -m venv (Join-Path $AgentRoot '.venv')
        if ($LASTEXITCODE -ne 0) { & py -3 -m venv (Join-Path $AgentRoot '.venv') }
    }
    else { & python -m venv (Join-Path $AgentRoot '.venv') }
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 or newer, then rerun Setup.ps1.' }
}
& $AgentPython -m pip install -r (Join-Path $AgentRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
if ($InstallOllama) {
    & winget install --id Ollama.Ollama --exact --source winget --scope user --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw 'Ollama installation failed. See the official Windows installation guide.' }
}
$AgentOllama=Get-Command ollama -ErrorAction SilentlyContinue
if (-not $AgentOllama) {
    $AgentOllamaPath=Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
    if (Test-Path -LiteralPath $AgentOllamaPath) { $AgentOllama=$AgentOllamaPath }
}
if ($AgentOllama) {
    # Keep large model files on the workspace drive. This launcher uses the same path.
    $env:OLLAMA_MODELS=Join-Path $AgentRoot 'runtime\models'
    $env:OLLAMA_NO_CLOUD='1'
    $AgentOllamaExe=if ($AgentOllama -is [string]) { $AgentOllama } else { $AgentOllama.Source }
    try { Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 | Out-Null }
    catch { Start-Process -FilePath $AgentOllamaExe -ArgumentList 'serve' -WindowStyle Hidden; Start-Sleep -Seconds 3 }
    & $AgentOllamaExe pull $Model
    if ($LASTEXITCODE -ne 0) { throw 'Local model download failed.' }
}
else { Write-Host 'Ollama is not installed. Rerun with -InstallOllama, or install it from https://ollama.com/download/windows.' }
Write-Host 'Setup ready. Run .\Start.ps1, then save your folder/website permissions once in Setup.'
