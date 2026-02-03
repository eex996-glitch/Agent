"""
Strategy Tournament System

Backtests all available strategies on the same data and selects the best
performer based on a composite score of:
- Sharpe Ratio (risk-adjusted returns)
- Profit Factor (gross profit / gross loss)
- Win Rate
- Max Drawdown (penalized)
- Consistency Score (prop firm compliance)

Provides confidence metrics for the Model Health widget.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
import os

from .base import BaseStrategy
from .trend_following import TrendFollowingStrategy
from .mean_reversion import MeanReversionStrategy
from .breakout import BreakoutStrategy
from .adaptive import AdaptiveStrategy


@dataclass
class StrategyScore:
    """Score and metrics for a single strategy"""
    name: str
    total_return: float = 0.0
    total_return_pct: float = 0.0
    num_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    avg_trade: float = 0.0
    consistency_score: float = 0.0
    composite_score: float = 0.0
    confidence: float = 0.0

    # Component confidence scores
    trend_confidence: float = 50.0
    signal_confidence: float = 50.0
    risk_confidence: float = 50.0
    overall_confidence: float = 50.0

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'total_return': self.total_return,
            'total_return_pct': self.total_return_pct,
            'num_trades': self.num_trades,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_pct': self.max_drawdown_pct,
            'avg_trade': self.avg_trade,
            'consistency_score': self.consistency_score,
            'composite_score': self.composite_score,
            'confidence': self.confidence,
            'trend_confidence': self.trend_confidence,
            'signal_confidence': self.signal_confidence,
            'risk_confidence': self.risk_confidence,
            'overall_confidence': self.overall_confidence,
        }


@dataclass
class TournamentResult:
    """Results from a strategy tournament"""
    timestamp: str
    num_strategies: int
    num_bars: int
    best_strategy: str
    scores: List[StrategyScore]
    rankings: List[str]
    confidence_metrics: Dict

    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp,
            'num_strategies': self.num_strategies,
            'num_bars': self.num_bars,
            'best_strategy': self.best_strategy,
            'rankings': self.rankings,
            'scores': [s.to_dict() for s in self.scores],
            'confidence_metrics': self.confidence_metrics,
        }


def generate_realistic_data(n_bars: int = 2000, seed: int = 42) -> pd.DataFrame:
    """
    Generate realistic synthetic futures price data with:
    - Trending periods (momentum)
    - Mean-reverting periods (range-bound)
    - Volatility clusters (GARCH-like)
    - Support/resistance zones
    - Volume patterns

    This produces data that strategies can actually find patterns in,
    unlike pure random walk data.
    """
    np.random.seed(seed)

    dates = pd.date_range(start='2025-06-01', periods=n_bars, freq='5min')

    # Base price
    price = 5000.0
    prices = []
    volumes = []

    # Regime parameters - switch every ~100-300 bars for more variety
    regime_length = 0
    regime_target = np.random.randint(100, 300)
    current_regime = 'trend_up'
    regimes = ['trend_up', 'trend_down', 'range', 'volatile']
    range_anchor = price  # For mean-reverting ranges

    # Volatility (GARCH-like)
    vol = 0.5
    base_vol = 0.5

    for i in range(n_bars):
        regime_length += 1

        # Switch regime periodically
        if regime_length > regime_target:
            regime_length = 0
            regime_target = np.random.randint(100, 300)
            current_regime = regimes[np.random.randint(0, len(regimes))]
            range_anchor = price  # Reset anchor for range-bound

        # Regime-dependent drift and volatility
        if current_regime == 'trend_up':
            drift = 0.15  # Stronger upward drift
            vol_mult = 0.7
        elif current_regime == 'trend_down':
            drift = -0.12  # Stronger downward drift
            vol_mult = 0.8
        elif current_regime == 'range':
            # Mean reversion around anchor level
            drift = (range_anchor - price) * 0.05 + np.random.randn() * 0.01
            vol_mult = 0.5
        else:  # volatile
            drift = np.random.randn() * 0.08
            vol_mult = 1.8

        # GARCH-like volatility clustering
        vol = 0.9 * vol + 0.1 * base_vol + 0.2 * abs(np.random.randn()) * vol_mult
        vol = max(0.2, min(vol, 3.0))

        # Price change
        change = drift + np.random.randn() * vol

        # Add occasional gaps/jumps (news events)
        if np.random.random() < 0.005:
            change += np.random.choice([-3, -2, 2, 3]) * vol

        price += change
        price = max(price, 4800)  # Floor

        # Generate OHLC
        intra_vol = vol * 0.5
        h = price + abs(np.random.randn()) * intra_vol
        l = price - abs(np.random.randn()) * intra_vol
        o = prices[-1] if prices else price
        o += np.random.randn() * 0.1  # Small gap from previous close

        prices.append(price)

        # Volume: higher in trends, spikes on breakouts
        base_volume = 5000
        if current_regime in ['trend_up', 'trend_down']:
            vol_adj = 1.2
        elif current_regime == 'volatile':
            vol_adj = 1.5
        else:
            vol_adj = 0.8

        v = int(base_volume * vol_adj * (1 + abs(np.random.randn()) * 0.3))
        # Volume spike on big moves
        if abs(change) > vol * 1.5:
            v = int(v * 2.0)
        volumes.append(v)

    close = np.array(prices)
    open_p = np.roll(close, 1)
    open_p[0] = close[0]

    # Generate proper OHLC
    high = np.maximum(close, open_p) + np.abs(np.random.randn(n_bars) * 0.5)
    low = np.minimum(close, open_p) - np.abs(np.random.randn(n_bars) * 0.5)

    df = pd.DataFrame({
        'open': open_p,
        'high': high,
        'low': low,
        'close': close,
        'volume': volumes
    }, index=dates)

    return df


def run_tournament(
    data: pd.DataFrame = None,
    starting_balance: float = 50000.0,
    max_loss_limit: float = 2000.0,
    point_value: float = 5.0,
    symbol: str = "MES",
    n_bars: int = 2000,
    progress_callback=None
) -> TournamentResult:
    """
    Run a tournament of all strategies on the same data.

    Args:
        data: Historical data (generated if None)
        starting_balance: Account starting balance
        max_loss_limit: MLL for risk management
        point_value: Dollar value per point
        symbol: Trading symbol
        n_bars: Number of bars for data generation
        progress_callback: Optional callback for progress updates

    Returns:
        TournamentResult with rankings and confidence metrics
    """
    from backtest.engine import BacktestEngine, BacktestConfig

    # Generate data if not provided
    if data is None:
        if progress_callback:
            progress_callback("Generating realistic market data...")
        data = generate_realistic_data(n_bars)

    # Define strategies to test
    strategies = [
        TrendFollowingStrategy(
            name="TrendFollowing",
            params={'adx_threshold': 22.0, 'stop_loss_atr_mult': 1.8}
        ),
        MeanReversionStrategy(
            name="MeanReversion",
            params={'require_reversal_candle': False, 'stop_loss_atr_mult': 1.5}
        ),
        BreakoutStrategy(
            name="Breakout",
            params={'donchian_period': 18, 'volume_threshold': 1.2}
        ),
        AdaptiveStrategy(
            name="Adaptive",
            params={'entry_threshold': 60}
        ),
        # Variant with different parameters
        TrendFollowingStrategy(
            name="TrendFollowing_Aggressive",
            params={'adx_threshold': 18.0, 'stop_loss_atr_mult': 1.5,
                    'take_profit_atr_mult': 4.0}
        ),
        MeanReversionStrategy(
            name="MeanReversion_Relaxed",
            params={'require_reversal_candle': False,
                    'bb_entry_threshold': 0.15,
                    'rsi_oversold': 35, 'rsi_overbought': 65}
        ),
    ]

    config = BacktestConfig(
        starting_balance=starting_balance,
        symbol=symbol,
        point_value=point_value,
        max_loss_limit=max_loss_limit,
        daily_loss_limit=1000.0,
        max_risk_per_trade=0.01,
        max_contracts=3
    )

    scores = []

    for i, strategy in enumerate(strategies):
        if progress_callback:
            progress_callback(
                f"Testing strategy {i+1}/{len(strategies)}: {strategy.name}..."
            )

        try:
            # Reset strategy
            strategy.reset()

            # Prepare data
            prepared_data = strategy.prepare_data(data.copy())

            # Run backtest
            engine = BacktestEngine(config)

            # Determine warmup period
            warmup = 250  # Default
            if hasattr(strategy, 'params'):
                # Use the largest period parameter as warmup
                period_params = [v for k, v in strategy.params.items()
                                if 'period' in k.lower() or 'ema' in k.lower()]
                if period_params:
                    warmup = max(max(period_params) + 50, 200)

            result = engine.run(strategy, prepared_data, start_idx=warmup)

            # Create score
            score = StrategyScore(
                name=strategy.name,
                total_return=result.total_return,
                total_return_pct=result.total_return_pct,
                num_trades=result.num_trades,
                win_rate=result.win_rate * 100,
                profit_factor=result.profit_factor,
                sharpe_ratio=result.sharpe_ratio,
                sortino_ratio=result.sortino_ratio,
                max_drawdown=result.max_drawdown,
                max_drawdown_pct=result.max_drawdown_pct,
                avg_trade=result.avg_trade,
                consistency_score=result.consistency_score,
            )

            # Calculate composite score (weighted ranking)
            score.composite_score = _calculate_composite(score)
            score.confidence = _calculate_confidence(score)

            # Component confidences
            score.trend_confidence = min(100, max(0,
                50 + score.sharpe_ratio * 10 + (score.win_rate - 50) * 0.5))
            score.signal_confidence = min(100, max(0,
                score.win_rate * 0.8 + score.profit_factor * 10))
            score.risk_confidence = min(100, max(0,
                90 - score.max_drawdown_pct * 5))
            score.overall_confidence = score.confidence

            scores.append(score)

        except Exception as e:
            if progress_callback:
                progress_callback(f"  Error testing {strategy.name}: {e}")
            # Add a zero-score entry
            scores.append(StrategyScore(name=strategy.name))

    # Rank strategies by composite score
    scores.sort(key=lambda s: s.composite_score, reverse=True)
    rankings = [s.name for s in scores]

    best = scores[0] if scores else None

    # Build confidence metrics from best strategy
    confidence_metrics = {}
    if best:
        confidence_metrics = {
            'overall': best.overall_confidence,
            'trend_detection': best.trend_confidence,
            'signal_quality': best.signal_confidence,
            'risk_assessment': best.risk_confidence,
            'best_strategy': best.name,
            'best_win_rate': best.win_rate,
            'best_profit_factor': best.profit_factor,
            'best_sharpe': best.sharpe_ratio,
            'best_max_dd': best.max_drawdown,
            'best_total_return': best.total_return,
            'best_num_trades': best.num_trades,
        }

    result = TournamentResult(
        timestamp=datetime.now().isoformat(),
        num_strategies=len(strategies),
        num_bars=len(data),
        best_strategy=best.name if best else "None",
        scores=scores,
        rankings=rankings,
        confidence_metrics=confidence_metrics,
    )

    if progress_callback:
        progress_callback(f"Tournament complete! Best: {result.best_strategy}")

    # Save tournament results
    _save_tournament_results(result)

    return result


def _calculate_composite(score: StrategyScore) -> float:
    """
    Calculate composite score from multiple metrics.
    Higher is better. Weights:
    - Sharpe Ratio: 25%
    - Profit Factor: 20%
    - Win Rate: 15%
    - Total Return: 15%
    - Max Drawdown (penalty): 15%
    - Consistency: 10%
    """
    composite = 0.0

    # Sharpe (0-25 points, capped at 3.0)
    sharpe_pts = min(25, max(0, score.sharpe_ratio * 8.33))
    composite += sharpe_pts

    # Profit Factor (0-20 points, capped at 3.0)
    pf_pts = min(20, max(0, (score.profit_factor - 0.5) * 8))
    composite += pf_pts

    # Win Rate (0-15 points)
    wr_pts = min(15, max(0, (score.win_rate - 30) * 0.375))
    composite += wr_pts

    # Total Return (0-15 points, normalized)
    ret_pts = min(15, max(0, (score.total_return_pct + 2) * 3))
    composite += ret_pts

    # Max Drawdown penalty (0-15 points, lower DD = more points)
    dd_pts = max(0, 15 - score.max_drawdown_pct * 1.5)
    composite += dd_pts

    # Consistency (0-10 points, score < 50% is good for prop firms)
    if score.consistency_score > 0:
        cons_pts = max(0, 10 - (score.consistency_score - 30) * 0.5)
    else:
        cons_pts = 5  # Neutral if no data
    composite += cons_pts

    # Penalty for too few trades (unreliable results)
    if score.num_trades < 5:
        composite *= 0.3
    elif score.num_trades < 10:
        composite *= 0.6
    elif score.num_trades < 20:
        composite *= 0.85

    return composite


def _calculate_confidence(score: StrategyScore) -> float:
    """Calculate confidence percentage (0-100) for model health display"""
    if score.num_trades < 3:
        return 20.0  # Very low confidence with few trades

    confidence = 50.0  # Start at neutral

    # Positive factors
    if score.win_rate > 55:
        confidence += (score.win_rate - 55) * 0.5
    if score.profit_factor > 1.0:
        confidence += min(15, (score.profit_factor - 1.0) * 10)
    if score.sharpe_ratio > 0:
        confidence += min(10, score.sharpe_ratio * 5)
    if score.total_return > 0:
        confidence += min(10, score.total_return_pct * 2)

    # Negative factors
    if score.max_drawdown_pct > 5:
        confidence -= (score.max_drawdown_pct - 5) * 2
    if score.win_rate < 40:
        confidence -= (40 - score.win_rate) * 0.5
    if score.profit_factor < 1.0:
        confidence -= (1.0 - score.profit_factor) * 15

    return max(10, min(95, confidence))


def _save_tournament_results(result: TournamentResult):
    """Save tournament results to logs directory"""
    try:
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        os.makedirs(logs_dir, exist_ok=True)

        filepath = os.path.join(logs_dir, 'tournament_results.json')
        with open(filepath, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)

    except Exception:
        pass  # Don't fail on log write errors


def get_latest_tournament_results() -> Optional[TournamentResult]:
    """Load the most recent tournament results"""
    try:
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        filepath = os.path.join(logs_dir, 'tournament_results.json')

        if not os.path.exists(filepath):
            return None

        with open(filepath) as f:
            data = json.load(f)

        scores = [StrategyScore(**s) for s in data.get('scores', [])]

        return TournamentResult(
            timestamp=data['timestamp'],
            num_strategies=data['num_strategies'],
            num_bars=data['num_bars'],
            best_strategy=data['best_strategy'],
            scores=scores,
            rankings=data['rankings'],
            confidence_metrics=data['confidence_metrics'],
        )

    except Exception:
        return None
