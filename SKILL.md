---
name: stata-cli
description: >-
  Run Stata commands, .do files, view data, inspect results, and get help from
  the terminal. Wraps PyStata with a daemon mode for fast execution. Built-in
  Stata reference library with 57 topics. Designed for AI agents.
---

# stata-cli

Run Stata code, `.do` files, view data, retrieve stored results, inspect
matrices — all from the command line. Designed for AI agent tool-use via
`Bash`. Includes a daemon mode for sub-second execution and a built-in
Stata reference library.

## Install

```bash
pip install stata-cli
```

Requires **Stata 17+** installed on the machine (provides PyStata).

## Critical Gotchas

These are Stata-specific pitfalls that lead to silent bugs. Internalize before writing code.

- **Missing values sort to +infinity** — `if income > 50000` includes missing! Use `if income > 50000 & !missing(income)`
- **`=` vs `==`** — `=` is assignment, `==` is comparison. `gen x = 1 if y = 1` is wrong.
- **Local macro syntax** — backtick + single-quote: `` `name' ``. Forgetting the closing `'` is the #1 macro bug.
- **`by` requires sort** — use `bysort id:` instead of `by id:`.
- **Factor variables** — use `i.race` for categorical. Bare `race` treats categories as continuous.
- **Always check `_merge`** — `tab _merge` after every `merge`.
- **`e()` results overwrite** — a new estimation command wipes previous `e()`. Use `estimates store`.

For full gotchas and patterns: `stata-cli skill`

## Commands

### Run code

```bash
stata-cli run "sysuse auto, clear"
stata-cli run "sysuse auto, clear
regress price mpg weight"
echo "display 42" | stata-cli run -
```

### Run a .do file

```bash
stata-cli do analysis.do
```

### View data

```bash
stata-cli data
stata-cli data --if "price>5000" --rows 50
```

### Retrieve stored results

```bash
stata-cli return r         # r() results (after summarize, etc.)
stata-cli return e         # e() results (after regress, etc.)
stata-cli return s         # s() results
```

### Variable metadata

```bash
stata-cli vars                # all variables
stata-cli vars price mpg      # specific variables
```

### Read matrices

```bash
stata-cli matrix e(b)         # coefficient vector
stata-cli matrix e(V)         # variance-covariance matrix
```

### Value labels

```bash
stata-cli labels               # list all value label names
stata-cli labels origin        # show value-label mapping
stata-cli labels --var foreign # show label attached to a variable
```

### Macros

```bash
stata-cli macro get "c(current_date)"
stata-cli macro get "e(cmd)"
stata-cli macro set myvar "hello"
```

### Frames

```bash
stata-cli frame
```

### Help

```bash
stata-cli help regress
stata-cli help summarize
```

### Stata reference library

```bash
stata-cli skill                # overview: gotchas, patterns, topic routing table
stata-cli skill --list         # list all 57 topics with descriptions
stata-cli skill regression     # linear regression reference
stata-cli skill did            # difference-in-differences guide
stata-cli skill reghdfe        # reghdfe package guide
```

Topics cover data management, econometrics, causal inference, graphics,
Mata programming, and 20+ community packages. Use `stata-cli skill <topic>`
to read detailed syntax, options, and idiomatic patterns before writing code.

### Stop execution

```bash
stata-cli stop
```

### Detect Stata path

```bash
stata-cli detect
```

## Daemon Mode

```bash
stata-cli daemon start     # start background daemon
stata-cli run "display 1"  # fast — auto-routes through daemon
stata-cli daemon status    # check daemon state
stata-cli daemon stop      # shut down
stata-cli daemon restart   # clean restart
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `--stata-path PATH` | Stata installation directory | auto-detected |
| `--edition [mp\|se\|be]` | Stata edition | `mp` |
| `--compact` | Strip verbose output noise | off |
| `--json` | Structured JSON output | off |
| `--timeout SECONDS` | Execution timeout | 600 |
| `--max-tokens N` | Max output tokens (0=unlimited) | 0 |
| `--no-daemon` | Force direct execution | off |
| `--graphs-dir PATH` | Graph export directory | `~/.stata-cli/graphs/` |
| `--graph-format [png\|svg\|pdf]` | Graph export format | `png` |
| `--log PATH` | Save output to a log file | off |

## JSON Output

```json
{
  "success": true,
  "output": ". display 1+1\n2",
  "error": "",
  "execution_time": 0.04,
  "return_code": 0,
  "extra": {}
}
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Stata command error |
| 2 | CLI usage error |
| 3 | Stata not found / init failure |

## Agent Usage Pattern

```bash
# Learn how to do DiD before writing code
stata-cli skill did

# Full analysis workflow
stata-cli run "sysuse auto, clear
summarize price mpg
regress price mpg weight
predict yhat
list make price yhat in 1/5"

# Get structured regression results
stata-cli return e

# Get coefficient matrix
stata-cli matrix e(b)

# Inspect variable metadata
stata-cli vars price mpg

# Check value labels
stata-cli labels --var foreign

# Check data after loading
stata-cli data --if "price>10000"

# Lookup command syntax
stata-cli help anova

# Compact mode for less noise
stata-cli --compact run "sysuse auto, clear
describe"
```
