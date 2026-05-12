"""Stata CLI - run Stata commands from the terminal."""

from __future__ import annotations

import json
import os
import sys

import click

from . import __version__
from .engine import StataEngine, Result
from .output_filter import apply_compact_filter, check_token_limit, clean_log_wrapper
from .utils import detect_stata_path


# Exit codes
EXIT_OK = 0
EXIT_STATA_ERROR = 1
EXIT_USAGE_ERROR = 2
EXIT_INIT_FAILURE = 3


def _exit(code: int) -> None:
    """Exit bypassing atexit hooks — PyStata registers one that resets the exit code to 0."""
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)


@click.group()
@click.version_option(__version__, prog_name="stata-cli")
@click.option("--stata-path", envvar="STATA_PATH", default=None, help="Path to Stata installation directory.")
@click.option("--edition", type=click.Choice(["mp", "se", "be"], case_sensitive=False), default="mp", help="Stata edition.")
@click.option("--compact", is_flag=True, default=False, help="Apply compact output filter (strip verbose noise).")
@click.option("--json", "use_json", is_flag=True, default=False, help="Output results as JSON (for agent consumption).")
@click.option("--timeout", type=float, default=600.0, help="Execution timeout in seconds.")
@click.option("--max-tokens", type=int, default=0, help="Max output tokens (0=unlimited). Saves full output to file when exceeded.")
@click.option("--no-daemon", is_flag=True, default=False, help="Force direct execution, skip daemon.")
@click.option("--graphs-dir", envvar="STATA_CLI_GRAPHS_DIR", default=None, help="Graph export directory.")
@click.pass_context
def cli(ctx, stata_path, edition, compact, use_json, timeout, max_tokens, no_daemon, graphs_dir):
    """Command-line interface for Stata."""
    ctx.ensure_object(dict)
    ctx.obj["stata_path"] = stata_path
    ctx.obj["edition"] = edition
    ctx.obj["compact"] = compact
    ctx.obj["json"] = use_json
    ctx.obj["timeout"] = timeout
    ctx.obj["max_tokens"] = max_tokens
    ctx.obj["no_daemon"] = no_daemon
    ctx.obj["graphs_dir"] = graphs_dir


def _get_engine(ctx) -> StataEngine:
    stata_path = ctx.obj["stata_path"] or detect_stata_path()
    if not stata_path:
        click.echo("Error: Stata installation not found.", err=True)
        click.echo("Set --stata-path or the STATA_PATH environment variable.", err=True)
        _exit(EXIT_INIT_FAILURE)
    try:
        engine = StataEngine(stata_path, ctx.obj["edition"], graphs_dir=ctx.obj.get("graphs_dir"))
        return engine
    except Exception as exc:
        click.echo(f"Error initializing Stata: {exc}", err=True)
        _exit(EXIT_INIT_FAILURE)


def _try_daemon(ctx, cmd_type: str, payload: dict) -> Result | None:
    """Try to route through daemon. Returns None if daemon unavailable."""
    if ctx.obj.get("no_daemon"):
        return None
    try:
        from .daemon import DaemonClient
        client = DaemonClient()
        if not client.is_running():
            return None
        if not client.connect():
            return None
        resp = client.send(cmd_type, payload)
        client.close()
        return Result(
            success=resp.get("success", resp.get("status") == "success"),
            output=resp.get("output", ""),
            error=resp.get("error", ""),
            execution_time=resp.get("execution_time", 0.0),
            return_code=resp.get("return_code", 0),
            extra=resp.get("extra", {}),
        )
    except Exception:
        return None


def _print_result(result, compact: bool, use_json: bool = False, max_tokens: int = 0, filter_echo: bool = False) -> None:
    output = result.output
    if output:
        output = clean_log_wrapper(output)
        if compact:
            output = apply_compact_filter(output, filter_command_echo=filter_echo)
        if max_tokens > 0:
            output, _ = check_token_limit(output, max_tokens)
        result.output = output

    graphs = result.extra.get("graphs", []) if result.extra else []

    if use_json:
        click.echo(result.to_json())
        if not result.success:
            _exit(EXIT_STATA_ERROR)
        return

    if output and output.strip():
        click.echo(output)
    if graphs:
        for g in graphs:
            click.echo(f"[graph] {g.get('name', 'graph')}: {g.get('path', '')}")
    if not result.success:
        if result.error:
            click.echo(result.error, err=True)
        _exit(EXIT_STATA_ERROR)


# ── Commands ─────────────────────────────────────────────────────────────

@cli.command()
@click.argument("code")
@click.pass_context
def run(ctx, code):
    """Execute a Stata code string.

    Use '-' to read code from stdin (for piping).

    \b
    Examples:
      stata-cli run "sysuse auto, clear"
      stata-cli run "display 1+1"
      echo "summarize price" | stata-cli run -
    """
    if code == "-":
        code = sys.stdin.read()
    if not code.strip():
        click.echo("Error: empty code.", err=True)
        _exit(EXIT_USAGE_ERROR)

    result = _try_daemon(ctx, "execute", {"code": code, "timeout": ctx.obj["timeout"]})
    if result is None:
        engine = _get_engine(ctx)
        result = engine.run(code, timeout=ctx.obj["timeout"])
    _print_result(result, ctx.obj["compact"], use_json=ctx.obj["json"], max_tokens=ctx.obj["max_tokens"])


@cli.command("do")
@click.argument("path", type=click.Path(exists=True))
@click.pass_context
def do_file(ctx, path):
    """Execute a Stata .do file.

    \b
    Examples:
      stata-cli do analysis.do
      stata-cli --compact do long_script.do
    """
    result = _try_daemon(ctx, "execute_file", {"path": os.path.abspath(path), "timeout": ctx.obj["timeout"]})
    if result is None:
        engine = _get_engine(ctx)
        result = engine.run_file(path, timeout=ctx.obj["timeout"])
    _print_result(result, ctx.obj["compact"], use_json=ctx.obj["json"], max_tokens=ctx.obj["max_tokens"], filter_echo=True)


@cli.command()
@click.pass_context
def detect(ctx):
    """Print the auto-detected Stata installation path."""
    stata_path = ctx.obj["stata_path"] or detect_stata_path()
    if stata_path:
        click.echo(stata_path)
    else:
        click.echo("Stata installation not found.", err=True)
        _exit(EXIT_INIT_FAILURE)


@cli.command("data")
@click.option("--if", "if_condition", default=None, help="Stata if condition for filtering.")
@click.option("--rows", type=int, default=10000, help="Maximum rows to return.")
@click.pass_context
def data_cmd(ctx, if_condition, rows):
    """View the current dataset as JSON.

    \b
    Examples:
      stata-cli data
      stata-cli data --if "price>5000" --rows 50
    """
    # Try daemon first
    try:
        from .daemon import DaemonClient
        client = DaemonClient()
        if not ctx.obj.get("no_daemon") and client.is_running() and client.connect():
            resp = client.send("get_data", {"if_condition": if_condition, "max_rows": rows})
            client.close()
            click.echo(json.dumps(resp, ensure_ascii=False, indent=2))
            return
    except Exception:
        pass

    engine = _get_engine(ctx)
    resp = engine.get_data(if_condition=if_condition, max_rows=rows)
    click.echo(json.dumps(resp, ensure_ascii=False, indent=2))


@cli.command("help")
@click.argument("topic")
@click.pass_context
def help_cmd(ctx, topic):
    """Display Stata help for a topic.

    \b
    Examples:
      stata-cli help regress
      stata-cli help summarize
    """
    result = _try_daemon(ctx, "help", {"topic": topic})
    if result is None:
        engine = _get_engine(ctx)
        result = engine.help(topic)
    if ctx.obj["json"]:
        click.echo(result.to_json())
    elif result.output and result.output.strip():
        click.echo(result.output)
    else:
        click.echo(f"No help found for: {topic}", err=True)
        _exit(EXIT_STATA_ERROR)


@cli.command("stop")
@click.pass_context
def stop_cmd(ctx):
    """Interrupt a running Stata command (daemon mode)."""
    try:
        from .daemon import DaemonClient
        client = DaemonClient()
        if client.is_running() and client.connect():
            resp = client.send("stop")
            client.close()
            click.echo(f"Stop signal: {resp.get('status', 'unknown')}")
            return
    except Exception:
        pass
    click.echo("Daemon not running.", err=True)
    _exit(EXIT_USAGE_ERROR)


# ── Daemon subcommands ───────────────────────────────────────────────────

@cli.group()
def daemon():
    """Manage the Stata daemon process."""


@daemon.command("start")
@click.option("--idle-timeout", type=int, default=3600, help="Auto-shutdown after N seconds idle.")
@click.pass_context
def daemon_start(ctx, idle_timeout):
    """Start the Stata daemon (keeps PyStata alive for fast execution)."""
    stata_path = ctx.obj["stata_path"] or detect_stata_path()
    if not stata_path:
        click.echo("Error: Stata installation not found.", err=True)
        _exit(EXIT_INIT_FAILURE)

    from .daemon import start_daemon, DaemonClient
    client = DaemonClient()
    if client.is_running():
        click.echo("Daemon already running.")
        return

    click.echo("Starting daemon...")
    ok = start_daemon(stata_path, ctx.obj["edition"], graphs_dir=ctx.obj.get("graphs_dir"), idle_timeout=idle_timeout)
    if ok:
        click.echo("Daemon started.")
    else:
        click.echo("Failed to start daemon.", err=True)
        _exit(EXIT_INIT_FAILURE)


@daemon.command("stop")
def daemon_stop():
    """Stop the Stata daemon."""
    from .daemon import stop_daemon, DaemonClient
    client = DaemonClient()
    if not client.is_running():
        click.echo("Daemon not running.")
        return
    click.echo("Stopping daemon...")
    stop_daemon()
    click.echo("Daemon stopped.")


@daemon.command("status")
def daemon_status_cmd():
    """Show daemon status."""
    from .daemon import daemon_status
    info = daemon_status()
    if not info:
        click.echo("Daemon not running.")
        return
    uptime = info.get("uptime", 0)
    idle = info.get("idle", 0)
    click.echo(f"Daemon running (PID {info.get('pid', '?')})")
    click.echo(f"  Stata: {info.get('stata_path', '?')} ({info.get('edition', '?')})")
    click.echo(f"  Uptime: {int(uptime)}s")
    click.echo(f"  Idle: {int(idle)}s")


@daemon.command("restart")
@click.option("--idle-timeout", type=int, default=3600, help="Auto-shutdown after N seconds idle.")
@click.pass_context
def daemon_restart(ctx, idle_timeout):
    """Restart the Stata daemon."""
    from .daemon import stop_daemon, start_daemon, DaemonClient
    client = DaemonClient()
    if client.is_running():
        click.echo("Stopping daemon...")
        stop_daemon()

    stata_path = ctx.obj["stata_path"] or detect_stata_path()
    if not stata_path:
        click.echo("Error: Stata installation not found.", err=True)
        _exit(EXIT_INIT_FAILURE)

    click.echo("Starting daemon...")
    ok = start_daemon(stata_path, ctx.obj["edition"], graphs_dir=ctx.obj.get("graphs_dir"), idle_timeout=idle_timeout)
    if ok:
        click.echo("Daemon restarted.")
    else:
        click.echo("Failed to restart daemon.", err=True)
        _exit(EXIT_INIT_FAILURE)


# Allow running as `python -m stata_cli`
def main():
    cli()


if __name__ == "__main__":
    main()
