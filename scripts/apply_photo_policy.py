"""Install deterministic album-order policy for every future import."""
import io
from PIL import Image
from photo_policy import review_image,choose_photos

def install(engine):
 def review(image):
  outcome,_=review_image(image,engine.TERMS)
  engine.PHOTO_COUNTS['screened']+=1
  if outcome=='rejected':engine.PHOTO_COUNTS['rejected']+=1
  if outcome=='error':engine.PHOTO_COUNTS['errors']=engine.PHOTO_COUNTS.get('errors',0)+1
  return outcome!='rejected'
 def photo(candidates,dest):
  if dest.exists():return True
  images=[]
  for url in candidates[:16]:
   try:
    image=Image.open(io.BytesIO(engine.get(url).content)).convert('RGB')
    if min(image.size)>=100:images.append(image)
   except Exception:continue
  selected=choose_photos(images,lambda im:('passed',None) if review(im) else ('rejected','private'))
  if not selected:return False
  image=images[selected[0]];image.thumbnail((500,500),Image.Resampling.LANCZOS);image.save(dest,'WEBP',quality=70)
  return True
 engine.photo_private=review;engine.photo=photo

if __name__=='__main__':
 import runpy
 import catalog
 install(catalog)
 runpy.run_path('scripts/finalize_batch.py',run_name='__main__')
