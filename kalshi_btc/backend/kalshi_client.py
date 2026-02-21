"""
Kalshi API Client
Handles authentication, market discovery, and order placement
for Kalshi prediction markets.

Kalshi API v2: https://trading-api.kalshi.com/trade-api/v2
"""

import requests
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

KALSHI_BASE_URL = "https://trading-api.kalshi.com/trade-api/v2"
KALSHI_DEMO_URL = "https://demo-api.kalshi.co/trade-api/v2"


@dataclass
class KalshiMarket:
    ticker: str
    title: str
    status: str
    yes_bid: float
    yes_ask: float
    no_bid: float
    no_ask: float
    close_time: str
    expected_expiration_time: str
    cap_strike: Optional[float] = None
    floor_strike: Optional[float] = None
    result: Optional[str] = None
    volume: int = 0
    open_interest: int = 0
    series_ticker: str = ""

    @property
    def mid_price(self) -> float:
        """Yes mid price (0-100 cents)"""
        if self.yes_bid and self.yes_ask:
            return (self.yes_bid + self.yes_ask) / 2
        return self.yes_ask or self.yes_bid or 50.0

    @property
    def implied_probability(self) -> float:
        """Implied probability from market price (0-1)"""
        return self.mid_price / 100.0


@dataclass
class KalshiOrder:
    order_id: str
    ticker: str
    side: str         # "yes" or "no"
    action: str       # "buy" or "sell"
    count: int        # number of contracts
    price: int        # price in cents (1-99)
    status: str       # "resting", "executed", "canceled"
    created_time: str = ""
    expiration_time: str = ""


@dataclass
class KalshiPosition:
    ticker: str
    position: int       # positive = yes, negative = no
    market_exposure: float
    realized_pnl: float
    unrealized_pnl: float
    total_traded: int


class KalshiClient:
    """
    Client for interacting with the Kalshi prediction market API.
    Supports both live and demo environments.
    """

    def __init__(self, email: str, password: str, demo: bool = True):
        self.email = email
        self.password = password
        self.demo = demo
        self.base_url = KALSHI_DEMO_URL if demo else KALSHI_BASE_URL
        self.token: Optional[str] = None
        self.member_id: Optional[str] = None
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def login(self) -> bool:
        """Authenticate and retrieve session token."""
        try:
            resp = self.session.post(
                f"{self.base_url}/login",
                json={"email": self.email, "password": self.password},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            self.token = data.get("token")
            self.member_id = data.get("member_id")
            if self.token:
                self.session.headers.update({"Authorization": f"Bearer {self.token}"})
                logger.info("Kalshi login successful, member_id=%s", self.member_id)
                return True
            return False
        except requests.exceptions.RequestException as e:
            logger.error("Kalshi login failed: %s", e)
            return False

    def logout(self):
        """Invalidate session token."""
        try:
            self.session.post(f"{self.base_url}/logout", timeout=5)
        except Exception:
            pass
        self.token = None

    def _get(self, path: str, params: dict = None) -> Optional[Dict]:
        """Make authenticated GET request."""
        try:
            resp = self.session.get(
                f"{self.base_url}{path}", params=params, timeout=10
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            logger.error("GET %s failed: %s | %s", path, e, e.response.text if e.response else "")
            return None
        except Exception as e:
            logger.error("GET %s error: %s", path, e)
            return None

    def _post(self, path: str, payload: dict) -> Optional[Dict]:
        """Make authenticated POST request."""
        try:
            resp = self.session.post(
                f"{self.base_url}{path}", json=payload, timeout=10
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            logger.error("POST %s failed: %s | %s", path, e, e.response.text if e.response else "")
            return None
        except Exception as e:
            logger.error("POST %s error: %s", path, e)
            return None

    # ──────────────────────────────────────────────
    # Market Discovery
    # ──────────────────────────────────────────────

    def get_markets(
        self,
        series_ticker: str = "KXBTC",
        status: str = "open",
        limit: int = 100,
    ) -> List[KalshiMarket]:
        """Fetch open Bitcoin prediction markets."""
        params = {
            "series_ticker": series_ticker,
            "status": status,
            "limit": limit,
        }
        data = self._get("/markets", params=params)
        if not data:
            return []

        markets = []
        for m in data.get("markets", []):
            try:
                market = KalshiMarket(
                    ticker=m.get("ticker", ""),
                    title=m.get("title", ""),
                    status=m.get("status", ""),
                    yes_bid=m.get("yes_bid", 0) or 0,
                    yes_ask=m.get("yes_ask", 0) or 0,
                    no_bid=m.get("no_bid", 0) or 0,
                    no_ask=m.get("no_ask", 0) or 0,
                    close_time=m.get("close_time", ""),
                    expected_expiration_time=m.get("expected_expiration_time", ""),
                    cap_strike=m.get("cap_strike"),
                    floor_strike=m.get("floor_strike"),
                    result=m.get("result"),
                    volume=m.get("volume", 0) or 0,
                    open_interest=m.get("open_interest", 0) or 0,
                    series_ticker=m.get("series_ticker", ""),
                )
                markets.append(market)
            except Exception as e:
                logger.warning("Failed to parse market: %s", e)

        logger.info("Fetched %d markets for series %s", len(markets), series_ticker)
        return markets

    def get_market(self, ticker: str) -> Optional[KalshiMarket]:
        """Fetch a single market by ticker."""
        data = self._get(f"/markets/{ticker}")
        if not data:
            return None
        m = data.get("market", {})
        return KalshiMarket(
            ticker=m.get("ticker", ticker),
            title=m.get("title", ""),
            status=m.get("status", ""),
            yes_bid=m.get("yes_bid", 0) or 0,
            yes_ask=m.get("yes_ask", 0) or 0,
            no_bid=m.get("no_bid", 0) or 0,
            no_ask=m.get("no_ask", 0) or 0,
            close_time=m.get("close_time", ""),
            expected_expiration_time=m.get("expected_expiration_time", ""),
            cap_strike=m.get("cap_strike"),
            floor_strike=m.get("floor_strike"),
            result=m.get("result"),
            volume=m.get("volume", 0) or 0,
            open_interest=m.get("open_interest", 0) or 0,
            series_ticker=m.get("series_ticker", ""),
        )

    def get_orderbook(self, ticker: str) -> Optional[Dict]:
        """Fetch market orderbook."""
        return self._get(f"/markets/{ticker}/orderbook")

    def find_btc_5min_markets(self) -> List[KalshiMarket]:
        """
        Find open Bitcoin markets that expire within the next 5-15 minutes.
        These are the short-duration binary markets suitable for 5-min predictions.
        """
        markets = self.get_markets(series_ticker="KXBTC", status="open")
        now = datetime.now(timezone.utc)
        short_markets = []

        for m in markets:
            if not m.close_time:
                continue
            try:
                close_dt = datetime.fromisoformat(
                    m.close_time.replace("Z", "+00:00")
                )
                mins_to_close = (close_dt - now).total_seconds() / 60
                # Target markets closing in 1-15 minutes
                if 1 <= mins_to_close <= 15:
                    short_markets.append(m)
            except ValueError:
                continue

        short_markets.sort(
            key=lambda x: x.close_time
        )
        logger.info("Found %d BTC short-duration markets", len(short_markets))
        return short_markets

    # ──────────────────────────────────────────────
    # Order Management
    # ──────────────────────────────────────────────

    def place_order(
        self,
        ticker: str,
        side: str,        # "yes" or "no"
        action: str,      # "buy" or "sell"
        count: int,       # number of contracts ($0.01 each, max payout $1)
        price: int,       # price in cents (1-99)
        order_type: str = "limit",
    ) -> Optional[KalshiOrder]:
        """
        Place a prediction market order.

        Args:
            ticker:     Market ticker (e.g. "KXBTCD-25MAR15-T96000")
            side:       "yes" (bet it happens) or "no" (bet it doesn't)
            action:     "buy" to open, "sell" to close
            count:      Number of contracts (each worth $1 if correct)
            price:      Limit price in cents (1-99)
            order_type: "limit" or "market"
        """
        payload = {
            "ticker": ticker,
            "client_order_id": f"btc_{ticker}_{int(datetime.now().timestamp())}",
            "type": order_type,
            "action": action,
            "side": side,
            "count": count,
            "yes_price": price if side == "yes" else (100 - price),
            "no_price": price if side == "no" else (100 - price),
            "expiration_ts": None,
            "sell_position_floor": None,
            "buy_max_cost": None,
        }

        data = self._post("/portfolio/orders", payload)
        if not data:
            return None

        order = data.get("order", {})
        return KalshiOrder(
            order_id=order.get("order_id", ""),
            ticker=ticker,
            side=side,
            action=action,
            count=count,
            price=price,
            status=order.get("status", "unknown"),
            created_time=order.get("created_time", ""),
        )

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a resting order."""
        data = self._post(f"/portfolio/orders/{order_id}/cancel", {})
        return data is not None

    def get_orders(self, ticker: str = None, status: str = None) -> List[KalshiOrder]:
        """Fetch portfolio orders."""
        params = {}
        if ticker:
            params["ticker"] = ticker
        if status:
            params["status"] = status

        data = self._get("/portfolio/orders", params=params)
        if not data:
            return []

        orders = []
        for o in data.get("orders", []):
            orders.append(KalshiOrder(
                order_id=o.get("order_id", ""),
                ticker=o.get("ticker", ""),
                side=o.get("side", ""),
                action=o.get("action", ""),
                count=o.get("count", 0),
                price=o.get("yes_price", 0),
                status=o.get("status", ""),
                created_time=o.get("created_time", ""),
            ))
        return orders

    def get_positions(self) -> List[KalshiPosition]:
        """Fetch current portfolio positions."""
        data = self._get("/portfolio/positions")
        if not data:
            return []

        positions = []
        for p in data.get("market_positions", []):
            positions.append(KalshiPosition(
                ticker=p.get("ticker", ""),
                position=p.get("position", 0),
                market_exposure=p.get("market_exposure", 0.0),
                realized_pnl=p.get("realized_pnl", 0.0),
                unrealized_pnl=p.get("unrealized_pnl", 0.0),
                total_traded=p.get("total_traded", 0),
            ))
        return positions

    def get_balance(self) -> Dict[str, float]:
        """Fetch account balance."""
        data = self._get("/portfolio/balance")
        if not data:
            return {"balance": 0.0, "payout": 0.0}
        return {
            "balance": (data.get("balance", 0) or 0) / 100.0,   # convert cents to dollars
            "payout": (data.get("payout", 0) or 0) / 100.0,
        }
