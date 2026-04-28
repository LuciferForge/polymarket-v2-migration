#!/usr/bin/env python3
"""V2 migration smoke test.

Run this after migrating to verify:
  1. py_clob_client_v2 imports cleanly
  2. Your env-vars are set
  3. Your wallet has V2 contract allowances (i.e., the UI migration was completed)

Usage:
    python tests/test_v2_imports.py

Exit code 0 on success, 1 on any failure with diagnostic output.

Requires:
    pip install py-clob-client-v2
    POLYMARKET_API_KEY, POLYMARKET_SECRET, POLYMARKET_PASSPHRASE,
    POLYMARKET_PRIVATE_KEY, POLYMARKET_PROXY_ADDRESS env-vars
"""
import os
import sys

V2_CTF_EXCHANGE = "0xE111180000d2663C0091e4f400237545B87B996B"
V2_NEGRISK_EXCHANGE = "0xe2222d279d744050d28e00520010520000310F59"
V1_CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
V1_NEGRISK_EXCHANGE = "0xC5d563A36AE78145C45a50134d48A1215220f80a"


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def ok(msg: str) -> None:
    print(f"OK:   {msg}")


def step_1_imports():
    """Test that V2 SDK is installed and imports cleanly."""
    try:
        from py_clob_client_v2.client import ClobClient
        from py_clob_client_v2.clob_types import (
            ApiCreds,
            BalanceAllowanceParams,
            AssetType,
            MarketOrderArgs,
        )
        from py_clob_client_v2.constants import POLYGON
    except ImportError as e:
        fail(f"V2 SDK not installed or broken: {e}\n      Run: pip install py-clob-client-v2")
    ok("py_clob_client_v2 imports cleanly")


def step_2_env_vars():
    """Test that all required env-vars are set."""
    required = [
        "POLYMARKET_API_KEY",
        "POLYMARKET_SECRET",
        "POLYMARKET_PASSPHRASE",
        "POLYMARKET_PRIVATE_KEY",
        "POLYMARKET_PROXY_ADDRESS",
    ]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        fail(f"Missing env-vars: {', '.join(missing)}")
    ok("All required env-vars are set")


def step_3_client_construction():
    """Test that the client can be constructed."""
    from py_clob_client_v2.client import ClobClient
    from py_clob_client_v2.clob_types import ApiCreds
    from py_clob_client_v2.constants import POLYGON

    creds = ApiCreds(
        api_key=os.environ["POLYMARKET_API_KEY"],
        api_secret=os.environ["POLYMARKET_SECRET"],
        api_passphrase=os.environ["POLYMARKET_PASSPHRASE"],
    )
    try:
        client = ClobClient(
            host="https://clob.polymarket.com",
            chain_id=POLYGON,
            key=os.environ["POLYMARKET_PRIVATE_KEY"],
            creds=creds,
            funder=os.environ["POLYMARKET_PROXY_ADDRESS"],
            signature_type=2,
        )
    except Exception as e:
        fail(f"ClobClient construction failed: {e}")
    ok("V2 ClobClient constructed successfully")
    return client


def step_4_balance_allowance(client):
    """Test that balance/allowance call works and references V2 contracts."""
    from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType

    try:
        resp = client.get_balance_allowance(
            BalanceAllowanceParams(
                asset_type=AssetType.COLLATERAL,
                signature_type=2,
            )
        )
    except Exception as e:
        fail(f"get_balance_allowance failed: {e}")

    balance = int(resp.get("balance", 0))
    allowances = resp.get("allowances", {})
    if isinstance(allowances, dict):
        allowance_addrs = [a.lower() for a in allowances.keys()]
    elif isinstance(allowances, list):
        allowance_addrs = [str(a).lower() for a in allowances]
    else:
        allowance_addrs = []

    print(f"      balance: {balance / 1e6:.4f} pUSD")
    print(f"      allowance contract addresses observed: {allowance_addrs}")

    has_v2_ctf = any(V2_CTF_EXCHANGE.lower() in a for a in allowance_addrs)
    has_v2_negrisk = any(V2_NEGRISK_EXCHANGE.lower() in a for a in allowance_addrs)
    has_v1_only = (
        any(V1_CTF_EXCHANGE.lower() in a for a in allowance_addrs)
        and not has_v2_ctf
    )

    if has_v1_only:
        fail(
            "Wallet has V1 allowances but no V2 — migration UI flow not yet completed.\n"
            "      Go to polymarket.com, click Trade on any market (≥5 shares),\n"
            "      sign all 3 approvals."
        )

    if not (has_v2_ctf or has_v2_negrisk):
        fail(
            "No V2 contract addresses found in allowance response.\n"
            "      This means your wallet has not been migrated to V2.\n"
            "      Open polymarket.com, click Trade on any market with ≥5 shares,\n"
            "      and sign the 3 migration approvals."
        )

    if has_v2_ctf:
        ok(f"V2 CTF Exchange allowance present ({V2_CTF_EXCHANGE})")
    if has_v2_negrisk:
        ok(f"V2 NegRisk Exchange allowance present ({V2_NEGRISK_EXCHANGE})")

    if balance == 0:
        print(
            "WARN: pUSD balance is zero. Migration is signed but you have no\n"
            "      collateral to trade with. Top up via polymarket.com or\n"
            "      bridge USDC.e and let the wrap happen on next trade."
        )


def main():
    print("Polymarket V2 migration smoke test")
    print("=" * 50)
    step_1_imports()
    step_2_env_vars()
    client = step_3_client_construction()
    step_4_balance_allowance(client)
    print("=" * 50)
    print("All checks passed. Your bot is V2-ready.")


if __name__ == "__main__":
    main()
