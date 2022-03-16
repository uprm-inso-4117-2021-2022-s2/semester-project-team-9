from cgitb import text
import imp
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse
import markdown
from .models import WikiPage, SubTopic


# Create your views here.


def home(request):
    t = '#**hello** my *friend*'
    
    return render(request,'home.html')


def ViewWikiPage(request,title):
    #page = WikiPage.objects.get(title=title)
    page = get_object_or_404(WikiPage, title=title)
    page_text = page.get_text()
    # topics = page.subtopics.all()
    topics_text = page.get_sub_topics()

    # for t in topics:
    #     topics_text[t.title] = markdown.markdown(t.text)

    return render(request,'pageview.html',{'page':page,'page_text':page_text,'topics_text':topics_text})
