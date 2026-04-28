# Allowances & contract addresses

This is the part of the migration that took me the longest because the docs gave conflicting signals. Here's what's actually true after watching it work end-to-end.

## The contract changes

| Component | V1 Address | V2 Address |
|-----------|-----------|-----------|
| CTF Exchange (binary markets) | `0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E` | `0xE111180000d2663C0091e4f400237545B87B996B` |
| NegRisk Exchange (multi-outcome) | `0xC5d563A36AE78145C45a50134d48A1215220f80a` | `0xe2222d279d744050d28e00520010520000310F59` |
| Collateral token | USDC.e (`0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174`) | pUSD (1:1 backed by USDC.e) |
| CTF (conditional tokens framework) | `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045` | unchanged |

The CTF (conditional tokens framework) — the contract that mints YES/NO outcome tokens — is unchanged. Only the **exchange** contracts (the matching/settlement layer) and the **collateral token** changed.

## Three approvals you need

For your wallet to trade on V2, three on-chain approvals must exist:

1. **pUSD wrap approval** — your wallet must let the pUSD wrapper contract pull USDC.e to mint pUSD.
2. **V2 CTF Exchange allowance** — the exchange must be able to move your pUSD and your CTF outcome tokens.
3. **V2 NegRisk Exchange allowance** — same as above, for multi-outcome markets.

All three are signed in a single UI flow when you trigger the migration.

## How to check programmatically

The SDK exposes a `get_balance_allowance` call that returns a structured response. After migration, this response should reference the V2 contract addresses, not the V1 ones.

```python
from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType

client = make_client()  # see examples/after-v2.py
resp = client.get_balance_allowance(
    BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=2)
)
print(resp)
```

A migrated wallet returns something like (illustrative):
```python
{
    "balance": "143000000",
    "allowances": {
        "0xE111180000d2663C0091e4f400237545B87B996B": "115792089237316195423570985008687907853269984665640564039457584007913129639935",
        "0xe2222d279d744050d28e00520010520000310F59": "115792089237316195423570985008687907853269984665640564039457584007913129639935"
    },
    "asset": "pUSD",
}
```

If the addresses listed are the V1 ones (`0x4bFb…` / `0xC5d5…`), you have not yet migrated.

If `allowances` is empty `{}`, the SDK is hitting V2 endpoints but your wallet has no V2 approvals — the migration UI flow has not been completed.

## How to migrate (the only working method)

You **cannot** complete this from a script. Polymarket requires the wallet signature flow to happen through their UI. Here's the step-by-step:

1. Open `polymarket.com` in a browser. Connect the same wallet your bot uses.
2. Click **Trade** on any open market.
3. Set the trade size to **at least 5 shares** (Polymarket's minimum to trigger the full approval bundle).
4. Click **Buy** or **Sell**. A wallet popup appears with **3 sequential signatures**:
   - **Signature 1: USDC.e → pUSD wrap.** Approves the pUSD wrapper contract to move your USDC.e.
   - **Signature 2: V2 CTF Exchange allowance.** Approves the V2 binary-markets exchange.
   - **Signature 3: V2 NegRisk Exchange allowance.** Approves the V2 multi-outcome exchange.
5. After all three sign, the trade itself executes. You now own ≥5 shares of whatever you bought.
6. **Verify on-chain (optional but reassuring):** open Polygonscan, look up your wallet, and check that the pUSD contract and both V2 exchange contracts appear in your token-approvals list.

Total cost: roughly 0.1 MATIC gas (a few cents). The signature flow takes about 60 seconds.

## What does NOT work

I tried each of these because the docs hinted they might work. None of them do.

- **`update_balance_allowance()` from the SDK** — only refreshes the SDK's view of existing allowances. Does not create new ones.
- **Manually approving the V2 contracts on Polygonscan** — you can do it, but Polymarket's order-posting will still reject your orders because the pUSD wrap signature is also required, and that one happens through their wrapper contract.
- **Signing into the Polymarket UI without trading** — login alone does not trigger the migration flow. You have to click Buy/Sell on a real market.
- **Trading <5 shares** — Polymarket gates the migration prompt behind a minimum. Below the threshold, the trade is rejected with a "minimum size" error before signatures are requested.

## Multi-wallet operators

If you operate multiple proxy-wallet addresses (one per bot, separate funder addresses, etc.), **each one must do its own migration UI flow**. There is no batched migration.

I had two wallets to migrate. Each took its own ~60 seconds + a few cents of gas. Plan for one round-trip per wallet.

## After migration: ongoing operations

Once migrated, V2 trading is a no-op compared to V1 from the bot's perspective. Your code calls `post_order`, the SDK signs against the V2 contracts, the matching engine fills.

USDC.e ↔ pUSD wrap/unwrap is reversible. The pUSD wrapper contract has an `unwrap` function callable any time. If you decide to off-ramp, unwrap to USDC.e first, then bridge or sell as before.

## Reference: useful URLs

- pUSD contract on Polygonscan: search "Polymarket USD" — auto-resolves to the V2 collateral.
- V2 CTF Exchange: `https://polygonscan.com/address/0xE111180000d2663C0091e4f400237545B87B996B`
- V2 NegRisk Exchange: `https://polygonscan.com/address/0xe2222d279d744050d28e00520010520000310F59`
- V2 SDK source: `https://github.com/Polymarket/py-clob-client-v2`
