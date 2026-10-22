"""Checkpoint all retained covers; do not overwrite manual or classification hides."""
import json,os,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from photo_policy import review_image
def read(path,fallback):return json.loads(Path(path).read_text()) if Path(path).exists() else fallback
def main():
 products=read('catalog.json',[]);states=read('estado.json',{});old_cache=read('photo-review.json',{});manual=read('manual-states.json',{});reasons=read('photo-recovery.json',{})
 names=json.loads(os.environ.get('CATALOG_CONFIG','{}')).get('blocked_terms',[])
 batch=[p for p in products if p['id'] not in reasons][:int(os.environ.get('PHOTO_BATCH_SIZE','400'))]
 def run(product):
  cover=product.get('cover');path=Path('images')/(cover or (product['id']+'.webp'))
  if not path.exists():return product,{'outcome':'missing','reason':'no_retained_photo'}
  try:
   with Image.open(path) as source:image=source.convert('RGB')
   outcome,reason=review_image(image,names)
   return product,{'outcome':outcome,'reason':reason,'digest':hashlib.sha256(path.read_bytes()).hexdigest()[:16]}
  except Exception:return product,{'outcome':'error','reason':None}
 with ThreadPoolExecutor(max_workers=16) as pool:
  for product,result in pool.map(run,batch):
   ident=product['id'];cover=product.get('cover');previous=states.get(ident,product.get('status','active'))
   automatic=previous=='hidden' and old_cache.get(cover) is False and product.get('sectionSlug')!='revision' and ident not in manual
   result['recovered']=False
   if ident not in manual and product.get('sectionSlug')!='revision':
    if result['outcome']=='rejected':states[ident]='hidden'
    elif result['outcome'] in ('passed','error') and automatic:states[ident]=product.get('status','active');result['recovered']=True
   if result['outcome'] in ('passed','rejected') and cover:old_cache[cover]=result['outcome']=='passed'
   reasons[ident]=result
 Path('estado.json').write_text(json.dumps(states,ensure_ascii=False,indent=2));Path('photo-review.json').write_text(json.dumps(old_cache,separators=(',',':')));Path('photo-recovery.json').write_text(json.dumps(reasons,separators=(',',':')))
 summary={'total':len(products),'processed':len(reasons),'remaining':len(products)-len(reasons),'recovered':sum(bool(x.get('recovered')) for x in reasons.values()),'rejected':sum(x['outcome']=='rejected' for x in reasons.values()),'errors':sum(x['outcome']=='error' for x in reasons.values()),'missing':sum(x['outcome']=='missing' for x in reasons.values()),'covers_changed':0,'visible':sum(states.get(p['id'],p['status']) in ('active','sold_out') and bool(p.get('cover')) and p.get('sectionSlug')!='revision' for p in products),'catalog_bytes':sum(p.stat().st_size for p in Path('images').glob('*.webp'))+Path('catalog.json').stat().st_size,'examples':[p['title'] for p in products if reasons.get(p['id'],{}).get('recovered')][:5],'original_album_recovery':'pending_private_mapping'}
 Path('photo-recovery-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False),flush=True);return summary
if __name__=='__main__':main()
