import os,json,re,time,threading,io
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import requests
from pathlib import Path
from urllib.parse import urljoin,urlparse
from bs4 import BeautifulSoup
import catalog as old
from identities import identity,slug,norm
from footwear_rules import is_footwear,footwear_type,shoe_sizes,brand_of,footwear_key,translate
extra=[''.join(map(chr,c)) for c in [(114,101,115,101,108,108,101,114),(115,117,112,112,108,105,101,114),(115,117,112,108,108,105,101,114),(65,65,65)]]
old.TERMS+=extra
old.PATTERN=re.compile('|'.join(re.escape(x).replace(r'\-',r'[- _]?') for x in old.TERMS),re.I)
sources=json.loads(os.environ['SOURCES_CONFIG'])
footwear_sources=json.loads(os.environ.get('FOOTWEAR_SOURCES_CONFIG','[]'))
if footwear_sources:
 sources=[s for s in sources if s.get('mode')!='shoes']+footwear_sources
if os.environ.get('REFRESH_SCOPE')=='footwear':sources=footwear_sources
old.CONFIG['sources']=sources
CATS={'camisetas':'Camisetas','conjuntos':'Conjuntos','chaquetas':'Chaquetas','buzos':'Buzos y sudaderas','shorts':'Shorts y pantalones','calzado':'Calzado','bolsos':'Bolsos','otros':'Otros'}
def clean(s):
 s=str(s or '')
 for t in extra:s=re.sub(r'\bfor\s+'+re.escape(t)+r'\b','',s,flags=re.I)
 return old.clean(s)
def category(t):
 if is_footwear(t):return 'calzado'
 t=t.lower()
 if re.search(r'\bbags?\b|backpack|handbag|crossbody|wallet|bolso|mochila|\u80cc\u5305|\u5305',t):return 'bolsos'
 if re.search(r'tracksuit|ch[aá]ndal|\bsets?\b|2\s*-?\s*piece|\u5957\u88c5',t) or (re.search(r'\b(kit|suit)\b',t) and re.search(r'shorts?|pants|trousers|\u77ed\u88e4|\u957f\u88e4',t)):return 'conjuntos'
 if re.search(r'jacket|windbreaker|cortavientos|anthem|chaqueta|\u5939\u514b|\u5916\u5957|\u98ce\u8863',t):return 'chaquetas'
 if re.search(r'hoodie|sweatshirt|sweater|sudadera|buzo|\u536b\u8863',t):return 'buzos'
 if re.search(r'shorts?|pants|trousers|pantaloneta|pantal[oó]n|\u77ed\u88e4|\u957f\u88e4',t):return 'shorts'
 if re.search(r'jersey|shirt|training|vest|polo|camiseta|\u7403\u8863|\u7bee\u7403|\u80cc\u5fc3|\u77ed\u8896|\u957f\u8896',t):return 'camisetas'
 return 'otros'
def normalize(items):
 report={'names_changed':0,'league_moves':0,'unresolved_teams':0}
 for p in items:
  for k,v in list(p.items()):
   if k in ('id','slug','cover'):continue
   if isinstance(v,str):p[k]=clean(v)
   elif isinstance(v,list):p[k]=[clean(s) if isinstance(s,str) else s for s in v]
  if p.get('team'):
   matched=identity(p['title'],p.get('league')) if 'independiente de medellin' in norm(p['title']) else identity(p['team'],p.get('league'))
   if matched:
    name,league=matched;report['names_changed']+=name!=p['team'];report['league_moves']+=league!=p.get('league')
    p.update(team=name,teamSlug=slug(name),league=league,leagueSlug=slug(league))
   else:report['unresolved_teams']+=1;p.update(team=None,teamSlug=None)
  cat=category(p['title'])
  if cat in ('calzado','bolsos') or p.get('categorySlug') in ('tenis','tacos','calzado'):
   if cat!='bolsos':
    cat='calzado';p['title']=translate(p['title']) or p['title'];p['footwearType']=p.get('footwearType') or ('futbol' if p.get('categorySlug')=='tacos' else footwear_type(p['title']));p['sizes']=shoe_sizes(p['title'])
   p.update(categorySlug=cat,category=CATS[cat],team=None,teamSlug=None,league=None,leagueSlug=None)
   p['brand']=brand_of(p['title'])
 return report
def title_of(page):
 h=page.select_one('.showalbumheader__gallerytitle') or page.select_one('.showalbumheader__title') or page.select_one('h1:not(.visually-hidden)') or page.select_one('title')
 return re.split(r'\s*\|\s*',h.get_text(' ',strip=True))[0] if h else ''
def key(p):
 cat=p.get('categorySlug')
 if cat=='calzado':return ('calzado',*footwear_key(p))
 if cat=='bolsos':return p.get('brand'),cat,norm(p.get('title'))
 return p.get('team'),p.get('season'),cat
def review_existing(items):
 states=json.loads(Path('estado.json').read_text());cache_path=Path('photo-review.json')
 cache=json.loads(cache_path.read_text()) if cache_path.exists() else {}
 candidates=[p for p in items if p.get('cover') and p['cover'] not in cache]
 def review(p):
  try:
   im=Image.open(Path('images')/p['cover']).convert('RGB');passed=old.photo_private(im)
  except Exception:passed=False
  return p['id'],p['cover'],passed
 with ThreadPoolExecutor(max_workers=24) as pool:
  for i,(ident,cover,passed) in enumerate(pool.map(review,candidates),1):
   cache[cover]=passed
   if not passed:states[ident]='hidden'
   if i%1000==0:print('Photo review',i,'of',len(candidates),flush=True)
 Path('estado.json').write_text(json.dumps(states,ensure_ascii=False,indent=2))
 cache_path.write_text(json.dumps(cache,separators=(',',':')))
 return {'checked':len(candidates),'rejected':sum(not cache[p['cover']] for p in candidates)}
def refresh_source(items,number,source,existing,known,lock,counter):
 report={'source':number,'group':'footwear' if source in footwear_sources else 'catalog','added':0,'duplicates':0,'unrecognized':0,'photo_rejected':0,'read_errors':0,'albums_checked':0,'listing_pages_checked':0,'status':'pending'}
 base=source['url'];host=urlparse(base).netloc;mode=source['mode'];albums=[];queue=[base];seen=set();album_cat={}
 if mode=='shoes':
  root=f'{urlparse(base).scheme}://{host}'
  for extra_url in (root+'/categories',root+'/albums',root+'/albums?tab=gallery'):
   if extra_url not in queue:queue.append(extra_url)
 try:
  while queue and len(seen)<40:
   url=queue.pop(0)
   if url in seen:continue
   seen.add(url)
   try:page=BeautifulSoup(old.get(url).text,'html.parser')
   except Exception as error:
    report['read_errors']+=1
    report['error_types']=report.get('error_types',{})
    code=str(error) if str(error) in ('certificate','http_401','http_403','http_429') else 'fetch'
    report['error_types'][code]=report['error_types'].get(code,0)+1
    continue
   report['listing_pages_checked']+=1
   cat_name=title_of(page) if re.search(r'/categories/\d+',urlparse(url).path) else ''
   for a in page.select('a[href]'):
    u=urljoin(url,a['href']);parsed=urlparse(u)
    if parsed.netloc!=host:continue
    if re.search(r'/albums/\d+',parsed.path):
     if u not in albums:albums.append(u)
     if cat_name and u not in album_cat:album_cat[u]=cat_name
    elif re.search(r'/categories/\d+',parsed.path) or re.search(r'[?&]page=',u):
     if u not in seen and u not in queue:queue.append(u)
  report['albums_discovered']=len(albums);report['status']='readable_partial' if albums else ('read_failed' if report['read_errors'] else 'no_readable_albums')
  for link in albums[:300 if mode=='shoes' else 120]:
   time.sleep(.3)
   try:page=BeautifulSoup(old.get(link).text,'html.parser')
   except Exception as error:
    report['read_errors']+=1
    report['error_types']=report.get('error_types',{})
    code=str(error) if str(error) in ('certificate','http_401','http_403','http_429') else 'fetch'
    report['error_types'][code]=report['error_types'].get(code,0)+1
    continue
   report['albums_checked']+=1;raw=title_of(page);cat=category(raw)
   if not raw:report['empty_title']=report.get('empty_title',0)+1
   if mode=='shoes':
    model=album_cat.get(link,'')
    cat='calzado';raw=translate((model+' '+raw) if model and translate(model).lower() not in translate(raw).lower() else raw)
    report['models_from_categories']=report.get('models_from_categories',0)+bool(model)
    if not raw:report['empty_title']=report.get('empty_title',0)+1;continue
   if mode=='shorts' and (cat not in ('shorts','conjuntos','chaquetas') or (cat=='conjuntos' and not re.search(r'shorts?|\u77ed\u88e4',raw,re.I))):continue
   matched=identity(raw,'NBA' if re.search(r'\bnba\b|\u7bee\u7403',raw,re.I) else None)
   if mode=='racing':
    racing=next((name for name,aliases in old.RACING.items() if any(a.lower() in raw.lower() for a in aliases)),None);matched=(racing,'Fórmula 1') if racing else None
   if mode=='american':
    candidates=[(name,p['league']) for name,p in known.items() if p.get('league') in ('NFL','NHL') and (norm(name) in norm(raw) or norm(name.split()[-1]) in norm(raw).split())];matched=max(candidates,key=lambda p:len(p[0])) if candidates else None
   if not matched:
    candidates=[(name,p.get('league')) for name,p in known.items() if norm(name) and re.search(r'(?<![a-z0-9])'+re.escape(norm(name))+r'(?![a-z0-9])',norm(raw))];matched=max(candidates,key=lambda p:len(p[0])) if candidates else None
   brand=brand_of(raw)
   if cat in ('calzado','bolsos'):matched=(None,None)
   if matched is None or cat=='otros':report['unrecognized']+=1;continue
   name,league=matched
   if mode=='american' and league not in ('NFL','NHL'):report['unrecognized']+=1;continue
   with lock:
    ident=counter[0];counter[0]+=1
   title=clean(old.translated(raw))
   if not re.search(r'[A-Za-zÀ-ÿ]{3}',title):title=f'{CATS[cat]} {name or brand}'
   item={'id':str(ident),'slug':str(ident),'title':title,'team':name,'teamSlug':slug(name) if name else None,'league':league,'leagueSlug':slug(league) if league else None,'categorySlug':cat,'category':CATS[cat],'brand':brand,'season':old.season(raw),'version':'fan','sizes':re.findall(r'(?<![A-Za-z0-9])(S|M|L|XL|2XL|3XL|4XL)(?![A-Za-z0-9])',raw,re.I) or ['S','M','L','XL','2XL'],'audiences':['hombre'],'colors':[],'price':None,'status':'active','cover':str(ident)+'.webp'}
   if cat=='calzado':
    item['footwearType']=footwear_type(raw);item['sizes']=shoe_sizes(raw);item['title']=clean(translate(raw)) or 'Calzado '+brand
   with lock:
    duplicate=key(item) in existing
    if not duplicate:existing.add(key(item))
   if duplicate:report['duplicates']+=1;continue
   pics=[]
   for im in page.select('.showalbum__children img, .showalbum__children [data-src], [data-origin-src], img[data-photoindex], img[data-original]'):
    u=im.get('data-origin-src') or im.get('data-original') or im.get('data-src') or im.get('src')
    if u and not u.startswith('data:'):
     u=urljoin(link,u)
     if u not in pics:pics.append(u)
   if not pics:report['no_photo_candidates']=report.get('no_photo_candidates',0)+1
   if not old.photo(pics,Path('images')/item['cover']):
    with lock:existing.discard(key(item))
    report['photo_rejected']+=1;continue
   with lock:items.insert(0,item)
   report['added']+=1
 except Exception:report['status']='read_failed'
 print(json.dumps(report),flush=True)
 return report
def refresh(items):
 existing={key(p) for p in items};known={p['team']:p for p in items if p.get('team')}
 for league,names in [('NFL',old.NFL_TEAMS),('NHL',old.NHL_TEAMS),('Fórmula 1',list(old.RACING))]:
  for name in names:known.setdefault(name,{'team':name,'league':league})
 counter=[max(int(p['id']) for p in items)+1];lock=threading.Lock()
 with ThreadPoolExecutor(max_workers=8) as pool:
  futures=[pool.submit(refresh_source,items,n,source,existing,known,lock,counter) for n,source in enumerate(old.CONFIG['sources'],1)]
  return [future.result() for future in futures]
if __name__=='__main__':
 try:
  items=json.loads(Path('catalog.json').read_text());changes=normalize(items);reports=refresh(items);normalize(items);retained=review_existing(items)
  Path('catalog.json').write_text(json.dumps(items,ensure_ascii=False,separators=(',',':')));old.audit(items)
  result={'products':len(items),'covers':sum(bool(p.get('cover')) for p in items),'bytes':sum(p.stat().st_size for p in Path('images').glob('*.webp')),'privacy':old.COUNTS,'normalization':changes,'retained_photo_review':retained,'sources':reports,'added':sum(r['added'] for r in reports),'footwear_products':sum(p.get('categorySlug')=='calzado' for p in items),'photo_screening':old.PHOTO_COUNTS,'photo_content_privacy':'ocr_screened_not_visual_guarantee'}
  Path('resultado.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 except Exception:print('Catalog refresh stopped safely; no private configuration is logged.');raise SystemExit(1)
