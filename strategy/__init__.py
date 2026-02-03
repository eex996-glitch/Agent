"""Strategy Package"""
from .base import BaseStrategy, TradeSignal, Signal, Position
from .indicators import Indicators
from .trend_following import TrendFollowingStrategy
from .mean_reversion import MeanReversionStrategy
from .breakout import BreakoutStrategy
from .adaptive import AdaptiveStrategy
from .tournament import run_tournament, get_latest_tournament_results, generate_realistic_data

