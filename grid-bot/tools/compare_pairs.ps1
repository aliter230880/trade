$pair = "dim230880:Dim_230880"
$b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
$h = @{Authorization="Basic $b64"}

$pairs = @("DOGE/USDT","XRP/USDT","LINK/USDT","AVAX/USDT","SOL/USDT","TON/USDT","ADA/USDT","TRX/USDT")

Write-Host ("{0,-12} {1,12} {2,8} {3,10} {4,8}" -f "Pair","Price","Span+-","Hourly%","Step%")
Write-Host ("-" * 56)

foreach ($sym in $pairs) {
    try {
        $r = Invoke-RestMethod "https://trade.aliterra.space/api/auto-range?key_id=3&symbol=$sym&days=7&levels_target=10" -Headers $h
        Write-Host ("{0,-12} {1,12:N4} {2,8:N2} {3,10:N3} {4,8:N3}" -f $sym, $r.current_price, $r.span_pct, $r.avg_hourly_range_pct, $r.step_pct)
    } catch {
        Write-Host "$sym : ERROR"
    }
}
