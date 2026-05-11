"""Simplified SMCL-to-plain-text converter for Stata help files."""

import re

_CHAR_CODES = {
    "S|": "$", "'g": "`", "-(": "{", ")-": "}",
    "-": "─", "|": "│", "+": "┼",
    "TT": "┬", "BT": "┴", "LT": "├", "RT": "┤",
    "TLC": "┌", "TRC": "┐", "BRC": "┘", "BLC": "└",
    "a'": "á", "e'": "é", "i'": "í", "o'": "ó", "u'": "ú",
    "n~": "ñ", "ss": "ß", "c,": "ç",
}


def _resolve_char(code: str) -> str:
    code = code.strip()
    if code in _CHAR_CODES:
        return _CHAR_CODES[code]
    if code.startswith("0x") or code.startswith("0X"):
        try:
            return chr(int(code[2:], 16))
        except (ValueError, OverflowError):
            return code
    try:
        n = int(code)
        if 1 <= n <= 0x10FFFF:
            return chr(n)
    except (ValueError, OverflowError):
        pass
    return code


# Tags that are simply stripped (content kept)
_STRIP_TAGS = re.compile(
    r"\{/?(?:txt|res|err|inp|com|bf|it|sf|ul|smcl|s6hlp|"
    r"p_end|pstd|phang|pmore|pin|p2colset[^}]*|p2col[^}]*|"
    r"marker[^}]*|dlgtab[^}]*|synoptset[^}]*|syntab[^}]*|"
    r"synopt[^}]*|synopthdr[^}]*|"
    r"col\s+\d+|right|center|break|reset|"
    r"bind\s+[^}]*)\}"
)

# {hline} or {hline N} -> dashes
_HLINE_RE = re.compile(r"\{hline(?:\s+(\d+))?\}")

# {help topic}, {help topic:text}, {manhelp topic section}
_HELP_RE = re.compile(r"\{(?:help|manhelp)\s+([^}:]+?)(?::([^}]+))?\}")

# {browse "url":text} or {browse "url"}
_BROWSE_RE = re.compile(r'\{browse\s+"([^"]*)"(?::([^}]+))?\}')

# {cmd:text}, {opt:text}, {hi:text}, {title:text}, {it:text}, {bf:text}
_STYLED_RE = re.compile(r"\{(?:cmd|opt|hi|title|input|stata)\s*:\s*([^}]*)\}")
_STYLED2_RE = re.compile(r"\{(?:it|bf|ul)\s*:\s*([^}]*)\}")

# {c CODE}
_CHAR_RE = re.compile(r"\{c\s+([^}]+)\}")

# {space N}
_SPACE_RE = re.compile(r"\{space\s+(\d+)\}")

# Catch-all: any remaining {tag ...} or {tag:...}
_CATCHALL_RE = re.compile(r"\{[a-zA-Z_][^}]*\}")

# SMCL header line
_SMCL_HEADER_RE = re.compile(r"^\{smcl\}\s*$", re.MULTILINE)

# Star-bang lines in starbang output
_STARBANG_RE = re.compile(r"^\*!\s?", re.MULTILINE)

# INCLUDE directives (Stata-internal cross-references)
_INCLUDE_RE = re.compile(r"^INCLUDE\s+help\s+\S+.*$", re.MULTILINE)


def smcl_to_text(raw: str) -> str:
    """Convert SMCL markup to readable plain text."""
    text = _SMCL_HEADER_RE.sub("", raw)
    text = _STARBANG_RE.sub("", text)
    text = _INCLUDE_RE.sub("", text)

    text = _HLINE_RE.sub(lambda m: "-" * int(m.group(1) or 78), text)
    text = _HELP_RE.sub(lambda m: m.group(2) or m.group(1), text)
    text = _BROWSE_RE.sub(lambda m: m.group(2) or m.group(1), text)
    text = _STYLED_RE.sub(r"\1", text)
    text = _STYLED2_RE.sub(r"\1", text)
    text = _CHAR_RE.sub(lambda m: _resolve_char(m.group(1)), text)
    text = _SPACE_RE.sub(lambda m: " " * int(m.group(1)), text)
    text = _STRIP_TAGS.sub("", text)
    text = _CATCHALL_RE.sub("", text)

    # Collapse runs of >2 blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"
