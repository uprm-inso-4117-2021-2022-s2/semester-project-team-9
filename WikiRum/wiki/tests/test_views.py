

import imp
from ipaddress import collapse_addresses
from turtle import title
from django.http import response
from django.test import TestCase
from django.test import TestCase, Client
from django.urls import reverse
from wiki.models import WikiPage, SubTopic
import json

class TestViews(TestCase):
    def setUp(self):
        self.client = Client()
        self.home_url = reverse('home')
        self.wikipage_url = reverse('wikipage',args=['Spanish'])
        self.spanishpage = WikiPage.objects.create(
            title = 'Spanish',
            text = 'This is **bold**.'
        )

    def test_home_get(self):

        response = self.client.get(self.home_url)

        self.assertEquals(response.status_code,200)

    def test_wikipage_get(self):
        response = self.client.get(self.wikipage_url)

        self.assertEquals(response.status_code,200)
        self.assertTemplateUsed(response, 'pageview.html')
        