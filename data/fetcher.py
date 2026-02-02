"""
Data Fetcher Module

Handles fetching historical and real-time market data from various sources.
Primary source: Yahoo Finance (free, reliable for backtesting)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Union
import os
import pickle
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    yf = None
    print("Warning: yfinance not installed. Run: pip install yfinance")


class DataFetcher:
    """
    Fetches market data from various sources
    
    Supports:
    - Yahoo Finance (default, free)
    - Local CSV files
    - Cached data for faster loading
    """
    
    # Yahoo Finance symbols for common futures
    YAHOO_SYMBOLS = {
        "ES": "ES=F",      # E-mini S&P 500
        "MES": "MES=F",    # Micro E-mini S&P 500
        "NQ": "NQ=F",      # E-mini NASDAQ-100
        "MNQ": "MNQ=F",    # Micro E-mini NASDAQ-100
        "YM": "YM=F",      # E-mini Dow
        "MYM": "MYM=F",    # Micro E-mini Dow
        "RTY": "RTY=F",    # E-mini Russell 2000
        "M2K": "M2K=F",    # Micro E-mini Russell 2000
        "CL": "CL=F",      # Crude Oil
        "GC": "GC=F",      # Gold
        "SI": "SI=F",      # Silver
        "ZB": "ZB=F",      # 30-Year Treasury Bond
        "ZN": "ZN=F",      # 10-Year Treasury Note
        "6E": "6E=F",      # Euro FX
        "6J": "6J=F",      # Japanese Yen
    }
    
    def __init__(
        self,
        cache_dir: str = "./data/cache",
        use_cache: bool = True
    ):
        """
        Initialize the data fetcher
        
        Args:
            cache_dir: Directory for caching data
            use_cache: Whether to use cached data
        """
        self.cache_dir = Path(cache_dir)
        self.use_cache = use_cache
        
        if use_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get_symbol(self, market: str) -> str:
        """
        Get Yahoo Finance symbol for a market
        
        Args:
            market: Market identifier (ES, MES, NQ, etc.)
            
        Returns:
            Yahoo Finance ticker symbol
        """
        return self.YAHOO_SYMBOLS.get(market.upper(), f"{market.upper()}=F")
    
    def fetch_historical(
        self,
        symbol: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        interval: str = "1d",
        days_back: int = 365
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data
        
        Args:
            symbol: Market symbol (ES, MES, etc.) or Yahoo Finance symbol
            start_date: Start date for data
            end_date: End date for data
            interval: Data interval (1m, 5m, 15m, 1h, 1d, etc.)
            days_back: Number of days back if no start_date provided
            
        Returns:
            DataFrame with OHLCV data
        """
        if yf is None:
            raise ImportError("yfinance required. Install with: pip install yfinance")
        
        # Convert symbol if needed
        ticker_symbol = self.get_symbol(symbol) if "=" not in symbol else symbol
        
        # Set date range
        if end_date is None:
            end_date = datetime.now()
        elif isinstance(end_date, str):
            end_date = pd.to_datetime(end_date)
        
        if start_date is None:
            start_date = end_date - timedelta(days=days_back)
        elif isinstance(start_date, str):
            start_date = pd.to_datetime(start_date)
        
        # Check cache first
        cache_key = f"{ticker_symbol}_{interval}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        cache_path = self.cache_dir / f"{cache_key}.pkl"
        
        if self.use_cache and cache_path.exists():
            print(f"Loading cached data: {cache_path}")
            return pd.read_pickle(cache_path)
        
        print(f"Fetching {ticker_symbol} from {start_date.date()} to {end_date.date()}")
        
        # Fetch from Yahoo Finance
        ticker = yf.Ticker(ticker_symbol)
        
        # Yahoo Finance has limits on intraday data
        # 1m: 7 days, 5m: 60 days, 15m: 60 days, 1h: 730 days
        df = ticker.history(
            start=start_date,
            end=end_date,
            interval=interval,
            auto_adjust=True,
            prepost=True  # Include pre/post market
        )
        
        if df.empty:
            print(f"Warning: No data returned for {ticker_symbol}")
            return pd.DataFrame()
        
        # Clean and standardize columns
        df = self._standardize_dataframe(df)
        
        # Cache the data
        if self.use_cache:
            df.to_pickle(cache_path)
            print(f"Cached data to: {cache_path}")
        
        return df
    
    def fetch_intraday(
        self,
        symbol: str,
        interval: str = "5m",
        days_back: int = 60
    ) -> pd.DataFrame:
        """
        Fetch intraday data with appropriate limits
        
        Args:
            symbol: Market symbol
            interval: Intraday interval (1m, 5m, 15m, 30m, 1h)
            days_back: Number of days (limited by Yahoo Finance)
            
        Returns:
            DataFrame with intraday OHLCV data
        """
        # Yahoo Finance limits for intraday data
        interval_limits = {
            "1m": 7,
            "2m": 60,
            "5m": 60,
            "15m": 60,
            "30m": 60,
            "60m": 730,
            "1h": 730,
            "90m": 60,
        }
        
        max_days = interval_limits.get(interval, 60)
        actual_days = min(days_back, max_days)
        
        if days_back > max_days:
            print(f"Warning: {interval} data limited to {max_days} days by Yahoo Finance")
        
        return self.fetch_historical(
            symbol=symbol,
            interval=interval,
            days_back=actual_days
        )
    
    def fetch_multiple_timeframes(
        self,
        symbol: str,
        timeframes: List[str] = ["5m", "15m", "1h", "1d"],
        days_back: int = 60
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for multiple timeframes
        
        Args:
            symbol: Market symbol
            timeframes: List of intervals to fetch
            days_back: Number of days to fetch
            
        Returns:
            Dictionary mapping timeframe to DataFrame
        """
        data = {}
        
        for tf in timeframes:
            print(f"Fetching {tf} data for {symbol}...")
            df = self.fetch_intraday(symbol, interval=tf, days_back=days_back)
            if not df.empty:
                data[tf] = df
        
        return data
    
    def _standardize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Standardize DataFrame columns and index
        
        Args:
            df: Raw DataFrame from data source
            
        Returns:
            Standardized DataFrame
        """
        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        
        # Standardize column names
        column_mapping = {
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume',
            'Adj Close': 'adj_close'
        }
        
        df = df.rename(columns=column_mapping)
        
        # Keep only standard OHLCV columns
        standard_cols = ['open', 'high', 'low', 'close', 'volume']
        available_cols = [col for col in standard_cols if col in df.columns]
        df = df[available_cols]
        
        # Remove any rows with NaN values
        df = df.dropna()
        
        # Sort by index
        df = df.sort_index()
        
        return df
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """
        Get the latest price for a symbol
        
        Args:
            symbol: Market symbol
            
        Returns:
            Latest closing price or None
        """
        if yf is None:
            return None
        
        ticker_symbol = self.get_symbol(symbol)
        ticker = yf.Ticker(ticker_symbol)
        
        try:
            info = ticker.info
            return info.get('regularMarketPrice') or info.get('previousClose')
        except Exception as e:
            print(f"Error getting latest price: {e}")
            return None
    
    def clear_cache(self, symbol: Optional[str] = None):
        """
        Clear cached data
        
        Args:
            symbol: Specific symbol to clear, or None for all
        """
        if symbol:
            ticker_symbol = self.get_symbol(symbol)
            for cache_file in self.cache_dir.glob(f"{ticker_symbol}*.pkl"):
                cache_file.unlink()
                print(f"Removed cache: {cache_file}")
        else:
            for cache_file in self.cache_dir.glob("*.pkl"):
                cache_file.unlink()
                print(f"Removed cache: {cache_file}")


class DataLoader:
    """
    Loads and prepares data for backtesting and analysis
    """
    
    def __init__(self, fetcher: Optional[DataFetcher] = None):
        """
        Initialize the data loader
        
        Args:
            fetcher: DataFetcher instance (creates new one if not provided)
        """
        self.fetcher = fetcher or DataFetcher()
    
    def load_backtest_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        primary_tf: str = "5m",
        secondary_tf: str = "15m",
        daily_tf: str = "1d"
    ) -> Dict[str, pd.DataFrame]:
        """
        Load data for backtesting with multiple timeframes
        
        Args:
            symbol: Market symbol
            start_date: Backtest start date
            end_date: Backtest end date
            primary_tf: Primary trading timeframe
            secondary_tf: Secondary confirmation timeframe
            daily_tf: Daily timeframe for trend
            
        Returns:
            Dictionary with data for each timeframe
        """
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        days = (end - start).days
        
        # Fetch all timeframes
        data = {}
        
        # Daily data (always fetch)
        print(f"Loading {daily_tf} data...")
        data[daily_tf] = self.fetcher.fetch_historical(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=daily_tf
        )
        
        # Intraday data (subject to Yahoo limits)
        for tf in [primary_tf, secondary_tf]:
            if tf != daily_tf:
                print(f"Loading {tf} data...")
                data[tf] = self.fetcher.fetch_intraday(
                    symbol=symbol,
                    interval=tf,
                    days_back=min(days, 60)  # Yahoo limit
                )
        
        return data
    
    def prepare_training_data(
        self,
        df: pd.DataFrame,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15
    ) -> tuple:
        """
        Split data into train/validation/test sets
        
        Args:
            df: DataFrame to split
            train_ratio: Proportion for training
            val_ratio: Proportion for validation
            
        Returns:
            Tuple of (train_df, val_df, test_df)
        """
        n = len(df)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))
        
        train_df = df.iloc[:train_end]
        val_df = df.iloc[train_end:val_end]
        test_df = df.iloc[val_end:]
        
        print(f"Data split: Train={len(train_df)}, Val={len(val_df)}, Test={len(test_df)}")
        
        return train_df, val_df, test_df


# Example usage
if __name__ == "__main__":
    # Create fetcher
    fetcher = DataFetcher(cache_dir="./data/cache", use_cache=True)
    
    # Fetch E-mini S&P 500 daily data
    print("=== Fetching ES Daily Data ===")
    es_daily = fetcher.fetch_historical("ES", days_back=365, interval="1d")
    print(f"Fetched {len(es_daily)} daily bars")
    print(es_daily.tail())
    
    # Fetch Micro E-mini S&P 500 intraday data
    print("\n=== Fetching MES 5-minute Data ===")
    mes_5m = fetcher.fetch_intraday("MES", interval="5m", days_back=30)
    print(f"Fetched {len(mes_5m)} 5-minute bars")
    print(mes_5m.tail())
    
    # Get latest price
    print("\n=== Latest Price ===")
    latest = fetcher.get_latest_price("ES")
    print(f"ES latest price: ${latest:,.2f}" if latest else "Could not fetch price")
