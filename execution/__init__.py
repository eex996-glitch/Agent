"""
Execution module for paper and live trading

Supports:
- Paper trading (local simulation)
- Tradovate Demo (paper via Tradovate API)
- Tradovate Live (MyFundedFutures/MFFU)
"""

from .paper_trading import PaperTradingEngine
from .tradovate_client import (
    TradovateClient,
    TradovateCredentials,
    TradovateEnvironment,
    OrderResult,
    Position,
    AccountInfo,
    create_demo_client,
    create_live_client
)
from .trading_interface import (
    TradingInterface,
    TradingMode,
    PaperTradingInterface,
    TradovateInterface,
    UnifiedOrderResult,
    UnifiedPosition,
    UnifiedBalance,
    create_trading_interface
)

__all__ = [
    # Paper Trading
    "PaperTradingEngine",
    
    # Tradovate Client
    "TradovateClient",
    "TradovateCredentials",
    "TradovateEnvironment",
    "OrderResult",
    "Position",
    "AccountInfo",
    "create_demo_client",
    "create_live_client",
    
    # Unified Interface
    "TradingInterface",
    "TradingMode",
    "PaperTradingInterface",
    "TradovateInterface",
    "UnifiedOrderResult",
    "UnifiedPosition",
    "UnifiedBalance",
    "create_trading_interface"
]
