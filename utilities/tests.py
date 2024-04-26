from django.test import TestCase
from utilities.models import (
    SpecialTypeTests,
    MentorDetails,
    SessionNotesRecommendations,
    BotQnA,
    UserActionInfo,
    BotEngagement,
    UserIDP,
    DirectoryPageInfo,
    CoachCoacheeJoiningPreviledge
)
from datetime import datetime,date
from utilities.choices import  UserCanJoinAsChoices
from users.choices import ProfileTypeChoice, BotTypeChoice, CoachCoacheeConnectionStatusChoice, StatusChoice



class MentorDetailsTest(TestCase):

    def setUp(self):

        # Create a MentorDetails instance for testing

        self.mentor_details = MentorDetails.objects.create(
            tenant_id="tenant1", mentor_id="mentor1", mentee_ids="mentee1, mentee2"
        )

    def test_mentor_details_model(self):

        # Test the MentorDetails instance

        self.assertEqual(self.mentor_details.tenant_id, "tenant1")

        self.assertEqual(self.mentor_details.mentor_id, "mentor1")

        self.assertEqual(self.mentor_details.mentee_ids, "mentee1, mentee2")





class SessionNotesRecommendationsModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create a sample object for testing
        cls.session_notes_recommendations = SessionNotesRecommendations.objects.create(
            tenant_id="test_tenant",
            created_date=datetime.now(),
            updated_date=datetime.now(),
            mentor_id="mentor123",
            mentee_id="mentee123",
            session_notes="Test session notes",
            recommendations="Test recommendations",
            simulation_codes="123ABC"
        )

    def test_tenant_id_field(self):
        session_notes_recommendations = SessionNotesRecommendationsModelTest.session_notes_recommendations
        self.assertEqual(session_notes_recommendations.tenant_id, "test_tenant")

    def test_created_date_field(self):
        session_notes_recommendations = SessionNotesRecommendationsModelTest.session_notes_recommendations
        self.assertIsNotNone(session_notes_recommendations.created_date)

    def test_updated_date_field(self):
        session_notes_recommendations = SessionNotesRecommendationsModelTest.session_notes_recommendations
        self.assertIsNotNone(session_notes_recommendations.updated_date)

    def test_mentor_id_field(self):
        session_notes_recommendations = SessionNotesRecommendationsModelTest.session_notes_recommendations
        self.assertEqual(session_notes_recommendations.mentor_id, "mentor123")

    def test_mentee_id_field(self):
        session_notes_recommendations = SessionNotesRecommendationsModelTest.session_notes_recommendations
        self.assertEqual(session_notes_recommendations.mentee_id, "mentee123")

    def test_session_notes_field(self):
        session_notes_recommendations = SessionNotesRecommendationsModelTest.session_notes_recommendations
        self.assertEqual(session_notes_recommendations.session_notes, "Test session notes")

    def test_recommendations_field(self):
        session_notes_recommendations = SessionNotesRecommendationsModelTest.session_notes_recommendations
        self.assertEqual(session_notes_recommendations.recommendations, "Test recommendations")

    def test_simulation_codes_field(self):
        session_notes_recommendations = SessionNotesRecommendationsModelTest.session_notes_recommendations
        self.assertEqual(session_notes_recommendations.simulation_codes, "123ABC")

    def test_db_table_name(self):
        self.assertEqual(SessionNotesRecommendations._meta.db_table, "session_notes_and_recommendations")





class BotQnAModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create a sample object for testing
        cls.bot_qna = BotQnA.objects.create(
            participant_id="test_participant",
            bot_id="test_bot",
            participant_qna={"question": "answer"},
            is_positive=True,
            qna_type="feedback",
            fitment_score={"score": 90},
            intake_summary="Test intake summary",
            is_anonymous=False
        )

    def test_participant_id_field(self):
        bot_qna = BotQnAModelTest.bot_qna
        self.assertEqual(bot_qna.participant_id, "test_participant")

    def test_bot_id_field(self):
        bot_qna = BotQnAModelTest.bot_qna
        self.assertEqual(bot_qna.bot_id, "test_bot")

    def test_participant_qna_field(self):
        bot_qna = BotQnAModelTest.bot_qna
        self.assertEqual(bot_qna.participant_qna, {"question": "answer"})

    def test_is_positive_field(self):
        bot_qna = BotQnAModelTest.bot_qna
        self.assertTrue(bot_qna.is_positive)

    def test_qna_type_field(self):
        bot_qna = BotQnAModelTest.bot_qna
        self.assertEqual(bot_qna.qna_type, "feedback")

    def test_fitment_score_field(self):
        bot_qna = BotQnAModelTest.bot_qna
        self.assertEqual(bot_qna.fitment_score, {"score": 90})

    def test_intake_summary_field(self):
        bot_qna = BotQnAModelTest.bot_qna
        self.assertEqual(bot_qna.intake_summary, "Test intake summary")

    def test_is_anonymous_field(self):
        bot_qna = BotQnAModelTest.bot_qna
        self.assertFalse(bot_qna.is_anonymous)

    def test_db_table_name(self):
        self.assertEqual(BotQnA._meta.db_table, "bot_qna")
        
        
        
        
        
class UserActionInfoModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create a sample object for testing
        cls.user_action_info = UserActionInfo.objects.create(
            user_id="test_user",
            bot_id="test_bot",
            feedback_given=5,
            feedback_recieved=3,
            transcript_email_sent=2,
            transcript_email_recieved=1,
            chat_attempted=10,
            interaction_attempted=15,
            avatar_bot_count=2,
            subject_matter_bot_count=3,
            session_notes_count=8,
            avatar_ids="[1, 2]",
            subject_matter_bot_ids="[3, 4, 5]"
        )

    def test_user_id_field(self):
        user_action_info = UserActionInfoModelTest.user_action_info
        self.assertEqual(user_action_info.user_id, "test_user")

    def test_bot_id_field(self):
        user_action_info = UserActionInfoModelTest.user_action_info
        self.assertEqual(user_action_info.bot_id, "test_bot")

    def test_feedback_given_field(self):
        user_action_info = UserActionInfoModelTest.user_action_info
        self.assertEqual(user_action_info.feedback_given, 5)

    def test_feedback_received_field(self):
        user_action_info = UserActionInfoModelTest.user_action_info
        self.assertEqual(user_action_info.feedback_recieved, 3)

    def test_transcript_email_sent_field(self):
        user_action_info = UserActionInfoModelTest.user_action_info
        self.assertEqual(user_action_info.transcript_email_sent, 2)

    def test_transcript_email_received_field(self):
        user_action_info = UserActionInfoModelTest.user_action_info
        self.assertEqual(user_action_info.transcript_email_recieved, 1)

    def test_chat_attempted_field(self):
        user_action_info = UserActionInfoModelTest.user_action_info
        self.assertEqual(user_action_info.chat_attempted, 10)

    def test_interaction_attempted_field(self):
        user_action_info = UserActionInfoModelTest.user_action_info
        self.assertEqual(user_action_info.interaction_attempted, 15)

    def test_avatar_bot_count_field(self):
        user_action_info = UserActionInfoModelTest.user_action_info
        self.assertEqual(user_action_info.avatar_bot_count, 2)

    def test_subject_matter_bot_count_field(self):
        user_action_info = UserActionInfoModelTest.user_action_info
        self.assertEqual(user_action_info.subject_matter_bot_count, 3)

    def test_session_notes_count_field(self):
        user_action_info = UserActionInfoModelTest.user_action_info
        self.assertEqual(user_action_info.session_notes_count, 8)

    def test_avatar_ids_field(self):
        user_action_info = UserActionInfoModelTest.user_action_info
        self.assertEqual(user_action_info.avatar_ids, "[1, 2]")

    def test_subject_matter_bot_ids_field(self):
        user_action_info = UserActionInfoModelTest.user_action_info
        self.assertEqual(user_action_info.subject_matter_bot_ids, "[3, 4, 5]")

    def test_db_table_name(self):
        self.assertEqual(UserActionInfo._meta.db_table, "user_action_info")



class BotEngagementModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create a sample object for testing
        cls.bot_engagement = BotEngagement.objects.create(
            bot_id="test_bot",
            user_id="test_user",
            interacted_on=date.today(),
            num_of_clicked_button=5,
            attempted_bot_questions=3,
            num_of_bot_sessions=2
        )

    def test_bot_id_field(self):
        bot_engagement = BotEngagementModelTest.bot_engagement
        self.assertEqual(bot_engagement.bot_id, "test_bot")

    def test_user_id_field(self):
        bot_engagement = BotEngagementModelTest.bot_engagement
        self.assertEqual(bot_engagement.user_id, "test_user")

    def test_interacted_on_field(self):
        bot_engagement = BotEngagementModelTest.bot_engagement
        self.assertEqual(bot_engagement.interacted_on, date.today())

    def test_num_of_clicked_button_field(self):
        bot_engagement = BotEngagementModelTest.bot_engagement
        self.assertEqual(bot_engagement.num_of_clicked_button, 5)

    def test_attempted_bot_questions_field(self):
        bot_engagement = BotEngagementModelTest.bot_engagement
        self.assertEqual(bot_engagement.attempted_bot_questions, 3)

    def test_num_of_bot_sessions_field(self):
        bot_engagement = BotEngagementModelTest.bot_engagement
        self.assertEqual(bot_engagement.num_of_bot_sessions, 2)

    def test_unique_together_constraint(self):
        # Test unique_together constraint
        with self.assertRaises(Exception):
            BotEngagement.objects.create(
                bot_id="test_bot",
                user_id="test_user",
                interacted_on=date.today(),
            )

    def test_db_table_name(self):
        self.assertEqual(BotEngagement._meta.db_table, "bot_engagements")




class UserIDPModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create a sample object for testing
        cls.user_idp = UserIDP.objects.create(
            user_id="test_user",
            user_name="Test User",
            strengths="Strengths",
            weakness="Weaknesses",
            opportunities="Opportunities",
            threats="Threats",
            key_focus_areas="Key Focus Areas",
            goals="Goals",
            priorities="Priorities",
            learning_histories="Learning Histories",
            key_skills="Key Skills",
            skill_gap_for_development="Skill Gap for Development",
            leadership_skill_focus_area="Leadership Skill Focus Area",
            book_recommendations="Book Recommendations",
            course_recommendations="Course Recommendations",
            recommended_hbr="Recommended HBR",
            recommended_ted_talk="Recommended TED Talk",
            recommended_scenarios={"scenario1": "description1", "scenario2": "description2"},
            learning_communities="Learning Communities",
            report="Report",
            success=True,
            total_scenarios_created=10
        )

    def test_opportunities_field(self):
        user_idp = UserIDPModelTest.user_idp
        self.assertEqual(user_idp.opportunities, "Opportunities")

    def test_threats_field(self):
        user_idp = UserIDPModelTest.user_idp
        self.assertEqual(user_idp.threats, "Threats")

    def test_key_focus_areas_field(self):
        user_idp = UserIDPModelTest.user_idp
        self.assertEqual(user_idp.key_focus_areas, "Key Focus Areas")

    def test_goals_field(self):
        user_idp = UserIDPModelTest.user_idp
        self.assertEqual(user_idp.goals, "Goals")

    def test_priorities_field(self):
        user_idp = UserIDPModelTest.user_idp
        self.assertEqual(user_idp.priorities, "Priorities")

    def test_learning_histories_field(self):
        user_idp = UserIDPModelTest.user_idp
        self.assertEqual(user_idp.learning_histories, "Learning Histories")

    def test_key_skills_field(self):
        user_idp = UserIDPModelTest.user_idp
        self.assertEqual(user_idp.key_skills, "Key Skills")

    def test_skill_gap_for_development_field(self):
        user_idp = UserIDPModelTest.user_idp
        self.assertEqual(user_idp.skill_gap_for_development, "Skill Gap for Development")

    def test_leadership_skill_focus_area_field(self):
        user_idp = UserIDPModelTest.user_idp
        self.assertEqual(user_idp.leadership_skill_focus_area, "Leadership Skill Focus Area")

    def test_book_recommendations_field(self):
        user_idp = UserIDPModelTest.user_idp
        self.assertEqual(user_idp.book_recommendations, "Book Recommendations")

    def test_course_recommendations_field(self):
        user_idp = UserIDPModelTest.user_idp
        self.assertEqual(user_idp.course_recommendations, "Course Recommendations")

    def test_recommended_hbr_field(self):
        user_idp = UserIDPModelTest.user_idp
        self.assertEqual(user_idp.recommended_hbr, "Recommended HBR")

    def test_recommended_ted_talk_field(self):
        user_idp = UserIDPModelTest.user_idp
        self.assertEqual(user_idp.recommended_ted_talk, "Recommended TED Talk")

    def test_recommended_scenarios_field(self):
        user_idp = UserIDPModelTest.user_idp
        self.assertEqual(user_idp.recommended_scenarios, {"scenario1": "description1", "scenario2": "description2"})

    def test_learning_communities_field(self):
        user_idp = UserIDPModelTest.user_idp
        self.assertEqual(user_idp.learning_communities, "Learning Communities")

    def test_report_field(self):
        user_idp = UserIDPModelTest.user_idp
        self.assertEqual(user_idp.report, "Report")

    def test_success_field(self):
        user_idp = UserIDPModelTest.user_idp
        self.assertTrue(user_idp.success)

    def test_total_scenarios_created_field(self):
        user_idp = UserIDPModelTest.user_idp
        self.assertEqual(user_idp.total_scenarios_created, 10)




class DirectoryPageInfoModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create a sample object for testing
        cls.directory_page_info = DirectoryPageInfo.objects.create(
            name="Test Name",
            profile_id="test_profile_id",
            department="Test Department",
            bot_type=BotTypeChoice.avatar_bot,
            profile_pic_url="test_profile_pic_url",
            profile_type=ProfileTypeChoice.coach,
            description="Test Description",
            experience="Test Experience",
            expertise="Test Expertise",
            status=StatusChoice.available,
            avatar_bot_id="test_avatar_bot_id",
            feedback_wall="Test Feedback Wall",
            skills="Test Skills",
            is_visible=True,
            is_approved=True,
            avatar_snippit="Test Avatar Snippit",
            avatar_bot_url="Test Avatar Bot URL",
            custom_user_bot_url="Test Custom User Bot URL",
            custom_user_bot_id="Test Custom User Bot ID",
            timer_enabled=True,
            time_value_in_days="Test Time Value",
            timer_reset=True,
            visual_tag="Test Visual Tag",
            ai_email="test@example.com",
            _previous_is_approved=True
        )

    def test_name_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertEqual(directory_page_info.name, "Test Name")
        
        
    def test_profile_id_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertEqual(directory_page_info.profile_id, "test_profile_id")
        
        
    def test_department_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertEqual(directory_page_info.department, "Test Department")

    def test_bot_type_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertEqual(directory_page_info.bot_type, BotTypeChoice.avatar_bot)

    def test_profile_pic_url_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertEqual(directory_page_info.profile_pic_url, "test_profile_pic_url")

    def test_profile_type_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertEqual(directory_page_info.profile_type, ProfileTypeChoice.coach)

    def test_description_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertEqual(directory_page_info.description, "Test Description")

    def test_experience_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertEqual(directory_page_info.experience, "Test Experience")

    def test_expertise_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertEqual(directory_page_info.expertise, "Test Expertise")

    def test_status_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertEqual(directory_page_info.status, StatusChoice.available)

    def test_avatar_bot_id_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertEqual(directory_page_info.avatar_bot_id, "test_avatar_bot_id")

    def test_feedback_wall_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertEqual(directory_page_info.feedback_wall, "Test Feedback Wall")

    def test_skills_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertEqual(directory_page_info.skills, "Test Skills")

    def test_is_visible_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertTrue(directory_page_info.is_visible)

    def test_is_approved_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertTrue(directory_page_info.is_approved)

    def test_avatar_snippit_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertEqual(directory_page_info.avatar_snippit, "Test Avatar Snippit")

    def test_avatar_bot_url_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertEqual(directory_page_info.avatar_bot_url, "Test Avatar Bot URL")

    def test_custom_user_bot_url_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertEqual(directory_page_info.custom_user_bot_url, "Test Custom User Bot URL")

    def test_custom_user_bot_id_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertEqual(directory_page_info.custom_user_bot_id, "Test Custom User Bot ID")

    def test_timer_enabled_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertTrue(directory_page_info.timer_enabled)

    def test_time_value_in_days_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertEqual(directory_page_info.time_value_in_days, "Test Time Value")

    def test_timer_reset_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertTrue(directory_page_info.timer_reset)

    def test_visual_tag_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertEqual(directory_page_info.visual_tag, "Test Visual Tag")

    def test_ai_email_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertEqual(directory_page_info.ai_email, "test@example.com")

    def test_previous_is_approved_field(self):
        directory_page_info = DirectoryPageInfoModelTest.directory_page_info
        self.assertTrue(directory_page_info._previous_is_approved)




class CoachCoacheeJoiningPreviledgeModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create a sample object for testing
        cls.coach_coachee_joining_previledge = CoachCoacheeJoiningPreviledge.objects.create(
            email="test@example.com",
            client_name="Test Client",
            can_join_as=UserCanJoinAsChoices.coachee,
            deleted=False
        )

    def test_email_field(self):
        coach_coachee_joining_previledge = CoachCoacheeJoiningPreviledgeModelTest.coach_coachee_joining_previledge
        self.assertEqual(coach_coachee_joining_previledge.email, "test@example.com")

    def test_client_name_field(self):
        coach_coachee_joining_previledge = CoachCoacheeJoiningPreviledgeModelTest.coach_coachee_joining_previledge
        self.assertEqual(coach_coachee_joining_previledge.client_name, "Test Client")

    def test_can_join_as_field(self):
        coach_coachee_joining_previledge = CoachCoacheeJoiningPreviledgeModelTest.coach_coachee_joining_previledge
        self.assertEqual(coach_coachee_joining_previledge.can_join_as, UserCanJoinAsChoices.coachee)

    def test_deleted_field(self):
        coach_coachee_joining_previledge = CoachCoacheeJoiningPreviledgeModelTest.coach_coachee_joining_previledge
        self.assertFalse(coach_coachee_joining_previledge.deleted)

    def test_db_table_name(self):
        self.assertEqual(CoachCoacheeJoiningPreviledge._meta.db_table, "coach_coachee_joining_previledge")

