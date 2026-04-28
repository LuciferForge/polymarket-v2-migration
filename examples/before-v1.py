#!/usr/bin/env python3
"""V1 — the BEFORE code.

This is representative of any Polymarket trading bot built before April 28, 2026.
It will fail with HTTP 503 cancel-only or `orderType` kwarg errors after the V2 cutover.

See `after-v2.py` for the post-migration version and `diff.md` for the explanation.
"""
import os
from py_clob_client.client import ClobClient            # ← V1 import
from py_clob_client.clob_types import (                  # ← V1 import
    ApiCreds,
    BalanceAllowanceParams,
    AssetType,
    MarketOrderArgs,
)
from py_clob_client.constants import POLYGON             # ← V1 import


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
        signature_type=2,  # POLY_GNOSIS_SAFE
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
    return client.post_order(signed_order, orderType="FOK")  # ← V1 kwarg name


def sell_yes(client, token_id: str, amount_usd: float, price: float):
    """Place a market SELL for YES tokens."""
    args = MarketOrderArgs(
        token_id=token_id,
        amount=round(amount_usd, 2),
        side="SELL",
    )
    signed_order = client.create_market_order(args)
    return client.post_order(signed_order, orderType="FOK")  # ← V1 kwarg name


if __name__ == "__main__":
    client = make_client()
    print(get_balance(client))
