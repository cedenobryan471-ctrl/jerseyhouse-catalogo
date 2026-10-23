"""Portadas de prenda completa para ropa de marca: si la portada es un acercamiento (puño, cordón,
tela, logo), se cambia por la foto del producto donde mejor se ve la prenda completa.
Si ninguna foto muestra la prenda completa, el producto se oculta. Usa CLIP, sin entrenar."""
import json, os
from pathlib import Path
from PIL import Image
import torch
from transformers import CLIPModel, CLIPProcessor

APPLY = os.environ.get('APPLY') == 'true'
FULL = ['a product photo of a whole garment', 'a person wearing clothes', 'several garments laid out or hanging']
DETAIL = ['a close-up photo of fabric texture', 'a close-up of a sleeve cuff or collar or drawstring', 'a close-up of a logo or label']
model = CLIPModel.from_pretrained('openai/clip-vit-base-patch32').eval()
proc = CLIPProcessor.from_pretrained('openai/clip-vit-base-patch32')
with torch.no_grad():
    t = model.get_text_features(**proc(text=FULL + DETAIL, return_tensors='pt', padding=True)); t = t / t.norm(dim=-1, keepdim=True)

def full_scores(paths):
    ims = []
    for p in paths:
        try: ims.append(Image.open(p).convert('RGB'))
        except Exception: ims.append(None)
    ok = [im for im in ims if im is not None]
    if not ok: return [0.0] * len(paths)
    with torch.no_grad():
        f = model.get_image_features(**proc(images=ok, return_tensors='pt')); f = f / f.norm(dim=-1, keepdim=True)
        prob = (100 * f @ t.T).softmax(dim=-1)
    it = iter(prob); return [round(float(next(it)[:len(FULL)].sum()), 3) if im is not None else 0.0 for im in ims]

items = json.loads(Path('catalog.json').read_text()); extras = Path('gallery-extra/images')
todo = [p for p in items if p.get('sectionSlug') in ('ropa-casual',) and p.get('cover') and not p.get('team') and p.get('status') != 'hidden']
report = {'checked': len(todo), 'changed': [], 'hidden': []}
for p in todo:
    gallery = p.get('gallery') or []
    s = full_scores([Path('images') / p['cover']] + [extras / k for k in gallery])
    if s[0] >= 0.5: continue
    best = max(range(1, len(s)), key=lambda i: s[i], default=None)
    if best is None or s[best] < 0.5:
        report['hidden'].append(p['id'])
        if APPLY: p['status'] = 'hidden'
        continue
    report['changed'].append(p['id'])
    if APPLY:
        new = gallery[best - 1]
        old = Path('images') / p['cover']
        with Image.open(extras / new) as im: im.convert('RGB').save(old, 'WEBP', quality=75)
        p['gallery'] = [k for k in gallery if k != new]
Path('full-covers.json').write_text(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in report.items()} | {'changed_ids': report['changed'], 'hidden_ids': report['hidden']}))
if APPLY: Path('catalog.json').write_text(json.dumps(items, ensure_ascii=False, separators=(',', ':')))
