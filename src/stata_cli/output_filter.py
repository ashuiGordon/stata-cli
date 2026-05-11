"""Output filtering for Stata CLI.

Provides compact-mode filtering (strips verbose/redundant output) and
cleanup of the log-file wrapper lines injected by the engine.
"""

import os
import re
import time
import tempfile


_BANNER_END_RE = re.compile(r"^-{40,}$")
_LOG_SCAFFOLD_PATTERNS = [
    re.compile(r"^\s*\.?\s*capture\s+log\s+close", re.IGNORECASE),
    re.compile(r"^\s*\.?\s*log\s+using\s+", re.IGNORECASE),
    re.compile(r"^\s*(name|log|log type|opened on|closed on):", re.IGNORECASE),
    # Continuation of a long log-using path that wraps to the next line
    re.compile(r"^>\s.*\.log"),
]


def clean_log_wrapper(output: str) -> str:
    """Remove Stata banner and ``log using`` / ``log close`` scaffolding."""
    if not output:
        return output

    lines = output.split("\n")

    # 1. Strip the startup banner (everything up to and including the "---…" separator)
    start = 0
    for i, line in enumerate(lines):
        if _BANNER_END_RE.match(line.strip()):
            start = i + 1
            break

    cleaned: list[str] = []
    for line in lines[start:]:
        if any(pat.match(line.strip()) for pat in _LOG_SCAFFOLD_PATTERNS):
            continue
        cleaned.append(line)

    while cleaned and not cleaned[0].strip():
        cleaned.pop(0)
    while cleaned and not cleaned[-1].strip():
        cleaned.pop()
    return "\n".join(cleaned)


def apply_compact_filter(output: str, filter_command_echo: bool = False) -> str:
    """Strip verbose/redundant output to reduce noise.

    Always filters:
    - Program definition blocks
    - Mata blocks
    - Loop code echoes (keeps actual output)
    - SMCL formatting tags
    - Verbose messages like "(N real changes made)"

    When *filter_command_echo* is True (e.g. for ``do`` files):
    - Command echo lines (``". "`` prefix)
    - Line continuations (``"> "``)
    """
    if not output:
        return output

    output = output.replace("\r\n", "\n").replace("\r", "\n")
    lines = output.split("\n")
    filtered: list[str] = []

    command_echo_pat = re.compile(r"^\.\s*$|^\.\s+\S")
    numbered_line_pat = re.compile(r"^\s*\d+\.\s")
    continuation_pat = re.compile(r"^>\s")

    program_drop_pat = re.compile(
        r"^\s*\.?\s*(capture\s+program\s+drop|cap\s+program\s+drop|cap\s+prog\s+drop)\s+\w+",
        re.IGNORECASE,
    )
    program_define_pat = re.compile(
        r"^\s*\.?\s*program\s+(define\s+)?(?!version|dir|drop|list|describe)\w+",
        re.IGNORECASE,
    )
    mata_start_pat = re.compile(
        r"^\s*(\d+\.)?\s*\.?\s*mata\s*:?\s*$|^-+\s*mata\s*\(",
        re.IGNORECASE,
    )
    end_pat = re.compile(r"^\s*(\d+\.)?\s*[.:]*\s*end\s*$", re.IGNORECASE)
    mata_sep_pat = re.compile(r"^-{20,}$")

    loop_start_pat = re.compile(
        r"^(\s*\d+\.)?\s*\.?\s*(foreach|forvalues|while)\s+.*\{\s*$",
        re.IGNORECASE,
    )
    loop_end_pat = re.compile(r"^\s*\d+\.\s*\}\s*$")

    real_changes_pat = re.compile(r"^\s*\([\d,]+\s+real\s+changes?\s+made\)\s*$", re.IGNORECASE)
    missing_values_pat = re.compile(r"^\s*\([\d,]+\s+missing\s+values?\s+generated\)\s*$", re.IGNORECASE)
    smcl_pat = re.compile(
        r"\{(txt|res|err|inp|com|bf|it|sf|hline|c\s+\||\-+|break|col\s+\d+|right|center|ul|/ul)\}"
    )

    in_program = False
    in_mata = False
    in_loop = False
    program_end_depth = 0
    loop_brace_depth = 0

    i = 0
    while i < len(lines):
        line = lines[i]

        if in_program:
            if mata_start_pat.match(line):
                program_end_depth += 1
            if end_pat.match(line):
                if program_end_depth > 0:
                    program_end_depth -= 1
                else:
                    in_program = False
            i += 1
            continue

        if in_mata:
            if end_pat.match(line):
                in_mata = False
                if i + 1 < len(lines) and mata_sep_pat.match(lines[i + 1]):
                    i += 1
            i += 1
            continue

        if in_loop:
            if loop_start_pat.match(line):
                loop_brace_depth += 1
                i += 1
                continue
            if loop_end_pat.match(line):
                if loop_brace_depth > 0:
                    loop_brace_depth -= 1
                else:
                    in_loop = False
                i += 1
                continue
            if command_echo_pat.match(line) or numbered_line_pat.match(line) or continuation_pat.match(line):
                i += 1
                continue
            if real_changes_pat.match(line) or missing_values_pat.match(line):
                i += 1
                continue
            line = smcl_pat.sub("", line)
            if line.strip():
                filtered.append(line)
            i += 1
            continue

        if loop_start_pat.match(line):
            in_loop = True
            loop_brace_depth = 0
            i += 1
            continue

        if program_drop_pat.match(line):
            i += 1
            continue
        if program_define_pat.match(line):
            in_program = True
            program_end_depth = 0
            i += 1
            continue
        if mata_start_pat.match(line):
            in_mata = True
            i += 1
            continue

        if real_changes_pat.match(line) or missing_values_pat.match(line):
            i += 1
            continue

        if filter_command_echo:
            if command_echo_pat.match(line) or numbered_line_pat.match(line) or continuation_pat.match(line):
                i += 1
                continue

        line = smcl_pat.sub("", line)
        filtered.append(line)
        i += 1

    # Collapse consecutive blank lines
    result: list[str] = []
    prev_blank = False
    for line in filtered:
        is_blank = not line.strip()
        if is_blank:
            if not prev_blank:
                result.append(line)
            prev_blank = True
        else:
            result.append(line)
            prev_blank = False

    while result and not result[-1].strip():
        result.pop()

    return "\n".join(result)


def check_token_limit(output: str, max_tokens: int) -> tuple[str, bool]:
    """Truncate output exceeding *max_tokens* (~4 chars/token).

    Returns ``(output, was_truncated)``.  When truncated the full output is
    saved to a temp file and a summary with the file path is returned.
    """
    if max_tokens <= 0 or not output:
        return output, False

    estimated_tokens = len(output) / 4
    if estimated_tokens <= max_tokens:
        return output, False

    logs_dir = os.path.join(tempfile.gettempdir(), "stata_cli_logs")
    os.makedirs(logs_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(logs_dir, f"stata_output_{timestamp}.log")

    try:
        with open(log_path, "w", encoding="utf-8") as fh:
            fh.write(output)
    except OSError:
        max_chars = max_tokens * 4
        return output[:max_chars] + f"\n\n... [Output truncated at {max_tokens} tokens]", True

    preview = output[:1000]
    if len(output) > 1000:
        preview += "\n... [truncated]"
    msg = (
        f"Output exceeded token limit ({int(estimated_tokens)} tokens > {max_tokens} max).\n"
        f"Full output saved to: {log_path}\n\n"
        f"--- Preview ---\n{preview}"
    )
    return msg, True
