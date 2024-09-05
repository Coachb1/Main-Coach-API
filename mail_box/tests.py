from django.test import TestCase
from mail_box.models import MailBox


class TestMailBox(TestCase):

    def test_create_mailbox_with_valid_email_and_prompt_with_django_settings(self):
        mailbox = MailBox.objects.create(email='test@example.com', prompt='This is a test prompt.')
        assert mailbox.email == 'test@example.com'
        assert mailbox.prompt == 'This is a test prompt.'

    # Creating a MailBox instance with a very long email (255 characters)
    def test_create_mailbox_with_long_email(self):
        long_email = 'a' * 243 + '@example.com'
        mailbox = MailBox.objects.create(email=long_email, prompt='This is a test prompt.')
        assert mailbox.email == long_email
        assert mailbox.prompt == 'This is a test prompt.'