# Polymarket V2 Migration Cookbook

**The complete guide for upgrading your Polymarket trading bot from V1 to V2 (cutover April 28, 2026).**

I migrated [a live-traded crash-recovery bot](https://github.com/LuciferForge/polymarket-crash-bot) (302 closed trades, 79.8% win rate) from V1 to V2 in 4 hours during today's cutover. This repo has the exact code diff, every error I hit, and how I solved each. If you're a developer with a bot that broke this morning — start here.

## TL;DR — What changed and what to do

| Layer | V1 | V2 | Action |
|-------|----|----|--------|
| Python SDK | `py-clob-client v0.34.6` | `py-clob-client-v2 v1.0.0` | `pip install py-clob-client-v2` |
| Import path | `from py_clob_client.X` | `from py_clob_client_v2.X` | Search/replace in all files |
| `post_order` kwarg | `orderType="FOK"` (camelCase) | `order_type=OrderType.FOK` (snake_case) | Rename in 2 places |
| CTF Exchange contract | `0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E` | `0xE111180000d2663C0091e4f400237545B87B996B` | SDK handles automatically once approved |
| NegRisk Exchange | `0xC5d563A36AE78145C45a50134d48A1215220f80a` | `0xe2222d279d744050d28e00520010520000310F59` | Approval needed |
| Collateral token | USDC.e | pUSD (1:1 backed by USDC.e) | One-time on-chain migration |
| Order fields | nonce, feeRateBps, taker | timestamp (ms), metadata, builder | SDK abstracts; only relevant if signing manually |
| Pre-existing open orders | Active | Cancelled at cutover | Re-place after migration |
| Pre-existing positions | Active | Resolve normally | No action |

If your bot is still running V1 imports as of April 28, 2026: **it will fail with HTTP 503 cancel-only or with `orderType` kwarg errors.** This guide tells you how to fix in <1 hour.

## What this repo contains

| File | What it does |
|------|--------------|
| [`examples/before-v1.py`](examples/before-v1.py) | The V1 code (representative of bots in the wild) |
| [`examples/after-v2.py`](examples/after-v2.py) | The same code rewritten for V2 |
| [`examples/diff.md`](examples/diff.md) | Side-by-side diff with line-by-line explanation |
| [`docs/timeline.md`](docs/timeline.md) | Hour-by-hour timeline of the April 28 cutover (cancel-only window, when allowances appeared, etc.) |
| [`docs/allowances.md`](docs/allowances.md) | V1 vs V2 contract addresses + how to detect via API + how to verify your wallet is migrated |
| [`docs/cancel-only.md`](docs/cancel-only.md) | The surprise post-cutover state — what triggers it, how to detect, when it lifts |
| [`docs/troubleshooting.md`](docs/troubleshooting.md) | The 12 specific errors I hit + the exact fix for each |
| [`tests/test_v2_imports.py`](tests/test_v2_imports.py) | Smoke test you can run to verify your migration |

## Quick start: 5-minute migration

1. **Install V2 SDK**
   ```bash
   pip install py-clob-client-v2
   ```
   (Don't uninstall V1 yet — keep it for rollback.)

2. **Search/replace imports** in your bot's code:
   ```bash
   sed -i '' 's|from py_clob_client\.|from py_clob_client_v2.|g' your_bot.py
   ```

3. **Fix `post_order` kwarg** — V2 changed `orderType` (camelCase) → `order_type` (snake_case):
   ```bash
   sed -i '' 's|orderType="FOK"|order_type="FOK"|g' your_bot.py
   ```

4. **Verify your account is migrated** to V2 contracts. Run [`tests/test_v2_imports.py`](tests/test_v2_imports.py) — it checks that V2 contract addresses (`0xE111…` and `0xe2222…`) appear in your `get_balance_allowance` response. If they don't, you need to:
   - Open polymarket.com in a browser
   - Click trade on any market (5+ shares)
   - Sign the migration approvals (USDC.e → pUSD wrap, V2 CTF allowance, V2 NegRisk allowance)
   - Cost: a few cents in Polygon gas

5. **Test with a tiny order before resuming production volume.** Don't unleash your bot on V2 until one manual order has cleanly settled.

## The non-obvious things

**Polymarket entered a "cancel-only" mode for several hours after the announced 1-hour cutover window.** API returned HTTP 503: `{"error":"Trading is currently cancel-only. New orders are not accepted, but cancels are allowed."}`. Reads (orderbook, balance, positions) kept working. New orders failed silently. **If your bot fired into this window, every BUY rejected with no on-chain effect.** Check your bot's error log — if you see 503 between 11:00–17:00 UTC on April 28, that's why.

**Allowances on V2 contracts only appear AFTER you trigger the migration prompt** (i.e., attempt a trade in the Polymarket UI). Just signing into the app does NOT migrate. The `update_balance_allowance()` SDK call also does NOT migrate — it only updates what's already approved. **Manual UI trade is the only way to trigger the wallet signature flow.**

**The slippage problem is unchanged.** V2 fixes nonce-related failed-fill issues but doesn't change order-book depth. If your bot used a price-discount ladder (5%, 15%, 25% off ref price) on TIMEOUT exits, that strategy still walks thin books down. We rewrote ours to be orderbook-aware ([here's how](https://github.com/LuciferForge/polymarket-crash-bot)).

## About the author

[LuciferForge](https://github.com/LuciferForge) — solo operator running a public-audited Polymarket bot ([302 closed trades, 79.8% WR](https://github.com/LuciferForge/polymarket-crash-bot)). Also runs [protodex.io](https://protodex.io) (5,800+ MCP servers indexed) and the [free Polymarket data API](https://api.protodex.io).

If this saved you a few hours, star the repo. If you're stuck on something the docs don't cover, open an issue — happy to help.

## License

MIT. Use it, fork it, ship something.
