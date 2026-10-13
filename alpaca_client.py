import json
import logging
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional, Any
import requests

SWEDISH_TZ = ZoneInfo("Europe/Stockholm")

logger = logging.getLogger("AlpacaClient")

SIM_FILE = Path(__file__).resolve().parent / "simulation_state.json"

DEFAULT_SIM_STATE = {
    "cash": 100.0,
    "starting_equity": 100.0,
    "currency": "SEK",
    "positions": {},  # symbol: { "qty": float, "avg_entry_price": float, "current_price": float, "entry_time": str }
    "orders": [],     # history of simulated orders
    "closed_trades": []
}

class AlpacaClient:
    def __init__(self, config: dict):
        self.config = config
        self.mode = config.get("mode", "simulation")
        self.api_key = config.get("alpaca_api_key", "").strip()
        self.secret_key = config.get("alpaca_secret_key", "").strip()
        self.base_url = config.get("alpaca_base_url", "https://paper-api.alpaca.markets").rstrip("/")
        self._sim_state = self._load_sim_state()

    def update_config(self, config: dict):
        self.config = config
        self.mode = config.get("mode", "simulation")
        self.api_key = config.get("alpaca_api_key", "").strip()
        self.secret_key = config.get("alpaca_secret_key", "").strip()
        self.base_url = config.get("alpaca_base_url", "https://paper-api.alpaca.markets").rstrip("/")

    # --- Simulation Persistence ---
    def _load_sim_state(self) -> dict:
        if SIM_FILE.exists():
            try:
                with open(SIM_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading simulation state: {e}")
        return json.loads(json.dumps(DEFAULT_SIM_STATE))

    def _save_sim_state(self):
        try:
            with open(SIM_FILE, "w", encoding="utf-8") as f:
                json.dump(self._sim_state, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving simulation state: {e}")

    def reset_simulation(self, starting_cash: float = 100.0):
        self._sim_state = {
            "cash": starting_cash,
            "starting_equity": starting_cash,
            "currency": "SEK",
            "positions": {},
            "orders": [],
            "closed_trades": []
        }
        self._save_sim_state()

        self._save_sim_state()

    # --- Headers for Alpaca ---
    def _headers(self) -> dict:
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type": "application/json"
        }

    def is_alpaca_configured(self) -> bool:
        return bool(self.api_key and self.secret_key and len(self.api_key) > 5)

    def test_connection(self) -> dict:
        if not self.is_alpaca_configured():
            return {"connected": False, "message": "API-nycklar saknas. Använder lokal simulering."}
        try:
            url = f"{self.base_url}/v2/account"
            r = requests.get(url, headers=self._headers(), timeout=5)
            if r.status_code == 200:
                data = r.json()
                return {
                    "connected": True,
                    "account_number": data.get("account_number"),
                    "status": data.get("status"),
                    "currency": data.get("currency", "USD"),
                    "equity": float(data.get("equity", 0)),
                    "message": "Ansluten till Alpaca (" + ("Paper" if "paper" in self.base_url else "Live") + ")"
                }
            else:
                return {"connected": False, "message": f"Alpaca fel {r.status_code}: {r.text}"}
        except Exception as e:
            return {"connected": False, "message": f"Kunde inte nå Alpaca: {str(e)}"}

    def get_clock(self) -> dict:
        if self.is_alpaca_configured():
            try:
                url = f"{self.base_url}/v2/clock"
                r = requests.get(url, headers=self._headers(), timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    return {
                        "is_open": data.get("is_open", False),
                        "next_open": data.get("next_open", ""),
                        "next_close": data.get("next_close", "")
                    }
            except Exception:
                pass
        now = datetime.now(SWEDISH_TZ)
        weekday = now.weekday()
        is_weekday = weekday < 5
        is_hours = (now.hour == 15 and now.minute >= 30) or (16 <= now.hour < 22)
        return {
            "is_open": is_weekday and is_hours,
            "next_open": "15:30",
            "next_close": "22:00"
        }


    # --- Account Information ---
    def get_account(self, current_prices: Optional[Dict[str, float]] = None) -> dict:
        usd_sek_rate = self.config.get("usd_sek_rate", 10.50)
        currency = self.config.get("currency", "SEK")

        if self.mode != "simulation" and self.is_alpaca_configured():
            try:
                url = f"{self.base_url}/v2/account"
                r = requests.get(url, headers=self._headers(), timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    equity_usd = float(data.get("equity", 0.0))
                    cash_usd = float(data.get("cash", 0.0))
                    buying_power_usd = float(data.get("buying_power", cash_usd))
                    last_equity_usd = float(data.get("last_equity", equity_usd))
                    
                    equity_sek = equity_usd * usd_sek_rate
                    cash_sek = cash_usd * usd_sek_rate
                    buying_power_sek = buying_power_usd * usd_sek_rate
                    last_equity_sek = last_equity_usd * usd_sek_rate
                    day_pl_sek = equity_sek - last_equity_sek
                    day_pl_pct = (day_pl_sek / last_equity_sek * 100) if last_equity_sek > 0 else 0.0
                    return {
                        "mode": self.mode,
                        "status": data.get("status", "ACTIVE"),
                        "currency": currency,
                        "cash": round(cash_sek, 2),
                        "equity": round(equity_sek, 2),
                        "cash_usd": round(cash_usd, 2),
                        "equity_usd": round(equity_usd, 2),
                        "buying_power": round(buying_power_sek, 2),
                        "day_pl": round(day_pl_sek, 2),
                        "day_pl_pct": round(day_pl_pct, 2),
                        "initial_equity": round(last_equity_sek, 2),
                        "connected_to_broker": True,
                        "usd_sek_rate": usd_sek_rate
                    }
            except Exception as e:
                logger.error(f"Failed to fetch Alpaca account, falling back to sim: {e}")

        # Simulation Mode / Fallback
        sim = self._sim_state
        current_prices = current_prices or {}
        pos_value_sek = 0.0
        for sym, pos in sim["positions"].items():
            price_usd = current_prices.get(sym, pos.get("current_price", pos.get("avg_entry_price", 0.0)))
            pos["current_price"] = price_usd
            pos_value_sek += pos["qty"] * price_usd * usd_sek_rate

        equity_sek = sim["cash"] + pos_value_sek
        starting_sek = sim.get("starting_equity", 100.0)
        total_pl_sek = equity_sek - starting_sek
        total_pl_pct = (total_pl_sek / starting_sek * 100) if starting_sek > 0 else 0.0

        return {
            "mode": "simulation",
            "status": "SIMULATED",
            "currency": currency,
            "cash": round(sim["cash"], 2),
            "equity": round(equity_sek, 2),
            "buying_power": round(sim["cash"], 2),
            "day_pl": round(total_pl_sek, 2),
            "day_pl_pct": round(total_pl_pct, 2),
            "initial_equity": starting_sek,
            "connected_to_broker": False,
            "usd_sek_rate": usd_sek_rate
        }

    def get_open_orders(self) -> List[dict]:
        if self.mode != "simulation" and self.is_alpaca_configured():
            try:
                url = f"{self.base_url}/v2/orders?status=open"
                r = requests.get(url, headers=self._headers(), timeout=5)
                if r.status_code == 200:
                    return r.json()
            except Exception as e:
                logger.error(f"Failed to fetch open orders: {e}")
        return []

    # --- Positions ---
    def get_positions(self, current_prices: Optional[Dict[str, float]] = None) -> List[dict]:
        current_prices = current_prices or {}
        usd_sek_rate = self.config.get("usd_sek_rate", 10.50)

        if self.mode != "simulation" and self.is_alpaca_configured():
            try:
                url = f"{self.base_url}/v2/positions"
                r = requests.get(url, headers=self._headers(), timeout=5)
                if r.status_code == 200:
                    positions = []
                    for p in r.json():
                        qty = float(p.get("qty", 0))
                        entry_price = float(p.get("avg_entry_price", 0))
                        current_price = float(p.get("current_price", entry_price))
                        market_val_sek = qty * current_price * usd_sek_rate
                        unrealized_pl_usd = float(p.get("unrealized_pl", 0))
                        unrealized_pl_sek = unrealized_pl_usd * usd_sek_rate
                        unrealized_plpc = float(p.get("unrealized_plpc", 0)) * 100
                        positions.append({
                            "symbol": p.get("symbol"),
                            "qty": qty,
                            "entry_price": entry_price,
                            "current_price": current_price,
                            "market_value_sek": round(market_val_sek, 2),
                            "unrealized_pl_sek": round(unrealized_pl_sek, 2),
                            "unrealized_pl_pct": round(unrealized_plpc, 2)
                        })
                    return positions
            except Exception as e:
                logger.error(f"Failed to fetch Alpaca positions: {e}")

        # Simulation Mode Positions
        sim = self._sim_state
        positions_list = []
        for sym, pos in list(sim["positions"].items()):
            qty = pos.get("qty", 0.0)
            if qty <= 0:
                continue
            entry_usd = pos.get("avg_entry_price", 0.0)
            curr_usd = current_prices.get(sym, pos.get("current_price", entry_usd))
            pos["current_price"] = curr_usd
            market_val_sek = qty * curr_usd * usd_sek_rate
            cost_basis_sek = qty * entry_usd * usd_sek_rate
            unrealized_pl_sek = market_val_sek - cost_basis_sek
            unrealized_pct = ((curr_usd - entry_usd) / entry_usd * 100) if entry_usd > 0 else 0.0
            positions_list.append({
                "symbol": sym,
                "qty": round(qty, 4),
                "entry_price": round(entry_usd, 2),
                "current_price": round(curr_usd, 2),
                "market_value_sek": round(market_val_sek, 2),
                "unrealized_pl_sek": round(unrealized_pl_sek, 2),
                "unrealized_pl_pct": round(unrealized_pct, 2),
                "entry_time": pos.get("entry_time", "")
            })
        self._save_sim_state()
        return positions_list

    # --- Orders ---
    def place_order(self, symbol: str, qty: float, side: str, order_type: str = "market",
                    limit_price: Optional[float] = None, current_price: Optional[float] = None) -> dict:
        symbol = symbol.upper()
        usd_sek_rate = self.config.get("usd_sek_rate", 10.50)

        if self.mode != "simulation" and self.is_alpaca_configured():
            try:
                url = f"{self.base_url}/v2/orders"
                payload = {
                    "symbol": symbol,
                    "qty": str(round(qty, 4)),
                    "side": side.lower(),
                    "type": order_type.lower(),
                    "time_in_force": "day"
                }
                if order_type.lower() == "limit" and limit_price:
                    payload["limit_price"] = str(round(limit_price, 2))

                r = requests.post(url, headers=self._headers(), json=payload, timeout=5)
                if r.status_code in (200, 201):
                    data = r.json()
                    return {
                        "success": True,
                        "order_id": data.get("id"),
                        "symbol": symbol,
                        "qty": qty,
                        "side": side,
                        "status": data.get("status"),
                        "created_at": data.get("created_at")
                    }
                else:
                    return {"success": False, "error": f"Alpaca order failed: {r.text}"}
            except Exception as e:
                return {"success": False, "error": f"Exception placing Alpaca order: {str(e)}"}

        # Simulation Mode Order Execution
        sim = self._sim_state
        fill_price_usd = current_price or limit_price or 100.0
        cost_sek = qty * fill_price_usd * usd_sek_rate

        order_record = {
            "order_id": f"sim_{int(datetime.now().timestamp()*1000)}",
            "symbol": symbol,
            "qty": qty,
            "side": side.lower(),
            "fill_price_usd": fill_price_usd,
            "cost_sek": round(cost_sek, 2),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        if side.lower() == "buy":
            if sim["cash"] < cost_sek:
                return {"success": False, "error": f"Inte tillräckligt med likvider ({sim['cash']:.2f} kr < {cost_sek:.2f} kr)"}
            sim["cash"] -= cost_sek
            if symbol in sim["positions"]:
                curr_pos = sim["positions"][symbol]
                total_qty = curr_pos["qty"] + qty
                new_avg = ((curr_pos["qty"] * curr_pos["avg_entry_price"]) + (qty * fill_price_usd)) / total_qty
                curr_pos["qty"] = total_qty
                curr_pos["avg_entry_price"] = new_avg
                curr_pos["current_price"] = fill_price_usd
            else:
                sim["positions"][symbol] = {
                    "qty": qty,
                    "avg_entry_price": fill_price_usd,
                    "current_price": fill_price_usd,
                    "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
        elif side.lower() == "sell":
            if symbol not in sim["positions"] or sim["positions"][symbol]["qty"] < qty * 0.999:
                return {"success": False, "error": f"Inget aktivt innehav i {symbol} att sälja"}
            curr_pos = sim["positions"][symbol]
            realized_pl_sek = (fill_price_usd - curr_pos["avg_entry_price"]) * qty * usd_sek_rate
            sim["cash"] += cost_sek
            curr_pos["qty"] -= qty
            
            sim["closed_trades"].append({
                "symbol": symbol,
                "qty": qty,
                "entry_price": curr_pos["avg_entry_price"],
                "exit_price": fill_price_usd,
                "pl_sek": round(realized_pl_sek, 2),
                "pl_pct": round((fill_price_usd - curr_pos["avg_entry_price"]) / curr_pos["avg_entry_price"] * 100, 2),
                "closed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

            if curr_pos["qty"] <= 0.0001:
                del sim["positions"][symbol]

        sim["orders"].insert(0, order_record)
        if len(sim["orders"]) > 100:
            sim["orders"] = sim["orders"][:100]

        self._save_sim_state()
        return {
            "success": True,
            "order_id": order_record["order_id"],
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "fill_price": fill_price_usd,
            "cost_sek": round(cost_sek, 2),
            "status": "filled",
            "created_at": order_record["timestamp"]
        }

    def close_position(self, symbol: str, current_price: Optional[float] = None) -> dict:
        symbol = symbol.upper()
        if self.mode != "simulation" and self.is_alpaca_configured():
            try:
                url = f"{self.base_url}/v2/positions/{symbol}"
                r = requests.delete(url, headers=self._headers(), timeout=5)
                if r.status_code in (200, 204):
                    return {"success": True, "message": f"Position för {symbol} stängd via Alpaca"}
                return {"success": False, "error": f"Kunde inte stänga position: {r.text}"}
            except Exception as e:
                return {"success": False, "error": str(e)}

        sim = self._sim_state
        if symbol in sim["positions"]:
            qty = sim["positions"][symbol]["qty"]
            return self.place_order(symbol, qty, "sell", current_price=current_price)
        return {"success": False, "error": f"Ingen position hittades för {symbol}"}

    def get_order_history(self) -> List[dict]:
        if self.mode != "simulation" and self.is_alpaca_configured():
            try:
                url = f"{self.base_url}/v2/orders?status=all&limit=50"
                r = requests.get(url, headers=self._headers(), timeout=5)
                if r.status_code == 200:
                    orders = []
                    for o in r.json():
                        orders.append({
                            "order_id": o.get("id"),
                            "symbol": o.get("symbol"),
                            "qty": float(o.get("qty", 0)),
                            "side": o.get("side"),
                            "status": o.get("status"),
                            "fill_price": float(o.get("filled_avg_price") or 0.0),
                            "timestamp": o.get("created_at", "")[:19].replace("T", " ")
                        })
                    return orders
            except Exception as e:
                logger.error(f"Failed to fetch Alpaca orders: {e}")

        return self._sim_state.get("orders", [])

    def get_closed_trades(self) -> List[dict]:
        return self._sim_state.get("closed_trades", [])
