# C / D Champion monitoring (research only)

**No brokerage access. No automatic orders. No guarantee of profits.** Each strategy is assigned a hypothetical **$200 notional amount**, not $400 deposited and not a paper P&L. The script only maintains a *target ticker*, not a filled position, because price-based simulated fills and costs have not been implemented.

## Definitions
- **C (YTD champion):** rank current S&P 500 constituents by total-return-adjusted close divided by preceding calendar-year final adjusted close. If the top-ranked challenger exceeds C's existing target by **at least 5 percentage points for 3 successive observed US trading sessions**, target ticker changes. If incumbent is no longer in today's valid data, choose the current leader and flag initialization.
- **D (rolling champion):** rank current constituents by adjusted-close return versus 252 trading sessions earlier. Check on the **first successfully observed NYSE trading session each ISO week** (typically Monday). Change target if challenger leads current D target by **at least 5 percentage points**. Later sessions in the same ISO week retain the target. An exchange holiday or a missed Monday run moves the review to the next successful trading session.
- Both are single-stock strategies with potentially very large drawdowns, concentrated risk, taxes and execution slippage.
- Signals are based on closes, *never* same-day tradable at those closing prices.

## Automatic operation
GitHub Actions -> **Champion rotation C/D monitor** -> **Run workflow** for initial run. Runs immediately on merge to the default branch, on relevant code changes, and thereafter at **23:30 UTC Monday–Friday** (after US stock-market close, DST-safe). GitHub scheduled workflows can run late or be skipped; confirm run status. Reads Yahoo Finance data via `yfinance`, scrapes the *current* S&P 500 list, fails closed on missing coverage.

Outputs:
- [latest.md](latest.md) created on first successful run, with Top 10 for each strategy and HOLD/WATCH/TARGET CHANGE.
- [state.json](state.json) remembers target, candidate and confirmation count.
- GitHub Issue on the first INITIAL TARGET or a confirmed TARGET CHANGE; use repo **Watch -> Custom -> Issues** to receive Github notifications. If Issues are disabled or GitHub fails to create an issue, consult the Action log. No email or push delivery is guaranteed.

## Limitations and safety
Current constituent universe introduces historical survivorship bias. Price source may revise adjusted prices. A ticker target is **not** proof of stock ownership. There is no real-money tracking, P&L, liquidity/execution-cost modelling, dividend reinvestment cash accounting, missing-data-adjusted universe or validated backtest. Do not treat reports as recommendations to invest. Strategy C confirmations must correspond to successive completed NYSE sessions. If a scan is missed, the 3-session counter resets. Freshness is checked against the official NYSE trading calendar, and stale price snapshots fail closed. Do not use this code to automate brokerage trades.

## Local run
```bash
pip install -r champion_rotation/requirements.txt
python -m champion_rotation.monitor
```
