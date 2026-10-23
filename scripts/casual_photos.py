"""Fotos limpias para ropa de marca: descarta fotos con letras chinas o rótulos de catálogo
(por ejemplo "MODEL WEAR", "PRODUCT DISPLAY") y prefiere la foto principal del álbum."""
import csv, io, re, subprocess, tempfile
from PIL import Image

CH = re.compile(r'[一-鿿]')
BANNER = re.compile(r'^(model|wear|display|product|detail|details|colou?r|size|chart|show|shows|new|hot|sale|real|shot|photo)$', re.I)


def text_marks(im):
    """(caracteres chinos seguros, palabras de rótulo) que el OCR encuentra en la foto."""
    im = im.convert('RGB'); w, h = im.size
    scale = 1000 / max(w, h)
    if scale > 1.05 or scale < 0.95: im = im.resize((int(w * scale), int(h * scale)))
    with tempfile.NamedTemporaryFile(suffix='.png') as f:
        im.save(f.name)
        r = subprocess.run(['tesseract', f.name, 'stdout', '-l', 'chi_sim+eng', '--psm', '11', 'tsv'],
                           capture_output=True, text=True, timeout=40, env={'OMP_THREAD_LIMIT': '1', 'PATH': '/usr/bin:/bin'})
    chinese = banner = 0
    for row in csv.DictReader(io.StringIO(r.stdout), delimiter='\t', quoting=csv.QUOTE_NONE):
        t = (row.get('text') or '').strip()
        try: conf = float(row.get('conf', -1))
        except ValueError: conf = -1
        if conf >= 65: chinese += len(CH.findall(t))
        if conf >= 80 and BANNER.match(t): banner += 1
    return chinese, banner


def has_text(im):
    try:
        chinese, banner = text_marks(im)
    except Exception:
        return False
    return chinese >= 2 or banner >= 2


def pick(images, seller_index, approved, max_photos):
    """approved: índices ya aprobados por la revisión general. Devuelve [portada, ...] sin fotos con texto."""
    clean = [i for i in approved if not has_text(images[i])]
    if not clean: return []
    order = ([seller_index] if seller_index in clean else []) + [i for i in clean if i != seller_index]
    return order[:max_photos]
