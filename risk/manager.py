"""
Risk Management Module

Handles all risk management functions including:
- Position sizing
- Drawdown monitoring
- Daily loss limits
- Prop firm rule enforcement
- Risk metrics calculation
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
from datetime import datetime, date
from enum import Enum


class RiskAction(Enum):
    """Risk management actions"""
    ALLOW = "allow"
    REDUCE_SIZE = "reduce_size"
    BLOCK = "block"
    CLOSE_ALL = "close_all"
    HALT_TRADING = "halt_trading"


@dataclass
class DailyStats:
    """Daily trading statistics"""
    date: date
    starting_balance: float
    ending_balance: float = 0.0
    high_balance: float = 0.0
    low_balance: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    num_trades: int = 0
    num_winners: int = 0
    num_losers: int = 0
    max_drawdown: float = 0.0
    
    @property
    def net_pnl(self) -> float:
        return self.realized_pnl + self.unrealized_pnl
    
    @property
    def win_rate(self) -> float:
        if self.num_trades == 0:
            return 0.0
        return self.num_winners / self.num_trades


@dataclass
class RiskState:
    """Current risk state of the account"""
    # Account state
    current_balance: float
    starting_balance: float
    high_water_mark: float
    
    # Daily state
    daily_pnl: float = 0.0
    daily_trades: int = 0
    consecutive_losses: int = 0
    
    # Limits
    max_loss_limit: float = 2000.0
    daily_loss_limit: float = 1000.0
    max_daily_trades: int = 20
    max_consecutive_losses: int = 3
    
    # Computed
    @property
    def total_pnl(self) -> float:
        return self.current_balance - self.starting_balance
    
    @property
    def drawdown(self) -> float:
        return self.high_water_mark - self.current_balance
    
    @property
    def drawdown_pct(self) -> float:
        if self.high_water_mark == 0:
            return 0.0
        return self.drawdown / self.high_water_mark * 100
    
    @property
    def available_risk(self) -> float:
        """Amount that can be lost before hitting MLL"""
        floor = self.high_water_mark - self.max_loss_limit
        return max(0, self.current_balance - floor)
    
    @property
    def daily_risk_remaining(self) -> float:
        """Amount that can be lost today before hitting daily limit"""
        return max(0, self.daily_loss_limit + self.daily_pnl)


class RiskManager:
    """
    Risk Management Engine
    
    Monitors and enforces risk limits including:
    - Maximum Loss Limit (trailing drawdown)
    - Daily Loss Limit
    - Position sizing
    - Trade frequency limits
    - Consecutive loss circuit breaker
    """
    
    def __init__(
        self,
        starting_balance: float,
        max_loss_limit: float = 2000.0,
        daily_loss_limit: float = 1000.0,
        max_risk_per_trade: float = 0.01,
        max_daily_trades: int = 20,
        max_consecutive_losses: int = 3,
        use_daily_loss_limit: bool = False  # TopstepX doesn't use this
    ):
        """
        Initialize the risk manager
        
        Args:
            starting_balance: Initial account balance
            max_loss_limit: Maximum loss limit (MLL)
            daily_loss_limit: Daily loss limit
            max_risk_per_trade: Maximum risk per trade as fraction
            max_daily_trades: Maximum trades per day
            max_consecutive_losses: Circuit breaker threshold
            use_daily_loss_limit: Whether to enforce daily loss limit
        """
        self.starting_balance = starting_balance
        self.current_balance = starting_balance
        self.high_water_mark = starting_balance
        
        # Limits
        self.max_loss_limit = max_loss_limit
        self.daily_loss_limit = daily_loss_limit
        self.max_risk_per_trade = max_risk_per_trade
        self.max_daily_trades = max_daily_trades
        self.max_consecutive_losses = max_consecutive_losses
        self.use_daily_loss_limit = use_daily_loss_limit
        
        # State tracking
        self.daily_stats: Dict[date, DailyStats] = {}
        self.current_date: Optional[date] = None
        self.consecutive_losses = 0
        self.is_halted = False
        self.halt_reason = ""
        
        # Trade history
        self.trades: List[Dict] = []
        
        # Best day tracking (for consistency target)
        self.best_day_pnl = 0.0
        self.total_realized_pnl = 0.0
    
    def _get_or_create_daily_stats(self, current_date: date) -> DailyStats:
        """Get or create daily stats for a date"""
        if current_date not in self.daily_stats:
            self.daily_stats[current_date] = DailyStats(
                date=current_date,
                starting_balance=self.current_balance,
                high_balance=self.current_balance,
                low_balance=self.current_balance
            )
        return self.daily_stats[current_date]
    
    def new_day(self, current_date: date):
        """
        Start a new trading day
        
        Args:
            current_date: The new trading date
        """
        # Finalize previous day if exists
        if self.current_date and self.current_date in self.daily_stats:
            prev_stats = self.daily_stats[self.current_date]
            prev_stats.ending_balance = self.current_balance
            
            # Update best day
            if prev_stats.realized_pnl > self.best_day_pnl:
                self.best_day_pnl = prev_stats.realized_pnl
        
        # Update high water mark (end of day)
        if self.current_balance > self.high_water_mark:
            self.high_water_mark = self.current_balance
        
        # Start new day
        self.current_date = current_date
        self._get_or_create_daily_stats(current_date)
        
        # Reset daily state
        self.consecutive_losses = 0
        
        # Check if we should unhalt
        if self.is_halted and self.halt_reason == "daily_loss_limit":
            self.is_halted = False
            self.halt_reason = ""
    
    def update_balance(self, new_balance: float, timestamp: datetime):
        """
        Update current balance
        
        Args:
            new_balance: New account balance
            timestamp: Current timestamp
        """
        self.current_balance = new_balance
        
        # Update daily stats
        current_date = timestamp.date()
        if current_date != self.current_date:
            self.new_day(current_date)
        
        stats = self._get_or_create_daily_stats(current_date)
        stats.high_balance = max(stats.high_balance, new_balance)
        stats.low_balance = min(stats.low_balance, new_balance)
        
        # Check for MLL breach
        self._check_mll_breach()
    
    def record_trade(
        self,
        entry_price: float,
        exit_price: float,
        quantity: int,
        direction: str,
        point_value: float,
        timestamp: datetime
    ) -> float:
        """
        Record a completed trade
        
        Args:
            entry_price: Entry price
            exit_price: Exit price
            quantity: Number of contracts
            direction: 'LONG' or 'SHORT'
            point_value: Dollar value per point
            timestamp: Trade completion time
            
        Returns:
            Trade P/L
        """
        # Calculate P/L
        price_diff = exit_price - entry_price
        if direction == 'SHORT':
            price_diff = -price_diff
        
        pnl = price_diff * quantity * point_value
        
        # Update balance
        self.current_balance += pnl
        self.total_realized_pnl += pnl
        
        # Update daily stats
        current_date = timestamp.date()
        stats = self._get_or_create_daily_stats(current_date)
        stats.realized_pnl += pnl
        stats.num_trades += 1
        
        if pnl > 0:
            stats.num_winners += 1
            self.consecutive_losses = 0
        elif pnl < 0:
            stats.num_losers += 1
            self.consecutive_losses += 1
        
        # Record trade
        self.trades.append({
            'timestamp': timestamp,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'quantity': quantity,
            'direction': direction,
            'pnl': pnl
        })
        
        # Update best day
        if stats.realized_pnl > self.best_day_pnl:
            self.best_day_pnl = stats.realized_pnl
        
        # Check risk limits
        self._check_mll_breach()
        self._check_daily_loss()
        self._check_consecutive_losses()
        
        return pnl
    
    def _check_mll_breach(self):
        """Check if Maximum Loss Limit has been breached"""
        floor = self.high_water_mark - self.max_loss_limit
        
        # Floor cannot go below starting - MLL
        absolute_floor = self.starting_balance - self.max_loss_limit
        floor = max(floor, absolute_floor)
        
        if self.current_balance <= floor:
            self.is_halted = True
            self.halt_reason = "max_loss_limit"
    
    def _check_daily_loss(self):
        """Check if daily loss limit has been breached"""
        if not self.use_daily_loss_limit:
            return
        
        if self.current_date is None:
            return
        
        stats = self.daily_stats.get(self.current_date)
        if stats and stats.realized_pnl <= -self.daily_loss_limit:
            self.is_halted = True
            self.halt_reason = "daily_loss_limit"
    
    def _check_consecutive_losses(self):
        """Check for consecutive loss circuit breaker"""
        if self.consecutive_losses >= self.max_consecutive_losses:
            self.is_halted = True
            self.halt_reason = "consecutive_losses"
    
    def can_trade(self) -> Tuple[bool, str]:
        """
        Check if trading is allowed
        
        Returns:
            Tuple of (can_trade, reason_if_blocked)
        """
        if self.is_halted:
            return False, self.halt_reason
        
        # Check daily trade limit
        if self.current_date:
            stats = self.daily_stats.get(self.current_date)
            if stats and stats.num_trades >= self.max_daily_trades:
                return False, "max_daily_trades"
        
        return True, ""
    
    def check_trade_risk(
        self,
        entry_price: float,
        stop_loss: float,
        quantity: int,
        point_value: float
    ) -> Tuple[RiskAction, str, int]:
        """
        Check if a proposed trade is within risk limits
        
        Args:
            entry_price: Proposed entry price
            stop_loss: Stop loss price
            quantity: Proposed quantity
            point_value: Dollar value per point
            
        Returns:
            Tuple of (action, reason, adjusted_quantity)
        """
        can_trade, reason = self.can_trade()
        if not can_trade:
            return RiskAction.BLOCK, reason, 0
        
        # Calculate trade risk
        price_risk = abs(entry_price - stop_loss)
        dollar_risk = price_risk * quantity * point_value
        
        # Check against available risk
        if dollar_risk > self.available_risk:
            # Try to reduce size
            max_quantity = int(self.available_risk / (price_risk * point_value))
            if max_quantity > 0:
                return RiskAction.REDUCE_SIZE, "risk_limit", max_quantity
            return RiskAction.BLOCK, "insufficient_risk_capacity", 0
        
        # Check against per-trade risk limit
        max_trade_risk = self.current_balance * self.max_risk_per_trade
        if dollar_risk > max_trade_risk:
            max_quantity = int(max_trade_risk / (price_risk * point_value))
            if max_quantity > 0:
                return RiskAction.REDUCE_SIZE, "per_trade_limit", max_quantity
            return RiskAction.BLOCK, "per_trade_limit_exceeded", 0
        
        return RiskAction.ALLOW, "", quantity
    
    @property
    def available_risk(self) -> float:
        """Amount that can be lost before hitting MLL"""
        floor = self.high_water_mark - self.max_loss_limit
        absolute_floor = self.starting_balance - self.max_loss_limit
        floor = max(floor, absolute_floor)
        return max(0, self.current_balance - floor)
    
    def get_state(self) -> RiskState:
        """Get current risk state"""
        daily_pnl = 0.0
        daily_trades = 0
        
        if self.current_date and self.current_date in self.daily_stats:
            stats = self.daily_stats[self.current_date]
            daily_pnl = stats.realized_pnl
            daily_trades = stats.num_trades
        
        return RiskState(
            current_balance=self.current_balance,
            starting_balance=self.starting_balance,
            high_water_mark=self.high_water_mark,
            daily_pnl=daily_pnl,
            daily_trades=daily_trades,
            consecutive_losses=self.consecutive_losses,
            max_loss_limit=self.max_loss_limit,
            daily_loss_limit=self.daily_loss_limit,
            max_daily_trades=self.max_daily_trades,
            max_consecutive_losses=self.max_consecutive_losses
        )
    
    def get_consistency_status(self) -> Dict:
        """
        Get consistency target status
        
        Returns:
            Dictionary with consistency metrics
        """
        if self.total_realized_pnl <= 0:
            return {
                'best_day_pnl': self.best_day_pnl,
                'total_pnl': self.total_realized_pnl,
                'best_day_percentage': 0.0,
                'is_consistent': False,
                'required_total': 0.0
            }
        
        best_day_pct = self.best_day_pnl / self.total_realized_pnl * 100
        is_consistent = best_day_pct < 50.0
        required_total = self.best_day_pnl / 0.50 if not is_consistent else self.total_realized_pnl
        
        return {
            'best_day_pnl': self.best_day_pnl,
            'total_pnl': self.total_realized_pnl,
            'best_day_percentage': best_day_pct,
            'is_consistent': is_consistent,
            'required_total': required_total,
            'additional_needed': max(0, required_total - self.total_realized_pnl)
        }
    
    def get_performance_metrics(self) -> Dict:
        """Calculate overall performance metrics"""
        if not self.trades:
            return {}
        
        pnls = [t['pnl'] for t in self.trades]
        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p < 0]
        
        total_pnl = sum(pnls)
        win_rate = len(winners) / len(pnls) if pnls else 0
        avg_winner = np.mean(winners) if winners else 0
        avg_loser = np.mean(losers) if losers else 0
        
        # Profit factor
        gross_profit = sum(winners) if winners else 0
        gross_loss = abs(sum(losers)) if losers else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Max drawdown
        cumulative = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = running_max - cumulative
        max_drawdown = np.max(drawdowns) if len(drawdowns) > 0 else 0
        
        return {
            'total_trades': len(pnls),
            'total_pnl': total_pnl,
            'win_rate': win_rate,
            'avg_winner': avg_winner,
            'avg_loser': avg_loser,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'best_trade': max(pnls) if pnls else 0,
            'worst_trade': min(pnls) if pnls else 0
        }
    
    def print_status(self):
        """Print current risk status"""
        state = self.get_state()
        consistency = self.get_consistency_status()
        
        print("\n" + "="*50)
        print("RISK STATUS")
        print("="*50)
        print(f"Balance: ${state.current_balance:,.2f}")
        print(f"Total P/L: ${state.total_pnl:,.2f}")
        print(f"High Water Mark: ${state.high_water_mark:,.2f}")
        print(f"Current Drawdown: ${state.drawdown:,.2f} ({state.drawdown_pct:.1f}%)")
        print(f"Available Risk: ${state.available_risk:,.2f}")
        print(f"Daily P/L: ${state.daily_pnl:,.2f}")
        print(f"Daily Trades: {state.daily_trades}")
        print(f"Consecutive Losses: {state.consecutive_losses}")
        print(f"Trading Halted: {self.is_halted} ({self.halt_reason})")
        
        print("\n--- Consistency ---")
        print(f"Best Day: ${consistency['best_day_pnl']:,.2f}")
        print(f"Best Day %: {consistency['best_day_percentage']:.1f}%")
        print(f"Consistent: {consistency['is_consistent']}")
        if not consistency['is_consistent']:
            print(f"Additional Needed: ${consistency['additional_needed']:,.2f}")


# Example usage
if __name__ == "__main__":
    # Create risk manager for 50K Topstep account
    rm = RiskManager(
        starting_balance=50000,
        max_loss_limit=2000,
        daily_loss_limit=1000,
        max_risk_per_trade=0.01,
        use_daily_loss_limit=False
    )
    
    print("=== Risk Manager Test ===")
    
    # Simulate some trades
    from datetime import datetime, timedelta
    
    base_time = datetime(2024, 1, 15, 9, 30)
    rm.new_day(base_time.date())
    
    # Trade 1: Winner
    rm.record_trade(
        entry_price=5000, exit_price=5010,
        quantity=2, direction='LONG',
        point_value=5, timestamp=base_time
    )
    print(f"\nAfter Trade 1 (Winner): Balance = ${rm.current_balance:,.2f}")
    
    # Trade 2: Winner
    rm.record_trade(
        entry_price=5015, exit_price=5030,
        quantity=2, direction='LONG',
        point_value=5, timestamp=base_time + timedelta(hours=1)
    )
    print(f"After Trade 2 (Winner): Balance = ${rm.current_balance:,.2f}")
    
    # Trade 3: Loser
    rm.record_trade(
        entry_price=5025, exit_price=5010,
        quantity=2, direction='LONG',
        point_value=5, timestamp=base_time + timedelta(hours=2)
    )
    print(f"After Trade 3 (Loser): Balance = ${rm.current_balance:,.2f}")
    
    # Check if we can trade
    can_trade, reason = rm.can_trade()
    print(f"\nCan Trade: {can_trade}")
    
    # Check trade risk
    action, reason, adj_qty = rm.check_trade_risk(
        entry_price=5000,
        stop_loss=4990,
        quantity=3,
        point_value=5
    )
    print(f"Trade Risk Check: {action.value}, Reason: {reason}, Adjusted Qty: {adj_qty}")
    
    # Print full status
    rm.print_status()
    
    # Print performance metrics
    print("\n--- Performance Metrics ---")
    metrics = rm.get_performance_metrics()
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"{key}: {value:.2f}")
        else:
            print(f"{key}: {value}")
