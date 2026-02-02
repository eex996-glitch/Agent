# News Module for Futures Trading Agent
# Financial news fetching and sentiment analysis

from .fetcher import NewsFetcher
from .sentiment import SentimentAnalyzer, TradingAdjuster

__all__ = ['NewsFetcher', 'SentimentAnalyzer', 'TradingAdjuster']
