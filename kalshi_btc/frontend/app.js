/**
 * Kalshi BTC Prediction Betting — Frontend Application
 * Connects to FastAPI backend via REST + WebSocket for real-time updates.
 */

'use strict';

// ──────────────────────────────────────────────────────────────────────────────
// Config
// ──────────────────────────────────────────────────────────────────────────────
const API_BASE = window.location.origin;
const WS_URL   = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;

// ──────────────────────────────────────────────────────────────────────────────
// State
// ──────────────────────────────────────────────────────────────────────────────
let ws          = null;
let priceChart  = null;
let chartTf     = '5m';
let lastSignal  = null;
let lastPrice   = null;
let wsConnected = false;
let pingInterval= null;
let chartData   = { labels: [], open: [], high: [], low: [], close: [], volume: [] };

// ──────────────────────────────────────────────────────────────────────────────
// Utility helpers
// ──────────────────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

function fmt(n, dec = 2) {
  if (n == null) return '—';
  return Number(n).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec });
}
function fmtPrice(n) {
  if (n == null) return '—';
  return '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function fmtPct(n) { return n == null ? '—' : fmt(n) + '%'; }

function toast(msg, type = 'info', duration = 3500) {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  $('toast-container').appendChild(el);
  setTimeout(() => el.remove(), duration);
}

function setDot(id, state) {          // state: 'connected' | 'error' | 'warning' | ''
  const dot = $(id);
  dot.className = `status-dot ${state}`;
}

function timeAgo(isoStr) {
  if (!isoStr) return '';
  const diff = Math.floor((Date.now() - new Date(isoStr)) / 1000);
  if (diff < 60)  return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  return `${Math.floor(diff/3600)}h ago`;
}

// ──────────────────────────────────────────────────────────────────────────────
// WebSocket
// ──────────────────────────────────────────────────────────────────────────────
function connectWS() {
  if (ws && ws.readyState === WebSocket.OPEN) return;

  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    wsConnected = true;
    setDot('ws-dot', 'connected');
    $('status-label').textContent = 'Live';
    pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('ping');
    }, 25000);
  };

  ws.onmessage = ({ data }) => {
    try {
      const msg = JSON.parse(data);
      if (msg.type === 'pong') return;
      if (msg.type === 'update') handleUpdate(msg);
    } catch (e) { console.warn('WS parse error', e); }
  };

  ws.onerror = () => setDot('ws-dot', 'error');

  ws.onclose = () => {
    wsConnected = false;
    setDot('ws-dot', 'error');
    $('status-label').textContent = 'Reconnecting…';
    clearInterval(pingInterval);
    setTimeout(connectWS, 3000);
  };
}

// ──────────────────────────────────────────────────────────────────────────────
// Update handlers
// ──────────────────────────────────────────────────────────────────────────────
function handleUpdate(msg) {
  if (msg.btc_price)  updatePriceDisplay(msg.btc_price);
  if (msg.signal)     updateSignalPanel(msg.signal);
  if (msg.stats)      updateStats(msg.stats);
  if (msg.open_bets)  renderOpenBets(msg.open_bets);
  $('last-update').textContent = 'Updated ' + timeAgo(msg.timestamp);
}

function updatePriceDisplay(price) {
  const prev = lastPrice;
  lastPrice = price;
  const el = $('btc-price-display');
  el.textContent = fmtPrice(price);
  if (prev) {
    el.style.color = price > prev ? 'var(--green)' : price < prev ? 'var(--red)' : '';
    setTimeout(() => el.style.color = '', 1000);
  }
  // Update signal meta price too
  $('sig-price').textContent = fmtPrice(price);
}

function updateSignalPanel(sig) {
  lastSignal = sig;

  // Direction badge
  const badge = $('signal-badge');
  const arrow = $('signal-arrow');
  const dir   = $('signal-direction');
  badge.className = 'signal-badge ' + sig.direction.toLowerCase();
  arrow.textContent = sig.direction === 'UP' ? '↑' : sig.direction === 'DOWN' ? '↓' : '—';
  dir.textContent   = sig.direction;

  // Confidence bar
  const conf = sig.confidence * 100;
  const bar  = $('conf-bar');
  bar.style.width = conf + '%';
  bar.className   = 'conf-bar ' + (conf >= 65 ? 'high' : conf <= 45 ? 'low' : '');
  $('conf-value').textContent = fmt(conf, 1) + '%';

  // Meta
  $('sig-price').textContent       = fmtPrice(sig.current_price);
  $('sig-change').textContent      = (sig.predicted_change_pct >= 0 ? '+' : '') + fmt(sig.predicted_change_pct, 3) + '%';
  $('sig-change').style.color      = sig.predicted_change_pct >= 0 ? 'var(--green)' : 'var(--red)';
  $('sig-kalshi-price').textContent= sig.kalshi_price + '¢';

  // Indicator bars
  const ind = sig.indicators;
  setIndBar('rsi-bar', 'rsi-val', ind.rsi, 0, 100);
  setMacdBar(ind.macd_histogram);
  setIndBar('adx-bar', 'adx-val', ind.adx, 0, 60);
  setIndBar('bb-bar', 'bb-val', ind.bb_position * 100, 0, 100);
  setIndBar('atr-bar', 'atr-val', ind.atr_pct * 20, 0, 100, ind.atr_pct.toFixed(3) + '%');
  const emaAlignPct = ((ind.ema_alignment + 1) / 2) * 100;
  setIndBar('ema-bar', 'ema-val', emaAlignPct, 0, 100, fmt(ind.ema_alignment, 2));

  // Component scores
  renderScores(sig.scores);

  // Reasoning
  renderReasoning(sig.reasoning, sig.direction);

  // Quick bet info
  updateQuickBetInfo(sig);
}

function setIndBar(barId, valId, val, min, max, customLabel = null) {
  const pct = Math.min(100, Math.max(0, ((val - min) / (max - min)) * 100));
  $(barId).style.width = pct + '%';
  $(valId).textContent = customLabel !== null ? customLabel : fmt(val, 1);
}

function setMacdBar(hist) {
  const bar = $('macd-bar');
  const val = $('macd-val');
  const pct = Math.min(100, Math.abs(hist) * 5000);
  bar.style.width = pct + '%';
  bar.style.background = hist >= 0 ? 'var(--green)' : 'var(--red)';
  val.textContent = hist.toFixed(4);
  val.style.color = hist >= 0 ? 'var(--green)' : 'var(--red)';
}

function renderScores(scores) {
  const names = {
    trend: 'Trend',
    momentum: 'Momentum',
    volatility: 'Volatility',
    volume: 'Volume',
    orderbook: 'Order Book',
    trade_momentum: 'Trade Flow',
    multi_tf: 'Multi-TF',
  };
  const grid = $('scores-grid');
  grid.innerHTML = '';
  for (const [key, label] of Object.entries(names)) {
    const v = scores[key] ?? 0;
    const isPos = v >= 0;
    const pct   = Math.abs(v) * 50; // 0-50% from center
    const row   = document.createElement('div');
    row.className = 'score-row';
    row.innerHTML = `
      <span class="score-name">${label}</span>
      <div class="score-bar-wrap">
        <div class="score-bar ${isPos ? 'pos' : 'neg'}" style="width:${pct}%"></div>
      </div>
      <span class="score-val ${isPos ? 'pos' : 'neg'}">${isPos ? '+' : ''}${v.toFixed(2)}</span>
    `;
    grid.appendChild(row);
  }
}

function renderReasoning(reasons, direction) {
  const list = $('reasoning-list');
  list.innerHTML = '';
  if (!reasons || reasons.length === 0) {
    list.innerHTML = '<li>No analysis available</li>';
    return;
  }
  for (const r of reasons) {
    const li = document.createElement('li');
    li.textContent = r;
    const isBull = /bull|up|buy|above|rising|oversold|accum|pressure|positive/i.test(r);
    const isBear = /bear|down|sell|below|fall|overbought|distribut|reversal/i.test(r);
    li.className = isBull ? 'bull' : isBear ? 'bear' : '';
    list.appendChild(li);
  }
}

function updateQuickBetInfo(sig) {
  const badge = $('qb-conf-badge');
  const info  = $('qb-info');
  const btn   = $('bet-signal-btn');
  const conf  = sig.confidence * 100;

  badge.textContent = fmt(conf, 1) + '%';
  badge.className   = 'badge badge-confidence ' + (conf >= 65 ? 'high' : conf >= 55 ? 'mid' : 'low');

  if (sig.direction === 'NEUTRAL') {
    info.textContent = 'Signal is NEUTRAL — no bet recommended.';
    btn.disabled = true;
  } else {
    const sideLabel = sig.direction === 'UP' ? 'YES (price goes up)' : 'NO (price goes down)';
    info.innerHTML = `
      Prediction: <b style="color:${sig.direction==='UP'?'var(--green)':'var(--red)'}">${sig.direction}</b>
      | Side: <b>${sideLabel}</b>
      | Kelly price: <b>${sig.kalshi_price}¢</b>
    `;
    btn.disabled = conf < 55;
  }
}

function updateStats(stats) {
  const pnl = stats.total_pnl;
  const pnlEl = $('stat-pnl');
  pnlEl.textContent = (pnl >= 0 ? '+' : '') + fmtPrice(pnl);
  pnlEl.className   = 'stat-value ' + (pnl >= 0 ? 'green' : 'red');

  $('stat-winrate').textContent = fmtPct(stats.win_rate);
  const roi = stats.roi_pct;
  const roiEl = $('stat-roi');
  roiEl.textContent = (roi >= 0 ? '+' : '') + fmtPct(roi);
  roiEl.className   = 'stat-value ' + (roi >= 0 ? 'green' : 'red');
  $('stat-exposure').textContent = fmtPrice(stats.current_exposure);

  $('stat-total').textContent   = stats.total_bets;
  $('stat-won').textContent     = stats.won;
  $('stat-lost').textContent    = stats.lost;
  $('stat-wagered').textContent = fmtPrice(stats.total_wagered);
  $('open-bet-count').textContent = stats.open_bets;
}

// ──────────────────────────────────────────────────────────────────────────────
// Bet rendering
// ──────────────────────────────────────────────────────────────────────────────
function renderOpenBets(bets) {
  const list = $('open-bets-list');
  if (!bets || bets.length === 0) {
    list.innerHTML = '<div class="empty-state">No open bets</div>';
    return;
  }
  list.innerHTML = bets.map(b => betItemHTML(b)).join('');
}

function renderHistoryBets(bets) {
  const list = $('history-bets-list');
  if (!bets || bets.length === 0) {
    list.innerHTML = '<div class="empty-state">No bet history</div>';
    return;
  }
  list.innerHTML = bets.map(b => betItemHTML(b)).join('');
}

function betItemHTML(b) {
  const pnlClass = b.status === 'won' ? 'won' : b.status === 'lost' ? 'lost' : 'open';
  const pnlLabel = b.status === 'won'
    ? `+${fmtPrice(b.profit_loss)}`
    : b.status === 'lost'
    ? fmtPrice(b.profit_loss)
    : 'Open';
  return `
    <div class="bet-item">
      <div class="bet-row1">
        <span class="bet-ticker">${b.ticker}</span>
        <span class="bet-side ${b.side}">${b.side.toUpperCase()}</span>
        <span class="bet-pnl ${pnlClass}">${pnlLabel}</span>
      </div>
      <div class="bet-row2">
        <span>${b.contracts} × ${b.entry_price_cents}¢ = ${fmtPrice(b.cost)}</span>
        <span>BTC @ ${fmtPrice(b.btc_price_at_entry)}</span>
        <span>${(b.confidence*100).toFixed(1)}% conf</span>
      </div>
    </div>
  `;
}

// ──────────────────────────────────────────────────────────────────────────────
// Chart (lightweight canvas implementation)
// ──────────────────────────────────────────────────────────────────────────────
async function loadChart(tf) {
  chartTf = tf;
  document.querySelectorAll('.tf-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.tf === tf);
  });

  try {
    const res = await fetch(`${API_BASE}/api/btc/klines?interval=${tf}&limit=80`);
    if (!res.ok) throw new Error(res.statusText);
    const candles = await res.json();
    renderChart(candles);
  } catch (e) {
    console.error('Chart load failed:', e);
    toast('Failed to load chart data', 'error');
  }
}

function renderChart(candles) {
  const canvas  = $('price-chart');
  const ctx     = canvas.getContext('2d');
  const W       = canvas.parentElement.clientWidth - 32;
  const H       = 220;
  canvas.width  = W;
  canvas.height = H;

  const closes  = candles.map(c => c.close);
  const highs   = candles.map(c => c.high);
  const lows    = candles.map(c => c.low);
  const opens   = candles.map(c => c.open);
  const n       = candles.length;
  const minP    = Math.min(...lows) * 0.9998;
  const maxP    = Math.max(...highs) * 1.0002;
  const padL    = 8, padR = 8, padT = 12, padB = 24;
  const cw      = (W - padL - padR) / n;
  const ph      = H - padT - padB;

  const toY = p => padT + ph - ((p - minP) / (maxP - minP)) * ph;
  const toX = i => padL + i * cw + cw / 2;

  ctx.clearRect(0, 0, W, H);

  // Background grid
  ctx.strokeStyle = 'rgba(48,54,61,0.6)';
  ctx.lineWidth   = 0.5;
  for (let i = 0; i <= 4; i++) {
    const y = padT + (ph / 4) * i;
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(W - padR, y);
    ctx.stroke();
    const val = maxP - ((maxP - minP) / 4) * i;
    ctx.fillStyle = 'rgba(139,148,158,0.7)';
    ctx.font = '9px monospace';
    ctx.fillText('$' + Math.round(val).toLocaleString(), padL, y - 2);
  }

  // Candles
  for (let i = 0; i < n; i++) {
    const x    = toX(i);
    const yH   = toY(highs[i]);
    const yL   = toY(lows[i]);
    const yO   = toY(opens[i]);
    const yC   = toY(closes[i]);
    const bull = closes[i] >= opens[i];
    const color = bull ? '#3fb950' : '#f85149';

    // Wick
    ctx.strokeStyle = color;
    ctx.lineWidth   = 1;
    ctx.beginPath();
    ctx.moveTo(x, yH);
    ctx.lineTo(x, yL);
    ctx.stroke();

    // Body
    ctx.fillStyle = bull ? 'rgba(63,185,80,0.8)' : 'rgba(248,81,73,0.8)';
    const bodyH   = Math.max(1, Math.abs(yC - yO));
    ctx.fillRect(x - Math.max(1, cw * 0.35), Math.min(yO, yC), Math.max(2, cw * 0.7), bodyH);
  }

  // Close price line overlay
  ctx.strokeStyle = 'rgba(88,166,255,0.5)';
  ctx.lineWidth   = 1.5;
  ctx.beginPath();
  closes.forEach((p, i) => {
    const x = toX(i), y = toY(p);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();

  // EMA overlay (simple 20-period)
  if (n >= 20) {
    let ema = closes[0];
    const k = 2 / 21;
    const emaVals = closes.map(c => { ema = c * k + ema * (1 - k); return ema; });
    ctx.strokeStyle = 'rgba(188,140,255,0.7)';
    ctx.lineWidth   = 1.5;
    ctx.setLineDash([4, 2]);
    ctx.beginPath();
    emaVals.forEach((p, i) => {
      const x = toX(i), y = toY(p);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // Latest price label
  if (n > 0) {
    const lastClose = closes[n - 1];
    const ly        = toY(lastClose);
    ctx.strokeStyle = 'rgba(88,166,255,0.8)';
    ctx.lineWidth   = 0.8;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(padL, ly); ctx.lineTo(W - padR, ly);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle   = 'var(--blue, #58a6ff)';
    ctx.font        = 'bold 10px monospace';
    ctx.fillText('$' + lastClose.toLocaleString('en-US', {maximumFractionDigits:0}), W - padR - 70, ly - 3);
  }
}

// ──────────────────────────────────────────────────────────────────────────────
// API calls
// ──────────────────────────────────────────────────────────────────────────────
async function refreshPrediction() {
  $('refresh-signal-btn').textContent = '…';
  $('refresh-signal-btn').disabled = true;
  try {
    const res  = await fetch(`${API_BASE}/api/prediction`);
    if (!res.ok) throw new Error(res.statusText);
    const sig  = await res.json();
    updateSignalPanel(sig);
    toast('Signal refreshed', 'success', 2000);
  } catch (e) {
    toast('Failed to refresh signal: ' + e.message, 'error');
  } finally {
    $('refresh-signal-btn').textContent = '↻';
    $('refresh-signal-btn').disabled = false;
  }
}

async function betOnSignal() {
  const btn = $('bet-signal-btn');
  btn.disabled = true;
  btn.textContent = 'Placing…';
  try {
    const res  = await fetch(`${API_BASE}/api/bet/signal`, { method: 'POST' });
    const data = await res.json();
    if (res.ok && data.placed) {
      toast(`Bet placed: ${data.bet.side.toUpperCase()} ${data.bet.contracts} contracts @ ${data.bet.entry_price_cents}¢`, 'success', 5000);
      loadStats();
      loadOpenBets();
    } else {
      toast(data.reason || 'No bet placed', 'warning', 4000);
    }
  } catch (e) {
    toast('Bet failed: ' + e.message, 'error');
  } finally {
    btn.disabled  = false;
    btn.textContent = 'Bet on Signal';
  }
}

async function placeManualBet() {
  const ticker    = $('ticker-input').value.trim();
  const side      = $('side-input').value;
  const contracts = parseInt($('contracts-input').value);
  const price     = parseInt($('price-input').value);

  if (!ticker) { toast('Enter a market ticker', 'warning'); return; }
  if (!contracts || contracts < 1) { toast('Invalid contract count', 'warning'); return; }
  if (!price || price < 1 || price > 99) { toast('Price must be 1-99', 'warning'); return; }

  const btn = $('manual-bet-btn');
  btn.disabled = true;
  btn.textContent = 'Placing…';
  try {
    const res = await fetch(`${API_BASE}/api/bet/manual`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticker, side, contracts, price }),
    });
    const data = await res.json();
    if (res.ok) {
      toast(`Order placed: ${data.order_id} — status: ${data.status}`, 'success', 5000);
    } else {
      toast(data.detail || 'Order failed', 'error');
    }
  } catch (e) {
    toast('Manual bet failed: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Place Manual Bet';
  }
}

async function loadStats() {
  try {
    const res = await fetch(`${API_BASE}/api/stats`);
    if (res.ok) updateStats(await res.json());
  } catch (_) {}
}

async function loadOpenBets() {
  try {
    const res = await fetch(`${API_BASE}/api/bets?status=open`);
    if (res.ok) renderOpenBets(await res.json());
  } catch (_) {}
}

async function loadHistory() {
  const btn = $('load-history-btn');
  btn.disabled = true;
  btn.textContent = '…';
  try {
    const res = await fetch(`${API_BASE}/api/bets`);
    if (res.ok) renderHistoryBets(await res.json());
  } catch (e) {
    toast('Failed to load history', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Load';
  }
}

async function loadMarkets() {
  const btn = $('load-markets-btn');
  btn.disabled = true;
  btn.textContent = '…';
  try {
    const res = await fetch(`${API_BASE}/api/markets/5min`);
    const list = $('markets-list');
    if (res.status === 503) {
      list.innerHTML = '<div class="empty-state">Kalshi not connected — add credentials to .env</div>';
      return;
    }
    const markets = await res.json();
    if (!markets.length) {
      list.innerHTML = '<div class="empty-state">No short-term markets open right now</div>';
      return;
    }
    list.innerHTML = markets.map(m => `
      <div class="market-item">
        <span class="market-ticker">${m.ticker}</span>
        <span class="market-title">${m.title}</span>
        <span class="market-prob" style="color:${m.implied_probability > 0.5 ? 'var(--green)' : 'var(--red)'}">${(m.implied_probability*100).toFixed(0)}%</span>
        <span class="market-close">${new Date(m.close_time).toLocaleTimeString()}</span>
      </div>
    `).join('');
  } catch (e) {
    toast('Failed to load markets', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Load';
  }
}

async function saveAutoBetConfig() {
  const enabled    = $('auto-bet-toggle').checked;
  const confidence = parseInt($('cfg-confidence').value) / 100;
  const maxBet     = parseFloat($('cfg-max-bet').value);
  const maxExp     = parseFloat($('cfg-max-exposure').value);
  const kelly      = parseInt($('cfg-kelly').value) / 100;

  try {
    const res = await fetch(`${API_BASE}/api/bet/auto/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        enabled,
        min_confidence: confidence,
        max_bet_size:   maxBet,
        max_exposure:   maxExp,
        kelly_fraction: kelly,
      }),
    });
    if (res.ok) {
      toast('Auto-bet config saved', 'success');
    } else {
      toast('Config save failed', 'error');
    }
  } catch (e) {
    toast('Config save error: ' + e.message, 'error');
  }
}

async function checkHealth() {
  try {
    const res  = await fetch(`${API_BASE}/api/health`);
    const data = await res.json();
    setDot('kalshi-dot', data.kalshi_connected ? 'connected' : 'warning');
    if (data.btc_price) updatePriceDisplay(data.btc_price);
  } catch (_) {
    setDot('kalshi-dot', 'error');
  }
}

// ──────────────────────────────────────────────────────────────────────────────
// Event listeners
// ──────────────────────────────────────────────────────────────────────────────
function initEventListeners() {
  // Signal refresh
  $('refresh-signal-btn').addEventListener('click', refreshPrediction);

  // Bet on signal
  $('bet-signal-btn').addEventListener('click', betOnSignal);

  // Manual bet
  $('manual-bet-btn').addEventListener('click', placeManualBet);

  // Cost preview for manual bet
  ['contracts-input', 'price-input'].forEach(id => {
    $(id).addEventListener('input', () => {
      const contracts = parseInt($('contracts-input').value) || 0;
      const price     = parseInt($('price-input').value) || 0;
      const cost      = (contracts * price / 100).toFixed(2);
      const payout    = (contracts * 1.0).toFixed(2);
      $('cost-preview').textContent   = cost;
      $('payout-preview').textContent = payout;
    });
  });

  // Auto-bet toggle
  $('auto-bet-toggle').addEventListener('change', (e) => {
    const card = $('autobet-config-card');
    if (e.target.checked) {
      card.classList.remove('hidden');
    } else {
      card.classList.add('hidden');
      // Disable immediately
      fetch(`${API_BASE}/api/bet/auto/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: false, min_confidence: 0.6, max_bet_size: 10, max_exposure: 50, kelly_fraction: 0.25 }),
      });
    }
  });

  // Config sliders
  $('cfg-confidence').addEventListener('input', e => {
    $('cfg-confidence-val').textContent = e.target.value + '%';
  });
  $('cfg-kelly').addEventListener('input', e => {
    $('cfg-kelly-val').textContent = e.target.value + '%';
  });

  // Save config
  $('save-autobet-btn').addEventListener('click', saveAutoBetConfig);

  // Timeframe buttons
  document.querySelectorAll('.tf-btn').forEach(btn => {
    btn.addEventListener('click', () => loadChart(btn.dataset.tf));
  });

  // History / markets load
  $('load-history-btn').addEventListener('click', loadHistory);
  $('load-markets-btn').addEventListener('click', loadMarkets);

  // Resize chart on window resize
  window.addEventListener('resize', () => {
    if (chartData.candles) renderChart(chartData.candles);
  });
}

// ──────────────────────────────────────────────────────────────────────────────
// Init
// ──────────────────────────────────────────────────────────────────────────────
async function init() {
  initEventListeners();
  connectWS();
  checkHealth();
  loadChart('5m');
  loadStats();

  // Periodically refresh health check
  setInterval(checkHealth, 30000);
  // Refresh chart periodically
  setInterval(() => loadChart(chartTf), 120000);
}

document.addEventListener('DOMContentLoaded', init);
