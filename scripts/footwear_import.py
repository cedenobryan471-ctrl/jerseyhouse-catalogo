"""Carga de calzado por tandas, sin IA.

- Lee las fuentes desde el secreto FOOTWEAR_SOURCES_CONFIG; nunca guarda direcciones.
- Tipo "album": cada álbum es un producto (título del álbum, varias fotos).
- Tipo "category": cada categoría es un producto (nombre de la categoría = modelo),
  y sus álbumes de una sola foto forman la galería.
- Las fotos se revisan con OCR (photo_policy) y se aceptan horizontales (los tenis lo son).
- El avance se guarda con claves opacas en footwear-progress.json.
"""
import hashlib, io, json, os, re, sys, warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlencode, parse_qsl, urlunparse

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageOps

sys.path.insert(0, 'scripts')
from footwear_rules import translate, brand_of, footwear_type, footwear_group, footwear_sole, footwear_collar, shoe_sizes, SIZE_RANGE
from photo_candidates import album_originals, seller_cover
from photo_policy import review_image, same_photo, background_score

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'}
CONFIG = json.loads(os.environ.get('CATALOG_CONFIG') or '{}')
TERMS = [t for t in CONFIG.get('blocked_terms', []) if t]
BATCH = int(os.environ.get('FOOTWEAR_BATCH', '60'))
PILOT = os.environ.get('FOOTWEAR_PILOT') == 'true'
MAX_PHOTOS = 4                      # portada + 3 de galería: cuida el límite de 1 GB
SIZE_BUDGET = 900_000_000           # nunca acercarse al límite de GitHub Pages
warnings.filterwarnings('ignore')


ALIASES = [(r'^\s*oma\b', 'Joma'), (r'\bmax\s?(\d{2,3})\b', 'Nike Air Max \\1'), (r'\bfree\s?metcon\s?(\d)', 'Nike Free Metcon \\1'),
           (r'^\s*sb\b', 'Nike SB'), (r'^\s*on\b(?!\s+running)', 'On Running'), (r'^\s*cloud', 'On Running Cloud'), (r'\bhoka\b', 'Hoka')]


def read(path, fallback):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else fallback


def opaque(*parts):
    return hashlib.sha256('|'.join(parts).encode()).hexdigest()[:16]


class Site:
    def __init__(self, url):
        o = urlparse(url)
        self.url, self.host, self.root = url, o.netloc, f'{o.scheme}://{o.netloc}'
        self.verify = True
        self.names = {}
        self.store_words = set()
        # Si la fuente tiene candado, la clave viaja solo en la cookie de esa página (nunca se guarda).
        self.cookies = {'indexlockcode': os.environ['CLAVE'].strip()} if os.environ.get('CLAVE', '').strip() else {}

    def learn_store(self, page):
        # Palabras del nombre de la tienda del proveedor: nunca pueden aparecer en un título.
        texts = [page.title.get_text(' ', strip=True) if page.title else '']
        texts += [h.get_text(' ', strip=True) for h in page.select('h1, .showheader__nickname, .showheader__headerTop')]
        for t in texts:
            for part in re.split(r'[|｜]', t):
                part = translate(part).strip()
                if part and not re.search(r'catalog', part, re.I): self.store_words.add(part.lower())

    def get(self, url, referer=None):
        headers = dict(UA)
        if referer: headers['Referer'] = referer
        for attempt in range(3):
            try:
                r = requests.get(url, headers=headers, timeout=(8, 25), verify=self.verify if urlparse(url).netloc == self.host else True, cookies=self.cookies if urlparse(url).netloc == self.host else None)
                r.raise_for_status(); return r
            except requests.exceptions.SSLError:
                # Solo para leer el HTML público del catálogo; las fotos siempre se verifican.
                if urlparse(url).netloc == self.host and self.verify: self.verify = False; continue
                raise
            except Exception:
                if attempt == 2: raise

    def page(self, url):
        return BeautifulSoup(self.get(url).text, 'html.parser')


def with_page(url, n):
    o = urlparse(url); q = dict(parse_qsl(o.query)); q['page'] = str(n)
    return urlunparse(o._replace(query=urlencode(q)))


def links(page, base, host, pattern):
    out = {}
    for a in page.select('a[href]'):
        u = urljoin(base, a['href']).split('#')[0]; p = urlparse(u)
        m = re.search(pattern, p.path)
        if p.netloc == host and m and m.group(1) not in out:
            out[m.group(1)] = (u, a)
    return out


def max_page(page):
    nums = [int(n) for a in page.select('a[href]') for n in re.findall(r'[?&]page=(\d+)', a['href'])]
    for el in page.select('input[max]'):
        try: nums.append(int(el.get('max')))
        except Exception: pass
    nums += [int(n) for n in re.findall(r'共\s*(\d+)\s*页', page.get_text(' '))]
    return min(max(nums), 200) if nums else 1


def shoe_title(raw):
    t = translate(raw)
    t = re.sub(r'\bnb\s?(\d{3,4})', r'New Balance \1', t, flags=re.I)
    t = re.sub(r'\bnb\b', 'New Balance', t, flags=re.I)
    t = re.sub(r'\baj\s?(\d{1,2})\b', r'Air Jordan \1', t, flags=re.I)
    for pattern, repl in ALIASES:
        t = re.sub(pattern, repl, t, flags=re.I)
    for term in TERMS:
        t = re.sub(re.escape(term), ' ', t, flags=re.I)
    t = re.sub(r'\S*/albums/\S*|\?uid=\d+|https?://\S+|\b[\w-]+\.(?:com|cn|net|org|shop|co)\S*|\S+@\S+', ' ', t, flags=re.I)
    t = SIZE_RANGE.sub(' ', t)
    t = re.sub(r'\b(?:size|sizes|talla|tallas|eur?|us)\s*[:：]?', ' ', t, flags=re.I)
    t = re.sub(r'\d{5,}|[（）()【】\[\]《》“”"#*|]+|\.(?:jpe?g|png)\b', ' ', t, flags=re.I)
    t = re.sub(r'(?<![\w])[A-Za-z](?![\w])', ' ', t)
    words, seen = [], set()
    for w in t.split():
        k = w.lower().strip('.,;:-_')
        if not k or k in seen: continue
        seen.add(k); words.append(w.strip('.,;:-_'))
    t = ' '.join(words)
    # La marca va primero.
    brand = brand_of(t)
    if brand != 'Otras marcas':
        t = re.sub(r'(?<![a-z])' + re.escape(brand) + r'(?![a-z])', ' ', t, flags=re.I)
        t = brand + ' ' + re.sub(r'\s+', ' ', t).strip()
    t = re.sub(r'\s+', ' ', t).strip(' -_,;.')
    if brand != 'Otras marcas':
        return t if len(t) > len(brand) + 2 else None
    return t if re.search(r'[A-Za-z]{3}', t) else None


def download(site, urls, referer):
    images = []
    for url in urls:
        try:
            r = site.get(url, referer=referer)
            with Image.open(io.BytesIO(r.content)) as im:
                im = ImageOps.exif_transpose(im).convert('RGB')
            if min(im.size) >= 200: images.append(im)
        except Exception:
            continue
    return images


def choose(images, seller_index=None):
    approved = []
    for i, im in enumerate(images):
        outcome, _ = review_image(im, TERMS)
        if outcome == 'rejected': continue
        if any(same_photo(im, images[j]) for j in approved): continue
        approved.append(i)
    if not approved: return []
    cover = seller_index if seller_index in approved else max(approved, key=lambda i: background_score(images[i]))
    return [cover] + [i for i in approved if i != cover][:MAX_PHOTOS - 1]


def ahash(im):
    g = im.convert('L').resize((8, 8)); px = list(g.getdata()); m = sum(px) / 64
    return ''.join('1' if v > m else '0' for v in px)


def save(ident, images, selected, extras):
    keys = []
    for n, i in enumerate(selected):
        im = images[i].copy()
        if n == 0:
            im.thumbnail((500, 500), Image.Resampling.LANCZOS); im.save(Path('images') / f'{ident}.webp', 'WEBP', quality=70)
        else:
            im.thumbnail((400, 400), Image.Resampling.LANCZOS); name = f'{ident}-{n}.webp'
            im.save(extras / name, 'WEBP', quality=45); keys.append(name)
    return keys


def product(ident, title, raw, keys):
    group = footwear_group(title + ' ' + raw)
    extra = {'sole': footwear_sole(title + ' ' + raw), 'collar': footwear_collar(title + ' ' + raw)} if group in ('tacos', 'futbol') else {}
    return {**extra, 'title': title, 'brand': brand_of(title), 'footwearType': footwear_group(title + ' ' + raw), 'id': ident, 'slug': ident,
            'team': None, 'teamSlug': None, 'league': None, 'leagueSlug': None, 'categorySlug': 'calzado', 'category': 'Calzado',
            'sizes': shoe_sizes(raw), 'season': None, 'version': 'fan', 'audiences': ['hombre'], 'colors': [], 'price': None,
            'status': 'active', 'cover': f'{ident}.webp', 'sectionSlug': 'calzado', 'gallery': keys}


def album_items(site, page):
    found = links(page, site.url, site.host, r'/albums/(\d+)')
    return [('album', aid, u) for aid, (u, _) in found.items()]


def category_items(site, page):
    found = links(page, site.url, site.host, r'/categories/(\d+)')
    out = []
    for cid, (u, a) in found.items():
        name = a.get_text(' ', strip=True)
        site.names[cid] = name
        out.append(('category', cid, u))
    return out


def discover(site):
    first = site.page(site.url)
    site.learn_store(first)
    albums = album_items(site, first)
    cats = category_items(site, first)
    if albums:
        sample = site.page(albums[0][2])
        h = sample.select_one('.showalbumheader__gallerytitle') or sample.select_one('h1')
        album_titled = bool(h and re.search(r'[A-Za-z]{3}', translate(h.get_text(' ', strip=True))))
        if album_titled:
            items = list(albums)
            site.pages_total = max_page(first); site.pages_read = 1
            for n in range(2, site.pages_total + 1):
                try:
                    known = {i[1] for i in items}
                    items += [x for x in album_items(site, site.page(with_page(site.url, n))) if x[1] not in known]; site.pages_read += 1
                except Exception: continue
            return items
    return cats


def process(site, item):
    kind, key, url = item
    page = site.page(url)
    if kind == 'album':
        h = page.select_one('.showalbumheader__gallerytitle') or page.select_one('h1')
        raw = h.get_text(' ', strip=True) if h else ''
        urls = album_originals(page, url)[:10]
        cover_url = seller_cover(page, url)
        if cover_url and cover_url in urls: urls.remove(cover_url)
        urls = ([cover_url] if cover_url else []) + urls
        images = download(site, urls, url)
        seller = 0 if cover_url and images else None
    else:
        raw = site.names.get(key, '')
        albums = album_items(site, page)[:8]
        urls = []
        for _, _, aurl in albums:
            try: urls += album_originals(site.page(aurl), aurl)[:1]
            except Exception: continue
        images = download(site, urls, url); seller = None
    title = shoe_title(raw)
    if title:
        low = title.lower()
        for w in site.store_words:
            if w and w in low: low = low.replace(w, ' ')
        title = title if low.split() == title.lower().split() else (shoe_title(low) if re.search(r'[a-z]{3}', low) else None)
    if not title: return None, 'no_title'
    if re.search(r'\bsocks?\b|calcet|medias', title, re.I): return None, 'not_shoe'
    if not images: return None, 'no_photos'
    selected = choose(images, seller)
    if not selected: return None, 'photos_rejected'
    return (title, raw, images, selected), 'ok'


def main():
    sources = json.loads(os.environ.get('FOOTWEAR_SOURCES_CONFIG') or '[]')
    items_all = read('catalog.json', []); progress = read('footwear-progress.json', {}); seen = set(read('footwear-seen.json', []))
    extras = Path('gallery-extra/images'); extras.mkdir(parents=True, exist_ok=True)
    pilot_dir = Path('footwear-pilot'); counter = max(int(p['id']) for p in items_all) + 1
    report = {'sources': [], 'added': 0}
    size_now = sum(p.stat().st_size for p in Path('images').glob('*.webp'))
    for number, source in enumerate(sources, 1):
        site = Site(source['url']); skey = opaque(source['url'])
        rep = {'source': number, 'added': 0, 'skipped': {}}
        try:
            items = discover(site)
        except Exception as e:
            rep['status'] = 'unreadable:' + type(e).__name__; report['sources'].append(rep); continue
        items = [x for x in items if opaque(site.host, x[0], x[1]) not in seen]
        rep['pages'] = [getattr(site, 'pages_read', 1), getattr(site, 'pages_total', 1)]
        rep['pending_before'] = len(items); rep['kind'] = items[0][0] if items else None
        batch = items[:10 if PILOT else BATCH]
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda it: (it, *safe_process(site, it)), batch))
        for it, data, status in results:
            if status != 'ok':
                rep['skipped'][status] = rep['skipped'].get(status, 0) + 1
                if not status.startswith('error'): seen.add(opaque(site.host, it[0], it[1]))
                continue
            if size_now > SIZE_BUDGET: rep['status'] = 'size_budget_reached'; break
            title, raw, images, selected = data
            h = opaque('img', ahash(images[selected[0]]))
            if h in seen:
                rep['skipped']['duplicate_photo'] = rep['skipped'].get('duplicate_photo', 0) + 1
                seen.add(opaque(site.host, it[0], it[1])); continue
            seen.add(h)
            ident = str(counter); counter += 1
            if PILOT:
                pilot_dir.mkdir(exist_ok=True)
                im = images[selected[0]].copy(); im.thumbnail((300, 300)); im.save(pilot_dir / f'{ident}.webp', 'WEBP', quality=60)
                (pilot_dir / f'{ident}.json').write_text(json.dumps({'title': title, 'type': footwear_type(title + ' ' + raw), 'sizes': shoe_sizes(raw), 'photos': len(selected)}, ensure_ascii=False))
            else:
                keys = save(ident, images, selected, extras)
                items_all.insert(0, product(ident, title, raw, keys))
                size_now += (Path('images') / f'{ident}.webp').stat().st_size
                seen.add(opaque(site.host, it[0], it[1]))
            rep['added'] += 1
        rep['pending_after'] = max(0, len(items) - len(batch)); rep.setdefault('status', 'ok')
        report['sources'].append(rep); report['added'] += rep['added']
    if not PILOT:
        for p in items_all:
            if p.get('categorySlug') == 'calzado' and int(p['id']) >= 12443:
                fixed = shoe_title(p['title'])
                if fixed: p['title'] = fixed; p['brand'] = brand_of(fixed)
        Path('catalog.json').write_text(json.dumps(items_all, ensure_ascii=False, separators=(',', ':')))
        Path('footwear-seen.json').write_text(json.dumps(sorted(seen)))
    report['remaining'] = sum(r.get('pending_after', 0) for r in report['sources'])
    report['footwear_products'] = sum(p.get('categorySlug') == 'calzado' for p in items_all)
    report['size_bytes'] = size_now
    text = json.dumps(report, ensure_ascii=False, indent=1)
    for src in sources:
        for part in urlparse(src.get('url', '')).netloc.split('.'):
            if len(part) >= 4 and part not in ('yupoo', 'www'): text = text.replace(part, '[x]')
    Path('footwear-result.json').write_text(text)
    if PILOT and pilot_dir.exists():
        for f in pilot_dir.glob('*.json'):
            t = f.read_text()
            for src in sources:
                for part in urlparse(src.get('url', '')).netloc.split('.'):
                    if len(part) >= 4 and part not in ('yupoo', 'www'): t = t.replace(part, '[x]')
            f.write_text(t)


def safe_process(site, item):
    try: return process(site, item)
    except Exception as e: return None, 'error_' + type(e).__name__


if __name__ == '__main__':
    main()
