# S1 second round: E1 contracts and E2 gate test run

## Command
`C:\Python314\python.exe -m pytest -q -p no:cacheprovider tests/vst/test_e1_contracts.py tests/vst/test_e2_gate.py`

## Revision
`git rev-parse HEAD` = 5a749ee620cb65fc09ba36575c27d1999dfa215e. The tree is dirty: uncommitted edits to tools/vst/{contracts,gate,runner,slice,store}.py, tests/vst/test_e1_contracts.py, tests/vst/test_e2_gate.py, docs and core files; untracked change records 0019 and 0020. The result proves the working tree, not the commit.

## Result
813 passed, 1 warning (pytest_asyncio DeprecationWarning, unrelated), 3.78 s. Green on the first run; no test or product defects were found.

## Scope of the new and updated tests
- Gate (E2): history attempts at other heads, stale deciding receipt (hard + unmet), all-deciding-stale NO_GO with markers/history, supervisor markers at other heads, terminal markers kept (future epoch) and dropped only for signature/binding failure, artifact checks on the deciding attempt only, artifact keys via the gate, pairwise-distinct keys.
- Contracts (E1): NFKC normalization, Cc/Cf rejection (including trailing newline), principals in receipts and manifests, artifact keys as repo-relative paths.
- Updated: stale head, all-stale reason text, forged+stale (now MODIFY), artifact-rejected slot reason text, principal variants that contained tab/newline.

## Not verified
Mutation behavior (not run by operator decision). E3/E4/E5 files. Product behavior outside these two files. Test-to-contract mapping was reviewed by reading, not by breaking the code.
