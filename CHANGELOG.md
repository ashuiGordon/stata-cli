# Changelog

All notable changes to this project will be documented in this file.

## [0.5.1] - 2026-05-19

### Improved
- Updated README, README.zh, and website with parallel session documentation
- Fixed socket leak in `_find_free_port` on Windows

## [0.5.0] - 2026-05-19

### Added
- Multi-session daemon support: `--session <name>` global option for running parallel Stata instances
  - `stata-cli --session proj_a daemon start` — start a named session
  - `stata-cli --session proj_a run "use data.dta"` — route commands to specific session
  - `stata-cli daemon status` — list all running sessions
  - `stata-cli daemon stop --all` — stop all sessions at once
- Each session has independent state (data, estimates, macros) — like opening multiple Stata windows

## [0.4.2] - 2026-05-15

### Fixed
- `stata-cli skill <topic> --compact` no longer errors — skill command now ignores unknown options (agents frequently pass global flags like `--compact` after the subcommand)

## [0.4.1] - 2026-05-15

### Improved
- `stata-cli --help` now shows actionable skill description: "57 topics, use 'skill --list' to browse" (improves agent discoverability)

## [0.4.0] - 2026-05-15

### Added
- `stata-cli skill` — built-in Stata reference library with 57 topics
  - 37 core references: regression, panel data, DiD, RD, matching, time series, Mata, etc.
  - 20 community package guides: reghdfe, estout, csdid, rdrobust, psmatch2, etc.
  - `stata-cli skill` shows overview with gotchas, common patterns, and routing table
  - `stata-cli skill --list` lists all topics grouped by category
  - `stata-cli skill <topic>` outputs detailed reference (aliases supported: `did`, `regression`, `panel`, etc.)
- Integrated reference content from [stata-skill](https://github.com/dylantmoore/stata-skill) (MIT license)

## [0.3.0] - 2026-05-13

### Added
- `stata-cli return r/e/s` — retrieve stored r(), e(), s() results as structured JSON
- `stata-cli vars` — inspect variable metadata (name, type, format, label)
- `stata-cli matrix` — read Stata matrices (e.g. `e(b)`, `e(V)`) as JSON
- `stata-cli labels` — list and inspect value labels
- `stata-cli macro get/set` — access Stata macros including `c()`, `e()`, `r()` system macros
- `stata-cli frame` — list Stata frames and current working frame
- `--graph-format png|svg|pdf` global option for graph export format
- `--log PATH` global option for saving output to a log file
- Full daemon support for all new commands

### Changed
- Split `run()` execution to capture r/e/s results via sfi before log close
- Python requirement lowered to >=3.9 (with `from __future__ import annotations`)

## [0.2.2] - 2026-05-12

### Fixed
- Python 3.10+ requirement (use native `str | None` syntax)
- npm package.json bin path fixed

## [0.2.1] - 2026-05-12

### Fixed
- Python 3.9 compatibility (`from __future__ import annotations`)

## [0.2.0] - 2026-05-12

### Added
- `stata-cli run` — execute inline Stata code or pipe from stdin
- `stata-cli do` — execute .do files with `///` continuation and graph auto-naming
- `stata-cli data` — view current dataset as JSON with `if`-condition filtering
- `stata-cli help` — browse Stata help with SMCL-to-plain-text conversion
- `stata-cli stop` — interrupt running Stata commands
- `stata-cli detect` — auto-detect Stata installation path
- `stata-cli daemon start/stop/status/restart` — daemon mode for sub-second execution
- `--compact` mode for reduced output noise
- `--json` mode for structured JSON output
- `--max-tokens` for output token limit management
- Graph auto-detection and PNG export
- npm wrapper (`npx stata-cli`)
