#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
INIT_FILE = ROOT / "editable_pages" / "__init__.py"
UV_LOCK = ROOT / "uv.lock"
PKG_INFO = ROOT / "django_editable_pages.egg-info" / "PKG-INFO"

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
PYPROJECT_VERSION_RE = re.compile(r'^version = "([^"]+)"$', re.MULTILINE)
INIT_VERSION_RE = re.compile(r'^__version__ = "([^"]+)"$', re.MULTILINE)
PKG_INFO_VERSION_RE = re.compile(r"^Version: (.+)$", re.MULTILINE)
UV_LOCK_VERSION_RE = re.compile(r'^version = "([^"]+)"$')


@dataclass(frozen=True)
class VersionSources:
    pyproject: str
    init: str
    uv_lock: str
    pkg_info: str


def fail(message: str) -> NoReturn:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def ensure_semver(label: str, version: str) -> str:
    if not SEMVER_RE.fullmatch(version):
        fail(f"{label} has invalid version '{version}' (expected X.Y.Z)")
    return version


def read_pyproject_version() -> str:
    if not PYPROJECT.is_file():
        fail(f"Missing {PYPROJECT.relative_to(ROOT)}")

    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    try:
        version = data["project"]["version"]
    except KeyError as error:
        fail(f"Could not read project.version from {PYPROJECT.relative_to(ROOT)}: {error}")

    if not isinstance(version, str):
        fail(f"{PYPROJECT.relative_to(ROOT)} project.version is not a string")

    return ensure_semver(PYPROJECT.relative_to(ROOT).as_posix(), version)


def set_pyproject_version(version: str) -> None:
    ensure_semver("Requested version", version)
    text = PYPROJECT.read_text(encoding="utf-8")
    updated, replacements = PYPROJECT_VERSION_RE.subn(f'version = "{version}"', text, count=1)
    if replacements != 1:
        fail(f"Expected exactly one top-level version line in {PYPROJECT.relative_to(ROOT)}")
    PYPROJECT.write_text(updated, encoding="utf-8")


def read_init_version() -> str:
    if not INIT_FILE.is_file():
        fail(f"Missing {INIT_FILE.relative_to(ROOT)}")

    text = INIT_FILE.read_text(encoding="utf-8")
    match = INIT_VERSION_RE.search(text)
    if match is None:
        fail(f"Could not find __version__ in {INIT_FILE.relative_to(ROOT)}")
    return ensure_semver(INIT_FILE.relative_to(ROOT).as_posix(), match.group(1))


def set_init_version(version: str) -> None:
    ensure_semver("Requested version", version)
    text = INIT_FILE.read_text(encoding="utf-8")
    if INIT_VERSION_RE.search(text) is None:
        stripped = text.strip()
        updated = f'__version__ = "{version}"\n' if stripped == "" else f'__version__ = "{version}"\n\n{text}'
        INIT_FILE.write_text(updated, encoding="utf-8")
        return

    updated, replacements = INIT_VERSION_RE.subn(f'__version__ = "{version}"', text, count=1)
    if replacements != 1:
        fail(f"Expected exactly one __version__ line in {INIT_FILE.relative_to(ROOT)}")
    INIT_FILE.write_text(updated, encoding="utf-8")


def _editable_package_version_line(lines: list[str]) -> tuple[int, str]:
    block_starts = [index for index, line in enumerate(lines) if line == "[[package]]"]
    block_starts.append(len(lines))

    target_line_number: int | None = None
    target_line: str | None = None

    for start, end in zip(block_starts, block_starts[1:], strict=False):
        block = lines[start:end]
        if 'name = "django-editable-pages"' not in block:
            continue
        if 'source = { editable = "." }' not in block:
            continue

        for offset, line in enumerate(block):
            if UV_LOCK_VERSION_RE.match(line):
                if target_line_number is not None:
                    fail(
                        "Found multiple editable django-editable-pages package blocks in "
                        f"{UV_LOCK.relative_to(ROOT)}"
                    )
                target_line_number = start + offset
                target_line = line
                break

    if target_line_number is None or target_line is None:
        fail(
            "Could not find the editable django-editable-pages package block in "
            f"{UV_LOCK.relative_to(ROOT)}"
        )

    return target_line_number, target_line


def read_uv_lock_version() -> str:
    if not UV_LOCK.is_file():
        fail(f"Missing {UV_LOCK.relative_to(ROOT)}")

    _, version_line = _editable_package_version_line(
        UV_LOCK.read_text(encoding="utf-8").splitlines()
    )
    match = UV_LOCK_VERSION_RE.match(version_line)
    if match is None:
        fail(f"Could not parse the editable package version from {UV_LOCK.relative_to(ROOT)}")
    return ensure_semver(UV_LOCK.relative_to(ROOT).as_posix(), match.group(1))


def read_pkg_info_version() -> str:
    if not PKG_INFO.is_file():
        fail(f"Missing {PKG_INFO.relative_to(ROOT)}")

    text = PKG_INFO.read_text(encoding="utf-8")
    match = PKG_INFO_VERSION_RE.search(text)
    if match is None:
        fail(f"Could not find a Version header in {PKG_INFO.relative_to(ROOT)}")

    return ensure_semver(PKG_INFO.relative_to(ROOT).as_posix(), match.group(1).strip())


def read_versions() -> VersionSources:
    return VersionSources(
        pyproject=read_pyproject_version(),
        init=read_init_version(),
        uv_lock=read_uv_lock_version(),
        pkg_info=read_pkg_info_version(),
    )


def command_current(_: argparse.Namespace) -> int:
    print(read_pyproject_version())
    return 0


def command_set(args: argparse.Namespace) -> int:
    set_pyproject_version(args.version)
    set_init_version(args.version)
    print(f"Updated pyproject.toml and editable_pages/__init__.py to {args.version}")
    return 0


def command_check_sync(args: argparse.Namespace) -> int:
    versions = read_versions()
    expected = args.expected_version
    if expected is not None:
        expected = ensure_semver("Expected version", expected)

    if versions.uv_lock != versions.pyproject:
        fail(
            "Version sources are out of sync: "
            f"pyproject.toml has {versions.pyproject}, "
            f"uv.lock has {versions.uv_lock}"
        )

    if versions.init != versions.pyproject:
        fail(
            "Version sources are out of sync: "
            f"pyproject.toml has {versions.pyproject}, "
            f"editable_pages/__init__.py has {versions.init}"
        )

    if versions.pkg_info != versions.pyproject:
        fail(
            "Version sources are out of sync: "
            f"pyproject.toml has {versions.pyproject}, "
            f"django_editable_pages.egg-info/PKG-INFO has {versions.pkg_info}"
        )

    if expected is not None and versions.pyproject != expected:
        fail(f"Expected version {expected}, but committed metadata is at {versions.pyproject}")

    print(f"Version metadata is in sync at {versions.pyproject}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and update committed release version metadata."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    current = subparsers.add_parser(
        "current", help="Print the current version from pyproject.toml."
    )
    current.set_defaults(func=command_current)

    set_version = subparsers.add_parser("set", help="Update the version in pyproject.toml.")
    set_version.add_argument("version", help="Version to write in X.Y.Z format.")
    set_version.set_defaults(func=command_set)

    check_sync = subparsers.add_parser(
        "check-sync",
        help="Verify that pyproject.toml, editable_pages/__init__.py, uv.lock, and PKG-INFO all share the same version.",
    )
    check_sync.add_argument(
        "--expected-version",
        help="Optionally require a specific synced version.",
    )
    check_sync.set_defaults(func=command_check_sync)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
