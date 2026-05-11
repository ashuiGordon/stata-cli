---
name: stata-cli
description: >-
  Run Stata commands, .do files, view data, and get help from the terminal.
  Wraps PyStata with a daemon mode for fast execution. Designed for AI agents.
---

# stata-cli

Run Stata code, `.do` files, view data, get help — all from the command line.
Designed for AI agent tool-use via `Bash`. Includes a daemon mode for
sub-second execution.

## Install

```bash
pip install stata-cli
```

Requires **Stata 17+** installed on the machine (provides PyStata).

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

Auto-preprocesses `///` line continuations and auto-names unnamed graph
commands for reliable export.

### View data

```bash
stata-cli data
stata-cli data --if "price>5000" --rows 50
```

Returns the current dataset as JSON with columns, data, types, and row counts.

### Help

```bash
stata-cli help regress
stata-cli help summarize
```

### Stop execution

```bash
stata-cli stop
```

### Detect Stata path

```bash
stata-cli detect
```

## Daemon Mode

Keeps PyStata alive in the background — reduces startup from ~2-3s to
milliseconds.

```bash
stata-cli daemon start     # start background daemon
stata-cli run "display 1"  # fast — auto-routes through daemon
stata-cli daemon status    # check daemon state
stata-cli daemon stop      # shut down
stata-cli daemon restart   # clean restart
```

Commands auto-route through the daemon when it's running. Use `--no-daemon`
to force direct execution.

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

Environment variables: `STATA_PATH`, `STATA_CLI_GRAPHS_DIR`.

## JSON Output

```bash
stata-cli --json run "display 1+1"
```

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

Fields: `success` (bool), `output` (string), `error` (string),
`execution_time` (seconds), `return_code` (Stata r-code, 0 = ok),
`extra` (dict, may contain `graphs` list with exported file paths).

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Stata command error |
| 2 | CLI usage error |
| 3 | Stata not found / init failure |

## Graph Export

When Stata code creates graphs, they are automatically detected and exported
as PNG to `~/.stata-cli/graphs/`. File paths appear in the output:

```
[graph] Graph: /Users/you/.stata-cli/graphs/exec-.../Graph.png
```

Or in JSON mode under `extra.graphs`.

## Agent Usage Pattern

```bash
# Full analysis workflow
stata-cli run "sysuse auto, clear
summarize price mpg
regress price mpg weight
predict yhat
list make price yhat in 1/5"

# Check data after loading
stata-cli data --if "price>10000"

# Lookup command syntax
stata-cli help anova

# Compact mode for less noise
stata-cli --compact run "sysuse auto, clear
describe"
```
