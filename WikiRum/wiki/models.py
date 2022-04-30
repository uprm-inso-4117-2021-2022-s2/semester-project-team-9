from email.policy import default
from unicodedata import category
from django.db import models
from django.contrib.auth.models import User
from django.db.models.deletion import CASCADE
from django.contrib.auth.models import User
import markdown
# Create your models here.


class WikiPage(models.Model):
    title = models.CharField(max_length=50)
    text = models.TextField(max_length=4000)
    img = models.ImageField(upload_to='images', default= None, blank=True)
    created_by = models.ForeignKey(User, related_name='pages',on_delete=CASCADE, null=True)
    category = models.CharField(max_length=50, null=True)

    def get_text(self):
         return markdown.markdown(self.text)

    def get_sub_topics(self):
        topics = self.subtopics.all()
        topics_text = {}
        for t in topics:
            topics_text[t.title] = markdown.markdown(t.text)
        return topics_text

class SubTopic(models.Model):
    title = models.CharField(max_length=50)
    text = models.TextField(max_length=4000)
    topic = models.ForeignKey(WikiPage,related_name='subtopics',on_delete=CASCADE)
    img = models.ImageField(upload_to='images',  default= None, blank=True)
    created_by = models.ForeignKey(User, related_name='topics',on_delete=CASCADE, null=True)
    def get_text(self):
         return markdown.markdown(self.text)

class Edit(models.Model):
    old_text = models.TextField(max_length=4000)
    new_text = models.TextField(max_length=4000)
    edited_at = models.DateTimeField(auto_now_add=True)
    edited_by = models.ForeignKey(User, related_name='edits',on_delete=CASCADE, null=True)
