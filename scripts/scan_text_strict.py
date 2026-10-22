"""Segunda revisión estricta: solo marca fotos con un rótulo chino claro (3+ caracteres
seguros en la franja superior), para no ocultar camisetas por errores del OCR en la tela."""
import json, re, subprocess, tempfile, csv, io
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image

CH = re.compile(r'[一-鿿]')

def chinese_chars(path, psm):
    r = subprocess.run(['tesseract', path, 'stdout', '-l', 'chi_sim', '--psm', str(psm), 'tsv'], capture_output=True, text=True, timeout=30)
    n = 0
    for row in csv.DictReader(io.StringIO(r.stdout), delimiter='\t'):
        t = (row.get('text') or '').strip()
        try: conf = float(row.get('conf', -1))
        except ValueError: conf = -1
        if conf >= 75: n += len(CH.findall(t))
    return n

def check(ident, cover):
    try:
        return _check(ident, cover)
    except Exception:
        return ident, False

def _check(ident, cover):
    with Image.open(Path('images') / cover) as im:
        im = im.convert('RGB'); w, h = im.size
        band = im.crop((0, 0, w, int(h * 0.35))).resize((w * 2, int(h * 0.35) * 2))
        with tempfile.NamedTemporaryFile(suffix='.png') as f:
            band.save(f.name)
            a = chinese_chars(f.name, 6); b = chinese_chars(f.name, 11) if a >= 3 else 0
    return ident, a >= 3 and b >= 3

def main():
    flagged = json.loads(Path('portadas-con-texto.json').read_text())['rejected']
    items = {p['id']: p for p in json.loads(Path('catalog.json').read_text())}
    todo = [(i, items[i]['cover']) for i in flagged if i in items and items[i].get('cover')]
    with ThreadPoolExecutor(max_workers=4) as pool:
        result = [i for i, bad in pool.map(lambda t: check(*t), todo) if bad]
    keep_reasons = [i for i, r in flagged.items() if r in ('phone', 'link', 'contact')]
    Path('portadas-con-texto-estricto.json').write_text(json.dumps({'checked': len(todo), 'chinese_label': result, 'contact_or_link': keep_reasons}, indent=1))

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        Path('portadas-con-texto-estricto.json').write_text(json.dumps({'fatal': type(error).__name__}))
