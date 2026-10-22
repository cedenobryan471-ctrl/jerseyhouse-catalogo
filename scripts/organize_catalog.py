"""Public catalog organization and generic-only translation, without AI."""
import re, json, html
from pathlib import Path
from collections import Counter
from catalog_rules import identity, slug, ALIASES
from footwear_rules import is_footwear, translate, brand_of, footwear_type
from footwear_rules import BRANDS

LABELS = {'camisetas':'Camisetas','conjuntos':'Conjuntos','chaquetas':'Chaquetas','buzos':'Buzos','shorts':'Shorts','calzado':'Calzado','accesorios':'Accesorios'}
SPECIAL = {'Selecciones':'selecciones','NBA':'nba','NFL':'nfl','NHL':'nhl','Fórmula 1':'formula-1'}
PROTECTED = ['Golden State Warriors','Red Bull','Real Madrid','Inter Miami','Orlando City','Blue Jays','White Sox','Red Sox','Black Stars','New York Red Bulls','Red Bull Racing']
WORDS = [('football t-shirt','Camiseta de fútbol'),('training suit','Camiseta de entrenamiento'),('training kit','Camiseta de entrenamiento'),('tracksuit','Conjunto deportivo'),('windbreaker','Rompevientos'),('hoodie','Sudadera'),('sweatshirt','Sudadera'),('sweater','Suéter'),('long sleeved','manga larga'),('long sleeve','manga larga'),('short sleeve','manga corta'),('t-shirt','Camiseta'),('shirt','Camiseta'),('jersey','Camiseta'),('shorts','Pantaloneta'),('pants','Pantalón'),('trousers','Pantalón'),('jacket','Chaqueta'),('training','entrenamiento'),('home','local'),('away','visitante'),('third','tercera'),('black','negro'),('white','blanco'),('blue','azul'),('red','rojo')]

def generic_title(title, team=None):
    text=html.unescape(title or '')
    text=re.sub(r'\brojo\s+bull\b','Red Bull',text,flags=re.I)
    repairs = {'Golden State Warriors': [('dorado State Warriors','Golden State Warriors')], 'Red Bull Racing': [('rojo Bull','Red Bull')], 'New York Red Bulls': [('New York rojo Bulls','New York Red Bulls')], 'Orlando City': [('Orlando ciudad','Orlando City')]}
    for damaged, original in repairs.get(team, []):text=re.sub(re.escape(damaged),original,text,flags=re.I)
    protected={}
    official=[name for _,name,_ in ALIASES]
    for name in sorted(set(PROTECTED+BRANDS+official+([team] if team else [])),key=len,reverse=True):
        token=f'ZZKEEP{len(protected)}ZZ'
        text,n=re.subn(re.escape(name),token,text,flags=re.I)
        if n:protected[token]=name
    for a,b in WORDS:text=re.sub(r'\b'+re.escape(a)+r'\b',b,text,flags=re.I)
    for token,name in protected.items():text=text.replace(token,name)
    return re.sub(r'\s+',' ',text).strip()

def ordered_title(title, team, category, colors=()):
    text=generic_title(title,team)
    if not team:return text
    text=re.sub(re.escape(team),'',text,flags=re.I)
    if team=='Red Bull Racing':text=re.sub(r'\bRed Bull\b','',text,flags=re.I)
    garment={'shorts':'Pantaloneta','camisetas':'Camiseta','conjuntos':'Conjunto deportivo','chaquetas':'Chaqueta','buzos':'Sudadera'}.get(category)
    if not garment:return generic_title(title,team)
    text=re.sub(r'\b(?:pantaloneta|pantal[oó]n|camiseta(?: de f[uú]tbol)?|conjunto deportivo|chaqueta|rompevientos|sudadera|suéter)\b','',text,flags=re.I)
    text=re.sub(r'\boscur[oa]\s+(azul|rojo|verde|gris)\b',r'\1 oscuro',text,flags=re.I)
    pattern=r'\b(?:azul|rojo|negro|blanco|verde|gris|amarillo|morado|dorado|celeste|naranja|rosado)(?:\s+(?:oscuro|claro))?\b'
    found=re.findall(pattern,text,flags=re.I)
    text=re.sub(pattern,'',text,flags=re.I)
    color=' '.join(dict.fromkeys(c.lower() for c in (found or colors)))
    suffix=re.sub(r'\s+',' ',text).strip(' |+-')
    return ' '.join(part for part in [team,garment,color,suffix] if part)

def classify(title, previous='', team=None):
    t=title.lower()
    if previous in ('calzado','tenis','tacos') or (not team and is_footwear(t)):return 'calzado'
    if re.search(r'\b(?:bags?|backpack|handbag|wallet|caps?|hats?|socks?|scarfs?|scarves|balls?)\b|bolso|mochila|gorra|bufanda|medias|calcet|bal[oó]n|背包|袜',t):return 'accesorios'
    if re.search(r'tracksuit|conjunto|ch[aá]ndal|\bsets?\b|2\s*[- ]?\s*pieces?|套装',t) or (re.search(r'\b(?:kits?|suits?)\b|camiseta\s*\+|top\s*\+',t) and re.search(r'\b(?:shorts?|pants|trousers)\b|pantaloneta|pantal[oó]n|短裤',t)):return 'conjuntos'
    if re.search(r'\b(?:shorts?|pants|trousers)\b|pantaloneta|pantal[oó]n|短裤|长裤',t):return 'shorts'
    if re.search(r'jacket|windbreaker|rompevientos|cortavientos|chaqueta|anthem|夹克|外套',t):return 'chaquetas'
    if re.search(r'hoodie|sweatshirt|sweater|sudadera|suéter|buzo|卫衣',t):return 'buzos'
    if re.search(r'jersey|shirt|camiseta|training|entrenamiento|vest|polo|uniform|\bt\b|球衣|篮球',t):return 'camisetas'
    if previous in LABELS:return previous
    if team:return 'camisetas'
    return None

def section(p):
    if p['categorySlug']=='calzado':return 'calzado'
    if p['categorySlug']=='accesorios':return 'accesorios'
    if p.get('team') and p.get('league'):return SPECIAL.get(p['league'],'futbol')
    return 'ropa-casual'

def organize(items):
    states_path=Path('estado.json');states=json.loads(states_path.read_text()) if states_path.exists() else {}
    review=[];moved=Counter()
    for p in items:
        previous=p.get('categorySlug','');team=p.get('team');league=p.get('league')
        p['title']=generic_title(p.get('title',''),team)
        if not team and re.search(r'\bRed Bull\b',p['title'],re.I):
            team='Red Bull Racing';league='Fórmula 1';p.update(team=team,teamSlug=slug(team),league=league,leagueSlug=slug(league))
        if not team:
            found=identity(p.get('title',''),league)
            if found:team,league=found;p.update(team=team,teamSlug=slug(team),league=league,leagueSlug=slug(league))
        cat=classify(p.get('title',''),previous,team)
        if not cat:
            states[p['id']]='hidden';p['sectionSlug']='revision'
            review.append({'id':p['id'],'reason':'Categoría o identidad no confirmada'})
            continue
        if previous=='otros':moved[cat]+=1
        p.update(categorySlug=cat,category=LABELS[cat])
        if cat in ('calzado','accesorios'):
            p.update(team=None,teamSlug=None,league=None,leagueSlug=None)
        if cat=='calzado':
            p['title']=translate(p['title']);p['brand']=brand_of(p['title']);p['footwearType']=footwear_type(p['title'])
        else:p['title']=ordered_title(p['title'],team,cat,p.get('colors',[]))
        p['sectionSlug']=section(p)
    states_path.write_text(json.dumps(states,ensure_ascii=False,indent=2))
    Path('revisar.json').write_text(json.dumps(review,ensure_ascii=False,indent=2))
    visible=[p for p in items if states.get(p['id'],p.get('status')) in ('active','sold_out') and p.get('cover') and p.get('sectionSlug')!='revision']
    return {'moved_from_others':dict(moved),'review':len(review),'sections_visible':dict(Counter(p['sectionSlug'] for p in visible)),'categories_visible':dict(Counter(p['categorySlug'] for p in visible)),'sections_total':dict(Counter(p.get('sectionSlug') for p in items)),'categories_total':dict(Counter(p['categorySlug'] for p in items))}