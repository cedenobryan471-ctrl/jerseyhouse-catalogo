"""Dice si alguna fuente (por hash del dueño) ya está en los secretos. Solo publica hashes cortos y sí/no."""
import json, os, re, hashlib
from urllib.parse import urlparse
def owner(u):
    u=u.strip()
    if not u: return None
    if '://' not in u: u='https://'+u
    o=urlparse(u); h=o.netloc.lower()
    m=re.search(r'/photos/([^/]+)', o.path)
    if h=='x.yupoo.com' and m: return m.group(1).lower()
    return h.split('.')[0]
def hs(x): return hashlib.sha256(x.encode()).hexdigest()[:12]
found={}
for name in ['CATALOG_CONFIG','SOURCES_CONFIG','FOOTWEAR_SOURCES_CONFIG','FUENTE_NUEVA','FUENTE_NUEVA_2','FUENTE_CALZADO']:
    v=os.environ.get(name,'') or ''
    for u in re.findall(r'(?:https?://)?[\w.-]+\.yupoo\.com[^\s"\']*', v):
        o=owner(u)
        if o: found.setdefault(hs(o),[]).append(name)
want=os.environ['HASHES'].split(',')
print(json.dumps({h: sorted(set(found.get(h,[]))) for h in want}))
print(json.dumps({'total_fuentes_en_secretos': len(found)}))
