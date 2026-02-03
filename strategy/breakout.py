"""
Breakout Strategy

Identifies and trades breakouts from consolidation ranges using:
- Donchian Channel breakouts (Richard Dennis Turtle Trading principles)
- Volume confirmation (breakout should have above-average volume)
- ATR expansion detection (volatility breakout)
- Inside bar breakout patterns
- Squeeze release detection (Bollinger inside Keltner)

Designed for prop firm compliance (MFFU):
- Trailing stops to lock in profits
- Conservative initial risk
- Quick exit on failed breakouts
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
from datetime import datetime

from .base import BaseStrategy, TradeSignal, Signal, OrderType, Position
from .indicators import Indicators


class BreakoutStrategy(BaseStrategy):
    """
    Breakout Strategy - trades range expansions

    Entry Conditions (Long):
    1. Price breaks above N-period high (Donchian upper)
    2. Volume > 1.5x average volume (confirmation)
    3. ATR expanding (current ATR > previous ATR)
    4. Not in overbought territory (RSI < 75)

    Entry Conditions (Short):
    1. Price breaks below N-period low (Donchian lower)
    2. Volume > 1.5x average volume
    3. ATR expanding
    4. Not in oversold territory (RSI > 25)

    Exit Conditions:
    - Trailing stop: 2x ATR
    - Opposite channel break
    - Failed breakout: price returns inside range within 3 bars
    """

    DEFAULT_PARAMS = {
        # Donchian Channel settings
        'donchian_period': 20,
        'donchian_exit_period': 10,  # Shorter period for exit channel

        # Volume settings
        'volume_period': 20,
        'volume_threshold': 1.3,  # Volume must be this multiple of average

        # ATR settings
        'atr_period': 14,
        'atr_expansion_periods': 5,  # Compare current ATR vs N periods ago
        'trailing_stop_atr_mult': 2.0,
        'stop_loss_atr_mult': 1.5,

        # RSI filter
        'rsi_period': 14,
        'rsi_max_long': 80.0,
        'rsi_min_short': 20.0,

        # Breakout confirmation
        'require_close_beyond': True,  # Require candle close beyond level
        'failed_breakout_bars': 3,  # Bars to wait for confirmation
        'min_bars_between_trades': 3,

        # Inside bar settings
        'use_inside_bar': True,

        # Position management
        'use_trailing_stop': True,
        'max_hold_bars': 48,

        # Squeeze detection
        'bb_period': 20,
        'bb_std': 2.0,
        'keltner_ema_period': 20,
        'keltner_atr_mult': 1.5,
    }

    def __init__(self, name: str = "Breakout", params: Dict[str, Any] = None):
        merged_params = self.DEFAULT_PARAMS.copy()
        if params:
            merged_params.update(params)
        super().__init__(name=name, params=merged_params)
        self.bars_since_last_trade = 0
        self.bars_in_position = 0
        self.breakout_bar = 0

    def on_init(self):
        self.bars_since_last_trade = self.params['min_bars_between_trades']
        self.bars_in_position = 0
        self.breakout_bar = 0

    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()

        # Donchian Channels
        donchian = Indicators.donchian_channels(
            df['high'], df['low'], self.params['donchian_period']
        )
        df['donchian_upper'] = donchian['upper']
        df['donchian_lower'] = donchian['lower']
        df['donchian_middle'] = donchian['middle']

        # Exit channel (shorter period)
        exit_donchian = Indicators.donchian_channels(
            df['high'], df['low'], self.params['donchian_exit_period']
        )
        df['exit_upper'] = exit_donchian['upper']
        df['exit_lower'] = exit_donchian['lower']

        # ATR
        df['atr'] = Indicators.atr(
            df['high'], df['low'], df['close'], self.params['atr_period']
        )

        # ATR expansion (current vs N bars ago)
        n = self.params['atr_expansion_periods']
        df['atr_expanding'] = df['atr'] > df['atr'].shift(n)

        # Volume analysis
        if 'volume' in df.columns:
            df['volume_sma'] = Indicators.volume_sma(
                df['volume'], self.params['volume_period']
            )
            df['volume_ratio'] = Indicators.volume_ratio(
                df['volume'], self.params['volume_period']
            )
        else:
            df['volume_ratio'] = 1.5  # Default to passing

        # RSI
        df['rsi'] = Indicators.rsi(df['close'], self.params['rsi_period'])

        # Bollinger Bands for squeeze
        bb = Indicators.bollinger_bands(
            df['close'], self.params['bb_period'], self.params['bb_std']
        )
        df['bb_upper'] = bb['upper']
        df['bb_lower'] = bb['lower']
        df['bb_bandwidth'] = bb['bandwidth']

        # Keltner for squeeze
        keltner = Indicators.keltner_channels(
            df['high'], df['low'], df['close'],
            self.params['keltner_ema_period'],
            self.params['atr_period'],
            self.params['keltner_atr_mult']
        )
        df['keltner_upper'] = keltner['upper']
        df['keltner_lower'] = keltner['lower']

        # Squeeze state
        df['in_squeeze'] = (df['bb_lower'] > df['keltner_lower']) & \
                           (df['bb_upper'] < df['keltner_upper'])
        df['squeeze_release'] = df['in_squeeze'].shift(1) & ~df['in_squeeze']

        # Inside bar detection
        df['inside_bar'] = (df['high'] < df['high'].shift(1)) & \
                           (df['low'] > df['low'].shift(1))

        # Range width (for measuring consolidation)
        df['range_width'] = (df['donchian_upper'] - df['donchian_lower']) / df['close'] * 100

        # EMA trend filter
        df['ema_fast'] = Indicators.ema(df['close'], 9)
        df['ema_slow'] = Indicators.ema(df['close'], 21)

        return df

    def _score_breakout(self, data: pd.DataFrame, idx: int, direction: str) -> float:
        """Score breakout quality (0-100)"""
        score = 0

        close = data['close'].iloc[idx]
        volume_ratio = data['volume_ratio'].iloc[idx]
        atr_expanding = data['atr_expanding'].iloc[idx]
        rsi = data['rsi'].iloc[idx]
        squeeze_release = data['squeeze_release'].iloc[idx]
        bb_bandwidth = data['bb_bandwidth'].iloc[idx]

        if direction == 'long':
            donchian = data['donchian_upper'].iloc[idx]
            prev_donchian = data['donchian_upper'].iloc[idx - 1] if idx > 0 else donchian
        else:
            donchian = data['donchian_lower'].iloc[idx]
            prev_donchian = data['donchian_lower'].iloc[idx - 1] if idx > 0 else donchian

        if pd.isna(donchian) or pd.isna(rsi):
            return 0

        # Price breaking channel (0-25 points)
        if direction == 'long':
            if close > donchian:
                score += 25
            elif data['high'].iloc[idx] > donchian:
                score += 15
        else:
            if close < donchian:
                score += 25
            elif data['low'].iloc[idx] < donchian:
                score += 15

        # Volume confirmation (0-25 points)
        if not pd.isna(volume_ratio):
            if volume_ratio >= self.params['volume_threshold'] * 1.5:
                score += 25
            elif volume_ratio >= self.params['volume_threshold']:
                score += 20
            elif volume_ratio >= 1.0:
                score += 10

        # ATR expansion (0-15 points)
        if atr_expanding:
            score += 15

        # Squeeze release bonus (0-15 points)
        if squeeze_release:
            score += 15
        elif not pd.isna(bb_bandwidth) and bb_bandwidth < 2.0:
            score += 5  # Low volatility, potential for expansion

        # Inside bar breakout bonus (0-10 points)
        if idx > 0 and data['inside_bar'].iloc[idx - 1]:
            score += 10

        # RSI filter (0-10 points, also acts as penalty)
        if direction == 'long':
            if rsi < 60:
                score += 10  # Room to run
            elif rsi > self.params['rsi_max_long']:
                score -= 15  # Already overbought, risky breakout
        else:
            if rsi > 40:
                score += 10
            elif rsi < self.params['rsi_min_short']:
                score -= 15

        return max(0, score)

    def generate_signal(
        self, data: pd.DataFrame, current_idx: int
    ) -> Optional[TradeSignal]:
        if current_idx < self.params['donchian_period'] + 5:
            return None

        required_cols = ['donchian_upper', 'donchian_lower', 'atr', 'rsi', 'volume_ratio']
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

            # Time exit
            if self.bars_in_position >= self.params['max_hold_bars']:
                return TradeSignal(
                    timestamp=current_time, signal=Signal.FLAT,
                    price=close, reason="max_hold_time"
                )

            # Failed breakout detection
            if self.bars_in_position <= self.params['failed_breakout_bars']:
                if self.position.is_long:
                    donchian_mid = data['donchian_middle'].iloc[current_idx]
                    if not pd.isna(donchian_mid) and close < donchian_mid:
                        return TradeSignal(
                            timestamp=current_time, signal=Signal.FLAT,
                            price=close, reason="failed_breakout"
                        )
                elif self.position.is_short:
                    donchian_mid = data['donchian_middle'].iloc[current_idx]
                    if not pd.isna(donchian_mid) and close > donchian_mid:
                        return TradeSignal(
                            timestamp=current_time, signal=Signal.FLAT,
                            price=close, reason="failed_breakout"
                        )

            # Exit channel signal (Turtle Trading exit)
            if self.position.is_long:
                exit_lower = data['exit_lower'].iloc[current_idx]
                if not pd.isna(exit_lower) and close < exit_lower:
                    return TradeSignal(
                        timestamp=current_time, signal=Signal.FLAT,
                        price=close, reason="exit_channel_break"
                    )
            elif self.position.is_short:
                exit_upper = data['exit_upper'].iloc[current_idx]
                if not pd.isna(exit_upper) and close > exit_upper:
                    return TradeSignal(
                        timestamp=current_time, signal=Signal.FLAT,
                        price=close, reason="exit_channel_break"
                    )

            return None

        # Cooldown check
        if self.bars_since_last_trade < self.params['min_bars_between_trades']:
            return None

        donchian_upper = data['donchian_upper'].iloc[current_idx]
        donchian_lower = data['donchian_lower'].iloc[current_idx]

        if pd.isna(donchian_upper) or pd.isna(donchian_lower):
            return None

        # Check for LONG breakout
        prev_close = data['close'].iloc[current_idx - 1] if current_idx > 0 else close
        prev_upper = data['donchian_upper'].iloc[current_idx - 1] if current_idx > 0 else donchian_upper

        if close > donchian_upper or (data['high'].iloc[current_idx] > prev_upper and close > prev_close):
            long_score = self._score_breakout(data, current_idx, 'long')

            if long_score >= 50:
                stop_loss = close - (atr * self.params['stop_loss_atr_mult'])
                take_profit = close + (atr * 3.0)  # 3x ATR target
                trailing = atr * self.params['trailing_stop_atr_mult'] if \
                    self.params['use_trailing_stop'] else None

                self.bars_since_last_trade = 0
                self.bars_in_position = 0

                return TradeSignal(
                    timestamp=current_time, signal=Signal.LONG,
                    price=close, stop_loss=stop_loss,
                    take_profit=take_profit, trailing_stop=trailing,
                    reason="breakout_long",
                    indicators={
                        'breakout_score': long_score,
                        'donchian_upper': donchian_upper,
                        'volume_ratio': data['volume_ratio'].iloc[current_idx],
                        'atr': atr
                    }
                )

        # Check for SHORT breakout
        prev_lower = data['donchian_lower'].iloc[current_idx - 1] if current_idx > 0 else donchian_lower

        if close < donchian_lower or (data['low'].iloc[current_idx] < prev_lower and close < prev_close):
            short_score = self._score_breakout(data, current_idx, 'short')

            if short_score >= 50:
                stop_loss = close + (atr * self.params['stop_loss_atr_mult'])
                take_profit = close - (atr * 3.0)
                trailing = atr * self.params['trailing_stop_atr_mult'] if \
                    self.params['use_trailing_stop'] else None

                self.bars_since_last_trade = 0
                self.bars_in_position = 0

                return TradeSignal(
                    timestamp=current_time, signal=Signal.SHORT,
                    price=close, stop_loss=stop_loss,
                    take_profit=take_profit, trailing_stop=trailing,
                    reason="breakout_short",
                    indicators={
                        'breakout_score': short_score,
                        'donchian_lower': donchian_lower,
                        'volume_ratio': data['volume_ratio'].iloc[current_idx],
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
