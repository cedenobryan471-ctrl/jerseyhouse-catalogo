"""Pure footwear classification, translation, size parsing and duplicate identity rules."""
import re
import unicodedata

BRANDS = ['New Balance', 'On Running', 'Under Armour', 'Loro Piana', 'Nike', 'Adidas', 'Puma', 'Asics',
          'Mizuno', 'Jordan', 'Converse', 'Vans', 'Reebok', 'Umbro', 'Joma', 'Lotto', 'Skechers',
          'Salomon', 'Timberland', 'Norda', 'Kailas', 'Hoka', 'Fila', 'Saucony', 'Brooks', 'Keen']
FOOTBALL_MODELS = re.compile(
    r'\b(?:mercurial|phantom|tiempo|predator|copa\s+mundial|\bcopa\b|future|morelia|ultra\s+match|'
    r'cleats?|football\s+boots?|soccer\s+(?:shoes?|boots?)|fg|ag|tf|sg|ic|futsal|tacos|guayos)\b|足球鞋|钉鞋',
    re.I)
FOOTWEAR = re.compile(r'\b(?:shoes?|sneakers?|running|basketball\s+shoes?|trainers?|casual|tenis|slides?|sandals?|boots?)\b|鞋', re.I)
SIZE_RANGE = re.compile(r'(?<![\d.])((?:[2-4]\d|50)(?:\.5)?)\s*[-–~至]\s*((?:[2-4]\d|50)(?:\.5)?)(?![\d.])')

# Chinese nicknames -> brand/model. Longest keys first so 阿迪马拉松 wins over 阿迪.
NICKNAMES = [
    ('阿迪马拉松', 'Adidas Marathon'), ('阿迪达斯', 'Adidas'), ('贝壳头', 'Adidas Superstar'),
    ('阿尔法', 'Adidas Alphabounce'), ('空军一号', 'Nike Air Force 1'), ('开拓者', 'Nike Blazer'),
    ('登月飞马', 'Nike Pegasus'), ('新百伦', 'New Balance'), ('天伯伦', 'Timberland'),
    ('萨洛蒙', 'Salomon'), ('昂跑', 'On Running'), ('诺达', 'Norda'), ('凯乐石', 'Kailas'),
    ('美津浓', 'Mizuno'), ('亚瑟士', 'Asics'), ('彪马', 'Puma'), ('乔丹', 'Jordan'),
    ('万斯', 'Vans'), ('耐克', 'Nike'), ('阿迪', 'Adidas'), ('面包鞋', 'Bread'),
    ('联名', 'Edición colaboración'), ('高帮', 'Bota alta'), ('薄底', 'Suela delgada'),
]
SUPPLIER_WORDS = re.compile(r'公司级|原厂|纯原|顶级|版本|\btop\b|original\s+quality|1\s*[:：]\s*1', re.I)
CHINESE = re.compile(r'[一-鿿]+')


def translate(title):
    """Replace Chinese nicknames with brand/model names, then drop remaining Chinese."""
    out = str(title or '')
    for zh, latin in NICKNAMES:
        out = out.replace(zh, ' ' + latin + ' ')
    out = SUPPLIER_WORDS.sub(' ', out)
    out = CHINESE.sub(' ', out)
    return re.sub(r'\s+', ' ', out).strip(' -_,;.')


def footwear_type(title):
    return 'futbol' if FOOTBALL_MODELS.search(title) else 'deportivos'


def is_footwear(title):
    if re.search(r'\b(?:jerseys?|shirts?|t[ -]?shirts?|shorts?|pants|jackets?|hoodies?|polo|camiseta|sudadera|bolso|bags?)\b|\bcasual\s+t\b|球衣|短裤|卫衣', title, re.I):
        return False
    return bool(FOOTBALL_MODELS.search(title) or FOOTWEAR.search(title))


def brand_of(title):
    for brand in BRANDS:
        if re.search(r'(?<![a-z])' + re.escape(brand) + r'(?![a-z])', title, re.I):
            return brand
    return 'Otras marcas'


def shoe_sizes(title):
    match = SIZE_RANGE.search(title)
    if match:
        start, end = float(match[1]), float(match[2])
        if start <= end and end - start <= 20:
            step = .5 if start % 1 or end % 1 else 1
            return [format(start + i * step, 'g') for i in range(int((end - start) / step) + 1)]
    match = re.search(r'(?:\b(?:EU|EUR|size|sizes|talla|tallas)\s*[:：]?\s*|尺码\s*[:：]?\s*)((?:(?:[2-4]\d|50)(?:\.5)?[\s,;/]*)+)', title, re.I)
    return list(dict.fromkeys(re.findall(r'(?:[2-4]\d|50)(?:\.5)?', match[1]))) if match else ['Consultar talla']


def footwear_key(product):
    title = SIZE_RANGE.sub('', product.get('title') or '')
    title = re.sub(r'\b(?:EU|EUR|size|sizes|talla|tallas)\s*[:：]?\s*(?:\d+(?:\.5)?[\s,;/]*)+', '', title, flags=re.I)
    title = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode().lower()
    return (product.get('brand'), product.get('footwearType'), re.sub(r'[^a-z0-9]+', ' ', title).strip())


CLEATS = re.compile(r'(?<![a-z])(?:fg|sg|ag|mg|hg|cleats?|tacos|guayos|football\s+boots?)(?![a-z])|钉鞋', re.I)
INDOOR = re.compile(r'(?<![a-z])(?:tf|ic|in|futsal|turf|indoor|astro|sala|streetgato|gato|md|t90)(?![a-z])|bota alta md|\b16\s+air\s+max', re.I)
AMERICAN_CLEATS = re.compile(r'vapor\s+edge|alpha\s+menace|force\s+savage|vapor\s+untouchable|adizero\s+impact|rugby|american\s+football', re.I)
RUNNING = re.compile(r'hoka|pegasus|vomero|ultraboost|adizero|alphafly|vaporfly|zoomx|invincible|zoom\s*fly|wildhorse|terra\s+kiger|journey\s+run|flex\s+experience|\bquest\b|brooks|ghost|saucony|triumph|wave\s+rider|\bcloud|marathon|alphabounce|mafate|clifton|bondi|\bmach\b|cielo|challenger|arahi|norda|terrex|trail|maxfly|zoom\s+victory|rival|skylon|metcon|ultra\s+glide', re.I)
CASUAL_MODELS = re.compile(r'gazelle|samba|superstar|campus|spezial|sl\s*72|taekwondo|handball', re.I)
BOOT_LINES = re.compile(r'mercurial|phantom|tiempo|predator|\bcopa\b|\bf50\b|future|morelia|furon|crazyfast|speedportal|\bx\s*\d{2}', re.I)


def footwear_group(title):
    """Tacos, tenis de fútbol (sala/sintética), tenis para correr o tenis casuales."""
    t = title or ''
    if CASUAL_MODELS.search(t) and not CLEATS.search(t): return 'casual'
    if AMERICAN_CLEATS.search(t): return 'americano'
    if CLEATS.search(t): return 'tacos'
    if INDOOR.search(t): return 'futbol'
    if BOOT_LINES.search(t): return 'tacos'
    if RUNNING.search(t): return 'correr'
    return 'casual'


HIGH_COLLAR = re.compile(r'bota\s+alta|superfly|(?<![a-z])df(?![a-z])|dynamic\s+fit|(?<![a-z])high(?![a-z])|freak\s*\+|elite\s*\+|\+\s*(?:fg|sg|tf|ag)|laceless|(?<![a-z])mid(?![a-z])', re.I)


def footwear_sole(title):
    """Suela: lisa (IC), taquillo (TF), fijo (FG/AG/MG/HG), atornillado (SG) u otros."""
    t = title or ''
    if re.search(r'(?<![a-z])(?:sg|sg-pro)(?![a-z])', t, re.I): return 'atornillado'
    if re.search(r'(?<![a-z])(?:fg|ag|mg|hg)(?![a-z])|fg/ag', t, re.I): return 'fijo'
    if re.search(r'(?<![a-z])(?:tf|turf)(?![a-z])', t, re.I): return 'taquillo'
    if re.search(r'(?<![a-z])(?:ic|in|futsal|indoor|sala)(?![a-z])', t, re.I): return 'lisa'
    return 'otros'


def footwear_collar(title):
    return 'alta' if HIGH_COLLAR.search(title or '') else 'baja'
