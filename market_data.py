import time
import logging
from typing import Dict, Optional, List
import pandas as pd
import numpy as np
import yfinance as yf

logger = logging.getLogger("MarketData")

# Simple in-memory cache to prevent unnecessary rate limiting
_BARS_CACHE: Dict[str, dict] = {}

class MarketData:
    def __init__(self, config: dict):
        self.config = config

    def get_bars(self, symbol: str, period: str = "3mo", interval: str = "1d", force_refresh: bool = False) -> Optional[pd.DataFrame]:
        symbol = symbol.upper()
        cache_key = f"{symbol}_{period}_{interval}"
        now = time.time()

        if not force_refresh and cache_key in _BARS_CACHE:
            cached = _BARS_CACHE[cache_key]
            if now - cached["time"] < 60:  # Cache for 60 seconds
                return cached["data"].copy()

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            if df.empty or len(df) < 15:
                logger.warning(f"No bars returned for {symbol}")
                return None

            df = df.dropna()
            _BARS_CACHE[cache_key] = {"time": now, "data": df}
            return df.copy()
        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {e}")
            return None

    def get_current_price(self, symbol: str) -> Optional[float]:
        symbol = symbol.upper()
        df = self.get_bars(symbol, period="5d", interval="1d")
        if df is not None and not df.empty:
            return round(float(df["Close"].iloc[-1]), 2)
        return None

    def get_usd_sek_rate(self) -> float:
        rate = self.config.get("usd_sek_rate", 10.50)
        try:
            df = self.get_bars("USDSEK=X", period="5d", interval="1d")
            if df is not None and not df.empty:
                rate = round(float(df["Close"].iloc[-1]), 2)
                self.config["usd_sek_rate"] = rate
        except Exception:
            pass
        return rate


    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        close = df["Close"]

        # Exponential Moving Averages
        df["EMA9"] = close.ewm(span=9, adjust=False).mean()
        df["EMA21"] = close.ewm(span=21, adjust=False).mean()
        df["SMA50"] = close.rolling(window=min(50, len(close))).mean()

        # Relative Strength Index (RSI 14)
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -1 * delta.clip(upper=0)
        roll_up = gain.ewm(com=13, adjust=False).mean()
        roll_down = loss.ewm(com=13, adjust=False).mean()
        rs = roll_up / roll_down.replace(0, np.nan)
        df["RSI"] = 100 - (100 / (1 + rs))
        df["RSI"] = df["RSI"].fillna(50)

        # MACD (12, 26, 9)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        df["MACD"] = ema12 - ema26
        df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
        df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

        # Bollinger Bands (20, 2)
        period = min(20, len(close))
        df["BB_Middle"] = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        df["BB_Upper"] = df["BB_Middle"] + (std * 2)
        df["BB_Lower"] = df["BB_Middle"] - (std * 2)

        # ATR (Average True Range 14)
        high = df["High"]
        low = df["Low"]
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["ATR"] = tr.rolling(window=min(14, len(tr))).mean().bfill()

        # Volume Moving Average
        if "Volume" in df.columns:
            df["Vol_MA20"] = df["Volume"].rolling(window=min(20, len(df))).mean()
            df["Vol_Surge"] = df["Volume"] / df["Vol_MA20"].replace(0, 1)

        return df

    def get_analysis_snapshot(self, symbol: str) -> Optional[dict]:
        df = self.get_bars(symbol, period="3mo", interval="1d")
        if df is None or len(df) < 25:
            return None

        df = self.calculate_indicators(df)
        last = df.iloc[-1]
        prev = df.iloc[-2]

        curr_price = round(float(last["Close"]), 2)
        prev_price = round(float(prev["Close"]), 2)
        change_pct = round(((curr_price - prev_price) / prev_price) * 100, 2)

        return {
            "symbol": symbol.upper(),
            "price": curr_price,
            "change_pct": change_pct,
            "rsi": round(float(last["RSI"]), 1),
            "ema9": round(float(last["EMA9"]), 2),
            "ema21": round(float(last["EMA21"]), 2),
            "sma50": round(float(last["SMA50"]), 2),
            "macd": round(float(last["MACD"]), 3),
            "macd_signal": round(float(last["MACD_Signal"]), 3),
            "macd_hist": round(float(last["MACD_Hist"]), 3),
            "bb_upper": round(float(last["BB_Upper"]), 2),
            "bb_lower": round(float(last["BB_Lower"]), 2),
            "atr": round(float(last["ATR"]), 2),
            "volume": int(last.get("Volume", 0)),
            "vol_surge": round(float(last.get("Vol_Surge", 1.0)), 2),
            "timestamp": str(df.index[-1])[:10]
        }
