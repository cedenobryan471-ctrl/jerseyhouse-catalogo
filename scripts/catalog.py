import os,json,re,io,time,unicodedata,hashlib,subprocess,tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.parse import urljoin,urlparse
import requests
from PIL import Image
from bs4 import BeautifulSoup

CONFIG=json.loads(os.environ['CATALOG_CONFIG'])
ROOT=Path('.')
(ROOT/'images').mkdir(exist_ok=True)
TERMS=CONFIG['blocked_terms']
PATTERN=re.compile('|'.join(re.escape(x).replace(r'\-',r'[- _]?') for x in TERMS),re.I)
ADDR=re.compile(r'https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+\.[a-z]{2,}|\b[a-z0-9-]+\.(?:com|cn|net|org|shop|co|io|app|ru)(?:/\S*)?',re.I)
PHONE=re.compile(r'(?<!\d)(?:\+?\d[ ()-]*){8,15}(?!\d)')
CHINESE=re.compile(r'[\u3400-\u9fff\uf900-\ufaff]+')
BRANDS=['Nike','Adidas','Puma','New Balance','Asics','Mizuno','Under Armour','Jordan','Converse','Vans','Reebok','Umbro','Joma','Lotto','Skechers']
COUNTS={'removed':0,'remaining':0}

def clean(value):
    s=str(value or '')
    for pattern in [ADDR,PATTERN,PHONE,CHINESE]:
        s,n=pattern.subn('',s);COUNTS['removed']+=n
    return re.sub(r'\s+',' ',s).strip(' -_|')

def get(url):
    for attempt in range(3):
        try:
            r=requests.get(url,timeout=40,headers={'User-Agent':'Mozilla/5.0'})
            if r.status_code in (401,403,429): raise ValueError('http_'+str(r.status_code))
            r.raise_for_status();return r
        except requests.exceptions.SSLError:
            raise ValueError('certificate') from None
        except Exception as error:
            if attempt==2:raise ValueError(str(error) if isinstance(error,ValueError) else 'fetch') from None
            time.sleep(2+attempt)

def fetch_rows():
    rows=[]
    for off in range(0,200000,1000):
        r=requests.get(CONFIG['data_url']+'/rest/v1/products',params={'select':'id,clean_title,season,version,sizes,audiences,status,colors,price_crc,first_seen_at,categories(name,slug),leagues(name,slug),teams(name,slug),product_images(storage_path,sort_order)','status':'in.(active,sold_out)','order':'first_seen_at.desc,id.asc','offset':off,'limit':1000},headers={'apikey':CONFIG['data_key']},timeout=60)
        if r.status_code!=200:raise ValueError('Export unavailable')
        part=r.json();rows+=part
        if len(part)<1000:break
    if len(rows)!=12428:raise ValueError('Export count changed; manual review required')
    return rows

PHOTO_COUNTS={'screened':0,'rejected':0}
def photo_private(im):
    with tempfile.NamedTemporaryFile(suffix='.png') as f:
        scan=im.copy();scan.thumbnail((1000,1000));scan.save(f.name)
        try:
            result=subprocess.run(['tesseract',f.name,'stdout','-l','eng+chi_sim','--psm','11'],capture_output=True,text=True,timeout=20,env={**os.environ,'OMP_THREAD_LIMIT':'1'})
            if result.returncode!=0:return False
            text=result.stdout
            bad=any(p.search(text) for p in (PATTERN,ADDR,CHINESE)) or re.search(r'(?:\+?\d[ ()-]*){8,15}',text)
            PHOTO_COUNTS['screened']+=1
            if bad:PHOTO_COUNTS['rejected']+=1
            return not bad
        except Exception:return False

def photo(candidates,dest):
    if dest.exists():return True
    choices=[]
    for index,url in enumerate(candidates[:4]):
        try:
            im=Image.open(io.BytesIO(get(url).content)).convert('RGB')
            if min(im.size)<150:continue
            choices.append((im.width/im.height,index,im))
        except Exception:continue
    if not choices:return False
    # Discard the widest candidate; preserve the earliest remaining portrait/full garment candidate.
    if len(choices)>1:
        widest=max(choices,key=lambda x:x[0])
        choices=[x for x in choices if x is not widest]
    eligible=[x for x in choices if x[0]<=1.3]
    if not eligible:return False
    im=None
    for choice in sorted(eligible,key=lambda x:x[1]):
        if photo_private(choice[2]):im=choice[2];break
    if im is None:return False
    im.thumbnail((500,500),Image.Resampling.LANCZOS)
    im.save(dest,'WEBP',quality=70)
    return True

def bootstrap():
    rows=fetch_rows();out=[];states=json.loads(Path('estado.json').read_text())
    def convert(pair):
        index,r=pair
        ident=str(index+1)
        def relation(key):return r.get(key) or {}
        cat=relation('categories');league=relation('leagues');team=relation('teams')
        title=clean(r['clean_title']) or 'Prenda deportiva'
        item={'id':ident,'slug':ident,'title':title,'league':clean(league.get('name')) or None,'leagueSlug':clean(league.get('slug')) or None,'team':clean(team.get('name')) or None,'teamSlug':clean(team.get('slug')) or None,'category':clean(cat.get('name')) or 'Otros','categorySlug':clean(cat.get('slug')) or 'otros','brand':next((b for b in BRANDS if b.lower() in title.lower()),'Otras marcas'),'season':clean(r.get('season')) or None,'version':clean(r.get('version')) or None,'sizes':[s for s in map(clean,r.get('sizes') or []) if s],'audiences':[s for s in map(clean,r.get('audiences') or []) if s],'colors':[s for s in map(clean,r.get('colors') or []) if s],'price':r.get('price_crc'),'status':r['status'],'cover':None}
        pics=sorted(r.get('product_images') or [],key=lambda x:x['sort_order'])
        paths=[CONFIG['image_origin']+'/api/public/img/'+x['storage_path'] for x in pics]
        if photo(paths,Path('images')/(ident+'.webp')):item['cover']=ident+'.webp'
        else:states[ident]='hidden'
        return index,item
    with ThreadPoolExecutor(max_workers=32) as pool:
        results=[]
        for result in pool.map(convert,enumerate(rows)):
            results.append(result)
            if len(results)%250==0:print('Exported',len(results),'of',len(rows),flush=True)
    out=[x[1] for x in sorted(results)]
    Path('estado.json').write_text(json.dumps(states,ensure_ascii=False,indent=2))
    return out

def norm(s):return re.sub(r'[^a-z0-9]+',' ',unicodedata.normalize('NFKD',s.lower()).encode('ascii','ignore').decode()).strip()
def garment(t):
    if re.search(r'\u7403\u978b|\u8fd0\u52a8\u978b|\u8fd0\u52a8\u9774',t):return 'tenis'
    if re.search(r'\u7403\u8863|\u80cc\u5fc3|\u77ed\u8896|\u957f\u8896',t):return 'camisetas'
    if re.search(r'2\s*piece|two[- ]piece|short set|\bset\b|tracksuit|\bkit\b.*(?:short|pants)',t,re.I):return 'conjuntos'
    if re.search(r'\u88e4\u5b50|\u77ed\u88e4|pantalonetas?',t,re.I):return 'shorts'
    if re.search(r'jacket|windbreaker|cortavientos|chaqueta',t,re.I):return 'chaquetas'
    if re.search(r'tracksuit|\bset\b|2\s*piece|chándal|\bkit\b.*(?:short|pants)',t,re.I):return 'conjuntos'
    if re.search(r'hoodie|sweatshirt|sweater|sudadera|buzo',t,re.I):return 'buzos'
    if re.search(r'cleats|football boots|soccer shoes|tacos',t,re.I):return 'tacos'
    if re.search(r'shoes|sneaker|tenis|slides',t,re.I):return 'tenis'
    if re.search(r'\bshorts?\b|\bpants\b|pantaloneta',t,re.I):return 'shorts'
    if re.search(r'jersey|shirt|training|vest|polo|camiseta',t,re.I):return 'camisetas'
    return 'otros'
def season(t):
    m=re.search(r'\b((?:19|20)\d{2}|\d{2})[-/](\d{2}|(?:19|20)\d{2})\b',t)
    if m:
        year=int(m[1]);year=year if year>99 else year+(1900 if year>=50 else 2000)
        return str(year)+'/'+m[2][-2:]
    m=re.search(r'\b(?:19|20)\d{2}\b',t)
    return m[0] if m else None

NFL_TEAMS=['Arizona Cardinals','Atlanta Falcons','Baltimore Ravens','Buffalo Bills','Carolina Panthers','Chicago Bears','Cincinnati Bengals','Cleveland Browns','Dallas Cowboys','Denver Broncos','Detroit Lions','Green Bay Packers','Houston Texans','Indianapolis Colts','Jacksonville Jaguars','Kansas City Chiefs','Las Vegas Raiders','Los Angeles Chargers','Los Angeles Rams','Miami Dolphins','Minnesota Vikings','New England Patriots','New Orleans Saints','New York Giants','New York Jets','Philadelphia Eagles','Pittsburgh Steelers','San Francisco 49ers','Seattle Seahawks','Tampa Bay Buccaneers','Tennessee Titans','Washington Commanders']
NHL_TEAMS=['Anaheim Ducks','Boston Bruins','Buffalo Sabres','Calgary Flames','Carolina Hurricanes','Chicago Blackhawks','Colorado Avalanche','Columbus Blue Jackets','Dallas Stars','Detroit Red Wings','Edmonton Oilers','Florida Panthers','Los Angeles Kings','Minnesota Wild','Montreal Canadiens','Nashville Predators','New Jersey Devils','New York Islanders','New York Rangers','Ottawa Senators','Philadelphia Flyers','Pittsburgh Penguins','San Jose Sharks','Seattle Kraken','St. Louis Blues','Tampa Bay Lightning','Toronto Maple Leafs','Utah Mammoth','Vancouver Canucks','Vegas Golden Knights','Washington Capitals','Winnipeg Jets']
RACING={'Ferrari':['ferrari','\u6cd5\u62c9\u5229'],'Mercedes':['mercedes','\u6885\u8d5b\u5fb7\u65af','\u5954\u9a70'],'McLaren':['mclaren','\u8fc8\u51ef\u4f26'],'Red Bull Racing':['red bull','\u7ea2\u725b'],'Aston Martin':['aston martin','\u963f\u65af\u987f\u9a6c\u4e01'],'Alpine':['alpine','\u963f\u5c14\u6d3e'],'Williams':['williams','\u5a01\u5ec9\u59c6\u65af'],'Haas':['haas','\u54c8\u65af'],'Audi':['audi','\u5965\u8fea'],'Cadillac':['cadillac','\u51ef\u8fea\u62c9\u514b'],'Racing Bulls':['racing bulls','visa cash app']}
def slug(s):return norm(s).replace(' ','-')
def translated(t):
    for a,b in [('long sleeve','manga larga'),('short sleeve','manga corta'),('training suit','Camiseta de entrenamiento'),('training kit','Camiseta de entrenamiento'),('training','entrenamiento'),('jersey','camiseta'),('home','Local'),('away','Visitante'),('third','Tercera'),('player','jugador'),('fan','aficionado'),('black','negro'),('white','blanco'),('blue','azul'),('red','rojo'),('green','verde'),('yellow','amarillo')]:
        t=re.sub(r'\b'+a+r'\b',b,t,flags=re.I)
    return clean(t)
def weekly(items):
    def design_key(p):
        if p.get('categorySlug') in ('tenis','tacos'):
            return (p.get('brand'),p.get('season'),p.get('categorySlug'),clean(p.get('title')))
        return (p.get('team'),p.get('season'),p.get('categorySlug'))
    existing={design_key(p) for p in items}
    known={p['team']:p for p in items if p.get('team')}
    template={'sizes':['S','M','L','XL','2XL'],'audiences':['hombre'],'colors':[],'price':None,'version':'fan','brand':'Otras marcas'}
    for league,names in [('NFL',NFL_TEAMS),('NHL',NHL_TEAMS),('Fórmula 1',list(RACING))]:
        for name in names:
            known.setdefault(name,{**template,'team':name,'teamSlug':slug(name),'league':league,'leagueSlug':'formula-1' if league=='Fórmula 1' else league.lower()})
    results=[];added=0
    for idx,source in enumerate(CONFIG['sources'],1):
        report={'source':idx,'added':0,'review':0,'status':'unavailable'}
        try:
            base=source['url'];mode=source['mode'];origin=urlparse(base).netloc
            html=get(base).text;soup=BeautifulSoup(html,'html.parser')
            links=[]
            for a in soup.select('a[href]'):
                u=urljoin(base,a['href'])
                if urlparse(u).netloc==origin and re.search(r'/albums/\d+',urlparse(u).path):
                    if u not in links:links.append(u)
            # Follow categories and listing pages on the same host; bounded per weekly run.
            listing=[]
            for a in soup.select('a[href]'):
                u=urljoin(base,a['href'])
                if urlparse(u).netloc==origin and (re.search(r'/categories/\d+',u) or re.search(r'[?&]page=',u)) and u not in listing:listing.append(u)
            for u in listing[:40]:
                try:
                    listing_soup=BeautifulSoup(get(u).text,'html.parser')
                    for a in listing_soup.select('a[href]'):
                        album=urljoin(u,a['href'])
                        if urlparse(album).netloc==origin and re.search(r'/albums/\d+',urlparse(album).path) and album not in links:links.append(album)
                except Exception:continue
            report['listing_pages_checked']=min(len(listing),40)
            report['status']='readable_partial' if links else 'no_readable_albums'
            report['albums_checked']=0
            # Bounded polite run: unrecognized teams require manual review, never invent a club.
            for link in links[:60]:
                time.sleep(.5)
                page=BeautifulSoup(get(link).text,'html.parser');report['albums_checked']+=1
                h=page.select_one('h1:not(.visually-hidden)') or page.select_one('h1') or page.select_one('title')
                raw=h.get_text(' ',strip=True) if h else ''
                raw=re.sub(r'\s+\d+$','',raw)
                title=clean(raw);category=garment(raw)
                if mode=='shorts':
                    if category not in ('shorts','conjuntos','chaquetas'):continue
                    if category=='conjuntos' and not re.search(r'shorts?|short set|\u77ed\u88e4',raw,re.I):continue
                if mode=='shoes' and category not in ('tenis','tacos'):continue
                matches=[(name,p) for name,p in known.items() if norm(name) and re.search(r'(?<![a-z0-9])'+re.escape(norm(name))+r'(?![a-z0-9])',norm(title))]
                if mode=='american':
                    for name,p in known.items():
                        if p.get('league') in ('NFL','NHL') and norm(name.split(' ')[-1]) in norm(title).split():matches.append((name,p))
                if mode=='racing':
                    matches=[(name,known[name]) for name,aliases in RACING.items() if any(alias.lower() in raw.lower() for alias in aliases)]
                if mode=='shoes':
                    brand=next((b for b in BRANDS if b.lower() in raw.lower()),'Otras marcas')
                    matches=[(brand,{**template,'team':None,'teamSlug':None,'league':None,'leagueSlug':None,'brand':brand})]
                if not matches:
                    report['review']+=1;continue
                name,p=max(matches,key=lambda x:len(x[0]))
                sea=season(raw);key=(p.get('team'),sea,category)
                if mode=='shoes':key=(p.get('brand'),sea,category,translated(title))
                if category=='otros' or key in existing:continue
                if mode=='american' and p.get('league') not in ('NFL','NHL'):
                    report['review']+=1;continue
                if mode=='racing' and p.get('league')!='Fórmula 1':
                    report['review']+=1;continue
                pics=[]
                for im in page.select('[data-origin-src], img[data-photoindex], img[data-type], img[data-original]'):
                    u=im.get('data-origin-src') or im.get('data-original') or im.get('data-src') or im.get('src')
                    if u and u.startswith(('http','//')):pics.append(urljoin(link,u))
                ident=str(max(int(x['id']) for x in items)+1)
                if not photo(pics,Path('images')/(ident+'.webp')):
                    report['review']+=1;continue
                item={**p,'id':ident,'slug':ident,'title':translated(title) or ('Camiseta '+name+(' '+sea if sea else '')),'season':sea,'categorySlug':category,'category':{'shorts':'Shorts y pantalones','conjuntos':'Conjuntos','chaquetas':'Chaquetas','buzos':'Buzos y sudaderas','camisetas':'Camisetas','tenis':'Tenis','tacos':'Tacos'}[category],'cover':ident+'.webp','status':'active','price':None,'sizes':list(dict.fromkeys(re.findall(r'(?<![A-Za-z0-9])(S|M|L|XL|2XL|3XL|4XL)(?![A-Za-z0-9])',raw,re.I))) or ['S','M','L','XL','2XL']}
                items.insert(0,item);existing.add(key);report['added']+=1;added+=1
        except Exception:report['status']='read_failed'
        results.append(report)
    return results,added

def audit(items):
    for p in items:
        for k,v in p.items():
            if k in ('id','slug','cover'):continue
            for s in (v if isinstance(v,list) else [v]):
                if not isinstance(s,str):continue
                for pat in (PATTERN,ADDR,PHONE,CHINESE):COUNTS['remaining']+=len(pat.findall(s))
    # No hidden source references in tracked code/config/data; generic service URLs are allowed.
    for path in [p for p in Path('.').rglob('*') if p.is_file() and '.git' not in p.parts and p.suffix in ('.py','.json','.md','.yml','.yaml')]:
        text=path.read_text()
        for term in TERMS:
            if re.search(re.escape(term),text,re.I):COUNTS['remaining']+=1
    if COUNTS['remaining']:raise ValueError('Privacy audit failed')
    if sum(p.stat().st_size for p in Path('images').glob('*.webp'))+len(json.dumps(items).encode())>=800_000_000:raise ValueError('Size limit exceeded')

if __name__=='__main__':
    try:
        is_initial=os.environ.get('BOOTSTRAP','').lower()=='true' and not Path('catalog.json').exists()
        items=bootstrap() if is_initial else json.loads(Path('catalog.json').read_text())
        reports,added=weekly(items)
        audit(items)
        Path('catalog.json').write_text(json.dumps(items,ensure_ascii=False,separators=(',',':')))
        states=json.loads(Path('estado.json').read_text())
        result={'products':len(items),'covers':sum(bool(p.get('cover')) for p in items),'hidden':len([v for v in states.values() if v=='hidden']),'bytes':sum(p.stat().st_size for p in Path('images').glob('*.webp')),'privacy':COUNTS,'photo_content_privacy':'ocr_screened_not_visual_guarantee','photo_screening':PHOTO_COUNTS,'sources':reports,'added':added}
        Path('resultado.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        print(json.dumps(result,ensure_ascii=False))
    except Exception:
        print('Catalog update failed safely. No source addresses or private data are logged.');raise SystemExit(1)
