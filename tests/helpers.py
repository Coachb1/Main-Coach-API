import json
import logging
import os
import random
import string
import tempfile
import time
from datetime import date, timedelta
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
from commons.fcfs_handler import FcfsHandler
from documents.choices import DocOwnerTypeChoice, DocTypeChoice
from documents.helpers import create_document, get_document_url
from email_sender.helpers import send_email, send_email_from_emailit, send_generic_email
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
from skills.models import SkillsRating, CompetencySkillAndClientMapping
from tenants.helpers import tenant_from_tenant_id
from tenants.models import Tenant
from test_bulk_upload.constants import get_skills_by_candidate_type
from tests.choices import InteractionModeChoices, PilotTestPreferencesChoices, QuestionForChoices, TestTypeChoices
from tests.choices import TestAttemptSessionStatusChoices
from tests.choices import TestQuestionResponseEvaluationStatusChoices
from tests.models import Test
from tests.models import TestAttemptSession
from tests.models import TestInvite
from tests.models import TestQuestion
from tests.models import TestQuestionResponse,TestReportConfig
from users.db import get_user_by_id, get_user_attribute
from users.db import get_user_display_name
from users.models import User
from users.models import UserAttribute, SignatureBot, ClientUserInfo
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
from commons.google_apis import speech_to_text, text_bison_compeletion, gemini_competions, gemini_completion
from pdf_generator.helpers import update_skill_name
from commons.utils import generic_completion
import threading
from tests.choices import ScenarioCaseChoices
from bs4 import BeautifulSoup
import requests
from test_bulk_upload.scripts import API_ENDPOINT_SLACK, limit_unique_skills_per_test
from skills.helpers import evaluate_rating_for_process_training , evaluate_competency_data, get_culture_skills
from readability import Document
from test_bulk_upload.constants import get_skills
from django.db.models import Q
from utilities.models import ScenarioCreationDetails
from commons.notifications import send_error_notification
from skills.helpers import json_extraction
from users.helpers import get_client_info_from_user_detail
from apis.accounts.serializers import clientUserInfoSerializer,TestReportConfigSerializer
from django.core.exceptions import ValidationError
from commons.google_apis import gemini_chat_completion
import csv
from collections import defaultdict
from tests.models import PsychometricReportSection, PsychometricReportSubsection, TestPilotuser, TestPilotRecords
from identities.helpers import get_user_via_identity, get_identity_value_by_tenant
from pdf_generator.helpers import get_report_from_test_attempt_session
from apis.tests.serializers import CreateTestSerializer
from tests.choices import PersonalityModelChoices
import json5 
logger = logging.getLogger(__name__)

fcfs_handler = FcfsHandler(2)

STRING_ASCII_DIGITS = (string.ascii_uppercase + string.digits)

TEST_CODE_LENGTH = 6
TEST_CODE_GENERATION_MAX_RETRY = 4
DEEPDIVE_CODE_LENGTH = 6
DEEPDIVE_CODE_GENERATION_MAX_RETRY = 4


def add_prefix(prefix, value):
    return f"{prefix}{value}"


@timeit
def get_unique_test_code(tenant: Tenant) -> str:
    """
    Generate a unique test code for a given tenant.

    This function generates a random string of a specified length, using uppercase ASCII characters and digits. 
    The generated string is prefixed with 'Q'. The function then checks if a test with the same code already exists 
    for the given tenant. If such a test exists, the function retries the generation process up to a maximum number 
    of retries. If the maximum number of retries is reached, the length of the test code is increased by one and 
    the retry count is reset to zero. This process continues until a unique test code is generated.

    Parameters:
    tenant (Tenant): The tenant for which the test code is being generated. This should be an instance of the Tenant model.

    Returns:
    str: A unique test code for the given tenant. The test code is a string starting with 'Q', followed by a combination 
    of uppercase ASCII characters and digits.

    Example:
    >>> tenant = Tenant.objects.get(name='example_tenant')
    >>> get_unique_test_code(tenant)
    'Q3FZ7A'
    """
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
def get_unique_deep_dive_access_code(tenant: Tenant) -> str:

    global DEEPDIVE_CODE_LENGTH

    access_code = get_random_string(
        length=DEEPDIVE_CODE_LENGTH, allowed_chars=STRING_ASCII_DIGITS)

    access_code = add_prefix('D', access_code)
    retries = 0
    while SignatureBot.objects.filter(tenant_id=tenant.uid,
                              access_code=access_code,
                              deleted=0).exists():
        if retries >= DEEPDIVE_CODE_GENERATION_MAX_RETRY:
            DEEPDIVE_CODE_LENGTH += 1
            retries = 0
            logger.info(
                "[get_unique_deep_dive_access_code] increased length of code to %s", DEEPDIVE_CODE_LENGTH)

        access_code = get_random_string(
            length=DEEPDIVE_CODE_LENGTH, allowed_chars=STRING_ASCII_DIGITS)
        access_code = add_prefix('D', access_code)
        retries += 1

    return access_code


@timeit
def create_test(tenant: Tenant,
                test_code:str,
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
                is_pitch: bool,
                articles:str,
                bot_name:str,
                creator_user_id:str,
                competency_group: str,
                area_domain:str,
                tab_category:str,
                is_recommended:bool,
                visual_tags: str,
                page_name: str,
                scenario_summary:str,
                creator_email:str,
                is_assigned:bool,
                assigned_to: str,
                assigned_by: str,
                web_page_url:str,
                sub_tab_category:str,
                calculate_culture: bool,
                snippet_url: str,
                pshycometric_sections: dict,
                psychometric:str,
                report_description:str,
                category: str,
                is_single_select:bool,
                psychometric_report_config:str,
                personality_model: str,
                skill_domain: str,
                creator_prompt_type:str,
                video_script:str,
                script_video_link: str,
                feedback_script_video_link:str,
                feedback_video_script_template:str) -> tuple[Test, list[TestQuestion]]:
    """
    This function creates a new test and its associated questions in the database.

    The function first validates the creator_id, then creates a new Test object with the provided parameters.
    It then iterates over the list of questions, creating a new TestQuestion object for each one and appending it to the test_questions list.

    Args:
        tenant (Tenant): The tenant object.
        creator_id (str): The unique identifier of the test creator.
        title (str): The title of the test.
        description (str): The description of the test.
        candidate_type (str): The type of candidate for the test.
        email_address_list (str): The list of email addresses to send the test to.
        max_test_allowed (int): The maximum number of tests allowed.
        send_only_to_email (bool): Flag to determine if the test should only be sent to the email.
        interaction_mode (str): The mode of interaction for the test.
        test_type (str): The type of the test.
        gpt_prompt_override (str): The GPT prompt override for the test.
        email_candidate (bool): Flag to determine if the candidate should be emailed.
        test_related_context (str): The context related to the test.
        orchestrated_conversation_details (dict): The details of the orchestrated conversation.
        description_media (str): The media description of the test.
        is_single_bot (bool): Flag to determine if the test is a single bot.
        is_checkin_type (bool): Flag to determine if the test is a checkin type.
        skills_to_evaluate (str): The skills to evaluate in the test.
        tedtalk_and_hbr_case (str): The TED Talk and HBR case for the test.
        is_learner_path (bool): Flag to determine if the test is a learner path.
        is_email_type (bool): Flag to determine if the test is an email type.
        scenario_case (str): The scenario case for the test.
        is_game_type (bool): Flag to determine if the test is a game type.
        is_free (bool): Flag to determine if the test is free.
        is_micro (bool): Flag to determine if the test is micro.
        image_url (str): The URL of the image for the test.
        rating (str): The rating of the test.
        source (str): The source of the test.
        client_name (str): The name of the client.
        questions (list): The list of questions for the test.
        goals (str): The goals of the test.
        course (str): The course of the test.
        industry (str): The industry of the test.
        exp_level (str): The experience level of the test.
        total_question (int): The total number of questions in the test.
        certificate_details (dict): The details of the certificate for the test.
        ui_information (dict): The UI information for the test.
        is_self_created (bool): Flag to determine if the test is self created.
        is_logged_in (bool): Flag to determine if the user is logged in.
        is_immersive (bool): Flag to determine if the test is immersive.
        media_props (dict): The media properties for the test.
        is_transcript_only (bool): Flag to determine if the test is transcript only.
        is_pitch (bool): Flag to determine if the test is a pitch.
        articles (str): The articles for the test.
        bot_name (str): The name of the bot for the
        creator_user_id (str): The unique identifier of the user who created the test.
        competency_group (str): The competency group for the test.
        area_domain (str): The area domain for the test.
        tab_category (str): The tab category for the test.

    Returns:
        tuple: A tuple containing the created Test object and a list of created TestQuestion objects.

    Raises:
        serializers.ValidationError: If the creator_id does not exist in the database.

    Example:
        >>> tenant = Tenant(uid='123')
        >>> creator_id = 'abc'
        >>> title = 'Test Title'
        >>> description = 'Test Description'
        >>> candidate_type = 'Type1'
        >>> email_address_list = 'test@example.com'
        >>> max_test_allowed = 10
        >>> send_only_to_email = False
        >>> interaction_mode = 'Mode1'
        >>> test_type = 'Type2'
        >>> gpt_prompt_override = 'Override1'
        >>> email_candidate = True
        >>> test_related_context = 'Context1'
        >>> orchestrated_conversation_details = {}
        >>> description_media = 'Media1'
        >>> is_single_bot = True
        >>> is_checkin_type = False
        >>> skills_to_evaluate = 'Skill1, Skill2'
        >>> tedtalk_and_hbr_case = 'Case1'
        >>> is_learner_path = False
        >>> is_email_type = True
        >>> scenario_case = 'Case2'
        >>> is_game_type = False
        >>> is_free = True
        >>> is_micro = False
        >>> image_url = 'http://example.com/image.jpg'
        >>> rating = '5'
        >>> source = 'Source1'
        >>> client_name = 'Client1'
        >>> questions = ['Question1', 'Question2']
        >>> goals = 'Goal1, Goal2'
        >>> course = 'Course1'
        >>> industry = 'Industry1'
        >>> exp_level = 'Level1'
        >>> total_question = 2
        >>> certificate_details = {}
        >>> ui_information = {}
        >>> is_self_created = True
        >>> is_logged_in = True
        >>> is_immersive = False
        >>> media_props = {}
        >>> is_transcript_only = False
        >>> is_pitch = True
        >>> articles = 'Article1, Article2'
        >>> bot_name = 'Bot1'
        >>> creator_user_id = 'abc'
        >>> competency_group = 'Group1'
        >>> area_domain = 'Domain1'
        >>> tab_category = 'Category1'
        >>> create_test(tenant, creator_id, title, description, candidate_type, email_address_list, max_test_allowed, send_only_to_email, interaction_mode, test_type, gpt_prompt_override, email_candidate, test_related_context, orchestrated_conversation_details, description_media, is_single_bot, is_checkin_type, skills_to_evaluate, tedtalk_and_hbr_case, is_learner_path, is_email_type, scenario_case, is_game_type, is_free, is_micro, image_url, rating, source, client_name, questions, goals, course, industry, exp_level, total_question, certificate_details, ui_information, is_self_created, is_logged_in, is_immersive, media_props, is_transcript_only, is_pitch, articles, bot_name, creator_user_id, competency_group, area_domain, tab_category)
        (<Test: Test object (1)>, [<TestQuestion: TestQuestion object (1)>, <TestQuestion: TestQuestion object (2)>])
    """

    try:
        creator = User.objects.get(
            tenant_id=tenant.uid, uid=creator_id, deleted=0)
    except User.DoesNotExist as e:
        logger.exception(
            "failed to create test, creator with id %s does not exist", creator_id)
        raise serializers.ValidationError("invalid creator id")

    if psychometric:
        psychometric = Psychometric.objects.get(uid=psychometric)
    if psychometric_report_config:
        psychometric_report_config = PsychometricReportSection.objects.get(uid=psychometric_report_config)
        
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
            is_pitch=is_pitch,
            articles=articles,
            bot_name=bot_name,
            creator_user_id=creator_user_id,
            competency_group=competency_group,
            area_domain=area_domain,
            tab_category=tab_category,
            is_recommended=is_recommended,
            visual_tags=visual_tags,
            page_name=page_name,
            scenario_summary=scenario_summary,
            creator_email=creator_email,
            is_assigned=is_assigned,
            assigned_to=assigned_to,
            assigned_by=assigned_by,
            web_page_url=web_page_url,
            sub_tab_category=sub_tab_category,
            calculate_culture=calculate_culture,
            snippet_url=snippet_url,
            pshycometric_sections=pshycometric_sections,
            psychometric=psychometric,
            report_description=report_description,
            category=category,
            is_single_select=is_single_select,
            psychometric_report_config=psychometric_report_config,
            personality_model=personality_model,
            skill_domain=skill_domain,
            creator_prompt_type=creator_prompt_type,
            feedback_script_video_link=feedback_script_video_link,
            script_video_link=script_video_link,
            video_script=video_script,
            feedback_video_script_template=feedback_video_script_template
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
                key_learning_skills=kls,
                snippet_url=question.get('snippet_url')
            )

            #
            # upsert_into_skill_index(tenant_id=tenant.uid,
            #                         skills=test_q.key_learning_skills.split(","))

            test_questions.append(test_q)

    logger.info("created test for tenant %s", tenant.uid)

    return test, test_questions

@timeit
def update_test(tenant: Tenant,
                test_code: str,
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
                is_pitch: bool,
                articles:str,
                bot_name:str,
                creator_user_id:str,
                competency_group: str,
                area_domain:str,
                tab_category:str,
                is_recommended:bool,
                visual_tags: str,
                page_name: str,
                scenario_summary:str,
                creator_email:str,
                is_assigned:bool,
                assigned_to: str,
                assigned_by: str,
                web_page_url:str,
                sub_tab_category:str,
                calculate_culture: bool,
                snippet_url: str,
                pshycometric_sections: dict,
                psychometric:str,
                report_description:str,
                category: str,
                is_single_select:bool,
                psychometric_report_config:str,
                personality_model: str,
                skill_domain: str,
                creator_prompt_type:str, 
                video_script:str,
                script_video_link: str,
                feedback_script_video_link:str,
                feedback_video_script_template:str
                ) -> tuple[Test, list[TestQuestion]]:
    
    try:
        test = Test.objects.get(tenant_id=tenant.uid, test_code=test_code)
    except Test.DoesNotExist:
        logger.exception("failed to update test, test with code %s does not exist", test_code)
        raise serializers.ValidationError("invalid test code")

    try:
        creator = User.objects.get(tenant_id=tenant.uid, uid=creator_id, deleted=0)
    except User.DoesNotExist:
        logger.exception("failed to update test, creator with id %s does not exist", creator_id)
        raise serializers.ValidationError("invalid creator id")

    with transaction.atomic():
        # Only update fields if the new value is different from the current value
        if test.title != title:
            test.title = title
        if test.candidate_type != candidate_type:
            test.candidate_type = candidate_type
        if test.email_address_list != email_address_list:
            test.email_address_list = email_address_list
        if test.send_only_to_email != send_only_to_email:
            test.send_only_to_email = send_only_to_email
        if test.email_candidate != email_candidate:
            test.email_candidate = email_candidate
        if test.gpt_prompt_override != gpt_prompt_override:
            test.gpt_prompt_override = gpt_prompt_override
        if test.description != description:
            test.description = description
        if test.interaction_mode != interaction_mode:
            test.interaction_mode = interaction_mode
        if test.test_type != test_type:
            test.test_type = test_type
        if test.is_single_bot != is_single_bot:
            test.is_single_bot = is_single_bot
        if test.skill_domain != skill_domain:
            test.skill_domain = skill_domain
        if test.creator_prompt_type != creator_prompt_type:
            test.creator_prompt_type = creator_prompt_type
        if test.is_learner_path != is_learner_path:
            test.is_learner_path = is_learner_path
        if test.is_checkin_type != is_checkin_type:
            test.is_checkin_type = is_checkin_type
        if test.is_email_type != is_email_type:
            test.is_email_type = is_email_type
        if test.skills_to_evaluate != skills_to_evaluate:
            test.skills_to_evaluate = skills_to_evaluate
        if test.tedtalk_and_hbr_case != tedtalk_and_hbr_case:
            test.tedtalk_and_hbr_case = tedtalk_and_hbr_case
        if test.test_related_context != test_related_context:
            test.test_related_context = test_related_context
        if test.orchestrated_conversation_details != orchestrated_conversation_details:
            test.orchestrated_conversation_details = orchestrated_conversation_details
        if test.description_media != description_media:
            test.description_media = description_media
        if test.max_test_allowed != max_test_allowed:
            test.max_test_allowed = max_test_allowed
        if test.scenario_case != scenario_case:
            test.scenario_case = scenario_case
        if test.is_game_type != is_game_type:
            test.is_game_type = is_game_type
        if test.is_free != is_free:
            test.is_free = is_free
        if test.is_micro != is_micro:
            test.is_micro = is_micro
        if test.rating != rating:
            test.rating = rating
        if test.image_url != image_url:
            test.image_url = image_url
        if test.source != source:
            test.source = source
        if test.client_name != client_name:
            test.client_name = client_name
        if test.goals != goals:
            test.goals = goals
        if test.course != course:
            test.course = course
        if test.industry != industry:
            test.industry = industry
        if test.exp_level != exp_level:
            test.exp_level = exp_level
        if test.total_question != total_question:
            test.total_question = total_question
        if test.certificate_details != certificate_details:
            test.certificate_details = certificate_details
        if test.ui_information != ui_information:
            test.ui_information = ui_information
        if test.is_self_created != is_self_created:
            test.is_self_created = is_self_created
        if test.is_logged_in != is_logged_in:
            test.is_logged_in = is_logged_in
        if test.is_immersive != is_immersive:
            test.is_immersive = is_immersive
        if test.media_props != media_props:
            test.media_props = media_props
        if test.is_transcript_only != is_transcript_only:
            test.is_transcript_only = is_transcript_only
        if test.is_pitch != is_pitch:
            test.is_pitch = is_pitch
        if test.articles != articles:
            test.articles = articles
        if test.bot_name != bot_name:
            test.bot_name = bot_name
        if test.creator_user_id != creator_user_id:
            test.creator_user_id = creator_user_id
        if test.competency_group != competency_group:
            test.competency_group = competency_group
        if test.area_domain != area_domain:
            test.area_domain = area_domain
        if test.tab_category != tab_category:
            test.tab_category = tab_category
        if test.is_recommended != is_recommended:
            test.is_recommended = is_recommended
        if test.visual_tags != visual_tags:
            test.visual_tags = visual_tags
        if test.page_name != page_name:
            test.page_name = page_name
        if test.scenario_summary != scenario_summary:
            test.scenario_summary = scenario_summary
        if test.creator_email != creator_email:
            test.creator_email = creator_email
        if test.is_assigned != is_assigned:
            test.is_assigned = is_assigned
        if test.assigned_to != assigned_to:
            test.assigned_to = assigned_to
        if test.assigned_by != assigned_by:
            test.assigned_by = assigned_by
        if test.web_page_url != web_page_url:
            test.web_page_url = web_page_url
        if test.sub_tab_category != sub_tab_category:
            test.sub_tab_category = sub_tab_category
        if test.calculate_culture != calculate_culture:
            test.calculate_culture = calculate_culture
        if test.snippet_url != snippet_url:
            test.snippet_url = snippet_url
        if test.report_description != report_description:
            test.report_description = report_description
        if test.category != category:
            test.category = category
        if test.is_single_select != is_single_select:
            test.is_single_select = is_single_select
        if test.psychometric_report_config != psychometric_report_config:
            test.psychometric_report_config = psychometric_report_config
        if test.personality_model != personality_model:
            test.personality_model = personality_model

        if test.video_script != video_script:
            test.video_script = video_script
        if test.script_video_link != script_video_link:
            test.script_video_link = script_video_link
        if test.feedback_script_video_link != feedback_script_video_link:
            test.feedback_script_video_link = feedback_script_video_link
        if test.feedback_video_script_template != feedback_video_script_template:
            test.feedback_video_script_template = feedback_video_script_template

        test.save()

        # Update or create test questions
        test_questions = []
        for question in questions:
            if question.get("question_id"):  # Update existing question
                try:
                    test_q = TestQuestion.objects.get(tenant_id=tenant.uid, test_id=test.uid, uid=question.get("question_id"))
                    # Only update fields if the new value is different from the current value


                    if test_q.media_link != question.get("media_link"):
                        test_q.media_link = question.get("media_link")

                    if test_q.gpt_prompt_override != question.get("gpt_prompt_override"):
                        test_q.gpt_prompt_override = question.get("gpt_prompt_override")

                    if test_q.question != question.get("question"):
                        test_q.question = question.get("question")

                    if test_q.can_be_skipped != question.get("can_be_skipped", False):
                        test_q.can_be_skipped = question.get("can_be_skipped", False)

                    if test_q.is_view_only != question.get("is_view_only", False):
                        test_q.is_view_only = question.get("is_view_only", False)

                    if test_q.subjective_answer != question.get("subjective_answer"):
                        test_q.subjective_answer = question.get("subjective_answer")

                    if test_q.objective_answer != question.get("objective_answer"):
                        test_q.objective_answer = question.get("objective_answer")

                    if test_q.mcq_options != question.get("mcq_options"):
                        test_q.mcq_options = question.get("mcq_options")

                    if test_q.mcq_answer != question.get("mcq_answer"):
                        test_q.mcq_answer = question.get("mcq_answer")

                    if test_q.mcq_path != question.get('mcq_path'):
                        test_q.mcq_path = question.get('mcq_path')

                    if test_q.loader_wait_text != question.get("loader_wait_text"):
                        test_q.loader_wait_text = question.get("loader_wait_text")
                        
                    if not(test.test_type == TestTypeChoices.orchestrated_conversation or test.test_type == TestTypeChoices.dynamic_discussion or test.test_type == TestTypeChoices.dynamic_discussion_thread):
                        if test_q.key_learning_point != (question.get("key_learning_point")
                                                        or get_question_key_learning_point(test_title=title, test_question=question.get("question"))):
                            test_q.key_learning_point = (question.get("key_learning_point")
                                                        or get_question_key_learning_point(test_title=title, test_question=question.get("question")))
                        if test_q.key_learning_skills != (question.get("key_learning_skills")
                                                        or get_question_key_learning_skills(test_title=title, test_question=question.get("question"))):
                            test_q.key_learning_skills = (question.get("key_learning_skills")
                                                        or get_question_key_learning_skills(test_title=title, test_question=question.get("question")))
                                                        
                    if test_q.snippet_url != question.get('snippet_url'):
                        test_q.snippet_url = question.get('snippet_url')

                    test_q.save()
                except TestQuestion.DoesNotExist:
                    logger.exception("failed to update question, question with id %s does not exist", question.get("question_id"))
                    raise serializers.ValidationError("invalid question id")
            else:  # Create a new question
                test_q = TestQuestion.objects.create(
                    tenant_id=tenant.uid,
                    test_id=test.uid,
                    question_number=question.get("question_number"),
                    question_type=question.get("question_type"),
                    question_for=question.get("question_for"),
                    media_link=question.get("media_link"),
                    gpt_prompt_override=question.get("gpt_prompt_override"),
                    question=question.get("question"),
                    can_be_skipped=question.get("can_be_skipped", False),
                    is_view_only=question.get("is_view_only", False),
                    subjective_answer=question.get("subjective_answer"),
                    objective_answer=question.get("objective_answer"),
                    mcq_options=question.get("mcq_options"),
                    mcq_answer=question.get("mcq_answer"),
                    mcq_path=question.get('mcq_path'),
                    loader_wait_text=question.get("loader_wait_text"),
                    key_learning_point=(
                        question.get("key_learning_point")
                        or get_question_key_learning_point(test_title=title, test_question=question.get("question"))
                    ),
                    key_learning_skills=(
                        question.get("key_learning_skills")
                        or get_question_key_learning_skills(test_title=title, test_question=question.get("question"))
                    ),
                    snippet_url=question.get('snippet_url')
                )
                test_questions.append(test_q)

    logger.info("updated test for tenant %s", tenant.uid)

    return test, test_questions


@timeit
def create_test_invite(tenant: Tenant,
                       test_id: str,
                       participant_id: str,
                       expires_at: str) -> TestInvite:
    """
    This function creates a new test invitation in the database.

    The function first validates the test_id and participant_id by checking if they exist in the database. 
    If either does not exist, it raises a ValidationError. 
    If both exist, it creates a new TestInvite object with the provided parameters and returns it.

    Args:
        tenant (Tenant): The tenant object.
        test_id (str): The unique identifier of the test.
        participant_id (str): The unique identifier of the participant.
        expires_at (str): The expiration date of the invitation in string format (YYYY-MM-DD HH:MM:SS).

    Returns:
        TestInvite: The newly created TestInvite object.

    Raises:
        serializers.ValidationError: If the test_id or participant_id does not exist.

    Example:
        >>> tenant = Tenant.objects.get(uid='tenant1')
        >>> create_test_invite(tenant, 'test1', 'participant1', '2022-12-31 23:59:59')
        <TestInvite: TestInvite object (1)>
    """
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
                                        participant_id: str,
                                        is_signature_bot: bool,
                                        is_idp_discussion_opted:bool,
                                        intake_id: str) -> TestAttemptSession:
    """
    Creates a test question answer session for a participant.

    This function is responsible for creating a new test attempt session for a given participant. It first checks if the participant is not a signature bot and if the test has not exceeded the maximum allowed attempts. If the test has a limit on the number of attempts and it's not zero, it decreases the count by one. 

    If a test invite ID is provided, it validates the existence of the test invite. It also validates the existence of the participant. 

    If the participant is a signature bot, it retrieves the signature bot object and assigns its UID to the test ID. 

    Finally, it creates a new TestAttemptSession object with the provided details and the current time as the start time. The session is set to expire 30 minutes from the start time.

    Args:
        tenant (Tenant): The tenant object.
        test_id (str): The ID of the test.
        test_invite_id (str): The ID of the test invite.
        participant_id (str): The ID of the participant.
        is_signature_bot (bool): Indicates if the participant is a signature bot.
        is_idp_discussion_opted (bool): Indicates if the participant opted for IDP discussion.

    Returns:
        TestAttemptSession: The created test question answer session object.

    Raises:
        serializers.ValidationError: If the test ID, test invite ID, or participant ID is invalid, or if the maximum number of test attempts has been exceeded.

    Example:
        >>> tenant = Tenant.objects.get(uid='tenant1')
        >>> create_test_question_answer_session(tenant, 'test1', 'invite1', 'participant1', False, False)
        <TestAttemptSession: TestAttemptSession object (1)>
    """
    test = None
    try:
        if not is_signature_bot:
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

    if is_signature_bot:
        signature_bot = SignatureBot.objects.get(tenant_id=tenant.uid, bot_id=test_id, deleted=0)
        test_id = signature_bot.uid
    
    test_attempt_session = TestAttemptSession.objects.create(
        tenant_id=tenant.uid,
        test_id=test_id,
        participant_id=participant_id,
        test_invite_id=test_invite_id,
        started_at=now,
        expires_at=now + datetime.timedelta(minutes=30),
        is_checkin_type= test.is_checkin_type if not is_signature_bot else False,
        is_idp_discussion_opted=is_idp_discussion_opted,
        intake_id=intake_id,
        is_signature_bot=is_signature_bot
    )

    logger.info("created test_attempt_session for tenant %s", tenant.uid)

    if test and  test.scenario_case == ScenarioCaseChoices.game:
        # initializing first question

        first_question_text = gemini_chat_completion(
                                prompt=test.gpt_prompt_override,
                                previous_conv=[{
                                    "role": "user",
                                    "text": "START"
                                }],
                                temperature=0,
                                top_p=0,
                                # models=["gemini-1.5-flash-001","gemini-1.5-pro-001","gemini-1.0-pro"],
                            )

        TestQuestionResponse.objects.create(
            tenant_id=test_attempt_session.tenant_id,
            test_attempt_session_id=test_attempt_session.uid,
            question_id=str(test_attempt_session.uid) + f'-1',
            question_text = first_question_text
        )

    return test_attempt_session


@timeit
def create_test_question_answer(tenant: Tenant,
                                test_attempt_session_id: str,
                                question_id: str,
                                response_file: str = None,
                                response_text: str = None,
                                is_whatsapp: bool = False) -> TestQuestionResponse:
    """
    Creates a TestQuestionResponse object for a given test attempt session and question.

    This function first retrieves the TestAttemptSession and TestQuestion objects using the provided IDs. 
    If the question is for the user and no response file or text is provided, it raises a ValidationError. 
    It then attempts to create a TestQuestionResponse object with the provided details. 
    If the creation fails, it retrieves the first existing TestQuestionResponse object with the same test_attempt_session_id and question_id. 
    Depending on the test type and the question for, it processes the response differently.

    Args:
        tenant (Tenant): The Tenant object for which the TestQuestionResponse is to be created.
        test_attempt_session_id (str): The unique identifier of the TestAttemptSession.
        question_id (str): The unique identifier of the TestQuestion.
        response_file (str, optional): The response file. Defaults to None.
        response_text (str, optional): The response text. Defaults to None.
        is_whatsapp (bool, optional): A flag indicating whether the response is from WhatsApp. Defaults to False.

    Raises:
        serializers.ValidationError: If the TestAttemptSession or TestQuestion does not exist, or if the question is for the user and no response file or text is provided.

    Returns:
        TestQuestionResponse: The created or retrieved TestQuestionResponse object.

    Example:
        >>> tenant = Tenant.objects.get(uid='tenant_uid')
        >>> create_test_question_answer(tenant, 'test_attempt_session_id', 'question_id', response_text='This is a response')
        <TestQuestionResponse: TestQuestionResponse object (1)>
    """
    try:
        test_attempt_session = TestAttemptSession.objects.get(
            tenant_id=tenant.uid, uid=test_attempt_session_id, deleted=0)
    except TestAttemptSession.DoesNotExist as e:
        logger.exception("failed to get session, test attempt session with id %s does not exist",
                         test_attempt_session_id)
        raise serializers.ValidationError("invalid test_attempt_session_id")

    test = Test.objects.get(uid=test_attempt_session.test_id)
    
    if test.scenario_case == ScenarioCaseChoices.game:
        if response_file is None and response_text is None:
            raise serializers.ValidationError("response is required for game test")
        
        # here we will save response to last created question response since 
        # it's already created while test attempt creation

        test_question_response = TestQuestionResponse.objects.filter(tenant_id=tenant.uid,
                                                                     deleted=False,
                                                                     test_attempt_session_id=test_attempt_session_id
                                                                     ).last()
        if not test_question_response:
            raise serializers.ValidationError("no question response found for this test attempt session")
        # saving response text or response file

        test_question_response.response_file = response_file
        test_question_response.response_text = response_text
        test_question_response.evaluation_status = TestQuestionResponseEvaluationStatusChoices.success

        test_question_response.save(update_fields=['response_file', 'response_text', 'evaluation_status'])
        

        test_question_response.refresh_from_db()

        print(test_question_response.response_text)
        return process_dynamic_game(
            test=test,
            test_question_response=test_question_response,
            test_attempt_session=test_attempt_session
        )

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
    """
    it soft delete test response
    """
    test_response.deleted = test_response.deleted + 1
    test_response.save()



#*********************** Process MCQ response start *******************************
@timeit
def process_mcq_response(test_question_response: TestQuestionResponse, is_whatsapp: bool = False):
    """
    This function processes the response of a multiple-choice question (MCQ) from a test session.

    The function retrieves the test question and test session related to the response. It then generates a comment on the user's decision using a generic completion function. The selected skill from the MCQ options is also identified and saved. The function updates the evaluation status of the test question response to 'success'. If the processed question is the last one in the test session, the function marks the session as completed and generates a summary of the user's decisions throughout the test. It also updates the SkillsRating object related to the participant.

    Parameters:
    test_question_response (TestQuestionResponse): The test question response object that needs to be processed.
    is_whatsapp (bool, optional): A flag indicating if the test was taken on WhatsApp. Defaults to False.

    Returns:
    TestQuestionResponse: The updated test question response object.

    Example:
    Given a TestQuestionResponse object with uid '123', question_id '456', test_attempt_session_id '789', and response_text 'Option A', the function will update the feedback_text, mcq_skill, and evaluation_status fields of the object. If this is the last question in the test session, the function will also update the status and finished_at fields of the related TestAttemptSession object, and update the total_questions_attempted and total_tests_attempted fields of the related SkillsRating object.
    """
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
@timeit
def extract_mcq_options_from_response(text):
    """
    This function extracts multiple choice question (MCQ) options from a given text.

    The function uses regular expressions to search for a specific pattern in the text. The pattern is defined as follows:
    "Situation:(.*?)Choice 1:(.*?)Choice 2:", where (.*?) is a non-greedy match for any characters. 

    The function then extracts the matched groups and assigns them to the variables 'next_question', 'choice1', and 'choice2'. 
    The 'next_question' and 'choice1' are extracted directly from the regex match, while 'choice2' is extracted by splitting the text on "Choice 2:" and taking the second part.

    If the pattern is not found in the text, the function logs an error message.

    Args:
        text (str): The input text from which to extract the MCQ options. The text should be formatted as follows: 
        "Situation: <situation text> Choice 1: <choice 1 text> Choice 2: <choice 2 text>"

    Returns:
        dict: A dictionary containing the next situation and the two choices. The keys of the dictionary are 'next_situation', 'option_a', and 'option_b'. 
        If the pattern is not found in the text, the function returns None.

    Example:
        >>> extract_mcq_options_from_response("Situation: You see a cat. Choice 1: Pet the cat. Choice 2: Ignore the cat.")
        {'next_situation': 'You see a cat.', 'option_a': 'Pet the cat.', 'option_b': 'Ignore the cat.'}
        
    """
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

@timeit
def process_dynamic_mcq_response(test_question_response: TestQuestionResponse, is_whatsapp: bool = False):
    """
    This function processes the response of a dynamic multiple-choice question (MCQ) in a test session.

    The function retrieves the related test question and test attempt session from the database. It checks if the test session is already completed, and if so, it returns the test question response without further processing. 

    The function then updates the metadata of the test question response with the question from the test attempt session's feedback summary. It also retrieves the related test from the database.

    The function generates a comment on the user's decision using the `generic_completion` function and updates the test question response with this comment. It also sets the `mcq_skill` field to 'NA' and the `evaluation_status` field to 'success'.

    If the current question is the last question in the test, the function marks the test session as completed and generates a summary of the user's decisions throughout the test. It also generates a list of skills using the `get_dynamic_mcq_skills_prompt` and `generic_completion` functions.

    The function then generates a session report link and updates the `SkillsRating` object related to the participant with the total number of questions attempted and total tests attempted.

    Parameters:
    test_question_response (TestQuestionResponse): The test question response object to be processed.
    is_whatsapp (bool, optional): A flag indicating whether the test is conducted on WhatsApp. Defaults to False.

    Returns:
    TestQuestionResponse: The updated test question response object.

    Example:
    >>> process_dynamic_mcq_response(test_question_response_obj)
    <TestQuestionResponse: TestQuestionResponse object (1)>
    """    
    
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
    """
    This function processes a test question response and updates the test attempt session status if the question is the last one.

    The function first retrieves the question and test attempt session associated with the given test question response. 
    If the test attempt session is already completed, the function returns the test question response without any further processing.

    If the question is the last one in the test, the function enters a loop where it waits for all previous questions to be processed. 
    This is done by checking the count of not yet evaluated test responses. If all previous questions are processed or a time limit is reached, 
    the loop is exited.

    If the question is the last one and the test type is not 'dynamic_mcq', the function attempts to update the test attempt session status to 'completed'. 
    If the update is successful, the function calls the '__process_test_response' function to further process the test question response.

    Finally, the function refreshes the test question response from the database to reflect any changes made during the processing and returns it.

    Args:
        test_question_response (TestQuestionResponse): The test question response to be processed.
        is_whatsapp (bool, optional): A flag indicating whether the response is from WhatsApp. Defaults to False.

    Returns:
        TestQuestionResponse: The processed test question response.

    Raises:
        ValueError: If unable to evaluate response within the time limit.
        Exception: If there is an error while updating the test attempt session status.

    Example:
        >>> process_test_response(test_question_response_obj, is_whatsapp=True)
        <TestQuestionResponse: TestQuestionResponse object (1)>
    """
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
    """
    This function evaluates the relevance of a test question response.

    The function uses the `evaluate_relevacy` helper function to determine the relevance score of the response to the question.
    If the evaluation fails, the test question response is marked as failed and deleted. If the evaluation is successful, the relevance score is saved in the `relevance` field of the `test_question_response` object.

    Parameters:
    question (Question): The Question object that the response is for.
    test_question_response (TestQuestionResponse): The TestQuestionResponse object that contains the response to be evaluated.
    test (Test): The Test object that the question and response are part of.
    test_attempt_session (TestAttemptSession): The TestAttemptSession object that represents the session of the test attempt.

    Returns:
    None. The function updates the `relevance` field of the `test_question_response` object in-place.

    Raises:
    ValueError: If the evaluation fails and a relevance score cannot be obtained.

    Example:
    >>> question = Question.objects.get(id=1)
    >>> test_question_response = TestQuestionResponse.objects.get(id=1)
    >>> test = Test.objects.get(id=1)
    >>> test_attempt_session = TestAttemptSession.objects.get(id=1)
    >>> evaluate_relevence_thread(question, test_question_response, test, test_attempt_session)
    """

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
    """
    Evaluates the rating for a given response to a test question during a training process in a separate thread.

    This function uses the `evaluate_rating_for_process_training` function to evaluate the candidate's response to a test question. 
    The evaluation is based on a comparison between the candidate's answer and the correct answer. 
    If the evaluation is successful, the rating is saved in the `test_question_response` object. 
    If the evaluation fails, the `test_question_response` object is marked as failed and deleted.

    Args:
        question (object): The test question object.
        test_question_response (object): The test question response object.
        test (object): The test object.
        test_attempt_session (object): The test attempt session object.

    Raises:
        ValueError: If the evaluation fails.

    Example:
        >>> question = TestQuestion.objects.get(id=1)
        >>> test_question_response = TestQuestionResponse.objects.get(id=1)
        >>> test = Test.objects.get(id=1)
        >>> test_attempt_session = TestAttemptSession.objects.get(id=1)
        >>> evaluate_rating_thread(question, test_question_response, test, test_attempt_session)
        # This will evaluate the rating for the given response and save it in the `test_question_response` object.
    """
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
def evaluate_competency_data_thread(question, test_question_response, test, test_attempt_session,competency_skill):
    """ 
    This function evaluates the competency data for a given test attempt session. It constructs a conversation string from the provided test question responses and then calls the evaluate_competency_data function to evaluate the competency data based on the test description, the constructed conversation, the test attempt session, and the competency skills. The evaluated competency data is then saved to the test attempt session.

    Args: question (obj): The question object. test_question_response (list): A list of test question response objects. test (obj): The test object. test_attempt_session (obj): The test attempt session object. competency_skill (list): A list of competency skills to be evaluated.

    Returns: None. The function saves the evaluated competency data to the test attempt session.

    Example: >>> evaluate_competency_data_thread(question, test_question_response, test, test_attempt_session, ["skill1", "skill2"]) # This will evaluate the competency data for the given test attempt session and save it to the test attempt session.

    Note: This function does not return any value. The evaluated competency data is directly saved to the test attempt session. 
    
    """
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
                                        competency_skill,
                                        test.is_free
                                        )

    
    for skill, values in competency_data.items():
        if values["rating"] in "0":
            values["rating"] = "1"
            values["level"] = "1"
    test_attempt_session.competency_data = competency_data
    test_attempt_session.save(update_fields=["competency_data"])


@timeit
def set_language_skills_in_thread(user_response,test_attempt_session):
    """
    This function is used to evaluate the English language ability of a user based on their response. 
    It uses the Anthropic API to generate a language ability score on a scale of 1 to 10.

    The function constructs a prompt that includes the user's response and sends it to the Anthropic API. 
    The API then generates a completion based on the prompt, which is interpreted as the language ability score. 
    This score is then saved in the `language_skills` field of the `test_attempt_session` object.

    Args:
        user_response (str): The user's response that needs to be evaluated. It should be a string of the user's speech.
        test_attempt_session (TestAttemptSession): The test attempt session object where the language skills score will be stored.

    Returns:
        None. The function doesn't return anything but updates the `language_skills` field of the `test_attempt_session` object.

    Example:
        >>> user_response = "Hello, my name is John Doe. I am a software engineer."
        >>> test_attempt_session = TestAttemptSession.objects.get(id=1)
        >>> set_language_skills_in_thread(user_response, test_attempt_session)
        # This will update the `language_skills` field of the `test_attempt_session` object with the score generated by the Anthropic API.
    """

    language_skills_prompt = f"""
    \n\nHuman:
    Please provide an English language ability score (on a scale of 1 to 10) to a person based on the below recorded speech.

    Candidate answer: ${user_response}

    Always give the output in a single paragraph.
    Keep the output less than 400 words.
    Keep the output more than 200 words.
    Note : Do not include any introduction sentence or word-count in the output.
    \n\nAssistant:"""

    language_skills = generic_completion(prompt=language_skills_prompt, tokens=150, llm_order=['anthropic','gemini','gpt'])
    logger.info(f"===========================> language_skills: {language_skills}")
    test_attempt_session.language_skills = language_skills
    test_attempt_session.save(update_fields=["language_skills"])

@timeit
def speech_metrics_in_thread(test_question_response, transcript):
    """
    Calculate speech metrics for a test question response in a separate thread.

    This function calculates the speech metrics for a given test question response in a separate thread. It uses the CoachMetricApi to get the speech metrics from the audio file associated with the test question response. The calculated speech metrics are then saved to the test question response object.

    Parameters:
    - test_question_response (TestQuestionResponse): The test question response object for which to calculate the speech metrics.
    - transcript (str): The transcript of the audio file associated with the test question response.

    Returns:
    None

    Example Usage:
    speech_metrics_in_thread(test_question_response, transcript)
    """
    speech_met = coach_metric_api.get_speech_metrics_from_audio(
                            test_question_response.response_file,transcript)
    test_question_response.speech_metrics = speech_met
    test_question_response.save(update_fields=["speech_metrics"])

@timeit
def __process_test_response(question: TestQuestion, test: Test, test_attempt_session: TestAttemptSession,
                            test_question_response: TestQuestionResponse, is_whatsapp: bool = False,
                            last_question_number: int = 0):
    """
    Process the test response for a given question in a test attempt session.

    Args:
        question (TestQuestion): The question object for which the response is being processed.
        test (Test): The test object to which the question belongs.
        test_attempt_session (TestAttemptSession): The test attempt session object for the participant.
        test_question_response (TestQuestionResponse): The response object to be processed.
        is_whatsapp (bool, optional): Indicates if the response is from WhatsApp. Defaults to False.
        last_question_number (int, optional): The question number of the last question in the test. Defaults to 0.

    Returns:
        TestQuestionResponse or None: The processed response object or None if the response is view-only.

    Raises:
        ValueError: If the relevancy score cannot be obtained for the response.

    Description:
        This function processes the test response for a given question in a test attempt session. It performs the following steps:

        1. Logs the start of the process.
        2. Refreshes the test attempt session from the database.
        3. Checks the test type and calls the appropriate processing function.
        4. Updates the current and next question indices in the test attempt session.
        5. Saves the updated fields in the test attempt session.
        6. If the question is view-only, sets the evaluation status to success and saves the response.
        7. If the interaction mode is not text, processes the response based on the interaction mode.
        8. Generates a transcription for audio or video responses using the GPT Whisper API or the Speech-to-Text API.
        9. If the test is not free and not transcript-only, and the scenario case is not process training, calculates speech metrics for the response.
        10. Saves the updated fields in the test question response.
        11. If the response text is empty, saves the response again.
        12. If the scenario case is not feedback_role_play, generates the feedback prompt based on the test type and scenario case.
        13. If the test is an email type or employee feedback or English support, generates the feedback using the appropriate prompt template.
        14. If the prompt is overridden, generates the feedback using the overridden prompt.
        15. If the prompt is not overridden, generates the feedback using the chat conversation prompt.
        16. If the response length is too low, sets the feedback text to indicate that no feedback can be generated.
        17. If the scenario case is process_training or the test is transcript-only, sets the feedback text to indicate no feedback.
        18. Generates the feedback using the appropriate model (Anthropic Completion, TextBison Completion, or GPT-3 Completion).
        19. If the feedback text does not meet the criteria, repeats steps 15-18 up to 3 times.
        20. Sets the metadata and feedback text in the test question response.
        21. If the test is pitch-based, sets the language skills in a separate thread.
        22. Sets the evaluation status to success and saves the updated fields in the test question response.
        23. If the evaluation status is not success, saves the response again.
        24. If the test attempt session is completed, updates the finished_at field and calculates the skills rating.
        25. Generates the session report URL.
        26. If the test is free, generates the summary feedback session report URL.
        27. Sends the report link via email if email addresses are provided.
        28. Sends the report link via WhatsApp if the response is from WhatsApp and the test type is not interview.
        29. Logs the end of the process.

    Examples:
        # Example 1: Processing an MCQ response
        question = TestQuestion.objects.get(id=1)
        test = Test.objects.get(id=1)
        test_attempt_session = TestAttemptSession.objects.get(id=1)
        test_question_response = TestQuestionResponse.objects.get(id=1)
        response = __process_test_response(question, test, test_attempt_session, test_question_response)
        # Returns the processed response object

        # Example 2: Processing a dynamic MCQ response
        question = TestQuestion.objects.get(id=2)
        test = Test.objects.get(id=1)
        test_attempt_session = TestAttemptSession.objects.get(id=1)
        test_question_response = TestQuestionResponse.objects.get(id=2)
        response = __process_test_response(question, test, test_attempt_session, test_question_response)
        # Returns the processed response object

        # Example 3: Processing a view-only response
        question = TestQuestion.objects.get(id=3)
        test = Test.objects.get(id=1)
        test_attempt_session = TestAttemptSession.objects.get(id=1)
        test_question_response = TestQuestionResponse.objects.get(id=3)
        response = __process_test_response(question, test, test_attempt_session, test_question_response)
        # Returns None
    """
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

        elif test.scenario_case == ScenarioCaseChoices.english_support:
            prompt = get_english_support_feedback_prompt(
                    prompt_template=question.gpt_prompt_override or test.gpt_prompt_override,
                    test_title=test.title,
                    test_description=test.description,
                    question=question.question,
                    candidate_reply=test_question_response.response_text,
                    user_feedback_prompt=user_feedback_prompt
            )

        elif test.scenario_case == ScenarioCaseChoices.journaling:
            prompt = get_journaling_feedback_prompt(
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
                    user_feedback_prompt=user_feedback_prompt,
                    articles= test.articles,
                    scenario_summary=test.scenario_summary,
                    )


        feedback_text = ''
        raw_text = ''
        response_text = test_question_response.response_text
        go_for_feedback = True

        # words = word_tokenize(test_question_response.response_text)

        # if len(words) <= 10 :
        #     feedback_text = "No feedback can be generated because of too low response length"
        #     go_for_feedback = False

        if test.scenario_case in [ScenarioCaseChoices.psychometric, ScenarioCaseChoices.process_training]:
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
                            
                        elif test.scenario_case == ScenarioCaseChoices.english_support:
                                    prompt = get_english_support_feedback_prompt(
                                                            prompt_template=question.gpt_prompt_override or test.gpt_prompt_override,
                                                            test_title=test.title,
                                                            test_description=test.description,
                                                            question=question.question,
                                                            candidate_reply=test_question_response.response_text,
                                                            user_feedback_prompt=user_feedback_prompt
                                                    )
                                    
                        elif test.scenario_case == ScenarioCaseChoices.journaling:
                            prompt = get_journaling_feedback_prompt(
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
                                    user_feedback_prompt=user_feedback_prompt,
                                    articles=test.articles,
                                    scenario_summary=test.scenario_summary,)

                    max_retry -= 1


                if test.is_free:
                    anthropic_feedback = anthropic_completion(prompt, 1200)
                    if anthropic_feedback:
                        feedback_text = anthropic_feedback
                    else:
                        feedback_text = 'Feedback could not be generated'
                
                else:
                    try:
                        feedback_text = gemini_completion(prompt=prompt,instruction="Please always respond within 150 tokens in summary format. Always respond in a Markdown language.")
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
                    #         feedback_text = gemini_completion(prompt)
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

        if feedback_text:
            feedback_text = re.sub(r'\([^)]*\)', '', feedback_text)   # to remove any word limit in ()
            test_question_response.feedback_text = feedback_text
            updated_fields.append("feedback_text")
            updated_fields.append("metadata")


    if test.scenario_case == ScenarioCaseChoices.pitch:
        threading.Thread(target=set_language_skills_in_thread, args=(test_question_response.response_text,test_attempt_session)).start()


    test_question_response.evaluation_status = TestQuestionResponseEvaluationStatusChoices.success
    test_question_response.save(
        update_fields=updated_fields)

    test_question_response.refresh_from_db()
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
        if user_info.evaluate_relevency:
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
            if user_info.evaluate_relevency:
                relevancy_score, is_evaluated = evaluate_relevacy(test_question_response,
                                                    question.question,
                                                    test_question_response.response_text,
                                                    test.description,
                                                    test.title,
                                                    )

        if user_info.evaluate_relevency and not is_evaluated:
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
        if test.scenario_case in [ScenarioCaseChoices.process_training, ScenarioCaseChoices.psychometric] or test.is_transcript_only:
            # saving psychometric data
            if test.scenario_case == ScenarioCaseChoices.psychometric:
                generate_psychometric_report_data(test=test,test_attempt_session=test_attempt_session)

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
    """
    Process the orchestrated test response by the user.

    Args:
        test_question_response (TestQuestionResponse): The test question response object.

    Returns:
        TestQuestionResponse: The updated test question response object.

    Raises:
        Exception: If there is an error while generating the transcription or speech metrics.

    This function processes the test question response provided by the user. It updates the current and next question status
    in the test attempt session, generates the transcript for the response, and calculates the speech metrics if applicable.
    For dynamic discussion tests, it generates feedback, evaluates relevance, and extracts key learnings and key learning points.

    The function takes a TestQuestionResponse object as input, which contains the response file, response text, and other relevant information.

    Example:
        test_question_response = TestQuestionResponse(
            test_attempt_session_id="123",
            question_id="456",
            response_file="audio.wav",
            response_text="This is my response."
        )
        processed_response = process_orchestrated_test_response_by_user(test_question_response)
    """
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
            elif test.scenario_case == ScenarioCaseChoices.journaling:
                prompt = get_journaling_feedback_prompt(
                        prompt_template=question.gpt_prompt_override or test.gpt_prompt_override,
                        test_title=test.title,
                        test_description=test.description,
                        question=question.question,
                        candidate_reply=test_question_response.response_text,
                        user_feedback_prompt=""
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
                        user_feedback_prompt=""
                    )
                else:
                    prompt = get_chat_conversation_prompt_v3(
                                        test_title=test.title,
                                        test_description=test.description,
                                        question=question_text,
                                        question_context=question.subjective_answer,
                                        candidate_reply=test_question_response.response_text,
                                        user_feedback_prompt="",
                                        articles=test.articles,
                                        scenario_summary=test.scenario_summary,)
        
        feedback_text = generic_completion(prompt=prompt,
                                           tokens=1200, 
                                           fallback_text="Feedback could not be generated",
                                           is_free=test.is_free,
                                           instruction="Please always respond within 150 tokens in summary format. Always respond in a Markdown language."
                                           )
            
        test_question_response.feedback_text = feedback_text
        update_fields.append("feedback_text")
        logger.info(f"************dynamic discussion feedback : {feedback_text}")
        
        user_info = UserAttribute.objects.get(user_id=test_attempt_session.participant_id)

        if user_info.evaluate_relevency:
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
            kls = generic_completion(kls_prompt, 50,'no kls',is_free=test.is_free )
            
            # retry kls if it is not received
            if kls is None or kls == 'no kls' or kls == '':
                kls = gemini_completion(kls_prompt)

            klp_prompt = f"""
                TestTitle: {test.title}
                Question: {question_text}

                For given "Question" and the "TestTitle" extract a key learning from an ideal answer to the "Question"  as "Output". The "Output" should be a single sentence with maximum 25 words, do not append it with "Key Learning:"
                """

            logger.info(f"************dynamic discussion klp prompt : {klp_prompt}")
            klp = generic_completion(klp_prompt, 50, 'no klp',is_free=test.is_free)

            # retry klp if it is not received
            if klp is None or klp == 'no klp' or klp == '':
                klp = gemini_completion(klp_prompt)
            
            test_question_response.kls_klp = {"kls":kls.strip(), "klp":klp.split(':')[-1].strip()}
            update_fields.append("kls_klp")
            logger.info(f"************dynamic discussion kls and klp : {test_question_response.kls_klp}")
            end = time.time()
            logger.info(f"####################### process_orchestrated_test_response_by_user: LOGIC for dynamic discussion took {end - start:.2f} #######################")

    update_fields.extend(["evaluation_status", "updated"])
    test_question_response.evaluation_status = TestQuestionResponseEvaluationStatusChoices.success
    test_question_response.save(update_fields=update_fields)
    logger.info(f"$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$######################IMP :::::::: dynamic discussion response saved : {test_question_response}")

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
    """
    fetches transcript from a response url
    """
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
    """
    To generate speech metrics  from a response_url and transcript.
    """
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
def get_feedback(question, test_question_response, question_text, test):
    """
    This function generates feedback for a given test question response.

    The function first checks if the test conversation should start with a user message. If so, it generates a dynamic discussion prompt. If not, it checks if there is a background context. If there is, it generates an interview feedback prompt. If there is no background context, it checks if there is a gpt prompt override either at the question level or at the test level. If there is, it generates an overridden prompt. If there is no gpt prompt override, it generates a chat conversation prompt.

    The generated prompt is then passed to the `generic_completion` function to generate the feedback text. The feedback text is then saved to the `feedback_text` field of the `test_question_response` object.

    Args:
        question (Question): The Question object for which feedback is to be generated.
        test_question_response (TestQuestionResponse): The TestQuestionResponse object for which feedback is to be generated.
        question_text (str): The text of the question.
        test (Test): The Test object for which feedback is to be generated.

    Returns:
        None. The function saves the generated feedback text to the `feedback_text` field of the `test_question_response` object.

    Example:
        >>> get_feedback(question_obj, test_question_response_obj, "What is your name?", test_obj)
        # This will generate feedback for the given question and save it to the `feedback_text` field of the `test_question_response_obj`.
    """
    # function implementation
    
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
                                    user_feedback_prompt="",
                                    articles=test.articles,
                                    scenario_summary=test.scenario_summary,)
        
    test_question_response.feedback_text = generic_completion(
                                            prompt=prompt,
                                            tokens=1200, 
                                            fallback_text="Feedback could not be generated",
                                            is_free=test.is_free,
                                            instruction="Please always respond within 150 tokens in summary format. Always respond in a Markdown language."
                                            )
    logger.info(f"************dynamic discussion feedback : {test_question_response.feedback_text}")
    test_question_response.save(update_fields=["feedback_text"])


@timeit
def get_relevency_kls_klp(test_question_response, question_text, test):
    """
    This function evaluates the relevance of a test question response, and generates key learning and skills (KLS) and key learning points (KLP) for the question.

    The function first calls the `evaluate_relevacy` function to get a relevance score for the test question response. The relevance score is then saved to the `relevance` field of the `test_question_response` object.

    Next, the function generates a KLS prompt and uses the `generic_completion` function to get the KLS for the question. The KLS is then saved to the `kls_klp` field of the `test_question_response` object.

    Finally, the function generates a KLP prompt and uses the `generic_completion` function to get the KLP for the question. The KLP is then saved to the `kls_klp` field of the `test_question_response` object.

    Args:
        test_question_response (TestQuestionResponse): The test question response object to evaluate.
        question_text (str): The text of the question.
        test (Test): The test object that the question belongs to.

    Returns:
        None. The function updates the `relevance` and `kls_klp` fields of the `test_question_response` object in-place.

    Example:
        >>> get_relevency_kls_klp(test_question_response, "What is the capital of France?", test)
        # This will update the `relevance` and `kls_klp` fields of the `test_question_response` object.
    """
    try:
        logger.info(f"@@@@@@@@@@@@@@@@@@@@@@ getting relevancy, kls, klp  for question ==> {question_text} @@@@@@@@@@@@@@@@@@@@@@")    
        test_attempt_session = TestAttemptSession.objects.get(
            uid=test_question_response.test_attempt_session_id
            )
        user_info = UserAttribute.objects.get(user_id=test_attempt_session.participant_id)
        update_fields = []
        relevancy_score = {'relevance': 1}
        if user_info.evaluate_relevency:
            relevancy_score, is_evaluated = evaluate_relevacy(test_question_response,
                                                    question_text,
                                                    test_question_response.response_text,
                                                    test.description,
                                                    test.title,
                                                    )

            logger.info(f"@@@@@@@@@@@@@@@@@@@@@@ relevancy_score @@@@@@@@@@@@@@@@@@@@@@: {relevancy_score}, is_evaluated: {is_evaluated} ")
        relevance = 1
        if "relevance" in relevancy_score:
            relevance = int(relevancy_score['relevance'])

        test_question_response.relevance = relevance
        update_fields.append("relevance")

        kls_prompt = f"pick most suitable 2 skills for this question: {question_text} from the list of these skills : {test.skills_to_evaluate}. please separate them with comma. do not add extra sentence"
        logger.info(f"************dynamic discussion kls prompt : {kls_prompt}")
        kls = generic_completion(kls_prompt, 50, 'no kls',test.is_free)
        
        logger.info(f"@@@@@@@@@@@@@@@@ kls : {kls} @@@@@@@@@@@@@@@@@@@@@@")

        klp_prompt = f"""
            TestTitle: {test.title}
            Question: {question_text}

            For given "Question" and the "TestTitle" extract a key learning from an ideal answer to the "Question"  as "Output". The "Output" should be a single sentence with maximum 25 words, do not append it with "Key Learning:"
            """

        logger.info(f"************dynamic discussion klp prompt : {klp_prompt}")
        klp = generic_completion(klp_prompt, 50, 'no klp')
        logger.info(f"@@@@@@@@@@@@@@@@ klp : {klp} @@@@@@@@@@@@@@@@@@@@@@")
        
        test_question_response.kls_klp = {"kls":kls.strip(), "klp":klp.split(':')[-1].strip()}
        update_fields.append("kls_klp")
        logger.info(f"************dynamic discussion kls and klp : {test_question_response.kls_klp}")
        
        test_question_response.evaluation_status = TestQuestionResponseEvaluationStatusChoices.success
        update_fields.append("evaluation_status")
        test_question_response.save(update_fields=update_fields)
        logger.info(f"************respone after saving relevancy, kls, klp : {test_question_response.kls_klp}")
        
        logger.info(f"@@@@@@@@@@@@@@@@@@@@@@ done getting relevancy, kls, klp in THREAD for question ===> {question_text} @@@@@@@@@@@@@@@@@@@@@@")

    except Exception as e:
        logger.error(f"@@@@@@@@@@@!!!!!!!!!!!!!!!!Error while getting relevancy, kls, klp: {e}", exc_info=True)


@timeit
def process_dynamic_game(test_question_response:TestQuestionResponse, test:Test
                         ,test_attempt_session:TestAttemptSession):
    
    logger.info("$$$$$$$$$$$$$$$$$$$$$$$$4 Handled by dynamic game thred $$$$$$$$$$$")
    update_fields = []
    if test.interaction_mode != InteractionModeChoices.text:
        update_fields.extend(["response_text"])

        if test.interaction_mode == InteractionModeChoices.audio:
            if test_question_response.response_file:
                transcript, transcript_length = get_transcript(test_question_response)
                test_question_response.response_text = transcript               

        elif test.interaction_mode == InteractionModeChoices.video:
            if test_question_response.response_file:
                transcript, transcript_length = get_transcript(test_question_response)
                test_question_response.response_text = transcript

        elif test.interaction_mode == InteractionModeChoices.any:
            if test_question_response.response_file:
            
                transcript, transcript_length = get_transcript(test_question_response)
                test_question_response.response_text = transcript

        if len(update_fields)>0:
            test_question_response.save(update_fields=update_fields)

    
    # now getting all question response pair for the test_attempt_session
    previous_conversation = [{
                                    "role": "user",
                                    "text": "START"
                                }]
    for question_response in TestQuestionResponse.objects.filter(
        test_attempt_session_id=test_attempt_session.uid,
        deleted=False
    ):
        print(question_response.question_text)
        print(question_response.response_text)
        previous_conversation.append({
            "text": question_response.question_text,
            "role": "model"
        })
        previous_conversation.append({
            "text": question_response.response_text,
            "role": "user"
        })


    next_question = gemini_chat_completion(
        prompt = test.gpt_prompt_override, # we are saving custom prompt in this field
        previous_conv=previous_conversation,
        temperature=0,
        top_p=0,
        # models=["gemini-1.5-flash-001","gemini-1.5-pro-001","gemini-1.0-pro"],
    )

    print(next_question)
    # now checking if the next_question is last/end conversation with score

    score_match = re.search(r'achieved a score of (\d+) out of (\d+)', next_question)
    if score_match:
        score = int(score_match.group(1))  # Extract the achieved score
        # total_score = int(score_match.group(2))  # Extract the total score
        test_attempt_session.test_score = score
        test_attempt_session.finished_at = timezone.now()
        test_attempt_session.status = TestAttemptSessionStatusChoices.completed

        test_attempt_session.save(update_fields=['test_score', 'finished_at', 'status'])
        print("Test completed")

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


            return test_question_response



    new_test_question_response = TestQuestionResponse.objects.create(
        tenant_id=test_attempt_session.tenant_id,
        test_attempt_session_id=test_attempt_session.uid,
        question_id=str(test_attempt_session.uid) + f'-{len(previous_conversation) + 1}',
        question_text = next_question
    )
    
    return new_test_question_response

@timeit
def process_dynamic_threads_response_by_user(test_question_response: TestQuestionResponse):
    """
    This function processes the response of a user in a dynamic thread test scenario. It updates the test attempt session's 
    current and next question status, calculates speech metrics if the interaction mode is audio or video, and generates 
    feedback and relevancy scores for the response. If it's the last response in the test, it also updates the test attempt 
    session status to 'completed' and generates a report.

    Parameters:
    test_question_response (TestQuestionResponse): An instance of the TestQuestionResponse model. This represents the 
    user's response to a test question.

    Process:
    1. Fetches the related test attempt session and test.
    2. Updates the current and next question indices in the test attempt session.
    3. Checks if the current response is the last response in the test.
    4. If the interaction mode is audio or video, it generates a transcript of the response and calculates speech metrics.
    5. If the test type is 'dynamic_discussion_thread', it generates feedback and relevancy scores for the response.
    6. If it's the last response in the test, it updates the test attempt session status to 'completed', calculates group 
       discussion report metrics, and generates a report.

    Returns:
    test_question_response (TestQuestionResponse): The updated TestQuestionResponse instance.

    Example:
    >>> process_dynamic_threads_response_by_user(test_question_response)
    <TestQuestionResponse: TestQuestionResponse object (1)>
    """
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
                logger.info(f"@@@@@@@@@@@@@@@@ getting relevancy, kls, klp in THREAD @@@@@@@@@@@@@@@@@@@@@@")
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

        if test.feedback_video_script_template:
            klps_objects =  TestQuestionResponse.objects.filter(deleted=False,test_attempt_session_id=test_attempt_session.uid).exclude(kls_klp=None) # get all klps
            klps = []
            for klp in klps_objects:
                if klp.kls_klp:
                    klps.append(klp.kls_klp.get('klp'))
            klps = list(set(klps)) # remove duplicates

            feedback_script = Template(test.feedback_video_script_template).safe_substitute(
                klps="\n\n".join(klps)
            )
            test_attempt_session.feedback_video_script = feedback_script
            test_attempt_session.save(update_fields=["feedback_video_script"])
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

    This function processes the response of a bot to a test question in an orchestrated test scenario. 

    The function first checks if the bot already has a response. If it does, the function updates the evaluation status to 'success' and saves the response. If not, it retrieves the question, test attempt session, and test details. It then updates the current and next question indices in the test attempt session.

    The function generates a prompt for the test, test attempt session, and question. It then tries to retrieve previous bot responses. If there are no previous responses, it sets an empty list.

    The function then enters a loop to generate a bot response. If the test is being conducted over WhatsApp, it uses the gpt3_completion function. Otherwise, it uses the anthropic_completion function for the first iteration, gpt3_completion for the second, and gemini_completion for the third. 

    It then checks the similarity between the current and previous bot responses. If the similarity is over 80%, it logs the information and continues to the next iteration. If the similarity is less than or equal to 80%, it logs the information and breaks the loop.

    If no bot response is generated, it increments the 'deleted' field of the test question response, saves it, and raises a ValueError. If a bot response is generated, it updates the metadata, response text, and evaluation status of the test question response, and saves it.

    Args:
        test_question_response (TestQuestionResponse): The test question response object that needs to be processed.
        is_whatsapp (bool, optional): A flag indicating whether the test is being conducted over WhatsApp. Defaults to False.

    Returns:
        TestQuestionResponse: The updated test question response object.

    Raises:
        ValueError: If no bot response is generated after three attempts.

    Example:
        >>> process_orchestrated_test_response_by_bot_llm(test_question_response_obj, is_whatsapp=True)
        <TestQuestionResponse: TestQuestionResponse object (1)>
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
    bot_llm_response_text = ""

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


    # previous_bot_question = TestQuestion.objects.filter(
    #     test_id=test.uid, deleted=0).order_by("-question_number").first()

    try:
        previous_bot_responses = TestQuestionResponse.objects.filter(
            ~Q(responder_type='user'),
            test_attempt_session_id=test_attempt_session.uid,
            deleted=0
        ).order_by("-id")
    except:
        previous_bot_responses = []

    logger.info(f"<<<<<<<<<<<<<<<<<<<<<<<<<<< previous bot response >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> : {previous_bot_responses} =>")

    for i in range(3):
        if is_whatsapp:
            # bot_llm_response_text = gpt3_completion(prompt=prompt,stop=['user',"CoachBot"],max_tokens=1000).text
            bot_llm_response_text = gemini_completion(prompt)
        else:
            # bot_llm_response_text = generic_completion(prompt, 300, 'question could not be generated')
            if test.is_free:
                bot_llm_response_text = generic_completion(prompt, 300, 'question could not be generated',is_free=test.is_free)
            else:
                if i == 0:
                    try:
                        bot_llm_response_text = gemini_completion(prompt)
                    except Exception as e:
                        logger.error(f"Error in gemini_completion completion: {e}. retrying ...")
                        bot_llm_response_text = anthropic_completion(prompt, 300)
                elif i == 1:
                    try:
                        bot_llm_response_text = anthropic_completion(prompt, 300)
                    except Exception as e:
                        logger.error(f"Error in anthropic completion: {e}. retrying ...")
                        bot_llm_response_text = gpt3_completion(prompt=prompt, stop=['user', "CoachBot"], max_tokens=1000).text
                else:
                    try:
                        bot_llm_response_text = gpt3_completion(prompt=prompt, stop=['user', "CoachBot"], max_tokens=1000).text
                    except Exception as e:
                        logger.error(f"Error in gpt3 completion: {e}. retrying ...")
                        bot_llm_response_text = gemini_completion(prompt)

                bot_llm_response_text = extract_question(bot_llm_response_text,question.question_for)
            
            
            
        initial_bot_questions = test.orchestrated_conversation_details.get('initial_messages')
        
        for initial_bot_question in initial_bot_questions:
            if calculate_similarity(initial_bot_question, bot_llm_response_text) > 80:
                logger.info(f"############### bot llm response is similar to initial bot response. so generating new response no:{i+1} ## Current: {bot_llm_response_text}, ## Initial: {initial_bot_question} ***************")
                continue
        
        current_and_previous_question_similarity = 0
        for previous_bot_response in previous_bot_responses:
            if previous_bot_response and previous_bot_response.response_text:
                current_and_previous_question_similarity = max(current_and_previous_question_similarity,calculate_similarity(previous_bot_response.response_text, bot_llm_response_text))
                if current_and_previous_question_similarity > 80:
                    break

        if current_and_previous_question_similarity > 80:
            logger.info(f"############### bot llm response is similar to previous bot response. so generating new response no:{i+1} ## Current: {bot_llm_response_text}, ## Previous: {previous_bot_response} ***************")
            continue
        else:
            logger.info("*************** bot llm response is unique so saving it ***************")
            break

    end = time.time()
    logger.info(f"####################### process_orchestrated_test_response_by_bot_llm: LOGIC for generating next question took {end - start:.2f} #######################")

    if not bot_llm_response_text:
        # delete this response
        test_question_response.deleted = test_question_response.deleted + 1
        test_question_response.save()
        raise ValueError("unable to get response from ai for %s",
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
    """
    This function calculates the metrics for a group discussion test attempt.

    It first retrieves the user persona and objective from the test details, and then gets the chat conversation.
    The function then evaluates the cultural skills rating and the skills rating for the group discussion.
    If the score for any skill is greater than 8.5, it is trimmed to 8.5. If it's less than 1.5, it is set to 1.5.
    The function then calculates the average skills rating and updates the skills rating if the scores are the same.
    It also calculates the test score and average score.
    If the test is not free, it also gets the meeting summary and areas of improvement.
    Finally, it updates the SkillsRating object for the participant with the new scores and saves it.

    Parameters:
    test_attempt_session (TestAttemptSession): The test attempt session object for which the metrics are to be calculated.
    test (Test): The test object which contains the details of the test.

    Returns:
    TestAttemptSession: The updated test attempt session object with the calculated metrics.

    Example:
    >>> test_attempt_session = TestAttemptSession.objects.get(uid='some-uid')
    >>> test = Test.objects.get(uid='some-uid')
    >>> updated_test_attempt_session = calc_group_discussion_report_metrics(test_attempt_session, test)
    """

    temp_rating = {}
    skills_count = {}

    user_persona = test.orchestrated_conversation_details.get(
        "test_user_persona")
    objective = test.description

    chat_conversation = get_group_discussion_chat_conversation(
        test_attempt_session, user_persona)
    
    updated_fields = ["test_score","avg_score","finished_at","updated"]
    
    if test.calculate_culture:
        culture_skills_rating = evaluate_group_discussion_conversation(
            test_attempt_session, chat_conversation, user_persona, objective, test.test_code,test,test.is_free)

        # Step 1: Sort the dictionary by its values in descending order
        sorted_dict = dict(sorted(culture_skills_rating.items(), key=lambda item: item[1], reverse=True))

        # Step 2: Extract the first 8 elements from the sorted dictionary  # because we want max 8 skill to evaluate
        culture_skills_rating = dict(list(sorted_dict.items())[:8])

        # if culture_skills_rating score is greater than 8.5 then trim the score to 8.5
        for skill in culture_skills_rating:
            if culture_skills_rating[skill] > 9.5:
                culture_skills_rating[skill] = 9.4
            elif culture_skills_rating[skill] < 0.5:
                culture_skills_rating[skill] = 0.6

        culture_skills_rating = update_culture_skills_if_same_scores(
            culture_skills_rating)

        culture_skills_rating = {key.capitalize() : value for key, value in culture_skills_rating.items()}

        test_attempt_session.culture_skills_rating = culture_skills_rating

        updated_fields.append('culture_skills_rating')

    skills_rating = evaluate_skills_group_discussion_conversation(
        test_attempt_session, chat_conversation, user_persona, objective, test.skills_to_evaluate,test,test.is_free)
    
    # Step 1: Sort the dictionary by its values in descending order
    sorted_dict = dict(sorted(skills_rating.items(), key=lambda item: item[1], reverse=True))

    # Step 2: Extract the first 8 elements from the sorted dictionary  # because we want max 8 skill to evaluate
    skills_rating = dict(list(sorted_dict.items())[:8])
    skills_rating = {key.capitalize() : value for key, value in skills_rating.items()}
    
    for skill in skills_rating:
        if skill in temp_rating:
            temp_rating[skill] += skills_rating[skill] or random.randint(3, 7)
            skills_count[skill] += 1
        else:
            temp_rating[skill] = skills_rating[skill] or random.randint(3, 7)
            skills_count[skill] = 1

    # If skills_rating score is greater than 8.5 then trim the score to 8.5
    for skill in skills_rating:
        if skills_rating[skill] > 9.5:
            skills_rating[skill] = 9.4
        elif skills_rating[skill] < 0.5:
            skills_rating[skill] = 0.6


    skills_rating_score = {}
    # calculate average skills rating
    for skill in skills_rating:
        skills_rating_score[skill] = temp_rating[skill] / skills_count[skill]

    skills_rating = update_skills_rating_if_same_scores(skills_rating_score)

    
    test_score = 0
    for skill in skills_rating:
        test_score += skills_rating[skill]

    avg_score = test_score / len(skills_rating.keys())
    
    
    

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
    """
    This function generates a comprehensive report from a test attempt session.

    The function takes a TestAttemptSession object as an input and processes the data related to the test attempt session. 
    It retrieves the participant's information, test details, chat conversation, and other relevant data. 
    It also calculates the average speech metrics if the test type is dynamic discussion or dynamic discussion thread. 
    The function then organizes all this information into a dictionary and returns it.

    Parameters:
    test_attempt_session (TestAttemptSession): An instance of the TestAttemptSession model. This object contains all the information related to a specific test attempt session.

    Returns:
    dict: A dictionary containing the following keys:
        - participant_name: The name of the participant.
        - date: The date when the test was started.
        - title: The title of the test.
        - objective: The objective of the test.
        - chat_conversation: A list of chat conversations.
        - meeting_summary: The summary of the meeting.
        - areas_of_improvement: Areas where the participant can improve.
        - culture_skills: The rating of the participant's culture skills.
        - feedback_summary: The summary of the feedback.
        - skill_summary: The summary of the skills.
        - start_with_user: A boolean indicating whether the conversation started with the user.
        - speech_metrics_avg: The average speech metrics.
        - response_relevance: A boolean indicating whether the response was relevant.
        - flashcards: A list of flashcards (only if the test type is dynamic discussion or dynamic discussion thread).
        - mindmap_data: A dictionary containing the test name and content for the mindmap (only if the test type is dynamic discussion or dynamic discussion thread).
        - skills_rating: The rating of the participant's skills.
        - certificate_details: The details of the certificate.
        - ui_information: The UI information of the test.

    Example:
    {
        'participant_name': 'John Doe',
        'date': '01 January 2022',
        'title': 'Test Title',
        'objective': 'Test Objective',
        'chat_conversation': [{'user_name': 'John Doe', 'message': 'Hello', 'is_bot': False}],
        'meeting_summary': 'Summary of the meeting',
        'areas_of_improvement': 'Area of improvement',
        'culture_skills': {'Communication': 4},
        'feedback_summary': 'Summary of the feedback',
        'skill_summary': 'Summary of the skills',
        'start_with_user': True,
        'speech_metrics_avg': {'Fluency Percentage': 95.0},
        'response_relevance': True,
        'flashcards': [{'text': 'Key learning point'}],
        'mindmap_data': {'test_name': 'Test Title', 'content': [{'question': 'Question', 'ideal_answer': 'Ideal answer', 'learnings': ['Learning 1', 'Learning 2']}]},
        'skills_rating': {'Communication': 4},
        'certificate_details': 'Certificate details',
        'ui_information': 'UI information'
    }
    """    
    test_attempt_session_id = test_attempt_session.uid

    participant_id = test_attempt_session.participant_id
    participant_name = get_user_display_name(get_user_by_id(participant_id))

    date = test_attempt_session.started_at.strftime("%d %B %Y")

    test = Test.objects.get(uid=test_attempt_session.test_id, deleted=0)
    title = test.title
    test_report_config = TestReportConfig.objects.filter(deleted=False, test=test).first()
    test_report_config= TestReportConfigSerializer(test_report_config).data if test_report_config else None

    
    logger.info(f"############### get_meeting_report_from_test_attempt_session:   participant_id: {participant_id}, test_attempt_session_id: {test_attempt_session_id}, test_id: {test.uid} , test_title: {test.title}, participant_name: {participant_name} ###############")

    objective = test.description

    user_persona = test.orchestrated_conversation_details.get(
        "test_user_persona")

    chat_conversation = test.orchestrated_conversation_details.get(
        "initial_messages")

    chat_conversation += get_group_discussion_chat_conversation(
        test_attempt_session, user_persona, is_report=True)
    
    logger.info(f"############### get_meeting_report_from_test_attempt_session:   chat_conversation: {chat_conversation}, objectives: {objective} , user_persona: {user_persona} ###############")

    chat_conversation_with_details = []
    flashcards = []
    start_with_user_message = test.orchestrated_conversation_details.get('start_with_user')
    speech_metrics_avg = {}
    response_relevance = True
    culture_map_evaluation_criteria = get_culture_skills(
                    "ocean_model" if test.scenario_case == ScenarioCaseChoices.psychometric else "workplace_skills", 
                    only_criteria=True 
                    )
    # try:
    #     client = get_client_info_from_user_detail(tenant_id=test_attempt_session.tenant_id,
    #                                                 user_uid=test_attempt_session.participant_id
    #                                                 )
    #     client_name = client.client_name if client else None
    #     client_id = client.id if client else None
    # except:
    #     client_name = None
    #     client_id = None

    try:
        client = get_client_info_from_user_detail(tenant_id=test_attempt_session.tenant_id,
                                                    user_uid=test_attempt_session.participant_id
                                                    )
        client_name = client.client_name if client else None
        client_id = client.id if client else None
        client_info = clientUserInfoSerializer(client).data

    except:
        client_name = None
        client_id = None
        client_info = None

    psychometric_data = None
    psychometric_info = None
    other_psychometric_infos = {}

    if test_attempt_session.pshycometric_data:
        psychometric_data = test_attempt_session.pshycometric_data
        psychometric_info = format_psychometric_items(test.psychometric)
        other_psychometric_infos['max_ranges'] = find_highest_count_range(psychometric_data)


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
            test_data.append({'response':test_response.response_text,'responder_type':test_response.responder_type,'feedback':test_response.feedback_text or "Feedback couldn't be generated.",})
        logger.info({"************test_responses":test_data})
        for test_response in test_responses:
            if test_response.responder_type == QuestionForChoices.user:
                if count == 1:
                    if start_with_user_message is not None:
                        data[f"question"] = test.description
                    else:
                        data[f"question"] = chat_conversation[0].split(":", 1)[1].strip('" \'')
                data["response"] = test_response.response_text.strip('" \'')
                data["feedback"] = re.sub(r'\([^)]*\)', '',  test_response.feedback_text or "Feedback couldn't be generated.")
                
                logger.info(f"############### get_meeting_report_from_test_attempt_session:  kls_klp_in_response: {test_response.kls_klp} ###############")
                
                key_learning_point = test_response.kls_klp.get('klp') if test_response.kls_klp else 'No key learning point found.'
                flashcards.append({'text':key_learning_point})
                chat_conversation_with_details.append(data)
                count += 1
                mindmap_contents.append(
                    {
                        "question":data["question"],
                        "ideal_answer": key_learning_point,
                        "learnings": test_response.kls_klp.get('kls').strip().split(',') if test_response.kls_klp else [],
                    }
                )
                data = {}
                
            else:
                data[f"question"] = test_response.response_text.split(':')[-1].strip('" \'')

            
            if test_response.speech_metrics:
                speech_metrics = test_response.speech_metrics
                logger.info(f"############### get_meeting_report_from_test_attempt_session:  speech_metrics: {speech_metrics} ###############")

                # We only need ['pace', 'filler_word_percentage', 'power_word_percentage', 'silence_number','fluency_percentage'] from speech_metrics
                speech_metrics = {k: v for k, v in speech_metrics.items(
                ) if k in ['fluency_percentage', 'pace','power_word_percentage','filler_word_percentage', 'silence_number']}

                # Convert the Keys to human readable format
                speech_metrics = {k.replace("_", " ").title(
                ): v for k, v in speech_metrics.items()}

                # Add the speech_metrics to the list of all_speech_metrics
                all_speech_metrics.append(speech_metrics)

        # Get the averaged speech metrics for the test attempt session
        logger.info(f"############### get_meeting_report_from_test_attempt_session:  all_speech_metrics: {all_speech_metrics} ###############")
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
    culture_skills = {key.strip('"\'' ): value for key, value in culture_skills.items()} if culture_skills else None # to strip extra qoutes from key

    data = {
        "participant_name": participant_name,
        "date": date,
        "title": title,
        "objective": test.description,
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
        "response_relevance" : response_relevance,
        "client_info": client_info,
        "client_name":client_name,
        "client_id": client_id,
        'pshycometric_data': psychometric_data,
        'psychometric_info': psychometric_info,
        "other_psychometric_infos": other_psychometric_infos,
        'report_description': test.report_description,
        "category": test.category,
        "interaction_code": test.test_code,
        "personality_model_data": test_attempt_session.personality_model_data,
        "culture_map_evaluation_criteria": culture_map_evaluation_criteria,
        "skill_domain": test.skill_domain,
        "creator_prompt_type": test.creator_prompt_type,
        'feedback_video_script': test_attempt_session.feedback_video_script if test_attempt_session.feedback_video_script else test.feedback_video_script_template,
        'video_script': test.video_script,

        'feedback_video_link': test_attempt_session.feedback_video_link if test_attempt_session.feedback_video_link else test.feedback_script_video_link

    }
    
    logger.info(f"############### get_meeting_report_from_test_attempt_session:  data: {data} ###############")

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
        
    logger.info(f"############### get_meeting_report_from_test_attempt_session:  data: {data} ###############")
        
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
    data['test_report_config']=test_report_config
    

    return data


@timeit
def get_group_discussion_summary(objective: str, chat_conversation: str):
    """
    This function generates a summary of a group discussion based on the provided objective and conversation.

    The function constructs a prompt using the objective and conversation, and then uses the `generic_completion` function to generate a summary. If the `generic_completion` function fails to generate a summary, it retries once before defaulting to "Could not generate".

    The function is decorated with the `timeit` decorator, which logs the time taken to execute the function.

    Args:
        objective (str): The objective of the group discussion. This should be a string describing the purpose or goal of the discussion.
        chat_conversation (str): The conversation of the group discussion. This should be a string containing the entire conversation text.

    Returns:
        str: A string containing the summary of the group discussion. If the summary cannot be generated, the function returns "Could not generate".

    Example:
        >>> objective = "Discuss the new product launch"
        >>> chat_conversation = "Alice: I think we should launch next month. Bob: I agree, but we need to sort out the marketing first."
        >>> get_group_discussion_summary(objective, chat_conversation)
        'The group discussed the new product launch and agreed to schedule it for next month after sorting out the marketing.'
    """
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
    """
    This function generates areas of improvement for a given user persona based on a chat conversation and an objective.

    The function constructs a prompt using the objective, chat conversation, and user persona. This prompt is then passed to the `anthropic_completion` function, which generates a response using the Anthropic API. The response is expected to be an analysis of the efficiency and efficacy of the meeting in relation to the predefined areas of improvement. 

    If the `anthropic_completion` function fails to generate a response, a default response indicating that generation was not possible is returned.

    Args:
        objective (str): The objective of the discussion.
        chat_conversation (str): The conversation that took place during the meeting.
        user_persona (str): The persona for which the areas of improvement are to be evaluated.

    Returns:
        dict: A dictionary where the keys are the areas of improvement and the values are the generated responses. If the response generation fails, the values will be "Could not generate".

    Example:
        >>> get_areas_of_improvement("Increase sales", "We discussed various strategies...", "Sales Manager")
        {
            "Sticking to Agenda": "The Sales Manager was able to...",
            "Driving to decision": "The Sales Manager could improve...",
            "Sticking to Positive behavior": "The Sales Manager demonstrated..."
        }
    """
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

    while cnt < 1:  # Because gemini_completion already has a retry mechanism
        try:
            res = gemini_completion(prompt)
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
    """
    This function retrieves the conversation of a group discussion from a test attempt session.

    The function iterates over the responses in the test attempt session, and for each response, it checks the responder type.
    If the responder is a user, it appends the user's persona and response text to the conversation.
    If the responder is not a user, it appends the responder's display name and response text to the conversation.
    The function then checks if the conversation is for a report. If it is, it returns the conversation as a list of strings.
    If it's not for a report, it returns the conversation as a single string.

    Parameters:
    test_attempt_session (TestAttemptSession): The test attempt session object from which to retrieve the conversation.
    test_user_persona (str): The persona of the user in the test attempt session.
    is_report (bool): A flag indicating whether the conversation is for a report. Default is False.

    Returns:
    If is_report is True, it returns a list of strings where each string is a line of the conversation.
    If is_report is False, it returns a single string that contains the entire conversation.

    Example:
    >>> get_group_discussion_chat_conversation(test_attempt_session, "User1", True)
    ['User1: Hello', 'Bot: Hi', 'User1: How are you?', 'Bot: I am fine.']

    >>> get_group_discussion_chat_conversation(test_attempt_session, "User1", False)
    'User1: Hello\nBot: Hi\nUser1: How are you?\nBot: I am fine.'
    """
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
    This function _calc_score calculates the score for a given test attempt session and updates the skills_rating field in the TestAttemptSession object. It also uses these skills ratings to update the skills table.

    Parameters: test_attempt_session (TestAttemptSession): An instance of the TestAttemptSession model. This represents a single attempt of a test by a participant. test (Test): An instance of the Test model. This represents the test that the participant is attempting.

    Process: The function first retrieves all the responses for the participant in the test attempt session. It then calculates various scores and ratings based on these responses, such as the average score, speech score, and skills rating. If the test is not free, it also calculates the speech metrics and feedback text. The function then calculates the skills rating for each response and updates the skills_rating field in the TestAttemptSession object. If the test has a speech metric, it also updates the speech_score field. The function finally updates the SkillsRating table with the calculated skills ratings.

    Input Requirements: The test_attempt_session parameter must be an instance of the TestAttemptSession model, and the test parameter must be an instance of the Test model.

    Output: The function does not return any value. However, it updates the skills_rating, test_score, avg_score, finished_at, and speech_score fields in the TestAttemptSession object. It also updates the SkillsRating table with the calculated skills ratings.

    Example: Let's assume we have a TestAttemptSession instance tas and a Test instance t. We can call the function as follows: _calc_score(tas, t) This will update the tas object and the SkillsRating table based on the responses in the tas object for the test t. 

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
        competency_data = UserAttribute.objects.get(user_id=test_attempt_session.participant_id).competency_data
        compentecy_skills = []
        client = ClientUserInfo.objects.filter(deleted=False,tenant_id=test_attempt_session.tenant_id, member_emails__contains=UserAttribute.objects.get(user_id=test_attempt_session.participant_id).attributes.get('email')).last()
        if client:
            compentecy_skills = list(CompetencySkillAndClientMapping.objects.filter(deleted=False,tenant_id=test_attempt_session.tenant_id,client_id=client.uid).values_list('competency_skill',flat=True))

        if len(compentecy_skills) == 0:
            compentecy_skills = ["Communication Skills","Teamwork","Planning and Organizing","Client Focus"]
            if competency_data:
                compentecy_skills = list(competency_data.values())


        evaluate_competency_data_thread(questions,responses,test,test_attempt_session,compentecy_skills)
        
    evaluate_personality_model_data(test_attempt_session=test_attempt_session, test=test)
    
    # skills_=[]
    # for question in questions:
    #     required_skills = question.key_learning_skills.split(",")
    #     required_skills = [skill.strip() for skill in required_skills if skill]
    #     required_skills = [skill.lower() for skill in required_skills if skill]
    #     for s in required_skills:
    #         skills_.append(s)

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

    response_skills_rating = calc_skills_rating(test_attempt_session=test_attempt_session,
                                                responses=responses, 
                                                test=test,
                                                user_skill_prompt=user_skill_prompt)
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

    if test.calculate_culture:
        culture_skills_rating = calc_culture_skills_rating(test_attempt_session, responses, test)

        logger.info({"***************************culture_skills_rating_score":culture_skills_rating})

        culture_skills_rating = update_culture_skills_if_same_scores(
            culture_skills_rating)
        
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
    """
    This function is designed to increment the average score of a participant's skills rating based on their past successful sessions.

    The function first retrieves the total number of successful sessions for the participant excluding the current one. If the total successful sessions are only one, it returns the current skills rating and average score without any modification.

    If there are more than one successful sessions, it calculates the average score of the last 5 sessions. If the average score is less than 5, it returns the current skills rating and average score without any modification.

    If the average score is 5 or more, it increments the skills rating by a certain percentage (up to 10%) based on the total number of successful sessions. The incremented skills rating is then used to calculate the new average score.

    Parameters:
    skills_rating (dict): A dictionary where keys are skill names and values are the corresponding ratings. Each rating should be a float.
    avg_score (float): The current average score of the participant.
    participant_id (str): The ID of the participant.
    test_attempt_session (TestAttemptSession): The current test attempt session object.

    Returns:
    tuple: A tuple containing the updated skills rating dictionary and the new average score.

    Example:
    Given a skills_rating = {'skill1': 7.5, 'skill2': 8.0}, avg_score = 7.75, participant_id = '123', and a valid test_attempt_session,
    the function might return ({'skill1': 8.25, 'skill2': 8.8}, 8.525) assuming there were 10 successful past sessions and the average score of the last 5 sessions was 5 or more.
    """
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
    """
    This method generate session report link save it in testattemptsession.report_url
    """

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
    elif test.scenario_case == ScenarioCaseChoices.psychometric:
        report_type = ReportType.PERSONALITY_PSYCHOMATRIC_REPORT

    report_url = f"{FRONTEND_BASE_URL}/{report_type}/{refresh_token}/?session_id={test_attempt_session_id}&interaction_id={test_id}&backend={BACKEND}"

    test_attempt_session.report_url = report_url
    test_attempt_session.save(update_fields=["report_url"])

    return report_url


@timeit
def generate_summary_feedback_session_report_link(test_attempt_session: TestAttemptSession, test: Test):
    """
    This method generate summary_feedback_session_report_link save it in testattemptsession.report_url
    """
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
    """
    This method generate meeting_report_link save it in testattemptsession.report_url
    """
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
    """
    This method generate dynamic_discussion_report_link save it in testattemptsession.report_url
    """
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
    """
    This function modifies the skill ratings to ensure uniqueness and a multiple of 0.25. 
    It is designed to handle situations where multiple skills have the same rating, which can cause issues in further analysis.

    The function works by iterating over the skills dictionary, which is sorted by the rating value. 
    For each skill, it checks if the rating is already present in the `value_counts` dictionary (which keeps track of the frequency of each rating). 
    If the rating is not unique (i.e., it appears more than once), the function will increment or decrement the rating by 0.25 until it becomes unique. 
    The increment or decrement is chosen randomly. 
    The function also ensures that the final rating is between 0 and 9 (inclusive).

    If the function takes more than 2 seconds to find a unique rating, it will log a message and break out of the loop.

    Parameters:
    skills (dict): A dictionary where the keys are skill names (str) and the values are their corresponding ratings (float). 
                   The ratings should be between 0 and 10 (inclusive).

    Returns:
    modified_skills (dict): A dictionary with the same keys as the input, but the values may be modified to ensure uniqueness. 
                            The values will be rounded to 2 decimal places.

    Example:
    Input: {'skill1': 5.0, 'skill2': 5.0, 'skill3': 6.0}
    Output: {'skill1': 5.0, 'skill2': 5.25, 'skill3': 6.0}
    """
    logger.info(f"skills before: {skills}")
    modified_skills = {}
    value_counts = {}
    start = time.time()

    if len(skills) == len(set(skills.values())):
        return skills


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
    """
    Sends a report link via email to a participant and a list of other recipients.

    This function first checks if the report has already been sent to the participant's email. If it has, the function returns immediately.
    It retrieves the participant's attributes, including their name and email, and the list of additional email recipients from the test object.
    It then prepares the data for the email, including the report URL, test name, and participant's name.
    The email subject is formatted to include the test name, participant's name, and the date the test was completed.
    If the test object indicates that the participant should receive the email, the function attempts to send the email to the participant.
    It then sends the email to each of the additional recipients.
    Finally, it logs a success message and updates the 'is_report_sent_to_email' field of the test attempt session object to True.

    Parameters:
    test (Test): The test object, which contains information about the test and the list of additional email recipients.
    test_attempt_session (TestAttemptSession): The test attempt session object, which contains information about the participant and the test attempt.
    report_url (str): The URL of the report to be sent.
    is_whatsapp (bool, optional): A flag indicating whether the participant is using WhatsApp. Defaults to False.

    Returns:
    None

    Raises:
    Exception: If there is an error sending the email to the participant, an exception is raised and logged.

    Example:
    send_report_link_to_email(test_object, test_attempt_session_object, 'http://example.com/report')
    """
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
        participant_name = get_user_display_name(get_user_by_id(test_attempt_session.participant_id))

    

    data = {
        "report_url": report_url,
        "test_name": test_name,
        "candidate_name": participant_name,
        "real_name": participant_attributes.get("real_name"),
    }

    if not participant_attributes.get("real_name"):
        data["real_name"] = participant_name
        data["candidate_name"] = participant_attributes.get("email")

    email_subject = f"{data['real_name']}, your simulation feedback report on **{test_name}**  is completed on {test_completion_date} 🚀🚀"

    participant_email = participant_attributes.get(
        "profile", {}).get("email") or participant_attributes.get('email',None)

    data['user_email'] = participant_email
    # fatchin client information if any and adding its email address list to test's emailaddress list.
    report_on = test.email_candidate
    client = get_client_info_from_user_detail(tenant_id=test_attempt_session.tenant_id,email=participant_email)
    if client:
        logger.info(f" << Client Name: {client.client_name}>>")
        report_on = client.report_on if (client.report_on is not None and test.scenario_case not in ['assessment']) else report_on
        if client.email_address_list:
            email_address_list.extend([email.strip() 
                                    for email in client.email_address_list.split(',') if len(email.strip())>0])
            email_address_list = list(set(email_address_list))  # removing duplicates
            logger.info(f" << Client Name: {client.client_name}>> <<emails : {email_address_list}>>")


    for to_email in email_address_list:
        try:
            send_email(to_email, email_subject, data=data)
        except Exception as e:
            logger.exception(e)
            send_error_notification("send_report_link_to_email",f"failed to send email to {to_email}, err: {e}",data)

    logger.info("report emails sent successfully test_attempt_session: %s", test_attempt_session.uid)

    if participant_email and report_on:
        try:
            send_email(participant_email, email_subject, data=data)
        except Exception as e:
            logger.exception("failed to send email to participant %s email %s, err: %s",
                             participant_id, participant_email, e)
            send_error_notification("send_report_link_to_email",f"failed to send email to participant {participant_id} email {participant_email}, err: {e}",e)
            raise e


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
        participant_name = get_user_display_name(get_user_by_id(test_attempt_session.participant_id))


    

    data = {
        "report_url": report_url,
        "test_name": test_name,
        "candidate_name": participant_name,
        "real_name": participant_attributes.get("real_name"),
    }
    if not participant_attributes.get("real_name"):
        data["real_name"] = participant_name
        data["candidate_name"] = participant_attributes.get("email")

    email_subject = f"{data['real_name']}, your simulation feedback report on **{test_name}**  is completed on {test_completion_date} 🚀🚀"

    participant_email = participant_attributes.get(
        "profile", {}).get("email") or participant_attributes.get('email')
    data['user_email'] = participant_email

    # fatchin client information if any and adding its email address list to test's emailaddress list.
    report_on = test.email_candidate
    client = get_client_info_from_user_detail(tenant_id=test_attempt_session.tenant_id,email=participant_email)
    if client:
        logger.info(f" << Client Name: {client.client_name}>>")
        report_on = client.report_on if (client.report_on is not None and test.scenario_case not in ['assessment']) else report_on

        if client.email_address_list:
            email_address_list.extend([email.strip() 
                                    for email in client.email_address_list.split(',') if len(email.strip())>0])
            email_address_list = list(set(email_address_list))  # removing duplicates
            logger.info(f" << Client Name: {client.client_name}>> <<emails : {email_address_list}>>")


    for to_email in email_address_list:
        try:
            send_email(to_email, email_subject, data=data)
        except Exception as e:
            logger.exception(e)
            send_error_notification("send_report_link_to_email",f"failed to send email to {to_email}, err: {e}",data)

    logger.info("report emails sent successfully test_attempt_session: %s", test_attempt_session.uid)


    if participant_email and report_on:
        try:
            send_email(participant_email, email_subject, data=data)
        except Exception as e:
            logger.exception("failed to send email to participant %s email %s, err: %s",
                             participant_id, participant_email, e)
            send_error_notification("send_report_link_to_email_orch",f"failed to send email to participant {participant_id} email {participant_email}, err: {e}",data)
            raise e

    test_attempt_session.is_report_sent_to_email = True
    test_attempt_session.save(update_fields=["is_report_sent_to_email"])


@timeit
def send_report_link_to_whatsapp(test: Test, test_attempt_session: TestAttemptSession, report_url: str):
    """
    This method send report link to whatsapp
    """
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
    """ 
    This function calc_culture_skills_rating is used to calculate the cultural skills rating for a given test attempt session.

    It takes three parameters:

    test_attempt_session: This is an instance of a TestAttemptSession model. It represents a specific attempt of a test by a user.
    responses: This is a list of response objects. Each response object should have a question_id attribute which corresponds to the ID of a question in the TestQuestion model, and a response_text attribute which is the text of the user's response to that question.
    test: This is an instance of the Test model. It represents the test that the user is attempting.
    The function first constructs a conversation string by iterating over the responses. For each response, it fetches the corresponding question from the TestQuestion model and appends the question and response text to the conversation string.

    Then, it calls the evaluate_conversation function to evaluate the conversation. If the test is free, it passes True for the is_free parameter of evaluate_conversation, otherwise it passes False.

    The evaluate_conversation function returns a dictionary where the keys are the names of the cultural skills and the values are the ratings for those skills. If the evaluation fails, evaluate_conversation returns None and calc_culture_skills_rating also returns None.

    Finally, the function trims any skill ratings that are outside the range 1.5 to 8.5 and returns the dictionary of cultural skills ratings.

    Example:

    test_attempt_session = TestAttemptSession.objects.get(uid='some-uid')
    responses = [
        {'question_id': 'q1', 'response_text': 'This is my response to question 1'},
        {'question_id': 'q2', 'response_text': 'This is my response to question 2'},
    ]
    test = Test.objects.get(test_code='some-test-code')

    culture_skills_rating = calc_culture_skills_rating(test_attempt_session, responses, test)
    # Returns: {'hierarchy': 8.5, 'consensual': 7.0, 'indirect negative feedback': 6.5, 'relationship-based': 5.0, 'high context communication': 4.5, 'Persuasion': 4.0, 'argumentative': 3.5}
    """
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
        test_attempt_session=test_attempt_session,
        conversation=conversation,
        test=test,
        is_free=test.is_free
    )

    if not is_evaluated:
        return None

    # if score is greater than 8.5 then trim it to 8.5
    for skill in culture_skills_rating:
        if culture_skills_rating[skill] > 9.5:
            culture_skills_rating[skill] = 9.4
        elif culture_skills_rating[skill] < 0.5:
            culture_skills_rating[skill] = 0.6

    return culture_skills_rating


@timeit
def calc_skills_rating(test_attempt_session, responses, test,user_skill_prompt):
    """
    This function calculates the skills rating for a test attempt session based on the responses provided by the user.

    The function first constructs a conversation string by iterating over the responses. Each response is associated with a question from the test, and the conversation string is formed by concatenating the question and response texts. 

    The conversation string, along with other test details and skills, is then passed to the `evaluate_response_skill` function, which evaluates the conversation based on the specified skills. If the test is free, the `evaluate_response_skill` function is called with an additional flag set to True.

    Parameters:
    test_attempt_session (object): The test attempt session object.
    responses (list): A list of response objects. Each response object should have a `question_id` and `response_text` attribute.
    test (object): The test object. It should have `title`, `description`, `test_code`, and `is_free` attributes.
    skills (list): A list of skills to be evaluated.
    user_skill_prompt (str): The user skill prompt.

    Returns:
    dict: A dictionary where each key is a skill and the corresponding value is the rating for that skill. If the evaluation is not successful, the function returns None.

    Raises:
    Exception: If the evaluation is not successful.

    Example:
    >>> calc_skills_rating(test_attempt_session, responses, test, ["skill1", "skill2"], "User Skill Prompt")
    {'skill1': 4.5, 'skill2': 9.0}
    """
    skills_rating = {}

    conversation = ""
    count = 1
    skills_to_evaluate = {}
    for response in responses:

        question = TestQuestion.objects.get(
            uid=response.question_id)

        question_text = question.question
        response_text = response.response_text
        skills_to_evaluate[question.uid] = question.key_learning_skills

        conversation += f"{count}. [Question:] {question_text}\n"
        if not question.is_view_only:
            conversation += f"[Answer:] {response_text}\n\n"

        count += 1

    unique_skills_to_evaluate = limit_unique_skills_per_test(skills_to_evaluate)
    all_skills = [
        skill.strip()
        for skills in unique_skills_to_evaluate.values()
        for skill in skills.split(',')
    ]
    # Evaluate conversation
    if test.is_free:
        skills_rating, is_evaluated = evaluate_response_skill(
            test_attempt_session, conversation, test.title, test.description, test.test_code,all_skills,user_skill_prompt,True)
    else:
        skills_rating, is_evaluated = evaluate_response_skill(
            test_attempt_session, conversation, test.title, test.description, test.test_code,all_skills,user_skill_prompt)

    if not is_evaluated:
        return None
    
    for skill in skills_rating:
        if skills_rating[skill] > 9.5:
            skills_rating[skill] = 9.1
        elif skills_rating[skill] < 0.5:
            skills_rating[skill] = 0.6

    return skills_rating

@timeit
def get_feedback_output_format_prompt(prompt_type,test_type):
    if prompt_type == 'code':
        if test_type == 'interview':
            return """
            RUN THE BELOW CODE AS IT IS WHILE GENERATING RESPONSE:
            # Define word limits for each section
            word_limits = {
                "Key insights to improve the response": 10,
                "What went well?": 10,
                "What did not work?": 10,
                "A sample candidate answer": 20,
                "Pro Interview Insights": 10
            }

            # Function to truncate text to word limit
            def truncate_text(text, word_limit):
                if not isinstance(text, str):
                    raise ValueError("Input text must be a string")
                words = text.split()
                if len(words) > word_limit:
                    return ' '.join(words[:word_limit])
                return text

            # Function to generate feedback
            def generate_feedback(key_insights, what_went_well, what_did_not_work, sample_candidate_answer, pro_interview_insights):
                if not all(isinstance(x, str) for x in [key_insights, what_went_well, what_did_not_work, sample_candidate_answer, pro_interview_insights]):
                    raise ValueError("All input values must be strings")

                feedback = {
                    "Key insights to improve the response": truncate_text(key_insights, word_limits["Key insights to improve the response"]),
                    "What went well?": truncate_text(what_went_well, word_limits["What went well?"]),
                    "What did not work?": truncate_text(what_did_not_work, word_limits["What did not work?"]),
                    "A sample candidate answer": truncate_text(sample_candidate_answer, word_limits["A sample candidate answer"]),
                    "Pro interview insights": truncate_text(pro_interview_insights, word_limits["Pro Interview Insights"])
                }

                # Ensure total word count never exceeds 60 words
                total_words = sum(len(section.split()) for section in feedback.values())
                if total_words > 60:
                    for key, value in feedback.items():
                        words = value.split()
                        excess_words = total_words - 60
                        if excess_words > 0:
                            feedback[key] = ' '.join(words[:-excess_words])
                            total_words = sum(len(section.split()) for section in feedback.values())
                            if total_words <= 60:
                                break

                return feedback

            # Generate the feedback
            try:
                key_insights = "This is a sample key insight to improve the response"
                what_went_well = "This is a sample of what went well"
                what_did_not_work = "This is a sample of what did not work"
                sample_candidate_answer = "This is a sample candidate answer"
                pro_interview_insights = "This is a sample pro interveiw insights"

                feedback = generate_feedback(key_insights, what_went_well, what_did_not_work, sample_candidate_answer, pro_interview_insights)

                # Print the feedback
                final_response = ""
                for key, value in feedback.items():
                    final_response += f"\n{key}: {value}"
                print(final_response)
            except ValueError as e:
                print(f"Error: {e}")
            except Exception as e:
                print(f"An unexpected error occurred: {e}")


            NOTE: The total number of words should be at the maximum 60 words. Provide the feedback exactly in the format and sections above. 
            """

        else:
            return """
            RUN THE BELOW CODE AS IT IS WHILE GENERATING RESPONSE:
            # Define word limits for each section
            word_limits = {
                "Key insights to improve the response": 10,
                "What went well?": 10,
                "What did not work?": 10,
                "A sample candidate answer": 20,
                "A counter intuitive insight": 10
            }

            # Function to truncate text to word limit
            def truncate_text(text, word_limit):
                if not isinstance(text, str):
                    raise ValueError("Input text must be a string")
                words = text.split()
                if len(words) > word_limit:
                    return ' '.join(words[:word_limit])
                return text

            # Function to generate feedback
            def generate_feedback(key_insights, what_went_well, what_did_not_work, sample_candidate_answer, counter_intuitive_insight):
                if not all(isinstance(x, str) for x in [key_insights, what_went_well, what_did_not_work, sample_candidate_answer, counter_intuitive_insight]):
                    raise ValueError("All input values must be strings")

                feedback = {
                    "Key insights to improve the response": truncate_text(key_insights, word_limits["Key insights to improve the response"]),
                    "What went well?": truncate_text(what_went_well, word_limits["What went well?"]),
                    "What did not work?": truncate_text(what_did_not_work, word_limits["What did not work?"]),
                    "A sample candidate answer": truncate_text(sample_candidate_answer, word_limits["A sample candidate answer"]),
                    "A counter intuitive insight": truncate_text(counter_intuitive_insight, word_limits["A counter intuitive insight"])
                }

                # Ensure total word count never exceeds 60 words
                total_words = sum(len(section.split()) for section in feedback.values())
                if total_words > 60:
                    for key, value in feedback.items():
                        words = value.split()
                        excess_words = total_words - 60
                        if excess_words > 0:
                            feedback[key] = ' '.join(words[:-excess_words])
                            total_words = sum(len(section.split()) for section in feedback.values())
                            if total_words <= 60:
                                break

                return feedback

            # Generate the feedback
            try:
                key_insights = "This is a sample key insight to improve the response"
                what_went_well = "This is a sample of what went well"
                what_did_not_work = "This is a sample of what did not work"
                sample_candidate_answer = "This is a sample candidate answer"
                counter_intuitive_insight = "This is a sample counter intuitive insight"

                feedback = generate_feedback(key_insights, what_went_well, what_did_not_work, sample_candidate_answer, counter_intuitive_insight)

                # Print the feedback
                final_response = ""
                for key, value in feedback.items():
                    final_response += f"\n{key}: {value}"
                print(final_response)
            except ValueError as e:
                print(f"Error: {e}")
            except Exception as e:
                print(f"An unexpected error occurred: {e}")


            NOTE: The total number of words should be at the maximum 60 words. Provide the feedback exactly in the format and sections above. 
            """

    else: 
        if test_type == "interview":
            return"""
            The feedback should be structured in the following format:

            Key Insights: "Output text"
            What went well: Output text"
            What did not work: Output text"
            Sample Candidate Answer : "Output text"
            Pro Interview Insights :  "Output text"            
            """
        else:
            return """
                The feedback should be structured in the following format:
                    Key Insights: "Output text"
                    What went well: Output text"
                    What did not work: Output text"
                    Sample Candidate Answer : "Output text"
                    Counter Intuitive Insight :  "Output text"
                """



@timeit
def get_interview_feedback(title,description,background, question_text,candidate_comment):
    """
    to get interview feedback prompt
    """
    format_prompt = get_feedback_output_format_prompt(prompt_type='text',test_type='interview')
    prompt = Template("""
            \n\nHuman:

            Title: ${title}.

            Test Description: ${description}

            background: ${background}

            Question : ${question_text}

            Candidate Comment : ${candidate_comment}

            Please provide interview feedback for a candidate who has provided a "Candidate Comment" for an interview as specified in the "Test Description". Provide the feedback based on the information provided in "background”. Please provide feedback which specifically helps the candidate in an interview. 

            ${format_prompt}

            \n\nAssistant
                """).substitute(
                    title=title,
                    description=description,
                    question_text=question_text,
                    candidate_comment= candidate_comment,
                    background=background,
                    format_prompt=format_prompt
                )
    return prompt

@timeit
def get_chat_conversation_prompt_v3(test_title: str,
                                    test_description: str,
                                    question: str,
                                    question_context: str,
                                    candidate_reply: str,
                                    user_feedback_prompt:str,
                                    articles:str = None,
                                    scenario_summary:str = None):
    """
    this method used to get prompt for feedback.
    """
    article_information = ''
    if articles:
        for url in articles.split(','):
            articles_data = scrape_article_data(url.strip())
            if articles_data:
                articles_data = articles_data['article_content']
                article_information += f"\n articles_data"

    if scenario_summary:
        article_information += scenario_summary
    
    if len(article_information) == 0:
        articles = None
            

    format_prompt = get_feedback_output_format_prompt(prompt_type='text',test_type='normal')

    if question_context:
        if articles:
            template = Template(
                """
                \n\nHuman:
                Title: ${test_title}. 
                Test Description: ${test_description}
                Customer question:  ${question} 
                Expert Suggestions:  ${question_context}
                Article: ${article_info} 
                Candidate answer:  ${candidate_reply}
        
                Please provide communication and subject matter feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on "Expert suggestions",  "Title" , only if they are relevant to the situation. The feedback should include whether right questions are asked for engagement. When provided, please base the feedback on the information provided in "Article". Use the information in the "Article" to further provide the feedback. Please provide feedback which specifically help enhance people skills of the responder.
                ${format_prompt}
                ${user_feedback_prompt}
                \n\nAssistant:
                """
            )
            return template.substitute(test_title=test_title,
                                    test_description=test_description,
                                    question=question,
                                    question_context=question_context,
                                    candidate_reply=candidate_reply,
                                    user_feedback_prompt=user_feedback_prompt,
                                    article_info=article_information,
                                    format_prompt=format_prompt)

        else:
            template = Template(
                """
                \n\nHuman:
                Title: ${test_title}. 
                Test Description: ${test_description}
                Customer question:  ${question} 
                Expert Suggestions:  ${question_context} 
                Candidate answer:  ${candidate_reply}
        
                Please provide communication and subject matter feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on "Expert suggestions",  "Title" , only if they are relevant to the situation. The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the responder. 
                ${format_prompt}
                ${user_feedback_prompt}
                \n\nAssistant:
                """
            )
            return template.substitute(test_title=test_title,
                                    test_description=test_description,
                                    question=question,
                                    question_context=question_context,
                                    candidate_reply=candidate_reply,
                                    user_feedback_prompt=user_feedback_prompt,
                                    format_prompt=format_prompt)
    else:
        if articles:
            template = Template(
                """
                \n\nHuman:
                Title: ${test_title}. 
                Test Description: ${test_description}
                Customer question:  ${question} 
                Candidate answer:  ${candidate_reply}
                Article: ${article_info} 
                
                Please provide communication and subject matter feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on "Title" , only if they are relevant to the situation. The feedback should include whether right questions are asked for engagement. When provided, please base the feedback on the information provided in "Article". Use the information in the "Article" to further provide the feedback. Please provide feedback which specifically help enhance people skills of the responder.
                ${format_prompt}
                
                 
                ${user_feedback_prompt}
                \n\nAssistant:
                """
            )
            # log template for debugging
            return template.substitute(test_title=test_title,
                                    test_description=test_description,
                                    question=question,
                                    candidate_reply=candidate_reply,
                                    user_feedback_prompt=user_feedback_prompt,
                                    article_info=article_information,
                                    format_prompt=format_prompt)


        else:
            template = Template(
                """
                \n\nHuman:
                Title: ${test_title}. 
                Test Description: ${test_description}
                Customer question:  ${question} 
                Candidate answer:  ${candidate_reply}
                
                Please provide communication and subject matter feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on "Title" , only if they are relevant to the situation. The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the responder.
                ${format_prompt}
                
                 
                ${user_feedback_prompt}
                \n\nAssistant:
                """
            )
            # log template for debugging
            return template.substitute(test_title=test_title,
                                    test_description=test_description,
                                    question=question,
                                    candidate_reply=candidate_reply,
                                    user_feedback_prompt=user_feedback_prompt,
                                    format_prompt=format_prompt)


@timeit
def get_user_first_dynamic_discussion_prompt(scenareo, test_title: str, test_description: str, comment: str, bot_response:str, question_number: int):
    """
    Generate a dynamic discussion prompt for providing feedback on manager, team member, or sales rep comments.

    Parameters:
    - scenario (str): Type of scenario, possible values: 'manager-team', 'team-manager', 'sales-customer', 'customer-sales'.
    - test_title (str): Title of the test.
    - test_description (str): Description of the test.
    - comment (str): Manager, team member, or sales rep comment.
    - bot_response (str): Bot response (applicable for 'team-manager' and 'customer-sales' scenarios).
    - question_number (int): Question number, used to determine the structure of the prompt.

    Returns:
    - str: Generated discussion prompt.

    Examples:
    >>> get_user_first_dynamic_discussion_prompt('manager-team', 'Leadership Skills Test', 'Evaluate the manager’s leadership skills.', 'The manager's comment is...', '', 1)
    # Returns the generated discussion prompt for providing feedback on a manager's comment.

    >>> get_user_first_dynamic_discussion_prompt('team-manager', 'Team Collaboration Test', 'Assess the team member’s collaboration skills.', 'The team member's comment is...', 'The bot response is...', 2)
    # Returns the generated discussion prompt for providing feedback on a team member's comment along with the bot response.

    >>> get_user_first_dynamic_discussion_prompt('sales-customer', 'Sales Pitch Test', 'Evaluate the sales rep’s pitch.', 'The sales rep's comment is...', '', 1)
    # Returns the generated discussion prompt for providing feedback on a sales rep's comment.
    """

    format_prompt = get_feedback_output_format_prompt(prompt_type='text',test_type='normal')

    match scenareo:
        case 'manager-team':
            if question_number == 1:
                template = Template(
                """
                    \n\nHuman:
                    Title: ${title}.

                    Test Description: ${description}

                    Manager Comment: ${manager_context}

                    Please provide communication and subject matter feedback for a manager who has provided a "Manager Comment" as specified for the "Test Description". The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the manager.  :

                    ${format_prompt}
                    NOTE : If the Manager Comment is a question provide feedback on how the manager can ask better questions.
                    NOTE : Do not provide any kind of heading or introduction text in the output. Start directly with the feedback and only provide the feedback.
                    \n\nAssistant:
                """
                        )
                return template.substitute(title=test_title, description=test_description,
                                            manager_context=comment,
                                            format_prompt=format_prompt)

            template = Template(
            '''
            \n\nHuman:
            Title: ${title}.

            Test Description: ${description}

            Bot response : ${bot_response}

            Manager Comment : ${manager_context}

            Please provide communication and subject matter feedback for a manager who has provided a "Manager Comment". Feedback must be based on test description and conversation so far. The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the responder.  :

            ${format_prompt}
            NOTE : If the Manager Comment is a question, provide feedback on how the manager can ask better questions.

            NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output. Start directly with the feedback and only provide the feedback.
            \n\nAssistant:
            ''')

            
            return template.substitute(title=test_title, description=test_description,
                                        manager_context=comment, bot_response=bot_response,
                                        format_prompt=format_prompt)
            
        case 'team-manager':
            if question_number == 1:
                template = Template(
                """
                    \n\nHuman:
                    Title: ${title}.

                    Test Description: ${description}

                    Team Member Comment: ${team_comment}

                    Please provide communication and subject matter feedback for a team member who has provided a "Team Member Comment" as specified for the "Test Description". The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the team member.  :

                    ${format_prompt}

                    NOTE : If the Team Member Comment is a question provide feedback on how the team member can ask better questions.


                    NOTE : Do not provide any kind of heading or introduction text in the output. Start directly with the feedback and only provide the feedback.
                    \n\nAssistant:

                """
                        )
                return template.substitute(title=test_title, description=test_description,
                                            team_comment=comment, format_prompt=format_prompt)

            template = Template(
            '''
                \n\nHuman:
                Title: ${title}.

                Test Description: ${description}

                Bot response : ${bot_response}

                Team Member Comment : ${team_comment}

                Please provide communication and subject matter feedback for a team member who has provided a "Team Member". Feedback must be based on test description and conversation so far. The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the team member.  :
                ${format_prompt}

                NOTE : If the Team Member Comment is a question, provide feedback on how the team member can ask better questions.


                NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output. Start directly with the feedback and only provide the feedback.

                \n\nAssistant:

            ''')

            
            return template.substitute(title=test_title, description=test_description,
                                        team_comment=comment, bot_response=bot_response,
                                        format_prompt=format_prompt)
        case 'sales-customer':
            if question_number == 1:
                template = Template(
                """
                    \n\nHuman:
                    Title: ${title}.

                    Test Description: ${description}

                    Sales rep Comment: ${sales_comment}

                    Please provide communication and subject matter feedback for a Sales rep who has provided a "Sales rep Comment" as specified for the "Test Description". The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the Sales rep.  :

                    ${format_prompt}
                    NOTE : If the Sales rep Comment is a question provide feedback on how the Sales rep can ask better questions.


                    NOTE : Do not provide any kind of heading or introduction text in the output. Start directly with the feedback and only provide the feedback.
                    
                    \n\nAssistant:

                """
                        )
                return template.substitute(title=test_title, description=test_description,
                                            sales_comment=comment, format_prompt=format_prompt)

            template = Template(
            '''
                \n\nHuman:
                Title: ${title}.

                Test Description: ${description}

                Bot response : ${bot_response}

                Sales rep Comment : ${sales_comment}

                Please provide communication and subject matter feedback for a Sales rep who has provided a "Sales rep". Feedback must be based on test description and conversation so far. The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the Sales rep.  :

                ${format_prompt}
                NOTE : If the Sales rep Comment is a question, provide feedback on how the Sales rep can ask better questions.
                NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output. Start directly with the feedback and only provide the feedback.
                \n\nAssistant:

            ''')

            
            return template.substitute(title=test_title, description=test_description,
                                        sales_comment=comment, bot_response=bot_response,
                                        format_prompt=format_prompt)
        case 'customer-sales':
            if question_number == 1:
                template = Template(
                """
                    \n\nCustomer:
                    Title: ${title}.

                    Test Description: ${description}

                    Customer Comment: ${sales_comment}

                    Please provide communication and subject matter feedback for a customer who has provided a "Customer Comment" as specified for the "Test Description". The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically helps enhance people skills of the customer.  :

                    ${format_prompt}
                    NOTE: If the Customer Comment is a question provide feedback on how the customer can ask better questions.


                    NOTE: Do not provide any kind of heading or introduction text in the output. Start directly with the feedback and only provide the feedback.

                    \n\nAssistant:

                """
                        )
                return template.substitute(title=test_title, description=test_description,
                                            sales_comment=comment, format_prompt=format_prompt)

            template = Template(
            '''
                \n\nCustomer:
                Title: ${title}.

                Test Description: ${description}

                Bot response: ${bot_response}

                Customer Comment: ${sales_comment}

                Please provide communication and subject matter feedback for a customer who has provided a "Customer Comment". Feedback must be based on the test description and conversation so far. The feedback should include whether the right questions are asked for engagement. Please provide feedback which specifically helps enhance people skills of the customer.  :

                ${format_prompt}
                NOTE: If the Customer Comment is a question, provide feedback on how the customer can ask better questions.

                NOTE: Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output. Start directly with the feedback and only provide the feedback.

                \n\nAssistant:

            ''')
            
            return template.substitute(title=test_title, description=test_description,
                                        sales_comment=comment, bot_response=bot_response,
                                        format_prompt=format_prompt)
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
            if question_number == 2:
                user_comment = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session_id,
                                                                responder_type=QuestionForChoices.user,
                                                                deleted=0).first()
                template = Template(
                '''
                \n\nHuman:
                main_context: ${test_main_context}

                customer_comment: ${user_comment}

                Provide a response to the customer’s comment as the sales rep based on the given context. Do not provide any feedback on the response.

                NOTE: NEVER provide the response in bullet points. Only provide the response in paragraphs.

                NOTE: The response should not be more than 25 words.

                NOTE: Do not show the word count.

                NOTE: Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output.
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
                \n\nCustomer:
                main_context: ${test_main_context}

                current_conversation: ${current_conversation}

                customer_comment: ${user_comment}

                Provide a response to the customer’s comment as the sales rep based on the given context. Do not provide any feedback on the response.

                NOTE: NEVER provide the response in bullet points. Only provide the response in paragraphs.

                NOTE: The response should not be more than 25 words.

                NOTE: Do not show the word count.

                NOTE: Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output.
                \n\nAssistant:

                '''
                )

                return template.substitute(test_main_context=test.description,
                                        user_comment=user_comment.response_text, current_conversation=current_conversation)
        case default:
            logger.warning("!!!!!!!!!!!!!!!!!! Invalid user_first scenareo type: %s", scenareo)
            return "nothing"

@timeit
def extract_question(text, responder_name):
    # Define the regular expression pattern to match the question part
    text = text.replace('{',"").replace("}","")
    pattern = r":\s*([^:]+)$"
    
    # Search for the pattern in the provided text
    match = re.search(pattern, text)
    
    # If a match is found, extract and return the question part
    if match:
        print(match.group(1).strip() )
        pattern = rf"\b{responder_name}\b[:,]?\s*"
    
        # Replace all occurrences of the pattern with an empty string
        cleaned_text = re.sub(pattern, '', match.group(1).strip(), flags=re.IGNORECASE)
        # Ensure there's no space before punctuation marks
        cleaned_text = re.sub(r'\s+([?.!,])', r'\1', cleaned_text)
        
        # Return the cleaned text, stripped of leading/trailing whitespace
        return cleaned_text.strip()
    
    else:
        return text.strip()

@timeit
def get_orchestrated_test_conversation_prompt(test: Test,
                                              test_attempt_session: TestAttemptSession,
                                              question: TestQuestion):
    """
    This function generates a conversation prompt for an orchestrated test.

    The function first retrieves the main context, user persona, initial messages, and other details from the test. It then constructs the current conversation based on these details and the responses from the test attempt session. If a response text is not immediately available, the function waits for it to be populated, with a maximum wait time of 30 seconds.

    The function then generates a prompt based on the test type and other conditions. The prompt is a string that includes the main context, current conversation, and the question text, formatted according to specific rules.

    Parameters:
    - test (Test): The test object. It should have an 'orchestrated_conversation_details' attribute which is a dictionary containing details about the test.
    - test_attempt_session (TestAttemptSession): The test attempt session object. It is used to retrieve the responses for the test.
    - question (TestQuestion): The question object. The question text is included in the prompt.

    Returns:
    - str: The generated prompt. The prompt includes the main context, current conversation, and the question text, formatted according to specific rules.

    Example:
    >>> test = Test.objects.get(id=1)
    >>> test_attempt_session = TestAttemptSession.objects.get(id=1)
    >>> question = TestQuestion.objects.get(id=1)
    >>> prompt = get_orchestrated_test_conversation_prompt(test, test_attempt_session, question)
    >>> print(prompt)
    'Human: Main context : This is the main context. Current conversation : This is the current conversation. Candidate response : This is the question text. NOTE: Based on the Candidate response, and the main context ask the candidate the next question. The question should continue the Current conversation. Do not provide any feedback on the response. Always ask a unique, different and specific question based on Candidate response. The question should be relevant to the information or response given in Candidate response. Always ask a question that helps understand the problem better or ask how to implement a solution to the problem. Read the Current conversation and make sure the next question is unique and has not been repeated in the conversation before. Never ask a question that has been asked before. NOTE: The question should not be more than 25 words. NOTE: Do not show the word count. NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output. Start directly with the question and only provide the question. Assistant:'
    """

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

    discussion_conversation = [que for que in initial_messages]
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
            discussion_conversation.append(f"user: {response_text}" if len(response_text.split(":")) == 1 else response_text)
        else:
            conv_text = f"{test_response.responder_type}: {response_text}"
            if len(response_text.strip())>0:
                discussion_conversation.append(conv_text if len(response_text.split(":")) == 1 else response_text)

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

                Read the Current conversation and make sure the next question is unique and has not been repeated in the conversation before. Never ask a question that has been asked before.

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

            print(f"""
            main_context: {test_main_context}
            current_conversation: {current_conversation}
            question_text: {question_text}
            
            """)

            
            current_conv = discussion_conversation[:-4] if len(discussion_conversation) > 4 else ""
            current_response = (discussion_conversation[-4:] if len(discussion_conversation) > 4 else discussion_conversation)[:-1]
            candidate_response = discussion_conversation[-1]
            main_context = f"""
            Title: {test.title}
            Description: {test.description}
            """

            print(f"""
            main_context: {main_context}
            current_conversation: {current_conv}
            current_response: {current_response}
            candidate_response: {candidate_response}
            discussion_coversation: {discussion_conversation}
            len discussion_conversation: {len(discussion_conversation)}
            """)

            if test.test_code != 'QKFSSBD':

                template = Template("""
                    \n\nHuman:
                    Main context: ${test_main_context}
                    Current conversation : {
                                    ${current_conversation}
                                    }
                    Current Responses: {
                                    ${current_responses}
                                    }
                    Candidate response: {
                                    ${candidate_response}
                                    }
                    
                    Based on the (Candidate response), and the (main context), ask the candidate the next question. The question should continue the (candidate response) and the (Current Response) which shall always redirect to the (main context) or (candidate response) if it is not relevant. Do not provide any feedback on the response.
                    ${question_text}
                    Always ask a unique, different and specific question based on the (Candidate response), (main context), and (Current Response). The question should be relevant to the information or response given in the (Candidate response). Always ask a question that helps understand the problem better or ask how to implement a solution to the problem.
                    Always pose the questions as for the role play, also ask questions as very specific role who is assigned to ask questions in the (main context).
                    Always take the role of who will be asking questions from the (main context) to generate questions.
                                    
                    Always add name in front of the question as based from the (main context) while generating the question and which user will respond using (Format for Questions),
                    {
                    Format for Questions
                    Name: Question
                    }
                                    
                    Analyze the role of the user from the (main context) who will never ask the question, there will be always one user who will never ask the question, just respond.
                    Never misinterpret the role of the user who will be answering only from the (main context) while generating questions. In this role of user will never ask any questions.
                    Always stick with the role who is asking question from the (main context) while generating questions.
                    Read the (Current response) and (Current conversation) and make sure the next question is unique and has not been repeated in the (Current response) and (Current conversation) before. Never ask a question that has been asked before. Never repeat the same response.
                    NOTE: The question should not be more than 25 words.
                    NOTE: There will be always one role of the user who will never ask any question, but only answer. Never generate questions for that role of the user from the (main context).
                    NOTE: Analyse the role of the user who will never ask questions from the (main context) and never generate questions from his side.
                    NOTE: Do not show the word count.
                    NOTE: Pose the questions as for the role play, also ask questions as a very specific role the person who is asking questions from the (main context) while generating the questions.
                    NOTE: Always stick with the role of the person while generating questions from the (main context).
                    NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output. Start directly with the question and only provide the question.
                    NOTE: Always follow the format but never mention in the response.
                    NOTE: Never give brackets to show the response.
                    Note: Never ask a question that has been asked before. Never repeat the same response.
                    \n\nAssistant:
                """).substitute(
                    test_main_context=main_context,
                    current_conversation="\n".join(current_conv) if isinstance(current_conv,list)  else current_conv,
                    current_responses="\n".join(current_response),
                    candidate_response=candidate_response,
                    question_text=question_text
                )
                print("="* 100)
                print(template)
                print("="* 100)

            else:

                template = Template(
                        '''
                        \n\nHuman:
                        Main context : ${test_main_context}
                        Current conversation : ${current_conversation}
                        Candidate response : ${question_text}

                        NOTE: Based on the Candidate response, and the main context ask the candidate the next question. The question should continue the Current conversation. Do not provide any feedback on the response.
                        Always ask a unique, different and specific question based on Candidate response. The question should be relevant to the information or response given in Candidate response. Always ask a question that helps understand the problem better or ask how to implement a solution to the problem.

                        Read the Current conversation and make sure the next question is unique and has not been repeated in the conversation before. Never ask a question that has been asked before.

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

            Read the Current conversation and make sure the response is unique and has not been repeated in the conversation before. Never give a response that has been given before.

            NOTE: Please respond as ${question_for} only. Do not respond as any other persona.
            NOTE: Please respond in not more than 180 words. The total number of words should not be more than 150 words.
            NOTE: Always directly start responding without name in front.
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

        Please provide communication and subject matter feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on "Title" , only if they are relevant to the situation. The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the responder. 
        The feedback should be structured in the following format: 
        - What went well ? : "output text"
        - What could be improved ? : "output text"
        - Some new ideas to reframe the context : "output text"
        - A sample re-written email : "output text"
        - A counter intuitive insight : "output text"

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
    format_prompt = get_feedback_output_format_prompt(prompt_type='text',test_type='normal')

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
            ${format_prompt}
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
                                   user_feedback_prompt=user_feedback_prompt,
                                   format_prompt=format_prompt)

    else:
        template = Template(
            """
            \n\nHuman:
            Title: ${test_title}. 
            Test Description: ${test_description}
            Customer question:  ${question} 
            Evaluation Criteria: ${prompt_template}
            Candidate answer:  ${candidate_reply}
    
            Please provide communication and subject matter feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on  "Title" , only if they are relevant to the situation. The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the responder.
            ${format_prompt}

            ${user_feedback_prompt}
            \n\nAssistant:
            """
        )
        return template.substitute(test_title=test_title,
                                   test_description=test_description,
                                   question=question,
                                   prompt_template=prompt_template,
                                   candidate_reply=candidate_reply,
                                   user_feedback_prompt=user_feedback_prompt,
                                   format_prompt=format_prompt)
    

@timeit
def get_english_support_feedback_prompt(prompt_template: str,
                        test_title: str,
                        test_description: str,
                        question: str,
                        candidate_reply: str,
                        user_feedback_prompt:str):
        format_prompt = get_feedback_output_format_prompt(prompt_type='text',test_type='normal')

        template = Template(
            """
            \n\nHuman:
            Title: ${test_title}. 
            Test Description: ${test_description}
            Customer question:  ${question} 
            Evaluation Criteria: ${prompt_template} 
            Candidate answer:  ${candidate_reply}

            Please provide feedback on the English speaking proficiency of a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on areas such as grammar, vocabulary usage, fluency, and overall clarity of communication. 

            Additionally, comment on their ability to convey complex ideas effectively and their overall command of the English language. Comment on the emotions that should have been used in the response and does that choice of words reflect that emotion. 

            Provide constructive insights that help gauge the candidate's overall language proficiency and potential for improvement. Provide the feedback based on Expert Suggestions. Please provide feedback which specifically help enhance English speaking skills of the candidate. Only provide feedback on the English proficiency of the candidate.

            ${format_prompt}
            ${user_feedback_prompt}
            \n\nAssistant:
            """
        )
        
        return template.substitute(test_title=test_title,
                            test_description=test_description,
                            question=question,
                            prompt_template=prompt_template,
                            candidate_reply=candidate_reply,
                            user_feedback_prompt=user_feedback_prompt,
                            format_prompt=format_prompt)
@timeit
def get_journaling_feedback_prompt(prompt_template: str,
                        test_title: str,
                        test_description: str,
                        question: str,
                        candidate_reply: str,
                        user_feedback_prompt:str):
        format_prompt = get_feedback_output_format_prompt(prompt_type='text',test_type='normal')

        template = Template(
            """
            \n\nHuman:
            Title: ${test_title}. 
            Test Description: ${test_description}
            Customer question:  ${question} 
            Evaluation Criteria: ${prompt_template} 
            Candidate answer:  ${candidate_reply}

            Please provide communication and subject matter feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on "Title", only if they are relevant to the situation. The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the responder.

            FOR Sample Candidate: Provide constructive feedback in the context of journaling, presenting a sample candidate response based on the provided Q&A. Maintain the structure outlined in the custom prompt while intentionally including with full statements reference to the XYZ AB framework. Never mention letters XYZ AB.

            ${format_prompt}
            ${user_feedback_prompt}
            \n\nAssistant:
            """
        )
        
        return template.substitute(test_title=test_title,
                            test_description=test_description,
                            question=question,
                            prompt_template=prompt_template,
                            candidate_reply=candidate_reply,
                            user_feedback_prompt=user_feedback_prompt,
                            format_prompt=format_prompt)

    
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
    """
    Generate a prompt to extract a key learning point from an ideal answer to a given question.

    Parameters:
    - test_title (str): Title of the test.
    - test_question (str): Text of the question.

    Returns:
    - str: Extracted key learning point.

    Examples:
    >>> get_question_key_learning_point('Leadership Skills Test', 'What qualities make a great leader?')
    # Returns the extracted key learning point from an ideal answer to the given question.
    """
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
    """
    Generate a prompt to extract key learning skills from an ideal answer to a given question.

    Parameters:
    - test_title (str): Title of the test.
    - test_question (str): Text of the question.

    Returns:
    - str: Extracted key learning skills, separated by commas.

    Examples:
    >>> get_question_key_learning_skills('Leadership Skills Test', 'What qualities make a great leader?')
    # Returns the extracted key learning skills from an ideal answer to the given question.
    """

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
    """
    Generates a test report for a given test.

    This function retrieves all completed test attempt sessions for a given test, 
    calculates the scores for each participant, and sorts them in descending order. 
    It then counts the total number of questions in the test. 
    If the `only_data` flag is set to True, it returns a dictionary containing the test name, 
    total number of questions, total number of test attempts, test scores, and test code. 
    If the `only_data` flag is set to False, it generates a PDF report using the test data, 
    saves it as a document in the system, and returns the URL of the document.

    Args:
        test (Test): The test object for which the report is to be generated.
        only_data (bool, optional): A flag to determine whether to return only the test data 
                                     or to generate a PDF report. Defaults to False.

    Returns:
        str or dict: If `only_data` is True, returns a dictionary containing the test data. 
                     If `only_data` is False, returns a string representing the URL of the generated PDF report.

    Example:
        >>> get_test_report(test_object, only_data=True)
        {
            'test_name': 'Sample Test',
            'total_questions': 10,
            'total_tests_attempts': 5,
            'test_scores': [{'score': 80, 'avg_score': 80, 'speech_score': 80, 'participant': 'John Doe'}, ...],
            'test_code': 'TEST123'
        }

        >>> get_test_report(test_object, only_data=False)
        'https://example.com/document/test_report_123.pdf'
    """
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
    """
    this method used to create scenario format using anthropic 
    """
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
    """
    Categorize skills based on their scores and descriptions.

    Parameters:
    - skill_dict (dict): Dictionary containing skills as keys and their scores as values.
    - skills_object (dict): Dictionary containing skills as keys and their descriptions as values.

    Returns:
    - list: List of dictionaries containing categorized skills, scores, and descriptions.

    Example:
    >>> categorize_skills({'communication': 0.8, 'leadership': 0.9}, {'Communication': 'Effective communication...', 'Leadership': 'Ability to lead...'})
    # Returns a list of dictionaries with categorized skills, scores, and descriptions.
    """
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
    """
    This function retrieves and processes skills tracking data for a given participant.

    The function first filters the TestAttemptSession objects based on the provided participant_id and orders them by id in descending order. If the count of these sessions is more than 15, it limits the sessions to the latest 15. If there are no sessions, it returns None.

    For each TestAttemptSession, it retrieves the corresponding Test object and extracts the candidate_type. If the candidate_type is None, it defaults to 'Manager'. It also retrieves the participant's name and the skills rating for the session.

    The function then categorizes the skills ratings into four categories: People, Partnership, Process, and Personality, based on the candidate_type. It returns a dictionary containing the participant's name, the interaction date, and a list of dictionaries for each category with the category name and the categorized skills.

    Args:
        participant_id (str): The id of the participant for whom to retrieve and process the skills tracking data.

    Returns:
        dict: A dictionary containing the participant's name, the interaction date, and a list of dictionaries for each category with the category name and the categorized skills. Returns None if there are no TestAttemptSession objects for the given participant_id.

    Example:
        >>> get_skills_tracker_data('123')
        {
            'data': {
                'participant_name': 'John Doe',
                'interaction_date': '01 Jan 2022',
                'mylist': [
                    {
                        'chart_name': 'People',
                        'trends': {...}
                    },
                    {
                        'chart_name': 'Partnership',
                        'trends': {...}
                    },
                    {
                        'chart_name': 'Process',
                        'trends': {...}
                    },
                    {
                        'chart_name': 'Personality',
                        'trends': {...}
                    }
                ]
            }
        }
    """
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
    """
    Update user attributes for the given user_id in the UserAttribute model.

    Parameters:
    - user_id (str): Unique identifier for the user.
    - var_dict (dict): Dictionary containing attribute names as keys and their updated values as values.

    Example:
    >>> update_prompt_user_attributes('123456', {'attribute1': 'value1', 'attribute2': 'value2'})
    """
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
    """
    This function is used to submit feedback for a given test question response. It first fetches the relevant test, question, and test attempt session objects based on the provided session_id, tenant_id, and question_id. It then creates or retrieves a TestQuestionResponse object and updates it with the response file and its transcript.

    Based on the difficulty level of the user, it appends the appropriate feedback prompts. If the test is of email type or employee feedback scenario, it generates a specific prompt. Otherwise, it generates a prompt based on whether there is a gpt_prompt_override or not.

    The function then checks the length of the response text. If it's too short, it sets a feedback text indicating that no feedback can be generated. If the length is sufficient, it tries to generate feedback using the gpt3_completion function. If gpt3_completion fails to generate feedback, it tries to generate feedback using the gemini_completion function and if that fails too, it uses the anthropic_completion function.

    Finally, it updates the TestQuestionResponse object with the generated feedback and the metadata related to the gpt prompt and response, and saves it.

    Args:
        session_id (str): The unique identifier of the test attempt session.
        tenant_id (str): The unique identifier of the tenant.
        question_id (str): The unique identifier of the question.
        response_file (str): The path to the response file.

    Returns:
        str: The feedback text generated for the response.

    Example:
        >>> submit_feedback('session123', 'tenant123', 'question123', 'path/to/response/file')
    """
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
                user_feedback_prompt=user_feedback_prompt,
                articles=test.articles,
                scenario_summary=test.scenario_summary,)


    feedback_text = ''
    raw_text = ''
    response_text = test_question_response.response_text
    go_for_feedback = True

    # words = word_tokenize(test_question_response.response_text)

    # if len(words) <= 10 :
    #     feedback_text = "No feedback can be generated because of too low response length"
    #     go_for_feedback = False
    
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
                                user_feedback_prompt=user_feedback_prompt,
                                articles=test.articles,
                                scenario_summary=test.scenario_summary,)

                max_retry -= 1


            if test.is_free:
                    anthropic_feedback = anthropic_completion(prompt, 1200)
                    if anthropic_feedback:
                        feedback_text = anthropic_feedback
                    else:
                        feedback_text = 'Feedback could not be generated'
                
            else:
                try:
                    feedback_text = gemini_completion(prompt=prompt,instruction="Please always respond within 150 tokens in summary format. Always respond in a Markdown language.")
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
    
    test_question_response.save(update_fields=['metadata','feedback_text'])
    logger.info("######################## Feedback is ready ######################")

    return test_question_response.feedback_text


#------------- ScenarioCreator ------------------

# all scenario prompt static, dynamic
def get_scenario_prompt(scenario_type,information,skill_count=2,question_count=3):
    prompt = ""
    if scenario_type == 'normal':
      prompt = """
        \n\nHuman:
        {Information} -
        %s -
        Read this {information} thoroughly. Now based on this information and your understanding create an advanced and tough simulation situation to practice the skills presented in the {information}. After creating the situation provide these:
        Description - Define the situation, and the problem. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on based on data, industry, events, etc. The description should just describe the problem and what was the specific situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.
        Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
        Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.
        Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide a feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
        KLP - With each question add one or two line takeaway for providing feedback. The takeaways should be related to the question it is provided with.
        KLS - With each question, add the skill(s) that are tested. And For every question choose exactly {%s} skill(s) and not more or less than {%s} should be chosen for each question. The skills for all the questions should be unique. Each question shall have a unique skill.
        Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
        In every response, you must:
        Clearly state your role as X.
        Identify Y as the person asking
        The Question, Custom Prompt, KLP, KLS should be numbered.
        Here the format looks like :
        "Title:",
        "Description:”,
        “Statement:",
        "Question 1:",
        "Prompt 1:",
        "Takeaway 1:" ,
        "Skills 1:" repeated for {%s} question(s). Do not include any {responder} response.
        'The Question, Prompt, Takeaway, Skills should be numbered.'
        NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
        NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
        NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated. Each skill shall only be one word.
        NOTE: "Rating" must be included.
        NOTE : Make sure the simulation is very advanced and tough.
        NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
        NOTE: Never miss Title, Description, Statement and other variables.
        NOTE: Do not mention "X" or "Y".
        \n\nAssistant:

    """
    elif scenario_type == 'role_play':
      prompt= """
        \n\nHuman:
        {Information} - %s-
        Read this {information} thoroughly. Based on this information and your understanding create an advanced and tough roleplay situation to practice the skills presented in the {information}. After making the situation provide these:
        Description - Define the situation and the problem. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on data, industry, events, etc. The description should describe the problem and what was the particular situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third-person point of view. Describe 100 to 200 words. Do not add any conclusion.
        Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
        Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the problem. NEVER respond to the questions.
        Custom prompt - With each question, add a prompt asking for feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
        KLP - With each question add one or two line takeaways for providing feedback. The takeaways should be related to the question it is supplied with.
        KLS - Add the skill(s) that are tested with each question. And For every question choose exactly {%s} skill(s) and not more or less than {%s} should be chosen for each question. The skills for all the questions should be unique.
        Always use indian names in the role play, also mention what role the user will be playing while answering the questions in the description.
        Always use name in each question. The role play shall also have element of a other person who will be asking the questions.
        Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
        The Question, Custom Prompt, KLP, KLS should be numbered.
        Here the format looks like :
        "Title:",
        "Description:”,
        “Statement:",
        "Question 1:",
        "Prompt 1:",
        "Takeaway 1:" ,
        "Skills 1:" repeated for {%s} question(s). Do not include any {responder} response.
        'The Question, Prompt, Takeaway, Skills should be numbered.'
        NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
        NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
        NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated. Each skill shall only be one word.
        NOTE: "Rating" must be included.
        NOTE: Make sure the roleplay is very advanced and tough.
        NOTE: Always use a name in each question. The role play shall also have the element of an other person who will be asking the questions.
        NOTE: Always mention in the context what role the user will be playing the role while answering.
        NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
        NOTE: Never miss Title, Description, Statement and other variables.
        NOTE: Do not mention "X" or "Y".
        \n\nAssistant:
        """
      
    elif scenario_type == "case":
      prompt = """
        \n\nHuman:
        {Information} - %s
        Read this {information} thoroughly. Now based on this information and your understanding create an advanced and tough simulation situation to practice the skills presented in the {information}. After creating the situation provide these:
        Description - Define the situation, and the problem. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on based on data, industry, events, etc. The description should just describe the problem and what was the specific situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.
        Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
        Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.
        Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide a feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
        KLP - With each question add one or two line takeaway for providing feedback. The takeaways should be related to the question it is provided with.
        KLS - With each question, add the skill(s) that are tested. And For every question choose exactly {%s} skill(s) and not more or less than {%s} should be chosen for each question. The skills for all the questions should be unique.
        Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
        Always Use a literary genre to generate the response in high literature.
        Literary genres encompass a wide spectrum of styles and themes, ranging from the imaginative realms of fiction, poetry, drama, and fantasy to the factual landscapes of non-fiction, biography, and autobiography. Mystery, science fiction, romance, historical fiction, and horror delve into specific narrative territories, while thriller, adventure, satire, comedy, tragedy, and epic offer diverse storytelling approaches. Additionally, fables, fairy tales, mythology, and folklore explore cultural narratives and traditions. Genres like dystopian, gothic, bildungsroman (coming-of-age), absurdist, and magical realism push the boundaries of conventional storytelling, while realistic fiction and experimental literature offer unique perspectives on reality and form. Each genre contributes to the rich tapestry of literary expression, offering readers a multitude of worlds and experiences to explore.
        In every response, you must:
        Clearly state your role as X.
        Identify Y as the person asking
        The Question, Custom Prompt, KLP, KLS should be numbered.
        Here the format looks like :
        "Title:",
        "Description:”,
        “Statement:",
        "Question 1:",
        "Prompt 1:",
        "Takeaway 1:" ,
        "Skills 1:" repeated for {%s} question(s). Do not include any {responder} response.
        'The Question, Prompt, Takeaway, Skills should be numbered.'
        NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
        NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
        NOTE: "Rating" must be included.
        NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated. Each skill shall only be one word.
        NOTE : Make sure the simulation is very advanced and tough.
        NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
        NOTE: Always use suitable literary genre to genre create the response.
        NOTE: Never miss Title, Description, Statement and other variables.
        NOTE: Do not mention "X" or "Y".
        \n\nAssistant:

        """
      
    elif scenario_type == "interview":
      prompt = """
        \n\nHuman:
        {Information} - %s
        Read this {information} thoroughly. Now based on this information and your understanding create an advanced and tough simulation situation to practice the skills presented in the {information}. After creating the situation provide these:
        Description - Define the situation, and the problem. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on based on data, industry, events, etc. The description should just describe the problem and what was the specific situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.
        Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
        Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.
        Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide a feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
        KLP - With each question add one or two line takeaway for providing feedback. The takeaways should be related to the question it is provided with.
        KLS - With each question, add the skill(s) that are tested. And For every question choose exactly {%s} skill(s) and not more or less than {%s} should be chosen for each question. The skills for all the questions should be unique.
        Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
        Always use a interview to generate the response for communication and information gathering.
        An interview is a formal conversation between an interviewer and an interviewee, typically in a professional setting, to assess the interviewee's suitability for a particular role or to gather information. It is a common practice in the corporate world and other professional settings, where employers or hiring managers conduct interviews to evaluate potential candidates for employment.
        In every response, you must:
        Clearly state your role as X.
        Identify Y as the person asking
        The Question, Custom Prompt, KLP, KLS should be numbered.
        Here the format looks like :
        "Title:",
        "Description:”,
        “Statement:",
        "Question 1:",
        "Prompt 1:",
        "Takeaway 1:" ,
        "Skills 1:" repeated for {%s} question(s). Do not include any {responder} response.
        'The Question, Prompt, Takeaway, Skills should be numbered.'
        NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
        NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
        NOTE: "Rating" must be included.
        NOTE : Make sure the simulation is very advanced and tough.
        NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated. Each skill shall only be one word.
        NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
        NOTE: Always use interview for communication and information gathering.
        NOTE: Never miss Title, Description, Statement and other variables.
        NOTE: Do not mention "X" or "Y".
        \n\nAssistant:
        """
    elif scenario_type == 'checkin':
      prompt = """
          \n\nHuman:
          {Information} - %s
          Read this {information} thoroughly. Now based on this information and your understanding create an advanced and tough simulation situation to practice the skills presented in the {information}. After creating the situation provide these:
          Description - Define the situation, and the problem. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on based on data, industry, events, etc. The description should just describe the problem and what was the specific situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.
          Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description related to the check-in.
          Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.
          Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide a feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
          KLP - With each question add one or two line takeaway for providing feedback. The takeaways should be related to the question it is provided with.
          KLS - With each question, add the skill(s) that are tested. And For every question choose exactly {%s} skill(s) and not more or less than {%s} should be chosen for each question. The skills for all the questions should be unique.
          Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
          Always use a check-in to generate the response for communication and information gathering.
          Check-in in a corporate setting refers to the process of employees or participants recording their arrival at the workplace, a meeting, a conference, or any other professional gathering. This practice allows for improved attendance tracking, resource allocation, and streamlined communication within the enterprise.
          In every response, you must:
          Clearly state your role as X.
          Identify Y as the person asking
          The Question, Custom Prompt, KLP, KLS should be numbered.
          Here the format looks like :
          "Title:",
          "Description:”,
          “Statement:",
          "Question 1:",
          "Prompt 1:",
          "Takeaway 1:" ,
          "Skills 1:" repeated for {%s} question(s). Do not include any {responder} response.
          'The Question, Prompt, Takeaway, Skills should be numbered.'
          NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
          NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable like an check-in.
          . Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
          NOTE: "Rating" must be included.
          NOTE : Make sure the simulation is very advanced and tough.
          NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
          NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated. Each skill shall only be one word.
          NOTE: Always use check-in for communication and information gathering.
          NOTE: Never miss Title, Description, Statement and other variables.
          NOTE: Do not mention "X" or "Y".
          \n\nAssistant:

          """
    elif scenario_type == "static_hard":
      prompt = '''
      \n\nHuman:
            {Information} -
            %s -
            Read this {information} thoroughly. Now based on this information and your understanding create an advanced and tough simulation situation to practice the skills presented in the {information}. After creating the situation provide these:
            Description - Define the situation, and the problem focuses exclusively on hard skills. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on data, industry, events, etc. The description should just describe the problem and what was the specific situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.
            Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
            Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.Question shall focus exclusively on hard skills
            Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
            KLP - With each question add one or two line takeaways for providing feedback. The takeaways should be related to the question it is provided with.
            KLS - With each question, add the skill(s) that are tested. And For every question choose exactly {%s} skill(s) and not more or less than {%s} should be chosen for each question. The skills for all the questions should be unique AND shall not repeat from (information). Each question shall have a unique skill AND shall not repeat from (information) and focus exclusively on hard skills
            Always end the description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
            In every response, you must:
            Clearly state your role as X as in (information).
            Identify Y as the person asking as in (information)
            The Question, Custom Prompt, KLP, KLS should be numbered.
            Here the format looks like :
            "Title:",
            "Description:”,
            “Statement:",
            "Question 1:",
            "Prompt 1:",
            "Takeaway 1:" ,
            "Skills 1:" repeated for {%s} question(s). Do not include any {responder} response.
            'The Question, Prompt, Takeaway, Skills should be numbered.'

            NOTE: Description, questions, and skills should focus exclusively on hard skills.
            NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
            NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
            NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated. Each skill shall only be one word AND shall not repeat from (information).
            NOTE: "Rating" must be included.
            NOTE : Make sure the simulation is very advanced and tough.
            NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description] as in (information). Your intent is to achieve Z.
            NOTE: Never miss Title, Description, Statement and other variables.
            \n\nAssistant:


      '''
    elif scenario_type == 'static_soft':
      prompt = """
            (information: %s)

            Carefully review and analyze the provided {information}. Based on this assessment, create a rigorous, high-level simulation that serves as an extended version of the previous scenario, diving deeper into the required skills and interactions. This new scenario must specifically address new areas for candidates to explore, ensuring a targeted approach to tackling an entirely new challenge.

            Key Requirements:
              Create a brand new scenaio in the same industry. Target ONLY soft skills that are not covered in the {information} context.
              Note: Never change the Industry Domain of the scenario.

            Deliver the extended scenario accordingly


            Read this {information} thoroughly. Now based on this information and your understanding create an advanced and tough simulation situation to practice the skills presented in the {information}. After creating the situation provide these:
            Description - Define the situation, and the problem focuses exclusively on soft skills. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on data, industry, events, etc. The description should just describe the problem and what was the specific situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.
            Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
            Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.Question shall focus exclusively on soft skills
            Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
            KLP - With each question add one or two line takeaways for providing feedback. The takeaways should be related to the question it is provided with.
            KLS - With each question, add the skill(s) that are tested. And For every question choose exactly {%s} skill(s) and not more or less than {%s} should be chosen for each question. The skills for all the questions should be unique AND shall not repeat from (SKILLS) instead use different skills. Each question shall have a unique skill AND shall not repeat from (SKILLS) instead use different skills and focus exclusively on soft skills.
            Always end the description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
            In every response, you must:
            Clearly state your role as X as in (information).
            Identify Y as the person asking as in (information)
            The Question, Custom Prompt, KLP, KLS should be numbered.
            Here the format looks like :
            "Title:",
            "Description:”,
            “Statement:",
            "Question 1:",
            "Prompt 1:",
            "Takeaway 1:" ,
            "Skills 1:" repeated for {%s} question(s). Do not include any {responder} response.
            'The Question, Prompt, Takeaway, Skills should be numbered.'

            NOTE: Description, questions, and skills should focus exclusively on soft skills.
            NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
            NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
            NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated. Each skill shall only be one word AND shall not repeat from (SKILLS) instead use different skills.
            NOTE: "Rating" must be included.
            NOTE : Make sure the simulation is very advanced and tough.
            NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description] as in (information). Your intent is to achieve Z.
            NOTE: Never miss Title, Description, Statement and other variables.
            \n\nAssistant:

      """
    elif scenario_type == 'static_role_play_soft':
      prompt = """
      \n\nHuman:
                {Information} - %s-
                Read this {information} thoroughly. Based on this information and your understanding create an advanced and tough roleplay situation to practice the skills presented in the {information}. After making the situation provide these:
                Description - Define the situation and the problem focuses exclusively on soft skills. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on data, industry, events, etc. The description should describe the problem and what was the particular situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third-person point of view. Describe 100 to 200 words. Do not add any conclusion.
                Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
                Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the problem. NEVER respond to the questions. Question shall focus exclusively on soft skills
                Custom prompt - With each question, add a prompt asking for feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
                KLP - With each question add one or two line takeaways for providing feedback. The takeaways should be related to the question it is supplied with.
                KLS - Add the skill(s) that are tested with each question. And For every question choose exactly {%s} skill(s) and not more or less than {%s} should be chosen for each question. The skills for all the questions should be unique and and focus exclusively on soft skills.
                Always use indian names in the role play, also mention what role the user will be playing while answering the questions in the description.
                Always use name in each question. The role play shall also have element of a other person who will be asking the questions.
                Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
                The Question, Custom Prompt, KLP, KLS should be numbered.
                Here the format looks like :
                "Title:",
                "Description:”,
                “Statement:",
                "Question 1:",
                "Prompt 1:",
                "Takeaway 1:" ,
                "Skills 1:" repeated for {%s} question(s). Do not include any {responder} response.
                'The Question, Prompt, Takeaway, Skills should be numbered.'

                NOTE: Description, questions, and skills should focus exclusively on soft skills.
                NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
                NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
                NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated. Each skill shall only be one word.
                NOTE: "Rating" must be included.
                NOTE: Make sure the roleplay is very advanced and tough.
                NOTE: Always use a name in each question. The role play shall also have the element of an other person who will be asking the questions.
                NOTE: Always mention in the context what role the user will be playing the role while answering.
                NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
                NOTE: Never miss Title, Description, Statement and other variables.

                \n\nAssistant:

      """

    elif scenario_type == 'static_role_play_hard':
      prompt = """
      \n\nHuman:
                {Information} - %s-
                Read this {information} thoroughly. Based on this information and your understanding create an advanced and tough roleplay situation to practice the skills presented in the {information}. After making the situation provide these:
                Description - Define the situation and the problem focuses exclusively on hard skills. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on data, industry, events, etc. The description should describe the problem and what was the particular situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third-person point of view. Describe 100 to 200 words. Do not add any conclusion.
                Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
                Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the problem. NEVER respond to the questions. Question shall focus exclusively on hard skills
                Custom prompt - With each question, add a prompt asking for feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
                KLP - With each question add one or two line takeaways for providing feedback. The takeaways should be related to the question it is supplied with.
                KLS - Add the skill(s) that are tested with each question. And For every question choose exactly {%s} skill(s) and not more or less than {%s} should be chosen for each question. The skills for all the questions should be unique and and focus exclusively on hard skills.
                Always use indian names in the role play, also mention what role the user will be playing while answering the questions in the description.
                Always use name in each question. The role play shall also have element of a other person who will be asking the questions.
                Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
                The Question, Custom Prompt, KLP, KLS should be numbered.
                Here the format looks like :
                "Title:",
                "Description:”,
                “Statement:",
                "Question 1:",
                "Prompt 1:",
                "Takeaway 1:" ,
                "Skills 1:" repeated for {%s} question(s). Do not include any {responder} response.
                'The Question, Prompt, Takeaway, Skills should be numbered.'

                NOTE: Description, questions, and skills should focus exclusively on hard skills.
                NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
                NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
                NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated. Each skill shall only be one word.
                NOTE: "Rating" must be included.
                NOTE: Make sure the roleplay is very advanced and tough.
                NOTE: Always use a name in each question. The role play shall also have the element of an other person who will be asking the questions.
                NOTE: Always mention in the context what role the user will be playing the role while answering.
                NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
                NOTE: Never miss Title, Description, Statement and other variables.

                \n\nAssistant:



      """
    elif scenario_type == 'dynamic_start_with_user':
      prompt = """
      \n\nHuman:
      {Information} - %s

      Read this {information} thoroughly. Now based on this information and your understanding create an advanced and detailed description for a conversation between a manager and a team member to practice the skills presented in the {information}. After creating the situation provide these:

      Description - Define the situation, and the problem. The problem should be a normal corporate problem. The description should always be about a conversation between the manager and a team member. Make the description specific based on data, industry, events, etc. Give the name of the manager. Never give the name of the team member. The description should just describe the problem and what was the specific situation that led to this problem. Keep the context Indian. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.  It should not be about writing an email.
      According to the description always end description with this approach and mention this : You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
      In every response, you must:
      Clearly state your role as X.
      Identify Y as the person asking
      Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.

      Prompts - As given in the output format.


      Here the format looks like :
      {
        "Title": "GIVE TITLE",
        "Context": "GIVE DESCRIPTION",
        "Candidate Type": based on information who will respond” ,
        "Scenario Case": "dynamic_discussion",
        "Email Address List": "mail@coachbots.com",
        "Certificate Title": "SAME AS TITLE",
        "Area/Domain": "BASED ON TITLE AND DESCRIPTION",
        "start with user": "based on information",
        "is_dynamic_thread": true,
        "Responder": "the second person name who will ask the questions",
        "Person 0": "the second person name who will ask the questions :",
        "0": "Please respond in order to continue.",
        "1": "Now the second person name who will ask the questions will respond to this remark as a Selfish type of person.",
        "2": "Please respond in order to continue.",
        "3": "Now the second person name who will ask the questions will respond to this remark as a Insincere type of person.",
        "4": "Conclude the discussion as a participant."
      }


      Do not include any response.
      Always provide the output in the given format.

      NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.

      NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - "Rating : 6". Do not include any other explanation.

      NOTE : Make sure the situation is very advanced and tough.

      NOTE : there must be only one manager in picture.

      NOTE : Never miss the Title, Description, Questions.
      NOTE: Do not mention "X" or "Y".

      \n\nAssistant:

      """

      return f"{prompt}"%(information)

    if scenario_type == 'normal_dynamic_test':
        prompt = '''
          \n\nHuman:
                        {Information} - (%s)

                        Read this {information} thoroughly. Now based on this information and your understanding create an advanced and detailed description for a conversation between a manager and a team member to practice the skills presented in the {information}. After creating the situation provide these:

                        Description - Define the situation, and the problem. The problem should be a normal corporate problem. The description should always be about a conversation between the manager and a team member. Make the description specific based on data, industry, events, etc. Give the name of the manager. Never give the name of the team member. The description should just describe the problem and what was the specific situation that led to this problem. Keep the context Indian. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.  It should not be about writing an email.
                        According to the description always end description with this approach and mention this : You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
                        In every response, you must:
                        Clearly state your role as X.
                        Identify Y as the person asking
                        Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
                        Questions - Give me the first question based on the situation in description .The question should be deep, thoughtful and realistic. Give the name of person asking the question. Keep it less than 35 words. NEVER provide a response to the question. Never start with any introduction sentences. Start with the question directly.
                        Output format - Y: question?
                        For example - Ajay: question?

                        Prompts - As given in the output format.

                        Here the format looks like :

                        Title:
                        Description:
                        Questions:
                        Prompts: - ["Please respond in order to continue.",
                        "Respond as {Y}",
                        ]


                        Note: Add in prompts set of above ["Please respond in order to continue.",
                        "Respond as {Y}",
                        ] for {%s} and at last add "Conclude the discussion as a participant."

                        Write the manager's name in place of {Y}. The Y should always be the same. Do not make any changes in the given format. .

                        Do not include any response.
                        Always provide the output in the given format.

                        NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.

                        NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - "Rating : 6". Do not include any other explanation.

                        NOTE : Make sure the situation is very advanced and tough.

                        NOTE : there must be only one manager in picture.

                        NOTE : Never miss the Title, Description, Questions.
                        NOTE: Do not mention "X" or "Y".

                        \n\nAssistant:


        '''

        return f"{prompt}"%(information,question_count*2-2)

    if scenario_type == 'normal_dynamic_test_hard':
        prompt = '''
          \n\nHuman:
                        {Information} - (%s)

                        Read this {information} thoroughly. Now based on this information and your understanding create an advanced and detailed description for a conversation between a manager and a team member to practice the skills presented in the {information}. After creating the situation provide these:

                        Description - Define the situation, and the problem focuses exclusively on hard skills. The problem should be a normal corporate problem. The description should always be about a conversation between the manager and a team member. Make the description specific based on data, industry, events, etc. Give the name of the manager. Never give the name of the team member. The description should just describe the problem and what was the specific situation that led to this problem. Keep the context Indian. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.  It should not be about writing an email.
                        According to the description always end description with this approach and mention this : You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
                        In every response, you must:
                        Clearly state your role as X.
                        Identify Y as the person asking
                        Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
                        Questions - Give me the first question based on the situation in description .The question should be deep, thoughtful and realistic. Give the name of person asking the question. Keep it less than 35 words. NEVER provide a response to the question. Question shall focus exclusively on hard skills. Never start with any introduction sentences. Start with the question directly.
                        KLS - With each question, add the skill(s) that are tested. And For every question choose exactly {8} skill(s) and not more or less than {8} should be chosen for each question. The skills for all the questions should be unique AND shall not repeat from (information). Each question shall have a unique skill AND shall not repeat from (information) and focus exclusively on hard skills. A comma seprated list of skills should be provided.
                        Output format - Y: question?
                        For example - Ajay: question?

                        Prompts - As given in the output format.

                        Here the format looks like :

                        Title:
                        Description:
                        Questions:
                        Skills:
                        Prompts: - ["Please respond in order to continue.",
                        "Respond as {Y}",
                        ]


                        Note: Add in prompts set of above ["Please respond in order to continue.",
                        "Respond as {Y}",
                        ] for {%s} and at last add "Conclude the discussion as a participant."

                        Write the manager's name in place of {Y}. The Y should always be the same. Do not make any changes in the given format. .

                        Do not include any response.
                        Always provide the output in the given format.
                        NOTE: Description, questions, and Skills should focus exclusively on hard skills.
                        NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.

                        NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - "Rating : 6". Do not include any other explanation.

                        NOTE : Make sure the situation is very advanced and tough.

                        NOTE : there must be only one manager in picture.

                        NOTE : Never miss the Title, Description, Questions, Skills.
                        NOTE: Do not mention "X" or "Y".

                        \n\nAssistant:


        '''

        return f"{prompt}"%(information,question_count*2-2)

    if scenario_type == 'normal_dynamic_test_soft':
        prompt = '''
                \n\nHuman:
                        {Information} - (%s)

                        Read this {information} thoroughly. Now based on this information and your understanding create an advanced and detailed description for a conversation between a manager and a team member to practice the skills presented in the {information}. After creating the situation provide these:

                        Description - Define the situation, and the problem focuses exclusively on soft skills. The problem should be a normal corporate problem. The description should always be about a conversation between the manager and a team member. Make the description specific based on data, industry, events, etc. Give the name of the manager. Never give the name of the team member. The description should just describe the problem and what was the specific situation that led to this problem. Keep the context Indian. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.  It should not be about writing an email.
                        According to the description always end description with this approach and mention this : You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
                        In every response, you must:
                        Clearly state your role as X.
                        Identify Y as the person asking
                        Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
                        Questions - Give me the first question based on the situation in description .The question should be deep, thoughtful and realistic. Give the name of person asking the question. Keep it less than 35 words. NEVER provide a response to the question. Question shall focus exclusively on soft skills. Never start with any introduction sentences. Start with the question directly.
                        KLS - With each question, add the skill(s) that are tested. And For every question choose exactly {8} skill(s) and not more or less than {8} should be chosen for each question. The skills for all the questions should be unique AND shall not repeat from (information). Each question shall have a unique skill AND shall not repeat from (information) and focus exclusively on soft skills. A comma seprated list of skills should be provided.
                        Output format - Y: question?
                        For example - Ajay: question?

                        Prompts - As given in the output format.

                        Here the format looks like :

                        Title:
                        Description:
                        Questions:
                        Skills:
                        Prompts: - ["Please respond in order to continue.",
                        "Respond as {Y}",
                        ]


                        Note: Add in prompts set of above ["Please respond in order to continue.",
                        "Respond as {Y}",
                        ] for {%s} and at last add "Conclude the discussion as a participant."

                        Write the manager's name in place of {Y}. The Y should always be the same. Do not make any changes in the given format. .

                        Do not include any response.
                        Always provide the output in the given format.
                        NOTE: Description, questions, and Skills should focus exclusively on soft skills.
                        NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.

                        NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - "Rating : 6". Do not include any other explanation.

                        NOTE : Make sure the situation is very advanced and tough.

                        NOTE : there must be only one manager in picture.

                        NOTE : Never miss the Title, Description, Questions, Skills.
                        NOTE: Do not mention "X" or "Y".

                        \n\nAssistant:


        '''

        return f"{prompt}"%(information,question_count*2-2)

    return f"{prompt}"%(information, question_count, skill_count, skill_count, question_count)

# only game scenario type (dynamic)
def get_game_prompt(industry, information, num_of_questions, question_type, candidate_type):
  prompt = '''
    Create a large "${Industry}" corporate scenario is less than 100 words with a title upto 8-12 words that related to : (${information}).

    Further create ${num_of_questions} MCQ questions with 4 options each that are related to the paragraph that the user must answer as a new manager tasked with solving the issue at hand.
    The Questions must have 4 options and will have ${question_type} right answer - however they should not be straightforward and it may appear other choices are right as well.
    Always end the description with As a ${candidate_type} select the right option for the questions presented below.

    GIVE IN THIS VALID JSON FORMAT:
    json ```
    {
      "title": "title goes here",
      "description": "decrtiption title goes here",
      "is_single_select": "TRUE or FALSE",
      "questions" :[
        {
          ""context"": {
            ""section"": ""Section Text""
          },
          ""details"": {
            ""question"": ""Question Text""
          },
          ""content"": {
            ""instruction"": ""Choose one or more options from A, B, C or D"",
            ""options"": {

                ""A"": ""Option A"",
                ""B"": ""Option B"",
                ""C"": ""Option C"",
                ""D"": ""Option D""

            }
          }
        },
      ],
    }
    ```

    (If the prompt mentions "single," then the value of "is_single_select" should be "TRUE" instead.)
    (If the prompt mentions "multiple," then the value of "is_single_select" should be "FALSE" instead.)
    NOTE: All keys required in output format.

    '''

  return Template(prompt).substitute(Industry=industry, information=information, num_of_questions=num_of_questions, question_type=question_type, candidate_type=candidate_type)

def format_game_custom_prompt(is_single_select, questions, title, description, num_of_questions=None, static=True):
  instruction = "Choose one option from A, B, C or D" if is_single_select else "Choose one or more options from A, B, C or D"
  if static:
    questions = "\n\n".join([str(i) for i in questions])
    custom_prompt = """
    **Prompt Guidelines:**

    1. **Display the End Game Message**: Ensure the final message appears as specified, substituting 'x' with the player's total score and replacing '[Game Name]' with the actual game title:
      - Congratulations 🎉. You have completed the [Game Name]. You have achieved a score of [x out of 100].

    2. **No clipping or trucation of text**: Ensure that each option is presented in its entirety, without any clipping or truncation of text. Do not hallucinate or invent options; present only the options exactly as provided in the game design.

    3. **Demand Correct Input for Progression**: Require players to input a valid choice precisely to advance to subsequent levels. Repeat the prompt until a correct input is received.

    4. **Display the Feedback**: Upon game completion, provide approximately 50 words of feedback summarizing the impact of the user's choices on the outcome. Briefly suggest alternative strategies for potentially improved results in future playthroughs.

    5. **Always Present Full Level Details**: Consistently show all levels and options exactly as scripted. Complete all levels and only give feedback as last. Every level and option must be displayed in full, without omission or partial rendering of any text.

    6. **Start with Level Prompt**: When the command """"START"""" is given, begin immediately with the first level.

    7. **Output in JSON format**:  Ensure that the game’s output is formatted as valid JSON. Below is the structure:
    json
    if game not ended:
      ``` json
      {
        ""context"": {
          ""section"": ""Section Text""
        },
        ""details"": {
          ""question"": ""Question Text""
        },
        ""content"": {
          ""instruction"": ""${instruction}"",
          ""options"": {

              ""A"": ""Option A"",
              ""B"": ""Option B"",
              ""C"": ""Option C"",
              ""D"": ""Option D""

          }
        }
      }
    ```
    if game ended:
    json
    {
    ""end_message"" : ""[End Game Message]"",
    ""feedback"": ""[Feedback Text]""
    }


    Let's continue with the game using these guidelines.

    ---
    ## Title:
    ${title}

    ## Overview & Gameplay Objectives:
    ${description}

    ---
    if game not ended:
    Ensure that the game’s output is formatted as valid JSON. Below is the structure:
    json
    if game not ended:
    ```json
    ${questions}
    ```
    ---

    ## End Game Message:
    Congratulations 🎉. You have completed the [Game Name]. You have achieved a score of [x out of 100].

    ## Feedback:
    Provide 50 words of feedback regarding the answers of the options chosen by the user, and suggest if they could have done anything better."
    """

    return Template(custom_prompt).substitute(instruction=instruction,questions=questions,title=title,description=description)
  else:
    custom_prompt = """
    **Prompt Guidelines:**

    1. **Display the End Game Message**: Ensure the final message appears as specified, substituting 'x' with the player's total score and replacing '[Game Name]' with the actual game title:
      - Congratulations 🎉. You have completed the [Game Name]. You have achieved a score of [x out of 100].

    2. **No clipping or trucation of text**: Ensure that each option is presented in its entirety, without any clipping or truncation of text. Do not hallucinate or invent options; present only the options exactly as provided in the game design.

    3. **Demand Correct Input for Progression**: Require players to input a valid choice precisely to advance to subsequent levels. Repeat the prompt until a correct input is received.

    4. **Display the Feedback**: Upon game completion, provide approximately 50 words of feedback summarizing the impact of the user's choices on the outcome. Briefly suggest alternative strategies for potentially improved results in future playthroughs.

    5. **Always Present Full Level Details**: Consistently show all levels and options exactly as scripted. Complete all levels and only give feedback as last. Every level and option must be displayed in full, without omission or partial rendering of any text.

    6. **Start with Level Prompt**: When the command """"START"""" is given, begin immediately with the first level.

    7. **Output in JSON format**:  Ensure that the game’s output is formatted as valid JSON. Below is the structure:
    json
    if game not ended:
      ``` json
    {
        ""context"": {
          ""section"": ""Section Text""
        },
        ""details"": {
          ""question"": ""Question Text""
        },
        ""content"": {
          ""instruction"": ""${instruction}"",
          ""options"": {

              ""A"": ""Option A"",
              ""B"": ""Option B"",
              ""C"": ""Option C"",
              ""D"": ""Option D""

          }questions
        }
      }
    ```
    if game ended:
    json
    {
    ""end_message"" : ""[End Game Message]"",
    ""feedback"": ""[Feedback Text]""
    }

    8. **Craft Challenging Decision Options**: Offer related and nuanced options prompting strategic contemplation for informed decision-making.

    9. **Total Number of Levels** = ${number_of_level}

    Let's continue with the game using these guidelines.

    ---

    "## Title:
    ""${title}""
    ## Overview & Gameplay Objectives:
    ${description}
    ---
    if game not ended:
    Ensure that the game’s output is formatted as valid JSON. Below is the structure:
    json
    if game not ended:
      ```json
    {
        ""context"": {
          ""section"": ""Section Text""
        },
        ""details"": {
          ""question"": ""Question Text""
        },
        ""content"": {
          ""instruction"": ""${instruction}"",
          ""options"": {

              ""A"": ""Option A"",
              ""B"": ""Option B"",
              ""C"": ""Option C"",
              ""D"": ""Option D""

          }
        }
      }
```
    ---

    ## End Game Message:
    Congratulations 🎉. You have completed the [Game Name]. You have achieved a score of [x out of 100].

    ## Feedback:
    Provide 50 words of feedback regarding the answers of the options chosen by the user, and suggest if they could have done anything better.


        """

    return Template(custom_prompt).substitute(instruction=instruction,title=title,description=description,number_of_level=num_of_questions)

# ----game scenario ends----

# ------------Extractors ---------

def extract_text_only(input_text):
    # Remove digits from the text
    text_without_digits = re.sub(r'\d', '', input_text)

    # Remove extra whitespaces
    cleaned_text = ' '.join([st.replace("-","").strip().capitalize()  for st in text_without_digits.replace("."," ").strip().split()])
    return cleaned_text

# for static scenarios
def extract_information(text):
    """
    Extract information from a given text containing details about a scenario.

    Parameters:
    - text (str): The text containing information about a scenario.

    Returns:
    - tuple: A tuple containing title, description, question_info, skill_to_evaluate, and rating.

    Example:
    >>> extract_information('Title: Test\nDescription: Test Description\nQuestion: What is your approach to leadership?\nPrompt: Provide your leadership style.\nTakeaway: Effective communication is key.\nSkills: Communication, Leadership\nRating: 5')
    # Returns a tuple with extracted information from the scenario text.
    """
    # Regular expressions for extracting title, description, questions, prompts, takeaways, and skills
    text = text.replace("KLS", "Skills")
    text = text.replace("KLP", "Takeaway")
    text = text.replace("Custom prompt", "Prompt")

    title_pattern = re.compile(r'Title\s*:\s*(.+)')
    description_pattern = re.compile(r'Description\s*:\s*(.+)')
    statement_pattern = re.compile(r'Statement\s*:\s*(.+)')
    question_pattern = re.compile(r'Question\s*(\d*)\s*:\s*(.+)')
    prompt_pattern = re.compile(r'Prompt\s*(\d*)\s*:\s*(.+)')
    takeaway_pattern = re.compile(r'Takeaway\s*(\d*)\s*:\s*(.+)')
    skills_pattern = re.compile(r'Skills\s*(\d*)\s*:\s*(.+)')
    rating_pattern = re.compile(r'Rating\s*:\s*(\d+)')

    # Extracting information using regular expressions
    title_match = title_pattern.search(text)
    description_match = description_pattern.search(text)
    rating_match = rating_pattern.search(text)
    statement_match = statement_pattern.search(text)

    # If title_pattern doesn't match, try to find the title as the lines before the description
    if not title_match:
        pattern = re.compile(r'^(?:Title\s*:\s*)?(?:"(.*?)"|([^"\n]*))\n*Description\s*:')
        title_match = pattern.search(text)
        if not title_match:
            raise ValueError("Invalid format. Unable to extract the title.")


    if not (title_match and description_match and  question_pattern.findall(text) and prompt_pattern.findall(text) and takeaway_pattern.findall(text) and skills_pattern.findall(text)):
        invalid_fields = []

        if not title_match:
            invalid_fields.append("title")
        if not description_match:
            invalid_fields.append("description")
        if not question_pattern.findall(text):
            invalid_fields.append("question pattern")
        if not prompt_pattern.findall(text):
            invalid_fields.append("prompt pattern")
        if not takeaway_pattern.findall(text):
            invalid_fields.append("takeaway pattern")
        if not skills_pattern.findall(text):
            invalid_fields.append("skills pattern")

        raise ValueError(f"Invalid format. Unable to extract necessary information. Invalid fields: {', '.join(invalid_fields)}")

    title = title_match.group(1)
    description = f"{description_match.group(1)} {statement_match.group(1)}" if statement_match else description_match.group(1)
    rating = int(rating_match.group(1)) if rating_match else 0

    questions = []
    for match in question_pattern.finditer(text):
        question_number = match.group(1) if match.group(1) else len(questions) + 1
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

    informations = {
        'title': title,
        'description': description,
        'questions': questions
    }

    title = informations['title']
    description = informations['description']

    question_info = []
    skill_to_evaluate = set()
    for que in informations['questions']:
        question_info.append({
            "question": que["text"],
            "question_type": "subjective",
            "gpt_prompt_override": que["prompt"].replace("{","").replace("}",""),
            "subjective_answer": "",
            "key_learning_point": extract_text_only(que['takeaway']),
            "key_learning_skills": extract_text_only(que['skills'])
        })

        for skill in que['skills'].split(','):
            skill_to_evaluate.add(extract_text_only(skill.strip().capitalize()))

    if len(skill_to_evaluate) < 6:
        raise ValueError(f"Skills must have at least 6. Got:  {len(skill_to_evaluate)}, {skill_to_evaluate}")
    
    if len(skill_to_evaluate) > 8:
        skill_to_evaluate = list(skill_to_evaluate)[:8]

    skill_to_evaluate = ', '.join(skill_to_evaluate)

    informations['skill_to_evaluate'] = skill_to_evaluate

    return title, description, question_info, skill_to_evaluate, rating, informations


# for dynamic scenarios
def extract_information_dynamic_scenario(text,candidate_type="Manager",num_questions=3, start_with_user=None):
    """
    Extract information from a dynamic scenario text.

    Parameters:

    - text (str): The dynamic scenario text to extract information from.

    - is_dynamic (bool): Indicates whether the scenario is dynamic.

    - candidate_type (str): Type of candidate (e.g., 'Manager', 'Team Member').

    Returns:

    - tuple: A tuple containing title, description, question_info, rating, evaluation_skill_list, and orchestrated_conversation_details.
    Example:

    >>> extract_information_dynamic_scenario('Title: Test Title\nDescription: Test Description\nQuestion: What is your approach to leadership?\nRating: 5', is_dynamic=True, candidate_type='Manager')

    # Returns a tuple with extracted information from the dynamic scenario text.
    """

    if not text:
        raise ValueError("Invalid format. Text is empty.")

    try:

      data = extract_json_from_string(text)
      manager_name = data['Person 0'].split(':')[0].strip()
      question_info = []
      title = data['Title']
      description = data['Context']

      for key, value in data.items():
        if key.isdigit():
          
          question_info.append({
            "question": value,
            "question_type": "subjective",
            "gpt_prompt_override": "",
            "subjective_answer": "",
            'question_for': manager_name if manager_name.strip().lower() in value.strip().lower() else 'user'
          })

      test_main_context = description + data['Person 0']

      orchestrated_conversation_details = {
            "test_main_context": test_main_context,
            "test_user_persona": data['Candidate Type'].capitalize(),
            "objective": description,
            "initial_messages": [data['Person 0']],
            "responder_name": data.get('Responder')

        }
      if start_with_user:
            orchestrated_conversation_details['start_with_user'] = start_with_user

      infomation = {
        'title': title,
        'description': description,
        'question_info': question_info,
        "candidate_type": data['Candidate Type'].capitalize(),
        'area_domain': data['Area/Domain'],
        'certificate_title': data['Certificate Title'],
        'email_list': data['Email Address List'],
        'orchestrated_conversation_details': orchestrated_conversation_details
      }
      if data.get('start with user') != "None":
        infomation['start_with_user'] = data['start with user']

      evaluation_skill_list = data.get('skill_list')
      if not evaluation_skill_list:
        skills_list_candidate = set()

        for item in get_skills(candidate_type.capitalize()):

                skills_list_candidate.add(item.capitalize())



        evaluation_skill_list = [skill.strip() for skill in sorted(skills_list_candidate)]



        if len(evaluation_skill_list) < 6:

            raise ValueError(f"Skills must have at least 4. Got:  {len(skills_list_candidate)}, {skills_list_candidate}")



        if len(evaluation_skill_list) > 8:

            evaluation_skill_list = evaluation_skill_list[:8]



        evaluation_skill_list = ','.join(evaluation_skill_list)

        infomation['skills_list'] = evaluation_skill_list

      logger.info(f'scenario info============================: {infomation}')


      return title, description, question_info, 10, evaluation_skill_list, orchestrated_conversation_details, infomation

    except Exception as e:
      print(e)

    text = text.replace('KLS', 'Skills')

    title_pattern = re.compile(r'Title\s*:\s*(.*?)\n', re.DOTALL)

    description_pattern = re.compile(r'Description\s*:\s*(.*?)\n', re.DOTALL)

    question_pattern = re.compile(r'Question\s*:\s*(.+)')

    skill_pattern = re.compile(r'Skills:\s*(.+)')

    rating_pattern = re.compile(r'Rating\s*:\s*(\d+)')

    if not question_pattern.findall(text):

        question_pattern = re.compile(r'Questions\s*:\s*(.+)')



    # Extracting information using regular expressions

    title_match = title_pattern.search(text)

    description_match = description_pattern.search(text)

    questions_match = question_pattern.search(text)

    rating_match = rating_pattern.search(text)
    skill_match = skill_pattern.search(text)



    # If title_pattern doesn't match, try to find the title as the lines before the description

    if not title_match:

        pattern = re.compile(r'^(?:Title\s*:\s*)?(?:"(.*?)"|([^"\n]*))\n*Description\s*:')

        title_match = pattern.search(text)

        if not title_match:

            raise ValueError("Invalid format. Unable to extract the title.")





    if not (title_match and description_match and question_pattern.findall(text)):

        raise ValueError("Invalid format. Unable to extract necessary information.")




    title = title_match.group(1).strip()

    description = description_match.group(1).strip()

    questions = questions_match.group(1).strip()

    rating = int(rating_match.group(1)) if rating_match else 0

    skill_list = skill_match.group(1).strip().split(',') if skill_match else None

    question_info = []



    test_main_context = description + questions

    orchestrated_conversation_details = {

            "test_main_context": test_main_context,

            "test_user_persona": candidate_type.capitalize(),

            "objective": description,

            "initial_messages": [questions],

            "responder_name":questions.split(':')[0].strip()


        }

    if start_with_user:
        orchestrated_conversation_details['start_with_user'] = start_with_user


    evaluation_skill_list = skill_list

    if not evaluation_skill_list:
        skills_list_candidate = set()

        for item in get_skills(candidate_type.capitalize()):

                skills_list_candidate.add(item.capitalize())



        evaluation_skill_list = [skill.strip() for skill in sorted(skills_list_candidate)]



    if len(evaluation_skill_list) < 6:

        raise ValueError(f"Skills must have at least 4. Got:  {len(skills_list_candidate)}, {skills_list_candidate}")



    if len(evaluation_skill_list) > 8:

        evaluation_skill_list = evaluation_skill_list[:8]



    evaluation_skill_list = ','.join(evaluation_skill_list)



    manager_name = questions.split(':')[0].strip()

    for i in range(1,2*num_questions):

        question = {

                "question_type": "subjective",

                "gpt_prompt_override": "",

                "subjective_answer": ""

            }



        if i % 2 == 0:

            question['question'] = f"Respond as {manager_name}"

            question['question_for'] = manager_name

        else:

            question['question'] = "Please respond in order to continue"

            question['question_for'] = 'user'



        if i == (2*num_questions-1):

            question['question'] = "Conclude the discussion as a participant."



        question_info.append(question)



    infomation = {
        'title': title,
        'description': description,
        'question_info': question_info,
        'skill_to_evaluate': evaluation_skill_list,
        'orchestrated_conversation_details': orchestrated_conversation_details,
        'candidate_type': candidate_type,
        'certificate_title': title,
        'responder': manager_name,
    }

    logger.info(f'scenario info============================: {infomation}')

    return title, description, question_info, rating, evaluation_skill_list,orchestrated_conversation_details, infomation

# for game type (dyanmic)
def extract_game_type(text,case_type, question_count=10, candidate_type='Manager'):
  data = extract_json_from_string(text)
  if not data:
    raise ValueError("Invalid format. Unable to extract necessary information.")
  information = {
      "title": data['title'],
      "description": data['description'],
      "game_questions": data['questions'],
      "is_single_select": data['is_single_select'].strip().lower() == 'true',
      "email_list": "mail@coachbots.com",
      "custom_prompt": format_game_custom_prompt(is_single_select=data.get('is_single_select'),
                                                questions=data.get('questions'),
                                                title=data.get('title'),
                                                description=data.get('description'),
                                                num_of_questions=question_count,
                                                static= True if case_type == 'static_game' else False
                                            )
  }

  orchestrated_conversation_details = {
            "test_main_context": information.get('description'),
            "test_user_persona": candidate_type,
            "objective": information.get('description'),
            "initial_messages": [],
            "responder_name": ""

        }
  logger.info(f'scenario info============================: {information}')

  return data['title'], data['description'], [],10,"communication skill",orchestrated_conversation_details,information

# helpers
def scrape_meta_info(url):
    """
    Scrape meta information (title and description) from a given URL.

    Parameters:
    - url (str): The URL to scrape meta information from.

    Returns:
    - tuple: A tuple containing the title and description extracted from the meta tags.
             If an error occurs, the tuple contains an error message.

    Example:
    >>> scrape_meta_info('https://example.com')
    # Returns a tuple with the title and description extracted from the meta tags of the given URL.
    """
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

def get_prompt_for_feedback_bot(site_information):
    prompt = """
                \n\nHuman:
                 {Information} - %s

                Read this {information} thoroughly. Now based on this information and your understanding create an advanced and tough simulation situation to practice the skills presented in the {information}. The situation should be extremely relevant to the information provided. The simulation should ask questions from the user. For example if the user is a team member the questions should be asked from the team member, and if the user is a manager the questions should be asked from the manager. Understand the context clearly and then create the situation. After creating the situation provide these:

                Description - Define the situation, and the problem. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on based on data, industry, events, etc. The description should just describe the problem and what was the specific situation that led to this problem. No dialogues should be included. Keep the context Indian. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.

                Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description. 

                Questions - Develop a set of {3} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions. All the questions should be asked to the same person. If the situation is for team member only ask the questions from the team member.

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

                NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.

                NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.

                NOTE : Make sure the simulation is very advanced and tough.

                \n\nAssistant:
            """%(site_information)
        
    return prompt

def get_one_scenario_prompt(site_information,prompt_type, num_questions=3, case='default'):
    prompt = ''
    if prompt_type == TestTypeChoices.dynamic_discussion_thread:
        prompt = """
                        \n\nHuman:
                        {Information} - %s

                        Read this {information} thoroughly. Now based on this information and your understanding create an advanced and detailed description for a conversation between a manager and a team member to practice the skills presented in the {information}. After creating the situation provide these:

                        Description - Define the situation, and the problem. The problem should be a normal corporate problem. The description should always be about a conversation between the manager and a team member. Make the description specific based on data, industry, events, etc. Give the name of the manager. Never give the name of the team member. The description should just describe the problem and what was the specific situation that led to this problem. Keep the context Indian. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.  It should not be about writing an email.
                        Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description. 
                        Questions - Give me the first question the manager will ask the team member based on the situation .The question should be deep, thoughtful and realistic. Give the name of person asking the question. Keep it less than 35 words. NEVER provide a response to the question. Never start with any introduction sentences. Start with the question directly. 
                        Output format - Manager name: Question
                        For example - Ajay: question?
                        Prompts - As given in the output format. 

                        Here the format looks like :

                        "Title:",

                        "Description:",

                        "Questions:",

                        "Prompts:" - ["Please respond in order to continue." 
                        "Respond as {Manager name}", 
                        "Please respond in order to continue." 
                        "Respond as {Manager name}", 
                        "Please respond in order to continue." 
                        "Respond as {Manager name}", 
                        "Please respond in order to continue." 
                        "Respond as {Manager name}", 
                        "Please respond in order to continue." 
                        "Respond as {Manager name}"
                        "Conclude the discussion as a participant."]

                        Write the manager's name in place of {Manager name}. The Manager name should always be the same. Do not make any changes in the given format. . 

                        Do not include any response.
                        Always provide the output in the given format. 

                        NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.

                        NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - "Rating : 6". Do not include any other explanation.
                        
                        NOTE : Make sure the situation is very advanced and tough.

                        NOTE : there must be only one manager in picture.

                        NOTE : Never miss the Title, Description, Questions.

                        \n\nAssistant: 

                    """%(site_information)  
    else:
        if case == 'normal':
            prompt = """
            \n\nHuman:
            {Information} -
            %s -
            Read this {information} thoroughly. Now based on this information and your understanding create an advanced and tough simulation situation to practice the skills presented in the {information}. After creating the situation provide these:
            Description - Define the situation, and the problem. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on based on data, industry, events, etc. The description should just describe the problem and what was the specific situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.
            Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
            Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.
            Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide a feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
            KLP - With each question add one or two line takeaway for providing feedback. The takeaways should be related to the question it is provided with.
            KLS - With each question, add the skill(s) that are tested. And For every question choose exactly {2} skill(s) and not more or less than {2} should be chosen for each question. The skills for all the questions should be unique. Each question shall have a unique skill.
            Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
            In every response, you must:
            Clearly state your role as X.
            Identify Y as the person asking
            The Question, Custom Prompt, KLP, KLS should be numbered.
            Here the format looks like :
            "Title",
            "Description”,
            “Statement",
            "Question 1",
            "Prompt 1",
            "Takeaway 1" ,
            "Skills 1" repeated for {%s} question(s). Do not include any {responder} response.
            'The Question, Prompt, Takeaway, Skills should be numbered.'
            NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
            NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
            NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated. Each skill shall only be one word.
            NOTE: "Rating" must be included.
            NOTE : Make sure the simulation is very advanced and tough.
            NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
            NOTE: Never miss Title, Description, Statement and other variables.
            \n\nAssistant:

            """
        elif case == 'role_play':
            prompt= """
                \n\nHuman:
                {Information} - %s-
                Read this {information} thoroughly. Based on this information and your understanding create an advanced and tough roleplay situation to practice the skills presented in the {information}. After making the situation provide these:
                Description - Define the situation and the problem. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on data, industry, events, etc. The description should describe the problem and what was the particular situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third-person point of view. Describe 100 to 200 words. Do not add any conclusion.
                Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
                Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the problem. NEVER respond to the questions.
                Custom prompt - With each question, add a prompt asking for feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
                KLP - With each question add one or two line takeaways for providing feedback. The takeaways should be related to the question it is supplied with.
                KLS - Add the skill(s) that are tested with each question. And For every question choose exactly {2} skill(s) and not more or less than {2} should be chosen for each question. The skills for all the questions should be unique.
                Always use indian names in the role play, also mention what role the user will be playing while answering the questions in the description.
                Always use name in each question. The role play shall also have element of a other person who will be asking the questions.
                Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
                The Question, Custom Prompt, KLP, KLS should be numbered.
                Here the format looks like :
                "Title",
                "Description",
                “Statement",
                "Question 1",
                "Prompt 1",
                "Takeaway 1" ,
                "Skills 1" repeated for {%s} question(s). Do not include any {responder} response.
                'The Question, Prompt, Takeaway, Skills should be numbered.'
                NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
                NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
                NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated. Each skill shall only be one word.
                NOTE: "Rating" must be included.
                NOTE: Make sure the roleplay is very advanced and tough.
                NOTE: Always use a name in each question. The role play shall also have the element of an other person who will be asking the questions.
                NOTE: Always mention in the context what role the user will be playing the role while answering.
                NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
                NOTE: Never miss Title, Description, Statement and other variables.
                
                \n\nAssistant:
                """
        elif case == "case":
            prompt = """
             \n\nHuman:
            {Information} - %s
            Read this {information} thoroughly. Now based on this information and your understanding create an advanced and tough simulation situation to practice the skills presented in the {information}. After creating the situation provide these:
            Description - Define the situation, and the problem. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on based on data, industry, events, etc. The description should just describe the problem and what was the specific situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.
            Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
            Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.
            Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide a feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
            KLP - With each question add one or two line takeaway for providing feedback. The takeaways should be related to the question it is provided with.
            KLS - With each question, add the skill(s) that are tested. And For every question choose exactly {2} skill(s) and not more or less than {2} should be chosen for each question. The skills for all the questions should be unique.
            Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
            Always Use a literary genre to generate the response in high literature.
            Literary genres encompass a wide spectrum of styles and themes, ranging from the imaginative realms of fiction, poetry, drama, and fantasy to the factual landscapes of non-fiction, biography, and autobiography. Mystery, science fiction, romance, historical fiction, and horror delve into specific narrative territories, while thriller, adventure, satire, comedy, tragedy, and epic offer diverse storytelling approaches. Additionally, fables, fairy tales, mythology, and folklore explore cultural narratives and traditions. Genres like dystopian, gothic, bildungsroman (coming-of-age), absurdist, and magical realism push the boundaries of conventional storytelling, while realistic fiction and experimental literature offer unique perspectives on reality and form. Each genre contributes to the rich tapestry of literary expression, offering readers a multitude of worlds and experiences to explore.
            In every response, you must:
            Clearly state your role as X.
            Identify Y as the person asking
            The Question, Custom Prompt, KLP, KLS should be numbered.
            Here the format looks like :
            "Title",
            "Description”,
            “Statement",
            "Question 1",
            "Prompt 1",
            "Takeaway 1" ,
            "Skills 1" repeated for {%s} question(s). Do not include any {responder} response.
            'The Question, Prompt, Takeaway, Skills should be numbered.'
            NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
            NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
            NOTE: "Rating" must be included.
            NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated. Each skill shall only be one word.
            NOTE : Make sure the simulation is very advanced and tough.
            NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
            NOTE: Always use suitable literary genre to genre create the response.
            NOTE: Never miss Title, Description, Statement and other variables.
            \n\nAssistant:
            """

        elif case == "interview":
            prompt = """
            \n\nHuman:
            {Information} - %s 
            Read this {information} thoroughly. Now based on this information and your understanding create an advanced and tough simulation situation to practice the skills presented in the {information}. After creating the situation provide these:
            Description - Define the situation, and the problem. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on based on data, industry, events, etc. The description should just describe the problem and what was the specific situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.
            Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
            Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.
            Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide a feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
            KLP - With each question add one or two line takeaway for providing feedback. The takeaways should be related to the question it is provided with.
            KLS - With each question, add the skill(s) that are tested. And For every question choose exactly {2} skill(s) and not more or less than {2} should be chosen for each question. The skills for all the questions should be unique.
            Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
            Always use a interview to generate the response for communication and information gathering.
            An interview is a formal conversation between an interviewer and an interviewee, typically in a professional setting, to assess the interviewee's suitability for a particular role or to gather information. It is a common practice in the corporate world and other professional settings, where employers or hiring managers conduct interviews to evaluate potential candidates for employment.
            In every response, you must:
            Clearly state your role as X.
            Identify Y as the person asking
            The Question, Custom Prompt, KLP, KLS should be numbered.
            Here the format looks like :
            "Title",
            "Description”,
            “Statement",
            "Question 1",
            "Prompt 1",
            "Takeaway 1" ,
            "Skills 1" repeated for {%s} question(s). Do not include any {responder} response.
            'The Question, Prompt, Takeaway, Skills should be numbered.'
            NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
            NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
            NOTE: "Rating" must be included.
            NOTE : Make sure the simulation is very advanced and tough.
            NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated. Each skill shall only be one word.
            NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
            NOTE: Always use interview for communication and information gathering.
            NOTE: Never miss Title, Description, Statement and other variables.
            \n\nAssistant:
            """
        elif case == 'checkin':
            prompt = """
                \n\nHuman:
                {Information} - %s
                Read this {information} thoroughly. Now based on this information and your understanding create an advanced and tough simulation situation to practice the skills presented in the {information}. After creating the situation provide these:
                Description - Define the situation, and the problem. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on based on data, industry, events, etc. The description should just describe the problem and what was the specific situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.
                Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description related to the check-in.
                Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.
                Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide a feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
                KLP - With each question add one or two line takeaway for providing feedback. The takeaways should be related to the question it is provided with.
                KLS - With each question, add the skill(s) that are tested. And For every question choose exactly {2} skill(s) and not more or less than {2} should be chosen for each question. The skills for all the questions should be unique.
                Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
                Always use a check-in to generate the response for communication and information gathering.
                Check-in in a corporate setting refers to the process of employees or participants recording their arrival at the workplace, a meeting, a conference, or any other professional gathering. This practice allows for improved attendance tracking, resource allocation, and streamlined communication within the enterprise.
                In every response, you must:
                Clearly state your role as X.
                Identify Y as the person asking
                The Question, Custom Prompt, KLP, KLS should be numbered.
                Here the format looks like :
                "Title",
                "Description”,
                “Statement",
                "Question 1",
                "Prompt 1",
                "Takeaway 1" ,
                "Skills 1" repeated for {%s} question(s). Do not include any {responder} response.
                'The Question, Prompt, Takeaway, Skills should be numbered.'
                NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
                NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable like an check-in.
                . Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
                NOTE: "Rating" must be included.
                NOTE : Make sure the simulation is very advanced and tough.
                NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
                NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated. Each skill shall only be one word.
                NOTE: Always use check-in for communication and information gathering.
                NOTE: Never miss Title, Description, Statement and other variables.

                \n\nAssistant:

                """
        else:

            prompt = """
            \n\nHuman:
            {Information} -
            %s -
            Read this {information} thoroughly. Now based on this information and your understanding create an advanced and tough simulation situation to practice the skills presented in the {information}. After creating the situation provide these:
            Description - Define the situation, and the problem. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on based on data, industry, events, etc. The description should just describe the problem and what was the specific situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.
            Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
            Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.
            Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide a feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
            KLP - With each question add one or two line takeaway for providing feedback. The takeaways should be related to the question it is provided with.
            KLS - With each question, add the skill(s) that are tested. And For every question choose exactly {2} skill(s) and not more or less than {2} should be chosen for each question. The skills for all the questions should be unique. Each question shall have a unique skill.
            Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
            In every response, you must:
            Clearly state your role as X.
            Identify Y as the person asking
            The Question, Custom Prompt, KLP, KLS should be numbered.
            Here the format looks like :
            "Title",
            "Description”,
            “Statement",
            "Question 1",
            "Prompt 1",
            "Takeaway 1" ,
            "Skills 1" repeated for {%s} question(s). Do not include any {responder} response.
            'The Question, Prompt, Takeaway, Skills should be numbered.'
            NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
            NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
            NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated. Each skill shall only be one word.
            NOTE: "Rating" must be included.
            NOTE : Make sure the simulation is very advanced and tough.
            NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
            NOTE: Never miss Title, Description, Statement and other variables.
            \n\nAssistant:
            """

            # prompt = """
            #     \n\nHuman:
            #         {Information} - %s

            #     Read this {information} thoroughly. Now based on this information and your understanding create  an advanced and tough simulation situation to practice the skills presented in the {information}. After creating the situation provide these:

            #     Description - Define the situation, and the problem. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on based on data, industry, events, etc. The description should just describe the problem and what was the specific situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.
            #     Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description. 
            #     Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.
            #     Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide a feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
            #     KLP - With each question add one or two line takeaway for providing feedback. The takeaways should be related to the question it is provided with.
            #     KLS - With each question, add the skill(s) that are tested. And For every question choose exactly {2} skill(s) and not more or less than {2} should be chosen for each question. The skills for all the questions should be unique.
            #     The Question, Custom Prompt, KLP, KLS should be numbered.

            #     Here the format looks like :

            #     "Title",

            #     "Description",

            #     "Question 1",

            #     "Prompt 1",

            #     "Takeaway 1" ,

            #     "Skills 1" repeated for {%s} question(s). Do not include any {responder} response.

            #     'The Question, Prompt, Takeaway, Skills should be numbered.'


            #     NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
                
            #     NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
                
            #     NOTE: "Rating" must be included.
                
            #     NOTE : Make sure the simulation is very advanced and tough.
                
            #     \n\nAssistant:
            # """  

        prompt = f"{prompt}"%(site_information, num_questions, num_questions) 
        
    logger.info({"prompt": prompt})

    return prompt
        
def get_report_using_session(session_id, type_of_test):
    test_attempt_session = TestAttemptSession.objects.get(uid=session_id)

    if type_of_test == TestTypeChoices.dynamic_discussion_thread:
        data = get_meeting_report_from_test_attempt_session(
                test_attempt_session)
    else:
        data = get_report_from_test_attempt_session(
                test_attempt_session, only_data=True)


    

    if type_of_test == TestTypeChoices.dynamic_discussion_thread:
      r ={
      'Title': data['title'],
      'description': data['test_description'],
      'objective': data['objective'],

      'question And Answer': data['chat_conversation'],
      'skills_graph_data': data['skills_rating'],
      'skills_explanation': data['skills_explanation'],
      'feedback_summary': data['feedback_summary'],
      'skill_summary': data['skill_summary'],
      'culture_graph_data': data['culture_skills'],
      'culture_skills_explanation': data['culture_skills_explanation'],
      'competency_data': data['competency_data']
    }
    else:
        r = {
      'Title': data['title'],
      'description': data['test_description'],
      'question And Answer': data['qa'],
      'skills_graph_data': data['skills_graph_data'],
      'skills_explanation': data['skills_explanation'],
      'feedback_summary': data['feedback_summary'],
      'skill_summary': data['skill_summary'],
      'culture_graph_data': data['culture_graph_data'],
      'culture_skills_explanation': data['culture_skills_explanation'],
      'competency_data': data['competency_data']
    }

    result = ''
    for key, value in r.items():
        result += f"{key}: {value}\n\n"

    return result

def get_test_info_by_session_id(session_id):
    data = ""
    session = TestAttemptSession.objects.filter(deleted=False, uid=session_id).first()
    if session:
        test = Test.objects.filter(deleted=False, uid=session.test_id).first()
        if test:
            data = f'''
            Title: {test.title}
            Description: {test.description}
            SKILLS: [{test.skills_to_evaluate}]
            '''

    return data

        
def get_scenario_creation_report_prompt(prompt_type, session_id, num_questions=3,case='default'):
    prompt = ''
    # report_data = get_report_using_session(session_id,prompt_type)
    report_data = get_test_info_by_session_id(session_id=session_id)

    if prompt_type == TestTypeChoices.dynamic_discussion_thread:
        prompt = """
                        \n\nHuman:
                        {Information} - ${information}

                        Read this {information} thoroughly. Now based on this information and your understanding create an advanced and detailed description for a conversation between a manager and a team member to practice the skills presented in the {information}. After creating the situation provide these:

                        Description - Define the situation, and the problem. The problem should be a normal corporate problem. The description should always be about a conversation between the manager and a team member. Make the description specific based on data, industry, events, etc. Give the name of the manager. Never give the name of the team member. The description should just describe the problem and what was the specific situation that led to this problem. Keep the context Indian. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.  It should not be about writing an email.
                        Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description. 
                        Questions - Give me the first question the manager will ask the team member based on the situation .The question should be deep, thoughtful and realistic. Give the name of person asking the question. Keep it less than 35 words. NEVER provide a response to the question. Never start with any introduction sentences. Start with the question directly. 
                        Output format - Manager name: Question
                        For example - Ajay: question?
                        Prompts - As given in the output format. 

                        Here the format looks like :

                        "Title:",

                        "Description:",

                        "Questions:",

                        "Prompts:" - ["Please respond in order to continue." 
                        "Respond as {Manager name}", 
                        "Please respond in order to continue." 
                        "Respond as {Manager name}", 
                        "Please respond in order to continue." 
                        "Respond as {Manager name}", 
                        "Please respond in order to continue." 
                        "Respond as {Manager name}", 
                        "Please respond in order to continue." 
                        "Respond as {Manager name}"
                        "Conclude the discussion as a participant."]

                        Write the manager's name in place of {Manager name}. The Manager name should always be the same. Do not make any changes in the given format. . 

                        Do not include any response.
                        Always provide the output in the given format. 

                        NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.

                        NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - "Rating : 6". Do not include any other explanation.
                        
                        NOTE : Make sure the situation is very advanced and tough.

                        NOTE : there must be only one manager in picture.

                        NOTE : Never miss the Title, Description, Questions.

                        \n\nAssistant: 

                    """
        prompt = Template(prompt).substitute(information = report_data)  
    else:
        if case == 'normal':
            prompt = """
                \n\nHuman:
                information: "${information}"

                Carefully review and analyze the provided {information}. Using this assessment, create a rigorous, high-level simulation that serves as an extended version of the previous scenario. This new scenario must specifically address areas where candidates previously scored low or where improvement is needed, ensuring a targeted approach to skill development.

                Key Requirements:

                The new scenario must build upon the previous one, extending its complexity while introducing fresh challenges.
                Focus on areas where candidates demonstrated lower scores or struggled, ensuring the simulation directly targets weaknesses.
                Introduce new variables, constraints, or decision points that escalate difficulty while maintaining continuity.
                Challenge candidates to apply deeper critical thinking, adaptability, and problem-solving skills under more complex conditions.
                Avoid repeating previous instructions unless necessary for context—focus on expanding and intensifying the situation rather than restating it.
                Additionally, provide an analysis of which key areas need improvement and how this extended scenario aims to strengthen them.

                Deliver the extended scenario accordingly.


                Give:
                Description - Define the situation, and the problem. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on data, industry, events, etc. The description should just describe the problem and what was the specific situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.  It should not be about writing an email.
                Title - Give a specific and relevant title for this description in less than 10 words.
                Questions - Develop a set of ${num_of_question} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.
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

                "Skills 1" repeated for ${num_of_question} question(s). Do not include any {responder} response.

                NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - "Rating : 6". Do not include any other explanation.
                
                NOTE : Make sure the simulation is very advanced and tough.
                \n\nAssistant:

                """ 
        elif case == 'soft_skills':

            prompt = '''
            \n\nHuman:
            (information: ${information})

            Carefully review and analyze the provided {information}. Based on this assessment, create a rigorous, high-level simulation that serves as an extended version of the previous scenario, diving deeper into the required skills and interactions. This new scenario must specifically address new areas for candidates to explore, ensuring a targeted approach to tackling an entirely new challenge. 

            Key Requirements:
                Create a brand new scenaio in the same industry. Target ONLY soft skills that are not covered in the {information} context.
                Note: Never change the Industry Domain of the scenario.
                
            Deliver the extended scenario accordingly


            Read this {information} thoroughly. Now based on this information and your understanding create an advanced and tough simulation situation to practice the skills presented in the {information}. After creating the situation provide these:
            Description - Define the situation, and the problem focuses exclusively on soft skills. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on data, industry, events, etc. The description should just describe the problem and what was the specific situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.
            Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
            Questions - Develop a set of ${num_of_question} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.Question shall focus exclusively on soft skills
            Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
            KLP - With each question add one or two line takeaways for providing feedback. The takeaways should be related to the question it is provided with.
            KLS - With each question, add the skill(s) that are tested. And For every question choose exactly {2} skill(s) and not more or less than {2} should be chosen for each question. The skills for all the questions should be unique AND shall not repeat from (information). Each question shall have a unique skill AND shall not repeat from (information) and focus exclusively on soft skills.
            Always end the description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
            In every response, you must:
            Clearly state your role as X as in (information).
            Identify Y as the person asking as in (information)
            The Question, Custom Prompt, KLP, KLS should be numbered.
            Here the format looks like :
            "Title",
            "Description”,
            “Statement",
            "Question 1",
            "Prompt 1",
            "Takeaway 1" ,
            "Skills 1" repeated for ${num_of_question} question(s). Do not include any {responder} response.
            'The Question, Prompt, Takeaway, Skills should be numbered.'
            
            NOTE: Description, questions, and skills should focus exclusively on soft skills.
            NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
            NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
            NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated. Each skill shall only be one word AND shall not repeat from (information).
            NOTE: "Rating" must be included.
            NOTE : Make sure the simulation is very advanced and tough.
            NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description] as in (information). Your intent is to achieve Z.
            NOTE: Never miss Title, Description, Statement and other variables.
            \n\nAssistant:
                    
        '''
            
        elif case == 'previous_normal_test':
            prompt = """
            (information: ${information})

            Carefully review and analyze the provided {information}. Based on this assessment, create a rigorous, high-level simulation that serves as an extended version of in the context of the  previous scenario, diving deeper into the required skills and interactions. This new scenario must specifically address new areas for candidates to explore, ensuring a targeted approach to tackling an entirely new challenge. 

            Key Requirements:

            The new scenario must build upon the previous one, increasing its complexity while introducing fresh challenges.
            Focus on areas where candidates can explore new perspectives, ensuring the simulation directly targets their strengths and weaknesses.
            Introduce new variables, constraints, or decision points that heighten difficulty while maintaining continuity with the prior scenario.
            Challenge candidates to apply deeper critical thinking, adaptability, and problem-solving skills under more complex conditions.
            Avoid repeating previous instructions unless necessary for context—emphasize expanding and intensifying the situation rather than restating it.
            Give the statement while ensuring the variables of who you are and whom you are responding to are clearly the same as in (information). 

            Deliver the extended scenario accordingly

            Read this {information} thoroughly. Now, based on this information and your understanding, create an advanced and detailed description to practice the skills presented in the {information}. After creating the situation, provide these:

            Description - Define the situation and the problem. The problem should be related to the {information} provided. The description should always involve a conversation based on the context of the {information}. Make the description specific based on the information, focusing on relevant details. Provide the name of the individual in a leadership role based on the information, but never provide the name of the other person involved. The description should detail the situation that led to the issue, and it should not include dialogues. It should always be from a third-person perspective. Provide the description in 100 to 200 words. Avoid adding any conclusions. The situation should not be related to writing emails.

            Always replace the terms with those relevant to the {information}, ensuring the scenario is based on the specifics of the context and is open-ended for further exploration.
            Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
            Questions - Develop a set of ${num_of_question} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.Question shall focus exclusively on hard skills
            Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
            KLP - With each question add one or two line takeaways for providing feedback. The takeaways should be related to the question it is provided with.
            KLS - With each question, add the skill(s) that are tested. And For every question choose exactly {2} skill(s) and not more or less than {2} should be chosen for each question. The skills for all the questions should be unique AND shall not repeat from (information). Each question shall have a unique skill AND shall not repeat from (information) and focus exclusively on hard skills
            Always end the description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
            In every response, you must:
            Clearly state your role as X as in (information).
            Identify Y as the person asking as in (information)
            The Question, Custom Prompt, KLP, KLS should be numbered.
            Here the format looks like :
            "Title",
            "Description”,
            “Statement",
            "Question 1",
            "Prompt 1",
            "Takeaway 1" ,
            "Skills 1" repeated for ${num_of_question} question(s). Do not include any {responder} response.
            'The Question, Prompt, Takeaway, Skills should be numbered.'
            
            NOTE: Description, questions, and skills should focus exclusively on hard skills.
            NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
            NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
            NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated. Each skill shall only be one word AND shall not repeat from (information).
            NOTE: "Rating" must be included.
            NOTE : Make sure the simulation is very advanced and tough.
            NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description] as in (information). Your intent is to achieve Z.
            NOTE: Never miss Title, Description, Statement and other variables.
            \n\nAssistant:
        """
            
        elif case == 'hard_skills':
            prompt = '''
            \n\nHuman:
            (information: ${information})

            Carefully review and analyze the provided {information}. Based on this assessment, create a rigorous, high-level simulation that serves as an extended version of the previous scenario, diving deeper into the required skills and interactions. This new scenario must specifically address new areas for candidates to explore, ensuring a targeted approach to tackling an entirely new challenge.

            Key Requirements:
                Create a brand new scenaio in the same industry. Target ONLY hard skills that are not covered in the {information} context.
                Note: Never change the Industry Domain of the scenario.
                
            Deliver the extended scenario accordingly

            Read this {information} thoroughly. Now based on this information and your understanding create an advanced and tough simulation situation to practice the skills presented in the {information}. After creating the situation provide these:
            Description - Define the situation, and the problem focuses exclusively on hard skills. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on data, industry, events, etc. The description should just describe the problem and what was the specific situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.
            Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
            Questions - Develop a set of ${num_of_question} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.Question shall focus exclusively on hard skills
            Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
            KLP - With each question add one or two line takeaways for providing feedback. The takeaways should be related to the question it is provided with.
            KLS - With each question, add the skill(s) that are tested. And For every question choose exactly {2} skill(s) and not more or less than {2} should be chosen for each question. The skills for all the questions should be unique AND shall not repeat from (information). Each question shall have a unique skill AND shall not repeat from (information) and focus exclusively on hard skills
            Always end the description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
            In every response, you must:
            Clearly state your role as X as in (information).
            Identify Y as the person asking as in (information)
            The Question, Custom Prompt, KLP, KLS should be numbered.
            Here the format looks like :
            "Title",
            "Description”,
            “Statement",
            "Question 1",
            "Prompt 1",
            "Takeaway 1" ,
            "Skills 1" repeated for ${num_of_question} question(s). Do not include any {responder} response.
            'The Question, Prompt, Takeaway, Skills should be numbered.'

            NOTE: Description, questions, and skills should focus exclusively on hard skills.
            NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
            NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
            NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated. Each skill shall only be one word AND shall not repeat from (information).
            NOTE: "Rating" must be included.
            NOTE : Make sure the simulation is very advanced and tough.
            NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description] as in (information). Your intent is to achieve Z.
            NOTE: Never miss Title, Description, Statement and other variables.
            \n\nAssistant:
            
            '''
        prompt = Template(prompt).substitute(information = report_data,
                                            num_of_question=num_questions) 
        
    logger.info({"prompt": prompt})

    return prompt
        

def get_improved_title(title):
    prompt = f"""
        \nHuman:
        title: {title}
        improve this title to 20 words.

        NOTE: Make sure the title is very specific and relevant.
        NOTE: do not start with any introduction sentences. Start with the title directly.
        \nAssistant:
    """

    title = anthropic_completion(prompt, 25)
    title = title.split(':')[-1]
    return title
    
def select_other_element(lst, specified_element):
    # Remove the specified element from the list
    other_elements = [elem for elem in lst if elem != specified_element]
    
    # Return a random choice from the remaining elements
    if other_elements:
        return random.choice(other_elements)
    else:
        return random.choice(lst)

def decode_basic_auth_token(token: str) -> str:
    decoded_token = base64.b64decode(token).decode("utf-8")
    key_and_secret = decoded_token.split(":")

    key = key_and_secret[0]
    secret = key_and_secret[1]

    return key, secret


@timeit
def create_scenario_from_site_context(url,
                                      access_token, 
                                      tenant_id, 
                                      context,
                                      is_feedback_bot=False, 
                                      use_anthropic = False,
                                      type_of_test=TestTypeChoices.test,
                                      scenario_case=ScenarioCaseChoices.simulation, 
                                      origin = None,
                                      competency = None, 
                                      creator_user_id = None, 
                                      custom_prompt = None, 
                                      scenario_summary=None, 
                                      assign_to=None, 
                                      assigned_by=None, 
                                      is_micro = True, 
                                      regeneration=False,
                                      flavour=None,
                                      previous_session_id=None,
                                      by_pass_access_token=False,
                                      game_single_select=False,
                                      available_case=None
                                      ):
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
    logger.info(f"{'#'*100}  creating scenario from site context {'#'*100} ")

    garbage_scenarios = []
    scenario = ""
    max_retry = 3
    case_type = None

    game_case_types = ["static_game","dynamic_game"]

    static_case_types = ["checkin","interview","case", "normal","role_play","static_role_play_soft",
    "static_role_play_hard","static_soft","static_hard"]

    dynamic_case_types = ["normal_dynamic_test","normal_dynamic_test_soft","normal_dynamic_test_hard"]
    dynamic_start_with_user_case_types = ["dynamic_start_with_user"]

    all_case_types = [
    "checkin","interview","case", "normal","role_play","static_role_play_soft",
    "static_role_play_hard","static_soft","static_hard","dynamic_start_with_user",
    "normal_dynamic_test","normal_dynamic_test_soft","normal_dynamic_test_hard",
    "static_game","dynamic_game"
    ]

    if flavour:
        if flavour in dynamic_case_types:
            type_of_test = TestTypeChoices.dynamic_discussion_thread
            scenario_case = ScenarioCaseChoices.dynamic_discussion

        elif flavour in game_case_types:
            type_of_test = TestTypeChoices.dynamic_discussion_thread
            scenario_case = ScenarioCaseChoices.game
        elif flavour in dynamic_start_with_user_case_types:
            type_of_test = TestTypeChoices.dynamic_discussion_thread
            if scenario_case == ScenarioCaseChoices.simulation:
                scenario_case = "start_with_userteam-manager"


    start_with_user_opt = ["team-manager","sales-customer","customer-sales","manager-team"]
    start_with_user = None
    available_case_types = all_case_types
    if type_of_test == TestTypeChoices.dynamic_discussion_thread and scenario_case == ScenarioCaseChoices.game:
        available_case_types = game_case_types
    elif type_of_test == TestTypeChoices.dynamic_discussion_thread and scenario_case.startswith("start_with_user"):
        start_with_user = scenario_case.split("start_with_user")[-1]
        scenario_case = ScenarioCaseChoices.dynamic_discussion
        available_case_types = dynamic_start_with_user_case_types
    elif type_of_test == TestTypeChoices.dynamic_discussion_thread:
        scenario_case = ScenarioCaseChoices.dynamic_discussion
        available_case_types = dynamic_case_types
    elif type_of_test == TestTypeChoices.test:
        available_case_types = static_case_types

    if previous_session_id:
        available_case_types = ['previous_normal_test']

    if available_case:
        available_case_types = available_case # it will override 

    for i in range(max_retry):
        logger.info(f"==========================================trying outer test generation for {i+1} time=================================================================")
        if case_type is not None:
            case_type = select_other_element(available_case_types, case_type)
        else:
            if regeneration:
                if flavour:
                    case_type = select_other_element(available_case_types, flavour)
                else: 
                    case_type = random.choice(available_case_types)
            else:
                if flavour:
                    case_type = flavour
                else: 
                    case_type = random.choice(available_case_types)


        try:
            site_information = ""
            industry = None
            if context:
                print(f'here {context}')
                context_data = json.loads(context)
                title, des, industry = context_data['title'], context_data['data']['information'],context_data['data'].get('industry')
                site_information = f"{title} {des}"
                if i > 0:
                    title = get_improved_title(title)
                logger.info(f"{'#'*100} title: {title}, context: {des} 'title-value': {json.loads(context)['title']} {'#'*100} ")
            
            site_information = replace_words(site_information)

            if custom_prompt:
                prompt = custom_prompt
            elif is_feedback_bot:
                prompt = get_prompt_for_feedback_bot(site_information)
            elif previous_session_id:
                prompt = get_scenario_creation_report_prompt(
                    prompt_type=type_of_test,
                    num_questions=3 if is_micro else 6,
                    case=case_type,
                    session_id=previous_session_id
                )
            else:
                if start_with_user:
                    site_information += f'\nStart With User: {start_with_user}'
                elif case_type == 'dynamic_start_with_user':
                    start_with_user = random.choice(start_with_user_opt)
                    site_information += f'\nStart With User: {start_with_user}'

                if type_of_test == TestTypeChoices.dynamic_discussion_thread and scenario_case == ScenarioCaseChoices.game:
                    prompt = get_game_prompt(
                        industry=industry,
                        information=site_information,
                        num_of_questions=10,
                        question_type= 'single' if game_single_select else 'multiple',
                        candidate_type='manager'
                        )
                else:
                    prompt = get_scenario_prompt(
                        information=site_information,
                        scenario_type=case_type,
                        question_count=3 if is_micro else 6,
                    )

            logger.info(f"{previous_session_id} Final Prompt: {prompt}")
            response = {}
            scenario = ''
            title, description, question_info, skill_to_evalaute, scenario_information = "","","","", {}
            orchestrated_details = ""
            rating = 0 
            for j in range(1):
                try:

                    logger.info(f"============================flavour:  {case_type} ===================================")
                    if use_anthropic:
                        logger.info(f'trying scenario creation anthropic for {i +1} time')
                        scenario = anthropic_completion(prompt,5000)
                    else:
                        logger.info(f'trying scenario creation gemini for {i +1} time')
                        scenario = gemini_completion(prompt)
                        scenario = re.sub(r'[#*]', '', scenario)

                    if type_of_test == TestTypeChoices.dynamic_discussion_thread and scenario_case == ScenarioCaseChoices.game:
                        title,description,question_info,rating,skill_to_evalaute,orchestrated_details, scenario_information = extract_game_type(text=scenario,
                                                                                                                                                case_type=case_type,
                                                                                                                                                question_count=10,
                                                                                                                                                candidate_type='Manager')
                    elif type_of_test == TestTypeChoices.dynamic_discussion_thread:
                        title,description,question_info,rating,skill_to_evalaute,orchestrated_details, scenario_information = extract_information_dynamic_scenario(text=scenario, 
                                                                                                                                                                   num_questions=3 if is_micro else 6,
                                                                                                                                                                   start_with_user=start_with_user 
                                                                                                                                                                   )
                    else:
                        title, description, question_info, skill_to_evalaute,rating, scenario_information = extract_information(scenario)

                except Exception as e:
                    logger.exception(f"{'#'*100}  failed to extract information from bison scenario {'#'*100} : {e} ")
                    scd = ScenarioCreationDetails.objects.create(
                            tenant_id=tenant_id,
                            creator_id = creator_user_id if creator_user_id else "system",
                            input = f"{title} : {des}",
                            output = scenario,
                            status = "failed",
                            reason_of_failure = f"failed to extract information from bison. Reason : {e}"
                        )
                    logger.info(f"{'#'*100}  failed to generate scenario from bison, retrying {'#'*100} ")
                    try:
                        case_type = select_other_element(available_case_types,case_type)
                        logger.info(f"============================flavour 2:  {case_type} ===================================")
                        if start_with_user:
                            site_information += f'\nStart With User: {start_with_user}'
                        elif case_type == 'dynamic_start_with_user':
                            start_with_user = random.choice(start_with_user_opt)
                            site_information += f'\nStart With User: {start_with_user}'

                        if type_of_test == TestTypeChoices.dynamic_discussion_thread and scenario_case == ScenarioCaseChoices.game:
                            prompt = get_game_prompt(
                                industry=industry,
                                information=site_information,
                                num_of_questions=10,
                                question_type= 'single' if game_single_select else 'multiple',
                                candidate_type='manager'
                                )
                        else:
                            prompt = get_scenario_prompt(
                                information=site_information,
                                scenario_type=case_type,
                                question_count=3 if is_micro else 6,
                            )
                        if use_anthropic:
                            logger.info(f'**retrying scenario creation anthropic for {i +1} time')
                            scenario = anthropic_completion(prompt,5000)
                        else:
                            logger.info(f'**retrying scenario creation gemini for {i +1} time')
                            scenario = gemini_completion(prompt)
                        
                        if type_of_test == TestTypeChoices.dynamic_discussion_thread and scenario_case == ScenarioCaseChoices.game:
                            title,description,question_info,rating,skill_to_evalaute,orchestrated_details, scenario_information = extract_game_type(text=scenario,
                                                                                                                                                    case_type=case_type,
                                                                                                                                                    question_count=10,
                                                                                                                                                    candidate_type='Manager')
                        elif type_of_test == TestTypeChoices.dynamic_discussion_thread:
                            title,description,question_info,rating,skill_to_evalaute,orchestrated_details,scenario_information = extract_information_dynamic_scenario(text=scenario,
                                                                                                                                                                    num_questions=3 if is_micro else 6,
                                                                                                                                                                    start_with_user=start_with_user
                                                                                                                                                                    )
                        else:
                            title, description, question_info, skill_to_evalaute,rating,scenario_information = extract_information(scenario)
                    

                    except Exception as e:
                        garbage_scenarios.append(scenario)
                        rating = 0
                        logger.exception(f"{'#'*100}  failed to generate scenario for following reason {'#'*100} : {e} ")
                        scd = ScenarioCreationDetails.objects.create(
                                tenant_id=tenant_id,
                                creator_id = creator_user_id if creator_user_id else "system",
                                input = f"{title} : {des}",
                                output = scenario,
                                status = "failed",
                                reason_of_failure = f"failed to generate scenario for following reason : {e}"
                            )

                if scenario == 'failed to generate scenario':
                    continue
                break

            admin_user = User.objects.filter(tenant_id=tenant_id,role='admin').first()

            logger.info(f"{'#'*100}  skills to evaluate:  <==> {skill_to_evalaute}, description: {description}  {'#'*100} ")
            if case_type == 'role_play':
                scenario_case = ScenarioCaseChoices.role_play

            test_json = {
                "title": json.loads(context)['title'] if origin == "script" else title,
                "description": description,
                "email_address_list":'coachbots@googlegroups.com',
                "questions": question_info,
                "skills_to_evaluate": skill_to_evalaute,
                "creator_id": admin_user.uid,
                "scenario_case": 'pms' if competency is not None else scenario_case,
                "interaction_mode":'text' if scenario_case == ScenarioCaseChoices.game else 'any',
                "test_type":type_of_test,
                "email_candidate":True,
                "gpt_prompt_override":"",
                "is_self_created": True,
                "certificate_details": {"title": scenario_information.get('certificate_title')} if scenario_information.get('certificate_title') else {'title': title},
                "competency_group": competency,
                "creator_user_id": creator_user_id,
                'is_assigned': True if assign_to is not None else False,
                'assigned_to': assign_to,
                'assigned_by': assigned_by,
                'is_micro': is_micro,
                'candidate_type': scenario_information.get("candidate_type","Manager"),
            }
            if scenario_information.get('custom_prompt'):
                test_json['gpt_prompt_override'] = scenario_information.get('custom_prompt')

            if scenario_summary:
                test_json["scenario_summary"] = scenario_summary
            if type_of_test == TestTypeChoices.dynamic_discussion_thread:
                test_json["orchestrated_conversation_details"] = orchestrated_details

            if not url in [None,""]:
                test_json["web_page_url"] = url.strip()

            json_data = json.dumps(test_json)

            if by_pass_access_token:
                try:
                    tenant = Tenant.objects.get(uid=tenant_id)
                    serializer = CreateTestSerializer(data=test_json)
                    serializer.is_valid(raise_exception=True)

                    if serializer.validated_data["creator_id"] is None:
                        serializer.validated_data["creator_id"] = admin_user.uid



                    test, test_questions = create_test(
                        tenant=tenant,
                        **serializer.validated_data
                    )
                    result = {'title': test.title,'test_code': test.test_code,
                                'description': test.description,'test_type': test.test_type,
                                "is_micro": test.is_micro,"scenario_case": test.scenario_case,
                                "interaction_mode": test.interaction_mode, 
                                "scenario": scenario,'prompt': prompt,
                                "test_id": test.uid,
                                "description_media": test.description_media}
                    logger.info(f'created Test: {result}')
                    return result
                    
                except Exception as e:
                    logger.error(e,exc_info=True)
                    scd = ScenarioCreationDetails.objects.create(
                                    tenant_id=tenant_id,
                                    creator_id = creator_user_id if creator_user_id else "system",
                                    input = f"{title} : {des}",
                                    output = scenario,
                                    status = "failed",
                                    reason_of_failure = f"failed to extract information for following reason : {e}"
                                )
                    raise e


            else:
                headers = {
                            'Content-Type': 'application/json',
                            'Authorization': access_token
                        }
                
                logger.info(f"{'#'*100} Scenario raw data : {test_json}  , origin :{origin} {'#'*100} ")
                # return test_json
                
                try:
                    resp = requests.post(
                                            API_ENDPOINT_SLACK, data=json_data, headers=headers, verify=False)
                    response = resp.json()
                    print("%"*200, '\n', response, '\n', admin_user.uid,'\n', resp.status_code, "%"*200)
             
                    if origin == "script":
                        resp_json = test_json.copy()
                        resp_json['test_code'] = response['test_code']

                        return resp_json
                    
                    return {'title': response['title'],'test_code': response['test_code'],
                            'description': response['description'],'test_type': response['test_type'],
                            "is_micro": response['is_micro'],"scenario_case": response['scenario_case'],
                            "interaction_mode": response['interaction_mode'], 
                            "scenario": scenario, 'prompt': prompt
                            , "test_id": response['uid'], "description_media": response['description_media']}
                    
                except Exception as e:
                    logger.error(e,exc_info=True)
                    scd = ScenarioCreationDetails.objects.create(
                                    tenant_id=tenant_id,
                                    creator_id = creator_user_id if creator_user_id else "system",
                                    input = f"{title} : {des}",
                                    output = scenario,
                                    status = "failed",
                                    reason_of_failure = f"failed to extract information for following reason : {e}"
                                )
                    raise e

        except Exception as e:
            logger.exception(f"{'#'*100}  failed to generate scenario for following reason {'#'*100} : {e} ")
            scd = ScenarioCreationDetails.objects.create(
                                tenant_id=tenant_id,
                                creator_id = creator_user_id if creator_user_id else "system",
                                input = f"{context}",
                                output = scenario,
                                status = "failed",
                                reason_of_failure = f"failed to extract information for following reason : {e}"
                            )
            # send_error_notification("create_scenario_from_site_context",f"failed to generate scenario for following reason : {e}",e)


            if i+1 == max_retry:
                logger.info(f"{'!'*100}  failed outer {max_retry} times  {'!'*100}")
                # TODO: send email to user if creator_user_id is not None
                if creator_user_id:
                    send_error_notification("create_scenario_from_site_context",f"failed to generate scenario for following reason : {e}",e)
                    try:
                        user = User.objects.get(uid=creator_user_id)
                        send_generic_email(
                            f'Scenario Generation(by user:{creator_user_id} ) Failed for given details',context)
                        send_generic_email(
                            f'Scenario Generation(by user:{creator_user_id} ) Failed for given details',context,'help@coachbots.com')
                    except Exception as e:
                        logger.error(e,exc_info=True)
                        
                return {'message':"failed to generate the scenario","data":garbage_scenarios}
            continue

    # logger.info(f"!!!!!!!!!!!!!!!!!!!!!! Everything failed !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")

# ---------------ScenarioCreator -----------------
def fetch_test_codes_by_site_context(url,tenant_id,by='skills',is_micro=True):
    """
    This function is used to fetch the test codes based on the site context
    by can be skills and web_page
    """

    tests = None
    if by == 'web_page':
        tests = Test.objects.filter(tenant_id=tenant_id,deleted=0,web_page_url=url.strip(),is_micro=is_micro).order_by("id")
    else:
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
            "test_type": test.test_type,
            "is_micro": test.is_micro,
            'interaction_mode': test.interaction_mode,
            'scenario_case': test.scenario_case ,
            "description_media": test.description_media
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
    """
    This method gives similarity percentage b/w two sentences.
    """
    # Tokenize and remove stopwords
    stop_words = set(stopwords.words('english'))
    words1 = [word.lower() for word in word_tokenize(sentence1) if word.isalpha() and word.lower() not in stop_words]
    words2 = [word.lower() for word in word_tokenize(sentence2) if word.isalpha() and word.lower() not in stop_words]

    # Calculate the Jaccard similarity
    intersection = len(set(words1) & set(words2))
    union = len(set(words1) | set(words2))
    similarity_percentage = (intersection / union) * 100

    logger.info(f"{'#'*100} Similarity between {sentence1} and {sentence2} is {similarity_percentage} {'#'*100}")

    return similarity_percentage


# @timeit
# def scrape_article_data(url):
#     # Send a GET request to fetch the HTML content
#     response = requests.get(url)
    
#     # Check if the request was successful (status code 200)
#     if response.status_code == 200:
#         # Parse the HTML content using BeautifulSoup
#         soup = BeautifulSoup(response.content, 'html.parser')
#         # Extract article content
#         article_content = ''
#         article_body = soup.find('div')
#         if article_body:
#             paragraphs = soup.find_all('p')
#             article_content = '\n'.join([p.get_text() for p in paragraphs])
        
#         return {
#             'article_content': article_content
#         }
#     else:
#         print("Failed to retrieve the page.")
#         return {}


@timeit
def scrape_article_data(url):
    """
    This function is designed to scrape the title and content of an article from a given URL.

    The function sends a GET request to the provided URL and checks the response status. If the status code is 200, 
    indicating a successful request, it proceeds to parse the HTML content using BeautifulSoup and the readability's Document module. 
    The Document module is used to extract the title and the summary of the HTML content. BeautifulSoup is then used to further parse 
    the summary content and extract the text within the 'div' tag and all 'p' tags, which are assumed to contain the main article content.

    Parameters:
    url (str): The URL of the web page to scrape. This should be a string containing a valid URL.

    Returns:
    dict: A dictionary containing the title and content of the article. The dictionary has the following structure:
        {
            'title': 'The title of the article',
            'article_content': 'The content of the article'
        }
    If the GET request fails, the function logs an error message and returns an empty dictionary.

    Example:
    >>> scrape_article_data('https://example.com/article')
    {
        'title': 'Example Article',
        'article_content': 'This is an example article...'
    }
    """
    # Send a GET request to fetch the HTML content
    try:
        user_agents =[
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
        ]
    

        request_headers = {
            'user-agent': random.choice(user_agents)
        }
        response = requests.get(url, headers=request_headers)
        logger.info(f"================================ {response.status_code}, {response.content}=============")
        
        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Parse the HTML content using BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            # Find the meta title and description tags
            description_tag = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
            description = description_tag.get('content') if description_tag else None

            doc = Document(response.content)
            soup = BeautifulSoup(doc.summary(), 'html.parser')
            
            # Extract title
            title = doc.title()
            # Extract article content
            article_content = ''
            article_body = soup.find('div')
            if article_body:
                paragraphs = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span'])
                article_content = '\n'.join([p.get_text().strip() for p in paragraphs])


            logger.info(f"""
            Extracted article data : title : {title}
            =============================
            description : {description}
            =============================
            content : {article_content}
            """)

            return {
                'title': replace_words(title),
                'description': replace_words(description),
                'article_content': replace_words(article_content)
            }
        else:
            logger.error("Failed to retrieve the page.")
            return {}
        
    except Exception as e:
        logger.exception (f"Failed to extract infomation : {e}")
        return {}





















#=============================================================================================================
### these three funciton is for testing purpose only
def test_model(model_name, num_tests=50):
    results = []
    context = "discussing next steps in career ladder & career development stretegies"

    # prompt = get_one_scenario_prompt(site_information=context,prompt_type="test")
    prompt = get_one_scenario_prompt(site_information=context,prompt_type=TestTypeChoices.dynamic_discussion_thread)
    for _ in range(num_tests):
        scenario = ''
        start_time = time.time()
        try:
            scenario = gemini_completion(prompt,[model_name])
            print(scenario)
            title,description,question_info,rating,skill_to_evalaute,orchestrated_details,_ = extract_information_dynamic_scenario(text=scenario)
            print(title, description, question_info, skill_to_evalaute,rating,orchestrated_details) # Replace with your test data path
            results.append((True, scenario,"",(time.time()-start_time)))
        except Exception as e:
            results.append((False, scenario,f"{e}",(time.time()-start_time)))
    
    return results

def write_to_csv(output_file, results):
    import csv
    
    with open(output_file, 'a', newline='') as csvfile:  # Use 'a' for append mode
        fieldnames = ['Model', 'Test', 'Status', 'Output', 'Reason', 'Time']
        
        # Check if the file is empty, and write header only if it's empty
        file_empty = csvfile.tell() == 0
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if file_empty:
            writer.writeheader()

        for model_name, test_results in results.items():
            for test_num, (status, output, reason, time) in enumerate(test_results, start=1):
                writer.writerow({'Model': model_name, 'Test': test_num, 'Status': 'Success' if status else 'Failure', 'Output': output, 'Reason': reason, 'Time': time})

def testing_palm_models():
    model_list = ['text-bison@001']  # Add your model names to test
    num_tests = 20

    results = {}
    for model_name in model_list:
        results[model_name] = test_model(model_name, num_tests)

    success_output_file = 'success_output.csv'
    failure_output_file = 'failure_output.csv'

    write_to_csv("testing_palm_models.csv", results)
    # write_to_csv(success_output_file,results)
    # You can choose to write failure results to a different file or combine them as needed.
    # write_to_csv(failure_output_file, results)


def write_to_csv_v2(output_file, results):
    import csv
    #is_created, failed_scenarios,test_scenario,reasons,(time.time()-start_time)
    with open(output_file, 'a', newline='') as csvfile:  # Use 'a' for append mode
        fieldnames = ['Model','Failed Scenarios', 'Test', 'Status', 'Output', 'Reason', 'Time']
        
        # Check if the file is empty, and write header only if it's empty
        file_empty = csvfile.tell() == 0
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if file_empty:
            writer.writeheader()

        for model_name, test_results in results.items():
            for test_num, (status,failed,output, reason, time) in enumerate(test_results, start=1):
                writer.writerow({'Model': model_name,'Failed Scenarios': failed ,'Test': test_num, 'Status': 'Success' if status else 'Failure', 'Output': output, 'Reason': reason, 'Time': time})


def test_scenario(scenario_case,test_type):
    end_result = {}
    results = []
    context = "discussing next steps in career ladder & career development stretegies"

    # prompt = get_one_scenario_prompt(site_information=context,prompt_type="test")
    for _ in range(1):
        scenario = ''
        start_time = time.time()
        is_created, failed_scenarios, test_scenario, reasons = create_scenario_from_site_context(url='',
                                                                                                 access_token="",
                                                                                                tenant_id="62d76be2-b439-4528-9ae4-2af389abb5f5",
                                                                                                context='{"title":"","data":{"information":"discussing next steps in career ladder & career development stretegies"} }',
                                                                                                use_anthropic=False,
                                                                                                type_of_test=test_type,
                                                                                                flavour=scenario_case,
                                                                                                available_case = [scenario_case] ,# it will override
                                                                                                by_pass_access_token=True,
        )


        results.append((is_created, failed_scenarios,test_scenario,reasons,(time.time()-start_time)))
    
    end_result[f'text-bison@001'] = results
    
        
    write_to_csv_v2("testing_create_scenario_palm_models.csv", end_result)



# def create_feedback_bot(name,profile_id,email,user_id,bio,project):
    
#     json_data = {
#     "bot_type": "feedback_bot",
#     "bot_name": name,
#     "profile_id": profile_id,
#     "email": email,
#     "attributes": {
#       "heading": "welcome to feedback bot",
#       "feedback_questions": {
#         "1": "As witnessed by you what would be some of my strengths and/or weaknesses, that you have come across?",
#         "2": "Regarding workplace team management skills, how would you rate my skills?",
#         "3": "I am trying to improve my project management skills. In the past quarter have you seen any examples? Examples would be great.",
#         "4": "How would like to see me implement the feedback you have provided so far?"
#       }
#     },
#     "feedback_questions": {
#       "1": "As witnessed by you what would be some of my strengths and/or weaknesses, that you have come across?",
#       "2": "Regarding workplace team management skills, how would you rate my skills?",
#       "3": "I am trying to improve my project management skills. In the past quarter have you seen any examples? Examples would be great.",
#       "4": "How would like to see me implement the feedback you have provided so far?"
#     },
#     "participant_id": user_id,
#     "additional_data": {
#       "short_profile_bio": bio,
#       "current_projects": project,
#       "suggested_projects": ""
#     },
#     "bot_base_url": "https://playground.coachbots.com"
#   }

#     import requests
#     import json

#     url = "http://localhost:8001/api/v1/accounts/create-bot-by-details/"

#     payload = json.dumps(json_data)
#     headers = {
#     'Authorization': 'Basic Yzc3MjFmZGItYTllMC00YTYxLWEzMTYtNDRhODA1N2VkMjY0OjhjNWNlZWZlLTY2Y2QtNDliZi04MTY5LTBhNjMwMmU5NmZlMA==',
#     'Content-Type': 'application/json'
#     }

#     response = requests.request("POST", url, headers=headers, data=payload)

#     print(response.text)
#     data = response.json()
    

#     return data['bot_id']


# from users.models import CoachCoacheeMentorMenteeProfile

# def create_feed():
#     user_ids = [
#         {'user_id': '2bc1aae5-0044-4091-ab06-b0415b0f460d'}, 
#                 ]
#     result = []

#     for i in user_ids:
#         user_id = i['user_id']
        
#         user = get_user_by_id(user_id)
#         name = user.name
#         profile = CoachCoacheeMentorMenteeProfile.objects.get(user_id=user_id)

#         email = profile.email
#         profile_id = profile.uid
#         bio = profile.about
#         project = ""

#         result.append(create_feedback_bot(name,profile_id,email,user_id,bio,project))

#     print(result)


# def save_record(bot):
#     ids = [bot
#     ]

#     for i in ids:
#         si = SignatureBot.objects.get(bot_id=i)
#         profile = CoachCoacheeMentorMenteeProfile.objects.get(user_id=si.user_id)
#         about = profile.about
#         si.bot_details['info'] = about
#         si.bot_details['coach_name'] = profile.name
#         si.save()


def create_role_skill_bot():
    from users.models import BotAttribute
    from utilities.models import DirectoryPageInfo
    bots = [
        {
            "bot_name": "Communication Skills",
            "prompt": """User Situation : ${user_intake}
User Context : ${user_context}

Provide some guidance and tips to the user who's asking a problem related to Communication at workplace in User Context. 
The background information is provided in User Situation.  
Use a checklist kind of approach to give guidance or tips.
Provide tailored advice to help users become better communicators. 
The advice should be in the form of checklists that the user can do to solve the particular problem.
Customize the response to make it suitable to the situation. 
Also explain how the person can implement the tips in their particular situation. 

Add this line during the conversation wherever it's most suitable, "You can visit the coachbot library to practice these." Please integrate this in the natural flow of the response and conversation. You can change the text according to the situation to make it more contextual and customized for the conversation. ONLY add these lines when it's suitable in the response.
It doesn't need to be in every response, only give them wherever it makes sense. 

NOTE: ONLY provide guidance on communication skills.
NOTE: If the given User Context is not directly related to "Communication at Workplace" please just respond with "I am specifically trained for the subject matter described as defined in my page. Unfortunately I can not answer this question."
NOTE: NEVER provide any kind of explanation or summary of the response.
NOTE: NEVER start with any kind of introduction sentence. Do not provide any kind of heading or introduction text in the output. 
NOTE: Start directly with the response and only provide the response.
""",
            "intake": {
                "1": "What are your current challenges?",
                "2": "What outcomes do you wish to achieve?"
            },
            "about": "The Communication Skills bot is equipped with practical techniques and tailored advice, it helps you enhance your verbal and non-verbal communication abilities. From active listening to assertiveness, it provides personalized coaching to boost your confidence in any conversation or presentation. With clear, straightforward guidance, it empowers you to convey your message effectively and build stronger connections in both personal and professional settings."
        }
    ]
    user_id = "eb1a3c1b-33a6-4025-ae80-cb5d013c48d9"
    tenant_id = "62d76be2-b439-4528-9ae4-2af389abb5f5"
    result = []
    for bot in bots:
        bot_id = bot['bot_name'].lower().replace(" ","-")+ '-' + user_id[:5]
        singature_bot = SignatureBot.objects.create(
            tenant_id =tenant_id,
            bot_id = bot_id,
            user_id=user_id,
            bot_type='coachbots',
            bot_scenario_case= 'skill_bot',
            attributes= {"heading": f"welcome to {bot['bot_name']} bot"},
            custom_prompt = bot['prompt'],
            bot_details ={"subject": bot["bot_name"], "coach_name": "Coachbot", "is_login_required": False, "is_strict_login_required": False},
            is_approved = True
        )

        BotAttribute.objects.create(
                                    tenant_id=tenant_id,
                                    bot_id=singature_bot.uid,
                                    bot_name=bot['bot_name'],
                                    coach_name = "Coachbot",
                                    coach_email = "mail@coachbots.com",
                                    initial_qnas = bot['intake'],
                                    about = bot['about'],
                                    )
        
        DirectoryPageInfo.objects.create(
            name = bot["bot_name"],
            department = 'HR',
            profile_pic_url = 'https://res.cloudinary.com/dtbl4jg02/image/upload/v1709723404/v6olyb3foi7a0l8rubk8.jpg',
            profile_type = 'coachbots',
            description = bot['about'],
            is_visible = True,
            is_approved = True,
            avatar_bot_id = bot_id,
            avatar_bot_url = f'https://playground.coachbots.com/subject-expert/{bot_id}',
            profile_id = 'de30992a-bb4d-41eb-ba1b-4e0447704f64'
        )

        result.append(bot_id)

    return result




def get_conversation_summary(conv):
            
    transcript_summary_prompt = f"""
        Conversation : ${conv}

        Summarize this coaching conversation. Create the summary like an action plan and provide it in bullet points. Do not leave out any important information. The summary should be a quarter of the length of the original Conversation.

        NOTE : Never start with any kind of introduction sentence. Do not provide any kind of heading or introduction text in the output. Start directly with the summary and only provide the summary .
    """
    transcript_summary = anthropic_completion(transcript_summary_prompt, 1000)
    return transcript_summary

def  get_relevant_session_summary(conversation_summeries,intake_summery,only_rel_json=False):


    summary = ""
    for index, conv in enumerate(conversation_summeries,start=1):
        summary += f" summary_text_{index}: {conv}\n\n"

    prompt = """
    \n\nHuman: 

    "Conversation Summaries": ${conversation_summeries}

    "Intake Summary": ${intake_summery}

    "REQUIRED FROM LLM:" Please check whether the summaries provided in "Conversation Summaries"list individually is even slightly related to the "Intake Summary" asked and the description provided. Assign a relevancy score between 0 to 10, 10 being highly relevant  and 0 being completely irrelevant . ONLY when the entire summary is completely random and unrelated to the inake summary and description give the relevancy score value as 0. 
    NOTE: Please Reply in a valid JSON format only and no other format will be accepted. 
    NOTE: Don't put any other text in the reply other than the JSON. NOTE: Output Format Example: {{"summary_text_1":"1"},"summery_text_2":"5",..} 
    NOTE: Do not add any other sentence, information or explanation in the output. Only provide the output in the format given above. 
    
    \n\nAssistant:
    
    """

    prompt = Template(prompt).substitute(
        conversation_summeries = summary,
        intake_summery = intake_summery
    )

    summary_data = anthropic_completion(prompt, 1000)
    json_data = json_extraction(summary_data)
    logger.info(f"summary_data: {summary_data}, json: {json_data}")
    json_data = json.loads(json_data)

    if only_rel_json:
        return json_data

    
    sorted_summary_rating = sorted(json_data.items(), key=lambda x: x[1], reverse=True)
    logger.info(f"summary: {sorted_summary_rating}")
    try:
        rel_summary = conversation_summeries[int(sorted_summary_rating[0][0].split('_')[-1]) - 1]
    except Exception as e:
        logger.exception(f"failed with error: {e}")
        rel_summary = conversation_summeries[-1]

    
    return rel_summary





def create_scenario_from_transcript(conversation,access_token, tenant_id, context=None, source=None, competency=None, creator_user_id=None):
    simulation_prompt = f"""
    Information : ${conversation}

    Read this {{Information}} thoroughly. This is the conversation summary between a coach/mentor and coachee. Now based on this information and your understanding create an advanced and tough simulation situation to practice the skills discussed in the {{Information}}. After creating the situation provide these:

    Description - Define the situation, and the problem. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on data, industry, events, etc. The description should just describe the problem and what was the specific situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion. It should not be about writing an email.
    Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
    Questions - Develop a set of {3} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.
    Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {{Please provide a feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}}
    KLP - With each question add one or two line takeaway for providing feedback. The takeaways should be related to the question it is provided with.
    KLS - With each question, add the skill(s) that are tested. And For every question choose exactly {2} skill(s) and not more or less than {2} should be chosen for each question. The skills for all the questions should be unique.
    The Question, Custom Prompt, KLP, KLS should be numbered.

    Here the format looks like :

    "Title",

    "Description",

    "Question 1",

    "Prompt 1",

    "Takeaway 1" ,

    "Skills 1" repeated for {3} question(s). Do not include any {{responder}} response.

    NOTE : Based on this information {{information}} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - "Rating : 6". Do not include any other explanation.

    NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description. 
    NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated. Each skill shall only be one word.
    NOTE: Never miss Title, Description.
    NOTE : Make sure the simulation is very advanced and tough.
        """
        
        
    scenario = create_scenario_from_site_context(None, access_token, tenant_id, json.dumps({'title': "",'data':{'information':''}}), origin=source, competency=competency, creator_user_id=creator_user_id, custom_prompt=simulation_prompt)
    
    return scenario



def simulate_llm_resposne():
    prompt = """
        \n\nHuman:\n        
        {Information} - ${coach_information}
Conversation History : ${conversation}

Context : ${intake}\n        
Personality: None\n        IDP: None\n        Action Plan & Session Notes: None\n\n        Read this {Information} thoroughly and understand it deeply. Act as the individual described in the provided information, mimicking their 
personality traits, speech patterns, and values throughout the responses. Understand the given instructions before creating a response. ALWAYS follow these instructions to generate the responses :\n        1. Act as the person whose information is given here {Information}. Include details about their background, achievements, and notable personality traits.\n        2. Analyze the personal stories, or responses given in {Information} to identify the person's speech patterns, vocabulary, and storytelling style. Utilize this information to generate conversational responses that reflect the user's natural language and tone.\n        3. Analyze the \"Speech Patterns\" and vocabulary of the person from the given FAQs given here {Information} and model it when creating the response. Pay 
attention to their tone, expressions, and commonly used phrases to ensure authenticity.\n        4. Use their \"Values and Beliefs\" given here {Information} to ensure that generated response aligns with their worldview and perspectives.\n        5. Integrate their \"Frequently Used Phrases\" given here {Information} while generating the responses.  Weave these phrases seamlessly into the responses, ensuring they feel natural and consistent with the individual's communication style.\n        6. Analyze the \"Emotional Expressions\" from the given FAQs  given here {Information} to mimic emotional nuances while generating the responses, ensuring that the response reflects the person's emotional range and communication style accurately.\n        7. Analyze the \"Life Experiences\" given here {Information} . Draw on these experiences when crafting personalized narratives or offering advice, creating a deeper connection with the coachee and enhancing the realism of the responses.\n        8. Analyze and imitate the \"Problem-Solving Approach\" given here {Information} to generate a response that reflects the person's decision-making style and problem-solving approach to resolve situations.\n        Use all the information provided here {Information} to act as the coach and respond to the coachee. \n\n   
     Conduct a session with a coachee who is sharing their concern in this context {context}. Understand the coachee's concern and problem before providing any advice or solution in the response. The response should be directly related to the concern shared by the coachee.  The personality of the coachee is given here {Personality}. Understand the coachee's personality and always tailor your response accordingly.\n        Understand the coachee's perspective to the question and provide the information they want. \n        Offer advice, coaching, and mentoring based on the coach's style and character traits given in {Information}. Consider any other relevant information to provide comprehensive coaching advice. \n        Provide a response based on all the information you have on the coach. Always provide accurate information about yourself as the coach when asked by the coachee. \n        The response should always be directly related to the question. \n        If the coachees' Individual Development Plan is given in the IDP, make sure the response is based on that information.\n        If the coachees' Action Plan is given in Action Plan, make sure the response is based on the plan provided and it should be short and precise.\n        Consider the prior conversation given in Conversation History when providing the response.\n        Offer actionable advice or solutions to the coachee\u2019s potential challenges.\n   
     Break down complex ideas into practical steps.\n        Pose questions to the coachee to create engagement.\n        Encourage 
self-reflection or thought-provoking moments.\n        Maintain a tone that feels friendly and approachable.\n        Use the Custom Knowledge base here {Information}. Always refer to {Information} first, before providing a response. \n        Never provide any answer about a subject the coach is not familiar with. If the user asks any questions about a subject that is not mentioned in  {Information} as Areas of expertise, please respond that you are not familiar with the topic.\n\n        Always provide the response in a 
first-person tone.\n        Always ask a contextual question at the end to further understand the details.\n        Always respond as the coach.\n        NEVER give visual cues like smiles warmly etc.\n\n        NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output. Start directly with the response and only provide the 
response.\n        NOTE : Always assume suitable details to respond, never respond with unfortunately I can't provide an answer to that question.\n\n        NOTE: Make sure to keep the response short. Get straight to the point without unnecessary elaboration or repetition. Eliminate redundant phrases or ideas that don't add value to the response. Choose words and phrases that convey your message clearly and directly. Make sure to give short answers but do not miss out any necessary information.\n\n        NOTE: Provide concise responses without exceeding a brief length constraint. Aim for brevity while delivering complete information and answers.\n\n  
      \n\nAssistant:\n\n

        """


    

    # print(anthropic_completion("what is value engineering?",1000))
    # print(gpt3_completion("what is value engineering?",stop=['user','coachbots']))
    questions = [
        "How do you approach guiding individuals through significant life transformations, considering the unique challenges they may face at different stages of life?",
        "In your experience as a senior coaching practitioner, what strategies have you found most effective in fostering sustainable and meaningful change in your clients' lives?",
        "Could you share a particularly impactful success story where your coaching significantly influenced someone's journey towards personal growth and transformation?",
        "Methodology?",
        "Successes?"
    ]
    intakes= {
"Please let me know more about you as a person that you think might be relevant to our session today.": "I am a straightforward person who likes to get to the point, very precise and short answers to my questions. I prefer when people validate their approach before jumping on to provide solutions.",
"What do you want to achieve with your session with me today - let me know the goals you have in mind.": "I want to solve for how do I go about finding focus in my life.",
"What specific problems you are facing currently that are a priority for you? What have you tried so far in terms of finding your solutions?": "I easily get distracted with so many goals that I have set for myself.",
"Do you believe your solutions have worked so far? Why or why not?": "Haven't really given it much thought."
}   
    intake = ""
    for key, value in intakes.items():
        intake += f" Question: {key}, Answer: {value} \n"

    coach_data = {
        "media_data": {
            "extracted_from_article": {
                "https://hbr.org/2023/12/8-essential-qualities-of-successful-leaders": "Becoming a great leader is a journey of continuous learning and growth. It’s a process — one that thrives on embracing challenges, seeking feedback, fostering connections, and cultivating understanding. In this article, the author outlines the eight most essential leadership qualities, according to Harvard Business School professor Linda Hill, one of the world’s top experts on leadership. Star leaders aren’t born with superhuman capabilities, Linda explains. Rather, they tend to have intentionally put themselves in situations where they have to learn, adapt, and grow — a crucible for developing the tenacity and fortitude to motivate and guide others."
            },
            "extracted_from_youtube": {
                "https://www.youtube.com/watch?v=vLFxOOEyhUE": "okay hi everyone oh god you're like a bunch of high school kids in the morning my name is John Muldoon that was quite the intro by the way thank you I am the principal of the high school here on the pusci campus of Shanghai American school and I'll tell you I'm also I'm a little nervous to be standing up here today i-i've still in this stage a lot this year and I've talked with a lot of different people but there's something about that like red-dot back there on the ground that is intimidating and part about my part of what I'm going to talk about tonight is about being honest with yourself and other people and so I figure what better way to start then say that I'm a little nervous by be and be honest with you ah see you laughed a lot during the last one which I think makes the bar pretty high for me so here's the thing I I'm gonna talk to you a little bit about and I there's a disclaimer here in a very unscientific art of why I'm nervous as I saw our school psychologist out here and I'm sure there is yeah so I'm sure that the psychologist in the crowd is going to be very analytical with the advice I give all of you so I hope none of it is malpractice here's the thing our brains are supremely powerful organs and we don't often think about how we're using them right I actually I can pinpoint the first time I actually thought about how we use our brain I was in sixth grade so has in sixth grade and I'll be asked to do my family's going through a really hard time a really horrible time actually and we're spending a lot of time in the car so my dad's driving him and I'm sitting next to him up front my sister and my brother and I are in the back cramps it's always a good recipe for something right and my father is compulsively listening to motivational tapes right yeah cassette tapes right yeah so he's listening cassette tapes with all these people who are telling me and my family through the speakers of the car how great life is and how awesome we are and how everything is gonna be amazing it was like the worst great hey it was objectively the worst thing ever and totally not what I wanted to hear when I was going through some horrible things that I could not control and I'll never forget I remember this one and particularly this guy I chefs my dad if you still as a team so this guy says that the key to happiness is to talk to yourself but not just like talk to yourself right to say like really great thinks yourself he's like you should wake up every day this and it sounded so ridiculous to actually listen to it right he he's like you get up every day and you go to the mirror and you look at yourself and you're like you look good today is gonna be awesome right hey said if you do this all the time you'll actually get little voices that develop in your head that say nice things to you all day long and so here I am I'm like 11 or 12 years old and I'm like training your brain to get little voices that talk to you all day long yeah like I'm pretty sure that's the mark of something not good right I mean I can't tell how many fights we had about this as a family mostly started by me right like why can't we just listen to the radio like a normal family but I'll never forget it part of it is because we were going through what was probably the darkest chapter of my father's life and he was show he chose to listen to somebody tell him good things it was a choice he made I didn't understand that back then so you fast forward a little bit I had just become an assistant principal in my life right so I guess we're fast working a lot I'm feeling pretty good and I find out that my favorite teacher ever my 6th grade social studies teacher is retiring so I'm like I'm gonna stop by and see him that day like that day I found I drove to the school I didn't tell him I was coming I just went I don't know why I did he was my favorite teacher he helped me through so much in that same time period in my life when I went through so much so I I just walked no one stopped me it was amazing I walk right down the hallway right to his old classroom he's still there like he always was right I opened the door and I go in he looks up at me and he goes holy hell well actually that's not what he said I can't tell you what he said on the stage but he said something like that and he comes over and he gives me this big hug and he says John Muldoon I can't believe you're still alive right and I'm like are you confusing me with another John Logan but but he wasn't and actually the truth is that he was he was right we talked a lot about it he only knew me at that time period in my life well I and I got I'll be tell you I was so angry right and he he our parting thought he left me with so he's not around anymore it's a little sad to think about but the party thought that he left me with was how proud he was of seeing me and how happy I seems because he said in over 35 years of teaching he had never met an anger kid than me and it's kind of funny but it's also kind of tragic that I remember him so fondly and I think about that's his memory of me of like all the anger anyways the change didn't happen overnight for me if you fast forward a little bit or actually rewind from when I became an assistant principal I was in ninth grade I was in high school things were still not going well for me I was actually angrier than I had been in sixth grade was just saying something I didn't have any friends I mean I was so isolated my grades were awful they got I am not ashamed to tell you I was just about to fail out of high school by the middle of the year of my freshman year and I had the assist my history teacher another history teacher that took an interest in me right it's probably my second favorite teacher maybe why I became a history teacher myself actually and he was like a Jedi right like I actually like I owe this man my life he conducted what I can only call psychological warfare on me he got me so angry that he tricked me into wanting to do well at school I don't know how he did it like I think about it now I have no idea how it happened but it did in the trip I mean like please do not underestimate the magnitude of this transformation I was talking with my counselor about how I was not going to be coming back to school next year if I didn't turn things around right and and all of a sudden I was getting all A's and B's and I was being nicer to people and I actually maybe was working my way towards making friends right like actually yeah whatever I the transformation it was so severe my father sat me down and he asked me if I was on drugs right like and that's pretty messed up when you think like like son you know your grades have just gotten really good and you know it looks like maybe you have some friends now and you're not so miserable to be around are you on the drugs greatly that's that's actually how it went but this rosy period in my life was not destined to last because as I think everybody here knows you really can't trick a halfway intelligent teenager into doing something they don't want to do for too long and so by the end of the year the the gig was up and I had this huge confrontation with this teacher which like if we're being asked was not smart I mean to pick a verbal fight with a like Jedi psychological warfare mind master but I left the Year feeling so angry and deflated and confused and and thinking though is the key word I left the year thinking like how did this happen and I was thinking about it because I was so angry they did that myself actually that I had let him trick me and so I didn't know it at the time but I was in search of an epiphany and I wish I could tell you that it happened and it was amazing and it was like this moment that changed everything right away and it was on top of a mountain and right but that's actually it's not how it happened it I was at work at this Lake horrible summer job and it wasn't something that happened and changed my life right away but I'm standing there I'm at work and this mom comes in with this little kid and he's given I was like little matchbox model cars right you know what I'm talking about she's got this little matchbox car and I hope you're ready for this it was a model of my dad's old car like the same crazy sparkly gold paint with the weird white roof like it was though it was a model of my dad's old car I could practically hear the tape of the guy with the voices in your head talking to me right like my brain hurt when I saw that car and I I'm like this it's all within a week of getting out of school and I stand there there's no coincidence in my mind it cannot be a coincidence that this guy tricked me tricked my brain and I thought I was pretty smart he tricked me into doing something I didn't want to do and then a couple days later I'm reminded of this other time in my life where someone told me you can trick your brain into doing anything so I started thinking about it there has to be a connection and I know now and we all know now there is a connection right your brain is so powerful there are so many studies in your brain there's a lot of studies on the patterns of thinking in your brain and the words that emerge and the patterns of that thinking literally how you talk to yourself and the power of it you know some of these examples I'm gonna share with you are fresh in my mind cuz I was just reading an NPR article but there's so many you should look at them 19:11 the scoober psychologist and most people think this is when we first really started thinking about patterns of thinking by accident one day they noticed and I guess in 1911 like really fashionable for a woman to wear really big hats right so they noticed that women when they walk through doorways with these hats on they had to dock and kind of tilt their head they did it even when they didn't wear their hats and they were like why is that so they studied it and they figured out that if you have a pattern that established itself in your brain absent a conscious decision not to do it you'll do it it's not rocket science right it's pretty deductive for us now there's a lot of studies on it there's another one about doors oddly enough right in 2013 there's a group of scientists that are working with young woman that have anorexia and they notice that they don't walk through the door the way they were expecting them to despite the fact that all of them were on the smaller side and the doors were double doors like we have the back the auditorium here they walked through sideways like they were sneaking past someone right or squeezing through despite the fact that there was plenty of room so they looked at it they added it to their study expanding the scope of their study and they wanted to figure it out and they found that they had such patterns of disordered thinking in the brain that it influenced so many of their behaviors and the crazy thing of like how they walked through doors and the crazy thing about it is that they had no idea that they had these patterns of thinking running that way in their brain and they were not aware of the influence on their behavior all the time you know there's so many there's another one and then I'll stop sharing studies with you there's one from the University of Pennsylvania they actually found when they studied football players that by imagining throwing a football properly you have a similar performance gain to when you actually practice it physically that's crazy right you can you can practice doing something in your mind and it has not quite the same magnitude of effect but a similar effect it's doing it physically is really unbelievable now I didn't know any of this then right I didn't know that the patterns in your brain start being established when you're young all of the messages that you all hear when you're when you were younger all the messages that you hear right now even the ones you're not aware of they get in somehow and the more you hear something the more it takes root the more your brain accepts it even if you disagree with it and these roots grow and if we use the kind of vernacular from the audio cassette guy that's when the voices start right that's when you start having patterns of behavior influence other ways that you think the way you feel and the things that you do this is why some people and we see this right we all know people like this they've been told from when they were really young that if they work really hard and they don't give up that they can do anything right those people act differently and then people they get it the opposite message that they can never do anything right even though they probably disagree with the message that they can never do anything right take it another level and this is when like thinking about it I wonder if I've really lost my mind sometimes the voices in your head if that's what we're calling them they talk to each other they're having a conversation in your head I'm a visual thinker so I like to think about it like speed-dating event right we're in a big auditorium and all these little like positive and negative patterns of behavior moving from table to table talking to each other and what happens is when they're interacting with each other the positive patterns lessen the effect of the negative patterns the negative patterns lessen the effect of the positive patterns right it's in Crimea it makes sense but it's incredible and this when you like look at it on a macro level is why someone who's supremely positive bounces back from bad news much faster than someone who's not they are less fazed by a setback in their life because they have a lot of other positive thought processes that counteract the negative impact of it it doesn't make them less likely to understand what's happening but they feel differently about it and they might act differently the converse is true right the sweet sweet joy of an unbelievable moment in life might be fleeting for someone that has predominantly negative thought patterns anyways I didn't know any of this when I was 15 right but I had listened to a lot of motivational tapes back in the day so here I am I am going to conduct an experiment I decide on myself we have a scientist out there I just like shaking his head no you can't conduct an experiment on yourself but I was 15 right I'm using experiment and research very loosely and so i decide i am going to get cool right but not just like cool like ridiculously cool and and here's the thing like it's really hard to believe i wasn't cool in high school right my students are telling me this right now but the truth of the matter is i was so not cool and I knew it and that's okay I own it so I'm like I'm gonna do exactly what that guy in the tape said I should do so I woke up and and so none of this is a surprise to anyone that knows me I'm a very intense person right I woke up every day and I looked in that mirror and I told myself how amazingly cool I was right I was like the best-looking coolest kid that went to my school and and I this is actually really embarrassing but I mean my wife said I shouldn't share this part but I'm going to share this part I actually got blue paint blues my favorite color and I I painted on the wall across from my bed four big letters c ool right and I'm like I'm going for broke and then I don't know if it's because I was 15 if it's because I was like desperate for something positive in my life or what but after a while I convinced myself that I was in fact pretty cool right Jeremy our school psychologist now you're gonna have to unpack that later but and then something amazing happens cuz we all know right like I didn't really change that much about me I was changing the way I was thinking about me but my sister my younger sister who by the way was super cool and always really popular she comes bursting through the door one day while I'm singing my bed literally talking to myself about how cool I am and she just like can't take it anymore she's like you are so not cool if you have to tell yourself that you're cool you are not cool even worse if you have to tell other people that you're cool you're hurting yourself even more and then like I know she's amazing now but at the time oh my god right she looks at me and she's like maybe and this is brilliant she didn't mean it to be brilliant but it was brilliant maybe you should not try to be cool maybe you should just try to be happy for a little bit so that we're not all miserable being around you right harsh so she leaves and not the norm for me at the time I didn't react I just kind of sat there in my bed like crushed my experiment of failure thinking about how uncool iam but also thinking like it's not that I don't feel happy I also don't feel unhappy and that was so weird for me to think about and I realized and I had never like thought about it like my my predominant emotion my like real only emotion that I was consistently feeling was anger I was mad and and I did the smartest thing I've ever done in my life still to this day I asked myself why why was I so mad and I went all the way back it's a sixth grade and I started think about all the things that had happened and how they were all out of my control I was pulling it all the threads it was horrible it was painful to think about and it I I didn't pick up another experiment right away took me a little while as I'm thinking about all this thinking about how I was thinking and think about how I was feeling but eventually I decided that I couldn't take my sister's advice I couldn't try to be happy was just too big right I was gonna do a second experiment I was just going to try to be thankful for some things in my life there were good every day but I attacked it with the same intensity I attacked trying to be cool right so like I I mean I was an animal I was thanking everyone for everything right you let me borrow a pencil was the best thing that ever happened to me right and and I mean like I would show up in your doorstep five years after you did something if I was grasping at straws for something to thank someone for and I would thank you for something you did five years ago and and people didn't really know how to take me it was kind of like back when I had that rapid transformation during the school year nobody knew who what was going on with me nobody could explain it some people actually thought when I thanked them for things I was making fun of them and actually my dad asked me if I was on drugs again but something this this was like the watershed moment in my life I actually started to realize there were so many good things in my life that I was missing because I was so busy being angry at everything and I also realized that thinking about how is always anger things helped me realize when I was getting angry and stop it and I actually was feeling happier right so while I'm going through all this I start making all of these rules like these rules for life I I call them like trade secrets for not being a jerk right actually that's pretty negative I call them trade secrets we can call them trade secrets for like being a good person and I can share some of them with you let's share two of them the first one is what I've been doing every day since I was 15 years old my first rule I give sincere thanks three times a day three times a day that's it right now I do it a lot more than that but I give sincere thanks three times a day the second rule is be great and it's not like be great like objectively oh he's great that's not what it is right this is something I subject everybody here to all the time if you ask me how I'm doing right like ask me how I'm doing I'm great I'm the best I've ever been I'm living the dream these are all things I say every day the people when they ask me how I'm doing but that's actually not where it stops right like sometimes people tell you to do that like everyone hears it like fake it till you make it right that's a lie you're lying to yourself I'm not saying I'm great because I'm trying to convince myself I'm great I respond so over-the-top so positive because that's a signal to me it's actually a moment that I take every time somebody asked me how I'm doing to check in how do I actually feel and most of the time I feel really great I'm an intense person we've already established that so I feel really great and that's awesome 99.9 percent of the time I'm not lying to you point one percent of the time I don't know I say I'm great I might not actually feel great I might take a second and I might look at you and I might say actually I'm not feeling great and depend on how well we know each other I might say more I might not I don't know but think about how many times a day you were asked how you are or what's up that's how many times a day I think actively about how I'm feeling and why I'm feel and next up what am I gonna do about it because if we don't actively manage these patterns in our brain they manage to us and if you don't think about how you're gonna do that if you don't have a system or something that works for you you're just letting it go you're just letting things happen I couldn't clearly write we saw where that got me in my life I couldn't do it so there's a couple things that go with this right I told you there's a very unscientific Chua lis have a way that they type in behavioral sciences have a way that they talk about this and I never say them in the right order so I have a flashcard what they actually say is that the first thing you do is that you have to identify the emotion in the pattern right you have to recognize you're having it you have to put a name on it I'm angry I'm sad and whatever the second thing is you have to source it it's not enough just to say I'm angry why are you angry where's that anger coming from you have to pull it those threads it's not easy takes time it's pretty painful sometimes the next thing you have to do is identify what you actually want to be if you're sad do you want to be happy that's also not so easy sometimes and then the next one and this makes us sound awfully like you're a computer you have to consciously manage the way you think about that thing and the pattern that controls those things in your brain so that you like overwrite the bad pattern with the good pattern new pet old pattern with the new pattern and that's how you go about changing the way your brain works from a very unscientific I used to call this mind over matter right that was like my mantra when I was growing up mind over matter today's gonna be great I'm gonna make it great but I don't call it that anymore I call it being your own coach I think it's much more accurate we all deserve a great coach in our life we should start with ourselves it's hard work being a coach is really hard work I've coached a lot of things in my life to do it well it's really hard anyone can be a coach but to be a really great coach the kind of coach you want that's a lot of work gonna be your own coach forget it's a full-time job but it's worth it I mean my sixth grade teacher thought I was gonna die before I was 30 that's horrible I used to teach sixth grade I never thought that about any of my kids even the ones that I was really worried about so this isn't the system for everyone this is what worked for me the power of your brain is undisputed you can't just let it do its own thing you need to think intentionally about what's going on in there you also need to be aware there are a lot of critics to what I'm talking about right now right there's a lot of critics for all the resources out there there are people that say that you're deceiving yourself when you do this it's not really honest and I have two answers for that the first answer is that this is all about honesty it doesn't work if you're not honest right if you wake up every day and you're just trying to be cool right or you tell yourself that you're great when you're not and you don't think about why you're not really great how you really feel doesn't work so the deception critique doesn't hold up for me but if I'm being asked today I asked I don't care right this works for me like I just said my sixth grade teacher thought I was gonna make it I was so unhappy and angry that's no way to go through life I don't want to say that thinking like this and finding this way in the system that works for me save me from death but definitely saved my life in more ways than it didn't and I'm so profoundly thankful for all the happy little accidents along the way of my life that helped me to stumble onto it so think about your thinking listen to the voices in your head and be your own best coach thank you for having me tonight [Applause]"
            }
        },
        "additional_data": {
            "department": "External",
            "experience": "10 - 15 years",
            "area_domain": "Life Transformation",
            "profile_type": "icons_by_ai",
            "article_links": "https://hbr.org/2023/12/8-essential-qualities-of-successful-leaders",
            "youtube_links": "https://www.youtube.com/watch?v=vLFxOOEyhUE",
            "admired_leaders": "Brene Brown, Simon Sinek",
            "profile_description": "I am an experienced psychologist and certified life coach with over 10 years of experience in behavior analysis, competency modeling, and coaching. As an ICF-accredited professional certified coach (PCC), she specializes in utilizing psychometric assessments, ability tests, and techniques like REBT and NLP to provide impactful coaching. \nGopika has designed and implemented assessment processes, tools, and frameworks to evaluate behaviors, personalities, and competencies. She conducts development centers, 360-degree feedback, and counseling sessions focused on capability building. \nHer experience includes coaching and counseling corporate executives, managers, and employees across industries to help them become more effective leaders. She is adept at situational leadership, is empathetic, and is passionate about enabling positive behavioral change in her clients to drive superior performance. (Names are changed on request to protect privacy). ",
            "mentoring_frameworks": "Situational Leadership Model\nEmotional Intelligence Coaching\nSolution-Focused Coaching",
            "mentoring_preferences": "Coaching (Reflection)",
            "dominant_point_of_view": "Empathy and self-awareness are foundational for effective leadership and personal growth. By understanding ourselves and others, we can drive positive change and achieve superior performance.",
            "problem_solving_approach": "In terms of problem-solving, my general approach revolves around facilitating deep reflection, challenging limiting beliefs, and identifying practical strategies for overcoming obstacles. I utilize techniques like Rational Emotive Behavior Therapy (REBT) and Neuro-Linguistic Programming (NLP) to empower clients to navigate challenges, embrace discomfort for growth, and adopt new perspectives. I create a safe and non-judgmental space where clients can explore and address their concerns, ultimately driving meaningful behavioral change and sustainable growth in their personal and professional lives.",
            "provide_answers_using_emojis": False,
            "discuss_how_you_helped_others_in_coachMentoring": "Context Action Result (CAR) #1:\nContext: Sarah, a young professional struggling with career dissatisfaction, reached out to Gopika for guidance in exploring a career change. \nAction: Gopika conducted thorough assessments of Sarah's skills, interests, and values. She provided resources to help Sarah identify alternative career paths aligned with her passion for writing.\nResult: Sarah successfully transitioned into a new role in content creation, finding fulfillment and renewed motivation in her career.\n\nCAR #2:\nContext: John, a working father, felt overwhelmed by the demands of his job and family responsibilities, leading to burnout and stress.\nAction: Gopika worked with John to create a personalized work-life balance plan, emphasizing task prioritization, time management strategies, and boundary setting.\nResult: John achieved a healthier work-life balance, experiencing reduced stress levels, improved productivity, and strengthened relationships with his family.\n\nCAR #3:\nContext: Emily and Mark, a couple facing communication issues and conflict struggles, sought help from Gopika to enhance their relationship.\nAction: Gopika facilitated couples counseling sessions focusing on communication skills, empathy-building exercises, and conflict resolution techniques.\nResult: Emily and Mark developed stronger communication skills, a deeper understanding of each other's perspectives, and a more harmon"
        }
    }
    
    coach_info =''
    for key, value in coach_data.items():
        coach_info += f"{key}: {value}\n"

    
    conversation_history = {}
        
    # for index, que in enumerate(questions,start=1):
    #     history = ""
    #     for key, value in conversation_history.items():
    #         history += f"User: {key}, Coach: {value}\n"


    #     prompt = Template(prompt).substitute(conversation=history,
    #                                             coach_information = coach_info,
    #                                             intake = intake
    #                                             )

    #     # response = anthropic_completion(prompt,1000)

    #     # print(f"(Anthropic){index}   User: {que}, coach: {response}")

    #     # response = gpt3_completion(prompt,stop=['user','coachbots'])

    #     # print(f"(gpt){index}   User: {que}, coach: {response.text}")

    #     response = gemini_competions(prompt)

    #     # print(f"(gemini){index}   User: {que}, coach: {response}")

    #     conversation_history[que] = response

    # h = ""
    # for key, value in conversation_history.items():
    #     h += f"User: {key}, Coach: {value}\n\n"

    # print('rsponse',h)

    signature_bot = SignatureBot.objects.get(deleted=False,bot_id="avatar_bot-87b15-lyfe.-life-transformation-by-a-senior-coaching-practitioner.")
    provide_answers_using_emojis = signature_bot.data.get('additional_data')
    if provide_answers_using_emojis:

        provide_answers_using_emojis = provide_answers_using_emojis.get('provide_answers_using_emojis')
        print(provide_answers_using_emojis,'a')
    else:
        provide_answers_using_emojis = False

    # if provide_answers_using_emojis:

    prompt  = prompt.split('Assistant:')
    prompt.insert(-1, f"Note: Always use emojis and icons in response to make the responses lively where applicable. \n\nAssistant:")
    prompt = '\n'.join(prompt)
    print(prompt)





def summaries():
    from coaching_conversations.helpers import get_bot_conversation_data_user
    tenant_id = '62d76be2-b439-4528-9ae4-2af389abb5f5'
    bot_id = "fcd73746-845b-4349-a4c7-53eb46fa7f57"
    user_id = "ae8981a7-bcad-42c8-9c57-1f0df47b5182"
    tenant = Tenant.objects.get(uid=tenant_id)
    sessions = TestAttemptSession.objects.filter(deleted=0,tenant_id=tenant_id,test_id=bot_id,participant_id=user_id)
    conversation_data = get_bot_conversation_data_user(sessions,tenant,user_id,only_converation=True)
    conversation_history = [{"coach": i['coach_message_text'], "user":i['participant_message_text']} for i in conversation_data]
    print(conversation_history)
    print("="*10)

    summery = get_conversation_summary(conversation_history)
    print('summary',summery)
    print("="*10)

    for s in sessions:
        if s.conversation_summary:
            print(s.conversation_summary)
            print('='*10)


    

def update_scenarios(test):

    title = test.get("Title")
    description = test.get('Test description')

    question = []
    prompt = []
    kls = []
    klps = []
    for key, value in test.items():
        if key.startswith('Question'):
            print(key)
            question.append(value)

        if key.startswith('Custom Prompt'):
            print(key)
            prompt.append(value)

        if key.startswith('KLS'):
            print(key)
            kls.append(value)

        if key.startswith('KLP'):
            print(key)
            klps.append(value)


    print(f"title: {title}, desc : {description}")
    print(f"{question}, {prompt}, {kls}, {klps}")

    code = test.get('Test code')
    test_obj = Test.objects.get(deleted=False,test_code = code)

    print(test_obj.title)
    print(test_obj.description)
    print(test_obj.skills_to_evaluate)
    skills = []

    for s in kls:
        skills.extend([sk.strip().capitalize() for sk in s.split(',')])

    skills = ",".join(set(skills))
    print(skills)
    test_obj.title = title
    test_obj.description = description
    test_obj.skills_to_evaluate = skills

    test_obj.save()

    test_ques = TestQuestion.objects.filter(test_id=test_obj.uid)

    for index, que in enumerate(test_ques):

        print(f'{index}{que.question}')
        que.question = question[index]
        que.gpt_prompt_override = prompt[index]
        que.key_learning_point = klps[index]
        que.key_learning_skills = kls[index]

        que.save()

        print(f"""
         {question[index]},
         {prompt[index]},
         {klps[index]},
         {kls[index]}
        """)


    print(f"{'*'*100}{code}")



def get_low_skill_scenarios(tenant,test_codes=None,min_skill_count=4):

    scenarios = []
    tests = Test.objects.filter(deleted=False,tenant_id=tenant.uid)

    if test_codes:
        test_codes = [test.strip() for test in test_codes.split(",")]
        tests = tests.filter(test_code__in=test_codes)


    for test in tests:
    
        skills_to_evaluate = test.skills_to_evaluate

        if skills_to_evaluate:
            unique_skills = set([skill.strip() for skill in skills_to_evaluate.split(',')])
            if len(unique_skills) < min_skill_count:
                scenarios.append({
                "Test Code": test.test_code,
                "Skills": ",".join(unique_skills),
                "Skill count": len(unique_skills)
            })


    return scenarios



def set_is_micro():
    print("################# Process started ################3")
    tests = Test.objects.filter(tenant_id="62d76be2-b439-4528-9ae4-2af389abb5f5",deleted=0)
    dynamic_change_count = 0
    static_change_count = 0
    print("########## Total tests fetched : ",tests.count())
    for test in tests:
        if test.test_type == TestTypeChoices.dynamic_discussion_thread:
            questions = TestQuestion.objects.filter(tenant_id="62d76be2-b439-4528-9ae4-2af389abb5f5",test_id=test.uid,question_for='user')
            if questions.count() == 3:
                test.is_micro = True
                test.save()
                dynamic_change_count += 1
        
        if test.test_type == TestTypeChoices.test:
            questions = TestQuestion.objects.filter(tenant_id="62d76be2-b439-4528-9ae4-2af389abb5f5",test_id=test.uid)
            if questions.count() == 3:
                test.is_micro = True
                test.save()
                static_change_count += 1
                
        print("********* Records Changed  ********")
        print(f"Dynamic : {dynamic_change_count},    Static : {static_change_count}")
        print("************************************")
        
def search_keywords(text, keywords=['Simulation', "Role play"]):
    # Combine the keywords into a single regex pattern
    pattern = '|'.join(re.escape(keyword) for keyword in keywords)
    # Use re.IGNORECASE to make the search case insensitive
    matches = re.findall(pattern, text, re.IGNORECASE)
    return matches

def replace_words(text):
    if not text:
        return text
    # Define replacements
    replacements = {
        r'\broleplay\b': 'Act',
        r'\brole play\b': 'Act',
        r'\bsimulation\b': 'mimicry',
        r'\bsimulations\b': 'mimicry'
    }
    
    # Replace each word using regex, case-insensitive
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text


@timeit
def generate_psychometric_report_data(test:Test,test_attempt_session:TestAttemptSession):

    prompt = """
    ### SCENARIO
    Use this scenario: 
    ${title}
    ${description}

    ${qna}

    ### PERSONALITY EVALUATION
    Act as an ideal personality analyst, providing an in-depth analysis based on the given scenario. Use the personality dimensions and scores provided to deliver a score report. Include the following sections in your response for each dimension:

    1. Dimension Overview: Analyze the specific dimension, do not mention.
    2. Dimension Scale: Reference the scale from 1 to 9, defining the polar traits, do not mention the scale.
    3. Your Score: Reflect the user's score for the specific dimension.

    Always comply with giving the response in the PERSONALITY DIMENSIONS FORMAT.

    Additionally, always print the response only in the PERSONALITY DIMENSIONS FORMAT below, with no other visual cue or heading title or end summary. No place shall go blank; assume and provide results for every scenario.

    ### PERSONALITY DIMENSIONS FORMAT
    ${personality_dims}

    """
    responses = TestQuestionResponse.objects.filter(
        deleted=False,
        test_attempt_session_id=test_attempt_session.uid
    ).order_by('created')

    # Create a dictionary mapping question IDs to question texts
    question_ids = [response.question_id for response in responses if response.question_id]
    questions = {question.uid: question.question for question in TestQuestion.objects.filter(uid__in=question_ids)}

    # Build the Q&A string
    qna = ""
    for response in responses:
        question_text = questions.get(response.question_id, "Question not found")
        qna += f"Q: {question_text}\nAns: {response.response_text}\n\n"

    
    per_dims = ""
    num_of_sections = 0

    section_dict = {}
    if test.psychometric:

        # Iterate over each PsychometricItem associated with the Psychometric set
        for item in test.psychometric.psy_items.filter(deleted=False):
            # Append the subsection to the list for the corresponding section
            if item.section not in section_dict:
                section_dict[item.section] = []  # Create a new list for this section
            section_dict[item.section].append(item.subsection)  # Add the subsection

        logger.info(f"sections: {section_dict}")
        # Build the output string from the section dictionary
        num_of_sections = 0
        for section, subsections in section_dict.items():
            params = ", ".join(f"{subsection} - Score [Score]" for subsection in subsections)
            per_dims += f"{section}: {params}\n"

        num_of_sections = int(len(section_dict))

    else:
        for key, value in test.pshycometric_sections.items():
            params = ", ".join(f"{param} - Score [Score]" for param in value)
            per_dims += f"{key}: {params}\n"

        num_of_sections = len(test.pshycometric_sections)
        section_dict = test.pshycometric_sections

    logger.info(f" parameters:  {per_dims}")

    prompt = Template(prompt).substitute(
        title=test.title,
        description=test.description,
        qna=qna,
        personality_dims = per_dims
    )

    result = {}
    errors = []
    llm_order = ['gemini', 'anthropic', 'gpt']

    # Outer loop for psychometric generation attempts (max 3 times)
    for attempt in range(1, 4):
        logger.info(f"====================Generating psychometric for {attempt} time, order: {llm_order}")
        
        # Inner loop for the psychometric report generation (max 3 tries per attempt)
        for inner_attempt in range(1, 4):
            try:
                logger.info(f"Generating psychometric report data for attempt {inner_attempt}.")
                
                # Call to generic completion function with necessary parameters
                response = generic_completion(
                    prompt=prompt,
                    is_free=test.is_free,
                    top_p=0,
                    temp=0,
                    llm_order=llm_order
                )
                
                # Parse the result and break out of the inner loop on success
                result = parse_personality_dimensions(response, num_of_sections, section_dict)
                
                # If the inner loop is successful, break both loops
                logger.info(f"==========================Successfully generated psychometric report for inner attempt {inner_attempt}.")
                break  # Exit the inner loop
                
            except Exception as e:
                errors.append(str(e))
                logger.exception(f"Failed to generate section for inner attempt {inner_attempt}, reason: {e}")
                
                
                # If we reached 3 failures, log and break out of the inner loop
                if inner_attempt == 3:
                    # Rotate llm_order to the right (shift elements to the right)
                    llm_order = llm_order[-1:] + llm_order[:-1]
                    logger.error(f"=======================Failed to generate report after {inner_attempt} attempts. Skipping to next psychometric generation.")
                    break  # Exit the inner loop after 3 failed attempts
                continue  # Continue to next inner attempt on failure
        
        # If the inner loop was successful, break the outer loop as well
        if len(result.keys()) > 0:  # This means the inner loop broke successfully (not due to failure after 3 attempts)
            logger.info(f"Psychometric generated successfully for {attempt} time.")
            break  # Exit the outer loop as well
        else:
            logger.error(f"All attempts failed for psychometric {attempt}. Moving to the next.")
            continue  # Continue to the next psychometric generation attempt


    logger.info(f"psychometric json: {result}")

    if not result:
        send_error_notification(module='generate_psychometric_report_data',
                                msg=f"Failed to generate psychometric report data.",
                                data=errors)
        raise ValidationError(f"Failed to generate psychometric report data. reason: {errors} ")

    test_attempt_session.pshycometric_data = result

    test_attempt_session.save(update_fields=['pshycometric_data'])


    generate_culture_rating(test=test,test_attempt_session=test_attempt_session)

    return result

def generate_culture_rating(test:Test,test_attempt_session:TestAttemptSession):
    responses = TestQuestionResponse.objects.filter(
                        test_attempt_session_id=test_attempt_session.uid,
                        deleted=0
                    )
    
    if test.calculate_culture:
        culture_skills_rating = calc_culture_skills_rating(test_attempt_session, responses, test)

        logger.info({"***************************culture_skills_rating_score":culture_skills_rating})

        culture_skills_rating = update_culture_skills_if_same_scores(
            culture_skills_rating)
        updated_fields = []

        if culture_skills_rating is not None:
            culture_skills_rating = {key.strip('"\'' ): value for key, value in culture_skills_rating.items()}  # to strip extra qoutes from key
            culture_skills_rating = {key.capitalize() : value for key, value in culture_skills_rating.items()}
            test_attempt_session.culture_skills_rating = culture_skills_rating
            updated_fields.append("culture_skills_rating")


    if len(updated_fields) >0:
        test_attempt_session.save(update_fields=updated_fields)

def parse_personality_dimensions(text_response, expected_sections, psy_dict):
    # Initialize the dictionary to hold the results
    psy_dict_cleaned = {
        key.strip(): [value.strip() for value in values]
        for key, values in psy_dict.items()
    }
    results = {}

    # Check if the input string is empty
    if not text_response.strip():
        raise ValueError("The input text_response is empty.")

    # Split the text into lines and iterate through them
    for line in text_response.strip().split('\n'):
        if "PERSONALITY DIMENSIONS FORMAT" in line:
            continue
        # Use regex to extract the dimension and its details
        match = re.match(r'^\s*(.+?):\s*(.+)$', line)
        if match:
            dimension = match.group(1).strip()
            details = match.group(2).strip()

            # Split details into individual scores
            scores = {}
            for detail in details.split(','):
                detail = detail.strip()
                # Extract the name and score
                score_match = re.match(r'^(.*?)\s*-?\s*Score[^\d]*(\d*\.?\d+)', detail)
                if score_match:
                    name = score_match.group(1).strip()
                    score = float(score_match.group(2))
                    scores[name] = score
                else:
                    raise ValueError(f"Invalid score format in detail: '{detail}', response: {text_response}")

            # Add the dimension and its scores to the results dictionary
            results[dimension] = scores
            logger.info(f"{list(scores.keys())}  psy= {psy_dict_cleaned},{psy_dict_cleaned.get(dimension)}, {[key.strip() for key in scores.keys()] == psy_dict_cleaned.get(dimension,[])}")
            if [key.strip() for key in scores.keys()] != psy_dict_cleaned.get(dimension,[]):
                raise ValidationError(f"Invalid output given by LLM in line `{line}`. response: {text_response}")
        else:
            raise ValueError(f"Invalid line format: '{line}'")

    # Check if the number of extracted sections matches the expected count
    if expected_sections != len(results):
        raise ValueError(f"Expected {expected_sections} sections, but found {len(results)}: {results}")

    return results

import json
from .models import Psychometric, PsychometricItem, TestMapping

def extract_section_details(json_data):
    extracted_data = []

    # Assuming json_data contains a list with a single dictionary
    for main_data in json_data:

        # Loop through the parameters to extract details
        for param in main_data.get("parameters", []):
            # Find the description for the corresponding parameter
            section_description = next(
                (note["description"] for note in main_data.get("generate_note", [])
                 if note["parameter"] == param["parameterName"].replace('-','vs')),
                None
            )
            
            # Create a result structure for each parameter
            parameter_info = {
                "section": main_data.get("dimension", "Unknown Dimension"),
                "subsection": param["parameterName"],
                "parameter": {
                    "parameterName": param["parameterName"],
                    "parameters": param["parameters"],
                    "description": section_description
                },
                "range_values": {
                    r["range"]: {
                        "strengths": r["strengths"],
                        "areas_for_improvement": r["areas_for_improvement"]
                    }
                    for r in param.get("ranges", [])
                }
            }

            psychometric_item, created = PsychometricItem.objects.get_or_create(
                section=parameter_info.get('section'),
                subsection=parameter_info.get('subsection'),
                defaults={
                    'parameters': parameter_info.get('parameter'),
                    'range_values': parameter_info.get("range_values")
                }
            )
            extracted_data.append(parameter_info)

    return extracted_data




def add_section():
    json_data = [
      {
        "dimension": "Subject Matter Expertise",
        "generate_note": [
            {
                "parameter": "Learning Agility vs Fixed Mindset",
                "description": "This dimension evaluates an individual's ability to swiftly adapt to new challenges and absorb novel information as opposed to exhibiting a reluctance to change. It underscores the capacity for continuous learning and intellectual flexibility."
            },
            {
                "parameter": "Feedback Receptivity vs Defensiveness",
                "description": "This gauges how open an individual is to receiving and integrating constructive criticism into their personal and professional development, as contrasted with defensive behaviour that may hinder growth."
            }
        ],
        "parameters": [
            {
                "parameterName": "Learning Agility - Fixed Mindset",
                "parameters": ["Learning Agility", "Fixed Mindset"],
                "ranges": [
                    {
                        "range": "0-3",
                        "strengths": [
                            "Growth: Your growth mindset allows you to embrace challenges and see setbacks as opportunities for learning. This makes you highly adaptable and able to thrive in a dynamic environment.",
                            "Collaboration: Your growth mindset makes you more open to different perspectives and willing to learn from others. This can lead to strong relationships and effective collaboration."
                        ],
                        "areas_for_improvement": [
                            "Consistency: Your focus on growth and development can sometimes make you less consistent in your actions. It's important to find a balance between adaptability and reliability.",
                            "Self-confidence: Your focus on growth and development can sometimes make you overly critical of yourself. It's important to cultivate self-confidence and celebrate your achievements."
                        ],
                        "overall": ""
                    },
                    {
                        "range": "4-7",
                        "strengths": [
                            "Adaptability: You are able to balance your fixed mindset with a willingness to learn and grow. This makes you adaptable and able to navigate change effectively.",
                            "Resilience: Your ability to balance your fixed mindset with a growth mindset can make you more resilient to setbacks. You are able to learn from your mistakes and bounce back from challenges."
                        ],
                        "areas_for_improvement": [
                            "Growth: Your fixed mindset may still limit your growth potential in certain areas. It's important to continue to cultivate a growth mindset and challenge your beliefs about your abilities.",
                            "Collaboration: Your fixed mindset can sometimes make it difficult to collaborate with others. It's important to be open to different perspectives and willing to learn from others."
                        ],
                        "overall": ""
                    },
                    {
                        "range": "8-10",
                        "strengths": [
                            "Consistency: You are reliable and predictable, sticking to your routines and habits.",
                            "Focus: Your fixed mindset allows you to focus on your strengths and avoid areas where you may struggle."
                        ],
                        "areas_for_improvement": [
                            "Growth: Your fixed mindset can limit your growth potential. It's important to cultivate a growth mindset that embraces challenges and sees setbacks as opportunities for learning.",
                            "Adaptability: Your fixed mindset can make it difficult to adapt to change. Developing your adaptability will help you thrive in a dynamic environment."
                        ],
                        "overall": ""
                    }
                ]
            },
            {
                "parameterName": "Feedback Receptivity - Defensiveness",
                "parameters": ["Feedback Receptivity", "Defensiveness"],
                "ranges": [
                    {
                        "range": "0-3",
                        "strengths": [
                            "Relationships: Your receptive nature allows you to build strong relationships with others. You are open to different perspectives and willing to listen to others.",
                            "Learning: Your receptivity makes you a lifelong learner. You are always open to new ideas and experiences."
                        ],
                        "areas_for_improvement": [
                            "Independence: Your receptive nature can sometimes make you overly dependent on the opinions of others. It's important to develop your independence and learn to trust your own judgment.",
                            "Assertiveness: Your receptive nature can sometimes make it difficult to assert yourself and stand up for your needs. It's important to develop your assertiveness skills to avoid being taken advantage of."
                        ],
                        "overall": ""
                    },
                    {
                        "range": "4-7",
                        "strengths": [
                            "Adaptability: Your ability to balance receptivity and defensiveness makes you adaptable and able to navigate different social situations.",
                            "Relationships: Your balanced approach allows you to build strong relationships while maintaining a sense of independence."
                        ],
                        "areas_for_improvement": [
                            "Assertiveness: Your balanced approach can sometimes make it difficult to assert yourself and stand up for your needs. It's important to develop your assertiveness skills to avoid being taken advantage of.",
                            "Decision-making: Your balanced approach can sometimes make it difficult to make decisions, as you may struggle to choose between being receptive to others and standing up for your beliefs."
                        ],
                        "overall": ""
                    },
                    {
                        "range": "8-10",
                        "strengths": [
                            "Independence: Your defensive nature can make you independent and self-reliant. You are not easily influenced by the opinions of others.",
                            "Focus: Your defensiveness can allow you to focus on your goals and avoid distractions."
                        ],
                        "areas_for_improvement": [
                            "Relationships: Your defensiveness can make it difficult to build strong relationships with others. It's important to be open to different perspectives and avoid making assumptions.",
                            "Learning: Your defensiveness can limit your ability to learn and grow. It's important to be open to feedback and willing to admit your mistakes."
                        ],
                        "overall": ""
                    }
                ]
            }
        ]
    },
  {
    "dimension": "Innovation Drive",
    "generate_note": [
      {
        "parameter": "Growth Orientation vs Comfort Zones",
        "description": "Assesses an individual's propensity to seek out and embrace new opportunities for improvement and innovation. It contrasts with a preference for stability and familiarity that may lead to stagnation."
      },
      {
        "parameter": "Experimentation vs Risk Aversion",
        "description": "Reflects the willingness to try untested methods and accept uncertainty in the pursuit of advancements, as opposed to avoiding risks and maintaining the status quo to prevent failure."
      }
    ],
    "parameters": [
      {
        "parameterName": "Growth Orientation - Comfort Zones",
        "parameters": ["Growth Orientation", "Comfort Zones"],
        "ranges": [
          {
            "range": "0-3",
            "strengths": [
              "Growth-focused: You are driven to learn and expand your skills consistently.",
              "Adaptive: You readily embrace new methods and ideas, adapting quickly to changes."
            ],
            "areas_for_improvement": [
              "Stability Needs: Ensure some stability in your knowledge and methods to avoid constant change causing inefficiencies.",
              "Overextending: Be mindful of not stretching yourself too thin by taking on too many new challenges at once."
            ],
            "overall": ""
          },
          {
            "range": "4-7",
            "strengths": [
              "Balanced Learning: You show a balance between seeking growth and using your current expertise.",
              "Versatility: You can smoothly transition between learning new skills and relying on well-established ones."
            ],
            "areas_for_improvement": [
              "Further Challenge: Continue to seek new challenges to grow and expand your skills.",
              "Risk-Taking: Consider taking calculated risks that push you slightly outside your comfort zone to facilitate growth."
            ],
            "overall": ""
          },
          {
            "range": "8-10",
            "strengths": [
              "Consistency: You prefer familiar methods that you are proficient in.",
              "Reliability: Your adherence to proven methods makes you a reliable performer in established areas."
            ],
            "areas_for_improvement": [
              "Growth: It's important to push beyond your comfort zones. Strive to learn and expand your skills continually.",
              "Adaptability: Be open to adopting new approaches and ideas, as this can enhance your capability to tackle unforeseen challenges."
            ],
            "overall": ""
          }
        ]
      },
      {
        "parameterName": "Experimentation - Risk Aversion",
        "parameters": ["Experimentation", "Risk Aversion"],
        "ranges": [
          {
            "range": "0-3",
            "strengths": [
              "Innovative: You are highly willing to try new strategies, embracing the possibility of initial setbacks.",
              "Adaptability: You are adaptable to changes and quick in implementing new ideas."
            ],
            "areas_for_improvement": [
              "Risk Mitigation: Ensure you have risk mitigation strategies to balance out your innovative approaches.",
              "Long-term Planning: Having a strong long-term plan can help balance innovative approaches with stability."
            ],
            "overall": ""
          },
          {
            "range": "4-7",
            "strengths": [
              "Balanced Approach: You use a balanced approach, occasionally trying new strategies while evaluating risks.",
              "Versatility: You can adapt to new situations while managing potential risks effectively."
            ],
            "areas_for_improvement": [
              "Increase Risk Tolerance: Be more willing to take calculated risks for growth.",
              "Proactivity: Take a more proactive stance in seeking out new opportunities rather than just responding to changes."
            ],
            "overall": ""
          },
          {
            "range": "8-10",
            "strengths": [
              "Caution: You avoid potential risks, thereby mitigating the chances of failure.",
              "Stability: Your risk-averse nature contributes to maintaining long-term stability."
            ],
            "areas_for_improvement": [
              "Experimentation: Be more open to experimentation. Some calculated risks can lead to significant rewards.",
              "Flexibility: Cultivate more flexibility to adapt when necessary, even in low-risk scenarios."
            ],
            "overall": ""
          }
        ]
      }
    ]
  },
  {
    "dimension": "Communication Mastery",
    "generate_note": [
      {
        "parameter": "Empathy vs Self-Focus",
        "description": "Evaluates the ability to genuinely understand and resonate with the emotions and perspectives of others, enhancing interpersonal relationships, compared to a focus predominantly on personal needs and views."
      },
      {
        "parameter": "Active Listening vs Interrupting",
        "description": "Measures the skill of engaging in meaningful dialogue through attentive listening and acknowledging others' inputs, in contrast to a tendency to interrupt, which may hinder effective communication."
      }
    ],
    "parameters": [
      {
        "parameterName": "Active Listening - Interrupting",
        "parameters": ["Active Listening", "Interrupting"],
        "ranges": [
          {
            "range": "0-3",
            "strengths": [
              "Excellent Listener: You listen intently and make others feel heard.",
              "Respectful Communication: You respect others' turns to speak and rarely interrupt."
            ],
            "areas_for_improvement": [
              "Assertiveness: Ensure your viewpoints are also adequately expressed in conversations.",
              "Engagement: Actively participate more to share your thoughts and contribute to discussions."
            ],
            "overall": ""
          },
          {
            "range": "4-7",
            "strengths": [
              "Balance: You strike a balance between listening and asserting your viewpoints.",
              "Adaptability: You can adjust your communication style depending on the situation."
            ],
            "areas_for_improvement": [
              "Enhance Listening: Focus more on active listening to improve understanding in conversations.",
              "Monitoring Interruptions: Be mindful of not interrupting others and let them finish their thoughts."
            ],
            "overall": ""
          },
          {
            "range": "8-10",
            "strengths": [
              "Assertive: You ensure that your viewpoints are heard.",
              "Taking Initiative: You actively engage in conversations and lead discussions."
            ],
            "areas_for_improvement": [
              "Listening Skills: Develop active listening skills to ensure you fully understand others' perspectives.",
              "Patience: Practice patience and allow others to complete their thoughts without interruption."
            ],
            "overall": ""
          }
        ]
      },
      {
        "parameterName": "Empathy - Self-Focus",
        "parameters": ["Empathy", "Self-Focus"],
        "ranges": [
          {
            "range": "0-3",
            "strengths": [
              "Highly Empathetic: You are very attuned to others' emotions and perspectives.",
              "Compassionate Listener: You excel at understanding and validating others' feelings."
            ],
            "areas_for_improvement": [
              "Balance Self-Care: Ensure you do not neglect your own needs in the process of understanding and helping others.",
              "Assertiveness: Work on being more assertive in expressing your own needs and viewpoints."
            ],
            "overall": ""
          },
          {
            "range": "4-7",
            "strengths": [
              "Balance: You manage a balance between considering your own viewpoint and those of others.",
              "Adaptable: You can shift perspectives depending on the situation at hand."
            ],
            "areas_for_improvement": [
              "Enhance Empathy: Work on boosting your empathy to better understand and connect with others.",
              "Self-Focus Development: Develop a stronger sense of self-focus to ensure your needs and goals are also met."
            ],
            "overall": ""
          },
          {
            "range": "8-10",
            "strengths": [
              "Self-Focused: You are determined and stay focused on your own goals.",
              "Independent Thinker: You have a strong sense of self and can make decisions independently."
            ],
            "areas_for_improvement": [
              "Empathy: Develop your empathy to become more attuned to others' emotions and perspectives.",
              "Active Listening: Practice active listening to improve your connections and understanding of others."
            ],
            "overall": ""
          }
        ]
      }
    ]
  },
  
  {
    "dimension": "People Leadership",
    "generate_note": [
      {
        "parameter": "Collaboration vs Competitiveness",
        "description": "Assesses an individual's capability to work cooperatively with others to achieve shared objectives, balancing personal ambition with teamwork as opposed to competing at the expense of collaboration."
      },
      {
        "parameter": "Relationship Building vs Transactional Approach",
        "description": "Reflects the ability to cultivate deep, trusting relationships based on mutual respect and understanding, in contrast to treating interactions as mere transactions."
      }
    ],
    "parameters": [
      {
        "parameterName": "Collaboration - Competitiveness",
        "parameters": ["Collaboration", "Competitiveness"],
        "ranges": [
          {
            "range": "0-3",
            "strengths": [
              "Highly Collaborative: You prioritize shared goals and coordinate teamwork effectively.",
              "Team-Oriented: Strong alignment with team objectives and collective success."
            ],
            "areas_for_improvement": [
              "Competitive Drive: Cultivate a healthy competitive spirit to help drive personal and team growth.",
              "Ambition: Enhance your personal drive and ambition to ensure balanced progress."
            ],
            "overall": ""
          },
          {
            "range": "4-7",
            "strengths": [
              "Balanced: You maintain an effective balance between competition and collaboration.",
              "Adaptability: You can adjust your approach based on the situation's demands."
            ],
            "areas_for_improvement": [
              "Team Spirit: Work on deepening team engagement and nurturing a collaborative environment.",
              "Competitive Edge: Strengthen your competitive drive to enhance overall performance."
            ],
            "overall": ""
          },
          {
            "range": "8-10",
            "strengths": [
              "Competitive Edge: You possess a strong competitive drive, constantly striving to outperform others.",
              "Ambitious: Your ambition drives both personal and team success."
            ],
            "areas_for_improvement": [
              "Collaboration: Focus on enhancing teamwork and prioritizing shared objectives.",
              "Inclusiveness: Make efforts to include and value diverse perspectives and contributions within the team."
            ],
            "overall": ""
          }
        ]
      },
      {
        "parameterName": "Relationship Building - Transactional Approach",
        "parameters": ["Relationship Building", "Transactional Approach"],
        "ranges": [
          {
            "range": "0-3",
            "strengths": [
              "Strong Relationships: You invest significantly in building authentic and meaningful connections.",
              "Collaborative Environment: You create a supportive and collaborative atmosphere that can lead to enhanced teamwork and morale."
            ],
            "areas_for_improvement": [
              "Task Efficiency: Ensure task efficiency is not compromised while fostering relationships.",
              "Goal Achievement: Focus more on specific goals and task completion to balance relationship-building efforts."
            ],
            "overall": ""
          },
          {
            "range": "4-7",
            "strengths": [
              "Balanced Approach: You maintain a good equilibrium between task orientation and relationship building.",
              "Flexible Interaction: You adapt your approach based on the situation, fostering both task completion and relationship building."
            ],
            "areas_for_improvement": [
              "Deepen Relationships: Work towards deepening your interactions and building more substantial connections.",
              "Prioritization: Improve your ability to prioritize between tasks and relationship-building efforts as needed."
            ],
            "overall": ""
          },
          {
            "range": "8-10",
            "strengths": [
              "Task-focused: You prioritize task completion and efficiency, ensuring that goals are met promptly.",
              "Objective-driven: Your approach is highly goal-oriented, making you effective in achieving targets."
            ],
            "areas_for_improvement": [
              "Relationship Building: Invest in building more authentic connections to foster better long-term collaboration and trust.",
              "Team Morale: Enhance efforts to build team morale and a collaborative environment, which can ultimately lead to greater overall success."
            ],
            "overall": ""
          }
        ]
      }
    ]
  },
  {
    "dimension": "Ethical Governance",
    "generate_note": [
      {
        "parameter": "Emotional Regulation vs Impulsivity",
        "description": "Evaluates the ability to maintain composure and deliberate responses in emotionally charged situations, compared to reacting impulsively, which may lead to unintended consequences."
      },
      {
        "parameter": "Self-Confidence vs Self-Doubt",
        "description": "Measures the degree of confidence in one's decisions and actions, empowering leadership and initiative, as opposed to pervasive self-doubt that can undermine effectiveness."
      }
    ],
    "parameters": [
      {
        "parameterName": "Emotional Regulation - Impulsivity",
        "parameters": ["Emotional Regulation", "Impulsivity"],
        "ranges": [
          {
            "range": "0-3",
            "strengths": [
              "Control: You have excellent control over your emotions.",
              "Thoughtfulness: You approach situations with a level-headed and calm demeanor."
            ],
            "areas_for_improvement": [
              "Flexibility: Ensure your actions are timely and responsive without being overly restrained.",
              "Balance: Aim to strike a balance between measured responses and necessary quick actions."
            ],
            "overall": ""
          },
          {
            "range": "4-7",
            "strengths": [
              "Balance: You maintain a balance between emotional regulation and taking action.",
              "Awareness: You are generally aware of your emotional reactions and can adjust appropriately."
            ],
            "areas_for_improvement": [
              "Consistency: Work towards consistently regulating your emotions in all situations.",
              "Reflection: Spend more time reflecting on impulsive moments to better recognize triggers."
            ],
            "overall": ""
          },
          {
            "range": "8-10",
            "strengths": [
              "Enthusiasm: You approach situations with energy and spontaneity.",
              "Decisiveness: Your capacity to make quick decisions is a valuable skill in certain situations."
            ],
            "areas_for_improvement": [
              "Emotional Control: Develop better emotional regulation to manage emotions constructively.",
              "Thoughtfulness: Strive to increase your thoughtfulness to avoid impulsive actions that may lead to negative outcomes."
            ],
            "overall": ""
          }
        ]
      },
      {
        "parameterName": "Self-Confidence - Self-Doubt",
        "parameters": ["Self-Confidence", "Self-Doubt"],
        "ranges": [
          {
            "range": "0-3",
            "strengths": [
              "Highly Confident: You have a high level of self-confidence in your abilities and decisions.",
              "Decisiveness: You are able to make quick decisions without much hesitation."
            ],
            "areas_for_improvement": [
              "Overconfidence: Ensure your confidence does not border on overconfidence to avoid potential complacency.",
              "Receptiveness: Stay open to feedback and be willing to admit when you might be wrong."
            ],
            "overall": ""
          },
          {
            "range": "4-7",
            "strengths": [
              "Balanced: You maintain a balanced level of self-confidence without frequent self-doubt.",
              "Reflective: You are capable of considering different perspectives before making decisions."
            ],
            "areas_for_improvement": [
              "Increase Assurance: Work on increasing your self-assurance to trust your decisions more.",
              "Consistency: Aim for a more consistent level of self-confidence to reduce occasional self-doubt."
            ],
            "overall": ""
          },
          {
            "range": "8-10",
            "strengths": [
              "Self-Improvement: You recognize the need for self-improvement and are proactive in seeking it.",
              "Humbleness: You understand your limitations and actively work on them."
            ],
            "areas_for_improvement": [
              "Confidence: Build more self-confidence to believe in your abilities and decisions.",
              "Positive Reinforcement: Focus on acknowledging your strengths and past successes to boost self-belief."
            ],
            "overall": ""
          }
        ]
      }
    ]
  },
  {
    "dimension": "Strategic Thinking",
    "generate_note": [
      {
        "parameter": "Strategic Thinking vs Short-Term Focus",
        "description": "Reflects an individual's ability to align current actions with long-term goals, emphasising foresight and comprehensive planning as opposed to concentrating solely on immediate results."
      },
      {
        "parameter": "Decision-Making vs Procrastination",
        "description": "Assesses the capability to make informed and timely decisions while managing uncertainties, versus delaying necessary actions due to indecision or avoidance."
      }
    ],
    "parameters": [
      {
        "parameterName": "Strategic Thinking - Short-Term Focus",
        "parameters": ["Strategic Thinking", "Short-Term Focus"],
        "ranges": [
          {
            "range": "0-3",
            "strengths": [
              "Strategy: You excel at strategic thinking and long-term goal setting.",
              "Vision: You have a strong ability to envision the future and set meaningful long-term goals."
            ],
            "areas_for_improvement": [
              "Practical Focus: Maintain daily practical focus to ensure that immediate tasks align with your strategic vision.",
              "Execution: Enhance your ability to execute on short-term tasks to ensure tangible progress toward your long-term goals."
            ],
            "overall": ""
          },
          {
            "range": "4-7",
            "strengths": [
              "Balance: You balance short-term and long-term planning effectively.",
              "Flexibility: You can adapt to changing circumstances while keeping an eye on long-term objectives."
            ],
            "areas_for_improvement": [
              "Vision: Enhance your strategic vision to better align actions with long-term goals.",
              "Consistency: Increase consistency in aligning immediate tasks with long-term objectives."
            ],
            "overall": ""
          },
          {
            "range": "8-10",
            "strengths": [
              "Prudence: You are effective in short-term planning and task completion.",
              "Focus: You have a strong focus on immediate tasks, ensuring timely completion."
            ],
            "areas_for_improvement": [
              "Strategic Thinking: Develop long-term strategic thinking to align your actions with future goals.",
              "Risk Management: Balance short-term focus with longer-term risk assessment to avoid potential pitfalls."
            ],
            "overall": ""
          }
        ]
      },
      {
        "parameterName": "Decision-Making - Procrastination",
        "parameters": ["Decision-Making", "Procrastination"],
        "ranges": [
          {
            "range": "0-3",
            "strengths": [
              "Decisiveness: You are highly decisive and take prompt actions.",
              "Action-Oriented: You complete tasks efficiently without unnecessary delays."
            ],
            "areas_for_improvement": [
              "Avoid Impulsiveness: Ensure your decisions are well-thought-out to avoid impulsive actions.",
              "Reflective Thinking: Take time for reflective thinking to enhance the quality of your decisions."
            ],
            "overall": ""
          },
          {
            "range": "4-7",
            "strengths": [
              "Balance: You balance decision-making and action effectively.",
              "Moderate Pace: You are able to weigh options carefully without rushing or lengthy delays."
            ],
            "areas_for_improvement": [
              "Avoid Procrastination: Reduce tendencies to procrastinate on important decisions.",
              "Improve Decision Speed: Aim to slightly increase your decision-making speed to enhance productivity."
            ],
            "overall": ""
          },
          {
            "range": "8-10",
            "strengths": [
              "Deliberation: You make careful, deliberate decisions.",
              "Thoughtfulness: You tend to thoroughly consider the consequences before taking action."
            ],
            "areas_for_improvement": [
              "Increase Decisiveness: Work on being more decisive to take timely actions when needed.",
              "Avoid Overthinking: Limit overthinking to prevent decision-making delays and missed opportunities."
            ],
            "overall": ""
          }
        ]
      }
    ]
  }
,

  {
    "dimension": "Operational Excellence",
    "generate_note": [
      {
        "parameter": "Delegation vs Micromanagement",
        "description": "Measures trust placed in team members' capabilities and the effective distribution of responsibilities, as opposed to tendencies toward micromanagement that may stifle autonomy and creativity."
      },
      {
        "parameter": "Adaptability to Change vs Resistance",
        "description": "Evaluates the capacity to embrace and effectively navigate changing environments, showing flexibility and resilience as opposed to exhibiting resistance that may hinder progress."
      }
    ],
    "parameters": [
      {
        "parameterName": "Delegation - Micromanagement",
        "parameters": ["Delegation", "Micromanagement"],
        "ranges": [
          {
            "range": "0-3",
            "strengths": [
              "Excellent Delegator: You excel at delegating tasks and empowering your team.",
              "Trust in Team: You trust your team’s abilities and encourage their independence."
            ],
            "areas_for_improvement": [
              "Maintain Oversight: Ensure you retain some level of oversight to catch potential issues early.",
              "Provide Guidance: Make sure you still provide adequate guidance and support when necessary."
            ],
            "overall": ""
          },
          {
            "range": "4-7",
            "strengths": [
              "Balanced Approach: You maintain a balanced approach to delegation and control.",
              "Flexibility: You know when to delegate and when to get involved."
            ],
            "areas_for_improvement": [
              "Effective Delegation: Work on delegating more effectively to empower your team further.",
              "Reduce Micromanagement: Try to identify areas where you can reduce unnecessary control."
            ],
            "overall": ""
          },
          {
            "range": "8-10",
            "strengths": [
              "Detail-oriented: You focus meticulously on details to ensure accuracy.",
              "High Standards: Your high standards often lead to high-quality outcomes."
            ],
            "areas_for_improvement": [
              "Improve Delegation: Enhance your delegation skills to better trust and empower your team.",
              "Avoid Over-Control: Work on avoiding over-controlling tendencies to allow your team more autonomy."
            ],
            "overall": ""
          }
        ]
      },
      {
        "parameterName": "Adaptability to Change - Resistance",
        "parameters": ["Adaptability to Change", "Resistance"],
        "ranges": [
          {
            "range": "0-3",
            "strengths": [
              "Highly Adaptable: You are highly adaptable to change, effectively navigating and adjusting to shifting priorities and unexpected circumstances.",
              "Flexibility: You can quickly pivot and respond to new situations without much disruption."
            ],
            "areas_for_improvement": [
              "Over-Adapting: Ensure that you do not over-adjust or lose track of long-term goals.",
              "Consistency: Strive to maintain a consistent approach to certain tasks to ensure stability."
            ],
            "overall": ""
          },
          {
            "range": "4-7",
            "strengths": [
              "Balanced Adaptability: You balance stability with the ability to adjust, providing a dependable yet flexible approach.",
              "Moderate Flexibility: You can manage some level of change without significant disruption."
            ],
            "areas_for_improvement": [
              "Increase Adaptability: Enhance your ability to handle unexpected changes and shifting priorities more efficiently.",
              "Proactive Planning: Develop strategies to better anticipate and prepare for potential changes."
            ],
            "overall": ""
          },
          {
            "range": "8-10",
            "strengths": [
              "Stability: You remain steady and stable in your habits, providing consistency.",
              "Structured Approach: Your structured method helps in maintaining clear objectives and processes."
            ],
            "areas_for_improvement": [
              "Embrace Change: Work on embracing change more to navigate shifting priorities and unexpected circumstances effectively.",
              "Flexibility: Increase your flexibility to adjust to new situations and evolving requirements."
            ],
            "overall": ""
          }
        ]
      }
    ]
  },
  {
    "dimension": "Financial Acumen",
    "generate_note": [
      {
        "parameter": "Short-term Focus vs Forward Thinking Focus",
        "description": "Reflects the balance between achieving immediate financial results and crafting strategic plans for future stability and growth, ensuring sustainable economic health."
      },
      {
        "parameter": "Data Driven vs Process Driven",
        "description": "Measures the prioritization of empirical data and analytics in decision-making processes versus a reliance on traditional methods and established procedures."
      }
    ],
    "parameters": [
      {
        "parameterName": "Short term Focus - Forward Thinking Focus",
        "parameters": ["Short term Focus", "Forward Thinking Focus"],
        "ranges": [
          {
            "range": "0-3",
            "strengths": [
              "Innovative Energy: Your youthful perspective brings fresh, creative ideas to improve ROI and explore new financial strategies.",
              "Opportunistic: You are quick to identify tactical avenues that offer short-term spikes."
            ],
            "areas_for_improvement": [
              "Short-Term Focus: It's essential to balance your excitement for ROI considerations with a sustainable growth vision.",
              "Practical Execution: Gain more experience in translating your financial savvy into executable financial strategies that deliver consistent returns."
            ],
            "overall": ""
          },
          {
            "range": "4-7",
            "strengths": [
              "Balanced Vision: With more experience, you effectively balance immediate ROI goals with longer-term financial planning, creating a sustainable growth path.",
              "Strategic Foresight: You have developed a strong sense of foresight, aligning financial decisions with upcoming market trends and organizational goals."
            ],
            "areas_for_improvement": [
              "Managing Financial Risk: As you take on more responsibility, it’s important to refine your ability to manage financial risks associated with forward-thinking strategies.",
              "Efficiency in Execution: As your experience grows, focus on improving the efficiency of turning future-oriented financial strategies into actions that capitalize on opportunities quickly."
            ],
            "overall": ""
          },
          {
            "range": "8-10",
            "strengths": [
              "Visionary Financial Leadership: Your extensive experience allows you to consistently focus on long-term ROI, with a clear understanding of how current decisions will impact future growth.",
              "Proactive Financial Planning: You have a well-honed ability to align financial strategies with long-term goals, leading to consistent and substantial improvements in ROI."
            ],
            "areas_for_improvement": [
              "Adapting to Change: Despite your strong forward-thinking focus, be mindful of maintaining flexibility to quickly adjust strategies in response to fast-changing market conditions.",
              "Tactical Precision: While your vision is clear, focus on sharpening the tactical execution of forward-thinking ideas, ensuring that both immediate and long-term ROI are optimized."
            ],
            "overall": ""
          }
        ]
      },
      {
        "parameterName": "Data Driven - Process Driven",
        "parameters": ["Data Driven", "Process Driven"],
        "ranges": [
          {
            "range": "0-3",
            "strengths": [
              "Data Awareness: At this stage, you’re beginning to understand the importance of using data in financial decisions.",
              "Process Familiarity: You are starting to recognize the value of structured financial processes."
            ],
            "areas_for_improvement": [
              "Data Utilization: Focus on learning how to effectively collect and interpret financial data to inform basic decisions.",
              "Process Learning: Develop a stronger understanding of foundational financial processes to establish consistency."
            ],
            "overall": ""
          },
          {
            "range": "4-7",
            "strengths": [
              "Data-Driven Foundations: You actively use data to guide financial decisions, developing a more precise understanding of its impact.",
              "Process Improvement: You can identify areas where financial processes can be optimized for better results."
            ],
            "areas_for_improvement": [
              "Data Flexibility: Incorporate flexibility by combining your growing data skills with qualitative insights.",
              "Process Innovation: Begin exploring innovative approaches to enhance existing financial processes without sacrificing efficiency."
            ],
            "overall": ""
          },
          {
            "range": "8-10",
            "strengths": [
              "Strategic Data Use: You leverage data analytics to drive strategic financial decisions, ensuring accuracy and maximizing long-term ROI.",
              "Advanced Process Optimization: You excel at fine-tuning financial processes, which substantially enhances efficiency and outcomes."
            ],
            "areas_for_improvement": [
              "Holistic Decision-Making: Integrate intuitive insights with data-driven strategies to further optimize financial planning.",
              "Continuous Innovation: Maintain a balance between steadfast processes and the introduction of novel methods to ensure dynamic financial success."
            ],
            "overall": ""
          }
        ]
      }
    ]
  }






  
]

    data = extract_section_details(json_data)
    print(data)



def format_psychometric_items(psychometric:Psychometric):
    # Use a set to keep track of unique sections for the dimension
    sections = {}

    # Loop through each PsychometricItem in the Psychometric set
    for item in psychometric.psy_items.filter(deleted=False):
        # Use item.section as the dimension
        section = sections.get(item.section)
        if not section:
            section = {
                "dimension": item.section,  
                "generate_note": [],
                "parameters": []
            }

        print(f'seciton: {sections, section}')
              
        parameters = item.parameters
        section["generate_note"].append({
                "parameter": " vs ".join(parameters.get('parameters')),
                "description": parameters.get('description')
            })

        parameter_data = {
                "parameterName": parameters.get('parameterName'),
                "parameters": parameters.get('parameters'),
                "ranges": []
            }
        
        for range_key, range_value in item.range_values.items():
                range_entry = {
                    "range": range_key,
                    "strengths": range_value.get("strengths", []),
                    "areas_for_improvement": range_value.get("areas_for_improvement", []),
                    "overall": range_value.get("overall", "")
                }
                parameter_data["ranges"].append(range_entry)

        section['parameters'].append(parameter_data)

        sections[f"{item.section}"] = section

    return sections.values()

def find_highest_count_range(data):
    # Define ranges as tuples of (min, max)
    if not data:
        return []
    ranges = [(0, 3), (4, 7), (8, 10)]
    
    # Dictionary to store counts for each range
    range_counts = defaultdict(int)
    
    # Iterate through nested dictionary and count values in each range
    for category, subcategory_values in data.items():
        for subcategory, value in subcategory_values.items():
            for r in ranges:
                if r[0] <= value <= r[1]:
                    range_counts[r] += 1
                    break  # Stop after finding the correct range
    
    # Find the maximum count
    print(range_counts)
    max_count = max(range_counts.values())
    
    # Get all ranges with the maximum count
    most_common_ranges = [f"{r[0]}-{r[1]}" for r, count in range_counts.items() if count == max_count]
    
    return most_common_ranges




def parse_psychometric_csv(csv_file):
    """
    Parses and validates a CSV file for PsychometricItems, creating a structured 
    JSON for each item that matches the PsychometricItem model fields.
    """
    items = []
    decoded_file = csv_file.read().decode('utf-8').splitlines()
    reader = csv.DictReader(decoded_file)

    # Regex patterns for detecting range-related columns
    range_pattern = re.compile(r'^Range (\d+)$')
    strengths_pattern = re.compile(r'^Strengths (\d+)$')
    improvement_pattern = re.compile(r'^Areas Improvement (\d+)$')

    for row in reader:
        # Extract required fields and validate they are present
        section = row.get('Section')
        parameter_names = row.get('Parameter Names')
        parameter_description = row.get('Parameter Description')
        avg_value = row.get('Average Score')

        if not section  or not parameter_names or not parameter_description or not avg_value:
            raise ValidationError("All fields are required: 'Section', 'Parameter Names', 'Average Score' and 'Parameter Description'.")

        # if not isinstance(avg_value, [int, float]):
        #     raise ValidationError("Please enter valid value for Average Score")
        # Prepare the parameters field
        parameter_list = [p.strip() for p in parameter_names.split(',') if len(p.strip())>0]
        parameter_name = " - ".join(parameter_list)
        parameters = {
            "parameters": parameter_list,
            "description": parameter_description,
            "parameterName": parameter_name
        }

        subsection = parameter_name

        # Dynamically parse range values using regex
        range_values = {}
        ranges_found = {}

        for key, value in row.items():
            # Match Range, Strengths, and Areas for Improvement fields by number
            range_match = range_pattern.match(key)
            strengths_match = strengths_pattern.match(key)
            improvement_match = improvement_pattern.match(key)

            if range_match:
                range_num = range_match.group(1)
                ranges_found[range_num] = {"range": value}
            elif strengths_match:
                range_num = strengths_match.group(1)
                strengths = re.findall(r'([A-Za-z\s_-]+:\s*.*?)(?=[A-Za-z\s_-]+:|$)', value, re.DOTALL) or [value]
                ranges_found.setdefault(range_num, {})["strengths"] = [s.strip() for s in strengths if s.strip()]
            elif improvement_match:
                range_num = improvement_match.group(1)
                areas = re.findall(r'([A-Za-z\s_-]+:\s*.*?)(?=[A-Za-z\s_-]+:|$)', value, re.DOTALL) or [value]

                ranges_found.setdefault(range_num, {})["areas_for_improvement"] = [a.strip() for a in areas if a.strip()]

        # Validate and organize range data into range_values structure
        for range_num, range_data in ranges_found.items():
            if "range" not in range_data or "strengths" not in range_data or "areas_for_improvement" not in range_data:
                raise ValidationError(f"Missing data for range {range_num}: Ensure Range, Strengths, and Areas for Improvement are provided.")
            
            range_values[range_data["range"]] = {
                "strengths": range_data["strengths"],
                "areas_for_improvement": range_data["areas_for_improvement"]
            }

        # Collect item data for creation
        item_data = {
            "section": section,
            "subsection": subsection,
            "parameters": parameters,
            "range_values": range_values,
            'average_value': avg_value
        }
        items.append(item_data)

    logger.info(f"items: {items}")
    if len(items) == 0:
        raise ValidationError("Should be at least one row in csv.")
    return items



def format_game_json_to_string(data):
    """
    Convert the given JSON structure into a formatted string representation.

    Args:
        data (dict): The JSON data to be formatted.

    Returns:
        str: A human-readable string representation of the JSON data.
    """
    def format_section(section_data):
        formatted = []
        for key, value in section_data.items():
            if isinstance(value, dict):
                formatted.append(f"  {key.capitalize()}:")
                for sub_key, sub_value in value.items():
                    formatted.append(f"    {sub_key.capitalize()}: {sub_value}")
            elif isinstance(value, list):
                formatted.append(f"  {key.capitalize()}:")
                for item in value:
                    formatted.append(f"    - {item}")
            else:
                formatted.append(f"  {key.capitalize()}: {value}")
        return "\n".join(formatted)

    details = format_section(data.get("details", {}))
    content_str = format_section(data.get('content',{}))
    context = ""
    for value in data.get('context', {}).values():
        context += f"{value}\n"


    return f"{context}{details}\n\n{content_str}"


def delete_soft_deleted_test_attempt_session(sessions:TestAttemptSession):
    if sessions.exists():
        for test_attempt_session in sessions:
            print('deleting session : ', test_attempt_session.uid)
            TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session.uid).delete()

        sessions.delete()

def cleanup_database():
    from users.models import CoachCoacheeMentorMenteeProfile
    with transaction.atomic():
        # deleting all deleted test
        tests = Test.objects.filter(deleted=True)
        print('test count to delete:', tests.count())
        if tests.count() > 0:
            for test in tests:
                print('deleting test: ', test.uid)
                sessions = TestAttemptSession.objects.filter(test_id=test.uid)
                delete_soft_deleted_test_attempt_session(sessions=sessions)
                TestQuestion.objects.filter(test_id=test.uid).delete()

            tests.delete()

        # deleting all soft deleted test attempt session
        sessions = TestAttemptSession.objects.filter(deleted=True)
        print('total session: ', sessions.count())
        if sessions.count() > 0:
            delete_soft_deleted_test_attempt_session(sessions=sessions)

        #deleting singature bot and profile soft deleted
        profile = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=True)
        print('profile: ', profile.count())
        if profile.count() > 0:
            profile.delete()
        bot = SignatureBot.objects.filter(deleted=True)
        print('bot: ', bot.count())
        if bot.count() > 0:
            bot.delete()


def check_updates(instance, updates):
    """
    Checks if any values in the updates dictionary differ from the current instance values.

    Args:
        instance: The model instance to compare.
        updates: Dictionary containing field-value pairs to check for updates.

    Returns:
        bool: True if any value is updated, False otherwise.
    """
    updated_fields = []
    for field, new_value in updates.items():
        old_value = getattr(instance, field, None)
        if old_value != new_value:
            updated_fields.append(field)

    return updated_fields if updated_fields else []



def get_next_test(test_pilot_user: TestPilotuser):
    test_sequence = ["dynamic_game", "static_role_play_soft", "dynamic_start_with_user", 
                    "static_hard", "static_soft", "normal_dynamic_test_hard", 
                    "static_role_play_hard", "normal_dynamic_test_soft", "case", "checkin",
                    "static_game"]
    soft = ['static_role_play_soft', 'dynamic_start_with_user', 'static_soft','normal_dynamic_test_soft']
    hard = ['static_hard', 'normal_dynamic_test_hard', 'static_role_play_hard']
    others = ['dynamic_game', 'case', 'checkin','static_game']


    if test_pilot_user.preferences == PilotTestPreferencesChoices.only_hard_skills:
        test_sequence = hard
    elif test_pilot_user.preferences == PilotTestPreferencesChoices.only_soft_skills:
        test_sequence = soft


    previous_records = TestPilotRecords.objects.filter(pilotuser=test_pilot_user).last()

    if previous_records and previous_records.scenario_case_type in test_sequence:
        last_index = test_sequence.index(previous_records.scenario_case_type)
        next_index = (last_index + 1) % len(test_sequence)  # Loop back if at the end
        next_test = test_sequence[next_index]
    else:
        next_test = test_sequence[0]  # Start from beginning if unknown

    logger.info(f"{previous_records.scenario_case_type if previous_records else 'None'}, {next_test}")

    return next_test



def get_future_date(days=5, date_format="%Y-%m-%d"):
    """Returns the date 'days' days from today in the specified format."""
    future_date = datetime.datetime.today() + timedelta(days=days)
    return future_date.strftime(date_format)

def get_test_pilot_email_template(name, title, code, platform, access_code ):
    template = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Leadership Simulation Email</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    padding: 20px;
                }
                .container {
                    max-width: 600px;
                    margin: auto;
                    background: #f9f9f9;
                    padding: 20px;
                    border-radius: 10px;
                }
                .btn {
                    display: inline-block;
                    padding: 10px 20px;
                    color: #fff;
                    background: #007bff;
                    text-decoration: none;
                    border-radius: 5px;
                }
                .footer {
                    margin-top: 20px;
                    font-size: 12px;
                    color: #666;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <p>Hi ${name},</p>
                <p>Your weekly leadership simulation is ready! The details are below.</p>
                <p>Spend 10 minutes practicing real-time interaction & real-world decision making with our interactive platform.</p>
                <h3>Access Details</h3>
                <ul>
                    <li><a href="${platform_url}"><strong>Platform</strong> </a></li>
                    <li><strong>Access Code:</strong>${access_code}</li>
                    <li><strong>Interaction Code:</strong> ${test_code}</li>
                </ul>
                <h3>How to Participate</h3>
                <p>Visit the platform URL and locate the login page.</p>
                <p>Enter the access and interaction codes when prompted (case-sensitive).</p>
                <p>You may be asked for your name and email. Simulation feedback reports will be delivered to this email.</p>
                <p>CoachBot skills engine will detect skill gaps based on your performance and serve another scenario (Optional).</p>
                <p>Complete the scenario and the optional step by <strong>${next_day}</strong> date to maximize your Leadership Leaderboard scores!</p>
                <h3>This Week’s Simulation Title: ${title}</h3>
                <p><em>Note: The theme and track of the simulations are based on your inputs/organizational mandate. Please contact us if you wish to change them.</em></p>
                <p>Need help? Reply directly or contact <a href="mailto:support@coachbot.com">support@coachbot.com</a>.</p>
                <p>Keep growing,</p>
                <p><strong>Team CoachBot</strong></p>
                <p class="footer">This is an automated email. Please do not reply directly.</p>
            </div>
        </body>
        </html>             
        """

    return Template(template).substitute(name=name, title=title, test_code=code, platform_url=platform, access_code=access_code, next_day=get_future_date())

def process_test_pilot_user_csv(csv, tenant_id):
    test_to_create = ['simulation', 'role_play', 'games', 'dynamic', 'dynamic_user_first']
    test = None
    for row in csv:
        email = row.get("Email").strip()
        name = row.get("Name").strip()
        targeted_skills = row.get("Targeted Skills").strip()
        same_intake = str(row.get('Same Intake')).strip().lower() == 'true'
        send_email_to_user = (
                                str(row.get('Send Email')).strip().lower() == 'true'
                                if row.get('Send Email') and len(str(row.get('Send Email'))) > 0
                                else True
                            )

        
        print('saem_intake', test, same_intake, send_email_to_user)

        if not email or not name or not targeted_skills:
            raise ValidationError('CSV contains empty required fields.')

        # Create or update record
        defaults = {
            "name": row.get("Name"),
            "targeted_skills": row.get("Targeted Skills").strip() if row.get("Targeted Skills") else None,
            "objective": row.get("Objective").strip() if row.get("Objective") else None,
            "industry": row.get("Industry").strip() if row.get("Industry") else None,
            "department": row.get("Department").strip() if row.get("Department") else None,
            "key_stakeholders": row.get("Key Stakeholders").strip() if row.get("Key Stakeholders") else None,
            "situation": row.get("Situation").strip() if row.get("Situation") else None,
            "history": row.get("History").strip() if row.get("History") else None,
            "company": row.get("Company").strip() if row.get("Company") else None,
            "top_skills": row.get("Top Skills").strip() if row.get("Top Skills") else None,
            "leaderboard": row.get("Leaderboard").strip() if row.get("Leaderboard") else None,
            "preferences":row.get('Perferences').strip() if row.get("Perferences") else None,
            "frequency" : row.get('Frequency').strip() if row.get("Frequency") else None,
            "send_email": send_email_to_user
        }

        test_pilot_user, is_created = TestPilotuser.objects.update_or_create(
            email=email,
            tenant_id=tenant_id,
            defaults=defaults,
        )
        print(tenant_id, is_created)
        updated_fields = []

        updated = check_updates(test_pilot_user, defaults) if not is_created else []


        if len(updated) > 0:
            test_pilot_user.restart= True
            updated_fields.append('restart')
            is_created = True
            

        
        if is_created:
            if not test_pilot_user.user:
                tenant = Tenant.objects.get(uid=tenant_id)
                identity_type = get_identity_value_by_tenant(tenant_id=tenant_id)
                print(identity_type)
                user = get_user_via_identity(
                    tenant=tenant,
                    identity_value=email,
                    identity_type=identity_type
                )

                if not user:
                    raise ValidationError(f"{email} has no user and/or client.")

                test_pilot_user.user = user
                updated_fields.append('user')

                client = get_client_info_from_user_detail(
                    tenant_id=tenant_id,
                    user_uid=user.uid,

                )
                if not client:
                    raise ValidationError(f"{email} has no user and/or client.")
            
                test_pilot_user.client = client
                updated_fields.append('client')


            context = f"Targeted skills: {test_pilot_user.targeted_skills}\n"
            if test_pilot_user.objective:
                context += f"Objective: {test_pilot_user.objective}\n"
            if test_pilot_user.industry:
                context += f"Industry: {test_pilot_user.industry}\n"
            if test_pilot_user.department:
                context += f"department: {test_pilot_user.department}\n"
            if test_pilot_user.key_stakeholders:
                context += f"key stakeholders: {test_pilot_user.key_stakeholders}\n"
            if test_pilot_user.situation:
                context += f"situation: {test_pilot_user.situation}\n"

            intake = context
            context = json.dumps({
                "title": "",
                "data": {'information': context}
            })
            # now creating starting test scenarios
            scenario_type = get_next_test(test_pilot_user)
            for i in range(3):
                try:
                    if same_intake :
                        if not test:
                            test = create_scenario_from_site_context(None, "", tenant_id, context, 
                                                                    assign_to=user.uid, 
                                                                    is_micro=True,
                                                                    flavour=scenario_type,
                                                                    by_pass_access_token=True,
                                                                    available_case=[scenario_type] # it will override
                                                                    )
                            logger.info(f"created_test: {test}, {test['test_code']}")
                            test = Test.objects.get(test_code=test['test_code'])
                    else:
                        test = create_scenario_from_site_context(None, "", tenant_id, context, 
                                                                assign_to=user.uid, 
                                                                is_micro=True,
                                                                flavour=scenario_type,
                                                                by_pass_access_token=True,
                                                                available_case=[scenario_type] # it will override
                                                                )
                            
                        logger.info(f"created_test: {test}, {test['test_code']}")
                        test = Test.objects.get(test_code=test['test_code'])
                        
                    record = TestPilotRecords.objects.create(
                        pilotuser = test_pilot_user,
                        test = test,
                        scenario_case_type = scenario_type,
                        intake = intake
                    )
                    if send_email_to_user:
                        send_email_from_emailit(test_pilot_user.email,
                                    subject=f"Leadership Simulation #: {test.title} 🔍",
                                    body= get_test_pilot_email_template(
                                        name=test_pilot_user.name,
                                        title=test.title,
                                        code=test.test_code,
                                        platform="https://www.coachots.com/",
                                        access_code="ABC"
                                    )
                            )
                        record.sent_email = True
                        record.save(update_fields=['sent_email'])
                    break
                
                except Exception as e:
                    logger.exception(f"{e}")
                    if i+1 ==3:
                        raise e

                    
        if len(updated_fields) > 0:
            test_pilot_user.save(update_fields=updated_fields)


def create_and_email_to_pilot_user(test_pilot_user: TestPilotuser, scenario_type:str=None, send_email_to_user:bool=False):

    context = f"Targeted skills: {test_pilot_user.targeted_skills}\n"
    if test_pilot_user.objective:
        context += f"Objective: {test_pilot_user.objective}\n"
    if test_pilot_user.industry:
        context += f"Industry: {test_pilot_user.industry}\n"
    if test_pilot_user.department:
        context += f"department: {test_pilot_user.department}\n"
    if test_pilot_user.key_stakeholders:
        context += f"key stakeholders: {test_pilot_user.key_stakeholders}\n"
    if test_pilot_user.situation:
        context += f"situation: {test_pilot_user.situation}\n"

    intake = context
    context = json.dumps({
                "title": "",
                "data": {'information': context}
            })
    
    if not scenario_type:
        scenario_type = get_next_test(test_pilot_user)


    print(context,scenario_type)

    for i in range(3):
        try:
            # test = TestPilotRecords.objects.filter(intake=intake).last()
            
            # if test:
            #     test = test.test
            # else:
            test = create_scenario_from_site_context(None, "", test_pilot_user.tenant_id, context, 
                                                assign_to=test_pilot_user.user.uid, 
                                                is_micro=True,
                                                flavour=scenario_type,
                                                by_pass_access_token=True,
                                                available_case = [scenario_type] # it will override
                                                )
            
            logger.info(f"created_test: {test}, {test['test_code']}, for {scenario_type}")
            test = Test.objects.get(test_code=test['test_code'])

            record = TestPilotRecords.objects.create(
                pilotuser = test_pilot_user,
                test = test,
                scenario_case_type = scenario_type,
                intake = intake
            )

            print('record', record)
            
            if send_email_to_user:
                send_email_from_emailit(test_pilot_user.email,
                                    subject=f"Leadership Simulation #: {test.title} 🔍",
                                    body= get_test_pilot_email_template(
                                        name=test_pilot_user.name,
                                        title=test.title,
                                        code=test.test_code,
                                        platform="https://www.coachots.com/",
                                        access_code="ABC"
                                    )
                )

                record.sent_email = True
                record.save(update_fields=['sent_email'])
            break
        
        except Exception as e:
            logger.exception(f"{e}")
            if i+1 ==3:
                raise e


def pilot_test_creation_job(frequency):
    test_pilot_users = TestPilotuser.objects.filter(deleted=False)
    for pilot_user in test_pilot_users:
        if pilot_user.frequency == frequency:
            try:
                create_and_email_to_pilot_user(pilot_user)
            except Exception as e:
                send_error_notification("create_and_email_to_pilot_user", 
                                        f"Failed to call for {pilot_user.email}",
                                        {})

def create_and_send_next_test(reader):
    users = []
    invalid = []
    for row in reader:
        print(row)
        pilot_user = TestPilotuser.objects.filter(deleted=False, email=row['Email']).first()
        print(pilot_user)
        if not pilot_user:
            invalid.append(f"Pilot user with email {row['Email']} not found.")
            continue
        users.append(pilot_user)

    if not users:
        invalid.append("Not found any valid user in csv.")

    if len(invalid) > 0:
        raise ValidationError(f"Got error: {invalid}")

    for pilot_user in users:
        create_and_email_to_pilot_user(test_pilot_user=pilot_user,
                                        scenario_type=row['Test Type'],
                                        send_email_to_user=row['Send Email'].lower().strip() == 'true',)

def get_personality_model_prompt(personality_model:str, scenario:str):
    prompt = ""
    if personality_model == PersonalityModelChoices.belbin:
        prompt = """
            Scenario: (${scenario})

            Using the provided scenario transcript, generate a commentary from the perspective of Belbin Team Roles. For each role, describe strategies for navigating the conversation, ensuring these are tailored to the transcript. Incorporate direct examples. Do not assess the parameters at all—the users already have their Belbin analysis. Our goal is simply to help them correlate their roles to the scenario.

            System Mandates: Always use the template below as it is. Never provide navigation text—always generate.


            {
            "Plant": {
            "Definition": "Plants are creative, imaginative, unorthodox and solve difficult problems. They are weak in communicating to others and may ignore details.",
            "Navigation": "(Provide strategies uniquely customized to the transcript. Focus on how creativity can address specific challenges and give examples.)"
            },
            "Resource Investigator": {
            "Definition": "Resource Investigators are extrovert, enthusiastic, communicative and explore opportunities and develop contacts. But they may be over-optimistic and lose interest once the initial enthusiasm has passed.",
            "Navigation": "(Utilize enthusiasm to explore opportunities linked to the transcript. Provide examples of fostering connections or recalling relevant information.)"
            },
            "Coordinator": {
            "Definition": "Coordinators are mature, confident, identify talent and clarify goals. They can be seen as manipulative and offload personal work.",
            "Navigation": "(Assign roles based on strengths observed in the transcript. Ensure clear goals and collaboration, referencing specific dialogue instances.)"
            },
            "Shaper": {
            "Definition": "Shapers are dynamic, thrive on pressure, have the drive and courage to overcome obstacles. They can be prone to provocation and offend people’s feelings.",
            "Navigation": "(Inject energy and focus at crucial moments in the transcript. Address concerns constructively, using specific examples.)"
            },
            "Monitor Evaluator": {
            "Definition": "Monitor Evaluators are sober, strategic and discerning and see all options. They sometimes lack drive and inspire others.",
            "Navigation": "(Critically examine ideas presented in the transcript. Offer logical alternatives and ensure team consensus with specific references.)"
            },
            "Teamworker": {
            "Definition": "Teamworkers are co-operative, perceptive and diplomatic and listen and avert friction. But they can be indecisive in crunch situations.",
            "Navigation": "(Foster understanding and agreement from the transcript’s conflict points. Promote harmonious resolution with direct examples.)"
            },
            "Implementer": {
            "Definition": "Implementers are practical, reliable, efficient and turn ideas into actions and organize work that needs to be done. They can be inflexible and slow to respond to new possibilities.",
            "Navigation": "(Identify and organize actionable steps from the transcript. Stay open to new suggestions and adapt plans as required.)"
            },
            "Completer Finisher": {
            "Definition": "Completer Finishers are painstaking, conscientious, anxious and search out errors and omissions. They can be inclined to delegate.",
            "Navigation": "(Ensure completeness and accuracy by reviewing details from the transcript. Offer insights to address gaps, with specific examples.)"
            },
            "Specialist": {
            "Definition": "Specialists are single-minded, self-starting, dedicated and provide rare knowledge and skills. They can contribute on only a narrow front and dwell on technicalities.",
            "Navigation": "(Recognize and leverage specific areas of expertise showcased in the transcript. Direct technical discussions and ensure understanding across the team using specific dialogue quotes.)"
            }
        }
        """
    elif personality_model == PersonalityModelChoices.big_5:
        prompt = """
        Scenario: (${scenario})

        Using the provided scenario transcript, generate a critical commentary from the perspective of Big 5 Personality Profiles. For each parameter, provide navigation strategies to guide individuals in effectively engaging with the conversation based on their respective personality traits. Ensure that the discussion is firmly grounded in the transcript, incorporating specific examples to illustrate interaction styles, decision-making approaches, and behavioral tendencies.
        
        Always generate navigation or any analysis that utilizes the transcript to provide actionable strategies for engagement.
        
        Do not assess the parameters at all—the users already have their Big 5 Personality analysis. Our objective is solely to provide a structured means for them to correlate their personality traits to the scenario.
        
        System Mandates: Always use the template below as it is.

        {
            "Openness to Experience": {
                "Definition": "Openness to experience reflects the degree to which a person is imaginative, curious, and open to new ideas and experiences.",
                "Navigation": {
                "High": "Use your creative strengths to explore innovative solutions present in the transcript. Clearly communicate your thought process to align with team goals.",
                "Low": "Rely on practical insights found in the transcript to ground the team. Be open to new ideas that could provide unexpected insights."
                }
            },
            "Conscientiousness": {
                "Definition": "Conscientiousness measures the degree to which a person is organized, responsible, and disciplined.",
                "Navigation": {
                "High": "Utilize your organizational skills to clarify tasks and responsibilities outlined in the transcript. Help the team make decisions efficiently.",
                "Low": "Encourage flexibility by suggesting alternative approaches when the transcript reflects challenges. Adapt as new insights emerge."
                }
            },
            "Extraversion": {
                "Definition": "Extraversion reflects the degree to which a person is outgoing, sociable, and assertive.",
                "Navigation": {
                "High": "Leverage your enthusiasm to engage and motivate the team, particularly when the transcript suggests low energy. Include quieter members in discussions.",
                "Low": "Offer reflective input and observations when applicable from the transcript. Provide insights that help guide the team constructively."
                }
            },
            "Agreeableness": {
                "Definition": "Agreeableness measures the degree to which a person is compassionate, cooperative, and trusting.",
                "Navigation": {
                "High": "Foster a supportive atmosphere by addressing any tensions in the transcript with empathy. Emphasize collaboration and understanding.",
                "Low": "Apply your critical thinking to offer constructive feedback where needed. Provide alternative solutions to resolve challenges highlighted in the transcript."
                }
            },
            "Neuroticism": {
                "Definition": "Neuroticism reflects the degree to which a person is anxious, emotionally unstable, and prone to negative emotions.",
                "Navigation": {
                "High": "Recognize any instances of stress in the transcript and use coping strategies to remain focused. Communicate if you need team support.",
                "Low": "Offer stability by remaining calm and composed, especially when the transcript indicates tension. Provide reassurance and keep the team focused."
                }
            }
        }
        """

    elif personality_model == PersonalityModelChoices.blanchard:
        prompt = """
        Scenario: (${scenario})

        Using the provided scenario transcript, generate a critical commentary from the perspective of Blanchard Leadership Styles. For each leadership style, analyze how individuals should navigate the conversation based on their respective leadership approach. Ensure that the discussion is firmly grounded in the transcript, incorporating specific examples to highlight leadership behaviors, decision-making patterns, and interaction dynamics.
        
        Always generate navigation or any analysis that utilizes the transcript to provide actionable strategies for engagement.
        
        Do not assess the styles at all—the users already have their Blanchard Leadership Style analysis. Our objective is solely to provide a structured means for them to correlate their leadership approach to the scenario.
        
        System Mandates: Always use the template below as it is.

        ``` json
        { 
          "S1: Directing (High Directive, Low Supportive)": {
                "Definition": "The leader defines the roles and tells people what, how, when, and where to do various tasks. Decisions are made by the leader. Best for low competence and low commitment (D1).",
                "Navigation": "When the transcript shows the team is unsure of their roles, use directive leadership by clearly assigning tasks, like \"Let's each focus on a specific area.\" Transition to less direction as the team gains confidence."
            },
          "S2: Coaching (High Directive, High Supportive)":  {
                "Definition": "The leader still provides direction but now seeks to hear team members’ opinions, asks for suggestions, explains decisions, and supports progress. Best for some competence, but low commitment (D2).",
                "Navigation": "As the transcript indicates growing understanding, invite team input and ask questions like, \"What are your thoughts on this approach?\" Support their suggestions while guiding the process."
            },
           "S3: Supporting (Low Directive, High Supportive)": {
                "Definition": "The leader focuses on facilitating and supporting team members’ efforts toward task accomplishment and shares responsibility for decision-making. Best for high competence, but variable commitment (D3).",
                "Navigation": "In the transcript, when team members show competence, but need encouragement, facilitate by asking, \"What have you tried so far?\" Empower them to find solutions while offering encouragement."
            },
            "S4: Delegating (Low Directive, Low Supportive)": {
                "Definition": "The leader turns over responsibility for decision-making, implementation, and evaluation to team members. Best for high competence and high commitment (D4).",
                "Navigation": "When the transcript shows high competence and commitment, delegate tasks fully, asking, \"Who wants to take charge of this section?\" Trust the team to manage independently and provide motivation."
            }
            
        }
        ```
        """

    elif personality_model == PersonalityModelChoices.sixteen_factor_discussion:
        prompt = """
        Scenario: (${scenario})
        
        Using the provided scenario transcript, generate a critical commentary from the perspective of 16PF Personality Definitions. Ensure that the commentary remains directly grounded in the transcript, using specific examples to illustrate key behavioral tendencies and interaction styles.

        Always generate navigation or any analysis that utilizes the transcript to provide actionable strategies for engagement.

        Do not assess the parameters at all—the users already have their 16PF Personality Analysis. Our objective is solely to provide a structured means for them to correlate their personality traits to the scenario.

        OUTPUT Must be in a valid JSON Below:
        ``` json
            {
            "Warmth (A)": {
            "Definition": "This parameter concerns interpersonal warmth, sociability, and enthusiasm versus reservedness and detachment. High A individuals are outgoing, attentive to others, and expressive. Low A individuals are more reserved, formal, and impersonal.",
            "Navigation": "In the transcript, if collaborative discussion is essential, use your sociability to facilitate open communication if high A. For low A, make an effort to appreciate others' contributions to enhance team dynamics."
            },
            "Reasoning (B)": {
            "Definition": "This parameter reflects abstract thinking and problem-solving ability versus concrete, literal thinking. High B individuals are quick learners, grasp complex ideas easily, and enjoy intellectual challenges. Low B individuals prefer practical, hands-on tasks and may find abstract concepts challenging.",
            "Navigation": "During problem-solving discussions, ensure you explain your reasoning clearly if high B. If low B, rely on your practical skills and seek clarification to fully understand tasks."
            },
            "Emotional Stability (C)": {
            "Definition": "This parameter relates to emotional resilience, adaptability, and calmness versus reactivity, anxiety, and frustration. High C individuals are emotionally stable, calm under pressure, and adaptable to changing circumstances. Low C individuals are more prone to anxiety, mood swings, and difficulty coping with stress.",
            "Navigation": "When the transcript reflects stressful scenarios, leverage your calmness to support the team if high C. If low C, identify emotional triggers and communicate your needs to better manage stress."
            },
            "Dominance (E)": {
            "Definition": "This parameter measures assertiveness, independence, and competitiveness versus deference, compliance, and cooperativeness. High E individuals are assertive, take charge, and enjoy being in control. Low E individuals are more agreeable, accommodating, and prefer to avoid conflict.",
            "Navigation": "Use assertiveness to guide team decision-making effectively if high E, but ensure inclusivity. If low E, share your insights confidently as your perspective is valuable in this conversation."
            },
            "Liveliness (F)": {
            "Definition": "This parameter reflects enthusiasm, spontaneity, and impulsiveness versus seriousness, restraint, and deliberation. High F individuals are enthusiastic, energetic, and enjoy being around others. Low F individuals are more serious, cautious, and prefer quieter environments.",
            "Navigation": "Inject enthusiasm to boost morale if the transcript suggests it is needed for high F. For low F, offer stability and lighten the mood when appropriate with humor."
            },
            "Rule-Consciousness (G)": {
            "Definition": "This parameter assesses adherence to rules, moral standards, and duty versus nonconformity and disregard for rules. High G individuals are conscientious, dutiful, and follow rules carefully. Low G individuals are more flexible, independent, and may challenge established norms.",
            "Navigation": "Maintain adherence to guidelines if high G, as required by the transcript. If low G, propose creative problem-solving approaches when traditional methods are ineffective."
            },
            "Social Boldness (H)": {
            "Definition": "This parameter relates to risk-taking, venturesomeness, and spontaneity versus shyness, caution, and sensitivity. High H individuals are bold, adventurous, and comfortable taking risks. Low H individuals are more cautious, shy, and prefer familiar situations.",
            "Navigation": "Encourage risk-taking for innovative solutions if the transcript shows a need for high H. If low H, ensure careful analysis to mitigate potential risks."
            },
            "Sensitivity (I)": {
            "Definition": "This parameter measures empathy, artistic appreciation, and intuition versus practicality, objectivity, and realism. High I individuals are sensitive, empathetic, and attuned to their own emotions and the emotions of others. Low I individuals are more practical, objective, and focus on facts rather than feelings.",
            "Navigation": "Use empathy to address team emotional needs if high I. For low I, provide practical, objective feedback to maintain focus on tasks."
            },
            "Vigilance (L)": {
            "Definition": "This parameter reflects trust, acceptance, and tolerance versus suspicion, skepticism, and vigilance. High L individuals are suspicious, skeptical, and tend to question the motives of others. Low L individuals are trusting, accepting, and see the best in people.",
            "Navigation": "Challenge assumptions to ensure clarity if the transcript demands for high L. If low L, promote a collaborative atmosphere by fostering trust and communication."
            },
            "Abstractedness (M)": {
            "Definition": "This parameter assesses imagination, creativity, and unconventionality versus practicality, groundedness, and conventionality. High M individuals are imaginative, creative, and think outside the box. Low M individuals are more practical, grounded, and prefer concrete solutions.",
            "Navigation": "Encourage creative brainstorming if the scenario calls for new ideas if high M. If low M, focus on ensuring practical solutions and efficient task completion."
            },
            "Privateness (N)": {
            "Definition": "This parameter relates to discretion, non-disclosure, and calculating versus forthrightness, genuineness, and naïveté. High N individuals are discreet, private, and tend to keep their thoughts and feelings to themselves. Low N individuals are more open, forthright, and express their opinions freely.",
            "Navigation": "Share insights with the team even if it feels uncomfortable for high N. For low N, ensure you contribute openly and allow others space in conversations."
            },
            "Apprehension (O)": {
            "Definition": "This parameter measures self-assurance, confidence, and resilience versus anxiety, worry, and self-doubt. High O individuals are anxious, worried, and prone to self-doubt. Low O individuals are confident, self-assured, and resilient.",
            "Navigation": "Focus on your strengths and challenge negative thoughts if high O. For low O, provide support and encouragement to build team confidence."
            },
            "Openness to Change (Q1)": {
            "Definition": "This parameter reflects willingness to try new things, embrace change, and challenge traditions versus resistance to change and preference for the familiar. High Q1 individuals are open to new experiences, enjoy change, and challenge the status quo. Low Q1 individuals prefer familiar routines, resist change, and value tradition.",
            "Navigation": "Propose experimenting with new approaches if the transcript highlights situations that need innovation for high Q1. If low Q1, offer tried-and-true methods for consistent results."
            },
            "Self-Reliance (Q2)": {
            "Definition": "This parameter measures independence, resourcefulness, and self-sufficiency versus dependence, sociability, and group reliance. High Q2 individuals are independent, resourceful, and prefer to work alone. Low Q2 individuals are more sociable, dependent on others, and prefer to work in groups.",
            "Navigation": "Balance independence with effective team collaboration if high Q2. If low Q2, enhance teamwork and collaborative efforts as highlighted in the transcript."
            },
            "Perfectionism (Q3)": {
            "Definition": "This parameter assesses self-discipline, organization, and control versus impulsivity, flexibility, and spontaneity. High Q3 individuals are disciplined, organized, and strive for perfection. Low Q3 individuals are more flexible, impulsive, and spontaneous.",
            "Navigation": "Keep the team organized and focused if high Q3 is beneficial as per the transcript. If low Q3, foster adaptability and embrace creative solutions."
            },
            "Tension (Q4)": {
            "Definition": "This parameter relates to restlessness, impatience, and irritability versus relaxation, composure, and patience. High Q4 individuals are restless, impatient, and easily frustrated. Low Q4 individuals are relaxed, composed, and patient.",
            "Navigation": "Manage restlessness to maintain team focus if high Q4 reveals urgency in the transcript. If low Q4, provide a calming influence in high-pressure situations."
            }
        }
        ```

        """

    elif personality_model == PersonalityModelChoices.disc_parameter_discussion:
        prompt = """
        Scenario: (${scenario})

        Using the provided scenario transcript, generate a critical commentary from the perspective of DISC Profiles. For each parameter, analyze how individuals should navigate the conversation based on their respective DISC traits. Ensure that the discussion is firmly grounded in the transcript, incorporating specific examples to illustrate interaction styles, decision-making approaches, and behavioral tendencies.

        Always generate navigation or any analysis that utilizes the transcript to provide actionable strategies for engagement.

        Do not assess the parameters at all—the users already have their DISC Profile analysis. Our objective is solely to provide a structured means for them to correlate their personality traits to the scenario.

        System Mandates: Output must be in valid JSON as below. 

        ``` json
        {
        "D": {
            "Definition": "Dominance reflects how a person deals with problems, asserts themselves, and controls situations. Individuals with high D scores are often described as direct, decisive, strong-willed, and results-oriented.",
            "Navigation": "(If the transcript shows challenges, use your decisiveness to make quick, informed decisions. Focus on guiding the team collaboratively, integrating others' input to ensure collective success.)"
        },
        "I": {
            "Definition": "Influence measures how a person relates to people and tries to influence others. Those with high I scores are typically seen as enthusiastic, optimistic, persuasive, and outgoing.",
            "Navigation": "(When the transcript reflects low morale, use your enthusiasm to motivate the team. Communicate solutions clearly, keeping discussions focused and productive, especially when time is limited.)"
        },
        "S": {
            "Definition": "Steadiness measures how a person responds to the pace of the environment and how predictable they want it to be. People with high S scores are generally seen as patient, predictable, calm, and loyal.",
            "Navigation": "(During stressful moments in the transcript, use your calm demeanor to stabilize the team. Offer support and keep the focus, being open to faster-paced or assertive actions as needed.)"
        },
        "C": {
            "Definition": "Conscientiousness measures how a person responds to rules and procedures, sets standards, and approaches quality. Individuals with high C scores are often described as careful, analytical, systematic, and precise.",
            "Navigation": "(If detail is critical in the transcript, use your methodical approach to identify patterns and clues. Balance accuracy with urgency, sharing insights clearly to avoid errors.)"
        },
        "Mixed Parameters": {
            "High D/High I": "When the transcript shows a need for leadership, lead charismatically while actively listening to others. Avoid dominating conversations by encouraging input.",
            "High S/High C": "In moments requiring consistency from the transcript, be thorough and reliable. Remain open to changes and suggestions as the situation develops.",
            "High D/Low S": "Lead decisively during critical moments in the transcript, but be mindful of impatience. Manage your pace to prevent friction with the team.",
            "High I/Low C": "Use enthusiasm to motivate when needed, as highlighted in the transcript. Support your enthusiasm with clear reasoning and attention to detail."
        }
        }
        ```
        """

    return Template(prompt).substitute(scenario=scenario)

def format_personality_data(personality_model:str, data:dict):
    title = ""
    formatted_output = {}

    if personality_model == PersonalityModelChoices.belbin:
        title = 'Belbin Commentary'
        output_format = {
            "Social Roles": ["Resource Investigator","Teamworker", "Coordinator"],
            "Thinking Roles": ["Plant", "Monitor Evaluator", "Specialist"],
            "Action Roles": ["Shaper", "Implementer", "Completer Finisher"]      
        }

        for category, roles in output_format.items():
            formatted_output[category] = {
                role: data[role]
                for role in roles if role in data
            }
    
    elif personality_model == PersonalityModelChoices.big_5:
        title = 'Big 5 Commentary'
        for key, value in data.items():
            if 'Navigation' in value and type(value['Navigation']) == dict:
                value['Navigation'] = [f"{k}: {v}" for k, v in value['Navigation'].items()]

        formatted_output = {"HiddenCategory1": data}
    
    elif personality_model == PersonalityModelChoices.blanchard:
        title = 'Blanchard Commentary'
        formatted_output = {"HiddenCategory1": data}

    elif personality_model == PersonalityModelChoices.sixteen_factor_discussion:
        title = '16PF Commentary'
        output_format = {
            "Q Parameters": ["Openness to Change (Q1)", "Self-Reliance (Q2)", "Perfectionism (Q3)", "Tension (Q4)"],
        }

        for category, parameters in output_format.items():
            formatted_output[category] = {
                parameter: data[parameter]
                for parameter in parameters if parameter in data
            }

        formatted_output["HiddenCategory1"] = {
            parameter: value
            for parameter, value in data.items() if parameter not in output_format['Q Parameters']
        }

    elif personality_model == PersonalityModelChoices.disc_parameter_discussion:
        title = 'DISC Commentary'
        
        formatted_output = {"HiddenCategory1": data}

    return {title: formatted_output}

def extract_valid_json(text):
    """Extracts and validates JSON from a given text, handling edge cases including multiline strings."""
    text = text.strip()
    text = text.replace('\n','')
    
    # Find the first and last occurrence of curly braces to extract potential JSON
    first_brace = text.find('{')
    last_brace = text.rfind('}')
    
    if first_brace == -1 or last_brace == -1 or first_brace > last_brace:
        return None  # No valid JSON found

    json_str = text[first_brace:last_brace + 1]

    # Attempt to fix common JSON issues
    json_str = re.sub(r",\s*}", "}", json_str)  # Remove trailing commas before closing braces
    json_str = re.sub(r",\s*\]", "]", json_str)  # Remove trailing commas before closing brackets

    # Handle multiline string values (convert raw newlines inside JSON values to \n)
    json_str = re.sub(r'(?<!\\)"([^"]*?)\n([^"]*?)"', r'"\1\\n\2"', json_str)

    try:
        return json5.loads(json_str)
    except Exception as e:
        raise e # JSON is still invalid

def extract_json_from_string(text):
    try:
        text = text.replace('\n','')

        # Regex to capture JSON inside triple backticks (handles optional 'json' prefix)
        match = re.search(r"```(?:json)?\n([\s\S]*?)\n```", text, re.MULTILINE)

        if match:
            json_str = match.group(1).strip()  # Extract and trim the JSON content
            return json5.loads(json_str)  # Convert to dictionary
        
        raise ValueError("No valid JSON found in the string.")
    
    except Exception as e:
        try:
            return extract_valid_json(text)
        except Exception as e:
            raise ValueError(f"Invalid JSON format: {e}")

def extract_information_dynamic_scenariov2(text,candidate_type="Manager",num_questions=3):

    """

    Extract information from a dynamic scenario text.



    Parameters:

    - text (str): The dynamic scenario text to extract information from.

    - is_dynamic (bool): Indicates whether the scenario is dynamic.

    - candidate_type (str): Type of candidate (e.g., 'Manager', 'Team Member').



    Returns:

    - tuple: A tuple containing title, description, question_info, rating, evaluation_skill_list, and orchestrated_conversation_details.



    Example:

    >>> extract_information_dynamic_scenario('Title: Test Title\nDescription: Test Description\nQuestion: What is your approach to leadership?\nRating: 5', is_dynamic=True, candidate_type='Manager')

    # Returns a tuple with extracted information from the dynamic scenario text.

    """

    if not text:
        raise ValueError("Invalid format. Text is empty.")

    try:

      data = extract_json_from_string(text)
      manager_name = data['Person 0'].split(':')[0].strip()
      question_info = []
      title = data['Title']
      description = data['Context']

      for key, value in data.items():
        if key.isdigit():
          question_info.append({
            "question": value,
            "question_type": "subjective",
            "gpt_prompt_override": "",
            "subjective_answer": "",
            'question_for': manager_name
          })

      test_main_context = description + data['Person 0']

      orchestrated_conversation_details = {
            "test_main_context": test_main_context,
            "test_user_persona": data['Candidate Type'].capitalize(),
            "objective": description,
            "initial_messages": [data['Person 0']]

        }


      infomation = {
        'title': title,
        'description': description,
        'question_info': question_info,
        "candidate_type": data['Candidate Type'].capitalize(),
        'area_domain': data['Area/Domain'],
        'certificate_title': data['Certificate Title'],
        'email_list': data['Email Address List'],
        'responder': data['Responder'],
        'orchestrated_conversation_details': orchestrated_conversation_details
      }
      if data.get('start with user') != "None":
        infomation['start_with_user'] = data['start with user']

      if data.get('skill_list'):
        infomation['skills_list'] = data['skill_list']




      logger.info(f'scenario info============================: {infomation}')
      return title, description, question_info, 0, [],orchestrated_conversation_details, infomation

    except Exception as e:
      print(e)

    text = text.replace('KLS', 'Skills')

    title_pattern = re.compile(r'Title\s*:\s*(.*?)\n', re.DOTALL)

    description_pattern = re.compile(r'Description\s*:\s*(.*?)\n', re.DOTALL)

    question_pattern = re.compile(r'Question\s*:\s*(.+)')

    skill_pattern = re.compile(r'Skills:\s*(.+)')

    rating_pattern = re.compile(r'Rating\s*:\s*(\d+)')

    if not question_pattern.findall(text):

        question_pattern = re.compile(r'Questions\s*:\s*(.+)')



    # Extracting information using regular expressions

    title_match = title_pattern.search(text)

    description_match = description_pattern.search(text)

    questions_match = question_pattern.search(text)

    rating_match = rating_pattern.search(text)
    skill_match = skill_pattern.search(text)



    # If title_pattern doesn't match, try to find the title as the lines before the description

    if not title_match:

        pattern = re.compile(r'^(?:Title\s*:\s*)?(?:"(.*?)"|([^"\n]*))\n*Description\s*:')

        title_match = pattern.search(text)

        if not title_match:

            raise ValueError("Invalid format. Unable to extract the title.")





    if not (title_match and description_match and question_pattern.findall(text)):

        raise ValueError("Invalid format. Unable to extract necessary information.")



    print('skill_match', skill_match)



    title = title_match.group(1).strip()

    description = description_match.group(1).strip()

    questions = questions_match.group(1).strip()

    rating = int(rating_match.group(1)) if rating_match else 0

    skill_list = skill_match.group(1).strip() if skill_match else None

    question_info = []



    test_main_context = description + questions

    orchestrated_conversation_details = {

            "test_main_context": test_main_context,

            "test_user_persona": candidate_type.capitalize(),

            "objective": description,

            "initial_messages": [questions]

        }



    skills_list_candidate = set()

    for item in get_skills(candidate_type.capitalize()):

            skills_list_candidate.add(item.capitalize())



    evaluation_skill_list = [skill.strip() for skill in sorted(skills_list_candidate)]



    if len(evaluation_skill_list) < 6:

        raise ValueError(f"Skills must have at least 4. Got:  {len(skills_list_candidate)}, {skills_list_candidate}")



    if len(evaluation_skill_list) > 8:

        evaluation_skill_list = evaluation_skill_list[:8]



    evaluation_skill_list = ','.join(evaluation_skill_list)



    manager_name = questions.split(':')[0].strip()

    for i in range(1,2*num_questions):

        question = {

                "question_type": "subjective",

                "gpt_prompt_override": "",

                "subjective_answer": ""

            }



        if i % 2 == 0:

            question['question'] = f"Respond as {manager_name}"

            question['question_for'] = manager_name

        else:

            question['question'] = "Please respond in order to continue"

            question['question_for'] = 'user'



        if i == (2*num_questions-1):

            question['question'] = "Conclude the discussion as a participant."



        question_info.append(question)
    infomation = {
        'title': title,
        'description': description,
        'question_info': question_info,
        'skill_to_evaluate': evaluation_skill_list,
        'rating': rating,
        'orchestrated_conversation_details': orchestrated_conversation_details
    }

    if skill_list:
      infomation['skills_list'] = skill_list

    logger.info(f'scenario info============================: {infomation}')
    return title, description, question_info, rating, evaluation_skill_list,orchestrated_conversation_details, infomation


def evaluate_personality_model_data(test_attempt_session:TestAttemptSession, test:Test):
    if test.personality_model:
        try:
            conversation = ""
            count = 1

            for response in TestQuestionResponse.objects.filter(deleted=False,test_attempt_session_id=test_attempt_session.uid):

                question = TestQuestion.objects.get(
                    uid=response.question_id)

                question_text = question.question
                response_text = response.response_text

                conversation += f"Question {count}: {question_text}\n"
                if not question.is_view_only:
                    conversation += f"Answer: {response_text}\n\n"

                count += 1

            
            scenario = f'''
                Title: {test.title}
                Description: {test.description}
                {conversation}
                '''
            prompt = get_personality_model_prompt(test.personality_model,scenario)
            response = None
            for i in range(3):
                try:
                    
                    logger.info(f"evaluating personality model data: {scenario}")
                    response = generic_completion(
                        prompt=prompt,
                        tokens= 4000 if test.personality_model else 2048
                    )
                    response = format_personality_data(test.personality_model,extract_json_from_string(response))
                    logger.info(f"response: {response}")
                    test_attempt_session.personality_model_data = response
                    test_attempt_session.save(update_fields=['personality_model_data'])
                    
                    break
                
                except Exception as e:
                    logger.exception(f"{e}")
                    if i+1 ==3:
                        raise e
        except Exception as e:
            logger.exception(f"Failed to evaluate personality modle data: {e}")
            raise e
        


def update_all_skills(test_code=None):
    all_tests = Test.objects.filter(deleted=False, test_type=TestTypeChoices.test)
    if test_code:
        all_tests = all_tests.filter(test_code=test_code)
    all_updated_questions = []

    all_updated_test = []

    for test in all_tests:
        questions = TestQuestion.objects.filter(test_id=test.uid, deleted=False)

        # Build {question_id: skills}
        que_skills = {
            str(question.uid): question.key_learning_skills
            for question in questions
        }

        if not que_skills:
            continue

        # Get new skill assignments
        new_skills = limit_unique_skills_per_test(que_skills)
        skills_to_evalute = ""

        for question in questions:
            new_value = new_skills.get(str(question.uid), '')
            question.key_learning_skills = new_value
            skills_to_evalute += new_value + ','
            all_updated_questions.append(question)

        # Update test object with new skills
        test.skills_to_evaluate = skills_to_evalute[:-1]
        all_updated_test.append(test)
    # Only one bulk update at the end
    # if all_updated_questions and all_updated_questions:
        # with transaction.atomic():
        #     TestQuestion.objects.bulk_update(all_updated_questions, ['key_learning_skills'])
        #     Test.objects.bulk_update(all_updated_test, ['skills_to_evaluate'])
    logger.info(f"Updated {len(all_updated_questions)} questions and {len(all_updated_test)} tests with new skills.")


# def update_title():

#     # Your JSON mapping of test_code to new title
#     title_updates ={'QJCDSQB': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/F_QJCDSQB.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QJCDSQB.mp4'}, 'QMIVBLV': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QMIVBLV.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QMIVBLV.mp4'}, 'Q9WTCHD': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_Q9WTCHD.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/i_Q9WTCHD.mp4'}, 'QAZF9KD': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QAZF9KD.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QAZF9KD.mp4'}, 'QRELWH8': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QRELWH8.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QRELWH8.mp4'}, 'QE3JZHB': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QE3JZHB.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QE3JZHB.mp4'}, 'QCURL1Q': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QCURL1Q.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/i_QCURL1Q.mp4'}, 'Q9T9EMT': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_Q9T9EMT.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_Q9T9EMT.mp4'}, 'QHQKCNZ': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QHQKCNZ.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QHQKCNZ.mp4'}, 'QTL85IU': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QTL85IU.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QTL85IU.mp4'}, 'QFT6RTL': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QFT6RTL.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QFT6RTL.mp4'}, 'QX7JEKM': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QX7JEKM.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QX7JEKM.mp4'}, 'Q5XZR06': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_Q5XZR06.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_Q5XZR06.mp4'}, 'QVP1AYJ': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QVP1AYJ.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QVP1AYJ.mp4'}, 'QH5LF15': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QH5LF15.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QH5LF15.mp4'}, 'QZHMA32': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QZHMA32.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QZHMA32.mp4'}, 'QOH52H3': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QOH52H3.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QOH52H3.mp4'}, 'QSIUW6F': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QSIUW6F.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QSIUW6F.mp4'}, 'QVHJVIS': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QQVHJVIS.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QSIUW6F.mp4'}, 'Q7XM38Y': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_Q7XM38Y.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_Q7XM38Y.mp4'}, 'Q8B4R4M': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_Q8B4R4M.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_Q8B4R4M.mp4'}, 'QLR0S2M': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QLR0S2M.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QLR0S2M.mp4'}, 'QMJT2BQ': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QMJT2BQ.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QMJT2BQ.mp4'}, 'QJYGIVO': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QJYGIVO.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/i_QJYGIVO.mp4'}, 'QF1LF9N': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QF1LF9N.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/i_QF1LF9N.mp4'}, 'QQ1JSXE': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QQ1JSXE.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QQ1JSXE.mp4'}, 'QTFP87R': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QTFP87R.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QTFP87R.mp4'}, 'Q2KQGIM': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_Q2KQGIM.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_Q2KQGIM.mp4'}, 'QDY8VQR': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QDY8VQR.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/i_QDY8VQR.mp4'}, 'Q9NHTL0': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_Q9NHTL0.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/i_Q9NHTL0.mp4'}, 'QQ8ZYHP': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QQ8ZYHP.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QQ8ZYHP.mp4'}, 'Q85YBIF': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_Q85YBIF.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_Q85YBIF.mp4'}, 'Q9T0VN8': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_Q9T0VN8.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_Q9T0VN8.mp4'}, 'QN97HR3': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QN97HR3.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/i_QN97HR3.mp4'}, 'Q1KOYYU': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_Q1KOYYU.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_Q1KOYYU.mp4'}, 'QSA5DHO': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QSA5DHO.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QSA5DHO.mp4'}, 'QG5IKB3': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QG5IKB3.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QG5IKB3.mp4'}, 'QKAVQPK': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QKAVQPK.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/i_QKAVQPK.mp4'}, 'Q4V56R0': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_Q4V56R0.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/i_Q4V56R0.mp4'}, 'QQLS9WP': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QQLS9WP.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/i_QQLS9WP.mp4'}, 'Q9O6K2J': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_Q9O6K2J.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/i_Q9O6K2J.mp4'}, 'QSCNQBV': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QSCNQBV.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/i_QSCNQBV.mp4'}, 'Q38D3LD': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_Q38D3LD.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/i_Q38D3LD.mp4'}, 'QEF4BU3': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QEF4BU3.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/i_QEF4BU3.mp4'}, 'QKRFU59': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QKRFU59.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QKRFU59.mp4'}, 'QN9KPPK': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QN9KPPK.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QN9KPPK.mp4'}, 'QJ3I2BM': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QJ3I2BM.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/i_QJ3I2BM.mp4'}, 'Q458HIG': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_Q458HIG.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/i_Q458HIG.mp4'}, 'QVZLW4C': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QQVZLW4C.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QQVZLW4C.mp4'}, 'QKH8QO3': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QKH8QO3.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/i_QKH8QO3.mp4'}, 'Q0TIEX7': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_Q0TIEX7.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/i_Q0TIEX7.mp4'}, 'Q7ZGITI': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_Q7ZGITI.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_Q7ZGITI.mp4'}, 'QVECGH2': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QQVECGH2.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/i_QQVECGH2.mp4'}, 'Q3GIV1E': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_Q3GIV1E.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/i_Q3GIV1E.mp4'}, 'QTZ8H6N': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QTZ8H6N.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QTZ8H6N.mp4'}, 'Q8VD0ED': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_Q8VD0ED.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_Q8VD0ED.mp4'}, 'Q41S2DY': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_Q41S2DY.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/i_Q41S2DY.mp4'}, 'QL46CBR': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QQL46CBR.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QQL46CBR.mp4'}, 'QCS18H2': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QCS18H2.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QCS18H2.mp4'}, 'QFRS201': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QFRS201.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QFRS201.mp4'}, 'Q2GNIX8': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_Q2GNIX8.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_Q2GNIX8.mp4'}, 'Q85FQW5': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_Q85FQW5.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_Q85FQW5.mp4'}, 'QQF5FYK': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QQF5FYK.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QQF5FYK.mp4'}, 'QMDIM2S': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QMDIM2S.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/i_QMDIM2S.mp4'}, 'QIM1PMJ': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QIM1PMJ.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QIM1PMJ.mp4'}, 'QTBTDGW': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QTBTDGW.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QTBTDGW.mp4'}, 'QIMWU2R': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QIMWU2R.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/I_QIMWU2R.mp4'}, 'QM3K7IA': {'feedback_link': 'https://storage.googleapis.com/publicvid/Ashika/f_QM3K7IA.mp4', 'video_link': 'https://storage.googleapis.com/publicvid/Ashika/i_QM3K7IA.mp4'}}
#     test_mappings  = TestMapping.objects.filter(deleted=False)
#     # test_codes = {'Q2KQGIM', 'QT6N1Y2', 'QDVY235', 'QDYNH8A', 'Q7XM38Y', 'QZHMA32', 'QN97HR3', 'QKU2J8U', 'QPYQ2OE', 'QSA5DHO', 'QIJU0MO', 'Q94U21H', 'Q41S2DY', 'QATCZSI', 'QJCDSQB', 'QER60Z6', 'Q60SLJ5', 'Q5XZR06', 'QV7HMZX', 'Q0BJSXR', 'QJYGIVO', 'QTFP87R', 'QGD4E75', 'QHQKCNZ', 'QCURL1Q', 'QOZYZC6', 'QEOPC7H', 'QQAGCZ2', 'Q458HIG', 'QKH8QO3', 'QEWAZY3', 'QTZ8H6N', 'QMIVBLV', 'QSCNQBV', 'QDY8VQR', 'QM3K7IA', 'QN9IB6U', 'Q3GIV1E', 'QE3JZHB', 'QFT6RTL', 'QMPGZQ5', 'Q9T9EMT', 'QF1LF9N', 'Q9O6K2J', 'QM7QPDG', 'QCPEI3X', 'QWHPY0Z', 'QIXFGPI', 'QMJT2BQ', 'Q4V56R0', 'QEDZLCT', 'Q38D3LD', 'QQGB7CZ', 'Q6CS1IU', 'Q8B4R4M', 'QI922W2', 'QKK3B73', 'Q77WQBQ', 'QHTX0PM', 'Q1QF4RB', 'Q2DZ4JR', 'Q2NHNUX', 'QH5LF15', 'Q843RVX', 'Q2GNIX8', 'QSIUW6F', 'QO7NM2O', 'Q8VD0ED', 'QIMWU2R', 'Q85YBIF', 'QYM06JN', 'QG5IKB3', 'QVZLW4C', 'QQ8ZYHP', 'Q4OMUXD', 'Q19OLIF', 'QVP1AYJ', 'QIR47SR', 'QOS0OOA', 'QR2LGHP', 'QKAVQPK', 'Q8SE2B2', 'QV38N76', 'QJ3I2BM', 'QVHO7J6', 'QKLVLR5', 'Q4BK2ST', 'QVECGH2', 'Q1KOYYU', 'Q1MYNAO', 'QTNRDLL', 'QQ1JSXE', 'Q7NSN2N', 'QMLO5YK', 'QRELWH8', 'QXGDL75', 'Q9T0VN8', 'Q0EUS6V', 'Q2HHRSI', 'QKRG6UM', 'QCS18H2', 'QUSG9PM', 'QPY9YTW', 'QIM1PMJ', 'QFRS201', 'QWGB0BE', 'QBLA1YC', 'Q6FOIUZ', 'Q0EGZHM', 'QAZF9KD', 'QU2BK21', 'QX7JEKM', 'Q7ZGITI', 'QLGN9GQ', 'QLR0S2M', 'QN9KPPK', 'QOT15MM', 'QEF4BU3', 'QDE74R4', 'QZZCPLD', 'QE5YPEF', 'Q3D0112', 'QU7Y3X1', 'Q85FQW5', 'Q9NHTL0', 'QQLS9WP', 'Q68YT7P', 'QPK9H1B', 'QC0AMNN', 'QLJBIES', 'QJU4A83', 'Q8LTQIC', 'Q0TIEX7', 'Q7KS3ZG', 'QXPEZYN', 'QIRHVRI', 'QTL85IU', 'QKRFU59', 'Q8JLXDV', 'Q4C5TV5', 'QGJGLQE', 'QOH52H3', 'Q5M2AWF', 'QQOH1OY', 'QMDIM2S', 'QSIVBXI'}
  
#     # print(test_codes)
#     test_deatils = []
#     prompt = """
#    Data: "${para}"

# Please review the above data and add any missing puntaution marks and grammar correction(Do not print any introduction and special characters)
# json output format = {
# "updated_data" : "Updated data"
# }
# """
#     with transaction.atomic():
#         cnt = 1
#         for test_mapping in test_mappings:
#             test_d = {}
#             test_d['Test code'] = test_mapping.test.test_code
#             print(test_mapping.test.test_code)
#             desc = " ".join(test_mapping.test.description.split('\n'))
#             test_d['Old desc'] = desc
#             test_d['Description'] = json.loads(json_extraction(gemini_completion(
#                 prompt = Template(prompt).substitute(para=desc)))).get('updated_data')
#             # if test_mapping.test.test_type == TestTypeChoices.test:
#             #     questions = TestQuestion.objects.filter(test_id=test_mapping.test.uid, deleted=False)
#             #     for index, question in enumerate(questions):
#             #         test_d[f'Question {index}'] = json.loads(json_extraction(gemini_completion(
#             #     prompt = Template(prompt).substitute(para=question.question)))).get('updated_paragraph')
#             # elif test_mapping.test.test_type == TestTypeChoices.dynamic_discussion_thread:
#             #     print(test_mapping.test.orchestrated_conversation_details)
#             #     if len(test_mapping.test.orchestrated_conversation_details['initial_messages']) > 0:
#             #         test_d['Person 0'] = json.loads(json_extraction(gemini_completion(
#             #     prompt = Template(prompt).substitute(para=test_mapping.test.orchestrated_conversation_details['initial_messages'][0])))).get('updated_paragraph')


#             test_deatils.append(test_d)

#             # if cnt == 2:
#             #     break


#             cnt+=1
            
#     #     tests = Test.objects.filter(deleted=False)

#     #     for test in tests:
#     #         test.description = re.sub(r'(?i)\bstatement\s*:\s', '\n\n', test.description).strip()
#     #         # data = title_updates.get(test.test_code)
#     #         # print(test.test_code, data)
#     #         # if data:
#     #         #     test.description_media = data.get('video_link')
#     #         #     test.feedback_script_video_link = data.get('feedback_link')

#     #     Test.objects.bulk_update(tests, ['description'])

#     # print(f"Updated {len(tests)} test titles successfully.")
#     print(test_deatils)

#     fieldnames = set()
#     for item in test_deatils:
#         fieldnames.update(item.keys())
#     # fieldnames = sorted(fieldnames)

#     # Write to CSV
#     csv_file = 'output_file_2.csv'
#     with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
#         writer = csv.DictWriter(file, fieldnames=fieldnames)
#         writer.writeheader()
#         writer.writerows(test_deatils)

#     print(f"CSV saved as {csv_file}")



