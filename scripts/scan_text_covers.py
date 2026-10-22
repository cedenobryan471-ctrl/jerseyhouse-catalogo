"""Revisa con OCR todas las portadas visibles y lista las que tienen letras chinas, teléfonos o links."""
import json, os, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image
sys.path.insert(0, 'scripts')
from photo_policy import review_image

def main():
    config = json.loads(os.environ.get('CATALOG_CONFIG') or '{}'); terms = config.get('blocked_terms', [])
    items = json.loads(Path('catalog.json').read_text()); states = json.loads(Path('estado.json').read_text())
    todo = [p for p in items if states.get(p['id'], p['status']) != 'hidden' and p.get('cover') and (Path('images') / p['cover']).exists()]
    def check(p):
        try:
            with Image.open(Path('images') / p['cover']) as im: outcome, reason = review_image(im.convert('RGB'), terms)
        except Exception: outcome, reason = 'error', None
        return p['id'], outcome, reason
    found = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for ident, outcome, reason in pool.map(check, todo):
            if outcome == 'rejected': found[ident] = reason
    Path('portadas-con-texto.json').write_text(json.dumps({'checked': len(todo), 'rejected': found}, indent=1))

if __name__ == '__main__':
    main()
