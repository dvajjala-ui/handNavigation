param([switch]$StartAtLogin,[switch]$StartNow)
$ErrorActionPreference='Stop'
$script=Join-Path $PSScriptRoot 'Start-StickerDock-Worker.ps1'
$powershell=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$workerShell=New-Object -ComObject WScript.Shell
function New-WorkerShortcut([string]$folder){
 $shortcut=$workerShell.CreateShortcut((Join-Path $folder 'HandNavigate StickerDock worker.lnk'))
 $shortcut.TargetPath=$powershell
 $shortcut.Arguments='-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "'+$script+'"'
 $shortcut.WorkingDirectory=$PSScriptRoot
 $shortcut.WindowStyle=7
 $shortcut.Description='Connect HandNavigate to StickerDock collection requests. Requires this PC to stay awake.'
 $shortcut.Save()
}
New-WorkerShortcut ([Environment]::GetFolderPath('Desktop'))
if($StartAtLogin){New-WorkerShortcut ([Environment]::GetFolderPath('Startup'))}
if($StartNow){
 $folder=Join-Path $PSScriptRoot 'runtime\service-live'
 $lock=Join-Path $folder 'worker.lock'
 $running=$false
 if(Test-Path -LiteralPath $lock){$workerPid=(Get-Content -LiteralPath $lock -Raw|ConvertFrom-Json).pid;$running=$null -ne (Get-Process -Id $workerPid -ErrorAction SilentlyContinue)}
 if(-not $running){Start-Process -FilePath $powershell -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$script+'"')) -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $folder 'worker-output.log') -RedirectStandardError (Join-Path $folder 'worker-errors.log')}
}
Write-Output 'Worker shortcut ready. Daily collection requires this PC to remain awake and signed in.'
