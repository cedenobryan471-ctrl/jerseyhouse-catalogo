"""Compara la portada con las fotos de la galería (CLIP) y cambia la portada cuando una foto de la galería
muestra mucho mejor la prenda completa. Solo para los ids en cover-swap-ids.json; nunca toca portadas elegidas a mano."""
import json
from pathlib import Path
from PIL import Image
import torch
from transformers import CLIPModel, CLIPProcessor
FULL = ['a photo of a whole t-shirt hanging on a hanger', 'a photo of a whole football shirt laid flat', 'a photo of a whole jacket']
DETAIL = ['a close-up of a logo or crest on fabric', 'a close-up of a shirt collar', 'a close-up of a sleeve', 'a close-up of fabric texture']
model = CLIPModel.from_pretrained('openai/clip-vit-base-patch32').eval(); proc = CLIPProcessor.from_pretrained('openai/clip-vit-base-patch32')
with torch.no_grad():
    t = model.get_text_features(**proc(text=FULL + DETAIL, return_tensors='pt', padding=True)); t = t / t.norm(dim=-1, keepdim=True)
def scores(paths):
    ims = [Image.open(p).convert('RGB') for p in paths]
    with torch.no_grad():
        f = model.get_image_features(**proc(images=ims, return_tensors='pt')); f = f / f.norm(dim=-1, keepdim=True)
        pr = (100 * f @ t.T).softmax(dim=-1)
    return [float(x[:len(FULL)].sum()) for x in pr]
ids = set(json.loads(Path('cover-swap-ids.json').read_text()))
manual = set(json.loads(Path('portadas.json').read_text()))
items = json.loads(Path('catalog.json').read_text()); extras = Path('gallery-extra/images'); changed = []
for p in items:
    if p['id'] not in ids or p['id'] in manual: continue
    gal = [k for k in p.get('gallery') or [] if (extras / k).exists()]
    if not gal: continue
    sc = scores([Path('images') / p['cover']] + [extras / k for k in gal])
    best = max(range(1, len(sc)), key=lambda i: sc[i])
    if sc[0] < 0.5 and sc[best] - sc[0] > 0.3:
        new = gal[best - 1]
        with Image.open(extras / new) as im:
            im = im.convert('RGB'); im.thumbnail((500, 500)); im.save(Path('images') / p['cover'], 'WEBP', quality=75)
        p['gallery'] = [k for k in p['gallery'] if k != new]; changed.append(p['id'])
Path('catalog.json').write_text(json.dumps(items, ensure_ascii=False, separators=(',', ':')))
Path('cover-swap-result.json').write_text(json.dumps({'checked': len(ids), 'changed': len(changed)}))
