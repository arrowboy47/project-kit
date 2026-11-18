"""Shared, locked API for the project-kit tools.

Every tool imports from here. Do not duplicate this logic in a tool module, and do
not change a signature without architect approval (see PRODUCT_BRIEF.md).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# ── config ──────────────────────────────────────────────────────────────

KIT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = KIT_ROOT / "templates"


def vault_root() -> Path:
    return Path(os.environ.get("PK_VAULT", "~/Documents/Notes")).expanduser()


def projects_root() -> Path:
    return Path(os.environ.get("PK_PROJECTS", "~/projects")).expanduser()


def gh_owner() -> str:
    return os.environ.get("PK_GH_OWNER", "arrowboy47")


def projects_index_path(vault: Path | None = None) -> Path:
    return (vault or vault_root()) / "Projects" / "Projects Index.md"


STATES = ("active", "paused", "done", "archived")
KINDS = ("code", "vault")
VISIBILITIES = ("public", "private")
REQUIRED_ALL = ("type", "topic", "status", "state", "kind", "description", "tags")
REQUIRED_CODE = ("slug", "repo", "visibility")

# ── names ───────────────────────────────────────────────────────────────


def index_basename(name: str) -> str:
    return f"_{name} Index"


def backlog_basename(name: str) -> str:
    return f"{name} Backlog"


def log_basename(name: str) -> str:
    return f"{name} Log"


INDEX_RE = re.compile(r"^_(?P<name>.+) Index\.md$")

# ── frontmatter (minimal YAML subset, stdlib only) ──────────────────────

FM_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.S)


def _scalar(v: str):
    v = v.strip()
    if v == "":
        return ""
    if (v[0] == v[-1]) and v[0] in "\"'" and len(v) >= 2:
        return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [_scalar(x) for x in _split_inline_list(inner)]
    return v


def _split_inline_list(s: str) -> list[str]:
    out, cur, q = [], "", None
    for ch in s:
        if q:
            cur += ch
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
            cur += ch
        elif ch == ",":
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return [x.strip() for x in out]


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter dict, body). Supports `key: scalar`, `key: [a, b]`,
    `key:` followed by `  - item` lines, and `# comments`. Missing frontmatter → ({}, text)."""
    m = FM_RE.match(text)
    if not m:
        return {}, text
    data: dict = {}
    key = None
    for raw in m.group(1).splitlines():
        line = re.sub(r"\s+#.*$", "", raw) if "#" in raw and not raw.strip().startswith("- ") else raw
        if not line.strip() or line.strip().startswith("#"):
            continue
        item = re.match(r"^\s*-\s+(.*)$", line)
        if item and key is not None:
            if not isinstance(data.get(key), list):
                data[key] = []
            data[key].append(_scalar(item.group(1)))
            continue
        kv = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if kv:
            key = kv.group(1)
            data[key] = _scalar(kv.group(2)) if kv.group(2).strip() else []
    return data, text[m.end():]


def _dump_value(v) -> str:
    if isinstance(v, list):
        return "[" + ", ".join(_dump_value(x) for x in v) + "]"
    s = str(v)
    if s == "" or re.search(r"[:#\[\]{},&*!|>'\"%@`]", s) or s != s.strip():
        return '"' + s.replace('"', '\\"') + '"'
    return s


def dump_frontmatter(data: dict) -> str:
    """Serialize back to a `---` block. Lists render inline. Key order preserved."""
    lines = ["---"]
    for k, v in data.items():
        lines.append(f"{k}: {_dump_value(v)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


# ── project discovery ───────────────────────────────────────────────────


@dataclass
class Project:
    name: str
    index: Path                      # absolute path to the index note
    meta: dict = field(default_factory=dict)

    @property
    def folder(self) -> Path:
        return self.index.parent

    @property
    def kind(self) -> str:
        return str(self.meta.get("kind", ""))

    @property
    def state(self) -> str:
        return str(self.meta.get("state", ""))

    @property
    def slug(self) -> str:
        return str(self.meta.get("slug", ""))

    @property
    def repo(self) -> str:
        return str(self.meta.get("repo", ""))

    @property
    def visibility(self) -> str:
        return str(self.meta.get("visibility", ""))

    @property
    def aliases(self) -> list[str]:
        a = self.meta.get("aliases") or []
        return [a] if isinstance(a, str) else list(a)

    @property
    def runs_on(self) -> list[str]:
        r = self.meta.get("runs_on") or []
        return [r] if isinstance(r, str) else list(r)

    @property
    def backlog(self) -> Path:
        return self.folder / f"{backlog_basename(self.name)}.md"

    @property
    def log(self) -> Path:
        return self.folder / f"{log_basename(self.name)}.md"

    @property
    def code_dir(self) -> Path | None:
        return projects_root() / self.slug if self.kind == "code" and self.slug else None


def find_projects(vault: Path | None = None, include_archived: bool = True) -> list[Project]:
    """Every `_<Name> Index.md` one level under `Projects/` (and `Archive/Projects/`)."""
    vault = vault or vault_root()
    roots = [vault / "Projects"]
    if include_archived:
        roots.append(vault / "Archive" / "Projects")
    found = []
    for root in roots:
        if not root.is_dir():
            continue
        for idx in sorted(root.glob("*/_* Index.md")):
            m = INDEX_RE.match(idx.name)
            if not m:
                continue
            meta, _ = parse_frontmatter(idx.read_text(encoding="utf-8"))
            found.append(Project(name=m.group("name"), index=idx, meta=meta))
    return found


def get_project(key: str, vault: Path | None = None) -> Project | None:
    """Look up by display name or slug (exact, then case-insensitive)."""
    projects = find_projects(vault)
    for p in projects:
        if key in (p.name, p.slug):
            return p
    k = key.lower()
    for p in projects:
        if k in (p.name.lower(), p.slug.lower()):
            return p
    return None


# ── templates ───────────────────────────────────────────────────────────


def render_template(template: str, **vars) -> str:
    """Fill `{{var}}` placeholders in templates/<template>. Unknown placeholders raise KeyError."""
    text = (TEMPLATES / template).read_text(encoding="utf-8")
    vars.setdefault("date", date.today().isoformat())

    def sub(m):
        return str(vars[m.group(1)])

    return re.sub(r"\{\{(\w+)\}\}", sub, text)


# ── vault walking and wikilinks ─────────────────────────────────────────

SKIP_DIRS = {".obsidian", ".trash", ".git"}


def iter_notes(vault: Path | None = None):
    """Yield every .md file in the vault, skipping SKIP_DIRS."""
    vault = vault or vault_root()
    for p in sorted(vault.rglob("*.md")):
        if any(part in SKIP_DIRS for part in p.relative_to(vault).parts):
            continue
        yield p


# [[target#heading|display]]  (also matches ![[embeds]], prefix kept by caller)
WIKILINK_RE = re.compile(r"\[\[([^\]|#\n]+)(#[^\]|\n]*)?(?:\|([^\]\n]*))?\]\]")


def basename_map(vault: Path | None = None) -> dict[str, list[Path]]:
    """Lowercased note basename (no .md) → paths. Obsidian matches basenames case-insensitively."""
    out: dict[str, list[Path]] = {}
    for p in iter_notes(vault):
        out.setdefault(p.stem.lower(), []).append(p)
    return out


def link_resolves_to(target: str, note: Path, from_file: Path, vault: Path, bmap: dict) -> bool:
    """True when wikilink `target` written in `from_file` resolves to `note`.

    Rules (Obsidian-compatible enough for this vault): a path-qualified target
    (`a/b/Name`) must match the end of the note's vault-relative path; a bare
    basename resolves to the note when it is the only note with that basename,
    or when it sits in the same folder as `from_file`.
    """
    t = target.strip().removesuffix(".md")
    rel = note.relative_to(vault).with_suffix("").as_posix().lower()
    if "/" in t:
        return rel.endswith(t.lower())
    if t.lower() != note.stem.lower():
        return False
    candidates = bmap.get(t.lower(), [])
    if len(candidates) <= 1:
        return True
    return note.parent == from_file.parent


def rewrite_links_to(text: str, from_file: Path, old_note: Path, new_basename: str,
                     vault: Path, bmap: dict) -> str:
    """Rewrite every wikilink in `text` that resolves to `old_note` so it targets
    `new_basename`, keeping heading anchors and display text. A link with no
    display text gets the old target text as its display, so prose reads the same."""

    def sub(m):
        target, anchor, display = m.group(1), m.group(2) or "", m.group(3)
        if not link_resolves_to(target, old_note, from_file, vault, bmap):
            return m.group(0)
        shown = display if display is not None else target.strip().split("/")[-1]
        if shown == new_basename and not anchor:
            return f"[[{new_basename}]]"
        return f"[[{new_basename}{anchor}|{shown}]]"

    return WIKILINK_RE.sub(sub, text)


def rename_note(old: Path, new: Path, vault: Path | None = None, dry_run: bool = False) -> list[Path]:
    """Move/rename a note and fix every inbound wikilink vault-wide.

    Refuses case-only renames (unsafe on the case-insensitive LiveSync target) and
    refuses to overwrite. Returns the list of files whose links changed (plus the
    moved note). With dry_run nothing is written.
    """
    vault = vault or vault_root()
    if old.resolve() == new.resolve() or str(old).lower() == str(new).lower():
        raise ValueError(f"refusing case-only or no-op rename: {old} -> {new}")
    if new.exists():
        raise FileExistsError(new)
    bmap = basename_map(vault)
    changed: list[Path] = []
    for f in iter_notes(vault):
        text = f.read_text(encoding="utf-8")
        new_text = rewrite_links_to(text, f, old, new.stem, vault, bmap)
        if new_text != text:
            changed.append(f)
            if not dry_run:
                f.write_text(new_text, encoding="utf-8")
    if not dry_run:
        new.parent.mkdir(parents=True, exist_ok=True)
        old.rename(new)
    changed.append(new)
    return changed


def add_to_projects_index(name: str, description: str, section: str = "Active",
                          vault: Path | None = None, dry_run: bool = False) -> bool:
    """Append `N. [[_<name> Index|<name>]]: <description>` under `## <section>` in
    Projects Index (creating the section at the end if missing). No-op and False
    when the index is already linked anywhere in the file."""
    path = projects_index_path(vault)
    text = path.read_text(encoding="utf-8")
    if f"[[{index_basename(name)}" in text:
        return False
    lines = text.rstrip("\n").split("\n")
    head = f"## {section}"
    if head not in lines:
        lines += ["", head, ""]
    start = lines.index(head) + 1
    end = start
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1
    numbered = [l for l in lines[start:end] if re.match(r"^\d+\. ", l)]
    entry = f"{len(numbered) + 1}. [[{index_basename(name)}|{name}]]: {description}"
    insert_at = end
    while insert_at > start and lines[insert_at - 1].strip() == "":
        insert_at -= 1
    lines.insert(insert_at, entry)
    if not dry_run:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True
