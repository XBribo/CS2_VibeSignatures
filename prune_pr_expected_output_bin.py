#!/usr/bin/env python3
"""
Prune PR-added expected_output YAMLs from the copied bin/ cache.

Used by .github/workflows/pr-self-runner.yml right after the persisted
bin/<gamever> YAML cache is copied into the PR workspace. It deletes the
expected_output YAML artifacts that the PR *adds* to config.yaml (the set
difference of expected_output between the PR base and PR head), so
ida_analyze_bin.py is forced to regenerate them (full validation) instead of
skipping skills whose outputs already exist on disk.

Usage:
    python prune_pr_expected_output_bin.py -gamever <version> -baseref <gitref>
    python prune_pr_expected_output_bin.py -gamever <version> -baseconfigyaml <path>

    -gamever: Game version subdirectory under bindir (required)
    -bindir: Root directory of copied binaries/YAML (default: bin)
    -configyaml: Path to the head config.yaml (default: config.yaml)
    -baseref: Git ref of the PR base; the base config is read via
              `git show <ref>:<configyaml>` (configyaml must be repo-root-relative)
    -baseconfigyaml: Path to the base config.yaml file (alternative to -baseref)

Exactly one of -baseref / -baseconfigyaml must be provided.

Requirements:
    uv sync
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile

try:
    import yaml
except ImportError as e:
    print(f"Error: Missing required dependency: {e.name}")
    print("Please install required dependencies with: uv sync")
    sys.exit(1)

import ida_analyze_bin

DEFAULT_BIN_DIR = "bin"
DEFAULT_CONFIG_FILE = "config.yaml"
PLATFORMS = ("windows", "linux")
ARG_ERROR_EXIT = 2


def parse_args(argv=None):
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Delete PR-added expected_output YAMLs from bin/ so validation re-runs them",
    )
    parser.add_argument("-gamever", required=True, help="Game version subdirectory under bindir (required)")
    parser.add_argument(
        "-bindir", default=DEFAULT_BIN_DIR, help=f"Root directory of copied binaries (default: {DEFAULT_BIN_DIR})"
    )
    parser.add_argument(
        "-configyaml",
        default=DEFAULT_CONFIG_FILE,
        help=f"Path to the head config.yaml (default: {DEFAULT_CONFIG_FILE})",
    )
    parser.add_argument(
        "-baseref",
        default=None,
        help="Git ref of the PR base; base config read via `git show <ref>:<configyaml>`",
    )
    parser.add_argument(
        "-baseconfigyaml",
        default=None,
        help="Path to the base config.yaml file (alternative to -baseref)",
    )
    return parser.parse_args(argv)


def collect_required_output_paths(modules, gamever, bindir):
    """
    Return the set of absolute expected_output YAML paths declared by modules.

    Mirrors the skip logic in ida_analyze_bin.py: for every skill the required
    outputs are expected_output + expected_output_{platform}, resolved under
    bin/<gamever>/<module>/ with {platform} expanded. Skills pinned to a single
    platform contribute only that platform's outputs. Paths that fail to resolve
    (e.g. escape the gamever root) are logged and skipped rather than raising.
    """
    outputs = set()
    for module in modules:
        module_name = module["name"]
        binary_dir = os.path.join(bindir, gamever, module_name)
        for skill in module.get("skills", []) or []:
            skill_platform = skill.get("platform")
            for platform in PLATFORMS:
                if skill_platform and skill_platform != platform:
                    continue
                try:
                    required, _optional, _combined = ida_analyze_bin.expand_skill_output_paths(
                        binary_dir, skill, platform
                    )
                except ValueError as exc:
                    print(
                        f"  Warning: skipping unresolved output for {module_name}/{skill.get('name')} ({platform}): {exc}"
                    )
                    continue
                outputs.update(required)
    return outputs


def compute_added_output_paths(head_modules, base_modules, gamever, bindir):
    """Return sorted absolute expected_output paths present in head but not base."""
    head_outputs = collect_required_output_paths(head_modules, gamever, bindir)
    base_outputs = collect_required_output_paths(base_modules, gamever, bindir)
    return sorted(head_outputs - base_outputs)


def delete_paths(paths):
    """Delete existing files; return (deleted, absent). A missing file is a no-op."""
    deleted = []
    absent = []
    for path in paths:
        if os.path.exists(path):
            os.remove(path)
            deleted.append(path)
        else:
            absent.append(path)
    return deleted, absent


def load_base_modules(baseref, configyaml):
    """Read the base config.yaml via `git show <baseref>:<configyaml>` and parse it."""
    rev = f"{baseref}:{configyaml}"
    result = subprocess.run(
        ["git", "show", rev],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or f"git show {rev} failed"
        raise RuntimeError(message)

    handle = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8")
    try:
        handle.write(result.stdout)
        handle.close()
        return ida_analyze_bin.parse_config(handle.name)
    finally:
        os.remove(handle.name)


def _display_path(path):
    """Best-effort path relative to cwd for readable logging."""
    try:
        return os.path.relpath(path)
    except ValueError:
        return path


def main(argv=None):
    """Main entry point."""
    args = parse_args(argv)

    if bool(args.baseref) == bool(args.baseconfigyaml):
        print("Error: provide exactly one of -baseref or -baseconfigyaml")
        return ARG_ERROR_EXIT

    if not os.path.exists(args.configyaml):
        print(f"Error: head config file not found: {args.configyaml}")
        return ARG_ERROR_EXIT

    print(f"Head config: {args.configyaml}")
    print(f"Binary directory: {args.bindir}")
    print(f"Game version: {args.gamever}")

    try:
        head_modules = ida_analyze_bin.parse_config(args.configyaml)
    except (ValueError, yaml.YAMLError) as exc:
        print(f"Error: failed to parse head config: {exc}")
        return ARG_ERROR_EXIT

    try:
        if args.baseconfigyaml:
            print(f"Base config: {args.baseconfigyaml}")
            if not os.path.exists(args.baseconfigyaml):
                print(f"Error: base config file not found: {args.baseconfigyaml}")
                return ARG_ERROR_EXIT
            base_modules = ida_analyze_bin.parse_config(args.baseconfigyaml)
        else:
            print(f"Base config: git show {args.baseref}:{args.configyaml}")
            base_modules = load_base_modules(args.baseref, args.configyaml)
    except (ValueError, yaml.YAMLError, RuntimeError) as exc:
        print(f"Error: failed to load base config: {exc}")
        return 1

    added = compute_added_output_paths(head_modules, base_modules, args.gamever, args.bindir)

    if not added:
        print("\nNo PR-added expected_output artifacts; nothing to prune.")
        return 0

    deleted, absent = delete_paths(added)

    print(f"\n{'=' * 50}")
    print(f"PR-added expected_output artifacts: {len(added)}")
    print(f"Deleted from bin: {len(deleted)}; not present (no-op): {len(absent)}")
    for path in deleted:
        print(f"  [DELETED] {_display_path(path)}")
    for path in absent:
        print(f"  [ABSENT ] {_display_path(path)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
