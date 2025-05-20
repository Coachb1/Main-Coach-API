# forms.py

from django import forms

from tenants.models import Tenant
from users.models import ClientUserInfo, User

class TenantForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = ['test_per_month', 'is_repeat']

class ClientForm(forms.ModelForm):
    class Meta:
        model = ClientUserInfo
        fields = ['test_per_month', 'is_repeat']

class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['test_per_month', 'is_repeat']
