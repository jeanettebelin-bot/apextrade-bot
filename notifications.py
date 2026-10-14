import threading
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger("Notifications")

class TelegramNotifier:
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def update_config(self, new_config: Dict[str, Any]):
        self.config = new_config

    @property
    def bot_token(self) -> str:
        return self.config.get("telegram_bot_token", "").strip()

    @property
    def chat_id(self) -> str:
        return str(self.config.get("telegram_chat_id", "")).strip()

    @property
    def is_enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        if not self.is_enabled:
            return False

        def _send():
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                payload = {
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True
                }
                res = requests.post(url, json=payload, timeout=8)
                if not res.ok:
                    logger.warning(f"Telegram notification failed ({res.status_code}): {res.text}")
                    return False
                return True
            except Exception as e:
                logger.error(f"Error sending Telegram notification: {e}")
                return False

        # Send asynchronously so trading logic never halts
        threading.Thread(target=_send, daemon=True).start()
        return True

    def test_connection(self, token: Optional[str] = None, chat_id: Optional[str] = None) -> Dict[str, Any]:
        t = token or self.bot_token
        c = chat_id or self.chat_id
        if not t or not c:
            return {"success": False, "error": "Bot Token och Chat ID måste fyllas i."}

        try:
            url = f"https://api.telegram.org/bot{t}/sendMessage"
            payload = {
                "chat_id": c,
                "text": "🚀 <b>ApexTrade Test-notis</b>\n\nGrattis! Telegram-kopplingen fungerar klockrent. Du kommer nu få alla viktiga signaler direkt i fickan!",
                "parse_mode": "HTML"
            }
            res = requests.post(url, json=payload, timeout=8)
            data = res.json()
            if res.ok and data.get("ok"):
                return {"success": True, "message": "Testnotis skickad framgångsrikt!"}
            else:
                desc = data.get("description", "Okänt fel från Telegram")
                return {"success": False, "error": f"Telegram svarade: {desc}"}
        except Exception as e:
            return {"success": False, "error": f"Nätverksfel: {str(e)}"}

    def notify_buy(self, symbol: str, shares: float, price_usd: float, total_sek: float, reason: str):
        msg = (
            f"🟢 <b>KÖP GENOMFÖRT</b>\n\n"
            f"<b>Aktie:</b> {symbol}\n"
            f"<b>Antal:</b> {shares:.4f} st\n"
            f"<b>Kurs:</b> ${price_usd:.2f}\n"
            f"<b>Belopp:</b> ~{total_sek:.2f} kr\n"
            f"<b>Analys:</b> {reason}\n\n"
            f"<i>Stop-loss och vinstmål aktiverade.</i>"
        )
        self.send_message(msg)

    def notify_sell(self, symbol: str, price_usd: float, pl_sek: float, pl_pct: float, reason: str):
        is_win = pl_sek >= 0
        icon = "🎯 <b>VINST HEMTAGEN</b>" if is_win else "🛑 <b>STOP-LOSS SKYDD</b>"
        pl_color = f"+{pl_sek:.2f} kr (+{pl_pct:.2f}%)" if is_win else f"{pl_sek:.2f} kr ({pl_pct:.2f}%)"
        
        msg = (
            f"{icon}\n\n"
            f"<b>Aktie:</b> {symbol}\n"
            f"<b>Säljkurs:</b> ${price_usd:.2f}\n"
            f"<b>Resultat:</b> {pl_color}\n"
            f"<b>Orsak:</b> {reason}\n\n"
            f"<i>Likviden återförd till kontot för återinvestering.</i>"
        )
        self.send_message(msg)

    def notify_dip_alert(self, symbols: list, message: str):
        syms_str = ", ".join(symbols) if symbols else "Korgen"
        msg = (
            f"🛒 <b>BÖRSREA UPPTÄCKT!</b>\n\n"
            f"Marknaden är tillfälligt översåld i: <b>{syms_str}</b>.\n\n"
            f"{message}\n\n"
            f"💡 <i>Gyllene tillfälle för en strategisk kapitalinjektion via Revolut.</i>"
        )
        self.send_message(msg)

    def notify_streak_alert(self, streak_count: int, message: str):
        msg = (
            f"🔥 <b>VINST-FLOW AKTIVT!</b>\n\n"
            f"Boten har stängt <b>{streak_count} vinstaffärer i rad</b>!\n\n"
            f"{message}\n\n"
            f"⚡ <i>Momentum-strategin presterar optimalt i nuvarande marknadsklimat.</i>"
        )
        self.send_message(msg)

    def notify_daily_recap(self, report: dict):
        spy_pct = report.get("spy", {}).get("change_pct", 0.0)
        qqq_pct = report.get("qqq", {}).get("change_pct", 0.0)
        mkt_avg = report.get("market_avg", 0.0)
        pl_sek = report.get("portfolio_day_pl_sek", 0.0)
        pl_pct = report.get("portfolio_day_pl_pct", 0.0)
        alpha = report.get("alpha", 0.0)
        badge = report.get("badge_text", "")
        title = report.get("analysis_title", "Dagsrapport")
        text = report.get("analysis_text", "")
        date_str = report.get("date", "")
        session_label = report.get("session_label", "Börsbokslut")

        pl_str = f"+{pl_sek:.2f} kr (+{pl_pct:.2f}%)" if pl_sek >= 0 else f"{pl_sek:.2f} kr ({pl_pct:.2f}%)"
        mkt_str = f"S&P 500: {spy_pct:+.2f}% | Nasdaq: {qqq_pct:+.2f}%"

        gainer_str = ""
        if report.get("top_gainer"):
            tg = report["top_gainer"]
            gainer_str = f"🌟 <b>Dagens Raket:</b> {tg['symbol']} ({tg['pl_pct']:+.2f}%)\n"

        msg = (
            f"📊 <b>DAGLIG BÖRSBOKSLUT & ALFA-ANALYS</b> ({date_str})\n"
            f"<i>{session_label}</i>\n\n"
            f"💰 <b>Portföljresultat idag:</b> <code>{pl_str}</code>\n"
            f"🌐 <b>Wall Street:</b> {mkt_str} (Snitt: {mkt_avg:+.2f}%)\n"
            f"🎯 <b>Relativ Prestation (Alfa):</b> <b>{badge}</b>\n\n"
            f"{gainer_str}"
            f"<b>{title}</b>\n"
            f"{text}\n\n"
            f"👉 <a href=\"https://apextrade-bot-qxdv.onrender.com\">Öppna Kontrollpanelen</a>"
        )
        self.send_message(msg)

