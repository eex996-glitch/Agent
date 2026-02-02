"""
Paper Trading Engine

Local simulation of trading without connecting to any broker.
Useful for testing strategies before going live.
"""

import json
import os
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from enum import Enum
from pathlib import Path
import threading
import time
from loguru import logger


class OrderSide(Enum):
    BUY = "Buy"
    SELL = "Sell"


class OrderType(Enum):
    MARKET = "Market"
    LIMIT = "Limit"
    STOP = "Stop"
    STOP_LIMIT = "StopLimit"


class OrderStatus(Enum):
    PENDING = "Pending"
    WORKING = "Working"
    FILLED = "Filled"
    CANCELLED = "Cancelled"
    REJECTED = "Rejected"


class TimeInForce(Enum):
    DAY = "Day"
    GTC = "GTC"  # Good Till Cancelled
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill


@dataclass
class PaperOrder:
    """Represents an order in paper trading"""
    id: int
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType
    price: Optional[float] = None  # For limit orders
    stop_price: Optional[float] = None  # For stop orders
    time_in_force: TimeInForce = TimeInForce.DAY
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    filled_price: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    filled_at: Optional[datetime] = None
    parent_order_id: Optional[int] = None  # For bracket orders
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "order_type": self.order_type.value,
            "price": self.price,
            "stop_price": self.stop_price,
            "time_in_force": self.time_in_force.value,
            "status": self.status.value,
            "filled_quantity": self.filled_quantity,
            "filled_price": self.filled_price,
            "created_at": self.created_at.isoformat(),
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "parent_order_id": self.parent_order_id
        }


@dataclass
class PaperPosition:
    """Represents a position in paper trading"""
    symbol: str
    quantity: int  # Positive = long, negative = short
    entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    opened_at: datetime = field(default_factory=datetime.now)
    
    def update_price(self, price: float, point_value: float = 5.0):
        """Update current price and calculate P&L"""
        self.current_price = price
        self.unrealized_pnl = (price - self.entry_price) * self.quantity * point_value
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "opened_at": self.opened_at.isoformat()
        }


@dataclass
class PaperFill:
    """Represents a trade fill"""
    id: int
    order_id: int
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    timestamp: datetime = field(default_factory=datetime.now)
    commission: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "price": self.price,
            "timestamp": self.timestamp.isoformat(),
            "commission": self.commission
        }


@dataclass
class MarketConfig:
    """Configuration for a tradeable market"""
    symbol: str
    tick_size: float = 0.25  # Minimum price increment
    point_value: float = 5.0  # Dollar value per point
    commission: float = 0.62  # Per contract round trip
    margin_requirement: float = 1000.0  # Initial margin per contract
    trading_hours: tuple = ("18:00", "17:00")  # ET


# Default market configurations
DEFAULT_MARKETS = {
    "MES": MarketConfig("MES", tick_size=0.25, point_value=5.0, commission=0.62, margin_requirement=40),
    "ES": MarketConfig("ES", tick_size=0.25, point_value=50.0, commission=2.25, margin_requirement=400),
    "MNQ": MarketConfig("MNQ", tick_size=0.25, point_value=2.0, commission=0.62, margin_requirement=100),
    "NQ": MarketConfig("NQ", tick_size=0.25, point_value=20.0, commission=2.25, margin_requirement=1000),
    "MYM": MarketConfig("MYM", tick_size=1.0, point_value=0.5, commission=0.62, margin_requirement=50),
    "YM": MarketConfig("YM", tick_size=1.0, point_value=5.0, commission=2.25, margin_requirement=500),
}


class PaperTradingEngine:
    """
    Paper Trading Engine for local simulation
    
    Features:
    - Simulates order execution with realistic fills
    - Tracks positions and P&L
    - Supports market, limit, and stop orders
    - Bracket order support
    - Persistence to file
    - Slippage simulation
    """
    
    def __init__(
        self,
        initial_balance: float = 50000.0,
        slippage_ticks: int = 1,
        data_dir: str = None,
        markets: Dict[str, MarketConfig] = None
    ):
        self.initial_balance = initial_balance
        self.cash_balance = initial_balance
        self.slippage_ticks = slippage_ticks
        
        # Data persistence
        self.data_dir = Path(data_dir) if data_dir else Path.home() / ".paper_trading"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Markets
        self.markets = markets or DEFAULT_MARKETS
        
        # State
        self.orders: Dict[int, PaperOrder] = {}
        self.positions: Dict[str, PaperPosition] = {}
        self.fills: List[PaperFill] = []
        self.order_counter = 0
        self.fill_counter = 0
        
        # Current prices (for order simulation)
        self.current_prices: Dict[str, float] = {}
        
        # Statistics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        self.max_drawdown = 0.0
        self.peak_balance = initial_balance
        
        # Callbacks
        self.on_fill: Optional[Callable] = None
        self.on_position_change: Optional[Callable] = None
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Load state if exists
        self._load_state()
        
        logger.info(f"Paper Trading Engine initialized with ${initial_balance:,.2f}")
    
    # ==================== Order Management ====================
    
    def place_order(
        self,
        symbol: str,
        side: str,  # "Buy" or "Sell"
        quantity: int,
        order_type: str = "Market",
        price: float = None,
        stop_price: float = None,
        time_in_force: str = "Day"
    ) -> Dict:
        """
        Place an order
        
        Returns:
            Dict with order_id and status
        """
        with self._lock:
            self.order_counter += 1
            order_id = self.order_counter
            
            order = PaperOrder(
                id=order_id,
                symbol=symbol,
                side=OrderSide(side),
                quantity=quantity,
                order_type=OrderType(order_type),
                price=price,
                stop_price=stop_price,
                time_in_force=TimeInForce(time_in_force),
                status=OrderStatus.WORKING
            )
            
            self.orders[order_id] = order
            logger.info(f"Order placed: {order_type} {side} {quantity} {symbol} @ {price or 'MKT'}")
            
            # Try to fill immediately if market order
            if order_type == "Market":
                self._try_fill_order(order)
            
            self._save_state()
            
            return {
                "success": True,
                "order_id": order_id,
                "status": order.status.value,
                "message": "Order placed"
            }
    
    def place_bracket_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        entry_price: float = None,
        stop_loss: float = None,
        take_profit: float = None
    ) -> Dict:
        """Place a bracket order with stop loss and take profit"""
        
        # Place entry order
        entry_result = self.place_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type="Market" if entry_price is None else "Limit",
            price=entry_price
        )
        
        if not entry_result["success"]:
            return entry_result
        
        entry_order_id = entry_result["order_id"]
        exit_side = "Sell" if side == "Buy" else "Buy"
        
        # Place stop loss
        if stop_loss:
            with self._lock:
                self.order_counter += 1
                sl_order = PaperOrder(
                    id=self.order_counter,
                    symbol=symbol,
                    side=OrderSide(exit_side),
                    quantity=quantity,
                    order_type=OrderType.STOP,
                    stop_price=stop_loss,
                    status=OrderStatus.WORKING,
                    parent_order_id=entry_order_id
                )
                self.orders[self.order_counter] = sl_order
        
        # Place take profit
        if take_profit:
            with self._lock:
                self.order_counter += 1
                tp_order = PaperOrder(
                    id=self.order_counter,
                    symbol=symbol,
                    side=OrderSide(exit_side),
                    quantity=quantity,
                    order_type=OrderType.LIMIT,
                    price=take_profit,
                    status=OrderStatus.WORKING,
                    parent_order_id=entry_order_id
                )
                self.orders[self.order_counter] = tp_order
        
        self._save_state()
        
        return {
            "success": True,
            "order_id": entry_order_id,
            "message": "Bracket order placed"
        }
    
    def cancel_order(self, order_id: int) -> Dict:
        """Cancel an order"""
        with self._lock:
            if order_id not in self.orders:
                return {"success": False, "message": "Order not found"}
            
            order = self.orders[order_id]
            if order.status not in [OrderStatus.WORKING, OrderStatus.PENDING]:
                return {"success": False, "message": f"Cannot cancel order in {order.status.value} status"}
            
            order.status = OrderStatus.CANCELLED
            logger.info(f"Order {order_id} cancelled")
            
            self._save_state()
            
            return {"success": True, "message": "Order cancelled"}
    
    def cancel_all_orders(self) -> int:
        """Cancel all working orders"""
        cancelled = 0
        for order_id, order in list(self.orders.items()):
            if order.status == OrderStatus.WORKING:
                order.status = OrderStatus.CANCELLED
                cancelled += 1
        
        self._save_state()
        logger.info(f"Cancelled {cancelled} orders")
        return cancelled
    
    def get_order(self, order_id: int) -> Optional[Dict]:
        """Get order details"""
        if order_id in self.orders:
            return self.orders[order_id].to_dict()
        return None
    
    def get_open_orders(self) -> List[Dict]:
        """Get all working orders"""
        return [
            order.to_dict() 
            for order in self.orders.values() 
            if order.status == OrderStatus.WORKING
        ]
    
    # ==================== Position Management ====================
    
    def get_positions(self) -> List[Dict]:
        """Get all open positions"""
        return [pos.to_dict() for pos in self.positions.values() if pos.quantity != 0]
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """Get position for a symbol"""
        if symbol in self.positions:
            return self.positions[symbol].to_dict()
        return None
    
    def flatten_position(self, symbol: str) -> Dict:
        """Close a position at market"""
        if symbol not in self.positions or self.positions[symbol].quantity == 0:
            return {"success": False, "message": "No position to flatten"}
        
        pos = self.positions[symbol]
        side = "Sell" if pos.quantity > 0 else "Buy"
        quantity = abs(pos.quantity)
        
        return self.place_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type="Market"
        )
    
    def flatten_all(self) -> int:
        """Flatten all positions"""
        flattened = 0
        for symbol, pos in list(self.positions.items()):
            if pos.quantity != 0:
                self.flatten_position(symbol)
                flattened += 1
        return flattened
    
    # ==================== Price Updates & Order Execution ====================
    
    def update_price(self, symbol: str, price: float):
        """
        Update current price for a symbol.
        This triggers order checking and position P&L updates.
        """
        with self._lock:
            self.current_prices[symbol] = price
            
            # Update position P&L
            if symbol in self.positions:
                market = self.markets.get(symbol.rstrip('0123456789'))  # Strip contract month
                point_value = market.point_value if market else 5.0
                self.positions[symbol].update_price(price, point_value)
            
            # Check working orders
            self._check_orders(symbol, price)
    
    def _check_orders(self, symbol: str, price: float):
        """Check if any orders should be filled"""
        for order in list(self.orders.values()):
            if order.symbol != symbol or order.status != OrderStatus.WORKING:
                continue
            
            if order.order_type == OrderType.LIMIT:
                # Buy limit fills at or below limit price
                # Sell limit fills at or above limit price
                if order.side == OrderSide.BUY and price <= order.price:
                    self._try_fill_order(order, price)
                elif order.side == OrderSide.SELL and price >= order.price:
                    self._try_fill_order(order, price)
            
            elif order.order_type == OrderType.STOP:
                # Buy stop fills at or above stop price
                # Sell stop fills at or below stop price
                if order.side == OrderSide.BUY and price >= order.stop_price:
                    self._try_fill_order(order, price)
                elif order.side == OrderSide.SELL and price <= order.stop_price:
                    self._try_fill_order(order, price)
    
    def _try_fill_order(self, order: PaperOrder, price: float = None):
        """Attempt to fill an order"""
        symbol_base = order.symbol.rstrip('0123456789')
        market = self.markets.get(symbol_base, DEFAULT_MARKETS.get("MES"))
        
        # Determine fill price
        if price is None:
            price = self.current_prices.get(order.symbol, order.price or 0)
        
        if price == 0:
            logger.warning(f"Cannot fill order {order.id} - no price available")
            return
        
        # Apply slippage
        slippage = self.slippage_ticks * market.tick_size
        if order.side == OrderSide.BUY:
            fill_price = price + slippage
        else:
            fill_price = price - slippage
        
        # Create fill
        self.fill_counter += 1
        fill = PaperFill(
            id=self.fill_counter,
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
            commission=market.commission * order.quantity
        )
        self.fills.append(fill)
        
        # Update order
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.filled_price = fill_price
        order.filled_at = datetime.now()
        
        # Update position
        self._update_position(order.symbol, order.side, order.quantity, fill_price, market)
        
        # Update cash for commission
        self.cash_balance -= fill.commission
        
        # Cancel linked orders (for brackets)
        if order.parent_order_id:
            self._cancel_linked_orders(order.parent_order_id, order.id)
        
        logger.info(f"Order {order.id} filled: {order.side.value} {order.quantity} {order.symbol} @ {fill_price:.2f}")
        
        # Callback
        if self.on_fill:
            self.on_fill(fill)
        
        self._save_state()
    
    def _update_position(self, symbol: str, side: OrderSide, quantity: int, price: float, market: MarketConfig):
        """Update position after a fill"""
        position_delta = quantity if side == OrderSide.BUY else -quantity
        
        if symbol not in self.positions:
            self.positions[symbol] = PaperPosition(
                symbol=symbol,
                quantity=position_delta,
                entry_price=price,
                current_price=price
            )
        else:
            pos = self.positions[symbol]
            old_qty = pos.quantity
            new_qty = old_qty + position_delta
            
            # Calculate realized P&L if closing/reducing position
            if old_qty != 0 and ((old_qty > 0 and position_delta < 0) or (old_qty < 0 and position_delta > 0)):
                closed_qty = min(abs(old_qty), abs(position_delta))
                realized = (price - pos.entry_price) * closed_qty * market.point_value
                if old_qty < 0:
                    realized = -realized
                
                pos.realized_pnl += realized
                self.total_pnl += realized
                self.cash_balance += realized
                
                # Update statistics
                self.total_trades += 1
                if realized > 0:
                    self.winning_trades += 1
                else:
                    self.losing_trades += 1
                
                # Update drawdown
                current_equity = self.cash_balance + self._get_unrealized_pnl()
                if current_equity > self.peak_balance:
                    self.peak_balance = current_equity
                drawdown = self.peak_balance - current_equity
                if drawdown > self.max_drawdown:
                    self.max_drawdown = drawdown
            
            # Update position
            if new_qty == 0:
                pos.quantity = 0
                pos.entry_price = 0
            elif (old_qty >= 0 and new_qty > old_qty) or (old_qty <= 0 and new_qty < old_qty):
                # Adding to position - average in
                if old_qty == 0:
                    pos.entry_price = price
                else:
                    total_cost = (pos.entry_price * abs(old_qty)) + (price * abs(position_delta))
                    pos.entry_price = total_cost / abs(new_qty)
                pos.quantity = new_qty
            else:
                # Reducing position - keep entry price
                pos.quantity = new_qty
        
        # Callback
        if self.on_position_change:
            self.on_position_change(self.positions.get(symbol))
    
    def _cancel_linked_orders(self, parent_id: int, except_id: int):
        """Cancel other orders linked to the same parent (for brackets)"""
        for order in self.orders.values():
            if order.parent_order_id == parent_id and order.id != except_id:
                if order.status == OrderStatus.WORKING:
                    order.status = OrderStatus.CANCELLED
    
    def _get_unrealized_pnl(self) -> float:
        """Calculate total unrealized P&L"""
        return sum(pos.unrealized_pnl for pos in self.positions.values())
    
    # ==================== Account Info ====================
    
    def get_balance(self) -> Dict:
        """Get account balance and equity"""
        unrealized = self._get_unrealized_pnl()
        equity = self.cash_balance + unrealized
        
        return {
            "cash_balance": self.cash_balance,
            "unrealized_pnl": unrealized,
            "equity": equity,
            "initial_balance": self.initial_balance,
            "total_pnl": self.total_pnl,
            "max_drawdown": self.max_drawdown
        }
    
    def get_statistics(self) -> Dict:
        """Get trading statistics"""
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": win_rate,
            "total_pnl": self.total_pnl,
            "max_drawdown": self.max_drawdown,
            "current_equity": self.cash_balance + self._get_unrealized_pnl()
        }
    
    # ==================== Persistence ====================
    
    def _save_state(self):
        """Save state to file"""
        state = {
            "cash_balance": self.cash_balance,
            "order_counter": self.order_counter,
            "fill_counter": self.fill_counter,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_pnl": self.total_pnl,
            "max_drawdown": self.max_drawdown,
            "peak_balance": self.peak_balance,
            "orders": {k: v.to_dict() for k, v in self.orders.items()},
            "positions": {k: v.to_dict() for k, v in self.positions.items()},
            "fills": [f.to_dict() for f in self.fills[-100:]],  # Keep last 100 fills
            "current_prices": self.current_prices
        }
        
        state_file = self.data_dir / "paper_state.json"
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def _load_state(self):
        """Load state from file"""
        state_file = self.data_dir / "paper_state.json"
        if not state_file.exists():
            return
        
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
            
            self.cash_balance = state.get("cash_balance", self.initial_balance)
            self.order_counter = state.get("order_counter", 0)
            self.fill_counter = state.get("fill_counter", 0)
            self.total_trades = state.get("total_trades", 0)
            self.winning_trades = state.get("winning_trades", 0)
            self.losing_trades = state.get("losing_trades", 0)
            self.total_pnl = state.get("total_pnl", 0.0)
            self.max_drawdown = state.get("max_drawdown", 0.0)
            self.peak_balance = state.get("peak_balance", self.initial_balance)
            self.current_prices = state.get("current_prices", {})
            
            logger.info(f"Paper trading state loaded. Balance: ${self.cash_balance:,.2f}")
            
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
    
    def reset(self):
        """Reset paper trading to initial state"""
        with self._lock:
            self.cash_balance = self.initial_balance
            self.orders.clear()
            self.positions.clear()
            self.fills.clear()
            self.order_counter = 0
            self.fill_counter = 0
            self.total_trades = 0
            self.winning_trades = 0
            self.losing_trades = 0
            self.total_pnl = 0.0
            self.max_drawdown = 0.0
            self.peak_balance = self.initial_balance
            self.current_prices.clear()
            
            self._save_state()
            logger.info("Paper trading reset to initial state")


# ==================== Example Usage ====================

if __name__ == "__main__":
    print("Paper Trading Engine Example")
    print("=" * 50)
    
    # Create engine
    engine = PaperTradingEngine(initial_balance=50000)
    
    # Simulate some trading
    engine.update_price("MESZ4", 5000.00)
    
    # Place a market buy
    result = engine.place_order(
        symbol="MESZ4",
        side="Buy",
        quantity=2,
        order_type="Market"
    )
    print(f"\nOrder result: {result}")
    
    # Check position
    positions = engine.get_positions()
    print(f"Positions: {positions}")
    
    # Price moves up
    engine.update_price("MESZ4", 5010.00)
    
    # Check balance
    balance = engine.get_balance()
    print(f"\nBalance: ${balance['equity']:,.2f}")
    print(f"Unrealized P&L: ${balance['unrealized_pnl']:,.2f}")
    
    # Close position
    result = engine.flatten_position("MESZ4")
    print(f"\nFlatten result: {result}")
    
    # Final stats
    stats = engine.get_statistics()
    print(f"\nStatistics: {stats}")
