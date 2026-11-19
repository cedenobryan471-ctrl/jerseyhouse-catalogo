"""Carga de ropa deportiva / gym (fuente FUENTE_D) por tandas, sin IA. Nada del proveedor llega al catálogo:
el nombre se arma solo con palabras de este archivo; fotos con letras chinas se descartan.

El título público se arma SOLO con palabras de este archivo: equipo (traducido del chino con el
diccionario TEAMS), temporada, local/visita y manga larga. Ningún texto del proveedor llega al
catálogo; fotos con letras chinas se descartan (los números sí se permiten).
"""
import json, os, re, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, 'scripts')
from footwear_import import Site, download, save, opaque, read, SIZE_BUDGET, TERMS, MAX_PHOTOS
from photo_policy import review_image, same_photo
from casual_photos import text_marks
from photo_candidates import album_originals, seller_cover
from sports_import import collect, album_raw
from identities import identity, slug
from retro_teams import TEAMS, SKIP, EXTRA

PILOT = os.environ.get('GYM_PILOT') == 'true'
BATCH = int(os.environ.get('GYM_BATCH', '80'))
SCALE = ['XS', 'S', 'M', 'L', 'XL', '2XL', '3XL', '4XL']
COLORS = [('negro', r'黑'), ('blanco', r'白'), ('gris', r'灰'), ('celeste', r'浅蓝|天蓝|浅兰|湖兰|湖蓝'), ('azul', r'蓝|兰'), ('rojo', r'红'),
          ('verde', r'绿'), ('rosado', r'粉'), ('morado', r'紫'), ('amarillo', r'黄'), ('naranja', r'橙'), ('dorado', r'金')]
KITS = [('Tercera', r'第三|三客'), ('Alterna', r'第二客|二客'), ('Portero', r'门将|守门员'), ('Entrenamiento', r'训练'),
        ('Visita', r'客'), ('Local', r'主')]
TEAM_RX = sorted(TEAMS, key=len, reverse=True)


SIZE_SCALE = ['XS', 'S', 'M', 'L', 'XL', '2XL', '3XL', '4XL']


def sizes_of(raw):
    m = re.search(r'(?<![A-Za-z0-9])(XS|S|M|L|XL|[2-4]XL)\s*[-~～]\s*([2-4]XL|XL|S|M|L)(?![A-Za-z])', raw, re.I)
    if m:
        a, b = SIZE_SCALE.index(m.group(1).upper()), SIZE_SCALE.index(m.group(2).upper())
        if a <= b: return SIZE_SCALE[a:b + 1]
    found = [x for x in SIZE_SCALE if re.search(r'(?<![A-Z0-9])' + x + r'(?![A-Z])', raw.upper())]
    return found or ['Consultar talla']


def garment(ctx, raw):
    t = ctx + ' ' + raw
    women = '女' in ctx
    if '未分类' in ctx or re.search(r'尺码表|尺寸表', t): return None
    if '+' in raw or re.search(r'上衣\+|套装', t): return 'conjuntos', 'Conjunto deportivo'
    if re.search(r'瑜伽', t): return 'pantalones', 'Legging de yoga'
    if re.search(r'外套', t): return 'chaquetas', 'Chaqueta deportiva'
    if re.search(r'连帽', t): return 'buzos', 'Sudadera deportiva con capucha'
    if re.search(r'polo', t, re.I): return 'camisetas', 'Polo deportivo'
    if re.search(r'背心', t): return 'camisetas', 'Top deportivo' if women else 'Esqueleto deportivo'
    if re.search(r'紧身中裤|打底中裤', t): return 'shorts', 'Licra corta'
    if re.search(r'中裤|短裤|五分|三分', t): return 'shorts', 'Short deportivo' if women else 'Pantaloneta deportiva'
    if re.search(r'紧身长裤|紧身裤', t): return 'pantalones', 'Legging deportivo' if women else 'Licra larga deportiva'
    if re.search(r'长裤', t): return 'pantalones', 'Pantalón deportivo'
    if re.search(r'紧身衣', t): return 'camisetas', 'Camiseta térmica manga larga'
    if re.search(r'长袖', t): return 'camisetas', 'Camiseta deportiva manga larga'
    if re.search(r'上衣', t): return 'camisetas', 'Blusa deportiva' if women else 'Camiseta deportiva'
    if re.search(r'短袖', t): return 'camisetas', 'Camiseta deportiva'
    return None


def build(raw, ctx=''):
    kind = garment(ctx, raw)
    if not kind: return None
    cat, label = kind
    women = '女' in ctx
    extra = 'afelpada' if '加绒' in raw else 'tela fresca' if re.search(r'冰感|冰丝', raw) else 'ultra suave' if '裸感' in raw else ''
    colors = [c for c, rx in COLORS if re.search(rx, raw)][:2]
    parts = [label, 'Mujer' if women else 'Hombre'] + ([extra] if extra else [])
    return dict(title=' '.join(parts), team=None, league=None, season=None, cat=cat, kids=False, women=women,
                sizes=sizes_of(raw), colors=colors)


def clean_photo(im):
    chinese, _ = text_marks(im)
    return chinese == 0


CATS = {'camisetas': 'Camisetas y tops', 'conjuntos': 'Conjuntos', 'chaquetas': 'Chaquetas', 'buzos': 'Buzos', 'pantalones': 'Licras y pantalones', 'shorts': 'Shorts'}
SPECIAL = {'Selecciones': 'selecciones', 'NBA': 'nba'}


def main():
    urls = [u.strip() for u in (os.environ.get('FUENTE_D'),) if u and u.strip()]
    from casual_photos import _ocr
    _ocr()  # si el lector de texto no carga, se detiene aquí
    items = read('catalog.json', []); seen = set(read('gym-seen.json', []))
    extras = Path('gallery-extra/images'); extras.mkdir(parents=True, exist_ok=True)
    counter = max(int(p['id']) for p in items) + 1; size_now = sum(p.stat().st_size for p in Path('images').glob('*.webp'))
    report = {'added': 0, 'skipped': {}, 'by_category': {}, 'remaining': 0}
    pilot_dir = Path('gym-pilot')
    states = read('estado.json', {})
    # Solo se compara con lo que ya estaba antes de esta carga (desde el id 23227 es de esta fuente).
    existing = {p['title'].lower() for p in items if int(p['id']) < 23227 and states.get(p['id']) != 'hidden'}
    todo = []  # (site, key, entry)
    for url in urls:
        if len(todo) >= BATCH and not PILOT: break
        site = Site(url)
        albums = collect(site, 'gym')
        pending = [(site, opaque(site.host, 'gym', a[0]), a) for a in albums if opaque(site.host, 'gym', a[0]) not in seen]
        report.setdefault('albums', []).append(len(albums))
        todo += pending[::max(1, len(pending) // 20)][:20] if PILOT else pending
    if not todo:
        Path('gym-result.json').write_text(json.dumps(report)); return
    batch = todo[:20] if PILOT else todo[:BATCH]

    def work(task):
        site, k, entry = task
        aid, aurl, ctx = entry
        try:
            page = site.page(aurl); raw = album_raw(page)
            data = build(raw, ctx)
            if not data: return task, None, 'no_reconocido'
            urls = album_originals(page, aurl)[:10]; cover = seller_cover(page, aurl)
            if cover and cover in urls: urls.remove(cover)
            images = download(site, ([cover] if cover else []) + urls, aurl)
            if not images: return task, None, 'sin_fotos'
            approved = []
            for i, im in enumerate(images[:10]):
                if review_image(im, TERMS)[0] == 'rejected' or any(same_photo(im, images[j]) for j in approved): continue
                approved.append(i)
            clean = []
            for i in approved:
                if clean_photo(images[i]): clean.append(i)
                if len(clean) >= MAX_PHOTOS: break
            if not clean: return task, None, 'fotos_con_chino'
            data['images'] = []
            for i in clean:
                im = images[i].copy(); im.thumbnail((600, 600)); data['images'].append(im)
            return task, data, 'ok'
        except Exception as e:
            return task, None, 'error_' + type(e).__name__

    with ThreadPoolExecutor(max_workers=6) as pool: results = list(pool.map(work, batch))
    for task, data, status in results:
        k = task[1]
        if status != 'ok':
            report['skipped'][status] = report['skipped'].get(status, 0) + 1
            if not status.startswith('error'): seen.add(k)
            continue
        if size_now > SIZE_BUDGET: report['status'] = 'size_budget_reached'; break
        ident = str(counter); counter += 1
        cat = data['cat']; report['by_category'][cat] = report['by_category'].get(cat, 0) + 1
        selected = list(range(len(data['images'])))
        if PILOT:
            pilot_dir.mkdir(exist_ok=True); im = data['images'][0].copy(); im.thumbnail((300, 300))
            im.save(pilot_dir / f'{ident}.webp', 'WEBP', quality=60)
            (pilot_dir / f'{ident}.json').write_text(json.dumps({k2: data[k2] for k2 in ('title', 'cat', 'sizes', 'colors')} | {'photos': len(selected)}, ensure_ascii=False))
        else:
            keys = save(ident, data['images'], selected, extras)
            items.insert(0, {'id': ident, 'slug': ident, 'title': data['title'], 'brand': 'Otras marcas',
                'categorySlug': cat, 'category': CATS[cat], 'sizes': data['sizes'], 'audiences': ['mujer'] if data['women'] else ['hombre'],
                'colors': data['colors'], 'price': None, 'status': 'active', 'cover': f'{ident}.webp', 'sectionSlug': 'gym', 'gallery': keys})
            size_now += (Path('images') / f'{ident}.webp').stat().st_size
            seen.add(k)
        report['added'] += 1
    report['remaining'] = 0 if PILOT else max(0, len(todo) - len(batch))
    report.setdefault('status', 'ok')
    if not PILOT:
        Path('catalog.json').write_text(json.dumps(items, ensure_ascii=False, separators=(',', ':')))
        Path('gym-seen.json').write_text(json.dumps(sorted(seen)))
    Path('gym-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    try: main()
    except Exception as e:
        Path('gym-result.json').write_text(json.dumps({'fatal': type(e).__name__, 'remaining': 0}))
