from cgitb import text
import imp
from turtle import title
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse
import markdown
from .models import WikiPage, SubTopic
from .forms import NewPageForm
from django.contrib.auth.models import User



# Create your views here.


def home(request):
    t = '#**hello** my *friend*'
    
    return render(request,'home.html')


def ViewWikiPage(request,title):
    #page = WikiPage.objects.get(title=title)
    page = get_object_or_404(WikiPage, title=title)
    page_text = page.get_text()
    # topics = page.subtopics.all()
    topics = page.subtopics.all()

    # for t in topics:
    #     topics_text[t.title] = markdown.markdown(t.text)

    return render(request,'pageview.html',{'page':page,'page_text':page_text,'topics':topics})


def NewPage(request):
    user = request.user
    if request.method == 'POST':
        form = NewPageForm(request.POST)
        if form.is_valid():
            page = form.save(commit=False)
            page.created_by = user
            page.save()
            return redirect('wikipage',tittle=page.title)
    else:
        form = NewPageForm()
        return render(request,'newpage.html',{'form': form})

def AddSubTopic(request,page_id):
    user = request.user
    page = get_object_or_404(WikiPage,pid = page_id)
    if request.method == 'POST':
        form = NewSubTopicForm(request.POST)
        if form.is_valid():
            topic = form.save(commit=False)
            topic.created_by = user
            topic.topic = page
            topic.save()
            return redirect('wikipage',title=topic.title)
    else:
        form = NewSubTopicForm()
        return render(request, 'newtopic.html', {'form':form, 'page':page})

