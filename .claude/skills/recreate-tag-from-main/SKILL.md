---
name: recreate-tag-from-main
description: |
  Delete a git tag locally and on origin, then re-create it (lightweight) on the
  current tip of the main branch and push it. Fetches first and verifies local
  main is in sync with origin/main before moving the tag; STOPS if main has
  diverged so a stale or unpushed commit is never tagged. Deletion of a
  non-existent tag is skipped, not an error.
  Triggers: recreate tag, re-create tag, move tag to main, retag main, delete and recreate tag, bump tag to latest main
disable-model-invocation: true
---

# Recreate Tag From Main

Move a named tag onto the current `main` tip: delete the old tag (local + `origin`), then create it fresh on `main` and push. Typical use is repointing a version tag (e.g. `14168`) after `main` advanced past the commit it originally marked.

## When to Use

- The user asks to "delete tag X and re-create it on main", "move tag X to the current main", "retag main as X", or similar.
- A release/version tag lags behind `main` and must be advanced to the latest commit.

## Inputs

- `TAG` — the tag name to recreate, taken from the user's request (e.g. `14168`). If the user did not name a tag, **ask** rather than guess.

## Safety Rules

- **NEVER** force-push or use `git push --tags`. Operate only on the single named `TAG`.
- **NEVER** tag a commit that is not on `origin/main`. If local `main` is ahead of or behind `origin/main`, STOP and report — do not tag a stale or unpushed commit.
- The remote is assumed to be `origin`. If `origin` is absent, abort and ask the user which remote to use.
- Re-creating is intentionally destructive to the *old* tag ref. Moving a tag that others may have already fetched rewrites what `TAG` means — only do this when the user explicitly asked.
- Do **not** switch branches or touch the working tree; this skill only manipulates the `TAG` ref and reads `main`.

## Method

### Step 1 — Validate preconditions and fetch

Confirm `origin` exists, then fetch the latest refs and tags (pruning deleted remote tags):

```bash
git remote                               # must contain 'origin'
git fetch origin --prune --prune-tags --tags
```

Abort with a clear message if `origin` is not present.

### Step 2 — Verify main is in sync with origin/main

The tag must land on a commit that exists on the remote. Confirm local `main` and `origin/main` point at the same commit:

```bash
git rev-parse main
git rev-parse origin/main
git log --oneline origin/main..main      # commits local-only (should be empty)
git log --oneline main..origin/main      # commits remote-only (should be empty)
```

- Both SHAs equal (both logs empty) → in sync. Proceed to Step 3.
- Local `main` is **behind** → STOP. Tell the user to `git pull --ff-only` first; do not tag a stale commit.
- Local `main` is **ahead** (unpushed commits) → STOP. Tagging then pushing would create a tag pointing at a commit not on `origin`. Ask the user to push `main` first.

### Step 3 — Inspect the current tag (report the move)

Show where `TAG` points today versus where it will move, so the change is visible:

```bash
git tag -l "<TAG>" -n1                    # local tag + its subject, if any
git ls-remote --tags origin "<TAG>"       # remote tag SHA, if any
```

- If `TAG` already resolves to the `main` tip, note it is already current but continue (the user explicitly asked to recreate it).
- If `TAG` does not exist locally or remotely, that is fine — the matching delete in Step 4 simply becomes a no-op.

### Step 4 — Delete the old tag (local, then remote)

Local delete (skip if the tag is not present locally — `git tag -d` errors on a missing tag):

```bash
git tag -d "<TAG>"                        # only if it exists locally
```

Remote delete — first check it still exists, then delete only if present:

```bash
git ls-remote --tags origin "<TAG>"       # empty → already gone, skip
git push origin --delete "<TAG>"          # only if the ls-remote was non-empty
```

If the remote delete fails (permission denied, protected tag), report the error and STOP — do not retry with force.

### Step 5 — Re-create the tag on main and push

Create a **lightweight** tag on the current `main` tip (matches the repo's existing version tags), then push just that tag:

```bash
git tag "<TAG>" main
git push origin "<TAG>"
```

> If the user explicitly wants an annotated tag with a message, use
> `git tag -a "<TAG>" main -m "<message>"` instead. Default to lightweight.

### Step 6 — Verify and report

Confirm the new tag resolves to the `main` tip both locally and on the remote:

```bash
git rev-parse "<TAG>"                     # must equal git rev-parse main
git rev-parse main
git ls-remote --tags origin "<TAG>"       # remote now points at the new SHA
```

Report to the user:
- The old SHA the tag pointed at (from Step 3) and the new SHA (`main` tip), with the new tip's short commit subject.
- Confirmation that both local and remote `TAG` now point at the `main` tip.

## Example Walk-through

User: "Delete local and remote tag `14168`, and re-create it on top of current main."

```
Step 1: git remote → origin present.                                  ✓
        git fetch origin --prune --prune-tags --tags
Step 2: rev-parse main == rev-parse origin/main (both logs empty)      ✓ in sync
Step 3: git tag -l 14168 -n1           → 14168 at 2687c49 (old merge)
        git ls-remote --tags origin 14168 → 2687c49...  (remote present)
Step 4: git tag -d 14168               → Deleted (was 2687c49)
        git ls-remote --tags origin 14168 → present
        git push origin --delete 14168 → [deleted] 14168
Step 5: git tag 14168 main             → created at f166b6f
        git push origin 14168          → [new tag] 14168 -> 14168
Step 6: rev-parse 14168 == rev-parse main == f166b6f                  ✓
        Report: 14168 moved 2687c49 → f166b6f ("Fix INetworkMessages_…"),
                local + remote in agreement.
```

## Notes

- Pure git workflow — no IDA Pro MCP or codebase analysis involved.
- Lightweight vs annotated: the repo's version tags are lightweight, so this skill defaults to lightweight. Switch to `-a`/`-m` only on explicit request.
- The skill never force-pushes, never uses `git push --tags`, and never force-deletes anything other than the single named `TAG` it was asked to recreate.
- If a step's precondition fails (diverged `main`, missing `origin`, blocked push), that is a signal to STOP and surface the situation, not to override.
