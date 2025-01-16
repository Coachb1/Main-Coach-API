from django.test import TestCase
from .models import Test, TestAttemptSessionStatusChoices, TestAttemptSession, Psychometric, PsychometricItem
from .choices import InteractionModeChoices, TestTypeChoices, ScenarioCaseChoices, TestAttemptSessionStatusChoices
from django.db.utils import IntegrityError

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



# psychometric test 


class TestPsychometricItem(TestCase):
    def setUp(self):
        self.item = PsychometricItem.objects.create(
            section="Personality",
            subsection="Openness",
            parameters={"scale": "1-5", "questions": 10},
            range_values={"min": 1, "max": 5},
            average_value="3.5"
        )

    def test_create_psychometric_item(self):
        """Test creating a basic psychometric item"""
        self.assertEqual(self.item.section, "Personality")
        self.assertEqual(self.item.subsection, "Openness")
        self.assertEqual(self.item.parameters["scale"], "1-5")
        self.assertEqual(self.item.range_values["min"], 1)
        self.assertEqual(self.item.average_value, "3.5")

    def test_string_representation(self):
        """Test the string representation of PsychometricItem"""
        expected_string = f"{self.item.id} -Personality : Openness"
        self.assertEqual(str(self.item), expected_string)

    def test_blank_subsection(self):
        """Test that subsection can be blank"""
        item = PsychometricItem.objects.create(section="Personality")
        self.assertIsNone(item.subsection)

class TestPsychometric(TestCase):
    def setUp(self):
        self.psychometric = Psychometric.objects.create(
            name="Big Five Personality Test",
            description="Measures five personality dimensions",
            tenant_id="tenant1"
        )
        self.item1 = PsychometricItem.objects.create(
            section="Personality",
            subsection="Conscientiousness"
        )
        self.item2 = PsychometricItem.objects.create(
            section="Personality",
            subsection="Extraversion"
        )

    def test_create_psychometric(self):
        """Test creating a basic psychometric"""
        self.assertEqual(self.psychometric.name, "Big Five Personality Test")
        self.assertEqual(
            self.psychometric.description, 
            "Measures five personality dimensions"
        )

    def test_add_items(self):
        """Test adding items to psychometric"""
        self.psychometric.items.add(self.item1, self.item2)
        self.assertEqual(self.psychometric.items.count(), 2)
        self.assertIn(self.item1, self.psychometric.items.all())
        self.assertIn(self.item2, self.psychometric.items.all())

    def test_unique_together_constraint(self):
        """Test that name and tenant_id combination must be unique"""
        with self.assertRaises(IntegrityError):
            Psychometric.objects.create(
                name="Big Five Personality Test",
                tenant_id="tenant1"
            )

class TestTest(TestCase):
    def setUp(self):
        self.psychometric = Psychometric.objects.create(
            name="Career Assessment",
            tenant_id="tenant1"
        )
        self.test = Test.objects.create(
            creator_id="user123",
            title="Career Aptitude Test",
            test_code="CAT001",
            tenant_id="tenant1",
            interaction_mode="async",
            test_type="trainer",
            psychometric=self.psychometric
        )

    def test_create_test(self):
        """Test creating a basic test"""
        self.assertEqual(self.test.title, "Career Aptitude Test")
        self.assertEqual(self.test.test_code, "CAT001")
        self.assertEqual(self.test.creator_id, "user123")
        self.assertEqual(self.test.psychometric, self.psychometric)

    def test_test_code_uniqueness(self):
        """Test that test_code must be unique per tenant"""
        with self.assertRaises(IntegrityError):
            Test.objects.create(
                creator_id="user456",
                title="Another Test",
                test_code="CAT001",  # Same test_code
                tenant_id="tenant1",  # Same tenant
                interaction_mode="async",
                test_type="trainer"
            )

    def test_boolean_fields_default_values(self):
        """Test default values of boolean fields"""
        self.assertFalse(self.test.is_single_bot)
        self.assertFalse(self.test.is_self_created)
        self.assertTrue(self.test.is_repeat)
        self.assertFalse(self.test.is_game_type)

class TestIntegration(TestCase):
    def setUp(self):
        # Create base test data
        self.psychometric = Psychometric.objects.create(
            name="Comprehensive Assessment",
            tenant_id="tenant1"
        )
        
        self.items = []
        sections = ["Cognitive", "Emotional", "Social"]
        for section in sections:
            item = PsychometricItem.objects.create(
                section=section,
                parameters={"questions": 5},
                range_values={"min": 0, "max": 100}
            )
            self.items.append(item)
            self.psychometric.items.add(item)

        self.test = Test.objects.create(
            creator_id="user123",
            title="Full Assessment Test",
            test_code="FAT001",
            tenant_id="tenant1",
            interaction_mode="async",
            test_type="trainer",
            psychometric=self.psychometric
        )

    def test_complete_assessment_flow(self):
        """Test the complete relationship between all models"""
        # Verify psychometric has correct items
        self.assertEqual(self.psychometric.items.count(), 3)
        
        # Verify test links to psychometric
        self.assertEqual(self.test.psychometric, self.psychometric)
        
        # Verify we can access items through test->psychometric
        test_items = self.test.psychometric.items.all()
        self.assertEqual(len(test_items), 3)
        
        # Verify sections are correct
        sections = [item.section for item in test_items]
        self.assertIn("Cognitive", sections)
        self.assertIn("Emotional", sections)
        self.assertIn("Social", sections)

    def test_cascade_relationships(self):
        """Test that relationships are maintained properly"""
        # Add psychometric sections to test
        self.test.pshycometric_sections = {
            "selected_sections": ["Cognitive", "Emotional"]
        }
        self.test.save()

        # Verify we can still access all relationships
        self.assertEqual(
            self.test.psychometric.items.filter(
                section__in=["Cognitive", "Emotional"]
            ).count(),
            2
        )

    def test_multi_tenant_isolation(self):
        """Test that tenant isolation works across all models"""
        # Create a different tenant's psychometric
        other_psychometric = Psychometric.objects.create(
            name="Comprehensive Assessment",  # Same name
            tenant_id="tenant2"  # Different tenant
        )
        
        # This should work because it's a different tenant
        other_test = Test.objects.create(
            creator_id="user456",
            title="Full Assessment Test",
            test_code="FAT001",  # Same code as previous test
            tenant_id="tenant2",
            interaction_mode="async",
            test_type="trainer",
            psychometric=other_psychometric
        )

        # Verify both tests exist
        self.assertNotEqual(self.test.tenant_id, other_test.tenant_id)
        self.assertEqual(Test.objects.count(), 2)