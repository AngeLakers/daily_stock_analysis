"""Daily SP500 leader monitor. Research signals only; no order execution."""
from __future__ import annotations
import json
import os
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import requests
import yfinance as yf

ROOT = Path("champion_rotation")
STATE = ROOT / "state.json"
REPORT = ROOT / "latest.md"
HEADERS = {"User-Agent": "ChampionRotationResearch/1.0 (educational market monitor)"}
BUFFER = 5.0  # percentage points
START_BALANCE = 200.0

def universe() -> list[str]:
    """Current SP500 only. Historical membership is NOT reconstructed."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    frames = pd.read_html(response.text)
    table = next((t for t in frames if "Symbol" in t.columns and "Security" in t.columns), None)
    if table is None or len(table) < 450:
        raise RuntimeError("S&P 500 member list unavailable or incomplete: fail closed")
    return sorted(set(str(t).replace(".", "-") for t in table["Symbol"].dropna()))

def prices(symbols: list[str]) -> pd.DataFrame:
    # Auto-adjust accounts for splits/dividends in ranking; no live intraday candles.
    chunks = []
    for i in range(0, len(symbols), 75):
        batch = symbols[i:i+75]
        data = yf.download(batch, period="2y", interval="1d", auto_adjust=True,
                           progress=False, threads=True, group_by="column")
        if data.empty:
            continue
        close = data["Close"]
        if isinstance(close, pd.Series):
            close = close.to_frame(batch[0])
        chunks.append(close)
    if not chunks:
        raise RuntimeError("No price data: fail closed")
    df = pd.concat(chunks, axis=1).sort_index()
    df = df.loc[:, ~df.columns.duplicated()]
    # Remove any in-progress trading day. Daily reports run after US close.
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("America/New_York"))
    if now.hour < 17:
        df = df[df.index.date < now.date()]
    return df.ffill(limit=1)

def rankings(close: pd.DataFrame) -> tuple[pd.Series, pd.Series, str]:
    end = close.dropna(how="all").index[-1]
    today = close.loc[end]
    prior = close[close.index.year < end.year]
    if prior.empty:
        raise RuntimeError("Previous year-end prices missing")
    ytd_base = prior.iloc[-1]
    ytd = ((today / ytd_base) - 1).mul(100)
    # 252 preceding trading sessions, requires an observed start and end.
    if len(close) < 253:
        raise RuntimeError("Insufficient history for 252-day momentum")
    rolling = ((today / close.iloc[-253]) - 1).mul(100)
    # A current constituent may have been recently listed: never substitute missing prices.
    return ytd.replace([float("inf"), -float("inf")], float("nan")).dropna().sort_values(ascending=False), rolling.replace([float("inf"), -float("-inf")], float("nan")).dropna().sort_values(ascending=False), end.strftime("%Y-%m-%d")

def transition(old: dict, rank: pd.Series, key: str, day: str, weekly: bool) -> tuple[dict, str]:
    """Outputs research TARGET, not an executed position."""
    leader = str(rank.index[0])
    target = old.get("target")
    if not target or target not in rank.index:
        return {"target": leader, "candidate": None, "streak": 0, "date": day}, "INITIAL TARGET (not an execution)"
    if old.get("date") == day:
        return old, "ALREADY CHECKED"
    # A weekly check occurs only on Monday (US/Eastern schedule).
    if weekly and pd.Timestamp(day).weekday() != 0:
        return {**old, "date": day}, "HOLD TARGET (weekly review on Monday)"
    advantage = float(rank.iloc[0] - rank[target])
    if leader == target or advantage < BUFFER:
        return {"target": target, "candidate": None, "streak": 0, "date": day}, "HOLD TARGET"
    if weekly:
        return {"target": leader, "candidate": None, "streak": 0, "date": day}, f"TARGET CHANGE: {target} -> {leader} (weekly, lead {advantage:.2f} pp)"
    streak = int(old.get("streak", 0)) + 1 if old.get("candidate") == leader else 1
    if streak >= 3:
        return {"target": leader, "candidate": None, "streak": 0, "date": day}, f"TARGET CHANGE: {target} -> {leader} (3 sessions, lead {advantage:.2f} pp)"
    return {"target": target, "candidate": leader, "streak": streak, "date": day}, f"WATCH {leader}: {streak}/3 qualifying trading days (lead {advantage:.2f} pp)"

def fmt_top(s: pd.Series) -> str:
    return "\n".join(f"| {i} | {ticker} | {value:+.2f}% |" for i, (ticker, value) in enumerate(s.head(10).items(), 1))

def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    members = universe()
    close = prices(members)
    ytd, rolling, day = rankings(close)
    if len(ytd) < 450 or len(rolling) < 400:
        raise RuntimeError(f"Too little usable coverage: YTD={len(ytd)}, rolling={len(rolling)}")
    previous = json.loads(STATE.read_text()) if STATE.exists() else {}
    new_c, message_c = transition(previous.get("C", {}), ytd, "C", day, weekly=False)
    new_d, message_d = transition(previous.get("D", {}), rolling, "D", day, weekly=True)
    changed = any("TARGET CHANGE" in x for x in (message_c, message_d))
    previous.update({"C": new_c, "D": new_d, "asof": day, "universe_count": len(members)})
    STATE.write_text(json.dumps(previous, ensure_ascii=False, indent=2) + "\n")
    result = f"""# S&P 500 Champion Monitor — {day}

Research-only, **not** a buy/sell instruction. Signals are calculated after a completed US market session. A changed TARGET is **not a filled order**.

- Model allocation: **USD ${START_BALANCE:.0f} per strategy**, independent shadow portfolios; no trades have been simulated or executed.
- Current membership: {len(members)} names. **Survivorship bias** applies to retrospective use; delisted names are missing.
- C: YTD adjusted-price winner, 5 percentage-point lead, **3 consecutive qualifying trading sessions**. {message_c}. Tracking target: **{new_c['target']}**.
- D: trailing 252-session adjusted-price winner, reviewed **Monday only**, 5 percentage-point lead. {message_d}. Tracking target: **{new_d['target']}**.
- Do not infer profitability from changing targets. Initial TARGET does not imply you already hold the stock.

## C: YTD leaders
| Rank | Ticker | Adjusted return |
|---:|---|---:|
{fmt_top(ytd)}

## D: trailing 252-session leaders
| Rank | Ticker | Adjusted return |
|---:|---|---:|
{fmt_top(rolling)}

## Data controls
Yahoo Finance via yfinance is unofficial and may be delayed or revised. Prices use adjusted closes rather than tradeable entry fills. The index membership list is scraped from Wikipedia and may change. Failures stop the pipeline and do not generate a trade signal. Weekly Monday signal may be delayed by a US market holiday. No brokerage integration or tax/slippage calculation. The USD 200 allocation is a notional reference only.
"""
    REPORT.write_text(result)
    print(result)
    if changed:
        # GitHub Actions creates an issue only for new changes; no auto-order.
        import subprocess
        title = f"Review champion target change — {day}"
        subprocess.run(["gh", "issue", "create", "--title", title, "--body-file", str(REPORT)], check=False)

if __name__ == "__main__":
    main()
