from django.test import TestCase
from django.db import IntegrityError
from django.utils import timezone
from unittest.mock import patch
from .models import MailBox, AuthorizedEmails, EmailConversation, AccountabilityIntake
from .choices import FollowupFreqType

class TestMailBox(TestCase):
    def setUp(self):
        self.mailbox = MailBox.objects.create(
            email="test@example.com",
            bot_name="TestBot",
            grant_id="grant123",
            intake_required=True
        )

    def test_create_mailbox(self):
        """Test creating a mailbox"""
        self.assertEqual(self.mailbox.email, "test@example.com")
        self.assertEqual(self.mailbox.bot_name, "TestBot")
        self.assertTrue(self.mailbox.intake_required)

    def test_unique_email_constraint(self):
        """Test that email must be unique when not deleted"""
        with self.assertRaises(IntegrityError):
            MailBox.objects.create(
                email="test@example.com",
                bot_name="AnotherBot",
                grant_id="grant456"
            )

    @patch('mail_box.models.get_cache')
    @patch('mail_box.models.set_cache')
    def test_get_mailbox_choices_with_cache(self, mock_set_cache, mock_get_cache):
        """Test get_mailbox_choices method with cache"""
        # Test when cache exists
        cached_choices = [(self.mailbox.uid, "TestBot")]
        mock_get_cache.return_value = cached_choices
        
        choices = MailBox.get_mailbox_choices()
        self.assertEqual(choices, cached_choices)
        mock_set_cache.assert_not_called()

    @patch('mail_box.models.get_cache')
    @patch('mail_box.models.set_cache')
    def test_get_mailbox_choices_without_cache(self, mock_set_cache, mock_get_cache):
        """Test get_mailbox_choices method without cache"""
        # Test when cache doesn't exist
        mock_get_cache.return_value = None
        
        choices = MailBox.get_mailbox_choices()
        self.assertEqual(len(choices), 1)
        self.assertEqual(choices[0][1], "TestBot")
        mock_set_cache.assert_called_once()

class TestAuthorizedEmails(TestCase):
    def setUp(self):
        self.mailbox = MailBox.objects.create(
            email="mailbox@example.com",
            bot_name="TestBot",
            grant_id="grant123"
        )
        self.auth_email = AuthorizedEmails.objects.create(
            mailbox_id=self.mailbox.uid,
            email="authorized@example.com",
            name="Test User",
            followup_fequency=FollowupFreqType.daily,
            is_whitelist=True
        )

    def test_create_authorized_email(self):
        """Test creating an authorized email"""
        self.assertEqual(self.auth_email.email, "authorized@example.com")
        self.assertEqual(self.auth_email.followup_fequency, FollowupFreqType.daily)
        self.assertTrue(self.auth_email.is_whitelist)

    def test_unique_mailbox_email_constraint(self):
        """Test that mailbox_id and email combination must be unique when not deleted"""
        with self.assertRaises(IntegrityError):
            AuthorizedEmails.objects.create(
                mailbox_id=self.mailbox.uid,
                email="authorized@example.com"
            )

    def test_optional_fields(self):
        """Test optional fields"""
        auth_email = AuthorizedEmails.objects.create(
            mailbox_id=self.mailbox.uid,
            email="optional@example.com"
        )
        self.assertIsNone(auth_email.goal)
        self.assertIsNone(auth_email.situation)
        self.assertFalse(auth_email.is_intake_filled)

class TestEmailConversation(TestCase):
    def setUp(self):
        self.conversation = EmailConversation.objects.create(
            mailbox_id="mailbox123",
            sender="sender@example.com",
            subject="Test Subject",
            body="Test body content",
            responder="user",
            sent_at=timezone.now()
        )

    def test_create_conversation(self):
        """Test creating an email conversation"""
        self.assertEqual(self.conversation.sender, "sender@example.com")
        self.assertEqual(self.conversation.subject, "Test Subject")
        self.assertEqual(self.conversation.responder, "user")

    def test_conversation_fields(self):
        """Test all fields of email conversation"""
        conversation = EmailConversation.objects.get(id=self.conversation.id)
        self.assertIsNotNone(conversation.sent_at)
        self.assertEqual(conversation.body, "Test body content")

class TestAccountabilityIntake(TestCase):
    def setUp(self):
        self.intake = AccountabilityIntake.objects.create(
            form_id="form123",
            email_address="intake@example.com",
            name="Intake User",
            competency_level="Intermediate",
            follow_up_frequency=FollowupFreqType.weekly,
            wants_rewards=True,
            overall_goals="Test goals",
            situational_context="Test context",
            submission_number=1
        )

    def test_create_intake(self):
        """Test creating an accountability intake"""
        self.assertEqual(self.intake.email_address, "intake@example.com")
        self.assertEqual(self.intake.follow_up_frequency, FollowupFreqType.weekly)
        self.assertTrue(self.intake.wants_rewards)

    def test_unique_form_email_constraint(self):
        """Test that form_id and email_address combination must be unique when not deleted"""
        with self.assertRaises(IntegrityError):
            AccountabilityIntake.objects.create(
                form_id="form123",
                email_address="intake@example.com",
                name="Another User",
                competency_level="Advanced",
                follow_up_frequency=FollowupFreqType.monthly,
                wants_rewards=False,
                overall_goals="Different goals",
                situational_context="Different context",
                submission_number=2
            )

    def test_string_representation(self):
        """Test string representation of intake"""
        expected_string = f"{self.intake.name} - {self.intake.email_address}"
        self.assertEqual(str(self.intake), expected_string)

class TestIntegration(TestCase):
    def setUp(self):
        # Create mailbox
        self.mailbox = MailBox.objects.create(
            email="mailbox@example.com",
            bot_name="IntegrationBot",
            grant_id="grant123",
            intake_required=True
        )
        
        # Create authorized email
        self.auth_email = AuthorizedEmails.objects.create(
            mailbox_id=self.mailbox.uid,
            email="authorized@example.com",
            name="Test User",
            followup_fequency=FollowupFreqType.daily
        )
        
        # Create intake
        self.intake = AccountabilityIntake.objects.create(
            form_id="form123",
            email_address="authorized@example.com",
            name="Test User",
            competency_level="Intermediate",
            follow_up_frequency=FollowupFreqType.daily,
            wants_rewards=True,
            overall_goals="Integration test goals",
            situational_context="Integration test context",
            submission_number=1
        )
        
        # Create email conversation
        self.conversation = EmailConversation.objects.create(
            mailbox_id=self.mailbox.uid,
            sender="authorized@example.com",
            subject="Integration Test",
            body="Integration test content",
            responder="user",
            sent_at=timezone.now()
        )

    def test_complete_flow(self):
        """Test complete flow from mailbox to conversation"""
        # Verify mailbox exists
        self.assertTrue(MailBox.objects.filter(email="mailbox@example.com").exists())
        
        # Verify authorized email is associated with mailbox
        self.assertEqual(self.auth_email.mailbox_id, self.mailbox.uid)
        
        # Verify intake matches authorized email
        self.assertEqual(self.intake.email_address, self.auth_email.email)
        self.assertEqual(self.intake.follow_up_frequency, self.auth_email.followup_fequency)
        
        # Verify conversation is associated with mailbox and authorized email
        self.assertEqual(self.conversation.mailbox_id, self.mailbox.uid)
        self.assertEqual(self.conversation.sender, self.auth_email.email)

    def test_mailbox_choices_integration(self):
        """Test mailbox choices with real data"""
        choices = MailBox.get_mailbox_choices()
        self.assertTrue(any(choice[1] == "IntegrationBot" for choice in choices))