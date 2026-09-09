#!/usr/bin/env python3
"""Check the converted site before you commit it.

    python3 verify-content.py

Reports, per category:
  * image references that point at a file which is not in the bundle
  * images sitting in a bundle that no post references
  * posts still pointing at the old WordPress host
  * unbalanced code fences
Run it after download-images.sh. Exit code is non-zero if anything is broken.
"""
import glob
import os
import re
import sys
from collections import defaultdict

MD_IMAGE = re.compile(r'!\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
MD_LINK = re.compile(r'(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
OLD_HOSTS = ('blog.ehn.nu/wp-content', 'blogehn.azurewebsites.net/wp-content')
IMAGE_EXT = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg')


def local_refs(text):
    for match in list(MD_IMAGE.finditer(text)) + list(MD_LINK.finditer(text)):
        target = match.group(1)
        if target.startswith(('http://', 'https://', '#', '/', 'mailto:')):
            continue
        yield target.split('#')[0]


def main():
    problems = defaultdict(list)
    referenced = defaultdict(set)
    files = sorted(glob.glob('content/**/index.md', recursive=True))
    if not files:
        print('No content found. Run this from the repository root.')
        return 1

    for path in files:
        bundle = os.path.dirname(path)
        text = open(path, encoding='utf-8').read()

        for target in local_refs(text):
            referenced[bundle].add(target)
            if not os.path.exists(os.path.join(bundle, target)):
                problems['missing file'].append(f'{path} -> {target}')

        for host in OLD_HOSTS:
            if host in text:
                problems['still points at WordPress'].append(path)
                break

        if text.count('\n```') % 2 != 0:
            problems['unbalanced code fence'].append(path)

    for bundle in {os.path.dirname(f) for f in files}:
        for entry in os.listdir(bundle):
            if entry == 'index.md' or not entry.lower().endswith(IMAGE_EXT):
                continue
            if entry not in referenced[bundle]:
                problems['orphan image'].append(os.path.join(bundle, entry))

    if not problems:
        print(f'{len(files)} files checked, nothing to fix.')
        return 0

    for kind, items in sorted(problems.items(), key=lambda kv: -len(kv[1])):
        print(f'\n{kind} ({len(items)}):')
        for item in items[:25]:
            print(f'  {item}')
        if len(items) > 25:
            print(f'  ... and {len(items) - 25} more')
    # orphans are untidy, not broken
    fatal = sum(len(v) for k, v in problems.items() if k != 'orphan image')
    return 1 if fatal else 0


if __name__ == '__main__':
    sys.exit(main())
