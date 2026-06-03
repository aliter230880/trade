$pair = "dim230880:Dim_230880"
$b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
$h = @{Authorization="Basic $b64"}

Write-Host "=== ORDERS for Bot 3 ==="
$orders = (Invoke-RestMethod "https://trade.aliterra.space/api/bots/3/orders?limit=20" -Headers $h).orders
$orders | Select-Object id, side, price, amount, status, level_index | Sort-Object price -Descending | Format-Table

Write-Host ""
Write-Host "=== TICKER ==="
Invoke-RestMethod "https://trade.aliterra.space/api/ticker?key_id=3&symbol=DOGE/USDT" -Headers $h | ConvertTo-Json
