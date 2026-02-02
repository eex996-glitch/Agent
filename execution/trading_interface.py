"""
Unified Trading Interface

Provides a consistent interface for both paper trading and live trading
through Tradovate/MFFU.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from enum import Enum
from loguru import logger

from .paper_trading import PaperTradingEngine
from .tradovate_client import (
    TradovateClient, 
    TradovateCredentials, 
    TradovateEnvironment,
    OrderResult
)


class TradingMode(Enum):
    """Trading mode selection"""
    PAPER = "paper"  # Local simulation
    DEMO = "demo"    # Tradovate demo account
    LIVE = "live"    # Live trading (MFFU, etc.)


@dataclass
class UnifiedOrderResult:
    """Standardized order result"""
    success: bool
    order_id: Optional[int] = None
    message: str = ""
    filled_price: Optional[float] = None
    filled_quantity: int = 0


@dataclass
class UnifiedPosition:
    """Standardized position"""
    symbol: str
    quantity: int
    entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0


@dataclass
class UnifiedBalance:
    """Standardized account balance"""
    cash: float
    equity: float
    unrealized_pnl: float
    realized_pnl: float


class TradingInterface(ABC):
    """Abstract base class for trading interfaces"""
    
    @abstractmethod
    def connect(self) -> bool:
        """Connect to the trading system"""
        pass
    
    @abstractmethod
    def disconnect(self):
        """Disconnect from the trading system"""
        pass
    
    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "Market",
        price: float = None,
        stop_price: float = None
    ) -> UnifiedOrderResult:
        """Place an order"""
        pass
    
    @abstractmethod
    def place_bracket_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        stop_loss: float = None,
        take_profit: float = None,
        entry_price: float = None
    ) -> UnifiedOrderResult:
        """Place a bracket order"""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: int) -> bool:
        """Cancel an order"""
        pass
    
    @abstractmethod
    def cancel_all_orders(self) -> int:
        """Cancel all orders, return count cancelled"""
        pass
    
    @abstractmethod
    def get_positions(self) -> List[UnifiedPosition]:
        """Get open positions"""
        pass
    
    @abstractmethod
    def get_position(self, symbol: str) -> Optional[UnifiedPosition]:
        """Get position for a specific symbol"""
        pass
    
    @abstractmethod
    def flatten_position(self, symbol: str) -> UnifiedOrderResult:
        """Close a position"""
        pass
    
    @abstractmethod
    def flatten_all(self) -> int:
        """Flatten all positions, return count closed"""
        pass
    
    @abstractmethod
    def get_balance(self) -> UnifiedBalance:
        """Get account balance"""
        pass
    
    @abstractmethod
    def update_price(self, symbol: str, price: float):
        """Update current price (for paper trading)"""
        pass


class PaperTradingInterface(TradingInterface):
    """Paper trading implementation"""
    
    def __init__(self, initial_balance: float = 50000.0, slippage_ticks: int = 1):
        self.engine = PaperTradingEngine(
            initial_balance=initial_balance,
            slippage_ticks=slippage_ticks
        )
        self.connected = False
    
    def connect(self) -> bool:
        self.connected = True
        logger.info("Paper trading connected")
        return True
    
    def disconnect(self):
        self.connected = False
        logger.info("Paper trading disconnected")
    
    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "Market",
        price: float = None,
        stop_price: float = None
    ) -> UnifiedOrderResult:
        result = self.engine.place_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            stop_price=stop_price
        )
        
        return UnifiedOrderResult(
            success=result["success"],
            order_id=result.get("order_id"),
            message=result.get("message", "")
        )
    
    def place_bracket_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        stop_loss: float = None,
        take_profit: float = None,
        entry_price: float = None
    ) -> UnifiedOrderResult:
        result = self.engine.place_bracket_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        
        return UnifiedOrderResult(
            success=result["success"],
            order_id=result.get("order_id"),
            message=result.get("message", "")
        )
    
    def cancel_order(self, order_id: int) -> bool:
        result = self.engine.cancel_order(order_id)
        return result["success"]
    
    def cancel_all_orders(self) -> int:
        return self.engine.cancel_all_orders()
    
    def get_positions(self) -> List[UnifiedPosition]:
        positions = []
        for pos_dict in self.engine.get_positions():
            positions.append(UnifiedPosition(
                symbol=pos_dict["symbol"],
                quantity=pos_dict["quantity"],
                entry_price=pos_dict["entry_price"],
                current_price=pos_dict["current_price"],
                unrealized_pnl=pos_dict["unrealized_pnl"]
            ))
        return positions
    
    def get_position(self, symbol: str) -> Optional[UnifiedPosition]:
        pos_dict = self.engine.get_position(symbol)
        if pos_dict and pos_dict["quantity"] != 0:
            return UnifiedPosition(
                symbol=pos_dict["symbol"],
                quantity=pos_dict["quantity"],
                entry_price=pos_dict["entry_price"],
                current_price=pos_dict["current_price"],
                unrealized_pnl=pos_dict["unrealized_pnl"]
            )
        return None
    
    def flatten_position(self, symbol: str) -> UnifiedOrderResult:
        result = self.engine.flatten_position(symbol)
        return UnifiedOrderResult(
            success=result["success"],
            message=result.get("message", "")
        )
    
    def flatten_all(self) -> int:
        return self.engine.flatten_all()
    
    def get_balance(self) -> UnifiedBalance:
        bal = self.engine.get_balance()
        return UnifiedBalance(
            cash=bal["cash_balance"],
            equity=bal["equity"],
            unrealized_pnl=bal["unrealized_pnl"],
            realized_pnl=bal["total_pnl"]
        )
    
    def update_price(self, symbol: str, price: float):
        self.engine.update_price(symbol, price)
    
    def reset(self):
        """Reset paper trading state"""
        self.engine.reset()
    
    def get_statistics(self) -> Dict:
        """Get paper trading statistics"""
        return self.engine.get_statistics()


class TradovateInterface(TradingInterface):
    """Tradovate/MFFU trading implementation"""
    
    def __init__(
        self,
        credentials: TradovateCredentials = None,
        environment: TradovateEnvironment = TradovateEnvironment.DEMO
    ):
        self.credentials = credentials or TradovateCredentials.from_env()
        self.environment = environment
        self.client: Optional[TradovateClient] = None
        self.connected = False
    
    def connect(self) -> bool:
        if not self.credentials.validate():
            logger.error("Invalid Tradovate credentials")
            return False
        
        self.client = TradovateClient(
            credentials=self.credentials,
            environment=self.environment
        )
        
        if self.client.authenticate():
            self.connected = True
            logger.info(f"Connected to Tradovate ({self.environment.value})")
            return True
        
        logger.error("Failed to connect to Tradovate")
        return False
    
    def disconnect(self):
        if self.client:
            self.client.session.close()
        self.connected = False
        logger.info("Disconnected from Tradovate")
    
    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "Market",
        price: float = None,
        stop_price: float = None
    ) -> UnifiedOrderResult:
        if not self.client:
            return UnifiedOrderResult(success=False, message="Not connected")
        
        result = self.client.place_order(
            symbol=symbol,
            action=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            stop_price=stop_price
        )
        
        return UnifiedOrderResult(
            success=result.success,
            order_id=result.order_id,
            message=result.message
        )
    
    def place_bracket_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        stop_loss: float = None,
        take_profit: float = None,
        entry_price: float = None
    ) -> UnifiedOrderResult:
        if not self.client:
            return UnifiedOrderResult(success=False, message="Not connected")
        
        result = self.client.place_bracket_order(
            symbol=symbol,
            action=side,
            quantity=quantity,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        
        return UnifiedOrderResult(
            success=result.success,
            order_id=result.order_id,
            message=result.message
        )
    
    def cancel_order(self, order_id: int) -> bool:
        if not self.client:
            return False
        result = self.client.cancel_order(order_id)
        return result.success
    
    def cancel_all_orders(self) -> int:
        if not self.client:
            return 0
        orders = self.client.get_open_orders()
        cancelled = 0
        for order in orders:
            if self.client.cancel_order(order["id"]).success:
                cancelled += 1
        return cancelled
    
    def get_positions(self) -> List[UnifiedPosition]:
        if not self.client:
            return []
        
        positions = []
        for pos in self.client.get_positions():
            positions.append(UnifiedPosition(
                symbol=pos.symbol,
                quantity=pos.net_pos,
                entry_price=pos.net_price,
                current_price=pos.net_price  # Would need market data for current
            ))
        return positions
    
    def get_position(self, symbol: str) -> Optional[UnifiedPosition]:
        positions = self.get_positions()
        for pos in positions:
            if pos.symbol == symbol:
                return pos
        return None
    
    def flatten_position(self, symbol: str) -> UnifiedOrderResult:
        if not self.client:
            return UnifiedOrderResult(success=False, message="Not connected")
        
        # Find the contract
        contract = self.client.find_contract(symbol)
        if not contract:
            return UnifiedOrderResult(success=False, message=f"Contract {symbol} not found")
        
        result = self.client.liquidate_position(contract["id"])
        return UnifiedOrderResult(
            success=result.success,
            message=result.message
        )
    
    def flatten_all(self) -> int:
        if not self.client:
            return 0
        self.client.flatten_all()
        return len(self.client.get_positions())
    
    def get_balance(self) -> UnifiedBalance:
        if not self.client:
            return UnifiedBalance(cash=0, equity=0, unrealized_pnl=0, realized_pnl=0)
        
        balance = self.client.get_cash_balance()
        if balance:
            return UnifiedBalance(
                cash=balance.get("cashBalance", 0),
                equity=balance.get("totalEquity", 0),
                unrealized_pnl=balance.get("unrealizedPnL", 0),
                realized_pnl=balance.get("realizedPnL", 0)
            )
        
        return UnifiedBalance(cash=0, equity=0, unrealized_pnl=0, realized_pnl=0)
    
    def update_price(self, symbol: str, price: float):
        # Not needed for live trading - prices come from exchange
        pass
    
    def get_accounts(self) -> List[Dict]:
        """Get available accounts"""
        if self.client:
            return [{"id": acc.id, "name": acc.name} for acc in self.client.accounts]
        return []
    
    def set_account(self, account_id: int) -> bool:
        """Set the active trading account"""
        if self.client:
            return self.client.set_active_account(account_id)
        return False


def create_trading_interface(
    mode: TradingMode,
    credentials: TradovateCredentials = None,
    initial_balance: float = 50000.0
) -> TradingInterface:
    """
    Factory function to create the appropriate trading interface
    
    Args:
        mode: Trading mode (PAPER, DEMO, or LIVE)
        credentials: Tradovate credentials (for DEMO/LIVE modes)
        initial_balance: Starting balance for paper trading
    
    Returns:
        TradingInterface implementation
    """
    if mode == TradingMode.PAPER:
        return PaperTradingInterface(initial_balance=initial_balance)
    
    elif mode == TradingMode.DEMO:
        return TradovateInterface(
            credentials=credentials,
            environment=TradovateEnvironment.DEMO
        )
    
    elif mode == TradingMode.LIVE:
        return TradovateInterface(
            credentials=credentials,
            environment=TradovateEnvironment.LIVE
        )
    
    raise ValueError(f"Unknown trading mode: {mode}")


# ==================== Example Usage ====================

if __name__ == "__main__":
    print("Trading Interface Example")
    print("=" * 50)
    
    # Paper trading example
    print("\n1. Paper Trading Mode")
    print("-" * 30)
    
    paper = create_trading_interface(TradingMode.PAPER, initial_balance=50000)
    paper.connect()
    
    # Simulate price
    paper.update_price("MESZ4", 5000.00)
    
    # Place order
    result = paper.place_order("MESZ4", "Buy", 2, "Market")
    print(f"Order: {result}")
    
    # Check position
    positions = paper.get_positions()
    print(f"Positions: {[p.__dict__ for p in positions]}")
    
    # Check balance
    balance = paper.get_balance()
    print(f"Balance: ${balance.equity:,.2f}")
    
    # Disconnect
    paper.disconnect()
    
    # Demo/Live trading example (requires credentials)
    print("\n2. Tradovate Mode (Demo)")
    print("-" * 30)
    
    creds = TradovateCredentials.from_env()
    if creds.validate():
        demo = create_trading_interface(TradingMode.DEMO, credentials=creds)
        if demo.connect():
            accounts = demo.get_accounts()
            print(f"Accounts: {accounts}")
            demo.disconnect()
    else:
        print("Set TRADOVATE_* environment variables to test demo/live modes")
