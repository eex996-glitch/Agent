"""
Backtesting Engine

Simulates trading strategies on historical data with realistic
execution modeling and comprehensive performance metrics.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Type
from datetime import datetime, timedelta
import json

# Import from our modules
import sys
sys.path.insert(0, '..')

from strategy.base import BaseStrategy, TradeSignal, Signal, Position
from strategy.trend_following import TrendFollowingStrategy
from risk.manager import RiskManager, RiskAction


@dataclass
class BacktestConfig:
    """Configuration for backtesting"""
    # Account settings
    starting_balance: float = 50000.0
    
    # Market settings
    symbol: str = "MES"
    point_value: float = 5.0  # MES = $5 per point
    tick_size: float = 0.25
    commission_per_contract: float = 0.62  # Round trip
    slippage_ticks: int = 1
    
    # Risk settings
    max_loss_limit: float = 2000.0
    daily_loss_limit: float = 1000.0
    max_risk_per_trade: float = 0.01
    max_contracts: int = 5
    
    # Execution settings
    use_limit_orders: bool = False
    allow_overnight: bool = False
    
    # Analysis settings
    benchmark_symbol: Optional[str] = None


@dataclass
class Trade:
    """Record of a completed trade"""
    entry_time: datetime
    exit_time: datetime
    direction: str
    entry_price: float
    exit_price: float
    quantity: int
    gross_pnl: float
    commission: float
    slippage: float
    net_pnl: float
    exit_reason: str
    bars_held: int
    mae: float = 0.0  # Maximum Adverse Excursion
    mfe: float = 0.0  # Maximum Favorable Excursion


@dataclass
class BacktestResult:
    """Results from a backtest"""
    # Configuration
    config: BacktestConfig
    strategy_name: str
    start_date: datetime
    end_date: datetime
    
    # Trade results
    trades: List[Trade] = field(default_factory=list)
    
    # Equity curve
    equity_curve: pd.Series = field(default_factory=pd.Series)
    
    # Summary metrics
    total_return: float = 0.0
    total_return_pct: float = 0.0
    num_trades: int = 0
    num_winners: int = 0
    num_losers: int = 0
    win_rate: float = 0.0
    avg_winner: float = 0.0
    avg_loser: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    avg_trade: float = 0.0
    avg_bars_held: float = 0.0
    
    # Consistency metrics
    best_day: float = 0.0
    worst_day: float = 0.0
    consistency_score: float = 0.0
    winning_days: int = 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'strategy': self.strategy_name,
            'start_date': str(self.start_date),
            'end_date': str(self.end_date),
            'total_return': self.total_return,
            'total_return_pct': self.total_return_pct,
            'num_trades': self.num_trades,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_pct': self.max_drawdown_pct,
            'sharpe_ratio': self.sharpe_ratio,
            'avg_trade': self.avg_trade,
            'best_day': self.best_day,
            'worst_day': self.worst_day,
            'consistency_score': self.consistency_score
        }
    
    def print_summary(self):
        """Print formatted summary"""
        print("\n" + "="*60)
        print(f"BACKTEST RESULTS: {self.strategy_name}")
        print("="*60)
        print(f"Period: {self.start_date.date()} to {self.end_date.date()}")
        print(f"Starting Balance: ${self.config.starting_balance:,.2f}")
        
        print("\n--- Performance ---")
        print(f"Total Return: ${self.total_return:,.2f} ({self.total_return_pct:.2f}%)")
        print(f"Max Drawdown: ${self.max_drawdown:,.2f} ({self.max_drawdown_pct:.2f}%)")
        print(f"Sharpe Ratio: {self.sharpe_ratio:.2f}")
        print(f"Sortino Ratio: {self.sortino_ratio:.2f}")
        print(f"Profit Factor: {self.profit_factor:.2f}")
        
        print("\n--- Trade Statistics ---")
        print(f"Total Trades: {self.num_trades}")
        print(f"Win Rate: {self.win_rate*100:.1f}%")
        print(f"Avg Winner: ${self.avg_winner:.2f}")
        print(f"Avg Loser: ${self.avg_loser:.2f}")
        print(f"Avg Trade: ${self.avg_trade:.2f}")
        print(f"Avg Bars Held: {self.avg_bars_held:.1f}")
        
        print("\n--- Consistency (Prop Firm) ---")
        print(f"Best Day: ${self.best_day:,.2f}")
        print(f"Worst Day: ${self.worst_day:,.2f}")
        print(f"Winning Days: {self.winning_days}")
        print(f"Consistency Score: {self.consistency_score:.1f}%")
        consistency_ok = "✓ PASS" if self.consistency_score < 50 else "✗ FAIL"
        print(f"Consistency Target: {consistency_ok}")
        print("="*60)


class BacktestEngine:
    """
    Backtesting engine for futures trading strategies
    
    Features:
    - Realistic execution with slippage and commission
    - Risk management integration
    - Detailed trade logging
    - Performance metrics calculation
    - Prop firm rule compliance checking
    """
    
    def __init__(self, config: BacktestConfig = None):
        """
        Initialize the backtest engine
        
        Args:
            config: Backtest configuration
        """
        self.config = config or BacktestConfig()
        self.risk_manager: Optional[RiskManager] = None
        self.strategy: Optional[BaseStrategy] = None
        
        # State
        self.current_balance = self.config.starting_balance
        self.position: Optional[Position] = None
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = []
        self.daily_pnl: Dict[str, float] = {}
        
        # Tracking
        self.current_bar_idx = 0
        self.bars_in_position = 0
        self.entry_bar_idx = 0
        self.position_high = 0.0
        self.position_low = float('inf')
    
    def _apply_slippage(self, price: float, direction: str, is_entry: bool) -> float:
        """Apply slippage to a price"""
        slippage = self.config.slippage_ticks * self.config.tick_size
        
        if is_entry:
            # Slippage works against us on entry
            if direction == 'LONG':
                return price + slippage
            else:
                return price - slippage
        else:
            # Slippage works against us on exit
            if direction == 'LONG':
                return price - slippage
            else:
                return price + slippage
    
    def _calculate_pnl(
        self,
        entry_price: float,
        exit_price: float,
        quantity: int,
        direction: str
    ) -> tuple:
        """Calculate trade P&L with costs"""
        # Gross P&L
        price_diff = exit_price - entry_price
        if direction == 'SHORT':
            price_diff = -price_diff
        
        gross_pnl = price_diff * quantity * self.config.point_value
        
        # Commission (round trip)
        commission = self.config.commission_per_contract * quantity
        
        # Slippage is already in prices, so we just track it
        slippage = self.config.slippage_ticks * self.config.tick_size * 2 * \
                   quantity * self.config.point_value
        
        net_pnl = gross_pnl - commission
        
        return gross_pnl, commission, slippage, net_pnl
    
    def _open_position(
        self,
        signal: TradeSignal,
        data: pd.DataFrame,
        bar_idx: int
    ):
        """Open a new position"""
        direction = 'LONG' if signal.signal == Signal.LONG else 'SHORT'
        fill_price = self._apply_slippage(signal.price, direction, is_entry=True)
        
        self.position = Position(
            entry_time=data.index[bar_idx],
            entry_price=fill_price,
            quantity=signal.quantity,
            direction=signal.signal,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            trailing_stop=signal.trailing_stop
        )
        
        self.entry_bar_idx = bar_idx
        self.bars_in_position = 0
        self.position_high = fill_price
        self.position_low = fill_price
        
        # Notify strategy
        self.strategy.on_fill(signal, fill_price, data.index[bar_idx])
    
    def _close_position(
        self,
        exit_price: float,
        exit_time: datetime,
        reason: str,
        bar_idx: int
    ):
        """Close current position"""
        if not self.position:
            return
        
        direction = 'LONG' if self.position.is_long else 'SHORT'
        fill_price = self._apply_slippage(exit_price, direction, is_entry=False)
        
        # Calculate P&L
        gross_pnl, commission, slippage, net_pnl = self._calculate_pnl(
            self.position.entry_price,
            fill_price,
            self.position.quantity,
            direction
        )
        
        # Calculate MAE/MFE
        if self.position.is_long:
            mae = (self.position.entry_price - self.position_low) * \
                  self.position.quantity * self.config.point_value
            mfe = (self.position_high - self.position.entry_price) * \
                  self.position.quantity * self.config.point_value
        else:
            mae = (self.position_high - self.position.entry_price) * \
                  self.position.quantity * self.config.point_value
            mfe = (self.position.entry_price - self.position_low) * \
                  self.position.quantity * self.config.point_value
        
        # Record trade
        trade = Trade(
            entry_time=self.position.entry_time,
            exit_time=exit_time,
            direction=direction,
            entry_price=self.position.entry_price,
            exit_price=fill_price,
            quantity=self.position.quantity,
            gross_pnl=gross_pnl,
            commission=commission,
            slippage=slippage,
            net_pnl=net_pnl,
            exit_reason=reason,
            bars_held=self.bars_in_position,
            mae=mae,
            mfe=mfe
        )
        self.trades.append(trade)
        
        # Update balance
        self.current_balance += net_pnl
        
        # Update daily P&L
        date_str = exit_time.strftime('%Y-%m-%d')
        self.daily_pnl[date_str] = self.daily_pnl.get(date_str, 0) + net_pnl
        
        # Record with risk manager
        self.risk_manager.record_trade(
            entry_price=self.position.entry_price,
            exit_price=fill_price,
            quantity=self.position.quantity,
            direction=direction,
            point_value=self.config.point_value,
            timestamp=exit_time
        )
        
        # Notify strategy
        self.strategy.on_exit(fill_price, exit_time, reason)
        
        # Clear position
        self.position = None
    
    def _check_stop_take_profit(
        self,
        data: pd.DataFrame,
        bar_idx: int
    ) -> Optional[tuple]:
        """Check if stop loss or take profit is hit"""
        if not self.position:
            return None
        
        high = data['high'].iloc[bar_idx]
        low = data['low'].iloc[bar_idx]
        
        # Update position tracking
        self.position_high = max(self.position_high, high)
        self.position_low = min(self.position_low, low)
        
        # Update trailing stop
        if self.position.trailing_stop:
            self.position.update_trailing_stop(data['close'].iloc[bar_idx])
        
        if self.position.is_long:
            # Check stop loss
            if self.position.stop_loss and low <= self.position.stop_loss:
                return self.position.stop_loss, 'stop_loss'
            # Check take profit
            if self.position.take_profit and high >= self.position.take_profit:
                return self.position.take_profit, 'take_profit'
        else:
            # Check stop loss
            if self.position.stop_loss and high >= self.position.stop_loss:
                return self.position.stop_loss, 'stop_loss'
            # Check take profit
            if self.position.take_profit and low <= self.position.take_profit:
                return self.position.take_profit, 'take_profit'
        
        return None
    
    def run(
        self,
        strategy: BaseStrategy,
        data: pd.DataFrame,
        start_idx: int = 0
    ) -> BacktestResult:
        """
        Run backtest
        
        Args:
            strategy: Trading strategy to test
            data: Historical data with indicators
            start_idx: Starting bar index (for warmup)
            
        Returns:
            BacktestResult with performance metrics
        """
        self.strategy = strategy
        self.current_balance = self.config.starting_balance
        self.position = None
        self.trades = []
        self.equity_curve = [self.config.starting_balance]
        self.daily_pnl = {}
        
        # Initialize risk manager
        self.risk_manager = RiskManager(
            starting_balance=self.config.starting_balance,
            max_loss_limit=self.config.max_loss_limit,
            daily_loss_limit=self.config.daily_loss_limit,
            max_risk_per_trade=self.config.max_risk_per_trade
        )
        
        print(f"Running backtest on {len(data)} bars...")
        print(f"Start: {data.index[start_idx]}, End: {data.index[-1]}")
        
        # Main loop
        current_date = None
        for bar_idx in range(start_idx, len(data)):
            self.current_bar_idx = bar_idx
            bar_time = data.index[bar_idx]
            bar_date = bar_time.date()
            
            # New day handling
            if bar_date != current_date:
                current_date = bar_date
                self.risk_manager.new_day(bar_date)
            
            # Check if in position
            if self.position:
                self.bars_in_position += 1
                
                # Check stop/take profit
                exit_check = self._check_stop_take_profit(data, bar_idx)
                if exit_check:
                    exit_price, reason = exit_check
                    self._close_position(exit_price, bar_time, reason, bar_idx)
                    self.equity_curve.append(self.current_balance)
                    continue
            
            # Check if trading is allowed
            can_trade, reason = self.risk_manager.can_trade()
            if not can_trade:
                self.equity_curve.append(self.current_balance)
                continue
            
            # Get signal from strategy
            signal = self.strategy.update(data, bar_idx)
            
            if signal:
                if signal.signal == Signal.FLAT and self.position:
                    # Exit signal
                    self._close_position(
                        signal.price,
                        bar_time,
                        signal.reason,
                        bar_idx
                    )
                
                elif signal.signal in [Signal.LONG, Signal.SHORT] and not self.position:
                    # Entry signal - check risk
                    if signal.stop_loss:
                        quantity = strategy.calculate_position_size(
                            signal,
                            self.current_balance,
                            self.config.max_risk_per_trade,
                            self.config.point_value,
                            self.config.max_contracts
                        )
                        
                        action, reason, adj_qty = self.risk_manager.check_trade_risk(
                            signal.price,
                            signal.stop_loss,
                            quantity,
                            self.config.point_value
                        )
                        
                        if action == RiskAction.ALLOW:
                            signal.quantity = quantity
                            self._open_position(signal, data, bar_idx)
                        elif action == RiskAction.REDUCE_SIZE and adj_qty > 0:
                            signal.quantity = adj_qty
                            self._open_position(signal, data, bar_idx)
            
            self.equity_curve.append(self.current_balance)
        
        # Close any open position at end
        if self.position:
            self._close_position(
                data['close'].iloc[-1],
                data.index[-1],
                'end_of_data',
                len(data) - 1
            )
        
        # Calculate results
        result = self._calculate_results(data, start_idx)
        
        return result
    
    def _calculate_results(
        self,
        data: pd.DataFrame,
        start_idx: int
    ) -> BacktestResult:
        """Calculate backtest performance metrics"""
        result = BacktestResult(
            config=self.config,
            strategy_name=self.strategy.name,
            start_date=data.index[start_idx],
            end_date=data.index[-1],
            trades=self.trades,
            equity_curve=pd.Series(
                self.equity_curve,
                index=data.index[start_idx:start_idx+len(self.equity_curve)]
            )
        )
        
        if not self.trades:
            return result
        
        # Basic metrics
        pnls = [t.net_pnl for t in self.trades]
        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p < 0]
        
        result.num_trades = len(pnls)
        result.num_winners = len(winners)
        result.num_losers = len(losers)
        result.total_return = sum(pnls)
        result.total_return_pct = result.total_return / self.config.starting_balance * 100
        
        result.win_rate = len(winners) / len(pnls) if pnls else 0
        result.avg_winner = np.mean(winners) if winners else 0
        result.avg_loser = np.mean(losers) if losers else 0
        result.avg_trade = np.mean(pnls)
        result.avg_bars_held = np.mean([t.bars_held for t in self.trades])
        
        # Profit factor
        gross_profit = sum(winners) if winners else 0
        gross_loss = abs(sum(losers)) if losers else 1
        result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Drawdown
        equity = np.array(self.equity_curve)
        running_max = np.maximum.accumulate(equity)
        drawdown = running_max - equity
        result.max_drawdown = np.max(drawdown)
        result.max_drawdown_pct = result.max_drawdown / self.config.starting_balance * 100
        
        # Risk-adjusted returns
        returns = np.diff(equity) / equity[:-1]
        if len(returns) > 0 and np.std(returns) > 0:
            # Annualize (assuming 5-min bars, ~78 bars per day, ~252 trading days)
            ann_factor = np.sqrt(252 * 78)
            result.sharpe_ratio = np.mean(returns) / np.std(returns) * ann_factor
            
            # Sortino (downside deviation)
            downside = returns[returns < 0]
            if len(downside) > 0:
                result.sortino_ratio = np.mean(returns) / np.std(downside) * ann_factor
        
        # Calmar ratio
        if result.max_drawdown > 0:
            ann_return = result.total_return_pct * (252 / len(self.trades)) if self.trades else 0
            result.calmar_ratio = ann_return / result.max_drawdown_pct
        
        # Daily metrics
        daily_pnls = list(self.daily_pnl.values())
        if daily_pnls:
            result.best_day = max(daily_pnls)
            result.worst_day = min(daily_pnls)
            result.winning_days = sum(1 for p in daily_pnls if p >= 150)  # MFFU threshold
            
            # Consistency score
            if result.total_return > 0:
                result.consistency_score = result.best_day / result.total_return * 100
        
        return result


# Example usage
if __name__ == "__main__":
    # Create sample data
    np.random.seed(42)
    n_bars = 2000
    dates = pd.date_range(start='2024-01-01', periods=n_bars, freq='5min')
    
    # Generate trending price data with some volatility
    trend = np.cumsum(np.random.randn(n_bars) * 0.3 + 0.01)
    noise = np.random.randn(n_bars) * 0.5
    close = 5000 + trend + noise
    
    high = close + np.abs(np.random.randn(n_bars) * 1.0)
    low = close - np.abs(np.random.randn(n_bars) * 1.0)
    volume = np.random.randint(1000, 10000, n_bars)
    
    df = pd.DataFrame({
        'open': np.roll(close, 1),
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)
    df['open'].iloc[0] = df['close'].iloc[0]
    
    # Create strategy and prepare data
    strategy = TrendFollowingStrategy(
        name="TrendFollowing_Test",
        params={'adx_threshold': 20.0}
    )
    df = strategy.prepare_data(df)
    
    # Create backtest config
    config = BacktestConfig(
        starting_balance=50000,
        symbol="MES",
        point_value=5.0,
        max_loss_limit=2000,
        max_contracts=5
    )
    
    # Run backtest
    engine = BacktestEngine(config)
    result = engine.run(strategy, df, start_idx=250)
    
    # Print results
    result.print_summary()
    
    # Show some trades
    if result.trades:
        print("\n--- Sample Trades ---")
        for trade in result.trades[:5]:
            print(f"{trade.direction}: Entry={trade.entry_price:.2f}, "
                  f"Exit={trade.exit_price:.2f}, P/L=${trade.net_pnl:.2f}, "
                  f"Reason={trade.exit_reason}")
