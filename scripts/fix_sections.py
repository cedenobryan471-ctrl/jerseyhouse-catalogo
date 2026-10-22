"""Reubica productos mal clasificados en Ropa casual y Accesorios, con reglas explícitas y sin IA."""
import json, re, sys
from pathlib import Path

def slug(text):
    import unicodedata
    t = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', t).strip('-')

# alias (regex sobre el título) -> (equipo, liga)
CLUBS = [
    (r'galatasaray', 'Galatasaray', 'Otras ligas'), (r'fenerbah?ce', 'Fenerbahçe', 'Otras ligas'),
    (r'be\s?ikta|besiktas', 'Beşiktaş', 'Otras ligas'), (r'pe\s?arol|penarol|peñarol', 'Peñarol', 'Otras ligas'),
    (r'cerro\s+port', 'Cerro Porteño', 'Otras ligas'), (r'k[øo]?benhavn|copenhagen', 'FC Copenhagen', 'Otras ligas'),
    (r'olympiacos', 'Olympiacos', 'Otras ligas'), (r'panathinaikos', 'Panathinaikos', 'Otras ligas'),
    (r'aek athens', 'AEK Athens', 'Otras ligas'), (r'bohemian', 'Bohemians', 'Otras ligas'),
    (r'hajduk', 'Hajduk Split', 'Otras ligas'), (r'dinamo zagreb', 'Dinamo Zagreb', 'Otras ligas'),
    (r'dynamo kyiv', 'Dynamo Kyiv', 'Otras ligas'), (r'shakhtar', 'Shakhtar Donetsk', 'Otras ligas'),
    (r'zenit', 'Zenit', 'Otras ligas'), (r'estrella roja', 'Estrella Roja', 'Otras ligas'),
    (r'maccabi', 'Maccabi Haifa', 'Otras ligas'), (r'beitar jerusalem', 'Beitar Jerusalem', 'Otras ligas'),
    (r'hapoel beer', 'Hapoel Beer-Sheva', 'Otras ligas'), (r'red bull salzburg|rojo bull salzburg', 'Red Bull Salzburg', 'Otras ligas'),
    (r'anderlecht', 'Anderlecht', 'Otras ligas'), (r'club brugge', 'Club Brugge', 'Otras ligas'),
    (r'servette', 'Servette', 'Otras ligas'), (r'legia', 'Legia Varsovia', 'Otras ligas'),
    (r'dinamo tbilisi', 'Dinamo Tbilisi', 'Otras ligas'), (r'\bel ahly\b', 'Al Ahly', 'Otras ligas'),
    (r'young africans', 'Young Africans', 'Otras ligas'), (r'kaizer chiefs', 'Kaizer Chiefs', 'Otras ligas'),
    (r'\bmc alg', 'MC Alger', 'Otras ligas'), (r'\baik\b', 'AIK', 'Otras ligas'), (r'fc copenhagen', 'FC Copenhagen', 'Otras ligas'),
    (r'millonarios|millionaire', 'Millonarios', 'Otras ligas'), (r'barranquilla', 'Junior de Barranquilla', 'Otras ligas'),
    (r'tolima', 'Deportes Tolima', 'Otras ligas'), (r'club nacional|uruguayan nation', 'Nacional', 'Otras ligas'),
    (r'\bolimpia\b|\bolympia\b|club olimpia', 'Olimpia', 'Otras ligas'), (r'motagua|mottagua', 'Motagua', 'Otras ligas'),
    (r'emelec', 'Emelec', 'Otras ligas'), (r'alianza lima', 'Alianza Lima', 'Otras ligas'),
    (r'sporting cristal', 'Sporting Cristal', 'Otras ligas'), (r'estudiantes de la plata', 'Estudiantes de La Plata', 'Otras ligas'),
    (r'wrexham', 'Wrexham', 'Otras ligas'), (r'portsmouth', 'Portsmouth', 'Otras ligas'),
    (r'lincoln city', 'Lincoln City', 'Otras ligas'), (r'bradford', 'Bradford City', 'Otras ligas'),
    (r'cork city', 'Cork City', 'Otras ligas'), (r'ayr united', 'Ayr United', 'Otras ligas'),
    (r'aberdeen', 'Aberdeen FC', 'Scottish Premiership'), (r'^camiseta celtics\b', 'Celtic', 'Scottish Premiership'),
    (r'^camiseta charlotte\b|^2023/24 charlotte\b', 'Charlotte FC', 'MLS'), (r'^camiseta (?:de entrenamiento )?miami\b|^2023/24 miami jackets', 'Inter Miami', 'MLS'),
    (r'st\.?\s?louis', 'St. Louis City', 'MLS'),
    (r'aniquiladores', 'Aniquiladores FC', 'Kings League'), (r'el barrio', 'El Barrio', 'Kings League'),
    (r'saiyans', 'Saiyans FC', 'Kings League'), (r'porcinos', 'Porcinos FC', 'Kings League'),
    (r'ultimate m[oó]stoles', 'Ultimate Móstoles', 'Kings League'), (r'\bpersas\b', 'Persas FC', 'Kings League'),
    (r'olimpo united', 'Olimpo United', 'Kings League'), (r'\bpio fc\b', 'PIO FC', 'Kings League'),
]
NBA_TEAMS = ['Chicago Bulls', 'Charlotte Hornets', 'Brooklyn Nets']
JAPAN = re.compile(r'\bjapan\b', re.I)

def fix(p):
    t = p.get('title') or ''
    sec = p.get('sectionSlug')
    if sec == 'accesorios' and re.search(r'dragon ball|goku|vegeta|saiyan|hat trick', t, re.I) and JAPAN.search(t):
        p.update(team='Japón', teamSlug='japon', league='Selecciones', leagueSlug='selecciones', category='Camisetas', categorySlug='camisetas', sectionSlug='selecciones')
        return 'japan'
    if sec == 'accesorios' and re.search(r'ball\s?#\s?\d', t, re.I):
        for team in NBA_TEAMS:
            if re.search(team.split()[-1], t, re.I) or re.search(team.split()[0], t, re.I):
                garment = ('Shorts', 'shorts') if re.search(r'pantal', t, re.I) else ('Camisetas', 'camisetas')
                p.update(team=team, teamSlug=slug(team), league='NBA', leagueSlug='nba', category=garment[0], categorySlug=garment[1], sectionSlug='nba')
                return 'nba_ball'
    if sec == 'ropa-casual' and p.get('league') == 'NBA' and not p.get('team'):
        team = 'Team USA' if re.search(r'\bUSA\b', t) else ('All-Star' if re.search(r'all-?star', t, re.I) else None)
        if team:
            p.update(team=team, teamSlug=slug(team), sectionSlug='nba'); return 'nba_special'
    if sec == 'ropa-casual' and p.get('categorySlug') in ('camisetas', 'chaquetas', 'conjuntos', 'shorts'):
        for pattern, team, league in CLUBS:
            if re.search(pattern, t, re.I):
                p.update(team=team, teamSlug=slug(team), league=league, leagueSlug=slug(league), sectionSlug='futbol')
                return 'club'
    return None

def main(path='catalog.json'):
    products = json.loads(Path(path).read_text())
    counts = {}
    for p in products:
        r = fix(p)
        if r: counts[r] = counts.get(r, 0) + 1
    Path(path).write_text(json.dumps(products, ensure_ascii=False, separators=(',', ':')))
    print(json.dumps({'moved': counts}))

if __name__ == '__main__':
    main(*sys.argv[1:])
