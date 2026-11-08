"""Revisa TODAS las portadas visibles (ropa): si la portada es un acercamiento (manga, cuello, escudo, tela) o la
espalda, busca en la galería una foto de frente con la prenda completa y la cambia. Si no hay ninguna mejor,
marca el producto con weak=true: la tienda lo deja al final del orden (no se oculta ni se borra).
Nunca toca portadas elegidas a mano (portadas.json). Guarda cover-audit.json con el resumen."""
import json, os
from pathlib import Path
from PIL import Image
import torch
from transformers import CLIPModel, CLIPProcessor

GOOD = ['a front view photo of a whole football shirt', 'a front view photo of a whole t-shirt on a hanger',
        'a photo of a whole jacket seen from the front', 'a photo of a whole tracksuit laid out flat',
        'a photo of a whole sports outfit with shirt and shorts', 'a photo of a person wearing a sports shirt facing the camera']
BAD = ['the back of a football shirt showing a name and number', 'a close-up of a shirt collar', 'a close-up of a sleeve cuff',
       'a close-up of a logo or crest on fabric', 'a close-up of fabric texture', 'a close-up of a size label']
model = CLIPModel.from_pretrained('openai/clip-vit-base-patch32').eval(); proc = CLIPProcessor.from_pretrained('openai/clip-vit-base-patch32')
with torch.no_grad():
    t = model.get_text_features(**proc(text=GOOD + BAD, return_tensors='pt', padding=True)); t = t / t.norm(dim=-1, keepdim=True)

def scores(paths):
    out = []
    for i in range(0, len(paths), 32):
        ims = []
        for p in paths[i:i + 32]:
            try: ims.append(Image.open(p).convert('RGB'))
            except Exception: ims.append(Image.new('RGB', (64, 64)))
        with torch.no_grad():
            f = model.get_image_features(**proc(images=ims, return_tensors='pt')); f = f / f.norm(dim=-1, keepdim=True)
            pr = (100 * f @ t.T).softmax(dim=-1)
        out += [float(x[:len(GOOD)].sum()) for x in pr]
    return out

items = json.loads(Path('catalog.json').read_text()); states = json.loads(Path('estado.json').read_text())
manual = set(json.loads(Path('portadas.json').read_text())); extras = Path('gallery-extra/images')
todo = [p for p in items if p.get('cover') and states.get(p['id'], p.get('status')) != 'hidden'
        and p.get('categorySlug') not in ('calzado', 'accesorios') and p['id'] not in manual]
cover_sc = dict(zip([p['id'] for p in todo], scores([Path('images') / p['cover'] for p in todo])))
swapped = weak = 0
APPLY = os.environ.get('APPLY') == 'true'; MIN_NEW = float(os.environ.get('MIN_NEW', '0.95')); MAX_OLD = float(os.environ.get('MAX_OLD', '0.25'))
log = {}
for p in todo:
    p.pop('weak', None)
    sc = cover_sc[p['id']]
    if sc >= 0.5: continue
    gal = [k for k in p.get('gallery') or [] if (extras / k).exists()]
    gs = scores([extras / k for k in gal]) if gal else []
    best = max(range(len(gs)), key=lambda i: gs[i]) if gs else None
    log[p['id']] = {'cover': round(sc, 3), 'best': gal[best] if best is not None else None, 'best_sc': round(gs[best], 3) if best is not None else None}
    if not APPLY: continue
    if best is not None and sc < MAX_OLD and gs[best] >= MIN_NEW:
        new = gal[best]
        with Image.open(extras / new) as im:
            im = im.convert('RGB'); im.thumbnail((500, 500)); im.save(Path('images') / p['cover'], 'WEBP', quality=75)
        p['gallery'] = [k for k in p['gallery'] if k != new]; swapped += 1
    else:
        p['weak'] = True; weak += 1
Path('catalog.json').write_text(json.dumps(items, ensure_ascii=False, separators=(',', ':')))
Path('cover-audit-scores.json').write_text(json.dumps(log))
Path('cover-audit.json').write_text(json.dumps({'checked': len(todo), 'swapped': swapped, 'weak': weak}))
print(swapped, weak)
