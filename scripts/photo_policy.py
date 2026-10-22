"""Deterministic privacy-only OCR and album-order selection, without AI."""
import re
import os
import subprocess
import tempfile
import csv
import io
from PIL import Image, ImageChops, ImageStat, ImageFilter

CHINESE = re.compile(r'[\u3400-\u9fff\uf900-\ufaff]')
LINK = re.compile(r'https?\s*[:/]\s*|\bwww\b|\.(?:com|cn|net|org|shop|co|io|app)\b|[\w.+-]+@[\w.-]+\.[a-z]{2,}', re.I)
CONTACT = re.compile(r'\b(?:whats\s*app|we\s*chat|qq)\b|微信|电话', re.I)
PHONE = re.compile(r'(?<!\d)(?:\+\d{1,3}[ ()-]*)?\d{4}[ -]?\d{4}(?!\d)|(?<!\d)\d{10,15}(?!\d)|(?<!\d)\d{3}[-.]\d{3}[-.]\d{4}(?!\d)')
NORMAL = {'nike', 'adidas', 'puma', 'jordan', 'new balance', 'asics', 'mizuno', 'under armour', 'original', 'top', 'aaa', 'factory', 'wholesale', 'supplier', 'reseller'}

def private_reason(text, names=()):
    for pattern, reason in ((CHINESE, 'chinese'), (LINK, 'link'), (CONTACT, 'contact'), (PHONE, 'phone')):
        checked = re.sub(r'\b(?:19|20)\d{2}\b', '', text) if reason == 'phone' else text
        if pattern.search(checked):
            return reason
    for name in names:
        if name.strip().lower() not in NORMAL and name.strip() and re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', text, re.I):
            return 'store_name'
    return None

def review_image(image, names=(), runner=subprocess.run):
    try:
        with tempfile.NamedTemporaryFile(suffix='.png') as file:
            scan=image.copy(); scan.thumbnail((1200,1200)); scan.save(file.name)
            first=ocr_words(file.name,11,runner)
            if first is None:return 'error',None
            text=' '.join(word for word,confidence in first if confidence>=60)
            reason=private_reason(text,names)
            if not reason:return ('error',None) if private_reason(' '.join(w for w,_ in first),names) else ('passed',None)
            # A second segmentation must confirm privacy text: fabric/crests often
            # hallucinate Chinese in a single multilingual OCR pass.
            second=ocr_words(file.name,12,runner)
            if second is None:return 'error',None
            confirmed=' '.join(word for word,confidence in second if confidence>=60)
            if private_reason(confirmed,names)!=reason:return 'error',None
            if reason=='chinese' and not (set(CHINESE.findall(text)) & set(CHINESE.findall(confirmed))):return 'error',None
            return 'rejected',reason
    except Exception:
        return 'error', None

def ocr_words(path, mode, runner):
    result=runner(['tesseract',path,'stdout','-l','eng+chi_sim','--psm',str(mode),'tsv'],capture_output=True,text=True,timeout=20,env={**os.environ,'OMP_THREAD_LIMIT':'1'})
    if result.returncode!=0:return None
    words=[]
    for row in csv.DictReader(io.StringIO(result.stdout),delimiter='\t'):
        if row.get('text','').strip():words.append((row['text'].strip(),float(row.get('conf',-1))))
    return words

def is_closeup(image, largest_area):
    if image.width * image.height < largest_area * .25:
        return True
    sample=image.convert('RGB').resize((64,64)).quantize(colors=16)
    counts=sample.getcolors() or []
    return max((count for count, _ in counts), default=0) / 4096 > .94

def choose_photos(images, review):
    """Images must be one original per album photo, in album order."""
    largest=max((im.width*im.height for im in images),default=0)
    chosen=[]
    for index, image in enumerate(images):
        if is_closeup(image,largest):
            continue
        outcome,_=review(image)
        if outcome != 'rejected' and not any(same_photo(image,images[other]) for other in chosen):
            chosen.append(index)
        if len(chosen)==4:
            break
    return chosen

def background_score(image):
    """Whole-frame smooth perimeter and centered contrast; never crop output."""
    sample=image.convert('RGB').resize((64,64))
    pixels=list(sample.getdata())
    border=[pixels[y*64+x] for y in range(64) for x in range(64) if x<6 or x>=58 or y<6 or y>=58]
    buckets={}
    for pixel in border:
        key=tuple(c//32 for c in pixel);buckets[key]=buckets.get(key,0)+1
    background=max(buckets,key=buckets.get)
    distance=lambda p:sum(abs(p[c]-(background[c]*32+16)) for c in range(3))/3
    smooth=sum(distance(p)<35 for p in border)/len(border)
    foreground=[(x,y) for y in range(64) for x in range(64) if distance(pixels[y*64+x])>45]
    if not foreground:return -1
    area=len(foreground)/4096
    if area<.08 or area>.88:return -1
    cx=sum(x for x,y in foreground)/len(foreground);cy=sum(y for x,y in foreground)/len(foreground)
    centered=1-(abs(cx-31.5)+abs(cy-31.5))/63
    return smooth*2+centered

def choose_cover_photos(images,review,seller_index=None,cover_position=None):
    eligible=[i for i,im in enumerate(images) if review(im)[0]!='rejected']
    if not eligible:return []
    largest=max((im.width*im.height for im in images),default=0)
    full=[i for i in eligible if not is_closeup(images[i],largest)] or eligible
    if cover_position=='last':cover=full[-1]
    elif cover_position=='first':cover=full[0]
    elif seller_index in full:cover=seller_index
    else:cover=max(full,key=lambda i:background_score(images[i]))
    chosen=[cover]
    for i in eligible:
        if not any(same_photo(images[i],images[j]) for j in chosen):chosen.append(i)
        if len(chosen)==8:break
    return chosen

def pilot_passes(correct,total):
    return total==20 and correct>=16

def same_photo(first, second):
    """Compare pixels, not filenames; ignore encoding and resolution differences."""
    if abs(first.width/first.height-second.width/second.height)>.06:return False
    a=first.convert('RGB').resize((64,64),Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(1))
    b=second.convert('RGB').resize((64,64),Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(1))
    difference=ImageChops.difference(a,b)
    return sum(ImageStat.Stat(difference).mean)/3 < 10 and ImageStat.Stat(ImageChops.difference(a.convert('L'),b.convert('L'))).mean[0]<8
