"""projects-status: one-screen health view of every repo under the projects root."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from projectkit import common

KEYS = ("slug", "git", "branch", "head", "upstream", "ahead", "behind",
        "dirty", "origin", "last_commit")
COMPARE_KEYS = ("slug", "here", "there", "issue")


class RemoteError(Exception):
    pass


def run(cmd: list[str], cwd=None, timeout=60) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, timeout=timeout,
                          capture_output=True, text=True, check=False)


def _git(path: Path, *args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    try:
        return run(["git", *args], cwd=str(path), timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(["git", *args], 124, "", "timeout")


def _out(r: subprocess.CompletedProcess) -> str | None:
    text = r.stdout.strip() if r.returncode == 0 else ""
    return text or None


def _is_repo(path: Path) -> bool:
    top = _out(_git(path, "rev-parse", "--show-toplevel"))
    return top is not None and Path(top).resolve() == path.resolve()


def describe(path: Path, fetch: bool = False) -> dict:
    row = dict.fromkeys(KEYS)
    row["slug"] = path.name
    row["git"] = False
    if not _is_repo(path):
        return row
    row["git"] = True
    if fetch:
        r = _git(path, "fetch", "--quiet", timeout=30)
        if r.returncode != 0:
            reason = (r.stderr or "").strip().splitlines()[-1:] or ["unknown error"]
            print(f"warning: fetch failed for {path.name}: {reason[0]}", file=sys.stderr)
    row["branch"] = _out(_git(path, "rev-parse", "--abbrev-ref", "HEAD"))
    row["head"] = _out(_git(path, "rev-parse", "--short", "HEAD"))
    row["upstream"] = _out(_git(path, "rev-parse", "--abbrev-ref", "@{u}"))
    if row["upstream"]:
        counts = _out(_git(path, "rev-list", "--left-right", "--count", "@{u}...HEAD"))
        if counts:
            behind, ahead = counts.split()
            row["behind"], row["ahead"] = int(behind), int(ahead)
    st = _git(path, "status", "--porcelain")
    if st.returncode == 0:
        row["dirty"] = len([line for line in st.stdout.splitlines() if line.strip()])
    row["origin"] = _out(_git(path, "remote", "get-url", "origin"))
    row["last_commit"] = _out(_git(path, "log", "-1", "--format=%cs"))
    return row


def _visible_dirs(parent: Path) -> list[Path]:
    out = []
    for entry in sorted(parent.iterdir()):
        if entry.name.startswith(".") or entry.is_symlink() or not entry.is_dir():
            continue
        out.append(entry)
    return out


def scan(include_archived: bool = False, fetch: bool = False,
         root: Path | None = None) -> list[dict]:
    root = root or common.projects_root()
    if not root.is_dir():
        return []
    targets: list[Path] = []
    for entry in _visible_dirs(root):
        if entry.name == "_archive":
            if include_archived:
                targets.extend(_visible_dirs(entry))
            continue
        targets.append(entry)
    return [describe(t, fetch=fetch) for t in targets]


def compare(local: list[dict], remote: list[dict]) -> list[dict]:
    lmap = {r["slug"]: r for r in local}
    rmap = {r["slug"]: r for r in remote}
    rows = []
    for slug in sorted(set(lmap) | set(rmap)):
        a, b = lmap.get(slug), rmap.get(slug)
        if a is None:
            issue = "only-there"
        elif b is None:
            issue = "only-here"
        elif a.get("branch") != b.get("branch"):
            issue = "branch-differs"
        elif a.get("git") and b.get("git") and a.get("head") != b.get("head"):
            issue = "head-differs"
        else:
            issue = ""
        rows.append({"slug": slug, "here": a is not None,
                     "there": b is not None, "issue": issue})
    return rows


def local_problems(row: dict) -> list[str]:
    if not row["git"]:
        return ["not a git repo"]
    out = []
    if (row["dirty"] or 0) > 0:
        out.append(f"dirty {row['dirty']}")
    if (row["ahead"] or 0) > 0:
        out.append(f"ahead {row['ahead']}")
    if (row["behind"] or 0) > 0:
        out.append(f"behind {row['behind']}")
    if row["origin"] is None:
        out.append("no origin")
    return out


def fetch_remote(host: str) -> list[dict]:
    cmd = ["ssh", "-o", "BatchMode=yes", host,
           os.environ.get("PK_REMOTE_CMD", "projects-status --json")]
    try:
        r = run(cmd, timeout=60)
    except subprocess.TimeoutExpired:
        raise RemoteError(f"ssh {host} timed out")
    if r.returncode != 0:
        raise RemoteError(f"ssh {host} failed (rc {r.returncode}): {r.stderr.strip()[:200]}")
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as e:
        raise RemoteError(f"could not parse output from {host}: {e}")


def _table(headers: list[str], rows: list[list[str]]) -> str:
    allrows = [headers] + rows
    widths = [max(len(r[i]) for r in allrows) for i in range(len(headers))]
    return "\n".join("  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip()
                     for r in allrows)


def _local_table(rows: list[dict]) -> str:
    cells = []
    for r in rows:
        if not r["git"]:
            cells.append([r["slug"], "not a git repo", "-", "-", "-", "-", "-"])
            continue
        sync = "-" if r["upstream"] is None else f"+{r['ahead']} -{r['behind']}"
        cells.append([r["slug"], r["branch"] or "-", r["head"] or "-", sync,
                      str(r["dirty"]), r["last_commit"] or "-", r["origin"] or "-"])
    return _table(["NAME", "BRANCH", "HEAD", "SYNC", "DIRTY", "LAST", "ORIGIN"], cells)


def _compare_table(rows: list[dict]) -> str:
    cells = [[r["slug"], "yes" if r["here"] else "no",
              "yes" if r["there"] else "no", r["issue"] or "-"] for r in rows]
    return _table(["NAME", "HERE", "THERE", "ISSUE"], cells)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="projects-status",
                                 description="Git health of every repo under the projects root.")
    ap.add_argument("--all", action="store_true", help="include _archive/ contents")
    ap.add_argument("--fetch", action="store_true", help="git fetch each repo first")
    ap.add_argument("--json", action="store_true", help="print JSON instead of a table")
    ap.add_argument("--remote", metavar="HOST", help="compare with projects-status on HOST over ssh")
    ap.add_argument("--strict", action="store_true", help="exit 1 on any problem")
    args = ap.parse_args(argv)

    local = scan(include_archived=args.all, fetch=args.fetch)
    problems: list[str] = []
    for row in local:
        problems += [f"{row['slug']}: {p}" for p in local_problems(row)]

    if args.remote:
        try:
            remote = fetch_remote(args.remote)
        except RemoteError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        rows = compare(local, remote)
        if args.json:
            print(json.dumps(rows, indent=1))
        else:
            print(_compare_table(rows))
        problems += [f"{r['slug']}: {r['issue']}" for r in rows if r["issue"]]
    else:
        if args.json:
            print(json.dumps(local, indent=1))
        else:
            print(_local_table(local))

    if args.strict and problems:
        for p in problems:
            print(f"strict: {p}", file=sys.stderr)
        return 1
    return 0
