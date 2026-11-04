"""Camisetas de entrenamiento y polos que en la foto vienen con pantaloneta o pantalón (conjunto):
pasan a la categoría Conjuntos y el nombre cambia de "Camiseta de entrenamiento" a "Conjunto de entrenamiento".
Usa CLIP sin entrenar. Guarda la lista en sets-moved.json para poder revertir."""
import json, os, re
from pathlib import Path
from PIL import Image
import torch
from transformers import CLIPModel, CLIPProcessor

APPLY = os.environ.get('APPLY') == 'true'
SET = ['a photo of a sports shirt together with shorts', 'a photo of a tracksuit jacket together with long pants',
       'a photo of a polo shirt together with pants', 'a photo of a sleeveless vest together with shorts']
SINGLE = ['a photo of a single t-shirt alone', 'a photo of a single jacket alone', 'a close-up photo of a shirt collar or logo']
model = CLIPModel.from_pretrained('openai/clip-vit-base-patch32').eval()
proc = CLIPProcessor.from_pretrained('openai/clip-vit-base-patch32')
with torch.no_grad():
    t = model.get_text_features(**proc(text=SET + SINGLE, return_tensors='pt', padding=True)); t = t / t.norm(dim=-1, keepdim=True)

items = json.loads(Path('catalog.json').read_text())
states = json.loads(Path('estado.json').read_text())
todo = [p for p in items if p.get('categorySlug') == 'camisetas' and p.get('cover') and states.get(p['id']) != 'hidden'
        and (p.get('version') == 'entrenamiento' or re.match(r'Polo\b', p['title']))]
moved = {}
for i in range(0, len(todo), 32):
    chunk = todo[i:i + 32]; ims = []
    for p in chunk:
        try: ims.append(Image.open(Path('images') / p['cover']).convert('RGB'))
        except Exception: ims.append(Image.new('RGB', (64, 64)))
    with torch.no_grad():
        f = model.get_image_features(**proc(images=ims, return_tensors='pt')); f = f / f.norm(dim=-1, keepdim=True)
        prob = (100 * f @ t.T).softmax(dim=-1)
    for p, pr in zip(chunk, prob):
        score = float(pr[:len(SET)].sum())
        if score < 0.7: continue
        old = p['title']
        new = re.sub(r'^Camiseta de entrenamiento', 'Conjunto de entrenamiento', old)
        new = re.sub(r'^Polo\b', 'Conjunto polo', new)
        if new == old: new = 'Conjunto ' + old[0].lower() + old[1:]
        moved[p['id']] = {'title': old, 'score': round(score, 2)}
        if APPLY: p['title'] = new; p['categorySlug'] = 'conjuntos'; p['category'] = 'Conjuntos'
report = {'checked': len(todo), 'moved': len(moved)}
Path('sets-result.json').write_text(json.dumps(report))
if APPLY:
    prev = json.loads(Path('sets-moved.json').read_text()) if Path('sets-moved.json').exists() else {}
    Path('sets-moved.json').write_text(json.dumps(prev | moved, ensure_ascii=False))
    Path('catalog.json').write_text(json.dumps(items, ensure_ascii=False, separators=(',', ':')))
else:
    Path('sets-preview.json').write_text(json.dumps(sorted(moved)))
