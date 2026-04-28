# Changelog

All notable changes to this cookbook will be documented in this file.

## [v1] - 2026-04-28

### Added
- Initial cookbook published the day of the Polymarket V1 → V2 cutover.
- Working code: `examples/before-v1.py`, `examples/after-v2.py`, `examples/diff.md`.
- Hour-by-hour `docs/timeline.md` of the cutover (11:00 UTC – 17:00 UTC).
- `docs/allowances.md` — V1 vs V2 contract addresses and the only working wallet-migration method (manual UI trade ≥5 shares).
- `docs/cancel-only.md` — detection, retry-storm avoidance, when it lifts.
- `docs/troubleshooting.md` — 12 specific errors I personally hit + the exact fix for each.
- `tests/test_v2_imports.py` — smoke test verifying V2 SDK is installed AND wallet has V2 contract allowances.

### Notes
- This cookbook is documentation-only — no PyPI distribution.
- Author: solo operator running [polymarket-crash-bot](https://github.com/LuciferForge/polymarket-crash-bot) (308 closed trades, 80.2% WR).
- Bot was migrated live during the April 28, 2026 cutover. Total wall time: ~4 hours.
