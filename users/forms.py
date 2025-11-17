# forms.py

from django import forms
from django.contrib.auth.hashers import make_password


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


class UserAdminForm(forms.ModelForm):
    new_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput,
        help_text="Leave empty if you do not want to change password"
    )

    class Meta:
        model = User
        fields = "__all__"

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("new_password"):
            user.password = make_password(self.cleaned_data["new_password"])
        if commit:
            user.save()
        return user
