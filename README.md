# Futures Trading Agent (Kali Linux Edition)

Automated futures trading system for prop firm evaluations (Topstep, Apex, etc.)

## Features

- **Backtest**: Test strategies on historical data
- **Paper Trading**: Local simulation (no API needed)
- **Demo Trading**: Tradovate demo account via API
- **Live Trading**: Apex Trader Funding via Tradovate API

## Quick Start (Kali Linux)

```bash
# 1. Install dependencies
sudo apt update
sudo apt install -y python3-pip python3-venv

# 2. Setup virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install packages
pip install -r requirements.txt

# 4. Run backtest
python main.py --mode backtest --symbol MES

# 5. Run paper trading
python main.py --mode paper --symbol MESZ4
```

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
--mode, -m        Trading mode: backtest, paper, demo, live
--symbol, -s      Contract symbol (e.g., MES, MESZ4, ESH5)
--account-size    Account size: 50000, 100000, 150000
--risk-per-trade  Risk per trade (0.01 = 1%)
--interval, -i    Update interval in seconds (default: 60)
--analyze         Analyze market conditions
--show-config     Show current configuration
```

## Project Structure

```
futures_trading_agent_kali/
├── main.py                      # Entry point
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
└── requirements.txt
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
