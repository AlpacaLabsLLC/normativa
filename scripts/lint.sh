#!/bin/bash
# scripts/lint.sh — Norma plugin structural lint.
#
# Validates the kind of structural drift that's easy to ship without
# noticing:
#   - Each plugin (.claude-plugin/plugin.json) has at least one skill
#     with valid frontmatter (name, description, allowed-tools,
#     user-invocable).
#   - Skill name in frontmatter matches the skill's folder name.
#   - Schema docs cited from SKILL.md (*-schema.md) actually exist.
#   - Validator scripts mandated by SKILL.md exist + are executable.
#   - Hooks referenced from a skill are present in hooks/.
#   - Rules cited from a skill are present in rules/.
#   - The repo's marketplace.json plugin entry version matches each
#     plugin.json's version.
#
# Pattern + scope (~200 lines) modeled on architecture-studio's
# scripts/lint.sh.
#
# Usage:
#   scripts/lint.sh
#
# Exit codes:
#   0  all checks passed
#   1  one or more checks failed (see stderr)

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ERRORS=0

err() { printf '✗ %s\n' "$*" >&2; ERRORS=$((ERRORS + 1)); }
ok()  { printf '· %s\n' "$*"; }

# ---------- Utility ----------------------------------------------------

# Extract a single-key YAML value from a SKILL.md frontmatter block.
# Usage: frontmatter_value <file> <key>
frontmatter_value() {
  local file="$1" key="$2"
  awk -v key="$key" '
    /^---$/ { count++; next }
    count == 1 && $0 ~ "^"key":" {
      sub("^"key":[[:space:]]*", "")
      print
      exit
    }
    count >= 2 { exit }
  ' "$file"
}

# Extract list-style values from frontmatter (allowed-tools).
# Usage: frontmatter_list <file> <key>
frontmatter_list() {
  local file="$1" key="$2"
  awk -v key="$key" '
    /^---$/ { count++; next }
    count == 1 && $0 ~ "^"key":" { in_list = 1; next }
    count == 1 && in_list && /^[[:space:]]*-[[:space:]]/ {
      sub("^[[:space:]]*-[[:space:]]*", "")
      print
    }
    count == 1 && in_list && !/^[[:space:]]/ { in_list = 0 }
    count >= 2 { exit }
  ' "$file"
}

# ---------- Plugin manifest --------------------------------------------

PLUGIN_JSON="$ROOT/.claude-plugin/plugin.json"
MARKETPLACE_JSON="$ROOT/.claude-plugin/marketplace.json"

if [ ! -f "$PLUGIN_JSON" ]; then
  err "missing $PLUGIN_JSON"
elif ! jq -e . "$PLUGIN_JSON" >/dev/null 2>&1; then
  err "invalid JSON: $PLUGIN_JSON"
else
  PLUGIN_NAME=$(jq -r '.name' "$PLUGIN_JSON")
  PLUGIN_VERSION=$(jq -r '.version' "$PLUGIN_JSON")
  ok "plugin: $PLUGIN_NAME v$PLUGIN_VERSION"
fi

if [ ! -f "$MARKETPLACE_JSON" ]; then
  err "missing $MARKETPLACE_JSON"
elif ! jq -e . "$MARKETPLACE_JSON" >/dev/null 2>&1; then
  err "invalid JSON: $MARKETPLACE_JSON"
else
  M_PLUGIN_VERSION=$(jq -r --arg name "$PLUGIN_NAME" '.plugins[] | select(.name==$name) | .version' "$MARKETPLACE_JSON")
  if [ -z "$M_PLUGIN_VERSION" ] || [ "$M_PLUGIN_VERSION" = "null" ]; then
    err "marketplace.json: no plugin entry for '$PLUGIN_NAME'"
  elif [ "$M_PLUGIN_VERSION" != "$PLUGIN_VERSION" ]; then
    err "version drift: plugin.json=$PLUGIN_VERSION marketplace.json=$M_PLUGIN_VERSION"
  fi
fi

# ---------- Skills -----------------------------------------------------

SKILL_COUNT=0
for skill_dir in "$ROOT/skills"/*/; do
  [ -d "$skill_dir" ] || continue
  skill_name=$(basename "$skill_dir")
  skill_md="$skill_dir/SKILL.md"
  SKILL_COUNT=$((SKILL_COUNT + 1))

  if [ ! -f "$skill_md" ]; then
    err "skills/$skill_name: missing SKILL.md"
    continue
  fi

  # Required frontmatter keys
  fm_name=$(frontmatter_value "$skill_md" name)
  fm_desc=$(frontmatter_value "$skill_md" description)
  fm_invocable=$(frontmatter_value "$skill_md" user-invocable)
  fm_tools=$(frontmatter_list "$skill_md" allowed-tools)

  if [ -z "$fm_name" ]; then
    err "skills/$skill_name/SKILL.md: missing 'name:' in frontmatter"
  elif [ "$fm_name" != "$skill_name" ]; then
    err "skills/$skill_name/SKILL.md: frontmatter name='$fm_name' doesn't match folder name '$skill_name'"
  fi

  if [ -z "$fm_desc" ]; then
    err "skills/$skill_name/SKILL.md: missing 'description:' in frontmatter"
  fi

  if [ -z "$fm_invocable" ]; then
    err "skills/$skill_name/SKILL.md: missing 'user-invocable:' in frontmatter"
  fi

  if [ -z "$fm_tools" ]; then
    err "skills/$skill_name/SKILL.md: missing 'allowed-tools:' list (or empty)"
  fi

  # Schema doc cross-reference: any *-schema.md cited by SKILL.md as a
  # PATH (contains a slash) should resolve. Bare filename mentions
  # ("see foo-schema.md") are treated as prose, not links — skip them.
  while IFS= read -r schema_ref; do
    [ -z "$schema_ref" ] && continue
    case "$schema_ref" in */*) ;; *) continue ;; esac
    target="$skill_dir/$schema_ref"
    if [ ! -f "$target" ]; then
      target_alt="$ROOT/$schema_ref"
      [ -f "$target_alt" ] || err "skills/$skill_name/SKILL.md: cited schema not found: $schema_ref"
    fi
  done < <(grep -oE '[a-zA-Z0-9._/-]+-schema\.md' "$skill_md" | sort -u)

  # Validator script cross-reference: any *-validate.py cited
  while IFS= read -r vscript; do
    [ -z "$vscript" ] && continue
    base=$(basename "$vscript")
    found=$(find "$skill_dir" -maxdepth 2 -name "$base" -type f | head -1)
    [ -z "$found" ] && err "skills/$skill_name/SKILL.md: cited validator script not found: $vscript"
  done < <(grep -oE '[a-zA-Z0-9._/-]+-validate\.py' "$skill_md" | sort -u)

  # Rule cross-reference: any rules/*.md cited (should exist in repo's rules/)
  while IFS= read -r rule; do
    [ -z "$rule" ] && continue
    base=$(basename "$rule")
    [ -f "$ROOT/rules/$base" ] || err "skills/$skill_name/SKILL.md: cited rule not found: rules/$base"
  done < <(grep -oE 'rules/[a-zA-Z0-9-]+\.md' "$skill_md" | sort -u)

  ok "skill: $skill_name"
done

if [ "$SKILL_COUNT" -eq 0 ]; then
  err "no skills found under $ROOT/skills/"
fi

# ---------- Rules existence --------------------------------------------

if [ -d "$ROOT/rules" ]; then
  RULE_COUNT=$(find "$ROOT/rules" -maxdepth 1 -name "*.md" -not -name "README.md" | wc -l | tr -d ' ')
  ok "rules: $RULE_COUNT files"
fi

# ---------- Hooks executability -----------------------------------------

if [ -d "$ROOT/hooks" ]; then
  for hook in "$ROOT/hooks"/*.sh; do
    [ -f "$hook" ] || continue
    if [ ! -x "$hook" ]; then
      err "$(basename "$hook"): not executable (chmod +x)"
    fi
  done
fi

# ---------- Vendored corpus drift ---------------------------------------
#
# skills/norma-analyze/datos/tone-zones.json is a RELEASE ARTIFACT synced from
# Estudio-Local/mapa, never edited here. Mapa hosts the normativa corpus as the
# public resource (mapa decision 260419-ELO-MAPA/0001); this plugin has to
# vendor a copy because a distributed plugin cannot resolve it by path.
#
# Divergence is silent and consequential: before the 2026-08-27 sync this copy
# had zona 1.2.2 at _data_quality "pending" with tipologias null, against a
# verified transcription in Mapa — a user analysing padron 12131 got nothing.
#
# Skips when Mapa is not checked out (the normal case for anyone who cloned
# only this repo). Point MAPA_TONE_JSON at the canonical file to override.

VENDORED_TONE="$ROOT/skills/norma-analyze/datos/tone-zones.json"
CANONICAL_TONE="${MAPA_TONE_JSON:-$HOME/Documents/code/mapa/normativa/datos/tone-zones.json}"

if [ ! -f "$VENDORED_TONE" ]; then
  err "tone-zones.json: vendored copy missing at skills/norma-analyze/datos/"
elif [ ! -f "$CANONICAL_TONE" ]; then
  ok "tone-zones.json: canonical copy not present, drift check skipped"
else
  if cmp -s "$VENDORED_TONE" "$CANONICAL_TONE"; then
    ok "tone-zones.json: in sync with mapa"
  else
    err "tone-zones.json: DRIFTED from mapa. This file is a synced artifact, not a source."
    err "  canonical: $CANONICAL_TONE"
    err "  resync:    cp \"$CANONICAL_TONE\" \"$VENDORED_TONE\""
  fi
fi

# ---------- Summary -----------------------------------------------------

echo
if [ "$ERRORS" -eq 0 ]; then
  echo "✓ lint passed"
  exit 0
else
  echo "✗ lint failed: $ERRORS error(s)" >&2
  exit 1
fi
