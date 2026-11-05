param([switch]$Remove)
$ErrorActionPreference='Stop'
$AgentStartup=[Environment]::GetFolderPath('Startup')
$AgentShortcut=Join-Path $AgentStartup 'HandNavigate Windows core.lnk'
if ($Remove) { if (Test-Path -LiteralPath $AgentShortcut) { Remove-Item -LiteralPath $AgentShortcut }; return }
$AgentShell=New-Object -ComObject WScript.Shell
$AgentLink=$AgentShell.CreateShortcut($AgentShortcut)
$AgentLink.TargetPath=(Get-Command powershell.exe).Source
$AgentLink.Arguments='-NoProfile -File "'+(Join-Path $PSScriptRoot 'Start.ps1')+'" -NoOpen'
$AgentLink.WorkingDirectory=$PSScriptRoot
$AgentLink.WindowStyle=7
$AgentLink.Save()
Write-Host 'Installed current-user login startup. The PC must be awake and this user signed in. Remove with -Remove.'
