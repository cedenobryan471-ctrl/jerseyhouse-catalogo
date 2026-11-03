"""Carga de camisetas retro (fuente FUENTE_RETRO) por tandas, sin IA.

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
from retro_teams import TEAMS

PILOT = os.environ.get('RETRO_PILOT') == 'true'
BATCH = int(os.environ.get('RETRO_BATCH', '80'))
SCALE = ['XS', 'S', 'M', 'L', 'XL', '2XL', '3XL', '4XL']
COLORS = [('negro', r'黑'), ('blanco', r'白'), ('gris', r'灰'), ('celeste', r'浅蓝|天蓝'), ('azul', r'蓝'), ('rojo', r'红'),
          ('verde', r'绿'), ('rosado', r'粉'), ('morado', r'紫'), ('amarillo', r'黄'), ('naranja', r'橙'), ('dorado', r'金')]
KITS = [('Tercera', r'第三|三客'), ('Alterna', r'第二客|二客'), ('Portero', r'门将|守门员'), ('Entrenamiento', r'训练'),
        ('Visita', r'客'), ('Local', r'主')]
TEAM_RX = sorted(TEAMS, key=len, reverse=True)


def team_of(raw):
    for zh in TEAM_RX:
        if zh in raw: return TEAMS[zh]
    return None


def season_of(raw):
    m = re.search(r'(?<!\d)((?:19|20)\d{2})(?:\s*[/-]\s*((?:19|20)?\d{2}))?(?!\d)', raw)
    if not m: return None
    return m.group(1) + ('/' + m.group(2)[-2:] if m.group(2) else '')


def sizes_of(raw):
    m = re.search(r'剩\s*([SMLX0-9 ]+)', raw, re.I)
    if m:
        found = [s for s in SCALE if re.search(r'(?<![A-Z0-9])' + s + r'(?![A-Z])', m.group(1).upper().replace(' ', '  '))]
        if not found:  # "SM" pegado = S y M
            found = [s for s in SCALE if s in m.group(1).upper()]
        if found: return found
    return ['S', 'M', 'L', 'XL', '2XL']


def build(raw):
    team = team_of(raw)
    if not team: return None
    ident = identity(team)
    if not ident or not ident[0]: return None
    name, league = ident
    season = season_of(raw)
    kit = next((k for k, rx in KITS if re.search(rx, raw)), None)
    long = bool(re.search(r'长袖', raw))
    special = bool(re.search(r'纪念|周年', raw))
    ucl = bool(re.search(r'欧冠', raw))
    parts = ['Camiseta', name, 'Retro'] + ([kit] if kit else []) + (['Champions'] if ucl else []) + \
            (['Edición especial'] if special else []) + ([season] if season else []) + (['Manga larga'] if long else [])
    colors = [c for c, rx in COLORS if re.search(rx, raw)][:2]
    return dict(title=' '.join(parts), team=name, league=league, season=season, sizes=sizes_of(raw), colors=colors)


def clean_photo(im):
    chinese, _ = text_marks(im)
    return chinese == 0


def main():
    url = (os.environ.get('FUENTE_RETRO') or '').strip()
    from casual_photos import _ocr
    _ocr()  # si el lector de texto no carga, se detiene aquí
    items = read('catalog.json', []); seen = set(read('retro-seen.json', []))
    extras = Path('gallery-extra/images'); extras.mkdir(parents=True, exist_ok=True)
    counter = max(int(p['id']) for p in items) + 1; size_now = sum(p.stat().st_size for p in Path('images').glob('*.webp'))
    report = {'added': 0, 'skipped': {}, 'by_section': {}}
    pilot_dir = Path('retro-pilot')
    if not url:
        report['status'] = 'sin_fuente'; report['remaining'] = 0
        Path('retro-result.json').write_text(json.dumps(report)); return
    site = Site(url)
    albums = collect(site, 'retro')
    key = lambda a: opaque(site.host, 'retro', a[0])
    pending = [a for a in albums if key(a) not in seen]
    states = read('estado.json', {})
    def kit_word(t):
        return next((k for k, _ in KITS if re.search(r'\b' + k + r'\b', t)), '')
    existing = {(p.get('teamSlug'), p.get('season'), kit_word(p['title']), 'Manga larga' in p['title'])
                for p in items if p.get('version') == 'retro' and states.get(p['id']) != 'hidden'}
    report['albums'] = len(albums)
    batch = pending[::max(1, len(pending) // 20)][:20] if PILOT else pending[:BATCH]

    def work(entry):
        aid, aurl, ctx = entry
        try:
            page = site.page(aurl); raw = album_raw(page)
            data = build(raw)
            if not data: return entry, None, 'equipo_desconocido'
            urls = album_originals(page, aurl)[:10]; cover = seller_cover(page, aurl)
            if cover and cover in urls: urls.remove(cover)
            images = download(site, ([cover] if cover else []) + urls, aurl)
            if not images: return entry, None, 'sin_fotos'
            approved = []
            for i, im in enumerate(images[:10]):
                if review_image(im, TERMS)[0] == 'rejected' or any(same_photo(im, images[j]) for j in approved): continue
                approved.append(i)
            clean = []
            for i in approved:
                if clean_photo(images[i]): clean.append(i)
                if len(clean) >= MAX_PHOTOS: break
            if not clean: return entry, None, 'fotos_con_chino'
            data['images'] = []
            for i in clean:
                im = images[i].copy(); im.thumbnail((600, 600)); data['images'].append(im)
            return entry, data, 'ok'
        except Exception as e:
            return entry, None, 'error_' + type(e).__name__

    with ThreadPoolExecutor(max_workers=6) as pool: results = list(pool.map(work, batch))
    for entry, data, status in results:
        if status != 'ok':
            report['skipped'][status] = report['skipped'].get(status, 0) + 1
            if not status.startswith('error'): seen.add(key(entry))
            continue
        if size_now > SIZE_BUDGET: report['status'] = 'size_budget_reached'; break
        dup = (slug(data['team']), data['season'], kit_word(data['title']), 'Manga larga' in data['title'])
        if dup in existing:
            report['skipped']['ya_en_tienda'] = report['skipped'].get('ya_en_tienda', 0) + 1; seen.add(key(entry)); continue
        existing.add(dup)
        ident = str(counter); counter += 1
        section = 'selecciones' if data['league'] == 'Selecciones' else 'futbol'
        report['by_section'][section] = report['by_section'].get(section, 0) + 1
        selected = list(range(len(data['images'])))
        if PILOT:
            pilot_dir.mkdir(exist_ok=True); im = data['images'][0].copy(); im.thumbnail((300, 300))
            im.save(pilot_dir / f'{ident}.webp', 'WEBP', quality=60)
            (pilot_dir / f'{ident}.json').write_text(json.dumps({k: data[k] for k in ('title', 'team', 'league', 'sizes', 'colors')} | {'photos': len(selected)}, ensure_ascii=False))
        else:
            keys = save(ident, data['images'], selected, extras)
            items.insert(0, {'id': ident, 'slug': ident, 'title': data['title'], 'brand': 'Otras marcas', 'team': data['team'],
                'teamSlug': slug(data['team']), 'league': data['league'], 'leagueSlug': slug(data['league']),
                'categorySlug': 'camisetas', 'category': 'Camisetas', 'sizes': data['sizes'], 'season': data['season'],
                'version': 'retro', 'audiences': ['hombre'], 'colors': data['colors'], 'price': None, 'status': 'active',
                'cover': f'{ident}.webp', 'sectionSlug': section, 'gallery': keys})
            size_now += (Path('images') / f'{ident}.webp').stat().st_size
            seen.add(key(entry))
        report['added'] += 1
    report['remaining'] = 0 if PILOT else max(0, len(pending) - len(batch))
    report.setdefault('status', 'ok')
    if not PILOT:
        Path('catalog.json').write_text(json.dumps(items, ensure_ascii=False, separators=(',', ':')))
        Path('retro-seen.json').write_text(json.dumps(sorted(seen)))
    Path('retro-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    try: main()
    except Exception as e:
        Path('retro-result.json').write_text(json.dumps({'fatal': type(e).__name__, 'remaining': 0}))
