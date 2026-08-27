#!/bin/bash
# post-write-disclaimer-check.sh
#
# Fires after the Write tool. Verifies that markdown / HTML outputs
# claiming to be regulatory (via the `normativa:requires-disclaimer`
# marker) also carry the canonical disclaimer block from
# rules/professional-disclaimer.md.
#
# Contract:
#   - A regulatory output ends with the canonical disclaimer block
#     followed by the HTML-comment marker
#     `<!-- normativa:requires-disclaimer -->`.
#   - Marker present + disclaimer present  → exit 0 (pass)
#   - Marker present + disclaimer missing  → exit 2 (block, blocking)
#   - Marker absent                        → exit 0 (silent — output
#                                              not claiming regulatory weight)
#
# Pattern lifted from architecture-studio's post-write-disclaimer-check.sh
# (different marker token + Spanish disclaimer phrasing).

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Only check writes with a file path.
[ -z "$FILE_PATH" ] && exit 0

# Only check markdown + HTML outputs (the surfaces that get printed
# / shared / used as analysis artifacts).
case "$FILE_PATH" in
  *.md|*.html) ;;
  *) exit 0 ;;
esac

# File may not be readable yet on some filesystems / hooks; bail
# gracefully so we don't false-fail.
[ ! -r "$FILE_PATH" ] && exit 0

# Marker check — case-sensitive, exact substring.
# LEGACY_MARKER is the pre-2026-08-27 spelling. Documents generated before the
# /norma → /normativa rename carry it, and they are still regulatory output, so
# the hook must keep recognising them. New output uses MARKER.
MARKER="normativa:requires-disclaimer"
LEGACY_MARKER="norma:requires-disclaimer"
if ! grep -qF "$MARKER" "$FILE_PATH" && ! grep -qF "$LEGACY_MARKER" "$FILE_PATH"; then
  # No marker → output isn't claiming regulatory weight. Stay silent.
  exit 0
fi

# Marker present → require the canonical disclaimer leading text.
# Exact phrase matches the rule in rules/professional-disclaimer.md.
DISCLAIMER_LEAD="Análisis indicativo, no certificación"
if grep -qF "$DISCLAIMER_LEAD" "$FILE_PATH"; then
  exit 0
fi

# Marker present but disclaimer missing — block the write.
cat <<EOF >&2
✗ ${FILE_PATH##*/}: marker '${MARKER}' present, but canonical disclaimer text is missing.

Per rules/professional-disclaimer.md, every output that emits the
'normativa:requires-disclaimer' marker must also include the canonical
"Análisis indicativo, no certificación..." block immediately above it.

Either add the disclaimer block, or remove the marker if this output
isn't regulatory.

Reference: rules/professional-disclaimer.md
EOF
exit 2
