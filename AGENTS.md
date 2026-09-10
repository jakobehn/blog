# AGENTS.md
Guidance for AI agents working in this repository.

## What this is
A Hugo blog migrated from WordPress, published to GitHub Pages. Posts date back to 2009 and their URLs must keep working.

- **Build:** Hugo **0.165.0 extended**, pinned in [.github/workflows/deploy.yml](.github/workflows/deploy.yml)
- **Deploy:** push to `main` → GitHub Pages
- **Production build command:** `hugo --minify`

## Theme
Blowfish, vendored as a git submodule at `themes/blowfish` and configured in the root [hugo.toml](hugo.toml).

PaperMod was the original theme and was removed once Blowfish went live. It survives in git history, so reverting the removal commit is the rollback path — there is no second theme in the working tree.

## Local builds

Hugo is not installed on the user's machine and they have declined a machine-wide install. To verify a build, download a portable binary instead:

```powershell
$d="$env:TEMP\hugo-portable"
Invoke-WebRequest "https://github.com/gohugoio/hugo/releases/download/v0.165.0/hugo_extended_0.165.0_windows-amd64.zip" -OutFile "$d\hugo.zip"
Expand-Archive "$d\hugo.zip" -DestinationPath $d -Force
& "$d\hugo.exe" --minify --destination public-test
```

Always verify a build before telling the user a change is ready. The build should produce **192 pages** with zero warnings and zero errors. Delete the test output directory afterwards — only `/public/` is gitignored.

## Content

- Posts are page bundles: `content/posts/<yyyy-mm-slug>/index.md`, images alongside the markdown (99 posts).
- `permalinks.posts = "/:year/:month/:slug/"` and per-post `aliases` preserve the original WordPress URLs. **Do not change either.**
- `markup.goldmark.renderer.unsafe = true` is required — many posts contain hand-written HTML.
- Front matter still uses PaperMod's `cover.image` for post images. A site-level override teaches Blowfish to read it, so there is no need to bulk-rewrite front matter to `featureImage`.

Migrated content contains artifacts from WordPress and Windows Live Writer: stripped backslashes, mangled links, thumbnail-sized images. The one-off Python scripts at the repo root (`wxr2hugo.py`, `set-post-covers.py`, `use-full-images.py`, `verify-content.py`) were used for the migration and are kept for reference.

## Layout overrides

Site-level overrides in `layouts/` shadow the theme. Both exist for a reason:

- [layouts/partials/functions/feature-image.html](layouts/partials/functions/feature-image.html) — falls back to the `cover.image` front matter the migration wrote, so posts do not need rewriting.
- [layouts/_default/_markup/render-link.html](layouts/_default/_markup/render-link.html) — wraps `urls.Parse` in `try`. Blowfish's stock hook aborts the build on the malformed `file://` UNC paths left by the migration. Do not remove this guard.

Theme-owned files under `themes/blowfish` are a submodule — never edit them; add a site-level override instead.

## Known gaps under Blowfish

- Blowfish has no `archives` layout. The Archive menu points at `/posts` with `groupByYear = true`.
- Blowfish's search is a header modal fed by the home JSON output, so there is no `/search/` page.
- [assets/css/extended/custom.css](assets/css/extended/custom.css) is **dead**. That path and its selectors (`.post-content`, `.entry-header`) are PaperMod's; Blowfish loads `assets/css/custom.css` and uses Tailwind markup. Porting it means rewriting it, not moving it.


## Never commit or push

**Do not run `git commit`, `git push`, `git revert`, or any other command that writes to git history or the remote.** Make changes in the working tree and leave them uncommitted for the user to review. Pushing to `main` triggers a production deployment to https://blog.ehn.nu/, so committing on the user's behalf publishes unreviewed changes to a live site. Staging with `git add` is also unnecessary — just leave the files modified.

Read-only git commands (`git status`, `git diff`, `git log`) are fine.