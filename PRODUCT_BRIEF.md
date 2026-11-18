# Project Kit: brief and architecture

## What and why

One consistent project system across AK's two machines (mochtop, the Z4) and his two agents (Claude Code, Jadu/Hermes). Before this, project code lived in three places (`~/Projects`, `~/projects`, `~/Documents/codin`), the vault had project notes in two homes with no rule for which goes where, and every agent session had to be told the structure again.

Project Kit is the mechanical half of the fix: four small scripts that both agents call, so the structure is enforced by code instead of by an agent remembering it. The rules themselves live in the vault note `Reference/Guides/Workflow/Project Workflow.md`.

Who uses it: AK, Claude Code (mochtop and Z4), Jadu (Z4).

## The four tools

| Command | Does | Exit code |
|---|---|---|
| `projects-status` | Per code dir under `~/projects`: branch, ahead/behind upstream, dirty count. `--remote jadu` compares with the other machine over ssh | 0, or 1 with `--strict` when anything drifts |
| `project-check` | Validates the invariants below for one project or `--all` | 0 when clean, 1 otherwise |
| `new-project` | Scaffolds a project (code dir, git, GitHub repo, vault folder, Projects Index line). `--adopt` fills in only what is missing for an existing project | 0 / 1 |
| `link-projects` | Vault linking pass: first plain mention of a project becomes `[[_<P> Index\|<P>]]`, plus `~/Projects/` to `~/projects/` path text. `--dry-run` prints a diff | 0 |

## Architecture

- Python 3 stdlib only (both machines run 3.14). No PyYAML.
- `projectkit/common.py` is the shared, locked API: config, frontmatter parsing, project discovery, templates, wikilink rewriting. The four tools import it and must not duplicate it.
- `bin/*` are thin executables that call `projectkit.<module>.main()`. Installed by symlink into `~/.local/bin` on both machines.
- `templates/` holds the note and repo templates with `{{var}}` placeholders.
- Config by environment, so tests can point at a temp vault:
  - `PK_VAULT` (default `~/Documents/Notes`)
  - `PK_PROJECTS` (default `~/projects`)
  - `PK_GH_OWNER` (default `arrowboy47`)

## Data model (locked: no new fields without architect approval)

A project is discovered from its vault index note `Projects/<folder>/_<Name> Index.md` (or `Archive/Projects/...` when archived). Its frontmatter:

```yaml
type: project
topic: project
status: growing                 # note maturity: seedling | growing | evergreen
state: active                   # active | paused | done | archived
kind: code                      # code | vault | workspace
slug: campSearch                # code only: dir under ~/projects and repo name
repo: arrowboy47/campSearch     # code only
visibility: public              # code only: public | private
runs_on: ["thebigbox"]          # optional: implies Reference/Guides/Projects/<Name>.md
aliases: ["campsearch"]         # optional: extra spellings for link-projects
description: "One plain sentence."
tags: [project]
```

`kind: workspace` is a plain (non-git) folder under `~/projects` whose subfolders are each their own repo, for example Local Websites with one repo per client. It carries `slug` but no `repo` or `visibility`, and each child repo must have a GitHub origin. `projects-status` lists children as `<slug>/<child>`.

Companion notes in the same folder: `<Name> Backlog.md`, `<Name> Log.md`. Code projects also carry `AGENTS.md` and `CLAUDE.md` (containing `@AGENTS.md`) at the repo root.

## Invariants (`project-check`)

1. Index frontmatter has every required key for its kind, with legal values.
2. `<Name> Backlog.md` and `<Name> Log.md` exist in the index's folder, and the index links both.
3. `Projects/Projects Index.md` links the index (`[[_<Name> Index` appears in it).
4. Code projects: `~/projects/<slug>` exists, is a git repo, `origin` points at `github.com/<repo>`, and `AGENTS.md` plus `CLAUDE.md` exist.
5. `--remote-visibility`: `gh repo view <repo> --json visibility` matches `visibility`.
6. `runs_on` set: `Reference/Guides/Projects/<Name>.md` exists and the index links it, and it links back.
7. `--layout`: every top-level entry in `~/projects` is a known slug, `_archive`, or a symlink.

## Risks

- Bulk vault edits replicate over LiveSync. Every write path has `--dry-run`, and the link pass is reviewed as a diff before apply.
- Case-insensitive sync target (MacBook Air): tools never do case-only renames.
- Link rewriting false positives on common words: patterns are case-sensitive, exact names plus explicit `aliases`, word-bounded, first mention only.
