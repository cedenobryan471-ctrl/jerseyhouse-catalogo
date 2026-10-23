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

def dhash(path):
    try:
        with Image.open(path) as im:
            g = im.convert('L').resize((9, 8)); px = list(g.getdata())
    except Exception:
        return None
    return tuple(px[r * 9 + c] > px[r * 9 + c + 1] for r in range(8) for c in range(8))

items = json.loads(Path('catalog.json').read_text()); extras = Path('gallery-extra/images')
todo = [p for p in items if p.get('sectionSlug') == 'ropa-casual' and p.get('cover') and not p.get('team') and p.get('status') != 'hidden']
files = {p['id']: [Path('images') / p['cover']] + [extras / k for k in p.get('gallery') or []] for p in todo}
hashes = {pid: [dhash(x) for x in fs] for pid, fs in files.items()}
# Fotos genéricas: la misma imagen usada en 3 o más productos distintos (puños, cordones, tela).
seen = {}
for pid, hs in hashes.items():
    for h in set(x for x in hs if x):
        seen.setdefault(h, set()).add(pid)
generic = {h for h, ids in seen.items() if len(ids) >= 3}
report = {'checked': len(todo), 'generic_photos': len(generic), 'changed': [], 'hidden': [], 'trimmed': 0}
for p in todo:
    gallery = p.get('gallery') or []
    hs = hashes[p['id']]; sc = full_scores(files[p['id']])
    own = [i for i in range(len(sc)) if hs[i] not in generic]
    cover_ok = 0 in own and sc[0] >= 0.5
    keep_gallery = [gallery[i - 1] for i in own if i > 0]
    if cover_ok:
        if APPLY and len(keep_gallery) != len(gallery): p['gallery'] = keep_gallery
        report['trimmed'] += len(gallery) - len(keep_gallery)
        continue
    cands = [i for i in own if i > 0 and sc[i] >= 0.5]
    if not cands:
        report['hidden'].append(p['id'])
        if APPLY: p['status'] = 'hidden'
        continue
    best = max(cands, key=lambda i: sc[i]); new = gallery[best - 1]
    report['changed'].append(p['id'])
    if APPLY:
        with Image.open(extras / new) as im: im.convert('RGB').save(Path('images') / p['cover'], 'WEBP', quality=75)
        p['gallery'] = [k for k in keep_gallery if k != new]
Path('full-covers.json').write_text(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in report.items()} | {'changed_ids': report['changed'], 'hidden_ids': report['hidden']}))
if APPLY: Path('catalog.json').write_text(json.dumps(items, ensure_ascii=False, separators=(',', ':')))
