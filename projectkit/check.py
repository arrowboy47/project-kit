"""project-check: validate the project invariants (PRODUCT_BRIEF.md) for one project, all projects, or the ~/projects layout."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from projectkit import common

REPO_RE = re.compile(r"^[\w.-]+/[\w.-]+$")


def run(cmd: list[str], cwd=None, timeout=60) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, timeout=timeout, capture_output=True, text=True, check=False)


def _run_ok(cmd: list[str], cwd=None):
    """Run via the module-level run(); None when the command is missing, times out, or exits non-zero."""
    try:
        r = run(cmd, cwd=cwd)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r if r.returncode == 0 else None


def _check_code_dir(p: common.Project) -> list[str]:
    if not p.slug:
        return []  # missing slug is already reported by invariant 1
    base = common.projects_root()
    d = base / "_archive" / p.slug if p.state == "archived" else base / p.slug
    if not d.is_dir():
        return [f"code dir missing: {d}"]
    problems: list[str] = []
    top = _run_ok(["git", "rev-parse", "--show-toplevel"], cwd=d)
    if top is None or Path(top.stdout.strip()).resolve() != d.resolve():
        problems.append(f"not a git repo: {d}")
    elif p.repo:
        url = _run_ok(["git", "remote", "get-url", "origin"], cwd=d)
        if url is None:
            problems.append("no origin remote")
        elif not re.search(rf"github\.com[:/]{re.escape(p.repo)}(\.git)?/?$", url.stdout.strip()):
            problems.append(f"origin is {url.stdout.strip()}, expected github.com/{p.repo}")
    for f in ("AGENTS.md", "CLAUDE.md"):
        if not (d / f).is_file():
            problems.append(f"missing {f} in {d}")
    return problems


def _check_workspace_dir(p: common.Project) -> list[str]:
    """A workspace root is not a git repo; each child folder that is a repo needs a GitHub origin."""
    if not p.slug:
        return []
    base = common.projects_root()
    d = base / "_archive" / p.slug if p.state == "archived" else base / p.slug
    if not d.is_dir():
        return [f"workspace dir missing: {d}"]
    problems: list[str] = []
    for f in ("AGENTS.md", "CLAUDE.md"):
        if not (d / f).is_file():
            problems.append(f"missing {f} in {d}")
    for child in sorted(d.iterdir()):
        if child.name.startswith(".") or not (child / ".git").exists():
            continue
        url = _run_ok(["git", "remote", "get-url", "origin"], cwd=child)
        if url is None or "github.com" not in url.stdout:
            problems.append(f"child repo {child.name} has no GitHub origin")
    return problems


def check_project(p: common.Project, vault: Path, *, vault_only: bool = False,
                  remote_visibility: bool = False) -> list[str]:
    """Return problem strings for one project. Empty list means OK."""
    problems: list[str] = []
    name = p.name
    meta = p.meta
    is_code = p.kind == "code"
    is_ws = p.kind == "workspace"

    # 1. frontmatter keys and legal values
    for key in common.REQUIRED_ALL:
        if key not in meta:
            problems.append(f"missing key: {key}")
    if "kind" in meta and p.kind not in common.KINDS:
        problems.append(f"bad kind: {p.kind}")
    if "state" in meta and p.state not in common.STATES:
        problems.append(f"bad state: {p.state}")
    if is_code:
        for key in common.REQUIRED_CODE:
            if key not in meta:
                problems.append(f"missing key: {key}")
        if "visibility" in meta and p.visibility not in common.VISIBILITIES:
            problems.append(f"bad visibility: {p.visibility}")
        if "repo" in meta and not REPO_RE.match(p.repo):
            problems.append(f"bad repo: {p.repo}")

    # 2. backlog and log exist and are linked from the index
    index_text = p.index.read_text(encoding="utf-8")
    for note, basename in ((p.backlog, common.backlog_basename(name)), (p.log, common.log_basename(name))):
        if not note.is_file():
            problems.append(f"missing note: {note.name}")
        if f"[[{basename}" not in index_text:
            problems.append(f"index does not link [[{basename}]]")

    # 3. Projects Index links this project
    pidx = common.projects_index_path(vault)
    if not pidx.is_file():
        problems.append(f"Projects Index missing: {pidx}")
    elif f"[[{common.index_basename(name)}" not in pidx.read_text(encoding="utf-8"):
        problems.append(f"Projects Index does not link [[{common.index_basename(name)}]]")

    # 4. code directory, git remote, agent files
    if is_code and not vault_only:
        problems.extend(_check_code_dir(p))

    if is_ws:
        if "slug" not in meta:
            problems.append("missing key: slug")
        if not vault_only:
            problems.extend(_check_workspace_dir(p))

    # 5. remote visibility matches the index (network, opt-in)
    if remote_visibility and is_code and p.repo:
        r = _run_ok(["gh", "repo", "view", p.repo, "--json", "visibility", "-q", ".visibility"])
        if r is None:
            problems.append(f"gh repo view failed for {p.repo}")
        else:
            actual = r.stdout.strip().lower()
            if actual != p.visibility.lower():
                problems.append(f"remote visibility is {actual or 'unknown'}, index says {p.visibility}")

    # 6. runs_on implies a Reference/Guides/Projects note that links back
    if p.runs_on:
        guide = vault / "Reference" / "Guides" / "Projects" / f"{name}.md"
        if not guide.is_file():
            problems.append(f"missing Reference/Guides/Projects/{name}.md")
        else:
            if "[[" + common.index_basename(name) not in guide.read_text(encoding="utf-8"):
                problems.append(f"Guides note does not link [[{common.index_basename(name)}]]")
        if not (f"Reference/Guides/Projects/{name}" in index_text
                or f"[[{name}]]" in index_text or f"[[{name}|" in index_text):
            problems.append(f"index does not link Reference/Guides/Projects/{name}")

    return problems


def check_layout(projects: list[common.Project], root: Path) -> list[str]:
    """Every top-level entry of root must be a code slug, _archive, hidden, or a symlink."""
    if not root.is_dir():
        return []
    slugs = {p.slug for p in projects if p.kind in ("code", "workspace") and p.slug}
    problems: list[str] = []
    for entry in sorted(root.iterdir()):
        if entry.name.startswith(".") or entry.name == "_archive" or entry.is_symlink():
            continue
        if entry.name not in slugs:
            problems.append(f"unknown dir in ~/projects: {entry.name}")
    return problems


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="project-check", description="Validate project invariants.")
    ap.add_argument("names", nargs="*", metavar="NAME_OR_SLUG")
    ap.add_argument("--all", action="store_true", help="check every project")
    ap.add_argument("--vault-only", action="store_true", help="skip code directory checks")
    ap.add_argument("--remote-visibility", action="store_true", help="compare visibility with GitHub (uses gh)")
    ap.add_argument("--layout", action="store_true", help="check the top level of ~/projects")
    return ap


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 2
    if not args.names and not args.all and not args.layout:
        print("project-check: give NAME_OR_SLUG, --all, or --layout", file=sys.stderr)
        return 2

    vault = common.vault_root()
    everything = common.find_projects(vault)
    fails = 0

    targets: list[common.Project] = []
    seen: set[Path] = set()

    def add(p: common.Project):
        if p.index not in seen:
            seen.add(p.index)
            targets.append(p)

    if args.all:
        for p in everything:
            add(p)
    for key in args.names:
        p = common.get_project(key, vault)
        if p is None:
            print(f"FAIL {key}: no project with that name or slug")
            fails += 1
            continue
        add(p)

    for p in targets:
        problems = check_project(p, vault, vault_only=args.vault_only,
                                 remote_visibility=args.remote_visibility)
        if problems:
            for problem in problems:
                print(f"FAIL {p.name}: {problem}")
            fails += len(problems)
        else:
            print(f"OK {p.name}")

    if args.layout:
        for problem in check_layout(everything, common.projects_root()):
            print(f"FAIL layout: {problem}")
            fails += 1

    return 1 if fails else 0
