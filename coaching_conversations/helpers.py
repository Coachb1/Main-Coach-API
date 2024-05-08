import logging

from django.utils import timezone
from rest_framework import serializers
from commons.google_search import get_searched_links_contents, scrape_article_data

from coaching_conversations.choices import CoachingConversationChoices
from coaching_conversations.models import CoachingConversation
from commons.openai_gpt import gpt3_completion
from commons.timeit import timeit
from external_apis.coach_whisper_api import coach_whisper_api
from tenants.models import Tenant
from tests.choices import TestTypeChoices, InteractionModeChoices
from tests.models import TestAttemptSession, Test, TestQuestion
from users.models import User
from commons.openai_gpt import gpt_wishper_api
from users.models import SignatureBot, BotAttribute, CoachCoacheeMentorMenteeProfile
from commons.anthropic import anthropic_completion
from users.db import get_user_display_name, get_user_by_id
from string import Template
from utilities.helpers import save_user_action_info, save_bot_engagement
import json
from utilities.models import BotQnA, UserIDP
from skills.models import CharacteristicsAndPrompts
from users.helpers import get_user_attribute
from users.models import BotAndUserMapping, ClientUserInfo, UserAttribute
from users.choices import ProfileTypeChoice
from users.choices import BotTypeChoice
from apis.accounts.serializers import UserIDPSerializers
from utilities.models import SessionNotesRecommendations
import requests
from utilities.prompts import get_intake_summary_prompt
from commons.utils import remove_punctuations
from tests.helpers import get_relevant_session_summary
from documents.utils import get_document_summary
from identities.models import Identity
import datetime
from utilities.helpers import extract_fields

logger = logging.getLogger(__name__)


@timeit
def create_test_coaching_conversation_session(tenant: Tenant,
                                              test_id: str,
                                              participant_id: str) -> TestAttemptSession:
    try:
        test = Test.objects.get(tenant_id=tenant.uid, uid=test_id, deleted=0)
    except Test.DoesNotExist as e:
        logger.exception(
            "failed to create session, test with id %s does not exist", test_id)
        raise serializers.ValidationError("invalid test id")

    try:
        participant = User.objects.get(
            tenant_id=tenant.uid, uid=participant_id, deleted=0)
    except User.DoesNotExist as e:
        logger.exception(
            "failed to create session, participant with id %s does not exist", test_id)
        raise serializers.ValidationError("invalid participant id")

    test_attempt_session = TestAttemptSession.objects.create(
        tenant_id=tenant.uid,
        test_id=test_id,
        participant_id=participant_id,
        test_invite_id=None,
        started_at=timezone.now()
    )

    logger.info(
        "created test_coaching_conversation_session for tenant %s", tenant.uid)

    return test_attempt_session


def get_coaching_conversation_prompt(candidate_data_str, test, question):
    """
    Generates a prompt for a coaching conversation based on the candidate's data, the test information, and the question being asked.
    
    Args:
        candidate_data_str (str): The candidate's response to the question.
        test (Test object): The test object containing information about the test.
        question (TestQuestion object): The question object containing information about the question.
    
    Returns:
        str: The generated prompt for the coaching conversation.
    """
#     return f"""
# Context:{candidate_data_str} \n\nImagine you are an life coach 
# who has just asked some question to which the candidate responds with the above 
# \"Context\". Provide developmental response to the candidate based on their answers, 
# and also ask a question to further explore their skills and knowledge in this domain. 
# Please make sure to provide elaborate feedback and it should be intertwined 
# with the question in a way that creates a cohesive conversation.
# NOTE: Do not show word count.(Eg: 50 words)
# """
    expert_suggestions = question.gpt_prompt_override if question.gpt_prompt_override else ""

    prompt = f"""
        Title: {test.title}. 
        Test Description: {test.description}
        Expert Suggestions:  {expert_suggestions} 
        Context : {candidate_data_str}

        You are a coach who is conducting a session with a candidate who is sharing their problem here {{Context}}. Provide a developmental response to the candidate based on their response. Provide realistic and actionable strategies to help the candidate solve their problem. Guide the candidate to reach an effective solution to their problem. The response should be based on the {expert_suggestions}. 
        Ask a question to further explore their skills and knowledge in this domain. 
        NOTE: The question should not be more than 100 words.
        NOTE: Do not show word count.(Eg: 50 words)
    """

    return prompt


@timeit
def initialize_coaching_conversation(tenant: Tenant,
                                     test_attempt_session_id: str, is_signature_bot: bool, initial_qna: str) -> CoachingConversation:
    """
    Initializes a coaching conversation based on a test attempt session.

    Args:
        tenant (Tenant): The tenant object representing the organization.
        test_attempt_session_id (str): The ID of the test attempt session.

    Returns:
        CoachingConversation: The newly created coaching conversation object.

    Raises:
        serializers.ValidationError: If the test ID is invalid or the test type is not supported.
    """
    test_attempt_session = TestAttemptSession.objects.get(
        tenant_id=tenant.uid,
        uid=test_attempt_session_id,
        deleted=0
    )

    if not is_signature_bot:
        try:
            test = Test.objects.get(tenant_id=tenant.uid,
                                    uid=test_attempt_session.test_id, deleted=0)
        except Test.DoesNotExist as e:
            logger.exception("failed, id %s does not exist",
                            test_attempt_session.test_id)
            raise serializers.ValidationError("invalid test id")

        if test.test_type != TestTypeChoices.coaching:
            raise serializers.ValidationError(
                f"test type {test.test_type} is not supported")

        question = TestQuestion.objects.get(
            tenant_id=tenant.uid, test_id=test.uid, deleted=0)
        
    signature_bot_question = "what would you like to discuss today?"
    if is_signature_bot:
        signature_bot = SignatureBot.objects.get(deleted=False,tenant_id=tenant.uid,uid=test_attempt_session.test_id)
        user = User.objects.get(tenant_id=tenant.uid,uid=test_attempt_session.participant_id)
        get_or_create_bot_user_mapping(signature_bot,user)
        
        bot_type = signature_bot.bot_type

        if bot_type in [BotTypeChoice.avatar_bot]:

            sessions = TestAttemptSession.objects.filter(deleted=0,tenant_id=tenant.uid,test_id=signature_bot.uid,participant_id=test_attempt_session.participant_id)

            session_summaries = []
            for session in sessions:
                if session.conversation_summary:
                    session_summaries.append(session.conversation_summary)


            initial_que_ans = ""

            initial_qna_text = None
            if bot_type == BotTypeChoice.avatar_bot:
                if test_attempt_session.intake_id:
                    initial_qna_text = BotQnA.objects.filter(tenant_id = tenant.uid,bot_id=signature_bot.uid,qna_type='initial_qna',uid=test_attempt_session.intake_id).order_by('-created').first()
                else:
                    initial_qna_text = BotQnA.objects.filter(tenant_id = tenant.uid,participant_id=test_attempt_session.participant_id,bot_id=signature_bot.uid,qna_type="initial_qna").order_by('-id').first()
            else:
                initial_qna_text = BotQnA.objects.filter(tenant_id = tenant.uid,participant_id=test_attempt_session.participant_id,bot_id=signature_bot.uid,qna_type="initial_qna").order_by('-id').first()

            if initial_qna_text:
                initial_que_ans = initial_qna_text.intake_summary


            releated_session_summary = None
            

            # if len(session_summaries) > 0:
            #     releated_session_summary = get_relevant_session_summary(session_summaries,initial_que_ans)

            logger.info(f" session_summaries: {session_summaries}")
            if releated_session_summary:
                test_attempt_session.related_previous_conversation_summary = releated_session_summary
                test_attempt_session.save(update_fields=['related_previous_conversation_summary'])

        if initial_qna:
            if test_attempt_session.intake_id:
                bot_qna = BotQnA.objects.filter(tenant_id = tenant.uid,bot_id=signature_bot.uid,qna_type='initial_qna',uid=test_attempt_session.intake_id).order_by('-created').first()
                if bot_qna:
                    initial_qna = bot_qna.participant_qna
                

            qna = json.loads(initial_qna)
            custom_prompt = signature_bot.custom_prompt
            # saving initial_qna
            # BotQnA.objects.create(
            #     tenant_id = tenant.uid,
            #     bot_id = signature_bot.uid,
            #     participant_id = test_attempt_session.participant_id,
            #     participant_qna = qna,
            #     qna_type = 'initial_qna'
            # )
            if custom_prompt:
                
                initial_que_ans = ''
                if signature_bot.bot_type not in [BotTypeChoice.subject_matter_bot, BotTypeChoice.user_bot]:
                    for que, ans in qna.items():
                        initial_que_ans += f"Question: {que} Answer: {ans} \n"

                

                coach_info = ""
                for key,val in signature_bot.data.items():
                    coach_info += f"{key}:{val}\n"

                sessions = TestAttemptSession.objects.filter(uid=test_attempt_session.uid) # current conversation

                conversation_data= get_bot_conversation_data_user(sessions,tenant,test_attempt_session.participant_id,only_converation=True)
                conversation_history = [{"coach": i['coach_message_text'], "user":i['participant_message_text']} for i in conversation_data]


                if signature_bot.bot_type == 'avatar_bot':
                    qna_block = get_qna_block_for_coach_mentor(coach_user_id=signature_bot.user_id,participant_id=test_attempt_session.participant_id,tenant_id=tenant.uid)
                    if qna_block:
                        qna_block_text = ''
                        for que, ans in qna_block.items():
                            qna_block_text += f"Question: {que} Answer: {ans}\n"

                        coach_info += "\n" + "FAQs:" + '\n' + qna_block_text

                    user_recent_idp = None
                    if test_attempt_session.is_idp_discussion_opted:
                        idp = UserIDP.objects.filter(tenant_id=tenant.uid, user_id=test_attempt_session.participant_id, deleted=0).order_by('-created').first()
                        if idp:
                            user_recent_idp = {
                                    "strengths": idp.strengths,
                                    "weakness": idp.weakness,
                                    "opportunities": idp.opportunities,
                                    "threats": idp.threats,
                                    "key_focus_areas": idp.key_focus_areas,
                                    "goals": idp.goals,
                                    "priorities": idp.priorities,
                                    "learning_histories": idp.learning_histories,
                                    "key_skills": idp.key_skills,
                                    "skill_gap_for_development": idp.skill_gap_for_development,
                                    "leadership_skill_focus_area": idp.leadership_skill_focus_area,
                                    "book_recommendations": idp.book_recommendations,
                                    "course_recommendations": idp.course_recommendations,
                                    "recommended_ted_talk": idp.recommended_ted_talk,
                                    "recommended_scenarios": idp.recommended_scenarios,
                                }
                    try:
                        personalities = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,user_id=test_attempt_session.participant_id).first()
                        highest_charactersic_prompt = CharacteristicsAndPrompts.objects.filter(name = personalities.high_rating_characteristics)
                        lowest_charactersic_prompt = CharacteristicsAndPrompts.objects.filter(name = personalities.low_rating_characteristics)
                        low_char_prompt = ""
                        for l in lowest_charactersic_prompt:
                            low_char_prompt += f"{l.negitive_prompt} "
                        high_char_prompt = ""
                        for l in highest_charactersic_prompt:
                            high_char_prompt += f"{l.positive_prompt} "
                        personality = low_char_prompt + " " + high_char_prompt

                    except Exception as e:
                        logger.exception(f"got error: {e}")
                        personality = None
            
                    custom_prompt = Template(custom_prompt).substitute(
                        coach_info = coach_info,
                        conversation_history = conversation_history,
                        context = initial_que_ans,
                        user_personality = personality if signature_bot.use_personality_context else None,
                        idp_report_data = user_recent_idp,
                        session_notes = get_latest_session_notes_coach_coachee(coach_user_id=signature_bot.user_id,coachee_user_id=test_attempt_session.participant_id,tenant_id=test_attempt_session.tenant_id)
                    )

                elif signature_bot.bot_type == BotTypeChoice.coachbots:
                    personality = None
                    if signature_bot.use_personality_context:
                        try:
                            personalities = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,user_id=test_attempt_session.participant_id).first()
                            highest_charactersic_prompt = CharacteristicsAndPrompts.objects.filter(name = personalities.high_rating_characteristics)
                            lowest_charactersic_prompt = CharacteristicsAndPrompts.objects.filter(name = personalities.low_rating_characteristics)
                            low_char_prompt = ""
                            for l in lowest_charactersic_prompt:
                                low_char_prompt += f"{l.negitive_prompt} "
                            high_char_prompt = ""
                            for l in highest_charactersic_prompt:
                                high_char_prompt += f"{l.positive_prompt} "
                            personality = low_char_prompt + " " + high_char_prompt

                        except Exception as e:
                            logger.exception(f"got error: {e}")
                            personality = None

                    custom_prompt = Template(custom_prompt).safe_substitute(
                        user_intake = initial_que_ans,
                        user_context = conversation_history,
                        user_personality = personality
                    )

                elif signature_bot.bot_type == 'helper_bot':
                    try:
                        personalities = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,user_id=test_attempt_session.participant_id).first()
                        highest_charactersic_prompt = CharacteristicsAndPrompts.objects.filter(name = personalities.high_rating_characteristics)
                        lowest_charactersic_prompt = CharacteristicsAndPrompts.objects.filter(name = personalities.low_rating_characteristics)
                        low_char_prompt = ""
                        for l in lowest_charactersic_prompt:
                            low_char_prompt += f"{l.negitive_prompt} "
                        high_char_prompt = ""
                        for l in highest_charactersic_prompt:
                            high_char_prompt += f"{l.positive_prompt} "
                        personality = low_char_prompt + " " + high_char_prompt

                    except Exception as e:
                        logger.exception(f"got error: {e}")
                        personality = None
            
                    bot_att = BotAttribute.objects.get(bot_id = signature_bot.uid)
                    faqs = bot_att.attached_faqs_context
                    faqs_text = ""
                    for que, ans in faqs.items():
                        faqs_text += f"Question: {que} Answer: {ans}\n"

                    idp_data = {}
                    if signature_bot.use_idp:
                        idp = UserIDP.objects.filter(deleted=False,tenant_id=tenant.uid,user_id=test_attempt_session.participant_id,success=True).order_by("-created").first()
                        if idp:
                            idp_data = {
                                "strengths": idp.strengths,
                                "weakness": idp.weakness,
                                "opportunities": idp.opportunities,
                                "threats": idp.threats,
                                "key_focus_areas": idp.key_focus_areas,
                                "goals": idp.goals,
                                "priorities": idp.priorities,
                                "learning_histories": idp.learning_histories,
                                "key_skills": idp.key_skills,
                                "skill_gap_for_development": idp.skill_gap_for_development,
                                "leadership_skill_focus_area": idp.leadership_skill_focus_area,
                                "book_recommendations": idp.book_recommendations,
                                "course_recommendations": idp.course_recommendations,
                                "recommended_ted_talk": idp.recommended_ted_talk,
                            }

                    custom_prompt = Template(custom_prompt).substitute(
                                    conversation_history = initial_que_ans,
                                    user_personality = personality if signature_bot.use_personality_context else None,
                                    articles = coach_info + " General FAQs: " + faqs_text,
                                    google_search = "" , # TODO: Add functionality for extacting googlesearch result
                                    idp_data = idp_data
                                )
                    
                # elif signature_bot.bot_type == 'subject_matter_bot':
                #     bot_att = BotAttribute.objects.get(bot_id = signature_bot.uid)
                #     faqs = bot_att.attached_faqs_context
                #     faqs_text = ""
                #     for que, ans in faqs.items():
                #         faqs_text += f"Question: {que} Answer: {ans}\n"

                    # custom_prompt = Template(custom_prompt).substitute(
                    #                 conversation_history = initial_que_ans,
                    #                 articles = coach_info + " General FAQs: " + faqs_text,
                    #                 google_search = ""  # TODO: Add functionality for extacting googlesearch result
                    #             )


                
            else:
                initial_que_ans = ''
                if signature_bot.bot_type not in [BotTypeChoice.subject_matter_bot, BotTypeChoice.user_bot]:
                    for que, ans in qna.items():
                        initial_que_ans += f"Question: {que} Answer: {ans} \n"

                

                coach_info = ""
                for key,val in signature_bot.data.items():
                    coach_info += f"{key}:{val}\n"

                sessions = TestAttemptSession.objects.filter(uid=test_attempt_session.uid)

                conversation_data= get_bot_conversation_data_user(sessions,tenant,test_attempt_session.participant_id,only_converation=True)
                conversation_history = [{"coach": i['coach_message_text'], "user":i['participant_message_text']} for i in conversation_data]


                if signature_bot.bot_type == 'avatar_bot':
                    qna_block = get_qna_block_for_coach_mentor(coach_user_id=signature_bot.user_id,participant_id=test_attempt_session.participant_id,tenant_id=tenant.uid)
                    if qna_block:
                        qna_block_text = ''
                        for que, ans in qna_block.items():
                            qna_block_text += f"Question: {que} Answer: {ans}\n"

                        coach_info += "\n" + "FAQs:" + '\n' + qna_block_text

                    user_recent_idp = None
                    if test_attempt_session.is_idp_discussion_opted:
                        idp = UserIDP.objects.filter(tenant_id=tenant.uid, user_id=test_attempt_session.participant_id, deleted=0).order_by('-created').first()
                        if idp:
                            user_recent_idp = {
                                    "strengths": idp.strengths,
                                    "weakness": idp.weakness,
                                    "opportunities": idp.opportunities,
                                    "threats": idp.threats,
                                    "key_focus_areas": idp.key_focus_areas,
                                    "goals": idp.goals,
                                    "priorities": idp.priorities,
                                    "learning_histories": idp.learning_histories,
                                    "key_skills": idp.key_skills,
                                    "skill_gap_for_development": idp.skill_gap_for_development,
                                    "leadership_skill_focus_area": idp.leadership_skill_focus_area,
                                    "book_recommendations": idp.book_recommendations,
                                    "course_recommendations": idp.course_recommendations,
                                    "recommended_ted_talk": idp.recommended_ted_talk,
                                    "recommended_scenarios": idp.recommended_scenarios,
                                }
                    try:
                        personalities = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,user_id=test_attempt_session.participant_id).first()
                        highest_charactersic_prompt = CharacteristicsAndPrompts.objects.filter(name = personalities.high_rating_characteristics)
                        lowest_charactersic_prompt = CharacteristicsAndPrompts.objects.filter(name = personalities.low_rating_characteristics)
                        low_char_prompt = ""
                        for l in lowest_charactersic_prompt:
                            low_char_prompt += f"{l.negitive_prompt} "
                        high_char_prompt = ""
                        for l in highest_charactersic_prompt:
                            high_char_prompt += f"{l.positive_prompt} "
                        personality = low_char_prompt + " " + high_char_prompt

                    except Exception as e:
                        logger.exception(f"got error: {e}")
                        personality = None
            
                    custom_prompt = Template(signature_bot_default_prompt()).substitute(
                        coach_info = coach_info,
                        conversation_history = conversation_history,
                        context = initial_que_ans,
                        user_personality = personality if signature_bot.use_personality_context else None,
                        idp_report_data = user_recent_idp,
                        session_notes = get_latest_session_notes_coach_coachee(coach_user_id=signature_bot.user_id,coachee_user_id=test_attempt_session.participant_id,tenant_id=test_attempt_session.tenant_id)
                    )

                elif signature_bot.bot_type == BotTypeChoice.user_bot:
                    if signature_bot.faqs:
                        coach_info += "\n FAQS: \n"
                        try:
                            faq = json.loads(signature_bot.faqs)
                        except:
                            faq = signature_bot.faqs

                        for que, ans in faq.items():
                            coach_info += f"Question: {que}, Answer: {ans}\n"

                    custom_prompt = Template(signature_bot_default_prompt(bot_type=BotTypeChoice.user_bot)).safe_substitute(
                        user_info = coach_info,
                        user_context = conversation_history
                    )
            logger.info(f"signature  bot prompt  {custom_prompt}")

            if signature_bot.bot_type != 'subject_matter_bot':
                signature_bot_question = anthropic_completion(custom_prompt,50000)



    next_conversation = CoachingConversation.objects.create(
        tenant_id=tenant.uid,
        test_attempt_session_id=test_attempt_session_id,
        coach_message_text=question.question if not is_signature_bot else signature_bot_question,
        coach_message_metadata=None
    )

    return next_conversation


@timeit
def continue_coaching_conversation(tenant: Tenant,
                                   reply_to_conversation: CoachingConversation,
                                   participant_message_text: str,
                                   participant_message_url: str,
                                   is_signature_bot: bool,
                                   is_prompt_only: bool) -> CoachingConversation:
    """
    Continues a coaching conversation by saving the participant's message, retrieving the test and session information,
    processing the participant's message based on the interaction mode, generating a response using OpenAI GPT-3.5,
    and creating a new coaching conversation with the generated response.

    :param tenant: The tenant object representing the current tenant.
    :param reply_to_conversation: The coaching conversation object to which the participant's message will be replied.
    :param participant_message_text: The text of the participant's message.
    :param participant_message_url: The URL of the participant's message audio or video file.
    :return: The newly created coaching conversation object with the generated response.
    """

    reply_to_conversation.participant_message_text = participant_message_text
    reply_to_conversation.participant_message_url = participant_message_url
    reply_to_conversation.status = CoachingConversationChoices.participant_message_saved
    reply_to_conversation.save()

    try:
        test_attempt_session = TestAttemptSession.objects.get(tenant_id=tenant.uid,
                                                              uid=reply_to_conversation.test_attempt_session_id,
                                                              deleted=0)
    except TestAttemptSession.DoesNotExist as e:
        logger.exception("failed to get session, test attempt session with id %s does not exist",
                         reply_to_conversation.test_attempt_session_id)
        raise serializers.ValidationError("invalid test_attempt_session_id")

    if not is_signature_bot:
        try:
            test = Test.objects.get(tenant_id=tenant.uid,
                                    uid=test_attempt_session.test_id, deleted=0)
        except Test.DoesNotExist as e:
            logger.exception("failed, id %s does not exist",
                            test_attempt_session.test_id)
            raise serializers.ValidationError("invalid test id")

        if test.interaction_mode == InteractionModeChoices.any:
            if participant_message_url:
                reply_to_conversation.participant_message_text = gpt_wishper_api(
                    participant_message_url
                )
                reply_to_conversation.save(
                update_fields=["participant_message_text", "updated"])

        if test.interaction_mode not in [InteractionModeChoices.any, InteractionModeChoices.text]:
            if not participant_message_url:
                raise serializers.ValidationError(
                    "participant_message_url is absent")

            if test.interaction_mode == InteractionModeChoices.audio:
                # reply_to_conversation.participant_message_text = coach_whisper_api.get_transcribe_from_audio(
                #     participant_message_url
                # )
                reply_to_conversation.participant_message_text = gpt_wishper_api(
                    participant_message_url
                )
            elif test.interaction_mode == InteractionModeChoices.video:
                # reply_to_conversation.participant_message_text = coach_whisper_api.get_transcribe_from_video(
                #     participant_message_url
                # )
                reply_to_conversation.participant_message_text = gpt_wishper_api(
                    participant_message_url
                )

            reply_to_conversation.save(
                update_fields=["participant_message_text", "updated"])

    #
    # test = Test.objects.get(
    #     tenant_id=tenant.uid,
    #     uid=test_attempt_session.test_id,
    #     deleted=0
    # )

    previous_conversations = CoachingConversation.objects.filter(
        tenant_id=tenant.uid,
        test_attempt_session_id=test_attempt_session.uid,
        deleted=0
    ).order_by(
        "id"
    ).values_list(
        "participant_message_text",
        flat=True
    )


    if is_signature_bot:
        
        current_conversation = CoachingConversation.objects.filter(deleted=0,tenant_id=tenant.uid,test_attempt_session_id=test_attempt_session.uid).count()
        signature_bot = SignatureBot.objects.get(tenant_id=tenant.uid, uid=test_attempt_session.test_id, deleted=0)
        save_bot_engagement(tenant_id=tenant.uid,bot_id=signature_bot.uid,user_id=test_attempt_session.participant_id,field_name="attempted_bot_questions")

        if current_conversation == 2 : # increasing action point if conversation contain two chat
            save_user_action_info(tenant.uid,test_attempt_session.participant_id,"chat_attempted")
            save_bot_engagement(tenant_id=tenant.uid,bot_id=signature_bot.uid,user_id=test_attempt_session.participant_id,field_name="num_of_bot_sessions")

        if current_conversation == 3 :
            if signature_bot.bot_type == BotTypeChoice.avatar_bot:
                save_user_action_info(tenant.uid,test_attempt_session.participant_id,"avatar_bot_count")
                save_user_action_info(tenant.uid,test_attempt_session.participant_id,"avatar_ids",bot_id=signature_bot.bot_id)
            elif signature_bot.bot_type in [BotTypeChoice.subject_matter_bot, BotTypeChoice.helper_bot]:
                save_user_action_info(tenant.uid,test_attempt_session.participant_id,"subject_matter_bot_count")
                save_user_action_info(tenant.uid,test_attempt_session.participant_id,"subject_matter_bot_ids",bot_id=signature_bot.bot_id)

        # prompt = f"""\nHuman: info: {signature_bot.data} based on this information answer this question : {participant_message_text}"""
        prompt = get_signature_bot_prompt(signature_bot.data, participant_message_text, signature_bot.bot_type, tenant, test_attempt_session.participant_id, signature_bot,test_attempt_session.uid)
        logger.info(f"signature  bot prompt  {prompt}")
        response = anthropic_completion(prompt,50000) if not is_prompt_only else ""
    else:
        question = TestQuestion.objects.get(
        tenant_id=tenant.uid, test_id=test_attempt_session.test_id, deleted=0)
        prompt = get_coaching_conversation_prompt(" ".join(previous_conversations), test, question)
        gpt_feedback = gpt3_completion(prompt, stop=["USER:", "CoachBot"])

        if not gpt_feedback.text:
            raise ValueError("unable to get feedback for %s",
                            reply_to_conversation.uid)

        coach_message_metadata = {
            "gpt": {
                "prompt": prompt,
                "response": {
                    "raw": gpt_feedback.raw,
                    "text": gpt_feedback.text,
                }
            },
            "prompt": prompt,
        }

    next_conversation = CoachingConversation.objects.create(
        tenant_id=tenant.uid,
        test_attempt_session_id=reply_to_conversation.test_attempt_session_id,
        coach_message_text=gpt_feedback.text if not is_signature_bot else response,
        coach_message_metadata=coach_message_metadata if not is_signature_bot else {"prompt": prompt}
    )

    return next_conversation





def get_signature_bot_prompt(page_info, candidate_data_str, bot_type, tenant, participant_id, signature_bot,test_attempt_session_id):
    """
    Generates a prompt for the Signature Bot based on the provided inputs.

    Args:
        page_info (str): Information about the page.
        candidate_data_str (str): Candidate data.
        bot_type (str): Type of bot ("coaching" or "generic").
        tenant (Tenant): Current tenant object.
        participant_id (str): Participant ID.
        signature_bot (SignatureBot): Signature bot object.

    Returns:
        str: Generated prompt for the Signature Bot.
    """
    old_coaching_prompt = f"""\n\nHuman:
    {{Information}} - {page_info}
    Context : {candidate_data_str}

    Read this {{information}} thoroughly and understand it deeply. The information contains all the information of a coach and their philosophies, ideas and guidelines. Act as the coach who works on these philosophies, ideas and guidelines. The information is just for your understanding do not refer to the information while giving the response. Provide the response in a first person tone.

    Conduct a session with a candidate who is asking a question here {{Context}}. Provide a response to the candidate based on the information given here {{information}}. Guide the candidate to reach an effective solution to their problem. 
    At the end ask a question to further understand the problem.

    NOTE: The response should not be more than 150 words.

    NOTE: The response should not be less than 50 words.

    NOTE: Do not show word count.(Eg: 50 words)

    NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output. Start directly with the response and only provide the response.

    \n\nAssistant:"""

    sessions = TestAttemptSession.objects.filter(deleted=0,tenant_id=tenant.uid,test_id=signature_bot.uid,participant_id=participant_id)
    conversation_data = get_bot_conversation_data_user(sessions,tenant,participant_id,only_converation=True)
    conversation_history = [{"coach": i['coach_message_text'], "user":i['participant_message_text']} for i in conversation_data]
    new_coaching_prompt = f""" 
        \n\nHuman:
        {{Information}} - {page_info}
        Conversation History : {conversation_history}
        Context : {candidate_data_str}

        Read this {{information}} thoroughly and understand it deeply. The information contains detailed insights into a coach's background, personality, philosophies, and coaching style. Act as the coach whose information is provided here and respond to the coachee. Additionally, offer general advice, coaching, and mentoring based on the coach's style. Consider any other relevant information to provide comprehensive coaching advice. Always provide the response in a first-person tone.

        Conduct a session with a coachee who is asking a question in this {{context}}. Understand the coachee's perspective to the question and provide the information they want. Provide a response based on all the information you have on the coach. Always provide accurate information about yourself as the coach when asked by the coachee. The response should always be directly related to the question. Consider the prior conversation given in Conversation History when providing the response.

        At the end ask a question to understand the problem.

        NOTE : The information is only about the coach not the coachee. 

        NOTE: The response should not be more than 150 words.

        NOTE: The response should not be less than 50 words.

        NOTE: Do not show word count.(Eg: 50 words)

        NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output. Start directly with the response and only provide the response.
        \n\nAssistant:"
    """


    generic_prompt = f"""\n\nHuman:
    {{Information}} - {page_info}
    Context : {candidate_data_str}
    Read this {{information}} thoroughly and understand it deeply. The user is seeking information on a specific topic, respond to the user with relevant details based on the available information. Provide comprehensive information and relevant details to address the user's query. The response should be directly related to the question asked. 
    The information contains all the details about the subject so answer based on that. The response should be detailed and specific based on the given information. The response should be informative, and tailored to the user's context.
    Only provide the response on the given information. Only provide the information that is directly related to the question in the response. 
    Do Not provide any additional information apart from what is given here. Do not provide unnecessary information in the response. 

    NOTE : Do not add any additional details to the response.
    NOTE: The response should not be more than 150 words.
    NOTE: Do not show word count.(Eg: 50 words)

    NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output. Start directly with the response and only provide the response.
    \n\nAssistant:"""


    prompt = new_coaching_prompt if bot_type == "avatar_bot" else generic_prompt 

    if signature_bot.custom_prompt:
        prompt = signature_bot.custom_prompt
        session = TestAttemptSession.objects.filter(tenant_id=tenant.uid,
                                                        uid=test_attempt_session_id,
                                                        deleted=0
                                                        )
        
        initial_que_ans = ""

        ## ========= removing precheck or intake from equation ==================

        # if bot_type in [BotTypeChoice.avatar_bot,BotTypeChoice.coachbots,BotTypeChoice.helper_bot]:
        #     initial_qna = None
        #     if bot_type == BotTypeChoice.avatar_bot:
        #         if session.first().intake_id:
        #             initial_qna = BotQnA.objects.filter(tenant_id = tenant.uid,bot_id=signature_bot.uid,qna_type='initial_qna',uid=session.first().intake_id).order_by('-created').first()
        #         else:
        #             initial_qna = BotQnA.objects.filter(tenant_id = tenant.uid,participant_id=participant_id,bot_id=signature_bot.uid,qna_type="initial_qna").order_by('-id').first()
        #     else:
        #         initial_qna = BotQnA.objects.filter(tenant_id = tenant.uid,participant_id=participant_id,bot_id=signature_bot.uid,qna_type="initial_qna").order_by('-id').first()

        #     if initial_qna:
        #         initial_que_ans = initial_qna.intake_summary
        
        logger.info(f"************************************************ initial_qna: {initial_que_ans}")
        # initial_que_ans = ''.join([f"Question: {que} Answer: {ans}" for que, ans in initial_qna])

        coach_info = ""
        for key,val in signature_bot.data.items():
            if val:
                coach_info += f"{key}: {val}\n"

        current_conv_data = get_bot_conversation_data_user(session,tenant,participant_id,only_converation=True)
        current_conv = [{"coach": i['coach_message_text'], "user":i['participant_message_text']} for i in current_conv_data]

            
        if bot_type == 'avatar_bot':
            
            qna_block = get_qna_block_for_coach_mentor(coach_user_id=signature_bot.user_id,participant_id=participant_id,tenant_id=tenant.uid)
            if qna_block:
                qna_block_text = ''
                for que, ans in qna_block.items():
                    qna_block_text += f"Question: {que} Answer: {ans}\n"

                coach_info += "\n" + "FAQs:" + '\n' + qna_block_text


            ## NOTE: removing session notes and idp from prompt and sending summary of conversation and precheck

            # user_recent_idp = None
            # latest_session = session.order_by('-created').first()
            # if latest_session.is_idp_discussion_opted:
            #     idp = UserIDP.objects.filter(tenant_id=tenant.uid, user_id=participant_id, deleted=0).order_by('-created_at').first()
            #     if idp:
            #         user_recent_idp = {
            #                 "strengths": idp.strengths,
            #                 "weakness": idp.weakness,
            #                 "opportunities": idp.opportunities,
            #                 "threats": idp.threats,
            #                 "key_focus_areas": idp.key_focus_areas,
            #                 "goals": idp.goals,
            #                 "priorities": idp.priorities,
            #                 "learning_histories": idp.learning_histories,
            #                 "key_skills": idp.key_skills,
            #                 "skill_gap_for_development": idp.skill_gap_for_development,
            #                 "leadership_skill_focus_area": idp.leadership_skill_focus_area,
            #                 "book_recommendations": idp.book_recommendations,
            #                 "course_recommendations": idp.course_recommendations,
            #                 "recommended_ted_talk": idp.recommended_ted_talk,
            #                 "recommended_scenarios": idp.recommended_scenarios,
            #             }
                
            
            ## getting related summary to initial_qna_summary and passing
            # rel_previous_conv_summary = session.first().related_previous_conversation_summary if session.first().related_previous_conversation_summary else ""
            rel_previous_conv_summary = ""
            for s in sessions:
                if s.conversation_summary:
                    rel_previous_conv_summary += f"\nPrevious conversation summary - {s.updated}:\n{s.conversation_summary}\n\n"

            logger.info(f"previous conversation summeries: {rel_previous_conv_summary}")
            try:
                personalities = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,user_id=participant_id).first()
                highest_charactersic_prompt = CharacteristicsAndPrompts.objects.filter(name = personalities.high_rating_characteristics)
                lowest_charactersic_prompt = CharacteristicsAndPrompts.objects.filter(name = personalities.low_rating_characteristics)
                low_char_prompt = ""
                for l in lowest_charactersic_prompt:
                    low_char_prompt += f"{l.negitive_prompt} "
                high_char_prompt = ""
                for l in highest_charactersic_prompt:
                    high_char_prompt += f"{l.positive_prompt} "
                personality = low_char_prompt + " " + high_char_prompt

            except Exception as e:
                logger.exception(f"got error: {e}")
                personality = None
            

            conv_history_data = ""
            # implementing v2 where we are passing previous conv summeries and current conversation without precheck/intake summery
            conv_history_data += f"{rel_previous_conv_summary}\n"
            conv_history_data += f"Current Conversation: \n {current_conv}\n"
            


            prompt = Template(prompt).substitute(
                coach_info = coach_info,
                conversation_history = conv_history_data,
                context = initial_que_ans,
                user_personality = personality if signature_bot.use_personality_context else None,
            )

        elif signature_bot.bot_type == BotTypeChoice.coachbots:
            personality = None
            if signature_bot.use_personality_context:
                try:
                    personalities = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,user_id=participant_id).first()
                    highest_charactersic_prompt = CharacteristicsAndPrompts.objects.filter(name = personalities.high_rating_characteristics)
                    lowest_charactersic_prompt = CharacteristicsAndPrompts.objects.filter(name = personalities.low_rating_characteristics)
                    low_char_prompt = ""
                    for l in lowest_charactersic_prompt:
                        low_char_prompt += f"{l.negitive_prompt} "
                    high_char_prompt = ""
                    for l in highest_charactersic_prompt:
                        high_char_prompt += f"{l.positive_prompt} "
                    personality = low_char_prompt + " " + high_char_prompt

                except Exception as e:
                    logger.exception(f"got error: {e}")
                    personality = None

            prompt = Template(prompt).safe_substitute(
                user_intake = initial_que_ans,
                user_context = current_conv,
                user_personality = personality
            )

        elif bot_type == 'helper_bot':
            try:
                personalities = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,user_id=participant_id).first()
                highest_charactersic_prompt = CharacteristicsAndPrompts.objects.filter(name = personalities.high_rating_characteristics)
                lowest_charactersic_prompt = CharacteristicsAndPrompts.objects.filter(name = personalities.low_rating_characteristics)
                low_char_prompt = ""
                for l in lowest_charactersic_prompt:
                    low_char_prompt += f"{l.negitive_prompt} "
                high_char_prompt = ""
                for l in highest_charactersic_prompt:
                    high_char_prompt += f"{l.positive_prompt} "
                personality = low_char_prompt + " " + high_char_prompt

            except Exception as e:
                logger.exception(f"got error: {e}")
                personality = None
            


            bot_att = BotAttribute.objects.get(bot_id = signature_bot.uid)
            faqs = bot_att.attached_faqs_context
            faqs_text = ""
            for que, ans in faqs.items():
                faqs_text += f"Question: {que} Answer: {ans}\n"

            if signature_bot.bot_type != 'subject_matter_bot':
                conversation = [f'Intake summary: {initial_que_ans}']
                conversation.extend(current_conv)

            # articles_contents = ""
            # if signature_bot.use_google_context:
            #     if 'article_links' in signature_bot.data:
            #         logger.info(f"###################################### signature_bot.data['article_links']: {signature_bot.data['article_links']}")
            #         for link in signature_bot.data['article_links'].split(","):
            #             contents = scrape_article_data(link).get('article_content',"\n")
            #             if contents:
            #                 articles_contents += contents


            idp_data = {}
            if signature_bot.use_idp:
                idp = UserIDP.objects.filter(deleted=False,tenant_id=tenant.uid,user_id=participant_id,success=True).order_by('-created').first()
                if idp:
                    idp_data = {
                        "strengths": idp.strengths,
                        "weakness": idp.weakness,
                        "opportunities": idp.opportunities,
                        "threats": idp.threats,
                        "key_focus_areas": idp.key_focus_areas,
                        "goals": idp.goals,
                        "priorities": idp.priorities,
                        "learning_histories": idp.learning_histories,
                        "key_skills": idp.key_skills,
                        "skill_gap_for_development": idp.skill_gap_for_development,
                        "leadership_skill_focus_area": idp.leadership_skill_focus_area,
                        "book_recommendations": idp.book_recommendations,
                        "course_recommendations": idp.course_recommendations,
                        "recommended_ted_talk": idp.recommended_ted_talk,
                        "recommended_scenarios": idp.recommended_scenarios,
                    }

            prompt = Template(prompt).substitute(
                            conversation_history = conversation,
                            user_personality =  personality if signature_bot.use_personality_context else None,
                            articles = coach_info + " General FAQs: " + faqs_text,
                            google_search =  get_searched_links_contents(candidate_data_str) if signature_bot.use_google_context else "" ,# TODO: Add functionality for extacting googlesearch result
                            idp_data = idp_data
                        )

            
        elif bot_type == 'subject_matter_bot':
            
            bot_att = BotAttribute.objects.get(bot_id = signature_bot.uid)
            faqs = bot_att.attached_faqs_context
            faqs_text = ""
            for que, ans in faqs.items():
                faqs_text += f"Question: {que} Answer: {ans}\n"

            # conversation = [{"coach": que, "user": ans} for que, ans in initial_que_ans.items()]
            # conversation.extend(current_conv)

            logger.info(f"####################33 use_google_context: {signature_bot.use_google_context}")

            # articles_contents = ""
            # if signature_bot.use_google_context:
            #     logger.info(f"###################################### signature_bot.data['article_links']: {signature_bot.data.get('article_links')}")
            #     for link in signature_bot.data['article_links'].split(","):
            #         contents = scrape_article_data(link).get('article_content',"\n")
            #         if contents:
            #             articles_contents += contents

            google_search_results = ""
            if signature_bot.use_google_context:
                google_search_results = get_searched_links_contents(candidate_data_str)
                logger.info(f"############################### google_search_results: {google_search_results}")
            
            prompt = Template(prompt).substitute(
                            conversation_history = current_conv,
                            articles = coach_info + " General FAQs: " + faqs_text,
                            google_search =  google_search_results # TODO: Add functionality for extacting googlesearch result
                        )


        else:
            prompt = Template(prompt).substitute(
                    info = page_info,
                    context_info = candidate_data_str
                    )
            

            
        logger.info(f"custom Prompt: {prompt}")
        
    else:
        session = TestAttemptSession.objects.filter(tenant_id=tenant.uid,
                                                        uid=test_attempt_session_id,
                                                        deleted=0
                                                        )
        
        initial_que_ans = ""
        # if bot_type in [BotTypeChoice.avatar_bot, BotTypeChoice.coachbots, BotTypeChoice.helper_bot]:
        #     initial_qna = None
        #     if session.first().intake_id:
        #         initial_qna = BotQnA.objects.filter(tenant_id = tenant.uid,bot_id=signature_bot.uid,qna_type='initial_qna',uid=session.intake_id).order_by('-created').first()
        #     else:
        #         initial_qna = BotQnA.objects.filter(tenant_id = tenant.uid,participant_id=participant_id,bot_id=signature_bot.uid,qna_type="initial_qna").order_by('-id').first()

        #     if initial_qna:
        #         initial_que_ans = initial_qna.participant_qna
        
        logger.info(f"************************************************ initial_qna: {initial_que_ans}")
        # initial_que_ans = ''.join([f"Question: {que} Answer: {ans}" for que, ans in initial_qna])


        coach_info = ""
        for key,val in signature_bot.data.items():
            if val:
                coach_info += f"{key}: {val}\n"

        current_conv_data = get_bot_conversation_data_user(session,tenant,participant_id,only_converation=True)
        current_conv = [{"coach": i['coach_message_text'], "user":i['participant_message_text']} for i in current_conv_data]

            
        if bot_type == 'avatar_bot':
            prompt = signature_bot_default_prompt()
            qna_block = get_qna_block_for_coach_mentor(coach_user_id=signature_bot.user_id,participant_id=participant_id,tenant_id=tenant.uid)
            if qna_block:
                qna_block_text = ''
                for que, ans in qna_block.items():
                    qna_block_text += f"Question: {que} Answer: {ans}\n"

                coach_info += "\n" + "FAQs:" + '\n' + qna_block_text
                
            # user_recent_idp = None
            # latest_session = session.order_by('-created').first()
            # logger.info(f"*************** latest_session  : {latest_session.uid}")
            # if latest_session.is_idp_discussion_opted:
            #     idp = UserIDP.objects.filter(tenant_id=tenant.uid, user_id=participant_id, deleted=0).order_by('-created').first()
            #     logger.info(f"*************** idp : {idp}")
            #     if idp:
            #         user_recent_idp = {
            #                 "strengths": idp.strengths,
            #                 "weakness": idp.weakness,
            #                 "opportunities": idp.opportunities,
            #                 "threats": idp.threats,
            #                 "key_focus_areas": idp.key_focus_areas,
            #                 "goals": idp.goals,
            #                 "priorities": idp.priorities,
            #                 "learning_histories": idp.learning_histories,
            #                 "key_skills": idp.key_skills,
            #                 "skill_gap_for_development": idp.skill_gap_for_development,
            #                 "leadership_skill_focus_area": idp.leadership_skill_focus_area,
            #                 "book_recommendations": idp.book_recommendations,
            #                 "course_recommendations": idp.course_recommendations,
            #                 "recommended_ted_talk": idp.recommended_ted_talk,
            #             }

            rel_previous_conv_summary = ""
            for s in sessions:
                if s.conversation_summary:
                    rel_previous_conv_summary += f"\nPrevious conversation summary - {s.updated}:\n{s.conversation_summary}\n\n"


            logger.info(f"previous conversation summeries: {rel_previous_conv_summary}")   

            conv_history_data = ""
            conv_history_data += f"{rel_previous_conv_summary}\n"
            conv_history_data += f"Current Conversation: \n {current_conv}\n"
            



            try:
                personalities = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,user_id=participant_id).first()
                highest_charactersic_prompt = CharacteristicsAndPrompts.objects.filter(name = personalities.high_rating_characteristics)
                lowest_charactersic_prompt = CharacteristicsAndPrompts.objects.filter(name = personalities.low_rating_characteristics)
                low_char_prompt = ""
                for l in lowest_charactersic_prompt:
                    low_char_prompt += f"{l.negitive_prompt} "
                high_char_prompt = ""
                for l in highest_charactersic_prompt:
                    high_char_prompt += f"{l.positive_prompt} "
                personality = low_char_prompt + " " + high_char_prompt

            except Exception as e:
                logger.exception(f"got error: {e}")
                personality = None
            

            prompt = Template(prompt).substitute(
                coach_info = coach_info,
                conversation_history = conv_history_data,
                context = initial_que_ans,
                user_personality = personality if signature_bot.use_personality_context else None,
            )

        elif signature_bot.bot_type == BotTypeChoice.user_bot:
            if signature_bot.faqs:
                coach_info += "\n FAQS: \n"
                try:
                    faq = json.loads(signature_bot.faqs)
                except:
                    faq = signature_bot.faqs

                for que, ans in faq.items():
                    coach_info += f"Question: {que}, Answer: {ans}\n"

            prompt = Template(signature_bot_default_prompt(bot_type=BotTypeChoice.user_bot)).safe_substitute(
                user_info = coach_info,
                user_context = current_conv
            )

    provide_answers_using_emojis = signature_bot.data.get('additional_data')
    if provide_answers_using_emojis:

        provide_answers_using_emojis = provide_answers_using_emojis.get('provide_answers_using_emojis')
        print(provide_answers_using_emojis,'provide_answers_using_emojis')
    else:
        provide_answers_using_emojis = False

    if provide_answers_using_emojis:

        prompt  = prompt.split('Assistant:')
        prompt.insert(-1, f"Note: Always use only Smileys and People emojis in response to make the responses lively where applicable. \n\nAssistant:")
        prompt = '\n'.join(prompt)

    return prompt



@timeit
def get_bot_conversation_data_user(sessions:TestAttemptSession,tenant:Tenant,user_id,only_converation=False):
    """
    Retrieves conversation data for a specific user in a test attempt session.

    Args:
        sessions (TestAttemptSession queryset): The test attempt sessions for a specific user.
        tenant (Tenant object): The current tenant object.
        user_id (str): The ID of the user.
        only_conversation (bool, optional): Flag to indicate if only conversation data should be returned. Defaults to False.

    Returns:
        list of dict or dict: If only_conversation is True, returns a list of dictionaries containing the conversation details. Otherwise, returns a dictionary containing the conversation data, participant name, participant ID, role, and date.
    """
    results=[]
    sessions = sessions.order_by('id')
    date=''
    for session in sessions:
        conversations = CoachingConversation.objects.filter(deleted=0,
            test_attempt_session_id=session.uid, tenant_id=tenant.uid).order_by("id")
        

        for conversation in conversations:
            if results and results[-1]['participant_message_text'] is None:
                results[-1]['participant_message_text'] = conversation.participant_message_text
            else:
                temp = {
                    "uid": conversation.uid,
                    "coach_message_text": conversation.coach_message_text,
                    "participant_message_text": conversation.participant_message_text,
                    "status": conversation.status,
                    "created": conversation.created,
                    "updated": conversation.updated,
                    "session_id": session.uid
                }

                results.append(temp)
        
        date = session.created

    if only_converation:
        return results
            
    participant_name = get_user_display_name(
            get_user_by_id(user_id))
    role = get_user_by_id(user_id).role

    data=({
        "results": results,
        "participant_name": participant_name,
        "participant_uid":user_id,
        "role": role,
        "date":date
    })
    return data



def signature_bot_default_prompt(bot_type=BotTypeChoice.avatar_bot):
    if bot_type == BotTypeChoice.avatar_bot:
        return """
        \n\nHuman:
        {Information} - ${coach_info}
        Conversation History : ${conversation_history}
        Context : ${context}
        Personality: ${user_personality}

        Read this {Information} thoroughly and understand it deeply. Act as the individual described in the provided information, mimicking their personality traits, speech patterns, and values throughout the responses. Understand the given instructions before creating a response. ALWAYS follow these instructions to generate the responses :
        1. Act as the person whose information is given here {Information}. Include details about their background, achievements, and notable personality traits.
        2. Analyze the personal stories, or responses given in {Information} to identify the person's speech patterns, vocabulary, and storytelling style. Utilize this information to generate conversational responses that reflect the user's natural language and tone.
        3. Analyze the "Speech Patterns" and vocabulary of the person from the given FAQs given here {Information} and model it when creating the response. Pay attention to their tone, expressions, and commonly used phrases to ensure authenticity.
        4. Use their "Values and Beliefs" given here {Information} to ensure that generated response aligns with their worldview and perspectives.
        5. Integrate their "Frequently Used Phrases" given here {Information} while generating the responses.  Weave these phrases seamlessly into the responses, ensuring they feel natural and consistent with the individual's communication style.
        6. Analyze the "Emotional Expressions" from the given FAQs  given here {Information} to mimic emotional nuances while generating the responses, ensuring that the response reflects the person's emotional range and communication style accurately.
        7. Analyze the "Life Experiences" given here {Information} . Draw on these experiences when crafting personalized narratives or offering advice, creating a deeper connection with the coachee and enhancing the realism of the responses.
        8. Analyze and imitate the "Problem-Solving Approach" given here {Information} to generate a response that reflects the person's decision-making style and problem-solving approach to resolve situations.
        Use all the information provided here {Information} to act as the coach and respond to the coachee. 

        Conduct a session with a coachee who is sharing their concern in this context {Context}. Understand the coachee's concern and problem before providing any advice or solution in the response. The response should be directly related to the concern shared by the coachee. If the personality of the coachee is given here {Personality}. Understand the coachee's personality and always tailor your response accordingly.
        Understand the coachee's perspective to the question and provide the information they want. 
        Select a suitable self reflection framework from the frameworks given in {Information} to guide the coachee towards self reflection according to his situation.
        Offer advice, coaching, and mentoring based on the coach's style and character traits given in {Information}. Consider any other relevant information to provide comprehensive coaching or mentoring advice. 
        Provide a response based on all the information you have on the coach. Always provide accurate information about yourself as the coach when asked by the coachee. 
        The response should always be directly related to the question. 
        Utilize the information provided in User Backstory to when relevant to create an Emotional Connection with the coachee and enhance the response.
        Consider the prior conversation given in Conversation History when providing the response.
        Offer actionable advice or solutions to the coachee’s potential challenges.
        Break down complex ideas into practical steps.
        Pose questions to the coachee to create engagement.
        Encourage self-reflection or thought-provoking moments.
        Maintain a tone that feels friendly and approachable.
        Use the Custom Knowledge base here {Information}. Always refer to {Information} first, before providing a response. 
        Never provide any answer about a subject the coach is not familiar with. If the user asks any questions about a subject that is not mentioned in  {Information} as Areas of expertise, please respond that you are not familiar with the topic.
        Utilize the frameworks shared in the {Information} to provide guidance or solution to the coachee. Only use the frameworks when it is directly related to the coachee’s solution.
        Use the context of case studies in the {Information} when relatable and provide it as a reference.

        Always provide the response in a first-person tone.
        Always ask a contextual question at the end to further understand the details.
        Always respond as the coach.
        Always consider drawing from  personal coach stories/scenario.
        NEVER give visual cues like smiles warmly etc.

        Add this line during the conversation wherever it's most suitable, "You can visit the coachbots library to practice these." Please integrate this in the natural flow of the response and conversation. You can change the text according to the situation to make it more contextual and customized for the conversation. ONLY add these lines when it's suitable in the response.
        It doesn't need to be in every response, only give them wherever it makes sense. 
        Always respond in less than 50 tokens. Never mention the token count.

        NOTE : Always priorities creating human connect in the response style.
        NOTE: Develop Context, Action and Results as personal stories.
        NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output. Start directly with the response and only provide the response.
        NOTE : Always assume suitable details to respond, never respond with unfortunately I can't provide an answer to that question.

        NOTE: Make sure to keep the response short. Get straight to the point without unnecessary elaboration or repetition. Eliminate redundant phrases or ideas that don't add value to the response. Choose words and phrases that convey your message clearly and directly. Make sure to give short answers but do not miss out any necessary information.

        NOTE: Provide concise responses without exceeding a brief length constraint. Aim for brevity while delivering complete information and answers.

        NOTE: Always respond in less than 50 tokens. Never mention the token count.

        \n\nAssistant:


        """
    elif bot_type == BotTypeChoice.user_bot:
        return """
        \n\nHuman:
        {Information}: ${user_info}
        User Context : ${user_context}

        Read this {Information} thoroughly and understand it thoroughly. Understand all the information given in User Context and give the response accordingly. 
        Provide an informative response to the candidate based on their concern. 
        Break down and clearly explain complex concepts in the given field.
        If the FAQs are provided use the answers given to address the commonly asked questions. 
        Always respond in less than 50 tokens. Never mention the token count.

        NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output. Start directly with the response and only provide the response.
        NOTE: If the given User Context is irrelevant to the User Situation please just respond with "I am specifically trained for the subject matter described as defined in my page. Unfortunately I can not answer this question."
        NOTE: Always respond in less than 50 tokens. Never mention the token count.
        """


@timeit
def get_or_create_bot_user_mapping(bot: SignatureBot, user: User):
    """
    Create or retrieve a mapping between a bot and a user.

    Args:
        bot (SignatureBot): The bot object.
        user (User): The user object.

    Returns:
        BotAndUserMapping: The created or retrieved BotAndUserMapping object representing the mapping between the bot and the user.
    """
    bot_user = get_user_by_id(bot.user_id)
    logger.info(f"user_id: {user.uid}")
    user_profile = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,user_id=user.uid)
    logger.info(f"bot_user_Id: {bot.user_id}")
    bot_user_profile = CoachCoacheeMentorMenteeProfile.objects.get(deleted=False,user_id=bot.user_id)
    bot_email = bot_user_profile.email or get_user_attribute(bot_user, "deepchat_profile").attributes.get("email", None)
    bot_user_name = bot_user_profile.name or bot_user.name
    bot_user_mob_no = bot_user_profile.mob_number

    user_email = get_user_attribute(user, "deepchat_profile").attributes.get("email", None)
    user_name = user.name
    user_mob_no = None
    if user_profile.count() > 0:
        user_profile = user_profile.first()
        user_mob_no = user_profile.mob_number

    bot_user_mapping, is_created = BotAndUserMapping.objects.get_or_create(
        tenant_id=user.tenant_id,
        bot_id=bot.uid,
        participant_id=user.uid,
    )
    bot_user_mapping.bot_owner_name = bot_user_name
    bot_user_mapping.bot_owner_email = bot_email
    bot_user_mapping.bot_owner_mob_number = bot_user_mob_no
    bot_user_mapping.user_mob_number = user_mob_no
    bot_user_mapping.user_name = user_name
    bot_user_mapping.user_email = user_email

    bot_user_mapping.save()

    return bot_user_mapping


def get_latest_session_notes_coach_coachee(coach_user_id,coachee_user_id,tenant_id):
    
    session_notes = SessionNotesRecommendations.objects.filter(tenant_id=tenant_id,mentor_id=coach_user_id,mentee_id=coachee_user_id).order_by('-created_date')

    if session_notes:
        session_note = session_notes.first()
        return session_note.session_notes
    else:
        return None


def get_qna_block_for_coach_mentor(coach_user_id,participant_id,tenant_id):
    try:
        participant_profile = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,tenant_id=tenant_id,user_id=participant_id).first()
        coach_profile = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,tenant_id=tenant_id,user_id=coach_user_id).first()
        result = None
        coach_mentor_qna = coach_profile.qna_for_coach_mentor
        if coach_mentor_qna:
            if participant_profile.profile_type == ProfileTypeChoice.coachee:
                result = coach_mentor_qna.get('coach',None)
            elif participant_profile.profile_type == ProfileTypeChoice.mentee:
                result = coach_mentor_qna.get('mentor',None)

        return result
                
        

    except Exception as e:
        logger.exception(f"Got Error while fetching qna block from coach or mentor : {e}")
        return None


def create_user_profile_and_bot(data,auth):
    from settings import BACKEND
    import traceback

    
    name = data.get('name',None)
    if not name :
        name = data.get('first name') + ' ' + data.get('last name')


    name = remove_punctuations(name)
        
    email = data.get('email')
    about = data.get('about')
    experience = data.get('experience')
    area_domain = data.get('area_domain')
    department = data.get('department')
    profile_type = data.get('profile_type')
    client_name = data.get('Client Name'.lower().strip(),None)
    mentoring_preferences = data.get('which way do you want to help the program participants the most?'.strip().lower(),None)
    mentoring_frameworks = data.get('please mention any coaching & mentoring frameworks or tools that you use in your approach.'.strip().lower(),None)
    high_rating_characteristics = data.get('please rate the characteristics/skills on which you will rate yourself highly.'.strip().lower(),None)
    low_rating_characteristics = data.get('please rate the characteristics/skills on which you will rate yourself near the lows.'.strip().lower(),None)
    common_phrases_and_expressions = data.get('are there any phrases or expressions you find yourself using often in conversations? These could be catchphrases, favorite quotes, or unique sayings that reflect your personality.'.strip().lower(),None)
    significant_challenges_and_solutions = data.get('what were the 3 most significant challenges you encountered in your journey, and how did you successfully navigate and overcome them?'.strip().lower(),None)
    coaching_for_fitment = data.get('coaching_for_fitment',None)
    profile_image_url = data.get('profile image url'.strip().lower(),None)
    admired_leaders = data.get('please add names of 1-2 well-known leaders that you admire.'.strip().lower(),None)
    problem_solving_approach = data.get('what is your general approach towards problem solving?'.strip().lower(),None)
    dominant_point_of_view = data.get('please articulate your dominant point of view which you want to discuss with the program participants as a general starting point.'.strip().lower(),None)
    youtube_links = data.get('Please enter 1-2 YouTube links that reflect your worldview on personal & professional development.'.strip().lower(),None)
    article_links = data.get('Please enter 1-2 article links that reflect what you wished everyone would follow in their growth journey.'.strip().lower(),None)
    coaching_level = data.get('What level of participant you want to interact with?'.strip().lower(),None)
    supported_outcome = data.get('what kind of outcome can you support in these sessions the most?'.strip().lower(),None)
    allow_coachee_to_create_session = data.get('Allow coaches and mentors to create their own action plans?'.strip().lower(),None)
    coach_same_department = data.get('I want to coach & mentor someone in the same department.'.strip().lower(),None)
    discuss_how_you_helped_others_in_coachMentoring = data.get('Please discuss how you have helped others as a coach/mentor or in other professional capacity. Please mentions these personal transformation stories in CAR format - Context, Action and Result achieved.'.strip().lower(),None)
    provide_answers_using_emojis = data.get('Would you like your AI Avatar to provide expressive answers using emojis?'.strip().lower(),None)
    journey_and_background = data.get("Backstory".lower().strip(),None)
    voice_sample = data.get('Do you want to provide a voice sample, if you want an audio avatar?'.strip().lower(),None)




    if not client_name:
        return False, {"email": email,'user_id':"",'error': f"Client name is required"}
    
    provided_links = {}
    if youtube_links:
        provided_links['youtube_links'] = youtube_links
    if article_links:
        provided_links['article_links'] = article_links

    coach_same_department = coach_same_department.lower() == "yes" if coach_same_department else False
    allow_coachee_to_create_session = allow_coachee_to_create_session.lower() == "yes" if allow_coachee_to_create_session else False
    voice_sample = voice_sample.lower() == "yes" if voice_sample else False

    coach_questions = [
        "As a coach, what foundational values do you believe individuals should prioritize and strive for in their personal and professional development journey?",
        "In your role as a coach, what kind of developmental framework do you employ, and why do you consider it to be the optimal framework for facilitating personal growth ?",
        "Can you provide an overview of your coaching process and what I can expect from our sessions?",
        "How do you handle situations where I feel stuck or unsure about my next steps?",
        "How can I integrate the lessons from these sessions into my daily life?",
        "Can you provide guidance on how to effectively balance personal and professional goals during our coaching process?"
            
        ]
    
    mentor_questions = [
        "As a mentor, what do you think are the different career paths available in this field? What are the core skills and understanding required to continuously grow in this field?",
        "What is the problem solving approach in your domain and why do you think that is the right construct for growing in this field?",
        "Can you provide an overview of your mentoring approach and what I can expect from our sessions?",
        "What opportunities for growth or advancement do you see in this field, and how can I position myself to capitalize on them?",
        "What are some common challenges or obstacles that individuals face when pursuing success in this field, and what strategies do you suggest for overcoming them?",
        "In your opinion, what are the key qualities or skills that contribute to success in the field I'm aiming to excel in, and how can I develop or enhance them?"
    ]

    qna_for_coach = {que : data.get(que.strip().lower()) for que in coach_questions if data.get(que.strip().lower())}

    qna_for_mentor = {que : data.get(que.strip().lower()) for que in mentor_questions if data.get(que.strip().lower())}

    qna_for_coach_mentor = {}
    if qna_for_coach:
        qna_for_coach_mentor['coach'] = qna_for_coach
    if qna_for_mentor:
        qna_for_coach_mentor['mentor'] = qna_for_mentor

    is_send_email = data.get('is_send_email',None)
    user_email = email
    if is_send_email and len(is_send_email)>0:
        if is_send_email == 'true':
            is_send_email = True
        elif is_send_email == 'false':
            is_send_email = False
        else:
            is_send_email = False
    
    if is_send_email != None and is_send_email == False:
        user_email = 'coachbots@googlegroups.com'
    else:
        if profile_type == 'icons_by_ai':
            user_email = ''



    # creating user

    url = f"{BACKEND}/api/v1/accounts/"
    tenant_id = ""
    payload = json.dumps({
    "user_context": {
        "name": name,
        "role": "member",
        "password": "Demo#123",
        "user_attributes": {
        "tag": "deepchat_profile",
        "attributes": {
            "name": name,
            "email": user_email
        }
        }
    },
    "identity_context": {
        "identity_type": "deepchat_unique_id",
        "value": email
    }
    })
    headers = {
    'Authorization': auth,
    'Content-Type': 'application/json'
    }

    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        response.raise_for_status()
        user = response.json()
        tenant_id = get_user_by_id(user.get('uid')).tenant_id
        logger.info(f"user: {user}, tenant_id: {tenant_id}")

    except Exception as e:
        logger.exception(f"user creation failed with error: {e}")
        return False, {"email": data.get('email'),'error': f"{e}: {traceback.format_exception()}"}

    user_id = user.get('uid')

    required_profile_list = ["coach-mentor", "coach",'mentor' ,'icons_by_ai']
    form_data = {
        "name": name,
        "user_id": user_id,
        "email": email,
        "about": about,
        "experience": experience,
        "profile_image_url": profile_image_url or "https://res.cloudinary.com/dtbl4jg02/image/upload/v1710139318/mdzmknenvvv4llgevykz.png",
        "department": department,
        "supported_outcome": supported_outcome,
        "coaching_for_fitment": coaching_for_fitment,
        "coaching_level": coaching_level,
        "coach_same_department":  coach_same_department,
        "profile_type": "coach" if profile_type in ["coach-mentor", "coach"] else "mentor" if profile_type == "mentor" else profile_type,
        "is_mentor": str(profile_type == "coach-mentor") if profile_type in ["coach-mentor", "coach"] else "False",
        "area_domain": area_domain if profile_type in required_profile_list else None,
        "mentoring_preferences": mentoring_preferences if profile_type in required_profile_list else None,
        "mentoring_frameworks": mentoring_frameworks if profile_type in required_profile_list else None,
        "dominant_point_of_view": dominant_point_of_view if profile_type in required_profile_list else None,
        "problem_solving_approach": problem_solving_approach if profile_type in required_profile_list else None,
        "provided_links": provided_links if profile_type in required_profile_list else None,
        "admired_leaders": admired_leaders if profile_type in required_profile_list else None,
        "allow_coachee_to_create_session": allow_coachee_to_create_session if profile_type in required_profile_list else None,
        "significant_challenges_and_solutions": significant_challenges_and_solutions if profile_type in required_profile_list else None,
        "common_phrases_and_expressions": common_phrases_and_expressions if profile_type in required_profile_list else None,
        "qna_for_coach_mentor" : qna_for_coach_mentor if qna_for_coach_mentor else None,
        "low_rating_characteristics": low_rating_characteristics if profile_type in ["coachee",'mentee'] else None,
        "high_rating_characteristics": high_rating_characteristics if profile_type in ["coachee",'mentee'] else None,
        'is_approved': True,
        "journey_and_background": journey_and_background,
        "voice_sample": voice_sample,
        "mentorship_contribution": discuss_how_you_helped_others_in_coachMentoring

    }

    url = f"{BACKEND}/api/v1/accounts/coach-coachee-mentor-mentee-profile/"

    payload = json.dumps(form_data)
    headers = {
    'Content-Type': 'application/json',
    'Authorization': auth
    }

    try:
        profile = requests.request("POST", url, headers=headers, data=payload)

        logger.info(f"profile_created: {profile.json()}")
        try:
            profile = profile.json()['data'][0]
        except: 
            profile = profile.json()['data']

    except Exception as e:
        logger.exception(f"profile creation failed with {e}")
        return False, {"email": data.get('email'),'user_id':user.get('uid'),'error': f"{e}: {traceback.format_exception()}"}

    if (coaching_level != None and coach_same_department != None and supported_outcome != None):
        qna_data = {
            "1": {
                "coach": "What level of coach/mentor do you want to interact with ?",
                "cochee": coaching_level
            },
            "2": {
                "coach": "I want a coach & mentor someone from the same department.",
                "cochee": coach_same_department
            },
            "3": {
                "coach": "What kind of outcome do you want from these sessions the most?",
                "cochee": supported_outcome
            }
        }


        intake_summary_prompt = get_intake_summary_prompt(qna_data)
        intake_summary = anthropic_completion(intake_summary_prompt,50000)
        # intake_summary = ""

        BotQnA.objects.create(
                        tenant_id = tenant_id,
                        participant_id = user.get('uid'),
                        participant_qna = qna_data,
                        is_positive = False,
                        bot_id = None,
                        qna_type = 'fitment',
                        intake_summary = intake_summary,
                        is_anonymous = False
                    )
        
    ## creating bot


    if profile_type in ['mentor','coach',"icons_by_ai",'coach-mentor']:
        media_data = {}
        if youtube_links:
            media_data['youtube_links'] = youtube_links
        if article_links:
            media_data['article_links'] = article_links
        url = f"{BACKEND}/api/v1/accounts/create-bot-by-details/"

        headers = {
            "Authorization": auth,
            "Content-Type": "application/json",
        }
        same_department = 'Yes' if coach_same_department else 'No'
        avatar_bot_creation_form_data = {
            "bot_type": 'avatar_bot',
            "profile_id": profile.get('uid'),
            "bot_name": name,
            "email": data.get('email'),
            "bot_details": {"info": data.get('about'), "coach_name": name},
            "attributes": {"heading": f"welcome to {name}'s avatar bot"},
            "participant_id": user.get('uid'),
            "bot_base_url": "https://playground.coachbots.com",
            "fitment_answer": f"{coaching_level},{same_department},{supported_outcome}",
            "fitment_data": {
                "options": {
                    "1": ["Someone Senior", "Any level"],
                    "2": ["Yes", "No"],
                    "3": [
                        "Career advancement",
                        "Skill development",
                        "Introspection & reflection",
                        "Networking & leadership",
                    ],
                },
                "mentee_que": {
                    "1": "What level of coach & mentor do you want?",
                    "2": "I want a coach & mentor someone from the same department.",
                    "3": "What kind of outcome do you want from these sessions the most?",
                },
                "mentor_que": {
                    "1": "What level of participant do you want to coach & mentor?",
                    "2": "I want to coach & mentor someone in the same department.",
                    "3": "What kind of outcome can you support in these sessions the most?",
                },
            },
            "additional_data": {
                "profile_type": profile_type,
                "area_domain": area_domain,
                "experience": experience,
                "mentoring_preferences": mentoring_preferences,
                "mentoring_frameworks": mentoring_frameworks,
                "dominant_point_of_view": dominant_point_of_view,
                "problem_solving_approach": problem_solving_approach,
                "admired_leaders": admired_leaders,
                "profile_description": about,
                "department": department,
                "youtube_links": youtube_links,
                "article_links": article_links,
                "voice_sample": voice_sample,
                "discuss_how_you_helped_others_in_coachMentoring": discuss_how_you_helped_others_in_coachMentoring,
                "provide_answers_using_emojis": provide_answers_using_emojis.lower() == 'yes' if provide_answers_using_emojis else False,
                "allow_coachee_to_create_session": allow_coachee_to_create_session,
                "significant_challenges_and_solutions": significant_challenges_and_solutions ,
                "common_phrases_and_expressions": common_phrases_and_expressions,
                "journey_and_background": journey_and_background,
                "fitment_answers": [
                      coaching_level,
                      coach_same_department,
                      supported_outcome,
                ],
                "coach_qna": qna_for_coach,
                "mentor_qna": qna_for_mentor
            },
            "media_data": media_data,
            'is_approved': True,
            'bot_scenario_case': profile.get('profile_type') if profile.get('profile_type') == 'icons_by_ai' else 'general'
        }

        try:
            response = requests.request(
                'POST',
                url,
                headers=headers,
                data=json.dumps( avatar_bot_creation_form_data),
            )
            logger.info(f"bot_created: {response.json()}")
            response.raise_for_status()
            response = response.json()
            data_json = {'bot_id': response.get('bot_uid'),"media_data": media_data,}
            resp = requests.request(
                'PATCH',
                url,
                headers=headers,
                data=json.dumps(data_json),
            )

            print(resp.json())

            # saving in clientuser info
            error = ''
            try:
                if client_name:
                    client = ClientUserInfo.objects.get(deleted=False, tenant_id=tenant_id, client_name = client_name.strip())

                    if profile.get('profile_type') == 'icons_by_ai':
                        unique_bot_ids = set(client.accessed_bot_ids.strip().split(',') if client.accessed_bot_ids else [])
                        unique_bot_ids.add(response.get('bot_id'))
                        client.accessed_bot_ids = ','.join(unique_bot_ids)
                        client.save(update_fields=['accessed_bot_ids'])
                    else:
                        unique_email_ids = set(client.member_emails.strip().split(',') if client.member_emails else [])
                        unique_email_ids.add(email)
                        client.member_emails = ','.join(unique_email_ids)
                        client.save(update_fields=['member_emails'])

            except Exception as e:
                logger.exception(f"saving client_info failed with error {e}")
                error = e



            return True, {"email": email,'user_id':user.get('uid'),'profile_id': profile.get('uid'),"bot_id": response.get('bot_id'),'error': f"{error}"}
        except Exception as e:
            logger.exception(f"bot creation failed with error {e}")
            return False, {"email": email,'user_id':user.get('uid'),'profile_id': profile.get('uid'),'error': f"{e}"}
        
    else:
        error=""
        try:
            if client_name:
                client = ClientUserInfo.objects.get(deleted=False, tenant_id=tenant_id, client_name = client_name.strip())

                if profile.get('profile_type') == 'icons_by_ai':
                        unique_bot_ids = set(client.accessed_bot_ids.strip().split(',') if client.accessed_bot_ids else [])
                        unique_bot_ids.add(response.get('bot_id'))
                        client.accessed_bot_ids = ','.join(unique_bot_ids)
                        client.save(update_fields=['accessed_bot_ids'])
                else:
                    unique_email_ids = set(client.member_emails.strip().split(',') if client.member_emails else [])
                    unique_email_ids.add(email)
                    client.member_emails = ','.join(unique_email_ids)
                    client.save(update_fields=['member_emails'])

        except Exception as e:
            logger.exception(f"saving client_info failed with error {e}")
            error = e

        return True, {"email": email,'user_id':user.get('uid'),'profile_id': profile.get('uid'),'error': f"{error}"}

def update_or_revert_avatar_bot_doc_summeries(tenant_id='62d76be2-b439-4528-9ae4-2af389abb5f5',revert=False):

    avatar_bots = SignatureBot.objects.filter(deleted=False,tenant_id=tenant_id,bot_type=BotTypeChoice.avatar_bot)
    # avatar_bots = SignatureBot.objects.filter(deleted=False, bot_id='avatar_bot-03e4b-lyfe-gemini-summary-testing2')

    if revert:
        for avatar_bot in avatar_bots:
            bot_att = BotAttribute.objects.get(deleted=False,bot_id=avatar_bot.uid)
            extracted_document = bot_att.extracted_documents
            media_data = {}
            if extracted_document.get('extracted_from_youtube',None):
                media_data['extracted_from_youtube'] = extracted_document.get('extracted_from_youtube',None) 
            if extracted_document.get('extracted_from_article',None):
                media_data['extracted_from_article'] = extracted_document.get('extracted_from_article',None) 
            if extracted_document.get('extracted_from_pdf',None):
                media_data['extracted_from_pdf'] = extracted_document.get('extracted_from_pdf',None) 
            if extracted_document.get('extracted_from_doc',None):
                media_data['extracted_from_doc'] = extracted_document.get('extracted_from_doc',None) 

            print('media_data_full', media_data)
            print('media_data_summary : ',extracted_document)
            if media_data:
                avatar_bot.data['media_data'] = media_data
                avatar_bot.save(update_fields=['data'])

                bot_att.extracted_documents = None
                bot_att.save(update_fields=['extracted_documents'])

        return "Document summaries reverted successfully"

    else:
        for avatar_bot in avatar_bots:
            media_data = avatar_bot.data.get('media_data')
            print('bot_id', avatar_bot.bot_id)
            print('media_data', media_data)
            if media_data:
                try:
                    bot_att = BotAttribute.objects.get(deleted=False,bot_id=avatar_bot.uid)
                    print('bot_att.extracted_documents', bot_att.extracted_documents)
                    if not bot_att.extracted_documents:
                        bot_att.extracted_documents = media_data
                        bot_att.save(update_fields=['extracted_documents'])

                        summaries = {}

                        for source, links in media_data.items():
                            summaries_temp = {}
                            for link, value in links.items():
                                summaries_temp[link] = get_document_summary(value)

                            summaries[source] = summaries_temp

                        
                        avatar_bot.data['media_data'] = summaries
                        avatar_bot.save(update_fields=['data'])
                except Exception as e:
                    print(e)


        return "Summeries updated successfully!"

def get_client_user_data(tenant):
    """
    Retrieves detailed user information for each client associated with a given tenant.

    This function filters through all clients linked to a specific tenant that have not been marked as deleted. For each client, it gathers the emails of its members, retrieves their corresponding user IDs from the Identity model, and fetches user attributes and additional client-specific information using these IDs. The function compiles a dictionary containing detailed user information, including user-specific and client-specific attributes, for each client under the given tenant.

    Parameters:
    - tenant (Tenant): An instance of the Tenant model. This object must have a valid 'uid' attribute that corresponds to the tenant ID.

    Returns:
    - dict: A dictionary where each key is a client name and each value is a list of dictionaries. Each dictionary in the list contains comprehensive user information, including user ID, name, client ID, and other attributes specific to the client and user.

    Example:
    ```python
    tenant_instance = Tenant(uid='12345')
    user_data = get_client_user_data(tenant_instance)
    print(user_data)
    # Output:
    # {
    #   'ClientXYZ': [
    #       {
    #           'user_id': 'user123',
    #           'name': 'John Doe',
    #           'client_id': 'client789',
    #           'client_name': 'ClientXYZ',
    #           'avatar_bot_creation': False,
    #           'feedback_bot_creation': True,
    #           ... (additional user and client-specific information)
    #       },
    #       ... (more user dictionaries)
    #   ],
    #   ... (more clients)
    # }
    ```
    """
    # Function implementation continues here...
    # get the client user associated with a Client Id
    clients = ClientUserInfo.objects.filter(deleted=False,tenant_id=tenant.uid)
    client_user_data = {}

    for client in clients:
        client_data = []
        member_emails = [email.strip() for email in client.member_emails.split(',') if len(email.strip())>0] if client.member_emails else []
        user_ids = list(Identity.objects.filter(
            deleted=False,
            tenant_id=tenant.uid,
            value__in=member_emails
        ).values_list('user_id', flat=True))
        for user_id in user_ids:
            user = User.objects.get(deleted=False,tenant_id=tenant.uid,uid=user_id)
            user_att = UserAttribute.objects.get(user_id=user_id).attributes
            email = user_att.get('email',None) if user_att else None

            user_info = get_client_user_info(client,email)
            user_info['user_id'] = user_id
            user_info['name'] = user.name
            user_info['client_id'] = client.uid

            client_data.append(user_info)

        client_user_data[client.client_name] = client_data

    return client_user_data


def update_client_id(tenant, old_client_id, new_client_id, user_email):
    """
    Updates the membership of a user identified by their email across client records within a specific tenant.
    This function removes the user's email from an old client's member list and adds it to a new client's member list.

    Parameters:
    - tenant (Tenant): The tenant object representing the current tenant context.
    - old_client_id (str): The unique identifier of the old client from which the user's email will be removed. If None, the email will be removed from all clients where it appears.
    - new_client_id (str): The unique identifier of the new client to which the user's email will be added.
    - user_email (str): The email address of the user to be updated.

    Process:
    - If an old_client_id is provided:
        1. Fetch the old client based on the tenant and old_client_id.
        2. Remove the user_email from the old client's member_emails list.
        3. Save the updated list back to the database.
    - If no old_client_id is provided:
        1. Fetch all clients associated with the tenant that contain the user_email in their member_emails.
        2. Remove the user_email from each of these clients' member_emails list.
        3. Save the updated lists back to the database.
    - For the new client:
        1. Fetch the new client based on the tenant and new_client_id.
        2. Add the user_email to the new client's member_emails list ensuring no duplicates.
        3. Save the updated list back to the database.

    Returns:
    None

    Example:
    >>> tenant = Tenant(uid="12345")
    >>> update_client_id(tenant, "old_client123", "new_client456", "user@example.com")
    This will remove "user@example.com" from "old_client123" and add it to "new_client456" within the tenant "12345".
    """
    # Function implementation follows

    logger.info(f"==================================================data: tenant: {tenant},old_client_id: {old_client_id},new_client_id: {new_client_id},user_email: {user_email}============================")
    
    if old_client_id:
        old_client = ClientUserInfo.objects.get(deleted=False,tenant_id=tenant.uid,uid=old_client_id)
        # remove user_email from old client

        emails_list = [email.strip() for email in old_client.member_emails.split(',') if len(email.strip()) > 0] if old_client.member_emails else []  # Split the string into a list of emails
        emails_list = [email for email in emails_list if email != user_email]  # Remove the specified email
        old_client.member_emails = ",".join(set(emails_list))
        old_client.save(update_fields=['member_emails'])

    else:
        all_client_of_user = ClientUserInfo.objects.filter(deleted=False,tenant_id=tenant.uid,member_emails__contains=user_email)
        for client in all_client_of_user:
            emails_list = [email.strip() for email in client.member_emails.split(',') if len(email.strip()) > 0] if client.member_emails else []  # Split the string into a list of emails
            emails_list = [email for email in emails_list if email != user_email]  # Remove the specified email
            client.member_emails = ",".join(set(emails_list))
            client.save(update_fields=['member_emails'])

            
    # add user_email to new_client
    new_client = ClientUserInfo.objects.get(deleted=False,tenant_id=tenant.uid,uid=new_client_id)
    unique_emails = set([email for email in new_client.member_emails.split(",") if len(email.strip()) > 0] if new_client.member_emails else [])
    unique_emails.add(user_email)
    new_client.member_emails = ",".join(unique_emails)
    new_client.save(update_fields=['member_emails'])


def disable_or_enable_client(email,is_disable,tenant):
    client = ClientUserInfo.objects.filter(deleted=False,tenant_id=tenant.uid,member_emails__contains=email).first()
    if client:
        if is_disable:
            unique_emails = set([email for email in client.restricted_ids.split(",") if len(email.strip()) > 0] if client.restricted_ids else [])
            unique_emails.add(email)
            client.restricted_ids = ",".join(unique_emails)
            client.save(update_fields=['restricted_ids'])
        else:
            emails_list = [email.strip() for email in client.restricted_ids.split(',') if len(email.strip()) > 0] if client.restricted_ids else []  # Split the string into a list of emails
            emails_list = [email for email in emails_list if email != email]  # Remove the specified email
            client.restricted_ids = ",".join(set(emails_list))
            client.save(update_fields=['restricted_ids'])
        

def get_client_user_info(client, email):
    """
    Retrieves comprehensive user information based on client settings and user email, 
    including restrictions and demo user status.

    This function checks if the provided email is in the client's restricted or demo lists.
    If the email is found in the demo list, it further checks if the demo period (2 weeks from account creation) 
    has expired, which may change the user's restricted status and demo user flag. It then compiles a dictionary 
    of user information including client-specific settings and user status.

    Parameters:
    - client (Client object): The client object containing attributes like restricted_ids, demo_ids, 
      client_name, avatar_bot_creation, feedback_bot_creation, subject_matter_bot_creation, 
      number_of_conversation_per_month, required_form_fields, accessed_bot_ids, coach_skills, 
      coach_expertise, departments, restricted_pages, and restricted_features.
    - email (str): The email address of the user to check against client's restricted and demo lists.

    Returns:
    - dict: A dictionary containing various pieces of user information such as:
        - client_name: Name of the client
        - avatar_bot_creation: Information about avatar bot creation settings
        - feedback_bot_creation: Information about feedback bot creation settings
        - subject_matter_bot_creation: Information about subject matter bot creation settings
        - monthly_conversation_limit: Monthly conversation limit for the user
        - required_form_details: Form details required from the user, processed into a structured format
        - is_restricted: Boolean indicating if the user is restricted
        - is_demo_user: Boolean indicating if the user is a demo user
        - accessed_bot_ids: IDs of bots the user has access to
        - coach_skills: Skills of the coach associated with the client
        - coach_expertise: Expertise areas of the coach associated with the client
        - departments: Departments within the client organization
        - restricted_pages: Pages the user is restricted from accessing
        - restricted_features: Features the user is restricted from using
        - user_email: The email of the user

    Example:
    >>> client = Client(client_name="ExampleCorp", restricted_ids="user@example.com", demo_ids="demo@example.com")
    >>> email = "demo@example.com"
    >>> get_client_user_info(client, email)
    {
        'client_name': 'ExampleCorp',
        'avatar_bot_creation': None,
        'feedback_bot_creation': None,
        'subject_matter_bot_creation': None,
        'monthly_conversation_limit': None,
        'required_form_details': None,
        'is_restricted': False,
        'is_demo_user': True,
        'accessed_bot_ids': None,
        'coach_skills': None,
        'coach_expertise': None,
        'departments': None,
        'restricted_pages': None,
        'restricted_features': None,
        'user_email': 'demo@example.com'
    }
    """
    # Function implementation continues here...
    restricted = False
    demo_user = False
    
    restricted_emails = []
    if client.restricted_ids:
        restricted_emails = [e.strip() for e in client.restricted_ids.split(',')]
    demo_emails = []
    if client.demo_ids:
        demo_emails = [e.strip() for e in client.demo_ids.split(',')]

    
    if email in restricted_emails:
        restricted = True
    if email in demo_emails:
        demo_user = True

    if demo_user:
        user_account = Identity.objects.get(deleted=False,tenant_id=client.tenant_id,value=email)
        specific_date = datetime.datetime.strptime(str(user_account.created.date()), "%Y-%m-%d")

        # Get today's date
        current_date = datetime.datetime.now()

        # Calculate the difference between today's date and the specific date
        time_difference = current_date - specific_date

        # Check if the difference is greater than or equal to 2 weeks
        if time_difference >= datetime.timedelta(weeks=2):
            restricted = True
            demo_user = False

        logger.info(f"time difference: {time_difference} ")

    user_info = {
        "client_name": client.client_name,
        "avatar_bot_creation": client.avatar_bot_creation,
        "feedback_bot_creation": client.feedback_bot_creation,
        "subject_matter_bot_creation": client.subject_matter_bot_creation,
        "monthly_conversation_limit": client.number_of_conversation_per_month,
        "required_form_details": extract_fields(client.required_form_fields) if client.required_form_fields else None,
        "is_restricted": restricted,
        "is_demo_user": demo_user,
        "accessed_bot_ids": client.accessed_bot_ids,
        "coach_skills": client.coach_skills,
        "coach_expertise": client.coach_expertise,
        "departments": client.departments,
        "restricted_pages": client.restricted_pages,
        "restricted_features": client.restricted_features,
        "user_email": email
    }

    return user_info

def is_business_email(email):
    import re
    # Define a regular expression pattern for personal email domains
    personal_email_pattern = r'@(gmail|yahoo|hotmail)\.(com|net|org)'
    
    # Use re.search to find if the email matches the pattern
    match = re.search(personal_email_pattern, email)
    
    # If match is found, it's not a business email, otherwise it is
    if match:
        return False
    else:
        return True


def create_client_id(domain):
    client = ClientUserInfo.objects.create(
        client_name =  domain.split(".")[0].capitalize(),
        domain_name = domain,
    )
    return client

def create_or_assign_client_id(email,tenant,create_new_client=False):

    # first needs to check if email already assigned

    already_assigned_client = ClientUserInfo.objects.filter(tenant_id=tenant.uid,deleted=False,member_emails__contains=email)
    if already_assigned_client.count() > 0:
        return already_assigned_client.first().client_name
    assigned = False
    client = None

    if is_business_email(email):
        domain = email.split('@')[-1]
        already_exist_client = ClientUserInfo.objects.filter(tenant_id=tenant.uid,deleted=False,domain_name=domain)
        if already_exist_client.count() == 0:
            if create_new_client:
                client = create_client_id(domain)
        else:
            client = already_exist_client.first()
            
        if client:
            unique_emails = set([email for email in client.member_emails.split(",") if len(email.strip()) > 0] if client.member_emails else [])
            unique_emails.add(email)
            client.member_emails = ",".join(unique_emails)
            client.save(update_fields=['member_emails'])

            # by default we will add it to restricted ids
            restricted_emails = set([email for email in client.restricted_ids.split(",") if len(email.strip()) > 0] if client.restricted_ids else [])
            restricted_emails.add(email)
            client.restricted_ids = ",".join(restricted_emails)
            client.save(update_fields=['restricted_ids'])

            assigned = True


    if not assigned:
        client = ClientUserInfo.objects.get(tenant_id=tenant.uid,deleted=False,uid='9f07b64c-2dee-4a92-9ac2-1d041ff26205')  # assigning to first-demo
        unique_emails = set([email for email in client.member_emails.split(",") if len(email.strip()) > 0] if client.member_emails else [])
        unique_emails.add(email)
        client.member_emails = ",".join(unique_emails)
        client.save(update_fields=['member_emails'])

        # by default we will add it to restricted ids
        restricted_emails = set([email for email in client.restricted_ids.split(",") if len(email.strip()) > 0] if client.restricted_ids else [])
        restricted_emails.add(email)
        client.restricted_ids = ",".join(restricted_emails)
        client.save(update_fields=['restricted_ids'])

    return client.client_name if client else None


    
       