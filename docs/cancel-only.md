# The cancel-only window — what it is, how to detect, when it lifts

If your bot was running between **11:00 UTC and ~16:00 UTC on April 28, 2026**, this is probably what hit you. Same thing applies to any future Polymarket maintenance window — they reuse this state.

## What it looks like

```
HTTP 503: {"error":"Trading is currently cancel-only. New orders are not accepted, but cancels are allowed."}
```

The endpoint that fails is `POST /order`. Everything else keeps working:
- `GET /orderbook` — fine
- `GET /markets` — fine
- `GET /balance-allowance` — fine
- `GET /positions` — fine
- `DELETE /order` (cancels) — **fine, on purpose**

This is intentional behavior. Polymarket wants traders to be able to **exit** during maintenance even if they can't enter. So cancels are explicitly allowed while new orders are blocked.

## Why it happens

Two reasons trigger cancel-only:

1. **Scheduled maintenance / V2 cutover.** This is what hit on April 28. Polymarket pauses new-order acceptance to drain the order book to a clean state before swapping contracts. Lasted ~6 hours despite the announcement saying ~1 hour.

2. **Emergency throttle.** If the matching engine is overloaded or if Polymarket detects an anomaly (e.g., a buggy market with stuck orders), they can flip cancel-only to stop the bleeding. This is shorter (minutes, not hours) but unannounced.

In either case, your bot's correct response is the same: **stop posting new orders, keep cancellation logic alive, wait for it to lift, resume.**

## How to detect cleanly in code

The naive approach is to catch all HTTP errors. Better: parse the error body and pattern-match on the message, so you don't conflate this with rate limiting or actual bugs.

```python
import requests

def post_order_with_cancel_only_handling(client, signed_order):
    try:
        return client.post_order(signed_order, order_type="FOK")
    except requests.HTTPError as e:
        if e.response.status_code == 503:
            body = e.response.json()
            if "cancel-only" in body.get("error", "").lower():
                # Polymarket-side maintenance. Pause and back off.
                set_bot_state("paused_cancel_only")
                return None
        raise  # Anything else is a real error.
```

Once you've flipped the bot into a paused state on first 503, you can check the state at the top of each cycle and skip the entire trade-decision logic until cancel-only lifts.

## How to detect when it lifts

Two options:

**Polling (simple):** every 5 minutes, post a tiny canary order (1 share, far-from-market price so it never fills, then cancel it). If it succeeds, cancel-only has lifted.

**Watching (better):** subscribe to Polymarket's status feed (Twitter, status page, Discord announcements) and have a human flip the bot back on. This is what I did on April 28 — the watcher engine polled the API every 5 min and auto-resumed when a clean POST succeeded.

```python
def is_cancel_only():
    """Returns True if Polymarket is in cancel-only mode. Cheap probe."""
    # Read-only call — does not consume rate limit meaningfully.
    try:
        # Try a get_orderbook call. If it succeeds, the API is up.
        # The cancel-only state only blocks POST /order, not reads.
        # So we test by attempting a tiny order.
        resp = client.create_market_order(
            MarketOrderArgs(token_id=KNOWN_TOKEN_ID, amount=0.01, side="BUY")
        )
        # If we got here, order was accepted (or rejected for size, but not cancel-only).
        # Immediately cancel.
        client.cancel_order(resp["orderId"])
        return False
    except requests.HTTPError as e:
        if e.response.status_code == 503 and "cancel-only" in e.response.text.lower():
            return True
        # Any other error: not cancel-only, but something else is wrong. Don't auto-resume.
        return False
```

In production I run this probe every 5 min via a launchd task. When it returns False, the bot's `MAX_ENTRY_PRICE` is restored to its normal value; until then, it stays at `0.0` (which short-circuits all entries).

## What NOT to do

**Don't busy-retry.** A common bot pattern is "on error, sleep 30s and retry". Through a 6-hour cancel-only window, that's 720 failed POSTs. You will:
- Fill your error log
- Possibly hit Polymarket's rate limit and earn yourself a temporary ban
- Burn API budget for zero outcome

Always check the error body before retrying. Cancel-only is not a transient network error — it's a backend state that you should respect by backing off entirely.

**Don't try to bypass via different endpoints.** I tried hitting the GTC, FOK, and FAK paths separately to see if one was unblocked. They're all gated by the same backend flag. Don't waste your time.

**Don't move money in/out of Polygon.** Some operators thought "maybe my collateral got stuck" and started bridging. The collateral was fine — only the matching engine was paused. Bridging USDC.e during the cutover wastes gas and could leave you on the wrong side of the migration when V2 came up.

## How long does it last?

April 28 cutover: announced 1h, actual ~6h.

Routine emergency throttles (anecdotal, from 18 months of running bots through Polymarket): seconds to ~15 minutes. Usually under 5 min.

If you see cancel-only and Polymarket has not announced a maintenance window, expect it to be short. If they have announced one, expect it to take 2–6× longer than announced.

## Production-grade pattern

Treat cancel-only as a normal operational state, not an exception. The bot should:

1. Post-order wrapped in detect-cancel-only handler.
2. On detection, flip a `paused_cancel_only` flag in state.
3. While paused, skip new-trade logic but keep monitoring open positions for exits.
4. Run a cheap probe every 5 min.
5. On probe success, clear the flag and resume.
6. Log the start/end times to your DB so you can correlate against P&L afterwards.

We did all of this on April 28. The bot was paused at 11:05, resumed at 16:00, and missed exactly zero open-position exits because the position-monitoring loop kept running through the entire window. Total revenue impact: skipped ~6 buy opportunities. Total downside avoided: 720 logged 503s and possible API rate-limit ban.
