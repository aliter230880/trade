$pair = "dim230880:Dim_230880"
$b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
$h = @{Authorization="Basic $b64"}

Write-Host "=== BOTS ==="
$bots = Invoke-RestMethod "https://trade.aliterra.space/api/bots" -Headers $h
$bots | ConvertTo-Json -Depth 5

Write-Host ""
Write-Host "=== TRADES ==="
foreach ($b in $bots) {
    Write-Host "--- Bot $($b.id) ---"
    $trades = (Invoke-RestMethod "https://trade.aliterra.space/api/bots/$($b.id)/trades?limit=100" -Headers $h).trades
    Write-Host "Total filled: $($trades.Count)"
    if ($trades.Count -gt 0) {
        $totalPnl = ($trades | Measure-Object -Property realized_pnl -Sum).Sum
        Write-Host "Sum realized_pnl: $totalPnl"
        $trades | Select-Object id, side, fill_price, fill_qty, fee, realized_pnl, filled_at | Format-Table
    }
}
