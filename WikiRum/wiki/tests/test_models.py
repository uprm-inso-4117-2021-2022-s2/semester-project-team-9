from django.test import TestCase
import markdown
from wiki.models import WikiPage, SubTopic

class TestModels(TestCase):
    def setUp(self):
        self.spanishpage = WikiPage.objects.create(
            title = 'Spanish',
            text = 'This is **bold**.'
        )
        self.spanishclasses = SubTopic.objects.create(
            title = 'Classes',
            text = "These are some of the classes we offer",
            topic = self.spanishpage
        )
        self.spanishsubtopic1 = SubTopic.objects.create(
            title = 'SubTopic1',
            text = "yeah",
            topic = self.spanishpage
        )

    def test_page_gettext(self):
        self.assertEquals(self.spanishpage.get_text(),markdown.markdown('This is **bold**.'))
    
    def test_page_get_subtopics(self):
        #print(self.spanishpage.get_sub_topics()[1])
        self.assertEquals(len(self.spanishpage.get_sub_topics()), 2)
        self.assertEquals(self.spanishpage.get_sub_topics()["SubTopic1"], "<p>yeah</p>")
