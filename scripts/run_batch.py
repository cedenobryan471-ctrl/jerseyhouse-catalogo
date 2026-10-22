"""Bounded, resumable catalog refresh without AI or public source addresses."""
import os,json,re,time,hashlib,threading
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse,urljoin
from bs4 import BeautifulSoup
import requests
import refresh as r
from footwear_rules import translate,brand_of,shoe_sizes,footwear_type,is_footwear,footwear_key
from identities import identity,slug

LABELS={'camisetas':'Camisetas','conjuntos':'Conjuntos','chaquetas':'Chaquetas','buzos':'Buzos','shorts':'Shorts','calzado':'Calzado','accesorios':'Accesorios'}
SPECIAL={'Selecciones':'selecciones','NBA':'nba','NFL':'nfl','NHL':'nhl','Fórmula 1':'formula-1'}
PROTECTED=['Golden State Warriors','Red Bull','Real Madrid','Inter Miami','Orlando City','Blue Jays','White Sox','Red Sox','Black Stars','Red Bull Racing','New York Red Bulls']
WORDS=[('football t-shirt','Camiseta de fútbol'),('training suit','Camiseta de entrenamiento'),('training kit','Camiseta de entrenamiento'),('tracksuit','Conjunto deportivo'),('windbreaker','Rompevientos'),('hoodie','Sudadera'),('sweatshirt','Sudadera'),('sweater','Suéter'),('long sleeved','manga larga'),('long sleeve','manga larga'),('short sleeve','manga corta'),('t-shirt','Camiseta'),('shirt','Camiseta'),('jersey','Camiseta'),('shorts','Pantaloneta'),('pants','Pantalón'),('trousers','Pantalón'),('jacket','Chaqueta'),('training','entrenamiento'),('home','local'),('away','visitante'),('third','tercera'),('black','negro'),('white','blanco'),('blue','azul'),('red','rojo')]
def generic_title(text,team=None):
 protected={}
 for name in sorted(set(PROTECTED+([team] if team else [])),key=len,reverse=True):
  token=f'ZZKEEP{len(protected)}ZZ';text,n=re.subn(re.escape(name),token,text,flags=re.I)
  if n:protected[token]=name
 for a,b in WORDS:text=re.sub(r'\b'+re.escape(a)+r'\b',b,text,flags=re.I)
 for token,name in protected.items():text=text.replace(token,name)
 return r.clean(text)
def classify(title,previous='',team=None):
 t=title.lower()
 if previous in ('calzado','tenis','tacos') or is_footwear(t):return 'calzado'
 if re.search(r'\b(?:bags?|backpack|handbag|wallet|caps?|hats?|socks?|scarfs?|scarves|balls?)\b|bolso|mochila|gorra|bufanda|medias|calcet|bal[oó]n|背包|袜',t):return 'accesorios'
 if re.search(r'tracksuit|conjunto|ch[aá]ndal|\bsets?\b|2\s*[- ]?\s*pieces?|套装',t) or (re.search(r'\b(?:kit|suit)\b',t) and re.search(r'\b(?:shorts?|pants|trousers)\b|短裤',t)):return 'conjuntos'
 if re.search(r'\b(?:shorts?|pants|trousers)\b|pantaloneta|pantal[oó]n|短裤|长裤',t):return 'shorts'
 if re.search(r'jacket|windbreaker|rompevientos|cortavientos|chaqueta|anthem|夹克|外套',t):return 'chaquetas'
 if re.search(r'hoodie|sweatshirt|sweater|sudadera|suéter|buzo|卫衣',t):return 'buzos'
 if re.search(r'jersey|shirt|camiseta|training|entrenamiento|vest|polo|uniform|\bt\b|球衣|篮球',t):return 'camisetas'
 if previous in LABELS:return previous
 if team:return 'camisetas'
 return None
def section(p):
 if p['categorySlug'] in ('calzado','accesorios'):return p['categorySlug']
 return SPECIAL.get(p['league'],'futbol') if p.get('team') and p.get('league') else 'ropa-casual'
def batch_slice(total,offset,size=8):
 start=offset if 0<=offset<total else 0
 return start,min(total,start+size)
def get(url):
 try:
  response=requests.get(url,timeout=(5,12),headers={'User-Agent':'Mozilla/5.0'})
  if response.status_code in (401,403,429):raise ValueError('http_'+str(response.status_code))
  response.raise_for_status();return response
 except requests.exceptions.SSLError:raise ValueError('certificate') from None
 except ValueError:raise
 except Exception:raise ValueError('fetch') from None
r.old.get=get

def organize(items,states):
 review=[];moved=Counter()
 for p in items:
  previous=p.get('categorySlug','');team=p.get('team');league=p.get('league')
  if not team:
   found=identity(p.get('title',''),league)
   if found:team,league=found;p.update(team=team,teamSlug=slug(team),league=league,leagueSlug=slug(league))
  cat=classify(p.get('title',''),previous,team)
  if not cat:
   states[p['id']]='hidden';p['sectionSlug']='revision';review.append({'id':p['id'],'reason':'Categoría o identidad no confirmada'});continue
  if previous=='otros':moved[cat]+=1
  p.update(categorySlug=cat,category=LABELS[cat])
  if cat in ('calzado','accesorios'):p.update(team=None,teamSlug=None,league=None,leagueSlug=None)
  if cat=='calzado':p['title']=r.clean(translate(p['title']));p['brand']=brand_of(p['title']);p['footwearType']=footwear_type(p['title'])
  else:p['title']=generic_title(p['title'],team)
  p['sectionSlug']=section(p)
 return review,moved

def main():
 items=json.loads(Path('catalog.json').read_text());states=json.loads(Path('estado.json').read_text())
 progress_path=Path('batch-progress.json');progress=json.loads(progress_path.read_text()) if progress_path.exists() else {}
 cache_path=Path('photo-review.json');cache=json.loads(cache_path.read_text()) if cache_path.exists() else {}
 seen={footwear_key(p) for p in items if p.get('categorySlug')=='calzado'};counter=[max(int(p['id']) for p in items)+1];lock=threading.Lock()
 def source_batch(number,source):
  report={'source':number,'group':'footwear' if source.get('mode')=='shoes' else 'catalog','added':0,'duplicates':0,'photo_rejected':0,'read_errors':0,'albums_checked':0,'models_from_categories':0,'status':'pending'}
  origin=urlparse(source['url']);root=origin.scheme+'://'+origin.netloc;key=hashlib.sha256(source['url'].encode()).hexdigest()[:20]
  queue=[source['url'],root+'/categories',root+'/albums',root+'/albums?tab=gallery'];visited=set();albums={}
  while queue and len(visited)<8:
   url=queue.pop(0)
   if url in visited:continue
   visited.add(url)
   try:page=BeautifulSoup(get(url).text,'html.parser')
   except Exception as e:
    report['read_errors']+=1;code=str(e) if str(e) in ('certificate','http_401','http_403','http_429') else 'fetch';report.setdefault('error_types',{})[code]=report.setdefault('error_types',{}).get(code,0)+1;continue
   model=r.title_of(page) if re.search(r'/categories/\d+',urlparse(url).path) else ''
   for a in page.select('a[href]'):
    u=urljoin(url,a['href']);parsed=urlparse(u)
    if parsed.netloc!=origin.netloc:continue
    if re.search(r'/albums/\d+',parsed.path):
     albums.setdefault(u,'')
     if model:albums[u]=model
    elif re.search(r'/categories/\d+',parsed.path) or re.search(r'[?&]page=',u):
     if u not in visited and u not in queue:queue.append(u)
  links=list(albums);start,end=batch_slice(len(links),progress.get(key,0),8)
  report.update(albums_discovered=len(links),batch_start=start,batch_end=end,remaining_albums=len(links)-end,listing_pages_checked=len(visited))
  for link in links[start:end]:
   try:page=BeautifulSoup(get(link).text,'html.parser')
   except Exception:report['read_errors']+=1;continue
   report['albums_checked']+=1;raw=r.title_of(page);model=albums[link]
   if source.get('mode')!='shoes':continue
   title=r.clean(translate(model+' '+raw if model and translate(model).lower() not in translate(raw).lower() else raw))
   report['models_from_categories']+=bool(model)
   if not title:continue
   product={'title':title,'brand':brand_of(title),'footwearType':footwear_type(title)};duplicate=footwear_key(product)
   with lock:
    if duplicate in seen:report['duplicates']+=1;continue
    seen.add(duplicate);ident=str(counter[0]);counter[0]+=1
   photos=[]
   for im in page.select('.showalbum__children img, .showalbum__children [data-src], [data-origin-src], img[data-photoindex], img[data-original]'):
    u=im.get('data-origin-src') or im.get('data-original') or im.get('data-src') or im.get('src')
    if u and not u.startswith('data:'):
     u=urljoin(link,u)
     if u not in photos:photos.append(u)
   if not r.old.photo(photos,Path('images')/(ident+'.webp')):
    with lock:seen.discard(duplicate)
    report['photo_rejected']+=1;continue
   product.update(id=ident,slug=ident,team=None,teamSlug=None,league=None,leagueSlug=None,categorySlug='calzado',category='Calzado',sizes=shoe_sizes(model+' '+raw),season=None,version='fan',audiences=['hombre'],colors=[],price=None,status='active',cover=ident+'.webp',sectionSlug='calzado')
   with lock:items.insert(0,product);cache[product['cover']]=True
   report['added']+=1
  progress[key]=end;report['status']='batch_complete' if links else 'read_failed' if report['read_errors'] else 'no_readable_albums'
  print(json.dumps(report),flush=True);return report
 sources=r.old.CONFIG['sources']
 with ThreadPoolExecutor(max_workers=3) as pool:reports=list(pool.map(lambda pair:source_batch(*pair),enumerate(sources,1)))
 review,moved=organize(items,states)
 Path('catalog.json').write_text(json.dumps(items,ensure_ascii=False,separators=(',',':')));Path('estado.json').write_text(json.dumps(states,ensure_ascii=False,indent=2));Path('revisar.json').write_text(json.dumps(review,ensure_ascii=False,indent=2));cache_path.write_text(json.dumps(cache));progress_path.write_text(json.dumps(progress))
 r.old.audit(items)
 visible=[p for p in items if states.get(p['id'],p['status']) in ('active','sold_out') and p.get('cover') and p.get('sectionSlug')!='revision']
 result={'products':len(items),'sources':reports,'added':sum(x['added'] for x in reports),'footwear_products':sum(p['categorySlug']=='calzado' for p in items),'privacy':r.old.COUNTS,'organization':{'moved_from_others':dict(moved),'review':len(review),'sections_visible':dict(Counter(p['sectionSlug'] for p in visible)),'categories_visible':dict(Counter(p['categorySlug'] for p in visible)),'sections_total':dict(Counter(p.get('sectionSlug') for p in items)),'categories_total':dict(Counter(p['categorySlug'] for p in items))},'examples':[p['title'] for p in items if p['categorySlug']=='calzado'][:10],'photo_screening':r.old.PHOTO_COUNTS,'photo_content_privacy':'ocr_screened_not_visual_guarantee'}
 Path('resultado.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':
 try:main()
 except Exception:print('Catalog batch failed safely; no private configuration is logged.');raise SystemExit(1)
