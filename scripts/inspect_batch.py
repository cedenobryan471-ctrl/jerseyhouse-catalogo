"""Prefer original covers and record only privacy-safe download diagnostics."""
import json,threading
from pathlib import Path
import execute_batch as runner
b=runner.b
original_soup=b.BeautifulSoup
original_translate=b.translate
references={};examples=[];guard=threading.Lock();counts={}
def count(key):
 with guard:counts[key]=counts.get(key,0)+1

def soup(*args,**kwargs):
 page=original_soup(*args,**kwargs)
 for image in page.select('img'):
  originals=[image.get(a) for a in ('data-origin-src','data-original','data-full','data-large','data-zoom-image')]
  srcset=[]
  for part in (image.get('srcset') or image.get('data-srcset') or '').split(','):
   fields=part.strip().split()
   if fields:
    try:weight=float(fields[1].rstrip('wx')) if len(fields)>1 else 0
    except ValueError:weight=0
    srcset.append((weight,fields[0]))
  preferred=next((v for v in originals if v),None) or next((v for _,v in sorted(srcset,reverse=True)),None)
  if preferred:image['data-origin-src']=preferred;count('original_attribute')
 return page
b.BeautifulSoup=soup

def translated(text):
 result=original_translate(text);clean=b.r.clean(result)
 if clean and b.brand_of(clean)!='Otras marcas':
  with guard:
   if clean not in examples and len(examples)<30:examples.append(clean)
 return result
b.translate=translated

original_get=b.get
thread_state=threading.local()
def listing_get(url):
 response=original_get(url)
 if '/albums/' in b.urlparse(url).path:thread_state.album=url
 return response
b.get=listing_get

def media_get(url):
 try:
  headers={'User-Agent':'Mozilla/5.0'}
  if getattr(thread_state,'album',None):headers['Referer']=thread_state.album
  response=b.requests.get(url,timeout=(5,12),headers=headers)
  if not response.ok:count('download_http_'+str(response.status_code));raise ValueError('fetch')
  if not response.headers.get('Content-Type','').startswith('image/'):count('download_non_image')
  else:count('download_image')
  return response
 except b.requests.exceptions.SSLError:count('download_certificate');raise ValueError('certificate') from None
 except Exception:count('download_failed');raise ValueError('fetch') from None
b.r.old.get=media_get
old_review=b.r.old.photo_private
def review(image):
 count('ocr_attempted');passed=old_review(image);count('ocr_passed' if passed else 'ocr_failed');return passed
b.r.old.photo_private=review

if __name__=='__main__':
 try:
  runner.main()
  path=Path('resultado.json');result=json.loads(path.read_text());result['photo_diagnostics']=counts;result['inspected_model_examples']=examples[:10];path.write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({'photo_diagnostics':counts,'model_examples':examples[:10]},ensure_ascii=False))
 except Exception as error:print('Catalog batch failed safely:',type(error).__name__);raise SystemExit(1)
