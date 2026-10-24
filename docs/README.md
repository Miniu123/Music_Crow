# Music Crow website — GitHub Pages

A buildless, responsive Polish landing page, privacy policy and license page. The public contact approved for this site is `minu3009@gmail.com`; the publisher is identified by the GitHub handle `Miniu123`. Review the policy against any future application changes before publishing updates.

## Publish from this repository

1. Upload the **entire `docs` folder**, including `assets/`, to the `main` branch of `Miniu123/Music_Crow`. You can use GitHub **Add file → Upload files** or commit the files locally. Keep the directory structure intact.
2. In the repository, open **Settings → Pages**.
3. Under **Build and deployment**, choose **Deploy from a branch**.
4. Select branch **main**, folder **/docs**, and click **Save**.
5. Wait for the Pages deployment to succeed under **Actions**. Use **Visit site** in the Pages settings to confirm the published address.

Expected addresses after deployment:

- Homepage: `https://miniu123.github.io/Music_Crow/`
- Privacy policy: `https://miniu123.github.io/Music_Crow/privacy.html`
- License: `https://miniu123.github.io/Music_Crow/license.html`

The license page distinguishes the MIT license for original project code from dependency and binary-distribution requirements. Keep its embedded MIT text and `assets/LICENSE.txt` identical to the repository's root `LICENSE`. Advertising is described as a possible future feature; the privacy policy continues to describe the current implementation without an advertising system.

No Node.js, npm, backend, build command, external fonts, analytics scripts, or secrets are needed. `.nojekyll` keeps this a plain static site. Relative asset links work under the repository path and under a custom domain. The homepage's illustrated player is decorative, not a browser music player.

## App download

The homepage's primary button and centred download section point directly to
`Music-Crow-0.1.0-x86_64.flatpak` on the repository's `main` branch, using
GitHub's raw download URL. The bundle and `SHA256SUMS` live in the repository
root, outside `docs/`; the website does not store a second copy. Publish both
root files as well as the website changes. The links become available only
after the files reach GitHub. Upload the bundle using Git (the browser upload
limit is lower), and keep it below GitHub's 100 MiB regular-file limit.

When replacing the bundle, update its SHA-256 checksum. For a new filename or
version, update both download buttons, the installation command and the
version labels in `index.html`, as well as the root README. Check the download
after deployment; a locally working page alone does not verify a published
binary.

## Publishing website changes

If this checkout is already linked to the correct repository, stage the website and download files with:

```bash
git add docs README.md .gitattributes Music-Crow-0.1.0-x86_64.flatpak SHA256SUMS
git commit -m "Add Music Crow Flatpak download and installation guide"
git push origin main
```

Review other application and licensing changes and include them as appropriate. Do not use `git add .` merely to publish the site. Only `docs` is used as the Pages publishing source, so user configuration and tokens must stay outside it.

GitHub instructions: https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site

## Google OAuth branding

After deployment, open both public URLs while signed out. In **Google Auth Platform → Branding**, enter the homepage and privacy-policy URLs, and use the same public support email: `minu3009@gmail.com`.

Hosting the pages does **not** itself verify ownership or guarantee Google's approval. Google separately requires verification of the domains used for OAuth branding. Do not enter `github.com` or `github.io` as a domain you own. If Google cannot verify your GitHub Pages subdomain for branding, connect a domain you control to GitHub Pages, verify that domain with **Google Search Console**, and use the custom-domain URLs for both pages.

For a custom domain, configure it in **Settings → Pages → Custom domain**, follow GitHub's DNS instructions, and enable **Enforce HTTPS** when available. When publishing from `/docs`, preserve the `docs/CNAME` file that GitHub creates. No custom domain is set in these files because none has been supplied.

- Google brand verification: https://developers.google.com/identity/verification/authentication-verification
- GitHub Pages custom domains: https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site

## Preview locally

```bash
python3 -m http.server 8000 --bind 127.0.0.1 --directory docs
```

Open `http://127.0.0.1:8000/` and `http://127.0.0.1:8000/privacy.html`.
