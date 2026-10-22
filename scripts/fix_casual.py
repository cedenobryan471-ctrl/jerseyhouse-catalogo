"""Saca de Ropa casual las camisetas deportivas que quedaron sin equipo. Reglas explícitas, sin IA."""
import json, re, sys
from pathlib import Path
from fix_sections import slug

# (patrón en el título, sección, liga, equipo)
RULES = [
    (r'red bull .*pantaloneta', 'formula-1', 'Fórmula 1', 'Red Bull Racing'),
    (r'san luis', 'futbol', 'Liga MX', 'Atlético San Luis'),
    (r'ガンバ', 'futbol', 'J1 League', 'Gamba Osaka'), (r'アントラーズ', 'futbol', 'J1 League', 'Kashima Antlers'),
    (r'camiseta deportivo (?:local|visitante|tercera)', 'futbol', 'LaLiga', 'Deportivo La Coruña'),
    (r'galata', 'futbol', 'Otras ligas', 'Galatasaray'), (r'caesars? chief', 'futbol', 'Otras ligas', 'Kaizer Chiefs'),
    (r'brandford', 'futbol', 'Otras ligas', 'Bradford City'), (r'confian', 'futbol', 'Brasileirão', 'Confiança'),
    (r'camiseta los angeles', 'futbol', 'MLS', 'Los Angeles FC'), (r'camiseta saudi', 'selecciones', 'Selecciones', 'Arabia Saudita'),
    (r'basque country', 'selecciones', 'Selecciones', 'País Vasco'), (r'paliroots|filistin', 'selecciones', 'Selecciones', 'Palestina'),
    (r'afc richmond', 'futbol', 'Ediciones especiales', 'AFC Richmond'), (r'cristiano ronaldo', 'futbol', 'Ediciones especiales', 'Cristiano Ronaldo'),
    (r'ibrahimovic', 'futbol', 'Ediciones especiales', 'Ibrahimović'), (r'joaqu[ií]n', 'futbol', 'Ediciones especiales', 'Joaquín'),
    (r'oasis', 'futbol', 'Ediciones especiales', 'Oasis'), (r'anti-?racism', 'futbol', 'Ediciones especiales', 'Premier League'),
    (r'lanzerite', 'futbol', 'Otros equipos', 'Lanzarote'), (r'canadian pacific', 'futbol', 'Otros equipos', 'Pacific FC'),
    (r'belgra\b', 'futbol', 'Liga Argentina', 'Belgrano'),
    (r'world cup champion', 'futbol', 'Ediciones especiales', 'Campeones del Mundo'),
    (r'thompson|durant', 'nba', 'NBA', 'Golden State Warriors'), (r'bryant|james#', 'nba', 'NBA', 'Los Angeles Lakers'),
    (r'markkanen|lavine|bjordan|bull stadium|slam dunk jordan', 'nba', 'NBA', 'Chicago Bulls'),
    (r'beal|kuzma|harrell', 'nba', 'NBA', 'Washington Wizards'), (r'trailblazer', 'nba', 'NBA', 'Portland Trail Blazers'),
    (r'eagles young', 'nba', 'NBA', 'Atlanta Hawks'),
]
CLUB_SHIRT = re.compile(r'^camiseta (?:de entrenamiento )?(.+?) (?:local|visitante|tercera equipaci[oó]n|portero)\b', re.I)

def main(path='catalog.json'):
    items = json.loads(Path(path).read_text()); moved = 0
    for p in items:
        if p.get('sectionSlug') != 'ropa-casual': continue
        t = p.get('title') or ''
        rule = next((r for r in RULES if re.search(r[0], t, re.I)), None)
        if rule:
            _, section, league, team = rule
        elif p.get('league') == 'NBA' or re.search(r'\bnba\b', t, re.I):
            section, league, team = 'nba', 'NBA', 'Otros NBA'
        elif (m := CLUB_SHIRT.match(t)):
            section, league, team = 'futbol', 'Otros equipos', m.group(1).strip()
        else:
            continue
        p.update(sectionSlug=section, league=league, leagueSlug=slug(league), team=team, teamSlug=slug(team))
        moved += 1
    Path(path).write_text(json.dumps(items, ensure_ascii=False, separators=(',', ':')))
    print(json.dumps({'moved_from_casual': moved}))

if __name__ == '__main__':
    sys.path.insert(0, 'scripts'); main(*sys.argv[1:])
