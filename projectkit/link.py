"""link-projects: link project mentions and fix old ~/Projects paths across the vault.

Dry run by default (prints a unified diff). --apply writes the files.

Linking never touches protected regions: frontmatter, fenced code, heading lines,
the `## History` section (up to the next `## ` heading), inline code spans, existing
[[wikilinks]], [text](links), and bare URLs. Path fixes run everywhere except
frontmatter and the `## History` section.
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from projectkit import common

EXCLUDED_PARTS = {"Archive", "Templates"}
EXCLUDED_FILES = {"Reference/Guides/Stack Log.md", "Projects/Projects Index.md"}
DAILY_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
DAILY_MAX_AGE_DAYS = 7

FM_RE = re.compile(r"\A---[ \t]*\r?\n(?:.*?\r?\n)?---[ \t]*(?:\r?\n|\Z)", re.S)
OPEN_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
CLOSE_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})\s*$")
HEADING_RE = re.compile(r"^\s{0,3}#")
HISTORY_RE = re.compile(r"^## History\s*$")
INLINE_RES = (
    re.compile(r"(`+).+?\1"),                          # inline code span
    re.compile(r"!?\[\[.*?\]\]"),                      # wikilink / embed
    re.compile(r"!?\[[^\]\n]*\]\([^)\n]*\)"),          # [text](url)
    re.compile(r"(?:https?|ftp)://[^\s<>\"']+"),       # bare URL
    re.compile(r"www\.[^\s<>\"']+"),                   # bare www URL
)
PATH_RE = re.compile(r"(~|/home/arrowboy|/home/Jadu)/Projects/")


# ── region classification ───────────────────────────────────────────────


def _classify(text: str) -> list[tuple[int, int, str]]:
    """Return (start, end, kind) for the frontmatter and every body line.

    kind is one of: fm, hist, fence, heading, text. Offsets index into `text`
    and exclude the trailing newline of each line.
    """
    spans: list[tuple[int, int, str]] = []
    body_start = 0
    fm = FM_RE.match(text)
    if fm:
        spans.append((0, fm.end(), "fm"))
        body_start = fm.end()

    fence: tuple[str, int] | None = None
    in_history = False
    pos = body_start
    for chunk in text[body_start:].split("\n"):
        start, end = pos, pos + len(chunk)
        pos = end + 1
        line = chunk.rstrip("\r")
        if in_history and not line.startswith("## "):
            kind = "hist"
        elif fence is not None:
            kind = "fence"
            m = CLOSE_FENCE_RE.match(line)
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1]:
                fence = None
        else:
            in_history = False
            m = OPEN_FENCE_RE.match(line)
            if m:
                fence = (m.group(1)[0], len(m.group(1)))
                kind = "fence"
            elif HISTORY_RE.match(line):
                in_history = True
                kind = "hist"
            elif HEADING_RE.match(line):
                kind = "heading"
            else:
                kind = "text"
        spans.append((start, end, kind))
    return spans


def _linkable_mask(text: str) -> bytearray:
    """1 for characters a new wikilink may cover, 0 for protected characters."""
    mask = bytearray(len(text))
    for start, end, kind in _classify(text):
        if kind != "text":
            continue
        mask[start:end] = b"\x01" * (end - start)
        chunk = text[start:end]
        for rx in INLINE_RES:
            for m in rx.finditer(chunk):
                a, b = start + m.start(), start + m.end()
                mask[a:b] = b"\x00" * (b - a)
    return mask


def _frozen_mask(text: str) -> bytearray:
    """1 for characters that path fixes must not touch (frontmatter, History)."""
    mask = bytearray(len(text))
    for start, end, kind in _classify(text):
        if kind in ("fm", "hist"):
            mask[start:end] = b"\x01" * (end - start)
    return mask


# ── transforms ──────────────────────────────────────────────────────────


def _in_project_folder(rel: str, project: common.Project) -> bool:
    dirs = Path(rel).parts[:-1]
    folder = project.folder.name
    return any(dirs[i] == "Projects" and dirs[i + 1] == folder for i in range(len(dirs) - 1))


def _link_one(text: str, rel: str, project: common.Project) -> tuple[str, int]:
    """Link the first unprotected mention of `project` in `text` (at most one link)."""
    target = common.index_basename(project.name)
    if f"[[{target}" in text or _in_project_folder(rel, project):
        return text, 0
    names = sorted(set([project.name] + project.aliases) - {""}, key=len, reverse=True)
    if not names:
        return text, 0
    rx = re.compile(r"(?<![\w/.-])(?:" + "|".join(re.escape(n) for n in names) + r")(?![\w-])")
    mask = _linkable_mask(text)
    for m in rx.finditer(text):
        a, b = m.start(), m.end()
        if 0 in mask[a:b]:
            continue
        return text[:a] + f"[[{target}|{m.group(0)}]]" + text[b:], 1
    return text, 0


def _fix_paths(text: str) -> tuple[str, int]:
    frozen = _frozen_mask(text)
    out: list[str] = []
    last = 0
    count = 0
    for m in PATH_RE.finditer(text):
        if frozen[m.start()]:
            continue
        out.append(text[last:m.start()])
        out.append(f"{m.group(1)}/projects/")
        last = m.end()
        count += 1
    out.append(text[last:])
    return "".join(out), count


def transform(text: str, rel_path: str, projects: list[common.Project],
              today: date) -> tuple[str, int, int]:
    """Return (new_text, links_added, path_fixes). Note selection lives in include_note,
    so `today` is accepted for the locked signature and not otherwise used here."""
    links = 0
    for project in projects:
        if project.state == "archived":
            continue
        text, added = _link_one(text, rel_path, project)
        links += added
    text, fixes = _fix_paths(text)
    return text, links, fixes


def include_note(rel: Path, today: date) -> bool:
    """Vault-relative note selection (see BUILD_PLAN Task 07)."""
    parts = rel.parts
    if EXCLUDED_PARTS.intersection(parts):
        return False
    if rel.name.endswith(" Log.md"):
        return False
    if rel.as_posix() in EXCLUDED_FILES:
        return False
    if parts and parts[0] == "Daily":
        m = DAILY_RE.match(rel.name) if len(parts) == 2 else None
        if not m:
            return False
        try:
            day = date.fromisoformat(m.group(1))
        except ValueError:
            return False
        if day < today - timedelta(days=DAILY_MAX_AGE_DAYS):
            return False
    return True


# ── vault driver ────────────────────────────────────────────────────────


@dataclass
class Change:
    rel: str
    old: str
    new: str
    links: int
    fixes: int


def plan(vault: Path, projects: list[common.Project], today: date) -> list[Change]:
    changes: list[Change] = []
    for note in common.iter_notes(vault):
        rel = note.relative_to(vault)
        if not include_note(rel, today):
            continue
        with open(note, encoding="utf-8", newline="") as fh:
            old = fh.read()
        new, links, fixes = transform(old, rel.as_posix(), projects, today)
        if new != old:
            changes.append(Change(rel.as_posix(), old, new, links, fixes))
    return changes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="link-projects",
        description="Link project mentions and fix ~/Projects paths in the vault. Dry run unless --apply.",
    )
    parser.add_argument("--apply", action="store_true", help="write the changes")
    parser.add_argument("--project", metavar="NAME", help="link only this project (name or slug)")
    args = parser.parse_args(argv)

    vault = common.vault_root()
    projects = [p for p in common.find_projects(vault) if p.state != "archived"]
    if args.project:
        key = args.project.lower()
        projects = [p for p in projects if key in (p.name.lower(), p.slug.lower())]
        if not projects:
            print(f"no active project named {args.project}", file=sys.stderr)
            return 2

    changes = plan(vault, projects, date.today())
    if args.apply:
        for c in changes:
            with open(vault / c.rel, "w", encoding="utf-8", newline="") as fh:
                fh.write(c.new)
    else:
        for c in changes:
            sys.stdout.writelines(difflib.unified_diff(
                c.old.splitlines(keepends=True),
                c.new.splitlines(keepends=True),
                fromfile=f"a/{c.rel}",
                tofile=f"b/{c.rel}",
            ))
    print(f"files: {len(changes)}, links: {sum(c.links for c in changes)}, "
          f"path fixes: {sum(c.fixes for c in changes)}")
    return 0
