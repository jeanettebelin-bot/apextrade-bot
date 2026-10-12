from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from bot_engine import BotEngine
from backtester import Backtester

app = FastAPI(title="Pengamaskinen - ApexTrade Autonomous Trading Bot")

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(exist_ok=True)

bot = BotEngine()
backtester = Backtester(bot.market_data)

# --- Pydantic Request Models ---
class ConfigUpdateRequest(BaseModel):
    mode: Optional[str] = None
    alpaca_api_key: Optional[str] = None
    alpaca_secret_key: Optional[str] = None
    alpaca_base_url: Optional[str] = None
    watchlist: Optional[List[str]] = None
    strategy: Optional[str] = None
    scan_interval_seconds: Optional[int] = None
    risk: Optional[Dict[str, Any]] = None

class BacktestRequest(BaseModel):
    symbol: str
    strategy: str = "trend_momentum"
    period: str = "6mo"
    stop_loss_pct: float = 2.5
    take_profit_pct: float = 5.0
    initial_capital: float = 10000.0

class ManualOrderRequest(BaseModel):
    symbol: str
    qty: float
    side: str

# --- API Endpoints ---
@app.get("/api/status")
def get_status():
    account = bot.alpaca_client.get_account(current_prices=bot.current_prices)
    positions = bot.alpaca_client.get_positions(current_prices=bot.current_prices)
    closed = bot.alpaca_client.get_closed_trades()
    wins = len([t for t in closed if t.get("pl", 0) > 0])
    win_rate = (wins / len(closed) * 100) if closed else 0.0

    return {
        "is_running": bot.is_running,
        "mode": bot.config.get("mode", "simulation"),
        "strategy": bot.config.get("strategy", "trend_momentum"),
        "last_scan_time": bot.last_scan_time,
        "account": account,
        "positions": positions,
        "position_count": len(positions),
        "total_trades_count": len(closed),
        "win_rate": round(win_rate, 1),
        "broker_connected": bot.alpaca_client.is_alpaca_configured(),
        "clock": bot.alpaca_client.get_clock()
    }


@app.post("/api/bot/start")
def start_bot():
    bot.start()
    return {"success": True, "message": "Boten har startats"}

@app.post("/api/bot/stop")
def stop_bot():
    bot.stop()
    return {"success": True, "message": "Boten har stoppats"}

@app.post("/api/bot/scan")
def trigger_scan():
    res = bot.scan_once()
    return {"success": True, "data": res}

@app.get("/api/watchlist")
def get_watchlist():
    items = []
    watchlist = bot.config.get("watchlist", [])
    for sym in watchlist:
        if sym in bot.signals_cache:
            data = bot.signals_cache[sym]
            items.append({
                "symbol": sym,
                "price": data["snapshot"]["price"],
                "change_pct": data["snapshot"]["change_pct"],
                "rsi": data["snapshot"]["rsi"],
                "ema9": data["snapshot"]["ema9"],
                "ema21": data["snapshot"]["ema21"],
                "signal": data["signal"],
                "confidence": data["confidence"],
                "reasons": data["reasons"]
            })
        else:
            # Fallback quick price
            price = bot.market_data.get_current_price(sym) or 0.0
            items.append({
                "symbol": sym,
                "price": price,
                "change_pct": 0.0,
                "rsi": 50.0,
                "ema9": price,
                "ema21": price,
                "signal": "PENDING",
                "confidence": 0,
                "reasons": ["Inväntar första marknadsscanning..."]
            })
    return {"watchlist": items}

@app.post("/api/positions/{symbol}/close")
def close_position(symbol: str):
    curr_price = bot.current_prices.get(symbol.upper())
    res = bot.alpaca_client.close_position(symbol, current_price=curr_price)
    if res.get("success"):
        bot.add_log("MANUAL", f"Position {symbol} stängdes manuellt av användaren")
    return res

@app.post("/api/orders/manual")
def manual_order(req: ManualOrderRequest):
    curr_price = bot.market_data.get_current_price(req.symbol) or 100.0
    res = bot.alpaca_client.place_order(req.symbol, req.qty, req.side, current_price=curr_price)
    if res.get("success"):
        bot.add_log("MANUAL", f"Manuell order: {req.side.upper()} {req.qty} {req.symbol} @ ${curr_price:.2f}")
    return res

@app.get("/api/orders")
def get_orders():
    return {"orders": bot.alpaca_client.get_order_history()}

@app.get("/api/trades/closed")
def get_closed_trades():
    return {"trades": bot.alpaca_client.get_closed_trades()}

@app.get("/api/logs")
def get_logs():
    return {"logs": bot.logs}

@app.post("/api/backtest")
def run_backtest(req: BacktestRequest):
    res = backtester.run_backtest(
        symbol=req.symbol,
        strategy_name=req.strategy,
        period=req.period,
        stop_loss_pct=req.stop_loss_pct,
        take_profit_pct=req.take_profit_pct,
        initial_capital=req.initial_capital
    )
    return res

@app.get("/api/config")
def get_config():
    cfg = bot.config.copy()
    # Mask secret key for security
    if cfg.get("alpaca_secret_key"):
        cfg["alpaca_secret_key_masked"] = cfg["alpaca_secret_key"][:4] + "********"
    else:
        cfg["alpaca_secret_key_masked"] = ""
    return cfg

@app.post("/api/config")
def update_config(req: ConfigUpdateRequest):
    current = bot.config.copy()
    update_data = req.dict(exclude_unset=True)

    for k, v in update_data.items():
        if k == "risk" and isinstance(v, dict):
            current["risk"] = {**current.get("risk", {}), **v}
        elif v is not None:
            current[k] = v

    bot.update_config(current)
    return {"success": True, "config": bot.config}

@app.post("/api/alpaca/test")
def test_alpaca_credentials():
    return bot.alpaca_client.test_connection()

@app.post("/api/simulation/reset")
def reset_simulation():
    bot.alpaca_client.reset_simulation(100.0)
    bot.add_log("INFO", "Kontosaldo återställt till 100,00 kr")
    return {"success": True, "message": "Kontot har återställts till 100,00 kr"}


# Serve frontend
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.api_route("/", methods=["GET", "HEAD"])
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "ApexTrade API is running. Web frontend files are loading..."}

@app.api_route("/healthz", methods=["GET", "HEAD"])
def healthz():
    return {"status": "ok"}
