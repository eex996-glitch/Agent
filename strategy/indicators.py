"""
Technical Indicators Module

Provides technical analysis indicators for strategy development.
All indicators return pandas Series or DataFrames that align with input data.
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple, Union


class Indicators:
    """
    Collection of technical indicators for futures trading
    """
    
    # ==================== TREND INDICATORS ====================
    
    @staticmethod
    def sma(series: pd.Series, period: int) -> pd.Series:
        """
        Simple Moving Average
        
        Args:
            series: Price series (typically close)
            period: Lookback period
            
        Returns:
            SMA series
        """
        return series.rolling(window=period).mean()
    
    @staticmethod
    def ema(series: pd.Series, period: int) -> pd.Series:
        """
        Exponential Moving Average
        
        Args:
            series: Price series
            period: Lookback period
            
        Returns:
            EMA series
        """
        return series.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def ema_ribbon(
        close: pd.Series,
        periods: list = [8, 13, 21, 34, 55, 89]
    ) -> pd.DataFrame:
        """
        EMA Ribbon - Multiple EMAs for trend visualization
        
        Args:
            close: Close price series
            periods: List of EMA periods
            
        Returns:
            DataFrame with EMA columns
        """
        ribbon = pd.DataFrame(index=close.index)
        for period in periods:
            ribbon[f'ema_{period}'] = Indicators.ema(close, period)
        return ribbon
    
    @staticmethod
    def macd(
        close: pd.Series,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> pd.DataFrame:
        """
        Moving Average Convergence Divergence
        
        Args:
            close: Close price series
            fast_period: Fast EMA period
            slow_period: Slow EMA period
            signal_period: Signal line period
            
        Returns:
            DataFrame with macd, signal, histogram columns
        """
        fast_ema = Indicators.ema(close, fast_period)
        slow_ema = Indicators.ema(close, slow_period)
        
        macd_line = fast_ema - slow_ema
        signal_line = Indicators.ema(macd_line, signal_period)
        histogram = macd_line - signal_line
        
        return pd.DataFrame({
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }, index=close.index)
    
    @staticmethod
    def adx(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14
    ) -> pd.DataFrame:
        """
        Average Directional Index with +DI and -DI
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: ADX period
            
        Returns:
            DataFrame with adx, plus_di, minus_di columns
        """
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        # Directional Movement
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        plus_dm = pd.Series(plus_dm, index=close.index)
        minus_dm = pd.Series(minus_dm, index=close.index)
        
        # Smoothed DI
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        
        # ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        return pd.DataFrame({
            'adx': adx,
            'plus_di': plus_di,
            'minus_di': minus_di
        }, index=close.index)
    
    @staticmethod
    def supertrend(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 10,
        multiplier: float = 3.0
    ) -> pd.DataFrame:
        """
        Supertrend Indicator
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: ATR period
            multiplier: ATR multiplier
            
        Returns:
            DataFrame with supertrend, direction columns
        """
        atr = Indicators.atr(high, low, close, period)
        hl2 = (high + low) / 2
        
        upper_band = hl2 + (multiplier * atr)
        lower_band = hl2 - (multiplier * atr)
        
        supertrend = pd.Series(index=close.index, dtype=float)
        direction = pd.Series(index=close.index, dtype=int)
        
        for i in range(1, len(close)):
            if close.iloc[i] > upper_band.iloc[i-1]:
                direction.iloc[i] = 1
            elif close.iloc[i] < lower_band.iloc[i-1]:
                direction.iloc[i] = -1
            else:
                direction.iloc[i] = direction.iloc[i-1]
                
                if direction.iloc[i] == 1 and lower_band.iloc[i] < lower_band.iloc[i-1]:
                    lower_band.iloc[i] = lower_band.iloc[i-1]
                if direction.iloc[i] == -1 and upper_band.iloc[i] > upper_band.iloc[i-1]:
                    upper_band.iloc[i] = upper_band.iloc[i-1]
            
            supertrend.iloc[i] = lower_band.iloc[i] if direction.iloc[i] == 1 else upper_band.iloc[i]
        
        return pd.DataFrame({
            'supertrend': supertrend,
            'direction': direction
        }, index=close.index)
    
    # ==================== MOMENTUM INDICATORS ====================
    
    @staticmethod
    def rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """
        Relative Strength Index
        
        Args:
            series: Price series (typically close)
            period: RSI period
            
        Returns:
            RSI series (0-100)
        """
        delta = series.diff()
        
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def stochastic(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        k_period: int = 14,
        d_period: int = 3
    ) -> pd.DataFrame:
        """
        Stochastic Oscillator
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            k_period: %K period
            d_period: %D smoothing period
            
        Returns:
            DataFrame with k, d columns
        """
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        
        k = 100 * (close - lowest_low) / (highest_high - lowest_low)
        d = k.rolling(window=d_period).mean()
        
        return pd.DataFrame({
            'k': k,
            'd': d
        }, index=close.index)
    
    @staticmethod
    def cci(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 20
    ) -> pd.Series:
        """
        Commodity Channel Index
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: CCI period
            
        Returns:
            CCI series
        """
        typical_price = (high + low + close) / 3
        sma = typical_price.rolling(window=period).mean()
        mean_deviation = typical_price.rolling(window=period).apply(
            lambda x: np.abs(x - x.mean()).mean()
        )
        
        cci = (typical_price - sma) / (0.015 * mean_deviation)
        return cci
    
    @staticmethod
    def williams_r(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14
    ) -> pd.Series:
        """
        Williams %R
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: Lookback period
            
        Returns:
            Williams %R series (-100 to 0)
        """
        highest_high = high.rolling(window=period).max()
        lowest_low = low.rolling(window=period).min()
        
        wr = -100 * (highest_high - close) / (highest_high - lowest_low)
        return wr
    
    # ==================== VOLATILITY INDICATORS ====================
    
    @staticmethod
    def atr(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14
    ) -> pd.Series:
        """
        Average True Range
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: ATR period
            
        Returns:
            ATR series
        """
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    @staticmethod
    def bollinger_bands(
        close: pd.Series,
        period: int = 20,
        std_dev: float = 2.0
    ) -> pd.DataFrame:
        """
        Bollinger Bands
        
        Args:
            close: Close prices
            period: SMA period
            std_dev: Standard deviation multiplier
            
        Returns:
            DataFrame with upper, middle, lower, bandwidth columns
        """
        middle = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        bandwidth = (upper - lower) / middle * 100
        
        return pd.DataFrame({
            'upper': upper,
            'middle': middle,
            'lower': lower,
            'bandwidth': bandwidth
        }, index=close.index)
    
    @staticmethod
    def keltner_channels(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        ema_period: int = 20,
        atr_period: int = 10,
        atr_mult: float = 2.0
    ) -> pd.DataFrame:
        """
        Keltner Channels
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            ema_period: EMA period for middle line
            atr_period: ATR period
            atr_mult: ATR multiplier for bands
            
        Returns:
            DataFrame with upper, middle, lower columns
        """
        middle = Indicators.ema(close, ema_period)
        atr = Indicators.atr(high, low, close, atr_period)
        
        upper = middle + (atr * atr_mult)
        lower = middle - (atr * atr_mult)
        
        return pd.DataFrame({
            'upper': upper,
            'middle': middle,
            'lower': lower
        }, index=close.index)
    
    @staticmethod
    def volatility_ratio(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14
    ) -> pd.Series:
        """
        Volatility Ratio (True Range / ATR)
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: ATR period
            
        Returns:
            Volatility ratio series
        """
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        atr = Indicators.atr(high, low, close, period)
        
        return tr / atr
    
    # ==================== VOLUME INDICATORS ====================
    
    @staticmethod
    def volume_sma(volume: pd.Series, period: int = 20) -> pd.Series:
        """
        Volume Simple Moving Average
        
        Args:
            volume: Volume series
            period: SMA period
            
        Returns:
            Volume SMA series
        """
        return volume.rolling(window=period).mean()
    
    @staticmethod
    def volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
        """
        Volume Ratio (current volume / average volume)
        
        Args:
            volume: Volume series
            period: Average period
            
        Returns:
            Volume ratio series
        """
        avg_vol = volume.rolling(window=period).mean()
        return volume / avg_vol
    
    @staticmethod
    def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """
        On Balance Volume
        
        Args:
            close: Close prices
            volume: Volume
            
        Returns:
            OBV series
        """
        direction = np.where(close > close.shift(1), 1,
                           np.where(close < close.shift(1), -1, 0))
        
        obv = (volume * direction).cumsum()
        return pd.Series(obv, index=close.index)
    
    @staticmethod
    def vwap(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        volume: pd.Series
    ) -> pd.Series:
        """
        Volume Weighted Average Price (intraday reset)
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            volume: Volume
            
        Returns:
            VWAP series
        """
        typical_price = (high + low + close) / 3
        cum_vol = volume.cumsum()
        cum_vol_price = (typical_price * volume).cumsum()
        
        vwap = cum_vol_price / cum_vol
        return vwap
    
    # ==================== SUPPORT/RESISTANCE ====================
    
    @staticmethod
    def pivot_points(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series
    ) -> pd.DataFrame:
        """
        Standard Pivot Points
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            
        Returns:
            DataFrame with pivot, r1, r2, r3, s1, s2, s3 columns
        """
        pivot = (high + low + close) / 3
        
        r1 = 2 * pivot - low
        s1 = 2 * pivot - high
        r2 = pivot + (high - low)
        s2 = pivot - (high - low)
        r3 = high + 2 * (pivot - low)
        s3 = low - 2 * (high - pivot)
        
        return pd.DataFrame({
            'pivot': pivot,
            'r1': r1, 'r2': r2, 'r3': r3,
            's1': s1, 's2': s2, 's3': s3
        }, index=close.index)
    
    @staticmethod
    def donchian_channels(
        high: pd.Series,
        low: pd.Series,
        period: int = 20
    ) -> pd.DataFrame:
        """
        Donchian Channels
        
        Args:
            high: High prices
            low: Low prices
            period: Lookback period
            
        Returns:
            DataFrame with upper, lower, middle columns
        """
        upper = high.rolling(window=period).max()
        lower = low.rolling(window=period).min()
        middle = (upper + lower) / 2
        
        return pd.DataFrame({
            'upper': upper,
            'lower': lower,
            'middle': middle
        }, index=high.index)
    
    # ==================== UTILITY FUNCTIONS ====================
    
    @staticmethod
    def add_all_indicators(
        df: pd.DataFrame,
        fast_ema: int = 9,
        slow_ema: int = 21,
        trend_ema: int = 200,
        rsi_period: int = 14,
        atr_period: int = 14,
        adx_period: int = 14,
        bb_period: int = 20,
        bb_std: float = 2.0
    ) -> pd.DataFrame:
        """
        Add common indicators to a DataFrame
        
        Args:
            df: DataFrame with OHLCV columns
            Various indicator parameters...
            
        Returns:
            DataFrame with indicator columns added
        """
        result = df.copy()
        
        # Trend indicators
        result['ema_fast'] = Indicators.ema(df['close'], fast_ema)
        result['ema_slow'] = Indicators.ema(df['close'], slow_ema)
        result['ema_trend'] = Indicators.ema(df['close'], trend_ema)
        
        # MACD
        macd = Indicators.macd(df['close'])
        result['macd'] = macd['macd']
        result['macd_signal'] = macd['signal']
        result['macd_hist'] = macd['histogram']
        
        # ADX
        adx = Indicators.adx(df['high'], df['low'], df['close'], adx_period)
        result['adx'] = adx['adx']
        result['plus_di'] = adx['plus_di']
        result['minus_di'] = adx['minus_di']
        
        # Momentum
        result['rsi'] = Indicators.rsi(df['close'], rsi_period)
        
        # Volatility
        result['atr'] = Indicators.atr(df['high'], df['low'], df['close'], atr_period)
        
        bb = Indicators.bollinger_bands(df['close'], bb_period, bb_std)
        result['bb_upper'] = bb['upper']
        result['bb_middle'] = bb['middle']
        result['bb_lower'] = bb['lower']
        result['bb_bandwidth'] = bb['bandwidth']
        
        # Volume (if available)
        if 'volume' in df.columns:
            result['volume_sma'] = Indicators.volume_sma(df['volume'], 20)
            result['volume_ratio'] = Indicators.volume_ratio(df['volume'], 20)
        
        return result


# Example usage
if __name__ == "__main__":
    # Create sample data
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    
    # Simulated price data
    close = pd.Series(100 + np.cumsum(np.random.randn(100) * 0.5), index=dates)
    high = close + np.abs(np.random.randn(100) * 0.3)
    low = close - np.abs(np.random.randn(100) * 0.3)
    volume = pd.Series(np.random.randint(1000, 5000, 100), index=dates)
    
    df = pd.DataFrame({
        'open': close.shift(1).fillna(close.iloc[0]),
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    })
    
    # Add all indicators
    df_with_indicators = Indicators.add_all_indicators(df)
    
    print("=== Sample Data with Indicators ===")
    print(df_with_indicators.tail(10))
    
    print("\n=== Available Columns ===")
    print(df_with_indicators.columns.tolist())
