# Kalshi BTC Prediction Betting

A full-stack application that uses **multi-factor technical analysis** to predict Bitcoin's 5-minute price direction and automatically size and place bets on **Kalshi** prediction markets.

## Features

### Prediction Engine
- **7-factor signal model** combining:
  - EMA ribbon alignment + ADX trend strength
  - RSI, MACD histogram, Stochastic momentum
  - Bollinger Bands position + ATR volatility regime
  - Order book bid/ask imbalance
  - Recent trade taker buy/sell momentum
  - Multi-timeframe (1m / 15m / 1h) confluence
- **Confidence scoring** (0–100%) with Kelly criterion bet sizing
- **Real-time data** from Binance public API (no API key needed)

### Kalshi Integration
- Automatic BTC market discovery (short-duration ≤15min contracts)
- Manual and signal-driven bet placement
- Portfolio position tracking
- Bet settlement and P&L tracking

### Dashboard
- Real-time BTC candlestick chart (1m/5m/15m/1h)
- Live signal badge with component breakdown
- Indicator gauges (RSI, MACD, ADX, Bollinger Bands, EMA alignment)
- Analysis reasoning list
- Open bets + history table
- Aggregated P&L statistics
- Auto-bet configuration with Kelly fraction slider

## Quick Start

```bash
# 1. Navigate to the app directory
cd kalshi_btc

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure credentials
cp .env.example .env
# Edit .env with your Kalshi credentials

# 5. Run the server
python run.py

# 6. Open the dashboard
# http://localhost:8000
```

## Configuration (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `KALSHI_EMAIL` | — | Your Kalshi account email |
| `KALSHI_PASSWORD` | — | Your Kalshi account password |
| `KALSHI_ENV` | `demo` | `demo` or `live` |
| `MIN_CONFIDENCE` | `0.62` | Minimum signal confidence to place a bet |
| `MAX_BET_SIZE` | `10.0` | Max dollars per bet |
| `MAX_EXPOSURE` | `50.0` | Max total dollars at risk |
| `KELLY_FRACTION` | `0.25` | Kelly fraction (0.25 = quarter-Kelly) |

> **Note:** Without Kalshi credentials the app runs in **data-only mode** — prediction signals and charts work, but no bets can be placed.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Dashboard (HTML) |
| GET | `/api/health` | Health check |
| GET | `/api/btc/price` | Current BTC price + 24h stats |
| GET | `/api/btc/klines` | Historical candles (`?interval=5m&limit=100`) |
| GET | `/api/prediction` | Latest 5-min prediction signal |
| GET | `/api/markets` | Open Kalshi BTC markets |
| GET | `/api/markets/5min` | BTC markets expiring ≤15min |
| POST | `/api/bet/manual` | Place manual bet |
| POST | `/api/bet/signal` | Bet on current signal (Kelly-sized) |
| GET/POST | `/api/bet/auto/config` | Get/set auto-bet config |
| GET | `/api/bets` | All bets (`?status=open\|won\|lost`) |
| GET | `/api/stats` | Aggregated P&L stats |
| GET | `/api/positions` | Kalshi portfolio positions |
| GET | `/api/balance` | Kalshi account balance |
| WS | `/ws` | Real-time updates feed |

## Project Structure

```
kalshi_btc/
├── backend/
│   ├── __init__.py
│   ├── main.py           # FastAPI app + WebSocket + REST endpoints
│   ├── kalshi_client.py  # Kalshi API v2 client (auth, markets, orders)
│   ├── btc_data.py       # Binance BTC price & candle fetcher
│   ├── predictor.py      # 7-factor technical analysis prediction engine
│   ├── bet_manager.py    # Kelly sizing + bet lifecycle management
│   └── models.py         # Pydantic request/response schemas
├── frontend/
│   ├── index.html        # Single-page dashboard
│   ├── style.css         # Dark theme styling
│   └── app.js            # WebSocket + REST client + chart rendering
├── requirements.txt
├── .env.example
├── run.py                # Server entry point
└── README.md
```

## Prediction Model Details

### Signal Components

| Component | Weight | Indicators Used |
|-----------|--------|-----------------|
| Trend | 20% | EMA-8/13/21/34/55 ribbon, ADX, +DI/-DI |
| Momentum | 20% | RSI-14, MACD histogram, Stochastic K/D crossovers |
| Volatility | 10% | Bollinger Bands %B, BB squeeze detection, ATR |
| Volume | 15% | Volume ratio (vs 20-bar avg), OBV trend |
| Order Book | 15% | Bid/ask volume imbalance (top 20 levels) |
| Trade Flow | 10% | Taker buy/sell ratio from recent aggTrades |
| Multi-TF | 10% | 1m/15m/1h EMA structure alignment |

### Kelly Criterion Sizing

```
Kelly % = (p × b − q) / b

Where:
  p = predicted probability of winning (signal confidence)
  q = 1 − p
  b = net odds (payout/cost − 1)
```

Uses **quarter-Kelly** (default) for conservative sizing that limits drawdown while maintaining edge exploitation.

## Risk Warning

**This software is for educational and research purposes.** Prediction markets involve financial risk. Past prediction accuracy does not guarantee future results. Never bet more than you can afford to lose. Always start with the demo environment.
