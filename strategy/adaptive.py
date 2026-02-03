"""
Adaptive Multi-Pattern Strategy

An ensemble strategy that detects the current market regime and applies
the optimal sub-strategy. Combines:

1. Regime Detection (ADX + Bollinger Bandwidth + Hurst Exponent approximation)
   - Trending regime -> Trend Following signals
   - Ranging regime -> Mean Reversion signals
   - Breakout regime -> Breakout signals

2. Multi-Pattern Recognition:
   - Candlestick patterns (engulfing, pin bars, inside bars, doji)
   - Support/Resistance levels (pivot points, recent highs/lows)
   - MACD divergence detection
   - Volume profile analysis
   - Supertrend confirmation

3. Ensemble Scoring:
   - Each pattern/indicator contributes weighted score
   - Only trades above confidence threshold
   - Dynamic threshold based on regime

Based on:
- Larry Connors' RSI(2) mean reversion
- Richard Dennis' Turtle Trading breakout
- Alexander Elder's Triple Screen
- John Ehlers' adaptive indicators

Designed for prop firm compliance (MFFU):
- Max 1% risk per trade
- Trailing drawdown awareness
- Consistency-focused position sizing
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

from .base import BaseStrategy, TradeSignal, Signal, OrderType, Position
from .indicators import Indicators


class MarketRegime(Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    BREAKOUT = "breakout"
    VOLATILE = "volatile"


class AdaptiveStrategy(BaseStrategy):
    """
    Adaptive Multi-Pattern Ensemble Strategy

    Detects market regime and applies the best approach for current conditions.
    Uses weighted scoring across multiple pattern recognition systems.
    """

    DEFAULT_PARAMS = {
        # Regime detection
        'adx_period': 14,
        'adx_trend_threshold': 25.0,
        'adx_strong_trend': 35.0,
        'bb_squeeze_threshold': 1.5,

        # EMA settings
        'fast_ema': 8,
        'slow_ema': 21,
        'trend_ema': 50,

        # RSI settings (Connors RSI-2 style for mean reversion)
        'rsi_period': 14,
        'rsi_short_period': 2,  # Connors RSI(2)
        'rsi_overbought': 70.0,
        'rsi_oversold': 30.0,
        'connors_rsi_ob': 90.0,  # More extreme for RSI(2)
        'connors_rsi_os': 10.0,

        # Supertrend
        'supertrend_period': 10,
        'supertrend_mult': 3.0,

        # ATR / risk
        'atr_period': 14,
        'stop_loss_atr_mult': 1.8,
        'take_profit_atr_mult': 2.5,
        'trailing_stop_atr_mult': 1.5,

        # Donchian
        'donchian_period': 20,

        # Pattern recognition
        'pin_bar_ratio': 2.5,  # Body to wick ratio for pin bars
        'engulfing_min_body': 0.6,  # Minimum body-to-range ratio

        # Scoring thresholds
        'entry_threshold': 65,  # Minimum score to enter
        'strong_entry_threshold': 80,  # Score for larger position

        # Position management
        'max_hold_bars': 36,
        'min_bars_between_trades': 2,
        'max_daily_trades': 6,
        'use_trailing_stop': True,

        # Divergence detection
        'divergence_lookback': 14,

        # Regime weights (how much to trust each regime's signals)
        'trend_weight': 1.0,
        'reversion_weight': 1.0,
        'breakout_weight': 0.9,
    }

    def __init__(self, name: str = "Adaptive", params: Dict[str, Any] = None):
        merged_params = self.DEFAULT_PARAMS.copy()
        if params:
            merged_params.update(params)
        super().__init__(name=name, params=merged_params)
        self.bars_since_last_trade = 0
        self.bars_in_position = 0
        self.current_regime = MarketRegime.RANGING
        self.daily_trades = 0
        self.last_date = None

    def on_init(self):
        self.bars_since_last_trade = self.params['min_bars_between_trades']
        self.bars_in_position = 0
        self.daily_trades = 0
        self.last_date = None

    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()

        # --- Core indicators ---
        df['ema_fast'] = Indicators.ema(df['close'], self.params['fast_ema'])
        df['ema_slow'] = Indicators.ema(df['close'], self.params['slow_ema'])
        df['ema_trend'] = Indicators.ema(df['close'], self.params['trend_ema'])

        # ADX for trend strength
        adx_data = Indicators.adx(
            df['high'], df['low'], df['close'], self.params['adx_period']
        )
        df['adx'] = adx_data['adx']
        df['plus_di'] = adx_data['plus_di']
        df['minus_di'] = adx_data['minus_di']

        # RSI standard and short
        df['rsi'] = Indicators.rsi(df['close'], self.params['rsi_period'])
        df['rsi2'] = Indicators.rsi(df['close'], self.params['rsi_short_period'])

        # ATR
        df['atr'] = Indicators.atr(
            df['high'], df['low'], df['close'], self.params['atr_period']
        )

        # MACD
        macd_data = Indicators.macd(df['close'])
        df['macd'] = macd_data['macd']
        df['macd_signal'] = macd_data['signal']
        df['macd_hist'] = macd_data['histogram']

        # Bollinger Bands
        bb = Indicators.bollinger_bands(df['close'], 20, 2.0)
        df['bb_upper'] = bb['upper']
        df['bb_middle'] = bb['middle']
        df['bb_lower'] = bb['lower']
        df['bb_bandwidth'] = bb['bandwidth']
        df['bb_pct_b'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

        # Keltner for squeeze
        keltner = Indicators.keltner_channels(
            df['high'], df['low'], df['close'], 20, 14, 1.5
        )
        df['squeeze'] = (df['bb_lower'] > keltner['lower']) & \
                        (df['bb_upper'] < keltner['upper'])

        # Donchian Channels
        donchian = Indicators.donchian_channels(
            df['high'], df['low'], self.params['donchian_period']
        )
        df['donchian_upper'] = donchian['upper']
        df['donchian_lower'] = donchian['lower']
        df['donchian_middle'] = donchian['middle']

        # Supertrend
        st = Indicators.supertrend(
            df['high'], df['low'], df['close'],
            self.params['supertrend_period'], self.params['supertrend_mult']
        )
        df['supertrend'] = st['supertrend']
        df['st_direction'] = st['direction']

        # Stochastic
        stoch = Indicators.stochastic(df['high'], df['low'], df['close'], 14, 3)
        df['stoch_k'] = stoch['k']
        df['stoch_d'] = stoch['d']

        # Volume analysis
        if 'volume' in df.columns:
            df['volume_ratio'] = Indicators.volume_ratio(df['volume'], 20)
            df['obv'] = Indicators.obv(df['close'], df['volume'])
        else:
            df['volume_ratio'] = 1.0

        # --- Candlestick pattern detection ---
        body = abs(df['close'] - df['open'])
        upper_wick = df['high'] - df[['close', 'open']].max(axis=1)
        lower_wick = df[['close', 'open']].min(axis=1) - df['low']
        total_range = df['high'] - df['low']
        total_range = total_range.replace(0, np.nan)

        # Bullish engulfing
        df['bullish_engulfing'] = (
            (df['close'] > df['open']) &  # Current is green
            (df['close'].shift(1) < df['open'].shift(1)) &  # Previous is red
            (df['close'] > df['open'].shift(1)) &  # Current close > prev open
            (df['open'] < df['close'].shift(1)) &  # Current open < prev close
            (body / total_range > self.params['engulfing_min_body'])
        )

        # Bearish engulfing
        df['bearish_engulfing'] = (
            (df['close'] < df['open']) &
            (df['close'].shift(1) > df['open'].shift(1)) &
            (df['close'] < df['open'].shift(1)) &
            (df['open'] > df['close'].shift(1)) &
            (body / total_range > self.params['engulfing_min_body'])
        )

        # Bullish pin bar (hammer) - long lower wick, small body at top
        df['bullish_pin'] = (
            (lower_wick > body * self.params['pin_bar_ratio']) &
            (upper_wick < body) &
            (body > 0)
        )

        # Bearish pin bar (shooting star) - long upper wick, small body at bottom
        df['bearish_pin'] = (
            (upper_wick > body * self.params['pin_bar_ratio']) &
            (lower_wick < body) &
            (body > 0)
        )

        # Inside bar
        df['inside_bar'] = (
            (df['high'] < df['high'].shift(1)) &
            (df['low'] > df['low'].shift(1))
        )

        # Doji (very small body relative to range)
        df['doji'] = body / total_range < 0.1

        # --- MACD Divergence ---
        df['bullish_div'] = False
        df['bearish_div'] = False
        lookback = self.params['divergence_lookback']
        for i in range(lookback, len(df)):
            # Bullish divergence: price lower low, MACD higher low
            if (df['close'].iloc[i] < df['close'].iloc[i-lookback:i].min() and
                df['macd_hist'].iloc[i] > df['macd_hist'].iloc[i-lookback:i].min()):
                df.iloc[i, df.columns.get_loc('bullish_div')] = True
            # Bearish divergence: price higher high, MACD lower high
            if (df['close'].iloc[i] > df['close'].iloc[i-lookback:i].max() and
                df['macd_hist'].iloc[i] < df['macd_hist'].iloc[i-lookback:i].max()):
                df.iloc[i, df.columns.get_loc('bearish_div')] = True

        return df

    def _detect_regime(self, data: pd.DataFrame, idx: int) -> MarketRegime:
        """Detect current market regime"""
        adx = data['adx'].iloc[idx]
        bb_bandwidth = data['bb_bandwidth'].iloc[idx]
        squeeze = data['squeeze'].iloc[idx]
        plus_di = data['plus_di'].iloc[idx]
        minus_di = data['minus_di'].iloc[idx]

        if pd.isna(adx) or pd.isna(bb_bandwidth):
            return MarketRegime.RANGING

        # Check for squeeze (about to breakout)
        if squeeze:
            return MarketRegime.BREAKOUT

        # Strong trend
        if adx > self.params['adx_strong_trend']:
            if plus_di > minus_di:
                return MarketRegime.TRENDING_UP
            else:
                return MarketRegime.TRENDING_DOWN

        # Moderate trend
        if adx > self.params['adx_trend_threshold']:
            if plus_di > minus_di:
                return MarketRegime.TRENDING_UP
            else:
                return MarketRegime.TRENDING_DOWN

        # High volatility but no trend
        if bb_bandwidth > 4.0:
            return MarketRegime.VOLATILE

        return MarketRegime.RANGING

    def _score_trend_signal(self, data: pd.DataFrame, idx: int,
                            direction: str) -> float:
        """Score trend-following signal quality (0-100)"""
        score = 0
        close = data['close'].iloc[idx]

        adx = data['adx'].iloc[idx]
        ema_fast = data['ema_fast'].iloc[idx]
        ema_slow = data['ema_slow'].iloc[idx]
        ema_trend = data['ema_trend'].iloc[idx]
        st_dir = data['st_direction'].iloc[idx]
        macd_hist = data['macd_hist'].iloc[idx]

        if pd.isna(adx):
            return 0

        if direction == 'long':
            # EMA alignment (0-20)
            if close > ema_trend and ema_fast > ema_slow:
                score += 20
            elif ema_fast > ema_slow:
                score += 10

            # ADX strength (0-20)
            if adx > self.params['adx_strong_trend']:
                score += 20
            elif adx > self.params['adx_trend_threshold']:
                score += 12

            # Supertrend confirmation (0-15)
            if st_dir == 1:
                score += 15

            # MACD positive (0-15)
            if not pd.isna(macd_hist) and macd_hist > 0:
                score += 15
            elif not pd.isna(macd_hist) and idx > 0:
                prev_hist = data['macd_hist'].iloc[idx-1]
                if not pd.isna(prev_hist) and macd_hist > prev_hist:
                    score += 8  # Histogram turning up

            # Pullback to EMA zone (0-15) - better entry
            atr = data['atr'].iloc[idx]
            if not pd.isna(atr) and atr > 0:
                dist = (close - ema_fast) / atr
                if -0.5 <= dist <= 1.0:
                    score += 15  # Near EMA
                elif dist <= 2.0:
                    score += 8

            # Candlestick confirmation (0-15)
            if data['bullish_engulfing'].iloc[idx]:
                score += 15
            elif data['bullish_pin'].iloc[idx]:
                score += 12
            elif idx > 0 and data['inside_bar'].iloc[idx-1]:
                score += 8

        else:  # short
            if close < ema_trend and ema_fast < ema_slow:
                score += 20
            elif ema_fast < ema_slow:
                score += 10

            if adx > self.params['adx_strong_trend']:
                score += 20
            elif adx > self.params['adx_trend_threshold']:
                score += 12

            if st_dir == -1:
                score += 15

            if not pd.isna(macd_hist) and macd_hist < 0:
                score += 15
            elif not pd.isna(macd_hist) and idx > 0:
                prev_hist = data['macd_hist'].iloc[idx-1]
                if not pd.isna(prev_hist) and macd_hist < prev_hist:
                    score += 8

            atr = data['atr'].iloc[idx]
            if not pd.isna(atr) and atr > 0:
                dist = (ema_fast - close) / atr
                if -0.5 <= dist <= 1.0:
                    score += 15
                elif dist <= 2.0:
                    score += 8

            if data['bearish_engulfing'].iloc[idx]:
                score += 15
            elif data['bearish_pin'].iloc[idx]:
                score += 12
            elif idx > 0 and data['inside_bar'].iloc[idx-1]:
                score += 8

        return score * self.params['trend_weight']

    def _score_reversion_signal(self, data: pd.DataFrame, idx: int,
                                direction: str) -> float:
        """Score mean-reversion signal quality (0-100)"""
        score = 0

        rsi = data['rsi'].iloc[idx]
        rsi2 = data['rsi2'].iloc[idx]
        bb_pct_b = data['bb_pct_b'].iloc[idx]
        stoch_k = data['stoch_k'].iloc[idx]

        if pd.isna(rsi) or pd.isna(bb_pct_b):
            return 0

        if direction == 'long':
            # Bollinger %B extreme (0-25)
            if bb_pct_b < 0:
                score += 25
            elif bb_pct_b < 0.1:
                score += 20
            elif bb_pct_b < 0.2:
                score += 12

            # RSI oversold (0-20)
            if rsi < 25:
                score += 20
            elif rsi < self.params['rsi_oversold']:
                score += 15
            elif rsi < 40:
                score += 5

            # Connors RSI(2) extreme (0-20)
            if not pd.isna(rsi2):
                if rsi2 < self.params['connors_rsi_os']:
                    score += 20
                elif rsi2 < 20:
                    score += 12

            # Stochastic oversold (0-15)
            if not pd.isna(stoch_k) and stoch_k < 20:
                score += 15
            elif not pd.isna(stoch_k) and stoch_k < 30:
                score += 8

            # Bullish divergence bonus (0-20)
            if data['bullish_div'].iloc[idx]:
                score += 20

        else:  # short
            if bb_pct_b > 1.0:
                score += 25
            elif bb_pct_b > 0.9:
                score += 20
            elif bb_pct_b > 0.8:
                score += 12

            if rsi > 75:
                score += 20
            elif rsi > self.params['rsi_overbought']:
                score += 15
            elif rsi > 60:
                score += 5

            if not pd.isna(rsi2):
                if rsi2 > self.params['connors_rsi_ob']:
                    score += 20
                elif rsi2 > 80:
                    score += 12

            if not pd.isna(stoch_k) and stoch_k > 80:
                score += 15
            elif not pd.isna(stoch_k) and stoch_k > 70:
                score += 8

            if data['bearish_div'].iloc[idx]:
                score += 20

        return score * self.params['reversion_weight']

    def _score_breakout_signal(self, data: pd.DataFrame, idx: int,
                               direction: str) -> float:
        """Score breakout signal quality (0-100)"""
        score = 0

        close = data['close'].iloc[idx]
        donchian_upper = data['donchian_upper'].iloc[idx]
        donchian_lower = data['donchian_lower'].iloc[idx]
        volume_ratio = data['volume_ratio'].iloc[idx]
        squeeze = data['squeeze'].iloc[idx]
        atr = data['atr'].iloc[idx]

        if pd.isna(donchian_upper) or pd.isna(donchian_lower):
            return 0

        if direction == 'long':
            # Breaking upper channel (0-30)
            if close > donchian_upper:
                score += 30
            elif data['high'].iloc[idx] > donchian_upper:
                score += 15

            # Volume confirmation (0-25)
            if not pd.isna(volume_ratio):
                if volume_ratio > 2.0:
                    score += 25
                elif volume_ratio > 1.5:
                    score += 18
                elif volume_ratio > 1.2:
                    score += 10

            # Squeeze release (0-25)
            if idx > 0 and data['squeeze'].iloc[idx-1] and not squeeze:
                score += 25
            elif squeeze:
                score += 10  # Still in squeeze, building energy

            # ATR expansion (0-20)
            if idx > 5 and not pd.isna(atr):
                prev_atr = data['atr'].iloc[idx-5]
                if not pd.isna(prev_atr) and atr > prev_atr * 1.2:
                    score += 20
                elif not pd.isna(prev_atr) and atr > prev_atr:
                    score += 10

        else:  # short
            if close < donchian_lower:
                score += 30
            elif data['low'].iloc[idx] < donchian_lower:
                score += 15

            if not pd.isna(volume_ratio):
                if volume_ratio > 2.0:
                    score += 25
                elif volume_ratio > 1.5:
                    score += 18
                elif volume_ratio > 1.2:
                    score += 10

            if idx > 0 and data['squeeze'].iloc[idx-1] and not squeeze:
                score += 25
            elif squeeze:
                score += 10

            if idx > 5 and not pd.isna(atr):
                prev_atr = data['atr'].iloc[idx-5]
                if not pd.isna(prev_atr) and atr > prev_atr * 1.2:
                    score += 20
                elif not pd.isna(prev_atr) and atr > prev_atr:
                    score += 10

        return score * self.params['breakout_weight']

    def generate_signal(
        self, data: pd.DataFrame, current_idx: int
    ) -> Optional[TradeSignal]:
        if current_idx < max(self.params['trend_ema'],
                             self.params['donchian_period'],
                             self.params['divergence_lookback']) + 5:
            return None

        required_cols = ['adx', 'ema_fast', 'rsi', 'bb_pct_b', 'donchian_upper',
                         'supertrend', 'bullish_engulfing', 'bullish_div']
        if not all(col in data.columns for col in required_cols):
            data = self.prepare_data(data)

        current_time = data.index[current_idx]
        close = data['close'].iloc[current_idx]
        atr = data['atr'].iloc[current_idx]

        if pd.isna(atr) or atr == 0:
            return None

        # Daily trade limit
        current_date = current_time.date() if hasattr(current_time, 'date') else None
        if current_date and current_date != self.last_date:
            self.last_date = current_date
            self.daily_trades = 0
        if self.daily_trades >= self.params['max_daily_trades']:
            return None

        self.bars_since_last_trade += 1

        # Position management
        if self.position:
            self.bars_in_position += 1

            if self.bars_in_position >= self.params['max_hold_bars']:
                return TradeSignal(
                    timestamp=current_time, signal=Signal.FLAT,
                    price=close, reason="max_hold_time"
                )

            # Exit on regime change (trend reversal)
            regime = self._detect_regime(data, current_idx)
            if self.position.is_long and regime == MarketRegime.TRENDING_DOWN:
                return TradeSignal(
                    timestamp=current_time, signal=Signal.FLAT,
                    price=close, reason="regime_change_bearish"
                )
            elif self.position.is_short and regime == MarketRegime.TRENDING_UP:
                return TradeSignal(
                    timestamp=current_time, signal=Signal.FLAT,
                    price=close, reason="regime_change_bullish"
                )

            # Mean reversion target for ranging regime trades
            if hasattr(self, '_entry_regime') and self._entry_regime == MarketRegime.RANGING:
                bb_middle = data['bb_middle'].iloc[current_idx]
                if not pd.isna(bb_middle):
                    if self.position.is_long and close >= bb_middle:
                        return TradeSignal(
                            timestamp=current_time, signal=Signal.FLAT,
                            price=close, reason="mean_reversion_target"
                        )
                    elif self.position.is_short and close <= bb_middle:
                        return TradeSignal(
                            timestamp=current_time, signal=Signal.FLAT,
                            price=close, reason="mean_reversion_target"
                        )

            return None

        # Cooldown
        if self.bars_since_last_trade < self.params['min_bars_between_trades']:
            return None

        # Detect regime
        regime = self._detect_regime(data, current_idx)
        self.current_regime = regime

        # Score signals for both directions
        long_score = 0
        short_score = 0

        if regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
            long_score = self._score_trend_signal(data, current_idx, 'long')
            short_score = self._score_trend_signal(data, current_idx, 'short')
        elif regime == MarketRegime.RANGING:
            long_score = self._score_reversion_signal(data, current_idx, 'long')
            short_score = self._score_reversion_signal(data, current_idx, 'short')
        elif regime == MarketRegime.BREAKOUT:
            long_score = self._score_breakout_signal(data, current_idx, 'long')
            short_score = self._score_breakout_signal(data, current_idx, 'short')
        elif regime == MarketRegime.VOLATILE:
            # In volatile regime, be more selective - use higher threshold
            long_trend = self._score_trend_signal(data, current_idx, 'long')
            long_rev = self._score_reversion_signal(data, current_idx, 'long')
            long_score = max(long_trend, long_rev) * 0.8  # Reduced confidence

            short_trend = self._score_trend_signal(data, current_idx, 'short')
            short_rev = self._score_reversion_signal(data, current_idx, 'short')
            short_score = max(short_trend, short_rev) * 0.8

        threshold = self.params['entry_threshold']
        best_direction = None
        best_score = 0

        if long_score >= threshold and long_score > short_score:
            best_direction = 'long'
            best_score = long_score
        elif short_score >= threshold and short_score > long_score:
            best_direction = 'short'
            best_score = short_score

        if best_direction is None:
            return None

        # Calculate stop/target based on regime
        if regime == MarketRegime.RANGING:
            sl_mult = self.params['stop_loss_atr_mult'] * 0.8  # Tighter for MR
            tp_mult = self.params['take_profit_atr_mult'] * 0.7
        elif regime == MarketRegime.BREAKOUT:
            sl_mult = self.params['stop_loss_atr_mult']
            tp_mult = self.params['take_profit_atr_mult'] * 1.3  # Let winners run
        else:
            sl_mult = self.params['stop_loss_atr_mult']
            tp_mult = self.params['take_profit_atr_mult']

        if best_direction == 'long':
            stop_loss = close - (atr * sl_mult)
            take_profit = close + (atr * tp_mult)
            signal_type = Signal.LONG
        else:
            stop_loss = close + (atr * sl_mult)
            take_profit = close - (atr * tp_mult)
            signal_type = Signal.SHORT

        # Risk/reward check
        risk = abs(close - stop_loss)
        reward = abs(take_profit - close)
        if risk <= 0 or reward / risk < 1.2:
            return None

        trailing = atr * self.params['trailing_stop_atr_mult'] if \
            self.params['use_trailing_stop'] else None

        self.bars_since_last_trade = 0
        self.bars_in_position = 0
        self.daily_trades += 1
        self._entry_regime = regime

        return TradeSignal(
            timestamp=current_time, signal=signal_type,
            price=close, stop_loss=stop_loss,
            take_profit=take_profit, trailing_stop=trailing,
            reason=f"adaptive_{regime.value}_{best_direction}",
            indicators={
                'score': best_score,
                'regime': regime.value,
                'long_score': long_score,
                'short_score': short_score,
                'adx': data['adx'].iloc[current_idx],
                'rsi': data['rsi'].iloc[current_idx],
                'atr': atr
            }
        )

    def on_fill(self, signal: TradeSignal, fill_price: float, fill_time: datetime):
        super().on_fill(signal, fill_price, fill_time)
        if signal.signal in [Signal.LONG, Signal.SHORT]:
            self.bars_in_position = 0

    def on_exit(self, exit_price: float, exit_time: datetime, reason: str):
        super().on_exit(exit_price, exit_time, reason)
        self.bars_in_position = 0
