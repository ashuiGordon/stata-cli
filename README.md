# stata-cli

Command-line interface for running Stata commands via PyStata.

## Requirements

- **Stata 17+** installed on your machine (provides the PyStata library)
- Python 3.9+

## Installation

### Via pip / pipx (recommended)

```bash
pip install stata-cli

# or, for an isolated install:
pipx install stata-cli
```

### Via npm / npx (zero Python setup)

```bash
# One-shot usage
npx stata-cli run "display 1+1"

# Global install
npm install -g stata-cli
```

The npm package is a thin wrapper that delegates to `uvx`, `pipx`, or `python3`.

## Usage

### Run code

```bash
stata-cli run "sysuse auto, clear"

# Multi-line
stata-cli run "sysuse auto, clear
summarize price mpg
regress price mpg weight"

# Pipe from stdin
echo "display 42" | stata-cli run -
```

### Run a .do file

```bash
stata-cli do analysis.do
stata-cli --compact do long_script.do
```

Do files are preprocessed: `///` line continuations are joined, and unnamed graph commands are auto-named for reliable export.

### View data

```bash
# Current dataset as JSON
stata-cli data

# With filter and row limit
stata-cli data --if "price>5000" --rows 50
```

### Help

```bash
stata-cli help regress
stata-cli help summarize
```

### Detect Stata path

```bash
stata-cli detect
```

### Stop execution

```bash
stata-cli stop
```

## Daemon Mode

The daemon keeps PyStata alive in the background, reducing execution time from ~2-3s to milliseconds.

```bash
# Start daemon
stata-cli daemon start

# Now all commands route through daemon automatically
stata-cli run "display 1+1"          # fast!

# Check status
stata-cli daemon status

# Restart (clean Stata state)
stata-cli daemon restart

# Stop daemon
stata-cli daemon stop
```

The daemon auto-shuts down after 1 hour of inactivity (configurable with `--idle-timeout`).

Use `--no-daemon` to force direct execution even when the daemon is running.

## Global Options

| Option | Description | Default |
|--------|-------------|---------|
| `--stata-path PATH` | Stata installation directory | auto-detected |
| `--edition [mp\|se\|be]` | Stata edition | `mp` |
| `--compact` | Strip verbose output | off |
| `--json` | Structured JSON output | off |
| `--timeout SECONDS` | Execution timeout | 600 |
| `--max-tokens N` | Max output tokens (0=unlimited) | 0 |
| `--no-daemon` | Force direct execution | off |
| `--graphs-dir PATH` | Graph export directory | `~/.stata-cli/graphs/` |

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

When graphs are created, they appear in `extra.graphs`:

```json
{
  "extra": {
    "graphs": [
      {"name": "Graph", "path": "/Users/you/.stata-cli/graphs/exec-.../Graph.png"}
    ]
  }
}
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `STATA_PATH` | Override Stata installation path |
| `STATA_CLI_GRAPHS_DIR` | Override graph export directory |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Stata command error |
| 2 | CLI usage error |
| 3 | Stata not found / init failure |

## For AI Agents

`stata-cli` is designed to be called directly from agent tool-use (e.g. Claude Code's `Bash` tool):

```bash
stata-cli run "sysuse auto, clear
reg price mpg weight
predict yhat"
```

Use `--json` for structured output:

```bash
stata-cli --json run "display 1+1"
# {"success": true, "output": ". display 1+1\n2", "error": "", "execution_time": 0.04, "return_code": 0, "extra": {}}
```

Agents can inspect exit codes and parse plain-text output naturally — no MCP server or port configuration required.

## License

MIT
