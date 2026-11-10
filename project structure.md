# Sentinel Repository Structure

```text
sentinel/
├── CLAUDE.md                     # Canonical development instructions
├── AGENTS.md                     # Cross-agent entry point
├── PROGRESS.md                   # Current verified development state
├── feature_list.json             # Machine-readable feature ledger
├── feature_list.schema.json
├── session-handoff.md
├── DECISIONS.md
├── init.sh / init.ps1            # Platform bootstrap wrappers
├── pyproject.toml                # Test and lint configuration
├── requirements.txt
├── .harness/
│   ├── scope.json                # Architecture and role boundaries
│   ├── arch-rules.json
│   └── verification.json
├── scripts/
│   ├── bootstrap.py
│   ├── check_arch.py
│   ├── verify.py
│   └── verify_feature.py
├── config/settings.py
├── src/
│   ├── llm/provider.py
│   ├── tools/registry.py
│   ├── harness/                  # Sentinel runtime harness
│   ├── agents/
│   ├── security/
│   ├── memory/
│   ├── healing/
│   ├── orchestrator/
│   ├── pipeline/
│   ├── integrations/
│   └── mcp/
├── tests/                        # Deterministic offline verification
├── evals/                        # Provider-backed acceptance evaluations
├── skills/
├── cli/sentinel.py
├── dashboard/app.py
├── docs/
│   └── development/
└── .github/workflows/
    ├── ci.yml
    ├── live-evals.yml
    └── sentinel-fix.yml
```

`.harness/` controls external development work; `src/harness/` is product code.
`.venv/` is the canonical environment. The legacy `harness/` virtual environment
is ignored and should be removed only after the Python 3.11.9 environment is
confirmed healthy.
