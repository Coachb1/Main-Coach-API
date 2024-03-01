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
from utilities.helpers import save_user_action_info
import json
from utilities.models import BotQnA, UserIDP
from skills.models import CharacteristicsAndPrompts
from users.helpers import get_user_attribute
from users.models import BotAndUserMapping
from users.choices import ProfileTypeChoice
from users.choices import BotTypeChoice
from apis.accounts.serializers import UserIDPSerializers
from utilities.models import SessionNotesRecommendations

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
        signature_bot = SignatureBot.objects.get(tenant_id=tenant.uid,uid=test_attempt_session.test_id)
        user = User.objects.get(tenant_id=tenant.uid,uid=test_attempt_session.participant_id)
        get_or_create_bot_user_mapping(signature_bot,user)

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
                if signature_bot.bot_type != BotTypeChoice.subject_matter_bot:
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
                            low_char_prompt += f"{l} "
                        high_char_prompt = ""
                        for l in highest_charactersic_prompt:
                            high_char_prompt += f"{l} "
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
                                low_char_prompt += f"{l} "
                            high_char_prompt = ""
                            for l in highest_charactersic_prompt:
                                high_char_prompt += f"{l} "
                            personality = low_char_prompt + " " + high_char_prompt

                        except Exception as e:
                            logger.exception(f"got error: {e}")
                            personality = None

                    custom_prompt = Template(custom_prompt).substitute(
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
                            low_char_prompt += f"{l} "
                        high_char_prompt = ""
                        for l in highest_charactersic_prompt:
                            high_char_prompt += f"{l} "
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
                                "recommended_scenarios": idp.recommended_scenarios,
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
                if signature_bot.bot_type != BotTypeChoice.subject_matter_bot:
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
                            low_char_prompt += f"{l} "
                        high_char_prompt = ""
                        for l in highest_charactersic_prompt:
                            high_char_prompt += f"{l} "
                        personality = low_char_prompt + " " + high_char_prompt

                    except Exception as e:
                        logger.exception(f"got error: {e}")
                        personality = None
            
                    custom_prompt = Template(avatar_bot_default_prompt()).substitute(
                        coach_info = coach_info,
                        conversation_history = conversation_history,
                        context = initial_que_ans,
                        user_personality = personality if signature_bot.use_personality_context else None,
                        idp_report_data = user_recent_idp,
                        session_notes = get_latest_session_notes_coach_coachee(coach_user_id=signature_bot.user_id,coachee_user_id=test_attempt_session.participant_id,tenant_id=test_attempt_session.tenant_id)
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
                                   is_signature_bot: bool) -> CoachingConversation:
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
        if current_conversation == 2 : # increasing action point if conversation contain two chat
            save_user_action_info(tenant.uid,test_attempt_session.participant_id,"chat_attempted")

        signature_bot = SignatureBot.objects.get(tenant_id=tenant.uid, uid=test_attempt_session.test_id, deleted=0)
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
        response = anthropic_completion(prompt,50000)
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
            }
        }

    next_conversation = CoachingConversation.objects.create(
        tenant_id=tenant.uid,
        test_attempt_session_id=reply_to_conversation.test_attempt_session_id,
        coach_message_text=gpt_feedback.text if not is_signature_bot else response,
        coach_message_metadata=coach_message_metadata if not is_signature_bot else None
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
        
        initial_qna = ""
        if bot_type == BotTypeChoice.avatar_bot:
            if session.first().intake_id:
                bot_qna = BotQnA.objects.filter(tenant_id = tenant.uid,bot_id=signature_bot.uid,qna_type='initial_qna',uid=session.intake_id).order_by('-created').first()
                if bot_qna:
                    initial_qna = bot_qna.participant_qna
            else:
                initial_qna = BotQnA.objects.filter(tenant_id = tenant.uid,participant_id=participant_id,bot_id=signature_bot.uid,qna_type="initial_qna").order_by('-id').first()

        else:
            initial_qna = BotQnA.objects.filter(tenant_id = tenant.uid,participant_id=participant_id,bot_id=signature_bot.uid,qna_type="initial_qna").order_by('-id').first()

        logger.info(f"************************************************ initial_qna: {initial_qna}")
        # initial_que_ans = ''.join([f"Question: {que} Answer: {ans}" for que, ans in initial_qna])
        initial_que_ans = initial_qna.participant_qna
        coach_info = ""
        for key,val in signature_bot.data.items():
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

            user_recent_idp = None
            latest_session = session.order_by('-created').first()
            if latest_session.is_idp_discussion_opted:
                idp = UserIDP.objects.filter(tenant_id=tenant.uid, user_id=participant_id, deleted=0).order_by('-created_at').first()
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
                personalities = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,user_id=participant_id).first()
                highest_charactersic_prompt = CharacteristicsAndPrompts.objects.filter(name = personalities.high_rating_characteristics)
                lowest_charactersic_prompt = CharacteristicsAndPrompts.objects.filter(name = personalities.low_rating_characteristics)
                low_char_prompt = ""
                for l in lowest_charactersic_prompt:
                    low_char_prompt += f"{l} "
                high_char_prompt = ""
                for l in highest_charactersic_prompt:
                    high_char_prompt += f"{l} "
                personality = low_char_prompt + " " + high_char_prompt

            except Exception as e:
                logger.exception(f"got error: {e}")
                personality = None
            

            prompt = Template(prompt).substitute(
                coach_info = coach_info,
                conversation_history = current_conv,
                context = initial_que_ans,
                user_personality = personality if signature_bot.use_personality_context else None,
                idp_report_data = user_recent_idp,
                session_notes = get_latest_session_notes_coach_coachee(coach_user_id=signature_bot.user_id,coachee_user_id=participant_id,tenant_id=tenant.uid)
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
                        low_char_prompt += f"{l} "
                    high_char_prompt = ""
                    for l in highest_charactersic_prompt:
                        high_char_prompt += f"{l} "
                    personality = low_char_prompt + " " + high_char_prompt

                except Exception as e:
                    logger.exception(f"got error: {e}")
                    personality = None

            custom_prompt = Template(custom_prompt).substitute(
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
                    low_char_prompt += f"{l} "
                high_char_prompt = ""
                for l in highest_charactersic_prompt:
                    high_char_prompt += f"{l} "
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
                conversation = [{"coach": que, "user": ans} for que, ans in initial_que_ans.items()]
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
        
        initial_qna = ""
        if bot_type == BotTypeChoice.avatar_bot:
            if session.first().intake_id:
                bot_qna = BotQnA.objects.filter(tenant_id = tenant.uid,bot_id=signature_bot.uid,qna_type='initial_qna',uid=session.intake_id).order_by('-created').first()
                if bot_qna:
                    initial_qna = bot_qna.participant_qna
            else:
                initial_qna = BotQnA.objects.filter(tenant_id = tenant.uid,participant_id=participant_id,bot_id=signature_bot.uid,qna_type="initial_qna").order_by('-id').first()

        else:
            initial_qna = BotQnA.objects.filter(tenant_id = tenant.uid,participant_id=participant_id,bot_id=signature_bot.uid,qna_type="initial_qna").order_by('-id').first()

        logger.info(f"************************************************ initial_qna: {initial_qna}")
        # initial_que_ans = ''.join([f"Question: {que} Answer: {ans}" for que, ans in initial_qna])
        initial_que_ans = initial_qna.participant_qna
        coach_info = ""
        for key,val in signature_bot.data.items():
            coach_info += f"{key}: {val}\n"

        current_conv_data = get_bot_conversation_data_user(session,tenant,participant_id,only_converation=True)
        current_conv = [{"coach": i['coach_message_text'], "user":i['participant_message_text']} for i in current_conv_data]

            
        if bot_type == 'avatar_bot':
            prompt = avatar_bot_default_prompt()
            qna_block = get_qna_block_for_coach_mentor(coach_user_id=signature_bot.user_id,participant_id=participant_id,tenant_id=tenant.uid)
            if qna_block:
                qna_block_text = ''
                for que, ans in qna_block.items():
                    qna_block_text += f"Question: {que} Answer: {ans}\n"

                coach_info += "\n" + "FAQs:" + '\n' + qna_block_text
                
            user_recent_idp = None
            latest_session = session.order_by('-created').first()
            if latest_session.is_idp_discussion_opted:
                idp = UserIDP.objects.filter(tenant_id=tenant.uid, user_id=participant_id, deleted=0).order_by('-created_at').first()
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
                personalities = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,user_id=participant_id).first()
                highest_charactersic_prompt = CharacteristicsAndPrompts.objects.filter(name = personalities.high_rating_characteristics)
                lowest_charactersic_prompt = CharacteristicsAndPrompts.objects.filter(name = personalities.low_rating_characteristics)
                low_char_prompt = ""
                for l in lowest_charactersic_prompt:
                    low_char_prompt += f"{l} "
                high_char_prompt = ""
                for l in highest_charactersic_prompt:
                    high_char_prompt += f"{l} "
                personality = low_char_prompt + " " + high_char_prompt

            except Exception as e:
                logger.exception(f"got error: {e}")
                personality = None
            

            prompt = Template(prompt).substitute(
                coach_info = coach_info,
                conversation_history = current_conv,
                context = initial_que_ans,
                user_personality = personality if signature_bot.use_personality_context else None,
                idp_report_data = user_recent_idp,
                session_notes = get_latest_session_notes_coach_coachee(coach_user_id=signature_bot.user_id,coachee_user_id=participant_id,tenant_id=tenant.uid)
            )

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



def avatar_bot_default_prompt():
    return """
    \n\nHuman:
    {Information} - ${coach_info}
    Conversation History : ${conversation_history}
    Context : ${context}
    Personality: ${user_personality}
    IDP: ${idp_report_data}
    Action Plan & Session Notes: ${session_notes}

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

    Conduct a session with a coachee who is sharing their concern in this context {candidate_data_str}. Understand the coachee's concern and problem before providing any advice or solution in the response. The response should be directly related to the concern shared by the coachee.  The personality of the coachee is given here {Personality}. Understand the coachee's personality and always tailor your response accordingly.
    Understand the coachee's perspective to the question and provide the information they want. 
    Offer advice, coaching, and mentoring based on the coach's style and character traits given in {Information}. Consider any other relevant information to provide comprehensive coaching advice. 
    Provide a response based on all the information you have on the coach. Always provide accurate information about yourself as the coach when asked by the coachee. 
    The response should always be directly related to the question. 
    If the coachees' Individual Development Plan is given in the IDP, make sure the response is based on that information.
    If the coachees' Action Plan is given in Action Plan, make sure the response is based on the plan provided and it should be short and precise.
    Consider the prior conversation given in Conversation History when providing the response.
    Offer actionable advice or solutions to the coachee’s potential challenges.
    Break down complex ideas into practical steps.
    Pose questions to the coachee to create engagement.
    Encourage self-reflection or thought-provoking moments.
    Maintain a tone that feels friendly and approachable.
    Use the Custom Knowledge base here {Information}. Always refer to {Information} first, before providing a response. 
    Never provide any answer about a subject the coach is not familiar with. If the user asks any questions about a subject that is not mentioned in  {Information} as Areas of expertise, please respond that you are not familiar with the topic.

    Always provide the response in a first-person tone.
    Always ask a contextual question at the end to further understand the details.
    Always respond as the coach.
    NEVER give visual cues like smiles warmly etc.

    NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output. Start directly with the response and only provide the response.
    NOTE : Always assume suitable details to respond, never respond with unfortunately I can't provide an answer to that question.

    NOTE: Make sure to keep the response short. Get straight to the point without unnecessary elaboration or repetition. Eliminate redundant phrases or ideas that don't add value to the response. Choose words and phrases that convey your message clearly and directly. Make sure to give short answers but do not miss out any necessary information.

    NOTE: Provide concise responses without exceeding a brief length constraint. Aim for brevity while delivering complete information and answers.

    \n\nAssistant:

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

