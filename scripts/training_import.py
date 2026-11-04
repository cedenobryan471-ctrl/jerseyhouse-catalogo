"""Carga de ropa de entrenamiento de equipos (fuentes FUENTE_A y FUENTE_B) por tandas, sin IA.

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

PILOT = os.environ.get('TRAINING_PILOT') == 'true'
BATCH = int(os.environ.get('TRAINING_BATCH', '80'))
SCALE = ['XS', 'S', 'M', 'L', 'XL', '2XL', '3XL', '4XL']
COLORS = [('negro', r'黑'), ('blanco', r'白'), ('gris', r'灰'), ('celeste', r'浅蓝|天蓝|浅兰|湖兰|湖蓝'), ('azul', r'蓝|兰'), ('rojo', r'红'),
          ('verde', r'绿'), ('rosado', r'粉'), ('morado', r'紫'), ('amarillo', r'黄'), ('naranja', r'橙'), ('dorado', r'金')]
KITS = [('Tercera', r'第三|三客'), ('Alterna', r'第二客|二客'), ('Portero', r'门将|守门员'), ('Entrenamiento', r'训练'),
        ('Visita', r'客'), ('Local', r'主')]
TEAM_RX = sorted(TEAMS, key=len, reverse=True)


def team_of(raw):
    eng = raw.split('-')[-1].strip() if '-' in raw else ''
    if eng and re.search(r'[A-Za-z]{3}', eng):
        ident = identity(eng)
        if ident and ident[0]: return ident
    for zh in TEAM_RX:
        if zh in raw:
            team = TEAMS[zh]
            ident = EXTRA.get(team) or identity(team)
            if ident and ident[0]: return ident
    return None


def season_of(raw):
    for m in re.finditer(r'(?<!\d)(\d{2})(\d{2})(?!\d)', raw.split('#', 1)[-1]):
        if int(m.group(2)) == int(m.group(1)) + 1: return f'20{m.group(1)}/{m.group(2)}'
    return None


def garment(ctx, raw):
    t = ctx + ' ' + raw
    if re.search(r'尺寸|尺码|NBA|光板', t): return None
    hood = bool(re.search(r'帽子|连帽', t))
    if re.search(r'POLO', raw, re.I): return 'conjuntos', 'Conjunto polo'
    if re.search(r'棉衣', t): return 'chaquetas', 'Chaqueta acolchada'
    if re.search(r'风衣', t): return 'chaquetas', 'Rompevientos'
    if re.search(r'背心', t): return 'conjuntos', 'Conjunto de esqueleto'
    if re.search(r'短袖', t): return 'conjuntos', 'Conjunto de entrenamiento manga corta'
    if re.search(r'半拉', t): return 'conjuntos', 'Conjunto de entrenamiento medio cierre' + (' con gorro' if hood else '')
    if re.search(r'长拉', t): return 'conjuntos', 'Conjunto de entrenamiento cierre completo' + (' con gorro' if hood else '')
    if re.search(r'夹克|jacket', t, re.I): return 'chaquetas', 'Chaqueta de entrenamiento' + (' con gorro' if hood else '')
    if re.search(r'训练|suit', t, re.I): return 'conjuntos', 'Conjunto de entrenamiento'
    return None


def build(raw, ctx=''):
    kind = garment(ctx, raw)
    if not kind: return None
    cat, label = kind
    ident = team_of(raw)
    if not ident: return None
    name, league = ident
    kids = bool(re.search(r'童装|kids|儿童', ctx + raw, re.I))
    season = season_of(raw)
    retro = bool(re.search(r'复古', raw))
    parts = [label, name] + (['Retro'] if retro else []) + ([season] if season else []) + (['(Niño)'] if kids else [])
    colors = [c for c, rx in COLORS if re.search(rx, re.sub(r'（.*?）|\(.*?\)', '', raw))][:2] or \
             [c for c, rx in COLORS if re.search(rx, raw)][:1]
    if colors: parts.insert(len(parts) - (1 if kids else 0), colors[0])
    return dict(title=' '.join(parts), team=name, league=league, season=season, cat=cat, kids=kids,
                sizes=['S', 'M', 'L', 'XL', '2XL'] if not kids else ['Consultar talla'], colors=colors)


def clean_photo(im):
    chinese, _ = text_marks(im)
    return chinese == 0


CATS = {'camisetas': 'Camisetas', 'conjuntos': 'Conjuntos', 'chaquetas': 'Chaquetas'}
SPECIAL = {'Selecciones': 'selecciones', 'NBA': 'nba'}


def main():
    urls = [u.strip() for u in (os.environ.get('FUENTE_A'), os.environ.get('FUENTE_B')) if u and u.strip()]
    from casual_photos import _ocr
    _ocr()  # si el lector de texto no carga, se detiene aquí
    items = read('catalog.json', []); seen = set(read('training-seen.json', []))
    extras = Path('gallery-extra/images'); extras.mkdir(parents=True, exist_ok=True)
    counter = max(int(p['id']) for p in items) + 1; size_now = sum(p.stat().st_size for p in Path('images').glob('*.webp'))
    report = {'added': 0, 'skipped': {}, 'by_category': {}, 'remaining': 0}
    pilot_dir = Path('training-pilot')
    states = read('estado.json', {})
    # Solo se compara con lo que ya estaba antes de esta carga (desde el id 23227 es de esta fuente).
    existing = {p['title'].lower() for p in items if int(p['id']) < 23227 and states.get(p['id']) != 'hidden'}
    todo = []  # (site, key, entry)
    for url in urls:
        if len(todo) >= BATCH and not PILOT: break
        site = Site(url)
        albums = collect(site, 'training')
        pending = [(site, opaque(site.host, 'training', a[0]), a) for a in albums if opaque(site.host, 'training', a[0]) not in seen]
        report.setdefault('albums', []).append(len(albums))
        todo += pending[::max(1, len(pending) // 20)][:20] if PILOT else pending
    if not todo:
        Path('training-result.json').write_text(json.dumps(report)); return
    batch = todo[:20] if PILOT else todo[:BATCH]

    def work(task):
        site, k, entry = task
        aid, aurl, ctx = entry
        try:
            page = site.page(aurl); raw = album_raw(page)
            data = build(raw, ctx)
            if not data: return task, None, 'no_reconocido'
            if data['title'].lower() in existing: return task, None, 'ya_en_tienda'
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
        if status == 'ok' and data['title'].lower() in existing: status = 'ya_en_tienda'
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
            (pilot_dir / f'{ident}.json').write_text(json.dumps({k2: data[k2] for k2 in ('title', 'team', 'league', 'cat', 'colors')} | {'photos': len(selected)}, ensure_ascii=False))
        else:
            keys = save(ident, data['images'], selected, extras)
            items.insert(0, {'id': ident, 'slug': ident, 'title': data['title'], 'brand': 'Otras marcas', 'team': data['team'],
                'teamSlug': slug(data['team']), 'league': data['league'], 'leagueSlug': slug(data['league']),
                'categorySlug': cat, 'category': CATS[cat], 'sizes': data['sizes'], 'season': data['season'],
                'version': 'entrenamiento', 'audiences': ['nino'] if data['kids'] else ['hombre'], 'colors': data['colors'],
                'price': None, 'status': 'active', 'cover': f'{ident}.webp',
                'sectionSlug': SPECIAL.get(data['league'], 'futbol'), 'gallery': keys})
            size_now += (Path('images') / f'{ident}.webp').stat().st_size
            seen.add(k)
        report['added'] += 1
    report['remaining'] = 0 if PILOT else max(0, len(todo) - len(batch))
    report.setdefault('status', 'ok')
    if not PILOT:
        Path('catalog.json').write_text(json.dumps(items, ensure_ascii=False, separators=(',', ':')))
        Path('training-seen.json').write_text(json.dumps(sorted(seen)))
    Path('training-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    try: main()
    except Exception as e:
        Path('training-result.json').write_text(json.dumps({'fatal': type(e).__name__, 'remaining': 0}))
