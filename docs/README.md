# Music Crow website — GitHub Pages

A buildless, responsive Polish landing page and privacy policy. The public contact approved for this site is `minu3009@gmail.com`; the publisher is identified by the GitHub handle `Miniu123`. Review the policy against any future application changes before publishing updates.

## Publish from this repository

1. Upload the **entire `docs` folder**, including `assets/`, to the `main` branch of `Miniu123/Music_Crow`. You can use GitHub **Add file → Upload files** or commit the files locally. Keep the directory structure intact.
2. In the repository, open **Settings → Pages**.
3. Under **Build and deployment**, choose **Deploy from a branch**.
4. Select branch **main**, folder **/docs**, and click **Save**.
5. Wait for the Pages deployment to succeed under **Actions**. Use **Visit site** in the Pages settings to confirm the published address.

Expected addresses after deployment:

- Homepage: `https://miniu123.github.io/Music_Crow/`
- Privacy policy: `https://miniu123.github.io/Music_Crow/privacy.html`

No Node.js, npm, backend, build command, external fonts, analytics scripts, or secrets are needed. `.nojekyll` keeps this a plain static site. Relative asset links work under the repository path and under a custom domain. The homepage's illustrated player is decorative, not a browser music player.

If this checkout is already linked to the correct repository, upload only the website and documentation changes with:

```bash
git add docs
git commit -m "Add Music Crow website and privacy policy"
git push origin main
```

The root `README.md` also links to this guide; add it separately after reviewing its other existing local edits. Do not use `git add .` merely to publish the site. Only `docs` is used as the Pages publishing source, so runtime configuration and tokens must stay outside it.

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
