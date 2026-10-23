"""Fotos limpias para ropa de marca: descarta fotos con letras chinas o rótulos de catálogo
(por ejemplo "MODEL WEAR", "PRODUCT DISPLAY") y prefiere la foto principal del álbum."""
import re
from PIL import Image

CH = re.compile(r'[一-鿿]')
BANNER = re.compile(r'^(model|wear|display|product|detail|details|colou?r|size|chart|show|shows|new|hot|sale|real|shot|photo)$', re.I)


_OCR = None


def _ocr():
    global _OCR
    if _OCR is None:
        from rapidocr_onnxruntime import RapidOCR
        _OCR = RapidOCR()
    return _OCR


def text_marks(im):
    """(caracteres chinos seguros, palabras de rótulo) que el OCR encuentra en la foto."""
    import numpy as np
    im = im.convert('RGB'); w, h = im.size
    if max(w, h) < 900:
        k = 900 / max(w, h); im = im.resize((int(w * k), int(h * k)))
    result, _ = _ocr()(np.asarray(im)[:, :, ::-1])
    chinese = banner = 0
    for _box, text, conf in result or []:
        if float(conf) < 0.6: continue
        chinese += len(CH.findall(text))
        banner += sum(1 for word in re.findall(r'[A-Za-z]+', text) if BANNER.match(word))
    return chinese, banner


def has_text(im):
    try:
        chinese, banner = text_marks(im)
    except Exception:
        return True
    return chinese >= 2 or banner >= 2


def pick(images, seller_index, approved, max_photos):
    """approved: índices ya aprobados por la revisión general. Devuelve [portada, ...] sin fotos con texto."""
    order = ([seller_index] if seller_index in approved else []) + [i for i in approved if i != seller_index]
    clean = []
    for i in order:
        if not has_text(images[i]): clean.append(i)
        if len(clean) >= max_photos: break
    return clean
