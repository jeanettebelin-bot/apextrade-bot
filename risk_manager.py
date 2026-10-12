import logging
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger("RiskManager")

class RiskManager:
    def __init__(self, config: dict):
        self.config = config

    def get_risk_params(self) -> dict:
        return self.config.get("risk", {})

    def evaluate_buy_order(self, symbol: str, current_price: float, account: dict, active_positions: list) -> Tuple[bool, str, float]:
        """
        Returns (is_approved, reason, calculated_shares)
        """
        risk = self.get_risk_params()
        equity = account.get("equity", 0.0)
        cash = account.get("cash", 0.0)
        day_pl_pct = account.get("day_pl_pct", 0.0)

        # 1. Circuit Breaker Check
        max_daily_loss = risk.get("max_daily_loss_pct", 3.0)
        if day_pl_pct <= -abs(max_daily_loss):
            return False, f"Nödbroms aktiverad: Dagens förlust ({day_pl_pct:.2f}%) överskrider gränsen på -{max_daily_loss}%", 0.0

        # 2. Max Open Positions Check
        max_positions = risk.get("max_open_positions", 4)
        existing_symbols = [p["symbol"].upper() for p in active_positions]
        if symbol.upper() in existing_symbols:
            return False, f"Innehav finns redan i {symbol}. Återköp blockerat för riskspridning.", 0.0

        if len(active_positions) >= max_positions:
            return False, f"Max antal positioner ({max_positions}) är redan uppnått.", 0.0

        # 3. Position Sizing
        max_pos_pct = risk.get("max_position_pct", 25.0) / 100.0
        target_allocation_sek = equity * max_pos_pct

        if cash < target_allocation_sek * 0.95:
            target_allocation_sek = cash * 0.95  # Använd tillgängliga likvider

        if target_allocation_sek < 5.0:  # Minimum 5 kr för mikroaffär
            return False, f"Otillräckligt med likvider för mikroorder ({cash:.2f} kr)", 0.0

        usd_sek_rate = self.config.get("usd_sek_rate", 10.50)
        price_sek = current_price * usd_sek_rate

        shares = target_allocation_sek / price_sek
        shares = round(shares, 4)

        if shares <= 0.0001:
            return False, "Beräknad fraktionsandel är för liten för orderboken", 0.0

        return True, f"Godkänd order: Allokering {target_allocation_sek:.2f} kr ({shares} aktier @ ${current_price:.2f})", shares


    def check_position_exit_conditions(self, position: dict, current_price: float) -> Tuple[bool, str]:
        """
        Checks if an active position should be closed due to Stop Loss, Take Profit, or Trailing Stop.
        Returns (should_close, trigger_reason)
        """
        risk = self.get_risk_params()
        entry_price = position.get("entry_price", current_price)
        stop_loss_pct = risk.get("stop_loss_pct", 2.5)
        take_profit_pct = risk.get("take_profit_pct", 5.0)

        pnl_pct = ((current_price - entry_price) / entry_price) * 100

        # Stop-loss
        if pnl_pct <= -abs(stop_loss_pct):
            return True, f"STOP-LOSS UTLÖST: Förlust på {pnl_pct:.2f}% (gräns: -{stop_loss_pct}%)"

        # Take-profit
        if pnl_pct >= abs(take_profit_pct):
            return True, f"TAKE-PROFIT UTLÖST: Vinstmål nått på +{pnl_pct:.2f}% (mål: +{take_profit_pct}%)"

        return False, "Inom risktolerans"
