import unittest
from bs4 import BeautifulSoup
from photo_candidates import image_candidates, album_originals, seller_cover

class PhotoCandidateRules(unittest.TestCase):
    def test_seller_header_cover_resolves_to_original_not_tiny_preview(self):
        page=BeautifulSoup('<div class="showalbumheader__gallerycover"><img src="/small/selected.jpg"></div><div class="showalbum__children"><img data-origin-src="/original/first.jpg"><img src="/medium/selected.jpg" data-origin-src="/original/selected.jpg"></div>','html.parser')
        self.assertEqual(seller_cover(page,'https://example.invalid/albums/12'),'https://example.invalid/original/selected.jpg')
    def test_noscript_preview_does_not_become_an_album_original(self):
        page=BeautifulSoup('<div class="showalbum__children"><img data-origin-src="/full.jpg"><noscript><img src="/small.jpg"></noscript></div>','html.parser')
        self.assertEqual(album_originals(page,'https://example.invalid/albums/12'),['https://example.invalid/full.jpg'])
    def test_cover_comes_from_exact_album_card(self):
        page=BeautifulSoup('<a href="/albums/99"><img src="/wrong.jpg"></a><a href="/albums/12?tab=gallery"><img data-src="/seller.jpg"></a>','html.parser')
        self.assertEqual(seller_cover(page,'https://example.invalid/albums/12'), 'https://example.invalid/seller.jpg')
    def test_missing_seller_cover_is_not_other_album(self):
        page=BeautifulSoup('<a href="/albums/99"><img src="/wrong.jpg"></a>','html.parser')
        self.assertIsNone(seller_cover(page,'https://example.invalid/albums/12'))
    def test_album_order_with_one_original_per_photo(self):
        page=BeautifulSoup('<div class="showalbum__children"><img data-origin-src="/first.jpg" src="/tiny.jpg"><img data-origin-src="/second.jpg"></div>','html.parser')
        self.assertEqual(album_originals(page,'https://example.invalid/album'),['https://example.invalid/first.jpg','https://example.invalid/second.jpg'])
    def test_original_before_thumbnail(self):
        page=BeautifulSoup('<div class="showalbum__children"><img data-origin-src="/full.jpg"></div><img data-origin-src="/tiny-detail.jpg">','html.parser')
        self.assertEqual(album_originals(page,'https://example.invalid/album'),['https://example.invalid/full.jpg'])
    def test_candidate_original_before_thumbnail(self):
        page=BeautifulSoup('<div class="showalbum__children"><img data-full="/full.jpg" data-src="/tiny.jpg"></div>','html.parser')
        self.assertEqual(image_candidates(page,'https://example.invalid/album'),['https://example.invalid/full.jpg','https://example.invalid/tiny.jpg'])
    def test_largest_srcset_first(self):
        page=BeautifulSoup('<div class="showalbum__children"><img srcset="/small.jpg 100w, /large.jpg 900w" src="data:image/png;base64,a"></div>','html.parser')
        self.assertEqual(image_candidates(page,'https://example.invalid/album'),['https://example.invalid/large.jpg','https://example.invalid/small.jpg'])

if __name__=='__main__':unittest.main()