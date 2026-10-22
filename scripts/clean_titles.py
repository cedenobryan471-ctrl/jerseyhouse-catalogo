"""Quita del nombre textos de proveedor y basura de codificación, sin IA."""
import json, re, sys
from pathlib import Path

GARBAGE = re.compile(r'\S*[Ꭰ-᏿ꭰ-ꮿﹰ-﻿]+\S*')
FIXES = [
    (r'\brojo\s+bulls\b', 'Red Bulls'), (r'\brojo\s+bull\b', 'Red Bull'),
    (r'\bdorado\s+state\s+warriors\b', 'Golden State Warriors'),
]
JUNK = [
    r'\bfor\s+sale\b', r'\bcheap\b', r'\bwholesale\b', r'\bsupply\b', r'\bapparels?\b',
    r'\bf[úu]tbol\s+jerseys?\b', r'\bjerseys\b', r'\bf[úu]tbol\s+uniforms?\b', r'\buniforms?\b',
    r'\b(?:size\s*:?\s*)?(?:xs|s|m)-(?:xxl|[2-5]xl)\b', r'\(\d\)', r'\bdropship(?:p?ing)?\b', r'\bunifrom\b', r'\bbest\b(?=\s*$)',
]
TAIL = re.compile(r'(?:\s+(?:for|de|con|y|&))+$', re.I)

def clean_title(title):
    t = GARBAGE.sub(' ', title or '')
    for pattern, repl in FIXES:
        t = re.sub(pattern, repl, t, flags=re.I)
    for pattern in JUNK:
        t = re.sub(pattern, ' ', t, flags=re.I)
    t = t.replace('&#x27;', "'").replace('&amp;', '&')
    if not re.fullmatch(r'\s*Camiseta de f[úu]tbol\s*', t):
        t = re.sub(r'\bCamiseta de f[úu]tbol\b', 'Camiseta', t)
        if not re.search(r'bal[oó]n', t, re.I): t = re.sub(r'(?<=\S)\s+f[úu]tbol\b', ' ', t)
    t = re.sub(r'\b(Camiseta|Chaqueta|Pantaloneta|Kit|Polo)(?:\s+\1\b)+', r'\1', t, flags=re.I)  # prenda repetida
    t = re.sub(r'\s+', ' ', t).strip(' -_|,&')
    t = TAIL.sub('', t).strip(' -_|,&')
    return t or (title or '').strip()

def main(path='catalog.json'):
    products = json.loads(Path(path).read_text())
    changed = 0
    for product in products:
        new = clean_title(product.get('title'))
        if new != product.get('title'):
            product['title'] = new; changed += 1
    Path(path).write_text(json.dumps(products, ensure_ascii=False, separators=(',', ':')))
    print(json.dumps({'titles_cleaned': changed}))

if __name__ == '__main__':
    main(*sys.argv[1:])
