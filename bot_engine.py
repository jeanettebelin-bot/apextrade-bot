import time
import threading
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Dict, Any, Optional

SWEDISH_TZ = ZoneInfo("Europe/Stockholm")

from config import load_config, save_config
from alpaca_client import AlpacaClient
from market_data import MarketData
from strategies import get_strategy
from risk_manager import RiskManager
from notifications import TelegramNotifier

logger = logging.getLogger("BotEngine")

class BotEngine:
    def __init__(self):
        self.config = load_config()
        self.alpaca_client = AlpacaClient(self.config)
        self.market_data = MarketData(self.config)
        self.risk_manager = RiskManager(self.config)
        self.notifier = TelegramNotifier(self.config)
        
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        self.logs: List[Dict[str, str]] = []
        self.last_scan_time: Optional[str] = None
        self.signals_cache: Dict[str, Any] = {}
        self.current_prices: Dict[str, float] = {}
        self._last_notified_streak = 0
        self._last_notified_dip = False

        self.add_log("INFO", "Tradingbot initierad i " + self.config.get("mode", "simulation").upper() + "-läge")

    def add_log(self, level: str, message: str):
        record = {
            "time": datetime.now(SWEDISH_TZ).strftime("%H:%M:%S"),
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
        self.notifier.update_config(self.config)
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
        self.last_scan_time = datetime.now(SWEDISH_TZ).strftime("%Y-%m-%d %H:%M:%S")
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
                    try:
                        rate = self.alpaca_client.usd_sek_rate
                        qty = float(pos.get("qty", 1.0))
                        entry = float(pos.get("entry_price", curr_price))
                        pl_usd = (curr_price - entry) * qty
                        cost_usd = entry * qty
                        pl_pct = (pl_usd / cost_usd * 100) if cost_usd > 0 else 0.0
                        self.notifier.notify_sell(
                            symbol=sym,
                            price_usd=curr_price,
                            pl_sek=pl_usd * rate,
                            pl_pct=pl_pct,
                            reason=reason
                        )
                    except Exception as ex:
                        logger.warning(f"Notification error on sell: {ex}")
                else:
                    self.add_log("ERROR", f"Misslyckades att stänga {sym}: {res.get('error')}")

        # 3. If running, evaluate Buy signals
        if self.is_running:
            account = self.alpaca_client.get_account(current_prices=self.current_prices)
            current_active = self.alpaca_client.get_positions(current_prices=self.current_prices)
            open_orders = self.alpaca_client.get_open_orders()
            pending_symbols = [o.get("symbol", "").upper() for o in open_orders]
            max_pos = self.config.get("risk", {}).get("max_open_positions", 3)

            for symbol, analysis in self.signals_cache.items():
                if symbol.upper() in pending_symbols:
                    continue

                if len(current_active) + len(open_orders) >= max_pos:
                    continue

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
                            try:
                                rate = self.alpaca_client.usd_sek_rate
                                self.notifier.notify_buy(
                                    symbol=symbol,
                                    shares=shares,
                                    price_usd=curr_price,
                                    total_sek=shares * curr_price * rate,
                                    reason=reason
                                )
                            except Exception as ex:
                                logger.warning(f"Notification error on buy: {ex}")
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

    def get_capital_advisor(self) -> Dict[str, Any]:
        account = self.alpaca_client.get_account(current_prices=self.current_prices)
        equity = account.get("equity", 109.20)
        closed = self.alpaca_client.get_closed_trades()
        
        # 1. Streaks & Flow
        recent_trades = closed[:5] if len(closed) >= 5 else closed
        recent_wins = len([t for t in recent_trades if t.get("pl", 0) > 0])
        consecutive_wins = 0
        for t in closed:
            if t.get("pl", 0) > 0:
                consecutive_wins += 1
            else:
                break
        
        is_winning_streak = consecutive_wins >= 3 or (len(recent_trades) >= 3 and recent_wins / len(recent_trades) >= 0.7)
        
        # 2. Market Dip / Oversold Check
        oversold_symbols = []
        if self.signals_cache:
            for sym, sig in self.signals_cache.items():
                snap = sig.get("snapshot", {})
                rsi = snap.get("rsi")
                if rsi is not None and rsi <= 35:
                    oversold_symbols.append(sym)
        is_market_dip = len(oversold_symbols) >= 2 or (len(self.signals_cache) > 0 and len(oversold_symbols) / len(self.signals_cache) >= 0.3)
        
        # 3. Milestone progress
        milestones = [
            {"target": 120.0, "label": "Start: Verifiering (120 kr)", "phase": 1},
            {"target": 500.0, "label": "Milstolpe 1: Elddopet (500 kr)", "phase": 1},
            {"target": 1500.0, "label": "Milstolpe 2: 3 Fulla Innehav (1 500 kr)", "phase": 2},
            {"target": 5000.0, "label": "Milstolpe 3: Snöbollsacceleration (5 000 kr)", "phase": 3},
            {"target": 25000.0, "label": "Milstolpe 4: Självgående Maskin (25 000 kr)", "phase": 4},
            {"target": 100000.0, "label": "Milstolpe 5: Volontär med Kapital (100 000 kr)", "phase": 5},
        ]
        
        current_milestone = milestones[0]
        next_milestone = milestones[1]
        for idx, m in enumerate(milestones):
            if equity >= m["target"]:
                current_milestone = m
                if idx + 1 < len(milestones):
                    next_milestone = milestones[idx + 1]
                else:
                    next_milestone = m
        
        progress_pct = min(100.0, max(0.0, (equity / next_milestone["target"]) * 100.0)) if next_milestone["target"] > 0 else 100.0

        # 4. Smart Recommendation
        if is_market_dip:
            action = "KÖPLÄGE (BÖRSREA)"
            action_type = "dip"
            recommendation = f"Översålt läge upptäckt i {', '.join(oversold_symbols) if oversold_symbols else 'marknaden'}! Perfekt läge för en strategisk injektion på 300–500 kr för att rida på nästa studs."
        elif is_winning_streak:
            action = "VINST-FLOW AKTIVT"
            action_type = "streak"
            recommendation = f"Boten har vunnit {consecutive_wins} affärer i rad! Strategin är i optimal synk med börsen. Rekommenderad boost: +500 kr för att växla upp snöbollen."
        elif len(closed) < 5:
            action = "LÅT TESTET RULLA"
            action_type = "testing"
            recommendation = f"Fas 1 pågår: {len(closed)}/5 affärer klara. Låt boten samla data innan du pytsar in mer kapital."
        else:
            action = "FÖLJ SPARKALENDERN"
            action_type = "normal"
            recommendation = "Marknaden rör sig normalt. Nästa steg: Planera en månatlig insättning på 500 kr vid löning."

        # Send Telegram notification on new state transition
        if is_market_dip and not self._last_notified_dip:
            self._last_notified_dip = True
            self.notifier.notify_dip_alert(oversold_symbols, recommendation)
        elif not is_market_dip:
            self._last_notified_dip = False

        if is_winning_streak and consecutive_wins > self._last_notified_streak and consecutive_wins >= 3:
            self._last_notified_streak = consecutive_wins
            self.notifier.notify_streak_alert(consecutive_wins, recommendation)

        total_profit_sek = sum([float(t.get("pl", 0.0)) for t in closed if float(t.get("pl", 0.0)) > 0])
        harvest_pct = float(self.config.get("profit_harvest_pct", 10.0))
        harvest_vault_sek = total_profit_sek * (harvest_pct / 100.0)
        snowball_vault_sek = total_profit_sek * ((100.0 - harvest_pct) / 100.0)

        return {
            "equity_sek": equity,
            "current_milestone": current_milestone,
            "next_milestone": next_milestone,
            "progress_pct": round(progress_pct, 1),
            "is_winning_streak": is_winning_streak,
            "consecutive_wins": consecutive_wins,
            "is_market_dip": is_market_dip,
            "oversold_symbols": oversold_symbols,
            "action": action,
            "action_type": action_type,
            "recommendation": recommendation,
            "total_profit_sek": round(total_profit_sek, 2),
            "harvest_pct": harvest_pct,
            "snowball_pct": 100.0 - harvest_pct,
            "harvest_vault_sek": round(harvest_vault_sek, 2),
            "snowball_vault_sek": round(snowball_vault_sek, 2)
        }
