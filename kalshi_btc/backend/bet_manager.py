"""
Kalshi Bet Manager
Orchestrates finding Bitcoin markets, sizing bets, and placing orders
based on price prediction signals.
"""

import logging
import math
from datetime import datetime, timezone
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field

from .kalshi_client import KalshiClient, KalshiMarket, KalshiOrder
from .predictor import PredictionSignal

logger = logging.getLogger(__name__)


@dataclass
class BetRecord:
    """Tracks a single placed bet and its outcome."""
    bet_id: str
    ticker: str
    market_title: str
    direction: str          # "UP" | "DOWN"
    side: str               # "yes" | "no"
    contracts: int
    entry_price: int        # cents paid per contract
    cost: float             # total cost in dollars
    confidence: float
    predicted_change_pct: float
    btc_price_at_entry: float
    placed_at: str
    expiry_time: str
    status: str = "open"    # "open" | "won" | "lost" | "canceled"
    payout: float = 0.0
    profit_loss: float = 0.0
    kalshi_order_id: str = ""

    @property
    def max_payout(self) -> float:
        return self.contracts * 1.0  # each contract pays $1 if correct

    @property
    def roi_pct(self) -> float:
        if self.cost <= 0:
            return 0.0
        return (self.profit_loss / self.cost) * 100

    def to_dict(self) -> dict:
        return {
            "bet_id": self.bet_id,
            "ticker": self.ticker,
            "market_title": self.market_title,
            "direction": self.direction,
            "side": self.side,
            "contracts": self.contracts,
            "entry_price_cents": self.entry_price,
            "cost": round(self.cost, 2),
            "max_payout": round(self.max_payout, 2),
            "confidence": round(self.confidence, 4),
            "btc_price_at_entry": round(self.btc_price_at_entry, 2),
            "placed_at": self.placed_at,
            "expiry_time": self.expiry_time,
            "status": self.status,
            "payout": round(self.payout, 2),
            "profit_loss": round(self.profit_loss, 2),
            "roi_pct": round(self.roi_pct, 2),
        }


@dataclass
class BetManagerConfig:
    # Maximum total dollar exposure across all open bets
    max_exposure: float = 50.0

    # Maximum per-bet dollar amount
    max_bet_size: float = 10.0

    # Minimum confidence required before placing any bet
    min_confidence: float = 0.60

    # Kelly fraction for bet sizing (0.25 = quarter-Kelly, conservative)
    kelly_fraction: float = 0.25

    # Minimum contracts per bet
    min_contracts: int = 1

    # Maximum contracts per bet
    max_contracts: int = 50

    # Skip markets with implied probability far from our prediction
    # (avoids markets where price already reflects our edge)
    max_price_mismatch: float = 30.0   # cents

    # Auto-bet mode: if True, bets are placed automatically
    auto_bet: bool = False


class BetManager:
    """
    Manages the end-to-end flow:
    1. Find suitable BTC prediction markets on Kalshi
    2. Size bets using Kelly criterion
    3. Place orders
    4. Track open bets and P&L
    """

    def __init__(self, kalshi: KalshiClient, config: BetManagerConfig = None):
        self.kalshi = kalshi
        self.config = config or BetManagerConfig()
        self.open_bets: List[BetRecord] = []
        self.closed_bets: List[BetRecord] = []
        self._bet_counter = 0

    # ──────────────────────────────────────────────
    # Properties
    # ──────────────────────────────────────────────

    @property
    def total_exposure(self) -> float:
        return sum(b.cost for b in self.open_bets)

    @property
    def total_pnl(self) -> float:
        return sum(b.profit_loss for b in self.closed_bets)

    @property
    def win_rate(self) -> float:
        won = sum(1 for b in self.closed_bets if b.profit_loss > 0)
        total = len(self.closed_bets)
        return won / total if total > 0 else 0.0

    @property
    def all_bets(self) -> List[BetRecord]:
        return self.open_bets + self.closed_bets

    # ──────────────────────────────────────────────
    # Core Flow
    # ──────────────────────────────────────────────

    def evaluate_and_bet(
        self, signal: PredictionSignal, account_balance: float
    ) -> Optional[BetRecord]:
        """
        Given a prediction signal, find the best matching Kalshi market,
        size the bet, and optionally place it.

        Returns the BetRecord if a bet was placed (or simulated), else None.
        """
        # Gate: confidence threshold
        if signal.direction == "NEUTRAL":
            logger.info("Signal is NEUTRAL — skipping bet")
            return None

        if signal.confidence < self.config.min_confidence:
            logger.info(
                "Confidence %.2f below threshold %.2f — skipping",
                signal.confidence, self.config.min_confidence
            )
            return None

        # Gate: exposure limit
        if self.total_exposure >= self.config.max_exposure:
            logger.warning("Max exposure reached ($%.2f) — skipping", self.total_exposure)
            return None

        # Find markets
        markets = self.kalshi.find_btc_5min_markets()
        if not markets:
            logger.info("No suitable BTC 5-min markets available")
            return None

        # Select best market
        market = self._select_market(markets, signal)
        if not market:
            logger.info("No suitable market matched the signal")
            return None

        # Size the bet
        contracts, entry_price = self._size_bet(signal, market, account_balance)
        if contracts < self.config.min_contracts:
            logger.info("Calculated bet too small (%d contracts) — skipping", contracts)
            return None

        # Place or simulate
        bet = self._execute_bet(signal, market, contracts, entry_price)
        if bet:
            self.open_bets.append(bet)
            logger.info(
                "Bet placed: %s %s x%d @ %dc | ticker=%s",
                bet.side.upper(), bet.direction, bet.contracts,
                bet.entry_price, bet.ticker
            )
        return bet

    def _select_market(
        self, markets: List[KalshiMarket], signal: PredictionSignal
    ) -> Optional[KalshiMarket]:
        """
        Find the market best matching our prediction.

        For an UP prediction we want a YES contract on a market
        whose strike is just above current price (so we profit if price rises).
        For DOWN we want a NO contract on a market just above current price.
        """
        current_price = signal.current_price
        best_market = None
        best_score = float("-inf")

        for m in markets:
            if m.status != "open":
                continue
            if not m.yes_ask and not m.yes_bid:
                continue

            # Target: market with floor/cap near current price
            if m.cap_strike:
                distance = abs(m.cap_strike - current_price) / current_price
            elif m.floor_strike:
                distance = abs(m.floor_strike - current_price) / current_price
            else:
                distance = 0.0

            # Liquidity score
            spread = abs((m.yes_ask or 50) - (m.yes_bid or 50))
            liquidity_score = -spread - distance * 100

            if liquidity_score > best_score:
                best_score = liquidity_score
                best_market = m

        return best_market

    def _size_bet(
        self,
        signal: PredictionSignal,
        market: KalshiMarket,
        account_balance: float,
    ) -> Tuple[int, int]:
        """
        Kelly Criterion bet sizing.

        Kelly fraction = (p * b - q) / b
          p = our estimated probability of winning
          q = 1 - p
          b = net odds (payout/cost - 1)

        We use fractional Kelly for safety.
        Returns (contracts, price_in_cents).
        """
        p = signal.confidence  # our probability estimate
        q = 1.0 - p

        # Use market ask price as our entry cost
        if signal.direction == "UP":
            entry_price = market.yes_ask or 50
        else:
            entry_price = market.no_ask or 50

        entry_price = max(1, min(99, entry_price))

        cost_per_contract = entry_price / 100.0    # dollars
        payout_per_contract = 1.0                   # dollars if correct
        net_odds = (payout_per_contract / cost_per_contract) - 1.0  # b

        if net_odds <= 0:
            return 0, entry_price

        # Kelly fraction
        kelly = (p * net_odds - q) / net_odds
        kelly = max(0.0, kelly)

        # Apply fractional Kelly
        fraction = kelly * self.config.kelly_fraction

        # Dollar amount to bet
        max_from_kelly = account_balance * fraction
        max_from_config = min(
            self.config.max_bet_size,
            self.config.max_exposure - self.total_exposure
        )
        dollar_bet = min(max_from_kelly, max_from_config)
        dollar_bet = max(0.0, dollar_bet)

        contracts = int(dollar_bet / cost_per_contract)
        contracts = max(
            self.config.min_contracts,
            min(self.config.max_contracts, contracts)
        )

        logger.debug(
            "Kelly sizing: p=%.2f, odds=%.2f, kelly=%.3f, fraction=%.3f, "
            "contracts=%d, price=%dc",
            p, net_odds, kelly, fraction, contracts, entry_price
        )

        return contracts, entry_price

    def _execute_bet(
        self,
        signal: PredictionSignal,
        market: KalshiMarket,
        contracts: int,
        entry_price: int,
    ) -> Optional[BetRecord]:
        """Place the order on Kalshi (or simulate if auto_bet is False)."""
        self._bet_counter += 1
        bet_id = f"bet_{self._bet_counter:04d}"
        cost = (contracts * entry_price) / 100.0

        side = "yes" if signal.direction == "UP" else "no"
        kalshi_order_id = ""

        if self.config.auto_bet:
            order = self.kalshi.place_order(
                ticker=market.ticker,
                side=side,
                action="buy",
                count=contracts,
                price=entry_price,
            )
            if not order:
                logger.error("Order placement failed for %s", market.ticker)
                return None
            kalshi_order_id = order.order_id

        return BetRecord(
            bet_id=bet_id,
            ticker=market.ticker,
            market_title=market.title,
            direction=signal.direction,
            side=side,
            contracts=contracts,
            entry_price=entry_price,
            cost=cost,
            confidence=signal.confidence,
            predicted_change_pct=signal.predicted_change_pct,
            btc_price_at_entry=signal.current_price,
            placed_at=datetime.now(timezone.utc).isoformat(),
            expiry_time=market.close_time,
            status="open" if self.config.auto_bet else "simulated",
            kalshi_order_id=kalshi_order_id,
        )

    # ──────────────────────────────────────────────
    # Bet Settlement
    # ──────────────────────────────────────────────

    def settle_expired_bets(self, current_btc_price: float):
        """
        Check open bets against expiry time and settle against current BTC price.
        In live mode this would check Kalshi for official settlement.
        """
        now = datetime.now(timezone.utc)
        settled = []

        for bet in self.open_bets:
            try:
                expiry = datetime.fromisoformat(bet.expiry_time.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue

            if now < expiry:
                continue  # not yet expired

            # Determine outcome based on BTC price movement
            price_moved_up = current_btc_price > bet.btc_price_at_entry

            won = (bet.direction == "UP" and price_moved_up) or \
                  (bet.direction == "DOWN" and not price_moved_up)

            if won:
                bet.payout = bet.contracts * 1.0   # $1 per contract
                bet.profit_loss = bet.payout - bet.cost
                bet.status = "won"
            else:
                bet.payout = 0.0
                bet.profit_loss = -bet.cost
                bet.status = "lost"

            settled.append(bet)

        for bet in settled:
            self.open_bets.remove(bet)
            self.closed_bets.append(bet)
            logger.info(
                "Bet %s settled: %s | P&L $%.2f | BTC $%.0f → $%.0f",
                bet.bet_id, bet.status, bet.profit_loss,
                bet.btc_price_at_entry, current_btc_price
            )

        return settled

    # ──────────────────────────────────────────────
    # Stats
    # ──────────────────────────────────────────────

    def get_stats(self) -> dict:
        closed = self.closed_bets
        if not closed:
            return {
                "total_bets": 0,
                "open_bets": len(self.open_bets),
                "won": 0,
                "lost": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "total_wagered": 0.0,
                "roi_pct": 0.0,
                "current_exposure": round(self.total_exposure, 2),
            }

        won = sum(1 for b in closed if b.status == "won")
        lost = sum(1 for b in closed if b.status == "lost")
        total_wagered = sum(b.cost for b in closed)
        total_pnl = sum(b.profit_loss for b in closed)

        return {
            "total_bets": len(closed),
            "open_bets": len(self.open_bets),
            "won": won,
            "lost": lost,
            "win_rate": round(won / len(closed) * 100, 1),
            "total_pnl": round(total_pnl, 2),
            "total_wagered": round(total_wagered, 2),
            "roi_pct": round(total_pnl / total_wagered * 100, 2) if total_wagered > 0 else 0.0,
            "current_exposure": round(self.total_exposure, 2),
        }
