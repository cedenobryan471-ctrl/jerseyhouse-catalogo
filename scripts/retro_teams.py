"""Nombres de equipos en chino -> nombre que reconoce identities.identity."""
TEAMS = {
    # Inglaterra / Escocia / Gales / Irlanda
    '曼联': 'Manchester United', '曼彻斯特联': 'Manchester United', '曼城': 'Manchester City', '利物浦': 'Liverpool',
    '纽卡斯尔联': 'Newcastle United', '纽卡斯尔': 'Newcastle United', '阿森纳': 'Arsenal', '切尔西': 'Chelsea', '热刺': 'Tottenham',
    '西汉姆联': 'West Ham United', '阿斯顿维拉': 'Aston Villa', '埃弗顿': 'Everton', '利兹联': 'Leeds United',
    '凯尔特人': 'Celtic', '流浪者': 'Rangers', '科克城': 'Cork City', '德里城': 'Derry City',
    # España
    '巴萨': 'Barcelona', '巴塞': 'Barcelona', '巴塞罗那': 'Barcelona', '皇马': 'Real Madrid', '马竞': 'Atletico Madrid',
    '拉科鲁尼亚': 'Deportivo La Coruna', '瓦伦西亚': 'Valencia', '皇家贝蒂斯': 'Real Betis', '贝蒂斯': 'Real Betis',
    '塞尔塔': 'Celta Vigo', '西班牙人': 'Espanyol', '巴斯克': 'Athletic Bilbao',
    # Italia
    'AC米兰': 'AC Milan', 'AC': 'AC Milan', '国米': 'Inter Milan', '尤文': 'Juventus', '尤W': 'Juventus', '罗马': 'Roma',
    '拉齐奥': 'Lazio', '佛罗伦萨': 'Fiorentina', '那不勒斯': 'Napoli', '威尼斯': 'Venezia',
    # Alemania / Francia / Portugal / Países Bajos
    '拜仁': 'Bayern Munich', '多特': 'Borussia Dortmund', '巴黎': 'PSG', '马赛': 'Marseille', '里昂': 'Lyon', '摩纳哥': 'Monaco',
    '里斯本': 'Sporting CP', '本菲卡': 'Benfica', '波尔图': 'Porto', '阿贾克斯': 'Ajax',
    # América
    '弗拉门戈': 'Flamengo', '桑托斯': 'Santos', '科林蒂安': 'Corinthians', '博塔弗戈': 'Botafogo', '帕尔梅拉斯': 'Palmeiras',
    '圣保罗': 'Sao Paulo', '弗洛米嫩塞': 'Fluminense', '塞阿拉': 'Ceara', '博卡': 'Boca Juniors', '河床': 'River Plate',
    '蒙特雷': 'Monterrey', '老虎队': 'Tigres', '美洲队': 'Club America', '美洲': 'Club America', '洛杉矶银河': 'LA Galaxy',
    '凯撒酋长': 'Kaizer Chiefs', '川崎': 'Kawasaki Frontale',
    # Selecciones
    '爱尔兰': 'Ireland', '巴西': 'Brazil', '葡萄牙': 'Portugal', '冰岛': 'Iceland', '喀麦隆': 'Cameroon', '德国': 'Germany',
    '东德': 'East Germany', '法国': 'France', '南非': 'South Africa', '意大利': 'Italy', '英格兰': 'England', '美国': 'USA',
    '摩洛哥': 'Morocco', '阿根廷': 'Argentina', '西班牙': 'Spain', '苏格兰': 'Scotland', '墨西哥': 'Mexico', '日本': 'Japan',
    '荷兰': 'Netherlands', '哥伦比亚': 'Colombia', '尼日利亚': 'Nigeria', '挪威': 'Norway', '威尔士': 'Wales',
    '克罗地亚': 'Croatia', '土耳其': 'Turkey', '南斯拉夫': 'Yugoslavia', '慢斯拉夫': 'Yugoslavia', '希腊': 'Greece',
    '牙买加': 'Jamaica', '塞内加尔': 'Senegal', '波兰': 'Poland', '韩国': 'South Korea', '科瓦多尔': 'Ecuador', '厄瓜多尔': 'Ecuador',
}
# Prendas que no son camisetas de este cargador (chaquetas, conjuntos de niño, bandas, otros deportes).
SKIP = r'棒球服|外套|童装|套装|裤子|短裤|铁娘子|GAA|橄榄|Oasis|针织'
# Equipos que identities no conoce: (nombre, liga) directos.
EXTRA = {'Iceland': ('Islandia', 'Selecciones'), 'Cork City': ('Cork City', 'Otras ligas'),
         'Derry City': ('Derry City', 'Otras ligas'), 'Kaizer Chiefs': ('Kaizer Chiefs', 'Otras ligas')}
