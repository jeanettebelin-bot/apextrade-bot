import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "bot_config.json"

DEFAULT_CONFIG = {
    "mode": "simulation",  # "simulation", "paper", "live"
    "currency": "SEK",     # Basvaluta i svenska kronor
    "starting_capital_sek": 100.0,
    "usd_sek_rate": 10.50, # Uppdateras dynamiskt mot marknaden
    "alpaca_api_key": "",
    "alpaca_secret_key": "",
    "alpaca_base_url": "https://paper-api.alpaca.markets",
    "alpaca_data_url": "https://data.alpaca.markets/v2",
    "watchlist": ["AAPL", "MSFT", "NVDA", "TSLA", "SPY", "QQQ", "AMZN"],
    "strategy": "trend_momentum",  # "trend_momentum", "rsi_reversion", "breakout"
    "scan_interval_seconds": 60,
    "risk": {
        "max_position_pct": 25.0,       # 25 kr per position vid 100 kr startkapital
        "stop_loss_pct": 2.5,           # Hard exit vid -2.5% (ca -0.62 kr per 25 kr-post)
        "take_profit_pct": 5.0,         # Vinstmål vid +5.0% (ca +1.25 kr per 25 kr-post)
        "trailing_stop_pct": 1.5,       # Trailing stop
        "max_open_positions": 3,        # Max 3 poster samtidigt (t.ex. 3x 25 kr = 75 kr investerat, 25 kr i reserv)
        "max_daily_loss_pct": 3.0,      # Circuit breaker: pausa om dagsförlusten når -3.00 kr
        "allow_fractional": True        # Fraktionshandel krävs för mikrobelopp
    }
}

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                config = DEFAULT_CONFIG.copy()
                config.update(saved)
                if "risk" in saved:
                    config["risk"] = {**DEFAULT_CONFIG["risk"], **saved["risk"]}
                return config
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(new_config: dict) -> dict:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(new_config, f, indent=2)
    return new_config
