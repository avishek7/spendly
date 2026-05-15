---
description: Commit, push, open a squash-merged PR into main via GitHub MCP, then clean up the feature branch
allowed-tools: Read, Bash(git status), Bash(git diff), Bash(git log), Bash(git add), Bash(git commit), Bash(git push), Bash(git checkout), Bash(git pull), Bash(git branch), Bash(git remote), mcp__github__create_pull_request, mcp__github__merge_pull_request, mcp__github__pull_request_read, mcp__github__get_me, Bash(ls)
---
You are shipping a completed Spendly feature. Follow every step in order. Do not skip steps.

## Step 1 — Verify there is work to ship

Run `git status` and `git diff --stat HEAD`.

If the working tree is completely clean AND there are no commits ahead of origin on this branch, stop and tell the user:
"Nothing to ship — working tree is clean and branch is up to date with origin."

## Step 2 — Identify the current branch and locate the spec

Run `git branch --show-current` to get `<branch_name>`.

If the branch is `main` or `master`, stop and tell the user:
"You are on main. Checkout a feature branch first."

Extract `<feature_slug>` from the branch name by stripping the `feature/` prefix.
Example: `feature/edit-expense` → `edit-expense`

Search `.claude/specs/` for a file whose name ends in `-<feature_slug>.md`:
```
ls .claude/specs/
```
If found, set `<spec_file>` to that path and read it.
If not found, continue without a spec (you will write a generic commit message and PR body).

## Step 3 — Resolve GitHub owner and repo

Run:
```
git remote get-url origin
```

Parse `<owner>` and `<repo>` from the remote URL. Handle both HTTPS and SSH formats:
- `https://github.com/<owner>/<repo>.git` → strip `.git`
- `git@github.com:<owner>/<repo>.git` → strip `.git`

You will need these for all MCP GitHub tool calls.

## Step 4 — Stage all changes

Run:
```
git add -A
```

Then run `git status` to confirm what will be committed. If there is nothing staged (no changes at all), skip to Step 6 — the branch may already have unpushed commits.

## Step 5 — Craft and create the commit

Using the spec (if available) and `git diff --staged`, write a conventional commit message:

- Format: `<type>(<scope>): <short summary>`
- `type`: `feat` for new features, `fix` for bug fixes, `refactor` for refactors, `test` for test-only changes
- `scope`: the feature slug, e.g. `edit-expense`
- Summary: one imperative sentence, ≤72 chars, no period
- Body (optional): 1–3 bullet points explaining the key changes if the diff is non-trivial

Commit using a HEREDOC:
```bash
git commit -m "$(cat <<'EOF'
<your message here>
EOF
)"
```

## Step 6 — Push to origin

Run:
```
git push -u origin <branch_name>
```

If the push fails, stop and report the error to the user.

## Step 7 — Create the pull request using GitHub MCP

Derive the PR fields from the spec:

**title**: Use the spec's `# Spec: <title>` heading, prefixed with the step number if present in the spec filename.
Example: `feat(08): Edit Expense`

**body**: Build from the spec sections:
```
## Summary

<spec Overview paragraph>

## Changes

<bullet list from "Files to change" and "Files to create" spec sections>

## Definition of done

<verbatim checklist from the spec's "Definition of done" section, with - [ ] checkboxes>

---
🤖 Generated with [Claude Code](https://claude.ai/code)
```

Call the `mcp__github__create_pull_request` tool with:
- `owner`: parsed in Step 3
- `repo`: parsed in Step 3
- `title`: derived above
- `head`: `<branch_name>`
- `base`: `main`
- `body`: derived above

Capture the returned `number` (PR number) and `html_url` (PR URL) from the response.
Print the PR URL for the user.

## Step 8 — Squash merge using GitHub MCP

Call the `mcp__github__merge_pull_request` tool with:
- `owner`: parsed in Step 3
- `repo`: parsed in Step 3
- `pullNumber`: the PR number captured in Step 7
- `merge_method`: `squash`
- `commit_title`: the same subject line used in Step 5

If the merge fails (e.g. merge conflicts, required checks not passing), stop and report the error — do NOT force anything.

## Step 9 — Switch to main and pull latest

Run:
```
git checkout main
git pull origin main
```

## Step 10 — Delete the local feature branch

Run:
```
git branch -d <branch_name>
```

If `-d` fails because the branch is "not fully merged" (expected with squash merges), use `-D`:
```
git branch -D <branch_name>
```

## Step 11 — Report to the user

Print a summary in this exact format:
```
✅ Shipped <branch_name>

Commit:  <commit subject line>
PR:      <pr html_url>
Merge:   squash into main
Branch:  deleted locally
```

Then tell the user what the next step is (e.g. "Ready to start Step 09 — run /create-spec to begin.").
