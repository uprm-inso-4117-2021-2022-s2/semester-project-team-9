import imp
from django import forms
from .models import WikiPage, SubTopic

class NewPageForm(forms.ModelForm):
    class Meta:
        model = WikiPage
        fields = ['title','text','category']

class NewSubTopicForm(forms.ModelForm):
    class Meta:
        model = SubTopic
        fields = ['title', 'text']