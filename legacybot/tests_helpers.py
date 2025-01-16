from django.test import TestCase
from legacybot.models import Thread, ChatConversation, LegacyBotUser
from legacybot.helpers  import generate_bot_identifier, generate_action_report_data, get_or_generate_action_data

class GenerateBotIdentifierTests(TestCase):
    def test_generate_bot_identifier(self):
        bot_name = "My Cool Bot!"
        assistant_id = "asst_123456789"
        result = generate_bot_identifier(bot_name, assistant_id)
        expected = "my-cool-bot-123456"
        self.assertEqual(result, expected)

    def test_generate_bot_identifier_special_characters(self):
        bot_name = "Bot@Name#Special$Characters"
        assistant_id = "asst_987654321"
        result = generate_bot_identifier(bot_name, assistant_id)
        expected = "botname-special-characters-987654"
        self.assertEqual(result, expected)

class GenerateActionReportDataTests(TestCase):
    def test_generate_action_report_data(self):
        conversations = [
            ChatConversation(role="user", content="How do I reverse a string in Python?"),
            ChatConversation(role="assistant", content="You can use slicing: `reversed_string = my_string[::-1]`."),
        ]
        
        result = generate_action_report_data(conversations)
        
        self.assertIn("summary", result)
        self.assertIn("keyTakeaways", result)
        self.assertIn("skillsFocus", result)
        self.assertIsInstance(result["skillsFocus"], list)

class GetOrGenerateActionDataTests(TestCase):
    def setUp(self):
        # Create a mock user
        self.user = LegacyBotUser.objects.create(uid="user_123", session_per_conversation_step=10)
        
        # Create mock threads
        self.thread1 = Thread.objects.create(uid="thread_1", user_id=self.user.uid, chat_topic="Python Basics")
        self.thread2 = Thread.objects.create(uid="thread_2", user_id=self.user.uid, chat_topic="Advanced Python")
        
        # Create mock conversations
        ChatConversation.objects.create(thread_id=self.thread1.uid, role="user", content="What are Python's data types?")
        ChatConversation.objects.create(thread_id=self.thread1.uid, role="assistant", content="Python has int, float, str, list, dict, etc.")
        ChatConversation.objects.create(thread_id=self.thread2.uid, role="user", content="How do I handle exceptions in Python?")
        ChatConversation.objects.create(thread_id=self.thread2.uid, role="assistant", content="You can use try, except, finally blocks.")

    def test_get_or_generate_action_data(self):
        threads = Thread.objects.all()
        result = get_or_generate_action_data(threads)
        
        # Check if action data was generated for both threads
        self.assertEqual(len(result), 2)
        self.assertTrue(any("thread_1" in data for data in result))
        self.assertTrue(any("thread_2" in data for data in result))
        
        # Validate content of action data
        thread1_data = next(item for item in result if "thread_1" in item)
        self.assertIn("summary", thread1_data["thread_1"])
        self.assertIn("keyTakeaways", thread1_data["thread_1"])
        self.assertIn("skillsFocus", thread1_data["thread_1"])