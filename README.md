# blog.ehn.nu — Hugo

Converted from the WordPress export of 2 September 2026. 99 posts (Feb 2009 – Apr 2020),
4 pages, 561 comments preserved as static text.

## Do this first, before anything else

**The images are not in this repo yet, and the old site is the only place they exist.**
505 of them still live on `blog.ehn.nu/wp-content/uploads/`. 336 were never registered in
the WordPress media library, so the XML export cannot tell you what they are — this repo's
`image-manifest.tsv` was reconstructed by reading every `<img>` tag in every post.

Some posts point at `blogehn.azurewebsites.net`, the App Service default hostname. Those
images die the moment you stop the Azure app, so do not shut anything down yet.

```powershell
.\download-images.ps1            # pulls every image into its post folder
python3 verify-content.py        # confirms nothing is missing
```

Or, on bash: `bash download-images.sh`. The two are equivalent; use whichever suits you.

Both are safe to re-run: they skip files they already have and write anything they could
not fetch to `image-failures.tsv`. That file is itself a valid manifest, so you can retry
just the stragglers with `.\download-images.ps1 -Manifest image-failures.tsv`.

The PowerShell version takes `-Parallel <n>` on PowerShell 7+, which cuts the 505-image
run down considerably. It also forces TLS 1.2, needed if you are on Windows PowerShell 5.1.

Worth also taking a belt-and-braces archive of the live site while it is up:

```bash
wget --mirror --page-requisites --convert-links --no-parent -P wp-archive https://blog.ehn.nu/
```

Keep that tarball somewhere off this repo. If a conversion problem surfaces in six months,
it is the only copy of the original rendering you will have.

## Then get it running

```bash
git init && git add . && git commit -m "Import from WordPress"
git submodule add --depth=1 https://github.com/adityatelange/hugo-PaperMod.git themes/PaperMod
hugo server -D
```

`-D` includes drafts, which is how the unfinished Privacy Policy page is marked.

To deploy: push to GitHub, then Settings → Pages → Source → **GitHub Actions**. The workflow
in `.github/workflows/deploy.yml` does the rest. For the custom domain, add `blog.ehn.nu`
under Settings → Pages, put a `CNAME` file containing `blog.ehn.nu` in `static/`, and point
the DNS record at GitHub. Only flip DNS once the built site looks right.

## What the converter did

| | |
|---|---|
| Posts | 99, as page bundles under `content/posts/YYYY-MM-slug/` |
| Pages | About Me, Books, Speaking, Privacy Policy (draft) |
| Comments | 561 approved, appended to each post under `## Comments`. 26 pingbacks dropped |
| Code blocks | 135 from `<pre>`, 31 recovered from console output that was never in a `<pre>`, 5 from `[sourcecode]` shortcodes |
| Images | 505 localised into bundles, 11 left pointing at third-party hosts, 2 inline base64 blobs dropped |
| Emoticons | 25 Live Writer smiley images replaced with real emoji |
| Tables | 7 layout tables unwrapped, 4 genuine data tables kept |

Beyond the mechanical conversion:

- **Smart punctuation was reversed inside code only.** WordPress had rewritten `--` as `–`
  and straight quotes as curly ones, so commands like `az login --service-principal` were
  broken as published. Prose keeps its typography.
- **Runaway entity escaping was undone.** One post had `=&amp;amp;amp;amp;gt;` where `=>`
  belonged.
- **Live Writer's thumbnail pattern was preserved** as `[![alt](thumb.png)](full.png)`, so
  clicking an image still opens the full-size version.
- **Language tags were inferred** from block contents. 75 blocks could not be identified
  and are unlabelled — they will render fine, just without highlighting.

## URLs

Permalinks are configured as `/:year/:month/:slug/`, identical to WordPress. Every post
also carries an `aliases` entry for its old URL as a safety net. Nothing that currently
links to the blog should break.

## Things worth a human eye

- The 75 unlabelled code blocks. Adding a language to the fence is a two-second fix per
  block and improves the reading experience. Grep for '```\n' to find them.
- Posts from 2009–2012 reference CodePlex, MSDN blogs, and `visualstudiogallery.msdn.microsoft.com`.
  Those hosts are gone. Consider a one-line note at the top of the oldest posts rather than
  chasing dead links.
- 11 images are hotlinked from third parties (docker.com, brigade.sh, pbs.twimg.com). They
  work today and will rot eventually. `grep -rn '!\[.*\](http' content/` lists them.
- Comment threading is rendered with nested blockquotes. If that reads badly on a long
  thread, the `render_comments` function in the converter is where to change it.

## Re-running the conversion

`wxr2hugo.py` is idempotent and does not delete anything, so you can tweak it and re-run
against the same export:

```bash
python3 wxr2hugo.py blogehnnu_WordPress_2026-09-02.xml . 
python3 wxr2hugo.py export.xml out --limit-slugs some-post-slug   # one post, for testing
python3 wxr2hugo.py export.xml out --no-comments                  # drop the comments
```

Downloaded images are untouched by a re-run as long as the bundle names do not change.
