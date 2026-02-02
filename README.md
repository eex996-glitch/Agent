# Futures Trading Agent (Kali Linux Edition)

Automated futures trading system for prop firm evaluations (Topstep, Apex, etc.)

## Features

- **GUI Interface**: Full graphical interface with Kali-style dark theme
- **News Feed**: Real-time financial news with sentiment analysis
- **Model Health**: Live confidence metrics and profit visualization
- **Backtest**: Test strategies on historical data
- **Paper Trading**: Local simulation (no API needed)
- **Demo Trading**: Tradovate demo account via API
- **Live Trading**: Apex Trader Funding via Tradovate API
- **Sentiment-Based Trading**: News sentiment automatically adjusts trading parameters

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

# 4. Launch GUI (recommended)
python main.py --gui

# 5. Or run CLI backtest
python main.py --mode backtest --symbol MES

# 6. Or run CLI paper trading
python main.py --mode paper --symbol MESZ4
```

## GUI Interface

Launch the full graphical interface with:
```bash
python main.py --gui
```

### GUI Features
- **Dashboard**: Real-time trading display with position tracking
- **News Feed**: Live financial news with sentiment analysis
- **Model Health**: Confidence gauges and equity curve visualization
- **Dark Theme**: Kali-style green-on-black interface

### Screenshots
The GUI includes:
- Trading controls (start/stop, symbol selection, risk settings)
- Live P&L and drawdown tracking
- News sentiment gauge (-1 to +1 scale)
- Component confidence bars (trend, signal, risk, sentiment)
- Equity curve chart with profit highlighting

## Trading Modes

### Backtest
Test your strategy on historical data:
```bash
python main.py --mode backtest --symbol MES --account-size 50000
```

### Paper Trading (Local)
Simulate trading without any API connection:
```bash
python main.py --mode paper --symbol MESZ4 --interval 60
```

### Demo Trading (Tradovate API)
Trade on Tradovate's demo account:
```bash
# Set credentials first
export TRADOVATE_USERNAME='your_username'
export TRADOVATE_PASSWORD='your_password'
export TRADOVATE_CID='your_client_id'
export TRADOVATE_SEC='your_secret_key'

python main.py --mode demo --symbol MESZ4
```

### Live Trading (Apex/Tradovate)
Trade real money on your Apex account:
```bash
# Set credentials
export TRADOVATE_USERNAME='your_apex_username'
export TRADOVATE_PASSWORD='your_apex_password'
export TRADOVATE_CID='your_client_id'
export TRADOVATE_SEC='your_secret_key'

# Requires confirmation
python main.py --mode live --symbol MESZ4
```

## Getting Tradovate API Access

1. **Create Tradovate Account**: https://www.tradovate.com
2. **Fund Account**: $1,000+ required for API access
3. **Enable API**: Settings > API Access > Purchase subscription
4. **Generate Keys**: Click "Generate API Key", complete attestations
5. **Save Credentials**: Store CID (Client ID) and SEC (Secret Key)

For **Apex Trader Funding**:
- Use your Apex credentials (separate from direct Tradovate)
- Connect via Tradovate platform
- Same API endpoints work

## Configuration

### Account Sizes (Topstep Rules)
| Size | Profit Target | Max Loss | Max Contracts |
|------|--------------|----------|---------------|
| 50K  | $3,000       | $2,000   | 5             |
| 100K | $6,000       | $3,000   | 10            |
| 150K | $9,000       | $4,500   | 15            |

### Environment Variables
```bash
# Required for demo/live trading
export TRADOVATE_USERNAME='username'
export TRADOVATE_PASSWORD='password'
export TRADOVATE_CID='client_id'
export TRADOVATE_SEC='secret_key'

# Optional
export TRADOVATE_DEVICE_ID='device_id'
```

## Command Line Options

```
--gui, -g         Launch graphical interface
--mode, -m        Trading mode: backtest, paper, demo, live
--symbol, -s      Contract symbol (e.g., MES, MESZ4, ESH5)
--account-size    Account size: 50000, 100000, 150000
--risk-per-trade  Risk per trade (0.01 = 1%)
--interval, -i    Update interval in seconds (default: 60)
--analyze         Analyze market conditions
--show-config     Show current configuration
```

## News Feed & Sentiment Analysis

The system pulls news from multiple sources and analyzes sentiment to adjust trading:

### News Sources (configure via environment variables)
```bash
export NEWSAPI_KEY='your_key'        # newsapi.org
export ALPHAVANTAGE_KEY='your_key'   # Alpha Vantage
export FINNHUB_KEY='your_key'        # Finnhub
```

### Sentiment Impact on Trading
| Sentiment Score | Position Size | Direction Bias |
|----------------|---------------|----------------|
| > 0.5 (Strong Bullish) | +20% | Favor longs |
| > 0.2 (Bullish) | Normal | Slight long bias |
| -0.2 to 0.2 (Neutral) | Normal | No bias |
| < -0.2 (Bearish) | Normal | Slight short bias |
| < -0.5 (Strong Bearish) | -20% | Favor shorts |

### High-Impact News Handling
- Automatically pauses new entries for 5 minutes
- Widens stop losses by 50%
- Detected keywords: Fed, FOMC, CPI, Jobs Report, GDP

## Performance Logging & GitHub Sync

The system tracks all trading activity and syncs results to GitHub.

### Features
- **Session Logging**: Every trading session is recorded with full trade history
- **Performance Metrics**: Win rate, profit factor, Sharpe ratio, drawdown, and more
- **GitHub Sync**: Automatically push results to your GitHub repository
- **CSV Export**: Export trades for external analysis

### Logged Metrics
| Metric | Description |
|--------|-------------|
| Win Rate | Percentage of profitable trades |
| Profit Factor | Gross profit / Gross loss |
| Sharpe Ratio | Risk-adjusted return measure |
| Max Drawdown | Largest peak-to-trough decline |
| Expectancy | Expected profit per trade |
| Consistency Score | How evenly distributed profits are |

### GitHub Sync
Results are automatically synced to the `results/` directory:
```
results/
├── PERFORMANCE_SUMMARY.md    # Overall statistics
└── session_<id>/
    ├── session.json          # Full session data
    ├── trades.csv            # Trade list
    └── report.md             # Markdown report
```

Each sync creates a commit with P&L summary in the message.

## Project Structure

```
futures_trading_agent/
├── main.py                      # Entry point (CLI + GUI)
├── requirements.txt             # Dependencies
├── config/
│   ├── settings.py              # Configuration
│   └── prop_firm_rules.py       # Topstep rules
├── data/
│   └── fetcher.py               # Yahoo Finance data
├── strategy/
│   ├── trend_following.py       # Main strategy
│   └── indicators.py            # Technical indicators
├── risk/
│   └── manager.py               # Risk management
├── backtest/
│   └── engine.py                # Backtesting
├── execution/
│   ├── paper_trading.py         # Paper trading engine
│   ├── tradovate_client.py      # Tradovate API client
│   ├── trading_interface.py     # Unified interface
│   └── live_trader.py           # Live trading runner
├── gui/                         # Graphical Interface
│   ├── main_window.py           # Main application window
│   ├── dashboard.py             # Trading dashboard
│   ├── news_feed.py             # News feed widget
│   ├── model_health.py          # Health visualization
│   └── logs_widget.py           # Logs display and GitHub sync
├── news/                        # News & Sentiment
│   ├── fetcher.py               # Multi-source news fetcher
│   └── sentiment.py             # Sentiment analysis engine
├── logs/                        # Performance Logging (NEW)
│   ├── tracker.py               # Trade and session tracking
│   ├── metrics.py               # Performance metrics calculator
│   ├── storage.py               # Log persistence
│   └── github_sync.py           # GitHub sync functionality
└── results/                     # Synced results (gitignore optional)
```

## Strategy

**Trend Following** with:
- EMA alignment (9/21/200)
- ADX trend strength filter (>25)
- RSI momentum filter
- ATR-based stops and targets
- Bracket orders (entry + stop loss + take profit)

## Risk Management

- 1% max risk per trade (configurable)
- Position sizing based on ATR
- Prop firm drawdown limits enforced
- Scaling plan limits
- Daily trade limits

## VirtualBox Shared Folders

If running Kali in VirtualBox:
```bash
# Find shared folders
ls /media/sf_*

# Add user to vboxsf group
sudo usermod -aG vboxsf $USER
# Log out and back in
```

## Disclaimer

⚠️ **RISK WARNING**

Futures trading involves substantial risk of loss. This software is for educational purposes only. Past performance does not guarantee future results. Only trade with money you can afford to lose.

Not financial advice. Use at your own risk.

## License

MIT License
