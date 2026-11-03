#!/usr/bin/env python3
"""Read the public app catalog and build its static recipe blog. Never writes to Firebase.

Run: python3 scripts/build-recipes.py --only pesto-gnocchi
Omit --only to build the full public catalog (requires Pillow for optimized artwork).
"""
import concurrent.futures
import argparse
import hashlib
import html
import io
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://getryce.app'
STORE = 'https://apps.apple.com/app/id6768017245'
FIRESTORE = 'https://firestore.googleapis.com/v1/projects/ryce-f10a2/databases/(default)/documents/'
E = html.escape


def get(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def decode(value):
    kind, data = next(iter(value.items()))
    if kind == 'mapValue':
        return {k: decode(v) for k, v in data.get('fields', {}).items()}
    if kind == 'arrayValue':
        return [decode(v) for v in data.get('values', [])]
    if kind == 'integerValue':
        return int(data)
    if kind == 'doubleValue':
        return float(data)
    return data


def collection(name):
    docs, token = [], ''
    while True:
        query = urllib.parse.urlencode({'pageSize': 300, 'pageToken': token})
        result = json.loads(get(FIRESTORE + name + '?' + query))
        docs.extend({**{k: decode(v) for k, v in d['fields'].items()},
                     'id': d['name'].split('/')[-1]} for d in result.get('documents', []))
        token = result.get('nextPageToken')
        if not token:
            return docs


def theme_style(recipe):
    t = recipe['theme']
    stops = ','.join(f"{s['hex']} {s['location'] * 100:g}%" for s in t['backgroundGradient'])
    return (f"--recipe-bg:linear-gradient(180deg,{stops});--ink:{t['textPrimaryHex']};"
            f"--accent:{t['accentHex']};--card:{t['nutritionCardFillHex']};"
            f"--cta:{t['ctaFillHex']};--cta-text:{t['ctaTextHex']}")


def badge():
    return f'''<a class="store-badge" href="{STORE}" aria-label="Download Ryce on the App Store"><svg viewBox="0 0 24 28" aria-hidden="true"><path fill="currentColor" d="M19.4 14.9c0-3.1 2.6-4.6 2.7-4.7-1.5-2.2-3.8-2.5-4.6-2.5-2-.2-3.9 1.2-4.9 1.2s-2.6-1.2-4.3-1.1c-2.2 0-4.2 1.3-5.3 3.2-2.2 3.8-.6 9.5 1.5 12.6 1 1.5 2.3 3.1 3.9 3 1.6-.1 2.2-1 4.2-1s2.6 1 4.3.9c1.8 0 2.9-1.5 3.9-3 1.2-1.7 1.7-3.4 1.8-3.5-.1 0-3.2-1.2-3.2-5.1ZM16.1 5.7c.9-1.1 1.5-2.6 1.3-4.2-1.3.1-2.9.9-3.9 2-.8 1-1.6 2.5-1.4 4 1.5.1 3-.7 4-1.8Z"/></svg><span><small>Download on the</small><strong>App Store</strong></span></a>'''


def head(title, description, path, image=None, schema=None):
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)} · Ryce</title><meta name="description" content="{E(description, quote=True)}"><meta name="theme-color" content="#f6f3e9">
<link rel="canonical" href="{BASE}{path}"><link rel="icon" href="/ryce/assets/icon.png"><link rel="stylesheet" href="/recipes/recipes.css?v=1"><script src="/recipes/recipes.js?v=1" defer></script>
<meta property="og:type" content="article"><meta property="og:title" content="{E(title, quote=True)}"><meta property="og:description" content="{E(description, quote=True)}"><meta property="og:url" content="{BASE}{path}"><meta property="og:image" content="{BASE}{image or '/ryce/assets/icon.png'}"><meta name="twitter:card" content="summary_large_image">
{('<script type="application/ld+json">' + json.dumps(schema, ensure_ascii=False).replace('<', chr(92)+'u003c') + '</script>') if schema else ''}</head>'''


def footer():
    return '''<footer class="recipe-footer"><a class="wordmark" href="/">ryce</a><nav aria-label="Footer"><a href="/recipes/">All recipes</a><a href="/ryce-story/">Our story</a><a href="/privacy.html">Privacy</a><a href="/terms.html">Terms</a></nav><small>Made by Niyat Studio · © 2026</small></footer>'''


def card(doc):
    r = doc['recipe']
    groups = ' '.join(doc['collections'])
    search = ' '.join([r['title'], r['description'], *r['ingredients'], *doc['tags']]).lower()
    return f'''<a class="recipe-card" href="/recipes/{E(doc['id'])}/" style="{theme_style(r)}" data-groups="{E(groups)}" data-search="{E(search, quote=True)}" data-minutes="{r['minutes']}"><div class="card-art"><img src="{doc['image']}" alt="{E(r['title'], quote=True)} on a round plate" width="768" height="768" loading="lazy" decoding="async"></div><div class="card-copy"><p>{E(doc['collectionName'])}</p><h2>{E(r['title'])}</h2><span>{r['minutes']} min · {len(r['ingredients'])} ingredients <b aria-hidden="true">↗</b></span></div></a>'''


def detail(doc, related):
    r, rid = doc['recipe'], doc['id']
    schema = {'@context': 'https://schema.org', '@type': 'Recipe', 'name': r['title'],
              'description': r['description'], 'image': BASE + doc['image'],
              'author': {'@type': 'Organization', 'name': 'Ryce', 'url': BASE},
              'recipeIngredient': r['ingredients'],
              'recipeInstructions': [{'@type': 'HowToStep', 'position': i + 1, 'text': s} for i, s in enumerate(r['steps'])]}
    # The app records minutes without a preparation/cooking breakdown; don't invent one.
    ingredients = ''.join(f'<li><label><input type="checkbox"><span>{E(s)}</span></label></li>' for s in r['ingredients'])
    steps = ''.join(f'<li><span class="step-number" aria-hidden="true">{i+1}</span><p>{E(s)}</p></li>' for i, s in enumerate(r['steps']))
    n = r['nutrition']
    nutrition = ''.join(f'<div><dt>{label}</dt><dd>{n[key]}{unit}</dd></div>' for label, key, unit in [
        ('protein', 'proteinGrams', 'g'), ('carbs', 'carbsGrams', 'g'), ('fats', 'fatsGrams', 'g'), ('calories', 'calories', '<small>kcal</small>')])
    return head(r['title'], r['description'], f'/recipes/{rid}/', doc['image'], schema) + f'''
<body class="recipe-page" style="{theme_style(r)}"><a class="skip-link" href="#main">Skip to recipe</a><div class="recipe-backdrop" aria-hidden="true"></div>
<header class="recipe-topbar"><a class="glass back-link" href="/recipes/"><span aria-hidden="true">‹</span> All recipes</a><a class="wordmark" href="/" aria-label="Ryce home">ryce</a><button class="glass share-button" type="button" aria-label="Share this recipe"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 15V3m-4 4 4-4 4 4M7 11H5v10h14V11h-2"/></svg></button></header>
<main id="main" class="recipe-main" data-recipe-id="{E(rid)}"><article><div class="recipe-hero"><div class="plate-wrap"><img class="plate" src="{doc['image']}" alt="{E(r['title'], quote=True)} served on a round plate" width="768" height="768" fetchpriority="high"></div><div class="hero-copy"><h1>{E(r['title'])}</h1><p class="recipe-meta">{r['minutes']} min · {len(r['ingredients'])} ingredients</p><a class="cook-button" href="{STORE}"><span aria-hidden="true">▶</span> Cook</a><p class="description">{E(r['description'])}</p><dl class="nutrition" aria-label="Nutrition as shown in Ryce">{nutrition}</dl></div></div>
<div class="recipe-method"><section class="ingredients" aria-labelledby="ingredients-title"><h2 id="ingredients-title">Ingredients</h2><ul>{ingredients}</ul><button class="reset-ingredients" type="button" hidden>Reset checklist</button></section><section class="steps" id="steps" aria-labelledby="steps-title"><h2 id="steps-title">Steps</h2><ol>{steps}</ol></section></div></article>
<aside class="app-download"><img src="/ryce/assets/icon.png" alt="Ryce app icon" width="64" height="64"><p class="eyebrow">From inspiration to dinner</p><h2>Keep this one close.</h2><p>Save your favourite recipes, plan your meals,<br>and enjoy cooking with Ryce.</p>{badge()}</aside>
<section class="related" aria-labelledby="related-title"><div class="section-heading"><h2 id="related-title">Something else delicious.</h2><a href="/recipes/">All recipes <span aria-hidden="true">↗</span></a></div><div class="recipe-grid">{''.join(card(x) for x in related)}</div></section></main>{footer()}<p class="toast" role="status" aria-live="polite"></p></body></html>'''


def build(only=None):
    packs = sorted([p for p in collection('packs') if p.get('isActive')], key=lambda p: p.get('order', 0))
    recipes = collection('recipes')
    public = []
    for doc in recipes:
        groups = [p for p in packs if ('starter-pack' if p['id'] == 'starter' else 'pack-' + p['id']) in doc.get('tags', [])]
        if not groups:
            continue
        assert re.fullmatch(r'[a-z0-9-]+', doc['id']), 'Unsafe recipe ID'
        r = doc['recipe']
        assert r['imageURL'].startswith('https://firebasestorage.googleapis.com/'), 'Unexpected artwork host'
        assert r['ingredients'] and r['steps'] and r['title']
        for value in [r['theme'][k] for k in ['textPrimaryHex', 'accentHex', 'nutritionCardFillHex', 'ctaFillHex', 'ctaTextHex']] + [s['hex'] for s in r['theme']['backgroundGradient']]:
            assert re.fullmatch(r'#[0-9a-fA-F]{6}', value), 'Invalid theme color'
        # Publish only app catalog fields. Internal provenance and translation sidecars stay private to the source.
        public.append({'id': doc['id'], 'recipe': {k: r[k] for k in ['title', 'description', 'minutes', 'ingredients', 'steps', 'nutrition', 'theme', 'imageURL']},
                       'tags': doc['tags'], 'collections': [p['id'] for p in groups], 'collectionName': groups[0]['name']})
    public.sort(key=lambda d: d['recipe']['title'].casefold())
    if only:
        public = [doc for doc in public if doc['id'] == only]
        assert public, f'Recipe not found in active catalog: {only}'
        packs = [p for p in packs if any(p['id'] in doc['collections'] for doc in public)]
    assets = ROOT / 'assets/recipes'
    assets.mkdir(parents=True, exist_ok=True)

    def artwork(doc):
        # URL fingerprints refresh replaced art without downloading unchanged images.
        key = hashlib.sha256(doc['recipe']['imageURL'].encode()).hexdigest()[:10]
        name = f"{doc['id']}-{key}.webp"
        path = assets / name
        if not path.exists():
            im = Image.open(io.BytesIO(get(doc['recipe']['imageURL']))).convert('RGBA')
            im.thumbnail((768, 768), Image.Resampling.LANCZOS)
            im.save(path, 'WEBP', quality=88, method=6)
        doc['image'] = '/assets/recipes/' + name

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(artwork, public))
    recipes_dir = ROOT / 'recipes'
    recipes_dir.mkdir(exist_ok=True)
    for doc in public:
        related = sorted([d for d in public if d['id'] != doc['id']], key=lambda d: (not bool(set(d['collections']) & set(doc['collections'])), d['recipe']['title']))[:3]
        path = recipes_dir / doc['id']
        path.mkdir(exist_ok=True)
        (path / 'index.html').write_text(detail(doc, related))
    buttons = '<button type="button" data-filter="all" aria-pressed="true">All recipes</button>' + ''.join(f'<button type="button" data-filter="{E(p["id"])}" aria-pressed="false">{E("Everyday" if p["id"] == "starter" else p["name"])}</button>' for p in packs)
    index = head('Recipes for the everyday', 'Find something delicious to make. Explore every recipe from Ryce, with ingredients, simple steps, and a little inspiration for dinner.', '/recipes/') + f'''
<body class="recipe-index"><a class="skip-link" href="#main">Skip to recipes</a><header class="index-nav"><a class="wordmark" href="/" aria-label="Ryce home">ryce</a><nav aria-label="Main navigation"><a href="/recipes/" aria-current="page">Recipes</a><a href="/ryce-story/">Our story</a><a href="{STORE}">Get the app <span aria-hidden="true">↗</span></a></nav></header><main id="main"><section class="index-intro"><p class="eyebrow">A little inspiration for your table</p><h1>What sounds<br><em>good today?</em></h1><p>Good food, a few ingredients, and something to look forward to.<br>Find your next favourite recipe.</p></section><section class="recipe-collection" aria-label="Recipe collection"><div class="collection-tools"><div class="filters" role="group" aria-label="Filter by collection">{buttons}</div><label class="search-box"><span class="visually-hidden">Search recipes or ingredients</span><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg><input type="search" id="recipe-search" placeholder="A dish, an ingredient…" autocomplete="off"></label></div><div class="collection-summary"><p id="recipe-count" role="status">{len(public)} recipes to make your own</p><label>Sort by <select id="recipe-sort"><option value="name">Name, A–Z</option><option value="quick">Quickest first</option></select></label></div><div class="recipe-grid" id="recipe-grid">{''.join(card(d) for d in public)}</div><div class="empty-state" hidden><h2>Something else in mind?</h2><p>Try another ingredient or explore all recipes.</p><button type="button" id="clear-search">Show all recipes</button></div></section><aside class="index-download app-download"><p class="eyebrow">Your recipes. Your rhythm.</p><h2>Make room for good food.</h2><p>Bring your favourites to the table with Ryce.</p>{badge()}</aside></main>{footer()}</body></html>'''
    (recipes_dir / 'index.html').write_text(index)
    snapshot = {'source': 'Firebase public catalog', 'project': 'ryce-f10a2', 'recipeCount': len(public), 'collections': [{'id': p['id'], 'name': p['name']} for p in packs], 'recipes': public}
    (recipes_dir / 'catalog.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n')
    sitemap = ROOT / 'sitemap.xml'
    ns = 'http://www.sitemaps.org/schemas/sitemap/0.9'
    ET.register_namespace('', ns)
    tree = ET.parse(sitemap)
    for node in list(tree.getroot()):
        loc = node.find('{' + ns + '}loc')
        if loc is not None and loc.text.startswith(BASE + '/recipes/'):
            tree.getroot().remove(node)
    for path in ['/recipes/'] + ['/recipes/' + d['id'] + '/' for d in public]:
        node = ET.SubElement(tree.getroot(), '{' + ns + '}url')
        ET.SubElement(node, '{' + ns + '}loc').text = BASE + path
    tree.write(sitemap, encoding='utf-8', xml_declaration=True)
    print(f'Built {len(public)} recipe pages across {len(packs)} active collections.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', help='Build one recipe first, e.g. pesto-gnocchi')
    build(parser.parse_args().only)
