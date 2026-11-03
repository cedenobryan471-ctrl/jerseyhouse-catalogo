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
full = os.environ.get('PROBE_FULL') == '1'
sample = albums if full else random.sample(albums, min(150, len(albums)))
def fetch(entry):
    aid, aurl, ctx = entry
    try: return {'ctx': ctx[:120], 'raw': album_raw(site.page(aurl))[:200]}
    except Exception: return {'ctx': ctx[:120], 'raw': ''}
if full:
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as pool: rows = list(pool.map(fetch, sample))
else:
    rows = [fetch(e) if i < 40 else {'ctx': e[2][:120], 'raw': ''} for i, e in enumerate(sample[:150])]
os.makedirs('/tmp/probe', exist_ok=True)
json.dump(rows, open('/tmp/probe/sample.json', 'w'), ensure_ascii=False)
print(json.dumps({'status': 'ok', 'albums': len(albums)}))
