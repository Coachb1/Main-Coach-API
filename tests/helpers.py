import logging

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from commons.openai_gpt import gpt3_completion
from commons.timeit import timeit
from external_apis.coach_whisper_api import coach_whisper_api
from tenants.models import Tenant
from tests.choices import InteractionModeChoices, TestQuestionResponseEvaluationStatusChoices
from tests.models import Test
from tests.models import TestAttemptSession
from tests.models import TestInvite
from tests.models import TestQuestion
from tests.models import TestQuestionResponse
from users.models import User

logger = logging.getLogger(__name__)


@timeit
def create_test(tenant: Tenant,
                creator_id: str,
                title: str,
                description: str,
                interaction_mode: str,
                test_type: str,
                test_related_context: str,
                questions: list) -> tuple[Test, list[TestQuestion]]:
    try:
        creator = User.objects.get(tenant_id=tenant.uid, uid=creator_id, deleted=0)
    except User.DoesNotExist as e:
        logger.exception("failed to create test, creator with id %s does not exist", creator_id)
        raise serializers.ValidationError("invalid creator id")

    with transaction.atomic():
        test = Test.objects.create(
            tenant_id=tenant.uid,
            creator_id=creator.uid,
            title=title,
            description=description,
            interaction_mode=interaction_mode,
            test_type=test_type,
            test_related_context=test_related_context,
        )

        test_questions = []
        for question in questions:
            test_questions.append(
                TestQuestion.objects.create(
                    tenant_id=tenant.uid,
                    test_id=test.uid,
                    question_type=question.get("question_type"),
                    media_link=question.get("media_link"),
                    question=question.get("question"),
                    subjective_answer=question.get("subjective_answer"),
                    objective_answer=question.get("objective_answer"),
                    mcq_options=question.get("mcq_options"),
                    mcq_answer=question.get("mcq_answer"),
                )
            )

    logger.info("created test for tenant %s", tenant.uid)

    return test, test_questions


@timeit
def create_test_invite(tenant: Tenant,
                       test_id: str,
                       participant_id: str,
                       expires_at: str) -> TestInvite:
    try:
        test = Test.objects.get(tenant_id=tenant.uid, uid=test_id, deleted=0)
    except Test.DoesNotExist as e:
        logger.exception("failed to create invite, test with id %s does not exist", test_id)
        raise serializers.ValidationError("invalid test id")

    try:
        participant = User.objects.get(tenant_id=tenant.uid, uid=participant_id, deleted=0)
    except User.DoesNotExist as e:
        logger.exception("failed to create invite, participant with id %s does not exist", test_id)
        raise serializers.ValidationError("invalid participant id")

    test_invite = TestInvite.objects.create(
        tenant_id=tenant.uid,
        test_id=test_id,
        participant_id=participant_id,
        expires_at=expires_at
    )

    logger.info("created test invite for tenant %s", tenant.uid)

    return test_invite


@timeit
def create_test_question_answer_session(tenant: Tenant,
                                        test_id: str,
                                        test_invite_id: str,
                                        participant_id: str) -> TestAttemptSession:
    try:
        test = Test.objects.get(tenant_id=tenant.uid, uid=test_id, deleted=0)
    except Test.DoesNotExist as e:
        logger.exception("failed to create session, test with id %s does not exist", test_id)
        raise serializers.ValidationError("invalid test id")

    if test_invite_id:
        try:
            test_invite = TestInvite.objects.get(tenant_id=tenant.uid, uid=test_invite_id, deleted=0)
        except Test.DoesNotExist as e:
            logger.exception("failed to create session, test_invite with id %s does not exist", test_invite_id)
            raise serializers.ValidationError("invalid test_invite_id")

    try:
        participant = User.objects.get(tenant_id=tenant.uid, uid=participant_id, deleted=0)
    except User.DoesNotExist as e:
        logger.exception("failed to create session, participant with id %s does not exist", test_id)
        raise serializers.ValidationError("invalid participant id")

    test_attempt_session = TestAttemptSession.objects.create(
        tenant_id=tenant.uid,
        test_id=test_id,
        participant_id=participant_id,
        test_invite_id=test_invite_id,
        started_at=timezone.now(),
    )

    logger.info("created test_attempt_session for tenant %s", tenant.uid)

    return test_attempt_session


@timeit
def create_test_question_answer(tenant: Tenant,
                                test_attempt_session_id: str,
                                question_id: str,
                                response_file: str = None,
                                response_text: str = None) -> TestQuestionResponse:
    if not response_file and not response_text:
        raise serializers.ValidationError("either response_file or response_text should be present")

    try:
        session = TestAttemptSession.objects.get(tenant_id=tenant.uid, uid=test_attempt_session_id, deleted=0)
    except TestAttemptSession.DoesNotExist as e:
        logger.exception("failed to get session, test attempt session with id %s does not exist",
                         test_attempt_session_id)
        raise serializers.ValidationError("invalid test_attempt_session_id")

    try:
        question = TestQuestion.objects.get(tenant_id=tenant.uid, uid=question_id, deleted=0)
    except TestAttemptSession.DoesNotExist as e:
        logger.exception("failed to get question, question with id %s does not exist", question_id)
        raise serializers.ValidationError("invalid question_id")

    test_question_response = TestQuestionResponse.objects.create(
        tenant_id=tenant.uid,
        test_attempt_session_id=test_attempt_session_id,
        question_id=question_id,
        response_text=response_text,
        response_file=response_file
    )

    logger.info("created test_question_response for tenant %s", tenant.uid)

    test_question_response = process_test_response(test_question_response)

    return test_question_response


@timeit
def process_test_response(test_question_response: TestQuestionResponse):
    question = TestQuestion.objects.get(uid=test_question_response.question_id)
    test_attempt_session = TestAttemptSession.objects.get(uid=test_question_response.test_attempt_session_id)
    test = Test.objects.get(uid=test_attempt_session.test_id)
    # participant = User.objects.get(uid=test_attempt_session.participant_id)

    if test.interaction_mode != InteractionModeChoices.text:
        if test.interaction_mode == InteractionModeChoices.audio:
            test_question_response.response_text = coach_whisper_api.get_transcribe_from_audio(
                test_question_response.response_file)
        elif test.interaction_mode == InteractionModeChoices.video:
            test_question_response.response_text = ""
        test_question_response.save(update_fields=["response_text", "updated"])

    test_related_context = test.test_related_context
    prompt = get_chat_conversation_prompt_v2(
        test_title=test.title,
        test_related_context=test_related_context,
        question=question.question,
        question_context=question.subjective_answer,
        candidate_reply=test_question_response.response_text)
    gpt_feedback = gpt3_completion(prompt, stop=["USER:", "CoachBot"])
    if not gpt_feedback.text:
        # delete this response
        test_question_response.deleted = test_question_response.deleted + 1
        test_question_response.save()
        raise ValueError("unable to get feedback for %s", test_question_response.uid)

    test_question_response.metadata = {
        "gpt": {
            "prompt": prompt,
            "response": {
                "raw": gpt_feedback.raw,
                "text": gpt_feedback.text,
            }
        }
    }

    test_question_response.feedback_text = gpt_feedback.text
    test_question_response.evaluation_status = TestQuestionResponseEvaluationStatusChoices.success
    test_question_response.save(update_fields=["feedback_text", "evaluation_status", "updated"])

    return test_question_response


def get_chat_conversation_prompt(question: str,
                                 candidate_reply: str,
                                 test_related_context: str):
    if test_related_context:
        return get_chat_conversation_prompt_with_context(
            question=question, candidate_reply=candidate_reply, test_related_context=test_related_context)
    else:
        return get_chat_conversation_prompt_without_context(question=question, candidate_reply=candidate_reply)


def get_chat_conversation_prompt_without_context(question: str,
                                                 candidate_reply: str):
    bot_name = "CoachBot"
    bot_intro = f"I am a professional instructor named '{bot_name}'. My task is to evaluate, enrich and increase " \
                f"understanding of a candidate. I will read the 'QUESTION' and 'CANDIDATE_REPLY', and then I will " \
                f"proceed with my task."
    bot_purpose = "I will now evaluate, enrich and increase understanding of 'CANDIDATE_REPLY' related to the 'QUESTION'"

    return f"""
{bot_intro}

QUESTION:
{question}

CANDIDATE_REPLY: 
{candidate_reply}

{bot_purpose}:
{bot_name}:
"""


def get_chat_conversation_prompt_with_context(question: str,
                                              candidate_reply: str,
                                              test_related_context: str):
    bot_name = "CoachBot"
    bot_intro = f"I am a professional instructor named '{bot_name}'. My task is to evaluate, enrich and increase " \
                f"understanding of a candidate based about the 'QUESTION'. I will read the 'QUESTION', 'TEST_CONTEXT' and 'CANDIDATE_REPLY', and then I will " \
                f"proceed with my task."
    bot_purpose = "I will now evaluate, enrich and increase understanding of 'CANDIDATE_REPLY' related to the 'QUESTION' and use 'TEST_CONTEXT' as overall context to judge the 'CANDIDATE_REPLY'"

    return f"""
{bot_intro}

QUESTION:
{question}

TEST_CONTEXT:
{test_related_context}

CANDIDATE_REPLY: 
{candidate_reply}

{bot_purpose}:
{bot_name}:
"""


def get_chat_conversation_prompt_v2(test_title: str,
                                    test_related_context: str,
                                    question: str,
                                    question_context: str,
                                    candidate_reply: str):
    prompt = f"Title: {test_title}"
    if test_related_context:
        prompt = f"{prompt}\nGlobal Context: {test_related_context}."

    prompt = f"{prompt}\nQuestion: {question}"

    if question_context:
        prompt = f"{prompt}\nExpert Suggestions: {question_context}"

    prompt = f"{prompt}\nCandidate answer: {candidate_reply}"

    last_line = """Please provide critical and developmental feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on  "Title". The feedback length should be between 100 and 150 words"""

    if test_related_context and question_context:
        last_line = """Please provide critical and developmental feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Please take into account the human expert guidance as supplied in the "Expert Suggestions" while providing the feedback. Feedback must be based on  "Title" and "Global Context".The feedback length should be between 100 and 150 words"""
    elif test_related_context:
        last_line = """Please provide critical and developmental feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on  "Title" and "Global Context ".The feedback length should be between 100 and 150 words"""
    elif question_context:
        last_line = """Please provide critical and developmental feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Please take into account the human expert guidance as supplied in the "Expert Suggestions" while providing the feedback. Feedback must be based on  "Title" and "Expert Suggestions".The feedback length should be between 100 and 150 words"""

    prompt = f"{prompt}\n\n{last_line}"

    return prompt
