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
from users.models import SignatureBot
from commons.anthropic import anthropic_completion
from users.db import get_user_display_name, get_user_by_id

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
                                     test_attempt_session_id: str, is_signature_bot: bool) -> CoachingConversation:
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

    next_conversation = CoachingConversation.objects.create(
        tenant_id=tenant.uid,
        test_attempt_session_id=test_attempt_session_id,
        coach_message_text=question.question if not is_signature_bot else "initial question text",
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
        signature_bot = SignatureBot.objects.get(tenant_id=tenant.uid, bot_id=test_attempt_session.test_id, deleted=0)
        # prompt = f"""\nHuman: info: {signature_bot.data} based on this information answer this question : {participant_message_text}"""
        prompt = get_signature_bot_prompt(signature_bot.data, participant_message_text, signature_bot.bot_type)
        response = anthropic_completion(prompt,5000)
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




def get_signature_bot_prompt(page_info, candidate_data_str, bot_type):
    coaching_prompt = f"""\n\nHuman:
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


    prompt = coaching_prompt if bot_type == "coaching" else generic_prompt 

    return prompt



@timeit
def get_bot_conversation_data(conversations:CoachingConversation,session:TestAttemptSession,tenant:Tenant):
    
    results = []

    for conversation in conversations:
        results.append({
            "uid": conversation.uid,
            "coach_message_text": conversation.coach_message_text,
            "participant_message_text": conversation.participant_message_text,
            "status": conversation.status,
            "created": conversation.created,
            "updated": conversation.updated
        })

    test_attempt_session = TestAttemptSession.objects.get(
        uid=session.uid, tenant_id=tenant.uid)

    participant_id = test_attempt_session.participant_id
    date = test_attempt_session.created


    participant_name = get_user_display_name(
        get_user_by_id(participant_id))

    data ={
        "results": results,
        "participant_name": participant_name,
        "date": date,
        "logo": tenant.logo,
    }

    return data