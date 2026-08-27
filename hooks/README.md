# Norma — Hooks

Hooks fire on Claude Code tool events. Norma's hooks enforce contracts that would otherwise rely on convention.

| Hook | Event | Contract |
|------|-------|----------|
| [`post-write-disclaimer-check.sh`](./post-write-disclaimer-check.sh) | After `Write` tool, on `*.md` and `*.html` files | If the output carries the `<!-- normativa:requires-disclaimer -->` marker, the canonical disclaimer block from `rules/professional-disclaimer.md` MUST also be present. Marker without disclaimer = hook fails. No marker = hook stays silent. |

## Wiring the hook

Two ways to enable hooks for the Norma plugin:

### As a plugin user

If you installed Norma via `/plugin install normativa@normativa`, hooks ship inactive — Claude Code doesn't auto-enable plugin-bundled hooks (avoiding silent behavior changes). To enable, add to your `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/hooks/post-write-disclaimer-check.sh"
          }
        ]
      }
    ]
  }
}
```

The snippet is also available verbatim in [`settings-snippet.json`](./settings-snippet.json).

### As a Norma developer

The lint script (`scripts/lint.sh`) verifies that any SKILL.md citing `normativa:requires-disclaimer` also names this hook in its setup notes — so a skill author can't add a disclaimer-marker output without flagging the hook to its users.

## Why marker-driven (vs content-classification)

The hook does not classify documents by content (e.g. "this looks like a regulatory analysis"). It checks for an explicit author-emitted marker. This means:

- Test fixtures, debug dumps, draft notes, and ad-hoc scratch outputs that don't claim regulatory weight just don't carry the marker. Hook stays silent.
- Once a SKILL.md mandates the marker, dropping the disclaimer text by accident becomes a hook-failure (loud), not a silent regression (dangerous).

Pattern adopted from architecture-studio's `post-write-disclaimer-check.sh` (different marker, same contract).
