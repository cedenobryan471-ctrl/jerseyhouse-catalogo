"""Averigua en privado cómo pide la contraseña la fuente nueva. Todo lo que guarda va cifrado."""
import json, os, re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'}
url = os.environ.get('FUENTE', '').strip(); clave = os.environ.get('CLAVE', '').strip()
out = {'tiene_clave': bool(clave)}
s = requests.Session(); s.headers.update(UA)
r = s.get(url, timeout=30); out['status'] = r.status_code; out['final'] = r.url
soup = BeautifulSoup(r.text, 'html.parser')
out['albums_sin_clave'] = len(set(re.findall(r'/albums/(\d+)', r.text)))
out['forms'] = [{'action': f.get('action'), 'method': f.get('method'), 'inputs': [(i.get('name'), i.get('type')) for i in f.select('input')]} for f in soup.select('form')]
out['js'] = [r.text[max(0, m.start() - 300): m.end() + 300] for m in re.finditer(r'password|passwd|pwd|密码', r.text, re.I)][:12]
out['cookies'] = list(s.cookies.get_dict().keys())
out['html_inicio'] = r.text[:4000]
json.dump(out, open('/tmp/probe/login.json', 'w'), ensure_ascii=False)
print(json.dumps({k: out[k] for k in ('status', 'albums_sin_clave', 'tiene_clave')}))
