#!/usr/bin/env bash
# Download every image referenced by the converted posts into its page bundle.
# Run this from the repository root WHILE THE OLD WORDPRESS SITE IS STILL UP.
#
#   bash download-images.sh
#
# Re-running is safe: existing files are skipped. Failures are collected in
# image-failures.tsv so you can retry or source them from a backup.
set -uo pipefail

MANIFEST="${1:-image-manifest.tsv}"
FAILED="image-failures.tsv"
FALLBACK_HOST="blogehn.azurewebsites.net"

: > "$FAILED"
ok=0; skip=0; fail=0

while IFS=$'\t' read -r url bundle name; do
  [ "$url" = "url" ] && continue
  [ -z "${url:-}" ] && continue
  dest="$bundle/$name"
  if [ -s "$dest" ]; then skip=$((skip+1)); continue; fi
  mkdir -p "$bundle"
  if curl -fsSL --retry 3 --retry-delay 2 --max-time 60 -o "$dest.part" "$url"; then
    mv "$dest.part" "$dest"; ok=$((ok+1))
  else
    rm -f "$dest.part"
    alt="${url/blog.ehn.nu/$FALLBACK_HOST}"
    if [ "$alt" != "$url" ] && curl -fsSL --retry 2 --max-time 60 -o "$dest.part" "$alt"; then
      mv "$dest.part" "$dest"; ok=$((ok+1))
    else
      rm -f "$dest.part"
      printf '%s\t%s\t%s\n' "$url" "$bundle" "$name" >> "$FAILED"
      fail=$((fail+1))
    fi
  fi
done < "$MANIFEST"

echo "downloaded=$ok skipped=$skip failed=$fail"
[ "$fail" -gt 0 ] && echo "See $FAILED for the ones that did not come down."
exit 0
