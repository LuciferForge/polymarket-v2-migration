# V1 → V2 line-by-line diff

This is the annotated diff between [`before-v1.py`](before-v1.py) and [`after-v2.py`](after-v2.py). Three changes total. Everything else is identical.

## The diff

```diff
- from py_clob_client.client import ClobClient
- from py_clob_client.clob_types import (
+ from py_clob_client_v2.client import ClobClient
+ from py_clob_client_v2.clob_types import (
      ApiCreds,
      BalanceAllowanceParams,
      AssetType,
      MarketOrderArgs,
  )
- from py_clob_client.constants import POLYGON
+ from py_clob_client_v2.constants import POLYGON
  ...
- return client.post_order(signed_order, orderType="FOK")
+ return client.post_order(signed_order, order_type="FOK")
```

That's it. Three `import` rewrites and two kwarg renames.

## What changed and why

### 1. Import path: `py_clob_client` → `py_clob_client_v2`

Polymarket shipped V2 as a **separate package** rather than overwriting V1. This is good — it means you can install both and roll back if V2 misbehaves.

```bash
pip install py-clob-client-v2  # adds V2; doesn't remove V1
```

The package internals (auth, signing, market-order builder, balance-allowance) are mostly identical. The reason for the rename is that V2 swaps the underlying contract addresses (CTF Exchange and NegRisk Exchange) for new V2 deployments, and Polymarket wanted a clean break to avoid silent footguns.

If you're wondering "couldn't they have version-gated this?" — yes, but a parallel package lets bots be migrated incrementally rather than via a big-bang upgrade. Pragmatic call.

### 2. `post_order` kwarg: `orderType` (camelCase) → `order_type` (snake_case)

The V2 SDK adopted PEP-8 naming throughout. `post_order` was the most-used method that broke this — it accepts an order type (FOK, GTC, GTD, FAK) telling the matching engine how to handle the order.

This is the change most likely to bite you. If you grep your code for `orderType=`, you'll find every spot that needs updating. We had two — one for buy, one for sell.

```python
# V1
client.post_order(signed_order, orderType="FOK")

# V2
client.post_order(signed_order, order_type="FOK")
```

If you forget to change this, V2 raises `TypeError: post_order() got an unexpected keyword argument 'orderType'`. It is loud, not silent — that's a small mercy.

### 3. SDK contract addresses (handled automatically)

Under the hood, V2 also points at new on-chain contracts:

| Contract | V1 | V2 |
|----------|----|----|
| CTF Exchange | `0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E` | `0xE111180000d2663C0091e4f400237545B87B996B` |
| NegRisk Exchange | `0xC5d563A36AE78145C45a50134d48A1215220f80a` | `0xe2222d279d744050d28e00520010520000310F59` |
| Collateral | USDC.e | pUSD (1:1 backed) |

You don't change these in code — the SDK has them baked in. But your **wallet allowances** must be updated so the V2 contracts can move your collateral. The SDK can't do this for you; it requires an on-chain signature flow which is only triggered by a manual UI trade. See [`docs/allowances.md`](../docs/allowances.md) for the exact procedure.

## What did NOT change

- `signature_type=2` (POLY_GNOSIS_SAFE) — still correct for the funded-proxy flow most bots use
- `MarketOrderArgs(token_id, amount, side)` — same constructor
- `BalanceAllowanceParams(asset_type, signature_type)` — same fields
- `chain_id=POLYGON` — still chain 137
- `host="https://clob.polymarket.com"` — same endpoint
- Order-book reading (`get_order_book`, `get_market`, etc.) — unchanged

If you only do balance-checks and orderbook-reads, V2 is a near-zero-risk upgrade. The trade post path is where the kwarg change can break you.

## Manual signing (advanced)

If you bypass the SDK and sign EIP-712 orders yourself (e.g., a Rust bot, a Go bot, or a custom signer service), V2 changed the order struct:

| V1 fields | V2 fields |
|-----------|-----------|
| salt | salt |
| maker | maker |
| signer | signer |
| taker | (removed) |
| tokenId | tokenId |
| makerAmount | makerAmount |
| takerAmount | takerAmount |
| expiration | expiration |
| nonce | (removed) |
| feeRateBps | (removed) |
| side | side |
| signatureType | signatureType |
| (—) | timestamp (uint256, ms) |
| (—) | metadata (bytes32) |
| (—) | builder (address) |

The dropped fields (`nonce`, `feeRateBps`, `taker`) were sources of failed-fill bugs in V1. The new `timestamp` field is millisecond-precision and helps the matching engine deduplicate. The `builder` field is for revenue-sharing with order-flow integrators.

If you're using the SDK, all of this is handled for you. If you're hand-rolling EIP-712, update your typed-data schema accordingly.

## Verifying the migration in your code

Run [`tests/test_v2_imports.py`](../tests/test_v2_imports.py) — it imports `py_clob_client_v2`, instantiates the client with your env-vars, and confirms the V2 contract addresses appear in the balance-allowance response. If the test passes, you're on V2.
