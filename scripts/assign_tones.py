"""Calcula `tones` (color principal y secundario) para chaquetas, conjuntos y buzos nuevos.
Solo toca productos sin `tones`; los que ya tienen color (o se corrigieron a mano) no se cambian.
Usa solo Pillow: quita el fondo comparando con el color de los bordes de la foto."""
import json, os, sys
from PIL import Image

SECTIONS = ('chaquetas', 'conjuntos', 'buzos')
GROUP = {'verde oscuro': 'verde', 'oliva': 'verde', 'blanco roto': 'blanco', 'gris oscuro': 'negro',
         'azul oscuro': 'azul', 'azul marino': 'azul'}
NAMES = {'verde oscuro': (35, 75, 50), 'oliva': (105, 110, 65), 'blanco roto': (220, 215, 200), 'gris oscuro': (60, 60, 65),
         'azul oscuro': (30, 45, 110), 'negro': (30, 30, 30), 'blanco': (235, 235, 235), 'gris': (140, 140, 140),
         'rojo': (200, 30, 40), 'vino': (120, 25, 40), 'naranja': (240, 120, 30), 'amarillo': (240, 210, 40),
         'verde': (30, 140, 60), 'azul': (30, 70, 190), 'azul marino': (25, 35, 80), 'celeste': (110, 170, 230),
         'morado': (110, 50, 150), 'rosado': (240, 140, 180)}


def _lab(rgb):
    def f(c):
        c /= 255
        return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92
    r, g, b = (f(float(v)) for v in rgb)
    x, y, z = (r * .4124 + g * .3576 + b * .1805) / .9505, r * .2126 + g * .7152 + b * .0722, (r * .0193 + g * .1192 + b * .9505) / 1.089
    h = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return 116 * h(y) - 16, 500 * (h(x) - h(y)), 200 * (h(y) - h(z))


REF = {n: _lab(c) for n, c in NAMES.items()}


def tones_of(path):
    im = Image.open(path).convert('RGB').resize((96, 96))
    px = list(im.getdata())
    w = 96
    border = [px[i] for i in range(len(px)) if i < w * 3 or i >= len(px) - w * 3 or i % w < 3 or i % w >= w - 3]
    bg = tuple(sorted(c[k] for c in border)[len(border) // 2] for k in range(3))
    fg = [c for i, c in enumerate(px) if 16 <= i % w < w - 16 and sum((c[k] - bg[k]) ** 2 for k in range(3)) > 1600]
    if len(fg) < 400:
        fg = px
    counts = {}
    for c in fg[::2]:
        L = _lab(c)
        n = min(REF, key=lambda r: sum((L[k] - REF[r][k]) ** 2 for k in range(3)))
        g = GROUP.get(n, n)
        counts[g] = counts.get(g, 0) + 1
    order = sorted(counts, key=counts.get, reverse=True)
    tot = sum(counts.values())
    out = [order[0]]
    if len(order) > 1 and counts[order[1]] / tot > 0.3:
        out.append(order[1])
    return out


def main(catalog='catalog.json', images='images', force=False):
    c = json.load(open(catalog))
    done = 0
    for p in c:
        if p.get('categorySlug') not in SECTIONS or not p.get('cover') or (p.get('tones') and not force):
            continue
        path = os.path.join(images, p['cover'])
        if not os.path.exists(path):
            continue
        try:
            p['tones'] = tones_of(path)
            done += 1
        except Exception:
            pass
    if done and not force:
        json.dump(c, open(catalog, 'w'), ensure_ascii=False, separators=(',', ':'))
    print('colores asignados:', done)
    return c


if __name__ == '__main__':
    main()
