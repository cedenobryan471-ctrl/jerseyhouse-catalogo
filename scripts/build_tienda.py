"""Genera tienda.json: el mismo catálogo pero liviano (sin campos vacíos ni valores por defecto).
La tienda lo expande al leerlo; si falta, usa catalog.json."""
import json
from pathlib import Path

DEFAULTS = {'version': 'fan', 'status': 'active', 'brand': 'Otras marcas',
            'audiences': ['hombre'], 'sizes': ['S', 'M', 'L', 'XL', '2XL']}

def compact(p):
    q = {}
    for k, v in p.items():
        if v is None or v == '' or (v == [] and k not in DEFAULTS): continue
        if k == 'slug' and v == p['id']: continue
        if k == 'cover' and v == f"{p['id']}.webp": continue
        if DEFAULTS.get(k) == v: continue
        if k == 'gallery' and all(x == f"{p['id']}-{i + 1}.webp" for i, x in enumerate(v)):
            q['g'] = len(v); continue
        q[k] = v
    if p.get('cover') is None: q['cover'] = None
    if 'version' in p and p['version'] is None: q['version'] = None  # sin etiqueta "Versión" (ropa de marca, calzado)
    return q

def main():
    items = json.loads(Path('catalog.json').read_text())
    Path('tienda.json').write_text(json.dumps([compact(p) for p in items], ensure_ascii=False, separators=(',', ':')))

if __name__ == '__main__':
    main()
