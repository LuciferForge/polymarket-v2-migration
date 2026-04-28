# Troubleshooting — the 12 errors I hit and the exact fix for each

Every error in this doc is one I hit personally during the April 28 cutover. They are listed in roughly the order you'll encounter them as you migrate.

## 1. `ModuleNotFoundError: No module named 'py_clob_client_v2'`

**Cause:** V2 SDK not installed.

**Fix:**
```bash
pip install py-clob-client-v2
```

If you use a venv, make sure you're installing into the right one. If you use `pip3`, use that. If your bot runs under launchd or systemd, the system Python may not be the same as your shell Python — check the `ProgramArguments` interpreter path.

---

## 2. `TypeError: post_order() got an unexpected keyword argument 'orderType'`

**Cause:** You updated imports to V2 but missed the kwarg rename. V2 uses `order_type` (snake_case), V1 used `orderType` (camelCase).

**Fix:** grep your bot for `orderType=` and replace all with `order_type=`.

```bash
grep -rn 'orderType=' .
sed -i '' 's|orderType="FOK"|order_type="FOK"|g' your_bot.py
sed -i '' 's|orderType="GTC"|order_type="GTC"|g' your_bot.py
sed -i '' 's|orderType="GTD"|order_type="GTD"|g' your_bot.py
sed -i '' 's|orderType="FAK"|order_type="FAK"|g' your_bot.py
```

(Use `-i ''` on macOS, `-i` without quotes on Linux.)

---

## 3. `HTTPError 503: Trading is currently cancel-only`

**Cause:** Polymarket's matching engine is in maintenance / cutover mode. Not a bot bug.

**Fix:** Pause the bot, wait. See [`cancel-only.md`](cancel-only.md) for detection and auto-resume patterns.

---

## 4. `HTTPError 400: insufficient allowance for V2 CTF Exchange`

**Cause:** Your wallet has not yet completed the V2 migration UI flow. SDK is correctly hitting V2 endpoints, but the on-chain allowance for the V2 contract address doesn't exist on your wallet.

**Fix:** Go to polymarket.com, click Trade on any market, sign the migration approvals. See [`allowances.md`](allowances.md). You **cannot** fix this from a script.

---

## 5. `HTTPError 400: minimum order size 5 shares`

**Cause:** You're trying to migrate by trading <5 shares.

**Fix:** Use ≥5 shares for the migration trade specifically. Once allowances are signed, you can place smaller orders programmatically (subject to Polymarket's usual minimums).

---

## 6. `Decimal precision mismatch on amount`

**Cause:** V2 SDK is stricter about amount precision in `MarketOrderArgs`. V1 silently rounded; V2 raises if the amount has more than 2 decimal places.

**Fix:** wrap your amount in `round(amount_usd, 2)` before passing to `MarketOrderArgs`. This is what `examples/after-v2.py` does.

```python
args = MarketOrderArgs(
    token_id=token_id,
    amount=round(amount_usd, 2),  # <-- add the round()
    side="BUY",
)
```

---

## 7. `KeyError: 'POLYMARKET_PROXY_ADDRESS'`

**Cause:** Same env-var issue as V1. The funder address is your **proxy** wallet, not your EOA. V2 didn't change this — I'm including it because it's the most common configuration mistake people make on a first migration.

**Fix:** in your `.env`:

```
POLYMARKET_PRIVATE_KEY=<your EOA private key>
POLYMARKET_PROXY_ADDRESS=<your proxy address — get this from polymarket.com profile>
```

Do NOT use the EOA address as the funder. Polymarket uses a Gnosis Safe proxy for trading; the funder is the proxy.

---

## 8. `503 + retry storm fills error log to GB`

**Cause:** Naive retry loop didn't recognize cancel-only state, kept retrying every N seconds for hours.

**Fix:** see [`cancel-only.md`](cancel-only.md). Pattern-match on the error body. Set a paused flag. Only retry on a slow probe schedule, not in the hot path.

---

## 9. `Order accepted but no on-chain effect`

**Cause:** Order was accepted by V2 matching engine but failed to settle because your wallet's pUSD balance was zero (still all in USDC.e). The matching engine accepted the order optimistically; settlement failed silently.

**Fix:** verify pUSD balance is non-zero after migration. If your wallet shows USDC.e but no pUSD, the migration trade didn't actually wrap — re-run the UI flow.

```python
resp = client.get_balance_allowance(
    BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=2)
)
assert int(resp["balance"]) > 0, "pUSD balance is zero — migration incomplete"
```

---

## 10. `Slippage cost spiked after V2 migration`

**Cause:** Not actually V2's fault. Order-book depth is unchanged. But people often run their first post-migration trades at the same parameters they used pre-migration, when their existing markets had more depth than they now do (because the cutover thinned active book participation for hours).

**Fix:** for the first 24h post-migration, scale down position size and use orderbook-aware exit logic (compute max-shares-sellable-within-N%-of-mid before sizing the order). Don't rely on a fixed-discount ladder — it walks thin books down. We rewrote our exit ladder for this; the diff is in the [polymarket-crash-bot repo](https://github.com/LuciferForge/polymarket-crash-bot).

---

## 11. `Pre-existing open orders missing from V2`

**Cause:** All V1 open orders were cancelled at the cutover (11:00 UTC April 28). They are not retrievable.

**Fix:** if your bot maintained open-order state in its own DB, treat all open-order rows as stale at cutover time. Re-place orders post-migration if still relevant. Don't try to "reconcile" the old V1 IDs with V2 — they're gone.

---

## 12. `Position not visible in /positions endpoint`

**Cause:** This one took me 30 minutes to chase. Pre-existing positions are still on V1 contracts — the CTF (conditional tokens framework) is unchanged, so your shares didn't move. But the V2 SDK's `/positions` endpoint sometimes lags showing them in the first hour after migration.

**Fix:** wait 10–60 minutes. Or hit the on-chain CTF contract directly:

```python
# CTF position for a specific token_id, owner = your proxy address
# This bypasses the API entirely and reads from the chain.
from web3 import Web3
w3 = Web3(Web3.HTTPProvider("https://rpc.ankr.com/polygon"))
ctf = w3.eth.contract(
    address="0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",  # CTF (unchanged in V2)
    abi=ctf_abi,
)
balance = ctf.functions.balanceOf(YOUR_PROXY_ADDRESS, int(token_id)).call()
print(f"On-chain shares: {balance / 1e6}")
```

If `balance > 0`, your position exists. If the API is showing zero but the chain shows non-zero, it's an API lag — don't panic, don't double-buy.

---

## Things I expected to break that didn't

- **API key rotation** — V2 accepts the same API keys you generated under V1. No re-auth needed.
- **Reading market data** — orderbooks, prices, stats endpoints all worked normally throughout the cutover.
- **Cancel orders** — worked even during cancel-only mode (by design).
- **Webhook subscriptions** — same as before, just point at V2 endpoint URLs if you used the V1 ones explicitly.

---

## When in doubt

Read the actual error body. V2's error messages are notably more useful than V1's — they tell you which contract is missing approval, which kwarg is wrong, which size is below threshold. The error message is usually the answer.

If you find a 13th error not in this list, [open an issue](https://github.com/LuciferForge/polymarket-v2-migration/issues) — happy to add it.
