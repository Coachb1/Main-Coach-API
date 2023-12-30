import json
import logging
import os
import random
import string
import tempfile
import time
from datetime import date
from string import Template
import base64
import math

from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import get_random_string
from nltk.tokenize import sent_tokenize
from rest_framework import serializers
from rest_framework.response import Response

import settings
from apis.frontend_api.report_types import ReportType
from commons.anthropic import anthropic_completion
from commons.openai_gpt import gpt3_completion, gpt_wishper_api, num_tokens_for_prompt
from commons.timeit import timeit
from documents.choices import DocOwnerTypeChoice, DocTypeChoice
from documents.helpers import create_document, get_document_url
from email_sender.helpers import send_email
from external_apis.coach_metric_api import coach_metric_api, default_metrics
from external_apis.coach_whisper_api import coach_whisper_api
from external_apis.whatsapp_api import whatsapp_api
from pdf_generator.helpers import convert_html_to_pdf
from settings import BACKEND
from settings import FRONTEND_BASE_URL
from skills.constants import skills
from skills.helpers import evaluate_response, get_participant_info, evaluate_conversation, \
    evaluate_group_discussion_conversation, evaluate_skills_group_discussion_conversation, evaluate_response_skill, evaluate_relevacy, \
          calulate_summary_for_culture_and_normal_skill, feedback_summary
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
from clients.models import Client
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import nltk
nltk.download('punkt')
nltk.download('stopwords')
import pytz
import datetime
from skills.constants import skills as all_presented_skills
import re
from commons.google_apis import speech_to_text, text_bison_compeletion
from pdf_generator.helpers import update_skill_name
from commons.utils import generic_completion
import threading
from tests.choices import ScenarioCaseChoices
from bs4 import BeautifulSoup
import requests
from test_bulk_upload.scripts import API_ENDPOINT_SLACK
from skills.helpers import evaluate_rating_for_process_training , evaluate_competency_data

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
                is_free: bool,
                is_micro:bool,
                image_url: str,
                rating : str,
                source : str,
                client_name : str,
                questions: list,
                goals: str,
                course: str,
                industry: str,
                exp_level: str,
                total_question:int,
                certificate_details:dict,
                ui_information:dict,
                is_self_created:bool,
                is_logged_in:bool,
                is_immersive:bool,
                media_props:dict,
                is_transcript_only:bool,
                is_pitch: bool) -> tuple[Test, list[TestQuestion]]:
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
            is_free=is_free,
            is_micro=is_micro,
            rating=rating,
            image_url=image_url,
            source=source,
            client_name=client_name,
            goals=goals,
            course=course,
            industry=industry,
            exp_level=exp_level,
            total_question=total_question,
            certificate_details=certificate_details,
            ui_information=ui_information,
            is_self_created=is_self_created,
            is_logged_in=is_logged_in,
            is_immersive=is_immersive,
            media_props=media_props,
            is_transcript_only=is_transcript_only,
            is_pitch=is_pitch
        )

        test_questions = []
        for inx, question in enumerate(questions, start=1):
            if test.test_type == TestTypeChoices.orchestrated_conversation or test.test_type == TestTypeChoices.dynamic_discussion or test.test_type == TestTypeChoices.dynamic_discussion_thread:
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
                mcq_path= question.get('mcq_path'),
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
    
    
    try:
        test_question_response = TestQuestionResponse.objects.create(
            tenant_id=tenant.uid,
            test_attempt_session_id=test_attempt_session_id,
            question_id=question_id,
            responder_type=question.question_for,
            responder_display_name=question.question_for,
            response_text=response_text,
            response_file=response_file
        )
    except:
        test_question_response = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session_id,question_id=question_id).first()

    logger.info("created test_question_response for tenant %s", tenant.uid)

    test = Test.objects.get(uid=test_attempt_session.test_id)

    # handle orchestrated conversation in a different manner
    if test.test_type == TestTypeChoices.orchestrated_conversation or test.test_type == TestTypeChoices.dynamic_discussion or test.test_type == TestTypeChoices.dynamic_discussion_thread:
        if question.question_for == QuestionForChoices.user:
            if test.test_type == TestTypeChoices.orchestrated_conversation or test.test_type == TestTypeChoices.dynamic_discussion:
                return process_orchestrated_test_response_by_user(test_question_response)
            else:
                return process_dynamic_threads_response_by_user(test_question_response)
        else:
            return process_orchestrated_test_response_by_bot_llm(test_question_response,is_whatsapp=is_whatsapp)

    return process_test_response(
        test_question_response, is_whatsapp
    )


def delete_test_response(test_response):
    test_response.deleted = test_response.deleted + 1
    test_response.save()



#*********************** Process MCQ response start *******************************

def process_mcq_response(test_question_response: TestQuestionResponse, is_whatsapp: bool = False):
    question = TestQuestion.objects.get(uid=test_question_response.question_id)
    test_attempt_session = TestAttemptSession.objects.get(
        uid=test_question_response.test_attempt_session_id
    )

    logger.info(
        f"[process_mcq_response]: {test_question_response.uid}, and test_attempt_session: {test_attempt_session.uid}")

    if test_attempt_session.status == TestAttemptSessionStatusChoices.completed:
        logger.info(
            f"Test Session is already completed: {test_attempt_session.uid}")
        return test_question_response

    test = Test.objects.get(uid=test_attempt_session.test_id)

    updated_fields = []
    #* get comment for user decision
    prompt = """
        \n\nHuman:
        {Situation}: %s
        {Decision}: %s

        Based on the given situation {Situation} this is the decision {Decision} a candidate made. Analyze the decision critically and comment on the pros and cons of the decision, focusing on its short-term and long-term effects. Always comment on any potential downsides or risks of the decision in this situation. Always evaluate and comment on what worked well and what could be improved in the decision. Evaluate the decision-making process, focusing on the strategic aspects. Discuss how well the decision aligns with the overall situation. Keep it less than 150 words.
        \n\nAssistant:
        """%(question.question,test_question_response.response_text)

    comment = generic_completion(prompt, 300)
    test_question_response.feedback_text = comment
    updated_fields.append("feedback_text")
    logger.info(f"%%%%%%%%%%%%%%%%%%%%%%%%%%%%comment: {comment} \n\n mcq_options: {question.mcq_options}")


    # option_name = [key for key, value in question.mcq_options.items() if 'opt' in value and value['opt'] == test_question_response.response_text]
    try:
        selected_key = [key for key in question.mcq_options if question.mcq_options[key]['opt'] == test_question_response.response_text][0]
        
        selected_skill = question.mcq_options[selected_key][f"Skill {selected_key}"]
        logger.info(f"%%%%%%%%%%%%%%%%%%%%%%%%%%%% selected_skill: {selected_skill}, selected_key: {selected_key}")
        test_question_response.mcq_skill = selected_skill
        updated_fields.append("mcq_skill")
        
    except Exception as e:
        logger.exception(e)


    test_question_response.evaluation_status = TestQuestionResponseEvaluationStatusChoices.success
    updated_fields.append("evaluation_status")
    updated_fields.append("updated")

    test_question_response.save(update_fields=updated_fields)

    #* mark session completed if this is the last question
    total_responses = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session.uid, deleted=0).order_by("created")
    is_last_question = math.log2(test.total_question + 1) == total_responses.count()

    if is_last_question:
        test_attempt_session.status = TestAttemptSessionStatusChoices.completed
        test_attempt_session.finished_at = timezone.now()
        test_attempt_session.save(update_fields=["status","finished_at", "updated"])

        decision_data = []
        for response in total_responses:
            question = TestQuestion.objects.get(uid=response.question_id)
            decision_data.append({
                "situation": question.question,
                "decision": response.response_text
            })

        decision_map = ""

        for decision in decision_data:
            decision_map += f"situation: {decision['situation']}\ndecision: {decision['decision']}\n\n"

        #* get summary of user decisions
        
        prompt = f"""
            \n\nHuman:
            Scenario: {test.description}
            
            {decision_map}

            Summarize the entire interaction, highlighting key decisions and their implications. Provide insights into the consistency, adaptability, and effectiveness of the candidate's decision-making throughout the scenario. Additionally, discuss any patterns or trends observed in the candidate's decision-making approach and offer suggestions for improvement or areas to be mindful of in future decision-making situations. Keep it less than 200 words.
            \n\nAssistant:
        """
        logger.info(f"%%%%%%%%%%%%%%%%%%%%%%%%%%%%decision_map: {decision_map}")
        logger.info(f"%%%%%%%%%%%%%%%%%%%%%%%%%%%%prompt: {prompt}")

        session_summary = generic_completion(prompt, 500)
        test_attempt_session.mcq_summary = session_summary
        test_attempt_session.save(update_fields=["mcq_summary"])
        report_url = generate_session_report_link(test_attempt_session, test)

         # Get the object from SkillsRating table where participant_id = participant_id and of it doesn't exist then create it
        skills_rating_object, is_created = SkillsRating.objects.get_or_create(participant_id=test_attempt_session.participant_id,
                                                                            tenant_id=test_attempt_session.tenant_id)

        updated_fields = []
        skills_rating_object.total_questions_attempted += int(total_responses.count())
        skills_rating_object.total_tests_attempted += 1

        updated_fields.append("total_questions_attempted")
        updated_fields.append("total_tests_attempted")
        updated_fields.append("updated")

        skills_rating_object.save(update_fields=updated_fields)
        

#*********************** Process MCQ response end *******************************




#*********************** Process Dynamic MCQ response start *******************************

def extract_mcq_options_from_response(text):
    pattern = re.compile(r"Situation:(.*?)Choice 1:(.*?)Choice 2:", re.DOTALL)

    # Search for the pattern in the text
    match = re.search(pattern, text)

    # Extract the matched groups
    if match:
        next_question = match.group(1).strip()
        choice1 = match.group(2).strip()
        choice2 = text.split("Choice 2:")[1].strip()  # Extracting choice2 without using regex

        data = {}
        data['next_situation'] = next_question
        data['option_a'] = choice1
        data['option_b'] = choice2
        return data
    else:
        logger.error(f"Pattern not found in the text ==> {text}")

def process_dynamic_mcq_response(test_question_response: TestQuestionResponse, is_whatsapp: bool = False):
    question = TestQuestion.objects.get(uid=test_question_response.question_id)
    test_attempt_session = TestAttemptSession.objects.get(
        uid=test_question_response.test_attempt_session_id
    )

    logger.info(
        f"[process_mcq_response]: {test_question_response.uid}, and test_attempt_session: {test_attempt_session.uid}")

    logger.info(f"^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^test_attempt_session.status: {test_attempt_session.status}, test_attempt_session.finished_at: {test_attempt_session.finished_at}")
    if test_attempt_session.status == TestAttemptSessionStatusChoices.completed and test_attempt_session.finished_at is not None:
        logger.info(
            f"Dynamic MCQ Test Session is already completed: {test_attempt_session.uid}")
        return test_question_response

    test_question_response.metadata = {}
    test_question_response.metadata['question'] = test_attempt_session.feedback_summary # stored question in this field in case of dynamic mcq
    test_question_response.save(update_fields=["metadata"])

    test = Test.objects.get(uid=test_attempt_session.test_id)

    updated_fields = []
    #* get comment for user decision
    prompt = """
        \n\nHuman:
        {Situation}: %s
        {Decision}: %s

        Based on the given situation {Situation} this is the decision {Decision} a candidate made. Analyze the decision critically and comment on the pros and cons of the decision, focusing on its short-term and long-term effects. Always comment on any potential downsides or risks of the decision in this situation. Always evaluate and comment on what worked well and what could be improved in the decision. Evaluate the decision-making process, focusing on the strategic aspects. Discuss how well the decision aligns with the overall situation. Keep it less than 150 words.
        \n\nAssistant:
        """%(test_question_response.metadata['question'], test_question_response.response_text)

    comment = generic_completion(prompt, 300)
    test_question_response.feedback_text = comment
    updated_fields.append("feedback_text")
    logger.info(f"%%%%%%%%%%%%%%%%%%%%%%%%%%%%comment: {comment} \n\n mcq_options: {question.mcq_options}")

    # mcq_skills_prompt = get_dynamic_mcq_skills_prompt(skills, test_question_response.response_text, test_question_response.metadata['question'])
    # selected_skill = generic_completion(mcq_skills_prompt, 1000)

    test_question_response.mcq_skill = 'NA'
    updated_fields.append("mcq_skill")

    test_question_response.evaluation_status = TestQuestionResponseEvaluationStatusChoices.success
    updated_fields.append("evaluation_status")
    updated_fields.append("updated")

    test_question_response.save(update_fields=updated_fields)

    #* mark session completed if this is the last question
    total_responses = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session.uid, deleted=0).order_by("created")
    is_last_question = test.total_question  == total_responses.count()
    logger.info(f"==================================> is_last_question: {is_last_question}, test.total_question: {test.total_question}, total_responses.count(): {total_responses.count()} , evaluation_status: {test_question_response.evaluation_status}")

    if is_last_question:
        test_attempt_session.status = TestAttemptSessionStatusChoices.completed
        test_attempt_session.finished_at = timezone.now()
        test_attempt_session.save(update_fields=["status","finished_at", "updated"])

        decision_data = []
        for response in total_responses:
            question = TestQuestion.objects.get(uid=response.question_id)
            decision_data.append({
                "situation": question.question,
                "decision": response.response_text
            })

        decision_map = ""

        for decision in decision_data:
            decision_map += f"situation: {decision['situation']}\ndecision: {decision['decision']}\n\n"

        #* get summary of user decisions
        
        prompt = f"""
            \n\nHuman:
            Scenario: {test.description}
            
            {decision_map}

            Summarize the entire interaction, highlighting key decisions and their implications. Provide insights into the consistency, adaptability, and effectiveness of the candidate's decision-making throughout the scenario. Additionally, discuss any patterns or trends observed in the candidate's decision-making approach and offer suggestions for improvement or areas to be mindful of in future decision-making situations. Keep it less than 200 words.
            \n\nAssistant:
        """
        logger.info(f"%%%%%%%%%%%%%%%%%%%%%%%%%%%%decision_map: {decision_map}")
        logger.info(f"%%%%%%%%%%%%%%%%%%%%%%%%%%%%prompt: {prompt}")


        session_summary = generic_completion(prompt, 500)
        test_attempt_session.mcq_summary = session_summary

        skills_prompt = get_dynamic_mcq_skills_prompt(decision_map, test.total_question)
        logger.info(f"$$$$$$$$$$$$$$$$$$$$$$$$$$$$$ skills_prompt: {skills_prompt}")
        
        skills_string = generic_completion(skills_prompt, 1200)

        skills = re.findall(r"'([^']+)'", skills_string)
        logger.info(f"$$$$$$$$$$$$$$$$$$$$$$$$$$$$$ skills: {skills}")
        
        test_attempt_session.skills_explanation = {'mcq_skills': list(set(skills))}

        
        test_attempt_session.save(update_fields=["mcq_summary","skills_explanation"])
        
        report_url = generate_session_report_link(test_attempt_session, test)

         # Get the object from SkillsRating table where participant_id = participant_id and of it doesn't exist then create it
        skills_rating_object, is_created = SkillsRating.objects.get_or_create(participant_id=test_attempt_session.participant_id,
                                                                            tenant_id=test_attempt_session.tenant_id)

        updated_fields = []
        skills_rating_object.total_questions_attempted += int(total_responses.count())
        skills_rating_object.total_tests_attempted += 1

        updated_fields.append("total_questions_attempted")
        updated_fields.append("total_tests_attempted")
        updated_fields.append("updated")

        skills_rating_object.save(update_fields=updated_fields)
        

#*********************** Process Dynamic MCQ response end *******************************



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
    if is_last_question and test.test_type != TestTypeChoices.dynamic_mcq:
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
                end = time.time()
                logger.info(f"####################### process_test_response: processing LAST QUESTION took {end - start_time:.2f} #######################")
                break

    # if this was the last question; mark the session as completed
    with transaction.atomic():
        if is_last_question and test.test_type != TestTypeChoices.dynamic_mcq:
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

@timeit
def evaluate_relevence_thread(question, test_question_response, test, test_attempt_session):
    relevancy_score = {}
    relevancy_score, is_evaluated = evaluate_relevacy(test_question_response,
                                        question.question,
                                        test_question_response.response_text,
                                        test.description,
                                        test.title,
                                        test.is_free
                                        )

    if not is_evaluated:
        test_question_response.evaluation_status = TestQuestionResponseEvaluationStatusChoices.failed
        # delete this response
        delete_test_response(test_question_response)
        logger.error("failed to get relevancy_score, got %s", relevancy_score)
        raise ValueError("failed to get relevancy_score json for %s",
                         test_question_response.uid)

    relevance = 1
    if "relevance" in relevancy_score:
        relevance = int(relevancy_score['relevance'])  # taking relevance and deleting it form json

    test_question_response.relevance = relevance
    test_question_response.save(update_fields=["relevance"])

@timeit
def evaluate_rating_thread(question, test_question_response, test, test_attempt_session):
    raiting_score = {}
    raiting_score, is_evaluated = evaluate_rating_for_process_training(test_question_response,
                                        question.question,
                                        test_question_response.response_text,
                                        question.mcq_answer,
                                        test.title,
                                        test.is_free
                                        )

    if not is_evaluated:
        test_question_response.evaluation_status = TestQuestionResponseEvaluationStatusChoices.failed
        # delete this response
        delete_test_response(test_question_response)
        logger.error("failed to get raiting_score, got %s", raiting_score)
        raise ValueError("failed to get raiting_score json for %s",
                         test_question_response.uid)

    if "rating" in raiting_score:
        rating = raiting_score['rating']  # taking rating and deleting it form json
    
    logger.info({"reting_score": raiting_score})

    test_question_response.response_rating = rating
    test_question_response.save(update_fields=["response_rating"])

@timeit
def evaluate_competency_data_thread(question, test_question_response, test, test_attempt_session):
    competency_data = {}
    conversation = ""
    count = 1

    for response in test_question_response:

        question = TestQuestion.objects.get(
            uid=response.question_id)

        question_text = question.question
        response_text = response.response_text

        conversation += f"{count}. [Question:] {question_text}\n"
        if not question.is_view_only:
            conversation += f"[Answer:] {response_text}\n\n"

        count += 1
        

    competency_data, is_evaluated = evaluate_competency_data(test.description,
                                        conversation,
                                        test_attempt_session,
                                        test.is_free
                                        )

    

    test_attempt_session.competency_data = competency_data
    test_attempt_session.save(update_fields=["competency_data"])


@timeit
def set_language_skills_in_thread(user_response,test_attempt_session):
    language_skills_prompt = f"""
    \n\nHuman:
    Please provide an English language ability score (on a scale of 1 to 10) to a person based on the below recorded speech.

    Candidate answer: ${user_response}

    Always give the output in a single paragraph.
    Keep the output less than 400 words.
    Keep the output more than 200 words.
    Note : Do not include any introduction sentence or word-count in the output.
    \n\nAssistant:"""

    language_skills = anthropic_completion(language_skills_prompt, 150)
    logger.info(f"===========================> language_skills: {language_skills}")
    test_attempt_session.language_skills = language_skills
    test_attempt_session.save(update_fields=["language_skills"])

@timeit
def speech_metrics_in_thread(test_question_response, transcript):
    speech_met = coach_metric_api.get_speech_metrics_from_audio(
                            test_question_response.response_file,transcript)
    test_question_response.speech_metrics = speech_met
    test_question_response.save(update_fields=["speech_metrics"])


def __process_test_response(question: TestQuestion, test: Test, test_attempt_session: TestAttemptSession,
                            test_question_response: TestQuestionResponse, is_whatsapp: bool = False,
                            last_question_number: int = 0):
    logger.info(
        f"[__process_test_response]: {test_question_response.uid}, and test_attempt_session: {test_attempt_session.uid}")
    logger.info(f"{test_attempt_session.uid} - start __process_test_response")

    test_attempt_session.refresh_from_db()

    if test.test_type == TestTypeChoices.mcq:
        return process_mcq_response(test_question_response)

    if test.test_type == TestTypeChoices.dynamic_mcq:
        return process_dynamic_mcq_response(test_question_response)

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


    if test.interaction_mode == InteractionModeChoices.any:
        update_fields = ["response_text", "updated"]
        if test_question_response.response_file:

            start = time.time()
            transcript_length = 0
            try:
                logger.info("*************** generating transcription for(any: audio) using gpt_wishper_api *****")
                transcript = gpt_wishper_api(
                    test_question_response.response_file)
                test_question_response.response_text = transcript
                transcript_length = len(transcript.split())
                logger.info({"message":"************ transcript generated ******","transcript":transcript})
                end = time.time()
                logger.info(f"####################### __process_test_response: transcript generation for ANY: AUDIO took {end - start:.2f} #######################")
            except Exception as e:
                logger.error({"!!!!!!!!!!!!!!!!!Error while generating transcription from gpt_wishper_api":e}, exc_info=True)

                try: 
                    logger.info("*************** generating transcription for(any: audio) using speech_to_text *****")
                    transcript = speech_to_text(test_question_response.response_file)
                    test_question_response.response_text = transcript
                except Exception as e:
                    logger.error({"!!!!!!!!!!!!!!!!!Error while generating transcription from speech_to_text":e}, exc_info=True)
                    transcript = "Transcription couldn't be generated"
                    test_question_response.response_text = transcript

            end = time.time()
            logger.info(f"####################### _process_test_response: transcript generation for ANY: AUDIO took {end - start:.2f} #######################")

            if not test.is_free and (not test.is_transcript_only) and test.scenario_case != ScenarioCaseChoices.process_training :
                if transcript_length > 10:
                    if test.test_type == TestTypeChoices.trainer_thread:
                        threading.Thread(target=speech_metrics_in_thread, args=(test_question_response, transcript)).start()
                    else:
                        start = time.time()
                        max_tries = 2
                        retry = 0
                        while True:
                            try:
                                speech_met = coach_metric_api.get_speech_metrics_from_audio(
                                    test_question_response.response_file,transcript)
                                test_question_response.speech_metrics = speech_met

                                end = time.time()
                                logger.info(f"####################### _process_test_response: SPEECH METRICS For ANY: AUDIO took {end - start:.2f} #######################")
                                break
                            except Exception as e:
                                logger.exception(e)
                                retry += 1
                                if retry >= max_tries:
                                    # HACK sane default values
                                    test_question_response.speech_metrics = default_metrics
                                    logger.info("************************** _process_test_response: SPEECH METRICS failed for ANY: AUDIO. so assigned default values")
                                    break

                        
                else:
                    # HACK sane default values
                        test_question_response.speech_metrics = default_metrics

                update_fields.append("speech_metrics")

        test_question_response.save(update_fields=update_fields)
        
        if not test_question_response.response_text:
            test_question_response.save(update_fields=update_fields)

    if test.interaction_mode != InteractionModeChoices.text:
        update_fields = ["response_text", "updated"]
        if test.interaction_mode == InteractionModeChoices.audio:
            # try:
            #     test_question_response.response_text = coach_whisper_api.get_transcribe_from_audio(
            #         test_question_response.response_file)
            # except:
            if test_question_response.response_file:            
                start = time.time()
                transcript_length = 0
                try:
                    logger.info("*************** generating transcription for(audio) using gpt_wishper_api *****")
                    transcript = gpt_wishper_api(
                        test_question_response.response_file)
                    test_question_response.response_text = transcript
                    transcript_length = len(transcript.split())
                    logger.info({"message":"************ transcript generated ******","transcript":transcript})
                    end = time.time()
                    logger.info(f"####################### __process_test_response: transcript generation for AUDIO took {end - start:.2f} #######################")
                except Exception as e:
                    logger.error({"!!!!!!!!!!!!!!!!!Error while generating transcription from gpt_wishper_api":e}, exc_info=True)

                    try: 
                        logger.info("*************** generating transcription for(audio) using speech_to_text *****")
                        transcript = speech_to_text(test_question_response.response_file)
                        test_question_response.response_text = transcript
                    except Exception as e:
                        logger.error({"!!!!!!!!!!!!!!!!!Error while generating transcription from speech_to_text":e}, exc_info=True)
                        transcript = "Transcription couldn't be generated"
                        test_question_response.response_text = transcript

                end = time.time()
                logger.info(f"####################### _process_test_response: transcript generation for AUDIO took {end - start:.2f} #######################")

                if not test.is_free and (not test.is_transcript_only) and test.scenario_case != ScenarioCaseChoices.process_training:
                    if transcript_length > 10:
                        if test.test_type == TestTypeChoices.trainer_thread:
                            threading.Thread(target=speech_metrics_in_thread, args=(test_question_response, transcript)).start()
                        else:
                            start = time.time()
                            max_tries = 2
                            retry = 0
                            while True:
                                try:
                                    speech_met = coach_metric_api.get_speech_metrics_from_audio(
                                        test_question_response.response_file,transcript)
                                    test_question_response.speech_metrics = speech_met

                                    end = time.time()
                                    logger.info(f"####################### _process_test_response: SPEECH METRICS For AUDIO took {end - start:.2f} #######################")
                                    break
                                except Exception as e:
                                    logger.exception(e)
                                    retry += 1
                                    if retry >= max_tries:
                                        # HACK sane default values
                                        test_question_response.speech_metrics = default_metrics
                                        logger.info("************************** _process_test_response: SPEECH METRICS failed for AUDIO. so assgned default values")
                                        break

                            
                    else:
                        # HACK sane default values
                            test_question_response.speech_metrics = default_metrics

                    update_fields.append("speech_metrics")

        elif test.interaction_mode == InteractionModeChoices.video:
            # test_question_response.response_text = coach_whisper_api.get_transcribe_from_video(
            #     test_question_response.response_file)
            if test_question_response.response_file:
                start = time.time()
                transcript_length = 0
                try:
                    logger.info("****************** generating transcription for(video) using gpt_wishper_api *****")
                    transcript = gpt_wishper_api(
                        test_question_response.response_file)
                    test_question_response.response_text = transcript
                    transcript_length = len(transcript.split())
                    logger.info({"message":"**************** transcript generated ******","transcript":transcript})
                    end = time.time()
                    logger.info(f"####################### _process_test_response: transcript generation for VIDEO took {end - start:.2f} #######################")
                except Exception as e:
                    logger.error({"!!!!!!!!!!!!!!!!!Error while generating transcription from gpt_wishper_api":e}, exc_info=True)

                    try: 
                        logger.info("*************** generating transcription for(video) using speech_to_text *****")
                        transcript = speech_to_text(test_question_response.response_file)
                        test_question_response.response_text = transcript
                        end = time.time()
                        logger.info(f"####################### _process_test_response: transcript generation for VIDEO took {end - start:.2f} #######################")
                    except Exception as e:
                        logger.error({"!!!!!!!!!!!!!!!!!Error while generating transcription from speech_to_text":e}, exc_info=True)
                        transcript = "Transcription couldn't be generated"
                        test_question_response.response_text = transcript

                if not test.is_free and (not test.is_transcript_only) and test.scenario_case != ScenarioCaseChoices.process_training:
                    if transcript_length > 10:
                        if test.test_type == TestTypeChoices.trainer_thread:
                            threading.Thread(target=speech_metrics_in_thread, args=(test_question_response, transcript)).start()
                        else:
                            start = time.time()
                            max_tries = 2
                            retry = 0
                            while True:
                                try:
                                    speech_met_video = coach_metric_api.get_speech_metrics_from_video(
                                        test_question_response.response_file,transcript)
                                    test_question_response.speech_metrics = speech_met_video
                                    end = time.time()
                                    logger.info(f"####################### _process_test_response: SPEECH METRICS For VIDEO took {end - start:.2f} #######################")
                                    break

                                except Exception as e:
                                    retry += 1
                                    if retry >= max_tries:
                                        # HACK sane default values
                                        test_question_response.speech_metrics = default_metrics
                                        logger.info("************************** _process_test_response: SPEECH METRICS failed for VIDIO. so assgned default values")
                                        break

                    else:
                        test_question_response.speech_metrics = default_metrics
                        
                    update_fields.append("speech_metrics")

        test_question_response.save(update_fields=update_fields)

        if not test_question_response.response_text:
            test_question_response.save(update_fields=update_fields)

    updated_fields = ["evaluation_status", "updated"]
    if test.scenario_case != "feedback_role_play":
        user_info = UserAttribute.objects.get(user_id=test_attempt_session.participant_id)
        difficulty_level = user_info.difficulty_level
        user_feedback_prompt = ''
        if difficulty_level == 'easy':
            user_feedback_prompt = user_info.easy_feedback_prompt
        elif difficulty_level == 'critical':
            user_feedback_prompt == user_info.critical_feedback_prompt

        if user_info.custom_feedback_prompt_1:
            user_feedback_prompt = user_feedback_prompt + "\n" + user_info.custom_feedback_prompt_1
        if user_info.custom_feedback_prompt_2:
            user_feedback_prompt = user_feedback_prompt + "\n" + user_info.custom_feedback_prompt_2

        if test.is_email_type:
            prompt = get_email_type_prompt(
                test_title=test.title,
                test_description=test.description,
                question=question.question,
                candidate_reply=test_question_response.response_text,
                user_feedback_prompt=user_feedback_prompt)
            
        elif test.scenario_case == ScenarioCaseChoices.employee_feedback:
            prompt = emplyee_feedback_prompt(
                    prompt_template=question.gpt_prompt_override or test.gpt_prompt_override,
                    test_title=test.title,
                    test_description=test.description,
                    question=question.question,
                    candidate_reply=test_question_response.response_text,
                    user_feedback_prompt=user_feedback_prompt
            )

        else:
            if question.gpt_prompt_override or test.gpt_prompt_override:
                prompt = get_overridden_prompt(
                    prompt_template=question.gpt_prompt_override or test.gpt_prompt_override,
                    test_title=test.title,
                    test_description=test.description,
                    question=question.question,
                    question_context=question.subjective_answer,
                    candidate_reply=test_question_response.response_text,
                    user_feedback_prompt=user_feedback_prompt
                )
            else:
                prompt = get_chat_conversation_prompt_v3(
                    test_title=test.title,
                    test_description=test.description,
                    question=question.question,
                    question_context=question.subjective_answer,
                    candidate_reply=test_question_response.response_text,
                    user_feedback_prompt=user_feedback_prompt)


        feedback_text = ''
        raw_text = ''
        response_text = test_question_response.response_text
        go_for_feedback = True

        words = word_tokenize(test_question_response.response_text)

        if len(words) <= 10 :
            feedback_text = "No feedback can be generated because of too low response length"
            go_for_feedback = False

        if test.scenario_case == ScenarioCaseChoices.process_training or (test.is_transcript_only):
            feedback_text = "No feedback..."
            go_for_feedback = False
        
        if go_for_feedback:
            start = time.time()
            for i  in range(3):
                
                logger.info(f"tring feedback generation for {i+1} time")

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
                                candidate_reply=test_question_response.response_text,
                                user_feedback_prompt=user_feedback_prompt)
                            
                        elif test.scenario_case == ScenarioCaseChoices.employee_feedback:
                            prompt = emplyee_feedback_prompt(
                                    prompt_template=question.gpt_prompt_override or test.gpt_prompt_override,
                                    test_title=test.title,
                                    test_description=test.description,
                                    question=question.question,
                                    candidate_reply=test_question_response.response_text,
                                    user_feedback_prompt=user_feedback_prompt
                            )

                        else:
                            if question.gpt_prompt_override or test.gpt_prompt_override:
                                prompt = get_overridden_prompt(
                                    prompt_template=question.gpt_prompt_override or test.gpt_prompt_override,
                                    test_title=test.title,
                                    test_description=test.description,
                                    question=question.question,
                                    question_context=question.subjective_answer,
                                    candidate_reply=response_text,
                                    user_feedback_prompt=user_feedback_prompt
                                )
                            else:
                                prompt = get_chat_conversation_prompt_v3(
                                    test_title=test.title,
                                    test_description=test.description,
                                    question=question.question,
                                    question_context=question.subjective_answer,
                                    candidate_reply=response_text,
                                    user_feedback_prompt=user_feedback_prompt)

                    max_retry -= 1


                if test.is_free:
                    anthropic_feedback = anthropic_completion(prompt, 1200)
                    if anthropic_feedback:
                        feedback_text = anthropic_feedback
                    else:
                        feedback_text = 'Feedback could not be generated'
                
                else:
                    try:
                        feedback_text = text_bison_compeletion(prompt)
                    except Exception as e:
                        logger.exception(e)
                        anthropic_feedback = anthropic_completion(prompt, 1200) 
                        if not anthropic_feedback:
                            try:
                                feedback_text = gpt3_completion(prompt, stop=["USER:", "CoachBot"]).text
                            except Exception as e:
                                logger.exception(e)
                                feedback_text = "Feedback could not be generated"

                        else:
                            feedback_text = anthropic_feedback
                            raw_text = anthropic_feedback

                    # gpt_feedback = gpt3_completion(prompt, stop=["USER:", "CoachBot"])
                    # if not gpt_feedback.text:
                    #     try:
                    #         feedback_text = text_bison_compeletion(prompt)
                    #     except Exception as e:
                    #         logger.exception(e)
                    #         anthropic_feedback = anthropic_completion(prompt, 1200)
                    #         # feedback_text = "Feedback couldn't be generated Because of server overload. You may try after few minutes or you can choose to complete this interaction as well."
                    #         feedback_text = anthropic_feedback
                    # else:
                    #     feedback_text = gpt_feedback.text
                    #     raw_text = gpt_feedback.raw


                if "Unfortunately I cannot provide" not in feedback_text and "Very short responses are unrealistic" not in feedback_text and "PLEASE RESPOND WITH RELEVANCE" not in feedback_text and len(feedback_text.split()) < 250:
                    continue

                end = time.time()
                logger.info(f"######################## _process_response: fetching FEEDBACK  took {end - start:.2f} ########################")
                break


        test_question_response.metadata = {
            "gpt": {
                "prompt": prompt,
                "response": {
                    "raw": raw_text,
                    "text": feedback_text,
                }
            }
        }

        feedback_text = re.sub(r'\([^)]*\)', '', feedback_text)   # to remove any word limit in ()
        test_question_response.feedback_text = feedback_text
        updated_fields.append("feedback_text")
        updated_fields.append("metadata")

    if test.is_pitch:
        threading.Thread(target=set_language_skills_in_thread, args=(test_question_response.response_text,test_attempt_session)).start()


    test_question_response.evaluation_status = TestQuestionResponseEvaluationStatusChoices.success
    test_question_response.save(
        update_fields=updated_fields)
    
    if test_question_response != TestQuestionResponseEvaluationStatusChoices.success:
        test_question_response.save(
        update_fields=updated_fields)

    # Evaluating TestResponse based on skills required in the question [SAM CHANGES]
    # required_skills = question.key_learning_skills.split(",")
    # required_skills = [skill.strip() for skill in required_skills if skill]
    # required_skills = [skill.lower() for skill in required_skills if skill]

    # skills_rating = {}

    # skills_rating, is_evaluated = evaluate_response(
    #     test_question_response,
    #     question.question,
    #     test_question_response.response_text,
    #     required_skills,
    #     test.description,
    #     test.title,
    #     test.test_code,
    #     test_attempt_session.uid
    # )


    # instead of calculating relevace from skill we are now getting it 
    # from another prompt and skill for individual qustion is deprecated
    # because now we are cal skill_ratings at the end of conversation
    if test.test_type == TestTypeChoices.trainer_thread:
        threading.Thread(target=evaluate_relevence_thread, args=(question, test_question_response, test, test_attempt_session)).start()
        if test.scenario_case == ScenarioCaseChoices.process_training:
            threading.Thread(target=evaluate_rating_thread, args=(question, test_question_response, test, test_attempt_session)).start()
    else:
        if test.scenario_case == ScenarioCaseChoices.process_training:
            evaluate_rating_thread(question, test_question_response, test, test_attempt_session)

        relevancy_score = {}
        if test.is_free:
            relevancy_score, is_evaluated = evaluate_relevacy(test_question_response,
                                                question.question,
                                                test_question_response.response_text,
                                                test.description,
                                                test.title,
                                                True
                                                )
        else:
            relevancy_score, is_evaluated = evaluate_relevacy(test_question_response,
                                                question.question,
                                                test_question_response.response_text,
                                                test.description,
                                                test.title,
                                                )

        if not is_evaluated:
            test_question_response.evaluation_status = TestQuestionResponseEvaluationStatusChoices.failed
            # delete this response
            delete_test_response(test_question_response)
            logger.error("failed to get relevancy_score, got %s", relevancy_score)
            raise ValueError("failed to get relevancy_score json for %s",
                            test_question_response.uid)

        relevance = 1
        if "relevance" in relevancy_score:
            relevance = int(relevancy_score['relevance'])  # taking relevance and deleting it form json
    

        # # Removing the skills which are not required in the question
        # _to_be_deleted = []
        # for key in skills_rating.keys():
        #     if key not in required_skills:
        #         _to_be_deleted.append(key)

        # for key in _to_be_deleted:
        #     del skills_rating[key]

        # # If skill rating score is greater than 8.5 then we are setting it to 8.5
        # for skill in skills_rating:
        #     if skills_rating[skill] > 8.5:
        #         skills_rating[skill] = 8.5
        #     elif skills_rating[skill] < 1.5:
        #         skills_rating[skill] = 1.5

        # # Calculating the average score of the response
        # response_avg_score = 0
        # skills_count = 0
        # for skill in skills_rating:
        #     if isinstance(skills_rating[skill], str):
        #         continue

        #     response_avg_score += skills_rating[skill] or random.randint(3, 7)
        #     skills_count += 1

        # if skills_count == 0:
        #     response_avg_score = 0
        # else:
        #     response_avg_score = response_avg_score / skills_count

        # # Save skills rating and average score in TestQuestionResponse
        # test_question_response.skills_rating = skills_rating
        # test_question_response.avg_score = response_avg_score
        test_question_response.relevance = relevance
        test_question_response.save(update_fields=["relevance"])

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
        if test.scenario_case == ScenarioCaseChoices.process_training or test.is_transcript_only:
            test_attempt_session.finished_at = timezone.now()
            test_attempt_session.save(update_fields=['finished_at']) 

            total_responses = TestQuestionResponse.objects.filter(
                test_attempt_session_id=test_attempt_session.uid,
                deleted=0
            )

            # Get the object from SkillsRating table where participant_id = participant_id and of it doesn't exist then create it
            skills_rating_object, is_created = SkillsRating.objects.get_or_create(participant_id=test_attempt_session.participant_id,
                                                                                tenant_id=test_attempt_session.tenant_id)

            updated_fields = []
            skills_rating_object.total_questions_attempted += int(total_responses.count())
            skills_rating_object.total_tests_attempted += 1

            updated_fields.append("total_questions_attempted")
            updated_fields.append("total_tests_attempted")
            updated_fields.append("updated")

            skills_rating_object.save(update_fields=updated_fields)
        else:
            calc_score(test_attempt_session, test)

        if test.is_free:
            report_url = generate_summary_feedback_session_report_link(test_attempt_session, test)
        else:
            report_url = generate_session_report_link(test_attempt_session, test)

        # if test.email_address_list:
        #     send_report_link_to_email(
        #         test, test_attempt_session, report_url, is_whatsapp)

        # if is_whatsapp and test.test_type != TestTypeChoices.interview:
        #     send_report_link_to_whatsapp(
        #         test, test_attempt_session, report_url)

    logger.info(f"{test_attempt_session.uid} - end __process_test_response")


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
    print("########################## process_orchestrated_test_response_by_user: test.interaction_mode",test.interaction_mode)
    # for whatsapp only
    if test.interaction_mode == InteractionModeChoices.text:
        response = test_question_response.response_file
        if response:
            transcript = ''
            try:
                transcript = gpt_wishper_api(response)
            except Exception as e:
                logger.error(e)
                try:
                    transcript = speech_to_text(test_question_response.response_file)
                except Exception as e:
                    logger.error(e)
                    transcript = "Transcript Couldn't be generated."

            test_question_response.response_text = transcript
            update_fields.append('response_text')

    if test.interaction_mode != InteractionModeChoices.text:
        update_fields.extend(["response_text"])

        if test.interaction_mode == InteractionModeChoices.audio:
            # try:
            #     test_question_response.response_text = coach_whisper_api.get_transcribe_from_audio(
            #         test_question_response.response_file)
            # except:
            if test_question_response.response_file:
                start = time.time()
                transcript_length = 0
                try:
                    logger.info("*************** generating transcription for(audio) using gpt_wishper_api *****")
                    transcript = gpt_wishper_api(
                        test_question_response.response_file)
                    test_question_response.response_text = transcript
                    transcript_length = len(transcript.split())
                    logger.info({"message":"************ transcript generated ******","transcript":transcript})
                    end = time.time()
                    logger.info(f"####################### process_orchestrated_test_response_by_user: transcript generation for AUDIO took {end - start:.2f} #######################")
                except Exception as e:
                    logger.error({"!!!!!!!!!!!!!!!!!Error while generating transcription from gpt_wishper_api":e}, exc_info=True)

                    try: 
                        logger.info("*************** generating transcription for(audio) using speech_to_text *****")
                        transcript = speech_to_text(test_question_response.response_file)
                        test_question_response.response_text = transcript
                    except Exception as e:
                        logger.error({"!!!!!!!!!!!!!!!!!Error while generating transcription from speech_to_text":e}, exc_info=True)
                        transcript = "Transcription couldn't be generated"
                        test_question_response.response_text = transcript
                if not test.is_free:
                    if transcript_length > 10:
                        start = time.time()
                        max_tries = 2
                        retry = 0
                        while True:
                            try:
                                speech_met = coach_metric_api.get_speech_metrics_from_audio(
                                    test_question_response.response_file,transcript)
                                test_question_response.speech_metrics = speech_met
                                end = time.time()
                                logger.info(f"####################### process_orchestrated_test_response_by_user: SPEECH METRICS For AUDIO took {end - start:.2f} #######################")
                                break
                            except Exception as e:
                                logger.exception(e)
                                retry += 1
                                if retry >= max_tries:
                                    # HACK sane default values
                                    test_question_response.speech_metrics = default_metrics
                                    logger.info("************************** process_orchestrated_test_response_by_user SPEECH METRICS failed for AUDIO. so assgned default values")
                                    break

                            
                    else:
                        # HACK sane default values
                            test_question_response.speech_metrics = default_metrics

                    update_fields.append("speech_metrics")

        elif test.interaction_mode == InteractionModeChoices.video:
            # test_question_response.response_text = coach_whisper_api.get_transcribe_from_video(
            #     test_question_response.response_file)
            if test_question_response.response_file:
                start = time.time()
                transcript_length = 0
                try:
                    logger.info("****************** generating transcription for(video) using gpt_wishper_api *****")
                    transcript = gpt_wishper_api(
                        test_question_response.response_file)
                    test_question_response.response_text = transcript
                    transcript_length = len(transcript.split())
                    logger.info({"message":"**************** transcript generated ******","transcript":transcript})
                    end = time.time()
                    logger.info(f"####################### process_orchestrated_test_response_by_user: transcript generation for VIDEO took {end - start:.2f} #######################")
                except Exception as e:
                    logger.error({"!!!!!!!!!!!!!!!!!Error while generating transcription from gpt_wishper_api":e}, exc_info=True)

                    try: 
                        logger.info("*************** generating transcription for(video) using speech_to_text *****")
                        transcript = speech_to_text(test_question_response.response_file)
                        test_question_response.response_text = transcript
                    except Exception as e:
                        logger.error({"!!!!!!!!!!!!!!!!!Error while generating transcription from speech_to_text":e}, exc_info=True)
                        transcript = "Transcription couldn't be generated"
                        test_question_response.response_text = transcript
                if not test.is_free:
                    if transcript_length > 10:
                        start = time.time()
                        max_tries = 2
                        retry = 0
                        while True:
                            try:
                                speech_met_video = coach_metric_api.get_speech_metrics_from_video(
                                    test_question_response.response_file,transcript)
                                test_question_response.speech_metrics = speech_met_video
                                end = time.time()
                                logger.info(f"####################### process_orchestrated_test_response_by_user: SPEECH METRICS For VIDEO took {end - start:.2f} #######################")
                                break

                            except Exception as e:
                                retry += 1
                                if retry >= max_tries:
                                    # HACK sane default values
                                    test_question_response.speech_metrics = default_metrics
                                    logger.info("************************** process_orchestrated_test_response_by_user: SPEECH METRICS failed for VIDIO. so assgned default values")
                                    break

                    else:
                        test_question_response.speech_metrics = default_metrics
                        
                    update_fields.append("speech_metrics")

        elif test.interaction_mode == InteractionModeChoices.any:
            
            if test_question_response.response_file:
                start = time.time()
                transcript_length = 0
                try:
                    logger.info("*************** generating transcription for(any interaction mode) using gpt_wishper_api *****")
                    transcript = gpt_wishper_api(
                        test_question_response.response_file)
                    test_question_response.response_text = transcript
                    transcript_length = len(transcript.split())
                    logger.info({"message":"************ transcript generated ******","transcript":transcript})
                    end = time.time()
                    logger.info(f"####################### process_orchestrated_test_response_by_user: transcript generation for AUDIO took {end - start:.2f} #######################")
                except Exception as e:
                    logger.error({"!!!!!!!!!!!!!!!!!Error while generating transcription from gpt_wishper_api":e}, exc_info=True)

                    try: 
                        logger.info("*************** generating transcription for(any interaction mode) using speech_to_text *****")
                        transcript = speech_to_text(test_question_response.response_file)
                        test_question_response.response_text = transcript
                    except Exception as e:
                        logger.error({"!!!!!!!!!!!!!!!!!Error while generating transcription from speech_to_text":e}, exc_info=True)
                        transcript = "Transcription couldn't be generated"
                        test_question_response.response_text = transcript
                if not test.is_free:
                    if transcript_length > 10:
                        start = time.time()
                        max_tries = 2
                        retry = 0
                        while True:
                            try:
                                speech_met = coach_metric_api.get_speech_metrics_from_audio(
                                    test_question_response.response_file,transcript)
                                test_question_response.speech_metrics = speech_met
                                end = time.time()
                                logger.info(f"####################### process_orchestrated_test_response_by_user: SPEECH METRICS For AUDIO took {end - start:.2f} #######################")
                                break
                            except Exception as e:
                                logger.exception(e)
                                retry += 1
                                if retry >= max_tries:
                                    # HACK sane default values
                                    test_question_response.speech_metrics = default_metrics
                                    logger.info("************************** process_orchestrated_test_response_by_user SPEECH METRICS failed for AUDIO. so assgned default values")
                                    break

                            
                    else:
                        # HACK sane default values
                            test_question_response.speech_metrics = default_metrics

                    update_fields.append("speech_metrics")


    if test.test_type == TestTypeChoices.dynamic_discussion:
        start = time.time()
        logger.info(f"***************question number is {question.question_number}**************")
        start_with_user_message = test.orchestrated_conversation_details.get('start_with_user')
        background = test.orchestrated_conversation_details.get('background')
        if question.question_number == 1 and start_with_user_message is not None:
            question_text = test.description
        elif question.question_number == 1:
            question_text = test.orchestrated_conversation_details.get('initial_messages')[0]
        else:
            question_text = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session.uid).order_by("-created")[1].response_text
        logger.info(f"***************question text is {question_text}**************")

        if start_with_user_message is not None:
            prompt = get_user_first_dynamic_discussion_prompt(start_with_user_message, test.title, test.description, test_question_response.response_text,question_text, question.question_number)

        else:
            if background is not None:
                prompt = get_interview_feedback(test.title, test.description, background,question_text,test_question_response.response_text)
            else:
                if question.gpt_prompt_override or test.gpt_prompt_override:
                    prompt = get_overridden_prompt(
                        prompt_template=question.gpt_prompt_override or test.gpt_prompt_override,
                        test_title=test.title,
                        test_description=test.description,
                        question=question.question,
                        question_context=question.subjective_answer,
                        candidate_reply=test_question_response.response_text,
                        user_feedback_prompt=""
                    )
                else:
                    prompt = get_chat_conversation_prompt_v3(
                                        test_title=test.title,
                                        test_description=test.description,
                                        question=question_text,
                                        question_context=question.subjective_answer,
                                        candidate_reply=test_question_response.response_text,
                                        user_feedback_prompt="")
        
        feedback_text = generic_completion(prompt,1200, "Feedback could not be generated",test.is_free)
            
        test_question_response.feedback_text = feedback_text
        update_fields.append("feedback_text")
        logger.info(f"************dynamic discussion feedback : {feedback_text}")

        relevancy_score, is_evaluated = evaluate_relevacy(test_question_response,
                                            question_text,
                                            test_question_response.response_text,
                                            test.description,
                                            test.title,
                                            test.is_free
                                            )

        relevance = 1
        if "relevance" in relevancy_score:
            relevance = int(relevancy_score['relevance'])

        test_question_response.relevance = relevance
        update_fields.append("relevance")

        if not test.is_free:

            kls_prompt = f"pick most suitable 2 skills for this question: {question_text} from the list of these skills : {test.skills_to_evaluate}. please separate them with comma. do not add extra sentence"
            logger.info(f"************dynamic discussion kls prompt : {kls_prompt}")
            kls = generic_completion(kls_prompt, 50,'no kls' )

            klp_prompt = f"""
                TestTitle: {test.title}
                Question: {question_text}

                For given "Question" and the "TestTitle" extract a key learning from an ideal answer to the "Question"  as "Output". The "Output" should be a single sentence with maximum 25 words, do not append it with "Key Learning:"
                """

            logger.info(f"************dynamic discussion klp prompt : {klp_prompt}")
            klp = generic_completion(klp_prompt, 50, 'no klp')
            
            test_question_response.kls_klp = {"kls":kls.strip(), "klp":klp.split(':')[-1].strip()}
            update_fields.append("kls_klp")
            logger.info(f"************dynamic discussion kls and klp : {test_question_response.kls_klp}")
            end = time.time()
            logger.info(f"####################### process_orchestrated_test_response_by_user: LOGIC for dynamic discussion took {end - start:.2f} #######################")

    update_fields.extend(["evaluation_status", "updated"])
    test_question_response.evaluation_status = TestQuestionResponseEvaluationStatusChoices.success
    test_question_response.save(update_fields=update_fields)

    total_questions = TestQuestion.objects.filter(
        test_id=test.uid, deleted=0).count()

    total_responses = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session.uid,
                                                          deleted=0).count()

    if total_questions == total_responses:
        start = time.time()
        test_attempt_session.status = TestAttemptSessionStatusChoices.completed
        test_attempt_session.save()
        calc_group_discussion_report_metrics(test_attempt_session, test)

        if test.is_free:
            report_url = generate_summary_feedback_session_report_link(test_attempt_session,test)
        else:
            if test.test_type == TestTypeChoices.dynamic_discussion:
                report_url = generate_dynamic_discussion_report_link(test_attempt_session)
            else:
                report_url = generate_meeting_report_link(test_attempt_session)
        # if test.email_address_list:
        #     send_report_link_to_email_orch(test,test_attempt_session,report_url)
        # Evaluate skills rating for the test attempt session and update skills table in that.
        end = time.time()
        logger.info(f"####################### process_orchestrated_test_response_by_user: LOGIC for 'total_questions == total_responses:' took {end - start:.2f} #######################")

    return test_question_response


##########################* Dynamic Thread ############################



@timeit
def get_transcript(test_question_response):
    transcript_length = 0
    transcript = ""
    try:
        logger.info("*************** generating transcription for(audio) using gpt_wishper_api *****")
        transcript = gpt_wishper_api(
            test_question_response.response_file)
        transcript_length = len(transcript.split())
        logger.info({"message":"************ transcript generated ******","transcript":transcript})
    except Exception as e:
        logger.error({"!!!!!!!!!!!!!!!!!Error while generating transcription from gpt_wishper_api":e}, exc_info=True)

        try: 
            logger.info("*************** generating transcription for(audio) using speech_to_text *****")
            transcript = speech_to_text(test_question_response.response_file)
        
        except Exception as e:
            logger.error({"!!!!!!!!!!!!!!!!!Error while generating transcription from speech_to_text":e}, exc_info=True)
            transcript = "Transcription couldn't be generated"

    return transcript, transcript_length


@timeit
def get_speech_metrics(test_question_response,transcript):
    max_tries = 2
    retry = 0
    while True:
        try:
            speech_met = coach_metric_api.get_speech_metrics_from_audio(
                test_question_response.response_file,transcript)
            test_question_response.speech_metrics = speech_met
            break
        except Exception as e:
            logger.exception(e)
            retry += 1
            if retry >= max_tries:
                # HACK sane default values
                test_question_response.speech_metrics = default_metrics
                logger.info("************************** process_orchestrated_test_response_by_user SPEECH METRICS failed for AUDIO. so assgned default values")
                break
    test_question_response.save(update_fields=["speech_metrics"])


@timeit
def get_feedback(question, test_question_response,question_text,test):
    start_with_user_message = test.orchestrated_conversation_details.get('start_with_user')
    background = test.orchestrated_conversation_details.get('background')

    
    if start_with_user_message is not None:
            prompt = get_user_first_dynamic_discussion_prompt(start_with_user_message, test.title, test.description, test_question_response.response_text,question_text, question.question_number)

    else:
        if background is not None:
            prompt = get_interview_feedback(test.title, test.description, background, question_text, test_question_response.response_text)
        else:
            if question.gpt_prompt_override or test.gpt_prompt_override:
                prompt = get_overridden_prompt(
                    prompt_template=question.gpt_prompt_override or test.gpt_prompt_override,
                    test_title=test.title,
                    test_description=test.description,
                    question=question.question,
                    question_context=question.subjective_answer,
                    candidate_reply=test_question_response.response_text,
                    user_feedback_prompt=""
                )
            else:
                prompt = get_chat_conversation_prompt_v3(
                                    test_title=test.title,
                                    test_description=test.description,
                                    question=question_text,
                                    question_context=question.subjective_answer,
                                    candidate_reply=test_question_response.response_text,
                                    user_feedback_prompt="")
        
    test_question_response.feedback_text = generic_completion(prompt,1200, "Feedback could not be generated")
    logger.info(f"************dynamic discussion feedback : {test_question_response.feedback_text}")
    test_question_response.save(update_fields=["feedback_text"])


@timeit
def get_relevency_kls_klp(test_question_response, question_text, test):
    update_fields = []
    relevancy_score, is_evaluated = evaluate_relevacy(test_question_response,
                                            question_text,
                                            test_question_response.response_text,
                                            test.description,
                                            test.title,
                                            )

    relevance = 1
    if "relevance" in relevancy_score:
        relevance = int(relevancy_score['relevance'])

    test_question_response.relevance = relevance
    update_fields.append("relevance")

    kls_prompt = f"pick most suitable 2 skills for this question: {question_text} from the list of these skills : {test.skills_to_evaluate}. please separate them with comma. do not add extra sentence"
    logger.info(f"************dynamic discussion kls prompt : {kls_prompt}")
    kls = generic_completion(kls_prompt, 50, 'no kls',test.is_free)

    klp_prompt = f"""
        TestTitle: {test.title}
        Question: {question_text}

        For given "Question" and the "TestTitle" extract a key learning from an ideal answer to the "Question"  as "Output". The "Output" should be a single sentence with maximum 25 words, do not append it with "Key Learning:"
        """

    logger.info(f"************dynamic discussion klp prompt : {klp_prompt}")
    klp = generic_completion(klp_prompt, 50, 'no klp')
    
    test_question_response.kls_klp = {"kls":kls.strip(), "klp":klp.split(':')[-1].strip()}
    update_fields.append("kls_klp")
    logger.info(f"************dynamic discussion kls and klp : {test_question_response.kls_klp}")

    test_question_response.save(update_fields=update_fields)

@timeit
def process_dynamic_threads_response_by_user(test_question_response: TestQuestionResponse):
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

    total_questions = TestQuestion.objects.filter(
        test_id=test.uid, deleted=0).count()

    total_responses = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session.uid,
                                                            deleted=0).count()
    is_last_response = total_questions == total_responses

    logger.info(f"$$$$$$$$$$$$$$$$$$$$$$ is last respons is {is_last_response} $$$$$$$$$$$$$$")

    logger.info("$$$$$$$$$$$$$$$$$$$$$$$$4 Handled by dynamic thred $$$$$$$$$$$")
    update_fields = []
    if test.interaction_mode != InteractionModeChoices.text:
        update_fields.extend(["response_text"])

        if test.interaction_mode == InteractionModeChoices.audio:
            if test_question_response.response_file:
                transcript, transcript_length = get_transcript(test_question_response)
                test_question_response.response_text = transcript
                if not test.is_free:
                    if transcript_length > 10:
                        if is_last_response:
                            get_speech_metrics(test_question_response,transcript)
                        else:
                            threading.Thread(target=get_speech_metrics,
                                            kwargs={
                                                    "test_question_response":test_question_response,
                                                    "transcript":transcript
                                            }).start()
                    else:
                        test_question_response.speech_metrics = default_metrics

                    update_fields.append("speech_metrics")

        elif test.interaction_mode == InteractionModeChoices.video:
            if test_question_response.response_file:
                transcript, transcript_length = get_transcript(test_question_response)
                test_question_response.response_text = transcript

                if not test.is_free:
                    if transcript_length > 10:
                        if is_last_response:
                            get_speech_metrics(test_question_response,transcript)
                        else:
                            threading.Thread(target=get_speech_metrics,
                                            kwargs={
                                                    "test_question_response":test_question_response,
                                                    "transcript":transcript
                                            }).start()
                    else:
                        test_question_response.speech_metrics = default_metrics
                        
                    update_fields.append("speech_metrics")

        elif test.interaction_mode == InteractionModeChoices.any:
            if test_question_response.response_file:
            
                transcript, transcript_length = get_transcript(test_question_response)
                test_question_response.response_text = transcript

                if not test.is_free:
                    if transcript_length > 10:
                        if is_last_response:
                            get_speech_metrics(test_question_response,transcript)
                        else:
                            threading.Thread(target=get_speech_metrics,
                                            kwargs={
                                                    "test_question_response":test_question_response,
                                                    "transcript":transcript
                                            }).start()
                    else:
                        test_question_response.speech_metrics = default_metrics
                        
                    update_fields.append("speech_metrics")

    if test.test_type == TestTypeChoices.dynamic_discussion_thread:
        start = time.time()
        logger.info(f"***************question number is {question.question_number}**************")
        start_with_user_message = test.orchestrated_conversation_details.get('start_with_user')
        if question.question_number == 1 and start_with_user_message is not None:
            question_text = test.description
        elif question.question_number == 1:
            question_text = test.orchestrated_conversation_details.get('initial_messages')[0]
        else:
            question_text = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session.uid).order_by("-created")[1].response_text
        logger.info(f"***************question text is {question_text}**************")

        if is_last_response:
            get_feedback(question, test_question_response,question_text,test)
            if not test.is_free:
                get_relevency_kls_klp(test_question_response, question_text, test)
        else:
            threading.Thread(target=get_feedback,
                                kwargs={
                                        "question":question,
                                        "test_question_response":test_question_response,
                                        "question_text":question_text,
                                        "test":test
                                }).start()
            
            if not test.is_free:
                threading.Thread(target=get_relevency_kls_klp, kwargs={
                                    "test_question_response":test_question_response,
                                    "question_text":question_text,
                                    "test":test
                                }).start()
        
        end = time.time()
        logger.info(f"####################### process_dynamic_discussion_thread_response_by_user: LOGIC for dynamic discussion took {end - start:.2f} #######################")

    update_fields.extend(["evaluation_status", "updated"])
    test_question_response.evaluation_status = TestQuestionResponseEvaluationStatusChoices.success
    test_question_response.save(update_fields=update_fields)

    if total_questions == total_responses:
        start = time.time()
        test_attempt_session.status = TestAttemptSessionStatusChoices.completed
        test_attempt_session.save()
        calc_group_discussion_report_metrics(test_attempt_session, test)

        if test.is_free:
            report_url = generate_summary_feedback_session_report_link(test_attempt_session.test)

        else:
            if test.test_type == TestTypeChoices.dynamic_discussion_thread:
                report_url = generate_dynamic_discussion_report_link(test_attempt_session)
            else:
                report_url = generate_meeting_report_link(test_attempt_session)
        # if test.email_address_list:
        #     send_report_link_to_email_orch(test,test_attempt_session,report_url)
        # Evaluate skills rating for the test attempt session and update skills table in that.
        end = time.time()
        logger.info(f"####################### process_orchestrated_test_response_by_user: LOGIC for 'total_questions == total_responses:' took {end - start:.2f} #######################")

    return test_question_response


##########################* Dynamic Thread End ############################

@timeit
def process_orchestrated_test_response_by_bot_llm(test_question_response: TestQuestionResponse, is_whatsapp=False):
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

    start = time.time()
    prompt = get_orchestrated_test_conversation_prompt(test=test,
                                                       test_attempt_session=test_attempt_session,
                                                       question=question)
    logger.info(f"**************************************orchestrated test prompt******************************** : {prompt}")

    if is_whatsapp:
        bot_llm_response_text = gpt3_completion(prompt=prompt,stop=['user',"CoachBot"],max_tokens=1000).text
    else:
        bot_llm_response_text = generic_completion(prompt, 300, 'question could not be generated')

    end = time.time()
    logger.info(f"####################### process_orchestrated_test_response_by_bot_llm: LOGIC for generating next question took {end - start:.2f} #######################")

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


@timeit
def calc_group_discussion_report_metrics(test_attempt_session: TestAttemptSession, test: Test):

    temp_rating = {}
    skills_count = {}

    user_persona = test.orchestrated_conversation_details.get(
        "test_user_persona")
    objective = test.orchestrated_conversation_details.get("objective")

    chat_conversation = get_group_discussion_chat_conversation(
        test_attempt_session, user_persona)

    culture_skills_rating = evaluate_group_discussion_conversation(
        test_attempt_session, chat_conversation, user_persona, objective, test.test_code,test.is_free)


    # if culture_skills_rating score is greater than 8.5 then trim the score to 8.5
    for skill in culture_skills_rating:
        if culture_skills_rating[skill] > 8.5:
            culture_skills_rating[skill] = 8.5
        elif culture_skills_rating[skill] < 1.5:
            culture_skills_rating[skill] = 1.5

    skills_rating = evaluate_skills_group_discussion_conversation(
        test_attempt_session, chat_conversation, user_persona, objective, test.skills_to_evaluate,test.is_free)
    
    for skill in skills_rating:
        if skill in temp_rating:
            temp_rating[skill] += skills_rating[skill] or random.randint(3, 7)
            skills_count[skill] += 1
        else:
            temp_rating[skill] = skills_rating[skill] or random.randint(3, 7)
            skills_count[skill] = 1


    # If skills_rating score is greater than 8.5 then trim the score to 8.5
    # for skill in skills_rating:
    #     if skills_rating[skill] > 8.5:
    #         skills_rating[skill] = 8.5
    #     elif skills_rating[skill] < 1.5:
    #         skills_rating[skill] = 1.5


    skills_rating_score = {}
    # calculate average skills rating
    for skill in skills_rating:
        skills_rating_score[skill] = temp_rating[skill] / skills_count[skill]

    skills_rating = update_skills_rating_if_same_scores(skills_rating_score)

    culture_skills_rating = update_culture_skills_if_same_scores(
        culture_skills_rating)
    
    test_score = 0
    for skill in skills_rating:
        test_score += skills_rating[skill]

    avg_score = test_score / len(skills_rating.keys())
    culture_skills_rating = {key.capitalize() : value for key, value in culture_skills_rating.items()}

    test_attempt_session.culture_skills_rating = culture_skills_rating
    
    updated_fields = ["culture_skills_rating"
                      ,"test_score","avg_score","finished_at","updated"]

    skills_rating = {key.capitalize() : value for key, value in skills_rating.items()}
    if skills_rating:
        test_attempt_session.skills_rating = skills_rating
        updated_fields.append("skills_rating")

    # if skills_explanation:
    #     test_attempt_session.skills_explanation = skills_explanation
    #     updated_fields.append("skills_explanation")

    # if culture_skills_explanation:
    #     test_attempt_session.culture_skills_explanation = culture_skills_explanation
    #     updated_fields.append("culture_skills_explanation")

    responses = TestQuestionResponse.objects.filter(
        test_attempt_session_id=test_attempt_session.uid,
        responder_type='user',
        deleted=0
    )
    feedbacks = ''
    speech_score = {}
    has_speech_metric = False
    attempted_count = 0
    speech_count = 0
    for response in responses:
        if response.feedback_text:
            feedbacks += response.feedback_text + '\n'

        if not test.is_free:

            if response.speech_metrics:
                speech_count += 1
                has_speech_metric = True
                # get speech metrics from this response
                response_speech_metrics = response.speech_metrics
                # response_speech_metrics = {k: v for k, v in response_speech_metrics.items(
                # ) if k in ['fluency_percentage', 'pace','power_word_percentage','filler_word_percentage', 'silence_number']}

                try:
                    for key,value in response_speech_metrics.items():
                        if isinstance(value, str) and "%" in value:
                            try: 
                                value = float(value.replace("%", ""))
                            except:
                                pass
                                
                        if key in speech_score:
                            speech_score[key] += value or random.randint(3, 7)
                        else:
                            speech_score[key] = value or random.randint(3, 7)

                except Exception as e :
                    has_speech_metric = False
                    logger.error({"calc for speech matrix failed :" : e}, exc_info=True)

        attempted_count += 1

    # calculating feedback_summary and skill summary
    # skills_summary = calulate_summary_for_culture_and_normal_skill(test_attempt_session,culture_skills_rating,skills_rating)
    # if len(skills_summary) > 0:
    #     test_attempt_session.culture_and_skill_summary = skills_summary
    #     updated_fields.append("culture_and_skill_summary")
    

    # feedbacks_summary = feedback_summary(test_attempt_session,feedbacks)
    # if len(feedbacks_summary) > 0:
    #     test_attempt_session.feedback_summary = feedbacks_summary
    #     updated_fields.append("feedback_summary")
    if speech_count != int(responses.count()):
        has_speech_metric = False

    if not test.is_free:
        start = time.time()
        meeting_summary = get_group_discussion_summary(
            objective, chat_conversation)
        updated_fields.append("meeting_summary")
        areas_of_improvement = get_areas_of_improvement(
            objective, chat_conversation, user_persona)
        updated_fields.append("areas_of_improvement")
        test_attempt_session.meeting_summary = meeting_summary
        test_attempt_session.areas_of_improvement = areas_of_improvement
        end = time.time()
        logger.info(f"####################### calc_group_discussion_report_metrics: LOGIC for get meeting_summary and areas_of_improvement took {end - start:.2f} #######################")
    
    if has_speech_metric:
        test_attempt_session.speech_score = speech_score
        updated_fields.append("speech_score")

    
    test_attempt_session.finished_at = timezone.now()
    test_attempt_session.test_score = test_score
    test_attempt_session.avg_score = avg_score

    test_attempt_session.save(update_fields=updated_fields)

    # Get the object from SkillsRating table where participant_id = participant_id and of it doesn't exist then create it
    skills_rating_object, is_created = SkillsRating.objects.get_or_create(participant_id=test_attempt_session.participant_id,
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
    print(skills_rating,avg_score,test_score,skills_rating_object.uid )

    skills_rating_object.save(update_fields=updated_fields)


    return test_attempt_session


@timeit
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
    flashcards = []
    start_with_user_message = test.orchestrated_conversation_details.get('start_with_user')
    speech_metrics_avg = {}
    response_relevance = True


    if test.test_type in [ TestTypeChoices.dynamic_discussion, TestTypeChoices.dynamic_discussion_thread ]:
        start = time.time()
        all_speech_metrics = []
        data = {}
        mindmap_data = {}
        mindmap_contents = []
        count = 1
        test_responses = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session.uid,
                                                                evaluation_status=TestQuestionResponseEvaluationStatusChoices.success,
                                                                deleted=0).order_by('id')
        for participant_response in test_responses:
            relevance = participant_response.relevance
            if not relevance :
                response_relevance = False
                break


        test_data = []
        for test_response in test_responses:
            test_data.append({'response':test_response.response_text,'responder_type':test_response.responder_type,'feedback':test_response.feedback_text,})
        logger.info({"************test_responses":test_data})
        for test_response in test_responses:
            if test_response.responder_type == QuestionForChoices.user:
                if count == 1:
                    if start_with_user_message is not None:
                        data[f"question"] = test.description
                    else:
                        data[f"question"] = chat_conversation[0].split(":", 1)[1].strip('" \'')
                data["response"] = test_response.response_text.strip('" \'')
                data["feedback"] = re.sub(r'\([^)]*\)', '',  test_response.feedback_text)
                key_learning_point = test_response.kls_klp.get('klp')
                flashcards.append({'text':key_learning_point})
                chat_conversation_with_details.append(data)
                count += 1
                mindmap_contents.append(
                    {
                        "question":data["question"],
                        "ideal_answer": key_learning_point,
                        "learnings": test_response.kls_klp.get('kls').strip().split(','),
                    }
                )
                data = {}
                
            else:
                data[f"question"] = test_response.response_text.split(':')[-1].strip('" \'')

            
            if test_response.speech_metrics:
                speech_metrics = test_response.speech_metrics

                # We only need ['pace', 'filler_word_percentage', 'power_word_percentage', 'silence_number','fluency_percentage'] from speech_metrics
                speech_metrics = {k: v for k, v in speech_metrics.items(
                ) if k in ['fluency_percentage', 'pace','power_word_percentage','filler_word_percentage', 'silence_number']}

                # Convert the Keys to human readable format
                speech_metrics = {k.replace("_", " ").title(
                ): v for k, v in speech_metrics.items()}

                # Add the speech_metrics to the list of all_speech_metrics
                all_speech_metrics.append(speech_metrics)

        # Get the averaged speech metrics for the test attempt session
        for metric in all_speech_metrics:
            for k, v in metric.items():
                if isinstance(v, str) and "%" in v:
                    try:
                        v = float(v.replace("%", ""))
                    except:
                        pass

                if k in speech_metrics_avg:
                    speech_metrics_avg[k] += v
                else:
                    speech_metrics_avg[k] = v

        if test_responses[0].speech_metrics:
            for k, v in speech_metrics_avg.items():
                speech_metrics_avg[k] = v / len(test_responses)

        end = time.time()
        logger.info(f"####################### get_meeting_report_from_test_attempt_session: LOGIC for dynamic discussion REPORT took {end - start:.2f} #######################")


    else:
        for message in chat_conversation:
            user_name, message = message.split(":", 1)
            is_bot = False

            if user_name.strip().lower() != user_persona.strip().lower():
                is_bot = True
            else:
                user_name = 'User'

            chat_conversation_with_details.append(
                {"user_name": user_name, "message": message, "is_bot": is_bot})

    meeting_summary = test_attempt_session.meeting_summary
    areas_of_improvement = test_attempt_session.areas_of_improvement
    culture_skills = test_attempt_session.culture_skills_rating
    culture_skills = {key.strip('"\'' ): value for key, value in culture_skills.items()}  # to strip extra qoutes from key

    data = {
        "participant_name": participant_name,
        "date": date,
        "title": title,
        "objective": objective,
        "chat_conversation": chat_conversation_with_details,
        "meeting_summary": meeting_summary,
        "areas_of_improvement": areas_of_improvement,
        "culture_skills": culture_skills,
        # "skills_explanation": update_skill_name(test_attempt_session.skills_explanation),
        # "culture_skills_explanation":test_attempt_session.culture_skills_explanation,
        "feedback_summary" : test_attempt_session.feedback_summary,
        "skill_summary" : test_attempt_session.culture_and_skill_summary,
        "start_with_user": False if start_with_user_message is None else True,
        "speech_metrics_avg" : speech_metrics_avg,
        "response_relevance" : response_relevance
    }

    if data["start_with_user"]:
        data["bot_name"] = test.orchestrated_conversation_details.get('initial_messages')[0].split(":", 1)[0].strip('" \'')
        data["candidate_type"] = test.candidate_type

    # skill_exp = update_skill_name(test_attempt_session.skills_explanation)
    skill_exp = test_attempt_session.skills_explanation

    if skill_exp:
        if len(test_attempt_session.skills_rating) == len(skill_exp):
            data['skills_explanation'] = skill_exp
        else:
            data['skills_explanation'] = None

    culture_skill_exp = test_attempt_session.culture_skills_explanation
    if culture_skill_exp:
        if len(test_attempt_session.culture_skills_rating) == len(culture_skill_exp):
            data['culture_skills_explanation'] = culture_skill_exp
        else:
            data['culture_skills_explanation'] = None

    if test.test_type in [ TestTypeChoices.dynamic_discussion, TestTypeChoices.dynamic_discussion_thread ]:
        data['flashcards'] = flashcards
        data['mindmap_data'] = {
            "test_name": test.title,
            "content": mindmap_contents
        }
        
    if test_attempt_session.skills_rating:
        skills_rating = test_attempt_session.skills_rating
        skills_rating = {key.strip('"\'' ): value for key, value in skills_rating.items()}  # to strip extra qoutes from key

        # updated_skills_ratings = {}
        # existing_skills = []
        # for skill, values in skills_rating.items():
        #     for old , new in updated_skills.items():
        #         if skill.strip().capitalize() == old.strip().capitalize():
        #             updated_skills_ratings[new.strip()] = values
        #             existing_skills.append(skill)
        #         else:
        #             updated_skills_ratings[skill] = values

        # for i  in existing_skills:
        #     del updated_skills_ratings[i]
        
        # data["skills_rating"] = update_skill_name(skills_rating)
        data["skills_rating"] = skills_rating
        
    data["certificate_details"] = test.certificate_details
    data['ui_information'] = test.ui_information

    return data


@timeit
def get_group_discussion_summary(objective: str, chat_conversation: str):
    prompt = f"""
    \n\nHuman:
    [Objective of Discussion]: {objective};
    [Conversation]: {chat_conversation};

    Please provide a summary of the meeting in 100 words.
    NOTE: Please do NOT provide any introductions, conclusion or text like "Here is your summary". 
    NOTE: Please only provide the summary of the meeting.
    \n\nAssistant:
    """

    cnt = 0
    summary = ""

    while cnt < 1:
        try:
            summary = generic_completion(prompt, 200, "Could not generate")
            break
        except Exception as e:
            logger.exception(e)
            cnt += 1

    if cnt == 1:
        summary = "Could not generate"

    return summary


@timeit
def get_areas_of_improvement(objective: str, chat_conversation: str, user_persona: str):
    areas_of_improvement = ["Sticking to Agenda",
                            "Driving to decision", "Sticking to Positive behavior"]

    prompt = f"""
    \n\nHuman:
    [Objective of Discussion]: {objective};
    [Conversation]: {chat_conversation};

    Based on the discussion above please analyze the efficiency and efficacy of the meeting as it relates to the following parameters:{areas_of_improvement}. Please comment the output in seperate paragraphs where the paragraph headings are {areas_of_improvement} and values are the paragraphs explaining each heading respectively. Include what went well and where are the areas of improvment. Do not provide any introductions and conclusion. Each paragraph must be 50-70 words appropriately.
    
    PLEASE NOTE that you may evaluate the {areas_of_improvement} parameters for the {user_persona} persona only. Do not evaluate any other characters.
    NOTE: Do not include any mentions of word count requirements or limits in your response.

    OUTPUT FORMAT:
    Sticking to Agenda
    <paragraph>

    Driving to decision
    <paragraph>

    Sticking to Positive behavior
    <paragraph>
    \n\nAssistant:
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


@timeit
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


@timeit
def _calc_score(test_attempt_session: TestAttemptSession, test: Test):
    """
    This function calculates the score for the test attempt session and update the skills_rating field in this object
    Also it uses these skills rating to update the skills table
    """

    logger.info(f"{test_attempt_session.uid} - start last response calculation")
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
    feedbacks = ''

    # For calculating average score of the test
    avg_score = 0
    response_count = 0
    speech_count = 0

    for response in responses:
        # if response.skills_rating is None:
        #     continue

        # # get skills rating from this response
        # response_skills_rating = response.skills_rating
        # response_avg_score = response.avg_score

        # if response_avg_score:
        #     avg_score += response_avg_score
        #     response_count += 1
        if not test.is_free:
            if response.speech_metrics:
                speech_count += 1
                has_speech_metric = True
                # get speech metrics from this response
                response_speech_metrics = response.speech_metrics
                # response_speech_metrics = {k: v for k, v in response_speech_metrics.items(
                # ) if k in ['fluency_percentage', 'pace','power_word_percentage','filler_word_percentage', 'silence_number']}

                try:
                    for key,value in response_speech_metrics.items():
                        if isinstance(value, str) and "%" in value:
                            try: 
                                value = float(value.replace("%", ""))
                            except:
                                pass
                                
                        if key in speech_score:
                            speech_score[key] += value or random.randint(3, 7)
                        else:
                            speech_score[key] = value or random.randint(3, 7)

                except Exception as e :
                    has_speech_metric = False
                    logger.error({"calc for speech matrix failed :" : e}, exc_info=True)


            # joining every feedback for summary

            if response.feedback_text:
                feedbacks += response.feedback_text + "\n"




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

    if speech_count != int(responses.count()):
        has_speech_metric = False


    questions = TestQuestion.objects.filter(test_id=test_attempt_session.test_id,deleted=0)
    if test.scenario_case == ScenarioCaseChoices.pms:
        evaluate_competency_data_thread(questions,responses,test,test_attempt_session)
    skills_=[]
    for question in questions:
        required_skills = question.key_learning_skills.split(",")
        required_skills = [skill.strip() for skill in required_skills if skill]
        required_skills = [skill.lower() for skill in required_skills if skill]
        for s in required_skills:
            skills_.append(s)

    user_info = UserAttribute.objects.get(user_id=test_attempt_session.participant_id)
    difficulty_level = user_info.difficulty_level
    user_skill_prompt = ''
    if difficulty_level == 'easy':
        user_skill_prompt = user_info.easy_skill_prompt
    elif difficulty_level == 'critical':
        user_skill_prompt == user_info.critical_skill_prompt

    if user_info.custom_skill_prompt_1:
        user_skill_prompt = user_skill_prompt + "\n" + user_info.custom_skill_prompt_1
    if user_info.custom_skill_prompt_2:
        user_skill_prompt = user_skill_prompt + "\n" + user_info.custom_skill_prompt_2

    response_skills_rating = calc_skills_rating(test_attempt_session, responses, test,skills_,user_skill_prompt)
    response_skills_rating = {key.capitalize() : value for key, value in response_skills_rating.items()}
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

    logger.info({"***************************skills_rating_score":skills_rating_score})

    skills_rating_score, avg_score = increment_avg_score_in_percentages(
        skills_rating_score, avg_score, participant_id, test_attempt_session)
    skills_rating_score = update_skills_rating_if_same_scores(
        skills_rating_score)
    avg_score = sum(skills_rating_score.values()) / len(skills_rating_score)
    test_score = 0
    for skill in skills_rating_score:
        test_score += skills_rating_score[skill]


    culture_skills_rating = calc_culture_skills_rating(test_attempt_session, responses, test)

    logger.info({"***************************culture_skills_rating_score":culture_skills_rating})

    culture_skills_rating = update_culture_skills_if_same_scores(
        culture_skills_rating)

    # update skills_rating field in test_attempt_session
    skills_rating_score = {key.strip('"\'' ): value for key, value in skills_rating_score.items()}  # to strip extra qoutes from key
    skills_rating_score = {key.capitalize() : value for key, value in skills_rating_score.items()}
    
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

    # if skills_explanation is not None:
    #     test_attempt_session.skills_explanation = skills_explanation
    #     updated_fields.append("skills_explanation")

    if culture_skills_rating is not None:
        culture_skills_rating = {key.strip('"\'' ): value for key, value in culture_skills_rating.items()}  # to strip extra qoutes from key
        culture_skills_rating = {key.capitalize() : value for key, value in culture_skills_rating.items()}
        test_attempt_session.culture_skills_rating = culture_skills_rating
        updated_fields.append("culture_skills_rating")

    # if culture_skills_explanation is not None:
    #     test_attempt_session.culture_skills_explanation = culture_skills_explanation
    #     updated_fields.append("culture_skills_explanation")



    # calculating feedback_summary and skill summary
    # skills_summary = calulate_summary_for_culture_and_normal_skill(test_attempt_session,culture_skills_rating,skills_rating_score)
    # if len(skills_summary) > 0:
    #     test_attempt_session.culture_and_skill_summary = skills_summary
    #     updated_fields.append("culture_and_skill_summary")
    

    # feedbacks_summary = feedback_summary(test_attempt_session,feedbacks)
    # if len(feedbacks_summary) > 0:
    #     test_attempt_session.feedback_summary = feedbacks_summary
    #     updated_fields.append("feedback_summary")

    test_attempt_session.save(update_fields=updated_fields)
    
    if not test_attempt_session.finished_at:
        test_attempt_session.save(update_fields=updated_fields)



    if not test.is_self_created:
        # Get the object from SkillsRating table where participant_id = participant_id and of it doesn't exist then create it
        skills_rating_object, is_created = SkillsRating.objects.get_or_create(participant_id=participant_id,
                                                                            tenant_id=test_attempt_session.tenant_id)

        updated_fields = []

        skills_rating_object.skills_info = skills_rating_object.skills_info or {}
        total_test_attmepted = skills_rating_object.total_tests_attempted

        for skill, rating in skills_rating_score.items():

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

        if skills_rating_object.total_tests_attempted == total_test_attmepted:
            skills_rating_object.save(update_fields=updated_fields)

    logger.info(f"{test_attempt_session.uid} - end last response calculation")
    


def round_off_rating(number):
    return round(number * 2) / 2


@timeit
def increment_avg_score_in_percentages(skills_rating, avg_score, participant_id, test_attempt_session):
    # Get number of interactions for that candidate which are completed but are not the current one
    total_successful_sessions = TestAttemptSession.objects.filter(participant_id=participant_id,
                                                                  status=TestAttemptSessionStatusChoices.completed,
                                                                  deleted=0).exclude(uid=test_attempt_session.uid).exclude(finished_at=None)

    total_successful_sessions_count = total_successful_sessions.count()

    if total_successful_sessions_count == 1:
        return skills_rating, avg_score

    # Calculate the average score of last 5 interactions
    last_5_sessions = total_successful_sessions.order_by(
        "-finished_at")[:5]

    last_5_sessions_avg_score = 0

    for session in last_5_sessions:
        last_5_sessions_avg_score += session.avg_score or random.randint(3,7)

    if total_successful_sessions_count >=5:
        last_5_sessions_avg_score = last_5_sessions_avg_score / 5
    else:
        try:
            last_5_sessions_avg_score = last_5_sessions_avg_score / total_successful_sessions_count
        except:
            pass


    if last_5_sessions_avg_score < 5:
        return skills_rating, avg_score

    increase_by_percent = min(total_successful_sessions_count, 10)
    # 1 -> 1%, 2 -> 2%, 3 -> 3%, 4 -> 4%, 5 -> 5%, 6 -> 6%, 7 -> 7%, 8 -> 8%, 9 -> 9%, 10 -> 10%, 11 -> 10%, 12 -> 10%, 13 -> 10%, 14 -> 10%, 15 -> 10%, 16 -> 10%, 17 -> 10%, 18 -> 10%, 19 -> 10%, 20 -> 10%

    for skill in skills_rating:
        if skills_rating[skill] < 8:
            skills_rating[skill] = skills_rating[skill] + \
                                (skills_rating[skill] * increase_by_percent / 100)

            skills_rating[skill] = min(10, skills_rating[skill])
            skills_rating[skill] = round_off_rating(skills_rating[skill])

    avg_score = sum(skills_rating.values()) / len(skills_rating)
    avg_score = round_off_rating(avg_score)
    avg_score = min(10.0, avg_score)

    return skills_rating, avg_score


@timeit
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

    report_type = ReportType.INTERACTION_SESSION_REPORT
    if test.test_type == TestTypeChoices.mcq:
        report_type = ReportType.DecisionAnalysisReport
    elif test.scenario_case == ScenarioCaseChoices.process_training:
        report_type = ReportType.ProcessTrainingReport

    report_url = f"{FRONTEND_BASE_URL}/{report_type}/{refresh_token}/?session_id={test_attempt_session_id}&interaction_id={test_id}&backend={BACKEND}"

    test_attempt_session.report_url = report_url
    test_attempt_session.save(update_fields=["report_url"])

    return report_url


@timeit
def generate_summary_feedback_session_report_link(test_attempt_session: TestAttemptSession, test: Test):
    if test_attempt_session.report_url:
        return test_attempt_session.report_url

    test_id = test_attempt_session.test_id
    test_attempt_session_id = test_attempt_session.uid
    participant_id = test_attempt_session.participant_id

    tokens = create_new_tokens('user-report', 'uid', participant_id)
    refresh_token = tokens["refresh"]

    logger.info("[Refresh Token Generation] generated refresh token %s for participant %s",
                refresh_token[:6], participant_id)

    report_url = f"{FRONTEND_BASE_URL}/{ReportType.SUMMARY_FEEDBACK_REPORT}/{refresh_token}/?session_id={test_attempt_session_id}&interaction_id={test_id}&backend={BACKEND}"

    test_attempt_session.report_url = report_url
    test_attempt_session.save(update_fields=["report_url"])
    return report_url

@timeit
def generate_meeting_report_link(test_attempt_session: TestAttemptSession):
    if test_attempt_session.report_url:
        return test_attempt_session.report_url

    test_attempt_session_id = test_attempt_session.uid
    participant_id = test_attempt_session.participant_id

    tokens = create_new_tokens('user-report', 'uid', participant_id)
    refresh_token = tokens["refresh"]

    logger.info("[Refresh Token Generation] generated refresh token %s for participant %s",
                refresh_token[:6], participant_id)

    report_url = f"{FRONTEND_BASE_URL}/{ReportType.MEETING_ANALYSIS_REPORT}/{refresh_token}/?test_attempt_session_id={test_attempt_session_id}&backend={BACKEND}"

    test_attempt_session.report_url = report_url
    test_attempt_session.save(update_fields=["report_url"])

    return report_url


@timeit
def generate_dynamic_discussion_report_link(test_attempt_session: TestAttemptSession):
    if test_attempt_session.report_url:
        return test_attempt_session.report_url

    test_attempt_session_id = test_attempt_session.uid
    participant_id = test_attempt_session.participant_id

    tokens = create_new_tokens('user-report', 'uid', participant_id)
    refresh_token = tokens["refresh"]

    logger.info("[Refresh Token Generation] generated refresh token %s for participant %s",
                refresh_token[:6], participant_id)

    report_url = f"{FRONTEND_BASE_URL}/{ReportType.DYNAMIC_DISCUSSOIN_REPORT}/{refresh_token}/?test_attempt_session_id={test_attempt_session_id}&backend={BACKEND}"

    test_attempt_session.report_url = report_url
    test_attempt_session.save(update_fields=["report_url"])

    return report_url



@timeit
def modify_skills_rating_if_same(skills):
    logger.info(f"skills before: {skills}")
    modified_skills = {}
    value_counts = {}
    start = time.time()

    for skill, value in sorted(skills.items(), key=lambda x: x[1]):
        # Modify the value to be unique and a multiple of 0.25
        while True:
            # Randomly decide whether to increase or decrease the value
            increment = 0.25 if random.choice([True, False]) else -0.25

            # Apply the increment until uniqueness is achieved
            while round(value, 2) in value_counts and value_counts[round(value, 2)] >= 2:
                value += increment
                if value >= 9 or value <= 1:
                    break

            if value >= 9:
                value -= 0.5
            if value <= 1:
                value += 0.5

            # Break out of the loop if the value is unique and less than 10
            if (round(value, 2) not in value_counts or value_counts[round(value, 2)] < 2) and round(value, 2) <= 9 and round(value, 2) >= 0:
                break
            
            end = time.time()
            if end - start > 2:
                logger.info(f"Too much Time taken to modify skills: {end - start:.2f}")
                break

        # Add the modified value to the count of occurrences
        value_counts[round(value, 2)] = value_counts.get(round(value, 2), 0) + 1

        # Round the final value to 2 decimal places and store in the result dictionary
        modified_skills[skill] = round(value, 2)

    logger.info(f"skills after: {modified_skills}")
    return modified_skills


@timeit
def update_skills_rating_if_same_scores(skills_rating):
    return modify_skills_rating_if_same(skills_rating)
    total_skills = len(skills_rating)
    scores_frequency = {}
    for skill in skills_rating:
        score = skills_rating[skill]
        if score in scores_frequency:
            scores_frequency[score].append(skill)
        else:
            scores_frequency[score] = [skill]

    # # modify skills if any three skills have same score
    # if any(len(scores_frequency[score]) >= 3 for score in scores_frequency):
    #     return modify_skills_rating_if_same(skills_rating)

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



@timeit
def update_culture_skills_if_same_scores(culture_skills_rating):
    return modify_skills_rating_if_same(culture_skills_rating)

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
        # if len(scores_frequency[score]) > len(cultural_skills) / 2:
        #     # Increment half the skills by 0.5 and other half decrement by 0.5
        #     for i in range(0, len(scores_frequency[score])):
        #         skill = scores_frequency[score][i]
        #         if i < len(scores_frequency[score]) / 2:
        #             culture_skills_rating[skill] = culture_skills_rating[skill] + 0.5
        #         else:
        #             culture_skills_rating[skill] = culture_skills_rating[skill] - 0.5
        if len(scores_frequency[score]) > 1:
            random.shuffle(scores_frequency[score])  # Randomly shuffle skills with same score
            # Increment half the skills by 0.5 and other half decrement by 0.5
            for i in range(0, len(scores_frequency[score])):
                skill = scores_frequency[score][i]
                if i < len(scores_frequency[score]) / 2:
                    if i < i/2:
                        culture_skills_rating[skill] = culture_skills_rating[skill] + 0.75   # changed 1 to 0.75 aug
                    else:
                        culture_skills_rating[skill] = culture_skills_rating[skill] - 0.75   

                elif i > len(scores_frequency[score]) / 2:
                    if i > i/2:
                        culture_skills_rating[skill] = culture_skills_rating[skill] + 0.25   # changed 1 to 0.25 aug
                    else:
                        culture_skills_rating[skill] = culture_skills_rating[skill] - 0.25   


                if culture_skills_rating[skill] < 0:
                    culture_skills_rating[skill] = 0

                if culture_skills_rating[skill] > 10:
                    culture_skills_rating[skill] = 10

    # if the score is greater than 9 then trim it to 9
    for skill in culture_skills_rating:
        if culture_skills_rating[skill] > 9:
            culture_skills_rating[skill] = 9

    return culture_skills_rating


@timeit
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


@timeit
def send_report_link_to_email_orch(test: Test, test_attempt_session: TestAttemptSession, report_url: str,
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

    

    for to_email in email_address_list:
        send_email(to_email, email_subject, data=data)

    logger.info("report emails sent successfully test_attempt_session: %s", test_attempt_session.uid)

    if test.email_candidate:
        try:
            send_email(participant_email, email_subject, data=data)
        except Exception as e:
            logger.exception("failed to send email to participant %s email %s, err: %s",
                             participant_id, participant_email, e)
            raise e

    test_attempt_session.is_report_sent_to_email = True
    test_attempt_session.save(update_fields=["is_report_sent_to_email"])


@timeit
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
        whatsapp_api.send_whatsapp_report(participant_phone, report_url,test_name)
    except Exception as e:
        logger.exception("failed to send whatsapp message to participant %s with phone %s, err: %s",
                         participant_id, participant_phone, e)
        raise e

    test_attempt_session.is_report_sent_to_whatsapp = True
    test_attempt_session.save(update_fields=["is_report_sent_to_whatsapp"])



@timeit
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
    if test.is_free:
        culture_skills_rating, is_evaluated = evaluate_conversation(
            test_attempt_session, conversation, test.title, test.description, test.test_code,True)
    else:
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


@timeit
def calc_skills_rating(test_attempt_session, responses, test,skills,user_skill_prompt):
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
    if test.is_free:
        skills_rating, is_evaluated = evaluate_response_skill(
            test_attempt_session, conversation, test.title, test.description, test.test_code,skills,user_skill_prompt,True)
    else:
        skills_rating, is_evaluated = evaluate_response_skill(
            test_attempt_session, conversation, test.title, test.description, test.test_code,skills,user_skill_prompt)

    if not is_evaluated:
        return None

    return skills_rating

@timeit
def get_interview_feedback(title,description,background, question_text,candidate_comment):
    prompt = Template("""
            \n\nHuman:

            Title: ${title}.

            Test Description: ${description}

            background: ${background}

            Question : ${question_text}

            Candidate Comment : ${candidate_comment}

            Please provide interview feedback for a candidate who has provided a "Candidate Comment" for an interview as specified in the "Test Description". Provide the feedback based on the information provided in "background”. Please provide feedback which specifically helps the candidate in an interview. The feedback should be structured in the following format:

            "Feedback for the candidate's responses : "

            Key insights to improve

            What went well ?

            What did not work ?

            A sample candidate answer

            Pro Interview Insights

            NOTE: The total number of words should be at the minimum 400 words and maximum 500 words. Provide the feedback exactly in the format and sections above.

            NOTE : Always consider the information provided in the "background" when generating the feedback

            NOTE : Provide the feedback in bullet points under each section except A sample candidate answer.

            NOTE: Do not include any mentions of word count requirements or limits in your response.

            NOTE: Only provide feedback on the "Candidate Comment" not on the "Test Description."

            NOTE : A sample candidate answer is a sample Candidate comment based on the context provided.

            NOTE: Please suggest any industry standard framework or derived methods that can strengthen the candidate’s answer in "Key insights to improve the response."

            NOTE : In cases where the "Candidate Comment" consists of less than 15 words, always add the following statement after the feedback: "Warning: Very short responses are unrealistic and may lead to poor quality feedback."

            NOTE : Minimum response length is 250 words. Always adhere to the same.

            NOTE: Before providing any feedback, check if the candidate's response is even slightly related to the question asked and described situation. Assign a response alignment score from 0-10. If the score is 0, ONLY print this warning message: "FEEDBACK GENERATED IF ANY, SHOULD BE IGNORED BECAUSE OF POOR RELEVANCE. PLEASE RESPOND WITH RELEVANCE."

            NOTE : NEVER give any kind of explanation, suggestions or summary in the output.

            NOTE : NEVER print the response alignment score in the output.
            \n\nAssistant
                """).substitute(
                    title=title,
                    description=description,
                    question_text=question_text,
                    candidate_comment= candidate_comment,
                    background=background
                )
    return prompt

@timeit
def get_chat_conversation_prompt_v3(test_title: str,
                                    test_description: str,
                                    question: str,
                                    question_context: str,
                                    candidate_reply: str,
                                    user_feedback_prompt:str):
    if question_context:
        template = Template(
            """
            \n\nHuman:
            Title: ${test_title}. 
            Test Description: ${test_description}
            Customer question:  ${question} 
            Expert Suggestions:  ${question_context} 
            Candidate answer:  ${candidate_reply}
    
            Please provide communication and subject matter feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on "Expert suggestions",  "Title" , only if they are relevant to the situation. The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the responder. The feedback should be structured in the following format: 
            - Key insights to improve the response

            - What went well ?

            - What did not work ?

            - A sample candidate answer

            - A counter intuitive insight

            NOTE: The total number of words should be at the minimum 400 words and maximum 500 words. Provide the feedback exactly in the format and sections above.
            NOTE: Do not include any mentions of word count requirements or limits in your response.
            NOTE: Never give any feedback on the Question or anybody asking the question.
            NOTE: Please suggest any industry standard framework or derived methods that can strengthen the managers answer in "Key insights to improve the response."
            

            ${user_feedback_prompt}
            \n\nAssistant:
            """
        )
        return template.substitute(test_title=test_title,
                                   test_description=test_description,
                                   question=question,
                                   question_context=question_context,
                                   candidate_reply=candidate_reply,
                                   user_feedback_prompt=user_feedback_prompt)
    else:
        template = Template(
            """
            \n\nHuman:
            Title: ${test_title}. 
            Test Description: ${test_description}
            Customer question:  ${question} 
            Candidate answer:  ${candidate_reply}
            
            Please provide communication and subject matter feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on "Title" , only if they are relevant to the situation. The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the responder. The feedback should be structured in the following format: 
            - Key insights to improve the response

            - What went well ?

            - What did not work ?

            - A sample candidate answer

            - A counter intuitive insight

            NOTE: The total number of words should be at the minimum 400 words and maximum 500 words. Provide the feedback exactly in the format and sections above.           
            NOTE: Do not include any mentions of word count requirements or limits in your response.
            NOTE: Never give any feedback on the Question or anybody asking the question.
            NOTE: Please suggest any industry standard framework or derived methods that can strengthen the managers answer in "Key insights to improve the response."
            
            ${user_feedback_prompt}
            \n\nAssistant:
            """
        )
        # log template for debugging
        return template.substitute(test_title=test_title,
                                   test_description=test_description,
                                   question=question,
                                   candidate_reply=candidate_reply,
                                   user_feedback_prompt=user_feedback_prompt)


@timeit
def get_user_first_dynamic_discussion_prompt(scenareo, test_title: str, test_description: str, comment: str, bot_response:str, question_number: int):
    match scenareo:
        case 'manager-team':
            if question_number == 1:
                template = Template(
                """
                    \n\nHuman:
                    Title: ${title}.

                    Test Description: ${description}

                    Manager Comment: ${manager_context}

                    Please provide communication and subject matter feedback for a manager who has provided a "Manager Comment" as specified for the "Test Description". The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the manager. The feedback should be structured in the following format:

                    "Feedback for the manager comments/responses : "

                    Key insights to improve the response

                    What went well ?

                    What did not work ?

                    A sample candidate answer

                    A counter intuitive insight

                    NOTE: The total number of words should be at the minimum 400 words and maximum 500 words. Provide the feedback exactly in the format and sections above.

                    NOTE : Provide the feedback in bullet points under each section except A sample candidate answer.

                    NOTE: Do not include any mentions of word count requirements or limits in your response.

                    NOTE: Only provide feedback on the "Manager Comment" not on the "Test Description."

                    NOTE : If the Manager Comment is a question provide feedback on how the manager can ask better questions.

                    NOTE : A sample candidate answer is a sample Manager comment based on the context provided.

                    NOTE: Please suggest any industry standard framework or derived methods that can strengthen the managers answer in "Key insights to improve the response."

                    NOTE : In cases where the "Candidate answer" consists of less than 15 words, always add the following statement after the feedback: "Warning: Very short responses are unrealistic and may lead to poor quality feedback."

                    NOTE : Minimum response length is 300 words. Always adhere to the same.

                    NOTE : Check if the response provided is somewhat relevant to the question or completely irrelevant. If the response is completely irrelevant, start the feedback with the sentence: "FEEDBACK GENERATED IF ANY, SHOULD BE IGNORED BECAUSE OF POOR RELEVANCE. PLEASE RESPOND WITH RELEVANCE". No additional text should be added. DO NOT give any other feedback.

                    NOTE : Never start with any kind of introductory sentence.

                    NOTE : Do not provide any kind of heading or introduction text in the output. Start directly with the feedback and only provide the feedback.

                    NOTE : NEVER include sentences like (Here is the feedback for the candidate's response:) in the output.
                    \n\nAssistant:
                """
                        )
                return template.substitute(title=test_title, description=test_description,
                                            manager_context=comment)

            template = Template(
            '''
            \n\nHuman:
            Title: ${title}.

            Test Description: ${description}

            Bot response : ${bot_response}

            Manager Comment : ${manager_context}

            Please provide communication and subject matter feedback for a manager who has provided a "Manager Comment". Feedback must be based on test description and conversation so far. The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the responder. The feedback should be structured in the following format:

            "Feedback for the manager comments/responses : "

            Key insights to improve the response

            What went well ?

            What did not work ?

            A sample candidate answer

            A counter intuitive insight

            NOTE: The total number of words should be at the minimum 400 words and maximum 500 words. Provide the feedback exactly in the format and sections above.

            NOTE : Provide the feedback in bullet points under each section except A sample candidate answer.

            NOTE: Do not include any mentions of word count requirements or limits in your response.

            NOTE: Only provide feedback on the "Manager Comment". 

            NOTE : NEVER give any feedback on the "Bot response"

            NOTE : If the Manager Comment is a question, provide feedback on how the manager can ask better questions.

            NOTE : A sample candidate answer is a sample Manager Comment based on the context provided.

            NOTE : Minimum response length is 300 words. Always adhere to the same.

            NOTE: Please suggest any industry standard framework or derived methods that can strengthen the managers answer in "Key insights to improve the response."

            NOTE : If the "Manager Comment" consists of less than 15 words, always add the following statement at the end of the feedback: "Warning: Very short responses are unrealistic and may lead to poor quality feedback."

            NOTE : Check if the response provided by the Manager is somewhat relevant to the question or completely irrelevant. If the response is completely irrelevant, start the feedback with the sentence: "FEEDBACK GENERATED IF ANY, SHOULD BE IGNORED BECAUSE OF POOR RELEVANCE. PLEASE RESPOND WITH RELEVANCE". No additional text should be added. DO NOT give any other feedback.

            NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output. Start directly with the feedback and only provide the feedback.

            NOTE : NEVER include sentences like (Here is the feedback for the candidate's response:) in the output.
            \n\nAssistant:
            ''')

            
            return template.substitute(title=test_title, description=test_description,
                                        manager_context=comment, bot_response=bot_response)
            
        case 'team-manager':
            if question_number == 1:
                template = Template(
                """
                    \n\nHuman:
                    Title: ${title}.

                    Test Description: ${description}

                    Team Member Comment: ${team_comment}

                    Please provide communication and subject matter feedback for a team member who has provided a "Team Member Comment" as specified for the "Test Description". The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the team member. The feedback should be structured in the following format:

                    "Feedback for the team member's comments/responses : "

                    Key insights to improve the response

                    What went well ?

                    What did not work ?

                    A sample candidate answer

                    A counter intuitive insight

                    NOTE: The total number of words should be at the minimum 400 words and maximum 500 words. Provide the feedback exactly in the format and sections above.

                    NOTE : Provide the feedback in bullet points under each section except A sample candidate answer.

                    NOTE: Do not include any mentions of word count requirements or limits in your response.

                    NOTE: Only provide feedback on the "Team Member Comment" not on the "Test Description."

                    NOTE : If the Team Member Comment is a question provide feedback on how the team member can ask better questions.

                    NOTE : A sample candidate answer is a sample Team Member Comment based on the context provided.

                    NOTE: Please suggest any industry standard framework or derived methods that can strengthen the team members answer in "Key insights to improve the response."

                    NOTE : In cases where the "Team Member Comment" consists of less than 15 words, always add the following statement after the feedback: "Warning: Very short responses are unrealistic and may lead to poor quality feedback."

                    NOTE : Minimum response length is 300 words. Always adhere to the same.

                    NOTE : Check if the response provided is somewhat relevant to the question or completely irrelevant. If the response is completely irrelevant, start the feedback with the sentence: "FEEDBACK GENERATED IF ANY, SHOULD BE IGNORED BECAUSE OF POOR RELEVANCE. PLEASE RESPOND WITH RELEVANCE". No additional text should be added. DO NOT give any other feedback.

                    NOTE : Never start with any kind of introductory sentence.

                    NOTE : Do not provide any kind of heading or introduction text in the output. Start directly with the feedback and only provide the feedback.

                    NOTE : NEVER include sentences like (Here is the feedback for the candidate's response:) in the output.
                    \n\nAssistant:

                """
                        )
                return template.substitute(title=test_title, description=test_description,
                                            team_comment=comment)

            template = Template(
            '''
                \n\nHuman:
                Title: ${title}.

                Test Description: ${description}

                Bot response : ${bot_response}

                Team Member Comment : ${team_comment}

                Please provide communication and subject matter feedback for a team member who has provided a "Team Member". Feedback must be based on test description and conversation so far. The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the team member. The feedback should be structured in the following format:

                "Feedback for the team member comments/responses : "

                Key insights to improve the response

                What went well ?

                What did not work ?

                A sample candidate answer

                A counter intuitive insight

                NOTE: The total number of words should be at the minimum 400 words and maximum 500 words. Provide the feedback exactly in the format and sections above.

                NOTE : Provide the feedback in bullet points under each section except A sample candidate answer.

                NOTE: Do not include any mentions of word count requirements or limits in your response.

                NOTE: Only provide feedback on the "Team Member". 

                NOTE : NEVER give any feedback on the "Bot response"

                NOTE : If the Team Member Comment is a question, provide feedback on how the team member can ask better questions.

                NOTE : A sample candidate answer is a sample Team Member Comment based on the context provided.

                NOTE : Minimum response length is 300 words. Always adhere to the same.

                NOTE: Please suggest any industry standard framework or derived methods that can strengthen the team member's response in "Key insights to improve the response."

                NOTE : If the "Team Member Comment" consists of less than 15 words, always add the following statement at the end of the feedback: "Warning: Very short responses are unrealistic and may lead to poor quality feedback."

                NOTE : Check if the response provided by the team member is somewhat relevant to the question or completely irrelevant. If the response is completely irrelevant, start the feedback with the sentence: "FEEDBACK GENERATED IF ANY, SHOULD BE IGNORED BECAUSE OF POOR RELEVANCE. PLEASE RESPOND WITH RELEVANCE". No additional text should be added. DO NOT give any other feedback.

                NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output. Start directly with the feedback and only provide the feedback.

                NOTE : NEVER include sentences like (Here is the feedback for the candidate's response:) in the output.
                \n\nAssistant:

            ''')

            
            return template.substitute(title=test_title, description=test_description,
                                        team_comment=comment, bot_response=bot_response)
        case 'sales-customer':
            if question_number == 1:
                template = Template(
                """
                    \n\nHuman:
                    Title: ${title}.

                    Test Description: ${description}

                    Sales rep Comment: ${sales_comment}

                    Please provide communication and subject matter feedback for a Sales rep who has provided a "Sales rep Comment" as specified for the "Test Description". The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the Sales rep. The feedback should be structured in the following format:

                    "Feedback for the Sales rep comments/responses : "

                    Key insights to improve the response

                    What went well ?

                    What did not work ?

                    A sample candidate answer

                    A counter intuitive insight

                    NOTE: The total number of words should be at the minimum 400 words and maximum 500 words. Provide the feedback exactly in the format and sections above.

                    NOTE : Provide the feedback in bullet points under each section except A sample candidate answer.

                    NOTE: Do not include any mentions of word count requirements or limits in your response.

                    NOTE: Only provide feedback on the "Sales rep Comment" not on the "Test Description."

                    NOTE : If the Sales rep Comment is a question provide feedback on how the Sales rep can ask better questions.

                    NOTE : A sample candidate answer is a sample Sales rep comment based on the context provided.

                    NOTE: Please suggest any industry standard framework or derived methods that can strengthen the Sales rep’s answer in "Key insights to improve the response."

                    NOTE : In cases where the "Candidate answer" consists of less than 15 words, always add the following statement after the feedback: "Warning: Very short responses are unrealistic and may lead to poor quality feedback."

                    NOTE : Minimum response length is 300 words. Always adhere to the same.

                    NOTE : Check if the response provided is somewhat relevant to the question or completely irrelevant. If the response is completely irrelevant, start the feedback with the sentence: "FEEDBACK GENERATED IF ANY, SHOULD BE IGNORED BECAUSE OF POOR RELEVANCE. PLEASE RESPOND WITH RELEVANCE". No additional text should be added. DO NOT give any other feedback.

                    NOTE : Never start with any kind of introductory sentence.

                    NOTE : Do not provide any kind of heading or introduction text in the output. Start directly with the feedback and only provide the feedback.

                    NOTE : NEVER include sentences like (Here is the feedback for the candidate's response:) in the output.
                    \n\nAssistant:

                """
                        )
                return template.substitute(title=test_title, description=test_description,
                                            sales_comment=comment)

            template = Template(
            '''
                \n\nHuman:
                Title: ${title}.

                Test Description: ${description}

                Bot response : ${bot_response}

                Sales rep Comment : ${sales_comment}

                Please provide communication and subject matter feedback for a Sales rep who has provided a "Sales rep". Feedback must be based on test description and conversation so far. The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the Sales rep. The feedback should be structured in the following format:

                "Feedback for the Sales rep comments/responses : "

                Key insights to improve the response

                What went well ?

                What did not work ?

                A sample candidate answer

                A counter intuitive insight

                NOTE: The total number of words should be at the minimum 400 words and maximum 500 words. Provide the feedback exactly in the format and sections above.

                NOTE : Provide the feedback in bullet points under each section except A sample candidate answer.

                NOTE: Do not include any mentions of word count requirements or limits in your response.

                NOTE: Only provide feedback on the "Sales rep".

                NOTE : NEVER give any feedback on the "Bot response"

                NOTE : If the Sales rep Comment is a question, provide feedback on how the Sales rep can ask better questions.

                NOTE : A sample candidate answer is a sample Sales rep Comment based on the context provided.

                NOTE : Minimum response length is 300 words. Always adhere to the same.

                NOTE: Please suggest any industry standard framework or derived methods that can strengthen the Sales rep's response in "Key insights to improve the response."

                NOTE : If the "Sales rep Comment" consists of less than 15 words, always add the following statement at the end of the feedback: "Warning: Very short responses are unrealistic and may lead to poor quality feedback."

                NOTE : Check if the response provided by the Sales rep is somewhat relevant to the question or completely irrelevant. If the response is completely irrelevant, start the feedback with the sentence: "FEEDBACK GENERATED IF ANY, SHOULD BE IGNORED BECAUSE OF POOR RELEVANCE. PLEASE RESPOND WITH RELEVANCE". No additional text should be added. DO NOT give any other feedback.

                NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output. Start directly with the feedback and only provide the feedback.

                NOTE : NEVER include sentences like (Here is the feedback for the candidate's response:) in the output.
                \n\nAssistant:

            ''')

            
            return template.substitute(title=test_title, description=test_description,
                                        sales_comment=comment, bot_response=bot_response)
        case 'customer-sales':
            return "something"
        case default:
            logger.warning("!!!!!!!!!!!!!!!!!! Invalid user_first scenareo type for geting feedback prompt: %s", scenareo)
            return "nothing"

@timeit
def get_user_first_question_promt(scenareo: str, test, test_attempt_session_id,current_conversation, question_number):
    match scenareo:
        case 'manager-team':
            if question_number == 2:
                user_comment = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session_id,
                                                                responder_type=QuestionForChoices.user,
                                                                deleted=0).first()
                template = Template(
                '''
                \n\nHuman:
                main_context: ${test_main_context}

                comment: ${user_comment}

                Provide a response to the user's comment as the team member based on the given context. Do not provide any feedback on the response. The response should prompt the conversation to move forward. Do not offer to schedule a meeting later this is an ongoing conversation.

                Always give a unique, different and specific response based on the user's comment. The response should be relevant to the information or question or answer given in the comment. Always give a response to understand the problem better or ask how to implement a solution to the problem.

                NOTE : NEVER provide the response in bullet points. Only provide the response in paragraphs.

                NOTE: The response should not be more than 25 words.

                NOTE: Do not show the word count.

                NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output.
                \n\nAssistant:
                '''
                )

                return template.substitute(test_main_context=test.description,
                                        user_comment=user_comment.response_text)
            else:
                user_comment = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session_id,
                                                                    evaluation_status=TestQuestionResponseEvaluationStatusChoices.success,
                                                                    deleted=0, responder_type=QuestionForChoices.user).order_by('id').last()
                template = Template(
                '''
                \n\nHuman:
                main_context: ${test_main_context}
                current_conversation: ${current_conversation}
                comment: ${user_comment}

                Provide a response to the user's comment as the team member based on the given context. Do not provide any feedback on the response. The response should prompt the conversation to move forward. Do not offer to schedule a meeting later this is an ongoing conversation.

                Always give a unique, different and specific response based on the user's comment. The response should be relevant to the information or question or answer given in the comment. Always give a response to understand the problem better or ask how to implement a solution to the problem.

                NOTE : NEVER provide the response in bullet points. Only provide the response in paragraphs.

                NOTE: The response should not be more than 25 words.

                NOTE: Do not show the word count.

                NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output.
                \n\nAssistant:
                '''
                )

                return template.substitute(test_main_context=test.description,
                                        user_comment=user_comment.response_text, current_conversation=current_conversation)
        case 'team-manager':
            if question_number == 2:
                user_comment = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session_id,
                                                                responder_type=QuestionForChoices.user,
                                                                deleted=0).first()
                template = Template(
                '''
                \n\nHuman:
                main_context: ${test_main_context}}

                comment: ${user_comment}

                Provide a response to the user's comment as the manager based on the given context for an ongoing conversation. Do not provide any feedback on the response.
                The response should prompt the conversation to move forward. Do not offer to schedule a meeting later this is an ongoing conversation.

                Always give a unique, different and specific response based on the user's comment. The response should be relevant to the information or question or answer given in the comment. Always give a response to understand the problem better or ask how to implement a solution to the problem.

                NOTE : NEVER provide the response in bullet points. Only provide the response in paragraphs.

                NOTE: The response should not be more than 25 words.

                NOTE: Do not show the word count.

                NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output.
                \n\nAssistant:
                '''
                )

                return template.substitute(test_main_context=test.description,
                                        user_comment=user_comment.response_text)
            else:
                user_comment = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session_id,
                                                                    evaluation_status=TestQuestionResponseEvaluationStatusChoices.success,
                                                                    deleted=0, responder_type=QuestionForChoices.user).order_by('id').last()
                template = Template(
                '''
                \n\nHuman:
                 main_context: ${test_main_context}

                current_conversation: ${current_conversation}

                comment: ${user_comment}

                Provide a response to the user's comment as the manager based on the given context for an ongoing conversation. Do not provide any feedback on the response.
                The response should prompt the conversation to move forward. Do not offer to schedule a meeting later this is an ongoing conversation.

                Always give a unique, different and specific response based on the user's comment. The response should be relevant to the information or question or answer given in the comment. Always give a response to understand the problem better or ask how to implement a solution to the problem.
                
                NOTE : NEVER provide the response in bullet points. Only provide the response in paragraphs.

                NOTE: The response should not be more than 25 words.

                NOTE: Do not show the word count.

                NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output.
                \n\nAssistant:
                '''
                )

                return template.substitute(test_main_context=test.description,
                                        user_comment=user_comment.response_text, current_conversation=current_conversation)
        case 'sales-customer':
            if question_number == 2:
                user_comment = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session_id,
                                                                responder_type=QuestionForChoices.user,
                                                                deleted=0).first()
                template = Template(
                '''
                \n\nHuman:
                main_context: ${test_main_context}

                comment: ${user_comment}

                Provide a response to the user's comment as the customer based on the given context. Do not provide any feedback on the response.
                The response should prompt the conversation to move forward. Do not offer to schedule a meeting later this is an ongoing conversation.

                Always give a unique, different and specific response based on the user's comment. The response should be relevant to the information or question or answer given in the comment. Always give a response to understand the problem better or ask how to implement a solution to the problem.

                NOTE : NEVER provide the response in bullet points. Only provide the response in paragraphs.

                NOTE: The response should not be more than 25 words.

                NOTE: Do not show the word count.

                NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output.
                \n\nAssistant:
                '''
                )

                return template.substitute(test_main_context=test.description,
                                        user_comment=user_comment.response_text)
            else:
                user_comment = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session_id,
                                                                    evaluation_status=TestQuestionResponseEvaluationStatusChoices.success,
                                                                    deleted=0, responder_type=QuestionForChoices.user).order_by('id').last()
                template = Template(
                '''
                \n\nHuman:
                main_context: ${test_main_context}

                current_conversation: ${current_conversation}

                comment: ${user_comment}

                Provide a response to the user's comment as the customer based on the given context. Do not provide any feedback on the response.
                The response should prompt the conversation to move forward. Do not offer to schedule a meeting later this is an ongoing conversation.

                Always give a unique, different and specific response based on the user's comment. The response should be relevant to the information or question or answer given in the comment. Always give a response to understand the problem better or ask how to implement a solution to the problem.

                NOTE : NEVER provide the response in bullet points. Only provide the response in paragraphs.

                NOTE: The response should not be more than 25 words.

                NOTE: Do not show the word count.

                NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output.
                \n\nAssistant:
                '''
                )

                return template.substitute(test_main_context=test.description,
                                        user_comment=user_comment.response_text, current_conversation=current_conversation)
        case 'customer-sales':
            return "something"
        case default:
            logger.warning("!!!!!!!!!!!!!!!!!! Invalid user_first scenareo type: %s", scenareo)
            return "nothing"


@timeit
def get_orchestrated_test_conversation_prompt(test: Test,
                                              test_attempt_session: TestAttemptSession,
                                              question: TestQuestion):
    test_main_context = test.orchestrated_conversation_details.get(
        "test_main_context")
    test_user_persona = test.orchestrated_conversation_details.get(
        "test_user_persona")
    initial_messages = test.orchestrated_conversation_details.get(
        "initial_messages")
    start_with_user_message = test.orchestrated_conversation_details.get('start_with_user')
    background = test.orchestrated_conversation_details.get('background')

    current_conversation = ''

    if start_with_user_message is None:
        for message in initial_messages:
            conv_text = message
            current_conversation = current_conversation + "\n" + conv_text
    # else:
    #     current_conversation += f"{test.candidate_type}:" + TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session.uid,
    #                                                             evaluation_status=TestQuestionResponseEvaluationStatusChoices.success,
    #                                                             deleted=0).order_by('id').first().response_text

    for test_response in TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session.uid,
                                                            #  evaluation_status=TestQuestionResponseEvaluationStatusChoices.success,
                                                             deleted=0):
        logger.info(f"test_response: {test_response.response_text}")

        response_uid = test_response.uid
        response_text = test_response.response_text
        if test_response.response_text is None:
            start_time = time.time()
            while True :
                end_time = time.time()
                if end_time - start_time > 30:
                    logger.error(
                        f"[Time Limit] Unable to evaluate response text: {response_uid}")
                    raise ValueError("unable to evaluate response text: %s",
                                 response_uid)
                # Check if response_text is populated
                respo_text = TestQuestionResponse.objects.get(uid = response_uid,deleted=0).response_text
                if respo_text is not None :
                    response_text = respo_text
                    logger.info(f'response_text populated : {respo_text}')
                    break 
                logger.info('waiting for response text')
                time.sleep(1)
        
        if test_response.responder_type == QuestionForChoices.user:
            conv_text = f"{test_user_persona}: {response_text}"
        else:
            conv_text = f"{test_response.responder_type}: {response_text}"

        current_conversation = current_conversation + "\n" + conv_text

    question_text = question.question
    
    logger.info({"******************************conversation":current_conversation, "question number is": question.question_number,
                "question_text": question_text})

    if test.test_type in [ TestTypeChoices.dynamic_discussion, TestTypeChoices.dynamic_discussion_thread ] and start_with_user_message is not None:
        return get_user_first_question_promt(start_with_user_message, test, test_attempt_session.uid, current_conversation, question.question_number)
        
        # logger.info("******************************************************************************* and now we are good")
        # # template = Template(
        # #         '''
        # #         main_context: ${test_main_context}
        # #         comment: ${user_comment}

        # #         NOTE: Based on the candidate comment and the main context ask the candidate another question. Do not provide any feedback on the response.

        # #         NOTE: The question should not be more than 30 words.

        # #         NOTE: Do not show the word count.

        # #         NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output. Start directly with the question and only provide the question.
        # #         '''
        # #     )

        # # return template.substitute(test_main_context=test_main_context,
        # #                             user_comment=user_comment.response_text)

        # if question.question_number == 2:
        #     user_comment = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session.uid,
        #                                                     responder_type=QuestionForChoices.user,
        #                                                     deleted=0).first()
        #     template = Template(
        #     '''
        #     main_context: ${test_main_context}

        #     comment: ${user_comment}

        #     Provide a response to the user's comment as the team member based on the given context. Do not provide any feedback on the response.

        #     NOTE : NEVER provide the response in bullet points. Only provide the response in paragraphs.

        #     NOTE: The response should not be more than 25 words.

        #     NOTE: Do not show the word count.

        #     NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output.
        #     '''
        #     )

        #     return template.substitute(test_main_context=test.description,
        #                             user_comment=user_comment.response_text)
        # else:
        #     user_comment = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session.uid,
        #                                                         evaluation_status=TestQuestionResponseEvaluationStatusChoices.success,
        #                                                         deleted=0, responder_type=QuestionForChoices.user).order_by('id').last()
        #     template = Template(
        #     '''
        #     main_context: ${test_main_context}
        #     current_conversation: ${current_conversation}
        #     comment: ${user_comment}

        #     Provide a response to the user's comment as the team member based on the given context. Do not provide any feedback on the response.

        #     NOTE : NEVER provide the response in bullet points. Only provide the response in paragraphs.

        #     NOTE: The response should not be more than 25 words.

        #     NOTE: Do not show the word count.

        #     NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output.
        #     '''
        #     )

        #     return template.substitute(test_main_context=test.description,
        #                             user_comment=user_comment.response_text, current_conversation=current_conversation)
    
    if test.test_type in [ TestTypeChoices.dynamic_discussion, TestTypeChoices.dynamic_discussion_thread ]:

        if background is not None: # for interview type test
            user_comment = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session.uid,
                                                                responder_type=QuestionForChoices.user,
                                                                deleted=0).order_by('id').last()
            
            template = Template(
                """
                \n\nHuman:
                main_context: ${test_main_context}

                background: ${background}

                candidate_comment: ${user_comment}

                Based on the Candidate response, and the main context ask the candidate the next question. The question should continue the Current conversation. Do not provide any feedback on the response.
                Always ask a unique, different and specific question based on Candidate response. The question should be relevant to the information or response given in Candidate response. Always ask a question that helps understand the problem better or ask how to implement a solution to the problem.

                NOTE : NEVER provide the question in bullet points. Only provide the question in paragraphs.


                NOTE : Always consider the information provided in the "background" when giving the next question.


                NOTE: The question should not be more than 25 words.

                NOTE: Do not show the word count.

                NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output.
                \n\nAssistant

                """
            ).substitute(test_main_context=test_main_context,
                         background=background,
                         user_comment=user_comment.response_text)

        else:

            template = Template(
                    '''
                    \n\nHuman:
                    Main context : ${test_main_context}
                    Current conversation : ${current_conversation}
                    Candidate response : ${question_text}

                    NOTE: Based on the Candidate response, and the main context ask the candidate the next question. The question should continue the Current conversation. Do not provide any feedback on the response.
                    Always ask a unique, different and specific question based on Candidate response. The question should be relevant to the information or response given in Candidate response. Always ask a question that helps understand the problem better or ask how to implement a solution to the problem.

                    NOTE: The question should not be more than 25 words.

                    NOTE: Do not show the word count.

                    NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output. Start directly with the question and only provide the question.
                    \n\nAssistant:
                    '''
                ).substitute(test_main_context=test_main_context,
                                current_conversation=current_conversation,
                                question_text=question_text
                                )
    else:
        template = Template(
            """
            \n\nHuman:
            ${test_main_context}
            
            ${current_conversation}
            
            ${question_text}

            NOTE: Please respond as ${question_for} only. Do not respond as any other persona.
            NOTE: Please respond in not more than 180 words. The total number of words should not be more than 150 words.
            \n\nAssistant:
            """
        ).substitute(test_main_context=test_main_context,
                               current_conversation=current_conversation,
                               question_text=question_text,
                               question_for=question.question_for)
    # return template.substitute(test_main_context=test_main_context,
    #                            current_conversation=current_conversation,
    #                            question_text=question_text,
    #                            question_for=question.question_for)
    return template

@timeit
def get_email_type_prompt(test_title,
                          test_description,
                          question,
                          candidate_reply,
                          user_feedback_prompt):
    template = Template(
        """
        \n\nHuman:
        Title: ${test_title}. 
        Test Description: ${test_description}
        Customer question:  ${question} 
        Candidate answer:  ${candidate_reply}

        Please provide feedback on this email. Please do not add any introductory sentence and come to the point directly. Do not include any response to the email. The feedback should be directed to the writer of the email. Please add a sample re-written email.

        Please provide communication and subject matter feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on "Title" , only if they are relevant to the situation. The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the responder. The feedback should be structured in the following format: 
        - What went well ?
        - What could be improved ?
        - Some new ideas to reframe the context 
        - A sample re-written email.
        - A counter intuitive insight 

        NOTE: The total number of words should be at the minimum 400 words and maximum 500 words. Provide the feedback exactly in the format and sections above.
        NOTE: Do not include any mentions of word count requirements or limits in your response.
        NOTE: Never give any feedback on the Question or anybody asking the question.
        NOTE: Please suggest any industry standard framework or derived methods that can strengthen the managers answer in "Key insights to improve the response."
        

        ${user_feedback_prompt}
        \n\nAssistant:
        """
    )

    return template.substitute(test_title=test_title,
                               test_description=test_description,
                               question=question,
                               candidate_reply=candidate_reply,
                               user_feedback_prompt=user_feedback_prompt)

@timeit
def get_overridden_prompt(prompt_template: str,
                          test_title: str,
                          test_description: str,
                          question: str,
                          question_context: str,
                          candidate_reply: str,
                          user_feedback_prompt:str):
    if question_context:
        template = Template(
            """
            \n\nHuman:
            Title: ${test_title}. 
            Test Description: ${test_description}
            Customer question:  ${question} 
            Expert Suggestions:  ${question_context}
            Evaluation Criteria: ${prompt_template} 
            Candidate answer:  ${candidate_reply}
    
            Please provide communication and subject matter feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on "Expert suggestions", "Title", only if they are relevant to the situation. The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the responder.
            The feedback should be structured in the following format: 
            - Key insights to improve the response

            - What went well ?

            - What did not work ?

            - A sample candidate answer

            - A counter intuitive insight

            NOTE: The total number of words should be at the minimum 400 words and maximum 500 words. Provide the feedback exactly in the format and sections above.
            NOTE: Do not include any mentions of word count requirements or limits in your response.
            NOTE: Never give any feedback on the Question or anybody asking the question.
            NOTE: Please suggest any industry standard framework or derived methods that can strengthen the managers answer in "Key insights to improve the response."
            
            ${user_feedback_prompt}
            \n\nAssistant:
            """
        )
        return template.substitute(test_title=test_title,
                                   test_description=test_description,
                                   question=question,
                                   question_context=question_context,
                                   prompt_template=prompt_template,
                                   candidate_reply=candidate_reply,
                                   user_feedback_prompt=user_feedback_prompt)

    else:
        template = Template(
            """
            \n\nHuman:
            Title: ${test_title}. 
            Test Description: ${test_description}
            Customer question:  ${question} 
            Evaluation Criteria: ${prompt_template}
            Candidate answer:  ${candidate_reply}
    
            Please provide communication and subject matter feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on  "Title" , only if they are relevant to the situation. The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the responder. The feedback should be structured in the following format: 
            - Key insights to improve the response

            - What went well ?

            - What did not work ?

            - A sample candidate answer

            - A counter intuitive insight

            NOTE: The total number of words should be at the minimum 400 words and maximum 500 words. Provide the feedback exactly in the format and sections above.
            NOTE: Do not include any mentions of word count requirements or limits in your response.
            NOTE: Never give any feedback on the Question or anybody asking the question.
            NOTE: Please suggest any industry standard framework or derived methods that can strengthen the managers answer in "Key insights to improve the response."
            
            ${user_feedback_prompt}
            \n\nAssistant:
            """
        )
        return template.substitute(test_title=test_title,
                                   test_description=test_description,
                                   question=question,
                                   prompt_template=prompt_template,
                                   candidate_reply=candidate_reply,
                                   user_feedback_prompt=user_feedback_prompt)
@timeit
def emplyee_feedback_prompt(prompt_template: str,
                          test_title: str,
                          test_description: str,
                          question: str,
                          candidate_reply: str,
                          user_feedback_prompt:str):
    template = Template(
        """
        \n\nHuman:
        Title: ${test_title}.
        Test Description: ${test_description}
        Question: ${question}
        Evaluation Criteria: ${prompt_template}
        employee_performance: ${candidate_reply}
        An employee's performance is given in "employee_performance". As their manager provides comments on the employee's performance based on the employee's performance. The comments should be structured in the following format:
        - Key insights to improve the performance
        - What went well ?
        - What did not work ?
        NOTE: The total number of words should be at the minimum 400 words and maximum 500 words. Provide the feedback exactly in the format and sections above.
        NOTE: Do not include any mentions of word count requirements or limits in your response.
        NOTE : This comments should only be provided for the employee's performance. DO NOT provide feedback on the response,
        NOTE : In cases where the "employee_performance" consists of less than 15 words, always add the following statement after the feedback: "Warning: Very short responses are unrealistic and may lead to poor quality feedback."

        NOTE : Minimum response length is 300 words. Always adhere to the same.
        
        ${user_feedback_prompt}
        \n\nAssistant:
        """
    )
    return template.substitute(test_title=test_title,
                                test_description=test_description,
                                question=question,
                                prompt_template=prompt_template,
                                candidate_reply=candidate_reply,
                                user_feedback_prompt=user_feedback_prompt)

    

@timeit
def get_question_key_learning_point(test_title,
                                    test_question):
    prompt = Template(
        """
        \n\nHuman:
        TestTitle: ${test_title}
        Question: ${question_text}

        For given "Question" for the "TestTitle" extract a key learning from an ideal answer to the "Question"  as "Output". The "Output" should be a single paragraph using full words and sentences, do not append it with "Key Learning:".

        Output:
        \n\nAssistant:
        """
    ).safe_substitute(
        test_title=test_title,
        question_text=test_question
    )

    # gpt_feedback = gpt3_completion(prompt, stop=["USER:", "CoachBot"])

    # if not gpt_feedback.text:
    #     raise ValueError("unable to get key_learning_point")

    # return gpt_feedback.text

    anthropic_response = generic_completion(prompt, 1000)

    if not anthropic_response:
        anthropic_response = "Communication"

    return anthropic_response


@timeit
def get_question_key_learning_skills(test_title,
                                     test_question):
    skills_name_list = [skill['name'] for skill in skills]
    prompt = Template(
        """
        \n\nHuman:
TestTitle: ${test_title}
Question: ${question_text}

For given "Question" for the "TestTitle" extract skills that can be learned from a key learning from an ideal answer to the "Question"  as "Output". The "Output" should have comma separated skills where all skills are in small case.
Choose skills from this list only: ${skills_name_list}
NOTE: Choose only one or two skills from the list. Do not choose more than two skills.
NOTE: Do not provide any help text or any other text in the "Output" other than the skills.
Output:
\n\nAssistant:
"""
    ).safe_substitute(
        test_title=test_title,
        question_text=test_question,
        skills_name_list=skills_name_list
    )

    anthropic_response = generic_completion(prompt, 1000)

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


@timeit
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


@timeit
def generate_test_from_objective_anthropic(objective: str):
    skills_name_list = [skill['name'] for skill in skills]

    prompt = f"""
    \n\nHuman:
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
    \n\nAssistant:
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

@timeit
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


@timeit
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


@timeit
def admin_panel_updates(interaction_per_month,interaction_repeatation,logo_url,tenant_id,test_codes,user_id,test_type,scenario_case,test_code,interaction_mode):

    tenant_query = Tenant.objects.get(uid=tenant_id)
    updated_fields = []

    # updates related to worksapce/user level control

    if interaction_per_month:
        tenant_query.test_per_month = int(interaction_per_month)
        updated_fields.append('test_per_month')
    
    if interaction_repeatation:
        tenant_query.is_repeat = interaction_repeatation
        updated_fields.append('is_repeat')

    if logo_url:
        tenant_query.logo = logo_url
        updated_fields.append('logo')

    if len(updated_fields) > 0 :
        tenant_query.save(update_fields=updated_fields)


    # test_privilage control 

    if user_id and test_codes:
        user = UserAttribute.objects.get(user_id=user_id)

        user.test_previlage = test_codes
        user.save(update_fields=['test_previlage'])

    # TEst related updates

    if test_code:
        test = Test.objects.get(test_code=test_code,deleted=0)
        test_update_field = []

        if test:
            if test_type:
                test.test_type = test_type
                test_update_field.append("test_type")

            if scenario_case:
                test.scenario_case = scenario_case
                test_update_field.append("scenario_case")

            if interaction_mode:
                test.interaction_mode = interaction_mode
                test_update_field.append("interaction_mode")

            if len(test_update_field)> 0:
                test.save(update_fields=test_update_field)

@timeit
def update_prompt_user_attributes(user_id, var_dict):
    # Retrieve the UserAttribute object for the given user_id
    user_att = UserAttribute.objects.filter(user_id=user_id).first()

    # Initialize a list to track updated fields
    update_fields = []

    if user_att:
        # Iterate through the keys in var_dict
        for var in var_dict:
            # Check if the key exists in UserAttribute model
            if hasattr(user_att, var):
                # Update the attribute in the UserAttribute model
                setattr(user_att, var, var_dict[var])
                update_fields.append(var)

        # Save the changes to the UserAttribute object
        user_att.save(update_fields=update_fields)

@timeit
def submit_feedback(
        session_id,
        tenant_id,
        question_id,
        response_file,
):
    test_attempt_session = TestAttemptSession.objects.filter(tenant_id=tenant_id,uid=session_id,deleted=0).first()
    question = TestQuestion.objects.filter(tenant_id=tenant_id,uid=question_id).first()
    test = Test.objects.filter(tenant_id=tenant_id,uid=test_attempt_session.test_id).first()

    test_question_response = TestQuestionResponse.objects.get_or_create(
                                tenant_id=tenant_id,
                                test_attempt_session_id=session_id,
                                question_id=question_id,
                                responder_type=question.question_for,
                                responder_display_name=question.question_for,
                                response_text="",
                                response_file = response_file
                            )[0]
    
    transcript = gpt_wishper_api(
                    response_file)
    
    test_question_response.response_text = transcript
    test_question_response.save(update_fields=['response_text'])

    user_info = UserAttribute.objects.get(user_id=test_attempt_session.participant_id)
    difficulty_level = user_info.difficulty_level
    user_feedback_prompt = ''
    if difficulty_level == 'easy':
        user_feedback_prompt = user_info.easy_feedback_prompt
    elif difficulty_level == 'critical':
        user_feedback_prompt == user_info.critical_feedback_prompt

    if user_info.custom_feedback_prompt_1:
        user_feedback_prompt = user_feedback_prompt + "\n" + user_info.custom_feedback_prompt_1
    if user_info.custom_feedback_prompt_2:
        user_feedback_prompt = user_feedback_prompt + "\n" + user_info.custom_feedback_prompt_2

    if test.is_email_type:
        prompt = get_email_type_prompt(
            test_title=test.title,
            test_description=test.description,
            question=question.question,
            candidate_reply=test_question_response.response_text,
            user_feedback_prompt=user_feedback_prompt)
        
    elif test.scenario_case == ScenarioCaseChoices.employee_feedback:
        prompt = emplyee_feedback_prompt(
                prompt_template=question.gpt_prompt_override or test.gpt_prompt_override,
                test_title=test.title,
                test_description=test.description,
                question=question.question,
                candidate_reply=test_question_response.response_text,
                user_feedback_prompt=user_feedback_prompt
            )

    else:
        if question.gpt_prompt_override or test.gpt_prompt_override:
            prompt = get_overridden_prompt(
                prompt_template=question.gpt_prompt_override or test.gpt_prompt_override,
                test_title=test.title,
                test_description=test.description,
                question=question.question,
                question_context=question.subjective_answer,
                candidate_reply=test_question_response.response_text,
                user_feedback_prompt=user_feedback_prompt
            )
        else:
            prompt = get_chat_conversation_prompt_v3(
                test_title=test.title,
                test_description=test.description,
                question=question.question,
                question_context=question.subjective_answer,
                candidate_reply=test_question_response.response_text,
                user_feedback_prompt=user_feedback_prompt)


    feedback_text = ''
    raw_text = ''
    response_text = test_question_response.response_text
    go_for_feedback = True

    words = word_tokenize(test_question_response.response_text)

    if len(words) <= 10 :
        feedback_text = "No feedback can be generated because of too low response length"
        go_for_feedback = False
    
    if go_for_feedback:
        start = time.time()
        for i  in range(3):
            
            logger.info(f"tring feedback generation for {i+1} time")

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
                            candidate_reply=test_question_response.response_text,
                            user_feedback_prompt=user_feedback_prompt)
                        
                    elif test.scenario_case == ScenarioCaseChoices.employee_feedback:
                        prompt = emplyee_feedback_prompt(
                                prompt_template=question.gpt_prompt_override or test.gpt_prompt_override,
                                test_title=test.title,
                                test_description=test.description,
                                question=question.question,
                                candidate_reply=test_question_response.response_text,
                                user_feedback_prompt=user_feedback_prompt
                        )

                    else:
                        if question.gpt_prompt_override or test.gpt_prompt_override:
                            prompt = get_overridden_prompt(
                                prompt_template=question.gpt_prompt_override or test.gpt_prompt_override,
                                test_title=test.title,
                                test_description=test.description,
                                question=question.question,
                                question_context=question.subjective_answer,
                                candidate_reply=response_text,
                                user_feedback_prompt=user_feedback_prompt
                            )
                        else:
                            prompt = get_chat_conversation_prompt_v3(
                                test_title=test.title,
                                test_description=test.description,
                                question=question.question,
                                question_context=question.subjective_answer,
                                candidate_reply=response_text,
                                user_feedback_prompt=user_feedback_prompt)

                max_retry -= 1

            gpt_feedback = gpt3_completion(prompt, stop=["USER:", "CoachBot"])
            if not gpt_feedback.text:
                try:
                    feedback_text = text_bison_compeletion(prompt)
                except Exception as e:
                    logger.exception(e)
                    anthropic_feedback = anthropic_completion(prompt, 1200)
                    # feedback_text = "Feedback couldn't be generated Because of server overload. You may try after few minutes or you can choose to complete this interaction as well."
                    feedback_text = anthropic_feedback
            else:
                feedback_text = gpt_feedback.text
                raw_text = gpt_feedback.raw


            if "Unfortunately I cannot provide" not in feedback_text and "Very short responses are unrealistic" not in feedback_text and "PLEASE RESPOND WITH RELEVANCE" not in feedback_text and len(feedback_text.split()) < 300:
                continue

            end = time.time()
            logger.info(f"######################## _process_response: fetching FEEDBACK  took {end - start:.2f} ########################")
            break
            

    test_question_response.metadata = {
        "gpt": {
            "prompt": prompt,
            "response": {
                "raw": raw_text,
                "text": feedback_text,
            }
        }
    }

    feedback_text = re.sub(r'\([^)]*\)', '', feedback_text)   # to remove any word limit in ()
    test_question_response.feedback_text = feedback_text
    
    test_question_response.save(update_fields=['metadata','feedback_text'])
    logger.info("######################## Feedback is ready ######################")

    return test_question_response.feedback_text

def scrape_meta_info(url):
    try:
        # Send an HTTP GET request to the URL
        response = requests.get(url)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Parse the HTML content of the page
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find the meta title and description tags
            title_tag = soup.find('meta', attrs={'name': 'title'}) or soup.find('meta', attrs={'property': 'og:title'})
            description_tag = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})

            # Extract content from the meta tags
            title = title_tag['content'] if title_tag else None
            description = description_tag['content'] if description_tag else None

            return title, description

        else:
            return "Error: Unable to fetch the URL. Status code: " + str(response.status_code), ""

    except Exception as e:
        return "Error: " + str(e), ""


def extract_information(text):
    # Regular expressions for extracting title, description, questions, prompts, takeaways, and skills
    text = text.replace("KLS", "Skills")
    # Replace KLP with Takeaway
    text = text.replace("KLP", "Takeaway")
    text = text.replace("Custom prompt", "Prompt")


    title_pattern = re.compile(r'Title\s*:\s*(.+)')
    description_pattern = re.compile(r'Description\s*:\s*(.+)')
    question_pattern = re.compile(r'Question\s*(\d+)\s*:\s*(.+)')
    prompt_pattern = re.compile(r'Prompt\s*(\d+)\s*:\s*(.+)')
    takeaway_pattern = re.compile(r'Takeaway\s*(\d+)\s*:\s*(.+)')
    skills_pattern = re.compile(r'Skills\s*(\d+)\s*:\s*(.+)')
    rating_pattern = re.compile(r'Rating\s*:\s*(\d+)')
    

    # Extracting information using regular expressions
    title_match = title_pattern.search(text)
    description_match = description_pattern.search(text)
    rating_match = rating_pattern.search(text)
    if not (title_match and description_match and rating_match and question_pattern.findall(text) and prompt_pattern.findall(text) and takeaway_pattern.findall(text) and skills_pattern.findall(text)):
        raise ValueError("Invalid format. Unable to extract necessary information.")

    title = title_match.group(1)
    description = description_match.group(1)
    rating = int(rating_match.group(1)) if rating_match else 0

    questions = []
    for match in question_pattern.finditer(text):
        question_number = int(match.group(1))
        question_text = match.group(2)
        prompt_match = prompt_pattern.search(text, match.end())
        takeaway_match = takeaway_pattern.search(text, prompt_match.end())
        skills_match = skills_pattern.search(text, takeaway_match.end())

        prompt_text = prompt_match.group(2)
        takeaway_text = takeaway_match.group(2)
        skills_text = skills_match.group(2)
        question_data = {
            'text': question_text,
            'prompt': prompt_text,
            'takeaway': takeaway_text,
            'skills': skills_text
        }
        questions.append(question_data)
        

    informations =  {
        'title': title,
        'description': description,
        'rating': rating,
        'questions': questions
    }
    
    title = informations['title']
    description = informations['description']

    question_info = []
    skill_to_evalaute = ''
    for que in informations['questions']:
        question_info.append({
            "question": que["text"],
            "question_type": "subjective",
            "gpt_prompt_override": que["prompt"],
            "subjective_answer": "",
            "key_learning_point": que['takeaway'],
            "key_learning_skills": que['skills'].strip()
        })
        skills_to_eva = set()
        for skill in que['skills'].split(','):
            skills_to_eva.add(skill.strip().capitalize())

        for skill in skills_to_eva:
            skill_to_evalaute += skill +", "

    return title, description, question_info, skill_to_evalaute, rating

def extract_info_gpt(scenario):
    scenario = scenario.replace("KLS", "Skills")
    # Replace KLP with Takeaway
    scenario = scenario.replace("KLP", "Takeaway")
    scenario = scenario.replace("Custom prompt", "Prompt")


    # Extract title
    title_match = re.search(r"Title: (.+)", scenario)
    title = title_match.group(1) if title_match else None
    rating_pattern = re.compile(r'Rating\s*:\s*(\d+)')
    rating_match = rating_pattern.search(scenario)
    rating = int(rating_match.group(1)) if rating_match else 0

    # Extract description
    description_match = re.search(r"Description:\n(.+?)\nQuestions:", scenario, re.DOTALL)
    description = description_match.group(1).strip() if description_match else None

    if description is None:
        description_match = re.search(r"Description: (.+?)\nQuestion 1:", scenario, re.DOTALL)
        description = description_match.group(1).strip() if description_match else None

    question_info = []

    # Extract questions, prompts, takeaways, and skills
    question_matches = re.findall(r"(\d+)\. (.+?)\nPrompt \d+: (.+?)\nTakeaway \d+: (.+?)\nSkills \d+: (.+)", scenario)
    print(question_matches)
    if len(question_matches) == 0:
        question_matches = re.findall(r"Question (\d+): (.+?)\nPrompt \d+: (.+?)\nTakeaway \d+: (.+?)\nSkills \d+: (.+)", scenario)

    logger.info(f"{'#'*100}  question_matches: {question_matches} {'#'*100} ")
    skills_to_eva = set()
    for match in question_matches:
        num, question, prompt, takeaway, skills = match
        question_info.append({
            "question": question,
            "question_type": "subjective",
            "gpt_prompt_override": prompt,
            "subjective_answer": "",
            "key_learning_point": takeaway,
            "key_learning_skills": skills
        })
        for skill in skills.split(','):
            skills_to_eva.add(skill.capitalize())
    
    skill_to_evalaute =''

    for skill in skills_to_eva:
        skill_to_evalaute += skill +", "

    return title,description, question_info, skill_to_evalaute, rating


def create_scenario_from_site_context(url,access_token, tenant_id, context):
    """
    This function generates a scenario based on the meta information of a given URL.

    Parameters:
    - url (str): The URL of the webpage to scrape meta information from.
    - access_token (str): The access token for authentication.

    Returns:
    - response (dict): The response from the API endpoint where the generated scenario is sent.

    Example Usage:
    create_scenario_from_site_context("https://example.com", "access_token")

    Flow:
    1. Scrapes the meta information (title and description) from the given URL using web scraping techniques.
    2. Constructs a prompt string using the scraped information and a predefined template.
    3. Calls the 'generic_completion' function with the prompt to generate a scenario.
    4. Checks the generated scenario for a rating and if it meets the criteria, returns it as the output.
    5. If the generated scenario does not meet the criteria, repeats the process up to three times.
    6. If a suitable scenario is not generated within three attempts, returns a failure message.

    Note:
    - The generated scenario is evaluated based on a rating and certain criteria.
    - The simulation created is expected to be advanced and tough.

    """
    def decode_basic_auth_token(token: str) -> str:
            decoded_token = base64.b64decode(token).decode("utf-8")
            key_and_secret = decoded_token.split(":")

            key = key_and_secret[0]
            secret = key_and_secret[1]

            return key, secret

    garbage_scenarios = []
    for i in range(15):
        logger.info(f"trying outer test generation for {i+1} time")
        try:
            if context:
                context = json.loads(context)
                title, des = context['title'], context['data']['information']
                logger.info(f"{'#'*100} title: {title}, context: {des} {'#'*100} ")
            else:
                title, des = scrape_meta_info(url)
            
            site_information = f"{title} {des}"

            prompt = """
                \n\nHuman:
                    {Information} - %s

                Read this {information} thoroughly. Now based on this information and your understanding create  an advanced and tough simulation situation to practice the skills presented in the {information}. After creating the situation provide these:

                Description - Define the situation, and the problem. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on based on data, industry, events, etc. The description should just describe the problem and what was the specific situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.
                Title - Give a specific and relevant title for this description in less than 10 words.
                Questions - Develop a set of {3} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.
                Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide a feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
                KLP - With each question add one or two line takeaway for providing feedback. The takeaways should be related to the question it is provided with.
                KLS - With each question, add the skill(s) that are tested. And For every question choose exactly {2} skill(s) and not more or less than {2} should be chosen for each question. The skills for all the questions should be unique.
                The Question, Custom Prompt, KLP, KLS should be numbered.

                Here the format looks like :

                "Title",

                "Description",

                "Question 1",

                "Prompt 1",

                "Takeaway 1" ,

                "Skills 1" repeated for {3} question(s). Do not include any {responder} response.

                'The Question, Prompt, Takeaway, Skills should be numbered.'

                NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
                
                NOTE : Make sure the simulation is very advanced and tough.
                
                \n\nAssistant:
            """%(site_information)

            response = {}
            scenario = ''
            title, description, question_info, skill_to_evalaute = "","","",""
            for i in range(3):
                logger.info(f'trying scenario creation palm for {i +1} time')
                

                scenario = text_bison_compeletion(prompt)
                print("palm",scenario)
                print("#"*100)

                try:
                    title, description, question_info, skill_to_evalaute,rating = extract_information(scenario)
                except:
                    print('garbage scenario :',scenario)
                    garbage_scenarios.append(scenario)
                    rating = 0

                if scenario == 'failed to generate scenario' or rating <= 6:
                    # print(rating,"failed")
                    # if i+1 == 3:
                    #     for i in range(3):
                    #         logger.info(f'trying gpt for {i+1} time')
                    #         scenario = gpt3_completion(prompt, stop=["USER:", "CoachBot"]).text
                    #         print("gpt",scenario)
                    #         print("#"*100)
                    #         title,description, question_info, skill_to_evalaute,rating = extract_info_gpt(scenario)

                    #         if scenario == 'failed to generate scenario' or rating <= 6:
                    #             continue

                    #         break
                    # else:
                        continue
                break

            key, secret = decode_basic_auth_token(access_token.split(' ')[-1])
            # client = Client.objects.get(key=key)
            # creator = User.objects.get(uid=client.owner_id)
            admin_user = User.objects.filter(tenant_id=tenant_id,role='admin').first()

            logger.info(f"{'#'*100}  skills to evaluate:  <==> {skill_to_evalaute}, description: {description}  {'#'*100} ")

            json_data = json.dumps({
                "creator_id": admin_user.uid,
                "title": title,
                "description": description,
                "email_address_list":'mail@coachbots.com',
                "questions": question_info,
                "scenario_case": 'simulation',
                "interaction_mode":'any',
                "test_type":'test',
                "email_candidate":True,
                "gpt_prompt_override":"",
                "skills_to_evaluate": skill_to_evalaute,
                "is_self_created": True,
                "certificate_details": {"title": title},


            })
            headers = {
                        'Content-Type': 'application/json',
                        'Authorization': access_token
                    }
            
            try:
                response = requests.post(
                                        API_ENDPOINT_SLACK, data=json_data, headers=headers, verify=False)
                response = response.json()
                print("%"*200, '\n', response, '\n', admin_user.uid,'\n', "%"*200)
                return {'title': response['title'],'test_code': response['test_code'],'description': response['description']}
                
            except Exception as e:
                logger.error(e,exc_info=True)
                
                raise e

        except Exception as e:
            logger.error(e,exc_info=True)
            if i+1 == 15:
                logger.info(f"{'!'*100}  failed 15 times  {'!'*100}")
                return {'message':"failed to generate the scenario","data":garbage_scenarios}
            continue



def fetch_test_codes_by_site_context(url,tenant_id, context):

    title, des = scrape_meta_info(url)
    site_information = f"Title: {title} \n Description: {des}"


    all_skills_qs = Test.objects.filter(tenant_id=tenant_id,deleted=0).values_list('skills_to_evaluate')
    all_skills = set()
    up_skill_names = [skill.strip().capitalize() for skill in [s['name'] for s in all_presented_skills]]

    for skills in all_skills_qs:
        if skills[0]:
            skill_name_list = [sk.strip().capitalize() for sk in skills[0].split(',') if sk.strip().capitalize() in up_skill_names ]
            all_skills.update(skill_name_list)

    prompt = """
    {information} - %s
    {AllSkills} - %s

    According to the {information}, extract suitable skill from it skill must be from {AllSkills}.
    NOTE: ONly return skill nothing else
    """%(site_information,list(all_skills))

    skills = generic_completion(prompt,1000,'Failed to extract skills')
    skills = skills.split(':')[-1].strip()
    print(skills)
        
 
    tests = Test.objects.filter(tenant_id=tenant_id,deleted=0,skills_to_evaluate__icontains=skills)
    test_list = []
    for test in tests:
        test_list.append({
            "title": test.title,
            "test_code": test.test_code,
            "description": test.description,
        })

    return test_list

    

#************* Dynamic MCQ Start************#
def get_next_mcq_question_options_prompt(test_description, situation, choice_1, choice_2, user_decision):
    normal_prompt = f'''
    \n\nHuman:
    Scenario: {test_description}


    Situation: {situation}

    Choice 1: {choice_1}

    Choice 2: {choice_2}


    Decision: {user_decision}


    This is a scenario where the candidate has to make a decision between Choice 1 and Choice 2. Based on the decision generate the next part of the scenario where the candidate will be provided another situation and 2 choices. The candidate needs to make a decision between these choices. The situation should follow the natural flow of the story based on the Decision. The situation should be specific and realistic. Add necessary details in the Situation to make it specific. The Choices provided should be realistic, natural and professional. Keep the Choices relevant to the situation. The Choices and the Situation should be open ended to further develop the scenario. 

    Generate the next Situation, Choice 1 and Choice 2 for the candidate.
    \n\nAssistant: 

    '''


    stakeholders_relationship_strain_prompt = f"""
    \n\nHuman:
    Scenario: {test_description}
    Situation: {situation}
    Choice 1: {choice_1}
    Choice 2: {choice_2}
    Decision: {user_decision}

    This is a scenario where the candidate has to make a decision between Choice 1 and Choice 2. Based on the decision generate the next part of the scenario where the candidate will be provided another situation and 2 choices. The candidate needs to make a decision between these choices. The situation should follow the natural flow of the story based on the Decision. The situation should be specific and realistic. 

    The next situation should be based on the Stakeholders Relationship Strain. Add necessary details in the Situation to make it specific. The Choices provided should be realistic, natural and professional. Keep the Choices relevant to the situation. The Choices and the Situation should be open ended to further develop the scenario. 

    Generate the next Situation, Choice 1 and Choice 2 for the candidate. Only provide the next  Situation, Choice 1 and Choice 2 nothing else. 
    Output format  example : 
    Situation : situation
    Choice 1 : choice 1
    Choice 2 : choice 2 
    NOTE : Always give the output in this exact format.
    \n\nAssistant: 
    """

    Unexpected_Collaboration_Opportunity_prompt = f"""
        \n\nHuman:
        Scenario: {test_description}
        Situation: {situation}
        Choice 1: {choice_1}
        Choice 2: {choice_2}
        Decision: {user_decision}

        This is a scenario where the candidate has to make a decision between Choice 1 and Choice 2. Based on the decision generate the next part of the scenario where the candidate will be provided another situation and 2 choices. The candidate needs to make a decision between these choices. The situation should follow the natural flow of the story based on the Decision. The situation should be specific and realistic. 

        The next situation should be based on an Unexpected Collaboration Opportunity. Add necessary details in the Situation to make it specific. The Choices provided should be realistic, natural and professional. Keep the Choices relevant to the situation. The Choices and the Situation should be open ended to further develop the scenario. 

        Generate the next Situation, Choice 1 and Choice 2 for the candidate. Only provide the next  Situation, Choice 1 and Choice 2 nothing else. 
        Output format  example : 
        Situation : situation
        Choice 1 : choice 1
        Choice 2 : choice 2 
        NOTE : Always give the output in this exact format.
        \n\nAssistant:
    """

    Leadership_Crisis_and_Team_Morale_prompt = f"""
        \n\nHuman:
        Scenario: {test_description}
        Situation: {situation}
        Choice 1: {choice_1}
        Choice 2: {choice_2}
        Decision: {user_decision}

        This is a scenario where the candidate has to make a decision between Choice 1 and Choice 2. Based on the decision generate the next part of the scenario where the candidate will be provided another situation and 2 choices. The candidate needs to make a decision between these choices. The situation should follow the natural flow of the story based on the Decision. The situation should be specific and realistic. 

        The next situation should be based on Leadership Crisis and Team Morale. Add necessary details in the Situation to make it specific. The Choices provided should be realistic, natural and professional. Keep the Choices relevant to the situation. The Choices and the Situation should be open ended to further develop the scenario. 

        Generate the next Situation, Choice 1 and Choice 2 for the candidate. Only provide the next  Situation, Choice 1 and Choice 2 nothing else. 
        Output format  example : 
        Situation : situation
        Choice 1 : choice 1
        Choice 2 : choice 2 
        NOTE : Always give the output in this exact format.
        \n\nAssistant:
        """

    Innovative_Solution_Emerges_prompt = f"""
        \n\nHuman:
        Scenario: {test_description}
        Situation: {situation}
        Choice 1: {choice_1}
        Choice 2: {choice_2}
        Decision: {user_decision}

        This is a scenario where the candidate has to make a decision between Choice 1 and Choice 2. Based on the decision generate the next part of the scenario where the candidate will be provided another situation and 2 choices. The candidate needs to make a decision between these choices. The situation should follow the natural flow of the story based on the Decision. The situation should be specific and realistic. 

        The next situation should be based on Leadership Crisis and Team Morale. Add necessary details in the Situation to make it specific. The Choices provided should be realistic, natural and professional. Keep the Choices relevant to the situation. The Choices and the Situation should be open ended to further develop the scenario. 

        Generate the next Situation, Choice 1 and Choice 2 for the candidate. Only provide the next  Situation, Choice 1 and Choice 2 nothing else. 
        Output format  example : 
        Situation : situation
        Choice 1 : choice 1
        Choice 2 : choice 2 
        NOTE : Always give the output in this exact format.
        \n\nAssistant:
        """

    Stakeholder_Flexibility_and_Understanding_prompt = f"""
        \n\nHuman:
        Scenario: {test_description}
        Situation: {situation}
        Choice 1: {choice_1}
        Choice 2: {choice_2}
        Decision: {user_decision}

        This is a scenario where the candidate has to make a decision between Choice 1 and Choice 2. Based on the decision generate the next part of the scenario where the candidate will be provided another situation and 2 choices. The candidate needs to make a decision between these choices. The situation should follow the natural flow of the story based on the Decision. The situation should be specific and realistic. 

        The next situation should be based on Stakeholder Flexibility and Understanding. Add necessary details in the Situation to make it specific. The Choices provided should be realistic, natural and professional. Keep the Choices relevant to the situation. The Choices and the Situation should be open ended to further develop the scenario. 

        Generate the next Situation, Choice 1 and Choice 2 for the candidate. Only provide the next  Situation, Choice 1 and Choice 2 nothing else. 
        Output format  example : 
        Situation : situation
        Choice 1 : choice 1
        Choice 2 : choice 2 
        NOTE : Always give the output in this exact format.
        \n\nAssistant:
        """

    Unexpected_Disruption_prompt = f""" 
        \n\nHuman:
        Scenario: {test_description}
        Situation: {situation}
        Choice 1: {choice_1}
        Choice 2: {choice_2}
        Decision: {user_decision}

        This is a scenario where the candidate has to make a decision between Choice 1 and Choice 2. Based on the decision generate the next part of the scenario where the candidate will be provided another situation and 2 choices. The candidate needs to make a decision between these choices. The situation should follow the natural flow of the story based on the Decision. The situation should be specific and realistic.

        The next situation should be based on Unexpected Disruption. Add necessary details in the Situation to make it specific. The Choices provided should be realistic, natural and professional. Keep the Choices relevant to the situation. The Choices and the Situation should be open ended to further develop the scenario. 

        Generate the next Situation, Choice 1 and Choice 2 for the candidate. Only provide the next  Situation, Choice 1 and Choice 2 nothing else. 
        Output format  example : 
        Situation : situation
        Choice 1 : choice 1
        Choice 2 : choice 2 
        NOTE : Always give the output in this exact format.
        \n\nAssistant:
        """

    Regulatory_Hurdle_prompt = f"""
        \n\nHuman:
        Scenario: {test_description}
        Situation: {situation}
        Choice 1: {choice_1}
        Choice 2: {choice_2}
        Decision: {user_decision}

        This is a scenario where the candidate has to make a decision between Choice 1 and Choice 2. Based on the decision generate the next part of the scenario where the candidate will be provided another situation and 2 choices. The candidate needs to make a decision between these choices. The situation should follow the natural flow of the story based on the Decision. The situation should be specific and realistic.

        The next situation should be based on Unexpected Regulatory Hurdle. Add necessary details in the Situation to make it specific. The Choices provided should be realistic, natural and professional. Keep the Choices relevant to the situation. The Choices and the Situation should be open ended to further develop the scenario. 

        Generate the next Situation, Choice 1 and Choice 2 for the candidate. Only provide the next  Situation, Choice 1 and Choice 2 nothing else. 
        Output format  example : 
        Situation : situation
        Choice 1 : choice 1
        Choice 2 : choice 2 
        NOTE : Always give the output in this exact format.
        \n\nAssistant:
        """

    Key_Stakeholder_Disagreement_prompt = f"""
        \n\nHuman:
        Scenario: {test_description}
        Situation: {situation}
        Choice 1: {choice_1}
        Choice 2: {choice_2}
        Decision: {user_decision}

        This is a scenario where the candidate has to make a decision between Choice 1 and Choice 2. Based on the decision generate the next part of the scenario where the candidate will be provided another situation and 2 choices. The candidate needs to make a decision between these choices. The situation should follow the natural flow of the story based on the Decision. The situation should be specific and realistic.

        The next situation should be based on Key Stakeholder Disagreement. Add necessary details in the Situation to make it specific. The Choices provided should be realistic, natural and professional. Keep the Choices relevant to the situation. The Choices and the Situation should be open ended to further develop the scenario. 

        Generate the next Situation, Choice 1 and Choice 2 for the candidate. Only provide the next  Situation, Choice 1 and Choice 2 nothing else.
        Output format  example : 
        Situation : situation
        Choice 1 : choice 1
        Choice 2 : choice 2 
        NOTE : Always give the output in this exact format.
        \n\nAssistant:
        """


    prompts = [normal_prompt, stakeholders_relationship_strain_prompt, Unexpected_Collaboration_Opportunity_prompt, Leadership_Crisis_and_Team_Morale_prompt, Innovative_Solution_Emerges_prompt, Stakeholder_Flexibility_and_Understanding_prompt, Unexpected_Disruption_prompt, Regulatory_Hurdle_prompt, Key_Stakeholder_Disagreement_prompt]

    prompt = random.choice(prompts)

    return prompt


def get_last_mcq_question_options_promt(test_description, situation, choice_1, choice_2, user_decision):
    prompt = '''
    \n\nHuman:
    Scenario: {test_description}


    Situation: {situation}

    Choice 1: {choice_1}

    Choice 2: {choice_2}


    Decision: {user_decision}


    This is a scenario where the candidate has to make a decision between Choice 1 and Choice 2. Based on the decision generate the next part of the scenario where the candidate will be provided another situation and 2 choices. The candidate needs to make a decision between these choices. The situation should follow the natural flow of the story based on the Decision. The situation should be specific and realistic. Add necessary details in the Situation to make it specific. The Choices provided should be realistic, natural and professional. Keep the Choices relevant to the situation. This is the closing situation of the scenario. Make the Situation and Choices for ending the scenario.

    Generate the next Situation, Choice 1 and Choice 2 for the candidate.
    \n\nAssistant: 

    '''

    return prompt


def get_dynamic_mcq_skills_prompt(situation_decision_map, num_decisions):
    skills_prompt = f"""
    Teamwork
    Objection Handling
    Goal-oriented focus
    Ability to handle surprises
    Tenacity
    Empathy
    Methodical Approach
    Willingness to Learn
    Business Acumen
    Social Selling
    Storytelling
    Active Listening
    Presentation skills
    Curiosity
    Judgment
    Collaboration
    Clarity and Concision
    Friendliness
    Confidence
    Open-Mindedness
    Respectful 
    Feedback oriented
    Picking the Right Medium
    Being Assertive
    Asking Questions
    Inclusive Language
    Tone
    Self-motivated
    Standards
    Accountablility
    Courageous
    Engaged
    Character
    Humorous
    Passionate
    Integrity
    Likable
    Ethical
    Loyal
    Charisma
    Emotional intelligence
    Understanding of opportunity cost
    Humility
    Disciplined
    Perspective
    Risk management
    Self assurance
    Maturity
    Relationship building
    Social skills
    Speaking skills
    Honesty & Transparency
    Reasonable
    Boldness
    Presence
    Authenticity
    Ability to Confront
    Negotiation
    Clarity
    Ability to teach
    Interested in feedback
    Trustworthy 
    Ability to inspire
    Sharing your vision
    Turning vision into reality
    Motivational 
    Insightful
    Taking responsibly
    Rewarding
    Evaluative
    Coaching
    Enable others to act
    Set Expectations
    Fair
    Urgency
    Decisiveness
    Commitment to vision
    Consistency
    Does not fear mistakes/risk
    Ability to pivot
    Open minded
    Tough-minded
    Resourceful
    Faces obstacles with grace
    Street smart
    Make good decisions
    Strategic Thinking
    Proactive
    Flexible
    Manage setbacks
    Organized
    Creativity and resourcefulness
    Intuition
    Seeks out advice
    Pursue new experiences
    Reading
    Curiosity
    Competence
    Focused
    Intentional Learner
    Enjoys The Ride
    Improve lives around you
    Foster potential
    Supportive (Help other succeed)
    Performance driven
    Servant leadership
    Assertive
    Conviction
    Patience
    High-energy
    Problem solving
    Patience
    Attentiveness
    Emotional intelligence
    Communication skills
    Creativity and resourcefulness
    Persuasive
    Time management
    Knowledge of Pay Equity Laws
    DEI Strategist
    Inclusive Interviewing
    Mentorship 
    Feedback Mechanism Implementation
    Leadership 

    This is the skills list. Based on this list give me one skill that is reflected in each of these decisions which were taken in the particular situations. 
    context : {situation_decision_map}

    decisions_no : {num_decisions}

    Give me {num_decisions} skills in the output.
    Do Not change the name of the skill. Just give me the skills name directly.
    Never change the name of the skills.

    Output format : {"skill1", "skill2", "skill3"}

    Always give the output in the given format.
    NOTE: Give me the exact skill name as given. Do Not change the name of any of the skill.
    NOTE : Do not give the output as "skill", only use the name of the skills given.
    """


    skills_prompt = f"""
    Give me one skill that is reflected in each of these decisions which were taken in the particular situations.  The situations and decisions are given in the context. Give one skill for each of these decisions. The skills should be relevant to the decision. 
    context : {situation_decision_map}

    decisions_no : {num_decisions}
    Give me {num_decisions} skills in the output.

    Output format : {"skill1", "skill2", "skill3"}

    Always give the output in the given format.
    NOTE : Do not give the output as "skill", only use the name of the skills given.
    """

    return skills_prompt


#*************** Dynamic MCQ End ******************#




def calculate_similarity(sentence1, sentence2):
    # Tokenize and remove stopwords
    stop_words = set(stopwords.words('english'))
    words1 = [word.lower() for word in word_tokenize(sentence1) if word.isalpha() and word.lower() not in stop_words]
    words2 = [word.lower() for word in word_tokenize(sentence2) if word.isalpha() and word.lower() not in stop_words]

    # Calculate the Jaccard similarity
    intersection = len(set(words1) & set(words2))
    union = len(set(words1) | set(words2))
    similarity_percentage = (intersection / union) * 100

    return similarity_percentage