import imp
from django import forms
from .models import WikiPage

class NewPageForm(forms.ModelForm):
    class Meta:
        model = WikiPage
        fields = ['title','text']