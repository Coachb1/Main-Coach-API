from django import forms
from mail_box.models import AuthorizedEmails, MailBox

class AuthorizedEmailsAdminForm(forms.ModelForm):
    mailbox_id = forms.ChoiceField(
        # choices=MailBox.get_mailbox_choices(),
        choices = MailBox.objects.values_list('uid', 'bot_name'),
        required=True
    )

    class Meta:
        model = AuthorizedEmails
        fields = '__all__'