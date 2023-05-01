import logging
from string import Template

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
                gpt_prompt_override: str,
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
            gpt_prompt_override=gpt_prompt_override,
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
                    gpt_prompt_override=question.get("gpt_prompt_override"),
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
            test_question_response.response_text = coach_whisper_api.get_transcribe_from_video(
                test_question_response.response_file)
        test_question_response.save(update_fields=["response_text", "updated"])

    if question.gpt_prompt_override or test.gpt_prompt_override:
        prompt = get_overridden_prompt(
            prompt_template=question.gpt_prompt_override or test.gpt_prompt_override,
            test_title=test.title,
            question=question.question,
            question_context=question.subjective_answer,
            candidate_reply=test_question_response.response_text
        )
    else:
        prompt = get_chat_conversation_prompt_v3(
            test_title=test.title,
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


def get_chat_conversation_prompt_v3(test_title: str,
                                    question: str,
                                    question_context: str,
                                    candidate_reply: str):
    if question_context:
        template = Template(
            """
            Title: ${test_title}. 
            Customer question:  ${question} 
            Expert Suggestions:  ${question_context} 
            Candidate answer:  ${candidate_reply}
    
            Please provide communication and subject matter feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on "Expert suggestions",  "Title" , only if they are relevant to the situation. The feedback should include whether right questions are asked for engagement. The feedback should be structured in the following format: 
            1) What went well ? - 50 words minimum
            2) What did not work ? - 50 words minimum 
            3) Generate a sample candidate answer response.
            4) Rating of the response on scale of 1 to 10 in less than 5 words. Always the format X/10.
            """
        )
        return template.substitute(test_title=test_title,
                                   question=question,
                                   question_context=question_context,
                                   candidate_reply=candidate_reply)
    else:
        template = Template(
            """
            Title: ${test_title}. 
            Customer question:  ${question} 
            Candidate answer:  ${candidate_reply}
            
            Please provide communication and subject matter feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on "Title" , only if they are relevant to the situation. The feedback should include whether right questions are asked for engagement. The feedback should be structured in the following format: 
            1) What went well ? - 50 words minimum
            2) What did not work ? - 50 words minimum 
            3) Generate a sample candidate answer response.
            4) Rating of the response on scale of 1 to 10 in less than 5 words. Always the format X/10.
            """
        )
        return template.substitute(test_title=test_title,
                                   question=question,
                                   candidate_reply=candidate_reply)


def get_overridden_prompt(prompt_template: str,
                          test_title: str,
                          question: str,
                          question_context: str,
                          candidate_reply: str):
    return Template(prompt_template).safe_substitute(test_title=test_title,
                                                     question=question,
                                                     question_context=question_context,
                                                     candidate_reply=candidate_reply)
