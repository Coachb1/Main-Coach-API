from django import forms
from django.core.validators import FileExtensionValidator


class UploadFileForm_web(forms.Form):
    myfile = forms.FileField(label='Select a file',
                             required=True, allow_empty_file=False,
                             widget=forms.FileInput(
                                 attrs={'class': 'form-control-file'}),
                             validators=[FileExtensionValidator(allowed_extensions=['csv'])])

    email = forms.EmailField(label='Email',
                             max_length=100, required=True, error_messages={'required': 'Please enter an email'})

    password = forms.CharField(label='Password',
                               max_length=100, required=True,
                               widget=forms.PasswordInput(),
                               error_messages={'required': 'Please enter a password'})


class UploadFileForm_slack(forms.Form):
    myfile = forms.FileField(label='Select a file',
                             required=True, allow_empty_file=False,
                             widget=forms.FileInput(
                                 attrs={'class': 'form-control-file'}),
                             validators=[FileExtensionValidator(allowed_extensions=['csv'])])

    email = forms.EmailField(label='Email',
                             max_length=100, required=True, error_messages={'required': 'Please enter an email'})

    password = forms.CharField(label='Password',
                               max_length=100, required=True,
                               widget=forms.PasswordInput(),
                               error_messages={'required': 'Please enter a password'})

    client_domain_prefix = forms.CharField(label='Client Domain Prefix',
                                           required=True,
                                           max_length=100,
                                           error_messages={'required': 'Please enter the domain prefix'})
