from django.test import TestCase
from .models import Test, TestAttemptSessionStatusChoices, TestAttemptSession
from .choices import InteractionModeChoices, TestTypeChoices, ScenarioCaseChoices, TestAttemptSessionStatusChoices

class TestModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create a sample object for testing
        cls.test_object = Test.objects.create(
            creator_id="test_creator",
            title="Test Title",
            description="Test Description",
            max_test_allowed=10,
            interaction_mode=InteractionModeChoices.audio,
            test_type=TestTypeChoices.test,
            scenario_case=ScenarioCaseChoices.simulation,
            test_related_context="Test Related Context",
            gpt_prompt_override="GPT Prompt Override",
            test_code="TEST001",
            mindmap_doc_id="Mindmap Doc ID",
            flash_card_doc_id="Flash Card Doc ID",
            email_address_list="test@example.com",
            send_only_to_email=False,
            is_single_bot=False,
            is_self_created=False,
            is_repeat=True,
            is_game_type=False,
            is_immersive=False,
            is_free=False,
            is_checkin_type=False,
            is_learner_path=False,
            is_email_type=False,
            skills_to_evaluate="Communication Skills",
            source="CoachBot",
            image_url="https://example.com/image.jpg",
            rating="Not Rated",
            tedtalk_and_hbr_case="TED Talk and HBR Case",
            email_candidate=True,
            candidate_type="Candidate Type",
            orchestrated_conversation_details=None,
            certificate_details=None,
            ui_information=None,
            media_props=None,
            description_media=None,
            client_name="Demo",
            goals="Test Goals",
            course="Test Course",
            industry="Test Industry",
            exp_level="Test Exp Level",
            total_question=20,
            is_micro=False,
            is_logged_in=False,
            is_transcript_only=False,
            is_pitch=False,
            articles="Test Articles",
            bot_name="Test Bot",
            competency_group="Test Competency Group",
            creator_user_id="test_user",
            area_domain="Test Area Domain",
            tab_category="Test Tab Category",
            is_recommended=False,
            visual_tags="Test Visual Tags",
            page_name="Test Page Name",
            scenario_summary="Test Scenario Summary",
            creator_email="test@example.com"
        )

    def test_creator_id_field(self):
        test_object = TestModelTest.test_object
        self.assertEqual(test_object.creator_id, "test_creator")

    def test_title_field(self):
        test_object = TestModelTest.test_object
        self.assertEqual(test_object.title, "Test Title")


    def test_fields(self):
        test_object = TestModelTest.test_object
        self.assertEqual(test_object.mindmap_doc_id, "Mindmap Doc ID")
        self.assertEqual(test_object.flash_card_doc_id, "Flash Card Doc ID")
        self.assertEqual(test_object.email_address_list, "test@example.com")
        self.assertEqual(test_object.send_only_to_email, False)
        self.assertEqual(test_object.is_single_bot, False)
        self.assertEqual(test_object.is_self_created, False)
        self.assertEqual(test_object.is_repeat, True)
        self.assertEqual(test_object.is_game_type, False)
        self.assertEqual(test_object.is_immersive, False)
        self.assertEqual(test_object.is_free, False)
        self.assertEqual(test_object.is_checkin_type, False)
        self.assertEqual(test_object.is_learner_path, False)
        self.assertEqual(test_object.is_email_type, False)
        self.assertEqual(test_object.skills_to_evaluate, "Communication Skills")
        self.assertEqual(test_object.source, "CoachBot")
        self.assertEqual(test_object.image_url, "https://example.com/image.jpg")
        self.assertEqual(test_object.rating, "Not Rated")
        self.assertEqual(test_object.tedtalk_and_hbr_case, "TED Talk and HBR Case")
        self.assertEqual(test_object.email_candidate, True)
        self.assertEqual(test_object.candidate_type, "Candidate Type")
        






class TestAttemptSessionModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create a sample object for testing
        cls.test_attempt_session = TestAttemptSession.objects.create(
            test_id="test_id_001",
            participant_id="participant_id_001",
            test_invite_id="invite_001",
            expires_at="2024-04-30 12:00:00",
            started_at="2024-04-30 11:00:00",
            finished_at=None,
            status=TestAttemptSessionStatusChoices.in_progress,
            feedback_text="Test feedback",
            report_doc_id="report_001",
            skills_rating={"skill1": 4, "skill2": 3},
            skills_explanation={"skill1": "Explanation 1", "skill2": "Explanation 2"},
            test_score=None,
            avg_score=None,
            speech_score=None,
            culture_skills_rating=None,
            culture_skills_explanation=None,
            meeting_summary="Summary of the meeting",
            areas_of_improvement="Areas of improvement",
            current_question_idx=None,
            next_question_idx=1,
            report_url=None,
            is_report_sent_to_whatsapp=False,
            is_report_sent_to_email=False,
            is_checkin_type=False,
            feedback_summary="Feedback summary",
            culture_and_skill_summary="Culture and skill summary",
            mcq_summary="MCQ summary",
            competency_data=None,
            language_skills="English, Spanish",
            is_idp_discussion_opted=False,
            intake_id="intake_001",
            conversation_summary="Conversation summary",
            related_previous_conversation_summary="Related previous conversation summary"
        )

    def test_fields(self):
        test_attempt_session = TestAttemptSessionModelTest.test_attempt_session
        self.assertEqual(test_attempt_session.test_id, "test_id_001")
        self.assertEqual(test_attempt_session.participant_id, "participant_id_001")
        self.assertEqual(test_attempt_session.test_invite_id, "invite_001")
        self.assertEqual(str(test_attempt_session.expires_at), "2024-04-30 12:00:00")
        self.assertEqual(str(test_attempt_session.started_at), "2024-04-30 11:00:00")
        self.assertIsNone(test_attempt_session.finished_at)
        self.assertEqual(test_attempt_session.status, TestAttemptSessionStatusChoices.in_progress)
        self.assertEqual(test_attempt_session.feedback_text, "Test feedback")
        self.assertEqual(test_attempt_session.report_doc_id, "report_001")
        self.assertEqual(test_attempt_session.skills_rating, {"skill1": 4, "skill2": 3})
        self.assertEqual(test_attempt_session.skills_explanation, {"skill1": "Explanation 1", "skill2": "Explanation 2"})
        self.assertIsNone(test_attempt_session.test_score)
        self.assertIsNone(test_attempt_session.avg_score)
        self.assertIsNone(test_attempt_session.speech_score)
        self.assertIsNone(test_attempt_session.culture_skills_rating)
        self.assertIsNone(test_attempt_session.culture_skills_explanation)
        self.assertEqual(test_attempt_session.meeting_summary, "Summary of the meeting")
        self.assertEqual(test_attempt_session.areas_of_improvement, "Areas of improvement")
        self.assertIsNone(test_attempt_session.current_question_idx)
        self.assertEqual(test_attempt_session.next_question_idx, 1)
        self.assertIsNone(test_attempt_session.report_url)
        self.assertFalse(test_attempt_session.is_report_sent_to_whatsapp)
        self.assertFalse(test_attempt_session.is_report_sent_to_email)
        self.assertFalse(test_attempt_session.is_checkin_type)
        self.assertEqual(test_attempt_session.feedback_summary, "Feedback summary")
        self.assertEqual(test_attempt_session.culture_and_skill_summary, "Culture and skill summary")
        self.assertEqual(test_attempt_session.mcq_summary, "MCQ summary")
        self.assertIsNone(test_attempt_session.competency_data)
        self.assertEqual(test_attempt_session.language_skills, "English, Spanish")
        self.assertFalse(test_attempt_session.is_idp_discussion_opted)
        self.assertEqual(test_attempt_session.intake_id, "intake_001")
        self.assertEqual(test_attempt_session.conversation_summary, "Conversation summary")
        self.assertEqual(test_attempt_session.related_previous_conversation_summary, "Related previous conversation summary")

