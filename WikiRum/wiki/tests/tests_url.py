import imp
from django.test import SimpleTestCase
from django.urls import reverse, resolve
from wiki.views import home, ViewWikiPage

class TestUrls(SimpleTestCase):

    def test_home_url_is_resolves(self):
        url = reverse('home')
        self.assertEquals(resolve(url).func, home)

    def test_wikipage_url_resolves(self):
        url = reverse('wikipage', args=['English'])
        self.assertEquals(resolve(url).func, ViewWikiPage)