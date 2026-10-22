"""Extract original image candidates without leaking their addresses."""
from urllib.parse import urljoin, urlparse

ATTRIBUTES=('data-origin-src','data-original','data-full','data-large','data-zoom-image','data-src','src')

def seller_cover(page, album_url):
    """Extract only the thumbnail belonging to the exact album card."""
    header=page.select_one('.showalbumheader__gallerycover img')
    if header is not None:
        value=next((header.get(a) for a in ATTRIBUTES if header.get(a) and not header.get(a).startswith('data:')),None)
        if value:
            filename=urlparse(value).path.rsplit('/',1)[-1]
            for image in page.select('.showalbum__children img[data-origin-src]'):
                if any(urlparse(image.get(a,'')).path.rsplit('/',1)[-1]==filename for a in ATTRIBUTES):
                    return urljoin(album_url,image['data-origin-src'])
            return urljoin(album_url,value)
    target=urlparse(album_url).path.rstrip('/')
    for anchor in page.select('a[href]'):
        if urlparse(urljoin(album_url,anchor['href'])).path.rstrip('/')!=target:continue
        image=anchor.find('img')
        if image is None:continue
        value=next((image.get(a) for a in ATTRIBUTES if image.get(a) and not image.get(a).startswith('data:')),None)
        if value:return urljoin(album_url,value)
    return None

def cover_listing_pages(page, album_url):
    origin=urlparse(album_url)
    candidates=[]
    for anchor in page.select('a[href]'):
        url=urljoin(album_url,anchor['href']);parts=urlparse(url)
        if parts.netloc==origin.netloc and '/categories/' in parts.path and url not in candidates:candidates.append(url)
    return (candidates+[f'{origin.scheme}://{origin.netloc}/albums?tab=gallery'])[:4]

def image_candidates(page,base):
    candidates=[]
    for image in page.select('.showalbum__children img, .showalbum__children [data-src], img[data-photoindex], img[data-original], img[data-origin-src], img[data-full], img[data-large], img[data-zoom-image]'):
        values=[image.get(attribute) for attribute in ATTRIBUTES[:5]]
        srcset=[]
        for part in (image.get('srcset') or image.get('data-srcset') or '').split(','):
            fields=part.strip().split()
            if fields:
                try:weight=float(fields[1].rstrip('wx')) if len(fields)>1 else 0
                except ValueError:weight=0
                srcset.append((weight,fields[0]))
        values += [value for _,value in sorted(srcset,reverse=True)]
        values += [image.get(attribute) for attribute in ATTRIBUTES[5:]]
        for value in values:
            if value and not value.startswith('data:'):
                absolute=urljoin(base,value)
                if absolute not in candidates:candidates.append(absolute)
    return candidates

def album_originals(page,base):
    """One original per album photo, preserving the album's DOM order."""
    candidates=[]
    album_images=page.select('.showalbum__children img[data-origin-src]') or [im for im in page.select('.showalbum__children img') if im.find_parent('noscript') is None]
    for image in album_images or page.select('img[data-photoindex], img[data-origin-src], img[data-original]'):
        value=next((image.get(attribute) for attribute in ATTRIBUTES[:5] if image.get(attribute)),None)
        if not value:
            weighted=[]
            for part in (image.get('srcset') or image.get('data-srcset') or '').split(','):
                fields=part.strip().split()
                if fields:
                    try:weight=float(fields[1].rstrip('wx')) if len(fields)>1 else 0
                    except ValueError:weight=0
                    weighted.append((weight,fields[0]))
            value=max(weighted)[1] if weighted else image.get('data-src') or image.get('src')
        if value and not value.startswith('data:'):
            absolute=urljoin(base,value)
            if absolute not in candidates:candidates.append(absolute)
    return candidates