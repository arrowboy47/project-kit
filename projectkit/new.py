"""new-project: scaffold a code or vault project. Every step is idempotent (create or skip)."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from projectkit import common as c

RUBRIC = (
    "Pick --private if ANY of these hold, otherwise --public:\n"
    "  1. personal data\n"
    "  2. homelab internals (IPs, hostnames, ports, topology)\n"
    "  3. client or business-confidential material\n"
    "  4. secrets in history that cannot be scrubbed\n"
)

MOC_BLOCK = (
    "\n## Map of content\n\n"
    "- [[{name} Backlog]]: open work, as checkboxes\n"
    "- [[{name} Log]]: what happened, newest first\n"
)


def run(cmd: list[str], cwd=None, timeout=60) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, timeout=timeout, capture_output=True, text=True, check=False)


def default_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _rel(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return str(path)


def _is_git(d: Path) -> bool:
    return (d / ".git").exists()


def _has_origin(d: Path) -> bool:
    cfg = d / ".git" / "config"
    return cfg.is_file() and '[remote "origin"]' in cfg.read_text(encoding="utf-8")


def _has_commit(d: Path) -> bool:
    return run(["git", "rev-parse", "--verify", "-q", "HEAD"], cwd=d).returncode == 0


def _index_text(name: str, slug: str, repo: str, visibility: str, description: str,
                kind: str, state: str) -> str:
    tmpl = "index-code.md" if kind == "code" else "index-vault.md"
    text = c.render_template(tmpl, name=name, slug=slug, repo=repo,
                             visibility=visibility, description=description)
    return re.sub(r"(?m)^state: .*$", f"state: {state}", text, count=1)


def _merge_index(text: str, name: str, kind: str, slug: str, repo: str, visibility: str,
                 description: str, state: str) -> str:
    """Keep every existing frontmatter key and the body; add missing template keys;
    append a Map of content when the body does not link Backlog and Log."""
    existing, body = c.parse_frontmatter(text)
    tmeta, _ = c.parse_frontmatter(_index_text(name, slug, repo, visibility, description, kind, state))
    tmeta["type"] = "project"
    tmeta["topic"] = "project"
    for key, value in tmeta.items():
        existing.setdefault(key, value)
    existing["type"] = "project"
    existing["topic"] = "project"
    missing = [b for b in (c.backlog_basename(name), c.log_basename(name)) if f"[[{b}" not in body]
    if len(missing) == 2:
        body = body.rstrip("\n") + "\n" + MOC_BLOCK.format(name=name)
    elif missing:
        body = body.rstrip("\n") + "\n\n- [[" + missing[0] + "]]\n"
    return c.dump_frontmatter(existing) + body


def _code_steps(name: str, slug: str, folder: str, visibility: str, d: Path, *,
                no_github: bool, dry: bool) -> int:
    repo = f"{c.gh_owner()}/{slug}"

    if d.exists():
        print(f"skip dir {d} (exists)")
    else:
        print(f"create dir {d}")
        if not dry:
            d.mkdir(parents=True)

    if _is_git(d):
        print("skip git repo (exists)")
    else:
        print(f"create git repo in {d}")
        if not dry:
            r = run(["git", "init", "-b", "main"], cwd=d)
            if r.returncode != 0:
                print(f"git init failed: {r.stderr.strip()}", file=sys.stderr)
                return 1

    for fname in ("AGENTS.md", "CLAUDE.md"):
        path = d / fname
        if path.exists():
            print(f"skip {path} (exists)")
        else:
            print(f"create {path}")
            if not dry:
                path.write_text(c.render_template(fname, name=name, folder=folder), encoding="utf-8")

    if _has_origin(d):
        print("skip GitHub origin (exists)")
    elif no_github:
        print("skip GitHub repo (--no-github)")
    else:
        print(f"create GitHub repo {repo} ({visibility})")
        if not dry:
            cmd = ["gh", "repo", "create", repo, f"--{visibility}",
                   "--source", str(d), "--remote", "origin"]
            if _has_commit(d):
                cmd.append("--push")
            r = run(cmd, cwd=d)
            if r.returncode != 0:
                print(f"gh repo create failed: {r.stderr.strip()}", file=sys.stderr)
                return 1
    return 0


def _vault_steps(vault: Path, name: str, slug: str, folder: str, kind: str, repo: str,
                 visibility: str, description: str, state: str, from_note: str | None,
                 dry: bool) -> int:
    proj_dir = vault / "Projects" / folder
    if proj_dir.is_dir():
        print(f"skip Projects/{folder} (exists)")
    else:
        print(f"create Projects/{folder}")
        if not dry:
            proj_dir.mkdir(parents=True)

    index = proj_dir / f"{c.index_basename(name)}.md"
    label = _rel(index, vault)
    if index.exists():
        print(f"skip {label} (exists)")
    elif from_note:
        src = vault / from_note
        if not src.is_file():
            print(f"--from-note not found: {src}", file=sys.stderr)
            return 1
        print(f"create {label} (renamed from {from_note})")
        if not dry:
            changed = c.rename_note(src, index, vault)
            print(f"  rewrote inbound links in {len(changed) - 1} file(s)")
            merged = _merge_index(index.read_text(encoding="utf-8"), name, kind, slug, repo,
                                  visibility, description, state)
            index.write_text(merged, encoding="utf-8")
    else:
        print(f"create {label}")
        if not dry:
            index.write_text(_index_text(name, slug, repo, visibility, description, kind, state),
                             encoding="utf-8")

    for fname, tmpl in ((f"{c.backlog_basename(name)}.md", "backlog.md"),
                        (f"{c.log_basename(name)}.md", "log.md")):
        path = proj_dir / fname
        if path.exists():
            print(f"skip {_rel(path, vault)} (exists)")
        else:
            print(f"create {_rel(path, vault)}")
            if not dry:
                path.write_text(c.render_template(tmpl, name=name), encoding="utf-8")

    section = "Done" if state == "done" else state.capitalize()
    if c.add_to_projects_index(name, description, section=section, vault=vault, dry_run=dry):
        print(f"create Projects Index line under ## {section}")
    else:
        print("skip Projects Index line (exists)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="new-project", description="Create a code or vault project.")
    ap.add_argument("name")
    ap.add_argument("--kind", required=True, choices=c.KINDS)
    ap.add_argument("--description", required=True)
    ap.add_argument("--slug")
    vis = ap.add_mutually_exclusive_group()
    vis.add_argument("--public", action="store_true")
    vis.add_argument("--private", action="store_true")
    ap.add_argument("--folder")
    ap.add_argument("--state", choices=c.STATES, default="active")
    ap.add_argument("--adopt", action="store_true", help="use an existing code dir")
    ap.add_argument("--from-note", metavar="VAULT_REL_PATH", help="rename an existing hub note into the index")
    ap.add_argument("--no-github", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    name = args.name.strip()
    if not name:
        print("name must not be empty", file=sys.stderr)
        return 2
    if args.kind == "code" and not (args.public or args.private):
        print("--kind code needs exactly one of --public or --private.", file=sys.stderr)
        print(RUBRIC, end="", file=sys.stderr)
        return 2

    slug = args.slug or default_slug(name)
    if not slug:
        print("could not derive a slug from NAME; pass --slug", file=sys.stderr)
        return 2
    folder = args.folder or name
    dry = args.dry_run
    vault = c.vault_root()

    if args.kind == "code":
        visibility = "private" if args.private else "public"
        repo = f"{c.gh_owner()}/{slug}"
        d = c.projects_root() / slug
        if d.exists() and not args.adopt:
            print(f"{d} already exists, use --adopt", file=sys.stderr)
            return 1
        try:
            rc = _code_steps(name, slug, folder, visibility, d, no_github=args.no_github, dry=dry)
        except (OSError, ValueError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        if rc:
            return rc
    else:
        visibility = ""
        repo = ""

    try:
        rc = _vault_steps(vault, name, slug, folder, args.kind, repo, visibility,
                          args.description, args.state, args.from_note, dry)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if rc:
        return rc

    print(f"done: {name}. End each work session with a {name} Log entry.")
    return 0
