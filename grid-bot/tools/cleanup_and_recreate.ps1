$pair = "dim230880:Dim_230880"
$b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
$h = @{Authorization="Basic $b64"; "Content-Type"="application/json"}

Write-Host "=== Stopping & deleting all bots ==="
$bots = Invoke-RestMethod "https://trade.aliterra.space/api/bots" -Headers $h
foreach ($b in $bots) {
    Write-Host "Bot $($b.id) status=$($b.status), open=$($b.open_orders) -> deleting..."
    try {
        Invoke-RestMethod "https://trade.aliterra.space/api/bots/$($b.id)/stop" -Method POST -Headers $h | Out-Null
    } catch {}
    Start-Sleep -Seconds 2
    try {
        Invoke-RestMethod "https://trade.aliterra.space/api/bots/$($b.id)" -Method DELETE -Headers $h | Out-Null
    } catch {}
}

Start-Sleep -Seconds 3
Write-Host ""
Write-Host "=== Bots after cleanup ==="
(Invoke-WebRequest "https://trade.aliterra.space/api/bots" -Headers $h -UseBasicParsing).Content
