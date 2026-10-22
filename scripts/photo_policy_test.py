import unittest
from types import SimpleNamespace
from PIL import Image, ImageDraw
from photo_policy import private_reason, review_image, choose_photos, same_photo, choose_cover_photos, pilot_passes

def photo(width=600,height=600):
    image=Image.new('RGB',(width,height),'white');ImageDraw.Draw(image).rectangle((0,0,width//2,height),fill='red');return image

class PhotoPolicyTests(unittest.TestCase):
    def test_gallery_caps_at_eight_photos_including_cover(self):
        images=[]
        for index in range(10):
            image=Image.new('RGB',(600,600),'white')
            ImageDraw.Draw(image).rectangle((index*55,0,index*55+45,600),fill='black')
            images.append(image)
        selected=choose_cover_photos(images,lambda im:('passed',None),0)
        self.assertEqual(selected,list(range(8)))
    def test_seller_cover_has_priority_over_interior_first(self):
        first=photo();seller=photo();ImageDraw.Draw(seller).rectangle((0,0,300,600),fill='blue')
        self.assertEqual(choose_cover_photos([first,seller],lambda im:('passed',None),1)[0],1)
    def test_missing_cover_prefers_smooth_margin(self):
        fabric=photo();centered=Image.new('RGB',(600,600),'white');ImageDraw.Draw(centered).rectangle((150,100,450,500),fill='blue')
        self.assertEqual(choose_cover_photos([fabric,centered],lambda im:('passed',None))[0],1)
    def test_seller_cover_cannot_bypass_privacy(self):
        first=photo();seller=photo();ImageDraw.Draw(seller).rectangle((0,0,300,600),fill='blue')
        self.assertEqual(choose_cover_photos([first,seller],lambda im:('rejected','chinese') if im is seller else ('passed',None),1),[0])
    def test_continue_threshold_is_sixteen_of_twenty(self):
        self.assertFalse(pilot_passes(15,20))
        self.assertTrue(pilot_passes(16,20))
        self.assertFalse(pilot_passes(16,19))
    def test_position_rule_prefers_last_full_garment_photo(self):
        images=[photo() for _ in range(4)]
        for index,image in enumerate(images):ImageDraw.Draw(image).rectangle((0,0,50+index*40,600),fill='blue')
        self.assertEqual(choose_cover_photos(images,lambda im:('passed',None),0,cover_position='last')[0],3)
    def test_position_rule_never_chooses_a_closeup(self):
        full=photo();closeup=full.resize((120,120))
        self.assertEqual(choose_cover_photos([full,closeup],lambda im:('passed',None),None,cover_position='last')[0],0)
    def test_rejected_last_photo_falls_back_to_previous(self):
        images=[photo() for _ in range(3)]
        self.assertEqual(choose_cover_photos(images,lambda im:('rejected','chinese') if im is images[2] else ('passed',None),None,cover_position='last')[0],1)
    def test_normal_garment_text_is_allowed(self):
        self.assertIsNone(private_reason('Nike Adidas Puma Emirates Real Madrid 23 2024 2025', ['Nike','Adidas','Puma']))
    def test_chinese_is_rejected(self):
        self.assertEqual(private_reason('球衣'),'chinese')
    def test_contact_phone_and_links_rejected(self):
        for text in ['WhatsApp','WeChat','QQ 12345678','+506 7034 1276','www.store.com','http://store','store.com']:
            self.assertIsNotNone(private_reason(text))
    def test_store_name_rejected(self):
        self.assertEqual(private_reason('Example Store',['Example Store']),'store_name')
    def test_timeout_is_not_rejection(self):
        def fail(*args,**kwargs):raise TimeoutError()
        self.assertEqual(review_image(photo(),runner=fail),('error',None))
    def test_unconfirmed_chinese_is_an_error_not_rejection(self):
        responses=iter(['text\tconf\n球\t90\n','text\tconf\nNike\t95\n'])
        def run(*args,**kwargs):return SimpleNamespace(returncode=0,stdout=next(responses))
        self.assertEqual(review_image(photo(),runner=run),('error',None))
    def test_confirmed_chinese_is_rejected(self):
        def run(*args,**kwargs):return SimpleNamespace(returncode=0,stdout='text\tconf\n球衣\t92\n')
        self.assertEqual(review_image(photo(),runner=run),('rejected','chinese'))
    def test_low_confidence_privacy_is_not_rejection(self):
        def run(*args,**kwargs):return SimpleNamespace(returncode=0,stdout='text\tconf\n球衣\t10\n')
        self.assertEqual(review_image(photo(),runner=run),('error',None))
    def test_confirmed_phone_is_rejected(self):
        def run(*args,**kwargs):return SimpleNamespace(returncode=0,stdout='text\tconf\n+50670341276\t95\n')
        self.assertEqual(review_image(photo(),runner=run),('rejected','phone'))
    def test_first_wide_photo_is_kept(self):
        self.assertEqual(choose_photos([photo(900,600),photo()],lambda im:('passed',None)),[0,1])
    def test_rejected_first_photo_skipped(self):
        images=[photo(),photo()]
        self.assertEqual(choose_photos(images,lambda im:('rejected','chinese') if im is images[0] else ('passed',None)),[1])
    def test_small_and_monochrome_skipped(self):
        self.assertEqual(choose_photos([photo(100,100),Image.new('RGB',(600,600),'white'),photo()],lambda im:('passed',None)),[2])
    def test_four_photo_limit(self):
        photos=[photo() for _ in range(6)]
        for index,image in enumerate(photos):ImageDraw.Draw(image).rectangle((index*60,0,index*60+50,600),fill='black')
        self.assertEqual(choose_photos(photos,lambda im:('passed',None)),[0,1,2,3])
    def test_same_image_different_size_is_not_repeated(self):
        first=photo();copy=first.resize((900,900));different=photo()
        ImageDraw.Draw(different).rectangle((0,0,300,600),fill='blue')
        self.assertTrue(same_photo(first,copy))
        self.assertEqual(choose_photos([first,copy,different],lambda im:('passed',None)),[0,2])

if __name__=='__main__':unittest.main()
