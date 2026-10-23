"""Revisa en privado una fuente nueva: cuenta álbumes y guarda una muestra de títulos SOLO cifrada.
La dirección viene del secreto FUENTE_NUEVA y nunca se escribe en archivos públicos."""
import json, os, random, sys
sys.path.insert(0, 'scripts')
from sports_import import Site, collect, album_raw

url = (os.environ.get('FUENTE_NUEVA') or '').strip()
if not url:
    print(json.dumps({'status': 'sin_secreto'})); sys.exit(0)
site = Site(url)
albums = collect(site, 'probe')
random.seed(7)
sample = random.sample(albums, min(150, len(albums)))
rows = []
for aid, aurl, ctx in sample[:150]:
    raw = ''
    if len(rows) < 40:
        try: raw = album_raw(site.page(aurl))
        except Exception: raw = ''
    rows.append({'ctx': ctx[:120], 'raw': raw[:200]})
os.makedirs('/tmp/probe', exist_ok=True)
json.dump(rows, open('/tmp/probe/sample.json', 'w'), ensure_ascii=False)
print(json.dumps({'status': 'ok', 'albums': len(albums)}))
