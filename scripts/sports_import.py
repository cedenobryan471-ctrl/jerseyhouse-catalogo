"""Carga de NFL, NHL y Fórmula 1 por tandas, sin IA.

Privacidad al 100 %: el nombre público de cada producto se arma SOLO con palabras de este
archivo (equipo, prenda, versión, temporada). Ningún texto del proveedor llega al catálogo.
Si no se reconoce el equipo, el producto no se carga. No se guardan direcciones.
"""
import hashlib, json, os, re, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, 'scripts')
from footwear_import import Site, links, max_page, with_page, download, choose, save, opaque, read, SIZE_BUDGET
from photo_candidates import album_originals, seller_cover
from footwear_rules import translate

OTHER_SPORTS = re.compile(r'\bmlb\b|baseball|棒球|\bnba\b|篮球|basketball|soccer|足球', re.I)
PRIVATE = []
PILOT = os.environ.get('SPORTS_PILOT') == 'true'
BATCH = int(os.environ.get('SPORTS_BATCH', '40'))

def T(league, rows):
    return [(league, name, [a.lower() for a in aliases]) for name, *aliases in rows]

TEAMS = T('NHL', [
    ('Anaheim Ducks', 'anaheim ducks', '鸭队'), ('Boston Bruins', 'bruins', '棕熊'), ('Buffalo Sabres', 'sabres', '军刀'),
    ('Calgary Flames', 'flames', '火焰'), ('Carolina Hurricanes', 'hurricanes', '飓风'), ('Chicago Blackhawks', 'blackhawks', '黑鹰'),
    ('Colorado Avalanche', 'avalanche', '雪崩'), ('Columbus Blue Jackets', 'blue jackets', '蓝衣'), ('Dallas Stars', 'dallas stars', '达拉斯星'),
    ('Detroit Red Wings', 'red wings', '红翼'), ('Edmonton Oilers', 'oilers', '油人'), ('Florida Panthers', 'florida panthers', '佛罗里达美洲豹'),
    ('Los Angeles Kings', 'la kings', 'los angeles kings', '洛杉矶国王'), ('Minnesota Wild', 'minnesota wild', '狂野'), ('Montreal Canadiens', 'canadiens', '加拿大人'),
    ('Nashville Predators', 'predators', '掠夺者'), ('New Jersey Devils', 'devils', '魔鬼'), ('New York Islanders', 'islanders', '岛人'),
    ('New York Rangers', 'new york rangers', 'ny rangers', '纽约游骑兵'), ('Ottawa Senators', 'senators', '参议员'), ('Philadelphia Flyers', 'flyers', '飞人'),
    ('Pittsburgh Penguins', 'penguins', '企鹅'), ('San Jose Sharks', 'sharks', '鲨鱼'), ('Seattle Kraken', 'kraken', '海怪'),
    ('St. Louis Blues', 'st louis blues', 'st. louis blues', '蓝调'), ('Tampa Bay Lightning', 'tampa bay lightning', '坦帕湾闪电'),
    ('Toronto Maple Leafs', 'maple leafs', '枫叶'), ('Utah Mammoth', 'utah', '犹他'), ('Vancouver Canucks', 'canucks', '加人'),
    ('Vegas Golden Knights', 'golden knights', '金骑士'), ('Washington Capitals', 'capitals', '首都人'), ('Winnipeg Jets', 'winnipeg', '温尼伯')]) + T('NFL', [
    ('Arizona Cardinals', 'arizona cardinals', '红雀'), ('Atlanta Falcons', 'falcons', '猎鹰'), ('Baltimore Ravens', 'ravens', '乌鸦'),
    ('Buffalo Bills', 'buffalo bills', '布法罗比尔'), ('Carolina Panthers', 'carolina panthers', '黑豹'), ('Chicago Bears', 'chicago bears', '芝加哥熊'),
    ('Cincinnati Bengals', 'bengals', '猛虎'), ('Cleveland Browns', 'cleveland browns', '克利夫兰布朗'), ('Dallas Cowboys', 'cowboys', '牛仔'),
    ('Denver Broncos', 'broncos', '野马'), ('Detroit Lions', 'detroit lions', '雄狮'), ('Green Bay Packers', 'packers', '包装工'),
    ('Houston Texans', 'texans', '德州人'), ('Indianapolis Colts', 'colts', '小马'), ('Jacksonville Jaguars', 'jaguars', '美洲虎'),
    ('Kansas City Chiefs', 'kansas city chiefs', 'kc chiefs', '堪萨斯城酋长'), ('Las Vegas Raiders', 'raiders', '突袭者'), ('Los Angeles Chargers', 'chargers', '闪电侠', '洛杉矶闪电'),
    ('Los Angeles Rams', 'los angeles rams', 'la rams', '洛杉矶公羊'), ('Miami Dolphins', 'dolphins', '海豚'), ('Minnesota Vikings', 'vikings', '维京人'),
    ('New England Patriots', 'patriots', '爱国者'), ('New Orleans Saints', 'saints', '圣徒'), ('New York Giants', 'new york giants', 'ny giants', '纽约巨人'),
    ('New York Jets', 'new york jets', 'ny jets', '纽约喷气机'), ('Philadelphia Eagles', 'eagles', '老鹰'), ('Pittsburgh Steelers', 'steelers', '钢人'),
    ('San Francisco 49ers', '49ers', '49人'), ('Seattle Seahawks', 'seahawks', '海鹰'), ('Tampa Bay Buccaneers', 'buccaneers', '海盗'),
    ('Tennessee Titans', 'titans', '泰坦'), ('Washington Commanders', 'commanders', '指挥官')]) + T('Fórmula 1', [
    ('Ferrari', 'ferrari', '法拉利'), ('Mercedes', 'mercedes', '梅赛德斯', '奔驰'), ('McLaren', 'mclaren', '迈凯伦'),
    ('Red Bull Racing', 'red bull', '红牛'), ('Aston Martin', 'aston martin', '阿斯顿马丁'), ('Alpine', 'alpine', '阿尔派'),
    ('Williams', 'williams', '威廉姆斯'), ('Haas', 'haas', '哈斯'), ('Audi', 'audi', '奥迪'), ('Cadillac', 'cadillac', '凯迪拉克'),
    ('Racing Bulls', 'racing bulls', 'visa cash app')])
SECTION = {'NHL': 'nhl', 'NFL': 'nfl', 'Fórmula 1': 'formula-1'}
LEAGUE_WORD = {'NHL': re.compile(r'nhl|冰球|hockey', re.I), 'NFL': re.compile(r'nfl|橄榄球|football', re.I)}

GARMENTS = [('chaquetas', 'Chaqueta', r'jacket|windbreaker|夹克|外套|风衣|冲锋衣'), ('buzos', 'Sudadera', r'hoodie|sweatshirt|卫衣'),
            ('shorts', 'Pantaloneta', r'shorts?|短裤'), ('camisetas', 'Polo', r'\bpolo\b|polo衫'),
            ('camisetas', 'Camiseta', r'.')]
VERSIONS = [('Local', r'\bhome\b|主场'), ('Visitante', r'\baway\b|客场'), ('Alternativa', r'\balternate\b|\bthird\b|第三'),
            ('Retro', r'retro|复古'), ('Edición especial', r'special|limited|特别|限定'), ('Versión jugador', r'player|球员版')]

def match_team(text, league_hint=None):
    t = translate(text).lower() + ' ' + (text or '').lower()
    hits = [(len(a), lg, name) for lg, name, aliases in TEAMS for a in aliases
            if (a.isascii() and re.search(r'(?<![a-z])' + re.escape(a) + r'(?![a-z])', t)) or (not a.isascii() and a in t)]
    if league_hint: hits = [h for h in hits if h[1] == league_hint] or hits
    return (max(hits)[1], max(hits)[2]) if hits else None

def build_title(raw, team):
    garment = next((g for g in GARMENTS if re.search(g[2], raw, re.I)), GARMENTS[-1])
    version = [v for v, rx in VERSIONS if re.search(rx, raw, re.I)][:2]
    season = re.search(r'(?<!\d)(20[0-3]\d)(?:\s*[/-]\s*(\d{2}))?(?!\d)', raw)
    parts = [garment[1], team] + version + ([season.group(1) + ('/' + season.group(2) if season.group(2) else '')] if season else [])
    return ' '.join(parts), garment[0], garment[1]

SAFE = re.compile(r"^[A-Za-zÀ-ÿ0-9 .'/&-]+$")

def safe_title(title, team):
    # Solo letras/números de nuestro vocabulario; ningún número largo; debe empezar con nuestra prenda.
    return bool(SAFE.match(title)) and not re.search(r'\d{5,}', title) and team in title

def album_raw(page):
    h = page.select_one('.showalbumheader__gallerytitle') or page.select_one('h1')
    return h.get_text(' ', strip=True) if h else ''

def collect(site, mode):
    """Devuelve (key, url, contexto) por álbum, con el texto de la categoría como contexto (nunca se publica)."""
    first = site.page(site.url); out = []
    cats = links(first, site.url, site.host, r'/categories/(\d+)')
    if cats:
        for cid, (curl, anchor) in cats.items():
            ctx = anchor.get_text(' ', strip=True)
            try:
                cp = site.page(curl); pages = max_page(cp)
                for n in range(1, min(pages, 30) + 1):
                    page = cp if n == 1 else site.page(with_page(curl, n))
                    for aid, (aurl, a) in links(page, curl, site.host, r'/albums/(\d+)').items():
                        out.append((aid, aurl, ctx + ' ' + a.get_text(' ', strip=True)))
            except Exception:
                continue
    else:
        pages = max_page(first)
        for n in range(1, min(pages, 60) + 1):
            page = first if n == 1 else site.page(with_page(site.url, n))
            for aid, (aurl, a) in links(page, site.url, site.host, r'/albums/(\d+)').items():
                out.append((aid, aurl, a.get_text(' ', strip=True)))
    seen = set(); uniq = []
    for item in out:
        if item[0] not in seen: seen.add(item[0]); uniq.append(item)
    return uniq

def main():
    sources = [s for s in json.loads(os.environ.get('SOURCES_CONFIG') or '[]') if s.get('mode') in ('american', 'racing')]
    items = read('catalog.json', []); seen = set(read('sports-seen.json', []))
    extras = Path('gallery-extra/images'); extras.mkdir(parents=True, exist_ok=True)
    counter = max(int(p['id']) for p in items) + 1; size_now = sum(p.stat().st_size for p in Path('images').glob('*.webp'))
    report = {'sources': [], 'added': 0, 'by_league': {}, 'by_team': {}}
    pilot_dir = Path('sports-pilot')
    for number, source in enumerate(sources, 1):
        site = Site(source['url']); rep = {'source': number, 'mode': source['mode'], 'added': 0, 'skipped': {}}
        hint = 'Fórmula 1' if source['mode'] == 'racing' else None
        try: albums = collect(site, source['mode'])
        except Exception as e: rep['status'] = 'unreadable:' + type(e).__name__; report['sources'].append(rep); continue
        pending = [a for a in albums if opaque(site.host, 'album', a[0]) not in seen]
        rep['albums'] = len(albums); rep['pending_before'] = len(pending)
        batch = pending[::max(1, len(pending) // 40)][:40] if PILOT else pending[:BATCH]
        def work(entry):
            aid, aurl, ctx = entry
            if source['mode'] == 'american' and OTHER_SPORTS.search(ctx): return entry, None, 'other_sport'
            try:
                page = site.page(aurl); raw = album_raw(page); text = ctx + ' ' + raw
                if source['mode'] == 'american' and OTHER_SPORTS.search(raw): return entry, None, 'other_sport'
                league_hint = hint or next((lg for lg, rx in LEAGUE_WORD.items() if rx.search(text)), None)
                found = match_team(text, league_hint)
                if not found or (source['mode'] == 'american' and found[0] == 'Fórmula 1') or (source['mode'] == 'racing' and found[0] != 'Fórmula 1'):
                    if PILOT: PRIVATE.append({'mode': source['mode'], 'ctx': ctx[:80], 'raw': raw[:160]})
                    return entry, None, 'team_unknown'
                league, team = found
                title, cat, label = build_title(text, team)
                if not safe_title(title, team): return entry, None, 'unsafe_title'
                urls = album_originals(page, aurl)[:10]; cover = seller_cover(page, aurl)
                if cover and cover in urls: urls.remove(cover)
                images = download(site, ([cover] if cover else []) + urls, aurl)
                if not images: return entry, None, 'no_photos'
                selected = choose(images, 0 if cover else None)
                if not selected: return entry, None, 'photos_rejected'
                return entry, (league, team, title, cat, label, images, selected), 'ok'
            except Exception as e:
                return entry, None, 'error_' + type(e).__name__
        with ThreadPoolExecutor(max_workers=6) as pool: results = list(pool.map(work, batch))
        for (aid, _, _), data, status in results:
            key = opaque(site.host, 'album', aid)
            if status != 'ok':
                rep['skipped'][status] = rep['skipped'].get(status, 0) + 1
                if not status.startswith('error'): seen.add(key)
                continue
            if size_now > SIZE_BUDGET: rep['status'] = 'size_budget_reached'; break
            league, team, title, cat, label, images, selected = data
            ident = str(counter); counter += 1
            report['by_league'][league] = report['by_league'].get(league, 0) + 1
            report['by_team'][team] = report['by_team'].get(team, 0) + 1
            if PILOT:
                pilot_dir.mkdir(exist_ok=True); im = images[selected[0]].copy(); im.thumbnail((300, 300))
                im.save(pilot_dir / f'{ident}.webp', 'WEBP', quality=60)
                (pilot_dir / f'{ident}.json').write_text(json.dumps({'title': title, 'league': league, 'photos': len(selected)}, ensure_ascii=False))
            else:
                keys = save(ident, images, selected, extras)
                season = re.search(r'20\d\d(?:/\d\d)?', title)
                items.insert(0, {'id': ident, 'slug': ident, 'title': title, 'brand': 'Otras marcas', 'team': team,
                    'teamSlug': re.sub(r'[^a-z0-9]+', '-', team.lower()).strip('-'), 'league': league,
                    'leagueSlug': SECTION[league], 'categorySlug': cat, 'category': {'camisetas': 'Camisetas', 'chaquetas': 'Chaquetas', 'buzos': 'Buzos', 'shorts': 'Shorts'}[cat],
                    'sizes': ['S', 'M', 'L', 'XL', '2XL'], 'season': season.group(0) if season else None, 'version': 'fan',
                    'audiences': ['hombre'], 'colors': [], 'price': None, 'status': 'active', 'cover': f'{ident}.webp',
                    'sectionSlug': SECTION[league], 'gallery': keys})
                size_now += (Path('images') / f'{ident}.webp').stat().st_size
                seen.add(key)
            rep['added'] += 1
        rep['pending_after'] = max(0, len(pending) - len(batch)); rep.setdefault('status', 'ok')
        report['sources'].append(rep); report['added'] += rep['added']
    if not PILOT:
        Path('catalog.json').write_text(json.dumps(items, ensure_ascii=False, separators=(',', ':')))
        Path('sports-seen.json').write_text(json.dumps(sorted(seen)))
    report['remaining'] = sum(r.get('pending_after', 0) for r in report['sources'])
    Path('sports-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=1))
    if PILOT and PRIVATE:
        # Solo cifrado: nadie más que el dueño de la llave privada puede leerlo.
        Path('/tmp/private.json').write_text(json.dumps(PRIVATE, ensure_ascii=False))

if __name__ == '__main__':
    try: main()
    except Exception as e:
        Path('sports-result.json').write_text(json.dumps({'fatal': type(e).__name__}))
