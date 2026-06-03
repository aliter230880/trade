$pair = "dim230880:Dim_230880"
$b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
$h = @{Authorization="Basic $b64"; "Content-Type"="application/json"}

# AVAX cena ~$8.975, узкая сетка +-3% от цены
$body = @{
    api_key_id = 3
    symbol = "AVAX/USDT"
    lower_price = 8.71
    upper_price = 9.24
    grid_levels = 10
    order_size_quote = 4.5
    stop_loss_pct = 15
} | ConvertTo-Json

Write-Host "=== Creating bot ==="
Write-Host $body
$r = Invoke-RestMethod "https://trade.aliterra.space/api/bots" -Method POST -Headers $h -Body $body
$r | ConvertTo-Json
$botId = $r.id

Write-Host ""
Write-Host "=== Starting bot $botId ==="
$start = Invoke-RestMethod "https://trade.aliterra.space/api/bots/$botId/start" -Method POST -Headers $h
$start | ConvertTo-Json

Start-Sleep -Seconds 8

Write-Host ""
Write-Host "=== Status ==="
(Invoke-WebRequest "https://trade.aliterra.space/api/bots" -Headers $h -UseBasicParsing).Content

Write-Host ""
Write-Host "=== Orders ==="
$orders = (Invoke-RestMethod "https://trade.aliterra.space/api/bots/$botId/orders?limit=20" -Headers $h).orders | Where-Object { $_.status -eq "open" }
Write-Host "Open: $($orders.Count)"
$orders | Select-Object id, side, price, amount, level_index | Sort-Object price -Descending | Format-Table
