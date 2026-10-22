"""Nombres de selecciones en español dentro del título y tallas de niño correctas. Sin IA."""
import json, re, sys
from pathlib import Path

COUNTRIES = {'Brazil': 'Brasil', 'Spain': 'España', 'England': 'Inglaterra', 'Germany': 'Alemania', 'France': 'Francia',
    'Japan': 'Japón', 'Italy': 'Italia', 'Mexico': 'México', 'Netherlands': 'Países Bajos', 'Holland': 'Países Bajos',
    'Scotland': 'Escocia', 'Ireland': 'Irlanda', 'Wales': 'Gales', 'South Korea': 'Corea del Sur', 'Korea': 'Corea del Sur',
    'USA': 'Estados Unidos', 'United States': 'Estados Unidos', 'Belgium': 'Bélgica', 'Algeria': 'Argelia', 'Morocco': 'Marruecos',
    'Ivory Coast': 'Costa de Marfil', 'Croatia': 'Croacia', 'Poland': 'Polonia', 'Sweden': 'Suecia', 'Norway': 'Noruega',
    'Denmark': 'Dinamarca', 'Switzerland': 'Suiza', 'Turkey': 'Turquía', 'Greece': 'Grecia', 'Russia': 'Rusia', 'Peru': 'Perú',
    'Cameroon': 'Camerún', 'Egypt': 'Egipto', 'Saudi Arabia': 'Arabia Saudita', 'Northern Ireland': 'Irlanda del Norte',
    'Czech Republic': 'República Checa', 'Austria': 'Austria', 'Ukraine': 'Ucrania', 'Hungary': 'Hungría', 'Iceland': 'Islandia',
    'Senegal': 'Senegal', 'Ghana': 'Ghana', 'Jamaica': 'Jamaica', 'Canada': 'Canadá', 'Australia': 'Australia', 'Serbia': 'Serbia',
    'Finland': 'Finlandia', 'Romania': 'Rumania', 'Tunisia': 'Túnez', 'Qatar': 'Catar', 'Iran': 'Irán', 'Panama': 'Panamá',
    'Venezuela': 'Venezuela', 'Ecuador': 'Ecuador', 'Paraguay': 'Paraguay', 'Bolivia': 'Bolivia', 'Honduras': 'Honduras',
    'Costa Rica': 'Costa Rica', 'Palestine': 'Palestina', 'China': 'China', 'Thailand': 'Tailandia', 'New Zealand': 'Nueva Zelanda'}
PHRASES = [(r'\bspecial\s+edici[oó]n\b', 'Edición especial'), (r'\bspeci?al\s+edition\b', 'Edición especial'), (r'\blimited\s+edici[oó]n\b', 'Edición limitada'),
    (r'\bplayer\s+version\b', 'Versión jugador'), (r'\bfan\s+version\b', 'Versión aficionado'), (r'\bworld\s+cup\b', 'Mundial'),
    (r'\bcommemorative\b', 'Conmemorativa'), (r'\banniversary\b', 'Aniversario'), (r'\bfourth\b', 'Cuarta'), (r'\bpre-?match\b', 'Pre-partido'),
    (r'\bgoalkeeper\b|\bGK\b', 'Portero'), (r'\bjackets?\b', 'Chaqueta'), (r'\bhoodies?\b', 'Sudadera'), (r'\bshirts?\b', 'Camiseta'),
    (r'\btracksuits?\b', 'Conjunto deportivo'), (r'\bsuits?\b', 'Conjunto'), (r'\bconcept\b', 'Concepto'), (r'\btraining\b', 'entrenamiento')]
KIDS = re.compile(r'\bkids?\b|\byouth\b|\bchildren\b|\binfant\b|\bbaby\b|\bniñ[oa]s?\b', re.I)
KIDS_WORDS = re.compile(r'\b(?:kid|kids)\s+kits?\b|\bkids?\b|\byouth\b|\bchildren\s+sets?\b|\bchildren\b', re.I)

def main():
    items = json.loads(Path('catalog.json').read_text()); renamed = kids = 0
    names = sorted(COUNTRIES, key=len, reverse=True)
    pattern = re.compile(r'(?<![A-Za-zÀ-ÿ])(' + '|'.join(map(re.escape, names)) + r')(?![A-Za-zÀ-ÿ])')
    for p in items:
        if p.get('categorySlug') == 'calzado': continue
        t = p.get('title') or ''
        new = pattern.sub(lambda m: COUNTRIES[m.group(1)], t)
        for rx, repl in PHRASES: new = re.sub(rx, repl, new, flags=re.I)
        new = re.sub(r'\b(Camiseta|Chaqueta|Conjunto)(?:\s+\1\b)+', r'\1', new)
        m = re.search(r'(?:size\s*:?\s*)?\b(1[0-9]|2[0-9])\s*-\s*(2[0-9]|3[0-9])\b', new, re.I)
        kid_sizes = None
        if m and KIDS.search(new):
            a, b = int(m.group(1)), int(m.group(2)); kid_sizes = [str(x) for x in range(a, b + 1, 2)]
            new = new.replace(m.group(0), ' ')
        if KIDS.search(new):
            new = re.sub(r'\s+', ' ', KIDS_WORDS.sub(' ', new)).strip()
            if not new.endswith('(Niño)'): new += ' (Niño)'
            if kid_sizes: p['sizes'] = kid_sizes
            elif p.get('sizes') == ['S', 'M', 'L', 'XL', '2XL'] or not p.get('sizes'):
                p['sizes'] = ['Consultar talla de niño']
            p['audiences'] = ['nino']; kids += 1
        new = re.sub(r'\s+', ' ', new).strip()
        if new != t: p['title'] = new; renamed += 1
    Path('catalog.json').write_text(json.dumps(items, ensure_ascii=False, separators=(',', ':')))
    print(json.dumps({'renamed': renamed, 'kids': kids}))

if __name__ == '__main__':
    main()
