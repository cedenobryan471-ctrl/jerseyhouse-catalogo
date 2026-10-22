"""Remove original references and hide unidentified/duplicate footwear safely."""
import json,re
from pathlib import Path
from collections import Counter
import finalize_batch as final
b=final.b

def clean_title(title):
 text=re.sub(r'(?<![\w.])\d{5,}(?![\w.])',' ',final.translate(title))
 text=re.sub(r'\s+',' ',text).strip(' -_,;.')
 return text if re.search(r'[A-Za-zÀ-ÿ]{3}',text) else None

def main():
 assert clean_title('12453') is None
 assert clean_title('Adidas Superstar 3.0 12461')=='Adidas Superstar 3.0'
 items=json.loads(Path('catalog.json').read_text());states=json.loads(Path('estado.json').read_text());review=[];seen=set();hidden=0
 for p in sorted(items,key=lambda p:int(p['id'])):
  if p['categorySlug']!='calzado':continue
  title=clean_title(p['title'])
  if not title:
   p['title']='Calzado por identificar';p['sectionSlug']='revision';states[p['id']]='hidden';review.append({'id':p['id'],'reason':'Modelo de calzado no identificado'});hidden+=1;continue
  p['title']=title;p['brand']=b.brand_of(title)
  key=b.footwear_key(p)
  if key in seen:
   states[p['id']]='hidden';p['sectionSlug']='revision';review.append({'id':p['id'],'reason':'Modelo de calzado duplicado'});hidden+=1
  else:seen.add(key)
 # Prevent later organization from reactivating review metadata.
 existing=json.loads(Path('revisar.json').read_text());known={x['id'] for x in existing};existing.extend(x for x in review if x['id'] not in known)
 b.r.old.audit(items)
 visible=[p for p in items if states.get(p['id'],p['status']) in ('active','sold_out') and p.get('cover') and p.get('sectionSlug')!='revision']
 result=json.loads(Path('resultado.json').read_text());org=result['organization'];org.update(review=len(existing),sections_visible=dict(Counter(p['sectionSlug'] for p in visible)),categories_visible=dict(Counter(p['categorySlug'] for p in visible)),sections_total=dict(Counter(p.get('sectionSlug') for p in items)),categories_total=dict(Counter(p['categorySlug'] for p in items)))
 result['examples']=[p['title'] for p in visible if p['categorySlug']=='calzado'][:10];result['footwear_hidden_after_review']=hidden;result['privacy']=b.r.old.COUNTS
 Path('catalog.json').write_text(json.dumps(items,ensure_ascii=False,separators=(',',':')));Path('estado.json').write_text(json.dumps(states,ensure_ascii=False,indent=2));Path('revisar.json').write_text(json.dumps(existing,ensure_ascii=False,indent=2));Path('resultado.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':
 try:main()
 except Exception as error:print('Catalog cleanup failed safely:',type(error).__name__);raise SystemExit(1)
