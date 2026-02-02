#!/usr/bin/env python3
"""
Futures Trading Agent - Main Entry Point
Kali Linux Edition with GUI Support

Supports:
- Backtest: Test strategy on historical data
- Paper: Local simulation trading
- Demo: Tradovate demo account
- Live: Live trading via Tradovate/MFFU
- GUI: Full graphical interface with news feed and model health

Usage:
    python main.py --gui                          # Launch GUI
    python main.py --mode backtest --symbol MES   # CLI backtest
    python main.py --mode paper --symbol MESZ4    # CLI paper trading
    python main.py --mode demo --symbol MESZ4     # CLI demo trading
    python main.py --mode live --symbol MESZ4     # CLI live trading
"""

import argparse
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import MARKETS
from config.prop_firm_rules import MFFURules, get_mffu_rules
from data.fetcher import DataFetcher
from strategy.trend_following import TrendFollowingStrategy
from strategy.indicators import Indicators
from backtest.engine import BacktestEngine, BacktestConfig


def setup_argparse():
    parser = argparse.ArgumentParser(description='Futures Trading Agent - Kali Linux Edition')
    parser.add_argument('--gui', '-g', action='store_true', help='Launch graphical interface')
    parser.add_argument('--mode', '-m', choices=['backtest', 'paper', 'demo', 'live'], default='backtest')
    parser.add_argument('--symbol', '-s', default='MES', help='Symbol (e.g., MES, MESZ4)')
    parser.add_argument('--start', type=str, default=None)
    parser.add_argument('--end', type=str, default=None)
    parser.add_argument('--account-size', '-a', type=int, default=50000)
    parser.add_argument('--risk-per-trade', '-r', type=float, default=0.01)
    parser.add_argument('--interval', '-i', type=int, default=60, help='Update interval (seconds)')
    parser.add_argument('--show-config', action='store_true')
    parser.add_argument('--analyze', action='store_true')
    parser.add_argument('--clear-cache', action='store_true')
    return parser


def run_gui(args):
    """Launch the graphical user interface"""
    print("\n=== Launching GUI ===\n")
    print("Starting Futures Trading Agent GUI...")
    print("Kali Linux Dark Theme Enabled\n")

    try:
        from gui.main_window import run_gui as launch_gui
        return launch_gui()
    except ImportError as e:
        print(f"Error: Could not import GUI module: {e}")
        print("\nMake sure PyQt5 is installed:")
        print("  sudo apt install python3-pyqt5")
        print("  pip install PyQt5")
        return 1
    except Exception as e:
        print(f"Error launching GUI: {e}")
        return 1


def show_config(args):
    print("\n" + "="*50)
    print("CONFIGURATION")
    print("="*50)
    print(f"\nAccount: ${args.account_size:,}")
    
    rules = MFFURules(f"{args.account_size//1000}K")
    print(f"Profit Target: ${rules.profit_target:,.0f}")
    print(f"Max Loss: ${rules.max_loss_limit:,.0f}")

    print("\n--- Trading Modes ---")
    print("  backtest - Historical testing")
    print("  paper    - Local simulation")
    print("  demo     - Tradovate demo API")
    print("  live     - MFFU/Tradovate live")
    
    print("\n--- Markets ---")
    for sym, mkt in MARKETS.items():
        print(f"  {sym}: {mkt.name}")
    
    print("\n--- Tradovate Credentials ---")
    env_vars = ["TRADOVATE_USERNAME", "TRADOVATE_PASSWORD", "TRADOVATE_CID", "TRADOVATE_SEC"]
    configured = all(os.getenv(v) for v in env_vars)
    print(f"  Configured: {'Yes' if configured else 'No'}")
    if not configured:
        print("\n  Set for demo/live trading:")
        for v in env_vars:
            print(f"    export {v}='...'")


def analyze_market(args):
    print(f"\n=== Market Analysis: {args.symbol} ===\n")
    
    fetcher = DataFetcher(use_cache=True)
    data = fetcher.fetch_historical(args.symbol, days_back=90, interval='1d')
    
    if data.empty:
        print("Error: Could not fetch data")
        return
    
    data = Indicators.add_all_indicators(data)
    latest = data.iloc[-1]
    
    print(f"Price: ${latest['close']:.2f}")
    print(f"Trend: {'BULLISH' if latest['close'] > latest['ema_trend'] else 'BEARISH'}")
    print(f"ADX: {latest['adx']:.1f}")
    print(f"RSI: {latest['rsi']:.1f}")
    print(f"ATR: {latest['atr']:.2f}")


def run_backtest(args):
    print("\n=== Backtest ===\n")
    
    fetcher = DataFetcher(use_cache=True)
    data = fetcher.fetch_intraday(args.symbol, interval='5m', days_back=60)
    
    if data.empty:
        print("Error: Could not fetch data")
        return
    
    print(f"Symbol: {args.symbol}")
    print(f"Bars: {len(data)}")
    
    strategy = TrendFollowingStrategy(name="TrendFollowing")
    data = strategy.prepare_data(data)
    
    base = args.symbol.rstrip('0123456789').upper()
    market = MARKETS.get(base, MARKETS['MES'])
    rules = MFFURules(f"{args.account_size//1000}K")
    
    config = BacktestConfig(
        starting_balance=float(args.account_size),
        symbol=args.symbol,
        point_value=market.point_value,
        tick_size=market.tick_size,
        max_loss_limit=rules.max_loss_limit,
        daily_loss_limit=rules.daily_loss_limit,
        max_risk_per_trade=args.risk_per_trade,
        max_contracts=rules.max_contracts
    )
    
    engine = BacktestEngine(config)
    result = engine.run(strategy, data, start_idx=250)
    result.print_summary()


def run_paper_trading(args):
    print("\n=== Paper Trading ===\n")
    print(f"Symbol: {args.symbol}")
    print(f"Account: ${args.account_size:,}")
    print("Press Ctrl+C to stop\n")
    
    try:
        from execution.live_trader import LiveTrader
        from execution.trading_interface import TradingMode
        
        trader = LiveTrader(
            symbol=args.symbol,
            mode=TradingMode.PAPER,
            account_size=args.account_size,
            risk_per_trade=args.risk_per_trade,
            update_interval=args.interval,
            prop_firm_tier=f"{args.account_size//1000}k"
        )
        trader.run()
    except KeyboardInterrupt:
        print("\nStopped")


def run_demo_trading(args):
    print("\n=== Demo Trading (Tradovate) ===\n")
    
    from execution.tradovate_client import TradovateCredentials
    from execution.live_trader import LiveTrader
    from execution.trading_interface import TradingMode
    
    creds = TradovateCredentials.from_env()
    if not creds.validate():
        print("Error: Set TRADOVATE_* environment variables")
        return
    
    print(f"Symbol: {args.symbol}")
    print("Press Ctrl+C to stop\n")
    
    try:
        trader = LiveTrader(
            symbol=args.symbol,
            mode=TradingMode.DEMO,
            account_size=args.account_size,
            risk_per_trade=args.risk_per_trade,
            credentials=creds,
            update_interval=args.interval,
            prop_firm_tier=f"{args.account_size//1000}k"
        )
        trader.run()
    except KeyboardInterrupt:
        print("\nStopped")


def run_live_trading(args):
    print("\n=== LIVE TRADING ===\n")
    print("⚠️  WARNING: REAL MONEY!\n")
    
    from execution.tradovate_client import TradovateCredentials
    from execution.live_trader import LiveTrader
    from execution.trading_interface import TradingMode
    
    creds = TradovateCredentials.from_env()
    if not creds.validate():
        print("Error: Set TRADOVATE_* environment variables")
        return
    
    confirm = input("Type 'CONFIRM' to proceed: ")
    if confirm != "CONFIRM":
        print("Cancelled")
        return
    
    print(f"\nSymbol: {args.symbol}")
    print("Press Ctrl+C to stop\n")
    
    try:
        trader = LiveTrader(
            symbol=args.symbol,
            mode=TradingMode.LIVE,
            account_size=args.account_size,
            risk_per_trade=args.risk_per_trade,
            credentials=creds,
            update_interval=args.interval,
            prop_firm_tier=f"{args.account_size//1000}k"
        )
        trader.run()
    except KeyboardInterrupt:
        print("\nStopped")


def main():
    parser = setup_argparse()
    args = parser.parse_args()

    # Launch GUI if requested
    if args.gui:
        return run_gui(args)

    print("\n" + "="*50)
    print("   FUTURES TRADING AGENT")
    print("   Kali Linux Edition")
    print("   Paper | Demo | Live Trading")
    print("="*50)
    print("\n  Tip: Run with --gui for graphical interface\n")

    if args.show_config:
        show_config(args)
        return 0

    if args.clear_cache:
        DataFetcher().clear_cache()
        print("Cache cleared")
        return 0

    if args.analyze:
        analyze_market(args)
        return 0

    mode_handlers = {
        'backtest': run_backtest,
        'paper': run_paper_trading,
        'demo': run_demo_trading,
        'live': run_live_trading
    }

    handler = mode_handlers.get(args.mode)
    if handler:
        handler(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
