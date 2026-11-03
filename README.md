# Ryce website

Hosted with GitHub Pages at https://getryce.app from https://github.com/sforsethi/ryce-website (main branch, repository root).

This directory is a local source copy. The original https://apps.niyatstudio.com website remains hosted from sforsethi/apps-portfolio and was not changed.

Pages: /, /ryce/, /ryce-story/, /ryce-duo/, /marketing.html, /privacy.html, /terms.html, /eula.html. Extensionless legal and marketing paths also work.

DNS: apex A records 185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153. www CNAME sforsethi.github.io. Enable HTTPS in GitHub Pages after DNS and certificate provisioning finish.

## Recipe blog

The first published recipe is `/recipes/pesto-gnocchi/`; `/recipes/` links to it. Data comes from the live public Firestore catalog, filtered to the app’s active packs. No Firebase writes or credentials are used.

Rebuild only the first recipe:

```sh
python3 scripts/build-recipes.py --only pesto-gnocchi
```

After the first page is approved, omit `--only` to build all active catalog recipes. Requires Python 3 and Pillow. Pages are static HTML, images are optimized transparent WebP files, and ingredient selections stay in browser session storage. Recipe copy, nutrition and colors come directly from Firebase. The snapshot contains only public catalog fields, without internal provenance or translation sidecars.
