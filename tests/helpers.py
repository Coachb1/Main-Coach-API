import json
import logging
import os
import random
import string
import tempfile
import time
from datetime import date
from string import Template

from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import get_random_string
from nltk.tokenize import sent_tokenize
from rest_framework import serializers

import settings
from apis.frontend_api.report_types import ReportType
from commons.anthropic import anthropic_completion
from commons.openai_gpt import gpt3_completion, gpt_wishper_api, num_tokens_for_prompt
from commons.timeit import timeit
from documents.choices import DocOwnerTypeChoice, DocTypeChoice
from documents.helpers import create_document, get_document_url
from email_sender.helpers import send_email
from external_apis.coach_metric_api import coach_metric_api
from external_apis.coach_whisper_api import coach_whisper_api
from external_apis.whatsapp_api import whatsapp_api
from pdf_generator.helpers import convert_html_to_pdf
from settings import BACKEND
from settings import FRONTEND_BASE_URL
from skills.constants import skills
from skills.helpers import evaluate_response, get_participant_info, evaluate_conversation, \
    evaluate_group_discussion_conversation, evaluate_skills_group_discussion_conversation, evaluate_response_skill
from skills.models import SkillsRating
from tenants.helpers import tenant_from_tenant_id
from tenants.models import Tenant
from test_bulk_upload.constants import get_skills_by_candidate_type
from tests.choices import InteractionModeChoices, QuestionForChoices, TestTypeChoices
from tests.choices import TestAttemptSessionStatusChoices
from tests.choices import TestQuestionResponseEvaluationStatusChoices
from tests.models import Test
from tests.models import TestAttemptSession
from tests.models import TestInvite
from tests.models import TestQuestion
from tests.models import TestQuestionResponse
from users.db import get_user_by_id
from users.db import get_user_display_name
from users.models import User
from users.models import UserAttribute
from web_auth.helpers import create_new_tokens
from nltk.tokenize import word_tokenize
import nltk
nltk.download('punkt')
import pytz
import datetime

logger = logging.getLogger(__name__)

STRING_ASCII_DIGITS = (string.ascii_uppercase + string.digits)

TEST_CODE_LENGTH = 6
TEST_CODE_GENERATION_MAX_RETRY = 4


def add_prefix(prefix, value):
    return f"{prefix}{value}"


@timeit
def get_unique_test_code(tenant: Tenant) -> str:
    global TEST_CODE_LENGTH

    test_code = get_random_string(
        length=TEST_CODE_LENGTH, allowed_chars=STRING_ASCII_DIGITS)

    test_code = add_prefix('Q', test_code)
    retries = 0
    while Test.objects.filter(tenant_id=tenant.uid,
                              test_code=test_code,
                              deleted=0).exists():
        if retries >= TEST_CODE_GENERATION_MAX_RETRY:
            TEST_CODE_LENGTH += 1
            retries = 0
            logger.info(
                "[get_unique_test_code] increased length of test code to %s", TEST_CODE_LENGTH)

        test_code = get_random_string(
            length=TEST_CODE_LENGTH, allowed_chars=STRING_ASCII_DIGITS)
        test_code = add_prefix('Q', test_code)
        retries += 1

    return test_code


@timeit
def create_test(tenant: Tenant,
                creator_id: str,
                title: str,
                description: str,
                candidate_type: str,
                email_address_list: str,
                max_test_allowed: int,
                send_only_to_email: bool,
                interaction_mode: str,
                test_type: str,
                gpt_prompt_override: str,
                email_candidate: bool,
                test_related_context: str,
                orchestrated_conversation_details: dict,
                description_media: str,
                is_single_bot: bool,
                is_checkin_type: bool,
                skills_to_evaluate: str,
                tedtalk_and_hbr_case: str,
                is_learner_path: bool,
                is_email_type: bool,
                scenario_case: str,
                is_game_type: bool,
                image_url: str,
                rating : str,
                source : str,
                questions: list) -> tuple[Test, list[TestQuestion]]:
    try:
        creator = User.objects.get(
            tenant_id=tenant.uid, uid=creator_id, deleted=0)
    except User.DoesNotExist as e:
        logger.exception(
            "failed to create test, creator with id %s does not exist", creator_id)
        raise serializers.ValidationError("invalid creator id")

    with transaction.atomic():
        test = Test.objects.create(
            tenant_id=tenant.uid,
            creator_id=creator.uid,
            title=title,
            candidate_type=candidate_type,
            email_address_list=email_address_list,
            send_only_to_email=send_only_to_email,
            email_candidate=email_candidate,
            gpt_prompt_override=gpt_prompt_override,
            description=description,
            interaction_mode=interaction_mode,
            test_type=test_type,
            is_single_bot=is_single_bot,
            is_learner_path=is_learner_path,
            is_checkin_type=is_checkin_type,
            is_email_type=is_email_type,
            skills_to_evaluate=skills_to_evaluate,
            tedtalk_and_hbr_case=tedtalk_and_hbr_case,
            test_related_context=test_related_context,
            orchestrated_conversation_details=orchestrated_conversation_details,
            test_code=get_unique_test_code(tenant),
            description_media=description_media,
            max_test_allowed=max_test_allowed,
            scenario_case=scenario_case,
            is_game_type=is_game_type,
            rating=rating,
            image_url=image_url,
            source=source,
        )

        test_questions = []
        for inx, question in enumerate(questions, start=1):
            if test.test_type == TestTypeChoices.orchestrated_conversation:
                klp = ''
                kls = ''
            else:
                klp = (
                        question.get("key_learning_point")
                        or get_question_key_learning_point(test_title=title,
                                                           test_question=question.get("question"))
                )
                kls = (
                        question.get("key_learning_skills")
                        or get_question_key_learning_skills(test_title=title,
                                                            test_question=question.get("question"))
                )

            test_q = TestQuestion.objects.create(
                tenant_id=tenant.uid,
                test_id=test.uid,
                question_number=question.get("question_number") or inx,
                question_type=question.get("question_type"),
                question_for=question.get("question_for"),
                media_link=question.get("media_link"),
                gpt_prompt_override=question.get("gpt_prompt_override"),
                question=question.get("question"),
                can_be_skipped=question.get("can_be_skipped") or False,
                is_view_only=question.get("is_view_only") or False,
                subjective_answer=question.get("subjective_answer"),
                objective_answer=question.get("objective_answer"),
                mcq_options=question.get("mcq_options"),
                mcq_answer=question.get("mcq_answer"),
                loader_wait_text=question.get("loader_wait_text"),
                key_learning_point=klp,
                key_learning_skills=kls
            )

            #
            # upsert_into_skill_index(tenant_id=tenant.uid,
            #                         skills=test_q.key_learning_skills.split(","))

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
        logger.exception(
            "failed to create invite, test with id %s does not exist", test_id)
        raise serializers.ValidationError("invalid test id")

    try:
        participant = User.objects.get(
            tenant_id=tenant.uid, uid=participant_id, deleted=0)
    except User.DoesNotExist as e:
        logger.exception(
            "failed to create invite, participant with id %s does not exist", test_id)
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

        if test.max_test_allowed is not None:
            if test.max_test_allowed == 0:
                logger.exception(
                    f"Failed to create session for test for id {test_id}")
                raise serializers.ValidationError(
                    "maximum test allowed exceeded!")
            else:
                if test.max_test_allowed > 0:
                    test.max_test_allowed -= 1
                    test.save()

    except Test.DoesNotExist as e:
        logger.exception(
            "failed to create session, test with id %s does not exist", test_id)
        raise serializers.ValidationError("invalid test id")

    if test_invite_id:
        try:
            test_invite = TestInvite.objects.get(
                tenant_id=tenant.uid, uid=test_invite_id, deleted=0)
        except Test.DoesNotExist as e:
            logger.exception(
                "failed to create session, test_invite with id %s does not exist", test_invite_id)
            raise serializers.ValidationError("invalid test_invite_id")

    try:
        participant = User.objects.get(
            tenant_id=tenant.uid, uid=participant_id, deleted=0)
    except User.DoesNotExist as e:
        logger.exception(
            "failed to create session, participant with id %s does not exist", test_id)
        raise serializers.ValidationError("invalid participant id")

    timezone = pytz.timezone("Asia/Kolkata")
    now = datetime.datetime.now(timezone)
    
    test_attempt_session = TestAttemptSession.objects.create(
        tenant_id=tenant.uid,
        test_id=test_id,
        participant_id=participant_id,
        test_invite_id=test_invite_id,
        started_at=now,
        expires_at=now + datetime.timedelta(minutes=30),
        is_checkin_type=test.is_checkin_type
    )

    logger.info("created test_attempt_session for tenant %s", tenant.uid)

    return test_attempt_session


@timeit
def create_test_question_answer(tenant: Tenant,
                                test_attempt_session_id: str,
                                question_id: str,
                                response_file: str = None,
                                response_text: str = None,
                                is_whatsapp: bool = False) -> TestQuestionResponse:
    try:
        test_attempt_session = TestAttemptSession.objects.get(
            tenant_id=tenant.uid, uid=test_attempt_session_id, deleted=0)
    except TestAttemptSession.DoesNotExist as e:
        logger.exception("failed to get session, test attempt session with id %s does not exist",
                         test_attempt_session_id)
        raise serializers.ValidationError("invalid test_attempt_session_id")

    try:
        question = TestQuestion.objects.get(
            tenant_id=tenant.uid, uid=question_id, deleted=0)
    except TestAttemptSession.DoesNotExist as e:
        logger.exception(
            "failed to get question, question with id %s does not exist", question_id)
        raise serializers.ValidationError("invalid question_id")

    if question.question_for == QuestionForChoices.user and not response_file and not response_text:
        raise serializers.ValidationError(
            "either response_file or response_text should be present")

    test_question_response = TestQuestionResponse.objects.create(
        tenant_id=tenant.uid,
        test_attempt_session_id=test_attempt_session_id,
        question_id=question_id,
        responder_type=question.question_for,
        responder_display_name=question.question_for,
        response_text=response_text,
        response_file=response_file
    )

    logger.info("created test_question_response for tenant %s", tenant.uid)

    test = Test.objects.get(uid=test_attempt_session.test_id)

    # handle orchestrated conversation in a different manner
    if test.test_type == TestTypeChoices.orchestrated_conversation:
        if question.question_for == QuestionForChoices.user:
            return process_orchestrated_test_response_by_user(test_question_response)
        else:
            return process_orchestrated_test_response_by_bot_llm(test_question_response)

    return process_test_response(
        test_question_response, is_whatsapp
    )


def delete_test_response(test_response):
    test_response.deleted = test_response.deleted + 1
    test_response.save()


@timeit
def process_test_response(test_question_response: TestQuestionResponse, is_whatsapp: bool = False):
    question = TestQuestion.objects.get(uid=test_question_response.question_id)
    test_attempt_session = TestAttemptSession.objects.get(
        uid=test_question_response.test_attempt_session_id
    )

    logger.info(
        f"[process_test_response]: {test_question_response.uid}, and test_attempt_session: {test_attempt_session.uid}")

    if test_attempt_session.status == TestAttemptSessionStatusChoices.completed:
        logger.info(
            f"Test Session is already completed: {test_attempt_session.uid}")
        return test_question_response

    test = Test.objects.get(uid=test_attempt_session.test_id)
    # participant = User.objects.get(uid=test_attempt_session.participant_id)

    last_question_number = TestQuestion.objects.filter(
        test_id=test.uid,
        deleted=0
    ).order_by(
        "-question_number"
    ).first().question_number

    is_last_question = question.question_number == last_question_number

    # sometimes questions are being processed in background;
    #  this is a hack to ensure before processing last question, all the previous ones are processed
    if is_last_question:
        start_time = time.time()
        while True:
            end_time = time.time()
            if end_time - start_time > 92:
                logger.error(
                    f"[Time Limit] Unable to evaluate response: {test_question_response.uid}")
                raise ValueError("unable to evaluate response: %s",
                                 test_question_response.uid)

            time.sleep(4)

            not_evaluated_test_responses_count = TestQuestionResponse.objects.filter(
                test_attempt_session_id=test_attempt_session.uid,
                deleted=0
            ).exclude(
                uid=test_question_response.uid
            ).exclude(
                evaluation_status=TestQuestionResponseEvaluationStatusChoices.success
            ).count()

            if not_evaluated_test_responses_count == 0:
                break

    # if this was the last question; mark the session as completed
    with transaction.atomic():
        if is_last_question:
            try:
                _test_attempt_session = TestAttemptSession.objects.filter(
                    uid=test_attempt_session.uid, deleted=0
                ).select_for_update(nowait=True).get()
            except Exception as e:
                logger.exception(e)
                logger.info(
                    f"Test Session is failed for concurrent request: {test_attempt_session.uid}")
                raise e

            _test_attempt_session.status = TestAttemptSessionStatusChoices.completed
            _test_attempt_session.save(update_fields=["status", "updated"])

        transaction.on_commit(
            lambda: __process_test_response(
                question=question,
                test=test,
                test_attempt_session=test_attempt_session,
                test_question_response=test_question_response,
                is_whatsapp=is_whatsapp,
                last_question_number=last_question_number
            )
        )

    # refreshed from db to reflect any changes due to above logics
    test_question_response.refresh_from_db()

    return test_question_response


def __process_test_response(question: TestQuestion, test: Test, test_attempt_session: TestAttemptSession,
                            test_question_response: TestQuestionResponse, is_whatsapp: bool = False,
                            last_question_number: int = 0):
    logger.info(
        f"[__process_test_response]: {test_question_response.uid}, and test_attempt_session: {test_attempt_session.uid}")

    test_attempt_session.refresh_from_db()

    test_attempt_session.current_question_idx = question.question_number

    if question.question_number == last_question_number:
        test_attempt_session.next_question_idx = -1
    else:
        test_attempt_session.next_question_idx = question.question_number + 1

    test_attempt_session.save(
        update_fields=["current_question_idx", "next_question_idx", "updated"])

    if question.is_view_only:
        test_question_response.evaluation_status = TestQuestionResponseEvaluationStatusChoices.success
        test_question_response.save(
            update_fields=["evaluation_status", "updated"])
        return test_question_response

    if test.interaction_mode != InteractionModeChoices.text:
        update_fields = ["response_text", "updated"]
        if test.interaction_mode == InteractionModeChoices.audio:
            # try:
            #     test_question_response.response_text = coach_whisper_api.get_transcribe_from_audio(
            #         test_question_response.response_file)
            # except:
            
            try:
                transcript = gpt_wishper_api(
                    test_question_response.response_file)
                test_question_response.response_text = transcript
            except:
                transcript = "Transcription couldn't be generated"
                test_question_response.response_text = transcript

            try:
                speech_met = coach_metric_api.get_speech_metrics_from_audio(
                    test_question_response.response_file,transcript)
                test_question_response.speech_metrics = speech_met
            except Exception as e:
                logger.exception(e)

                # HACK sane default values
                speech_met = {
                    'energy_grade': 4,
                    'fluency_grade': 5,
                    'confidence_grade': 3,
                    'pace': 150,
                    'sentiment_percentage': "30%",
                    'power_word_density': 0,
                    'filler_words_score': 0,
                    'volume': 50,
                    'silence_number': 1,
                    "pitch": 165.0,
                    "transcript": "Transcription couldn't be generated",
                    "energy_cohort": "C",
                    "silence_length": 0,
                    "people_quotient": 0.0,
                    "confidence_cohort": "C",
                    "energy_percentage": 50,
                    "filler_words_cohort": 0,
                    "confidence_percentage": 55.0,
                    "sales_quotient_percentile": 0.0,
                    "aggregate_energy_percentage": 45.0,
                    "learner_quotient_percentile": 0.0,
                    "manager_quotient_percentile": 0.0,
                    "aggregate_fluency_percentage": 75.0,
                    "leadership_quotient_percentile": 0.0,
                    "aggregate_confidence_percentage": 55.0,
                    "power_word_percentage": '20%',
                    "filler_word_percentage": "9%",
                    "fluency_percentage": "50%"
                }

                test_question_response.speech_metrics = speech_met

            update_fields.append("speech_metrics")

        elif test.interaction_mode == InteractionModeChoices.video:
            # test_question_response.response_text = coach_whisper_api.get_transcribe_from_video(
            #     test_question_response.response_file)
            try:
                transcript = gpt_wishper_api(
                    test_question_response.response_file)
                test_question_response.response_text = transcript
            except:
                transcript = "Transcription couldn't be generated"
                test_question_response.response_text = transcript
            try:
                speech_met_video = coach_metric_api.get_speech_metrics_from_video(
                    test_question_response.response_file,transcript)
                test_question_response.speech_metrics = speech_met_video

            except Exception as e:
                
                logger.exception(e)

                # HACK sane default values
                speech_met_video = {
                    'energy_grade': 4,
                    'fluency_grade': 5,
                    'confidence_grade': 3,
                    'pace': 150,
                    'sentiment_percentage': "30%",
                    'power_word_density': 0,
                    'filler_words_score': 0,
                    'volume': 50,
                    'silence_number': 1,
                    "pitch": 165.0,
                    "transcript": "Transcription couldn't be generated",
                    "energy_cohort": "C",
                    "silence_length": 0,
                    "people_quotient": 0.0,
                    "confidence_cohort": "C",
                    "energy_percentage": 50,
                    "filler_words_cohort": 0,
                    "confidence_percentage": 55.0,
                    "sales_quotient_percentile": 0.0,
                    "aggregate_energy_percentage": 45.0,
                    "learner_quotient_percentile": 0.0,
                    "manager_quotient_percentile": 0.0,
                    "aggregate_fluency_percentage": 75.0,
                    "leadership_quotient_percentile": 0.0,
                    "aggregate_confidence_percentage": 55.0,
                    "power_word_percentage": '20%',
                    "filler_word_percentage": "9%",
                    "fluency_percentage": "50%"
                }
                test_question_response.speech_metrics = speech_met_video
            update_fields.append("speech_metrics")

        test_question_response.save(update_fields=update_fields)

    if test.is_email_type:
        prompt = get_email_type_prompt(
            test_title=test.title,
            test_description=test.description,
            question=question.question,
            candidate_reply=test_question_response.response_text)

    else:
        if question.gpt_prompt_override or test.gpt_prompt_override:
            prompt = get_overridden_prompt(
                prompt_template=question.gpt_prompt_override or test.gpt_prompt_override,
                test_title=test.title,
                test_description=test.description,
                question=question.question,
                question_context=question.subjective_answer,
                candidate_reply=test_question_response.response_text
            )
        else:
            prompt = get_chat_conversation_prompt_v3(
                test_title=test.title,
                test_description=test.description,
                question=question.question,
                question_context=question.subjective_answer,
                candidate_reply=test_question_response.response_text)


    feedback_text = ''
    raw_text = ''
    response_text = test_question_response.response_text
    go_for_feedback = True

    words = word_tokenize(test_question_response.response_text)

    if len(words) <= 5 :
        feedback_text = "No feedback can be generated because of too low response length"
        go_for_feedback = False
    
    if go_for_feedback:
        anthropic_feedback = anthropic_completion(prompt, 400)

        if not anthropic_feedback:

            max_retry = 3

            while max_retry > 0:
                num_tokens = num_tokens_for_prompt(response_text)
                sentences = sent_tokenize(response_text)
                if num_tokens < 1500:
                    break
                else:
                    response_text = " ".join(sentences[:-1])
                    if test.is_email_type:
                        prompt = get_email_type_prompt(
                            test_title=test.title,
                            test_description=test.description,
                            question=question.question,
                            candidate_reply=test_question_response.response_text)

                    else:
                        if question.gpt_prompt_override or test.gpt_prompt_override:
                            prompt = get_overridden_prompt(
                                prompt_template=question.gpt_prompt_override or test.gpt_prompt_override,
                                test_title=test.title,
                                test_description=test.description,
                                question=question.question,
                                question_context=question.subjective_answer,
                                candidate_reply=response_text
                            )
                        else:
                            prompt = get_chat_conversation_prompt_v3(
                                test_title=test.title,
                                test_description=test.description,
                                question=question.question,
                                question_context=question.subjective_answer,
                                candidate_reply=response_text)

                max_retry -= 1

            gpt_feedback = gpt3_completion(prompt, stop=["USER:", "CoachBot"])
            if not gpt_feedback.text:
                feedback_text = "Feedback couldn't be generated Because of server overload. You may try after few minutes or you can choose to complete this interaction as well."
            else:
                feedback_text = gpt_feedback.text
                raw_text = gpt_feedback.raw

        else:
            feedback_text = anthropic_feedback

    test_question_response.metadata = {
        "gpt": {
            "prompt": prompt,
            "response": {
                "raw": raw_text,
                "text": feedback_text,
            }
        }
    }

    test_question_response.feedback_text = feedback_text
    test_question_response.evaluation_status = TestQuestionResponseEvaluationStatusChoices.success
    test_question_response.save(
        update_fields=["metadata", "feedback_text", "evaluation_status", "updated"])

    # Evaluating TestResponse based on skills required in the question [SAM CHANGES]
    required_skills = question.key_learning_skills.split(",")
    required_skills = [skill.strip() for skill in required_skills if skill]
    required_skills = [skill.lower() for skill in required_skills if skill]

    skills_rating = {}

    skills_rating, is_evaluated = evaluate_response(
        test_question_response,
        question.question,
        test_question_response.response_text,
        required_skills,
        test.description,
        test.title,
        test.test_code,
        test_attempt_session.uid
    )
    

    if not is_evaluated:
        test_question_response.evaluation_status = TestQuestionResponseEvaluationStatusChoices.failed
        # delete this response
        delete_test_response(test_question_response)
        logger.error("failed to get skills_rating json, got %s", skills_rating)
        raise ValueError("failed to get skills_rating json for %s",
                         test_question_response.uid)

    relevance = 1
    if "relevance" in skills_rating:
        relevance = int(skills_rating['relevance'])  # taking relevance and deleting it form json
        del skills_rating['relevance']
 

    # Removing the skills which are not required in the question
    _to_be_deleted = []
    for key in skills_rating.keys():
        if key not in required_skills:
            _to_be_deleted.append(key)

    for key in _to_be_deleted:
        del skills_rating[key]

    # If skill rating score is greater than 8.5 then we are setting it to 8.5
    for skill in skills_rating:
        if skills_rating[skill] > 8.5:
            skills_rating[skill] = 8.5
        elif skills_rating[skill] < 1.5:
            skills_rating[skill] = 1.5

    # Calculating the average score of the response
    response_avg_score = 0
    skills_count = 0
    for skill in skills_rating:
        if isinstance(skills_rating[skill], str):
            continue

        response_avg_score += skills_rating[skill] or random.randint(3, 7)
        skills_count += 1

    if skills_count == 0:
        response_avg_score = 0
    else:
        response_avg_score = response_avg_score / skills_count

    # Save skills rating and average score in TestQuestionResponse
    test_question_response.skills_rating = skills_rating
    test_question_response.avg_score = response_avg_score
    test_question_response.relevance = relevance
    test_question_response.save(update_fields=["skills_rating", "avg_score","relevance"])

    # def __calc_score_in_different_thread():
    #     # Evaluate skills rating for the test attempt session and update skills table in that.
    #     calc_score(test_attempt_session, test)
    #     report_url = generate_session_report_link(test_attempt_session, test)

    #     if test.email_address_list:

    #         send_report_link_to_email(
    #             test, test_attempt_session, report_url, is_whatsapp)

    #     if is_whatsapp and test.test_type != TestTypeChoices.interview:
    #         send_report_link_to_whatsapp(
    #             test, test_attempt_session, report_url)

    if test_attempt_session.status == TestAttemptSessionStatusChoices.completed:
        # Evaluate skills rating for the test attempt session and update skills table in that.
        calc_score(test_attempt_session, test)
        report_url = generate_session_report_link(test_attempt_session, test)

        if test.email_address_list:
            send_report_link_to_email(
                test, test_attempt_session, report_url, is_whatsapp)

        if is_whatsapp and test.test_type != TestTypeChoices.interview:
            send_report_link_to_whatsapp(
                test, test_attempt_session, report_url)

    return test_question_response


@timeit
def process_orchestrated_test_response_by_user(test_question_response: TestQuestionResponse):
    test_attempt_session = TestAttemptSession.objects.get(
        uid=test_question_response.test_attempt_session_id, deleted=0)
    test = Test.objects.get(uid=test_attempt_session.test_id, deleted=0)
    question = TestQuestion.objects.get(uid=test_question_response.question_id)

    # Updating test attempt session current/next question status
    test_attempt_session.current_question_idx = question.question_number
    last_question_number = TestQuestion.objects.filter(
        test_id=test.uid, deleted=0).order_by("-question_number").first().question_number

    if question.question_number == last_question_number:
        test_attempt_session.next_question_idx = -1
    else:
        test_attempt_session.next_question_idx = question.question_number + 1

    test_attempt_session.save(
        update_fields=["current_question_idx", "next_question_idx", "updated"])

    update_fields = []
    if test.interaction_mode != InteractionModeChoices.text:
        update_fields.extend(["response_text"])

        if test.interaction_mode == InteractionModeChoices.audio:
            # test_question_response.response_text = coach_whisper_api.get_transcribe_from_audio(
            #     test_question_response.response_file)
            test_question_response.response_text = gpt_wishper_api(
                test_question_response.response_file)
        elif test.interaction_mode == InteractionModeChoices.video:
            # test_question_response.response_text = coach_whisper_api.get_transcribe_from_video(
            #     test_question_response.response_file)
            test_question_response.response_text = gpt_wishper_api(
                test_question_response.response_file)

    update_fields.extend(["evaluation_status", "updated"])
    test_question_response.evaluation_status = TestQuestionResponseEvaluationStatusChoices.success
    test_question_response.save(update_fields=update_fields)

    total_questions = TestQuestion.objects.filter(
        test_id=test.uid, deleted=0).count()

    total_responses = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session.uid,
                                                          deleted=0).count()

    if total_questions == total_responses:
        test_attempt_session.status = TestAttemptSessionStatusChoices.completed
        test_attempt_session.save()
        calc_group_discussion_report_metrics(test_attempt_session, test)
        # Evaluate skills rating for the test attempt session and update skills table in that.

    return test_question_response


@timeit
def process_orchestrated_test_response_by_bot_llm(test_question_response: TestQuestionResponse):
    """
       bot_llm response is always a text;; ignore test mode or question response type
   """

    # ignore processing if bot already has a response; useful in case of initial messages
    if test_question_response.response_text:
        test_question_response.evaluation_status = TestQuestionResponseEvaluationStatusChoices.success
        test_question_response.save()
        return

    question = TestQuestion.objects.get(uid=test_question_response.question_id)

    test_attempt_session = TestAttemptSession.objects.get(
        uid=test_question_response.test_attempt_session_id)

    test = Test.objects.get(uid=test_attempt_session.test_id)

    # Updating test attempt session current/next question status
    test_attempt_session.current_question_idx = question.question_number
    last_question_number = TestQuestion.objects.filter(
        test_id=test.uid, deleted=0).order_by("-question_number").first().question_number

    if question.question_number == last_question_number:
        test_attempt_session.next_question_idx = -1
    else:
        test_attempt_session.next_question_idx = question.question_number + 1

    test_attempt_session.save(
        update_fields=["current_question_idx", "next_question_idx", "updated"])

    prompt = get_orchestrated_test_conversation_prompt(test=test,
                                                       test_attempt_session=test_attempt_session,
                                                       question=question)

    bot_llm_response_text = anthropic_completion(prompt, 300)

    if not bot_llm_response_text:
        # delete this response
        test_question_response.deleted = test_question_response.deleted + 1
        test_question_response.save()
        raise ValueError("unable to get feedback for %s",
                         test_question_response.uid)

    test_question_response.metadata = {
        "anthropic": {
            "prompt": prompt
        }
    }

    test_question_response.response_text = bot_llm_response_text
    test_question_response.evaluation_status = TestQuestionResponseEvaluationStatusChoices.success
    test_question_response.save(
        update_fields=["metadata", "response_text", "evaluation_status", "updated"])

    return test_question_response


def calc_group_discussion_report_metrics(test_attempt_session: TestAttemptSession, test: Test):
    user_persona = test.orchestrated_conversation_details.get(
        "test_user_persona")
    objective = test.orchestrated_conversation_details.get("objective")

    chat_conversation = get_group_discussion_chat_conversation(
        test_attempt_session, user_persona)

    culture_skills_rating = evaluate_group_discussion_conversation(
        test_attempt_session, chat_conversation, user_persona, objective, test.test_code)


    # if culture_skills_rating score is greater than 8.5 then trim the score to 8.5
    for skill in culture_skills_rating:
        if culture_skills_rating[skill] > 8.5:
            culture_skills_rating[skill] = 8.5
        elif culture_skills_rating[skill] < 1.5:
            culture_skills_rating[skill] = 1.5

    skills_rating = evaluate_skills_group_discussion_conversation(
        test_attempt_session, chat_conversation, user_persona, objective, test.skills_to_evaluate)

    # If skills_rating score is greater than 8.5 then trim the score to 8.5
    for skill in skills_rating:
        if skills_rating[skill] > 8.5:
            skills_rating[skill] = 8.5
        elif skills_rating[skill] < 1.5:
            skills_rating[skill] = 1.5

    skills_rating = update_skills_rating_if_same_scores(skills_rating)

    culture_skills_rating = update_culture_skills_if_same_scores(
        culture_skills_rating)

    test_attempt_session.culture_skills_rating = culture_skills_rating
    updated_fields = ["culture_skills_rating",
                      "meeting_summary", "areas_of_improvement"]
    if skills_rating:
        test_attempt_session.skills_rating = skills_rating
        updated_fields.append("skills_rating")

    meeting_summary = get_group_discussion_summary(
        objective, chat_conversation)
    areas_of_improvement = get_areas_of_improvement(
        objective, chat_conversation, user_persona)

    test_attempt_session.meeting_summary = meeting_summary
    test_attempt_session.areas_of_improvement = areas_of_improvement

    test_attempt_session.save(update_fields=updated_fields)

    return test_attempt_session


def get_meeting_report_from_test_attempt_session(test_attempt_session: TestAttemptSession):
    test_attempt_session_id = test_attempt_session.uid

    participant_id = test_attempt_session.participant_id
    participant_name = get_user_display_name(get_user_by_id(participant_id))

    date = test_attempt_session.started_at.strftime("%d %B %Y")

    test = Test.objects.get(uid=test_attempt_session.test_id, deleted=0)
    title = test.title

    objective = test.orchestrated_conversation_details.get("objective")

    user_persona = test.orchestrated_conversation_details.get(
        "test_user_persona")

    chat_conversation = test.orchestrated_conversation_details.get(
        "initial_messages")

    chat_conversation += get_group_discussion_chat_conversation(
        test_attempt_session, user_persona, is_report=True)

    chat_conversation_with_details = []

    for message in chat_conversation:
        user_name, message = message.split(":", 1)
        is_bot = False

        if user_name.strip().lower() != user_persona.strip().lower():
            is_bot = True

        chat_conversation_with_details.append(
            {"user_name": user_name, "message": message, "is_bot": is_bot})

    meeting_summary = test_attempt_session.meeting_summary
    areas_of_improvement = test_attempt_session.areas_of_improvement
    culture_skills = test_attempt_session.culture_skills_rating

    data = {
        "participant_name": participant_name,
        "date": date,
        "title": title,
        "objective": objective,
        "chat_conversation": chat_conversation_with_details,
        "meeting_summary": meeting_summary,
        "areas_of_improvement": areas_of_improvement,
        "culture_skills": culture_skills
    }

    if test_attempt_session.skills_rating:
        data["skills_rating"] = test_attempt_session.skills_rating

    return data


def get_group_discussion_summary(objective: str, chat_conversation: str):
    prompt = f"""
    [Objective of Discussion]: {objective};
    [Conversation]: {chat_conversation};

    Please provide a summary of the meeting in 100 words.
    NOTE: Please do NOT provide any introductions, conclusion or text like "Here is your summary". 
    NOTE: Please only provide the summary of the meeting.
    """

    cnt = 0
    summary = ""

    while cnt < 1:
        try:
            summary = anthropic_completion(prompt, 200)
            break
        except Exception as e:
            logger.exception(e)
            cnt += 1

    if cnt == 1:
        summary = "Could not generate"

    return summary


def get_areas_of_improvement(objective: str, chat_conversation: str, user_persona: str):
    areas_of_improvement = ["Sticking to Agenda",
                            "Driving to decision", "Sticking to Positive behavior"]

    prompt = f"""
    [Objective of Discussion]: {objective};
    [Conversation]: {chat_conversation};

    Based on the discussion above please analyze the efficiency and efficacy of the meeting as it relates to the following parameters:{areas_of_improvement}. Please comment the output in seperate paragraphs where the paragraph headings are {areas_of_improvement} and values are the paragraphs explaining each heading respectively. Include what went well and where are the areas of improvment. Do not provide any introductions and conclusion. Each paragraph must be 50-70 words appropriately.
    
    PLEASE NOTE that you may evaluate the {areas_of_improvement} parameters for the {user_persona} persona only. Do not evaluate any other characters.

    OUTPUT FORMAT:
    Sticking to Agenda
    <paragraph>

    Driving to decision
    <paragraph>

    Sticking to Positive behavior
    <paragraph>
    """

    cnt = 0
    res = ""

    while cnt < 1:  # Because anthropic_completion already has a retry mechanism
        try:
            res = anthropic_completion(prompt, 300)
            break
        except Exception as e:
            logger.exception(e)
            cnt += 1

    if cnt == 1:
        res = {"Sticking to Agenda": "Could not generate",
               "Driving to decision": "Could not generate",
               "Sticking to Positive behavior": "Could not generate"}

    return res


def get_group_discussion_chat_conversation(test_attempt_session: TestAttemptSession, test_user_persona: str,
                                           is_report: bool = False):
    current_conversation = ''
    conversation_list = []
    for test_response in TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session.uid,
                                                             evaluation_status=TestQuestionResponseEvaluationStatusChoices.success,
                                                             deleted=0).order_by('id'):

        if test_response.responder_type == QuestionForChoices.user:
            conv_text = f"{test_user_persona}: {test_response.response_text}"
        else:
            conv_text = f"{test_response.responder_display_name}: {test_response.response_text}"

        current_conversation = current_conversation + "\n" + conv_text
        conversation_list.append(conv_text)

    if is_report:
        return conversation_list

    else:
        return current_conversation


def calc_score(test_attempt_session: TestAttemptSession, test: Test):
    with transaction.atomic():
        return _calc_score(test_attempt_session, test)


def _calc_score(test_attempt_session: TestAttemptSession, test: Test):
    """
    This function calculates the score for the test attempt session and update the skills_rating field in this object
    Also it uses these skills rating to update the skills table
    """
    # get participant id from test_attempt_session
    participant_id = test_attempt_session.participant_id

    # get all the responses for this participant
    responses = TestQuestionResponse.objects.filter(
        test_attempt_session_id=test_attempt_session.uid,
        deleted=0
    )

    culture_skills_rating = {}
    skills_rating = {}
    speech_score = {}
    skills_count = {}
    attempted_count = 0
    has_speech_metric = False

    # For calculating average score of the test
    avg_score = 0
    response_count = 0

    for response in responses:
        if response.skills_rating is None:
            continue

        # # get skills rating from this response
        # response_skills_rating = response.skills_rating
        # response_avg_score = response.avg_score

        # if response_avg_score:
        #     avg_score += response_avg_score
        #     response_count += 1

        if response.speech_metrics:
            has_speech_metric = True
            # get speech metrics from this response
            response_speech_metrics = response.speech_metrics

            for key,value in response_speech_metrics.items():
                if isinstance(value, str) and "%" in value:
                        value = float(value.replace("%", ""))
                if key in speech_score:
                    speech_score[key] += value or random.randint(3, 7)
                else:
                    speech_score[key] = value or random.randint(3, 7)

        # for skill in response_skills_rating:
        #     if skill in skills_rating:
        #         skills_rating[skill] += response_skills_rating[skill] or random.randint(3, 7)
        #         skills_count[skill] += 1
        #     else:
        #         skills_rating[skill] = response_skills_rating[skill] or random.randint(3, 7)
        #         skills_count[skill] = 1

        attempted_count += 1
    # skill_ = []
    # for skill in skills:
    #     skill_.append(skill['name'])

    questions = TestQuestion.objects.filter(test_id=test_attempt_session.test_id,deleted=0)
    skills_=[]
    for question in questions:
        required_skills = question.key_learning_skills.split(",")
        required_skills = [skill.strip() for skill in required_skills if skill]
        required_skills = [skill.lower() for skill in required_skills if skill]
        for s in required_skills:
            skills_.append(s)


    response_skills_rating = calc_skills_rating(test_attempt_session, responses, test,skills_)
    for skill in response_skills_rating:
        if skill in skills_rating:
            skills_rating[skill] += response_skills_rating[skill] or random.randint(3, 7)
            skills_count[skill] += 1
        else:
            skills_rating[skill] = response_skills_rating[skill] or random.randint(3, 7)
            skills_count[skill] = 1

    skills_rating_score = {}
    test_score = 0
    # calculate average skills rating
    for skill in skills_rating:
        skills_rating_score[skill] = skills_rating[skill] / skills_count[skill]
        test_score += skills_rating_score[skill]


    # Calculating the average score of the response
    avg_score = 0
    response_count = 0
    for skill in skills_rating_score:
        if isinstance(skills_rating_score[skill], str):
            continue

        avg_score += skills_rating_score[skill] or random.randint(3, 7)
        response_count += 1

    if response_count == 0:
        avg_score = 0
    else:
        avg_score = avg_score / response_count


    skills_rating_score = update_skills_rating_if_same_scores(
        skills_rating_score)
    skills_rating_score, avg_score = increment_avg_score_in_percentages(
        skills_rating_score, avg_score, participant_id, test_attempt_session)
    culture_skills_rating = calc_culture_skills_rating(test_attempt_session, responses, test)

    culture_skills_rating = update_culture_skills_if_same_scores(
        culture_skills_rating)

    # update skills_rating field in test_attempt_session
    test_attempt_session.skills_rating = skills_rating_score
    test_attempt_session.test_score = test_score
    test_attempt_session.avg_score = avg_score
    test_attempt_session.finished_at = timezone.now()

    if has_speech_metric:
        test_attempt_session.speech_score = speech_score

    updated_fields = ["skills_rating", "test_score", "avg_score",
                      "status", "finished_at", "updated"]

    if has_speech_metric:
        updated_fields.append("speech_score")

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
            required_average_score = rating / skills_count[skill]
            skills_rating_object.skills_info[skill]['average_score'] = required_average_score

    skills_rating_object.total_questions_attempted += attempted_count
    skills_rating_object.total_tests_attempted += 1

    updated_fields.append("skills_info")
    updated_fields.append("total_questions_attempted")
    updated_fields.append("total_tests_attempted")
    updated_fields.append("updated")

    skills_rating_object.save(update_fields=updated_fields)


def round_off_rating(number):
    return round(number * 2) / 2


def increment_avg_score_in_percentages(skills_rating, avg_score, participant_id, test_attempt_session):
    # Get number of interactions for that candidate which are completed but are not the current one
    total_successful_sessions = TestAttemptSession.objects.filter(participant_id=participant_id,
                                                                  status=TestAttemptSessionStatusChoices.completed,
                                                                  deleted=0).exclude(uid=test_attempt_session.uid)

    total_successful_sessions_count = total_successful_sessions.count()

    if total_successful_sessions_count == 1:
        return skills_rating, avg_score

    # Calculate the average score of last 5 interactions
    last_5_sessions = total_successful_sessions.order_by(
        "-finished_at")[:5]

    last_5_sessions_avg_score = 0

    for session in last_5_sessions:
        try:
            last_5_sessions_avg_score += session.avg_score
        except:
            pass

    last_5_sessions_avg_score = last_5_sessions_avg_score / 5

    if last_5_sessions_avg_score < 5:
        return skills_rating, avg_score

    increase_by_percent = min(total_successful_sessions_count, 10)
    # 1 -> 1%, 2 -> 2%, 3 -> 3%, 4 -> 4%, 5 -> 5%, 6 -> 6%, 7 -> 7%, 8 -> 8%, 9 -> 9%, 10 -> 10%, 11 -> 10%, 12 -> 10%, 13 -> 10%, 14 -> 10%, 15 -> 10%, 16 -> 10%, 17 -> 10%, 18 -> 10%, 19 -> 10%, 20 -> 10%

    # for skill in skills_rating:
    #     skills_rating[skill] = skills_rating[skill] + \
    #                            (skills_rating[skill] * increase_by_percent / 100)

    #     skills_rating[skill] = min(10, skills_rating[skill])
    #     skills_rating[skill] = round_off_rating(skills_rating[skill])

    # avg_score = avg_score + (avg_score * increase_by_percent / 100)
    # avg_score = round_off_rating(avg_score)
    # avg_score = min(10.0, avg_score)
    for skill in skills_rating:
        if skills_rating[skill] < 6:
            increase_factor = 1 + (skills_rating[skill] / 10) * (increase_by_percent / 100)
            skills_rating[skill] *= increase_factor
            skills_rating[skill] = min(10, skills_rating[skill])
            skills_rating[skill] = round_off_rating(skills_rating[skill])
    
    increase_factor_avg = 1 + (avg_score / 10) * (increase_by_percent / 100)
    avg_score *= increase_factor_avg
    avg_score = round_off_rating(avg_score)
    avg_score = min(10.0, avg_score)

    return skills_rating, avg_score


def generate_session_report_link(test_attempt_session: TestAttemptSession, test: Test):
    if test_attempt_session.report_url:
        return test_attempt_session.report_url

    test_id = test_attempt_session.test_id
    test_attempt_session_id = test_attempt_session.uid
    participant_id = test_attempt_session.participant_id

    tokens = create_new_tokens('user-report', 'uid', participant_id)
    refresh_token = tokens["refresh"]

    logger.info("[Refresh Token Generation] generated refresh token %s for participant %s",
                refresh_token[:6], participant_id)

    report_url = f"{FRONTEND_BASE_URL}/{ReportType.INTERACTION_SESSION_REPORT}/{refresh_token}/?session_id={test_attempt_session_id}&interaction_id={test_id}&backend={BACKEND}"

    test_attempt_session.report_url = report_url
    test_attempt_session.save(update_fields=["report_url"])

    return report_url


def update_skills_rating_if_same_scores(skills_rating):
    total_skills = len(skills_rating)
    scores_frequency = {}
    for skill in skills_rating:
        score = skills_rating[skill]
        if score in scores_frequency:
            scores_frequency[score].append(skill)
        else:
            scores_frequency[score] = [skill]

    for score in scores_frequency:
        if len(scores_frequency[score]) > 1:
            random.shuffle(scores_frequency[score])  # Randomly shuffle skills with same score
            # Increment half the skills by 0.5 and other half decrement by 0.5
            for i in range(0, len(scores_frequency[score])):
                skill = scores_frequency[score][i]
                if i < len(scores_frequency[score]) / 2:
                    if i < i/2:
                        skills_rating[skill] = skills_rating[skill] + 0.75   # changed 1 to 0.75 aug
                    else:
                        skills_rating[skill] = skills_rating[skill] - 0.75   

                elif i > len(scores_frequency[score]) / 2:
                    if i > i/2:
                        skills_rating[skill] = skills_rating[skill] + 0.25   # changed 1 to 0.25 aug
                    else:
                        skills_rating[skill] = skills_rating[skill] - 0.25   

                    # skills_rating[skill] = skills_rating[skill] - 0.5

                if skills_rating[skill] < 0:
                    skills_rating[skill] = 0

                if skills_rating[skill] > 10:
                    skills_rating[skill] = 10

    # # If the score is greater than 9 then trim it to 9
    # for skill in skills_rating:
    #     if skills_rating[skill] > 9:
    #         skills_rating[skill] = 9

    return skills_rating


def update_culture_skills_if_same_scores(culture_skills_rating):
    cultural_skills = ['hierarchy', 'consensual', 'indirect negative feedback',
                       'relationship based', 'high context communication', 'Persuasion', 'argumentative']

    if culture_skills_rating is None:
        culture_skills_rating = {}

        for skill in cultural_skills:
            culture_skills_rating[skill] = 6

    scores_frequency = {}
    for skill in culture_skills_rating:
        score = culture_skills_rating[skill]
        if score in scores_frequency:
            scores_frequency[score].append(skill)
        else:
            scores_frequency[score] = [skill]

    for score in scores_frequency:
        if len(scores_frequency[score]) > len(cultural_skills) / 2:
            # Increment half the skills by 0.5 and other half decrement by 0.5
            for i in range(0, len(scores_frequency[score])):
                skill = scores_frequency[score][i]
                if i < len(scores_frequency[score]) / 2:
                    culture_skills_rating[skill] = culture_skills_rating[skill] + 0.5
                else:
                    culture_skills_rating[skill] = culture_skills_rating[skill] - 0.5

                if culture_skills_rating[skill] < 0:
                    culture_skills_rating[skill] = 0

                if culture_skills_rating[skill] > 10:
                    culture_skills_rating[skill] = 10

    # if the score is greater than 9 then trim it to 9
    for skill in culture_skills_rating:
        if culture_skills_rating[skill] > 9:
            culture_skills_rating[skill] = 9

    return culture_skills_rating


def send_report_link_to_email(test: Test, test_attempt_session: TestAttemptSession, report_url: str,
                              is_whatsapp: bool = False):
    if test_attempt_session.is_report_sent_to_email:
        return

    test_name = test.title
    test_description = test.description
    test_completion_date = test_attempt_session.finished_at.strftime(
        "%d %b %Y")
    participant_id = test_attempt_session.participant_id

    participant_attributes = UserAttribute.objects.get(
        user_id=participant_id).attributes

    email_address_list = test.email_address_list
    email_address_list = email_address_list.split(",")
    email_address_list = [email_address.strip()
                          for email_address in email_address_list]

    if is_whatsapp:
        participant_name = participant_attributes.get("user_name")
        mobile_number = participant_attributes.get("mobile_number")
        participant_name = f"{participant_name} ({mobile_number})"
    else:
        participant_name = participant_attributes.get("name")

    

    data = {
        "report_url": report_url,
        "test_name": test_name,
        "candidate_name": participant_name,
        "real_name": participant_attributes.get("real_name"),
    }

    email_subject = f"{test_name} completed by {data['real_name']} (username: {data['candidate_name']}) on {test_completion_date} 🚀🚀"

    participant_email = participant_attributes.get(
        "profile", {}).get("email")

    if test.email_candidate:
        try:
            send_email(participant_email, email_subject, data=data)
        except Exception as e:
            logger.exception("failed to send email to participant %s email %s, err: %s",
                             participant_id, participant_email, e)
            raise e

    for to_email in email_address_list:
        send_email(to_email, email_subject, data=data)

    logger.info("report emails sent successfully test_attempt_session: %s", test_attempt_session.uid)

    test_attempt_session.is_report_sent_to_email = True
    test_attempt_session.save(update_fields=["is_report_sent_to_email"])


def send_report_link_to_whatsapp(test: Test, test_attempt_session: TestAttemptSession, report_url: str):
    if test_attempt_session.is_report_sent_to_whatsapp:
        return

    logger.info("sending whatsapp message to participant %s.",
                test_attempt_session.participant_id)

    logger.info(
        f"is Report Sent to Whatsapp Boolean: {test_attempt_session.is_report_sent_to_whatsapp}")

    test_name = test.title
    test_description = test.description
    participant_id = test_attempt_session.participant_id
    participant_attributes = UserAttribute.objects.get(
        user_id=participant_id).attributes

    participant_name = participant_attributes.get("user_name")

    logger.info(
        f"[Whatsapp Send Message Data] Participant Name: {participant_name}, Participant ID: {participant_id},  Test Name: {test_name}, Test Attempt Session ID: {test_attempt_session.uid}, participant_attributes: {participant_attributes}")

    # Get report url after removing it from the base url
    report_url = report_url.replace(FRONTEND_BASE_URL, "")
    # remove the first backslash
    report_url = report_url[1:]

    participant_phone = participant_attributes.get("mobile_number")

    try:
        whatsapp_api.send_whatsapp_report(participant_phone, report_url)
    except Exception as e:
        logger.exception("failed to send whatsapp message to participant %s with phone %s, err: %s",
                         participant_id, participant_phone, e)
        raise e

    test_attempt_session.is_report_sent_to_whatsapp = True
    test_attempt_session.save(update_fields=["is_report_sent_to_whatsapp"])


def calc_culture_skills_rating(test_attempt_session, responses, test):
    culture_skills_rating = {}

    conversation = ""
    count = 1

    for response in responses:

        question = TestQuestion.objects.get(
            uid=response.question_id)

        question_text = question.question
        response_text = response.response_text

        conversation += f"{count}. [Question:] {question_text}\n"
        if not question.is_view_only:
            conversation += f"[Answer:] {response_text}\n\n"

        count += 1

    # Evaluate conversation
    culture_skills_rating, is_evaluated = evaluate_conversation(
        test_attempt_session, conversation, test.title, test.description, test.test_code)

    if not is_evaluated:
        return None

    # if score is greater than 8.5 then trim it to 8.5
    for skill in culture_skills_rating:
        if culture_skills_rating[skill] > 8.5:
            culture_skills_rating[skill] = 8.5
        elif culture_skills_rating[skill] < 1.5:
            culture_skills_rating[skill] = 1.5

    return culture_skills_rating

def calc_skills_rating(test_attempt_session, responses, test,skills):
    skills_rating = {}

    conversation = ""
    count = 1

    for response in responses:

        question = TestQuestion.objects.get(
            uid=response.question_id)

        question_text = question.question
        response_text = response.response_text

        conversation += f"{count}. [Question:] {question_text}\n"
        if not question.is_view_only:
            conversation += f"[Answer:] {response_text}\n\n"

        count += 1

    # Evaluate conversation
    skills_rating, is_evaluated = evaluate_response_skill(
        test_attempt_session, conversation, test.title, test.description, test.test_code,skills)

    if not is_evaluated:
        return None

    return skills_rating

    
def get_chat_conversation_prompt_v3(test_title: str,
                                    test_description: str,
                                    question: str,
                                    question_context: str,
                                    candidate_reply: str):
    if question_context:
        template = Template(
            """
            Title: ${test_title}. 
            Test Description: ${test_description}
            Customer question:  ${question} 
            Expert Suggestions:  ${question_context} 
            Candidate answer:  ${candidate_reply}
    
            Please provide communication and subject matter feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on "Expert suggestions",  "Title" , only if they are relevant to the situation. The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the responder. The feedback should be structured in the following format: 
            1) Key insights to improve the response - 50 words.                                    
            2) What went well ? - 50 words minimum
            3) What did not work ? - 50 words minimum 
            4) A sample candidate answer - 50 words minimum
            5) A counter intuitive insight - 10 words minimum

            NOTE: The total number of words should not be more than 300 words. Provide the feedback exactly in the format given above.
            NOTE: Never include any word count in the feedback output. (For eg. 50 words)
            NOTE: Never give any feedback on the Question or anybody asking the question.
            NOTE: Please suggest any industry standard framework or derived methods that can strengthen the managers answer in "Key insights to improve the response."
            NOTE : In cases where the "Candidate answer" consists of less than 15 words, always add the following statement after the feedback: "Warning: Very short responses are unrealistic and may lead to poor quality feedback."
            NOTE : Check if the response provided is somewhat relevant to the question or completely irrelevant. If the response is completely irrelevant, start the feedback with the sentence: "FEEDBACK GENERATED IF ANY,  SHOULD BE IGNORED BECAUSE OF POOR RELEVANCE. PLEASE RESPOND WITH RELEVANCE". No additional text should be added. DO NOT give any other feedback.
            """
        )
        return template.substitute(test_title=test_title,
                                   test_description=test_description,
                                   question=question,
                                   question_context=question_context,
                                   candidate_reply=candidate_reply)
    else:
        template = Template(
            """
            Title: ${test_title}. 
            Test Description: ${test_description}
            Customer question:  ${question} 
            Candidate answer:  ${candidate_reply}
            
            Please provide communication and subject matter feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on "Title" , only if they are relevant to the situation. The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the responder. The feedback should be structured in the following format: 
            1) Key insights to improve the response - 50 words.                                    
            2) What went well ? - 50 words minimum
            3) What did not work ? - 50 words minimum 
            4) A sample candidate answer - 50 words minimum
            5) A counter intuitive insight - 10 words minimum

            NOTE: The total number of words should not be more than 300 words. Provide the feedback exactly in the format given above.
            NOTE: Never include any word count in the feedback output. (For eg. 50 words)
            NOTE: Never give any feedback on the Question or anybody asking the question.
            NOTE: Please suggest any industry standard framework or derived methods that can strengthen the managers answer in "Key insights to improve the response."
            NOTE : In cases where the "Candidate answer" consists of less than 15 words, always add the following statement after the feedback: "Warning: Very short responses are unrealistic and may lead to poor quality feedback."
            NOTE : Check if the response provided is somewhat relevant to the question or completely irrelevant. If the response is completely irrelevant, start the feedback with the sentence: "FEEDBACK GENERATED IF ANY,  SHOULD BE IGNORED BECAUSE OF POOR RELEVANCE. PLEASE RESPOND WITH RELEVANCE". No additional text should be added. DO NOT give any other feedback.
            """
        )
        return template.substitute(test_title=test_title,
                                   test_description=test_description,
                                   question=question,
                                   candidate_reply=candidate_reply)


def get_orchestrated_test_conversation_prompt(test: Test,
                                              test_attempt_session: TestAttemptSession,
                                              question: TestQuestion):
    test_main_context = test.orchestrated_conversation_details.get(
        "test_main_context")
    test_user_persona = test.orchestrated_conversation_details.get(
        "test_user_persona")
    initial_messages = test.orchestrated_conversation_details.get(
        "initial_messages")

    current_conversation = ''

    for message in initial_messages:
        conv_text = message
        current_conversation = current_conversation + "\n" + conv_text

    for test_response in TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session.uid,
                                                             evaluation_status=TestQuestionResponseEvaluationStatusChoices.success,
                                                             deleted=0):
        if test_response.responder_type == QuestionForChoices.user:
            conv_text = f"{test_user_persona}: {test_response.response_text}"
        else:
            conv_text = f"{question.question_for}: {test_response.response_text}"

        current_conversation = current_conversation + "\n" + conv_text

    question_text = question.question

    template = Template(
        """
        ${test_main_context}
        
        ${current_conversation}
        
        ${question_text}

        NOTE: Please respond as ${question_for} only. Do not respond as any other persona.
        NOTE: Please respond in not more than 180 words. The total number of words should not be more than 150 words.
        """
    )
    return template.substitute(test_main_context=test_main_context,
                               current_conversation=current_conversation,
                               question_text=question_text,
                               question_for=question.question_for)


def get_email_type_prompt(test_title,
                          test_description,
                          question,
                          candidate_reply):
    template = Template(
        """
        Title: ${test_title}. 
        Test Description: ${test_description}
        Customer question:  ${question} 
        Candidate answer:  ${candidate_reply}

        Please provide feedback on this email. Please do not add any introductory sentence and come to the point directly. Do not include any response to the email. The feedback should be directed to the writer of the email. Please add a sample re-written email.

        Please provide communication and subject matter feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on "Title" , only if they are relevant to the situation. The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the responder. The feedback should be structured in the following format: 
        1) What went well ? - 50 words minimum
        2) What could be improved ? - 50 words minimum 
        3) Some new ideas to reframe the context - 50 words minimum
        3) A sample re-written email. - 80 words minimum
        4) A counter intuitive insight - 10 words minimum

        NOTE: The total number of words should not be more than 300 words. Provide the feedback exactly in the format given above.
        NOTE: Do not show word count.(Eg: 50 words)
        NOTE: Never give any feedback on the Question or anybody asking the question.
        NOTE: Please suggest any industry standard framework or derived methods that can strengthen the managers answer in "Key insights to improve the response."
        NOTE : In cases where the "Candidate answer" consists of less than 15 words, always add the following statement after the feedback: "Warning: Very short responses are unrealistic and may lead to poor quality feedback." 
        NOTE : Check if the response provided is somewhat relevant to the question or completely irrelevant. If the response is irrelevant, start with the sentence: "FEEDBACK GENERATED IF ANY,  SHOULD BE IGNORED BECAUSE OF POOR RELEVANCE. PLEASE RESPOND WITH RELEVANCE". No additional text should be added. DO NOT give any other feedback. 
        """
    )

    return template.substitute(test_title=test_title,
                               test_description=test_description,
                               question=question,
                               candidate_reply=candidate_reply)


def get_overridden_prompt(prompt_template: str,
                          test_title: str,
                          test_description: str,
                          question: str,
                          question_context: str,
                          candidate_reply: str):
    if question_context:
        template = Template(
            """
            Title: ${test_title}. 
            Test Description: ${test_description}
            Customer question:  ${question} 
            Expert Suggestions:  ${question_context}
            Evaluation Criteria: ${prompt_template} 
            Candidate answer:  ${candidate_reply}
    
            Please provide communication and subject matter feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on "Expert suggestions", "Title", only if they are relevant to the situation. The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the responder.
            The feedback should be structured in the following format: 
            1) Key insights to improve the response - 50 words.                                    
            2) What went well ? - 50 words minimum
            3) What did not work ? - 50 words minimum 
            4) A sample candidate answer - 50 words minimum
            5) A counter intuitive insight - 10 words minimum

            NOTE: The total number of words should not be more than 300 words. Provide the feedback exactly in the format given above.
            NOTE: Never include any word count in the feedback output. (For eg. 50 words)
            NOTE: Never give any feedback on the Question or anybody asking the question.
            NOTE: Please suggest any industry standard framework or derived methods that can strengthen the managers answer in "Key insights to improve the response."
            NOTE : In cases where the "Candidate answer" consists of less than 15 words, always add the following statement after the feedback: "Warning: Very short responses are unrealistic and may lead to poor quality feedback."
            NOTE : Check if the response provided is somewhat relevant to the question or completely irrelevant. If the response is completely irrelevant, start the feedback with the sentence: "FEEDBACK GENERATED IF ANY,  SHOULD BE IGNORED BECAUSE OF POOR RELEVANCE. PLEASE RESPOND WITH RELEVANCE". No additional text should be added. DO NOT give any other feedback.
            """
        )
        return template.substitute(test_title=test_title,
                                   test_description=test_description,
                                   question=question,
                                   question_context=question_context,
                                   candidate_reply=candidate_reply)

    else:
        template = Template(
            """
            Title: ${test_title}. 
            Test Description: ${test_description}
            Customer question:  ${question} 
            Evaluation Criteria: ${prompt_template}
            Candidate answer:  ${candidate_reply}
    
            Please provide communication and subject matter feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on  "Title" , only if they are relevant to the situation. The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the responder. The feedback should be structured in the following format: 
            1) Key insights to improve the response - 50 words.                                    
            2) What went well ? - 50 words minimum
            3) What did not work ? - 50 words minimum 
            4) A sample candidate answer - 50 words minimum
            5) A counter intuitive insight - 10 words minimum

            NOTE: The total number of words should not be more than 300 words. Provide the feedback exactly in the format given above.
            NOTE: Never include any word count in the feedback output. (For eg. 50 words)
            NOTE: Never give any feedback on the Question or anybody asking the question.
            NOTE: Please suggest any industry standard framework or derived methods that can strengthen the managers answer in "Key insights to improve the response."
            NOTE : In cases where the "Candidate answer" consists of less than 15 words, always add the following statement after the feedback: "Warning: Very short responses are unrealistic and may lead to poor quality feedback."
            NOTE : Check if the response provided is somewhat relevant to the question or completely irrelevant. If the response is completely irrelevant, start the feedback with the sentence: "FEEDBACK GENERATED IF ANY,  SHOULD BE IGNORED BECAUSE OF POOR RELEVANCE. PLEASE RESPOND WITH RELEVANCE". No additional text should be added. DO NOT give any other feedback.
            """
        )
        return template.substitute(test_title=test_title,
                                   test_description=test_description,
                                   question=question,
                                   prompt_template=prompt_template,
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

    # gpt_feedback = gpt3_completion(prompt, stop=["USER:", "CoachBot"])

    # if not gpt_feedback.text:
    #     raise ValueError("unable to get key_learning_point")

    # return gpt_feedback.text

    anthropic_response = anthropic_completion(prompt, 1000)

    if not anthropic_response:
        anthropic_response = "Communication"

    return anthropic_response


@timeit
def get_question_key_learning_skills(test_title,
                                     test_question):
    skills_name_list = [skill['name'] for skill in skills]
    prompt = Template(
        """
TestTitle: ${test_title}
Question: ${question_text}

For given "Question" for the "TestTitle" extract skills that can be learned from a key learning from an ideal answer to the "Question"  as "Output". The "Output" should have comma separated skills where all skills are in small case.
Choose skills from this list only: ${skills_name_list}
NOTE: Choose only one or two skills from the list. Do not choose more than two skills.
NOTE: Do not provide any help text or any other text in the "Output" other than the skills.
Output:
"""
    ).safe_substitute(
        test_title=test_title,
        question_text=test_question,
        skills_name_list=skills_name_list
    )

    anthropic_response = anthropic_completion(prompt, 1000)

    if not anthropic_response:
        anthropic_response = "Communication"

    anthropic_response_skills = anthropic_response.split(",")

    result = []
    for skill in anthropic_response_skills:
        skill = skill.strip()
        if skill:
            result.append(skill)

    result = ",".join(result)

    return result

    # gpt_feedback = gpt3_completion(prompt, stop=["USER:", "CoachBot"])

    # if not gpt_feedback.text:
    #     raise ValueError("unable to get key_learning_skills")

    # return gpt_feedback.text


def get_test_report(test: Test, only_data=False):
    test_attempt_sessions = TestAttemptSession.objects.filter(
        tenant_id=test.tenant_id,
        test_id=test.uid,
        status=TestAttemptSessionStatusChoices.completed,
        deleted=0
    ).exclude(finished_at=None).order_by(
        "-avg_score"
    )

    css = os.path.join(settings.TEMPLATES_DIR, 'pdf_generator',
                       'reports', 'static', 'styles_report.css')
    test_scores = [
        {"score": test_attempt_session.test_score,
         "avg_score": test_attempt_session.avg_score,
         "speech_score": test_attempt_session.speech_score,
         "participant": get_participant_info(get_user_by_id(test_attempt_session.participant_id))["name"]}
        for test_attempt_session in test_attempt_sessions if User.objects.filter(uid=test_attempt_session.participant_id,is_excluded=0)
    ]
            

    # sort the test_scores by score
    test_scores.sort(key=lambda x: x["avg_score"], reverse=True)

    # Get total number of questions in the test
    total_questions = TestQuestion.objects.filter(
        test_id=test.uid, deleted=0).count()

    # PLACEHOLDER LOGIC
    # test_scores = []
    # while len(test_scores) < 19:
    #     test_scores.append({"score": 0, "participant": {"name": "PLACEHOLDER", "email": "NA"}})

    if only_data:
        return {
            'test_name': test.title,
            'total_questions': total_questions,
            'total_tests_attempts': len(test_scores),
            'test_scores': test_scores,
            'test_code': test.test_code
        }

    t = render_to_string(
        f"pdf_generator/reports/test_report.html", {
            'test_name': test.title,
            'total_tests_attempts': len(test_scores),
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

    # save to local storage
    # with open(f"./test_report_{test.uid}.pdf", "wb") as f:
    #     f.write(pdf)

    return get_document_url(doc)


def generate_test_from_objective_anthropic(objective: str):
    skills_name_list = [skill['name'] for skill in skills]

    prompt = f"""
    Develop a a set of six questions asked by a employee to his manager where the questions must be related to this objective: [{objective}]. Add a initial paragraph titled
    "introduction" to explain the context of the questions in 100 to 200 words that includes any reference
    to any Youtube video links or other article links. Add a title to the session of 5 to 10 words which tells us about the context. Do not add any conclusion. With each question, add a
    prompt that would ask feedback from Anthropic about the response quality of the manager from HR best practices
    and management frameworks point of view. With each question add a one or two line takeaway for a manager about
    providing feedback. With each question, add the management skill(s) that are tested by the question. 
    
    NOTE THAT: Choose skills from this list only: {skills_name_list}.
    
    NOTE THAT: Output the generated data is JSON format only. Do not output anything else.
    NOTE THAT: Don't output any other information other than the following JSON format:

    {"{"}
        "title": "Title of the session",
        "introduction": "Introduction paragraph",
        "questions": [
            {"{"}
                "question": "Question 1 text",
                "prompt": "Prompt 1 text",
                "takeaway": "Takeaway 1 text",
                "skills": ["Skills 1 text"]
            {"}"},
            {"{"}
                "question": "Question 2 text",
                "prompt": "Prompt 2 text",
                "takeaway": "Takeaway 2 text",
                "skills": ["Skills 2 text"]
            {"}"},
            {"{"}
                "question": "Question 3 text",
                "prompt": "Prompt 3 text",
                "takeaway": "Takeaway 3 text",
                "skills": ["Skills 3 text"]
            {"}"},
            {"{"}
                "question": "Question 4 text",
                "prompt": "Prompt 4 text",
                "takeaway": "Takeaway 4 text",
                "skills": ["Skills 4 text"]
            {"}"},
            {"{"}
                "question": "Question 5 text",
                "prompt": "Prompt 5 text",
                "takeaway": "Takeaway 5 text",
                "skills": ["Skills 5 text"]
            {"}"},
            {"{"}
                "question": "Question 6 text",
                "prompt": "Prompt 6 text",
                "takeaway": "Takeaway 6 text",
                "skills": ["Skills 6 text"]
            {"}"}
        ]
    {"}"}

    Generate the data in the above format only. Do not output anything else.
    """

    cnt = 0
    res = ""

    while cnt < 10:
        try:
            res = anthropic_completion(prompt, 1500)
            res = json.loads(res)
            break
        except Exception as e:
            logger.exception(e)
            cnt += 1

    if cnt == 10:
        res = {"status": "failed"}
    else:
        res["status"] = "success"

    return res


# Skills Tracker REport:

def categorize_skills(skill_dict, skills_object):
    categorized_skills = []
    skill_list = [skill.capitalize() for skill in skills_object.keys()]

    for skill, score in skill_dict.items():
        if skill.capitalize() in skill_list:
            try:
                categorized_skills.append({
                    "skill": skill.capitalize(),
                    "score": score,
                    "description": skills_object[skill.capitalize()],
                })
            except Exception as e:
                logger.info({"!!! ERROR !!!": "Error in categorize_skills", "error":e.args})

    return categorized_skills


def get_skills_tracker_data(participant_id):
    # Filter the test_attempt_session with the given participant_id and ordered by created
    test_attempt_sessions = TestAttemptSession.objects.filter(
        is_checkin_type=1, participant_id=participant_id, deleted=0).order_by("-id")

    if test_attempt_sessions.count() > 15:  # limiting test_attempt_sessions if more than 15
        test_attempt_sessions = test_attempt_sessions[:15]

    if test_attempt_sessions.count() == 0:
        return None

    data = {}
    candidate_type = 'Manager'
    skills = []

    for test_attempt_session in test_attempt_sessions:
        test = Test.objects.filter(
            uid=test_attempt_session.test_id, deleted=0).first()
        candidate_type = test.candidate_type
        if candidate_type is None:
            candidate_type = 'Manager'
        participant_id = test_attempt_session.participant_id
        participant_name = get_user_display_name(
            get_user_by_id(participant_id))
        skills_rating = test_attempt_session.skills_rating
        skills.append(skills_rating)

    scores = {}
    for skills_dict in skills[::-1]:
        if skills_dict:
            for skill_name, score in skills_dict.items():
                if skill_name in scores:
                    scores[skill_name].append(score)
                else:
                    scores[skill_name] = [score]

    skills_obj = get_skills_by_candidate_type(candidate_type.capitalize())
    # skills_obj =get_skills_by_candidate_type('Manager')
    people = skills_obj.PEOPLE
    process = skills_obj.PROCESS
    partnership = skills_obj.PARTNERSHIP
    personality = skills_obj.PERSONALITY

    mylist = [
        {
            "chart_name": "People",
            "trends": categorize_skills(scores, people),
        },
        {
            "chart_name": "Partnership",
            "trends": categorize_skills(scores, partnership),
        },
        {
            "chart_name": "Process",
            "trends": categorize_skills(scores, process),
        },
        {
            "chart_name": "Personality",
            "trends": categorize_skills(scores, personality),
        },
    ]

    data['data'] = {
        "participant_name": participant_name,
        "interaction_date": date.today().strftime("%d %b %Y"),
        "mylist": mylist
    }

    return data
