// ApexTrade Frontend Controller
let currentStatus = null;
let currentWatchlist = [];
let selectedSignalSymbol = null;
let pollInterval = null;

// Initialization on DOM Load
document.addEventListener("DOMContentLoaded", () => {
    fetchStatus();
    fetchWatchlist();
    fetchLogs();
    fetchPositions();
    fetchOrders();

    // Start live polling every 3.5 seconds
    pollInterval = setInterval(() => {
        fetchStatus(true);
        fetchLogs(true);
    }, 3500);

    // Watchlist refreshes slightly less frequently
    setInterval(() => {
        fetchWatchlist(true);
    }, 8000);
});

// --- Tab Switching ---
function switchTab(tabId) {
    document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(content => content.classList.remove("active"));

    const targetBtn = document.getElementById(`tab-btn-${tabId}`);
    const targetContent = document.getElementById(`tab-${tabId}`);

    if (targetBtn) targetBtn.classList.add("active");
    if (targetContent) targetContent.classList.add("active");

    if (tabId === "positions") fetchPositions();
    if (tabId === "orders") fetchOrders();
}

// --- Status & KPIs ---
async function fetchStatus(isBackground = false) {
    try {
        const res = await fetch("/api/status");
        if (!res.ok) return;
        const data = await res.json();
        currentStatus = data;
        renderStatus(data);
    } catch (e) {
        console.error("Error fetching status:", e);
    }
}

function renderStatus(data) {
    const acc = data.account || {};

    // 1. Header Engine Status
    const statusChip = document.getElementById("engine-status-chip");
    const statusText = document.getElementById("engine-status-text");
    const toggleBtn = document.getElementById("btn-toggle-engine");
    const toggleIcon = document.getElementById("toggle-engine-icon");
    const toggleLabel = document.getElementById("toggle-engine-label");

    if (data.is_running) {
        statusChip.className = "status-chip running";
        statusText.textContent = "AUTONOM MOTOR AKTIV";
        toggleBtn.className = "btn btn-primary btn-stop";
        toggleIcon.textContent = "⏸";
        toggleLabel.textContent = "Stoppa Bot";
    } else {
        statusChip.className = "status-chip stopped";
        statusText.textContent = "MOTOR PAUSAD";
        toggleBtn.className = "btn btn-primary";
        toggleIcon.textContent = "▶";
        toggleLabel.textContent = "Starta Bot";
    }

    // 2. Market Clock & Mode Badge
    const clockDot = document.getElementById("market-clock-dot");
    const clockText = document.getElementById("market-clock-text");
    if (data.clock && clockText) {
        if (data.clock.is_open) {
            clockDot.style.background = "#10b981";
            clockDot.style.boxShadow = "0 0 10px #10b981";
            clockText.textContent = "Wall Street: ÖPPEN";
        } else {
            clockDot.style.background = "#f43f5e";
            clockDot.style.boxShadow = "none";
            clockText.textContent = "Wall Street: Stängd (15:30)";
        }
    }

    const modeText = document.getElementById("mode-text");
    const modeBadge = document.getElementById("mode-badge");

    if (data.mode === "paper") {
        modeText.textContent = "Alpaca Paper (Sandbox)";
        modeBadge.style.color = "#38bdf8";
    } else if (data.mode === "live") {
        modeText.textContent = "⚠️ Alpaca LIVE";
        modeBadge.style.color = "#f43f5e";
    } else {
        modeText.textContent = "Lokal Profil (100 kr)";
        modeBadge.style.color = "#06b6d4";
    }

    // 3. Strategy Badge
    const stratBadge = document.getElementById("active-strategy-badge");
    if (stratBadge) {
        stratBadge.textContent = "Strategi: " + formatStrategyName(data.strategy);
    }

    // 4. KPIs
    const equityElem = document.getElementById("kpi-equity");
    const cashSub = document.getElementById("kpi-cash-sub");
    const dayPlElem = document.getElementById("kpi-day-pl");
    const dayPlPctElem = document.getElementById("kpi-day-pl-pct");
    const posCountElem = document.getElementById("kpi-positions-count");
    const tabPosCount = document.getElementById("tab-pos-count");
    const winRateElem = document.getElementById("kpi-win-rate");
    const closedSub = document.getElementById("kpi-closed-trades-sub");

    const equity = acc.equity || 100.0;
    const cash = acc.cash || 100.0;
    const dayPl = acc.day_pl || 0;
    const dayPlPct = acc.day_pl_pct || 0;

    equityElem.textContent = equity.toFixed(2) + " kr";
    cashSub.textContent = "Tillgängligt: " + cash.toFixed(2) + " kr";

    const isPositive = dayPl >= 0;
    dayPlElem.className = `kpi-value ${isPositive ? 'positive' : 'negative'}`;
    dayPlElem.textContent = (isPositive ? "+" : "-") + Math.abs(dayPl).toFixed(2) + " kr";

    dayPlPctElem.className = `kpi-subtext ${isPositive ? 'positive' : 'negative'}`;
    dayPlPctElem.textContent = `${isPositive ? '+' : ''}${dayPlPct.toFixed(2)}% idag`;

    posCountElem.textContent = `${data.position_count} / 3`;
    if (tabPosCount) tabPosCount.textContent = data.position_count;

    winRateElem.textContent = `${data.win_rate}%`;
    closedSub.textContent = `${data.total_trades_count} avslutade affärer`;

    // 5. Snöbollsassistenten (Capital & Compounding Advisor)
    if (data.advisor) {
        const adv = data.advisor;
        const badge = document.getElementById("advisor-trigger-badge");
        const recText = document.getElementById("advisor-rec-text");
        const msLabel = document.getElementById("advisor-milestone-label");
        const msPct = document.getElementById("advisor-milestone-pct");
        const msFill = document.getElementById("advisor-progress-fill");
        const msSub = document.getElementById("advisor-milestone-sub");

        if (badge) {
            badge.className = `advisor-trigger-badge ${adv.action_type || 'normal'}`;
            let icon = "🛡️ ";
            if (adv.action_type === "dip") icon = "🛒 ";
            if (adv.action_type === "streak") icon = "🔥 ";
            badge.textContent = `${icon}${adv.action || 'FÖLJ PLAN'}`;
        }

        if (recText) recText.textContent = adv.recommendation || "";
        
        if (adv.next_milestone && msLabel) {
            msLabel.textContent = `Mål: ${adv.next_milestone.label || 'Milstolpe'}`;
        }
        if (msPct) msPct.textContent = `${adv.progress_pct || 0}%`;
        if (msFill) msFill.style.width = `${Math.min(100, adv.progress_pct || 0)}%`;
        if (msSub && adv.next_milestone) {
            msSub.textContent = `${(adv.equity_sek || 0).toFixed(2)} kr av ${adv.next_milestone.target.toFixed(2)} kr`;
        }

        const harvestVal = document.getElementById("advisor-harvest-val");
        const snowballVal = document.getElementById("advisor-snowball-val");
        if (harvestVal) harvestVal.textContent = `${(adv.harvest_vault_sek || 0).toFixed(2)} kr`;
        if (snowballVal) snowballVal.textContent = `${(adv.snowball_vault_sek || 0).toFixed(2)} kr`;
    }
}

function formatStrategyName(name) {
    if (name === "trend_momentum") return "Trend Momentum (EMA + MACD)";
    if (name === "rsi_reversion") return "Mean Reversion (RSI < 32)";
    if (name === "breakout") return "Volatilitetsutbrott (Bollinger)";
    return name;
}

// --- Toggle Bot Engine ---
async function toggleEngine() {
    if (!currentStatus) return;
    const endpoint = currentStatus.is_running ? "/api/bot/stop" : "/api/bot/start";
    try {
        const res = await fetch(endpoint, { method: "POST" });
        const data = await res.json();
        fetchStatus();
        fetchLogs();
    } catch (e) {
        alert("Kunde inte ändra botens status: " + e);
    }
}

// --- Trigger Manual Scan ---
async function triggerManualScan() {
    const btn = document.getElementById("btn-manual-scan");
    btn.disabled = true;
    btn.innerHTML = "<span>⏳</span><span>Scannar...</span>";
    try {
        await fetch("/api/bot/scan", { method: "POST" });
        await fetchWatchlist();
        await fetchStatus();
        await fetchLogs();
    } catch (e) {
        console.error(e);
    } finally {
        btn.disabled = false;
        btn.innerHTML = "<span>🔄</span><span>Scanna Nu</span>";
    }
}

// --- Watchlist & Signals Board ---
async function fetchWatchlist(isBackground = false) {
    try {
        const res = await fetch("/api/watchlist");
        if (!res.ok) return;
        const data = await res.json();
        currentWatchlist = data.watchlist || [];
        renderWatchlist(currentWatchlist);
    } catch (e) {
        console.error("Error fetching watchlist:", e);
    }
}

function renderWatchlist(items) {
    const tbody = document.getElementById("watchlist-tbody");
    if (!items || items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="empty-cell">Inga aktier i bevakningslistan.</td></tr>`;
        return;
    }

    tbody.innerHTML = items.map(item => {
        const isUp = item.change_pct >= 0;
        const changeClass = isUp ? 'positive' : 'negative';
        const changeStr = (isUp ? '+' : '') + item.change_pct.toFixed(2) + '%';
        const signalClass = item.signal.toLowerCase();

        return `
            <tr>
                <td class="ticker-cell">${item.symbol}</td>
                <td class="price-cell">$ ${item.price.toFixed(2)}</td>
                <td class="${changeClass} font-mono">${changeStr}</td>
                <td class="font-mono">${item.rsi.toFixed(1)}</td>
                <td class="font-mono">
                    <span style="color: ${item.ema9 >= item.ema21 ? '#10b981' : '#f43f5e'}">
                        ${item.ema9 >= item.ema21 ? '▲ Bullish' : '▼ Bearish'}
                    </span>
                </td>
                <td>
                    <span class="signal-pill ${signalClass}" onclick="openSignalDetails('${item.symbol}')" style="cursor: pointer" title="Klicka för detaljerad analys">
                        ${item.signal} (${item.confidence}%) 🔍
                    </span>
                </td>
                <td>
                    <button class="btn btn-sm ${item.signal === 'BUY' ? 'btn-primary' : 'btn-secondary'}" onclick="openSignalDetails('${item.symbol}')">
                        Inspektera
                    </button>
                </td>
            </tr>
        `;
    }).join("");
}

// --- Live Logs Terminal ---
async function fetchLogs(isBackground = false) {
    try {
        const res = await fetch("/api/logs");
        if (!res.ok) return;
        const data = await res.json();
        renderLogs(data.logs || []);
    } catch (e) {
        console.error("Error fetching logs:", e);
    }
}

function renderLogs(logs) {
    const container = document.getElementById("terminal-logs");
    if (!logs || logs.length === 0) return;

    container.innerHTML = logs.map(l => {
        const tagClass = l.level.toLowerCase();
        return `
            <div class="log-line">
                <span class="log-time">${l.time}</span>
                <span class="log-tag ${tagClass}">${l.level}</span>
                <span class="log-msg">${escapeHtml(l.message)}</span>
            </div>
        `;
    }).join("");
}

function escapeHtml(str) {
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// --- Active Positions ---
async function fetchPositions() {
    try {
        const res = await fetch("/api/status");
        if (!res.ok) return;
        const data = await res.json();
        renderPositions(data.positions || []);
    } catch (e) {
        console.error("Error fetching positions:", e);
    }
}

function renderPositions(positions) {
    const tbody = document.getElementById("positions-tbody");
    if (!positions || positions.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" class="empty-cell">Inga aktiva innehav just nu. Boten köper när köpsignaler identifieras!</td></tr>`;
        return;
    }

    tbody.innerHTML = positions.map(pos => {
        const isUp = pos.unrealized_pl_pct >= 0;
        const plClass = isUp ? 'positive' : 'negative';
        const stopLossPrice = pos.entry_price * 0.975;
        const takeProfitPrice = pos.entry_price * 1.05;
        const marketValStr = pos.market_value_sek !== undefined ? `${pos.market_value_sek.toFixed(2)} kr` : `$ ${pos.market_value.toFixed(2)}`;
        const plVal = pos.unrealized_pl_sek !== undefined ? pos.unrealized_pl_sek : pos.unrealized_pl;
        const plStr = (isUp ? '+' : '') + plVal.toFixed(2) + (pos.unrealized_pl_sek !== undefined ? " kr" : " $");

        return `
            <tr>
                <td class="ticker-cell">${pos.symbol}</td>
                <td class="font-mono">${pos.qty}</td>
                <td class="font-mono">$ ${pos.entry_price.toFixed(2)}</td>
                <td class="font-mono">$ ${pos.current_price.toFixed(2)}</td>
                <td class="font-mono">${marketValStr}</td>
                <td class="${plClass} font-mono">
                    ${plStr} (${isUp ? '+' : ''}${pos.unrealized_pl_pct.toFixed(2)}%)
                </td>
                <td class="font-mono negative">$ ${stopLossPrice.toFixed(2)} (-2.5%)</td>
                <td class="font-mono positive">$ ${takeProfitPrice.toFixed(2)} (+5.0%)</td>
                <td>
                    <button class="btn btn-sm btn-danger-ghost" onclick="closePosition('${pos.symbol}')">
                        Stäng
                    </button>
                </td>
            </tr>
        `;
    }).join("");
}

async function closePosition(symbol) {
    if (!confirm(`Är du säker på att du vill stänga innehavet i ${symbol}?`)) return;
    try {
        const res = await fetch(`/api/positions/${symbol}/close`, { method: "POST" });
        const data = await res.json();
        if (data.success) {
            fetchPositions();
            fetchStatus();
            fetchLogs();
        } else {
            alert("Kunde inte stänga: " + (data.error || "Okänt fel"));
        }
    } catch (e) {
        alert("Nätverksfel: " + e);
    }
}

// --- Order & Trade History ---
async function fetchOrders() {
    try {
        const res = await fetch("/api/trades/closed");
        if (!res.ok) return;
        const data = await res.json();
        renderClosedTrades(data.trades || []);
    } catch (e) {
        console.error("Error fetching closed trades:", e);
    }
}

function renderClosedTrades(trades) {
    const tbody = document.getElementById("closed-trades-tbody");
    if (!trades || trades.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="empty-cell">Inga realiserade affärer än.</td></tr>`;
        return;
    }

    tbody.innerHTML = trades.map(t => {
        const plVal = t.pl_sek !== undefined ? t.pl_sek : t.pl;
        const isUp = plVal >= 0;
        const plClass = isUp ? 'positive' : 'negative';
        const plStr = (isUp ? '+' : '') + plVal.toFixed(2) + (t.pl_sek !== undefined ? " kr" : " $");

        return `
            <tr>
                <td class="ticker-cell">${t.symbol}</td>
                <td class="font-mono">${t.qty}</td>
                <td class="font-mono">$ ${t.entry_price.toFixed(2)}</td>
                <td class="font-mono">$ ${t.exit_price.toFixed(2)}</td>
                <td class="${plClass} font-mono">${plStr}</td>
                <td class="${plClass} font-mono">${isUp ? '+' : ''}${t.pl_pct.toFixed(2)}%</td>
                <td class="font-mono" style="color: var(--text-dim)">${t.closed_at}</td>
            </tr>
        `;
    }).join("");
}


// --- Backtest Runner ---
async function runBacktest() {
    const symbol = document.getElementById("bt-symbol").value.trim().toUpperCase();
    const strategy = document.getElementById("bt-strategy").value;
    const period = document.getElementById("bt-period").value;
    const stopLoss = parseFloat(document.getElementById("bt-stop-loss").value);
    const takeProfit = parseFloat(document.getElementById("bt-take-profit").value);

    if (!symbol) {
        alert("Ange en aktiesymbol (t.ex. NVDA eller AAPL)");
        return;
    }

    const btn = document.getElementById("btn-run-backtest");
    btn.disabled = true;
    btn.innerHTML = "<span>⏳</span><span>Beräknar historik...</span>";

    try {
        const res = await fetch("/api/backtest", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                symbol: symbol,
                strategy: strategy,
                period: period,
                stop_loss_pct: stopLoss,
                take_profit_pct: takeProfit,
                initial_capital: 10000.0
            })
        });

        const data = await res.json();
        if (data.success) {
            renderBacktestResults(data);
        } else {
            alert("Backtest misslyckades: " + (data.error || "Okänt fel"));
        }
    } catch (e) {
        alert("Fel vid körning av backtest: " + e);
    } finally {
        btn.disabled = false;
        btn.innerHTML = "<span>🧪</span><span>Kör Backtest</span>";
    }
}

function renderBacktestResults(data) {
    const container = document.getElementById("backtest-results");
    container.style.display = "flex";

    const returnElem = document.getElementById("bt-result-return");
    const alphaElem = document.getElementById("bt-result-alpha");
    const bhElem = document.getElementById("bt-result-bh");
    const winRateElem = document.getElementById("bt-result-winrate");
    const tradesCountElem = document.getElementById("bt-result-trades-count");
    const pfElem = document.getElementById("bt-result-pf");
    const ddElem = document.getElementById("bt-result-drawdown");

    const isProfit = data.total_return_pct >= 0;
    returnElem.className = `kpi-value ${isProfit ? 'positive' : 'negative'}`;
    returnElem.textContent = `${isProfit ? '+' : ''}${data.total_return_pct.toFixed(2)}%`;

    const isAlpha = data.alpha >= 0;
    alphaElem.className = `kpi-subtext ${isAlpha ? 'positive' : 'negative'}`;
    alphaElem.textContent = `Meravkastning (Alpha): ${isAlpha ? '+' : ''}${data.alpha.toFixed(2)}%`;

    const isBhProfit = data.buy_and_hold_return_pct >= 0;
    bhElem.className = `kpi-value ${isBhProfit ? 'positive' : 'negative'}`;
    bhElem.textContent = `${isBhProfit ? '+' : ''}${data.buy_and_hold_return_pct.toFixed(2)}%`;

    winRateElem.textContent = `${data.win_rate}%`;
    tradesCountElem.textContent = `${data.total_trades} affärer (${data.winning_trades} vinster / ${data.losing_trades} förluster)`;

    pfElem.textContent = data.profit_factor.toFixed(2);
    ddElem.textContent = `Max Drawdown: -${data.max_drawdown_pct.toFixed(2)}%`;

    // Render trades table
    const tbody = document.getElementById("bt-trades-tbody");
    if (!data.trades || data.trades.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="empty-cell">Inga signaler utlöstes under denna testperiod med valda inställningar.</td></tr>`;
        return;
    }

    tbody.innerHTML = data.trades.map(t => {
        const isUp = t.pl >= 0;
        const plClass = isUp ? 'positive' : 'negative';

        return `
            <tr>
                <td class="font-mono">${t.entry_date}</td>
                <td class="font-mono">${t.exit_date}</td>
                <td class="font-mono">$ ${t.entry_price.toFixed(2)}</td>
                <td class="font-mono">$ ${t.exit_price.toFixed(2)}</td>
                <td class="font-mono">${t.shares}</td>
                <td class="${plClass} font-mono">${isUp ? '+' : ''}$ ${t.pl.toFixed(2)}</td>
                <td class="${plClass} font-mono">${isUp ? '+' : ''}${t.pl_pct.toFixed(2)}%</td>
                <td><span class="badge">${t.reason}</span></td>
            </tr>
        `;
    }).join("");
}

// --- Signal Details & Quick Buy Modal ---
function openSignalDetails(symbol) {
    selectedSignalSymbol = symbol;
    const item = currentWatchlist.find(x => x.symbol === symbol);
    if (!item) return;

    const modal = document.getElementById("signal-modal");
    const title = document.getElementById("signal-modal-title");
    const body = document.getElementById("signal-modal-body");
    const buyBtn = document.getElementById("btn-signal-buy");

    title.textContent = `Analys & Signal: ${item.symbol}`;
    const signalClass = item.signal.toLowerCase();

    body.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <div>
                <div style="font-size: 26px; font-weight: 700; font-family: var(--font-mono);">$ ${item.price.toFixed(2)}</div>
                <div style="font-size: 13px; color: ${item.change_pct >= 0 ? '#10b981' : '#f43f5e'}">
                    ${item.change_pct >= 0 ? '+' : ''}${item.change_pct.toFixed(2)}% (24h)
                </div>
            </div>
            <div class="signal-pill ${signalClass}" style="font-size: 14px; padding: 6px 14px;">
                ${item.signal} (${item.confidence}%)
            </div>
        </div>

        <div style="margin-bottom: 14px;">
            <div style="font-size: 12px; font-weight: 700; color: var(--text-dim); text-transform: uppercase; margin-bottom: 6px;">Tekniska Indikatorer</div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-family: var(--font-mono); font-size: 13px; background: rgba(0,0,0,0.2); padding: 12px; border-radius: 8px;">
                <div>RSI (14): <strong>${item.rsi.toFixed(1)}</strong></div>
                <div>EMA 9: <strong>$ ${item.ema9.toFixed(2)}</strong></div>
                <div>EMA 21: <strong>$ ${item.ema21.toFixed(2)}</strong></div>
                <div>Trend: <strong style="color: ${item.ema9 >= item.ema21 ? '#10b981' : '#f43f5e'}">${item.ema9 >= item.ema21 ? 'Uptrend' : 'Downtrend'}</strong></div>
            </div>
        </div>

        <div>
            <div style="font-size: 12px; font-weight: 700; color: var(--text-dim); text-transform: uppercase; margin-bottom: 6px;">Strategins Argument & Rationale</div>
            <ul style="padding-left: 20px; font-size: 13px; color: var(--text-muted); display: flex; flex-direction: column; gap: 6px;">
                ${item.reasons.map(r => `<li>${escapeHtml(r)}</li>`).join("")}
            </ul>
        </div>
    `;

    buyBtn.style.display = item.signal === "BUY" ? "inline-flex" : "none";
    modal.style.display = "flex";
}

function closeSignalModal() {
    document.getElementById("signal-modal").style.display = "none";
    selectedSignalSymbol = null;
}

async function executeSignalBuy() {
    if (!selectedSignalSymbol) return;
    const symbol = selectedSignalSymbol;
    closeSignalModal();

    try {
        const res = await fetch("/api/orders/manual", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ symbol: symbol, qty: 10, side: "buy" })
        });
        const data = await res.json();
        if (data.success) {
            alert(`Order genomförd: Köpte ${symbol}`);
            fetchStatus();
            fetchLogs();
            fetchPositions();
        } else {
            alert("Kunde inte lägga order: " + (data.error || "Okänt fel"));
        }
    } catch (e) {
        alert("Fel: " + e);
    }
}

// --- Settings & Modal ---
async function openSettingsModal() {
    try {
        const res = await fetch("/api/config");
        if (!res.ok) return;
        const cfg = await res.json();

        // Populate fields
        const mode = cfg.mode || "simulation";
        if (mode === "simulation") document.getElementById("mode-radio-sim").checked = true;
        if (mode === "paper") document.getElementById("mode-radio-paper").checked = true;
        if (mode === "live") document.getElementById("mode-radio-live").checked = true;

        document.getElementById("cfg-alpaca-key").value = cfg.alpaca_api_key || "";
        document.getElementById("cfg-alpaca-secret").value = cfg.alpaca_secret_key || "";
        document.getElementById("cfg-telegram-token").value = cfg.telegram_bot_token || "";
        document.getElementById("cfg-telegram-chat").value = cfg.telegram_chat_id || "";

        const risk = cfg.risk || {};
        document.getElementById("cfg-max-pos").value = risk.max_position_pct || 10;
        document.getElementById("cfg-stop-loss").value = risk.stop_loss_pct || 2.5;
        document.getElementById("cfg-take-profit").value = risk.take_profit_pct || 5.0;
        document.getElementById("cfg-max-positions").value = risk.max_open_positions || 4;
        document.getElementById("cfg-daily-loss").value = risk.max_daily_loss_pct || 3.0;
        document.getElementById("cfg-scan-interval").value = cfg.scan_interval_seconds || 60;
        document.getElementById("cfg-watchlist").value = (cfg.watchlist || []).join(", ");

        document.getElementById("settings-modal").style.display = "flex";
    } catch (e) {
        alert("Kunde inte ladda inställningar: " + e);
    }
}

function closeSettingsModal() {
    document.getElementById("settings-modal").style.display = "none";
}

async function saveSettings() {
    const selectedMode = document.querySelector('input[name="bot-mode"]:checked').value;
    const apiKey = document.getElementById("cfg-alpaca-key").value.trim();
    const secretKey = document.getElementById("cfg-alpaca-secret").value.trim();
    const telegramToken = document.getElementById("cfg-telegram-token").value.trim();
    const telegramChat = document.getElementById("cfg-telegram-chat").value.trim();

    const maxPos = parseFloat(document.getElementById("cfg-max-pos").value);
    const stopLoss = parseFloat(document.getElementById("cfg-stop-loss").value);
    const takeProfit = parseFloat(document.getElementById("cfg-take-profit").value);
    const maxOpenPos = parseInt(document.getElementById("cfg-max-positions").value, 10);
    const dailyLoss = parseFloat(document.getElementById("cfg-daily-loss").value);
    const scanInterval = parseInt(document.getElementById("cfg-scan-interval").value, 10);
    const watchlistStr = document.getElementById("cfg-watchlist").value;
    const watchlist = watchlistStr.split(",").map(s => s.trim().toUpperCase()).filter(s => s.length > 0);

    const payload = {
        mode: selectedMode,
        alpaca_api_key: apiKey,
        alpaca_secret_key: secretKey,
        alpaca_base_url: selectedMode === "live" ? "https://api.alpaca.markets" : "https://paper-api.alpaca.markets",
        telegram_bot_token: telegramToken,
        telegram_chat_id: telegramChat,
        scan_interval_seconds: scanInterval,
        watchlist: watchlist,
        risk: {
            max_position_pct: maxPos,
            stop_loss_pct: stopLoss,
            take_profit_pct: takeProfit,
            max_open_positions: maxOpenPos,
            max_daily_loss_pct: dailyLoss
        }
    };

    try {
        const res = await fetch("/api/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            closeSettingsModal();
            fetchStatus();
            fetchWatchlist();
            fetchLogs();
        } else {
            alert("Kunde inte spara inställningar");
        }
    } catch (e) {
        alert("Fel vid sparande: " + e);
    }
}

async function testAlpacaConnection() {
    const feedback = document.getElementById("alpaca-test-result");
    const btn = document.getElementById("btn-test-alpaca");
    feedback.style.display = "block";
    feedback.className = "test-feedback";
    feedback.textContent = "Testar anslutning mot Alpaca...";
    btn.disabled = true;

    // Save current keys first so backend tests the typed keys
    const apiKey = document.getElementById("cfg-alpaca-key").value.trim();
    const secretKey = document.getElementById("cfg-alpaca-secret").value.trim();
    await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ alpaca_api_key: apiKey, alpaca_secret_key: secretKey })
    });

    try {
        const res = await fetch("/api/alpaca/test", { method: "POST" });
        const data = await res.json();
        if (data.connected) {
            feedback.className = "test-feedback success";
            feedback.textContent = `✓ Ansluten! Konto: ${data.account_number} (${data.currency} ${data.equity.toFixed(2)})`;
        } else {
            feedback.className = "test-feedback error";
            feedback.textContent = `✗ Misslyckades: ${data.message}`;
        }
    } catch (e) {
        feedback.className = "test-feedback error";
        feedback.textContent = "Nätverksfel: " + e;
    } finally {
        btn.disabled = false;
    }
}

async function testTelegramConnection() {
    const feedback = document.getElementById("telegram-test-result");
    const btn = document.getElementById("btn-test-telegram");
    feedback.style.display = "block";
    feedback.className = "test-feedback";
    feedback.textContent = "Skickar testnotis till Telegram...";
    btn.disabled = true;

    const botToken = document.getElementById("cfg-telegram-token").value.trim();
    const chatId = document.getElementById("cfg-telegram-chat").value.trim();

    try {
        const res = await fetch("/api/telegram/test", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ bot_token: botToken, chat_id: chatId })
        });
        const data = await res.json();
        if (data.success) {
            feedback.className = "test-feedback success";
            feedback.textContent = "✓ " + data.message;
        } else {
            feedback.className = "test-feedback error";
            feedback.textContent = "✗ " + (data.error || "Kunde inte skicka notis");
        }
    } catch (e) {
        feedback.className = "test-feedback error";
        feedback.textContent = "Nätverksfel: " + e;
    } finally {
        btn.disabled = false;
    }
}

async function resetSimBalance() {
    if (!confirm("Vill du återställa saldot till 100,00 kr och rensa alla öppna testpositioner?")) return;
    try {

        const res = await fetch("/api/simulation/reset", { method: "POST" });
        const data = await res.json();
        if (data.success) {
            alert(data.message);
            closeSettingsModal();
            fetchStatus();
            fetchPositions();
            fetchLogs();
            fetchOrders();
        }
    } catch (e) {
        alert("Fel vid återställning: " + e);
    }
}
