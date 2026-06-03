$pair = "dim230880:Dim_230880"
$b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
$h = @{Authorization="Basic $b64"}

Write-Host "=== Stopping bot #3 ==="
$r = Invoke-RestMethod "https://trade.aliterra.space/api/bots/3/stop" -Method POST -Headers $h
$r | ConvertTo-Json

Start-Sleep -Seconds 5

Write-Host ""
Write-Host "=== Status after stop ==="
(Invoke-WebRequest "https://trade.aliterra.space/api/bots" -Headers $h -UseBasicParsing).Content

Start-Sleep -Seconds 2

Write-Host ""
Write-Host "=== Deleting bot #3 (clearing DB) ==="
$r = Invoke-RestMethod "https://trade.aliterra.space/api/bots/3" -Method DELETE -Headers $h
$r | ConvertTo-Json

Write-Host ""
Write-Host "=== Final state ==="
(Invoke-WebRequest "https://trade.aliterra.space/api/bots" -Headers $h -UseBasicParsing).Content
