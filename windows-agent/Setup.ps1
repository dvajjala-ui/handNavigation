param([switch]$InstallOllama,[string]$Model='qwen3.5:4b',[switch]$RepairDownloader)
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
$AgentOllama=Get-Command ollama -ErrorAction SilentlyContinue
foreach ($AgentCandidate in @((Join-Path $AgentRoot 'runtime\ollama\ollama.exe'),(Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'))) {
    if (-not $AgentOllama -and (Test-Path -LiteralPath $AgentCandidate)) { $AgentOllama=$AgentCandidate }
}
if ($InstallOllama -or $AgentOllama) {
    & (Join-Path $AgentRoot 'Install-LocalModel.ps1') -Model $Model -RepairDownloader:$RepairDownloader
}
else { Write-Host 'Ollama is not installed. Rerun with -InstallOllama, or install it from https://ollama.com/download/windows.' }
Write-Host 'Setup ready. Run .\Start.ps1, then save your folder/website permissions once in Setup.'
