# PHASES

## Phase 0 — Scaffold
- [x] `uv init --lib`, Python 3.12, `uv_build`, ruff `ALL`, pytest, branch coverage config
- [x] CLAUDE.md, PHASES.md, README.md, LICENSE
- [x] Name chosen: `pyaggregate` is taken on PyPI, so the package is `pyaggregation`

## Phase 1 — Design (written only)
- [x] `docs/DESIGN.md`: `Fold`, `Aggregate`, `Report`, built-ins (`total`, `count`, `average`, `share`, `minimum`, `maximum`), empty-input rules, `Decimal` handling, JSON shape
- [x] Author confirms a real project needs it (gate for Phase 2): "Yes, build it", 2026-11-11

## Phase 2 — Core
- [x] Folds, `Report` with `&`, one-pass evaluation, `group_by`

## Phase 3 — Compiler and schema
- [ ] Report compiler delegating `of`/`where` to injected compilers; JSON Schema

## Phase 4 — Release
- [ ] GitHub repository, CI, PyPI

## Later
- [ ] SQL compiler (SQLAlchemy `func.sum`, `FILTER`, `GROUP BY`)
