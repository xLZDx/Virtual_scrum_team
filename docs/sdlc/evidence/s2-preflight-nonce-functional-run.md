# S2 preflight nonce functional verification

- Story/gate: S2 E5, VST-014 — explicit run/nonce-bound sandbox preflight input validation.
- Product source HEAD: `6ee97cb06b52900c3c2ab2a9b1b415ae117a7932`.
- Test/evidence basis HEAD: `deed6abe34eeaa8620593442bcdb1413d846f798`.
- Platform: Windows; CPython 3.14.3; pytest 8.4.2.
- Exact command:

```text
C:\Python314\python.exe -m pytest -q tests/vst/test_s2_sandbox_probe.py -k "collect_inventory_generates_nonce_only_when_omitted or collect_inventory_preserves_explicit_nonce or collect_inventory_rejects_invalid_explicit_nonce_before_probing"
```

- Result: 4 passed, 22 deselected, 0 failed, in 1.20 seconds.
- Coverage: omitted nonce produces a nonempty string; explicit nonce is preserved; empty and non-string explicit nonces raise `ContractError` before platform or filesystem probing.
- Warning: one pytest-asyncio deprecation warning for `asyncio.get_event_loop_policy`, reported during the passing run.
- Limitations: focused Windows functional evidence only. It does not replace the existing fresh WSL probe acceptance or prove production deployment, OS quotas, process cleanup, or full sandbox acceptance.
- Worktree was clean after the exact-head run.

See detailed change records 0162 (implementation), 0163 (tests), and 0164 (exact-head evidence).
