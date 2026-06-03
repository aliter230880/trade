// Grid bot - frontend logic

const api = (path, options = {}) =>
  fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  }).then(async (r) => {
    const text = await r.text();
    let data;
    try { data = JSON.parse(text); } catch { data = { detail: text }; }
    if (!r.ok) throw new Error(data.detail || r.statusText);
    return data;
  });

async function loadExchanges() {
  const { exchanges } = await api("/exchanges");
  const sel = document.getElementById("exchange-select");
  sel.innerHTML = exchanges
    .map((e) => `<option value="${e}">${e}</option>`)
    .join("");
}

async function loadKeys() {
  const keys = await api("/keys");
  const tbody = document.querySelector("#keys-table tbody");
  if (!keys.length) {
    tbody.innerHTML = `<tr><td colspan="7" style="color:#8a93a6">Ключей пока нет</td></tr>`;
    return;
  }
  tbody.innerHTML = keys
    .map(
      (k) => `
      <tr data-id="${k.id}">
        <td>${k.id}</td>
        <td>${k.exchange}</td>
        <td>${k.label}</td>
        <td>${k.testnet ? "✅" : "—"}</td>
        <td><code>${k.masked_key}</code></td>
        <td class="balance">…</td>
        <td>
          <button class="danger" onclick="deleteKey(${k.id})">×</button>
        </td>
      </tr>`
    )
    .join("");

  for (const k of keys) {
    api(`/keys/${k.id}/status`)
      .then((s) => {
        const cell = document.querySelector(`tr[data-id="${k.id}"] .balance`);
        if (!cell) return;
        if (s.connected) {
          cell.innerHTML = `<span class="status-ok">${
            s.balance_usdt != null ? s.balance_usdt.toFixed(2) : "0 (пополни demo)"
          }</span>`;
        } else {
          cell.innerHTML = `<span class="status-err" title="${s.error || ""}">ошибка</span>`;
        }
      })
      .catch(() => {});
  }
}

async function deleteKey(id) {
  if (!confirm(`Удалить ключ #${id}?`)) return;
  await api(`/keys/${id}`, { method: "DELETE" });
  loadKeys();
}

document.getElementById("key-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const payload = {
    exchange: f.exchange.value,
    label: f.label.value || "default",
    testnet: f.testnet.checked,
    api_key: f.api_key.value.trim(),
    api_secret: f.api_secret.value.trim(),
    passphrase: f.passphrase.value.trim(),
  };
  try {
    await api("/keys", { method: "POST", body: JSON.stringify(payload) });
    f.api_key.value = "";
    f.api_secret.value = "";
    f.passphrase.value = "";
    loadKeys();
  } catch (err) {
    alert("Ошибка: " + err.message);
  }
});

document.getElementById("ticker-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const url = `/ticker?key_id=${f.key_id.value}&symbol=${encodeURIComponent(
    f.symbol.value
  )}`;
  const out = document.getElementById("ticker-result");
  out.textContent = "Загрузка…";
  try {
    const t = await api(url);
    out.textContent = JSON.stringify(t, null, 2);
  } catch (err) {
    out.textContent = "Ошибка: " + err.message;
  }
});

// -------- Bots --------

document.getElementById("bot-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const payload = {
    api_key_id: Number(f.api_key_id.value),
    symbol: f.symbol.value.trim(),
    lower_price: Number(f.lower_price.value),
    upper_price: Number(f.upper_price.value),
    grid_levels: Number(f.grid_levels.value),
    order_size_quote: Number(f.order_size_quote.value),
  };
  if (f.stop_loss_pct && f.stop_loss_pct.value.trim() !== "") {
    payload.stop_loss_pct = Number(f.stop_loss_pct.value);
  }
  if (payload.upper_price <= payload.lower_price) {
    alert("Верхняя цена должна быть больше нижней");
    return;
  }
  try {
    await api("/bots", { method: "POST", body: JSON.stringify(payload) });
    loadBots();
  } catch (err) {
    alert("Ошибка: " + err.message);
  }
});

async function loadBots() {
  const bots = await api("/bots");
  const tbody = document.querySelector("#bots-table tbody");
  if (!bots.length) {
    tbody.innerHTML = `<tr><td colspan="11" style="color:#8a93a6">Ботов пока нет</td></tr>`;
    return;
  }
  tbody.innerHTML = bots
    .map((b) => {
      const isRunning = b.status === "running";
      const startStop = isRunning
        ? `<button class="warn" onclick="stopBot(${b.id})">Stop</button>`
        : `<button onclick="startBot(${b.id})">Start</button>`;
      const statusCls =
        b.status === "running" ? "status-ok" :
        b.status === "error" ? "status-err" : "";
      return `
        <tr>
          <td>${b.id}</td>
          <td>${b.exchange}</td>
          <td>${b.symbol}</td>
          <td>${b.lower_price} – ${b.upper_price}</td>
          <td>${b.grid_levels}</td>
          <td>${b.order_size_quote} USDT</td>
          <td><span class="${statusCls}">${b.status}</span></td>
          <td>${b.open_orders}</td>
          <td>${b.filled_orders}</td>
          <td>${b.realized_pnl.toFixed(4)}</td>
          <td>
            ${startStop}
            <button class="ghost" onclick="showTrades(${b.id})" title="История сделок">📊</button>
            <button class="danger" onclick="deleteBot(${b.id})">×</button>
          </td>
        </tr>`;
    })
    .join("");
}

async function startBot(id) {
  try {
    await api(`/bots/${id}/start`, { method: "POST" });
    loadBots();
  } catch (err) {
    alert("Ошибка старта: " + err.message);
  }
}

async function stopBot(id) {
  if (!confirm(`Остановить бот #${id} и снять все ордера?`)) return;
  try {
    await api(`/bots/${id}/stop`, { method: "POST" });
    loadBots();
  } catch (err) {
    alert("Ошибка стоп: " + err.message);
  }
}

async function deleteBot(id) {
  if (!confirm(`Удалить бот #${id} (ордера будут сняты)?`)) return;
  try {
    await api(`/bots/${id}`, { method: "DELETE" });
    loadBots();
  } catch (err) {
    alert("Ошибка: " + err.message);
  }
}

(async () => {
  try {
    const h = await api("/health");
    document.getElementById("version-tag").textContent = `v${h.version}`;
  } catch {}
  await loadExchanges();
  await loadKeys();
  await loadBots();
  await loadTelegramStatus();
  // авто-обновление таблицы ботов раз в 5 секунд
  setInterval(loadBots, 5000);
})();

// -------- Auto range --------
async function autoFillRange() {
  const f = document.getElementById("bot-form");
  const info = document.getElementById("auto-range-info");
  const keyId = f.api_key_id.value;
  const symbol = f.symbol.value.trim();
  if (!keyId || !symbol) {
    alert("Сначала заполни Ключ ID и Символ");
    return;
  }
  info.textContent = "Считаю волатильность…";
  try {
    const r = await api(
      `/auto-range?key_id=${keyId}&symbol=${encodeURIComponent(symbol)}`
    );
    f.lower_price.value = r.lower_price;
    f.upper_price.value = r.upper_price;
    f.grid_levels.value = r.grid_levels;
    info.innerHTML =
      `Цена: <b>${r.current_price}</b>, коридор ±${r.span_pct}%, ` +
      `шаг ~${r.step_pct}% (по ${r.candles_used} часовым свечам)`;
  } catch (err) {
    info.textContent = "Ошибка: " + err.message;
  }
}

// -------- Trades history --------
async function showTrades(botId) {
  const pane = document.getElementById("trades-pane");
  if (pane.dataset.bot === String(botId)) {
    pane.innerHTML = "";
    pane.dataset.bot = "";
    return;
  }
  pane.dataset.bot = String(botId);
  pane.innerHTML = `<div class="trades-card">Загрузка…</div>`;
  try {
    const r = await api(`/bots/${botId}/trades?limit=200`);
    if (!r.trades.length) {
      pane.innerHTML = `<div class="trades-card">У бота #${botId} пока нет закрытых сделок.</div>`;
      return;
    }
    const rows = r.trades.map((t) => {
      const cls = t.realized_pnl > 0 ? "pnl-pos" : t.realized_pnl < 0 ? "pnl-neg" : "";
      return `<tr>
        <td>${t.id}</td>
        <td>${t.side}</td>
        <td>${(t.fill_price ?? t.price).toFixed(4)}</td>
        <td>${(t.fill_qty ?? t.amount).toFixed(6)}</td>
        <td>${(t.fee ?? 0).toFixed(4)} ${t.fee_coin || ""}</td>
        <td class="${cls}">${t.realized_pnl ? t.realized_pnl.toFixed(4) : "—"}</td>
        <td>${t.filled_at ? t.filled_at.replace("T", " ").slice(0, 19) : ""}</td>
      </tr>`;
    }).join("");
    const total = r.trades.reduce((s, t) => s + (t.realized_pnl || 0), 0);
    pane.innerHTML = `
      <div class="trades-card">
        <h4>История сделок бота #${botId} (всего ${r.trades.length}, итого P&L: ${total.toFixed(4)} USDT)</h4>
        <table>
          <thead><tr><th>ID</th><th>Side</th><th>Цена</th><th>Кол-во</th>
                     <th>Комиссия</th><th>P&L</th><th>Время</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  } catch (err) {
    pane.innerHTML = `<div class="trades-card">Ошибка: ${err.message}</div>`;
  }
}

// -------- Telegram --------
async function loadTelegramStatus() {
  try {
    const r = await api("/notifier/status");
    document.getElementById("tg-status").textContent = r.telegram_configured
      ? "✅ Telegram настроен"
      : "⚠️ Telegram не настроен (заполни .env и перезапусти сервер)";
  } catch {}
}

async function testTelegram() {
  try {
    await api("/notifier/test", { method: "POST" });
    alert("Сообщение отправлено в Telegram");
  } catch (err) {
    alert("Ошибка: " + err.message);
  }
}


// -------- Backtest --------

function copyParamsFromCreate() {
  const src = document.getElementById("bot-form");
  const dst = document.getElementById("backtest-form");
  dst.symbol.value = src.symbol.value;
  dst.lower_price.value = src.lower_price.value;
  dst.upper_price.value = src.upper_price.value;
  dst.grid_levels.value = src.grid_levels.value;
  dst.order_size_quote.value = src.order_size_quote.value;
}

document.getElementById("backtest-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const out = document.getElementById("backtest-result");
  out.innerHTML = `<div class="trades-card">Считаю… (может занять 10-30 сек)</div>`;
  const payload = {
    key_id: Number(f.key_id.value),
    symbol: f.symbol.value.trim(),
    lower_price: Number(f.lower_price.value),
    upper_price: Number(f.upper_price.value),
    grid_levels: Number(f.grid_levels.value),
    order_size_quote: Number(f.order_size_quote.value),
    days: Number(f.days.value),
    timeframe: f.timeframe.value,
    fee_rate: Number(f.fee_rate.value),
  };
  try {
    const r = await api("/backtest", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderBacktest(r);
  } catch (err) {
    out.innerHTML = `<div class="trades-card">Ошибка: ${err.message}</div>`;
  }
});

function renderBacktest(r) {
  const out = document.getElementById("backtest-result");
  const pnlCls = r.realized_pnl_usdt > 0 ? "pnl-pos" :
                 r.realized_pnl_usdt < 0 ? "pnl-neg" : "";
  const monthlyCls = r.estimated_monthly_pct > 0 ? "pnl-pos" :
                     r.estimated_monthly_pct < 0 ? "pnl-neg" : "";

  // Текстовый ASCII-график equity
  const curve = r.equity_curve || [];
  const eqs = curve.map(p => p.equity);
  const minE = Math.min(...eqs);
  const maxE = Math.max(...eqs);
  const range = maxE - minE || 1;
  const chartH = 8;
  const chartLines = [];
  for (let row = chartH; row >= 0; row--) {
    let line = "";
    for (const p of curve) {
      const y = Math.round(((p.equity - minE) / range) * chartH);
      line += y === row ? "●" : " ";
    }
    chartLines.push(line);
  }

  out.innerHTML = `
    <div class="trades-card">
      <h4>Результат: ${r.symbol}, ${r.days} дней (${r.timeframe})</h4>
      <div class="bt-stats">
        <div><span>Цена:</span><b>${r.start_price} → ${r.end_price}
              (${r.price_change_pct >= 0 ? "+" : ""}${r.price_change_pct.toFixed(2)}%)</b></div>
        <div><span>Сделок:</span><b>${r.total_trades} (закрытых пар: ${r.matched_pairs})</b></div>
        <div><span>Realized P&L:</span><b class="${pnlCls}">${r.realized_pnl_usdt >= 0 ? "+" : ""}${r.realized_pnl_usdt} USDT</b></div>
        <div><span>Комиссии:</span><b>${r.fees_paid_usdt} USDT</b></div>
        <div><span>% от капитала:</span><b class="${pnlCls}">${r.pnl_pct_on_capital >= 0 ? "+" : ""}${r.pnl_pct_on_capital}%</b></div>
        <div><span>В пересчёте на месяц:</span><b class="${monthlyCls}">${r.estimated_monthly_pct >= 0 ? "+" : ""}${r.estimated_monthly_pct}%</b></div>
        <div><span>Max drawdown:</span><b>${r.max_drawdown_pct}%</b></div>
        <div><span>Свечей:</span><b>${r.candles_used}</b></div>
      </div>
      <h4>Equity curve</h4>
      <pre class="chart">${chartLines.join("\n")}</pre>
      <details>
        <summary>Последние сделки (${(r.trades || []).length})</summary>
        <table style="margin-top:8px">
          <thead><tr><th>Side</th><th>Цена</th><th>Кол-во</th><th>Комиссия</th><th>P&L</th></tr></thead>
          <tbody>${(r.trades || []).slice(-30).reverse().map(t => `
            <tr>
              <td>${t.side}</td>
              <td>${t.price.toFixed(4)}</td>
              <td>${t.qty.toFixed(6)}</td>
              <td>${t.fee.toFixed(4)}</td>
              <td class="${t.pnl > 0 ? "pnl-pos" : t.pnl < 0 ? "pnl-neg" : ""}">${t.pnl ? t.pnl.toFixed(4) : "—"}</td>
            </tr>`).join("")}
          </tbody>
        </table>
      </details>
    </div>
  `;
}
