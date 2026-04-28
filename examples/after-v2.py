#!/usr/bin/env python3
"""V2 — the AFTER code.

Same logic as `before-v1.py`, rewritten for the post-April-28-2026 V2 exchange.

Three changes versus V1:
  1. Import path:        py_clob_client.*  →  py_clob_client_v2.*
  2. post_order kwarg:   orderType="FOK"   →  order_type="FOK"
  3. SDK version pin:    py-clob-client    →  py-clob-client-v2 (>=1.0.0)

Everything else (signing, balance, market-order construction) is identical
because the SDK abstracts the contract addresses and order-field changes.

See `diff.md` for line-by-line annotation.
"""
import os
from py_clob_client_v2.client import ClobClient            # ← V2 import
from py_clob_client_v2.clob_types import (                  # ← V2 import
    ApiCreds,
    BalanceAllowanceParams,
    AssetType,
    MarketOrderArgs,
)
from py_clob_client_v2.constants import POLYGON             # ← V2 import


def make_client():
    creds = ApiCreds(
        api_key=os.environ["POLYMARKET_API_KEY"],
        api_secret=os.environ["POLYMARKET_SECRET"],
        api_passphrase=os.environ["POLYMARKET_PASSPHRASE"],
    )
    return ClobClient(
        host="https://clob.polymarket.com",
        chain_id=POLYGON,
        key=os.environ["POLYMARKET_PRIVATE_KEY"],
        creds=creds,
        funder=os.environ["POLYMARKET_PROXY_ADDRESS"],
        signature_type=2,  # POLY_GNOSIS_SAFE — unchanged
    )


def get_balance(client):
    params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=2)
    return client.get_balance_allowance(params)


def buy_yes(client, token_id: str, amount_usd: float, price: float):
    """Place a market BUY for YES tokens."""
    args = MarketOrderArgs(
        token_id=token_id,
        amount=round(amount_usd, 2),
        side="BUY",
    )
    signed_order = client.create_market_order(args)
    return client.post_order(signed_order, order_type="FOK")  # ← V2 kwarg name


def sell_yes(client, token_id: str, amount_usd: float, price: float):
    """Place a market SELL for YES tokens."""
    args = MarketOrderArgs(
        token_id=token_id,
        amount=round(amount_usd, 2),
        side="SELL",
    )
    signed_order = client.create_market_order(args)
    return client.post_order(signed_order, order_type="FOK")  # ← V2 kwarg name


if __name__ == "__main__":
    client = make_client()
    print(get_balance(client))
