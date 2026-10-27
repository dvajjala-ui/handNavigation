param([string]$DataFolder=(Join-Path $PSScriptRoot 'runtime\service-live'))
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$workerNode=Get-Command node -ErrorAction Stop
$config=Join-Path $DataFolder 'stickerdock.json'
if(-not (Test-Path -LiteralPath $config)){throw 'Connect this worker to StickerDock first. See SERVICE.md; never paste its secret into Admin.'}
if(-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'node_modules\playwright'))){throw 'Run npm ci once before starting this source checkout.'}
$env:HANDNAVIGATE_DATA=$DataFolder
$env:HANDNAVIGATE_BROWSER_CHANNEL='chrome'
$env:HANDNAVIGATE_HEADLESS='0'
$env:HANDNAVIGATE_INTERACTIVE_WAIT_SECONDS='180'
$env:HANDNAVIGATE_DAILY_LIMIT='20'
& $workerNode.Source (Join-Path $PSScriptRoot 'service\server.cjs')
exit $LASTEXITCODE
