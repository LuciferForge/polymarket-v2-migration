# April 28, 2026 — Cutover hour-by-hour

This is what I observed running a live bot through the V1 → V2 cutover. Times are UTC. If you ran a bot during this window, this should help you reconcile what your error logs are showing.

## TL;DR

Polymarket announced a 1-hour cutover. The actual disruption was ~6 hours of mixed states (cancel-only, partial V2, full V2). Bots that aggressively retried during this window racked up 503 errors with no on-chain effect. Bots that backed off cleanly and waited for V2-ready signal resumed without incident.

## The window

| Time (UTC) | State | What worked | What didn't |
|------------|-------|-------------|-------------|
| 11:00 | Cutover begins. Polymarket front-end shows maintenance banner. | Reads (orderbook, balance, market, positions) | New orders (POST /order → HTTP 503 cancel-only) |
| 11:00–13:00 | Pure cancel-only window. V1 contracts paused; V2 not yet active for general traffic. | Cancels of pre-existing V1 orders | New orders, edits |
| 13:00–14:30 | V2 contracts activated for trading **but bots still on V1 SDK kept getting 503**. The V1 SDK was talking to V1 endpoints which were no longer accepting orders. | UI users who'd already migrated their wallet | Any V1 SDK code path posting orders |
| 14:30–16:00 | Mixed state. Some markets routable on V2; others still flapping. | V2 SDK against migrated wallets | V1 SDK; V2 SDK against un-migrated wallets (allowance errors) |
| 16:00 onward | Stable V2. Order posting reliable for migrated wallets. | Everything, on V2 | Anyone still on V1 imports (HTTP 503 / kwarg errors) |

## Pre-existing state at cutover

**Open orders:** All open V1 limit orders were cancelled at 11:00 UTC. If your bot tracked open-order state in its own DB, that DB became stale at 11:00. Re-fetch open orders from the V2 API after migration; don't trust any local cache from before the cutover.

**Open positions:** Untouched. Positions resolve normally on the existing market schedule. The migration only changed the trading layer — settlement and resolution work the same.

**USDC.e balance:** Not auto-migrated. After triggering the migration prompt in the UI (manual trade of ≥5 shares), your USDC.e is wrapped 1:1 into pUSD. The wrap is reversible — pUSD can be unwrapped back to USDC.e at any time via the same UI.

## What the bot saw

Logged errors during the 11:00–16:00 window, by phase:

**Phase 1 (11:00–13:00 — pure cancel-only):**
```
HTTP 503: {"error":"Trading is currently cancel-only. New orders are not accepted, but cancels are allowed."}
```
This was the dominant error. Reads succeeded. POST /order failed.

**Phase 2 (13:00–14:30 — V1 SDK pointing at V1 endpoints, V1 endpoints disabled):**
```
HTTP 503 (same message)
```
Indistinguishable from Phase 1 from the bot's perspective. The fix was: stop retrying, switch SDK, switch wallet allowances, then resume.

**Phase 3 (14:30 onward — V2 SDK against un-migrated wallet):**
```
HTTP 400: {"error":"insufficient allowance for V2 CTF Exchange"}
```
This was the signal that you needed to do the manual UI migration trade. The SDK couldn't trigger it.

## What I did, in order

| Time | Action | Result |
|------|--------|--------|
| 11:05 | Detected first 503. Paused bot via `MAX_ENTRY_PRICE = 0.0` config flag. | Bot stopped firing buys; existing positions kept being monitored. |
| 11:30 | Read [Polymarket V2 announcement](https://x.com/polymarket) and [SDK release notes](https://github.com/Polymarket/py-clob-client-v2). | Confirmed the change list (imports, kwargs, contracts). |
| 12:00 | `pip install py-clob-client-v2` in venv. Did NOT uninstall V1. | Both SDKs available; rollback path preserved. |
| 12:15 | `sed -i '' 's\|from py_clob_client\.\|from py_clob_client_v2.\|g' agents/trader/*.py` | All imports updated. |
| 12:20 | `sed -i '' 's\|orderType="FOK"\|order_type="FOK"\|g' agents/trader/*.py` | Kwarg renamed in 2 places. |
| 12:30 | Ran smoke test: `python -c "from py_clob_client_v2.client import ClobClient; print('ok')"` | Passed. |
| 12:45 | Opened polymarket.com, clicked Trade on a small market, signed migration approvals. Cost ~$0.01 in MATIC gas. | Wallet now holds pUSD; V2 allowances appeared in `get_balance_allowance` response. |
| 13:00 | Manual test: posted a 1-share order, watched it settle on-chain. | Order filled. Migration verified. |
| 14:00 | Resumed bot at half-size (`POSITION_SIZE_USD = 5.0` instead of 10). | First 3 orders went through cleanly. |
| 17:00 | Confirmed 6 hours of clean operation. Returned to normal POSITION_SIZE_USD. | Back to production. |

Total wall time: 4 hours (12:00–16:00 of active work, plus 2 hours of waiting for V2 to stabilize before resuming).

## Lessons

1. **Don't retry blindly.** A bot that retries every 30s for 6 hours through cancel-only mode generates ~720 failed POST requests, fills your error log, and risks rate-limiting. Pause the bot the moment you see the first 503 and read the error message.

2. **Keep both SDKs installed during cutover.** `pip install py-clob-client-v2` does NOT remove the V1 package. If V2 misbehaves, you can revert imports in 30 seconds. After V2 is stable for 24h, uninstall V1.

3. **The UI migration trade is the only allowance trigger.** No SDK call, no manual `update_balance_allowance`, no copying-and-resigning of approvals on Polygonscan will work. You must click Trade in the Polymarket UI on any market for ≥5 shares. Once approved on-chain, it's permanent.

4. **Test with one tiny order before resuming production volume.** A clean manual order through the V2 path proves: SDK works, wallet is migrated, contracts approved, signing flow correct. If that fails, your bot will fail too — debug at the small scale.

5. **Pre-existing positions are unaffected.** If your bot has open positions at cutover, they keep monitoring fine. Only the trade-post path is broken during the window.
