"""Recover original stored photos using unique metadata matches, never positions."""
import io
import json
import os
import re
import hashlib
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import requests
from PIL import Image, ImageOps, ImageDraw
from photo_policy import choose_cover_photos, review_image
from bs4 import BeautifulSoup
from photo_candidates import album_originals, seller_cover, cover_listing_pages

def read(path, fallback):
    return json.loads(Path(path).read_text()) if Path(path).exists() else fallback

def identity(product):
    return (product.get('title','').strip(), product.get('season'), product.get('version'), tuple(sorted(product.get('sizes') or [])), tuple(sorted(product.get('audiences') or [])), product.get('team'), product.get('league'), product.get('category'), tuple(sorted(product.get('colors') or [])), product.get('price'))

def unique_matches(original, rows, clean):
    """Only one-to-one matches are usable; ambiguous products remain unchanged."""
    public=defaultdict(list); private=defaultdict(list)
    for product in original:public[identity(product)].append(product['id'])
    for row in rows:
        candidate={'title':clean(row['clean_title']) or 'Prenda deportiva','season':clean(row.get('season')) or None,'version':clean(row.get('version')) or None,'sizes':[s for s in map(clean,row.get('sizes') or []) if s],'audiences':[s for s in map(clean,row.get('audiences') or []) if s]}
        for field,relation in [('team','teams'),('league','leagues'),('category','categories')]:
            candidate[field]=clean((row.get(relation) or {}).get('name')) or ('Otros' if field=='category' and relation in row else None)
        candidate['colors']=[s for s in map(clean,row.get('colors') or []) if s]
        candidate['price']=row.get('price_crc')
        private[identity(candidate)].append(row)
    return {ids[0]:private[key][0] for key,ids in public.items() if len(ids)==1 and len(private.get(key,[]))==1}

def needs_recovery(product, recovery, extras):
    return recovery.get(product['id'],{}).get('policy') not in ('seller-cover-v4-eight','seller-cover-v5-position') or any(not (extras/key).is_file() for key in product.get('gallery',[]))

def main():
    config=json.loads(os.environ['CATALOG_CONFIG'])
    # Import only inside execution: config stays in the runner's secret environment.
    import catalog
    original_response=requests.get('https://raw.githubusercontent.com/cedenobryan471-ctrl/jerseyhouse-catalogo/7382ef1a5b6aae4e630ee827d2b9361505eb7c5f/catalog.json',timeout=60)
    original_response.raise_for_status(); original=original_response.json()
    cache=Path('/tmp/gallery-private-rows.json')
    if cache.exists():rows=read(cache,[])
    else:
        rows=[]
        for offset in range(0,200000,1000):
            response=requests.get(config['data_url']+'/rest/v1/products',params={'select':'id,source_url,clean_title,season,version,sizes,audiences,colors,price_crc,categories(name),leagues(name),teams(name),product_images(storage_path,sort_order)','order':'id.asc','offset':offset,'limit':1000},headers={'apikey':config['data_key']},timeout=(5,60))
            response.raise_for_status();part=response.json();rows.extend(part)
            if len(part)<1000:break
        cache.write_text(json.dumps(rows));cache.chmod(0o600)
    matches=unique_matches(original,rows,catalog.clean)
    products=read('catalog.json',[]);states=read('estado.json',{});manual=read('manual-states.json',{})
    recovery=read('gallery-recovery.json',{});photo_review=read('photo-review.json',{})
    old_review=read('photo-recovery.json',{})
    extras=Path('gallery-extra/images');extras.mkdir(parents=True,exist_ok=True)
    # Portadas elegidas a mano por el dueño: nunca se vuelven a procesar.
    portadas={**read('auto-covers-applied.json',{}),**read('portadas.json',{})}
    pilot=os.environ.get('GALLERY_PILOT')=='true'
    preview=Path('pilot-preview');preview.mkdir(exist_ok=True)
    batch=[p for p in products if (int(p['id'])<=20 if pilot else (needs_recovery(p,recovery,extras) and p['id'] not in portadas))][:int(os.environ.get('GALLERY_BATCH_SIZE','200'))]
    def process(product):
        row=matches.get(product['id'])
        if not row:return product,{'outcome':'unmatched','photos':0},[]
        images=[];errors=0;seller_index=None;cover_url=None
        source=row.get('source_url')
        if not source:return product,{'outcome':'no_album','photos':0},[]
        try:
            response=requests.get(source,timeout=(5,15),headers={'User-Agent':'Mozilla/5.0'})
            response.raise_for_status()
            page=BeautifulSoup(response.text,'html.parser')
            candidates=album_originals(page,source)
            cover_url=seller_cover(page,source)
            for listing_url in ([] if cover_url else cover_listing_pages(page,source)):
                try:
                    listing=requests.get(listing_url,timeout=(5,15),headers={'User-Agent':'Mozilla/5.0'})
                    listing.raise_for_status()
                    cover_url=seller_cover(BeautifulSoup(listing.text,'html.parser'),source)
                    if cover_url:break
                except Exception:continue
        except Exception:return product,{'outcome':'read_error','photos':0},[]
        for url in ([cover_url] if cover_url else [])+candidates[:24]:
            try:
                response=requests.get(url,timeout=(5,15),headers={'Referer':source,'User-Agent':'Mozilla/5.0'})
                response.raise_for_status()
                with Image.open(io.BytesIO(response.content)) as image: images.append(ImageOps.exif_transpose(image).convert('RGB'))
                if url==cover_url:seller_index=len(images)-1
            except Exception:errors+=1
        outcomes=[];checks={}
        def review(image):
            key=id(image)
            if key not in checks:
                checks[key]=review_image(image,config.get('blocked_terms',[]));outcomes.append(checks[key][0])
            return checks[key]
        # Sin posición fija: 'last' arruinaba portadas buenas (probado en 73 productos).
        selected=choose_cover_photos(images,review,seller_index,cover_position=os.environ.get('GALLERY_COVER_POSITION') or None)
        if pilot:
            sheet=Image.new('RGB',(1200,((len(images)+3)//4)*330),'white')
            drawing=ImageDraw.Draw(sheet)
            for index,image in enumerate(images):
                if review(image)[0]=='rejected':continue
                thumb=image.copy();thumb.thumbnail((290,290),Image.Resampling.LANCZOS)
                x=(index%4)*300;y=(index//4)*330
                sheet.paste(thumb,(x+(300-thumb.width)//2,y+20))
                label=f'{index} {image.width}x{image.height}'
                if index in selected:label+=' COVER' if index==selected[0] else ' GALLERY'
                drawing.text((x+6,y+4),label,fill='black')
            if images:sheet.save(preview/(product['id']+'.jpg'),quality=85)
            if selected:
                selected_image=images[selected[0]].copy();selected_image.thumbnail((600,600),Image.Resampling.LANCZOS);selected_image.save(preview/(product['id']+'-cover.webp'),'WEBP',quality=60)
            safe_result={'id':product['id'],'selected':selected,'seller_cover_found':seller_index is not None,'photos':[{'index':i,'width':im.width,'height':im.height,'outcome':review(im)[0],'reason':review(im)[1]} for i,im in enumerate(images)]}
            (preview/(product['id']+'.json')).write_text(json.dumps(safe_result))
            structure={'images':[{'classes':im.get('class',[]),'parent_classes':im.parent.get('class',[]),'attrs':[a for a in im.attrs if a!='alt'],'candidate_index':next((i for i,url in enumerate(candidates) if any(im.get(a) and im.get(a) in url for a in ('src','data-src','data-origin-src'))),None)} for im in page.select('img')], 'meta_images':[{'property':m.get('property') or m.get('name'),'candidate_index':next((i for i,url in enumerate(candidates) if m.get('content')==url),None)} for m in page.select('meta') if 'image' in str(m.get('property') or m.get('name'))]}
            (preview/(product['id']+'-structure.json')).write_text(json.dumps(structure))
            return product,{'outcome':'pilot','photos':len(selected)},[]
        if not selected:return product,{'outcome':'read_error' if errors or not images else 'no_approved_photo','photos':0},[]
        ident=product['id'];cover=Path('images')/(ident+'.webp')
        previous=hashlib.sha256(cover.read_bytes()).hexdigest() if cover.exists() else None
        keys=[]
        for number,index in enumerate(selected):
            image=images[index].copy();image.thumbnail((500,500) if number==0 else (400,400),Image.Resampling.LANCZOS)
            name=f'{ident}.webp' if number==0 else f'{ident}-{number}.webp'
            destination=cover if number==0 else extras/name
            image.save(destination,'WEBP',quality=70 if number==0 else 45)
            if number:keys.append(name)
        changed=previous!=hashlib.sha256(cover.read_bytes()).hexdigest()
        return product,{'outcome':'saved','photos':len(selected),'cover_changed':changed,'ocr_errors':outcomes.count('error')},keys
    with ThreadPoolExecutor(max_workers=16) as pool:
        for product,result,keys in pool.map(process,batch):
            ident=product['id'];result['recovered']=recovery.get(ident,{}).get('recovered',False);result['policy']='seller-cover-v5-position'
            if result['outcome']=='saved':
                previous=states.get(ident,product['status'])
                automatic=previous=='hidden' and (photo_review.get(product.get('cover')) is False or old_review.get(ident,{}).get('outcome') in ('rejected','missing'))
                if automatic and ident not in manual and product.get('sectionSlug')!='revision':
                    states[ident]='sold_out' if product.get('status')=='sold_out' else 'active';result['recovered']=True
                product['cover']=ident+'.webp';product['gallery']=keys;photo_review[product['cover']]=True
            recovery[ident]=result
    for ident in portadas:
        entry=recovery.setdefault(ident,{'outcome':'manual-cover','photos':0});entry['policy']='seller-cover-v5-position'
    if pilot:
        print('Visual pilot prepared; catalog, states and public photos remain unchanged.',flush=True)
        return
    Path('catalog.json').write_text(json.dumps(products,ensure_ascii=False,separators=(',',':')))
    Path('estado.json').write_text(json.dumps(states,ensure_ascii=False,indent=2))
    Path('gallery-recovery.json').write_text(json.dumps(recovery,separators=(',',':')))
    Path('photo-review.json').write_text(json.dumps(photo_review,separators=(',',':')))
    processed=sum(not needs_recovery(p,recovery,extras) for p in products)
    summary={'total':len(products),'processed':processed,'remaining':len(products)-processed,'uniquely_matched':len(matches),'recovered':sum(bool(x.get('recovered')) for x in recovery.values()),'covers_changed':sum(bool(x.get('cover_changed')) for x in recovery.values()),'with_gallery':sum(x.get('photos',0)>1 for x in recovery.values()),'unmatched':sum(x['outcome']=='unmatched' for x in recovery.values()),'read_errors':sum(x['outcome']=='read_error' for x in recovery.values()),'visible':sum(states.get(p['id'],p['status']) in ('active','sold_out') and bool(p.get('cover')) and p.get('sectionSlug')!='revision' for p in products),'catalog_bytes':sum(p.stat().st_size for p in Path('images').glob('*.webp'))+Path('catalog.json').stat().st_size,'extras_bytes':sum(p.stat().st_size for p in extras.glob('*.webp')),'examples':[{'id':p['id'],'title':p['title']} for p in products if recovery.get(p['id'],{}).get('recovered')][:5]}
    if summary['catalog_bytes']>=1_000_000_000 or summary['extras_bytes']>=1_000_000_000:raise ValueError('pages_size_limit')
    Path('gallery-recovery-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':
    try:main()
    except Exception as error:
        print('Gallery recovery stopped safely:',type(error).__name__)
        raise SystemExit(1)
