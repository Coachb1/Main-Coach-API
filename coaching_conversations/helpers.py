import logging

from django.utils import timezone
from rest_framework import serializers

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
from utilities.models import BotQnA
from skills.models import CharacteristicsAndPrompts

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
        
    signature_bot_question = "what do you want to ask ?"
    if is_signature_bot:
        if initial_qna:

            qna = json.loads(initial_qna)
            signature_bot = SignatureBot.objects.get(tenant_id=tenant.uid,uid=test_attempt_session.test_id)
            custom_prompt = signature_bot.custom_prompt
            # saving initial_qna
            BotQnA.objects.create(
                tenant_id = tenant.uid,
                bot_id = signature_bot.uid,
                participant_id = test_attempt_session.participant_id,
                participant_qna = qna,
                qna_type = 'initial_qna'
            )
            if custom_prompt:
                
                initial_que_ans = ''
                for que, ans in qna.items():
                    initial_que_ans += f"Question: {que} Answer: {ans} \n"

                

                coach_info = ""
                for key,val in signature_bot.data.items():
                    coach_info += f"{key}:{val}\n"

                sessions = TestAttemptSession.objects.filter(tenant_id = tenant.uid, test_id = signature_bot.uid)

                conversation_data= get_bot_conversation_data_user(sessions,tenant,test_attempt_session.participant_id,only_converation=True)
                conversation_history = [{"coach": i['coach_message_text'], "user":i['participant_message_text']} for i in conversation_data]


                if signature_bot.bot_type == 'avatar_bot':
                    try:
                        personalities = CoachCoacheeMentorMenteeProfile.objects.get(user_id=test_attempt_session.participant_id)
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
                        personality = "The person is highly flexible. This may lead to challenges such as difficulty setting boundaries, indecision, and susceptibility to manipulation. They may grapple with assertiveness, find it hard to maintain stability, and experience issues related to personal and professional relationships. Please provide a response that offers gentle guidance on establishing healthy boundaries, encourages confident decision-making, and promotes assertiveness."
            
                    custom_prompt = Template(custom_prompt).substitute(
                        coach_info = coach_info,
                        conversation_history = conversation_history,
                        context = initial_que_ans,
                        user_personality = personality
                    )
                elif signature_bot.bot_type == 'helper_bot':
                    try:
                        personalities = CoachCoacheeMentorMenteeProfile.objects.get(user_id=test_attempt_session.participant_id)
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
                        personality = "The person is highly flexible. This may lead to challenges such as difficulty setting boundaries, indecision, and susceptibility to manipulation. They may grapple with assertiveness, find it hard to maintain stability, and experience issues related to personal and professional relationships. Please provide a response that offers gentle guidance on establishing healthy boundaries, encourages confident decision-making, and promotes assertiveness."
            
                    bot_att = BotAttribute.objects.get(bot_id = signature_bot.uid)
                    faqs = bot_att.attached_faqs_context
                    faqs_text = ""
                    for que, ans in faqs.items():
                        faqs_text += f"Question: {que} Answer: {ans}\n"

                    custom_prompt = Template(custom_prompt).substitute(
                                    conversation_history = initial_que_ans,
                                    user_personality = personality,
                                    articles = coach_info + " General FAQs: " + faqs_text,
                                    google_search = ""  # TODO: Add functionality for extacting googlesearch result
                                )
                    
                elif signature_bot.bot_type == 'subject_matter_bot':
                    bot_att = BotAttribute.objects.get(bot_id = signature_bot.uid)
                    faqs = bot_att.attached_faqs_context
                    faqs_text = ""
                    for que, ans in faqs.items():
                        faqs_text += f"Question: {que} Answer: {ans}\n"

                    custom_prompt = Template(custom_prompt).substitute(
                                    conversation_history = initial_que_ans,
                                    articles = coach_info + " General FAQs: " + faqs_text,
                                    google_search = ""  # TODO: Add functionality for extacting googlesearch result
                                )


                
                logger.info(f"signature  bot prompt  {custom_prompt}")
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
        if current_conversation == 5: # increasing action point if conversation contain five chat
            save_user_action_info(tenant,test_attempt_session.participant_id,"chat_attempted")
            
        signature_bot = SignatureBot.objects.get(tenant_id=tenant.uid, uid=test_attempt_session.test_id, deleted=0)
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
        initial_qna = BotQnA.objects.filter(tenant_id = tenant.uid,participant_id=participant_id,bot_id=signature_bot.uid,qna_type="initial_qna").order_by('-id')[0]
        logger.info(f"************************************************ initial_qna: {initial_qna}")
        # initial_que_ans = ''.join([f"Question: {que} Answer: {ans}" for que, ans in initial_qna])
        initial_que_ans = initial_qna.participant_qna
        coach_info = ""
        for key,val in signature_bot.data.items():
            coach_info += f"{key}: {val}\n"
            
        if bot_type == 'avatar_bot':
            


            try:
                personalities = CoachCoacheeMentorMenteeProfile.objects.get(user_id=participant_id)
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
                personality = "The person is highly flexible. This may lead to challenges such as difficulty setting boundaries, indecision, and susceptibility to manipulation. They may grapple with assertiveness, find it hard to maintain stability, and experience issues related to personal and professional relationships. Please provide a response that offers gentle guidance on establishing healthy boundaries, encourages confident decision-making, and promotes assertiveness."
            

            prompt = Template(prompt).substitute(
                coach_info = coach_info,
                conversation_history = conversation_history,
                context = initial_que_ans,
                user_personality = personality
            )

        elif bot_type == 'helper_bot':
            try:
                personalities = CoachCoacheeMentorMenteeProfile.objects.get(user_id=participant_id)
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
                personality = "The person is highly flexible. This may lead to challenges such as difficulty setting boundaries, indecision, and susceptibility to manipulation. They may grapple with assertiveness, find it hard to maintain stability, and experience issues related to personal and professional relationships. Please provide a response that offers gentle guidance on establishing healthy boundaries, encourages confident decision-making, and promotes assertiveness."
            

            session = TestAttemptSession.objects.filter(tenant_id=tenant.uid,
                                                        uid=test_attempt_session_id,
                                                        deleted=0
                                                        )
            current_conv_data = get_bot_conversation_data_user(session,tenant,participant_id,only_converation=True)
            current_conv = [{"coach": i['coach_message_text'], "user":i['participant_message_text']} for i in current_conv_data]

            bot_att = BotAttribute.objects.get(bot_id = signature_bot.uid)
            faqs = bot_att.attached_faqs_context
            faqs_text = ""
            for que, ans in faqs.items():
                faqs_text += f"Question: {que} Answer: {ans}\n"

            conversation = [{"coach": que, "user": ans} for que, ans in initial_que_ans.items()]
            conversation.extend(current_conv)

            prompt = Template(prompt).substitute(
                            conversation_history = conversation,
                            user_personality = personality,
                            articles = coach_info + " General FAQs: " + faqs_text,
                            google_search = ""  # TODO: Add functionality for extacting googlesearch result
                        )

            
        elif bot_type == 'subject_matter_bot':
            session = TestAttemptSession.objects.filter(tenant_id=tenant.uid,
                                                        uid=test_attempt_session_id,
                                                        deleted=0
                                                        )
            current_conv_data = get_bot_conversation_data_user(session,tenant,participant_id,only_converation=True)
            current_conv = [{"coach": i['coach_message_text'], "user":i['participant_message_text']} for i in current_conv_data]
            bot_att = BotAttribute.objects.get(bot_id = signature_bot.uid)
            faqs = bot_att.attached_faqs_context
            faqs_text = ""
            for que, ans in faqs.items():
                faqs_text += f"Question: {que} Answer: {ans}\n"

            conversation = [{"coach": que, "user": ans} for que, ans in initial_que_ans.items()]
            conversation.extend(current_conv)
            
            prompt = Template(prompt).substitute(
                            conversation_history = conversation,
                            articles = coach_info + " General FAQs: " + faqs_text,
                            google_search = ""  # TODO: Add functionality for extacting googlesearch result
                        )


        else:
            prompt = Template(prompt).substitute(
                    info = page_info,
                    context_info = candidate_data_str
                    )
            

            
        logger.info(f"custom Prompt: {prompt}")
        
            

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
                    "updated": conversation.updated
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
    return """\n\nHuman:
    {Information} - ${coach_info}
    Conversation History : ${conversation_history}
    Context : ${context}
    Personality: ${user_personality}

    Read this {information} thoroughly and understand it deeply. The information contains detailed insights into a coach's background, personality, philosophies, and coaching style. Act as the coach whose information is provided here and respond to the coachee. 

    Conduct a session with a coachee who is sharing their concern in this context {Context}. Understand the coachee's concern and problem before providing any advice or solution in the response. The response should be directly related to the concern shared by the coachee.  The personality of the coachee is given here {Personality}. Understand the coachee's personality and always tailor your response accordingly.
    Understand the coachee's perspective to the question and provide the information they want. 
    Offer general advice, coaching, and mentoring based on the coach's style. Consider any other relevant information to provide comprehensive coaching advice. 
    Provide a response based on all the information you have on the coach. Always provide accurate information about yourself as the coach when asked by the coachee. 
    The response should always be directly related to the question. 
    Consider the prior conversation given in Conversation History when providing the response.
    Offer actionable advice or solutions to the coachee's potential challenges.
    Break down complex ideas into practical steps.
    Pose questions to the coachee to create engagement.
    Encourage self-reflection or thought-provoking moments.
    Maintain a tone that feels friendly and approachable.
    Use the Custom Knowledge base here {Information}. Always refer to {Information} first, before providing a response. 

    Always provide the response in a first-person tone.
    Always ask a contextual question at the end to further understand the details.
    Always respond as the coach.

    NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output. Start directly with the response and only provide the response.

    \n\nAssistant:"""

