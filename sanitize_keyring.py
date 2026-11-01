#!/usr/bin/env python3
"""Fold multiline gnome-keyring INI values so GKeyFile can parse them.

Proton stores JSON+PEM in the unencrypted keyring. Literal newlines in
those secrets make gnome-keyring reject the whole file, after which Chrome
creates a new encrypted 'Default' keyring and prompts for a password.

Folding alone is not enough: a value that only *looks* single-line still
decodes to one that holds real newlines, and the daemon stores the decoded
value. On the next save it writes those newlines back raw, which leaves an
unparseable line and the following daemon start loads no collections at all
(the same prompt, one boot later). So a JSON secret is re-encoded with its
newlines escaped inside the string, leaving no real newline in the value.

`--persist` sanitizes Omarchy's passwordless INI (if it exists) and pins
the `default` alias to it. It does not create keyrings, restart the
daemon, or quarantine Chrome stores.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# GKeyFile keys are lowercase, digits, hyphens. Proton PEM continuations are
# mixed-case base64 and BEGIN/END markers, so they do not match.
_KEY_LINE = re.compile(r"^[a-z][a-z0-9-]*=")

_JSON_ESCAPES = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}


def is_key_line(line: str) -> bool:
    """Return True if line starts a gnome-keyring GKeyFile field."""
    return _KEY_LINE.match(line) is not None


def gkeyfile_escape(value: str) -> str:
    """Encode a value so GKeyFile decodes it back unchanged."""
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def reencode_json_value(value: str) -> str | None:
    """Return JSON with no raw newline left in it, or None if not JSON.

    Newlines inside a JSON string become the two characters ``\\n`` (which is
    what the producer meant); whitespace outside a string becomes a space, and
    JSON ignores it. The result therefore round-trips through GKeyFile with no
    real newline in the stored value.
    """
    if not value.lstrip().startswith(("{", "[")):
        return None
    repaired: list[str] = []
    in_string = False
    escaped = False
    for char in value:
        if escaped:
            repaired.append(char)
            escaped = False
            continue
        if char == "\\":
            repaired.append(char)
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            repaired.append(char)
            continue
        if char in _JSON_ESCAPES:
            repaired.append(_JSON_ESCAPES[char] if in_string else " ")
            continue
        repaired.append(char)
    candidate = "".join(repaired)
    try:
        json.loads(candidate)
    except ValueError:
        return None
    return candidate


def sanitize_keyring_text(text: str) -> str:
    """Return INI text with multiline values made GKeyFile-parseable.

    Values that are JSON are re-encoded so the stored value holds no real
    newline; anything else is folded with GKeyFile ``\\n``.
    """
    lines = text.splitlines()
    out: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not is_key_line(line):
            out.append(line)
            index += 1
            continue
        key, _, value = line.partition("=")
        index += 1
        parts = [value]
        while (
            index < len(lines)
            and lines[index] != ""
            and not is_key_line(lines[index])
            and not lines[index].startswith("[")
        ):
            parts.append(lines[index])
            index += 1
        if len(parts) == 1:
            out.append(f"{key}={value}")
        else:
            joined = "\n".join(parts)
            reencoded = reencode_json_value(joined)
            if reencoded is None:
                out.append(f"{key}={'\\n'.join(parts)}")
            else:
                out.append(f"{key}={gkeyfile_escape(reencoded)}")
    result = "\n".join(out)
    if text.endswith("\n"):
        result += "\n"
    return result


def sanitize_keyring_file(path: Path) -> bool:
    """Rewrite an INI keyring atomically. Returns True if the file changed."""
    if path.is_symlink() or not path.is_file():
        return False
    original = path.read_text(encoding="utf-8")
    if not original.lstrip().startswith("["):
        return False
    sanitized = sanitize_keyring_text(original)
    if sanitized == original:
        return False
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(sanitized, encoding="utf-8")
        tmp.chmod(0o600)
        os.replace(tmp, path)
    except OSError:
        if tmp.exists() and not tmp.is_symlink():
            tmp.unlink()
        raise
    path.chmod(0o600)
    return True


def keyring_dir() -> Path:
    """Return the gnome-keyring directory, honoring PROTONVPN_KEYRING_DIR."""
    override = os.environ.get("PROTONVPN_KEYRING_DIR")
    if override:
        return Path(override)
    return Path.home() / ".local/share/keyrings"


def persist_session() -> bool:
    """Sanitize Default_keyring.keyring and pin the default alias to it.

    No-ops if the passwordless INI is missing. Does not create keyrings,
    restart gnome-keyring, or move Chrome stores. Returns True if the INI
    or alias file changed.
    """
    directory = keyring_dir()
    ini = directory / "Default_keyring.keyring"
    alias = directory / "default"
    if ini.is_symlink() or not ini.is_file():
        return False
    try:
        head = ini.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False
    if not head.lstrip().startswith("["):
        return False
    changed = sanitize_keyring_file(ini)
    wanted = "Default_keyring\n"
    if alias.is_symlink():
        return changed
    current = alias.read_text(encoding="utf-8") if alias.is_file() else ""
    if current != wanted:
        tmp = alias.with_name(alias.name + ".tmp")
        try:
            tmp.write_text(wanted, encoding="utf-8")
            tmp.chmod(0o644)
            os.replace(tmp, alias)
        except OSError:
            if tmp.exists() and not tmp.is_symlink():
                tmp.unlink()
            raise
        return True
    return changed


def main(argv: list[str] | None = None) -> int:
    """CLI entry: sanitize one keyring file, or `--persist` the session store."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, nargs="?")
    parser.add_argument(
        "--persist",
        action="store_true",
        help="sanitize Default_keyring.keyring and pin the default alias",
    )
    args = parser.parse_args(argv)
    if args.persist:
        if args.path is not None:
            parser.error("--persist does not take a path")
        persist_session()
        return 0
    if args.path is None:
        parser.error("path or --persist is required")
    sanitize_keyring_file(args.path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
