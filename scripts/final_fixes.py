"""Últimos arreglos de orden, se corren después de todo lo demás en cada carga.
- "Otras ligas" no es una liga: esos equipos van a "Otros equipos".
- Camisetas de selección o equipo que quedaron en Accesorios vuelven a su sección."""
import json, re
from pathlib import Path

p = Path('catalog.json'); items = json.loads(p.read_text()); changed = 0
for x in items:
    if x.get('league') == 'Otras ligas':
        x['league'] = 'Otros equipos'; x['leagueSlug'] = 'otros-equipos'; changed += 1
    if x.get('sectionSlug') == 'accesorios' and re.search(r'\bcamiseta\b|\bkit\b|jersey|jap[oó]n', x.get('title', ''), re.I):
        if re.search(r'jap[oó]n', x['title'], re.I):
            x.update(team='Japón', teamSlug='japon', league='Selecciones', leagueSlug='selecciones', sectionSlug='selecciones')
        x['categorySlug'] = 'camisetas'; x['category'] = 'Camisetas'; changed += 1
if changed: p.write_text(json.dumps(items, ensure_ascii=False, separators=(',', ':')))
print('arreglos finales:', changed)
