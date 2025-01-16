from django.test import TestCase
from django.db import IntegrityError
from .models import (
    LegacyBotRoleAndPermissions,
    LegacyBot,
    LegacyBotUser,
    Thread,
    ChatConversation,
    LegacyBotUserMapping
)

class TestLegacyBotRoleAndPermissions(TestCase):
    def setUp(self):
        self.role_perm = LegacyBotRoleAndPermissions.objects.create(
            role="premimum",
            max_session=10
        )

    def test_create_role_permissions(self):
        """Test creating role and permissions"""
        self.assertEqual(self.role_perm.role, "premimum")
        self.assertEqual(self.role_perm.max_session, 10)

    def test_unique_role_constraint(self):
        """Test that role must be unique when not deleted"""
        with self.assertRaises(IntegrityError):
            LegacyBotRoleAndPermissions.objects.create(
                role="premimum",
                max_session=20
            )

    def test_string_representation(self):
        """Test string representation of role permissions"""
        self.assertEqual(str(self.role_perm), "premimum")

class TestLegacyBotUser(TestCase):
    def setUp(self):
        self.user = LegacyBotUser.objects.create(
            email="test@example.com",
            name="Test User",
            first_name="Test",
            last_name="User",
            max_session=10,
            session_per_conversation_step=5
        )

    def test_create_user(self):
        """Test creating a legacy bot user"""
        self.assertEqual(self.user.email, "test@example.com")
        self.assertEqual(self.user.name, "Test User")
        self.assertEqual(self.user.max_session, 10)

    def test_unique_email_constraint(self):
        """Test that email must be unique when not deleted"""
        with self.assertRaises(IntegrityError):
            LegacyBotUser.objects.create(
                email="test@example.com",
                name="Another User"
            )

    def test_optional_fields(self):
        """Test optional fields can be null"""
        user = LegacyBotUser.objects.create(
            email="optional@example.com",
            name="Optional User"
        )
        self.assertIsNone(user.first_name)
        self.assertIsNone(user.last_name)
        self.assertIsNone(user.preferences)

class TestLegacyBot(TestCase):
    def setUp(self):
        self.user = LegacyBotUser.objects.create(
            email="creator@example.com",
            name="Creator"
        )
        self.bot = LegacyBot.objects.create(
            domain="test-domain",
            bot_identifier="test-bot",
            assistant_id="asst_123",
            assitant_type="chat",
            name="Test Bot",
            creator=self.user
        )

    def test_create_bot(self):
        """Test creating a legacy bot"""
        self.assertEqual(self.bot.domain, "test-domain")
        self.assertEqual(self.bot.assistant_id, "asst_123")
        self.assertEqual(self.bot.creator, self.user)

    def test_unique_domain_assistant_constraint(self):
        """Test that domain and assistant_id combination must be unique when not deleted"""
        with self.assertRaises(IntegrityError):
            LegacyBot.objects.create(
                domain="test-domain",
                assistant_id="asst_123",
                assitant_type="chat",
                name="Another Bot"
            )

class TestThread(TestCase):
    def setUp(self):
        self.thread = Thread.objects.create(
            bot_id="bot_123",
            thread_id="thread_123",
            user_id="user_123",
            chat_topic="Test Topic"
        )

    def test_create_thread(self):
        """Test creating a thread"""
        self.assertEqual(self.thread.bot_id, "bot_123")
        self.assertEqual(self.thread.thread_id, "thread_123")
        self.assertEqual(self.thread.chat_topic, "Test Topic")

    def test_unique_constraint(self):
        """Test unique constraint for bot_id, thread_id, and user_id combination"""
        with self.assertRaises(IntegrityError):
            Thread.objects.create(
                bot_id="bot_123",
                thread_id="thread_123",
                user_id="user_123",
                chat_topic="Another Topic"
            )

class TestChatConversation(TestCase):
    def setUp(self):
        self.user = LegacyBotUser.objects.create(
            email="test@example.com",
            name="Test User",
            uid="user_123"
        )
        self.bot = LegacyBot.objects.create(
            domain="test-domain",
            bot_identifier="test-bot",
            assistant_id="asst_123",
            assitant_type="chat",
            name="Test Bot",
            uid="bot_123"
        )
        self.thread = Thread.objects.create(
            bot_id=self.bot.uid,
            thread_id="thread_123",
            user_id=self.user.uid,
            chat_topic="Test Topic",
            uid="thread_123"
        )
        self.conversation = ChatConversation.objects.create(
            thread_id=self.thread.uid,
            role="USER",
            content="Hello, bot!"
        )

    def test_create_conversation(self):
        """Test creating a chat conversation"""
        self.assertEqual(self.conversation.role, "USER")
        self.assertEqual(self.conversation.content, "Hello, bot!")

    def test_get_user_and_bot(self):
        """Test get_user_and_bot method"""
        user, bot = self.conversation.get_user_and_bot()
        self.assertEqual(user, self.user)
        self.assertEqual(bot, self.bot)

class TestLegacyBotUserMapping(TestCase):
    def setUp(self):
        # Create test user and bot
        self.user = LegacyBotUser.objects.create(
            email="test@example.com",
            name="Test User",
            session_per_conversation_step=2
        )
        self.bot = LegacyBot.objects.create(
            domain="test-domain",
            bot_identifier="test-bot",
            assistant_id="asst_123",
            assitant_type="chat",
            name="Test Bot"
        )
        # Create mapping
        self.mapping = LegacyBotUserMapping.objects.create(
            user=self.user,
            bot=self.bot
        )
        # Create threads and conversations
        self.thread1 = Thread.objects.create(
            bot_id=self.bot.uid,
            thread_id="thread_1",
            user_id=self.user.uid,
            chat_topic="Topic 1"
        )
        self.thread2 = Thread.objects.create(
            bot_id=self.bot.uid,
            thread_id="thread_2",
            user_id=self.user.uid,
            chat_topic="Topic 2"
        )
        # Create conversations
        ChatConversation.objects.create(
            thread_id=self.thread1.uid,
            role="USER",
            content="Hello 1"
        )
        ChatConversation.objects.create(
            thread_id=self.thread1.uid,
            role="BOT",
            content="Response 1"
        )
        ChatConversation.objects.create(
            thread_id=self.thread2.uid,
            role="USER",
            content="Hello 2"
        )

    def test_update_thread_and_conversation_info(self):
        """Test updating thread and conversation info"""
        self.mapping.update_thread_and_conversation_info()

        # Check totals
        self.assertEqual(self.mapping.total_thread, 2)
        self.assertEqual(self.mapping.total_conversation, 3)
        self.assertEqual(self.mapping.total_session, 1)  # 3 conversations / 2 steps per session = 1 session

        # Check thread_and_conversation_info structure
        info = self.mapping.thread_and_conversation_info
        self.assertEqual(info["total_threads"], 2)
        self.assertEqual(info["total_conversations"], 3)
        self.assertEqual(len(info["thread_details"]), 2)

    def test_unique_user_bot_constraint(self):
        """Test that user-bot combination must be unique"""
        with self.assertRaises(IntegrityError):
            LegacyBotUserMapping.objects.create(
                user=self.user,
                bot=self.bot
            )

    def test_string_representation(self):
        """Test string representation of mapping"""
        expected = f"Mapping for user {self.user.name} ({self.user.email}) and bot {self.bot.name} ({self.bot.domain})"
        self.assertEqual(str(self.mapping), expected)