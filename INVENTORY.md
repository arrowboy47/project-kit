# INVENTORY: every project candidate, with verdict and action

Built 2026-11-17 from: mochtop `~/Projects`, `~/projects`, `~/Documents/codin`; Z4 `~/projects`; vault `Projects/`, `Reference/Guides/Projects/`, Projects Index, Future Tasks; GitHub `arrowboy47` repo list. The 90-day activity cutoff is 2026-08-19.

**This file is Gate 1 (merge plan) and Gate 2 (project list).** Nothing in Phase 3 or later runs until AK approves it. Section E lists the decisions that need an answer; each has a recommended default.

## A. Code projects (`~/projects/<slug>` on both machines)

Rubric verdict is **Project** for all of these (rule 3, or the "code AK writes lives in a repo" rule).

| Project | Slug | Visibility | Remote today | Merge action | Evidence |
|---|---|---|---|---|---|
| CampSearch | `campSearch` | public | `arrowboy47/campSearch` | Commit and push the mochtop WIP (branch `phase2-retrieval`, 6 dirty files); Z4 fetches. Old `codin/campsearch` copy is a stale duplicate, archived | mochtop HEAD 6730673 on `phase2-retrieval`, Z4 f91ce01 on `main`; thebigbox also holds a clone (left untouched) |
| Personal Website | `mywebsite` | public | `arrowboy47/mywebsite` | None, already identical | HEAD 3ca8b2c both sides |
| readsync | `readsync` | public | `arrowboy47/readsync` | Z4 `git pull` (mochtop is newer); mochtop's lowercase folder moves in with the rest | mochtop 5845218, Z4 af437b2 |
| Jadu Skills | `jadu-skills` | public (sanitized) | `arrowboy47/jadu-skills` | Review the Z4 untracked file `3d-print-optimization-prompt.md` before any commit | Z4 dirty=1 |
| Server Monitoring System | `server_monitoring_system` | private | `arrowboy47/server-monitoring-system` (private) | None; review the 1 dirty file on each side | `attacksurface.md` is 30 KB of topology |
| Personal Data Warehouse | `personal-data-warehouse` | **public now, recommend private** | `arrowboy47/personal-data-warehouse` | None | Schema and ETL for AK's personal data; gitleaks plus LAN grep decide at Gate 3 |
| Job Pilot | `job-pilot` | private | **none** (Z4 only) | Flatten out of `job-applications/`; create remote | Z4 repo HEAD 6402ea2, clean; live service `job-pilot-serve` plus plugin plus 4 cron scripts reference the old path |
| Vinted Book Watch | `vinted-book-watch` | private | **none** (Z4 only) | Create remote; commit the 14 dirty files after review | Live cron `vinted_book_watch_live.sh`; texts Dia, so it likely holds contact details |
| 3D Print Expertise | `3d-print-expertise` | private (decide at Gate 3) | **none** (Z4 only) | Create remote; review 23 dirty files | Absorbs vault notes `3D Printing Ideas` and `3dprinting` |
| Automations | `automations` | private | none | `git init`; sync the 5 differing files (newest wins: `vault-lint/vault_lint.py` from mochtop, `vram-guard`, `recipes`, `open-webui` from Z4); `.gitignore` `open-webui/data` | Not git on either machine; `vault_lint.py` is run from here by Agent Brief |
| GPU Stack | `gpu-stack` | private | none | `git init` on the Z4, then clone to mochtop | Z4 only; contains `gpu_check.py` and Honcho MCP source used by services |
| Game Streaming | `game-streaming` | private (decide at Gate 3) | none | `git init` on the Z4; `.gitignore` `emulators/` and `spike/` logs | Z4 only; AppImages are large binaries |
| Actual Dashboard | `actual-dashboard` | private | none | `git init` on mochtop, then clone to the Z4; `.gitignore` `node_modules` | mochtop only; finance data rule applies (counts only) |
| Local Websites | `Connies` | private | `arrowboy47/Connies` (private) | Flatten `businesses/Local_Websites/Connies` to `~/projects/Connies`; rename the Claude memory dir to its new path key | Project name stays "Local Websites"; client #2 gets its own repo later |
| Project Kit | `project-kit` | public (pending Gate 3) | **none yet** | Created and tested on both machines; GitHub repo creation was blocked by the permission classifier, so it waits for AK's OK | 58 tests pass on both machines |

## B. Vault-only projects (`kind: vault`)

| Project | Source notes | State | Notes |
|---|---|---|---|
| Pond Build | `Projects/Pondbuild/` (6 notes; `Pond.md` becomes the index) | paused | Last edited Apr 2026 |
| Prepped Business | `Projects/Prepped Business/` (`Prepped.md` becomes the index) | paused | Apr 2026 |
| GRE Study | `Projects/GRE Study.md` | active | Learning goal with an end (the exam) |
| Vending Machine Business | `Reference/Guides/Projects/Vending Machine Business.md`, `Projects/Glassslipper vending.md`, plus `PLAN.md`, `JADU_INTEGRATION.md`, `research/` copied from `~/Projects/businesses/vending-machine-business` | paused | Code dir is dormant (last change Aug 5), archived after the docs are copied |
| Kaggle ML Cert | `Projects/Kaggle ML Cert/` | paused | |
| New Fish Tank | `Projects/New Fish tank.md` | active | Borderline against rule 3(c); kept because it is a physical build |
| Jadu TikTok Series | `Projects/Jadu Tiktok Series.md` | active | |
| Social Media Auto-Upload | `Projects/Server/Social Media Auto-Upload.md`, `Projects/Simulanteous Video Upload.md` | paused | Becomes `kind: code` if `codin/uploader` is adopted (it holds a `client_secrets.json`, so it would be private) |
| BlueBubbles Integration | `Reference/Guides/Projects/BlueBubbles Integration Scope.md`, the stray `Projects/BUILD_PLAN.md` (it is the BlueBubbles plan) | active | Code lives in `~/.hermes/scripts`, inside the Hermes repo, so no `~/projects` dir |
| Recipe Pipeline | `Recipe Pipeline`, `Recipe Pipeline V2 Plan`, `Recipe Creators` | active | See decision 4 |

## C. Not projects

| Item | Verdict | Where it goes |
|---|---|---|
| Homelab | Meta-project | Stays a pointer; its index, backlog and log are Infrastructure Index, Stack Backlog, Stack Log |
| Stats Learning Project | Open-ended notes (rule 3a fails) | Moves to `Reference/` (a move, so links survive) |
| LegalReview | Work | Moves to `Areas of Responsibility/` |
| Kamaal corn | An ingredient or recipe list | Moves to `Reference/Food/` |
| Vinted Book Watchlist | Note inside a project | Moves into the Vinted Book Watch folder |
| Better Book Search Engine, expedia-alternative, catan scraper | Ideas | Stay in Future Tasks; Projects Index gets an "Ideas" section pointing there, which also fixes its 2 unresolved links |
| Hermes Job Agent, Job Notification System | Retired by Job Pilot | Stay in place with their retired banners; listed under Archived |
| `~/.hermes` repo (`Jadu-Hermes_Agent`, private), dotfiles repos | Infra repos | Out of scope |

## D. Moves and triage (code locations)

**mochtop `~/Projects` and `~/projects`:** everything in section A moves under lowercase `~/projects`, with a `~/Projects -> projects` compatibility symlink. `businesses/realestatefinder` (Apr 20, not git, has a service file) and `businesses/vending-machine-business` go to `~/projects/_archive/`. The empty `businesses/expedia-alternative` is removed (an idea, no content). `free-my-tv-src` (a Hisense TV debloat, rule 2 and the vault already has `Android TV Debloat and Catppuccin Theme`) goes to `~/src/`; it holds LAN recon, so it never goes public.

**mochtop `~/Documents/codin` (dormant by the 90-day rule):**
- Git repos moved to `~/projects/_archive/`: `AKweb2` (duplicate of mywebsite), `campsearch` (duplicate of campSearch), `Catan_Analysis` (see decision 5), `coffee`, `dailypy`, `finance`, `Habu`, `kobo-dashboard`, `PiAssistant`, `RepSearch` (third-party), `Valentines_Day_Proposal`.
- Left in place: the 15 non-git folders (`agents`, `AKweb`, `betterlife`, `data`, `ipod_upload`, `leet`, `motelBookingcom`, `onepiecetokindle`, `Practice`, `scripts`, `teen_signin`, `tempdir`, `uploader`, `webdev`, `realestatefinder`). They are not repos, so they are not projects. `codin` stays as scratch.
- Before any move: grep for references from services, cron or plugins; anything referenced counts as active and stays.

**Z4 `~/projects` third-party clones to `~/src/`:**
- `vinted-scraper` (omkarcloud): `vinted-book-watch/scripts/run_scraper.py` and its cron script default to `~/projects/vinted-scraper`, so `SCRAPER_DIR` is updated in the same step and the unit or script is verified.
- `yt-shorts-pipeline`: nothing references it.
- `Jev-playground`: `kev` is a third-party clone, but `laya-serve.service` runs `Jev-playground/laya/.venv/bin/laya-serve` (and Email Automation depends on it), so the unit is edited and restarted, with a `.bak` copy first.

**Z4 `~/projects/job-applications`:** `job-pilot` is flattened out to `~/projects/job-pilot` (service, plugin yaml, 4 scripts and the skill are rewritten, with a compatibility symlink left behind). `_archive/` holds the retired hermes-job-agent and is a superset of mochtop's copy, so mochtop's copy is simply dropped after a subset check. The per-job application packages (`Visa - ...`, `Stanford ...`, `Walmart ...`) and `_system` are personal data, not code; see decision 1.

**Z4 path rename:** none. Lowercase `~/projects` is already the Z4 layout, so none of the roughly 46 Z4 files referencing `/home/Jadu/projects` changes. Only the job-pilot, Jev-playground and vinted-scraper references above are touched.

**`readsync/refs/*`:** the plan said to move these to `~/src`. They are gitignored per-machine clones inside readsync and the docs reference them, so I recommend leaving them there. They are not a top-level `~/projects` entry, so the layout check ignores them.

## E. Decisions for AK (each has a recommended default)

1. **Job application packages.** Per-job folders and `_system` are data, not a project. Recommend moving them to `~/data/job-applications/` on the Z4 only, with a compatibility symlink for whatever reads them, instead of leaving a non-project folder in `~/projects`.
2. **Local Websites repo.** Recommend project "Local Websites" with slug `Connies` (the only repo). Alternative: slug `local-websites` with Connies as a subfolder (this makes a nested repo, which I advise against).
3. **PDW visibility.** Recommend flipping `personal-data-warehouse` to private now, since it is a schema for personal data. Say no if you want it public as a showcase.
4. **Recipe Pipeline.** Recommend a vault project that points to the code in `automations/recipes` (no code move, since cron scripts reference it). `recipe-swipe` (a public GitHub repo that is cloned on neither machine) gets cloned later if you want to work on it.
5. **Catan_Analysis.** Code, no remote, last touched 2026-07-21 (119 days), and Future Tasks lists "catan game stats scraper". Recommend archiving as the plan says, and promoting it later if you restart it. Or tell me to adopt it as a project now.
6. **Project Kit public repo.** The auto-mode classifier blocked `gh repo create --public`. Say "create it" and I will run it at Gate 3 together with the others (after gitleaks and the LAN grep, both clean in a first pass: zero LAN-pattern hits).
7. **Remote creation for Z4-only repos** (job-pilot, vinted-book-watch, 3d-print-expertise): created private first. Flipping any to public needs your explicit OK per repo.
8. **Kamaal corn** moves to `Reference/Food/`. **New Fish Tank** is kept as a project despite being borderline.

## F. What happens after approval

Phase 3 (T10 to T15) in `BUILD_PLAN.md`: reconcile shared repos, merge the non-git dirs, move mochtop to `~/projects`, flatten and move on the Z4 with service checks, then Gate 3 (secret scan plus per-repo visibility) before any remote is created or flipped.
