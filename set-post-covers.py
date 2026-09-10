#!/usr/bin/env python3
"""Set PaperMod cover images on migrated posts.

Picks the first image referenced in each post body that is large enough to look
good as a cover (small inline thumbnails from the WordPress era are skipped).
"""

import re
import sys
from pathlib import Path

from PIL import Image

POSTS = Path("content/posts")
MIN_WIDTH = 480
MIN_ASPECT = 1.0  # landscape only

MD_IMAGE = re.compile(r"!\[[^\]]*\]\(\s*([^)\s]+)")
HTML_IMAGE = re.compile(r"""<img[^>]+src=["']([^"']+)["']""", re.IGNORECASE)
TITLE = re.compile(r"^title:\s*(.+?)\s*$", re.MULTILINE)


def split_front_matter(text):
    if not text.startswith("---\n"):
        return None, None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, None
    return text[4:end], text[end + 5 :]


def image_refs(body):
    refs = [(m.start(), m.group(1)) for m in MD_IMAGE.finditer(body)]
    refs += [(m.start(), m.group(1)) for m in HTML_IMAGE.finditer(body)]
    refs.sort()
    seen = set()
    for _, ref in refs:
        if ref not in seen:
            seen.add(ref)
            yield ref


def pick_cover(bundle, body):
    for ref in image_refs(body):
        if "://" in ref or ref.startswith("/"):
            continue
        candidate = bundle / ref.split("?")[0]
        if not candidate.is_file():
            continue
        try:
            with Image.open(candidate) as im:
                width, height = im.size
        except OSError:
            continue
        if width >= MIN_WIDTH and width / height >= MIN_ASPECT:
            return candidate.name
    return None


def main():
    updated = skipped = no_match = 0
    for index in sorted(POSTS.glob("*/index.md")):
        text = index.read_text(encoding="utf-8")
        front, body = split_front_matter(text)
        if front is None:
            print(f"! no front matter: {index}", file=sys.stderr)
            continue
        if re.search(r"^cover:", front, re.MULTILINE):
            skipped += 1
            continue

        cover = pick_cover(index.parent, body)
        if cover is None:
            no_match += 1
            continue

        title = TITLE.search(front)
        alt = title.group(1).strip('"').replace('"', "'") if title else "Cover image"
        front = f'{front}\ncover:\n  image: "{cover}"\n  alt: "{alt}"'
        index.write_text(f"---\n{front}\n---\n{body}", encoding="utf-8")
        updated += 1

    print(f"covers set: {updated}, already had one: {skipped}, no suitable image: {no_match}")


if __name__ == "__main__":
    main()
