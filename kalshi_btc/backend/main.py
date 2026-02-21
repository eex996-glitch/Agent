"""
Kalshi Bitcoin Prediction Betting — Backend API
FastAPI application providing real-time BTC analysis and Kalshi bet management.

Endpoints:
  GET  /api/health              — health check
  GET  /api/btc/price           — current BTC price + 24h stats
  GET  /api/btc/klines          — historical OHLCV candles
  GET  /api/prediction          — latest 5-min prediction signal
  GET  /api/markets             — available Kalshi BTC markets
  POST /api/bet/manual          — manually place a bet
  POST /api/bet/auto/config     — configure / toggle auto-betting
  GET  /api/bets                — all bets (open + closed)
  GET  /api/stats               — aggregated P&L statistics
  GET  /api/positions           — Kalshi portfolio positions
  WS   /ws                      — real-time updates (price + signal)
"""

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

from .kalshi_client import KalshiClient
from .btc_data import BTCDataFetcher
from .predictor import BTCPredictor, PredictionSignal
from .bet_manager import BetManager, BetManagerConfig
from .models import (
    PlaceBetRequest, AutoBetRequest, HealthResponse,
    PredictionResponse, MarketResponse, BetResponse, StatsResponse
)

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Application State
# ──────────────────────────────────────────────

class AppState:
    def __init__(self):
        self.kalshi = KalshiClient(
            email=os.getenv("KALSHI_EMAIL", ""),
            password=os.getenv("KALSHI_PASSWORD", ""),
            demo=os.getenv("KALSHI_ENV", "demo").lower() == "demo",
        )
        self.btc = BTCDataFetcher()
        self.predictor = BTCPredictor()
        self.bet_manager = BetManager(
            self.kalshi,
            BetManagerConfig(
                auto_bet=False,
                min_confidence=float(os.getenv("MIN_CONFIDENCE", "0.60")),
                max_bet_size=float(os.getenv("MAX_BET_SIZE", "10.0")),
                max_exposure=float(os.getenv("MAX_EXPOSURE", "50.0")),
                kelly_fraction=float(os.getenv("KELLY_FRACTION", "0.25")),
            ),
        )
        self.kalshi_connected: bool = False
        self.last_signal: Optional[PredictionSignal] = None
        self.last_signal_time: float = 0.0
        self.ws_clients: list = []
        self._prediction_task: Optional[asyncio.Task] = None
        self._settle_task: Optional[asyncio.Task] = None


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Kalshi BTC Betting backend...")

    # Try Kalshi login
    if state.kalshi.email and state.kalshi.password:
        state.kalshi_connected = state.kalshi.login()
        if state.kalshi_connected:
            logger.info("Kalshi connected (demo=%s)", state.kalshi.demo)
        else:
            logger.warning("Kalshi login failed — running in data-only mode")
    else:
        logger.warning("No Kalshi credentials configured — running in data-only mode")

    # Start background workers
    state._prediction_task = asyncio.create_task(_prediction_loop())
    state._settle_task     = asyncio.create_task(_settlement_loop())

    yield  # app is running

    # Shutdown
    if state._prediction_task:
        state._prediction_task.cancel()
    if state._settle_task:
        state._settle_task.cancel()
    if state.kalshi_connected:
        state.kalshi.logout()
    logger.info("Backend shutdown complete")


app = FastAPI(
    title="Kalshi BTC Betting API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
_frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(_frontend_dir):
    app.mount("/static", StaticFiles(directory=_frontend_dir), name="static")


# ──────────────────────────────────────────────
# Background Workers
# ──────────────────────────────────────────────

async def _prediction_loop():
    """Refresh prediction every 60 seconds and broadcast to WebSocket clients."""
    while True:
        try:
            await _refresh_prediction()
            await _broadcast_update()
        except Exception as e:
            logger.error("Prediction loop error: %s", e)
        await asyncio.sleep(60)


async def _settlement_loop():
    """Check open bets for expiry every 30 seconds."""
    while True:
        try:
            price = await asyncio.to_thread(state.btc.get_current_price)
            if price:
                settled = state.bet_manager.settle_expired_bets(price)
                if settled:
                    await _broadcast_update()
        except Exception as e:
            logger.error("Settlement loop error: %s", e)
        await asyncio.sleep(30)


async def _refresh_prediction():
    """Fetch fresh market data and compute a new prediction."""
    try:
        # Fetch data concurrently
        tfs = await asyncio.to_thread(state.btc.get_multi_tf_klines)
        ob  = await asyncio.to_thread(state.btc.get_order_book_pressure)
        tm  = await asyncio.to_thread(state.btc.get_trade_momentum)

        df_5m  = tfs.get("5m")
        df_1m  = tfs.get("1m")
        df_15m = tfs.get("15m")
        df_1h  = tfs.get("1h")

        if df_5m is None or df_5m.empty:
            logger.warning("No 5m data — skipping prediction refresh")
            return

        signal = state.predictor.predict(
            df_5m=df_5m,
            orderbook=ob,
            trade_momentum=tm,
            df_1m=df_1m,
            df_15m=df_15m,
            df_1h=df_1h,
        )
        state.last_signal = signal
        state.last_signal_time = time.time()

        # Auto-bet if enabled
        if state.bet_manager.config.auto_bet:
            bal = state.kalshi.get_balance() if state.kalshi_connected else {"balance": 1000.0}
            state.bet_manager.evaluate_and_bet(signal, bal.get("balance", 100.0))

    except Exception as e:
        logger.error("_refresh_prediction error: %s", e)


async def _broadcast_update():
    """Push a JSON update to all connected WebSocket clients."""
    if not state.ws_clients:
        return
    price = await asyncio.to_thread(state.btc.get_current_price)
    msg = {
        "type": "update",
        "btc_price": price,
        "signal": state.last_signal.to_dict() if state.last_signal else None,
        "stats": state.bet_manager.get_stats(),
        "open_bets": [b.to_dict() for b in state.bet_manager.open_bets],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    dead = []
    for ws in state.ws_clients:
        try:
            await ws.send_text(json.dumps(msg))
        except Exception:
            dead.append(ws)
    for ws in dead:
        state.ws_clients.remove(ws)


# ──────────────────────────────────────────────
# REST Endpoints
# ──────────────────────────────────────────────

@app.get("/")
async def serve_frontend():
    """Serve the main dashboard HTML."""
    index = os.path.join(_frontend_dir, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return {"message": "Kalshi BTC Betting API — frontend not found"}


@app.get("/api/health")
async def health():
    price = await asyncio.to_thread(state.btc.get_current_price)
    return {
        "status": "ok",
        "kalshi_connected": state.kalshi_connected,
        "btc_price": price,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/btc/price")
async def btc_price():
    """Current BTC price and 24-hour stats."""
    ticker = await asyncio.to_thread(state.btc.get_ticker_24h)
    if not ticker:
        price = await asyncio.to_thread(state.btc.get_current_price)
        ticker = {"price": price}
    return ticker


@app.get("/api/btc/klines")
async def btc_klines(interval: str = "5m", limit: int = 100):
    """Historical OHLCV candles."""
    if interval not in ("1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d"):
        raise HTTPException(400, "Invalid interval")
    limit = max(1, min(500, limit))
    df = await asyncio.to_thread(state.btc.get_klines, interval, limit)
    if df.empty:
        raise HTTPException(503, "Could not fetch candle data")
    df = df.reset_index()
    df["timestamp"] = df["timestamp"].astype(str)
    return df.to_dict(orient="records")


@app.get("/api/prediction")
async def get_prediction():
    """Latest 5-minute prediction signal. Refreshes if stale (>90s)."""
    age = time.time() - state.last_signal_time
    if state.last_signal is None or age > 90:
        await _refresh_prediction()

    if state.last_signal is None:
        raise HTTPException(503, "Prediction not available — check BTC data feed")

    return state.last_signal.to_dict()


@app.get("/api/markets")
async def get_markets(limit: int = 20):
    """Available Kalshi Bitcoin prediction markets."""
    if not state.kalshi_connected:
        raise HTTPException(503, "Kalshi not connected — check credentials")
    markets = await asyncio.to_thread(state.kalshi.get_markets, "KXBTC", "open", limit)
    return [
        {
            "ticker": m.ticker,
            "title": m.title,
            "status": m.status,
            "yes_bid": m.yes_bid,
            "yes_ask": m.yes_ask,
            "no_bid": m.no_bid,
            "no_ask": m.no_ask,
            "close_time": m.close_time,
            "implied_probability": round(m.implied_probability, 4),
            "volume": m.volume,
        }
        for m in markets
    ]


@app.get("/api/markets/5min")
async def get_5min_markets():
    """Kalshi BTC markets expiring in the next 1-15 minutes."""
    if not state.kalshi_connected:
        raise HTTPException(503, "Kalshi not connected")
    markets = await asyncio.to_thread(state.kalshi.find_btc_5min_markets)
    return [
        {
            "ticker": m.ticker,
            "title": m.title,
            "yes_bid": m.yes_bid,
            "yes_ask": m.yes_ask,
            "close_time": m.close_time,
            "implied_probability": round(m.implied_probability, 4),
        }
        for m in markets
    ]


@app.post("/api/bet/manual")
async def place_manual_bet(req: PlaceBetRequest):
    """Manually place a bet on a specific Kalshi market."""
    if not state.kalshi_connected:
        raise HTTPException(503, "Kalshi not connected — cannot place real bets")

    order = await asyncio.to_thread(
        state.kalshi.place_order,
        req.ticker, req.side.value, "buy", req.contracts, req.price,
    )
    if not order:
        raise HTTPException(500, "Order placement failed — check Kalshi API logs")

    return {
        "success": True,
        "order_id": order.order_id,
        "status": order.status,
        "ticker": req.ticker,
        "side": req.side.value,
        "contracts": req.contracts,
        "price": req.price,
    }


@app.post("/api/bet/signal")
async def bet_on_signal():
    """
    Evaluate the current prediction signal and place a bet using
    Kelly-sized position. Uses auto-bet logic with current config.
    """
    if state.last_signal is None:
        await _refresh_prediction()
    if state.last_signal is None:
        raise HTTPException(503, "No prediction signal available")

    if state.kalshi_connected:
        bal_data = await asyncio.to_thread(state.kalshi.get_balance)
        balance = bal_data.get("balance", 100.0)
    else:
        balance = 100.0  # simulate with $100

    bet = state.bet_manager.evaluate_and_bet(state.last_signal, balance)
    if bet is None:
        return {
            "placed": False,
            "reason": "Signal below confidence threshold or exposure limit reached",
            "signal": state.last_signal.to_dict(),
        }

    return {
        "placed": True,
        "bet": bet.to_dict(),
        "signal": state.last_signal.to_dict(),
    }


@app.post("/api/bet/auto/config")
async def configure_auto_bet(req: AutoBetRequest):
    """Enable/disable auto-betting and update its configuration."""
    cfg = state.bet_manager.config
    cfg.auto_bet = req.enabled
    cfg.min_confidence = req.min_confidence
    cfg.max_bet_size = req.max_bet_size
    cfg.max_exposure = req.max_exposure
    cfg.kelly_fraction = req.kelly_fraction
    return {
        "auto_bet_enabled": cfg.auto_bet,
        "min_confidence": cfg.min_confidence,
        "max_bet_size": cfg.max_bet_size,
        "max_exposure": cfg.max_exposure,
        "kelly_fraction": cfg.kelly_fraction,
    }


@app.get("/api/bet/auto/config")
async def get_auto_bet_config():
    """Get current auto-bet configuration."""
    cfg = state.bet_manager.config
    return {
        "auto_bet_enabled": cfg.auto_bet,
        "min_confidence": cfg.min_confidence,
        "max_bet_size": cfg.max_bet_size,
        "max_exposure": cfg.max_exposure,
        "kelly_fraction": cfg.kelly_fraction,
    }


@app.get("/api/bets")
async def get_bets(status: Optional[str] = None):
    """All bets. Filter by status: 'open', 'won', 'lost', 'simulated'."""
    bets = state.bet_manager.all_bets
    if status:
        bets = [b for b in bets if b.status == status]
    return [b.to_dict() for b in reversed(bets)]  # newest first


@app.get("/api/stats")
async def get_stats():
    """Aggregated betting statistics and P&L."""
    return state.bet_manager.get_stats()


@app.get("/api/positions")
async def get_positions():
    """Current Kalshi portfolio positions."""
    if not state.kalshi_connected:
        raise HTTPException(503, "Kalshi not connected")
    positions = await asyncio.to_thread(state.kalshi.get_positions)
    return [
        {
            "ticker": p.ticker,
            "position": p.position,
            "market_exposure": p.market_exposure,
            "realized_pnl": p.realized_pnl,
            "unrealized_pnl": p.unrealized_pnl,
        }
        for p in positions
    ]


@app.get("/api/balance")
async def get_balance():
    """Kalshi account balance."""
    if not state.kalshi_connected:
        return {"balance": None, "payout": None, "error": "Kalshi not connected"}
    return await asyncio.to_thread(state.kalshi.get_balance)


# ──────────────────────────────────────────────
# WebSocket
# ──────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """
    Real-time feed: sends JSON updates every time prediction or price changes.
    Message format:
      { type: "update", btc_price, signal, stats, open_bets, timestamp }
    """
    await ws.accept()
    state.ws_clients.append(ws)
    logger.info("WebSocket client connected (total=%d)", len(state.ws_clients))

    # Send immediate snapshot on connect
    await _broadcast_update()

    try:
        while True:
            # Keep-alive: wait for client ping or disconnect
            data = await asyncio.wait_for(ws.receive_text(), timeout=30.0)
            if data == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    except Exception as e:
        logger.error("WebSocket error: %s", e)
    finally:
        if ws in state.ws_clients:
            state.ws_clients.remove(ws)
        logger.info("WebSocket client disconnected (total=%d)", len(state.ws_clients))
