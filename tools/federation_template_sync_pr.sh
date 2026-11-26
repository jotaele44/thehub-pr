#!/usr/bin/env bash
# Open or refresh one producer's federation-template sync pull request.
#
# .github/workflows/federation-template-sync.yml runs this from inside a
# producer checkout, after render_federation_templates.py --template-ref has
# re-rendered it (federation-templates/README.md, "Auto-propagation").
#
# Environment:
#   REPO      producer repository name, e.g. aguayluz-pr (required)
#   HUB_SHA   the thehub-pr commit the render used (required)
#   OWNER     repository owner (default: jotaele44)
#   GH_TOKEN  the SYNC_PAT secret; empty means dry run
#
# Outcomes, in order:
#   1. Token set and the producer refuses a dry-run push: error, exit 1. This
#      runs before the drift checks, so a run with no drift still tests the token.
#   2. No drift: notice, exit 0.
#   3. Only the PRII_TEMPLATE_REF value in template-drift.yml moved: notice,
#      exit 0, no PR. The rendered files already match, so the producer keeps
#      its current pin until a template change actually reaches it.
#   4. Drift and no token: dry-run notice, exit 0.
#   5. Drift and a token: commit, force-push the standing branch
#      "federation-template-sync", then update its open PR or open one.
# Steps 2 and 3 warn when a sync PR is still open, because it no longer carries
# anything the producer needs.
set -euo pipefail

: "${REPO:?REPO is required}"
: "${HUB_SHA:?HUB_SHA is required}"
OWNER="${OWNER:-jotaele44}"
GH_TOKEN="${GH_TOKEN:-}"

BRANCH="federation-template-sync"
PIN_FILE=".github/workflows/template-drift.yml"
PERMISSIONS="Contents, Pull requests and Workflows: Read and write"
HUB_SHORT="${HUB_SHA:0:12}"
PULLS="repos/$OWNER/$REPO/pulls"

fail() {
  echo "::error title=SYNC_PAT cannot sync $REPO::$1 SYNC_PAT must include $OWNER/$REPO in its repository access, with $PERMISSIONS. See federation-templates/README.md, \"Auto-propagation\"."
  exit 1
}

open_pr_number() {
  gh api "$PULLS?head=$OWNER:$BRANCH&state=open" --jq '.[0].number // empty'
}

warn_if_sync_pr_open() {
  [ -n "$GH_TOKEN" ] || return 0
  local number
  if ! number="$(open_pr_number)"; then
    echo "::warning::Could not list $OWNER/$REPO pull requests to look for an open sync PR."
    return 0
  fi
  if [ -n "$number" ]; then
    echo "::warning title=Stale sync PR::$OWNER/$REPO#$number is open, but $REPO already matches thehub-pr@$HUB_SHORT without it. Close it."
  fi
}

# The renderer rewrites exactly this line (render_federation_templates.py,
# _TEMPLATE_REF_LINE); blank its value so two copies compare equal otherwise.
blank_pin() {
  sed -E 's/^([[:space:]]*PRII_TEMPLATE_REF:[[:space:]]*)[0-9a-f]{40}[[:space:]]*$/\1/'
}

only_pin_moved() {
  [ -z "$(git status --porcelain -- . ":(exclude)$PIN_FILE")" ] || return 1
  git cat-file -e "HEAD:$PIN_FILE" 2>/dev/null || return 1
  [ -f "$PIN_FILE" ] || return 1
  cmp -s <(git show "HEAD:$PIN_FILE" | blank_pin) <(blank_pin < "$PIN_FILE")
}

# 1. Preflight. A dry run still makes the remote check write access.
if [ -n "$GH_TOKEN" ]; then
  if ! out="$(git push --dry-run --force origin "HEAD:refs/heads/$BRANCH" 2>&1)"; then
    printf '%s\n' "$out" >&2
    fail "A dry-run push to $OWNER/$REPO was refused."
  fi
fi

# 2. No drift. --porcelain also lists untracked files, so a newly rendered
#    target counts as drift.
if [ -z "$(git status --porcelain)" ]; then
  echo "::notice::$REPO already matches the canonical templates."
  warn_if_sync_pr_open
  exit 0
fi

echo "Drift detected in $REPO:"
git status --short

# 3. Pin-only.
if only_pin_moved; then
  echo "::notice::$REPO: only PRII_TEMPLATE_REF would change. Its rendered files already match thehub-pr@$HUB_SHORT, so no sync PR is opened and it keeps its current pin."
  warn_if_sync_pr_open
  exit 0
fi

# 4. Dry run.
if [ -z "$GH_TOKEN" ]; then
  echo "::notice::SYNC_PAT absent — dry run; no PR opened. Set SYNC_PAT to enable propagation."
  exit 0
fi

# 5. Sync.
git config user.name "prii-federation-bot"
git config user.email "noreply@github.com"
git checkout -q -B "$BRANCH"
git add -A
git commit -q \
  -m "chore: sync shared federation boilerplate from thehub-pr@$HUB_SHORT" \
  -m "Re-rendered the shared federation templates (which can carry action-pin bumps in the rendered workflows) and rebound the drift gate's PRII_TEMPLATE_REF to $OWNER/thehub-pr@$HUB_SHA. Automated by thehub-pr federation-template-sync."

if ! out="$(git push --force origin "HEAD:refs/heads/$BRANCH" 2>&1)"; then
  printf '%s\n' "$out" >&2
  fail "Pushing $BRANCH to $OWNER/$REPO was refused after the dry run passed. A refusal that names a workflow file means Workflows: Read and write is missing."
fi
printf '%s\n' "$out"

title="Sync shared federation boilerplate from thehub-pr@$HUB_SHORT"
body="Automated re-render of the shared boilerplate from \`thehub-pr/federation-templates\` at $OWNER/thehub-pr@$HUB_SHA, including the drift gate's \`PRII_TEMPLATE_REF\` binding to that commit. The canonical templates changed; this brings $REPO's copies back in sync so its template-drift check passes. Action-pin bumps in rendered workflows arrive this way: Dependabot skips those files here and bumps the templates in thehub-pr.

The \`$BRANCH\` branch is regenerated from \`main\` and force-pushed whenever a thehub-pr template change reaches $REPO, and this PR is updated to match. Do not push to it by hand: change the template in thehub-pr, or re-run federation-template-sync there to refresh this PR."

number="$(open_pr_number)" || fail "Pushed $BRANCH, but could not list $OWNER/$REPO pull requests."
if [ -n "$number" ]; then
  url="$(gh api -X PATCH "$PULLS/$number" -f title="$title" -f body="$body" --jq '.html_url')" \
    || fail "Pushed $BRANCH, but could not update $OWNER/$REPO#$number."
  echo "::notice::Updated $url for thehub-pr@$HUB_SHORT."
else
  url="$(gh api -X POST "$PULLS" -f title="$title" -f head="$BRANCH" -f base=main -f body="$body" --jq '.html_url')" \
    || fail "Pushed $BRANCH, but could not open its pull request on $OWNER/$REPO."
  echo "::notice::Opened $url for thehub-pr@$HUB_SHORT."
fi
