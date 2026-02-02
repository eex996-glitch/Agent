"""
Global Configuration Settings for Futures Trading Agent

This module contains all configurable parameters for the trading system.
Modify these settings to customize behavior for different markets and risk profiles.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
import os
from datetime import time


class TradingMode(Enum):
    """Trading operation modes"""
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


class PropFirm(Enum):
    """Supported prop trading firms"""
    MFFU = "mffu"  # MyFundedFutures
    CUSTOM = "custom"


@dataclass
class AccountConfig:
    """Account configuration settings"""
    # Account tier (50K, 100K, 150K for MFFU)
    account_size: int = 50000

    # Starting balance for paper trading
    starting_balance: float = 50000.0

    # Currency
    currency: str = "USD"

    # Prop firm selection
    prop_firm: PropFirm = PropFirm.MFFU


@dataclass
class RiskConfig:
    """Risk management configuration"""
    # Maximum risk per trade as percentage of account
    max_risk_per_trade: float = 0.01  # 1%
    
    # Maximum daily loss as percentage of account
    max_daily_loss: float = 0.02  # 2%
    
    # Maximum number of consecutive losses before circuit breaker
    max_consecutive_losses: int = 3
    
    # Maximum number of open positions
    max_open_positions: int = 1
    
    # Trailing stop ATR multiplier
    trailing_stop_atr_mult: float = 2.0
    
    # Take profit ATR multiplier
    take_profit_atr_mult: float = 3.0
    
    # Risk/Reward minimum ratio
    min_risk_reward: float = 1.5
    
    # Maximum position hold time in minutes (0 = no limit)
    max_hold_time_minutes: int = 240
    
    # Daily profit target for consistency
    daily_profit_target: float = 200.0


@dataclass 
class MarketConfig:
    """Market configuration for a specific futures contract"""
    symbol: str = "ES=F"  # Yahoo Finance symbol
    name: str = "E-mini S&P 500"
    exchange: str = "CME"
    
    # Contract specifications
    tick_size: float = 0.25
    tick_value: float = 12.50  # Dollar value per tick
    point_value: float = 50.0  # Dollar value per point
    
    # Margin requirements (approximate)
    initial_margin: float = 12650.0
    maintenance_margin: float = 11500.0
    day_trade_margin: float = 500.0  # Reduced for day trading
    
    # Trading hours (CT timezone)
    market_open: time = time(17, 0)  # 5:00 PM CT Sunday
    market_close: time = time(16, 0)  # 4:00 PM CT Friday
    daily_close: time = time(16, 0)  # Daily settlement
    daily_open: time = time(17, 0)  # Daily re-open
    
    # Preferred trading session
    session_start: time = time(8, 30)  # Regular trading hours start
    session_end: time = time(15, 0)  # Regular trading hours end


# Pre-configured market definitions
MARKETS: Dict[str, MarketConfig] = {
    "ES": MarketConfig(
        symbol="ES=F",
        name="E-mini S&P 500",
        exchange="CME",
        tick_size=0.25,
        tick_value=12.50,
        point_value=50.0,
        initial_margin=12650.0,
        maintenance_margin=11500.0,
        day_trade_margin=500.0
    ),
    "MES": MarketConfig(
        symbol="MES=F",
        name="Micro E-mini S&P 500",
        exchange="CME",
        tick_size=0.25,
        tick_value=1.25,
        point_value=5.0,
        initial_margin=1265.0,
        maintenance_margin=1150.0,
        day_trade_margin=50.0
    ),
    "NQ": MarketConfig(
        symbol="NQ=F",
        name="E-mini NASDAQ-100",
        exchange="CME",
        tick_size=0.25,
        tick_value=5.0,
        point_value=20.0,
        initial_margin=17600.0,
        maintenance_margin=16000.0,
        day_trade_margin=500.0
    ),
    "MNQ": MarketConfig(
        symbol="MNQ=F",
        name="Micro E-mini NASDAQ-100",
        exchange="CME",
        tick_size=0.25,
        tick_value=0.50,
        point_value=2.0,
        initial_margin=1760.0,
        maintenance_margin=1600.0,
        day_trade_margin=50.0
    ),
    "YM": MarketConfig(
        symbol="YM=F",
        name="E-mini Dow",
        exchange="CBOT",
        tick_size=1.0,
        tick_value=5.0,
        point_value=5.0,
        initial_margin=9350.0,
        maintenance_margin=8500.0,
        day_trade_margin=500.0
    ),
    "RTY": MarketConfig(
        symbol="RTY=F",
        name="E-mini Russell 2000",
        exchange="CME",
        tick_size=0.10,
        tick_value=5.0,
        point_value=50.0,
        initial_margin=6820.0,
        maintenance_margin=6200.0,
        day_trade_margin=500.0
    ),
    "CL": MarketConfig(
        symbol="CL=F",
        name="Crude Oil",
        exchange="NYMEX",
        tick_size=0.01,
        tick_value=10.0,
        point_value=1000.0,
        initial_margin=6160.0,
        maintenance_margin=5600.0,
        day_trade_margin=500.0
    ),
    "GC": MarketConfig(
        symbol="GC=F",
        name="Gold",
        exchange="COMEX",
        tick_size=0.10,
        tick_value=10.0,
        point_value=100.0,
        initial_margin=10450.0,
        maintenance_margin=9500.0,
        day_trade_margin=500.0
    ),
}


@dataclass
class StrategyConfig:
    """Strategy configuration settings"""
    # Timeframes for analysis
    primary_timeframe: str = "5min"  # For trade execution
    secondary_timeframe: str = "15min"  # For trend confirmation
    higher_timeframe: str = "1h"  # For bias direction
    
    # Moving Average Periods
    fast_ema: int = 9
    medium_ema: int = 21
    slow_ema: int = 50
    trend_ema: int = 200
    
    # RSI Settings
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    
    # ADX Settings
    adx_period: int = 14
    adx_threshold: float = 25.0  # Minimum for trend confirmation
    
    # ATR Settings
    atr_period: int = 14
    
    # MACD Settings
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    
    # Volume Settings
    volume_ma_period: int = 20
    volume_threshold: float = 1.5  # Multiplier for volume confirmation
    
    # Entry Settings
    pullback_threshold: float = 0.382  # Fib retracement level
    breakout_buffer: float = 2.0  # Ticks above/below breakout level


@dataclass
class DataConfig:
    """Data configuration settings"""
    # Data source
    data_source: str = "yfinance"  # Options: yfinance, alpaca, ib
    
    # Historical data settings
    lookback_days: int = 365  # Days of historical data to fetch
    
    # Cache settings
    cache_enabled: bool = True
    cache_dir: str = "./data/cache"
    
    # Update frequency
    update_interval_seconds: int = 5  # For paper/live trading


@dataclass
class LoggingConfig:
    """Logging configuration"""
    log_level: str = "INFO"
    log_dir: str = "./logs"
    log_to_file: bool = True
    log_to_console: bool = True
    
    # Trade logging
    log_trades: bool = True
    trade_log_file: str = "trades.csv"


@dataclass
class Settings:
    """Main settings container"""
    # Mode
    mode: TradingMode = TradingMode.BACKTEST
    
    # Sub-configurations
    account: AccountConfig = field(default_factory=AccountConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    data: DataConfig = field(default_factory=DataConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    # Active market
    active_market: str = "MES"  # Key from MARKETS dict
    
    @property
    def market(self) -> MarketConfig:
        """Get the active market configuration"""
        return MARKETS.get(self.active_market, MARKETS["MES"])
    
    def get_market(self, symbol: str) -> Optional[MarketConfig]:
        """Get market configuration by symbol"""
        return MARKETS.get(symbol)


# Global settings instance
settings = Settings()


def load_settings_from_env():
    """Load settings overrides from environment variables"""
    global settings
    
    # Account settings
    if os.getenv("ACCOUNT_SIZE"):
        settings.account.account_size = int(os.getenv("ACCOUNT_SIZE"))
    
    if os.getenv("STARTING_BALANCE"):
        settings.account.starting_balance = float(os.getenv("STARTING_BALANCE"))
    
    # Risk settings
    if os.getenv("MAX_RISK_PER_TRADE"):
        settings.risk.max_risk_per_trade = float(os.getenv("MAX_RISK_PER_TRADE"))
    
    if os.getenv("MAX_DAILY_LOSS"):
        settings.risk.max_daily_loss = float(os.getenv("MAX_DAILY_LOSS"))
    
    # Market selection
    if os.getenv("ACTIVE_MARKET"):
        settings.active_market = os.getenv("ACTIVE_MARKET")
    
    # Mode
    if os.getenv("TRADING_MODE"):
        mode_str = os.getenv("TRADING_MODE").lower()
        settings.mode = TradingMode(mode_str)


# Load environment overrides on import
load_settings_from_env()
