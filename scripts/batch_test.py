import unittest
from run_batch import classify,generic_title,section,batch_slice
class Rules(unittest.TestCase):
 def test_shorts(self):
  for t in ['Football T-shirt shorts','training pants','NBA trousers','短裤']:self.assertEqual(classify(t,'camisetas','Real Madrid'),'shorts')
 def test_sets(self):
  self.assertEqual(classify('training kit shorts'),'conjuntos');self.assertEqual(classify('training kit'),'camisetas')
 def test_unknown(self):self.assertIsNone(classify('unidentified model','otros'))
 def test_names(self):
  for t in ['Golden State Warriors','Red Bull','Real Madrid','Inter Miami','Orlando City','Blue Jays','White Sox','Red Sox','Black Stars']:self.assertEqual(generic_title(t+' Football T-shirt',t),t+' Camiseta de fútbol')
 def test_sections(self):
  for league,expected in [('NBA','nba'),('NFL','nfl'),('NHL','nhl'),('Fórmula 1','formula-1'),('Selecciones','selecciones'),('LaLiga','futbol')]:self.assertEqual(section({'league':league,'team':'Team','categorySlug':'camisetas'}),expected)
 def test_resume(self):self.assertEqual(batch_slice(100,8),(8,16))
if __name__=='__main__':unittest.main()
