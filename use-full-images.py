#!/usr/bin/env python3
"""Show full-size images instead of the WordPress-era thumbnails.

Migrated posts render "[![alt](x_thumb.png)](x.png)": a small thumbnail linked
to the full image. Where the full image was downloaded into the page bundle the
thumbnail is replaced by it, and the now-redundant link is dropped. Cover images
reuse the same mapping so list pages stop showing thumbnails as well.
"""

import re
import sys
from pathlib import Path

POSTS = Path("content/posts")

LINKED_IMAGE = re.compile(
    r"\[!\[(?P<alt>.*?)\]\(\s*(?P<src>[^)\s]+?)\s*(?:\"(?P<title>[^\"]*)\")?\)\]"
    r"\(\s*(?P<href>[^)\s]+?)\s*(?:\"[^\"]*\")?\)"
)
BARE_IMAGE = re.compile(
    r"!\[(?P<alt>.*?)\]\(\s*(?P<src>[^)\s]+?)\s*(?:\"(?P<title>[^\"]*)\")?\)"
)
COVER_IMAGE = re.compile(r"^(?P<lead>\s+image:\s*\")(?P<src>[^\"]+)(?P<tail>\")\s*$", re.MULTILINE)

# The migration prefixed files whose names collided inside a bundle.
DEDUP_PREFIX = re.compile(r"^\d+_")
THUMB_STEM = re.compile(r"^(?P<base>.+)_thumb(?P<suffix>[-_]?\d+)?$")


def is_local(ref):
    return "://" not in ref and not ref.startswith("/")


def derived_names(name):
    """Plausible full-size file names for a thumbnail file name."""
    stem, dot, ext = name.rpartition(".")
    if not dot:
        return []
    stems = [stem]
    if DEDUP_PREFIX.match(stem):
        stems.append(DEDUP_PREFIX.sub("", stem))
    names = []
    for candidate in stems:
        m = THUMB_STEM.match(candidate)
        if m:
            names.append(f"{m.group('base')}{m.group('suffix') or ''}.{ext}")
    return names


def build_mapping(bundle, body):
    """Map thumbnail file names to the full-size file they link to.

    Thumbnails that link to a full-size image that was never downloaded are
    recorded as unresolvable, so a same-named local file is not mistaken for
    their full-size version.
    """
    mapping = {}
    unresolved = set()
    for m in LINKED_IMAGE.finditer(body):
        src = m.group("src").split("?")[0]
        href = m.group("href").split("?")[0]
        if not is_local(src) or src == href:
            continue
        if is_local(href) and (bundle / href).is_file():
            mapping[src] = href
        else:
            unresolved.add(src)
    return mapping, unresolved


def resolve(bundle, mapping, unresolved, src):
    """Return the full-size file name for src, or None to leave it alone."""
    name = src.split("?")[0]
    if "_thumb" not in name or not is_local(name):
        return None
    if name in mapping:
        return mapping[name]
    if name in unresolved:
        return None
    # No link to follow: only trust a name-derived match that nothing else claims.
    taken = set(mapping) | set(mapping.values()) | unresolved
    candidates = [c for c in derived_names(name) if c not in taken and (bundle / c).is_file()]
    return candidates[0] if len(candidates) == 1 else None


def main():
    dry_run = "--apply" not in sys.argv
    total_files = 0
    total_changes = 0

    for post in sorted(POSTS.glob("*/index.md")):
        bundle = post.parent
        text = post.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            continue
        end = text.find("\n---\n", 4)
        if end == -1:
            continue
        front_matter, body = text[4:end], text[end + 5 :]

        mapping, unresolved = build_mapping(bundle, body)
        changes = []

        def swap(m):
            full = resolve(bundle, mapping, unresolved, m.group("src"))
            if not full:
                return m.group(0)
            changes.append((m.group("src"), full))
            title = f' "{m.group("title")}"' if m.group("title") else ""
            return f'![{m.group("alt")}]({full}{title})'

        def cover(m):
            full = resolve(bundle, mapping, unresolved, m.group("src"))
            if not full:
                return m.group(0)
            changes.append((m.group("src"), full))
            return f'{m.group("lead")}{full}{m.group("tail")}'

        front_matter = COVER_IMAGE.sub(cover, front_matter)
        body = BARE_IMAGE.sub(swap, LINKED_IMAGE.sub(swap, body))

        if not changes:
            continue

        total_files += 1
        total_changes += len(changes)
        print(f"{bundle.name}: {len(changes)} image(s)")
        for old, new in changes:
            print(f"    {old} -> {new}")

        if not dry_run:
            post.write_text(f"---\n{front_matter}\n---\n{body}", encoding="utf-8")

    print(
        f"\n{total_changes} image reference(s) in {total_files} post(s)"
        f"{' (dry run, pass --apply to write)' if dry_run else ' updated'}"
    )


if __name__ == "__main__":
    main()
