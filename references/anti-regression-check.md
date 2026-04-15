# Anti-Regression Settings Check (First-Run Onboarding)

Runs **once per machine** at the start of the first SuperFlow session. Detects whether the user's `~/.claude/settings.json` is configured to mitigate the Feb-Mar 2026 Claude Code quality regression. If not, shows a diff and asks the user whether to apply.

This is a **conversational** step — talk to the user, do not silently mutate their settings.

---

## Why this exists

Anthropic confirmed two regression-causing changes to Claude Code in Feb-Mar 2026 (see [issue #42796](https://github.com/anthropics/claude-code/issues/42796), [bcherny HN reply](https://news.ycombinator.com/item?id=47664442)):

1. **Adaptive thinking** (Feb 9, with Opus 4.6) — model self-paces reasoning per turn; produces zero-thinking turns even at `effort=high`
2. **Default effort lowered** (Mar 3) from `high` to `medium`

Behavioral symptoms in shipped code: reads-per-edit dropped 6.6 → 2.0, doubling of full-rewrites instead of targeted edits, premature stops. SuperFlow runs all code through subagents (Rule 1), where the most aggressive workarounds (env vars, `ultrathink` keyword) are partially or entirely ineffective. The recommended settings below give the best mitigation that doesn't require patching the Claude Code binary.

---

## Detection

```bash
SETTINGS=~/.claude/settings.json
MARKER=~/.claude/.superflow-anti-regression-checked

# Skip if user already decided
if [ -f "$MARKER" ]; then
  echo "DISMISSED"
  exit 0
fi

# Skip if settings.json does not exist or is unreadable (let user create it first)
if [ ! -r "$SETTINGS" ]; then
  echo "NO_SETTINGS"
  exit 0
fi

# Build list of missing or suboptimal keys
MISSING=()
jq -e '.env.CLAUDE_CODE_EFFORT_LEVEL == "max"' "$SETTINGS" >/dev/null 2>&1 || MISSING+=("CLAUDE_CODE_EFFORT_LEVEL")
jq -e '.env.CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING == "1"' "$SETTINGS" >/dev/null 2>&1 || MISSING+=("CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING")
jq -e '.env.MAX_THINKING_TOKENS' "$SETTINGS" >/dev/null 2>&1 || MISSING+=("MAX_THINKING_TOKENS")
jq -e '.env.CLAUDE_CODE_AUTO_COMPACT_WINDOW' "$SETTINGS" >/dev/null 2>&1 || MISSING+=("CLAUDE_CODE_AUTO_COMPACT_WINDOW")
jq -e '.showThinkingSummaries == true' "$SETTINGS" >/dev/null 2>&1 || MISSING+=("showThinkingSummaries")
jq -e '[.hooks.PreCompact? // [] | select(type == "array") | .[]?.hooks[]?.command? // empty] | any(endswith("/precompact-state-externalization.sh"))' "$SETTINGS" >/dev/null 2>&1 || MISSING+=("PreCompactHook")

if [ ${#MISSING[@]} -eq 0 ]; then
  echo "ALL_SET"
else
  printf "MISSING:%s\n" "$(IFS=,; echo "${MISSING[*]}")"
fi
```

Outputs (one of):
- `DISMISSED` → user already chose, skip silently
- `NO_SETTINGS` → cannot help, skip silently
- `ALL_SET` → already configured, skip silently
- `MISSING:KEY1,KEY2,...` → run the prompt below

---

## User prompt

When detection returns `MISSING:...`, show the user this message inline (do NOT auto-apply). Translate the prose to the user's language (Russian, English, etc.) but keep the diff block and key names verbatim.

```
🛡️  SuperFlow detected your Claude Code config could mitigate the Feb-Mar 2026 quality regression.

Anthropic confirmed two regressions: adaptive thinking (model under-thinks per turn) + lowered default effort. SuperFlow's subagents are particularly affected — env-var workarounds only cover 1 of 5 adaptive code paths, and `ultrathink` keyword does not work in subagents.

Recommended additions to ~/.claude/settings.json:

  env:
    CLAUDE_CODE_EFFORT_LEVEL=max                 # raise default effort to max
    CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1      # turn off model self-pacing
    MAX_THINKING_TOKENS=63999                    # fixed thinking budget (only honored when adaptive is off)
    CLAUDE_CODE_AUTO_COMPACT_WINDOW=400000       # keep working context tight, prevent CLAUDE.md drown-out

  showThinkingSummaries: true                    # restore visible thinking blocks in UI

Plus a PreCompact hook (dumps sprint state to .superflow/compact-log/ before
compaction so the orchestrator can hydrate afterwards — see hooks/README.md):

  hooks.PreCompact:
    ~/.claude/skills/superflow/hooks/precompact-state-externalization.sh

Trade-off: higher token spend per session, slightly higher latency. SuperFlow workflows benefit most.

Sources: github.com/anthropics/claude-code/issues/42796 · news.ycombinator.com/item?id=47664442

Apply? [y]es / [n]o / [s]kip-permanently
```

Wait for user response. Three branches:

- **`y` / yes / да** → run the apply script below, then write marker with `decision: "applied"`
- **`n` / no / нет** → write marker with `decision: "deferred"` (will ask again on next first run if marker is removed manually)
- **`s` / skip-permanently / никогда** → write marker with `decision: "dismissed"` and a note that user can re-trigger by deleting the marker file

After any of the three, continue Phase 0 / Phase 1 routing without further interruption.

---

## Apply script

Backs up `settings.json` first, then merges the recommended keys via `jq` (preserves all existing settings).

```bash
SETTINGS=~/.claude/settings.json
BACKUP_DIR=~/.claude/backups
mkdir -p "$BACKUP_DIR"
cp "$SETTINGS" "$BACKUP_DIR/settings.json.$(date +%Y%m%d-%H%M%S).pre-anti-regression.bak"

# Merge env keys + append PreCompact hook entry (idempotent; preserves existing
# env vars and any existing PreCompact entries that don't already reference the
# SuperFlow hook).
HOOK_CMD="$HOME/.claude/skills/superflow/hooks/precompact-state-externalization.sh"
jq --arg cmd "$HOOK_CMD" '
  # Normalize .hooks.PreCompact: absent or non-array becomes an empty array so
  # the append below can never error. Preserves any existing array entries.
  .env = (.env // {}) + {
    "CLAUDE_CODE_EFFORT_LEVEL": "max",
    "CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING": "1",
    "MAX_THINKING_TOKENS": "63999",
    "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "400000"
  }
  | .showThinkingSummaries = true
  | .hooks = (.hooks // {})
  | .hooks.PreCompact = (
      (if (.hooks.PreCompact | type) == "array" then .hooks.PreCompact else [] end) as $existing
      | $existing
      + (
          if ([$existing[]?.hooks[]?.command? // empty]
               | any(endswith("/precompact-state-externalization.sh")))
          then []
          else [{"hooks": [{"type": "command", "command": $cmd}]}]
          end
        )
    )
' "$SETTINGS" > "$SETTINGS.tmp" && mv "$SETTINGS.tmp" "$SETTINGS"

echo "Applied. Backup at: $BACKUP_DIR/settings.json.*.pre-anti-regression.bak"
```

After successful apply, show the user:
```
✅ Settings updated. Backup saved at ~/.claude/backups/settings.json.*.pre-anti-regression.bak.
   Restart Claude Code (exit + relaunch) for env vars to take effect.
```

The restart note is important — env vars in `settings.json` are read at process startup, not picked up live.

---

## Marker file

After any of the three user decisions:

```bash
cat > ~/.claude/.superflow-anti-regression-checked << EOF
{
  "checked_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "decision": "applied|deferred|dismissed",
  "missing_at_check": ["KEY1", "KEY2"],
  "superflow_version": "4.6.0"
}
EOF
```

To re-trigger the check on a future session: `rm ~/.claude/.superflow-anti-regression-checked`.

---

## Recommended PostCompact hook

The Phase 0 check does **not** detect or install `PostCompact` automatically (its `additionalContext` text is prose-heavy and too easy to false-negative on). But a correctly configured PostCompact hook is what makes the PreCompact dump useful — it tells the orchestrator to re-read the rules AND read the latest dump from `.superflow/compact-log/`.

Canonical recommendation to document in onboarding:

```json
{
  "hooks": {
    "PostCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo '{\"hookSpecificOutput\":{\"hookEventName\":\"PostCompact\",\"additionalContext\":\"CONTEXT COMPACTION OCCURRED. If you are running a SuperFlow workflow, you MUST immediately: (1) Read ~/.claude/rules/superflow-enforcement.md (2) Read the SuperFlow SKILL.md file (3) Re-read references/phase2-execution.md if in Phase 2 (4) ls -t .superflow/compact-log/ — if a dump exists, Read the most recent one to hydrate pre-compaction state. Critical reminders: NEVER write code directly - dispatch subagents. ALWAYS use git worktrees. ALWAYS run Product Acceptance Review before PRs.\"}}'"
          }
        ]
      }
    ]
  }
}
```

If the user already has a PostCompact hook (likely, for SuperFlow users running 4.x), the apply script should NOT overwrite it — ask the user to add step (4) to their existing `additionalContext` manually. The reason: the existing text may have been customized, and merging prose safely is out of scope for `jq`.

---

## Edge cases

- **`jq` not installed** → fall back to `python3 -c "import json; ..."` for both detection and apply. If neither is available, output `NO_TOOLS` and skip the check (do not block SuperFlow startup).
- **`settings.json` is malformed JSON** → output `INVALID_SETTINGS`, show user a one-line warning ("Your settings.json has a JSON syntax error, please fix it before SuperFlow can recommend env vars"), skip the check, do not write a marker (so it'll re-check after fix).
- **User's existing `CLAUDE_CODE_EFFORT_LEVEL` is `high` (not `max`)** → still considered missing for our purposes; the apply will overwrite to `max`. If user wants to keep `high`, they should choose `s` (skip-permanently).
- **`MAX_THINKING_TOKENS` is set but to a value lower than `31999`** → considered "present" by current detection (we only check key existence, not value). This is intentional: we don't want to override user's explicit numerical choice. Document this in the user prompt if you want to be more aggressive in a future version.
- **Multiple Claude Code installations / users on same machine** → marker is per-user (`~/.claude/`), so each user gets the prompt once.
