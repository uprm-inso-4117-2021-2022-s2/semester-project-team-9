from email.policy import default
from django.db import models
from django.contrib.auth.models import User
from django.db.models.deletion import CASCADE
import markdown
# Create your models here.


class WikiPage(models.Model):
    title = models.CharField(max_length=50)
    text = models.TextField(max_length=4000)
    img = models.ImageField(upload_to='images', default= None, blank=True)

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

class Edit(models.Model):
    old_text = models.TextField(max_length=4000)
    new_text = models.TextField(max_length=4000)
    edited_at = models.DateTimeField(auto_now_add=True)


