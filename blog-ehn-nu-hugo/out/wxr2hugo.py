#!/usr/bin/env python3
"""
Convert a WordPress WXR export into a Hugo content tree of page bundles.

Usage:
    python3 wxr2hugo.py EXPORT.xml OUTDIR [--limit-slugs slug1,slug2]

Produces:
    OUTDIR/content/posts/<YYYY-MM-slug>/index.md      one bundle per post
    OUTDIR/content/<slug>.md                          standalone pages
    OUTDIR/download-images.sh                         fetches images into bundles
    OUTDIR/image-manifest.tsv                         url -> local path mapping
"""
import argparse
import html as htmllib
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
from datetime import datetime
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup, NavigableString
from markdownify import MarkdownConverter

NS = {
    'wp': 'http://wordpress.org/export/1.2/',
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'excerpt': 'http://wordpress.org/export/1.2/excerpt/',
    'dc': 'http://purl.org/dc/elements/1.1/',
}

# Hosts that are really the same site. Images on these get localised.
SELF_HOSTS = {'blog.ehn.nu', 'www.blog.ehn.nu', 'blogehn.azurewebsites.net'}
# Preferred host to download from (the azurewebsites one dies with the App Service).
CANONICAL_HOST = 'blog.ehn.nu'

# --------------------------------------------------------------------------
# Code block handling
# --------------------------------------------------------------------------

# WordPress' texturiser rewrote punctuation inside code. Undo it, but only
# ever inside code regions -- doing this to prose would be wrong.
CODE_UNTEXTURISE = [
    ('\u2018', "'"), ('\u2019', "'"),          # curly single quotes
    ('\u201c', '"'), ('\u201d', '"'),          # curly double quotes
    ('\u2013', '--'), ('\u2014', '--'),        # en/em dash -> double hyphen
    ('\u2026', '...'),
    ('\u00a0', ' '),                           # nbsp
]

LANG_HINTS = [
    # order matters: first match wins
    (r'^\s*(az |azd |kubectl |helm |docker |docker-compose |brig |wget |curl |apt-get |choco )', 'bash'),

    (r'^\s*(PS |PS C:\\)|Get-|Set-|New-|Write-Host|\$env:|param\s*\(', 'powershell'),
    (r'^\s*(using |namespace |public class |private |internal |\[assembly)', 'csharp'),
    (r'\b(const|var|let|function|require\()\b.*[;{]', 'javascript'),
    (r'^\s*<\?xml|^\s*<Project|^\s*<configuration|^\s*<[A-Za-z]+ xmlns', 'xml'),
    (r'^\s*\{\s*$|^\s*"\$schema"|^\s*"apiVersion"', 'json'),
    (r'^\s*(apiVersion|kind|metadata):\s*$|^\s*- name:', 'yaml'),
    (r'^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE TABLE)\b', 'sql'),
    (r'^\s*#!/bin/(ba)?sh|\bfi\b\s*$|\$\(', 'bash'),
]


def guess_language(code, declared=None):
    if declared:
        d = declared.strip().lower()
        alias = {'js': 'javascript', 'cs': 'csharp', 'c#': 'csharp',
                 'ps': 'powershell', 'shell': 'bash', 'sh': 'bash',
                 'text': '', 'plain': ''}
        return alias.get(d, d)
    head = '\n'.join(code.strip().splitlines()[:6])
    for pattern, lang in LANG_HINTS:
        if re.search(pattern, head, re.MULTILINE):
            return lang
    return ''


def clean_code_text(text):
    """Undo WP entity double-escaping and smart punctuation inside code."""
    # Some posts have &amp;amp;amp;gt; style runaway escaping. Unescape until stable.
    prev = None
    while prev != text and '&' in text:
        prev = text
        text = htmllib.unescape(text)
    for bad, good in CODE_UNTEXTURISE:
        text = text.replace(bad, good)
    # strip trailing whitespace per line, collapse >2 blank lines
    lines = [ln.rstrip() for ln in text.replace('\r\n', '\n').split('\n')]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    out, blanks = [], 0
    for ln in lines:
        if ln.strip():
            blanks = 0
            out.append(ln)
        else:
            blanks += 1
            if blanks <= 1:
                out.append('')
    return '\n'.join(out)


def pre_to_text(tag):
    """Recover plain text from a <pre>, honouring <br> as newline."""
    parts = []
    just_broke = False
    for node in tag.descendants:
        if isinstance(node, NavigableString):
            text = str(node)
            if just_broke:
                if not text.strip():
                    continue      # swallow whitespace that followed <br />
                text = re.sub(r'^[ \t]*\r?\n', '', text)
            just_broke = False
            parts.append(text)
        elif node.name == 'br':
            parts.append('\n')
            just_broke = True
    return ''.join(parts)


def normalise_code_blocks(soup, stats):
    """Replace every <pre> with a placeholder holding a fenced code block."""
    fences = {}
    for i, pre in enumerate(soup.find_all('pre')):
        declared = None
        cls = ' '.join(pre.get('class') or [])
        m = re.search(r'(?:brush:|language-|lang:)\s*([a-z#+]+)', cls, re.I)
        if m:
            declared = m.group(1)
        inner_code = pre.find('code')
        if inner_code is not None:
            ccls = ' '.join(inner_code.get('class') or [])
            m2 = re.search(r'(?:language-|lang-)([a-z#+]+)', ccls, re.I)
            if m2:
                declared = m2.group(1)
        code = clean_code_text(pre_to_text(pre))
        if not code:
            pre.decompose()
            continue
        lang = guess_language(code, declared)
        stats['code_blocks'] += 1
        stats['langs'][lang or 'plain'] = stats['langs'].get(lang or 'plain', 0) + 1
        key = f'@@CODEFENCE{i}@@'
        fence = '`' * max(3, (max((len(m) for m in re.findall(r'`+', code)), default=0) + 1))
        fences[key] = f'{fence}{lang}\n{code}\n{fence}'
        pre.replace_with(NavigableString('\n\n' + key + '\n\n'))
    return fences


# Live Writer inserted these as images. They are just emoji.
EMOTICONS = [
    (r'wlEmoticon-smile', '🙂'),
    (r'wlEmoticon-openmouthed', '😃'),
    (r'wlEmoticon-winking', '😉'),
    (r'wlEmoticon-sadsmile|wlEmoticon-disappointed', '🙁'),
    (r'wlEmoticon-surprised', '😮'),
    (r'wlEmoticon-thumbsup', '👍'),
]

# Lines that strongly suggest a console paste rather than prose.
CODEY_LINE = re.compile(
    r'''^\s{2,}\S                       # indented
      | ^(?:az|azd|kubectl|helm|docker|docker-compose|brig|dotnet|git|npm|node
          |choco|wget|curl|apt-get|yum|ssh|scp|msbuild|nuget|terraform|kubeadm)\s
      | ^(?:PS\s+[A-Za-z]:\\|[A-Za-z]:\\|/usr/|/etc/|/var/|\./)
      | ^(?:Step\s+\d+/\d+|--->|==>|\$\s|>\s*\w+\s*=)
      | ^[{}\[\]]\s*$
      | ^-{3,}
      | ^\s*[\w.$-]+\s*[:=]\s*\S.*$
      | ;\s*$
    ''', re.VERBOSE)


def looks_like_code(text):
    lines = [ln for ln in text.replace('\r\n', '\n').split('\n')]
    meaningful = [ln for ln in lines if ln.strip()]
    if len(meaningful) < 3:
        return False
    hits = sum(1 for ln in meaningful if CODEY_LINE.match(ln))
    if hits < 2:
        return False
    # long flowing sentences argue against it being code
    prose = sum(1 for ln in meaningful
                if len(ln) > 120 and ln.count(' ') > 18 and not CODEY_LINE.match(ln))
    if prose > len(meaningful) * 0.25:
        return False
    return hits / len(meaningful) >= 0.4


def promote_code_paragraphs(soup, stats):
    """Turn <p>/<blockquote> that are really console pastes into <pre>."""
    for tag in soup.find_all(['p', 'blockquote']):
        if tag.find('pre') or tag.find('img'):
            continue
        if not tag.find('br') and tag.name == 'p':
            continue
        text = clean_code_text(pre_to_text(tag))
        if not looks_like_code(text):
            continue
        pre = soup.new_tag('pre')
        pre['class'] = ['recovered']
        pre.string = text
        tag.replace_with(pre)
        stats['recovered_code_blocks'] += 1


SOURCECODE_RE = re.compile(
    r'\[sourcecode(?P<attrs>[^\]]*)\](?P<body>.*?)\[/sourcecode\]',
    re.S | re.I)


def convert_sourcecode_shortcodes(raw_html, stats):
    """[sourcecode language="x"]...[/sourcecode] -> <pre class="brush: x">"""
    def repl(m):
        attrs = m.group('attrs') or ''
        lang = ''
        lm = re.search(r'(?:language|lang)\s*=\s*"?([\w#+]+)"?', attrs, re.I)
        if lm:
            lang = lm.group(1)
        stats['shortcode_blocks'] += 1
        body = htmllib.escape(m.group('body'))
        return f'<pre class="brush: {lang}">{body}</pre>'
    return SOURCECODE_RE.sub(repl, raw_html)


# --------------------------------------------------------------------------
# Images
# --------------------------------------------------------------------------

class ImageRegistry:
    """Maps remote image URLs to per-bundle local filenames."""

    def __init__(self):
        self.rows = []          # (download_url, bundle, filename)
        self._seen = {}         # (bundle, filename) -> download_url

    def localise(self, url, bundle):
        split = urlsplit(url)
        if split.scheme not in ('http', 'https') or split.netloc not in SELF_HOSTS:
            return None
        path = unquote(split.path)
        name = os.path.basename(path)
        if not name:
            return None
        # download from the canonical host, whatever the post said
        download = f'https://{CANONICAL_HOST}{path}'
        key = (bundle, name)
        if key in self._seen:
            if self._seen[key] != download:
                # same filename, different source: disambiguate
                stem, ext = os.path.splitext(name)
                n = 2
                while (bundle, f'{stem}-{n}{ext}') in self._seen:
                    n += 1
                name = f'{stem}-{n}{ext}'
                key = (bundle, name)
            else:
                return name
        self._seen[key] = download
        self.rows.append((download, bundle, name))
        return name


def rewrite_media(soup, bundle, images, stats):
    """Localise <img> and unwrap the Live Writer thumb->fullsize <a> pattern."""
    for img in soup.find_all('img'):
        src = (img.get('src') or '').strip()
        if src.startswith('data:'):
            stats['inline_data_images'] += 1
            img.decompose()
            continue
        emoji = next((e for pat, e in EMOTICONS if re.search(pat, src, re.I)), None)
        if emoji:
            target = img.parent if (img.parent is not None
                                    and img.parent.name == 'a'
                                    and len(img.parent.find_all(True)) == 1) else img
            target.replace_with(NavigableString(emoji))
            stats['emoticons'] += 1
            continue
        local = images.localise(src, bundle)
        if local:
            img['src'] = local
            stats['local_images'] += 1
        else:
            stats['remote_images'] += 1
        # drop the layout cruft Live Writer left behind
        for attr in ('style', 'width', 'height', 'border', 'class',
                     'srcset', 'sizes', 'loading', 'data-src'):
            img.attrs.pop(attr, None)
        if not (img.get('alt') or '').strip():
            img['alt'] = ''

        parent = img.parent
        if parent is not None and parent.name == 'a':
            href = (parent.get('href') or '').strip()
            hlocal = images.localise(href, bundle)
            if hlocal:
                if hlocal == local:
                    parent.unwrap()          # link to itself, pointless
                else:
                    parent['href'] = hlocal  # keep click-through to full size
                    stats['thumb_links'] += 1
            elif not href:
                parent.unwrap()


def split_images_from_paragraphs(soup):
    """Give images their own block when they share a paragraph with text."""
    for p in soup.find_all('p'):
        imgs = p.find_all('img')
        if not imgs:
            continue
        text = p.get_text(strip=True)
        if not text:
            continue
        anchor = p
        for img in imgs:
            node = img.parent if (img.parent is not None
                                  and img.parent.name == 'a'
                                  and len(img.parent.find_all('img')) == 1) else img
            wrapper = soup.new_tag('p')
            node.extract()
            wrapper.append(node)
            anchor.insert_after(wrapper)
            anchor = wrapper
        if not p.get_text(strip=True) and not p.find(['img', 'iframe']):
            p.decompose()


INTERNAL_POST_RE = re.compile(
    r'^https?://(?:www\.)?blog\.ehn\.nu(/\d{4}/\d{2}/[^"\s]*)$', re.I)


def rewrite_links(soup, stats):
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        m = INTERNAL_POST_RE.match(href)
        if m:
            a['href'] = m.group(1)
            stats['internal_links'] += 1
        elif href.startswith('https://blogehn.azurewebsites.net/'):
            a['href'] = href.replace('https://blogehn.azurewebsites.net',
                                     f'https://{CANONICAL_HOST}')
        # strip WordPress sharing widgets
        if 'addtoany.com' in href:
            a.decompose()


# --------------------------------------------------------------------------
# HTML -> Markdown
# --------------------------------------------------------------------------

class BlogConverter(MarkdownConverter):
    """markdownify with ATX headings and sane emphasis characters."""

    class Options(MarkdownConverter.DefaultOptions):
        heading_style = 'ATX'
        bullets = '-'
        strong_em_symbol = '*'
        code_language = ''
        escape_underscores = False
        escape_asterisks = False
        newline_style = 'BACKSLASH'

    def convert_pre(self, el, text, parent_tags=None):
        return text  # <pre> already turned into placeholders


def strip_wp_chrome(soup):
    """Remove Gutenberg comments, empty paragraphs and share widgets."""
    for el in soup.find_all(['script', 'style', 'ins']):
        el.decompose()
    for div in soup.find_all('div', class_=re.compile(r'addtoany|sharedaddy|mashsb')):
        div.decompose()
    for p in soup.find_all('p'):
        if not p.get_text(strip=True) and not p.find(['img', 'br', 'iframe']):
            p.decompose()


def unwrap_layout_tables(soup, stats):
    """Live Writer used single-row tables to frame code and images.

    Those are layout, not data, and a pipe table cannot hold a fenced block.
    Multi-row tables are left alone so real data tables survive.
    """
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        if not (table.find('pre') or len(rows) <= 1):
            continue
        replacement = soup.new_tag('div')
        for cell in table.find_all(['td', 'th']):
            block = soup.new_tag('div')
            for child in list(cell.contents):
                block.append(child.extract())
            replacement.append(block)
        table.replace_with(replacement)
        stats['unwrapped_tables'] += 1


BLOCK_COMMENT_RE = re.compile(r'<!--\s*/?wp:.*?-->', re.S)


def html_to_markdown(raw, bundle, images, stats):
    raw = raw.replace('\r\n', '\n')
    raw = BLOCK_COMMENT_RE.sub('', raw)
    raw = convert_sourcecode_shortcodes(raw, stats)
    # WordPress stores paragraph breaks as bare newlines in classic posts
    raw = wpautop(raw)

    soup = BeautifulSoup(raw, 'html.parser')
    strip_wp_chrome(soup)
    unwrap_layout_tables(soup, stats)
    promote_code_paragraphs(soup, stats)
    fences = normalise_code_blocks(soup, stats)
    rewrite_media(soup, bundle, images, stats)
    split_images_from_paragraphs(soup)
    rewrite_links(soup, stats)

    md = BlogConverter().convert_soup(soup)

    for key, fence in fences.items():
        md = md.replace(key, fence)

    md = merge_adjacent_fences(md)
    md = requote_fences(md)
    md = re.sub(r'[ \t]*\\\n(?=[ \t]*(\n|$))', '\n', md)  # dangling hard break
    md = re.sub(r'\n[ \t]*\\[ \t]*(?=\n)', '', md)        # lone backslash line
    md = re.sub(r'\n{3,}', '\n\n', md)
    md = re.sub(r'[ \t]+\n', '\n', md)
    return md.strip() + '\n'


ADJACENT_FENCE_RE = re.compile(
    r'```([a-z#+]*)\n(.*?)\n```\n{1,2}```\1\n(.*?)\n```', re.S)


def requote_fences(md):
    """A fence opened inside a blockquote must keep '>' on every line."""
    out, marker = [], None
    for line in md.split('\n'):
        m = re.match(r'^((?:[ \t]*>)+[ \t]?|[ \t]+)```', line)
        if marker is None and m:
            marker = m.group(1)
            out.append(line)
            continue
        if marker is not None:
            if not line.startswith(marker):
                line = (marker + line) if line.strip() else marker.rstrip()
            body = line[len(marker):]
            out.append(line)
            if body.strip().startswith('```'):
                marker = None
            continue
        out.append(line)
    return '\n'.join(out)


def merge_adjacent_fences(md):
    """The old editor emitted one <pre> per line; stitch those back together."""
    prev = None
    while prev != md:
        prev = md
        md = ADJACENT_FENCE_RE.sub(
            lambda m: f'```{m.group(1)}\n{m.group(2)}\n{m.group(3)}\n```', md)
    return md


BLOCK_TAGS = ('p|div|pre|table|thead|tbody|tr|td|th|ul|ol|li|blockquote|h[1-6]'
              r'|figure|section|article|hr|iframe|script|style|form')


def wpautop(text):
    """Approximation of WordPress' wpautop for classic-editor content."""
    if re.search(r'<p[\s>]', text, re.I):
        return text  # already has paragraphs
    text = re.sub(r'\n{2,}', '\n\n', text)
    chunks = text.split('\n\n')
    out = []
    for chunk in chunks:
        c = chunk.strip()
        if not c:
            continue
        if re.match(r'^\s*</?(' + BLOCK_TAGS + r')[\s/>]', c, re.I):
            out.append(c)
        else:
            out.append('<p>' + c.replace('\n', '<br />\n') + '</p>')
    return '\n\n'.join(out)


# --------------------------------------------------------------------------
# Front matter and comments
# --------------------------------------------------------------------------

def yaml_scalar(value):
    s = str(value)
    if s == '':
        return '""'
    if re.match(r'^\d{4}-\d{2}-\d{2}T[\d:]+Z$', s):
        return s
    if re.search(r'[:#\[\]{}&*?|>%@`"\']|^\s|\s$|^-\s|^\d{4}-\d{2}', s):
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return s


def yaml_list(values):
    return '[' + ', '.join(yaml_scalar(v) for v in values) + ']'


def build_front_matter(meta):
    lines = ['---']
    for key, value in meta.items():
        if value in (None, '', [], {}):
            continue
        if isinstance(value, list):
            lines.append(f'{key}: {yaml_list(value)}')
        elif isinstance(value, bool):
            lines.append(f'{key}: {"true" if value else "false"}')
        else:
            lines.append(f'{key}: {yaml_scalar(value)}')
    lines.append('---')
    return '\n'.join(lines) + '\n'


def parse_wp_date(raw):
    if not raw or raw.startswith('0000'):
        return None
    try:
        return datetime.strptime(raw, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return None


def comment_tree(item):
    """Return approved, non-pingback comments as a parent-ordered list."""
    comments = []
    for c in item.findall('wp:comment', NS):
        if (c.findtext('wp:comment_approved', namespaces=NS) or '') != '1':
            continue
        ctype = (c.findtext('wp:comment_type', namespaces=NS) or '').strip()
        if ctype in ('pingback', 'trackback'):
            continue
        comments.append({
            'id': int(c.findtext('wp:comment_id', namespaces=NS) or 0),
            'parent': int(c.findtext('wp:comment_parent', namespaces=NS) or 0),
            'author': (c.findtext('wp:comment_author', namespaces=NS) or 'Anonymous').strip(),
            'url': (c.findtext('wp:comment_author_url', namespaces=NS) or '').strip(),
            'date': c.findtext('wp:comment_date', namespaces=NS) or '',
            'content': c.findtext('wp:comment_content', namespaces=NS) or '',
        })
    by_parent = {}
    for c in comments:
        by_parent.setdefault(c['parent'], []).append(c)
    for lst in by_parent.values():
        lst.sort(key=lambda c: c['date'])
    ordered = []

    def walk(pid, depth):
        for c in by_parent.get(pid, []):
            c['depth'] = depth
            ordered.append(c)
            walk(c['id'], depth + 1)
    walk(0, 0)
    # orphans whose parent fell outside the export
    known = {c['id'] for c in ordered}
    for c in comments:
        if c['id'] not in known:
            c['depth'] = 0
            ordered.append(c)
    return ordered


def render_comments(comments):
    if not comments:
        return ''
    out = ['\n---\n', '## Comments\n',
           '*Imported from the original WordPress site. '
           'Closed for new replies.*\n']
    for c in comments:
        raw = c['content']
        # Some comments arrived with their HTML escaped, sometimes only
        # partway through. Unescape sequences that are clearly tags.
        raw = re.sub(r'&lt;(/?[a-zA-Z][a-zA-Z0-9]*)((?:\s[^&<>]*?)?)\s*(/?)&gt;',
                     r'<\1\2\3>', raw)
        soup = BeautifulSoup(wpautop(raw), 'html.parser')
        body = BlogConverter().convert_soup(soup).strip()
        body = re.sub(r'\n{3,}', '\n\n', body)
        who = f"[{c['author']}]({c['url']})" if c['url'].startswith('http') else c['author']
        when = (parse_wp_date(c['date']) or datetime(1970, 1, 1)).strftime('%d %b %Y')
        prefix = '> ' * (c['depth'] + 1)
        block = [f"{prefix}**{who}** — {when}", prefix.rstrip()]
        for line in body.split('\n'):
            block.append(f'{prefix}{line}'.rstrip())
        out.append('\n'.join(block) + '\n')
    return '\n'.join(out)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def terms(item, domain):
    seen = OrderedDict()
    for cat in item.findall('category'):
        if cat.get('domain') == domain and cat.text:
            name = cat.text.strip()
            if name and name.lower() != 'uncategorized':
                seen[name] = True
    return list(seen)


def convert(xml_path, outdir, limit_slugs=None, with_comments=True):
    root = ET.parse(xml_path).getroot()
    channel = root.find('channel')
    items = channel.findall('item')
    images = ImageRegistry()
    stats = {'code_blocks': 0, 'recovered_code_blocks': 0, 'shortcode_blocks': 0,
             'local_images': 0, 'remote_images': 0, 'thumb_links': 0,
             'internal_links': 0, 'inline_data_images': 0, 'emoticons': 0,
             'unwrapped_tables': 0,
             'comments': 0, 'langs': {}}

    posts_dir = os.path.join(outdir, 'content', 'posts')
    os.makedirs(posts_dir, exist_ok=True)
    written = []

    for item in items:
        ptype = item.findtext('wp:post_type', namespaces=NS)
        status = item.findtext('wp:status', namespaces=NS)
        if ptype not in ('post', 'page'):
            continue
        slug = (item.findtext('wp:post_name', namespaces=NS) or '').strip()
        title = (item.findtext('title') or '').strip()
        if not slug:
            slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-') or 'untitled'
        if limit_slugs and slug not in limit_slugs:
            continue

        date = parse_wp_date(item.findtext('wp:post_date_gmt', namespaces=NS)) \
            or parse_wp_date(item.findtext('wp:post_date', namespaces=NS))
        raw = item.findtext('content:encoded', namespaces=NS) or ''

        if ptype == 'post':
            bundle = f'{date.strftime("%Y-%m")}-{slug}' if date else slug
            target_dir = os.path.join(posts_dir, bundle)
            os.makedirs(target_dir, exist_ok=True)
            path = os.path.join(target_dir, 'index.md')
            rel_bundle = f'content/posts/{bundle}'
        else:
            bundle = slug
            target_dir = os.path.join(outdir, 'content', slug)
            os.makedirs(target_dir, exist_ok=True)
            path = os.path.join(target_dir, 'index.md')
            rel_bundle = f'content/{bundle}'

        body = html_to_markdown(raw, rel_bundle, images, stats)

        meta = OrderedDict()
        meta['title'] = title
        if date:
            meta['date'] = date.strftime('%Y-%m-%dT%H:%M:%SZ')
        meta['slug'] = slug
        if ptype == 'post':
            meta['categories'] = terms(item, 'category')
            meta['tags'] = terms(item, 'post_tag')
        if status == 'draft':
            meta['draft'] = True
        meta['aliases'] = []
        if ptype == 'post' and date:
            meta['aliases'] = [f'/{date.strftime("%Y/%m")}/{slug}/']

        content = build_front_matter(meta) + '\n' + body
        if with_comments and ptype == 'post':
            cmts = comment_tree(item)
            stats['comments'] += len(cmts)
            content += render_comments(cmts)

        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(content)
        written.append((ptype, path, len(content)))

    write_image_scripts(outdir, images)
    return written, images, stats


def write_image_scripts(outdir, images):
    manifest = os.path.join(outdir, 'image-manifest.tsv')
    with open(manifest, 'w', encoding='utf-8') as fh:
        fh.write('url\tbundle\tfilename\n')
        for url, bundle, name in images.rows:
            fh.write(f'{url}\t{bundle}\t{name}\n')

    script = os.path.join(outdir, 'download-images.sh')
    with open(script, 'w', encoding='utf-8') as fh:
        fh.write(r'''#!/usr/bin/env bash
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
''')
    os.chmod(script, 0o755)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('xml')
    ap.add_argument('outdir')
    ap.add_argument('--limit-slugs', default=None)
    ap.add_argument('--no-comments', action='store_true')
    args = ap.parse_args()

    limit = set(args.limit_slugs.split(',')) if args.limit_slugs else None
    written, images, stats = convert(args.xml, args.outdir, limit,
                                    with_comments=not args.no_comments)

    print(f'wrote {len(written)} files to {args.outdir}')
    for k, v in stats.items():
        print(f'  {k}: {v}')
    print(f'  images to download: {len(images.rows)}')


if __name__ == '__main__':
    sys.exit(main())
