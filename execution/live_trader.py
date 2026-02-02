"""
Live Trading Runner

Connects the trading strategy to the execution interface for
paper trading or live trading via Tradovate/MFFU.
"""

import os
import sys
import time
import argparse
from datetime import datetime
from typing import Optional, Dict
import threading
from loguru import logger

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import get_market_config
from config.prop_firm_rules import get_mffu_rules
from data.fetcher import DataFetcher
from strategy.trend_following import TrendFollowingStrategy
from strategy.indicators import add_all_indicators
from risk.manager import RiskManager
from execution.trading_interface import (
    TradingMode,
    create_trading_interface
)
from execution.tradovate_client import TradovateCredentials


class LiveTrader:
    """Live Trading Runner - connects strategy to execution"""
    
    def __init__(
        self,
        symbol: str,
        mode: TradingMode = TradingMode.PAPER,
        account_size: float = 50000.0,
        risk_per_trade: float = 0.01,
        credentials: TradovateCredentials = None,
        update_interval: int = 60,
        max_daily_trades: int = 20,
        prop_firm_tier: str = "50k"
    ):
        self.symbol = symbol
        self.mode = mode
        self.account_size = account_size
        self.risk_per_trade = risk_per_trade
        self.update_interval = update_interval
        self.max_daily_trades = max_daily_trades
        
        # Create trading interface
        self.interface = create_trading_interface(
            mode=mode,
            credentials=credentials,
            initial_balance=account_size
        )
        
        # Create strategy and risk manager
        self.strategy = TrendFollowingStrategy()
        prop_rules = get_mffu_rules(prop_firm_tier)
        self.risk_manager = RiskManager(account_size, prop_rules)
        
        # Market config
        base_symbol = symbol.rstrip('0123456789')
        self.market_config = get_market_config(base_symbol)
        
        # Data fetcher
        self.data_fetcher = DataFetcher()
        
        # State
        self.running = False
        self.daily_trades = 0
        self.current_position_size = 0
        self.entry_price = 0.0
        self._stop_event = threading.Event()
        
        # Setup logging
        os.makedirs("logs", exist_ok=True)
        logger.add(f"logs/trading_{symbol}_{datetime.now():%Y%m%d}.log", level="INFO")
        logger.info(f"LiveTrader: {symbol} in {mode.value} mode")
    
    def connect(self) -> bool:
        """Connect to trading interface"""
        return self.interface.connect()
    
    def disconnect(self):
        """Disconnect from trading interface"""
        self.interface.disconnect()
    
    def get_current_data(self) -> Optional[Dict]:
        """Fetch current market data with indicators"""
        try:
            base = self.symbol.rstrip('0123456789')
            df = self.data_fetcher.get_historical_data(base, period="5d", interval="5m")
            
            if df is None or df.empty:
                return None
            
            df = add_all_indicators(df)
            latest = df.iloc[-1]
            
            return {
                "close": latest["Close"],
                "atr": latest.get("ATR_14", 1),
                "rsi": latest.get("RSI_14", 50),
                "adx": latest.get("ADX_14", 20),
                "df": df
            }
        except Exception as e:
            logger.error(f"Data error: {e}")
            return None
    
    def calculate_position_size(self, atr: float) -> int:
        """Calculate position size based on risk"""
        balance = self.interface.get_balance()
        risk_amount = balance.equity * self.risk_per_trade
        point_value = self.market_config.get("point_value", 5.0)
        stop_distance = atr * 2
        
        contracts = int(risk_amount / (stop_distance * point_value))
        max_contracts = self.risk_manager.get_max_contracts()
        
        return max(1, min(contracts, max_contracts))
    
    def check_signals(self, data: Dict) -> Optional[Dict]:
        """Check for trading signals"""
        df = data.get("df")
        if df is None:
            return None
        
        self.strategy.on_bar(df.iloc[-1], df)
        
        if self.strategy.signal:
            sig = self.strategy.signal
            close = data["close"]
            atr = data["atr"]
            
            is_long = sig["direction"] == "long"
            stop = close - atr * 2 if is_long else close + atr * 2
            target = close + atr * 3 if is_long else close - atr * 3
            
            return {
                "direction": sig["direction"],
                "entry": close,
                "stop": stop,
                "target": target,
                "atr": atr
            }
        return None
    
    def execute_entry(self, signal: Dict) -> bool:
        """Execute entry trade"""
        if not self.risk_manager.can_take_trade():
            logger.warning("Risk check failed")
            return False
        
        if self.daily_trades >= self.max_daily_trades:
            logger.warning("Max daily trades reached")
            return False
        
        qty = self.calculate_position_size(signal["atr"])
        side = "Buy" if signal["direction"] == "long" else "Sell"
        
        logger.info(f"Entry: {side} {qty} {self.symbol}")
        
        result = self.interface.place_bracket_order(
            symbol=self.symbol,
            side=side,
            quantity=qty,
            stop_loss=signal["stop"],
            take_profit=signal["target"]
        )
        
        if result.success:
            self.current_position_size = qty if side == "Buy" else -qty
            self.entry_price = signal["entry"]
            self.daily_trades += 1
            logger.info(f"Filled: {side} {qty} @ ~{signal['entry']:.2f}")
            return True
        
        logger.error(f"Entry failed: {result.message}")
        return False
    
    def update(self):
        """Single update cycle"""
        try:
            data = self.get_current_data()
            if not data:
                return
            
            self.interface.update_price(self.symbol, data["close"])
            
            # Check for entry if flat
            if self.current_position_size == 0:
                signal = self.check_signals(data)
                if signal:
                    self.execute_entry(signal)
            
            # Log status
            bal = self.interface.get_balance()
            logger.debug(f"Price: {data['close']:.2f} | Equity: ${bal.equity:,.2f}")
            
        except Exception as e:
            logger.error(f"Update error: {e}")
    
    def run(self):
        """Run trading loop"""
        if not self.connect():
            logger.error("Connection failed")
            return
        
        self.running = True
        logger.info(f"Started: {self.symbol} ({self.mode.value})")
        
        try:
            while self.running and not self._stop_event.is_set():
                self.update()
                self._stop_event.wait(self.update_interval)
        except KeyboardInterrupt:
            logger.info("Interrupted")
        finally:
            self.stop()
    
    def stop(self):
        """Stop trading"""
        logger.info("Stopping...")
        self.running = False
        self._stop_event.set()
        
        if self.current_position_size != 0:
            logger.warning("Flattening positions...")
            self.interface.flatten_all()
        
        self.disconnect()
        logger.info("Stopped")
    
    def status(self) -> Dict:
        """Get current status"""
        bal = self.interface.get_balance()
        return {
            "running": self.running,
            "mode": self.mode.value,
            "symbol": self.symbol,
            "equity": bal.equity,
            "daily_trades": self.daily_trades
        }


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description="Live Futures Trading")
    parser.add_argument("--symbol", "-s", default="MESZ4", help="Contract symbol")
    parser.add_argument("--mode", "-m", choices=["paper", "demo", "live"], default="paper")
    parser.add_argument("--balance", "-b", type=float, default=50000)
    parser.add_argument("--risk", "-r", type=float, default=0.01)
    parser.add_argument("--interval", "-i", type=int, default=60)
    parser.add_argument("--tier", "-t", choices=["50k", "100k", "150k"], default="50k")
    
    args = parser.parse_args()
    
    mode_map = {"paper": TradingMode.PAPER, "demo": TradingMode.DEMO, "live": TradingMode.LIVE}
    mode = mode_map[args.mode]
    
    credentials = None
    if mode != TradingMode.PAPER:
        credentials = TradovateCredentials.from_env()
        if not credentials.validate():
            print("\nSet Tradovate credentials:")
            print("  export TRADOVATE_USERNAME='...'")
            print("  export TRADOVATE_PASSWORD='...'")
            print("  export TRADOVATE_CID='...'")
            print("  export TRADOVATE_SEC='...'")
            sys.exit(1)
    
    trader = LiveTrader(
        symbol=args.symbol,
        mode=mode,
        account_size=args.balance,
        risk_per_trade=args.risk,
        credentials=credentials,
        update_interval=args.interval,
        prop_firm_tier=args.tier
    )
    
    print(f"\n{'='*50}")
    print(f"Live Trading: {args.symbol}")
    print(f"Mode: {args.mode.upper()}")
    print(f"Balance: ${args.balance:,.2f}")
    print(f"Risk/Trade: {args.risk*100:.1f}%")
    print(f"{'='*50}\n")
    print("Press Ctrl+C to stop\n")
    
    trader.run()


if __name__ == "__main__":
    main()
