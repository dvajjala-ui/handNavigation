$ErrorActionPreference='Stop'
$AgentRoot=$PSScriptRoot
$AgentPython=Join-Path $AgentRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $AgentPython)) { $AgentPython=Join-Path (Split-Path $AgentRoot -Parent) '.venv\Scripts\python.exe' }
& $AgentPython -m pip install pyinstaller==6.16.0
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller setup failed.' }
Push-Location $AgentRoot
try {
    # Some managed Python runtimes load an extra CA policy file from beside ssl.py.
    # Preserve that runtime policy in the package; never disable TLS verification.
    $AgentExtraData=@()
    $AgentTlsPolicy=& $AgentPython -c "import pathlib,ssl; print(pathlib.Path(ssl.__file__).with_name('codex-rejected-cas.pem'))"
    if (Test-Path -LiteralPath $AgentTlsPolicy) { $AgentExtraData+=@('--add-data',($AgentTlsPolicy+';.')) }
    & $AgentPython -m PyInstaller --noconfirm --onedir --console --name HandNavigateAgent --paths $AgentRoot --paths (Split-Path $AgentRoot -Parent) --collect-all playwright --add-data ((Join-Path $AgentRoot 'ui')+';ui') @AgentExtraData --distpath (Join-Path $AgentRoot 'dist') --workpath (Join-Path $AgentRoot 'runtime\build') --specpath (Join-Path $AgentRoot 'runtime') (Join-Path $AgentRoot 'agent.py')
    if ($LASTEXITCODE -ne 0) { throw 'Windows package build failed.' }
}
finally { Pop-Location }
Write-Host 'Built dist\HandNavigateAgent\HandNavigateAgent.exe. Keep the entire folder together. Installed Chrome and Ollama remain prerequisites.'
