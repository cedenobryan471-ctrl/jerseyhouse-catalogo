"""Aplica portadas elegidas automáticamente intercambiando la portada con una foto de la galería.

Nunca borra fotos: la portada anterior pasa a la galería en el lugar de la foto elegida.
Es idempotente: cada producto se intercambia una sola vez (auto-covers-applied.json).
"""
import json
from pathlib import Path
from PIL import Image

def read(path, fallback):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else fallback

def main():
    picks = read('auto-covers.json', {})
    applied = read('auto-covers-applied.json', {})
    manual = read('portadas.json', {})
    products = read('catalog.json', [])
    extras = Path('gallery-extra/images')
    byid = {p['id']: p for p in products}
    done = skipped = 0
    for ident, key in picks.items():
        product = byid.get(ident)
        if ident in applied or ident in manual or not product or key not in (product.get('gallery') or []):
            skipped += 1; continue
        cover = Path('images') / product['cover']
        extra = extras / key
        if not cover.is_file() or not extra.is_file():
            skipped += 1; continue
        with Image.open(cover) as old, Image.open(extra) as new:
            old = old.convert('RGB'); new = new.convert('RGB')
            old.thumbnail((400, 400), Image.Resampling.LANCZOS)
            new.save(cover, 'WEBP', quality=70)
            old.save(extra, 'WEBP', quality=45)
        applied[ident] = key; done += 1
    Path('auto-covers-applied.json').write_text(json.dumps(applied, separators=(',', ':')))
    print(json.dumps({'swapped': done, 'skipped': skipped, 'total_applied': len(applied)}))

if __name__ == '__main__':
    main()
