import logging
import os
import string
import tempfile
from string import Template

from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import get_random_string
from rest_framework import serializers

import settings
from commons.openai_gpt import gpt3_completion
from commons.timeit import timeit
from documents.choices import DocOwnerTypeChoice, DocTypeChoice
from documents.helpers import create_document, get_document_url
from external_apis.coach_whisper_api import coach_whisper_api
from pdf_generator.helpers import convert_html_to_pdf
from skills.helpers import evaluate_response, get_participant_info, upsert_into_skill_index, evaluate_conversation
from skills.models import SkillsRating
from tenants.helpers import tenant_from_tenant_id
from tenants.models import Tenant
from tests.choices import InteractionModeChoices, TestQuestionResponseEvaluationStatusChoices, \
    TestAttemptSessionStatusChoices
from tests.models import Test
from tests.models import TestAttemptSession
from tests.models import TestInvite
from tests.models import TestQuestion
from tests.models import TestQuestionResponse
from users.db import get_user_by_id
from users.models import User

# threading

logger = logging.getLogger(__name__)

STRING_ASCII_DIGITS = (string.ascii_uppercase + string.digits)

TEST_CODE_LENGTH = 6
TEST_CODE_GENERATION_MAX_RETRY = 4


@timeit
def get_unique_test_code(tenant: Tenant) -> str:
    global TEST_CODE_LENGTH

    test_code = get_random_string(length=TEST_CODE_LENGTH, allowed_chars=STRING_ASCII_DIGITS)
    retries = 0
    while Test.objects.filter(tenant_id=tenant.uid,
                              test_code=test_code,
                              deleted=0).exists():
        if retries >= TEST_CODE_GENERATION_MAX_RETRY:
            TEST_CODE_LENGTH += 1
            retries = 0
            logger.info("[get_unique_test_code] increased length of test code to %s", TEST_CODE_LENGTH)

        test_code = get_random_string(length=TEST_CODE_LENGTH, allowed_chars=STRING_ASCII_DIGITS)
        retries += 1

    return test_code


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
            test_code=get_unique_test_code(tenant)
        )

        test_questions = []
        for question in questions:
            test_q = TestQuestion.objects.create(
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
                    key_learning_point=(
                            question.get("key_learning_point")
                            or get_question_key_learning_point(test_title=title,
                                                               test_question=question.get("question"))
                    ),
                    key_learning_skills=(
                            question.get("key_learning_skills")
                            or get_question_key_learning_skills(test_title=title,
                                                                test_question=question.get("question"))
                    ),
                )

            upsert_into_skill_index(tenant_id=tenant.uid,
                                    skills=test_q.key_learning_skills.split(","))

            test_questions.append(test_q)

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

    # Evaluating TestResponse based on skills required in the question [SAM CHANGES]
    required_skills = question.key_learning_skills.split(",")
    required_skills = [skill.strip() for skill in required_skills]
    required_skills = [skill.lower() for skill in required_skills]

    skills_rating = {}

    skills_rating, is_evaluated = evaluate_response(question.question, test_question_response.response_text, required_skills)

    if not is_evaluated:
        test_question_response.evaluation_status = TestQuestionResponseEvaluationStatusChoices.failed
        # delete this response
        test_question_response.deleted = test_question_response.deleted + 1
        test_question_response.save()
        logger.error("failed to get skills_rating json, got %s", skills_rating)
        raise ValueError("unable to get feedback for %s", test_question_response.uid)

    for skill in required_skills:

        # Convert skills as very good -> 5, good -> 4, average -> 3, bad -> 2, very bad -> 1
        if skills_rating[skill] == "very good":
            skills_rating[skill] = 5
        elif skills_rating[skill] == "good":
            skills_rating[skill] = 4
        elif skills_rating[skill] == "average":
            skills_rating[skill] = 3
        elif skills_rating[skill] == "bad":
            skills_rating[skill] = 2
        elif skills_rating[skill] == "very bad":
            skills_rating[skill] = 1

    # Save skills rating in TestQuestionResponse
    test_question_response.skills_rating = skills_rating
    test_question_response.save(update_fields=["skills_rating"])

    # 2 Get the test id from this response
    test_id = test.uid
    # count number of questions in the test
    total_questions = TestQuestion.objects.filter(test_id=test_id, deleted=0).count()
    # count number of question response in the test attempt session
    total_responses = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session.uid,
                                                          deleted=0).count()

    if total_questions == total_responses:
        # TODO: Email to the users
        # Evaluate skills rating for the test attempt session and update skills table in that.
        calc_score(test_attempt_session)

    return test_question_response


def calc_score(test_attempt_session: TestAttemptSession):
    with transaction.atomic():
        return _calc_score(test_attempt_session)


def _calc_score(test_attempt_session: TestAttemptSession):
    """
    This function calculates the score for the test attempt session and update the skills_rating field in this object
    Also it uses these skills rating to update the skills table
    """
    # get participant id from test_attempt_session
    participant_id = test_attempt_session.participant_id
    # get all the responses for this participant
    responses = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session.uid, deleted=0)

    culture_skills_rating = {}
    skills_rating = {}
    skills_count = {}
    attempted_count = 0

    for response in responses:
        # get skills rating from this response
        response_skills_rating = response.skills_rating
        for skill in response_skills_rating:
            if skill in skills_rating:
                skills_rating[skill] += response_skills_rating[skill]
                skills_count[skill] += 1
            else:
                skills_rating[skill] = response_skills_rating[skill]
                skills_count[skill] = 1
        attempted_count += 1

    skills_rating_score = {}
    test_score = 0
    # calculate average skills rating
    for skill in skills_rating:
        skills_rating_score[skill] = skills_rating[skill] / skills_count[skill]
        test_score += skills_rating_score[skill]

    culture_skills_rating = calc_culture_skills_rating(responses)

    # update skills_rating field in test_attempt_session
    test_attempt_session.skills_rating = skills_rating_score
    test_attempt_session.test_score = test_score
    test_attempt_session.finished_at = timezone.now()
    test_attempt_session.status = TestAttemptSessionStatusChoices.completed

    updated_fields = ["skills_rating", "test_score", "status", "finished_at", "updated"]

    if culture_skills_rating is not None:
        test_attempt_session.culture_skills_rating = culture_skills_rating
        updated_fields.append("culture_skills_rating")

    test_attempt_session.save(update_fields=updated_fields)

    # Get the object from SkillsRating table where participant_id = participant_id and of it doesn't exist then create it
    skills_rating_object, is_created = SkillsRating.objects.get_or_create(participant_id=participant_id,
                                                                          tenant_id=test_attempt_session.tenant_id)

    updated_fields = []

    skills_rating_object.skills_info = skills_rating_object.skills_info or {}

    for skill, rating in skills_rating.items():

        if skill in skills_rating_object.skills_info:
            skills_rating_object.skills_info[skill]['score'] += rating
            skills_rating_object.skills_info[skill]['question_count'] += skills_count[skill]
        else:
            skills_rating_object.skills_info[skill] = {
                'score': rating,
                'question_count': skills_count[skill]
            }

        if skills_count[skill] == 0:
            skills_rating_object.skills_info[skill]['average_score'] = 0
        else:
            skills_rating_object.skills_info[skill]['average_score'] = rating / skills_count[skill]

    skills_rating_object.total_questions_attempted += attempted_count
    skills_rating_object.total_tests_attempted += 1

    updated_fields.append("skills_info")
    updated_fields.append("total_questions_attempted")
    updated_fields.append("total_tests_attempted")
    updated_fields.append("updated")

    skills_rating_object.save(update_fields=updated_fields)

def calc_culture_skills_rating(responses):
    culture_skills_rating = {}

    conversation = ""
    count = 1
    
    for response in responses:
        question_text = TestQuestion.objects.get(uid=response.question_id).question
        response_text = response.response_text

        conversation += f"{count}. [Question:] {question_text}\n"
        conversation += f"[Answer:] {response_text}\n\n"

        count += 1

    # Evaluate conversation
    culture_skills_rating, is_evaluated = evaluate_conversation(conversation)

    if not is_evaluated:
        return None

    return culture_skills_rating

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


@timeit
def get_question_key_learning_point(test_title,
                                    test_question):
    prompt = Template(
        """
TestTitle: ${test_title}
Question: ${question_text}

For given "Question" for the "TestTitle" extract a key learning from an ideal answer to the "Question"  as "Output". The "Output" should be a single paragraph using full words and sentences, do not append it with "Key Learning:".

Output:
"""
    ).safe_substitute(
        test_title=test_title,
        question_text=test_question
    )

    gpt_feedback = gpt3_completion(prompt, stop=["USER:", "CoachBot"])

    if not gpt_feedback.text:
        raise ValueError("unable to get key_learning_point")

    return gpt_feedback.text


@timeit
def get_question_key_learning_skills(test_title,
                                     test_question):
    prompt = Template(
        """
TestTitle: ${test_title}
Question: ${question_text}

For given "Question" for the "TestTitle" extract skills that can be learned from a key learning from an ideal answer to the "Question"  as "Output". The "Output" should have comma separated skills where all skills are in small case.
Choose skills from this list only: ['teamwork', 'leadership', 'people_management', 'conflict_management', 'negotiation', 'strategic_thinking', 'project_management', 'time_management', 'adaptability', 'engagement', 'empathy', 'communication', 'confidence', 'clarity']

Output:
"""
    ).safe_substitute(
        test_title=test_title,
        question_text=test_question
    )

    gpt_feedback = gpt3_completion(prompt, stop=["USER:", "CoachBot"])

    if not gpt_feedback.text:
        raise ValueError("unable to get key_learning_skills")

    return gpt_feedback.text


def get_test_report(test: Test) -> str:
    test_attempt_sessions = TestAttemptSession.objects.filter(
        tenant_id=test.tenant_id,
        test_id=test.uid,
        status=TestAttemptSessionStatusChoices.completed,
        deleted=0
    ).order_by(
        "-test_score"
    )

    css = os.path.join(settings.TEMPLATES_DIR, 'pdf_generator',
                       'reports', 'static', 'styles_report.css')

    test_scores = [
        {"score": test_attempt_session.test_score,
         "participant": {**get_participant_info(get_user_by_id(test_attempt_session.participant_id))}}
        for test_attempt_session in test_attempt_sessions
    ]

    t = render_to_string(
        f"pdf_generator/reports/test_report.html", {
            'test_name': test.title,
            'total_tests_attempts': len(test_attempt_sessions),
            'test_scores': test_scores,
            'test_code': test.test_code
        })

    pdf = convert_html_to_pdf(t, css)

    tenant = tenant_from_tenant_id(test.tenant_id)

    with tempfile.NamedTemporaryFile() as pdf_file:
        pdf_file.write(pdf)
        pdf_file.content_type = "application/pdf"
        pdf_file.size = len(pdf)

        doc = create_document(
            tenant=tenant,
            owner_type=DocOwnerTypeChoice.system,
            owner_id=tenant.uid,
            display_name=f"test_report_{test.uid}.pdf",
            doc_type=DocTypeChoice.TEST_REPORT,
            file=pdf_file
        )

    return get_document_url(doc)
