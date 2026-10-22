import unittest
from footwear_rules import footwear_sole, footwear_collar, footwear_group, footwear_type, shoe_sizes, brand_of, footwear_key, is_footwear, translate

class FootwearRules(unittest.TestCase):
    def test_casual_shirt_is_not_footwear(self):
        self.assertFalse(is_footwear('River Plate casual shirt'))
        self.assertFalse(is_footwear('Brazil casual T-Shirt'))
        self.assertFalse(is_footwear('2023/24 Flamengo blanco casual T'))
        self.assertFalse(is_footwear('Brazil casual T'))
        self.assertTrue(is_footwear('Nike casual shoes'))
    def test_football_terms(self):
        for term in ['cleats', 'football boots', 'FG', 'AG', 'TF', 'SG', 'IC', 'futsal', 'tacos', 'guayos', '足球鞋']:
            self.assertEqual(footwear_type(term), 'futbol')
    def test_football_models(self):
        for term in ['Nike Mercurial', 'Adidas Predator', 'Mizuno Morelia', 'Puma Future', 'Nike Phantom', 'Adidas Copa']:
            self.assertEqual(footwear_type(term), 'futbol')
    def test_sports_default(self):
        for term in ['sneakers', 'running', 'basketball', 'trainers', 'casual', 'unknown']:
            self.assertEqual(footwear_type(term), 'deportivos')
    def test_groups(self):
        for t, g in [('Nike Mercurial Vapor XV Elite FG', 'tacos'), ('Adidas Predator Elite SG', 'tacos'), ('Nike Mercurial Vapor IC', 'futbol'),
                     ('Adidas Copa TF', 'futbol'), ('Nike MD Streetgato', 'futbol'), ('Adidas Gazelle Indoor', 'casual'),
                     ('Hoka Clifton 9', 'correr'), ('New Balance 574', 'casual'), ('Nike T90 MD', 'futbol'), ('Nike Vapor Edge 360', 'americano'), ('Adidas F50 HYPERFAST EVO', 'tacos'), ('Adidas X23TF', 'futbol')]:
            self.assertEqual(footwear_group(t), g, t)
    def test_sole_collar(self):
        self.assertEqual(footwear_sole('Nike Mercurial Vapor XV Elite FG'), 'fijo')
        self.assertEqual(footwear_sole('Adidas Predator Elite SG'), 'atornillado')
        self.assertEqual(footwear_sole('Nike Phantom TF'), 'taquillo')
        self.assertEqual(footwear_sole('Nike Mercurial IC'), 'lisa')
        self.assertEqual(footwear_collar('Nike Bota alta Superfly 10 Elite FG'), 'alta')
        self.assertEqual(footwear_collar('Adidas Predator Freak+ FG'), 'alta')
        self.assertEqual(footwear_collar('Nike Vapor 15 Elite FG'), 'baja')
    def test_range_39_45(self):
        self.assertEqual(shoe_sizes('Nike 39-45'), ['39', '40', '41', '42', '43', '44', '45'])
    def test_missing_sizes(self):
        self.assertEqual(shoe_sizes('Jordan model 2026'), ['Consultar talla'])
    def test_brands(self):
        self.assertEqual(brand_of('new balance running'), 'New Balance')
        self.assertEqual(brand_of('unbranded shoes'), 'Otras marcas')
        self.assertEqual(brand_of('Salomon trail'), 'Salomon')
        self.assertEqual(brand_of('On Running cloud'), 'On Running')
    def test_duplicate_size_range(self):
        a = dict(brand='Nike', footwearType='futbol', title='Nike Mercurial FG 39-45')
        b = dict(a, title='Nike Mercurial FG 40-44')
        self.assertEqual(footwear_key(a), footwear_key(b))
    def test_different_models(self):
        a = dict(brand='Nike', footwearType='deportivos', title='Air Max 90')
        b = dict(a, title='Air Max 95')
        self.assertNotEqual(footwear_key(a), footwear_key(b))
    def test_translate_nicknames(self):
        self.assertEqual(translate('贝壳头 36-45'), 'Adidas Superstar 36-45')
        self.assertEqual(translate('空军一号 高帮'), 'Nike Air Force 1 Bota alta')
        self.assertEqual(translate('阿迪马拉松 公司级'), 'Adidas Marathon')
        self.assertEqual(translate('新百伦 面包鞋'), 'New Balance Bread')
        self.assertEqual(translate('乔丹 联名 顶级 1:1'), 'Jordan Edición colaboración')
    def test_translate_removes_chinese(self):
        self.assertNotRegex(translate('耐克 跑步鞋 男女款'), r'[一-鿿]')
        self.assertEqual(translate('顶级 纯原 版本 原厂'), '')

if __name__ == '__main__': unittest.main()
