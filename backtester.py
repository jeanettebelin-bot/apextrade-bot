import logging
from typing import Dict, Any, List
import pandas as pd
import numpy as np
from market_data import MarketData
from strategies import get_strategy

logger = logging.getLogger("Backtester")

class Backtester:
    def __init__(self, market_data: MarketData):
        self.market_data = market_data

    def run_backtest(self, symbol: str, strategy_name: str, period: str = "6mo",
                     stop_loss_pct: float = 2.5, take_profit_pct: float = 5.0,
                     initial_capital: float = 10000.0) -> Dict[str, Any]:
        symbol = symbol.upper()
        df = self.market_data.get_bars(symbol, period=period, interval="1d", force_refresh=True)

        if df is None or len(df) < 30:
            return {"success": False, "error": f"Otillräckligt med historisk kursdata för {symbol}"}

        df = self.market_data.calculate_indicators(df)
        strategy = get_strategy(strategy_name)

        capital = initial_capital
        cash = initial_capital
        position = None  # { "shares": float, "entry_price": float, "entry_date": str }
        trades: List[Dict[str, Any]] = []
        equity_curve: List[float] = [initial_capital]

        start_price = float(df["Close"].iloc[25])
        end_price = float(df["Close"].iloc[-1])
        buy_and_hold_return = ((end_price - start_price) / start_price) * 100

        # Simulate candle by candle starting after indicator warm-up
        for i in range(25, len(df)):
            sub_df = df.iloc[: i + 1]
            curr_row = df.iloc[i]
            date_str = str(df.index[i])[:10]
            curr_price = float(curr_row["Close"])

            # 1. If currently in a position, check exit conditions
            if position is not None:
                entry_price = position["entry_price"]
                pnl_pct = ((curr_price - entry_price) / entry_price) * 100
                should_exit = False
                exit_reason = ""

                # Stop loss
                if pnl_pct <= -abs(stop_loss_pct):
                    should_exit = True
                    exit_reason = f"Stop-Loss ({pnl_pct:.2f}%)"
                # Take profit
                elif pnl_pct >= abs(take_profit_pct):
                    should_exit = True
                    exit_reason = f"Take-Profit (+{pnl_pct:.2f}%)"
                else:
                    # Strategy exit signal
                    sig = strategy.evaluate(sub_df)
                    if sig.signal == "SELL" and sig.confidence >= 65:
                        should_exit = True
                        exit_reason = f"Strategisignal SELL ({sig.confidence}%)"

                if should_exit:
                    sell_value = position["shares"] * curr_price
                    realized_pl = sell_value - (position["shares"] * entry_price)
                    cash += sell_value
                    trades.append({
                        "entry_date": position["entry_date"],
                        "exit_date": date_str,
                        "entry_price": round(entry_price, 2),
                        "exit_price": round(curr_price, 2),
                        "shares": round(position["shares"], 2),
                        "pl": round(realized_pl, 2),
                        "pl_pct": round(pnl_pct, 2),
                        "reason": exit_reason
                    })
                    position = None

            # 2. If not in position, check buy signal
            elif position is None:
                sig = strategy.evaluate(sub_df)
                if sig.signal == "BUY" and sig.confidence >= 65:
                    # Allocate 95% of available cash
                    alloc = cash * 0.95
                    shares = alloc / curr_price
                    cash -= (shares * curr_price)
                    position = {
                        "shares": shares,
                        "entry_price": curr_price,
                        "entry_date": date_str
                    }

            # Calculate daily total equity
            total_eq = cash + (position["shares"] * curr_price if position else 0)
            equity_curve.append(round(total_eq, 2))

        # Close any open position at end
        if position is not None:
            last_price = float(df["Close"].iloc[-1])
            sell_value = position["shares"] * last_price
            realized_pl = sell_value - (position["shares"] * position["entry_price"])
            pnl_pct = ((last_price - position["entry_price"]) / position["entry_price"]) * 100
            cash += sell_value
            trades.append({
                "entry_date": position["entry_date"],
                "exit_date": str(df.index[-1])[:10],
                "entry_price": round(position["entry_price"], 2),
                "exit_price": round(last_price, 2),
                "shares": round(position["shares"], 2),
                "pl": round(realized_pl, 2),
                "pl_pct": round(pnl_pct, 2),
                "reason": "Testperiodens slut"
            })

        final_equity = cash
        total_return_pct = ((final_equity - initial_capital) / initial_capital) * 100

        # Metrics
        wins = [t for t in trades if t["pl"] > 0]
        losses = [t for t in trades if t["pl"] < 0]
        win_rate = (len(wins) / len(trades) * 100) if trades else 0.0

        total_gain = sum(t["pl"] for t in wins)
        total_loss = abs(sum(t["pl"] for t in losses))
        profit_factor = (total_gain / total_loss) if total_loss > 0 else (99.0 if total_gain > 0 else 1.0)

        # Max drawdown
        peak = equity_curve[0]
        max_dd = 0.0
        for val in equity_curve:
            if val > peak:
                peak = val
            dd = ((peak - val) / peak) * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        return {
            "success": True,
            "symbol": symbol,
            "strategy": strategy_name,
            "period": period,
            "initial_capital": initial_capital,
            "final_equity": round(final_equity, 2),
            "total_return_pct": round(total_return_pct, 2),
            "buy_and_hold_return_pct": round(buy_and_hold_return, 2),
            "alpha": round(total_return_pct - buy_and_hold_return, 2),
            "total_trades": len(trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(win_rate, 1),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "trades": trades
        }
