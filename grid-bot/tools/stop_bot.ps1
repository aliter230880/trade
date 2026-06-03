$pair = "dim230880:Dim_230880"
$b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
$h = @{Authorization="Basic $b64"}

Write-Host "Stopping bot #2..."
$r = Invoke-RestMethod "https://trade.aliterra.space/api/bots/2/stop" -Method POST -Headers $h
$r | ConvertTo-Json

Start-Sleep -Seconds 5

Write-Host ""
Write-Host "=== Bots after stop ==="
Invoke-RestMethod "https://trade.aliterra.space/api/bots" -Headers $h | ConvertTo-Json -Depth 5
