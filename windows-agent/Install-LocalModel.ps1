param(
    [string]$Model='qwen3.5:4b',
    [switch]$RepairDownloader
)
$ErrorActionPreference='Stop'
$AgentRoot=$PSScriptRoot
$AgentRuntime=Join-Path $AgentRoot 'runtime'
$AgentInstall=Join-Path $AgentRuntime 'ollama'
$AgentModels=Join-Path $AgentRuntime 'models'
New-Item -ItemType Directory -Force -Path $AgentRuntime,$AgentModels | Out-Null
$AgentOllama=$null
$AgentCandidates=@((Join-Path $AgentInstall 'ollama.exe'),(Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'))
$AgentCommand=Get-Command ollama -ErrorAction SilentlyContinue
if ($AgentCommand) { $AgentCandidates=@($AgentCommand.Source)+$AgentCandidates }
foreach ($AgentCandidate in $AgentCandidates) { if (Test-Path -LiteralPath $AgentCandidate) { $AgentOllama=$AgentCandidate; break } }
if (-not $AgentOllama) {
    # A new installation inherits a durable per-user model directory on this drive.
    # Preserve a model-directory preference if the user already configured one.
    $AgentConfiguredModels=[Environment]::GetEnvironmentVariable('OLLAMA_MODELS','User')
    if (-not $AgentConfiguredModels) {
        [Environment]::SetEnvironmentVariable('OLLAMA_MODELS',$AgentModels,'User')
        $env:OLLAMA_MODELS=$AgentModels
    }
    else { $env:OLLAMA_MODELS=$AgentConfiguredModels }
    $env:OLLAMA_NO_CLOUD='1'
    $AgentSettings=$null
    $AgentOriginal=$null
    $AgentHadSettings=$false
    try {
        if ($RepairDownloader) {
            $AgentExport=winget settings export | ConvertFrom-Json
            if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect WinGet settings.' }
            $AgentSettings=$AgentExport.userSettingsFile
            $AgentHadSettings=Test-Path -LiteralPath $AgentSettings
            $AgentConfig=[pscustomobject]@{}
            if ($AgentHadSettings) {
                $AgentOriginal=[IO.File]::ReadAllBytes($AgentSettings)
                # Do not overwrite a commented/custom JSON file we cannot parse.
                $AgentConfig=Get-Content -LiteralPath $AgentSettings -Raw | ConvertFrom-Json
            }
            if (-not $AgentConfig.PSObject.Properties['network']) { $AgentConfig | Add-Member -NotePropertyName network -NotePropertyValue ([pscustomobject]@{}) }
            $AgentConfig.network | Add-Member -NotePropertyName downloader -NotePropertyValue 'wininet' -Force
            $AgentConfig | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $AgentSettings -Encoding utf8
        }
        & winget install --id Ollama.Ollama --exact --source winget --scope user --location $AgentInstall --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
        if ($LASTEXITCODE -ne 0) { throw "Ollama package installation failed ($LASTEXITCODE)." }
    }
    finally {
        if ($AgentSettings) {
            if ($AgentHadSettings) { [IO.File]::WriteAllBytes($AgentSettings,$AgentOriginal) }
            elseif (Test-Path -LiteralPath $AgentSettings) { Remove-Item -LiteralPath $AgentSettings }
        }
    }
    foreach ($AgentCandidate in $AgentCandidates) { if (Test-Path -LiteralPath $AgentCandidate) { $AgentOllama=$AgentCandidate; break } }
}
if (-not $AgentOllama) { throw 'Ollama executable was not found after installation.' }
$AgentConfiguredModels=[Environment]::GetEnvironmentVariable('OLLAMA_MODELS','User')
$env:OLLAMA_MODELS=if ($AgentConfiguredModels) { $AgentConfiguredModels } else { $AgentModels }
$env:OLLAMA_NO_CLOUD='1'
try { Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 3 | Out-Null }
catch {
    Start-Process -FilePath $AgentOllama -ArgumentList 'serve' -WindowStyle Hidden -RedirectStandardOutput (Join-Path $AgentRuntime 'ollama.stdout.log') -RedirectStandardError (Join-Path $AgentRuntime 'ollama.stderr.log')
    $AgentReady=$false
    for ($AgentAttempt=0; $AgentAttempt -lt 30; $AgentAttempt++) {
        Start-Sleep -Milliseconds 500
        try { Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2 | Out-Null; $AgentReady=$true; break }
        catch {}
    }
    if (-not $AgentReady) { throw 'Ollama did not become ready. Inspect runtime/ollama.stderr.log.' }
}
@{executable=$AgentOllama;models=$env:OLLAMA_MODELS;endpoint='http://127.0.0.1:11434';model=$Model} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $AgentRuntime 'local-model.json') -Encoding utf8
& $AgentOllama pull $Model
if ($LASTEXITCODE -ne 0) { throw 'Local model download failed; rerun to resume it.' }
Write-Host "Local model ready: $Model"
