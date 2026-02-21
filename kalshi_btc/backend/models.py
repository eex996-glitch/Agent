"""
Pydantic models for API request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class BetSide(str, Enum):
    YES = "yes"
    NO  = "no"


class BetAction(str, Enum):
    BUY  = "buy"
    SELL = "sell"


class PlaceBetRequest(BaseModel):
    ticker: str = Field(..., description="Kalshi market ticker")
    side: BetSide = Field(..., description="'yes' or 'no'")
    contracts: int = Field(..., ge=1, le=500, description="Number of contracts")
    price: int = Field(..., ge=1, le=99, description="Limit price in cents")


class AutoBetRequest(BaseModel):
    enabled: bool
    min_confidence: float = Field(0.60, ge=0.50, le=0.99)
    max_bet_size: float = Field(10.0, ge=1.0, le=500.0)
    max_exposure: float = Field(50.0, ge=1.0, le=10000.0)
    kelly_fraction: float = Field(0.25, ge=0.05, le=1.0)


class PredictionResponse(BaseModel):
    direction: str
    confidence: float
    predicted_change_pct: float
    current_price: float
    bet_side: str
    kalshi_price: int
    scores: Dict[str, float]
    indicators: Dict[str, float]
    reasoning: List[str]
    timestamp: str


class MarketResponse(BaseModel):
    ticker: str
    title: str
    status: str
    yes_bid: float
    yes_ask: float
    no_bid: float
    no_ask: float
    close_time: str
    implied_probability: float
    volume: int


class BetResponse(BaseModel):
    bet_id: str
    ticker: str
    market_title: str
    direction: str
    side: str
    contracts: int
    entry_price_cents: int
    cost: float
    max_payout: float
    confidence: float
    btc_price_at_entry: float
    placed_at: str
    expiry_time: str
    status: str
    payout: float
    profit_loss: float
    roi_pct: float


class StatsResponse(BaseModel):
    total_bets: int
    open_bets: int
    won: int
    lost: int
    win_rate: float
    total_pnl: float
    total_wagered: float
    roi_pct: float
    current_exposure: float


class HealthResponse(BaseModel):
    status: str
    kalshi_connected: bool
    btc_price: Optional[float]
    timestamp: str
