param(
  [ValidateSet('list','run','status','stop')][string]$Action='list',
  [string]$WorkflowId,
  [string]$RunId,
  [int]$RowIndex=0,
  [string]$RequestId=([guid]::NewGuid().ToString()),
  [switch]$Wait,
  [string]$SettingsPath=(Join-Path $env:APPDATA 'HandNavigate\integration.json')
)
$ErrorActionPreference='Stop'
try {
  if(-not (Test-Path -LiteralPath $SettingsPath -PathType Leaf)){throw 'Open HandNavigate, go to Daily, and turn on its local API first.'}
  $config=Get-Content -LiteralPath $SettingsPath -Raw | ConvertFrom-Json
  if(-not $config.enabled){throw 'Turn on the local API in HandNavigate first.'}
  $endpoint='http://127.0.0.1:'+[int]$config.port+'/v1'
  $headers=@{Authorization='Bearer '+$config.token}
  switch($Action){
    'list' {$result=Invoke-RestMethod -Uri ($endpoint+'/workflows') -Headers $headers}
    'status' {if(-not $RunId){throw 'Supply -RunId.'};$result=Invoke-RestMethod -Uri ($endpoint+'/runs/'+[uri]::EscapeDataString($RunId)) -Headers $headers}
    'stop' {if(-not $RunId){throw 'Supply -RunId.'};$result=Invoke-RestMethod -Method Post -Uri ($endpoint+'/runs/'+[uri]::EscapeDataString($RunId)+'/stop') -Headers $headers -ContentType 'application/json' -Body '{}'}
    'run' {
      if(-not $WorkflowId){throw 'Supply -WorkflowId from the list command.'}
      $body=@{workflowId=$WorkflowId;rowIndex=$RowIndex;requestId=$RequestId}|ConvertTo-Json -Compress
      $result=Invoke-RestMethod -Method Post -Uri ($endpoint+'/runs') -Headers $headers -ContentType 'application/json' -Body $body
      if($Wait){
        $deadline=[DateTime]::UtcNow.AddMinutes(11)
        do {
          $result=Invoke-RestMethod -Uri ($endpoint+'/runs/'+$result.id) -Headers $headers
          if($result.status -ne 'RUNNING'){break}
          if([DateTime]::UtcNow -ge $deadline){throw 'Timed out waiting for the run. Inspect History before retrying.'}
          Start-Sleep -Seconds 2
        } while($true)
      }
    }
  }
  $result|ConvertTo-Json -Depth 12
  if($Wait -and $result.status -ne 'VERIFIED'){exit 1}
} catch {Write-Error $_.Exception.Message;exit 1}
