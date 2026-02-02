"""
Trend Following Strategy

A multi-timeframe trend following strategy designed for futures trading
with prop firm rule compliance (Topstep).

Key Features:
- EMA alignment for trend direction
- ADX for trend strength confirmation
- Pullback entries in trending markets
- ATR-based stop losses and profit targets
- Consistency-focused position sizing
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
from datetime import datetime

from .base import BaseStrategy, TradeSignal, Signal, OrderType, Position
from .indicators import Indicators


class TrendFollowingStrategy(BaseStrategy):
    """
    Adaptive Trend Following Strategy
    
    Entry Conditions (Long):
    1. Price above 200 EMA (uptrend)
    2. Fast EMA > Slow EMA (momentum)
    3. ADX > threshold (trending market)
    4. RSI not overbought
    5. Price pulls back to fast/slow EMA zone
    
    Entry Conditions (Short):
    1. Price below 200 EMA (downtrend)
    2. Fast EMA < Slow EMA (momentum)
    3. ADX > threshold (trending market)
    4. RSI not oversold
    5. Price pulls back to fast/slow EMA zone
    
    Exit Conditions:
    - Stop loss: ATR-based
    - Take profit: ATR-based or trailing
    - Time exit: Max hold time
    - Signal reversal
    """
    
    DEFAULT_PARAMS = {
        # EMA periods
        'fast_ema': 9,
        'slow_ema': 21,
        'trend_ema': 200,
        
        # ADX settings
        'adx_period': 14,
        'adx_threshold': 25.0,
        
        # RSI settings
        'rsi_period': 14,
        'rsi_overbought': 70.0,
        'rsi_oversold': 30.0,
        
        # ATR settings
        'atr_period': 14,
        'stop_loss_atr_mult': 2.0,
        'take_profit_atr_mult': 3.0,
        'trailing_stop_atr_mult': 1.5,
        
        # Entry settings
        'pullback_threshold': 0.5,  # % distance to EMA for pullback
        'min_risk_reward': 1.5,
        
        # Position management
        'use_trailing_stop': True,
        'partial_exit_enabled': False,
        'partial_exit_ratio': 0.5,
        
        # Time filters
        'max_hold_bars': 48,  # Max bars to hold position
        'min_bars_between_trades': 3,  # Cooldown period
    }
    
    def __init__(self, name: str = "TrendFollowing", params: Dict[str, Any] = None):
        """Initialize the strategy"""
        # Merge default params with provided params
        merged_params = self.DEFAULT_PARAMS.copy()
        if params:
            merged_params.update(params)
        
        super().__init__(name=name, params=merged_params)
        
        # State tracking
        self.bars_since_last_trade = 0
        self.bars_in_position = 0
    
    def on_init(self):
        """Initialize strategy state"""
        self.bars_since_last_trade = self.params['min_bars_between_trades']
        self.bars_in_position = 0
    
    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Add required indicators to the data
        
        Args:
            data: Raw OHLCV DataFrame
            
        Returns:
            DataFrame with indicators added
        """
        df = data.copy()
        
        # EMAs
        df['ema_fast'] = Indicators.ema(df['close'], self.params['fast_ema'])
        df['ema_slow'] = Indicators.ema(df['close'], self.params['slow_ema'])
        df['ema_trend'] = Indicators.ema(df['close'], self.params['trend_ema'])
        
        # ADX
        adx_data = Indicators.adx(
            df['high'], df['low'], df['close'],
            self.params['adx_period']
        )
        df['adx'] = adx_data['adx']
        df['plus_di'] = adx_data['plus_di']
        df['minus_di'] = adx_data['minus_di']
        
        # RSI
        df['rsi'] = Indicators.rsi(df['close'], self.params['rsi_period'])
        
        # ATR
        df['atr'] = Indicators.atr(
            df['high'], df['low'], df['close'],
            self.params['atr_period']
        )
        
        # MACD for additional confirmation
        macd_data = Indicators.macd(df['close'])
        df['macd'] = macd_data['macd']
        df['macd_signal'] = macd_data['signal']
        df['macd_hist'] = macd_data['histogram']
        
        # Trend direction
        df['trend'] = np.where(df['close'] > df['ema_trend'], 1,
                              np.where(df['close'] < df['ema_trend'], -1, 0))
        
        # EMA alignment
        df['ema_bullish'] = (df['ema_fast'] > df['ema_slow']).astype(int)
        df['ema_bearish'] = (df['ema_fast'] < df['ema_slow']).astype(int)
        
        # Distance from EMAs (for pullback detection)
        df['dist_from_fast_ema'] = (df['close'] - df['ema_fast']) / df['atr']
        df['dist_from_slow_ema'] = (df['close'] - df['ema_slow']) / df['atr']
        
        return df
    
    def _check_trend_conditions(self, data: pd.DataFrame, idx: int) -> tuple:
        """
        Check overall trend conditions
        
        Returns:
            Tuple of (is_uptrend, is_downtrend, is_trending)
        """
        close = data['close'].iloc[idx]
        ema_trend = data['ema_trend'].iloc[idx]
        ema_fast = data['ema_fast'].iloc[idx]
        ema_slow = data['ema_slow'].iloc[idx]
        adx = data['adx'].iloc[idx]
        
        # Check for NaN values
        if pd.isna(ema_trend) or pd.isna(adx):
            return False, False, False
        
        is_trending = adx > self.params['adx_threshold']
        is_uptrend = close > ema_trend and ema_fast > ema_slow
        is_downtrend = close < ema_trend and ema_fast < ema_slow
        
        return is_uptrend, is_downtrend, is_trending
    
    def _check_pullback(self, data: pd.DataFrame, idx: int, direction: str) -> bool:
        """
        Check if price has pulled back to EMA zone
        
        Args:
            data: DataFrame with indicators
            idx: Current index
            direction: 'long' or 'short'
            
        Returns:
            True if pullback condition is met
        """
        close = data['close'].iloc[idx]
        ema_fast = data['ema_fast'].iloc[idx]
        ema_slow = data['ema_slow'].iloc[idx]
        atr = data['atr'].iloc[idx]
        
        if pd.isna(atr) or atr == 0:
            return False
        
        # Calculate EMA zone
        ema_upper = max(ema_fast, ema_slow)
        ema_lower = min(ema_fast, ema_slow)
        
        # Add buffer based on ATR
        buffer = atr * self.params['pullback_threshold']
        
        if direction == 'long':
            # Price should be near or below the EMA zone
            return close <= ema_upper + buffer and close >= ema_lower - buffer
        else:
            # Price should be near or above the EMA zone
            return close >= ema_lower - buffer and close <= ema_upper + buffer
    
    def _check_momentum(self, data: pd.DataFrame, idx: int, direction: str) -> bool:
        """
        Check momentum conditions using RSI and MACD
        
        Args:
            data: DataFrame with indicators
            idx: Current index
            direction: 'long' or 'short'
            
        Returns:
            True if momentum conditions are met
        """
        rsi = data['rsi'].iloc[idx]
        macd_hist = data['macd_hist'].iloc[idx]
        
        if pd.isna(rsi) or pd.isna(macd_hist):
            return False
        
        if direction == 'long':
            # Not overbought, MACD histogram positive or turning up
            rsi_ok = rsi < self.params['rsi_overbought']
            macd_ok = macd_hist > data['macd_hist'].iloc[idx-1] if idx > 0 else True
            return rsi_ok and macd_ok
        else:
            # Not oversold, MACD histogram negative or turning down
            rsi_ok = rsi > self.params['rsi_oversold']
            macd_ok = macd_hist < data['macd_hist'].iloc[idx-1] if idx > 0 else True
            return rsi_ok and macd_ok
    
    def _calculate_stop_loss(
        self,
        entry_price: float,
        atr: float,
        direction: str
    ) -> float:
        """Calculate stop loss price"""
        stop_distance = atr * self.params['stop_loss_atr_mult']
        
        if direction == 'long':
            return entry_price - stop_distance
        else:
            return entry_price + stop_distance
    
    def _calculate_take_profit(
        self,
        entry_price: float,
        atr: float,
        direction: str
    ) -> float:
        """Calculate take profit price"""
        profit_distance = atr * self.params['take_profit_atr_mult']
        
        if direction == 'long':
            return entry_price + profit_distance
        else:
            return entry_price - profit_distance
    
    def generate_signal(
        self,
        data: pd.DataFrame,
        current_idx: int
    ) -> Optional[TradeSignal]:
        """
        Generate trading signal based on current market conditions
        
        Args:
            data: DataFrame with OHLCV and indicators
            current_idx: Current bar index
            
        Returns:
            TradeSignal if conditions are met, None otherwise
        """
        # Need enough data for indicators
        if current_idx < self.params['trend_ema']:
            return None
        
        # Ensure data has required indicators
        required_cols = ['ema_fast', 'ema_slow', 'ema_trend', 'adx', 'rsi', 'atr']
        if not all(col in data.columns for col in required_cols):
            data = self.prepare_data(data)
        
        current_time = data.index[current_idx]
        close = data['close'].iloc[current_idx]
        atr = data['atr'].iloc[current_idx]
        
        # Skip if ATR is invalid
        if pd.isna(atr) or atr == 0:
            return None
        
        # Update trade cooldown
        self.bars_since_last_trade += 1
        
        # If in position, update position tracking
        if self.position:
            self.bars_in_position += 1
            
            # Check for time-based exit
            if self.bars_in_position >= self.params['max_hold_bars']:
                return TradeSignal(
                    timestamp=current_time,
                    signal=Signal.FLAT,
                    price=close,
                    reason="max_hold_time",
                    indicators={'bars_held': self.bars_in_position}
                )
            
            # Check for trend reversal exit
            is_uptrend, is_downtrend, _ = self._check_trend_conditions(data, current_idx)
            
            if self.position.is_long and is_downtrend:
                return TradeSignal(
                    timestamp=current_time,
                    signal=Signal.FLAT,
                    price=close,
                    reason="trend_reversal"
                )
            elif self.position.is_short and is_uptrend:
                return TradeSignal(
                    timestamp=current_time,
                    signal=Signal.FLAT,
                    price=close,
                    reason="trend_reversal"
                )
            
            return None  # No exit signal, hold position
        
        # No position - check for entry
        
        # Check cooldown
        if self.bars_since_last_trade < self.params['min_bars_between_trades']:
            return None
        
        # Check trend conditions
        is_uptrend, is_downtrend, is_trending = self._check_trend_conditions(
            data, current_idx
        )
        
        if not is_trending:
            return None  # No trade in ranging market
        
        # Check for LONG entry
        if is_uptrend:
            pullback_ok = self._check_pullback(data, current_idx, 'long')
            momentum_ok = self._check_momentum(data, current_idx, 'long')
            
            if pullback_ok and momentum_ok:
                stop_loss = self._calculate_stop_loss(close, atr, 'long')
                take_profit = self._calculate_take_profit(close, atr, 'long')
                
                # Check risk/reward
                risk = close - stop_loss
                reward = take_profit - close
                if reward / risk < self.params['min_risk_reward']:
                    return None
                
                trailing = atr * self.params['trailing_stop_atr_mult'] if \
                    self.params['use_trailing_stop'] else None
                
                self.bars_since_last_trade = 0
                self.bars_in_position = 0
                
                return TradeSignal(
                    timestamp=current_time,
                    signal=Signal.LONG,
                    price=close,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    trailing_stop=trailing,
                    reason="trend_pullback_long",
                    indicators={
                        'adx': data['adx'].iloc[current_idx],
                        'rsi': data['rsi'].iloc[current_idx],
                        'atr': atr
                    }
                )
        
        # Check for SHORT entry
        elif is_downtrend:
            pullback_ok = self._check_pullback(data, current_idx, 'short')
            momentum_ok = self._check_momentum(data, current_idx, 'short')
            
            if pullback_ok and momentum_ok:
                stop_loss = self._calculate_stop_loss(close, atr, 'short')
                take_profit = self._calculate_take_profit(close, atr, 'short')
                
                # Check risk/reward
                risk = stop_loss - close
                reward = close - take_profit
                if reward / risk < self.params['min_risk_reward']:
                    return None
                
                trailing = atr * self.params['trailing_stop_atr_mult'] if \
                    self.params['use_trailing_stop'] else None
                
                self.bars_since_last_trade = 0
                self.bars_in_position = 0
                
                return TradeSignal(
                    timestamp=current_time,
                    signal=Signal.SHORT,
                    price=close,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    trailing_stop=trailing,
                    reason="trend_pullback_short",
                    indicators={
                        'adx': data['adx'].iloc[current_idx],
                        'rsi': data['rsi'].iloc[current_idx],
                        'atr': atr
                    }
                )
        
        return None
    
    def calculate_position_size(
        self,
        signal: TradeSignal,
        account_value: float,
        risk_per_trade: float,
        point_value: float = 5.0,  # Default for MES
        max_contracts: int = 5
    ) -> int:
        """
        Calculate position size based on risk management
        
        Uses fixed fractional position sizing:
        Position Size = (Account Risk) / (Trade Risk per Contract)
        
        Args:
            signal: The trade signal
            account_value: Current account value
            risk_per_trade: Fraction of account to risk (e.g., 0.01 for 1%)
            point_value: Dollar value per point
            max_contracts: Maximum allowed contracts (from scaling plan)
            
        Returns:
            Number of contracts to trade
        """
        if signal.stop_loss is None:
            return 1  # Default to 1 contract if no stop loss
        
        # Calculate dollar risk per contract
        price_risk = abs(signal.price - signal.stop_loss)
        dollar_risk_per_contract = price_risk * point_value
        
        if dollar_risk_per_contract == 0:
            return 1
        
        # Calculate max dollar risk for this trade
        max_dollar_risk = account_value * risk_per_trade
        
        # Calculate position size
        position_size = int(max_dollar_risk / dollar_risk_per_contract)
        
        # Apply limits
        position_size = max(1, min(position_size, max_contracts))
        
        return position_size
    
    def on_fill(self, signal: TradeSignal, fill_price: float, fill_time: datetime):
        """Handle order fill"""
        super().on_fill(signal, fill_price, fill_time)
        
        if signal.signal in [Signal.LONG, Signal.SHORT]:
            self.bars_in_position = 0
    
    def on_exit(self, exit_price: float, exit_time: datetime, reason: str):
        """Handle position exit"""
        super().on_exit(exit_price, exit_time, reason)
        self.bars_in_position = 0


# Example usage and testing
if __name__ == "__main__":
    import sys
    sys.path.insert(0, '..')
    
    # Create sample data
    np.random.seed(42)
    n_bars = 500
    dates = pd.date_range(start='2024-01-01', periods=n_bars, freq='5min')
    
    # Generate trending price data
    trend = np.cumsum(np.random.randn(n_bars) * 0.5 + 0.02)  # Slight upward bias
    noise = np.random.randn(n_bars) * 0.3
    close = 5000 + trend + noise
    
    high = close + np.abs(np.random.randn(n_bars) * 0.5)
    low = close - np.abs(np.random.randn(n_bars) * 0.5)
    volume = np.random.randint(1000, 10000, n_bars)
    
    df = pd.DataFrame({
        'open': np.roll(close, 1),
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)
    df['open'].iloc[0] = df['close'].iloc[0]
    
    # Create strategy
    strategy = TrendFollowingStrategy(
        name="TestTrendStrategy",
        params={'adx_threshold': 20.0}  # Lower threshold for test
    )
    
    # Prepare data with indicators
    df = strategy.prepare_data(df)
    
    print("=== Trend Following Strategy Test ===")
    print(f"Data shape: {df.shape}")
    print(f"Date range: {df.index[0]} to {df.index[-1]}")
    
    # Run through data
    signals_generated = []
    for i in range(250, len(df)):  # Start after warmup period
        signal = strategy.update(df, i)
        if signal:
            signals_generated.append(signal)
            print(f"\n{signal}")
            
            # Simulate fill
            if signal.signal in [Signal.LONG, Signal.SHORT]:
                strategy.on_fill(signal, signal.price, df.index[i])
            elif signal.signal == Signal.FLAT and strategy.position:
                strategy.on_exit(signal.price, df.index[i], signal.reason)
    
    print(f"\n=== Summary ===")
    print(f"Total signals: {len(signals_generated)}")
    print(f"Completed trades: {len(strategy.trades)}")
    
    if strategy.trades:
        print("\n=== Trade History ===")
        for trade in strategy.trades[:5]:  # Show first 5 trades
            pnl = (trade['exit_price'] - trade['entry_price']) * \
                  (1 if trade['direction'] == 'LONG' else -1)
            print(f"  {trade['direction']}: Entry={trade['entry_price']:.2f}, "
                  f"Exit={trade['exit_price']:.2f}, P/L={pnl:.2f}, "
                  f"Reason={trade['reason']}")
