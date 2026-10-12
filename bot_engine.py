import time
import threading
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from config import load_config, save_config
from alpaca_client import AlpacaClient
from market_data import MarketData
from strategies import get_strategy
from risk_manager import RiskManager

logger = logging.getLogger("BotEngine")

class BotEngine:
    def __init__(self):
        self.config = load_config()
        self.alpaca_client = AlpacaClient(self.config)
        self.market_data = MarketData(self.config)
        self.risk_manager = RiskManager(self.config)
        
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        self.logs: List[Dict[str, str]] = []
        self.last_scan_time: Optional[str] = None
        self.signals_cache: Dict[str, Any] = {}
        self.current_prices: Dict[str, float] = {}

        self.add_log("INFO", "Tradingbot initierad i " + self.config.get("mode", "simulation").upper() + "-läge")

    def add_log(self, level: str, message: str):
        record = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "message": message
        }
        self.logs.insert(0, record)
        if len(self.logs) > 200:
            self.logs = self.logs[:200]
        logger.info(f"[{level}] {message}")

    def update_config(self, new_config: dict):
        self.config = save_config(new_config)
        self.alpaca_client.update_config(self.config)
        self.market_data.config = self.config
        self.risk_manager.config = self.config
        self.add_log("INFO", f"Inställningar uppdaterade (Läge: {self.config.get('mode')})")

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self.add_log("SUCCESS", "Autonom handelsmotor startad")

    def stop(self):
        if not self.is_running:
            return
        self.is_running = False
        self._stop_event.set()
        self.add_log("WARNING", "Handelsmotorn stoppad av användaren")

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                self.scan_once()
            except Exception as e:
                self.add_log("ERROR", f"Fel under scanning: {str(e)}")

            interval = self.config.get("scan_interval_seconds", 60)
            self._stop_event.wait(timeout=interval)

    def scan_once(self) -> dict:
        self.last_scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.add_log("INFO", "Initierar marknadsscanning...")

        watchlist = self.config.get("watchlist", [])
        strategy_name = self.config.get("strategy", "trend_momentum")
        strategy = get_strategy(strategy_name)

        # 1. Update prices & indicator snapshots
        for symbol in watchlist:
            try:
                snapshot = self.market_data.get_analysis_snapshot(symbol)
                if snapshot:
                    self.current_prices[symbol] = snapshot["price"]
                    df = self.market_data.get_bars(symbol, period="3mo", interval="1d")
                    if df is not None:
                        df = self.market_data.calculate_indicators(df)
                        signal = strategy.evaluate(df)
                        self.signals_cache[symbol] = {
                            "snapshot": snapshot,
                            "signal": signal.signal,
                            "confidence": signal.confidence,
                            "reasons": signal.reasons
                        }
            except Exception as e:
                self.add_log("WARNING", f"Kunde inte analysera {symbol}: {e}")

        # 2. Monitor Active Positions for Stop-Loss / Take-Profit
        positions = self.alpaca_client.get_positions(current_prices=self.current_prices)
        for pos in positions:
            sym = pos["symbol"]
            curr_price = self.current_prices.get(sym, pos["current_price"])
            should_close, reason = self.risk_manager.check_position_exit_conditions(pos, curr_price)
            if should_close:
                self.add_log("ALERT", f"Stänger position {sym} @ ${curr_price:.2f}: {reason}")
                res = self.alpaca_client.close_position(sym, current_price=curr_price)
                if res.get("success"):
                    self.add_log("SUCCESS", f"Position {sym} stängdes framgångsrikt")
                else:
                    self.add_log("ERROR", f"Misslyckades att stänga {sym}: {res.get('error')}")

        # 3. If running, evaluate Buy signals
        if self.is_running:
            account = self.alpaca_client.get_account(current_prices=self.current_prices)
            current_active = self.alpaca_client.get_positions(current_prices=self.current_prices)

            for symbol, analysis in self.signals_cache.items():
                if analysis["signal"] == "BUY" and analysis["confidence"] >= 65:
                    curr_price = analysis["snapshot"]["price"]
                    approved, reason, shares = self.risk_manager.evaluate_buy_order(
                        symbol, curr_price, account, current_active
                    )

                    if approved:
                        self.add_log("BUY", f"KÖP SIGNAL {symbol} (Konfidens {analysis['confidence']}%): {reason}")
                        order_res = self.alpaca_client.place_order(
                            symbol=symbol, qty=shares, side="buy", current_price=curr_price
                        )
                        if order_res.get("success"):
                            self.add_log("SUCCESS", f"Order verkställd: Köpte {shares} {symbol} @ ${curr_price:.2f}")
                            # Refresh account & positions for next iteration
                            account = self.alpaca_client.get_account(current_prices=self.current_prices)
                            current_active = self.alpaca_client.get_positions(current_prices=self.current_prices)
                        else:
                            self.add_log("ERROR", f"Kunde inte verkställa köp av {symbol}: {order_res.get('error')}")
                    else:
                        self.add_log("INFO", f"Köp av {symbol} ignorerades av riskhanteraren: {reason}")

        self.add_log("INFO", f"Scanning slutförd. {len(self.signals_cache)} instrument analyserade.")
        return {
            "scan_time": self.last_scan_time,
            "analysed_count": len(self.signals_cache)
        }
