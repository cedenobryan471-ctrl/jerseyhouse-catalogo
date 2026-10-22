"""Separa calzado en Tacos / Tenis de fútbol / Tenis deportivos y oculta lo que no es calzado."""
import json, re, sys
from pathlib import Path
sys.path.insert(0, 'scripts')
from footwear_rules import footwear_group, footwear_sole, footwear_collar

NOT_SHOES = re.compile(r'\bsocks?\b', re.I)

def main():
    items = json.loads(Path('catalog.json').read_text()); states = json.loads(Path('estado.json').read_text())
    counts = {}; hidden = 0
    for p in items:
        if p.get('categorySlug') != 'calzado': continue
        p['footwearType'] = footwear_group(p.get('title'))
        if p['footwearType'] in ('tacos', 'futbol'):
            p['sole'] = footwear_sole(p.get('title')); p['collar'] = footwear_collar(p.get('title'))
        else:
            p.pop('sole', None); p.pop('collar', None)
        counts[p['footwearType']] = counts.get(p['footwearType'], 0) + 1
        if NOT_SHOES.search(p.get('title') or '') and states.get(p['id']) != 'hidden':
            states[p['id']] = 'hidden'; hidden += 1
    Path('catalog.json').write_text(json.dumps(items, ensure_ascii=False, separators=(',', ':')))
    Path('estado.json').write_text(json.dumps(states, ensure_ascii=False, indent=2))
    print(json.dumps({'groups': counts, 'hidden_not_shoes': hidden}))

if __name__ == '__main__':
    main()
