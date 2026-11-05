param([int]$Port=47841,[switch]$NoOpen,[switch]$Headless)
$ErrorActionPreference='Stop'
$AgentRoot=$PSScriptRoot
$AgentPython=Join-Path $AgentRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $AgentPython)) { $AgentPython=Join-Path (Split-Path $AgentRoot -Parent) '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $AgentPython)) { throw 'Run Setup.ps1 first.' }
$AgentOllama=Get-Command ollama -ErrorAction SilentlyContinue
foreach ($AgentCandidate in @((Join-Path $AgentRoot 'runtime\ollama\ollama.exe'),(Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'))) {
    if (-not $AgentOllama -and (Test-Path -LiteralPath $AgentCandidate)) { $AgentOllama=$AgentCandidate }
}
if ($AgentOllama) {
    $AgentConfiguredModels=[Environment]::GetEnvironmentVariable('OLLAMA_MODELS','User')
    if (-not $env:OLLAMA_MODELS) { $env:OLLAMA_MODELS=if ($AgentConfiguredModels) { $AgentConfiguredModels } else { Join-Path $AgentRoot 'runtime\models' } }
    $env:OLLAMA_NO_CLOUD='1'
    try { Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 | Out-Null }
    catch {
        $AgentOllamaExe=if ($AgentOllama -is [string]) { $AgentOllama } else { $AgentOllama.Source }
        Start-Process -FilePath $AgentOllamaExe -ArgumentList 'serve' -WindowStyle Hidden
    }
}
$AgentArgs=@((Join-Path $AgentRoot 'agent.py'))
if ($Headless) { $AgentArgs+='--headless' }
$AgentArgs+=@('serve','--port',"$Port")
if (-not $NoOpen) { $AgentArgs+='--open-ui' }
& $AgentPython @AgentArgs
