# forms.py

from django import forms
from django.contrib.auth.hashers import make_password
from commons.db.json_form_mixins import UniversalSchemaWidget


from tenants.models import Tenant
from tests.forms import BUTTON_CONFIG_SCHEMA
from users.models import ClientUserInfo, LibraryBotConfig, User
from users.schema import ANNOUNCEMENT_SCHEMA, BOT_CONFIG_SCHEMA, DEFAULT_FILTERS_SCHEMA, FEATURE_BOX_SCHEMA, FEATURE_BUTTON_SCHEMA

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


class LibraryBotConfigForm(forms.ModelForm):
    class Meta:
        model = LibraryBotConfig
        fields = '__all__'
        widgets = {
            # 'access_password':           forms.PasswordInput(render_value=True),
            'default_filters':           UniversalSchemaWidget(schema=DEFAULT_FILTERS_SCHEMA),
            'bot_config':                UniversalSchemaWidget(schema=BOT_CONFIG_SCHEMA),
            'feature_and_button_controls':      UniversalSchemaWidget(schema=FEATURE_BUTTON_SCHEMA),
            'feature_boxs':         UniversalSchemaWidget(schema=FEATURE_BOX_SCHEMA),
            'announcements_section':      UniversalSchemaWidget(schema=ANNOUNCEMENT_SCHEMA), 
            'card_button_config':        UniversalSchemaWidget(schema=BUTTON_CONFIG_SCHEMA),
        }

    