"""
Bitcoin Price Data Fetcher
Fetches real-time and historical BTC/USDT price data from Binance public API.
No API key required for market data.
"""

import requests
import logging
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

BINANCE_BASE = "https://api.binance.com/api/v3"
BINANCE_ALT  = "https://api1.binance.com/api/v3"   # fallback


class BTCDataFetcher:
    """
    Fetches Bitcoin OHLCV data from Binance public REST API.
    Primary symbol: BTCUSDT
    """

    def __init__(self, symbol: str = "BTCUSDT"):
        self.symbol = symbol
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        self._last_price: Optional[float] = None
        self._last_fetch: float = 0.0

    # ──────────────────────────────────────────────
    # Live Price
    # ──────────────────────────────────────────────

    def get_current_price(self) -> Optional[float]:
        """Get latest BTC spot price (USD)."""
        now = time.time()
        # Cache for 2 seconds to avoid hammering the API
        if self._last_price and (now - self._last_fetch) < 2.0:
            return self._last_price

        for base in [BINANCE_BASE, BINANCE_ALT]:
            try:
                resp = self.session.get(
                    f"{base}/ticker/price",
                    params={"symbol": self.symbol},
                    timeout=5,
                )
                resp.raise_for_status()
                price = float(resp.json()["price"])
                self._last_price = price
                self._last_fetch = now
                return price
            except Exception as e:
                logger.warning("Price fetch from %s failed: %s", base, e)

        return self._last_price  # return cached if all fail

    def get_ticker_24h(self) -> Dict:
        """24-hour rolling stats: price change, volume, high, low."""
        try:
            resp = self.session.get(
                f"{BINANCE_BASE}/ticker/24hr",
                params={"symbol": self.symbol},
                timeout=5,
            )
            resp.raise_for_status()
            d = resp.json()
            return {
                "price": float(d["lastPrice"]),
                "change_pct": float(d["priceChangePercent"]),
                "high_24h": float(d["highPrice"]),
                "low_24h": float(d["lowPrice"]),
                "volume_24h": float(d["volume"]),
                "quote_volume_24h": float(d["quoteVolume"]),
            }
        except Exception as e:
            logger.error("24h ticker fetch failed: %s", e)
            return {}

    # ──────────────────────────────────────────────
    # Historical Klines (OHLCV)
    # ──────────────────────────────────────────────

    def get_klines(
        self,
        interval: str = "5m",
        limit: int = 200,
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV candles.

        Args:
            interval: Binance interval string: 1m, 3m, 5m, 15m, 1h, 4h, 1d
            limit:    Number of candles (max 1000)

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        for base in [BINANCE_BASE, BINANCE_ALT]:
            try:
                resp = self.session.get(
                    f"{base}/klines",
                    params={
                        "symbol": self.symbol,
                        "interval": interval,
                        "limit": limit,
                    },
                    timeout=10,
                )
                resp.raise_for_status()
                raw = resp.json()
                return self._parse_klines(raw)
            except Exception as e:
                logger.warning("Klines fetch from %s failed: %s", base, e)

        logger.error("All kline sources failed; returning empty DataFrame")
        return pd.DataFrame()

    @staticmethod
    def _parse_klines(raw: List) -> pd.DataFrame:
        """Convert raw Binance kline list to OHLCV DataFrame."""
        rows = []
        for k in raw:
            rows.append({
                "timestamp": pd.Timestamp(k[0], unit="ms", tz="UTC"),
                "open":   float(k[1]),
                "high":   float(k[2]),
                "low":    float(k[3]),
                "close":  float(k[4]),
                "volume": float(k[5]),
                "trades": int(k[8]),
                "taker_buy_vol": float(k[9]),
            })
        df = pd.DataFrame(rows).set_index("timestamp")
        return df

    def get_multi_tf_klines(self) -> Dict[str, pd.DataFrame]:
        """
        Fetch multiple timeframes for multi-TF analysis.
        Returns dict: {"1m": df, "5m": df, "15m": df, "1h": df}
        """
        result = {}
        configs = [
            ("1m",  100),
            ("5m",  200),
            ("15m", 100),
            ("1h",  50),
        ]
        for interval, limit in configs:
            df = self.get_klines(interval=interval, limit=limit)
            if not df.empty:
                result[interval] = df
        return result

    # ──────────────────────────────────────────────
    # Order Book Depth
    # ──────────────────────────────────────────────

    def get_order_book_pressure(self, depth: int = 20) -> Dict[str, float]:
        """
        Calculate buy/sell pressure from top order book levels.
        Returns bid_volume, ask_volume, and imbalance ratio.
        """
        try:
            resp = self.session.get(
                f"{BINANCE_BASE}/depth",
                params={"symbol": self.symbol, "limit": depth},
                timeout=5,
            )
            resp.raise_for_status()
            book = resp.json()
            bid_vol = sum(float(b[1]) for b in book["bids"])
            ask_vol = sum(float(a[1]) for a in book["asks"])
            imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol + 1e-9)
            return {
                "bid_volume": round(bid_vol, 4),
                "ask_volume": round(ask_vol, 4),
                "imbalance": round(imbalance, 4),  # >0 = buy pressure
            }
        except Exception as e:
            logger.error("Order book fetch failed: %s", e)
            return {"bid_volume": 0, "ask_volume": 0, "imbalance": 0}

    # ──────────────────────────────────────────────
    # Recent Trades Momentum
    # ──────────────────────────────────────────────

    def get_trade_momentum(self, limit: int = 500) -> Dict[str, float]:
        """
        Analyze recent trades for buy/sell momentum.
        Taker buys = market buy orders (bullish pressure).
        """
        try:
            resp = self.session.get(
                f"{BINANCE_BASE}/aggTrades",
                params={"symbol": self.symbol, "limit": limit},
                timeout=5,
            )
            resp.raise_for_status()
            trades = resp.json()
            buy_vol = sum(float(t["q"]) for t in trades if not t["m"])
            sell_vol = sum(float(t["q"]) for t in trades if t["m"])
            total = buy_vol + sell_vol
            buy_ratio = buy_vol / total if total > 0 else 0.5
            return {
                "buy_volume": round(buy_vol, 4),
                "sell_volume": round(sell_vol, 4),
                "buy_ratio": round(buy_ratio, 4),
                "momentum": round((buy_ratio - 0.5) * 2, 4),  # -1 to +1
            }
        except Exception as e:
            logger.error("Trade momentum fetch failed: %s", e)
            return {"buy_volume": 0, "sell_volume": 0, "buy_ratio": 0.5, "momentum": 0}
