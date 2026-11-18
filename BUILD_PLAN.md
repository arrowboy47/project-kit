# BUILD_PLAN: Project Kit and the project-system rollout

Approved plan: `~/.claude/plans/pasted-content-id-a196-i-have-keen-rain.md` (2026-11-17). Brief, data model and invariants: `PRODUCT_BRIEF.md`.

**Locked shared state.** `projectkit/common.py` and `tests/conftest.py` are architect-owned. Contractors import from them and never edit them. Frontmatter fields are exactly those in PRODUCT_BRIEF.md.

**Contractor rules (every task).** Python 3 stdlib only. Touch only the files the task names. All subprocess calls go through a module-level `run(cmd: list[str], cwd=None, timeout=60) -> subprocess.CompletedProcess` (`capture_output=True, text=True, check=False`) so tests can monkeypatch it. Tests must never hit the network or real `~/projects` / vault (use the `vault` and `projects` fixtures). Each tool module exposes `main(argv: list[str] | None = None) -> int`. Each `bin/<cmd>` is:

```python
#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from projectkit.<module> import main
sys.exit(main())
```

(made executable). No em dashes in any text output or docs.

---

## Task 01: Backups [architect] ✅ 2026-11-17

Vault tarball, mochtop `~/Projects ~/projects ~/Documents/codin`, Z4 `~/projects`, Hermes skills/SOUL/memory/config/cron, both `~/.claude/CLAUDE.md`. In `~/backups-20261117/` on each machine.

Verify: `tar tzf ~/backups-20261117/mochtop-projects.tgz >/dev/null && ssh jadu 'tar tzf ~/backups-20261117/z4-projects.tgz >/dev/null'`

## Task 02: Kit skeleton [architect] ✅ 2026-11-17

Repo, brief, this plan, templates, `common.py`, fixtures.

Verify: `cd ~/projects/project-kit && python3 -m pytest tests/test_common.py`

## Task 03: Vault spec note [architect] ✅ 2026-11-17

Write `Reference/Guides/Workflow/Project Workflow.md` (`type: howto`) from the plan's conventions and rubric.

Verify: `python3 ~/Projects/automations/vault-lint/vault_lint.py "Workflow/Project Workflow.md"`

## Task 04: `projects-status` ✅ 2026-11-17

Files: `projectkit/status.py`, `bin/projects-status`, `tests/test_status.py`.

- Scan top-level dirs of `common.projects_root()`. Skip names starting with `.`; skip `_archive` unless `--all`. Skip symlinks.
- Per dir produce a dict with keys exactly: `slug, git, branch, head, upstream, ahead, behind, dirty, origin, last_commit`.
  - Not a git repo: `git=False`, others `None`.
  - `head`: short sha. `upstream`: `git rev-parse --abbrev-ref @{u}` or `None`. `ahead`/`behind`: from `git rev-list --left-right --count @{u}...HEAD` (behind is the left number), `None` without upstream. `dirty`: number of `git status --porcelain` lines. `origin`: `git remote get-url origin` or `None`. `last_commit`: `git log -1 --format=%cs` or `None`.
- `--fetch`: `git fetch --quiet` per repo first (timeout 30 s); a failure prints a warning line and continues.
- `--json`: print `json.dumps(list, indent=1)`. Otherwise print an aligned text table.
- `--remote HOST`: run `["ssh", "-o", "BatchMode=yes", HOST, os.environ.get("PK_REMOTE_CMD", "projects-status --json")]`, parse its JSON, and print the comparison from a pure function `compare(local: list[dict], remote: list[dict]) -> list[dict]`. Each row: `slug, here (bool), there (bool), issue` where issue is one of `only-here`, `only-there`, `head-differs` (both git, same branch, different head), `branch-differs`, or `""`.
- `--strict`: exit 1 when any local repo has `dirty>0`, `ahead>0`, `behind>0`, `git=False`, or `origin=None`; with `--remote`, also when any compare row has a non-empty issue. Without `--strict` always exit 0.

Tests (≥6): clean repo is strict-clean; a dirty file makes strict exit 1; a non-git dir is reported and fails strict; `_archive` skipped by default and listed with `--all`; `--json` output parses and has the exact keys; `compare()` covers all five issue values.

Verify: `cd ~/projects/project-kit && python3 -m pytest tests/test_status.py && ./bin/projects-status --json | python3 -m json.tool >/dev/null`

## Task 05: `project-check` ✅ 2026-11-17

Files: `projectkit/check.py`, `bin/project-check`, `tests/test_check.py`.

- CLI: `project-check [NAME_OR_SLUG ...] [--all] [--vault-only] [--remote-visibility] [--layout]`. No names and no `--all` and no `--layout` → usage error exit 2.
- Pure function `check_project(p: common.Project, vault: Path, *, vault_only=False, remote_visibility=False) -> list[str]` returning problem strings (empty = OK):
  1. Every key in `common.REQUIRED_ALL` present; `kind` in `KINDS`; `state` in `STATES`. For `kind: code`, every key in `REQUIRED_CODE`, `visibility` in `VISIBILITIES`, `repo` matches `^[\w.-]+/[\w.-]+$`.
  2. `p.backlog` and `p.log` exist; index text contains `[[<Name> Backlog` and `[[<Name> Log`.
  3. `common.projects_index_path(vault)` text contains `[[_<Name> Index`.
  4. Unless `vault_only`, for code: dir = `projects_root()/slug`, or `projects_root()/_archive/slug` when `state: archived`. Must exist, be a git repo, `git remote get-url origin` must contain `github.com/<repo>` or `github.com:<repo>` (optional `.git` suffix), and `AGENTS.md` and `CLAUDE.md` must exist there.
  5. If `remote_visibility` (and code): `gh repo view <repo> --json visibility -q .visibility` lowercased must equal `visibility`.
  6. If `runs_on` non-empty: `vault/Reference/Guides/Projects/<Name>.md` exists; the index contains `Reference/Guides/Projects/<Name>` or `[[<Name>]]` or `[[<Name>|`; the Guides note contains `[[_<Name> Index`.
- Pure function `check_layout(projects: list[Project], root: Path) -> list[str]`: every top-level entry of `root` that is not hidden, not `_archive`, not a symlink, must be the slug of some code project, else `unknown dir in ~/projects: <name>`.
- Output: `OK <Name>` or one `FAIL <Name>: <problem>` line per problem; layout problems as `FAIL layout: <problem>`. Exit 1 if any FAIL.

Tests (≥8): fixture `--all` passes (with both fixtures); each of invariants 1, 2, 3, 4 broken produces a FAIL; vault-only skips 4; runs_on missing Guides note fails; layout flags an unknown dir and ignores `_archive` and symlinks; gh is monkeypatched for 5.

Verify: `cd ~/projects/project-kit && python3 -m pytest tests/test_check.py`

## Task 06: `new-project` ✅ 2026-11-17

Files: `projectkit/new.py`, `bin/new-project`, `tests/test_new.py`.

- CLI: `new-project NAME --kind {code,vault} --description TEXT [--slug S] [--public | --private] [--folder F] [--state {active,paused,done,archived}] [--adopt] [--from-note VAULT_REL_PATH] [--no-github] [--dry-run]`.
- `--kind code` without exactly one of `--public/--private` → exit 2 and print the visibility rubric: private if it holds (1) personal data, (2) homelab internals (IPs, hostnames, ports, topology), (3) client/business-confidential material, (4) unscrubbable secrets in history; otherwise public.
- Default slug: NAME lowercased, runs of non-alphanumerics → `-`, stripped of `-`. Default folder: NAME. Default state: active.
- Every step prints `create <what>` or `skip <what> (exists)`. `--dry-run` prints the same lines and writes nothing, runs nothing.
- Code steps:
  1. `dir = projects_root()/slug`. Exists without `--adopt` → exit 1 `already exists, use --adopt`. Else mkdir.
  2. Not a git repo → `git init -b main`.
  3. `AGENTS.md`, `CLAUDE.md` from templates if missing (vars: name, folder).
  4. No `origin` and not `--no-github` → `gh repo create <owner>/<slug> --public|--private --source <dir> --remote origin`, adding `--push` only if the repo has at least one commit.
- Vault steps (both kinds):
  5. `folder = vault/Projects/<folder>`; mkdir.
  6. Index `folder/_<NAME> Index.md`:
     - With `--from-note`: `common.rename_note(vault/from_note, index_path, vault)`, then merge frontmatter: keep every existing key and value; add missing keys from the template's frontmatter (rendered with the CLI values; for `type` and `topic` force `project`); if the body lacks `[[<NAME> Backlog` or `[[<NAME> Log`, append `\n## Map of content\n\n- [[<NAME> Backlog]]: open work, as checkboxes\n- [[<NAME> Log]]: what happened, newest first\n`. Keep the original body otherwise.
     - Else if missing: render `index-code.md` or `index-vault.md` (vars: name, slug, repo=`<owner>/<slug>`, visibility, description), and set `state:` to the CLI state.
  7. Backlog and Log from templates if missing.
  8. `common.add_to_projects_index(NAME, description, section=state.capitalize() if state != "done" else "Done")`.
- Never overwrite an existing file. Last line: `done: <NAME>. End each work session with a <NAME> Log entry.`

Tests (≥7): vault project creates 3 notes + index line; code project creates dir, git repo, AGENTS.md/CLAUDE.md, and calls gh with `--private` (run monkeypatched to record; let `git` calls run for real inside tmp); refusal without visibility (exit 2); existing dir without `--adopt` exits 1; `--adopt` on Demo App changes no existing file (compare mtimes/content); `--from-note` renames an old hub note, keeps its body, adds missing keys, and rewrites an inbound link elsewhere; `--dry-run` writes nothing.

Verify: `cd ~/projects/project-kit && python3 -m pytest tests/test_new.py`

## Task 07: `link-projects` ✅ 2026-11-17

Files: `projectkit/link.py`, `bin/link-projects`, `tests/test_link.py`.

- CLI: `link-projects [--apply] [--project NAME]`. Default is a dry run that prints a unified diff (`difflib.unified_diff`, `a/<rel>` `b/<rel>`) and a summary line `files: N, links: M, path fixes: K`. `--apply` writes the files and prints the summary.
- Projects: `common.find_projects(vault)` minus `state: archived`; `--project` restricts to one.
- Notes: `common.iter_notes(vault)`, excluding:
  - any path part equal to `Archive` or `Templates`;
  - `Daily/<YYYY-MM-DD>.md` older than 7 days before today, and any other file under `Daily/`;
  - `Reference/Guides/Stack Log.md`, any file whose name ends in ` Log.md`, `Projects/Projects Index.md`.
- Pure function `transform(text: str, rel_path: str, projects: list[Project], today: date) -> tuple[str, int, int]`.
- Protected regions (never changed by linking): frontmatter; fenced code blocks; heading lines (`#`...); every line from a `## History` heading up to the next `## ` heading; inline code spans; existing `[[...]]` and `[text](url)` links; bare URLs.
- Linking, per project: patterns are `[p.name] + p.aliases`. Skip the note if it already contains `[[_<Name> Index`, or if the note lives inside that project's folder. Find the first case-sensitive match of any pattern with boundaries `(?<![\w/.-])PATTERN(?![\w-])` outside protected regions; replace it with `[[_<Name> Index|<matched text>]]`. One link per project per note.
- Path fixes (everywhere except frontmatter and the `## History` region, including inside code): `~/Projects/` → `~/projects/`, `/home/arrowboy/Projects/` → `/home/arrowboy/projects/`, `/home/Jadu/Projects/` → `/home/Jadu/projects/`.

Tests (≥9) against the `vault` fixture: Agent Brief gets the link and the path fix; Stack Log, old Daily, Archive, `.obsidian` untouched; History line untouched while the body mention above it is linked; a note already linking the index gets no second link; a heading mention is not linked; an inline-code mention is not linked; a project's own folder notes are untouched; `--apply` writes and a second dry run reports `files: 0`.

Verify: `cd ~/projects/project-kit && python3 -m pytest tests/test_link.py`

## Task 08: Install on both machines [architect] ✅ 2026-11-17

Symlink `bin/*` into `~/.local/bin` on mochtop; push the repo; clone on the Z4 and symlink there.

Verify: `command -v new-project project-check projects-status link-projects && ssh jadu 'bash -lc "command -v new-project project-check projects-status link-projects"'`

## Task 09: INVENTORY.md [architect] (GATE 1 + GATE 2) ✅ approved 2026-11-17

Every candidate with rubric verdict, name/slug, merge action, visibility, evidence. AK approves.

Done when: AK approves INVENTORY.md.

## Tasks 10 to 28

As written in the approved plan (Phases 3 to 8). Each is expanded here with exact file lists once INVENTORY.md is approved, because the file lists depend on the approved project set.

## Progress after T09 (2026-11-17)

- T10 done: campSearch WIP committed to `phase2-retrieval` and pushed; sms baseline pushed; PDW, readsync, campSearch `main` pulled on the Z4. `projects-status --remote jadu` heads match.
- T11 done: automations merged both ways (verified empty `rsync -rnc` diff); per-job application data already identical.
- T12 done: mochtop moved to `~/projects`, `~/Projects` is a compat symlink, Claude memory dirs renamed. Venv rebuild deferred to the symlink-removal gap (Stack Backlog).
- T13 done on both machines; `kind: workspace` added to the kit for Local_Websites (AK decision 2).
- **Gate 3 pending:** gitleaks install (needs sudo), then per-repo visibility calls and remote creation.
