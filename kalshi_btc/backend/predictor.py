"""
Bitcoin 5-Minute Price Predictor
Multi-indicator technical analysis engine that generates directional signals
with confidence scores for use in Kalshi prediction market betting.

Prediction: Will BTC price be HIGHER or LOWER in the next 5 minutes?
Confidence: 0.0–1.0 (0.5 = no edge, 1.0 = maximum conviction)
"""

import logging
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PredictionSignal:
    direction: str          # "UP" | "DOWN" | "NEUTRAL"
    confidence: float       # 0.0 – 1.0
    predicted_change_pct: float
    current_price: float

    # Component scores (-1 = strong down, +1 = strong up)
    trend_score: float = 0.0
    momentum_score: float = 0.0
    volatility_score: float = 0.0
    volume_score: float = 0.0
    orderbook_score: float = 0.0
    trade_momentum_score: float = 0.0
    multi_tf_score: float = 0.0

    # Indicator values for display
    rsi: float = 50.0
    macd_hist: float = 0.0
    adx: float = 20.0
    bb_position: float = 0.5   # 0=at lower band, 1=at upper band
    ema_alignment: float = 0.0  # 1=all bullish, -1=all bearish
    atr_pct: float = 0.0        # ATR as % of price

    # Metadata
    signal_components: Dict[str, float] = field(default_factory=dict)
    reasoning: List[str] = field(default_factory=list)

    @property
    def bet_side(self) -> str:
        """Which Kalshi side to bet: 'yes' (price above) or 'no' (price below)"""
        return "yes" if self.direction == "UP" else "no"

    @property
    def kalshi_price(self) -> int:
        """Estimated fair Kalshi price in cents based on confidence"""
        base = 50
        edge = int((self.confidence - 0.5) * 100)
        if self.direction == "UP":
            return min(95, max(5, base + edge))
        else:
            return min(95, max(5, base + edge))

    def to_dict(self) -> dict:
        return {
            "direction": self.direction,
            "confidence": round(self.confidence, 4),
            "predicted_change_pct": round(self.predicted_change_pct, 4),
            "current_price": round(self.current_price, 2),
            "bet_side": self.bet_side,
            "kalshi_price": self.kalshi_price,
            "scores": {
                "trend": round(self.trend_score, 3),
                "momentum": round(self.momentum_score, 3),
                "volatility": round(self.volatility_score, 3),
                "volume": round(self.volume_score, 3),
                "orderbook": round(self.orderbook_score, 3),
                "trade_momentum": round(self.trade_momentum_score, 3),
                "multi_tf": round(self.multi_tf_score, 3),
            },
            "indicators": {
                "rsi": round(self.rsi, 2),
                "macd_histogram": round(self.macd_hist, 4),
                "adx": round(self.adx, 2),
                "bb_position": round(self.bb_position, 3),
                "ema_alignment": round(self.ema_alignment, 3),
                "atr_pct": round(self.atr_pct, 4),
            },
            "reasoning": self.reasoning,
        }


class BTCPredictor:
    """
    Multi-factor Bitcoin price predictor for 5-minute horizon.

    Combines 7 independent signal sources, each weighted by historical
    reliability on short-term BTC moves:

    1. Trend (EMA alignment + ADX)       — weight 0.20
    2. Momentum (RSI + MACD)             — weight 0.20
    3. Volatility regime (BB + ATR)      — weight 0.10
    4. Volume analysis                   — weight 0.15
    5. Order book imbalance              — weight 0.15
    6. Recent trade momentum             — weight 0.10
    7. Multi-timeframe confluence        — weight 0.10
    """

    WEIGHTS = {
        "trend":          0.20,
        "momentum":       0.20,
        "volatility":     0.10,
        "volume":         0.15,
        "orderbook":      0.15,
        "trade_momentum": 0.10,
        "multi_tf":       0.10,
    }

    # Minimum confidence to generate a non-NEUTRAL signal
    CONFIDENCE_THRESHOLD = 0.55

    def __init__(self):
        pass

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    def predict(
        self,
        df_5m: pd.DataFrame,
        orderbook: Optional[Dict] = None,
        trade_momentum: Optional[Dict] = None,
        df_1m: Optional[pd.DataFrame] = None,
        df_15m: Optional[pd.DataFrame] = None,
        df_1h: Optional[pd.DataFrame] = None,
    ) -> PredictionSignal:
        """
        Generate a 5-minute price direction prediction.

        Args:
            df_5m:           5-minute OHLCV DataFrame (index=UTC timestamp)
            orderbook:       {"bid_volume", "ask_volume", "imbalance"} dict
            trade_momentum:  {"buy_ratio", "momentum"} dict
            df_1m/15m/1h:    Optional additional timeframe DataFrames

        Returns:
            PredictionSignal with direction and confidence
        """
        if df_5m is None or len(df_5m) < 50:
            logger.warning("Not enough 5m data for prediction")
            return self._neutral(df_5m)

        df = self._compute_indicators(df_5m)
        current_price = float(df["close"].iloc[-1])

        # ── Score each factor ──────────────────────
        trend_score,     trend_reasons     = self._score_trend(df)
        momentum_score,  momentum_reasons  = self._score_momentum(df)
        vol_score,       vol_reasons       = self._score_volatility(df)
        volume_score,    volume_reasons    = self._score_volume(df)
        ob_score = 0.0;  ob_reasons = []
        tm_score = 0.0;  tm_reasons = []
        mtf_score = 0.0; mtf_reasons = []

        if orderbook:
            ob_score, ob_reasons = self._score_orderbook(orderbook)
        if trade_momentum:
            tm_score, tm_reasons = self._score_trade_momentum(trade_momentum)
        if df_1m is not None or df_15m is not None or df_1h is not None:
            mtf_score, mtf_reasons = self._score_multi_tf(df_1m, df_15m, df_1h)

        # ── Weighted aggregate ─────────────────────
        raw_score = (
            self.WEIGHTS["trend"]          * trend_score +
            self.WEIGHTS["momentum"]       * momentum_score +
            self.WEIGHTS["volatility"]     * vol_score +
            self.WEIGHTS["volume"]         * volume_score +
            self.WEIGHTS["orderbook"]      * ob_score +
            self.WEIGHTS["trade_momentum"] * tm_score +
            self.WEIGHTS["multi_tf"]       * mtf_score
        )

        # ── Convert to probability ─────────────────
        # Sigmoid-like mapping: raw_score ∈ [-1, 1] → confidence ∈ [0, 1]
        confidence = 0.5 + (raw_score * 0.5)
        confidence = float(np.clip(confidence, 0.01, 0.99))

        # ── Direction ─────────────────────────────
        if confidence >= self.CONFIDENCE_THRESHOLD:
            direction = "UP"
        elif confidence <= (1 - self.CONFIDENCE_THRESHOLD):
            direction = "DOWN"
            confidence = 1 - confidence  # flip so confidence always > 0.5
        else:
            direction = "NEUTRAL"

        # ── Predicted change (ATR-based) ──────────
        atr = float(df["atr"].iloc[-1])
        predicted_change_pct = (atr / current_price) * 100 * (raw_score / 2)

        # ── Build signal ──────────────────────────
        latest = df.iloc[-1]
        all_reasons = (
            trend_reasons + momentum_reasons + vol_reasons +
            volume_reasons + ob_reasons + tm_reasons + mtf_reasons
        )

        signal = PredictionSignal(
            direction=direction,
            confidence=round(confidence, 4),
            predicted_change_pct=round(predicted_change_pct, 4),
            current_price=round(current_price, 2),
            trend_score=round(trend_score, 3),
            momentum_score=round(momentum_score, 3),
            volatility_score=round(vol_score, 3),
            volume_score=round(volume_score, 3),
            orderbook_score=round(ob_score, 3),
            trade_momentum_score=round(tm_score, 3),
            multi_tf_score=round(mtf_score, 3),
            rsi=round(float(latest["rsi"]), 2),
            macd_hist=round(float(latest["macd_hist"]), 6),
            adx=round(float(latest["adx"]), 2),
            bb_position=round(float(latest["bb_pct_b"]), 3),
            ema_alignment=round(trend_score, 3),
            atr_pct=round((atr / current_price) * 100, 4),
            reasoning=all_reasons[:10],  # top 10 reasons
        )

        logger.info(
            "Prediction: %s (conf=%.2f, raw=%.3f) @ $%.2f",
            direction, confidence, raw_score, current_price
        )
        return signal

    # ──────────────────────────────────────────────
    # Indicator Computation
    # ──────────────────────────────────────────────

    @staticmethod
    def _compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Add all technical indicators to DataFrame."""
        d = df.copy()
        close = d["close"]
        high = d["high"]
        low = d["low"]
        volume = d["volume"]

        # EMAs
        for p in [8, 13, 21, 34, 55]:
            d[f"ema_{p}"] = close.ewm(span=p, adjust=False).mean()

        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        d["macd"]      = ema12 - ema26
        d["macd_sig"]  = d["macd"].ewm(span=9, adjust=False).mean()
        d["macd_hist"] = d["macd"] - d["macd_sig"]

        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta).clip(lower=0).rolling(14).mean()
        rs = gain / (loss + 1e-9)
        d["rsi"] = 100 - (100 / (1 + rs))

        # Bollinger Bands
        bb_mid   = close.rolling(20).mean()
        bb_std   = close.rolling(20).std()
        d["bb_upper"]  = bb_mid + 2 * bb_std
        d["bb_lower"]  = bb_mid - 2 * bb_std
        d["bb_mid"]    = bb_mid
        d["bb_pct_b"]  = (close - d["bb_lower"]) / (d["bb_upper"] - d["bb_lower"] + 1e-9)
        d["bb_width"]  = (d["bb_upper"] - d["bb_lower"]) / bb_mid

        # ATR
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low  - close.shift(1)).abs(),
        ], axis=1).max(axis=1)
        d["atr"] = tr.rolling(14).mean()

        # ADX
        up_move   = high - high.shift(1)
        down_move = low.shift(1) - low
        plus_dm  = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        plus_dm  = pd.Series(plus_dm, index=close.index)
        minus_dm = pd.Series(minus_dm, index=close.index)
        atr14 = d["atr"]
        plus_di  = 100 * plus_dm.rolling(14).mean()  / (atr14 + 1e-9)
        minus_di = 100 * minus_dm.rolling(14).mean() / (atr14 + 1e-9)
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9)
        d["adx"]      = dx.rolling(14).mean()
        d["plus_di"]  = plus_di
        d["minus_di"] = minus_di

        # Stochastic
        low14  = low.rolling(14).min()
        high14 = high.rolling(14).max()
        d["stoch_k"] = 100 * (close - low14) / (high14 - low14 + 1e-9)
        d["stoch_d"] = d["stoch_k"].rolling(3).mean()

        # Volume indicators
        d["vol_sma20"] = volume.rolling(20).mean()
        d["vol_ratio"] = volume / (d["vol_sma20"] + 1e-9)

        # OBV
        obv_dir = np.where(close > close.shift(1), 1, np.where(close < close.shift(1), -1, 0))
        d["obv"] = (volume * obv_dir).cumsum()
        d["obv_ema"] = d["obv"].ewm(span=10, adjust=False).mean()

        # Price momentum
        d["roc_3"]  = close.pct_change(3) * 100
        d["roc_10"] = close.pct_change(10) * 100

        return d

    # ──────────────────────────────────────────────
    # Scoring Functions
    # ──────────────────────────────────────────────

    def _score_trend(self, df: pd.DataFrame) -> Tuple[float, List[str]]:
        """
        EMA alignment + ADX trend strength.
        Returns score ∈ [-1, +1] and list of reasoning strings.
        """
        reasons = []
        scores = []
        row = df.iloc[-1]

        # EMA ribbon alignment (8 > 13 > 21 > 34 > 55 = fully bullish)
        emas = [row["ema_8"], row["ema_13"], row["ema_21"], row["ema_34"], row["ema_55"]]
        bull_count = sum(1 for i in range(len(emas)-1) if emas[i] > emas[i+1])
        bear_count = sum(1 for i in range(len(emas)-1) if emas[i] < emas[i+1])
        ema_score = (bull_count - bear_count) / (len(emas) - 1)  # -1 to +1
        scores.append(ema_score)

        if bull_count >= 3:
            reasons.append(f"EMA ribbon bullish ({bull_count}/4 aligned)")
        elif bear_count >= 3:
            reasons.append(f"EMA ribbon bearish ({bear_count}/4 aligned)")

        # Price vs EMA 21
        price = row["close"]
        if price > row["ema_21"]:
            scores.append(0.5)
            reasons.append("Price above EMA21 (bullish)")
        else:
            scores.append(-0.5)
            reasons.append("Price below EMA21 (bearish)")

        # ADX trend strength
        adx = row["adx"]
        if adx > 25:
            adx_weight = min(1.0, adx / 50)
            if row["plus_di"] > row["minus_di"]:
                scores.append(adx_weight)
                reasons.append(f"Strong uptrend ADX={adx:.1f}, +DI>{' -DI'}")
            else:
                scores.append(-adx_weight)
                reasons.append(f"Strong downtrend ADX={adx:.1f}")
        else:
            scores.append(0.0)  # weak/no trend

        # Recent candle momentum (last 3 candles direction)
        last3 = df["close"].iloc[-4:-1]
        last3_dir = (last3.iloc[-1] - last3.iloc[0]) / (abs(last3.iloc[0]) + 1e-9)
        scores.append(np.clip(last3_dir * 50, -1, 1))

        final = float(np.mean(scores))
        return float(np.clip(final, -1, 1)), reasons

    def _score_momentum(self, df: pd.DataFrame) -> Tuple[float, List[str]]:
        """RSI + MACD + Stochastic momentum analysis."""
        reasons = []
        scores = []
        row = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else row

        # RSI scoring
        rsi = row["rsi"]
        if rsi > 70:
            scores.append(-0.7)
            reasons.append(f"RSI overbought ({rsi:.1f}) — bearish reversal likely")
        elif rsi > 60:
            scores.append(0.4)
            reasons.append(f"RSI bullish ({rsi:.1f})")
        elif rsi < 30:
            scores.append(0.7)
            reasons.append(f"RSI oversold ({rsi:.1f}) — bullish reversal likely")
        elif rsi < 40:
            scores.append(-0.4)
            reasons.append(f"RSI bearish ({rsi:.1f})")
        else:
            scores.append((rsi - 50) / 50 * 0.5)

        # MACD histogram
        hist = row["macd_hist"]
        prev_hist = prev["macd_hist"]
        if hist > 0 and hist > prev_hist:
            scores.append(0.8)
            reasons.append("MACD histogram rising (bullish momentum)")
        elif hist > 0:
            scores.append(0.3)
        elif hist < 0 and hist < prev_hist:
            scores.append(-0.8)
            reasons.append("MACD histogram falling (bearish momentum)")
        elif hist < 0:
            scores.append(-0.3)
        else:
            scores.append(0.0)

        # MACD line vs signal
        if row["macd"] > row["macd_sig"] and prev["macd"] <= prev["macd_sig"]:
            scores.append(1.0)
            reasons.append("MACD bullish crossover")
        elif row["macd"] < row["macd_sig"] and prev["macd"] >= prev["macd_sig"]:
            scores.append(-1.0)
            reasons.append("MACD bearish crossover")
        elif row["macd"] > row["macd_sig"]:
            scores.append(0.3)
        else:
            scores.append(-0.3)

        # Stochastic
        k = row["stoch_k"]
        d = row["stoch_d"]
        prev_k = prev["stoch_k"]
        prev_d = prev["stoch_d"]
        if k > 80:
            scores.append(-0.5)
            reasons.append(f"Stoch overbought K={k:.0f}")
        elif k < 20:
            scores.append(0.5)
            reasons.append(f"Stoch oversold K={k:.0f}")
        elif k > d and prev_k <= prev_d:
            scores.append(0.6)
            reasons.append("Stoch bullish crossover")
        elif k < d and prev_k >= prev_d:
            scores.append(-0.6)
            reasons.append("Stoch bearish crossover")
        else:
            scores.append((k - 50) / 100)

        return float(np.clip(np.mean(scores), -1, 1)), reasons

    def _score_volatility(self, df: pd.DataFrame) -> Tuple[float, List[str]]:
        """
        Bollinger Bands position and ATR regime.
        High vol + BB touch = reversal signal; trending candles = continuation.
        """
        reasons = []
        scores = []
        row = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else row

        pct_b = row["bb_pct_b"]
        bb_width = row["bb_width"]

        # BB squeeze: low volatility precedes breakout
        avg_width = df["bb_width"].rolling(20).mean().iloc[-1]
        if bb_width < avg_width * 0.7:
            reasons.append("BB squeeze detected — breakout imminent")
            # In a squeeze, lean on trend for direction
            if row["close"] > row["bb_mid"]:
                scores.append(0.4)
            else:
                scores.append(-0.4)
        elif pct_b > 1.0:
            scores.append(-0.6)
            reasons.append("Price above BB upper — mean reversion risk")
        elif pct_b < 0.0:
            scores.append(0.6)
            reasons.append("Price below BB lower — bounce likely")
        elif pct_b > 0.8:
            scores.append(0.3)  # riding upper band (trend)
        elif pct_b < 0.2:
            scores.append(-0.3)
        else:
            scores.append((pct_b - 0.5) * 0.5)

        # ATR expansion (high volatility = stronger moves)
        atr_now = row["atr"]
        atr_avg = df["atr"].rolling(20).mean().iloc[-1]
        if atr_now > atr_avg * 1.5:
            reasons.append(f"ATR expanding ({atr_now/atr_avg:.1f}x avg) — volatile conditions")

        return float(np.clip(np.mean(scores) if scores else 0.0, -1, 1)), reasons

    def _score_volume(self, df: pd.DataFrame) -> Tuple[float, List[str]]:
        """Volume trend confirms price moves."""
        reasons = []
        scores = []
        row = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else row

        vol_ratio = row["vol_ratio"]
        price_change = row["close"] - prev["close"]
        obv_slope = (row["obv"] - df["obv"].iloc[-5]) / 5 if len(df) >= 5 else 0

        # High volume move confirmation
        if vol_ratio > 2.0:
            if price_change > 0:
                scores.append(0.8)
                reasons.append(f"High volume bullish bar (vol {vol_ratio:.1f}x avg)")
            else:
                scores.append(-0.8)
                reasons.append(f"High volume bearish bar (vol {vol_ratio:.1f}x avg)")
        elif vol_ratio > 1.5:
            scores.append(np.sign(price_change) * 0.4)
        else:
            scores.append(0.0)

        # OBV trend
        if obv_slope > 0:
            scores.append(0.4)
            reasons.append("OBV rising — accumulation")
        elif obv_slope < 0:
            scores.append(-0.4)
            reasons.append("OBV falling — distribution")

        # OBV vs EMA divergence
        obv_ema_diff = row["obv"] - row["obv_ema"]
        scores.append(np.clip(obv_ema_diff / (abs(row["obv_ema"]) + 1e-9) * 0.5, -0.5, 0.5))

        return float(np.clip(np.mean(scores), -1, 1)), reasons

    def _score_orderbook(self, ob: Dict) -> Tuple[float, List[str]]:
        """Order book bid/ask imbalance."""
        reasons = []
        imbalance = ob.get("imbalance", 0.0)

        if imbalance > 0.3:
            reasons.append(f"Strong buy-side book pressure (imbalance={imbalance:.2f})")
        elif imbalance < -0.3:
            reasons.append(f"Strong sell-side book pressure (imbalance={imbalance:.2f})")

        score = float(np.clip(imbalance * 1.5, -1, 1))
        return score, reasons

    def _score_trade_momentum(self, tm: Dict) -> Tuple[float, List[str]]:
        """Recent trade flow: taker buys vs sells."""
        reasons = []
        momentum = tm.get("momentum", 0.0)   # -1 to +1
        buy_ratio = tm.get("buy_ratio", 0.5)

        if buy_ratio > 0.60:
            reasons.append(f"Taker buy dominance ({buy_ratio*100:.0f}% buys) — bullish flow")
        elif buy_ratio < 0.40:
            reasons.append(f"Taker sell dominance ({(1-buy_ratio)*100:.0f}% sells) — bearish flow")

        score = float(np.clip(momentum, -1, 1))
        return score, reasons

    def _score_multi_tf(
        self,
        df_1m: Optional[pd.DataFrame],
        df_15m: Optional[pd.DataFrame],
        df_1h: Optional[pd.DataFrame],
    ) -> Tuple[float, List[str]]:
        """Higher timeframe trend confluence."""
        reasons = []
        scores = []

        def quick_trend(df: pd.DataFrame, label: str) -> float:
            if df is None or len(df) < 21:
                return 0.0
            close = df["close"]
            ema9  = close.ewm(span=9,  adjust=False).mean().iloc[-1]
            ema21 = close.ewm(span=21, adjust=False).mean().iloc[-1]
            price = close.iloc[-1]
            score = 0.0
            if price > ema9 > ema21:
                score = 1.0
                reasons.append(f"{label}: bullish structure")
            elif price < ema9 < ema21:
                score = -1.0
                reasons.append(f"{label}: bearish structure")
            elif price > ema21:
                score = 0.4
            else:
                score = -0.4
            return score

        s1m  = quick_trend(df_1m,  "1m TF")
        s15m = quick_trend(df_15m, "15m TF")
        s1h  = quick_trend(df_1h,  "1h TF")

        # Weight: 1m most relevant for 5m prediction, 1h least
        weights = [0.5, 0.35, 0.15]
        valid = [(s, w) for s, w in zip([s1m, s15m, s1h], weights) if s != 0.0]
        if not valid:
            return 0.0, reasons

        total_w = sum(w for _, w in valid)
        score = sum(s * w for s, w in valid) / total_w

        # Confluence bonus: all agree
        non_zero = [s for s, _ in valid]
        if len(non_zero) >= 2 and all(s > 0 for s in non_zero):
            score = min(1.0, score * 1.2)
            reasons.append("Multi-TF bullish confluence")
        elif len(non_zero) >= 2 and all(s < 0 for s in non_zero):
            score = max(-1.0, score * 1.2)
            reasons.append("Multi-TF bearish confluence")

        return float(np.clip(score, -1, 1)), reasons

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    @staticmethod
    def _neutral(df: Optional[pd.DataFrame]) -> PredictionSignal:
        price = float(df["close"].iloc[-1]) if df is not None and len(df) > 0 else 0.0
        return PredictionSignal(
            direction="NEUTRAL",
            confidence=0.5,
            predicted_change_pct=0.0,
            current_price=price,
        )
