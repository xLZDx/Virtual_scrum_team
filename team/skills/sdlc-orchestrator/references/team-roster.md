# Team roster (virtual scrum team)

Single list of who is on the team, which phase they serve, and the exact agent file that runs the role. `adk-*` names are role aliases from the operator's workflow; no agent file with those names exists, so they are mapped to real agents and must be launched under the real name.

## Authoring roles (phases 1-4, 9-10)
| Role | Agent | Phase |
|---|---|---|
| Business analyst | `business-analyst` | 1 |
| Product owner | `product-owner` | 2, 9 |
| UI designer | `ui-designer` | 3 |
| Technical writer | `technical-writer` | 4, 9 |
| Reporting | `reporting-analyst` | 10 |
| Architect | `architect` (system), `code-architect` (feature) | 3 |
| Developer | `implementation-engineer` | 6 |

## Test and review roles (phases 4-8)
| Operator name | Real agent (+ skills) | Duty |
|---|---|---|
| `adk-test-engineer` (alias, role test-engineer) | `tdd-guide` | Advisory only: test-first coaching and test-quality review; does NOT author or execute required tests (ADR-0001) |
| `adk-test-engineer` (E2E, Playwright) | `e2e-runner` + skill `e2e-testing-contract` | Writes and runs E2E journeys for every epic |
| `adk-test-engineer` (test assessment) | `functional-test-reviewer` + skill `functional-testing` | Acceptance-to-test map; authors and runs focused functional tests; judges whether tests can fail |
| `adk-data-engineer/perf-tuning` (alias) | `performance-optimizer` + skill `performance-testing` | Advisory data/perf-tuning analysis when a hot path or data pipeline changed; does NOT author or execute required tests (ADR-0001) |
| `adk-tune-sql-query` (alias, confirmed by operator 2026-10-15) | `database-reviewer` + skills `db-change-contract`, `performance-testing` | Query plans, SQL tuning, schema and migration review |
| `silent-failure-hunter` | `silent-failure-hunter` | Swallowed errors, false success, unobserved failures |
| `database-reviewer` | `database-reviewer` | Schema, transactions, locks, migrations |
| `code-explorer` | `code-explorer` | Traces the real execution path before changing unfamiliar code (phase 3 and 6 prep) |
| `build-error-resolver` | `build-error-resolver` | Fixes build/type failures that tests or the implementer surface |
| `refactor-cleaner` | `refactor-cleaner` | Dead code/duplicate cleanup on a green tree, never mid-feature |
| `doc-updater` | `doc-updater` | Syncs existing docs with code after changes |
| `python-reviewer` | `python-reviewer` | Python-specific correctness review |
| `code-reviewer` | `code-reviewer` | Final integrated diff review |

Select only the roles relevant to the sprint's risks (delivery-efficiency v4 section 4). Reviewer runs use only Sonnet 5.5 medium or GPT-5.6 Luna low/medium; never GPT-5.6 Sol; no model substitution.
