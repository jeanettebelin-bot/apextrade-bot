from dataclasses import dataclass, field
from typing import List, Dict, Any
import pandas as pd

@dataclass
class SignalResult:
    signal: str           # "BUY", "SELL", "HOLD"
    confidence: int       # 0 - 100
    reasons: List[str] = field(default_factory=list)
    strategy_name: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)

class BaseStrategy:
    name: str = "base"
    description: str = ""

    def evaluate(self, df: pd.DataFrame) -> SignalResult:
        raise NotImplementedError

class TrendMomentumStrategy(BaseStrategy):
    name = "trend_momentum"
    description = "EMA9/EMA21 Crossover förstärkt med MACD och trendfilter (SMA50)"

    def evaluate(self, df: pd.DataFrame) -> SignalResult:
        if len(df) < 25:
            return SignalResult(signal="HOLD", confidence=0, reasons=["Otillräckligt med historisk data"])

        last = df.iloc[-1]
        prev = df.iloc[-2]

        reasons = []
        buy_score = 0
        sell_score = 0

        # 1. EMA 9 vs EMA 21 Crossover & Alignment
        ema9 = last["EMA9"]
        ema21 = last["EMA21"]
        prev_ema9 = prev["EMA9"]
        prev_ema21 = prev["EMA21"]

        if ema9 > ema21:
            buy_score += 35
            reasons.append(f"Bullish trend: EMA9 ({ema9:.2f}) ligger över EMA21 ({ema21:.2f})")
            if prev_ema9 <= prev_ema21:
                buy_score += 25
                reasons.append("Färsk köpsignal: Golden cross mellan EMA9 och EMA21")
        else:
            sell_score += 35
            reasons.append(f"Bearish trend: EMA9 ({ema9:.2f}) under EMA21 ({ema21:.2f})")
            if prev_ema9 >= prev_ema21:
                sell_score += 25
                reasons.append("Färsk säljsignal: Death cross mellan EMA9 och EMA21")

        # 2. MACD Histogram
        macd_hist = last["MACD_Hist"]
        if macd_hist > 0:
            buy_score += 20
            reasons.append(f"MACD-momentum är positivt (+{macd_hist:.3f})")
        else:
            sell_score += 20
            reasons.append(f"MACD-momentum är negativt ({macd_hist:.3f})")

        # 3. Macro trend (SMA50)
        close = last["Close"]
        sma50 = last["SMA50"]
        if close > sma50:
            buy_score += 20
            reasons.append(f"Priset handlas över 50-dagars medelvärde ({close:.2f} > {sma50:.2f})")
        else:
            sell_score += 20
            reasons.append(f"Priset handlas under 50-dagars medelvärde ({close:.2f} < {sma50:.2f})")

        # 4. RSI Overbought / Oversold protection
        rsi = last["RSI"]
        if rsi > 72:
            buy_score -= 30
            reasons.append(f"Varning: RSI är överköpt ({rsi:.1f})")
        elif rsi < 30:
            sell_score -= 20
            reasons.append(f"RSI är översålt ({rsi:.1f}) - kan vända uppåt")

        if buy_score >= 65 and buy_score > sell_score:
            return SignalResult(signal="BUY", confidence=min(buy_score, 100), reasons=reasons, strategy_name=self.name)
        elif sell_score >= 65 and sell_score > buy_score:
            return SignalResult(signal="SELL", confidence=min(sell_score, 100), reasons=reasons, strategy_name=self.name)
        else:
            return SignalResult(signal="HOLD", confidence=max(buy_score, sell_score), reasons=reasons, strategy_name=self.name)

class RSIReversionStrategy(BaseStrategy):
    name = "rsi_reversion"
    description = "Mean Reversion baserad på extrema RSI-nivåer och vändningssignaler"

    def evaluate(self, df: pd.DataFrame) -> SignalResult:
        if len(df) < 20:
            return SignalResult(signal="HOLD", confidence=0, reasons=["Otillräckligt med data"])

        last = df.iloc[-1]
        prev = df.iloc[-2]
        rsi = last["RSI"]
        reasons = []

        if rsi < 32:
            confidence = int(min(95, (35 - rsi) * 5 + 60))
            reasons.append(f"RSI översåld nivå ({rsi:.1f}) < 32")
            if last["Close"] > last["Open"]:
                reasons.append("Grön vändningsstapel indikerar köpare i marknaden")
                confidence = min(100, confidence + 15)
            return SignalResult(signal="BUY", confidence=confidence, reasons=reasons, strategy_name=self.name)

        elif rsi > 68:
            confidence = int(min(95, (rsi - 65) * 5 + 60))
            reasons.append(f"RSI överköpt nivå ({rsi:.1f}) > 68")
            if last["Close"] < last["Open"]:
                reasons.append("Röd säljstapel bekräftar vinsthemtagning")
                confidence = min(100, confidence + 15)
            return SignalResult(signal="SELL", confidence=confidence, reasons=reasons, strategy_name=self.name)

        return SignalResult(
            signal="HOLD",
            confidence=50,
            reasons=[f"RSI är neutralt ({rsi:.1f}) mellan 32 och 68"],
            strategy_name=self.name
        )

class BreakoutStrategy(BaseStrategy):
    name = "breakout"
    description = "Volatilitetsutbrott över Bollinger-banden bekräftat av volymökning"

    def evaluate(self, df: pd.DataFrame) -> SignalResult:
        if len(df) < 25:
            return SignalResult(signal="HOLD", confidence=0, reasons=["Otillräckligt med data"])

        last = df.iloc[-1]
        close = last["Close"]
        bb_upper = last["BB_Upper"]
        bb_lower = last["BB_Lower"]
        vol_surge = last.get("Vol_Surge", 1.0)
        reasons = []

        if close > bb_upper:
            reasons.append(f"Utbrott: Pris ({close:.2f}) stängde över övre Bollinger-bandet ({bb_upper:.2f})")
            confidence = 65
            if vol_surge > 1.25:
                reasons.append(f"Hög volym bekräftar utbrottet ({vol_surge:.2f}x volymsnitt)")
                confidence += 25
            return SignalResult(signal="BUY", confidence=min(100, confidence), reasons=reasons, strategy_name=self.name)

        elif close < bb_lower:
            reasons.append(f"Negativt haveri: Pris ({close:.2f}) bröt under nedre Bollinger-bandet ({bb_lower:.2f})")
            confidence = 65
            return SignalResult(signal="SELL", confidence=confidence, reasons=reasons, strategy_name=self.name)

        return SignalResult(
            signal="HOLD",
            confidence=40,
            reasons=[f"Priset konsoliderar innanför Bollinger-banden ({bb_lower:.2f} - {bb_upper:.2f})"],
            strategy_name=self.name
        )

STRATEGY_REGISTRY = {
    "trend_momentum": TrendMomentumStrategy(),
    "rsi_reversion": RSIReversionStrategy(),
    "breakout": BreakoutStrategy()
}

def get_strategy(name: str) -> BaseStrategy:
    return STRATEGY_REGISTRY.get(name, STRATEGY_REGISTRY["trend_momentum"])
