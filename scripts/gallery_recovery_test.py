import unittest
from gallery_recovery import unique_matches, needs_recovery
from pathlib import Path
from tempfile import TemporaryDirectory

class MappingTests(unittest.TestCase):
    def test_missing_extra_photos_are_recovered_again(self):
        product={'id':'12','gallery':['12-1.webp','12-2.webp','12-3.webp']}
        with TemporaryDirectory() as directory:
            extras=Path(directory);recovery={'12':{'policy':'seller-cover-v5-position'}}
            self.assertTrue(needs_recovery(product,recovery,extras))
            for key in product['gallery']:(extras/key).write_bytes(b'photo')
            self.assertFalse(needs_recovery(product,recovery,extras))
    def test_different_teams_cannot_share_photos(self):
        product={'id':'12','title':'Camiseta','team':'Real Madrid','league':'LaLiga','category':'Camisetas'}
        row={'clean_title':'Camiseta','teams':{'name':'Inter Miami'},'leagues':{'name':'LaLiga'},'categories':{'name':'Camisetas'}}
        self.assertEqual(unique_matches([product],[row],lambda v:str(v or '')), {})
    def test_matches_by_metadata_not_position(self):
        original=[{'id':'12','title':'Camiseta Real Madrid','season':'2025','version':'fan','sizes':['S'],'audiences':['hombre']}]
        row={'id':'private-id','clean_title':'Camiseta Real Madrid','season':'2025','version':'fan','sizes':['S'],'audiences':['hombre']}
        self.assertEqual(unique_matches(original,[row],lambda v:str(v or ''))['12']['id'],'private-id')
    def test_ambiguous_products_are_not_assigned_photos(self):
        product={'id':'12','title':'Camiseta','season':None,'version':None,'sizes':[],'audiences':[]}
        row={'clean_title':'Camiseta'}
        self.assertEqual(unique_matches([product],[row,row],lambda v:str(v or '')), {})
        self.assertEqual(unique_matches([product,{**product,'id':'13'}],[row],lambda v:str(v or '')), {})
if __name__=='__main__':unittest.main()
