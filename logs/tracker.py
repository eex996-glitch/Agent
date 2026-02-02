#!/usr/bin/env python3
"""
Performance Tracker
Logs all trading activity and calculates performance metrics
"""

import os
import json
import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from pathlib import Path
from enum import Enum
import threading
from loguru import logger


class TradeDirection(Enum):
    LONG = "long"
    SHORT = "short"


class TradeStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


@dataclass
class TradeLog:
    """Individual trade record"""
    trade_id: str
    session_id: str
    symbol: str
    direction: str  # 'long' or 'short'
    entry_time: str
    entry_price: float
    quantity: int
    stop_loss: float
    take_profit: float

    # Exit info (filled when closed)
    exit_time: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: str = ""  # 'stop_loss', 'take_profit', 'signal', 'manual', 'eod'

    # Results
    pnl: float = 0.0
    pnl_percent: float = 0.0
    commission: float = 0.0
    net_pnl: float = 0.0

    # Metadata
    status: str = "open"
    strategy: str = "trend_following"
    timeframe: str = "5m"
    sentiment_score: float = 0.0
    confidence: float = 0.0

    # Risk metrics
    risk_amount: float = 0.0
    reward_ratio: float = 0.0
    max_favorable_excursion: float = 0.0  # MFE
    max_adverse_excursion: float = 0.0    # MAE

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'TradeLog':
        return cls(**data)

    def close(self, exit_price: float, exit_reason: str, exit_time: datetime = None):
        """Close the trade and calculate P&L"""
        self.exit_time = (exit_time or datetime.now()).isoformat()
        self.exit_price = exit_price
        self.exit_reason = exit_reason
        self.status = "closed"

        # Calculate P&L
        if self.direction == "long":
            self.pnl = (exit_price - self.entry_price) * self.quantity
        else:
            self.pnl = (self.entry_price - exit_price) * self.quantity

        self.pnl_percent = (self.pnl / (self.entry_price * self.quantity)) * 100
        self.net_pnl = self.pnl - self.commission

        # Calculate reward ratio achieved
        if self.risk_amount > 0:
            self.reward_ratio = self.net_pnl / self.risk_amount


@dataclass
class SessionLog:
    """Trading session record"""
    session_id: str
    start_time: str
    end_time: Optional[str] = None

    # Account info
    starting_balance: float = 50000.0
    ending_balance: float = 50000.0
    account_tier: str = "50K"

    # Trading mode
    mode: str = "paper"  # paper, demo, live
    symbol: str = "MES"

    # Session results
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    break_even_trades: int = 0

    gross_pnl: float = 0.0
    net_pnl: float = 0.0
    total_commission: float = 0.0

    # Performance metrics
    win_rate: float = 0.0
    profit_factor: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0

    # Risk metrics
    max_drawdown: float = 0.0
    max_drawdown_percent: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0

    # Trade list
    trades: List[Dict] = field(default_factory=list)

    # Prop firm tracking
    profit_target: float = 3000.0
    max_loss_limit: float = 2000.0
    daily_loss_limit: float = 1000.0
    rules_violated: bool = False
    violation_reason: str = ""

    # Metadata
    notes: str = ""
    strategy_version: str = "1.0.0"

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'SessionLog':
        return cls(**data)


class PerformanceTracker:
    """
    Main performance tracking class
    Logs all trades, calculates metrics, and manages persistence
    """

    def __init__(
        self,
        log_dir: str = None,
        mode: str = "paper",
        account_size: float = 50000.0,
        symbol: str = "MES"
    ):
        self.log_dir = Path(log_dir or os.path.join(os.path.dirname(__file__), "data"))
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.mode = mode
        self.account_size = account_size
        self.symbol = symbol

        # Current session
        self.session_id = str(uuid.uuid4())[:8]
        self.session = SessionLog(
            session_id=self.session_id,
            start_time=datetime.now().isoformat(),
            starting_balance=account_size,
            ending_balance=account_size,
            mode=mode,
            symbol=symbol
        )

        # Active trades
        self.active_trades: Dict[str, TradeLog] = {}

        # Balance tracking
        self.current_balance = account_size
        self.peak_balance = account_size
        self.balance_history: List[Dict] = [
            {"time": datetime.now().isoformat(), "balance": account_size}
        ]

        # Lock for thread safety
        self._lock = threading.Lock()

        # Auto-save timer
        self.auto_save_interval = 60  # seconds
        self._last_save = datetime.now()

        logger.info(f"PerformanceTracker initialized. Session: {self.session_id}")

    # ==================== Trade Logging ====================

    def log_entry(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        quantity: int,
        stop_loss: float,
        take_profit: float,
        strategy: str = "trend_following",
        sentiment_score: float = 0.0,
        confidence: float = 0.0
    ) -> str:
        """Log a trade entry"""
        with self._lock:
            trade_id = f"{self.session_id}-{len(self.session.trades) + 1:04d}"

            # Calculate risk amount
            if direction == "long":
                risk_per_unit = entry_price - stop_loss
            else:
                risk_per_unit = stop_loss - entry_price
            risk_amount = risk_per_unit * quantity

            trade = TradeLog(
                trade_id=trade_id,
                session_id=self.session_id,
                symbol=symbol,
                direction=direction,
                entry_time=datetime.now().isoformat(),
                entry_price=entry_price,
                quantity=quantity,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strategy=strategy,
                sentiment_score=sentiment_score,
                confidence=confidence,
                risk_amount=risk_amount
            )

            self.active_trades[trade_id] = trade
            self.session.total_trades += 1

            logger.info(f"Trade entry logged: {trade_id} {direction} {quantity} {symbol} @ {entry_price}")

            self._maybe_auto_save()
            return trade_id

    def log_exit(
        self,
        trade_id: str,
        exit_price: float,
        exit_reason: str,
        commission: float = 0.0
    ) -> Optional[TradeLog]:
        """Log a trade exit"""
        with self._lock:
            if trade_id not in self.active_trades:
                logger.warning(f"Trade {trade_id} not found in active trades")
                return None

            trade = self.active_trades[trade_id]
            trade.commission = commission
            trade.close(exit_price, exit_reason)

            # Update session stats
            if trade.net_pnl > 0:
                self.session.winning_trades += 1
            elif trade.net_pnl < 0:
                self.session.losing_trades += 1
            else:
                self.session.break_even_trades += 1

            self.session.gross_pnl += trade.pnl
            self.session.net_pnl += trade.net_pnl
            self.session.total_commission += commission

            # Update balance
            self.current_balance += trade.net_pnl
            self.session.ending_balance = self.current_balance

            # Track peak and drawdown
            if self.current_balance > self.peak_balance:
                self.peak_balance = self.current_balance

            drawdown = self.peak_balance - self.current_balance
            if drawdown > self.session.max_drawdown:
                self.session.max_drawdown = drawdown
                self.session.max_drawdown_percent = (drawdown / self.peak_balance) * 100

            # Update largest win/loss
            if trade.net_pnl > self.session.largest_win:
                self.session.largest_win = trade.net_pnl
            if trade.net_pnl < self.session.largest_loss:
                self.session.largest_loss = trade.net_pnl

            # Log balance
            self.balance_history.append({
                "time": datetime.now().isoformat(),
                "balance": self.current_balance,
                "trade_id": trade_id,
                "pnl": trade.net_pnl
            })

            # Move to closed trades
            self.session.trades.append(trade.to_dict())
            del self.active_trades[trade_id]

            # Recalculate metrics
            self._update_metrics()

            # Check prop firm rules
            self._check_rules()

            logger.info(f"Trade exit logged: {trade_id} P&L: ${trade.net_pnl:.2f} ({exit_reason})")

            self._maybe_auto_save()
            return trade

    def update_trade_excursion(self, trade_id: str, current_price: float):
        """Update MFE/MAE for an active trade"""
        with self._lock:
            if trade_id not in self.active_trades:
                return

            trade = self.active_trades[trade_id]

            if trade.direction == "long":
                favorable = current_price - trade.entry_price
                adverse = trade.entry_price - current_price
            else:
                favorable = trade.entry_price - current_price
                adverse = current_price - trade.entry_price

            if favorable > trade.max_favorable_excursion:
                trade.max_favorable_excursion = favorable
            if adverse > trade.max_adverse_excursion:
                trade.max_adverse_excursion = adverse

    # ==================== Metrics ====================

    def _update_metrics(self):
        """Recalculate all performance metrics"""
        trades = self.session.trades

        if not trades:
            return

        # Win rate
        if self.session.total_trades > 0:
            self.session.win_rate = (self.session.winning_trades / self.session.total_trades) * 100

        # Average win/loss
        wins = [t['net_pnl'] for t in trades if t['net_pnl'] > 0]
        losses = [t['net_pnl'] for t in trades if t['net_pnl'] < 0]

        if wins:
            self.session.average_win = sum(wins) / len(wins)
        if losses:
            self.session.average_loss = sum(losses) / len(losses)

        # Profit factor
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 0

        if gross_loss > 0:
            self.session.profit_factor = gross_profit / gross_loss
        elif gross_profit > 0:
            self.session.profit_factor = float('inf')

        # Sharpe ratio (simplified daily)
        if len(trades) > 1:
            returns = [t['pnl_percent'] for t in trades]
            avg_return = sum(returns) / len(returns)

            variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
            std_dev = variance ** 0.5

            if std_dev > 0:
                # Annualized (assuming ~252 trading days)
                self.session.sharpe_ratio = (avg_return / std_dev) * (252 ** 0.5)

    def _check_rules(self):
        """Check if prop firm rules are violated"""
        # Max loss limit
        if self.session.net_pnl <= -self.session.max_loss_limit:
            self.session.rules_violated = True
            self.session.violation_reason = f"Max loss limit (${self.session.max_loss_limit}) exceeded"
            logger.warning(f"RULE VIOLATION: {self.session.violation_reason}")

        # Daily loss limit (simplified - would need daily tracking)
        if self.session.net_pnl <= -self.session.daily_loss_limit:
            self.session.rules_violated = True
            self.session.violation_reason = f"Daily loss limit (${self.session.daily_loss_limit}) exceeded"
            logger.warning(f"RULE VIOLATION: {self.session.violation_reason}")

    # ==================== Persistence ====================

    def _maybe_auto_save(self):
        """Auto-save if interval has passed"""
        if (datetime.now() - self._last_save).seconds >= self.auto_save_interval:
            self.save()

    def save(self):
        """Save session to disk"""
        with self._lock:
            self.session.end_time = datetime.now().isoformat()

            # Save session log
            session_file = self.log_dir / f"session_{self.session_id}.json"
            with open(session_file, 'w') as f:
                json.dump(self.session.to_dict(), f, indent=2)

            # Save balance history
            balance_file = self.log_dir / f"balance_{self.session_id}.json"
            with open(balance_file, 'w') as f:
                json.dump(self.balance_history, f, indent=2)

            self._last_save = datetime.now()
            logger.debug(f"Session saved: {session_file}")

    def load_session(self, session_id: str) -> Optional[SessionLog]:
        """Load a previous session"""
        session_file = self.log_dir / f"session_{session_id}.json"

        if not session_file.exists():
            logger.warning(f"Session file not found: {session_file}")
            return None

        with open(session_file, 'r') as f:
            data = json.load(f)

        return SessionLog.from_dict(data)

    def get_all_sessions(self) -> List[str]:
        """Get all saved session IDs"""
        sessions = []
        for f in self.log_dir.glob("session_*.json"):
            session_id = f.stem.replace("session_", "")
            sessions.append(session_id)
        return sorted(sessions)

    # ==================== Reports ====================

    def get_summary(self) -> Dict:
        """Get current session summary"""
        return {
            "session_id": self.session_id,
            "mode": self.mode,
            "symbol": self.symbol,
            "start_time": self.session.start_time,
            "current_time": datetime.now().isoformat(),
            "starting_balance": self.session.starting_balance,
            "current_balance": self.current_balance,
            "net_pnl": self.session.net_pnl,
            "total_trades": self.session.total_trades,
            "winning_trades": self.session.winning_trades,
            "losing_trades": self.session.losing_trades,
            "win_rate": f"{self.session.win_rate:.1f}%",
            "profit_factor": f"{self.session.profit_factor:.2f}",
            "max_drawdown": f"${self.session.max_drawdown:.2f}",
            "sharpe_ratio": f"{self.session.sharpe_ratio:.2f}",
            "rules_violated": self.session.rules_violated,
            "active_trades": len(self.active_trades)
        }

    def generate_report(self) -> str:
        """Generate a text report"""
        s = self.session

        report = f"""
================================================================================
                        TRADING PERFORMANCE REPORT
================================================================================

Session ID: {self.session_id}
Mode: {self.mode.upper()}
Symbol: {self.symbol}
Period: {s.start_time[:19]} to {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

--------------------------------------------------------------------------------
                              ACCOUNT SUMMARY
--------------------------------------------------------------------------------
Starting Balance:     ${s.starting_balance:>12,.2f}
Current Balance:      ${self.current_balance:>12,.2f}
Net P&L:              ${s.net_pnl:>12,.2f} ({(s.net_pnl/s.starting_balance)*100:+.2f}%)
Gross P&L:            ${s.gross_pnl:>12,.2f}
Total Commission:     ${s.total_commission:>12,.2f}

--------------------------------------------------------------------------------
                              TRADE STATISTICS
--------------------------------------------------------------------------------
Total Trades:         {s.total_trades:>12}
Winning Trades:       {s.winning_trades:>12} ({s.win_rate:.1f}%)
Losing Trades:        {s.losing_trades:>12}
Break-Even Trades:    {s.break_even_trades:>12}

Average Win:          ${s.average_win:>12,.2f}
Average Loss:         ${s.average_loss:>12,.2f}
Largest Win:          ${s.largest_win:>12,.2f}
Largest Loss:         ${s.largest_loss:>12,.2f}

--------------------------------------------------------------------------------
                            PERFORMANCE METRICS
--------------------------------------------------------------------------------
Win Rate:             {s.win_rate:>12.1f}%
Profit Factor:        {s.profit_factor:>12.2f}
Sharpe Ratio:         {s.sharpe_ratio:>12.2f}
Max Drawdown:         ${s.max_drawdown:>12,.2f} ({s.max_drawdown_percent:.2f}%)

--------------------------------------------------------------------------------
                            PROP FIRM STATUS
--------------------------------------------------------------------------------
Profit Target:        ${s.profit_target:>12,.2f}
Progress:             {(s.net_pnl/s.profit_target)*100:>12.1f}%
Max Loss Limit:       ${s.max_loss_limit:>12,.2f}
Remaining Buffer:     ${s.max_loss_limit + s.net_pnl:>12,.2f}
Rules Violated:       {'YES - ' + s.violation_reason if s.rules_violated else 'NO':>12}

================================================================================
"""
        return report

    def export_trades_csv(self, filepath: str = None) -> str:
        """Export trades to CSV"""
        import csv

        filepath = filepath or str(self.log_dir / f"trades_{self.session_id}.csv")

        if not self.session.trades:
            logger.warning("No trades to export")
            return filepath

        fieldnames = list(self.session.trades[0].keys())

        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.session.trades)

        logger.info(f"Trades exported to: {filepath}")
        return filepath

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.save()
