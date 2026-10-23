"""Evalúa el detector de texto sobre las portadas de ropa de marca. Solo publica ids."""
import json, sys
from pathlib import Path
from PIL import Image
sys.path.insert(0, 'scripts')
from casual_photos import text_marks
items = json.loads(Path('catalog.json').read_text())
out = {}
for p in items:
    if p['id'].isdigit() and int(p['id']) >= 17240 and not p.get('team') and p.get('cover'):
        with Image.open(Path('images') / p['cover']) as im:
            out[p['id']] = list(text_marks(im))
Path('casual-ocr-eval.json').write_text(json.dumps(out))
