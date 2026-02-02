#!/usr/bin/env python3
"""
Performance Metrics Calculator
Advanced metrics for trading performance analysis
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import math


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics"""

    # Basic metrics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0

    # P&L metrics
    total_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_profit: float = 0.0

    # Average metrics
    average_trade: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    win_loss_ratio: float = 0.0

    # Best/Worst
    largest_win: float = 0.0
    largest_loss: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0

    # Risk metrics
    profit_factor: float = 0.0
    payoff_ratio: float = 0.0
    expectancy: float = 0.0
    kelly_criterion: float = 0.0

    # Drawdown metrics
    max_drawdown: float = 0.0
    max_drawdown_percent: float = 0.0
    average_drawdown: float = 0.0
    recovery_factor: float = 0.0

    # Risk-adjusted returns
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # Time metrics
    average_trade_duration: float = 0.0  # minutes
    average_winning_duration: float = 0.0
    average_losing_duration: float = 0.0

    # Consistency
    consistency_score: float = 0.0
    best_day_pnl: float = 0.0
    worst_day_pnl: float = 0.0
    best_day_percent_of_total: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)


def calculate_metrics(
    trades: List[Dict],
    starting_balance: float = 50000.0,
    risk_free_rate: float = 0.02
) -> PerformanceMetrics:
    """
    Calculate comprehensive performance metrics from trade list

    Args:
        trades: List of trade dictionaries with net_pnl, entry_time, exit_time, etc.
        starting_balance: Initial account balance
        risk_free_rate: Annual risk-free rate for Sharpe calculation

    Returns:
        PerformanceMetrics object
    """
    metrics = PerformanceMetrics()

    if not trades:
        return metrics

    # Filter closed trades
    closed_trades = [t for t in trades if t.get('status') == 'closed']

    if not closed_trades:
        return metrics

    # Basic counts
    metrics.total_trades = len(closed_trades)
    pnls = [t.get('net_pnl', 0) for t in closed_trades]

    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p < 0]

    metrics.winning_trades = len(winners)
    metrics.losing_trades = len(losers)

    # Win rate
    if metrics.total_trades > 0:
        metrics.win_rate = (metrics.winning_trades / metrics.total_trades) * 100

    # P&L metrics
    metrics.total_pnl = sum(pnls)
    metrics.gross_profit = sum(winners) if winners else 0
    metrics.gross_loss = abs(sum(losers)) if losers else 0
    metrics.net_profit = metrics.total_pnl

    # Average metrics
    if metrics.total_trades > 0:
        metrics.average_trade = metrics.total_pnl / metrics.total_trades

    if winners:
        metrics.average_win = sum(winners) / len(winners)
        metrics.largest_win = max(winners)

    if losers:
        metrics.average_loss = abs(sum(losers) / len(losers))
        metrics.largest_loss = min(losers)

    # Win/Loss ratio
    if metrics.average_loss > 0:
        metrics.win_loss_ratio = metrics.average_win / metrics.average_loss

    # Profit factor
    if metrics.gross_loss > 0:
        metrics.profit_factor = metrics.gross_profit / metrics.gross_loss
    elif metrics.gross_profit > 0:
        metrics.profit_factor = float('inf')

    # Payoff ratio (same as win/loss ratio but commonly used)
    metrics.payoff_ratio = metrics.win_loss_ratio

    # Expectancy (expected value per trade)
    if metrics.total_trades > 0:
        win_prob = metrics.win_rate / 100
        loss_prob = 1 - win_prob
        metrics.expectancy = (win_prob * metrics.average_win) - (loss_prob * metrics.average_loss)

    # Kelly Criterion (optimal bet size)
    if metrics.average_loss > 0 and metrics.win_loss_ratio > 0:
        win_prob = metrics.win_rate / 100
        metrics.kelly_criterion = (win_prob - ((1 - win_prob) / metrics.win_loss_ratio)) * 100

    # Consecutive wins/losses
    metrics.max_consecutive_wins, metrics.max_consecutive_losses = _calculate_streaks(pnls)

    # Drawdown metrics
    dd_metrics = _calculate_drawdown_metrics(pnls, starting_balance)
    metrics.max_drawdown = dd_metrics['max_drawdown']
    metrics.max_drawdown_percent = dd_metrics['max_drawdown_percent']
    metrics.average_drawdown = dd_metrics['average_drawdown']

    # Recovery factor
    if metrics.max_drawdown > 0:
        metrics.recovery_factor = metrics.net_profit / metrics.max_drawdown

    # Sharpe ratio
    metrics.sharpe_ratio = _calculate_sharpe(pnls, starting_balance, risk_free_rate)

    # Sortino ratio
    metrics.sortino_ratio = _calculate_sortino(pnls, starting_balance, risk_free_rate)

    # Calmar ratio (annual return / max drawdown)
    if metrics.max_drawdown > 0:
        # Simplified - assumes trades over ~1 year
        annual_return = (metrics.net_profit / starting_balance) * 100
        metrics.calmar_ratio = annual_return / metrics.max_drawdown_percent if metrics.max_drawdown_percent > 0 else 0

    # Trade duration metrics
    duration_metrics = _calculate_duration_metrics(closed_trades)
    metrics.average_trade_duration = duration_metrics['average']
    metrics.average_winning_duration = duration_metrics['winning']
    metrics.average_losing_duration = duration_metrics['losing']

    # Consistency metrics
    consistency = _calculate_consistency(closed_trades)
    metrics.consistency_score = consistency['score']
    metrics.best_day_pnl = consistency['best_day']
    metrics.worst_day_pnl = consistency['worst_day']
    metrics.best_day_percent_of_total = consistency['best_day_percent']

    return metrics


def _calculate_streaks(pnls: List[float]) -> tuple:
    """Calculate max consecutive wins and losses"""
    if not pnls:
        return 0, 0

    max_wins = 0
    max_losses = 0
    current_wins = 0
    current_losses = 0

    for pnl in pnls:
        if pnl > 0:
            current_wins += 1
            current_losses = 0
            max_wins = max(max_wins, current_wins)
        elif pnl < 0:
            current_losses += 1
            current_wins = 0
            max_losses = max(max_losses, current_losses)
        else:
            current_wins = 0
            current_losses = 0

    return max_wins, max_losses


def _calculate_drawdown_metrics(pnls: List[float], starting_balance: float) -> Dict:
    """Calculate drawdown-related metrics"""
    if not pnls:
        return {'max_drawdown': 0, 'max_drawdown_percent': 0, 'average_drawdown': 0}

    balance = starting_balance
    peak = starting_balance
    drawdowns = []
    max_dd = 0
    max_dd_percent = 0

    for pnl in pnls:
        balance += pnl
        peak = max(peak, balance)
        dd = peak - balance
        dd_percent = (dd / peak) * 100 if peak > 0 else 0

        drawdowns.append(dd)
        max_dd = max(max_dd, dd)
        max_dd_percent = max(max_dd_percent, dd_percent)

    avg_dd = sum(drawdowns) / len(drawdowns) if drawdowns else 0

    return {
        'max_drawdown': max_dd,
        'max_drawdown_percent': max_dd_percent,
        'average_drawdown': avg_dd
    }


def _calculate_sharpe(pnls: List[float], starting_balance: float, risk_free_rate: float) -> float:
    """Calculate Sharpe ratio"""
    if len(pnls) < 2:
        return 0.0

    # Convert to returns
    returns = [p / starting_balance for p in pnls]

    avg_return = sum(returns) / len(returns)
    variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
    std_dev = math.sqrt(variance) if variance > 0 else 0

    if std_dev == 0:
        return 0.0

    # Daily risk-free rate (assuming 252 trading days)
    daily_rf = risk_free_rate / 252

    # Annualized Sharpe
    excess_return = avg_return - daily_rf
    sharpe = (excess_return / std_dev) * math.sqrt(252)

    return sharpe


def _calculate_sortino(pnls: List[float], starting_balance: float, risk_free_rate: float) -> float:
    """Calculate Sortino ratio (uses downside deviation)"""
    if len(pnls) < 2:
        return 0.0

    returns = [p / starting_balance for p in pnls]
    avg_return = sum(returns) / len(returns)

    # Only negative returns for downside deviation
    negative_returns = [r for r in returns if r < 0]

    if not negative_returns:
        return float('inf') if avg_return > 0 else 0.0

    downside_variance = sum(r ** 2 for r in negative_returns) / len(negative_returns)
    downside_dev = math.sqrt(downside_variance)

    if downside_dev == 0:
        return 0.0

    daily_rf = risk_free_rate / 252
    excess_return = avg_return - daily_rf

    sortino = (excess_return / downside_dev) * math.sqrt(252)
    return sortino


def _calculate_duration_metrics(trades: List[Dict]) -> Dict:
    """Calculate average trade durations in minutes"""
    durations = []
    winning_durations = []
    losing_durations = []

    for trade in trades:
        entry = trade.get('entry_time')
        exit_t = trade.get('exit_time')
        pnl = trade.get('net_pnl', 0)

        if entry and exit_t:
            try:
                entry_dt = datetime.fromisoformat(entry)
                exit_dt = datetime.fromisoformat(exit_t)
                duration = (exit_dt - entry_dt).total_seconds() / 60

                durations.append(duration)

                if pnl > 0:
                    winning_durations.append(duration)
                elif pnl < 0:
                    losing_durations.append(duration)
            except:
                pass

    return {
        'average': sum(durations) / len(durations) if durations else 0,
        'winning': sum(winning_durations) / len(winning_durations) if winning_durations else 0,
        'losing': sum(losing_durations) / len(losing_durations) if losing_durations else 0
    }


def _calculate_consistency(trades: List[Dict]) -> Dict:
    """Calculate trading consistency metrics"""
    if not trades:
        return {'score': 0, 'best_day': 0, 'worst_day': 0, 'best_day_percent': 0}

    # Group trades by day
    daily_pnl = {}
    for trade in trades:
        exit_time = trade.get('exit_time', '')
        if exit_time:
            try:
                day = exit_time[:10]  # YYYY-MM-DD
                pnl = trade.get('net_pnl', 0)
                daily_pnl[day] = daily_pnl.get(day, 0) + pnl
            except:
                pass

    if not daily_pnl:
        return {'score': 0, 'best_day': 0, 'worst_day': 0, 'best_day_percent': 0}

    daily_values = list(daily_pnl.values())
    best_day = max(daily_values)
    worst_day = min(daily_values)
    total_pnl = sum(daily_values)

    # Best day as percent of total (for consistency rule)
    best_day_percent = (best_day / total_pnl * 100) if total_pnl > 0 else 0

    # Consistency score (lower variance = more consistent)
    if len(daily_values) > 1:
        avg = sum(daily_values) / len(daily_values)
        variance = sum((v - avg) ** 2 for v in daily_values) / len(daily_values)
        std_dev = math.sqrt(variance)

        # Score: inverse of coefficient of variation (higher = more consistent)
        if avg != 0:
            cv = std_dev / abs(avg)
            consistency_score = max(0, 100 - (cv * 50))  # Scale to 0-100
        else:
            consistency_score = 50
    else:
        consistency_score = 100  # Single day = perfectly consistent

    return {
        'score': consistency_score,
        'best_day': best_day,
        'worst_day': worst_day,
        'best_day_percent': best_day_percent
    }


def format_metrics_report(metrics: PerformanceMetrics) -> str:
    """Format metrics as readable report"""
    return f"""
PERFORMANCE METRICS
==================

BASIC STATISTICS
  Total Trades:           {metrics.total_trades}
  Winning Trades:         {metrics.winning_trades} ({metrics.win_rate:.1f}%)
  Losing Trades:          {metrics.losing_trades}

P&L SUMMARY
  Net Profit:             ${metrics.net_profit:,.2f}
  Gross Profit:           ${metrics.gross_profit:,.2f}
  Gross Loss:             ${metrics.gross_loss:,.2f}

TRADE AVERAGES
  Average Trade:          ${metrics.average_trade:,.2f}
  Average Win:            ${metrics.average_win:,.2f}
  Average Loss:           ${metrics.average_loss:,.2f}
  Largest Win:            ${metrics.largest_win:,.2f}
  Largest Loss:           ${metrics.largest_loss:,.2f}

RISK METRICS
  Profit Factor:          {metrics.profit_factor:.2f}
  Win/Loss Ratio:         {metrics.win_loss_ratio:.2f}
  Expectancy:             ${metrics.expectancy:,.2f}
  Kelly Criterion:        {metrics.kelly_criterion:.1f}%

DRAWDOWN
  Max Drawdown:           ${metrics.max_drawdown:,.2f} ({metrics.max_drawdown_percent:.2f}%)
  Average Drawdown:       ${metrics.average_drawdown:,.2f}
  Recovery Factor:        {metrics.recovery_factor:.2f}

RISK-ADJUSTED RETURNS
  Sharpe Ratio:           {metrics.sharpe_ratio:.2f}
  Sortino Ratio:          {metrics.sortino_ratio:.2f}
  Calmar Ratio:           {metrics.calmar_ratio:.2f}

STREAKS
  Max Consecutive Wins:   {metrics.max_consecutive_wins}
  Max Consecutive Losses: {metrics.max_consecutive_losses}

CONSISTENCY
  Consistency Score:      {metrics.consistency_score:.1f}/100
  Best Day:               ${metrics.best_day_pnl:,.2f} ({metrics.best_day_percent_of_total:.1f}% of total)
  Worst Day:              ${metrics.worst_day_pnl:,.2f}
"""
