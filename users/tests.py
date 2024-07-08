from django.db import IntegrityError
from users.choices import CoachCoacheeConnectionStatusChoice
from users.models import User, SignatureBot, BotAttribute, BotAndUserMapping,ClientUserInfo, CoachCoacheeMentorMenteeProfile, CoachCoacheeRating, CoachCoacheeConnection
from identities.models import Identity
from .models import UserAttribute
from django.test import TestCase
from django.conf import settings
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.contrib.auth import get_user_model
from apis.accounts.serializers import SetupAccountSerializer, AccountSerializer

BASE_URL = f"{settings.BACKEND}/api/v1/accounts/"

class UserModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            name="John Doe",
            role="admin",
            password="password123",
            is_root=True,
            is_excluded=False
        )

    def test_can_login(self):
        self.assertTrue(self.user.can_login)
        
    def test_is_active(self):
        self.assertTrue(self.user.is_active)
        
    def test_name_field(self):
        self.assertEqual(self.user.name, "John Doe")

    def test_role_field(self):
        self.assertEqual(self.user.role, "admin")

    def test_password_field(self):
        self.assertEqual(self.user.password, "password123")

    def test_is_root_field(self):
        self.assertTrue(self.user.is_root)

    def test_is_excluded_field(self):
        self.assertFalse(self.user.is_excluded)


class IdentityModelTest(TestCase):
    def setUp(self):
        self.identity = Identity.objects.create(
            user_id="123",
            identity_type="email",
            value="test@example.com"
        )

    def test_user_id_field(self):
        self.assertEqual(self.identity.user_id, "123")

    def test_identity_type_field(self):
        self.assertEqual(self.identity.identity_type, "email")

    def test_value_field(self):
        self.assertEqual(self.identity.value, "test@example.com")

    def test_unique_together_constraint(self):
        # Attempt to create another identity with the same tenant_id, value, and deleted=False
        with self.assertRaises(Exception):
            Identity.objects.create(
                user_id="456",
                identity_type="email",
                value="test@example.com"
            )


class UserAttributeModelTest(TestCase):
    def setUp(self):
        self.user_attribute = UserAttribute.objects.create(
            user_id="123",
            tag="example_tag",
            attributes={"attribute_key": "attribute_value"},
            difficulty_level="Medium",
            midium_feedback_prompt="Some midium feedback",
            midium_skill_prompt="Some midium skill prompt",
            test_previlage="Some test previlage",
            competency_data={"key": "value"}
        )

    def test_user_id_field(self):
        self.assertEqual(self.user_attribute.user_id, "123")

    def test_tag_field(self):
        self.assertEqual(self.user_attribute.tag, "example_tag")

    def test_attributes_field(self):
        self.assertEqual(self.user_attribute.attributes, {"attribute_key": "attribute_value"})

    def test_difficulty_level_field(self):
        self.assertEqual(self.user_attribute.difficulty_level, "Medium")

    def test_midium_feedback_prompt_field(self):
        self.assertEqual(self.user_attribute.midium_feedback_prompt, "Some midium feedback")

    def test_midium_skill_prompt_field(self):
        self.assertEqual(self.user_attribute.midium_skill_prompt, "Some midium skill prompt")

    def test_test_previlage_field(self):
        self.assertEqual(self.user_attribute.test_previlage, "Some test previlage")

    def test_competency_data_field(self):
        self.assertEqual(self.user_attribute.competency_data, {"key": "value"})

    def test_unique_together_constraint(self):
        # Attempt to create another user attribute with the same tenant_id, user_id, and tag
        with self.assertRaises(Exception):
            UserAttribute.objects.create(
                user_id="123",
                tag="example_tag",
                attributes={"other_key": "other_value"},
                difficulty_level="Low",
                midium_feedback_prompt="Some other feedback",
                midium_skill_prompt="Some other skill prompt",
                test_previlage="Some other previlage",
                competency_data={"other_key": "other_value"}
            )


# class UserViewTests(APITestCase):
#     def test_create_user_account(self):
#         # url = reverse('your_create_view_url')  # Replace 'your_create_view_url' with the actual URL name
#         url = BASE_URL

#         # Sample request data
#         data = {
#             "user_context": {
#                 "name": "John Does",
#                 "role": "admin",
#                 "password": "password123",
#                 "is_root": True,
#                 "is_excluded": False
#             },
#             "identity_context": {
#                 "identity_type": "email",
#                 "value": "test@example.com"
#             }
#         }

#         # Make a POST request to create the user account
#         response = self.client.post(url, data, format='json')

#         # Ensure the request was successful (status code 201)
#         self.assertEqual(response.status_code, status.HTTP_201_CREATED)

#         # Ensure the user account was created in the database
#         self.assertTrue(User.objects.filter(name="John Does").exists())

#         # Ensure the identity was created in the database
#         self.assertTrue(Identity.objects.filter(value="test@example.com").exists())

#         # Ensure the response data matches the expected serialized user account data
#         expected_data = AccountSerializer(instance=User.objects.get(name="John Does")).data
#         self.assertEqual(response.data, expected_data)


class SignatureBotModelTest(TestCase):
    def setUp(self):
        self.signature_bot = SignatureBot.objects.create(
            bot_id="123",
            bot_type="chatbot",
            bot_details={"key": "value"},
            recommended_codes="ABC123",
            user_id="456",
            tag="example_tag",
            attributes={"attribute_key": "attribute_value"},
            data={"data_key": "data_value"},
            custom_prompt="Example custom prompt",
            faqs={"question": "answer"},
            is_fitment_analysis=True,
            is_strict_fitment=False,
            is_approved=True,
            is_active=True,
            is_system_bot=False,
            is_sample_bot=False,
            use_google_context=True,
            use_personality_context=False,
            use_idp=True,
            bot_scenario_case="general",
            is_approval_email_sent=True
        )

    def test_bot_id_field(self):
        self.assertEqual(self.signature_bot.bot_id, "123")

    def test_bot_type_field(self):
        self.assertEqual(self.signature_bot.bot_type, "chatbot")

    # Repeat similar tests for other fields...

    def test_custom_prompt_field(self):
        self.assertEqual(self.signature_bot.custom_prompt, "Example custom prompt")

    def test_bot_scenario_case_field(self):
        self.assertEqual(self.signature_bot.bot_scenario_case, "general")

    def test_is_approval_email_sent_field(self):
        self.assertTrue(self.signature_bot.is_approval_email_sent)
        
    def test_bot_details_field(self):
        self.assertEqual(self.signature_bot.bot_details, {"key": "value"})
        
    def test_recommended_codes_field(self):
        self.assertEqual(self.signature_bot.recommended_codes, "ABC123")
        
    def test_user_id_field(self):
        self.assertEqual(self.signature_bot.user_id, "456")
        
    def test_tag_field(self):
        self.assertEqual(self.signature_bot.tag, "example_tag")
        
    def test_attributes_field(self):
        self.assertEqual(self.signature_bot.attributes, {"attribute_key": "attribute_value"})
        
    def test_data_field(self):
        self.assertEqual(self.signature_bot.data, {"data_key": "data_value"})
        
    def test_custom_prompt_field(self):
        self.assertEqual(self.signature_bot.custom_prompt, "Example custom prompt")
        
    def test_faqs_field(self):
        self.assertEqual(self.signature_bot.faqs, {"question": "answer"})
        
    def test_is_fitment_analysis_field(self):
        self.assertTrue(self.signature_bot.is_fitment_analysis)
        
    def test_is_strict_fitment_field(self):
        self.assertFalse(self.signature_bot.is_strict_fitment)
        
    def test_is_approved_field(self):
        self.assertTrue(self.signature_bot.is_approved)
        
    def test_is_active_field(self):
        self.assertTrue(self.signature_bot.is_active)
        
    def test_is_system_bot_field(self):
        self.assertFalse(self.signature_bot.is_system_bot)
        
    def test_is_sample_bot_field(self):
        self.assertFalse(self.signature_bot.is_sample_bot)
        
    def test_use_google_context_field(self):
        self.assertTrue(self.signature_bot.use_google_context)
        
    def test_use_personality_context_field(self):
        self.assertFalse(self.signature_bot.use_personality_context)
        
    def test_use_idp_field(self):
        self.assertTrue(self.signature_bot.use_idp)
        
    def test_bot_scenario_case_field(self):
        self.assertEqual(self.signature_bot.bot_scenario_case, "general")
        
    def test_is_approval_email_sent_field(self):
        self.assertTrue(self.signature_bot.is_approval_email_sent)

    def test_unique_together_constraint(self):
        # Attempt to create another signature bot with the same tenant_id, user_id, and tag
        with self.assertRaises(Exception):
            SignatureBot.objects.create(
                bot_id="789",
                bot_type="assistant",
                bot_details={"other_key": "other_value"},
                recommended_codes="XYZ789",
                user_id="456",
                tag="example_tag",
                attributes={"other_attribute_key": "other_attribute_value"},
                data={"other_data_key": "other_data_value"},
                custom_prompt="Another custom prompt",
                faqs={"other_question": "other_answer"},
                is_fitment_analysis=False,
                is_strict_fitment=True,
                is_approved=False,
                is_active=False,
                is_system_bot=True,
                is_sample_bot=True,
                use_google_context=False,
                use_personality_context=True,
                use_idp=False,
                bot_scenario_case="specific",
                is_approval_email_sent=False
            )


class BotAttributeModelTest(TestCase):
    def setUp(self):
        self.bot_attribute = BotAttribute.objects.create(
            bot_id="bot123",
            bot_name="Test Bot",
            coach_name="John Doe",
            coach_email="john@example.com",
            client_name="Client Company",
            conversations_per_month=100,
            is_audio_response=False,
            about="This is a test bot.",
        )

    def test_bot_id_field(self):
        self.assertEqual(self.bot_attribute.bot_id, "bot123")

    def test_bot_name_field(self):
        self.assertEqual(self.bot_attribute.bot_name, "Test Bot")

    def test_coach_name_field(self):
        self.assertEqual(self.bot_attribute.coach_name, "John Doe")

    def test_coach_email_field(self):
        self.assertEqual(self.bot_attribute.coach_email, "john@example.com")

    def test_client_name_field(self):
        self.assertEqual(self.bot_attribute.client_name, "Client Company")

    def test_conversations_per_month_field(self):
        self.assertEqual(self.bot_attribute.conversations_per_month, 100)

    def test_is_audio_response_field(self):
        self.assertFalse(self.bot_attribute.is_audio_response)

    def test_about_field(self):
        self.assertEqual(self.bot_attribute.about, "This is a test bot.")

    def test_attached_data_field(self):
        self.assertIsNone(self.bot_attribute.attached_data)

    def test_attached_links_field(self):
        self.assertIsNone(self.bot_attribute.attached_links)


class BotAndUserMappingModelTest(TestCase):
    def setUp(self):
        self.mapping = BotAndUserMapping.objects.create(
            bot_id="test_bot",
            participant_id="test_user",
            bot_owner_name="Bot Owner",
            bot_owner_email="bot@example.com",
            bot_owner_mob_number="1234567890",
            user_mob_number="9876543210",
            user_name="Test User",
            user_email="user@example.com"
        )

    def test_bot_id_field(self):
        self.assertEqual(self.mapping.bot_id, "test_bot")

    def test_participant_id_field(self):
        self.assertEqual(self.mapping.participant_id, "test_user")

    def test_bot_owner_name_field(self):
        self.assertEqual(self.mapping.bot_owner_name, "Bot Owner")

    def test_bot_owner_email_field(self):
        self.assertEqual(self.mapping.bot_owner_email, "bot@example.com")

    def test_bot_owner_mob_number_field(self):
        self.assertEqual(self.mapping.bot_owner_mob_number, "1234567890")

    def test_user_mob_number_field(self):
        self.assertEqual(self.mapping.user_mob_number, "9876543210")

    def test_user_name_field(self):
        self.assertEqual(self.mapping.user_name, "Test User")

    def test_user_email_field(self):
        self.assertEqual(self.mapping.user_email, "user@example.com")

    def test_unique_together_constraint(self):
        # Test unique_together constraint
        with self.assertRaises(Exception):
            BotAndUserMapping.objects.create(
                bot_id="test_bot",
                participant_id="test_user",
                bot_owner_name="Another Bot Owner",
                bot_owner_email="another_bot@example.com",
                bot_owner_mob_number="9876543210",
                user_mob_number="1234567890",
                user_name="Another Test User",
                user_email="another_user@example.com"
            )


class ClientUserInfoTest(TestCase):

    def setUp(self):

        # Create a ClientUserInfo instance for testing

        self.client_user_info = ClientUserInfo.objects.create(
            tenant_id = '123',
            
            client_name="Test Client",

            owner_id="123",

            attributes={"key": "value"},

            member_emails="test@example.com",

            member_mob_numbers="+1234567890",

            member_user_ids="456",

            avatar_bot_creation=True,

            feedback_bot_creation=False,

            subject_matter_bot_creation=True,

            number_of_conversation_per_month=100,

            required_form_fields={"name": "required"},

            restricted_ids="789",

            demo_ids="012",

            accessed_bot_ids="345",

            coach_skills="skill1, skill2",

            coach_expertise="expertise1, expertise2",

            departments="dept1, dept2",

            coach_mentor_previledge="prev1, prev2",

            is_coach_mentor_previledge=True,

            restricted_pages="page1, page2",

            restricted_features="feature1, feature2"

        )


    def test_client_user_info_model(self):
        self.assertTrue(self.client_user_info.avatar_bot_creation)

        self.assertFalse(self.client_user_info.feedback_bot_creation)

        self.assertTrue(self.client_user_info.subject_matter_bot_creation)

        self.assertEqual(self.client_user_info.number_of_conversation_per_month, 100)

        self.assertDictEqual(self.client_user_info.attributes, {"key": "value"})

        self.assertEqual(self.client_user_info.member_emails, "test@example.com")

        self.assertEqual(self.client_user_info.member_mob_numbers, "+1234567890")

        self.assertEqual(self.client_user_info.member_user_ids, "456")

        self.assertEqual(self.client_user_info.required_form_fields, {"name": "required"})

        self.assertEqual(self.client_user_info.restricted_ids, "789")

        self.assertEqual(self.client_user_info.demo_ids, "012")

        self.assertEqual(self.client_user_info.accessed_bot_ids, "345")

        self.assertEqual(self.client_user_info.coach_skills, "skill1, skill2")

        self.assertEqual(self.client_user_info.coach_expertise, "expertise1, expertise2")

        self.assertEqual(self.client_user_info.departments, "dept1, dept2")

        self.assertEqual(self.client_user_info.coach_mentor_previledge, "prev1, prev2")

        self.assertTrue(self.client_user_info.is_coach_mentor_previledge)

        self.assertEqual(self.client_user_info.restricted_pages, "page1, page2")

        self.assertEqual(self.client_user_info.restricted_features, "feature1, feature2")


class CoachCoacheeMentorMenteeProfileTest(TestCase):

    def setUp(self):

        # Create a CoachCoacheeMentorMenteeProfile instance for testing

        self.coach_coachee_mentor_mentee_profile = CoachCoacheeMentorMenteeProfile.objects.create(

            profile_type="coach",

            name="Test Coach",

            email="test@example.com",

            user_id="123",

            bot_ids="bot1, bot2",

            bot_urls="https://example.com/bot1, https://example.com/bot2",

            profile_image_url="https://example.com/profile.jpg",

            hard_skill_areas="skill1, skill2",

            area_domain="domain1, domain2",

            provided_links={"link1": "https://example.com/link1", "link2": "https://example.com/link2"},

            low_rating_characteristics="characteristic1, characteristic2",

            high_rating_characteristics="characteristic3, characteristic4",

            mentoring_preferences="preference1, preference2",

            mentoring_frameworks="framework1, framework2",

            dominant_point_of_view="point1, point2",

            problem_solving_approach="approach1, approach2",

            admired_leaders="leader1, leader2",

            voice_sample=True,

            coaching_for_fitment="fitment1",

            coaching_level="level1",

            coach_same_department=True,

            supported_outcome="outcome1",

            coaching_style="style1",

            time_commitment="commitment1",

            is_approved=True,

            other_details={"detail1": "value1", "detail2": "value2"},

            bot_snippets={"snippet1": "value1", "snippet2": "value2"},

            mob_number="+1234567890",

            allow_coachee_to_create_session=True,

            is_mentor=True,

            qna_for_coach_mentor={"q1": "a1", "q2": "a2"},

            significant_challenges_and_solutions="challenge1, solution1",

            common_phrases_and_expressions="phrase1, expression1",

            admirer_user_ids="user1, user2",

            journey_and_background="journey1, background1",

            mentorship_contribution="contribution1",

            is_approved_email_sent=True

        )

    def test_coach_coachee_mentor_mentee_profile_model(self):

        # Test the CoachCoacheeMentorMenteeProfile instance

        self.assertEqual(self.coach_coachee_mentor_mentee_profile.profile_type, "coach")

        self.assertEqual(self.coach_coachee_mentor_mentee_profile.name, "Test Coach")

        self.assertEqual(self.coach_coachee_mentor_mentee_profile.email, "test@example.com")

        self.assertEqual(self.coach_coachee_mentor_mentee_profile.user_id, "123")

        self.assertEqual(self.coach_coachee_mentor_mentee_profile.bot_ids, "bot1, bot2")

        self.assertEqual(self.coach_coachee_mentor_mentee_profile.bot_urls, "https://example.com/bot1, https://example.com/bot2")

        self.assertEqual(self.coach_coachee_mentor_mentee_profile.profile_image_url, "https://example.com/profile.jpg")

        self.assertEqual(self.coach_coachee_mentor_mentee_profile.hard_skill_areas, "skill1, skill2")

        self.assertEqual(self.coach_coachee_mentor_mentee_profile.area_domain, "domain1, domain2")

        self.assertDictEqual(self.coach_coachee_mentor_mentee_profile.provided_links, {"link1": "https://example.com/link1", "link2": "https://example.com/link2"})

        self.assertEqual(self.coach_coachee_mentor_mentee_profile.low_rating_characteristics, "characteristic1, characteristic2")

        self.assertEqual(self.coach_coachee_mentor_mentee_profile.high_rating_characteristics, "characteristic3, characteristic4")

        self.assertEqual(self.coach_coachee_mentor_mentee_profile.mentoring_preferences, "preference1, preference2")

        self.assertEqual(self.coach_coachee_mentor_mentee_profile.mentoring_frameworks, "framework1, framework2")

        self.assertEqual(self.coach_coachee_mentor_mentee_profile.dominant_point_of_view, "point1, point2")

        self.assertEqual(self.coach_coachee_mentor_mentee_profile.problem_solving_approach, "approach1, approach2")

        self.assertEqual(self.coach_coachee_mentor_mentee_profile.admired_leaders, "leader1, leader2")


class CoachCoacheeRatingTest(TestCase):

    def setUp(self):

        # Create a CoachCoacheeRating instance for testing

        self.coach_coachee_rating = CoachCoacheeRating.objects.create(
            coach_id="123",
            coachee_id="456",
            rating=4.5,
            rating_type="overall",
            rating_comment="Good coach",
            is_deleted=False,
            is_active=True,
        )

    def test_coach_coachee_rating_model(self):

        # Test the CoachCoacheeRating instance

        self.assertEqual(self.coach_coachee_rating.coach_id, "123")

        self.assertEqual(self.coach_coachee_rating.coachee_id, "456")

        self.assertEqual(self.coach_coachee_rating.rating, 4.5)

        self.assertEqual(self.coach_coachee_rating.rating_type, "overall")

        self.assertEqual(self.coach_coachee_rating.rating_comment, "Good coach")

        self.assertFalse(self.coach_coachee_rating.is_deleted)

        self.assertTrue(self.coach_coachee_rating.is_active)

    def test_unique_together_constraint(self):

        # Test the unique_together constraint
        with self.assertRaises(IntegrityError):

            CoachCoacheeRating.objects.create(
                coach_id="123",
                coachee_id="456",
                rating=4.5,
                rating_type="overall",
                rating_comment="Good coach",
                is_deleted=False,
                is_active=True,
            )


class CoachCoacheeConnectionTest(TestCase):

    def setUp(self):

        # Create a CoachCoacheeConnection instance for testing

        self.coach_coachee_connection = CoachCoacheeConnection.objects.create(
            coach_id="123",
            coachee_id="456",
            connection_type="coach-coachee",
            status=CoachCoacheeConnectionStatusChoice.pending,
            is_approved=False,
            is_rejected=False,
            is_blocked=False,
            is_deleted=False,
            is_removed=False,
            coach_avatar_bot_id="bot123",
        )

    def test_coach_coachee_connection_model(self):

        # Test the CoachCoacheeConnection instance

        self.assertEqual(self.coach_coachee_connection.coach_id, "123")

        self.assertEqual(self.coach_coachee_connection.coachee_id, "456")

        self.assertEqual(self.coach_coachee_connection.connection_type, "coach-coachee")

        self.assertEqual(
            self.coach_coachee_connection.status,
            CoachCoacheeConnectionStatusChoice.pending,
        )

        self.assertFalse(self.coach_coachee_connection.is_approved)

        self.assertFalse(self.coach_coachee_connection.is_rejected)

        self.assertFalse(self.coach_coachee_connection.is_blocked)

        self.assertFalse(self.coach_coachee_connection.is_deleted)

        self.assertFalse(self.coach_coachee_connection.is_removed)

        self.assertEqual(self.coach_coachee_connection.coach_avatar_bot_id, "bot123")

    def test_unique_together_constraint(self):

        # Test the unique_together constraint

        with self.assertRaises(IntegrityError):

            CoachCoacheeConnection.objects.create(
                coach_id="123",
                coachee_id="456",
                connection_type="coach-coachee",
                status=CoachCoacheeConnectionStatusChoice.pending,
                is_approved=False,
                is_rejected=False,
                is_blocked=False,
                is_deleted=False,
                is_removed=False,
                coach_avatar_bot_id="bot123",
            )
