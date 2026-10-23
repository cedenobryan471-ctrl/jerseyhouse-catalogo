"""Carga de ropa de marca (casual) por tandas, sin IA.

Privacidad al 100 %: el nombre público se arma SOLO con palabras de este archivo (prenda, marca,
colores, tallas). Ningún texto del proveedor llega al catálogo y no se guardan direcciones.
La dirección viene del secreto FUENTE_NUEVA.
Sudaderas, chaquetas, rompevientos y abrigos van con categoría chaquetas/buzos (filtro Chaquetas);
salveques y bolsos a Accesorios; el resto a Ropa casual.
"""
import json, os, re, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, 'scripts')
from footwear_import import Site, download, save, opaque, read, SIZE_BUDGET, TERMS, MAX_PHOTOS
from photo_policy import review_image, same_photo
from casual_photos import pick, has_text
from photo_candidates import album_originals, seller_cover
from sports_import import collect, album_raw

PILOT = os.environ.get('CASUAL_PILOT') == 'true'
BATCH = int(os.environ.get('CASUAL_BATCH', '80'))

BRANDS = [
    ('Adidas Originals', r'三叶草|叶草|originals|clover'), ('Adidas', r'阿迪|adidas|\bad\b'),
    ('Jordan', r'乔丹|jordan|\baj\b'), ('Nike', r'耐克|nike|\bnk'), ('The North Face', r'北面|north\s*face|\btnf\b'),
    ('Puma', r'彪马|puma'), ('Under Armour', r'安德玛|安德码|under\s*armou?r|\bua\b'), ('New Balance', r'新百伦|new\s*balance|\bnb\b'),
    ("Arc'teryx", r'始祖鸟|arc.?teryx'), ('Lululemon', r'lululemon|露露'), ('Fila', r'斐乐|\bfila\b'), ('Descente', r'迪桑特|descente'),
    ('Salomon', r'萨洛蒙|salomon'), ('Columbia', r'哥伦比亚|columbia'), ('Champion', r'冠军|champion'), ('Kappa', r'卡帕|kappa'),
    ('Reebok', r'锐步|reebok'), ('Asics', r'亚瑟士|asics'), ('Converse', r'匡威|converse'), ('Vans', r'万斯|\bvans\b'),
    ('Lacoste', r'鳄鱼|lacoste'), ('Ralph Lauren', r'拉夫劳伦|ralph\s*lauren|\bpolo\s*rl'), ('Tommy Hilfiger', r'汤米|tommy'),
    ('Calvin Klein', r'\bck\b|calvin'), ('Hugo Boss', r'\bboss\b|波士'), ('Moncler', r'蒙口|moncler'), ('Canada Goose', r'加拿大鹅|canada\s*goose'),
    ('Stone Island', r'石头岛|stone\s*island'), ('Mizuno', r'美津浓|mizuno'), ('Umbro', r'茵宝|umbro'), ('Ellesse', r'ellesse'),
]
COLORS = [('azul marino', r'藏青|藏蓝|深蓝|navy'), ('celeste', r'浅蓝|天蓝|湖蓝'), ('negro', r'黑|black'), ('blanco', r'白|white'),
    ('gris', r'灰|grey|gray'), ('azul', r'蓝|blue'), ('rojo', r'红|red'), ('verde', r'绿|green|军绿'), ('rosado', r'粉|pink'),
    ('morado', r'紫|purple'), ('caqui', r'卡其|khaki'), ('café', r'咖|棕|brown'), ('beige', r'杏|米色|beige'), ('amarillo', r'黄|yellow'),
    ('naranja', r'橙|orange')]
SCALE = ['XS', 'S', 'M', 'L', 'XL', '2XL', '3XL', '4XL', '5XL']
CATS = {'camisetas': 'Camisetas', 'chaquetas': 'Chaquetas', 'buzos': 'Buzos', 'shorts': 'Shorts', 'pantalones': 'Pantalones',
        'conjuntos': 'Conjuntos', 'faldas': 'Faldas y vestidos', 'bolsos': 'Salveques y bolsos'}


def has(rx, text):
    return bool(re.search(rx, text or '', re.I))


def classify(ctx, raw):
    """(categorySlug, nombre de prenda) solo con nuestras palabras, o None si no se reconoce."""
    t = f'{ctx} {raw}'
    if (has(r'包', ctx) and not has(r'包装', ctx)) or has(r'背包|双肩包|书包|backpack', raw):
        if has(r'腰包|胸包', raw): return 'bolsos', 'Canguro'
        if has(r'斜挎|单肩|crossbody', raw): return 'bolsos', 'Bolso cruzado'
        if has(r'手提|tote', raw): return 'bolsos', 'Bolso'
        return 'bolsos', 'Salveque'
    if has(r'连衣裙', t): return 'faldas', 'Vestido'
    if has(r'裙', t): return 'faldas', 'Falda'
    if has(r'三件套', t): return 'conjuntos', 'Conjunto de 3 piezas'
    if has(r'长套|短套|(?<!外)套装', ctx) or (not has(r'外套|夹克|卫衣', raw) and has(r'长套|短套|(?<!外)套装', raw)):
        return 'conjuntos', 'Conjunto corto' if has(r'短套|短裤|短袖|夏季', t) else 'Conjunto largo'
    if has(r'短裤', ctx): return 'shorts', 'Pantaloneta'
    if has(r'长裤', ctx): return 'pantalones', 'Pantalón'
    if has(r'T恤', ctx): return 'camisetas', 'Polo' if has(r'polo', raw) else 'Camiseta'
    # Grupo chaquetas: se afina con el título del álbum.
    if has(r'马甲', raw): return 'chaquetas', 'Chaleco'
    if has(r'羽绒', raw): return 'chaquetas', 'Chaqueta de plumas'
    if has(r'棉服|棉衣|羽绒|马甲', t): return 'chaquetas', 'Chaqueta acolchada'
    if has(r'冲锋衣', t): return 'chaquetas', 'Chaqueta impermeable'
    if has(r'防晒|皮肤衣', t): return 'chaquetas', 'Chaqueta con protección solar'
    if has(r'风衣|防风|windbreaker', t): return 'chaquetas', 'Rompevientos'
    if has(r'卫衣|hoodie|sweatshirt', raw):
        if has(r'开衫|拉链|zip', raw): return 'buzos', 'Sudadera con cierre'
        if has(r'连帽|帽衫|hood', raw): return 'buzos', 'Sudadera con capucha'
        return 'buzos', 'Sudadera'
    if has(r'夹克|外套|棒球服|单衣|jacket', t): return 'chaquetas', 'Chaqueta'
    if has(r'卫衣', ctx): return 'buzos', 'Sudadera'
    if has(r'短裤|shorts', raw): return 'shorts', 'Pantaloneta'
    if has(r'裤|pants', raw): return 'pantalones', 'Pantalón'
    if has(r'polo', raw): return 'camisetas', 'Polo'
    if has(r'T恤|短袖|t-?shirt|tee', raw): return 'camisetas', 'Camiseta'
    return None


def brand_of(raw):
    return next((b for b, rx in BRANDS if re.search(rx, raw or '', re.I)), None)


def colors_of(raw):
    text = raw or ''; out = []
    for name, rx in COLORS:
        m = re.search(rx, text, re.I)
        if m:
            out.append(name); text = text[:m.start()] + ' ' * (m.end() - m.start()) + text[m.end():]
    return out[:6]


def sizes_of(raw, cat):
    if cat == 'bolsos': return ['Única']
    t = (raw or '').upper().replace(' ', '').replace('XXXXL', '4XL').replace('XXXL', '3XL').replace('XXL', '2XL')
    m = re.search(r'(XS|[2-5]XL|XL|S|M|L)[-—~～到至]+(XS|[2-5]XL|XL|S|M|L)', t)
    if m and m.group(1) in SCALE and m.group(2) in SCALE:
        a, b = SCALE.index(m.group(1)), SCALE.index(m.group(2))
        if a < b: return SCALE[a:b + 1]
    return ['S', 'M', 'L', 'XL', '2XL']


UNISEX = r'情侣|男女|中性|unisex'


def audience_of(cat, raw):
    if cat == 'faldas' or (has(r'女', raw) and not has(r'男', raw)): return ['mujer']
    if cat != 'bolsos' and has(UNISEX, raw): return ['hombre', 'mujer']
    return ['hombre']


def dhash(im):
    g = im.convert('L').resize((9, 8)); px = list(g.getdata())
    return [px[r * 9 + c] > px[r * 9 + c + 1] for r in range(8) for c in range(8)]


def fix_existing(site, albums, items, first_id=17240):
    """Una sola vez: corrige el público (mujer/unisex) de lo ya cargado. Solo cambia si la portada coincide."""
    from PIL import Image
    loaded = {int(p['id']): p for p in items if p['id'].isdigit() and int(p['id']) >= first_id and not p.get('team')}
    def one(k):
        p = loaded.get(first_id + k)
        if not p or k >= len(albums): return None
        aid, aurl, ctx = albums[k]
        try:
            page = site.page(aurl); raw = album_raw(page); cover = seller_cover(page, aurl)
            imgs = download(site, [cover], aurl) if cover else []
            mine = Image.open(Path('images') / p['cover'])
            if not imgs or sum(a != b for a, b in zip(dhash(imgs[0]), dhash(mine))) > 12: return None
            return p, audience_of(p['categorySlug'], raw)
        except Exception:
            return None
    fixed = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        for res in pool.map(one, range(len(loaded))):
            if not res: continue
            p, aud = res
            if aud != p.get('audiences'):
                p['audiences'] = aud; fixed += 1
                if aud == ['mujer'] and not p['title'].endswith('Mujer'): p['title'] += ' Mujer'
    return fixed


def fix_photos(items_path, first_id=17240):
    """Una sola vez: en lo ya cargado quita de la galería las fotos con texto y, si la portada tiene
    texto, pone en su lugar la primera foto limpia. Si ninguna foto queda limpia, el producto se oculta."""
    from PIL import Image
    items = json.loads(Path(items_path).read_text()); extras = Path('gallery-extra/images')
    todo = [p for p in items if p['id'].isdigit() and int(p['id']) >= first_id and not p.get('team') and p.get('cover')]
    def check(p):
        files = [Path('images') / p['cover']] + [extras / k for k in p.get('gallery') or []]
        flags = []
        for fpath in files:
            try:
                with Image.open(fpath) as im: flags.append(has_text(im))
            except Exception: flags.append(True)
        return p, flags
    report = {'checked': len(todo), 'cover_changed': [], 'gallery_trimmed': 0, 'hidden': []}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for p, flags in pool.map(check, todo):
            gallery = p.get('gallery') or []
            clean_gallery = [k for k, bad in zip(gallery, flags[1:]) if not bad]
            report['gallery_trimmed'] += len(gallery) - len(clean_gallery)
            if flags[0]:
                if not clean_gallery:
                    p['status'] = 'hidden'; report['hidden'].append(p['id']); continue
                new = clean_gallery.pop(0)
                with Image.open(extras / new) as im:
                    im.convert('RGB').save(Path('images') / p['cover'], 'WEBP', quality=75)
                report['cover_changed'].append(p['id'])
            p['gallery'] = clean_gallery
    Path(items_path).write_text(json.dumps(items, ensure_ascii=False, separators=(',', ':')))
    return report


def build_title(label, brand, women):
    return ' '.join([label] + ([brand] if brand else []) + (['Mujer'] if women else []))


SAFE = re.compile(r"^[A-Za-zÀ-ÿ0-9 .'/&()-]+$")


def main():
    url = (os.environ.get('FUENTE_NUEVA') or '').strip()
    control = read('casual-control.json', {})
    from casual_photos import _ocr
    _ocr()  # si el lector de texto no carga, se detiene aquí sin ocultar ni saltar nada
    if control.get('fix_photos') and not Path('casual-photos-fixed.json').exists():
        Path('casual-photos-fixed.json').write_text(json.dumps(fix_photos(items_path='catalog.json')))
    if control.get('pause'):
        Path('casual-result.json').write_text(json.dumps({'status': 'pausado', 'added': 0, 'remaining': 0})); return
    items = read('catalog.json', []); seen = set(read('casual-seen.json', []))
    extras = Path('gallery-extra/images'); extras.mkdir(parents=True, exist_ok=True)
    counter = max(int(p['id']) for p in items) + 1; size_now = sum(p.stat().st_size for p in Path('images').glob('*.webp'))
    report = {'added': 0, 'by_category': {}, 'skipped': {}}
    pilot_dir = Path('casual-pilot')
    if not url:
        report['status'] = 'sin_fuente'; Path('casual-result.json').write_text(json.dumps(report)); return
    site = Site(url)
    albums = collect(site, 'casual')
    key = lambda a: opaque(site.host, 'casual', a[0])
    if not PILOT and not Path('casual-audience-fixed.json').exists():
        report['audience_fixed'] = fix_existing(site, albums, items)
        Path('casual-audience-fixed.json').write_text(json.dumps({'fixed': report['audience_fixed']}))
    pending = [a for a in albums if key(a) not in seen]
    report['albums'] = len(albums)
    batch = pending[::max(1, len(pending) // 40)][:40] if PILOT else pending[:BATCH]

    def work(entry):
        aid, aurl, ctx = entry
        try:
            page = site.page(aurl); raw = album_raw(page)
            kind = classify(ctx, raw)
            if not kind: return entry, None, 'tipo_desconocido'
            cat, label = kind
            aud = audience_of(cat, raw); women = aud == ['mujer']
            brand = brand_of(raw)
            title = build_title(label, brand, women)
            if not SAFE.match(title): return entry, None, 'titulo_inseguro'
            urls = album_originals(page, aurl)[:10]; cover = seller_cover(page, aurl)
            if cover and cover in urls: urls.remove(cover)
            images = download(site, ([cover] if cover else []) + urls, aurl)
            if not images: return entry, None, 'sin_fotos'
            approved = []
            for i, im in enumerate(images[:9]):
                if review_image(im, TERMS)[0] == 'rejected' or any(same_photo(im, images[j]) for j in approved): continue
                approved.append(i)
            selected = pick(images, 0 if cover else None, approved, MAX_PHOTOS)
            if not selected: return entry, None, 'fotos_con_texto'
            kept = []
            for i in selected:
                im = images[i].copy(); im.thumbnail((600, 600)); kept.append(im)
            return entry, dict(cat=cat, title=title, brand=brand, women=women, aud=aud, colors=colors_of(raw),
                               sizes=sizes_of(raw, cat), images=kept), 'ok'
        except Exception as e:
            return entry, None, 'error_' + type(e).__name__

    with ThreadPoolExecutor(max_workers=6) as pool: results = list(pool.map(work, batch))
    for entry, data, status in results:
        if status != 'ok':
            report['skipped'][status] = report['skipped'].get(status, 0) + 1
            if not status.startswith('error'): seen.add(key(entry))
            continue
        if size_now > SIZE_BUDGET: report['status'] = 'size_budget_reached'; break
        ident = str(counter); counter += 1
        cat = data['cat']; report['by_category'][cat] = report['by_category'].get(cat, 0) + 1
        selected = list(range(len(data['images'])))
        if PILOT:
            pilot_dir.mkdir(exist_ok=True); im = data['images'][0].copy(); im.thumbnail((300, 300))
            im.save(pilot_dir / f'{ident}.webp', 'WEBP', quality=60)
            (pilot_dir / f'{ident}.json').write_text(json.dumps({k: data[k] for k in ('title', 'cat', 'colors', 'sizes')} | {'photos': len(selected)}, ensure_ascii=False))
        else:
            keys = save(ident, data['images'], selected, extras)
            brand = data['brand'] or 'Otras marcas'
            items.insert(0, {'id': ident, 'slug': ident, 'title': data['title'], 'brand': brand, 'team': None, 'teamSlug': None,
                'league': None, 'leagueSlug': None, 'categorySlug': cat, 'category': CATS[cat], 'sizes': data['sizes'],
                'season': None, 'version': None, 'audiences': data['aud'], 'colors': data['colors'],
                'price': None, 'status': 'active', 'cover': f'{ident}.webp',
                'sectionSlug': 'accesorios' if cat == 'bolsos' else 'ropa-casual', 'gallery': keys})
            size_now += (Path('images') / f'{ident}.webp').stat().st_size
            seen.add(key(entry))
        report['added'] += 1
    report['remaining'] = 0 if PILOT else max(0, len(pending) - len(batch))
    report.setdefault('status', 'ok')
    if not PILOT:
        Path('catalog.json').write_text(json.dumps(items, ensure_ascii=False, separators=(',', ':')))
        Path('casual-seen.json').write_text(json.dumps(sorted(seen)))
    Path('casual-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    try: main()
    except Exception as e:
        Path('casual-result.json').write_text(json.dumps({'fatal': type(e).__name__, 'remaining': 0}))
