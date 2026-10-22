"""Complete bounded footwear windows with non-recursive pure translation."""
import re,json
from pathlib import Path
import inspect_batch as process
b=process.b
pure_translate=process.original_translate
pure_brand=b.brand_of
def translate(text):
 return re.sub(r'\bAJ\b','Jordan',re.sub(r'\bnb\b','New Balance',pure_translate(text),flags=re.I),flags=re.I)
b.translate=translate
b.brand_of=lambda text:pure_brand(translate(text))
old_classify=b.classify
old_title=b.generic_title
def classify(title,previous='',team=None):
 if previous not in ('calzado','tenis','tacos') and re.search(r'\b(?:kits?|suits?)\b|camiseta\s*\+|top\s*\+',title,re.I) and re.search(r'\b(?:shorts?|pants|trousers)\b|pantaloneta|pantal[oó]n|短裤',title,re.I):return 'conjuntos'
 return old_classify(title,previous,team)
b.classify=classify

def title(text,team=None):
 protected={}
 for name in sorted(set(b.PROTECTED+([team] if team else [])),key=len,reverse=True):
  token=f'ZZSAFE{len(protected)}ZZ';text,n=re.subn(re.escape(name),token,text,flags=re.I)
  if n:protected[token]=name
 for english,spanish in [('sleeveless','sin mangas'),('football','fútbol'),('soccer','fútbol'),('basketball','básquet'),('cotton','algodón'),('dark','oscuro'),('short','corto'),('cheap jerseys','camisetas'),('replicas','')]:text=re.sub(r'\b'+re.escape(english)+r'\b',spanish,text,flags=re.I)
 for token,name in protected.items():text=text.replace(token,name)
 return old_title(text,team)
b.generic_title=title
if __name__=='__main__':
 try:
  assert translate('nb')=='New Balance'
  assert b.brand_of('nb')=='New Balance'
  assert classify('Short Traning Suits Soccer Jerseys')=='conjuntos'
  assert title('Golden State Warriors Hoodie','Golden State Warriors')=='Golden State Warriors Sudadera'
  totals={};added=0
  for iteration in range(2):
   process.runner.main()
   result=json.loads(Path('resultado.json').read_text());added+=result['added']
   for report in result['sources']:
    key=(report['group'],report['source']);previous=totals.get(key,{})
    for field in ('added','duplicates','photo_rejected','albums_checked'):report[field]+=previous.get(field,0)
    totals[key]=report
   if not any(x.get('remaining_albums',0)>0 for x in result['sources']):break
  result['sources']=list(totals.values());result['added']=added;result['photo_diagnostics']=process.counts;result['inspected_model_examples']=process.examples[:10]
  Path('resultado.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 except Exception as error:print('Catalog batch failed safely:',type(error).__name__);raise SystemExit(1)
