import unittest
from organize_catalog import classify, generic_title, section, ordered_title
from batch_rules import batch_slice

class OrganizationRules(unittest.TestCase):
    def test_red_bull_order_and_dark_blue(self):
        self.assertEqual(ordered_title('rojo bull oscuro azul Pantaloneta','Red Bull Racing','shorts',['azul']),'Red Bull Racing Pantaloneta azul oscuro')
    def test_team_names_do_not_become_colors(self):
        self.assertEqual(ordered_title('Golden State Warriors Shorts blue','Golden State Warriors','shorts'),'Golden State Warriors Pantaloneta azul')
    def test_shorts_never_shirts(self):
        for text in ['Football T-shirt shorts','training pants','NBA trousers','短裤']:
            self.assertEqual(classify(text,'camisetas','Real Madrid'),'shorts')
    def test_two_piece(self):
        self.assertEqual(classify('training kit shorts'),'conjuntos')
        self.assertEqual(classify('training kit'),'camisetas')
        self.assertEqual(classify('Short Traning Suits Soccer Jerseys'),'conjuntos')
        self.assertEqual(classify('Polo(Camiseta+Pantalón)'),'conjuntos')
        self.assertEqual(classify('Vest Kits(Top+Pantaloneta)'),'conjuntos')
    def test_accessories(self):
        for text in ['bolso','gorra','bufanda','medias','balón']:
            self.assertEqual(classify(text),'accesorios')
    def test_unknown(self):
        self.assertIsNone(classify('unidentified model','otros'))
    def test_preserve_names(self):
        self.assertEqual(generic_title('dorado State Warriors Shorts','Golden State Warriors'),'Golden State Warriors Pantaloneta')
        for team in ['Golden State Warriors','Red Bull','Real Madrid','Inter Miami','Orlando City','Blue Jays','White Sox','Red Sox','Black Stars']:
            self.assertEqual(generic_title(team+' Football T-shirt',team),team+' Camiseta de fútbol')
    def test_generic_words(self):
        for a,b in [('Shorts','Pantaloneta'),('Tracksuit','Conjunto deportivo'),('Windbreaker','Rompevientos'),('Hoodie','Sudadera')]:
            self.assertEqual(generic_title(a),b)
    def test_sports_separate(self):
        for league,expected in [('NBA','nba'),('NFL','nfl'),('NHL','nhl'),('Fórmula 1','formula-1'),('Selecciones','selecciones'),('LaLiga','futbol')]:
            self.assertEqual(section({'league':league,'team':'Team','categorySlug':'camisetas'}),expected)
    def test_bounded_resume(self):
        self.assertEqual(batch_slice(100,8,8),(8,16))
        self.assertEqual(batch_slice(10,8,8),(8,10))
        self.assertEqual(batch_slice(10,10,8),(0,8))

if __name__=='__main__':unittest.main()