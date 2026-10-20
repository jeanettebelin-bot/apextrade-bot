import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "bot_config.json"

DEFAULT_CONFIG = {
    "mode": "live",        # Live-handel som standard
    "currency": "SEK",     # Basvaluta i svenska kronor
    "starting_capital_sek": 109.20,
    "usd_sek_rate": 10.50, # Uppdateras dynamiskt mot marknaden
    "alpaca_api_key": "",
    "alpaca_secret_key": "",
    "alpaca_base_url": "https://api.alpaca.markets",
    "alpaca_data_url": "https://data.alpaca.markets/v2",
    "watchlist": ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META", "AMD", "AVGO", "PLTR", "COIN", "NFLX", "TSM", "JPM", "SPY", "QQQ"],
    "strategy": "trend_momentum",  # "trend_momentum", "rsi_reversion", "breakout"
    "scan_interval_seconds": 60,
    "profit_harvest_pct": 10.0,    # 10% av vinsterna reserveras för vinstskörd (90% snöboll)
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "risk": {
        "max_position_pct": 15.0,       # Ca 330 kr per position vid 2 200 kr
        "stop_loss_pct": 2.5,           # Hard exit vid -2.5%
        "take_profit_pct": 4.0,         # Vinstmål vid +4.0%
        "trailing_stop_pct": 1.5,       # Trailing stop
        "max_open_positions": 12,       # Max 12 poster samtidigt
        "max_daily_loss_pct": 3.0,      # Circuit breaker
        "allow_fractional": True        # Fraktionshandel krävs för mikrobelopp
    }
}

def load_config() -> dict:
    config = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                config.update(saved)
                if "risk" in saved:
                    config["risk"] = {**DEFAULT_CONFIG["risk"], **saved["risk"]}
        except Exception:
            pass

    # Läs från miljövariabler (för molndrift som Render)
    if os.environ.get("ALPACA_API_KEY"):
        config["alpaca_api_key"] = os.environ["ALPACA_API_KEY"].strip()
    if os.environ.get("ALPACA_SECRET_KEY"):
        config["alpaca_secret_key"] = os.environ["ALPACA_SECRET_KEY"].strip()
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        config["telegram_bot_token"] = os.environ["TELEGRAM_BOT_TOKEN"].strip()
    if os.environ.get("TELEGRAM_CHAT_ID"):
        config["telegram_chat_id"] = os.environ["TELEGRAM_CHAT_ID"].strip()
    if os.environ.get("BOT_MODE"):
        config["mode"] = os.environ["BOT_MODE"].strip().lower()
        if config["mode"] == "live":
            config["alpaca_base_url"] = "https://api.alpaca.markets"
        elif config["mode"] == "paper":
            config["alpaca_base_url"] = "https://paper-api.alpaca.markets"

    return config


def save_config(new_config: dict) -> dict:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(new_config, f, indent=2)
    return new_config
