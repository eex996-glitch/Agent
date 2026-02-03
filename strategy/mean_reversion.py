"""
Mean Reversion Strategy

Identifies overbought/oversold conditions and trades the reversion to the mean.
Uses Bollinger Bands, RSI extremes, and Stochastic oscillator for confirmation.

Based on well-known mean reversion principles:
- Bollinger Band %B for standard deviation extremes
- RSI for momentum exhaustion
- Stochastic for K/D crossover confirmation
- Keltner Channel squeeze detection for volatility compression

Designed for prop firm compliance (MFFU):
- Conservative position sizing
- Tight risk management
- Consistency-focused entries
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
from datetime import datetime

from .base import BaseStrategy, TradeSignal, Signal, OrderType, Position
from .indicators import Indicators


class MeanReversionStrategy(BaseStrategy):
    """
    Mean Reversion Strategy - trades pullbacks to the mean

    Entry Conditions (Long - Buy oversold):
    1. Price at or below lower Bollinger Band (%B < 0.1)
    2. RSI < 30 (oversold)
    3. Stochastic %K crosses above %D from oversold zone
    4. Price showing reversal candle (close > open after down move)

    Entry Conditions (Short - Sell overbought):
    1. Price at or above upper Bollinger Band (%B > 0.9)
    2. RSI > 70 (overbought)
    3. Stochastic %K crosses below %D from overbought zone
    4. Price showing reversal candle (close < open after up move)

    Exit Conditions:
    - Target: Middle Bollinger Band (SMA)
    - Stop: 1.5x ATR beyond entry
    - Time: Max 24 bars
    """

    DEFAULT_PARAMS = {
        # Bollinger Band settings
        'bb_period': 20,
        'bb_std': 2.0,
        'bb_entry_threshold': 0.1,  # %B threshold for entry

        # RSI settings
        'rsi_period': 14,
        'rsi_overbought': 70.0,
        'rsi_oversold': 30.0,

        # Stochastic settings
        'stoch_k_period': 14,
        'stoch_d_period': 3,
        'stoch_overbought': 80.0,
        'stoch_oversold': 20.0,

        # ATR settings
        'atr_period': 14,
        'stop_loss_atr_mult': 1.5,

        # Entry filters
        'min_bb_bandwidth': 1.0,  # Minimum bandwidth for volatility
        'require_reversal_candle': True,

        # Position management
        'use_middle_band_target': True,
        'max_hold_bars': 24,
        'min_bars_between_trades': 2,

        # Keltner squeeze detection
        'keltner_ema_period': 20,
        'keltner_atr_mult': 1.5,
    }

    def __init__(self, name: str = "MeanReversion", params: Dict[str, Any] = None):
        merged_params = self.DEFAULT_PARAMS.copy()
        if params:
            merged_params.update(params)
        super().__init__(name=name, params=merged_params)
        self.bars_since_last_trade = 0
        self.bars_in_position = 0

    def on_init(self):
        self.bars_since_last_trade = self.params['min_bars_between_trades']
        self.bars_in_position = 0

    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()

        # Bollinger Bands
        bb = Indicators.bollinger_bands(
            df['close'], self.params['bb_period'], self.params['bb_std']
        )
        df['bb_upper'] = bb['upper']
        df['bb_middle'] = bb['middle']
        df['bb_lower'] = bb['lower']
        df['bb_bandwidth'] = bb['bandwidth']

        # %B indicator
        df['bb_pct_b'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

        # RSI
        df['rsi'] = Indicators.rsi(df['close'], self.params['rsi_period'])

        # Stochastic
        stoch = Indicators.stochastic(
            df['high'], df['low'], df['close'],
            self.params['stoch_k_period'], self.params['stoch_d_period']
        )
        df['stoch_k'] = stoch['k']
        df['stoch_d'] = stoch['d']

        # ATR
        df['atr'] = Indicators.atr(
            df['high'], df['low'], df['close'], self.params['atr_period']
        )

        # Keltner Channels for squeeze detection
        keltner = Indicators.keltner_channels(
            df['high'], df['low'], df['close'],
            self.params['keltner_ema_period'],
            self.params['atr_period'],
            self.params['keltner_atr_mult']
        )
        df['keltner_upper'] = keltner['upper']
        df['keltner_lower'] = keltner['lower']

        # Squeeze: BB inside Keltner = low volatility, about to expand
        df['squeeze'] = (df['bb_lower'] > df['keltner_lower']) & \
                        (df['bb_upper'] < df['keltner_upper'])

        # Reversal candle detection
        df['bullish_reversal'] = (df['close'] > df['open']) & \
                                 (df['close'].shift(1) < df['open'].shift(1))
        df['bearish_reversal'] = (df['close'] < df['open']) & \
                                 (df['close'].shift(1) > df['open'].shift(1))

        # Williams %R
        df['williams_r'] = Indicators.williams_r(
            df['high'], df['low'], df['close'], 14
        )

        return df

    def _check_oversold(self, data: pd.DataFrame, idx: int) -> float:
        """Score oversold conditions (0-100)"""
        score = 0

        bb_pct_b = data['bb_pct_b'].iloc[idx]
        rsi = data['rsi'].iloc[idx]
        stoch_k = data['stoch_k'].iloc[idx]
        stoch_d = data['stoch_d'].iloc[idx]
        williams = data['williams_r'].iloc[idx]

        if pd.isna(bb_pct_b) or pd.isna(rsi):
            return 0

        # Bollinger %B score (0-30 points)
        if bb_pct_b < 0:
            score += 30
        elif bb_pct_b < self.params['bb_entry_threshold']:
            score += 25
        elif bb_pct_b < 0.2:
            score += 15

        # RSI score (0-25 points)
        if rsi < 20:
            score += 25
        elif rsi < self.params['rsi_oversold']:
            score += 20
        elif rsi < 40:
            score += 10

        # Stochastic score (0-25 points)
        if not pd.isna(stoch_k) and not pd.isna(stoch_d):
            if stoch_k < self.params['stoch_oversold']:
                score += 15
            # K crossing above D (bullish)
            if idx > 0:
                prev_k = data['stoch_k'].iloc[idx - 1]
                prev_d = data['stoch_d'].iloc[idx - 1]
                if not pd.isna(prev_k) and not pd.isna(prev_d):
                    if prev_k <= prev_d and stoch_k > stoch_d:
                        score += 10

        # Williams %R score (0-20 points)
        if not pd.isna(williams):
            if williams < -80:
                score += 20
            elif williams < -60:
                score += 10

        return score

    def _check_overbought(self, data: pd.DataFrame, idx: int) -> float:
        """Score overbought conditions (0-100)"""
        score = 0

        bb_pct_b = data['bb_pct_b'].iloc[idx]
        rsi = data['rsi'].iloc[idx]
        stoch_k = data['stoch_k'].iloc[idx]
        stoch_d = data['stoch_d'].iloc[idx]
        williams = data['williams_r'].iloc[idx]

        if pd.isna(bb_pct_b) or pd.isna(rsi):
            return 0

        # Bollinger %B score (0-30 points)
        if bb_pct_b > 1.0:
            score += 30
        elif bb_pct_b > (1 - self.params['bb_entry_threshold']):
            score += 25
        elif bb_pct_b > 0.8:
            score += 15

        # RSI score (0-25 points)
        if rsi > 80:
            score += 25
        elif rsi > self.params['rsi_overbought']:
            score += 20
        elif rsi > 60:
            score += 10

        # Stochastic score (0-25 points)
        if not pd.isna(stoch_k) and not pd.isna(stoch_d):
            if stoch_k > self.params['stoch_overbought']:
                score += 15
            # K crossing below D (bearish)
            if idx > 0:
                prev_k = data['stoch_k'].iloc[idx - 1]
                prev_d = data['stoch_d'].iloc[idx - 1]
                if not pd.isna(prev_k) and not pd.isna(prev_d):
                    if prev_k >= prev_d and stoch_k < stoch_d:
                        score += 10

        # Williams %R score (0-20 points)
        if not pd.isna(williams):
            if williams > -20:
                score += 20
            elif williams > -40:
                score += 10

        return score

    def generate_signal(
        self, data: pd.DataFrame, current_idx: int
    ) -> Optional[TradeSignal]:
        if current_idx < max(self.params['bb_period'], self.params['stoch_k_period']) + 5:
            return None

        required_cols = ['bb_upper', 'bb_pct_b', 'rsi', 'stoch_k', 'atr']
        if not all(col in data.columns for col in required_cols):
            data = self.prepare_data(data)

        current_time = data.index[current_idx]
        close = data['close'].iloc[current_idx]
        atr = data['atr'].iloc[current_idx]

        if pd.isna(atr) or atr == 0:
            return None

        self.bars_since_last_trade += 1

        # Position management
        if self.position:
            self.bars_in_position += 1

            # Time-based exit
            if self.bars_in_position >= self.params['max_hold_bars']:
                return TradeSignal(
                    timestamp=current_time, signal=Signal.FLAT,
                    price=close, reason="max_hold_time"
                )

            # Target: middle Bollinger Band
            if self.params['use_middle_band_target']:
                middle = data['bb_middle'].iloc[current_idx]
                if not pd.isna(middle):
                    if self.position.is_long and close >= middle:
                        return TradeSignal(
                            timestamp=current_time, signal=Signal.FLAT,
                            price=close, reason="target_middle_band"
                        )
                    elif self.position.is_short and close <= middle:
                        return TradeSignal(
                            timestamp=current_time, signal=Signal.FLAT,
                            price=close, reason="target_middle_band"
                        )

            return None

        # Cooldown check
        if self.bars_since_last_trade < self.params['min_bars_between_trades']:
            return None

        # Check for mean reversion opportunities
        oversold_score = self._check_oversold(data, current_idx)
        overbought_score = self._check_overbought(data, current_idx)

        # Need minimum score of 60 to enter
        min_score = 60

        # LONG entry (oversold reversion)
        if oversold_score >= min_score:
            # Optional reversal candle check
            if self.params['require_reversal_candle']:
                if not data['bullish_reversal'].iloc[current_idx]:
                    return None

            stop_loss = close - (atr * self.params['stop_loss_atr_mult'])
            middle_band = data['bb_middle'].iloc[current_idx]
            take_profit = middle_band if not pd.isna(middle_band) else close + (atr * 2)

            # Ensure positive risk/reward
            risk = close - stop_loss
            reward = take_profit - close
            if risk <= 0 or reward / risk < 1.0:
                return None

            self.bars_since_last_trade = 0
            self.bars_in_position = 0

            return TradeSignal(
                timestamp=current_time, signal=Signal.LONG,
                price=close, stop_loss=stop_loss, take_profit=take_profit,
                reason="mean_reversion_long",
                indicators={
                    'oversold_score': oversold_score,
                    'bb_pct_b': data['bb_pct_b'].iloc[current_idx],
                    'rsi': data['rsi'].iloc[current_idx],
                    'atr': atr
                }
            )

        # SHORT entry (overbought reversion)
        if overbought_score >= min_score:
            if self.params['require_reversal_candle']:
                if not data['bearish_reversal'].iloc[current_idx]:
                    return None

            stop_loss = close + (atr * self.params['stop_loss_atr_mult'])
            middle_band = data['bb_middle'].iloc[current_idx]
            take_profit = middle_band if not pd.isna(middle_band) else close - (atr * 2)

            risk = stop_loss - close
            reward = close - take_profit
            if risk <= 0 or reward / risk < 1.0:
                return None

            self.bars_since_last_trade = 0
            self.bars_in_position = 0

            return TradeSignal(
                timestamp=current_time, signal=Signal.SHORT,
                price=close, stop_loss=stop_loss, take_profit=take_profit,
                reason="mean_reversion_short",
                indicators={
                    'overbought_score': overbought_score,
                    'bb_pct_b': data['bb_pct_b'].iloc[current_idx],
                    'rsi': data['rsi'].iloc[current_idx],
                    'atr': atr
                }
            )

        return None

    def on_fill(self, signal: TradeSignal, fill_price: float, fill_time: datetime):
        super().on_fill(signal, fill_price, fill_time)
        if signal.signal in [Signal.LONG, Signal.SHORT]:
            self.bars_in_position = 0

    def on_exit(self, exit_price: float, exit_time: datetime, reason: str):
        super().on_exit(exit_price, exit_time, reason)
        self.bars_in_position = 0
