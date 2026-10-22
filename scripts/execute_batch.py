"""Bounded imports with privacy validation of public data, not rule dictionaries."""
import re,json,os
from pathlib import Path
import run_batch as b
original=b.is_footwear
def safe_footwear(title):
 if re.search(r'copa\s+(?:am[eé]rica|del\s+rey)|championship',title,re.I):return False
 return original(title)
b.is_footwear=safe_footwear
original_classify=b.classify
def classify(title,previous='',team=None):
 if team and previous not in ('calzado','tenis','tacos'):
  saved=b.is_footwear;b.is_footwear=lambda t:False
  try:return original_classify(title,previous,team)
  finally:b.is_footwear=saved
 return original_classify(title,previous,team)
b.classify=classify
original_title=b.generic_title
def repaired_title(text,team=None):
 repairs={'Golden State Warriors':[('dorado State Warriors','Golden State Warriors')],'Red Bull Racing':[('rojo Bull','Red Bull')],'New York Red Bulls':[('New York rojo Bulls','New York Red Bulls')],'Orlando City':[('Orlando ciudad','Orlando City')]}
 for damaged,proper in repairs.get(team,[]):text=re.sub(re.escape(damaged),proper,text,flags=re.I)
 return original_title(text,team)
b.generic_title=repaired_title
old_photo=b.r.old.photo
def photo(candidates,dest):
 return any(old_photo(candidates[i:i+4],dest) for i in range(0,min(len(candidates),16),4))
b.r.old.photo=photo

def audit(items):
 remaining=0
 for p in items:
  for k,v in p.items():
   if k in ('id','slug','cover'):continue
   for s in v if isinstance(v,list) else [v]:
    if isinstance(s,str):remaining+=sum(len(pattern.findall(s)) for pattern in (b.r.old.PATTERN,b.r.old.ADDR,b.r.old.PHONE,b.r.old.CHINESE))
 b.r.old.COUNTS['remaining']=remaining
 if remaining:raise ValueError('public_data_privacy')
 hosts=[b.urlparse(source['url']).netloc for source in b.r.old.CONFIG['sources']]
 for path in Path('scripts').glob('*.py'):
  if any(host and host in path.read_text() for host in hosts):raise ValueError('source_reference')
 if sum(p.stat().st_size for p in Path('images').glob('*.webp'))+len(json.dumps(items).encode())>=800_000_000:raise ValueError('size_limit')
b.r.old.audit=audit

def main():
 all_sources=b.r.old.CONFIG['sources'];reports=[]
 if os.environ.get('REFRESH_SCOPE')!='footwear':
  items=json.loads(Path('catalog.json').read_text());existing={b.r.key(p) for p in items};known={p['team']:p for p in items if p.get('team')};lock=b.threading.Lock();counter=[max(int(p['id']) for p in items)+1]
  for league,names in [('NFL',b.r.old.NFL_TEAMS),('NHL',b.r.old.NHL_TEAMS),('Fórmula 1',list(b.r.old.RACING))]:
   for name in names:known.setdefault(name,{'team':name,'league':league})
  progress=json.loads(Path('batch-progress.json').read_text()) if Path('batch-progress.json').exists() else {}
  for number,source in enumerate(all_sources,1):
   if source.get('mode')=='shoes':continue
   key=b.hashlib.sha256(source['url'].encode()).hexdigest()[:20];start=progress.get(key,0);counts={'listing':0,'album':0}
   def limited_get(url):
    if re.search(r'/albums/\d+',b.urlparse(url).path):
     index=counts['album'];counts['album']+=1
     if not start<=index<start+8:raise ValueError('batch_skip')
    else:
     counts['listing']+=1
     if counts['listing']>8:raise ValueError('batch_skip')
    return b.get(url)
   b.r.old.get=limited_get
   try:reports.append(b.r.refresh_source(items,number,source,existing,known,lock,counter))
   finally:b.r.old.get=b.get
   progress[key]=start+8 if counts['album']>start+8 else 0
  Path('catalog.json').write_text(json.dumps(items,ensure_ascii=False,separators=(',',':')));Path('batch-progress.json').write_text(json.dumps(progress))
 # El calzado lo carga footwear_import.py (workflow 'Cargar calzado'); aquí no, para no duplicar.
 b.r.old.CONFIG['sources']=[]
 b.main()
 if reports:
  result=json.loads(Path('resultado.json').read_text());result['sources']=reports+result['sources'];result['added']+=sum(r['added'] for r in reports);Path('resultado.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':
 try:main()
 except Exception as error:print('Catalog batch failed safely:',type(error).__name__);raise SystemExit(1)
