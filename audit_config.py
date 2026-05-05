#!/usr/bin/env python3
"""
Non-invasive security/configuration audit script.

Scans the current project directory and prints warnings about:
- hardcoded secrets
- weak defaults
- exposed tokens
- missing .env values
- duplicated admin/support IDs

This script does not modify files or change runtime behavior.
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Iterable


SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    "coverage",
    ".next",
    ".nuxt",
    ".turbo",
}

SKIP_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".7z",
    ".rar",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".pyc",
    ".pyo",
    ".class",
    ".sqlite",
    ".sqlite3",
    ".db",
}

ENV_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.test",
}

ENV_EXAMPLE_NAMES = {
    ".env.example",
    ".env.sample",
    ".env.template",
    "env.example",
    "env.sample",
}

SECRET_NAME_RE = re.compile(
    r"""
    \b(
        api[_-]?key |
        secret |
        token |
        password |
        passwd |
        private[_-]?key |
        client[_-]?secret |
        access[_-]?key |
        jwt[_-]?secret |
        signing[_-]?key |
        webhook[_-]?secret
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

ASSIGNMENT_RE = re.compile(
    r"""
    (?P<name>[A-Z0-9_./-]*(?:KEY|SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE_KEY|CLIENT_SECRET|ACCESS_KEY|JWT_SECRET|SIGNING_KEY)[A-Z0-9_./-]*)
    \s*[:=]\s*
    (?P<quote>['"]?)
    (?P<value>[^'"\s#,{]+)
    (?P=quote)
    """,
    re.IGNORECASE | re.VERBOSE,
)

EXPOSED_TOKEN_PATTERNS = [
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("Stripe key", re.compile(r"\b(?:sk|pk)_(?:live|test)_[A-Za-z0-9]{16,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("OpenAI-style API key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
]

WEAK_DEFAULT_RE = re.compile(
    r"""
    \b(
        debug\s*[:=]\s*(true|1|yes|on) |
        flask_env\s*[:=]\s*development |
        node_env\s*[:=]\s*development |
        secret[_-]?key\s*[:=]\s*['"]?(dev|test|secret|changeme|change_me|password|default) |
        jwt[_-]?secret\s*[:=]\s*['"]?(dev|test|secret|changeme|change_me|password|default) |
        password\s*[:=]\s*['"]?(password|admin|root|test|changeme|change_me|default)
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

ENV_USAGE_RE = re.compile(
    r"""
    (?:
        os\.environ\[['"](?P<py1>[A-Z][A-Z0-9_]*)['"]\] |
        os\.getenv\(['"](?P<py2>[A-Z][A-Z0-9_]*)['"] |
        process\.env\.(?P<js1>[A-Z][A-Z0-9_]*) |
        process\.env\[['"](?P<js2>[A-Z][A-Z0-9_]*)['"]\]
    )
    """,
    re.VERBOSE,
)

ADMIN_SUPPORT_RE = re.compile(
    r"""
    \b(?P<name>
        (?:ADMIN|ADMINS|SUPERUSER|SUPERUSERS|SUPPORT|SUPPORTS|OWNER|OWNERS)
        [A-Z0-9_]*(?:ID|IDS|USER|USERS)?
    )
    \s*[:=]\s*
    (?P<quote>['"]?)
    (?P<value>[A-Za-z0-9_,.@:-]+)
    (?P=quote)
    """,
    re.IGNORECASE | re.VERBOSE,
)


def is_probably_binary(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:2048]
    except OSError:
        return True
    return b"\x00" in chunk


def should_skip(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = path

    if any(part in SKIP_DIRS for part in relative.parts):
        return True

    if path.suffix.lower() in SKIP_EXTENSIONS:
        return True

    return False


def iter_project_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if should_skip(path, root):
            continue
        if is_probably_binary(path):
            continue
        yield path


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}

    for raw_line in read_text(path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip("'\"")
        values[key] = value

    return values


def warn(path: Path | None, line_number: int | None, message: str) -> None:
    if path is None:
        print(f"WARNING: {message}")
        return

    location = str(path)
    if line_number is not None:
        location = f"{location}:{line_number}"

    print(f"WARNING: {location}: {message}")


def looks_like_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {
        "",
        "changeme",
        "change_me",
        "change-me",
        "todo",
        "replace_me",
        "replace-me",
        "example",
        "sample",
        "placeholder",
        "default",
        "none",
        "null",
        "undefined",
    }


def scan_hardcoded_secrets(path: Path, text: str) -> None:
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("#"):
            continue

        assignment = ASSIGNMENT_RE.search(line)
        if not assignment:
            continue

        name = assignment.group("name")
        value = assignment.group("value").strip().strip("'\"")

        if looks_like_placeholder(value):
            warn(path, line_number, f"secret-like setting `{name}` uses a placeholder or empty value")
            continue

        if len(value) >= 8 and SECRET_NAME_RE.search(name):
            warn(path, line_number, f"possible hardcoded secret in `{name}`")


def scan_exposed_tokens(path: Path, text: str) -> None:
    for line_number, line in enumerate(text.splitlines(), start=1):
        for label, pattern in EXPOSED_TOKEN_PATTERNS:
            if pattern.search(line):
                warn(path, line_number, f"possible exposed {label}")


def scan_weak_defaults(path: Path, text: str) -> None:
    for line_number, line in enumerate(text.splitlines(), start=1):
        if WEAK_DEFAULT_RE.search(line):
            warn(path, line_number, "weak or development default detected")


def collect_env_usage(path: Path, text: str) -> set[str]:
    names: set[str] = set()

    for match in ENV_USAGE_RE.finditer(text):
        for group_name in ("py1", "py2", "js1", "js2"):
            value = match.group(group_name)
            if value:
                names.add(value)

    return names


def scan_admin_support_ids(path: Path, text: str) -> list[tuple[str, str, int]]:
    found: list[tuple[str, str, int]] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        match = ADMIN_SUPPORT_RE.search(line)
        if not match:
            continue

        name = match.group("name")
        raw_value = match.group("value")

        for value in re.split(r"[,;]", raw_value):
            value = value.strip()
            if value:
                found.append((name, value, line_number))

    return found


def audit_env_files(root: Path, files: list[Path]) -> dict[str, str]:
    env_values: dict[str, str] = {}
    example_values: dict[str, str] = {}

    for path in files:
        if path.name in ENV_FILE_NAMES:
            parsed = parse_env_file(path)
            env_values.update(parsed)

            for key, value in parsed.items():
                if looks_like_placeholder(value):
                    warn(path, None, f"env value `{key}` is empty or placeholder-like")

        if path.name in ENV_EXAMPLE_NAMES:
            example_values.update(parse_env_file(path))

    for key in sorted(example_values):
        if key not in env_values:
            warn(None, None, f"`.env` is missing value for example key `{key}`")

    return env_values


def audit_missing_used_env_values(used_env: set[str], env_values: dict[str, str]) -> None:
    for key in sorted(used_env):
        if key not in env_values and key not in os.environ:
            warn(None, None, f"referenced environment variable `{key}` is not set in .env or current environment")


def audit_duplicate_admin_support_ids(records: list[tuple[Path, str, str, int]]) -> None:
    seen: dict[str, list[tuple[Path, str, int]]] = {}

    for path, name, value, line_number in records:
        normalized = value.lower()
        seen.setdefault(normalized, []).append((path, name, line_number))

    for value, locations in sorted(seen.items()):
        names = {name for _, name, _ in locations}
        if len(locations) > 1 and len(names) > 1:
            details = ", ".join(f"{path}:{line} `{name}`" for path, name, line in locations)
            warn(None, None, f"duplicated admin/support ID `{value}` appears in multiple roles: {details}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Non-invasive project security/configuration audit."
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Project root to scan. Defaults to current directory.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"ERROR: scan root does not exist: {root}")
        return 2

    files = list(iter_project_files(root))
    used_env: set[str] = set()
    admin_support_records: list[tuple[Path, str, str, int]] = []

    print(f"Scanning project: {root}")
    print(f"Files scanned: {len(files)}")

    env_values = audit_env_files(root, files)

    for path in files:
        text = read_text(path)

        scan_hardcoded_secrets(path, text)
        scan_exposed_tokens(path, text)
        scan_weak_defaults(path, text)

        used_env.update(collect_env_usage(path, text))

        for name, value, line_number in scan_admin_support_ids(path, text):
            admin_support_records.append((path, name, value, line_number))

    audit_missing_used_env_values(used_env, env_values)
    audit_duplicate_admin_support_ids(admin_support_records)

    print("Audit complete. No files were modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
