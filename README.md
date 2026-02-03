# MFFU Futures Trading Agent

Automated futures trading system built for **MyFundedFutures (MFFU)** prop firm evaluations and funded accounts. Features a PyQt5 GUI with Kali Linux dark theme, multi-strategy tournament system, and full MFFU rule compliance.

## Core Features

- **Multi-Strategy Engine**: 4 strategy types (Trend Following, Mean Reversion, Breakout, Adaptive) with 6+ variants
- **Strategy Tournament**: Automated backtesting of all strategies on identical data to select the best performer
- **MFFU Rule Compliance**: EOD trailing drawdown, scaling plans, no daily loss limit, no consistency rule
- **Model Health Dashboard**: Real backtest-driven confidence metrics (no simulated/random data)
- **GUI Interface**: Full PyQt5 interface with Kali-style dark theme
- **Risk Management**: Position sizing, drawdown monitoring, scaling plan enforcement
- **Backtest Engine**: Tournament-powered backtesting with detailed trade analysis

## Quick Start (Kali Linux)

```bash
# 1. Install dependencies
sudo apt update
sudo apt install -y python3-pip python3-venv python3-pyqt5

# 2. Setup virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install packages
pip install -r requirements.txt

# 4. Launch GUI
python main.py --gui

# 5. Or run CLI backtest
python main.py --mode backtest --symbol MES --account-size 50000
```

## Trading Strategies

### Trend Following
- EMA alignment (9/21/50/200) for trend direction
- ADX trend strength filter (configurable threshold)
- RSI momentum confirmation
- ATR-based dynamic stops and targets
- Aggressive variant with tighter stops and wider targets

### Mean Reversion
- Bollinger Bands %B for overbought/oversold detection
- RSI, Stochastic K/D crossovers, Williams %R confirmation
- Multi-indicator scoring system (0-100, threshold 60)
- Optional reversal candle requirement
- Relaxed variant with wider entry zones

### Breakout
- Donchian Channel breakout detection
- Volume confirmation (configurable threshold)
- Bollinger/Keltner squeeze detection
- Inside bar breakout patterns
- Failed breakout exit logic (within 3 bars)
- Turtle Trading exit channel

### Adaptive Multi-Pattern
- Market regime detection (trending up/down, ranging, breakout, volatile)
- Candlestick pattern recognition (engulfing, pin bars, inside bars, doji)
- MACD divergence detection
- Connors RSI(2) for mean reversion
- Supertrend confirmation
- Ensemble scoring with regime-specific weights

## Strategy Tournament

The tournament system backtests all 6 strategy variants on identical synthetic data:

1. **TrendFollowing** - Standard trend following
2. **TrendFollowing_Aggressive** - Lower ADX threshold, tighter stops
3. **MeanReversion** - Standard mean reversion with reversal candle
4. **MeanReversion_Relaxed** - Wider entry zones, no reversal candle required
5. **Breakout** - Donchian channel breakouts with volume confirmation
6. **Adaptive** - Multi-pattern regime-aware strategy

### Scoring System
| Metric | Weight |
|--------|--------|
| Sharpe Ratio | 25% |
| Profit Factor | 20% |
| Win Rate | 15% |
| Total Return | 15% |
| Max Drawdown (penalty) | 15% |
| Consistency | 10% |

Results are saved to `logs/tournament_results.json` and drive the Model Health dashboard.

## GUI Interface

Launch with `python main.py --gui`

### Dashboard
- Real-time price display for selected MFFU contract
- Account balance, P&L, drawdown, and win rate cards
- Trading controls (start/stop, symbol selection, risk settings)
- Signal assessment logging with pattern detection
- Trade history table

### Model Health
- Overall confidence gauge from tournament backtest data
- Component confidence bars (Trend Detection, Signal Quality, Risk Assessment, Consistency)
- Best strategy performance summary
- Strategy rankings table with composite scores
- Equity curve visualization
- System health status indicators

### News Feed
- Financial news display with sentiment analysis
- Impact-weighted sentiment scoring
- Trading recommendations based on sentiment
- Sentiment factors breakdown

### Logs
- Trading session history
- Performance metrics display

## MyFundedFutures (MFFU) Rules

### Account Tiers
| Tier | Size | Profit Target | Max Loss (EOD) | Max Contracts |
|------|------|---------------|----------------|---------------|
| Starter | $50K | $3,000 | $2,000 | 5 |
| Standard | $100K | $6,000 | $3,500 | 10 |
| Premium | $150K | $9,000 | $5,000 | 15 |

### Key MFFU Advantages (Enforced in Code)
- **NO Daily Loss Limit** - `use_daily_loss_limit=False` in risk manager
- **NO Consistency Rule** - `has_consistency_rule=False` in prop firm config
- **EOD Trailing Drawdown** - Drawdown only trails at end of day, not intraday
- **No Time Limit** - No minimum trading days requirement
- **Scaling Plan** - Position sizes increase with profit milestones

### Scaling Plan (Starter $50K)
| Profit Level | Max Contracts |
|--------------|---------------|
| $0 - $999 | 2 |
| $1,000 - $1,499 | 3 |
| $1,500 - $1,999 | 4 |
| $2,000+ | 5 |

### Available Instruments (2026 Contracts)
The system supports 36 MFFU-available futures contracts across:
- **Equity Index**: ES, MES, NQ, MNQ, RTY, M2K, YM, MYM (Mar/Jun 2026)
- **Energy**: CL, MCL, NG (Mar/Jun 2026)
- **Metals**: GC, MGC, SI (Mar 2026)
- **Treasuries**: ZN, ZB, ZF, ZT (Mar 2026)
- **Currency**: 6E, M6E (Mar 2026)
- **Agriculture**: ZC, ZS, ZW (Mar 2026)

## Trading Modes

### Backtest (Tournament)
Test all strategies on synthetic data with MFFU rules:
```bash
python main.py --mode backtest --symbol MES --account-size 50000
```

### Paper Trading (Local)
Simulate trading without API connection:
```bash
python main.py --mode paper --symbol MESH6 --interval 60
```

### Demo Trading (Tradovate API)
Trade on Tradovate demo:
```bash
export TRADOVATE_USERNAME='your_username'
export TRADOVATE_PASSWORD='your_password'
export TRADOVATE_CID='your_client_id'
export TRADOVATE_SEC='your_secret_key'

python main.py --mode demo --symbol MESH6
```

### Live Trading (MFFU via Tradovate)
Trade on your MFFU funded account:
```bash
python main.py --mode live --symbol MESH6
```

## Project Structure

```
Agent/
├── main.py                          # Entry point (CLI + GUI)
├── requirements.txt                 # Dependencies
├── config/
│   ├── settings.py                  # Configuration
│   └── prop_firm_rules.py           # MFFU evaluation & funded rules
├── strategy/
│   ├── base.py                      # Base strategy class
│   ├── indicators.py                # Technical indicators library
│   ├── trend_following.py           # EMA/ADX trend strategy
│   ├── mean_reversion.py            # Bollinger/RSI reversion strategy
│   ├── breakout.py                  # Donchian/volume breakout strategy
│   ├── adaptive.py                  # Multi-pattern regime-aware strategy
│   └── tournament.py                # Strategy tournament & data generator
├── risk/
│   └── manager.py                   # Risk management (MFFU-compliant)
├── backtest/
│   └── engine.py                    # Backtesting engine
├── execution/
│   ├── paper_trading.py             # Paper trading engine
│   ├── tradovate_client.py          # Tradovate API client
│   ├── trading_interface.py         # Unified trading interface
│   └── live_trader.py               # Live trading runner
├── gui/
│   ├── main_window.py               # Main window + backtest dialog
│   ├── dashboard.py                 # Trading dashboard
│   ├── news_feed.py                 # News feed + sentiment
│   ├── model_health.py              # Tournament-driven health display
│   └── logs_widget.py               # Logs display
├── news/
│   ├── fetcher.py                   # Multi-source news fetcher
│   └── sentiment.py                 # Sentiment analysis
├── logs/
│   ├── tracker.py                   # Trade and session tracking
│   ├── metrics.py                   # Performance metrics
│   ├── storage.py                   # Log persistence
│   ├── github_sync.py               # GitHub sync functionality
│   └── tournament_results.json      # Cached tournament results
├── data/
│   └── fetcher.py                   # Market data fetcher
├── utils/
│   ├── errors.py                    # Error handling
│   └── logger.py                    # Logging configuration
└── tests/
    ├── conftest.py                  # Test configuration
    ├── test_prop_firm_rules.py      # MFFU rules tests
    └── test_error_handling.py       # Error handling tests
```

## Command Line Options

```
--gui, -g         Launch graphical interface
--mode, -m        Trading mode: backtest, paper, demo, live
--symbol, -s      Contract symbol (e.g., MES, MESH6, ESH6)
--account-size    Account size: 50000, 100000, 150000
--risk-per-trade  Risk per trade (0.01 = 1%)
--interval, -i    Update interval in seconds (default: 60)
--analyze         Analyze market conditions
--show-config     Show current configuration
```

## Risk Management

- EOD trailing drawdown enforcement (MFFU-specific)
- Position sizing based on ATR and account risk percentage
- Scaling plan enforcement per MFFU tier
- Maximum daily trade limits
- Consecutive loss circuit breaker
- Per-trade risk capping (configurable, default 1%)

## Disclaimer

**RISK WARNING**: Futures trading involves substantial risk of loss. This software is for educational purposes only. Past performance does not guarantee future results. Only trade with money you can afford to lose. Not financial advice.

## License

MIT License
