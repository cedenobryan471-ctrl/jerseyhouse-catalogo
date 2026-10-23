"""Marca prendas de ropa de marca donde una mujer aparece en las fotos (sola o en pareja).
Usa CLIP (comparación imagen/texto, sin entrenar nada). Solo escribe ids y puntajes."""
import json, os, sys
from pathlib import Path
from PIL import Image
import torch
from transformers import CLIPModel, CLIPProcessor

APPLY = os.environ.get('APPLY') == 'true'
LABELS = ['a photo of a woman wearing clothes', 'a photo of a man wearing clothes',
          'a photo of a man and a woman wearing clothes', 'a photo of clothes with no person']
model = CLIPModel.from_pretrained('openai/clip-vit-base-patch32').eval()
proc = CLIPProcessor.from_pretrained('openai/clip-vit-base-patch32')
with torch.no_grad():
    text = model.get_text_features(**proc(text=LABELS, return_tensors='pt', padding=True))
    text = text / text.norm(dim=-1, keepdim=True)

def scores(paths):
    ims = []
    for p in paths:
        try: ims.append(Image.open(p).convert('RGB'))
        except Exception: pass
    if not ims: return []
    with torch.no_grad():
        f = model.get_image_features(**proc(images=ims, return_tensors='pt'))
        f = f / f.norm(dim=-1, keepdim=True)
        prob = (100 * f @ text.T).softmax(dim=-1)
    return [round(float(r[0] + r[2]), 3) for r in prob]

items = json.loads(Path('catalog.json').read_text())
extras = Path('gallery-extra/images')
todo = [p for p in items if p.get('sectionSlug') == 'ropa-casual' and p.get('cover') and p['categorySlug'] != 'faldas' and not p.get('womanPhoto') and 'nino' not in p['audiences']]
out = {}
for p in todo:
    paths = [Path('images') / p['cover']] + [extras / k for k in p.get('gallery') or []]
    out[p['id']] = scores(paths)
Path('women-photos.json').write_text(json.dumps(out))
if APPLY:
    marked = 0
    for p in todo:
        s = out.get(p['id']) or []
        if s and max(s) >= 0.6:
            p['womanPhoto'] = True; marked += 1
            if 'mujer' not in p['audiences']: p['audiences'] = p['audiences'] + ['mujer']
            j = max(range(len(s)), key=lambda i: s[i]); g = p.get('gallery') or []
            if s[0] < 0.6 and 0 < j <= len(g): p['womanImage'] = g[j - 1]
    Path('catalog.json').write_text(json.dumps(items, ensure_ascii=False, separators=(',', ':')))
    print('marcadas', marked)
