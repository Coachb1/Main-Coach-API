import csv
import re
import json
import requests
import os
from dotenv import load_dotenv
from io import TextIOWrapper
import logging
from django.http import HttpResponse

from skills.helpers import generate_culture_map
from .constants import get_skills
from settings import BACKEND
from skills.constants import skills as pre_defined_skills
from tests.models import TestTypeChoices
from users.models import  ClientUserInfo
from tenants.helpers import tenant_from_subdomain_prefix
from commons.youtube_utils import format_youtube_link

load_dotenv()
logger = logging.getLogger(__name__)

# API endpoint URL move to env
API_ENDPOINT_LOGIN_WEB = os.getenv("API_ENDPOINT_LOGIN_WEB")
API_ENDPOINT_WEB = os.getenv("API_ENDPOINT_WEB")
API_ENDPOINT_SLACK = f"{BACKEND}/api/v1/tests/"
API_ENDPOINT_LOGIN_SLACK = os.getenv("API_ENDPOINT_LOGIN_SLACK")
LOCALHOST = "http://localhost:8000/api/v1/tests/"

# CONSTANTS
COURSE = "Course"  # not using as not implemented in backend
SOURCE = "source"  
TITLE = "Title"
INTERACTION_MODE = "Interaction Mode"
TEST_TYPE = "Test Type"
DESCRIPTION = "Test description"
QUESTION = "Question"
CUSTOM_PROMPT = "Custom Prompt"
KLP = "KLP"
KLS = "KLS"
QUESTION_INSIGHT = "QnA Insight"
EMAIL_ADDRESS_LIST = "Email Address List"
SEND_ONLY_TO_EMAIL = "Send only to email"
EMAIL_CANDIDATE = "Email Candidate"
CANDIDATE_TYPE = "Candidate Type"
DESCRIPTION_MEDIA = "Description Media"
MAX_TEST_ALLOWED = "Max Test Allowed"
IS_CHECKIN_TYPE = "is checkin type"
SKILLS_TO_EVALUATE = "Skills_list"
IS_LEARNER_PATH = "is learner path"
TED_TALK_AND_HBR_CASE = "Ted talks and HBR Case"
IS_EMAIL_TYPE = "is_email_type"
SCENARIO_CASE = "Scenario Case"
RATINGS = "rating"
IS_GAME_TYPE = "is_game_type"
IMAGE_URL = "image_url"
IS_DYNAMIC = "is_dynamic"
IS_DYNAMIC_THREAD = "is_dynamic_thread"
MEDIA_LINK = 'Que Media'
CLIENT = "Client Name"
GOALS = "Goals"
COURSE = "Course"
INDUSTRY = "Industry"
EXP_LEVEL = "Experience Level"
START_WITH_USER = "start with user"
IS_FREE = 'is_free'
BACKGROUND = 'Background'
CERTIFICATE_TITLE = "Certificate Title"
CERTIFICATE_DESCRIPTION = "Certificate Description"
TITLEUI = 'Title UI'
DESCRIPTIONUI = 'Description UI'
QUESTIONUI = 'Que UI'
IS_MICRO = 'is_micro'
IS_LOGGEDiN = 'is_logged_in'
IS_IMMERSIVE = 'Is Immersive'
TEST_CUSTUM_PROMPT = 'Test Custum Prompt'
TEST_IMAGE_LINK = 'Test Image Link'
TEST_IMAGE_PROPS = 'Test Image Props'
QUE_IMAGE_LINK = 'Que Image Link'
QUE_IMAGE_PROPS = 'Que Image Props'
NARRATION = 'Que Narration'
TEST_NARRATION = 'Test Narration'
ANSWER = 'Correct answer'
IS_TRANSCRIPT_ONLY = "Is Transcript Only"
IS_PITCH = "is_pitch"
CURRENT_NEWS = 'Current news'
BOT_NAME = "Bot Name"
USER_ID = "User ID" 
AREA_DOMAIN = "Area/Domain"
TAB_CATEGORY = "Tab Category"
SUB_TAB_CATEGORY = "Sub Tab Category"
IS_RECOMMENDED = 'Is Recommended'
VISUAL_TAGS = 'Visual Tags'
PAGE_NAME = 'Page Name'
USER_EMAIL = 'User Email'
COMPETENCY_SKILLS= 'Competency Skill'
RESPONDER = "Responder"
CALCULATE_CULTURE = "Calculate Culture"
TEST_SNIPPET_LINK = "Test Snippet Link"
QUE_SNIPPET_LINK = "Que Snippet Link"
TEST_CODE = "Test Code"
SECTIONS = "Sections"
PSYCHOMETRIC = "Psychometric Set"
REPORT_DESCRIPTION = "Report Description"
CATEGORY = "Category"
IS_SINGLE_SELECT = "Is Single Select"
PSYCHOMETRIC_REPORT_CONFIG = 'Psychometric Report Config'
PERSONALITY_MODEL = 'Personality Model'
ASKER_UI = 'Asker UI'
SKILL_DOMAIN = "Skill Domain"
CREATOR_PROMPT_TYPE = "Scenario Prompt Type"
VIDEO_SCRIPT = 'Video Script'
SCRIPT_VIDEO_LINK = 'Script Video Link'
FEEDBACK_SCRIPT_VIDEO_LINK = 'Feedback Video Link'
FEEDBACK_VIDEO_SCRIPT = 'Feedback Video Script'
TIME_LIMIT = "Time Limit"
INSTRUCTION_MEDIA_LINK = "Instruction Media"
NOTICE_BOARD = "Notice Board"
CULTURE_SKILLS =  "Culture Skills"
MCQ_OPTIONS = "Option"
MCQ_OPTIONS_MARKS = "OPT Marks"
IS_ASSESSMENT = "Is Assessment"
QUE_EXPLANATION = 'Q Explanation'
QUE_MARKS = "Q Marks"

SCORE_VISIBLE = "Score Visible"
EXPLANATION_VISIBLE = "Explanation Visible"

# range and feedback associated with the range score it generally for game but can be used for all test

RANGE = "Range"
RANGE_FEEDBACK = "Feedback"

GENERATE_FEEDBACK = "Generate Feedback"



def clean_text(input_text):
    # Remove all types of brackets except quotation marks
    return re.sub(r'[\[\]\(\)\{\}<>]', '', input_text).strip()

def limit_unique_skills_per_test(input_dict, max_unique_skills=8):
    """
    Enforces that exactly `max_unique_skills` unique skills are used across all questions,
    each question has at least one skill, and no skill repeats across questions.

    Args:
        input_dict (dict): Original dict with questions as keys and comma-separated skills as values.
        max_unique_skills (int): Total number of unique skills allowed in the test.

    Returns:
        dict: Updated dict with cleaned skills per question.
    """
    # Step 1: Parse skills per question
    question_skills = {
        q: [s.strip() for s in skills.split(',') if s.strip()]
        for q, skills in input_dict.items()
    }

    # Step 2: Collect all unique skills
    all_unique_skills = list(dict.fromkeys(
        skill for skills in question_skills.values() for skill in skills
    ))

    if len(all_unique_skills) < max_unique_skills:
        print("⚠️ Warning: Not enough unique skills to assign. Found:", len(all_unique_skills))
        return input_dict

    # Step 3: Assign one unique skill to each question first
    assigned_skills = set()
    updated_dict = {}
    skill_index = 0

    for q in question_skills:
        # Find the first unused skill from this question
        assigned = None
        for skill in question_skills[q]:
            if skill not in assigned_skills:
                assigned = skill
                assigned_skills.add(skill)
                break
        if assigned is None:
            # fallback: assign next available unused skill
            while skill_index < len(all_unique_skills):
                if all_unique_skills[skill_index] not in assigned_skills:
                    assigned = all_unique_skills[skill_index]
                    assigned_skills.add(assigned)
                    skill_index += 1
                    break
        if assigned:
            updated_dict[q] = [assigned]
        else:
            updated_dict[q] = []

    # Step 4: Distribute remaining unique skills
    remaining = max_unique_skills - len(assigned_skills)
    if remaining > 0:
        for q in updated_dict:
            if remaining == 0:
                break
            for skill in question_skills[q]:
                if skill not in assigned_skills:
                    updated_dict[q].append(skill)
                    assigned_skills.add(skill)
                    remaining -= 1
                    break

    # Step 5: Final formatting
    for q in updated_dict:
        input_dict[q] = ', '.join(updated_dict[q])

    return input_dict


def format_test_orchestrated_conversation(raw_data):
    """
    This function takes raw data in the form of a JSON string and formats it to create an orchestrated conversation test.

    The function first loads the input JSON data into a dictionary. It then extracts the required information from the dictionary and formats it according to the API requirements for creating an orchestrated conversation test.

    The function checks for the presence of certain keys in the input dictionary and performs the following actions based on their values:
    - 'Title': Sets the title of the test.
    - 'Context': Sets the description of the test.
    - 'Scenario Case': Sets the scenario case of the test.
    - 'Description Media': Sets the description media of the test.
    - 'Test Custum Prompt': Sets the GPT prompt override of the test.
    - 'Test Image Link' and 'Test Image Props': Sets the test image and its properties.
    - 'Test Narration': Sets the narration of the test.
    - 'Certificate Title' and 'Certificate Description': Sets the title and description of the certificate, if provided.
    - 'Is Dynamic': Sets the test type to dynamic discussion if the value is 'true'.
    - 'Is Dynamic Thread': Sets the test type to dynamic discussion thread if the value is 'true'.
    - 'Client Name': Sets the client name for the test.
    - 'Bot Name': Sets the bot name for the test.
    - 'Tab Category': Sets the tab category for the test.
    - 'Area/Domain': Sets the area/domain for the test.
    - 'Ted talks and HBR Case': Sets the TED talks and HBR case for the test.
    - 'Is Game Type': Sets the is game type flag for the test.
    - 'Is Immersive': Sets the is immersive flag for the test.
    - 'Is Transcript Only': Sets the is transcript only flag for the test.
    - 'Is Free': Sets the is free flag for the test.
    - 'Is Micro': Sets the is micro flag for the test.
    - 'Is Logged In': Sets the is logged in flag for the test.
    - 'Current news': Sets the articles for the test.
    - 'Image URL': Sets the image URL for the test.
    - 'Source': Sets the source for the test.
    - 'User ID': Sets the creator user ID for the test.
    - 'Ratings': Sets the rating for the test.
    - 'Email Address List': Sets the email address list for the test.
    - 'Candidate Type': Sets the candidate type for the test.
    - 'Is Checkin Type': Sets the is checkin type flag for the test.
    - 'Goals': Sets the goals for the test.
    - 'Course': Sets the course for the test.
    - 'Industry': Sets the industry for the test.
    - 'Experience Level': Sets the experience level for the test.
    - 'Start with user': Sets the start with user flag for the test.
    - 'Background': Sets the background for the test.
    - 'PersonX': Adds questions to the test based on the 'PersonX' keys in the input dictionary.

    The function then checks if the test type is dynamic discussion and if there is more than one bot specified. If so, it returns an error.

    Finally, the function converts the formatted output dictionary back to a JSON string and returns it.

    Args:
        raw_data (str): A JSON string containing the raw data for creating an orchestrated conversation test.

    Returns:
        str: A JSON string containing the formatted data for creating an orchestrated conversation test.

    Raises:
        Exception: If any required keys are missing or have null or empty values in the input dictionary.
        Exception: If the API call fails.

    Example:
        >>> raw_data = '''
        ... {
        ...     "Title": "Orchestrated Conversation Test",
        ...     "Context": "This is a test description",
        ...     "Scenario Case": "Case 1",
        ...     "Description Media": "Media link",
        ...     "Test Custum Prompt": "Custom prompt",
        ...     "Test Image Link": "Image link",
        ...     "Test Image Props": "Image props",
        ...     "Test Narration": "Test narration",
        ...     "Certificate Title": "Certificate title",
        ...     "Certificate Description": "Certificate description",
        ...     "Is Dynamic": "true",
        ...     "Is Dynamic Thread": "false",
        ...     "Client Name": "Client A",
        ...     "Bot Name": "Bot A",
        ...     "Tab Category": "Category A",
        ...     "Area/Domain": "Domain A",
        ...     "Ted talks and HBR Case": "Case A",
        ...     "Is Game Type": "true",
        ...     "Is Immersive": "false",
        ...     "Is Transcript Only": "true",
        ...     "Is Free": "false",
        ...     "Is Micro": "true",
        ...     "Is Logged In": "false",
        ...     "Current news": "News A",
        ...     "Image URL": "Image URL",
        ...     "Source": "Source A",
        ...     "User ID": "User A",
        ...     "Ratings": "5",
        ...     "Email Address List": "email1@example.com,email2@example.com",
        ...     "Candidate Type": "Manager",
        ...     "Is Checkin Type": "true",
        ...     "Goals": "Goal A",
        ...     "Course": "Course A",
        ...     "Industry": "Industry A",
        ...     "Experience Level": "Level A",
        ...     "Start with user": "true",
        ...     "Background": "Background A",
        ...     "Person1": "Question 1",
        ...     "Person2": "Question 2",
        ...     "Person3": "Question 3"
        ... }
        ... '''
        >>> format_test_orchestrated_conversation(raw_data)
        '{"creator_id": null, "title": "Orchestrated Conversation Test", "description": "This is a test description", "interaction_mode": "text", "email_candidate": true, "test_type": "dynamic_discussion", "scenario_case": "case 1", "description_media": "Media link", "gpt_prompt_override": "Custom prompt", "questions": [{"question": "Question 1", "question_type": "subjective", "gpt_prompt_override": "", "subjective_answer": "", "question_for": "Person1"}, {"question": "Question 2", "question_type": "subjective", "gpt_prompt_override": "", "subjective_answer": "", "question_for": "Person2"}, {"question": "Question 3", "question_type": "subjective", "gpt_prompt_override": "", "subjective_answer": "", "question_for": "Person3"}]}'
    """
    
    try:
        input_dict = json.loads(raw_data)

        test = None
        if TEST_CODE in input_dict and len(input_dict[TEST_CODE].strip()) > 0:
            test = Test.objects.filter(test_code = input_dict[TEST_CODE].strip()).first()
            if not test:
                return {"error": f"Test code not found to update : {input_dict[TEST_CODE].strip()}"}, False
            
        if test:
            output_dict = {
                "questions": [],

            }
            output_dict['test_code'] = test.test_code
            if TITLE in input_dict and (input_dict[TITLE] and len(input_dict[TITLE].strip()) > 0):
                    output_dict['title'] = input_dict[TITLE]
            else:
                output_dict['title'] = test.title
            if 'Context' in input_dict and (input_dict['Context'] and len(input_dict['Context'].strip()) > 0):
                    output_dict['description'] = clean_text(input_dict['Context'])
            else:
                output_dict['description'] = test.description

            
            if SCENARIO_CASE in input_dict and (input_dict[SCENARIO_CASE] and len(input_dict[SCENARIO_CASE].strip()) > 0):
                    output_dict['scenario_case'] = input_dict[SCENARIO_CASE].strip().lower()
            else:
                output_dict['scenario_case'] = test.scenario_case

            if DESCRIPTION_MEDIA in input_dict and (input_dict[DESCRIPTION_MEDIA] and len(input_dict[DESCRIPTION_MEDIA].strip()) > 0):
                    output_dict['description_media'] = input_dict[DESCRIPTION_MEDIA]
            else:
                output_dict['description_media'] = test.description_media
            if TEST_CUSTUM_PROMPT in input_dict and (input_dict[TEST_CUSTUM_PROMPT] and len(input_dict[TEST_CUSTUM_PROMPT].strip()) > 0):
                    output_dict['gpt_prompt_override'] = input_dict[TEST_CUSTUM_PROMPT]
            else:
                output_dict['gpt_prompt_override'] = test.gpt_prompt_override

            if TEST_TYPE in input_dict and (len(input_dict[TEST_TYPE].strip()) > 0):
                output_dict['test_type'] = input_dict[TEST_TYPE].strip().lower()
            else:
                output_dict['test_type'] = test.test_type
            
        else:
            output_dict = {
                "creator_id": None,
                "title": input_dict['Title'],
                "description": clean_text(input_dict['Context']),
                "interaction_mode": "text",
                "email_candidate": True,
                "test_type": "orchestrated_conversation",
                "scenario_case": input_dict[SCENARIO_CASE].strip().lower(),
                "description_media": input_dict.get(DESCRIPTION_MEDIA, None),
                "gpt_prompt_override": input_dict.get(TEST_CUSTUM_PROMPT,""),
                "questions": [],
            }


        if output_dict.get('description_media'):
            media = [link.strip() for link in output_dict['description_media'].strip().split(',')]
            medias = []
            for m in media:
                medias.append(format_youtube_link(m,only_video_id=True))


            output_dict['description_media'] = ",".join(medias)

        if output_dict.get('scenario_case') == 'personality_game':
            output_dict['scenario_case'] = 'game'
            output_dict['is_personality_game'] = True

        media_json = {}
        if TEST_IMAGE_LINK in input_dict and TEST_IMAGE_PROPS in input_dict and TEST_NARRATION in input_dict and (len(input_dict[TEST_IMAGE_LINK].strip()) > 0) and (len(input_dict[TEST_IMAGE_PROPS].strip()) > 0) and (len(input_dict[TEST_NARRATION].strip()) > 0):
            image_link = input_dict[TEST_IMAGE_LINK].strip()
            props_link_list = input_dict[TEST_IMAGE_PROPS].strip().split(',')
            narration = input_dict[TEST_NARRATION].strip()
            image_data_list = []
            for i in range(0, len(props_link_list), 2):
                    title = props_link_list[i]
                    coord = props_link_list[i + 1]

                    # Create a dictionary for each title and coord pair
                    image_data_list.append({"title": title.strip(), "coord": coord.strip().replace(".",",")})
            image_data_list.append(narration)
            media_json['test_image'] = {image_link: image_data_list}

        if media_json:
            output_dict['media_props'] = media_json

        
        if ASKER_UI in input_dict:
            if input_dict[ASKER_UI] and len(input_dict[ASKER_UI].strip()) > 0:
                input_dict[RESPONDER] = input_dict[ASKER_UI].strip()
        
        if any(key in input_dict for key in [CERTIFICATE_DESCRIPTION, CERTIFICATE_TITLE]):
            output_dict['certificate_details'] = {}

            if CERTIFICATE_TITLE in input_dict:
                if input_dict[CERTIFICATE_TITLE] and len(input_dict[CERTIFICATE_TITLE].strip()) > 0:
                    output_dict["certificate_details"]['title'] = input_dict[CERTIFICATE_TITLE]

            if CERTIFICATE_DESCRIPTION in input_dict:
                if input_dict[CERTIFICATE_DESCRIPTION] and len(input_dict[CERTIFICATE_DESCRIPTION].strip()) > 0:
                    output_dict['certificate_details']['description'] = input_dict[CERTIFICATE_DESCRIPTION]
        
        if IS_DYNAMIC in input_dict:
            if input_dict[IS_DYNAMIC] and len(input_dict[IS_DYNAMIC].strip()) > 0:
                is_dynamic = input_dict[IS_DYNAMIC].strip().lower()

                if is_dynamic == "true":
                    output_dict["test_type"] = TestTypeChoices.dynamic_discussion
                    output_dict["interaction_mode"] = 'any'

        if IS_DYNAMIC_THREAD in input_dict:
            if input_dict[IS_DYNAMIC_THREAD] and len(input_dict[IS_DYNAMIC_THREAD].strip()) > 0:
                is_dynamic_thread = input_dict[IS_DYNAMIC_THREAD].strip().lower()

                if is_dynamic_thread == "true":
                    output_dict["test_type"] = TestTypeChoices.dynamic_discussion_thread
                    output_dict["interaction_mode"] = 'any'
                    
        # if there is INTERACTION_MODE availble in csv then it will overwrite 
        if INTERACTION_MODE in input_dict:
            if input_dict[INTERACTION_MODE] and len(input_dict[INTERACTION_MODE].strip()) >0:
                output_dict["interaction_mode"] = input_dict[INTERACTION_MODE].strip().lower()

        if output_dict.get('scenario_case') in ['game','psychometric'] :
            output_dict['interaction_mode'] = 'text'
            
        if CLIENT in input_dict:
            if input_dict[CLIENT] and len(input_dict[CLIENT].strip()) > 0 :
                output_dict['client_name'] = input_dict[CLIENT].strip()
                try:
                    client_info = ClientUserInfo.objects.get(client_name=output_dict['client_name'])
                    logger.info(f"###########################Matching Client info: {client_info}")
                except ClientUserInfo.DoesNotExist:
                    available_clients = ClientUserInfo.objects.all().values_list('client_name', flat=True)
                    logger.info(f"###########################Available Client info: {available_clients}")
                    return {"error": f"Client does not exist: {output_dict['client_name']}. available clients: {list(available_clients)}"}, False

        if PERSONALITY_MODEL in input_dict and len(input_dict[PERSONALITY_MODEL].strip()) > 0:
            output_dict['personality_model'] = input_dict[PERSONALITY_MODEL].strip().lower()

        if NOTICE_BOARD in input_dict and len(input_dict[NOTICE_BOARD].strip()) > 0:
            output_dict['notice_board'] = input_dict[NOTICE_BOARD].strip()

        if BOT_NAME in input_dict:
            if input_dict[BOT_NAME] and len(input_dict[BOT_NAME].strip()) > 0 :
                output_dict['bot_name'] = input_dict[BOT_NAME].strip()

        if TIME_LIMIT in input_dict:
            if input_dict[TIME_LIMIT] and len(input_dict[TIME_LIMIT].strip()) > 0 :
                output_dict['time_limit'] = int(input_dict[TIME_LIMIT].strip())

        if INSTRUCTION_MEDIA_LINK in input_dict:
            if input_dict[INSTRUCTION_MEDIA_LINK] and len(input_dict[INSTRUCTION_MEDIA_LINK].strip()) > 0 :
                output_dict['instruction_media_link'] = input_dict[INSTRUCTION_MEDIA_LINK].strip()

        if PAGE_NAME in input_dict:
            if input_dict[PAGE_NAME] and len(input_dict[PAGE_NAME].strip()) > 0 :
                output_dict['page_name'] = input_dict[PAGE_NAME].strip()

        if TAB_CATEGORY in input_dict:
            if input_dict[TAB_CATEGORY] and len(input_dict[TAB_CATEGORY].strip()) > 0 :
                output_dict['tab_category'] = input_dict[TAB_CATEGORY].strip().capitalize()

        if SUB_TAB_CATEGORY in input_dict:
            if input_dict[SUB_TAB_CATEGORY] and len(input_dict[SUB_TAB_CATEGORY].strip()) > 0 :
                output_dict['sub_tab_category'] = input_dict[SUB_TAB_CATEGORY].strip().capitalize()

        if TEST_SNIPPET_LINK in input_dict:
            if input_dict[TEST_SNIPPET_LINK] and len(input_dict[TEST_SNIPPET_LINK].strip()) > 0 :
                output_dict['snippet_url'] = input_dict[TEST_SNIPPET_LINK].strip().capitalize()

        if 'tab_category' not in output_dict:
            if COMPETENCY_SKILLS in input_dict:
                if input_dict[COMPETENCY_SKILLS] and len(input_dict[COMPETENCY_SKILLS].strip()) > 0 :
                    output_dict['competency_group'] = input_dict[COMPETENCY_SKILLS].strip().capitalize()

        if AREA_DOMAIN in input_dict:
            if input_dict[AREA_DOMAIN] and len(input_dict[AREA_DOMAIN].strip()) > 0 :
                output_dict['area_domain'] = input_dict[AREA_DOMAIN].strip().capitalize()


        if SKILL_DOMAIN in input_dict:
            if input_dict[SKILL_DOMAIN] and len(input_dict[SKILL_DOMAIN].strip()) > 0 :
                output_dict['skill_domain'] = input_dict[SKILL_DOMAIN].strip()

        if CREATOR_PROMPT_TYPE in input_dict:
            if input_dict[CREATOR_PROMPT_TYPE] and len(input_dict[CREATOR_PROMPT_TYPE].strip()) > 0 :
                output_dict['creator_prompt_type'] = input_dict[CREATOR_PROMPT_TYPE].strip()
                if 'hard' in output_dict['creator_prompt_type'].lower() :
                    output_dict['calculate_culture'] = False

        if TED_TALK_AND_HBR_CASE in input_dict:
            if input_dict[TED_TALK_AND_HBR_CASE] and len(input_dict[TED_TALK_AND_HBR_CASE].strip()) > 0 :
                output_dict["tedtalk_and_hbr_case"] = input_dict[TED_TALK_AND_HBR_CASE]

        if REPORT_DESCRIPTION in input_dict:
            if input_dict[REPORT_DESCRIPTION] and len(input_dict[REPORT_DESCRIPTION].strip()) > 0 :
                output_dict["report_description"] = input_dict[REPORT_DESCRIPTION].strip()

        if VIDEO_SCRIPT in input_dict:
            if input_dict[VIDEO_SCRIPT] and len(input_dict[VIDEO_SCRIPT].strip()) > 0 :
                output_dict["video_script"] = input_dict[VIDEO_SCRIPT].strip()
        if SCRIPT_VIDEO_LINK in input_dict:
            if input_dict[SCRIPT_VIDEO_LINK] and len(input_dict[SCRIPT_VIDEO_LINK].strip()) > 0 :
                output_dict["script_video_link"] = input_dict[SCRIPT_VIDEO_LINK].strip()
        if FEEDBACK_SCRIPT_VIDEO_LINK in input_dict:
            if input_dict[FEEDBACK_SCRIPT_VIDEO_LINK] and len(input_dict[FEEDBACK_SCRIPT_VIDEO_LINK].strip()) > 0 :
                output_dict["feedback_script_video_link"] = input_dict[FEEDBACK_SCRIPT_VIDEO_LINK].strip()
        if FEEDBACK_VIDEO_SCRIPT in input_dict:
            if input_dict[FEEDBACK_VIDEO_SCRIPT] and len(input_dict[FEEDBACK_VIDEO_SCRIPT].strip()) > 0 :
                output_dict["feedback_video_script_template"] = input_dict[FEEDBACK_VIDEO_SCRIPT].strip()

        if output_dict.get('scenario_case') == 'game':
            output_dict['is_game_type'] = True
        if IS_GAME_TYPE in input_dict:
            if input_dict[IS_GAME_TYPE] and len(input_dict[IS_GAME_TYPE].strip()) > 0:
                is_game_type = input_dict[IS_GAME_TYPE].strip().lower()

                if is_game_type == "true":
                    output_dict['is_game_type'] = True
                elif is_game_type == "false":
                    output_dict['is_game_type'] = False
                else:
                    output_dict['is_game_type'] = False

        if IS_SINGLE_SELECT in input_dict:
            if input_dict[IS_SINGLE_SELECT] and len(input_dict[IS_SINGLE_SELECT].strip()) > 0:
                is_single_select = input_dict[IS_SINGLE_SELECT].strip().lower()

                if is_single_select == "true":
                    output_dict['is_single_select'] = True
                elif is_single_select == "false":
                    output_dict['is_single_select'] = False
                else:
                    output_dict['is_single_select'] = False


        if IS_RECOMMENDED in input_dict:
            if input_dict[IS_RECOMMENDED] and len(input_dict[IS_RECOMMENDED].strip()) > 0:
                is_recommended = input_dict[IS_RECOMMENDED].strip().lower()

                if is_recommended == "true":
                    output_dict['is_recommended'] = True
                elif is_recommended == "false":
                    output_dict['is_recommended'] = False
                else:
                    output_dict['is_recommended'] = False

        if CALCULATE_CULTURE in input_dict:
            if input_dict[CALCULATE_CULTURE] and len(input_dict[CALCULATE_CULTURE].strip()) > 0:
                calculate_culture = input_dict[CALCULATE_CULTURE].strip().lower()

                if calculate_culture == "true":
                    output_dict['calculate_culture'] = True
                elif calculate_culture == "false":
                    output_dict['calculate_culture'] = False
                else:
                    output_dict['calculate_culture'] = True 

        if GENERATE_FEEDBACK in input_dict:
            if input_dict[GENERATE_FEEDBACK] and len(input_dict[GENERATE_FEEDBACK].strip()) > 0:
                generate_feedback = input_dict[GENERATE_FEEDBACK].strip().lower()

                if generate_feedback == "true":
                    output_dict['generate_feedback'] = True
                elif generate_feedback == "false":
                    output_dict['generate_feedback'] = False
                else:
                    output_dict['generate_feedback'] = True 

        if IS_IMMERSIVE in input_dict:
            if input_dict[IS_IMMERSIVE] and len(input_dict[IS_IMMERSIVE].strip()) > 0:
                is_immersive = input_dict[IS_IMMERSIVE].strip().lower()

                if is_immersive == "true":
                    output_dict['is_immersive'] = True
                elif is_immersive == "false":
                    output_dict['is_immersive'] = False
                else:
                    output_dict['is_immersive'] = False

        if IS_TRANSCRIPT_ONLY in input_dict:
            if input_dict[IS_TRANSCRIPT_ONLY] and len(input_dict[IS_TRANSCRIPT_ONLY].strip()) > 0:
                is_transcript_only = input_dict[IS_TRANSCRIPT_ONLY].strip().lower()

                if is_transcript_only == "true":
                    output_dict['is_transcript_only'] = True
                elif is_transcript_only == "false":
                    output_dict['is_transcript_only'] = False
                else:
                    output_dict['is_transcript_only'] = False

        if output_dict.get('scenario_case') in ['journaling', 'observation']:
            output_dict['is_transcript_only'] = True

        if IS_FREE in input_dict:
            if input_dict[IS_FREE] and len(input_dict[IS_FREE].strip()) > 0:
                is_free = input_dict[IS_FREE].strip().lower()

                if is_free == "true":
                    output_dict['is_free'] = True
                elif is_free == "false":
                    output_dict['is_free'] = False
                else:
                    output_dict['is_free'] = False

        if IS_MICRO in input_dict:
            if input_dict[IS_MICRO] and len(input_dict[IS_MICRO].strip()) > 0:
                is_micro = input_dict[IS_MICRO].strip().lower()

                if is_micro == "true":
                    output_dict['is_micro'] = True
                else:
                    output_dict['is_micro'] = False

        if IS_LOGGEDiN in input_dict:
            if input_dict[IS_LOGGEDiN] and len(input_dict[IS_LOGGEDiN].strip()) > 0:
                is_logged_in= input_dict[IS_LOGGEDiN].strip().lower()

                if is_logged_in == "true":
                    output_dict['is_logged_in'] = True
                else:
                    output_dict['is_logged_in'] = False
                    
        if VISUAL_TAGS in input_dict:
            if input_dict[VISUAL_TAGS] and len(input_dict[VISUAL_TAGS].strip()) > 0:
                output_dict['visual_tags'] = input_dict.get(VISUAL_TAGS,None)
        
        
        if CURRENT_NEWS in input_dict:
            if input_dict[CURRENT_NEWS] and len(input_dict[CURRENT_NEWS].strip()) > 0:
                output_dict['articles'] = input_dict.get(CURRENT_NEWS,None)

        if IMAGE_URL in input_dict:
            if input_dict[IMAGE_URL] and len(input_dict[IMAGE_URL].strip()) > 0:
                output_dict['image_url'] = input_dict.get(IMAGE_URL,None)

        if SOURCE in input_dict :
            if input_dict[SOURCE] and len(input_dict[SOURCE].strip()) > 0:
                output_dict['source'] = input_dict.get(SOURCE,None)

        if USER_ID in input_dict :
            if input_dict[USER_ID] and len(input_dict[USER_ID].strip()) > 0:
                output_dict['creator_user_id'] = input_dict.get(USER_ID,None)
                
                
        if USER_EMAIL in input_dict :
            if input_dict[USER_EMAIL] and len(input_dict[USER_EMAIL].strip()) > 0:
                output_dict['creator_email'] = input_dict.get(USER_EMAIL,None)
        
        if RATINGS in input_dict:
            if input_dict[RATINGS] and len(input_dict[RATINGS].strip()) > 0:
                output_dict['rating'] = input_dict.get(RATINGS,None)

        bot_count = sum(1 for key in input_dict.keys()
                        if key.startswith('Person'))
        if bot_count == 1:
            output_dict["is_single_bot"] = True

        if output_dict["test_type"] == TestTypeChoices.dynamic_discussion and bot_count > 1:
            return {"error": "Dynamic discussion can only have one bot"}, False


        print('#'*100, input_dict)

        if GOALS in input_dict:
            output_dict['goals'] = input_dict.get(GOALS, None)

        if COURSE in input_dict:
            output_dict['course'] = input_dict.get(COURSE, None)

        if INDUSTRY in input_dict:
            output_dict['industry'] = input_dict.get(INDUSTRY, None)

        if EXP_LEVEL in input_dict:
            output_dict['exp_level'] = input_dict.get(EXP_LEVEL, None)

        print('*'*100, output_dict)

        if EMAIL_CANDIDATE in input_dict:
            if input_dict[EMAIL_CANDIDATE] and len(input_dict[EMAIL_CANDIDATE].strip()) > 0:
                email_candidate = input_dict[EMAIL_CANDIDATE].strip().lower()

                if email_candidate == "true":
                    output_dict['email_candidate'] = True
                elif email_candidate == "false":
                    output_dict['email_candidate'] = False
                else:
                    output_dict['email_candidate'] = True

        if output_dict.get('scenario_case') == 'assessment':
            output_dict['email_candidate'] = False
            
        if CATEGORY in input_dict:
            if input_dict[CATEGORY] and len(input_dict[CATEGORY].strip()) > 0 :
                output_dict['category'] = input_dict[CATEGORY].strip().capitalize()


        check_pass = True

        if IS_CHECKIN_TYPE in input_dict:
            if input_dict.get(IS_CHECKIN_TYPE) and len(input_dict[IS_CHECKIN_TYPE].strip()) > 0:
                is_checkin_type = input_dict[IS_CHECKIN_TYPE].strip().lower()

                if is_checkin_type == "true":
                    output_dict['is_checkin_type'] = True
                elif is_checkin_type == "false":
                    output_dict['is_checkin_type'] = False
                else:
                    output_dict['is_checkin_type'] = False

                if input_dict[IS_CHECKIN_TYPE] == 'TRUE':
                    
                    # skills_list = input_dict[SKILLS_TO_EVALUATE]
                    # skills_list_temp = []
                    # for s in skills_list.split(','):
                    #     skills_list_temp.append(s.strip().capitalize())
                    # skills_list = skills_list_temp

                    # candidate_type = input_dict[CANDIDATE_TYPE].capitalize()
                    # if not candidate_type:
                    #     candidate_type = 'Manager'
                    # skills_list_candidate = set()
                    # for item in get_skills(candidate_type):
                    #     skills_list_candidate.add(item.capitalize())
                    # skills_list_candidate = list(skills_list_candidate)

                    # print('*'*100)
                    # print(sorted(skills_list_candidate))
                    # print(sorted(skills_list))
                    # print()
                    # if sorted(skills_list_candidate) == sorted(skills_list):
                    #     check_pass = True
                    # else:
                    #     check_pass = False
                    check_pass = True

            

        if EMAIL_ADDRESS_LIST in input_dict and len(input_dict[EMAIL_ADDRESS_LIST].strip()) > 0:

            email_list = input_dict[EMAIL_ADDRESS_LIST].split(',')
            email_list = [email.strip() for email in email_list]
            email_list = ','.join(email_list)

            output_dict['email_address_list'] = email_list

        candidate_type = None
        if CANDIDATE_TYPE in input_dict and len(input_dict[CANDIDATE_TYPE].strip()) > 0:
            candidate_type = input_dict[CANDIDATE_TYPE].strip().capitalize()
            output_dict['candidate_type'] = input_dict[CANDIDATE_TYPE].strip().lower()

        if CULTURE_SKILLS in input_dict and len(input_dict[CULTURE_SKILLS]) > 0:
            culture = [ skill.strip() for skill in input_dict[CULTURE_SKILLS].strip().split(',') if skill.strip()]
            output_dict["culture_skills_to_evaluate"] = generate_culture_map(culture)


        if IS_ASSESSMENT in input_dict and len(input_dict[IS_ASSESSMENT]) > 0:
            output_dict["tag"] = 'assessment' if input_dict[IS_ASSESSMENT].strip().lower() == "true" else None

        skills_list = []
        if SKILLS_TO_EVALUATE in input_dict and len(input_dict[SKILLS_TO_EVALUATE]) > 0:
            skill_list = input_dict[SKILLS_TO_EVALUATE].split(',')
            skills_list = [skill.strip() for skill in skill_list]
        elif not test:

            # saving skills_to_evaluate from backend only

            if not candidate_type:
                candidate_type = 'Manager'
            skills_list_candidate = set()
            for item in get_skills(candidate_type):
                skills_list_candidate.add(item)

            evaluation_skill_list = [skill.strip() for skill in sorted(skills_list_candidate)]
            skills_list = evaluation_skill_list
            evaluation_skill_list = ','.join(evaluation_skill_list)

        if len(skills_list) < 6 and not test:
            return {"error": "Skills to evaluate should be more than 6"}, False
        if len(skills_list) > 8:
            skills_list = skills_list[:8]
        if len(skills_list)>0:
            output_dict['skills_to_evaluate'] = ",".join(skills_list)
        initial_messages = []
        test_main_context = output_dict.get('description')
        persons = []

        for key in input_dict:
            if key.startswith('Person'):
                name = input_dict[key].split(':')[0].strip()
                name = name.replace('*',"").replace(":","")
                persons.append(name)
                initial_messages.append(input_dict[key])
                test_main_context += input_dict[key]

        if test:
            orchestrated_conversation_details = test.orchestrated_conversation_details
            if CANDIDATE_TYPE in input_dict and len(CANDIDATE_TYPE) > 0:
                candidate_type = input_dict[CANDIDATE_TYPE].strip()
            elif test:
                candidate_type = test.candidate_type
            else:
                candidate_type = 'Manager'
            if len(initial_messages) > 0:
                orchestrated_conversation_details['initial_messages'] = initial_messages
            if test_main_context:
                orchestrated_conversation_details['test_main_context'] = test_main_context
            if candidate_type:
                orchestrated_conversation_details['test_user_persona'] = candidate_type
            if output_dict.get('description'):
                orchestrated_conversation_details['objective'] = output_dict.get('description')
        else:
            orchestrated_conversation_details = {
                "test_main_context": test_main_context,
                "test_user_persona": candidate_type,
                "objective": output_dict.get('description'),
                "initial_messages": initial_messages
            }

        if START_WITH_USER in input_dict:
            if input_dict[START_WITH_USER] and len(input_dict[START_WITH_USER].strip()) > 0:
                start_with_user = input_dict[START_WITH_USER].strip().lower()
                orchestrated_conversation_details["start_with_user"] = start_with_user

        if BACKGROUND in input_dict:
            if input_dict[BACKGROUND] and len(input_dict[BACKGROUND].strip()) > 0:
                background = input_dict[BACKGROUND].strip()
                orchestrated_conversation_details["background"] = background
                
        output_dict['orchestrated_conversation_details'] = orchestrated_conversation_details
        logger.info(f"<<<<<<<<Input Dict: {input_dict}>>>>>>>>>")
        
        question_to_update = None
        if test:
            question_to_update = TestQuestion.objects.filter(test_id=test.uid).order_by('question_number').values_list('question_number','uid')
            question_to_update = {str(question_number): uid for question_number, uid in question_to_update}

        for key in input_dict:
            if key.isdigit():
                question = {
                    "question": input_dict[key],
                    "question_type": "subjective",
                    "gpt_prompt_override": "",
                    "subjective_answer": ""
                }
                if question_to_update:
                    print(question_to_update[f"{int(key)+1}"],question_to_update)
                    question['question_id'] = question_to_update[f"{int(key)+1}"]
                # if "Please respond in order to continue" in input_dict[key]:
                #     question['question_for'] = "user"

                # else:
                #     for name in persons:
                #         if name.split()[0].lower() in input_dict[key].lower():
                #             question['question_for'] = name
                #             break
                print('persons', persons)
                matched_name = next((name for name in persons if name.strip().lower() in input_dict[key].lower()), None)
                if matched_name:
                    if RESPONDER in input_dict:
                    
                        if input_dict[RESPONDER] and len(input_dict[RESPONDER].strip()) > 0 and output_dict.get('test_type') == "dynamic_discussion_thread":
                            responder = input_dict[RESPONDER].strip()
                            matched_name = responder
                    question['question_for'] = matched_name
                else:
                    question['question_for'] = "user"
                                
                output_dict["questions"].append(question)
        
        # checking if last column is for user or not
        if 'questions' in output_dict and len(output_dict.get('questions')) > 0:
            last_question = output_dict['questions'][-1]
            if last_question['question_for'] != 'user':
                logger.exception(f"Last question should be for user: {output_dict.get('questions')}")
                json_data = {"last_question_for_user": "Last question should be for user"}
                return json_data, False
            

            # checking wheater two user type coming one after other
            question_for = [q['question_for'] for q in output_dict['questions']]
            for i in range(len(question_for) - 1):
                if question_for[i] == "user" and question_for[i + 1] == "user":
                    logger.exception(f"Questions for user should not occur continously: {output_dict.get('questions')}")

                    json_data = {"last_question_for_user": "Questions for user should not occur continously"}

                    return json_data, False

            output_dict['is_micro'] = False if ((len(output_dict.get('questions')) + 1) / 2) > 3 else True
            output_dict['total_question'] = len(output_dict.get('questions'))


        print(output_dict)
        output_json = json.dumps(output_dict)

        return output_json, check_pass

    except Exception as e:
        logger.exception(e)
        return None


def format_test_data_web(raw_data):

    try:
        input_dict = json.loads(raw_data)

        # Convert TRUE and FALSE to true and false
        for key in input_dict:
            if input_dict[key] == "TRUE":
                input_dict[key] = True
            elif input_dict[key] == "FALSE":
                input_dict[key] = False

        # Add empty array for notification key
        input_dict["notification"] = []
        input_dict['access_code'] = int(input_dict['access_code'])

        # Extract questions and their corresponding fields
        questions = []
        for key in list(input_dict.keys()):
            if key.startswith("question_") and not key.startswith("question_context_"):

                question_number = int(re.findall(r'\d+', key)[0])

                question = {
                    "question": input_dict[key].rstrip('_' + str(question_number)),
                    "media_link": input_dict.get("media_link_" + str(question_number), ''),
                    "question_context": input_dict.get("question_context_" + str(question_number), ''),
                    "ideal_answer": input_dict.get("ideal_answer_" + str(question_number), '')
                }

                questions.append(question)
                del input_dict[key]
                del input_dict["media_link_" + str(question_number)]
                del input_dict["question_context_" + str(question_number)]
                del input_dict["ideal_answer_" + str(question_number)]

        # Create output dictionary
        output_dict = {
            "questions": questions,
            **input_dict  # Merge remaining keys from input_dict
        }

        # Convert output dictionary to JSON
        output_json = json.dumps(output_dict)

        return output_json

    except Exception as e:
        logger.error(e)
        return None


def format_test_data_slack(raw_data,tenant):
    """ 
    The format_test_data_slack function takes in a raw_data parameter, which is expected to be a JSON string. It processes the input JSON data and formats it into a specific output JSON format.

    The function performs the following steps:

    Parses the raw_data JSON string into a Python dictionary using json.loads.
    Creates an output_dict with predefined keys and values extracted from the input_dict.
    Checks if certain keys exist in the input_dict and adds corresponding values to the output_dict.
    Handles special cases for certain keys and modifies the output_dict accordingly.
    Processes the questions in the input_dict and adds them to the output_dict.
    Handles additional logic based on the test_type and modifies the output_dict accordingly.
    Converts the output_dict to a JSON string using json.dumps.
    Returns the output JSON string and a boolean check_pass indicating if the processing was successful.
    Example: Input:

    raw_data = '{"title": "Test Title", "description": "Test Description", "max_test_allowed": 10, "interaction_mode": "interactive", "test_type": "single", "scenario_case": "case1", "questions": {"question1": "What is your name?", "question2": "How old are you?"}}'
    Output:

    '{"creator_id": null, "title": "Test Title", "description": "Test Description", "max_test_allowed": 10, "interaction_mode": "interactive", "test_type": "single", "scenario_case": "case1", "description_media": null, "gpt_prompt_override": "", "questions": [{"question": "What is your name?", "question_type": "subjective", "gpt_prompt_override": "", "subjective_answer": "", "key_learning_point": "", "key_learning_skills": null}, {"question": "How old are you?", "question_type": "subjective", "gpt_prompt_override": "", "subjective_answer": "", "key_learning_point": "", "key_learning_skills": null}], "total_question": 2}
    """
    try:
        input_dict = json.loads(raw_data)

        test = None
        if TEST_CODE in input_dict and len(input_dict[TEST_CODE].strip())>0:
            test = Test.objects.filter(test_code=input_dict[TEST_CODE].strip()).first()
            if not test:
                return {"error": f"Test code not found : {input_dict[TEST_CODE]}"}, False
            
        if test:
            output_dict = {'questions': []}
            output_dict['test_code'] = test.test_code
            if TITLE in input_dict and (input_dict[TITLE] and len(input_dict[TITLE].strip()) > 0):
                    output_dict['title'] = input_dict[TITLE]
            else:
                output_dict['title'] = test.title
            if DESCRIPTION in input_dict and (input_dict[DESCRIPTION] and len(input_dict[DESCRIPTION].strip()) > 0):
                    output_dict['description'] = clean_text(input_dict[DESCRIPTION])
            else:
                output_dict['description'] = test.description
            if SCENARIO_CASE in input_dict and (input_dict[SCENARIO_CASE] and len(input_dict[SCENARIO_CASE].strip()) > 0):
                    output_dict['scenario_case'] = input_dict[SCENARIO_CASE].strip().lower()
            else:
                output_dict['scenario_case'] = test.scenario_case

            if DESCRIPTION_MEDIA in input_dict and (input_dict[DESCRIPTION_MEDIA] and len(input_dict[DESCRIPTION_MEDIA].strip()) > 0):
                    output_dict['description_media'] = input_dict[DESCRIPTION_MEDIA]
            else:
                output_dict['description_media'] = test.description_media
        
            if TEST_TYPE in input_dict and (len(input_dict[TEST_TYPE].strip()) > 0):
                    output_dict['test_type'] = input_dict[TEST_TYPE].strip().lower()
            else:
                output_dict['test_type'] = test.test_type
            if INTERACTION_MODE in input_dict and (len(input_dict[INTERACTION_MODE].strip()) > 0):
                    output_dict['interaction_mode'] = input_dict[INTERACTION_MODE].strip().lower()
            else:
                output_dict['interaction_mode'] = test.interaction_mode

            if TEST_CUSTUM_PROMPT in input_dict and (len(input_dict[TEST_CUSTUM_PROMPT].strip()) > 0):
                    output_dict['gpt_prompt_override'] = input_dict[TEST_CUSTUM_PROMPT]
            else:
                output_dict['gpt_prompt_override'] = test.gpt_prompt_override
            

        else:

            output_dict = {
                "creator_id": None,
                "title": input_dict[TITLE],
                "description": clean_text(input_dict[DESCRIPTION]),
                "interaction_mode": input_dict[INTERACTION_MODE].strip().lower(),
                "test_type": input_dict[TEST_TYPE].strip().lower(),
                "scenario_case": input_dict[SCENARIO_CASE].strip().lower(),
                "description_media": input_dict.get(DESCRIPTION_MEDIA, None),
                "gpt_prompt_override": input_dict.get(TEST_CUSTUM_PROMPT,""),
                "questions": [],
            }
        if test:
            test_type = test.test_type
        else:
            test_type = input_dict[TEST_TYPE].strip().lower()

        if output_dict['description_media']:
            media = [link.strip() for link in output_dict['description_media'].strip().split(',')]
            medias = []
            for m in media:
                medias.append(format_youtube_link(m,only_video_id=True))

            output_dict['description_media'] = ",".join(medias)

        if output_dict.get('scenario_case') == 'personality_game':
            output_dict['scenario_case'] = 'game'
            output_dict['is_personality_game'] = True
            
        media_json = {}

        if TEST_IMAGE_LINK in input_dict and TEST_IMAGE_PROPS in input_dict and TEST_NARRATION in input_dict and (len(input_dict[TEST_IMAGE_LINK].strip()) > 0) and (len(input_dict[TEST_IMAGE_PROPS].strip()) > 0) and (len(input_dict[TEST_NARRATION].strip()) > 0):
            image_link = input_dict[TEST_IMAGE_LINK].strip()
            props_link_list = input_dict[TEST_IMAGE_PROPS].strip().split(',')
            narration = input_dict[TEST_NARRATION].strip()
            image_data_list = []
            for i in range(0, len(props_link_list), 2):
                    title = props_link_list[i]
                    coord = props_link_list[i + 1]

                    # Create a dictionary for each title and coord pair
                    image_data_list.append({"title": title.strip(), "coord": coord.strip().replace(".",",")})
            image_data_list.append(narration)
            media_json['test_image'] = {image_link: image_data_list}

        if any(key in input_dict for key in [CERTIFICATE_DESCRIPTION, CERTIFICATE_TITLE]):
            output_dict['certificate_details'] = {}

            if CERTIFICATE_TITLE in input_dict:
                if input_dict[CERTIFICATE_TITLE] and len(input_dict[CERTIFICATE_TITLE].strip()) > 0:
                    output_dict["certificate_details"]['title'] = input_dict[CERTIFICATE_TITLE]

            if CERTIFICATE_DESCRIPTION in input_dict:
                if input_dict[CERTIFICATE_DESCRIPTION] and len(input_dict[CERTIFICATE_DESCRIPTION].strip()) > 0:
                    output_dict['certificate_details']['description'] = input_dict[CERTIFICATE_DESCRIPTION]

        if any(key in input_dict for key in [TITLEUI, DESCRIPTIONUI]):
            output_dict['ui_information'] = {}

            if TITLEUI in input_dict:
                if input_dict[TITLEUI] and len(input_dict[TITLEUI].strip()) > 0:
                    output_dict["ui_information"]['title'] = input_dict[TITLEUI]
                    
            if DESCRIPTIONUI in input_dict:
                if input_dict[DESCRIPTIONUI] and len(input_dict[DESCRIPTIONUI].strip()) > 0:
                    output_dict["ui_information"]['description'] = input_dict[DESCRIPTIONUI]

            for key in input_dict:
                if key.startswith(QUESTIONUI):
                    output_dict['ui_information'][f"Question {key[len(QUESTIONUI) + 1:]}"] = input_dict.get(f"{QUESTIONUI} {key[len(QUESTIONUI) + 1:]}",None)
        
        if output_dict['scenario_case'] in ['psychometric', 'game'] :
            output_dict['interaction_mode'] = 'text'
            
        
        if IS_GAME_TYPE in input_dict:
            if input_dict[IS_GAME_TYPE] and len(input_dict[IS_GAME_TYPE].strip()) > 0:
                is_game_type = input_dict[IS_GAME_TYPE].strip().lower()

                if is_game_type == "true":
                    output_dict['is_game_type'] = True
                elif is_game_type == "false":
                    output_dict['is_game_type'] = False
                else:
                    output_dict['is_game_type'] = False

        if IS_RECOMMENDED in input_dict:
            if input_dict[IS_RECOMMENDED] and len(input_dict[IS_RECOMMENDED].strip()) > 0:
                is_recommended = input_dict[IS_RECOMMENDED].strip().lower()

                if is_recommended == "true":
                    output_dict['is_recommended'] = True
                elif is_recommended == "false":
                    output_dict['is_recommended'] = False
                else:
                    output_dict['is_recommended'] = False

        if TIME_LIMIT in input_dict:
            if input_dict[TIME_LIMIT] and len(input_dict[TIME_LIMIT].strip()) > 0 :
                output_dict['time_limit'] = int(input_dict[TIME_LIMIT].strip())

        if INSTRUCTION_MEDIA_LINK in input_dict:
            if input_dict[INSTRUCTION_MEDIA_LINK] and len(input_dict[INSTRUCTION_MEDIA_LINK].strip()) > 0 :
                output_dict['instruction_media_link'] = input_dict[INSTRUCTION_MEDIA_LINK].strip()

        if CALCULATE_CULTURE in input_dict:
            if input_dict[CALCULATE_CULTURE] and len(input_dict[CALCULATE_CULTURE].strip()) > 0:
                calculate_culture = input_dict[CALCULATE_CULTURE].strip().lower()

                if calculate_culture == "true":
                    output_dict['calculate_culture'] = True
                elif calculate_culture == "false":
                    output_dict['calculate_culture'] = False
                else:
                    output_dict['calculate_culture'] = True
                    
        if GENERATE_FEEDBACK in input_dict:
            if input_dict[GENERATE_FEEDBACK] and len(input_dict[GENERATE_FEEDBACK].strip()) > 0:
                generate_feedback = input_dict[GENERATE_FEEDBACK].strip().lower()

                if generate_feedback == "true":
                    output_dict['generate_feedback'] = True
                elif generate_feedback == "false":
                    output_dict['generate_feedback'] = False
                else:
                    output_dict['generate_feedback'] = True 

        if IS_PITCH in input_dict:
            if input_dict[IS_PITCH] and len(input_dict[IS_PITCH].strip()) > 0:
                is_pitch = input_dict[IS_PITCH].strip().lower()

                if is_pitch == "true":
                    output_dict['is_pitch'] = True
                elif is_pitch == "false":
                    output_dict['is_pitch'] = False
                else:
                    output_dict['is_pitch'] = False

        if IS_IMMERSIVE in input_dict:
            if input_dict[IS_IMMERSIVE] and len(input_dict[IS_IMMERSIVE].strip()) > 0:
                is_immersive = input_dict[IS_IMMERSIVE].strip().lower()

                if is_immersive == "true":
                    output_dict['is_immersive'] = True
                elif is_immersive == "false":
                    output_dict['is_immersive'] = False
                else:
                    output_dict['is_immersive'] = False

        is_transcript_only = False
        if IS_TRANSCRIPT_ONLY in input_dict:
            if input_dict[IS_TRANSCRIPT_ONLY] and len(input_dict[IS_TRANSCRIPT_ONLY].strip()) > 0:
                is_transcript_only = input_dict[IS_TRANSCRIPT_ONLY].strip().lower()

                if is_transcript_only == "true":
                    output_dict['is_transcript_only'] = True
                    is_transcript_only = True
                elif is_transcript_only == "false":
                    output_dict['is_transcript_only'] = False
                    is_transcript_only = False
                else:
                    output_dict['is_transcript_only'] = False
                    is_transcript_only = False
                    
        if output_dict['scenario_case'] in ['journaling', 'observation']:
            output_dict['is_transcript_only'] = True
            is_transcript_only = True

        if IS_FREE in input_dict:
            if input_dict[IS_FREE] and len(input_dict[IS_FREE].strip()) > 0:
                is_free = input_dict[IS_FREE].strip().lower()

                if is_free == "true":
                    output_dict['is_free'] = True
                elif is_free == "false":
                    output_dict['is_free'] = False
                else:
                    output_dict['is_free'] = False


        if IS_MICRO in input_dict:
            if input_dict[IS_MICRO] and len(input_dict[IS_MICRO].strip()) > 0:
                is_micro = input_dict[IS_MICRO].strip().lower()

                if is_micro == "true":
                    output_dict['is_micro'] = True
                else:
                    output_dict['is_micro'] = False

        if IS_LOGGEDiN in input_dict:
            if input_dict[IS_LOGGEDiN] and len(input_dict[IS_LOGGEDiN].strip()) > 0:
                is_logged_in= input_dict[IS_LOGGEDiN].strip().lower()

                if is_logged_in == "true":
                    output_dict['is_logged_in'] = True
                else:
                    output_dict['is_logged_in'] = False

        client_info = None
        if CLIENT in input_dict:
            if input_dict[CLIENT] and len(input_dict[CLIENT].strip()) > 0 :
                output_dict['client_name'] = input_dict[CLIENT].strip()
                try:
                    client_info = ClientUserInfo.objects.get(client_name=output_dict['client_name'])
                    logger.info(f"###########################Matching Client info: {client_info}")
                except ClientUserInfo.DoesNotExist:
                    available_clients = ClientUserInfo.objects.all().values_list('client_name', flat=True)
                    logger.info(f"###########################Available Client info: {available_clients}")
                    return {"error": f"Client does not exist: {output_dict['client_name']}. available clients: {list(available_clients)}"}, False

        if SECTIONS in input_dict:
            logger.info(f"###########################Sections: {input_dict[SECTIONS]}")
            if input_dict[SECTIONS] and len(input_dict[SECTIONS].strip()) > 0:
                sections = input_dict[SECTIONS]
                sections = extract_sections(sections)
                output_dict['pshycometric_sections'] = sections

        if PSYCHOMETRIC in input_dict and len(input_dict[PSYCHOMETRIC].strip()) >0:
            psy_uid_or_name = input_dict[PSYCHOMETRIC].strip()
            psycho = (
                Psychometric.objects.filter(tenant_id=tenant.uid)
                .filter(uid=psy_uid_or_name)
                .first()
                or
                Psychometric.objects.filter(tenant_id=tenant.uid)
                .filter(name=psy_uid_or_name)
                .first()
            )

            # If not found, try to find without tenant_id
            if not psycho:
                psycho = (
                    Psychometric.objects.filter(tenant_id=None)
                    .filter(uid=psy_uid_or_name)
                    .first()
                    or
                    Psychometric.objects.filter(tenant_id=None)
                    .filter(name=psy_uid_or_name)
                    .first()
                )

            if not psycho:
                return {"error": f"Psychometric set does not exist: {psy_uid_or_name}. If you are using name its case sansitive. (you can use uid or name)"}, False

            output_dict['psychometric'] = psycho.uid

            if PSYCHOMETRIC_REPORT_CONFIG in input_dict and len(input_dict[PSYCHOMETRIC_REPORT_CONFIG].strip()) >0:
                report_config = input_dict[PSYCHOMETRIC_REPORT_CONFIG].strip()
                psycho_report_config = (
                    PsychometricReportSection.objects.filter(uid=report_config).first()
                    or
                    PsychometricReportSection.objects.filter(name=report_config).first()
                )
                if not psycho_report_config:
                    return {"error": f"Psychometric report config does not exist: {report_config}. If you are using name its case sansitive. (you can use uid or name)"}, False
                
                output_dict['psychometric_report_config'] = psycho_report_config.uid
            else:
                output_dict['psychometric_report_config'] =  "3eecb3a3-dfca-4f9c-95c6-fccc1b25d717"  if  PsychometricReportSection.objects.filter(uid='3eecb3a3-dfca-4f9c-95c6-fccc1b25d717').first() else None


        if PERSONALITY_MODEL in input_dict and len(input_dict[PERSONALITY_MODEL].strip()) > 0:
            output_dict['personality_model'] = input_dict[PERSONALITY_MODEL].strip().lower()

        if NOTICE_BOARD in input_dict and len(input_dict[NOTICE_BOARD].strip()) > 0:
            output_dict['notice_board'] = input_dict[NOTICE_BOARD].strip()

        if BOT_NAME in input_dict:
            if input_dict[BOT_NAME] and len(input_dict[BOT_NAME].strip()) > 0 :
                output_dict['bot_name'] = input_dict[BOT_NAME].strip()

        if PAGE_NAME in input_dict:
            if input_dict[PAGE_NAME] and len(input_dict[PAGE_NAME].strip()) > 0 :
                output_dict['page_name'] = input_dict[PAGE_NAME].strip().lower()
                
        if CATEGORY in input_dict:
            if input_dict[CATEGORY] and len(input_dict[CATEGORY].strip()) > 0 :
                output_dict['category'] = input_dict[CATEGORY].strip().capitalize()


        if AREA_DOMAIN in input_dict:
            if input_dict[AREA_DOMAIN] and len(input_dict[AREA_DOMAIN].strip()) > 0 :
                output_dict['area_domain'] = input_dict[AREA_DOMAIN].strip().capitalize()

        if SKILL_DOMAIN in input_dict:
            if input_dict[SKILL_DOMAIN] and len(input_dict[SKILL_DOMAIN].strip()) > 0 :
                output_dict['skill_domain'] = input_dict[SKILL_DOMAIN].strip()

        if CREATOR_PROMPT_TYPE in input_dict:
            if input_dict[CREATOR_PROMPT_TYPE] and len(input_dict[CREATOR_PROMPT_TYPE].strip()) > 0 :
                output_dict['creator_prompt_type'] = input_dict[CREATOR_PROMPT_TYPE].strip()
                if 'hard' in output_dict['creator_prompt_type'].lower() :
                    output_dict['calculate_culture'] = False

        if TAB_CATEGORY in input_dict:
            if input_dict[TAB_CATEGORY] and len(input_dict[TAB_CATEGORY].strip()) > 0 :
                output_dict['tab_category'] = input_dict[TAB_CATEGORY].strip().capitalize()

        if SUB_TAB_CATEGORY in input_dict:
            if input_dict[SUB_TAB_CATEGORY] and len(input_dict[SUB_TAB_CATEGORY].strip()) > 0 :
                output_dict['sub_tab_category'] = input_dict[SUB_TAB_CATEGORY].strip().capitalize()

        if TEST_SNIPPET_LINK in input_dict:
            if input_dict[TEST_SNIPPET_LINK] and len(input_dict[TEST_SNIPPET_LINK].strip()) > 0 :
                output_dict['snippet_url'] = input_dict[TEST_SNIPPET_LINK].strip().capitalize()

        if 'tab_category' not in output_dict:
            if COMPETENCY_SKILLS in input_dict:
                if input_dict[COMPETENCY_SKILLS] and len(input_dict[COMPETENCY_SKILLS].strip()) > 0 :
                    output_dict['competency_group'] = input_dict[COMPETENCY_SKILLS].strip().capitalize()
        
        if CURRENT_NEWS in input_dict:
            if input_dict[CURRENT_NEWS] and len(input_dict[CURRENT_NEWS].strip()) > 0:
                output_dict['articles'] = input_dict.get(CURRENT_NEWS,None)

        if IMAGE_URL in input_dict:
            if input_dict[IMAGE_URL] and len(input_dict[IMAGE_URL].strip()) > 0:
                output_dict['image_url'] = input_dict.get(IMAGE_URL,None)

        if SOURCE in input_dict :
            if input_dict[SOURCE] and len(input_dict[SOURCE].strip()) > 0:
                output_dict['source'] = input_dict.get(SOURCE,None)

        if USER_ID in input_dict :
            if input_dict[USER_ID] and len(input_dict[USER_ID].strip()) > 0:
                output_dict['creator_user_id'] = input_dict.get(USER_ID,None)
        
        if RATINGS in input_dict:
            if input_dict[RATINGS] and len(input_dict[RATINGS].strip()) > 0:
                output_dict['rating'] = input_dict.get(RATINGS,None)
                
        if VISUAL_TAGS in input_dict:
            if input_dict[VISUAL_TAGS] and len(input_dict[VISUAL_TAGS].strip()) > 0:
                output_dict['visual_tags'] = input_dict.get(VISUAL_TAGS,None)


        if TED_TALK_AND_HBR_CASE in input_dict.keys():
            if input_dict[TED_TALK_AND_HBR_CASE] and len(input_dict(TED_TALK_AND_HBR_CASE).strip()) > 0:
                output_dict["tedtalk_and_hbr_case"] = input_dict[TED_TALK_AND_HBR_CASE]

        if REPORT_DESCRIPTION in input_dict:
            if input_dict[REPORT_DESCRIPTION] and len(input_dict[REPORT_DESCRIPTION].strip()) > 0 :
                output_dict["report_description"] = input_dict[REPORT_DESCRIPTION].strip()

        if VIDEO_SCRIPT in input_dict:
            if input_dict[VIDEO_SCRIPT] and len(input_dict[VIDEO_SCRIPT].strip()) > 0 :
                output_dict["video_script"] = input_dict[VIDEO_SCRIPT].strip()
        if SCRIPT_VIDEO_LINK in input_dict:
            if input_dict[SCRIPT_VIDEO_LINK] and len(input_dict[SCRIPT_VIDEO_LINK].strip()) > 0 :
                output_dict["script_video_link"] = input_dict[SCRIPT_VIDEO_LINK].strip()
        if FEEDBACK_SCRIPT_VIDEO_LINK in input_dict:
            if input_dict[FEEDBACK_SCRIPT_VIDEO_LINK] and len(input_dict[FEEDBACK_SCRIPT_VIDEO_LINK].strip()) > 0 :
                output_dict["feedback_script_video_link"] = input_dict[FEEDBACK_SCRIPT_VIDEO_LINK].strip()

        if FEEDBACK_VIDEO_SCRIPT in input_dict:
            if input_dict[FEEDBACK_VIDEO_SCRIPT] and len(input_dict[FEEDBACK_VIDEO_SCRIPT].strip()) > 0 :
                output_dict["feedback_video_script_template"] = input_dict[FEEDBACK_VIDEO_SCRIPT].strip()
        

        if CULTURE_SKILLS in input_dict and len(input_dict[CULTURE_SKILLS]) > 0:
            culture = [ skill.strip() for skill in input_dict[CULTURE_SKILLS].strip().split(',') if skill.strip()]
            output_dict["culture_skills_to_evaluate"] = generate_culture_map(culture)

        if IS_ASSESSMENT in input_dict and len(input_dict[IS_ASSESSMENT]) > 0:
            output_dict["tag"] = 'assessment' if input_dict[IS_ASSESSMENT].strip().lower() == "true" else None

        skills_list = set()
        if f'{KLS} 0' in input_dict.keys() or f'Skill 0'in input_dict:
            for key in input_dict:
                if key.startswith(KLS):
                    temp_skills = input_dict[key].split(',')
                    for skill in temp_skills:
                        skills_list.add(skill.strip())
                elif key.startswith('Skill'):    # for mcq type of test
                    temp_skills = input_dict[key].split(',')
                    for skill in temp_skills:
                        skills_list.add(skill.strip())
            skills_list = list(skills_list)

            # mismatch skill logic
            defined_skills_list = [ skill['name'].strip().lower() for skill in pre_defined_skills ]


            use_skills_fron_skill_bank = False
            if client_info:
                use_skills_fron_skill_bank = client_info.use_skills_from_skill_bank

            else:
                use_skills_fron_skill_bank = tenant.use_skills_from_skill_bank

            if use_skills_fron_skill_bank:
                unmatched_skills = []
                for skills in skills_list:
                    if skills.lower() not in defined_skills_list:
                        unmatched_skills.append(skills)

                if len(unmatched_skills) > 0 and test_type not in (TestTypeChoices.mcq, TestTypeChoices.dynamic_mcq):
                    return {"unmatched_skills": unmatched_skills, "Title": output_dict.get('Title')}, False

            unique_skill_count = len(set(skills_list))
            print('skillist', unique_skill_count)

            if unique_skill_count < 6 and not(output_dict.get('scenario_case') == 'psychometric' or is_transcript_only or output_dict['is_pitch'] == True):
                return {"unique_skills": set(skills_list), "Title": output_dict.get('Title')}, False
            
            if unique_skill_count > 6:
                que_skills = {key: value for key, value in input_dict.items() if key.startswith(KLS)}
                updated_skills = []
                if len(que_skills) > 0:
                    que_skills = limit_unique_skills_per_test(que_skills)
                    for key, value in que_skills.items():
                        input_dict[key] = value
                        updated_skills.extend(value.split(','))

                skills_list = list(set(updated_skills)) if len(updated_skills) > 0 else list(skills_list)
                # skills_list = list(skills_list)[:8]

            output_dict['skills_to_evaluate'] = ','.join(skills_list)

        check_pass = True

        if IS_CHECKIN_TYPE in input_dict:
            if input_dict.get(IS_CHECKIN_TYPE) and len(input_dict[IS_CHECKIN_TYPE].strip()) > 0:
                if input_dict[IS_CHECKIN_TYPE].strip().lower() == 'true':
                    check_pass = False
                else:
                    check_pass = True

                if input_dict[IS_CHECKIN_TYPE].strip().lower() == 'true':
                    candidate_type = input_dict[CANDIDATE_TYPE].capitalize()
                    if not candidate_type:
                        candidate_type = 'Manager'
                    skills_list_candidate = set()
                    for item in get_skills(candidate_type):
                        skills_list_candidate.add(item.lower())
                    skills_list_candidate = list(skills_list_candidate)
                    if sorted(skills_list_candidate) == sorted([i.lower() for i in skills_list]):
                        check_pass = True


        if output_dict.get('scenario_case') in ['process_training','psychometric', 'game'] or is_transcript_only:
            output_dict['skills_to_evaluate'] = "communication skills"


        if EMAIL_ADDRESS_LIST in input_dict:
            if input_dict[EMAIL_ADDRESS_LIST] and len(input_dict[EMAIL_ADDRESS_LIST].strip()) > 0:
                email_list = input_dict[EMAIL_ADDRESS_LIST].split(',')
                email_list = [email.strip() for email in email_list]
                email_list = ','.join(email_list)

                output_dict['email_address_list'] = email_list

        if SEND_ONLY_TO_EMAIL in input_dict:
            if input_dict[SEND_ONLY_TO_EMAIL] and len(input_dict[SEND_ONLY_TO_EMAIL].strip()) > 0:
                send_only_to_email = input_dict[SEND_ONLY_TO_EMAIL].strip().lower()

                if send_only_to_email == "true":
                    output_dict['send_only_to_email'] = True
                elif send_only_to_email == "false":
                    output_dict['send_only_to_email'] = False
                else:
                    output_dict['send_only_to_email'] = False

        if IS_CHECKIN_TYPE in input_dict:
            if input_dict[IS_CHECKIN_TYPE] and len(input_dict[IS_CHECKIN_TYPE].strip()) > 0:
                is_checkin_type = input_dict[IS_CHECKIN_TYPE].strip().lower()

                if is_checkin_type == "true":
                    output_dict['is_checkin_type'] = True
                elif is_checkin_type == "false":
                    output_dict['is_checkin_type'] = False
                else:
                    output_dict['is_checkin_type'] = False

        if IS_LEARNER_PATH in input_dict:
            if input_dict[IS_LEARNER_PATH] and len(input_dict[IS_LEARNER_PATH].strip()) > 0:
                is_learner_path = input_dict[IS_LEARNER_PATH].strip().lower()

                if is_learner_path == "true":
                    output_dict['is_learner_path'] = True
                elif is_learner_path == "false":
                    output_dict['is_learner_path'] = False
                else:
                    output_dict['is_learner_path'] = False

        if IS_EMAIL_TYPE in input_dict:
            if input_dict[IS_EMAIL_TYPE] and len(input_dict[IS_EMAIL_TYPE].strip()) > 0:
                is_email_type = input_dict[IS_EMAIL_TYPE].strip().lower()
                if is_email_type == "true":
                    output_dict['is_email_type'] = True
                elif is_email_type == "false":
                    output_dict['is_email_type'] = False
                else:
                    output_dict['is_email_type'] = False

        if EMAIL_CANDIDATE in input_dict:
            if input_dict[EMAIL_CANDIDATE] and len(input_dict[EMAIL_CANDIDATE].strip()) > 0:
                email_candidate = input_dict[EMAIL_CANDIDATE].strip().lower()

                if email_candidate == "true":
                    output_dict['email_candidate'] = True
                elif email_candidate == "false":
                    output_dict['email_candidate'] = False
                else:
                    output_dict['email_candidate'] = True

        if output_dict.get('scenario_case') == 'assessment':
            output_dict['email_candidate'] = False

        if CANDIDATE_TYPE in input_dict:
            if input_dict[CANDIDATE_TYPE] and len(input_dict[CANDIDATE_TYPE].strip()) > 0:
                output_dict['candidate_type'] = input_dict[CANDIDATE_TYPE].strip().lower()

        if MAX_TEST_ALLOWED in input_dict:
            if input_dict[MAX_TEST_ALLOWED] and len(input_dict[MAX_TEST_ALLOWED].strip()) > 0:
                output_dict['max_test_allowed'] = int(input_dict[MAX_TEST_ALLOWED])
            else:
                output_dict['max_test_allowed'] = None
        
        if SCORE_VISIBLE in input_dict:
            if input_dict[SCORE_VISIBLE] and len(input_dict[SCORE_VISIBLE].strip()) > 0:
                score_visible = input_dict[SCORE_VISIBLE].strip().lower()

                if score_visible == "true":
                    output_dict['score_visible'] = True
                elif score_visible == "false":
                    output_dict['score_visible'] = False
                else:
                    output_dict['score_visible'] = False

        if EXPLANATION_VISIBLE in input_dict:
            if input_dict[EXPLANATION_VISIBLE] and len(input_dict[EXPLANATION_VISIBLE].strip()) > 0:
                explanation_visible = input_dict[EXPLANATION_VISIBLE].strip().lower()

                if explanation_visible == "true":
                    output_dict['explanation_visible'] = True
                elif explanation_visible == "false":
                    output_dict['explanation_visible'] = False
                else:
                    output_dict['explanation_visible'] = False

        question_to_update = None
        if test:
            question_to_update = TestQuestion.objects.filter(test_id=test.uid).order_by('question_number').values_list('question_number','uid')
            question_to_update = {str(question_number): uid for question_number, uid in question_to_update}

        score_config = {}
        que_marks = {
            k[-1]: v
            for k, v in input_dict.items()
            if k.startswith(MCQ_OPTIONS_MARKS)
        }
        for key in input_dict:
            if key.startswith(RANGE):

                score_range = str(input_dict.get(f"{RANGE} {key[len(RANGE) + 1:]}", ''))
                feedback = str(input_dict.get(f"{RANGE_FEEDBACK} {key[len(RANGE) + 1:]}", ''))
                score_config[score_range] = {
                    'score': [r.strip() for r in score_range.split('-')],
                    'feedback': feedback
                }
                
            if key.startswith(QUESTION):
                question = {
                    "question": input_dict[key],
                    "question_type": "subjective",
                    "gpt_prompt_override": input_dict.get(f"{CUSTOM_PROMPT} {key[len(QUESTION) + 1:]}", ''),
                    "subjective_answer": "",
                    "key_learning_point": input_dict.get(f"{KLP} {key[len(QUESTION) + 1:]}", ''),
                    "key_learning_skills": input_dict.get(f"{KLS} {key[len(QUESTION) + 1:]}", None),

                }
                if f"{QUESTION_INSIGHT} {key[len(QUESTION) + 1:]}" in input_dict and len(input_dict[f"{QUESTION_INSIGHT} {key[len(QUESTION) + 1:]}"]) > 0:
                    question["question_insight"] = input_dict.get(f"{QUESTION_INSIGHT} {key[len(QUESTION) + 1:]}", '')
                if f"{QUE_EXPLANATION} {key[len(QUESTION) + 1:]}" in input_dict and len(input_dict[f"{QUE_EXPLANATION} {key[len(QUESTION) + 1:]}"]) > 0:
                    question["que_explanation"] = input_dict.get(f"{QUE_EXPLANATION} {key[len(QUESTION) + 1:]}", '')
                if f"{QUE_MARKS} {key[len(QUESTION) + 1:]}" in input_dict and len(input_dict[f"{QUE_MARKS} {key[len(QUESTION) + 1:]}"]) > 0:
                    question["que_marks"] = input_dict.get(f"{QUE_MARKS} {key[len(QUESTION) + 1:]}", '')
                
                options_for_question = {}
                q_number = key[len(QUESTION):].strip()
                mcq_key = f"{MCQ_OPTIONS} {q_number}"
                for k, value in input_dict.items():
                    print(f"DEBUG: Looking for keys starting with '{mcq_key}', checking key '{k}'")
                    if k.startswith(mcq_key):
                        t = {
                            "opt": value
                            }
                        
                        if k.strip()[-1] in que_marks:
                            t['marks'] = que_marks[k.strip()[-1]]
                                                
                        options_for_question[k.strip()[-1]] = t
                    

                if options_for_question:
                    question["mcq_options"] = options_for_question

                print(f"options_for_question: {options_for_question} for key: {key} and question: {question}")
                # if f"{MCQ_OPTIONS} {key[len(QUESTION) + 1:]}" in input_dict and len(input_dict[f"{MCQ_OPTIONS} {key[len(QUESTION) + 1:]}"]) > 0:
                #     question["mcq_options"] = input_dict.get(f"{MCQ_OPTIONS} {key[len(QUESTION) + 1:]}", '')

                if question_to_update:
                    print(question_to_update.get(key[len(QUESTION) + 1:]),question_to_update)
                    question['question_id'] = question_to_update.get(key[len(QUESTION) + 1:])

                if len(question.get('key_learning_point', '').strip()) == 0 and output_dict.get('scenario_case') in ['process_training', 'psychometric', 'game'] or is_transcript_only:
                    question['key_learning_point'] = "No key learning point for this question"
                    question['key_learning_skills'] = "communication skills"

                if f"{MEDIA_LINK} {key[len(QUESTION) + 1:]}" in input_dict and len(input_dict[f"{MEDIA_LINK} {key[len(QUESTION) + 1:]}"]) > 0:
                    question["media_link"] = input_dict.get(f"{MEDIA_LINK} {key[len(QUESTION) + 1:]}", '')

                if f"{QUE_SNIPPET_LINK} {key[len(QUESTION) + 1:]}" in input_dict and len(input_dict[f"{QUE_SNIPPET_LINK} {key[len(QUESTION) + 1:]}"]) > 0:
                    question["snippet_url"] = input_dict.get(f"{QUE_SNIPPET_LINK} {key[len(QUESTION) + 1:]}", '')

                if f"{ANSWER} {key[len(QUESTION) + 1:]}" in input_dict and len(input_dict[f"{ANSWER} {key[len(QUESTION) + 1:]}"]) > 0:
                    question["mcq_answer"] = input_dict.get(f"{ANSWER} {key[len(QUESTION) + 1:]}", '') # here I am using mcq_answer as correct answer

                if (f"{QUE_IMAGE_LINK} {key[len(QUESTION) + 1:]}" in input_dict and len(input_dict[f"{QUE_IMAGE_LINK} {key[len(QUESTION) + 1:]}"]) > 0) \
                    and (f"{QUE_IMAGE_PROPS} {key[len(QUESTION) + 1:]}" in input_dict and len(input_dict[f"{QUE_IMAGE_PROPS} {key[len(QUESTION) + 1:]}"]) > 0)\
                        and (f"{NARRATION} {key[len(QUESTION) + 1:]}" in input_dict and len(input_dict[f"{NARRATION} {key[len(QUESTION) + 1:]}"]) > 0):

                    que_image_link = input_dict[f"{QUE_IMAGE_LINK} {key[len(QUESTION) + 1:]}"].strip()
                    que_props_list = input_dict[f"{QUE_IMAGE_PROPS} {key[len(QUESTION) + 1:]}"].strip().split(',')
                   
                    narration = input_dict[f"{NARRATION} {key[len(QUESTION) + 1:]}"].strip()
                    image_data_list = []
                    for i in range(0, len(que_props_list), 2):
                        title = que_props_list[i]
                        coord = que_props_list[i + 1]

                        # Create a dictionary for each title and coord pair
                        image_data_list.append({"title": title.strip(), "coord": coord.strip().replace(".",",")})

                    image_data_list.append(narration)

                    media_json[f'que_image {key[len(QUESTION) + 1:]}'] = {que_image_link: image_data_list}
                    

                if test_type == "view":
                    question['is_view_only'] = True
                elif test_type == "single":
                    question['is_view_only'] = True

                output_dict["questions"].append(question)

            elif key.startswith('Story'):

                if test_type == TestTypeChoices.mcq or test_type == TestTypeChoices.dynamic_mcq:
                    key_name = "0"
                    temp = key.strip().split()  # like A
                    if len(temp)>1:
                        key_name = temp[-1]
                

                    if (f"{QUE_IMAGE_LINK} {key_name}" in input_dict and len(input_dict[f"{QUE_IMAGE_LINK} {key_name}"]) > 0) \
                        and (f"{QUE_IMAGE_PROPS} {key_name}" in input_dict and len(input_dict[f"{QUE_IMAGE_PROPS} {key_name}"]) > 0) \
                            and (f"{NARRATION} {key_name}" in input_dict and len(input_dict[f"{NARRATION} {key_name}"]) > 0):

                        que_img_list = input_dict[f"{QUE_IMAGE_LINK} {key_name}"].strip()
                        que_props_list = input_dict[f"{QUE_IMAGE_PROPS} {key_name}"].strip().split(',')
                        narration = input_dict[f"{NARRATION} {key_name}"].strip()
                        print(que_img_list,que_props_list,narration)

                        image_data_list = []
                        for i in range(0, len(que_props_list), 2):
                            title = que_props_list[i]
                            coord = que_props_list[i + 1]

                            # Create a dictionary for each title and coord pair
                            image_data_list.append({"title": title.strip(), "coord": coord.strip().replace(".",",")})

                        image_data_list.append(narration)
                        media_json[f'que_image {key_name}'] = {que_img_list: image_data_list}


                    keys = list(input_dict.keys())
                    question_keys = []  # to store needed field for a question
                    for i in range(len(keys)):
                        if key.strip() == keys[i]:
                            question_keys = (keys[i:i + 5])

                    question_text = input_dict[question_keys[0]]
                    option1_text = input_dict[question_keys[1]]
                    option2_text = input_dict[question_keys[3]]
                    skill1 = input_dict[question_keys[2]].strip()
                    skill2 = input_dict[question_keys[4]].strip()

                    path = question_keys[0]
                    option1_name = question_keys[1]
                    option2_name = question_keys[3]
                    skill1_name = question_keys[2]
                    skill2_name = question_keys[4]

                    question = {
                        "question": question_text,
                        "question_type": "mcq",
                        "mcq_options" : {
                            f"{option1_name}" : {'opt': option1_text, 
                                                f'{skill1_name}': skill1
                                                },
                            f"{option2_name}" : {'opt': option2_text,
                                                f'{skill2_name}': skill2}

                        },
                        'mcq_path' : path,
                        "key_learning_point": "No key learning point for this question",
                        "key_learning_skills": f'{skill1},{skill2}'

                    }

                    if f"{MEDIA_LINK} {key_name}" in input_dict and len(input_dict[f"{MEDIA_LINK} {key_name}"]) > 0:
                        question["media_link"] = input_dict.get(f"{MEDIA_LINK} {key_name}", '')
                    if f"{QUE_SNIPPET_LINK} {key_name}" in input_dict and len(input_dict[f"{QUE_SNIPPET_LINK} {key_name}"]) > 0:
                        question["snippet_url"] = input_dict.get(f"{QUE_SNIPPET_LINK} {key_name}", '')

                    output_dict["questions"].append(question)
        print(media_json)      
        if media_json:
            output_dict['media_props'] = media_json

        if test_type == 'single' and len(output_dict["questions"]) > 1:
            output_dict["questions"][-1]["is_view_only"] = False

        output_dict['total_question'] = int(len(output_dict['questions']))

        if score_config:
            output_dict['score_config'] = score_config

        if test_type == TestTypeChoices.dynamic_mcq:
            print(f"********************** total questions **********************: {input_dict}")
            if 'total_question' not in input_dict:
                logger.error("total question not found")
            output_dict['total_question'] = input_dict['total_question']

            for i in range(1, int(output_dict['total_question'])):
                question = {
                        "question": f"dummy question - {i}",
                        "question_type": "mcq",
                        "mcq_options" : {},
                        'mcq_path' : "path",
                        "key_learning_point": "No key learning point for this question",
                        "key_learning_skills": f'dummy skill'

                    }


                output_dict["questions"].append(question)

        print('output_dict',output_dict)
        output_json = json.dumps(output_dict)

        return output_json, check_pass

    except Exception as e:
        logger.exception(e)
        return {}, False


def login_web(email, password):
    try:
        if (email and password):
            headers = {
                'Content-Type': 'application/json',
            }
            data = json.dumps({
                'email': email,
                'password': password,
                'user_type': 'recruiter'
            })
            response = requests.post(
                API_ENDPOINT_LOGIN_WEB, data=data, headers=headers, verify=False)

            # Extract access token from response
            if (response.status_code == 200):
                access_token = response.json()['access']
                return access_token
            else:
                return False
    except Exception as e:
        return False


def login_slack(email, password, subdomain_prefix):
    """
    This function is used to authenticate a user with Slack using their email and password.

    The function constructs a payload with the user's email, password, and subdomain prefix, 
    then sends a POST request to the Slack login API endpoint. If the response status code is 200, 
    it means the login was successful and the function returns the access token. 
    If the status code is not 200, the function returns False. 
    If any exception occurs during the process, it is logged and the function also returns False.

    Parameters:
    email (str): The email address of the user. It should be a valid email address.
    password (str): The password of the user. It should not be empty.
    subdomain_prefix (str): The subdomain prefix of the user's Slack workspace. It should not be empty.

    Returns:
    str or bool: The access token as a string if the login is successful, False otherwise.

    Example:
    >>> login_slack('test@example.com', 'password123', 'myworkspace')
    'xoxp-1111827399-16111519414-20367011469-5f89a31i07'
    """
    try:
        url = f"{BACKEND}/api/v1/webauth/login/"
        # url = "http://localhost:8000/api/v1/webauth/login/"

        payload = json.dumps({
            "subdomain_prefix": subdomain_prefix,
            "identity_context": {
                "identity_type": "email",
                "value": email
            },
            "password": password
        })
        headers = {
            'Content-Type': 'application/json'
        }

        response = requests.request("POST", url, headers=headers, data=payload)

        if (response.status_code == 200):
            access_token = response.json()['access']
            return access_token
        else:
            return False

    except Exception as e:
        logger.error(e)
        return False


def create_test_web(csv_file, email, password):
    # List of column names to check for null or empty values
    columns_check = []

    access_token = login_web(email, password)
    if (access_token):
        logger.info("Login successful")
        valid_rows = []

        try:
            csv_text = TextIOWrapper(csv_file, encoding='utf-8-sig')
            csv_reader = csv.DictReader(csv_text)

            all_rows = list(csv_reader)

            # Check for null or empty data in specified columns for each row
            for row_data in all_rows:
                for col in columns_check:
                    if col not in row_data:
                        raise Exception(f"Column '{col}' not found in row")
                    elif not row_data[col]:
                        raise Exception(
                            f"Column '{col}' has null or empty value in row")

                # If row is valid, append it to list of valid rows to be sent to API
                valid_rows.append(row_data)

            logger.info(f"Total valid records: {len(valid_rows)}")

            # Call the API for all valid rows
            for row_data in valid_rows:

                raw_data = json.dumps(row_data)
                # Format the data as per the API requirements
                json_data = format_test_data_web(raw_data)

                # Calling the Test creation API with JSON data
                try:

                    headers = {
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {access_token}'
                    }

                    response = requests.post(
                        API_ENDPOINT_WEB, data=json_data, headers=headers, verify=False)

                except Exception as e:
                    return {
                        "errors": [f"Error occurred; Could not create tests"],
                        "exception": True
                    }

                # Check for successful API call
                if response.status_code != 201:
                    raise Exception("API call failed")

            logger.info(f"Total successful records created: {len(valid_rows)}")
            return {
                "success": True,
                "message": "Test created successfully",
                'errors': []
            }

        except Exception as e:
            return {
                "errors": [f"Error occurred; Could not create tests"],
                "exception": True
            }
    else:
        return {
            "errors": ["Invalid credentials"],
            "exception": True
        }


def create_test_slack(csv_file, email, password, subdomain_prefix):
    """
    This function is designed to create tests on Slack by reading data from a CSV file and making API calls.

    The function performs the following steps:
    1. Logs into Slack using provided email and password.
    2. Reads the CSV file and checks for null or empty values in specified columns for each row.
    3. Checks for empty Key Learning Skills (KLS), Key Learning Points (KLP), and questions.
    4. If a row is valid, it is appended to a list of valid rows to be sent to the API.
    5. For each valid row, the function formats the data as per the API requirements and makes a POST request to the API endpoint.
    6. If the API call is successful, the function increments a counter for successful records and maps the test name to the test code.
    7. If the API call fails, the function raises an exception.
    8. After all rows have been processed, the function writes the test name to test code mapping to a CSV file and returns it as a response.

    Parameters:
    csv_file (file): A CSV file containing the test data.
    email (str): The email address used to log into Slack.
    password (str): The password used to log into Slack.
    subdomain_prefix (str): The subdomain prefix for the Slack workspace.

    Returns:
    dict: A dictionary containing the following keys:
        - "success" (bool): Indicates whether the tests were created successfully.
        - "message" (str): A message indicating the result of the operation.
        - "errors" (list): A list of error messages, if any.
        - "file_response" (HttpResponse): A response containing the CSV file with the test name to test code mapping.
        - "exception" (bool): Indicates whether an exception occurred.

    Example:
    create_test_slack(csv_file, 'test@example.com', 'password', 'test')
    """
    logger.info(subdomain_prefix)
    # List of column names to check for null or empty values
    columns_check = [TITLE, DESCRIPTION,
                     INTERACTION_MODE, EMAIL_ADDRESS_LIST, TEST_TYPE, SCENARIO_CASE, CERTIFICATE_TITLE, AREA_DOMAIN, SKILL_DOMAIN]

    access_token = login_slack(email, password, subdomain_prefix)
    is_update = False

    if access_token:
        logger.info("Login successful")
        valid_rows = []
        response = None
        occured_errors = []
        tenant = tenant_from_subdomain_prefix(subdomain_prefix=subdomain_prefix)

        try:
            csv_text = TextIOWrapper(csv_file, encoding='utf-8-sig')
            csv_reader = csv.DictReader(csv_text)

            all_rows = list(csv_reader)

            # Check for null or empty data in specified columns for each row
            for row_data in all_rows:
                scenario_case = row_data.get(SCENARIO_CASE, '').lower()
                test_code = row_data.get(TEST_CODE, '').strip()
                columns_check = []
                if len(test_code) > 0:
                    columns_check = []
                elif scenario_case == 'observation':
                    columns_check = [TITLE, DESCRIPTION, EMAIL_ADDRESS_LIST, TEST_TYPE, SCENARIO_CASE]
                elif scenario_case == 'game':
                    columns_check = [TITLE, DESCRIPTION,
                     INTERACTION_MODE, EMAIL_ADDRESS_LIST, TEST_TYPE, SCENARIO_CASE, CERTIFICATE_TITLE, AREA_DOMAIN, SKILL_DOMAIN, SCORE_VISIBLE, EXPLANATION_VISIBLE]
                else:
                    columns_check = [TITLE, DESCRIPTION,
                     INTERACTION_MODE, EMAIL_ADDRESS_LIST, TEST_TYPE, SCENARIO_CASE, CERTIFICATE_TITLE, AREA_DOMAIN, SKILL_DOMAIN]


                for col in columns_check:
                    if col not in row_data:
                        occured_errors.append(f"Column '{col}' not found in row")
                    elif not row_data[col]:
                        occured_errors.append(f"Column '{col}' has null or empty value in row")

            # Checkoing for empty KLS and KLP and questions
            for row_data in all_rows:
                for key in row_data:
                    if key.startswith(QUESTION):
                        if not row_data[key] and (TEST_CODE not in row_data and IS_IMMERSIVE not in row_data or row_data[IS_IMMERSIVE].lower() == "false" or len(row_data[IS_IMMERSIVE]) == 0):
                            occured_errors.append(f"Column '{key}' has null or empty value in row")
                    if TEST_CODE not in row_data and (key.startswith(KLS) or key.startswith(KLP)):
                        if not row_data[key]:
                            occured_errors.append(f"Column '{key}' has null or empty value in row")
                        
                    if (SCENARIO_CASE in row_data and row_data[SCENARIO_CASE] == 'psychometric') and (PSYCHOMETRIC not in row_data or len(row_data[PSYCHOMETRIC].strip()) == 0):
                        occured_errors.append(f"Column '{PSYCHOMETRIC}' has null or empty value in row")

                        

                # If row is valid, append it to list of valid rows to be sent to API
                if len(occured_errors)> 0:
                    raise Exception(set(occured_errors))
                valid_rows.append(row_data)

            logger.info(f"Total valid records: {len(valid_rows)}")

            test_name_test_code_map = {}
            cnt = 1
            record_created = 0

            # Call the API for all valid rows
            for row_data in valid_rows:
                # logger.info(row_data)
                is_update = True if TEST_CODE in row_data.keys() and len(row_data[TEST_CODE].strip())> 0 else False
                raw_data = json.dumps(row_data)
                # Format the data as per the API requirements
                # Sending the creator_id as a parameter change it later
                json_data, check_pass = format_test_data_slack(raw_data,tenant)
                # logger.info(json_data)
                # Calling the Test creation API with JSON data

                if check_pass:

                    try:

                        headers = {
                            'Content-Type': 'application/json',
                            'Authorization': f'Bearer {access_token}'
                        }

                        logger.info("[Making Request]")

                        response = requests.post(
                            API_ENDPOINT_SLACK, data=json_data, headers=headers, verify=False)

                        logger.info("[Response Received]\n")

                        row_data = json.loads(raw_data)
                        title = row_data[TITLE] if not is_update else row_data['Test Code']
                        test_name_test_code_map[f"Test {cnt} {'updated' if is_update else ''}: {title}"
                                                ] = f"API call failed Details: {response.json()}" if response.status_code != 201 else response.json().get('test_code')
                        row_data = json.dumps(row_data)

                        cnt += 1
                        record_created += 1

                    except Exception as e:
                        logger.error(e)
                        occured_errors.append(f"Error occurred; Could not update tests {e.args}" if is_update else f"Error occurred; Could not create tests {e.args}")
                        return {
                            "errors": [f"Error occurred; Could not update tests {e.args}"] if is_update else [f"Error occurred; Could not create tests {e.args}"],
                            "exception": True,
                            "response": response
                        }

                    # Check for successful API call
                    if response.status_code != 201:
                        occured_errors.append(f"API call failed Details: {response.json()}")
                                            

                else:
                    title = row_data[TITLE] if not is_update else row_data['Test Code']

                    if "unmatched_skills" in json_data:
                        occured_errors.append("Mismatching skills")
                        test_name_test_code_map[f"Test {cnt}: {title}"
                                            ] = f"csv file contains Mismatching skills in test {json_data['Title']}: {', '.join(json_data['unmatched_skills'])}"
                        # return {
                        #     "errors": [f"csv file contains Mismatching skills in test {title}: {', '.join(json_data['unmatched_skills'])}"],
                        #     "exception": True,
                        # }
                    
                    elif "error" in json_data:
                        occured_errors.append(json_data["error"])

                        test_name_test_code_map[f"Test {cnt}: {title}"
                                            ] = json_data["error"]
                        # return {
                        #     "errors": [json_data["error"]],
                        #     "exception": True,
                        # }

                    elif "unique_skills" in json_data:
                        occured_errors.append(f"Minimum skill count detected in test {json_data['Title']}: {', '.join(json_data['unique_skills'])}")

                        test_name_test_code_map[f"Test {cnt}: {title}"
                                            ] = f"Minimum skill count detected in test {json_data['Title']}: {', '.join(json_data['unique_skills'])}"
                                            
                    else:
                        test_name_test_code_map[f"Test {cnt}: {title}"
                                                ] = "Not updated For This Title Because of it is not suiatable for checkin type test" if is_update else "Not Created For This Title Because of it is not suiatable for checkin type test"
                    
                        occured_errors.append("Not updated For This Title Because of it is not suiatable for checkin type test" if is_update else "Not Created For This Title Because of it is not suiatable for checkin type test")
                    cnt += 1

            logger.info(f"Total successful records created: {record_created}")

            # Create a csv file for test_name to test_code mapping
            with open('test_name_test_code_map.csv', 'w') as f:
                for key in test_name_test_code_map.keys():
                    f.write("%s,%s\n" % (key, test_name_test_code_map[key]))
            # Download the csv file
            with open('test_name_test_code_map.csv', 'rb') as fh:
                file_response = HttpResponse(
                    fh.read(), content_type="text/csv", status=200)
                file_response['Content-Disposition'] = 'inline; filename=' + \
                    os.path.basename('test_name_test_code_map.csv')

            # Delete the csv file
            os.remove('test_name_test_code_map.csv')

            print('occured', len(occured_errors))
            if len(occured_errors)> 0:
                return {
                "message": "Test updated successfully" if is_update else "Test created successfully",
                'errors': occured_errors,
                "exception": True,
                'file_response': file_response,
            }
            else:
                return {
                    "success": True,
                    "message": "Test updated successfully" if is_update else "Test created successfully",
                    'errors': [],
                    'file_response': file_response,
                }

        except Exception as e:
            logger.exception(e)
            return {
                "errors": [f"Error occurred; Could not update tests {e.args}"] if is_update else [f"Error occurred; Could not create tests {e.args}"],
                "exception": True,
            }
    else:
        return {
            "errors": ["Invalid credentials"],
            "exception": True,
        }


def create_test_orchestrated_conversation_slack(csv_file, email, password, subdomain_prefix):
    """
    This function creates orchestrated conversation tests in Slack based on the data provided in a CSV file.

    The function first logs into Slack using the provided email, password, and subdomain prefix. It then reads the CSV file and checks each row for null or empty values in the 'Title', 'Context', 'EMAIL_ADDRESS_LIST', and 'SCENARIO_CASE' columns. If any of these columns are missing or have null or empty values, an exception is raised.

    The function then formats the data from each valid row according to the API requirements for creating an orchestrated conversation test and sends a POST request to the Slack API to create the test. If the API call is successful, the test code is stored in a dictionary with the test name as the key.

    After all valid rows have been processed, the function writes the test name to test code mapping to a CSV file, sends the file as a response, and then deletes the file.

    Args:
        csv_file (file): A CSV file containing the data for creating the orchestrated conversation tests.
        email (str): The email address to use for logging into Slack.
        password (str): The password to use for logging into Slack.
        subdomain_prefix (str): The subdomain prefix to use for logging into Slack.

    Returns:
        dict: A dictionary containing the following keys:
            - 'success': A boolean indicating whether the tests were created successfully.
            - 'message': A string containing a success message if the tests were created successfully.
            - 'errors': A list of strings containing error messages if any errors occurred.
            - 'file_response': A HttpResponse object containing the CSV file with the test name to test code mapping if the tests were created successfully.
            - 'exception': A boolean indicating whether an exception occurred.

    Raises:
        Exception: If any required columns are missing or have null or empty values in the CSV file.
        Exception: If the API call fails.

    Example:
        >>> csv_file = open('test_data.csv', 'r')
        >>> email = 'user@example.com'
        >>> password = 'password'
        >>> subdomain_prefix = 'example'
        >>> create_test_orchestrated_conversation_slack(csv_file, email, password, subdomain_prefix)
        {
            'success': True,
            'message': 'Test created successfully',
            'errors': [],
            'file_response': <HttpResponse status_code=200, "text/csv">,
            'exception': False
        }
    """
    logger.info(f"create_test_orchestrated_conversation_slack: domain prefix {subdomain_prefix}")
    # List of column names to check for null or empty values
    columns_check = ['Title', 'Context', EMAIL_ADDRESS_LIST,
                     SCENARIO_CASE ]

    access_token = login_slack(email, password, subdomain_prefix)
    is_update = False

    if access_token:
        logger.info("Login successful")
        valid_rows = []
        response = None
        occured_errors = []

        try:
            csv_text = TextIOWrapper(csv_file, encoding='utf-8-sig')
            csv_reader = csv.DictReader(csv_text)

            all_rows = list(csv_reader)

            # Check for null or empty data in specified columns for each row

            

            for row_data in all_rows:
                scenario_case = row_data.get(SCENARIO_CASE, '').lower()
                if TEST_CODE in row_data:
                    columns_check = []
                else:
                    if scenario_case == 'game':
                        columns_check.extend([TEST_CUSTUM_PROMPT, IS_SINGLE_SELECT,SCORE_VISIBLE,EXPLANATION_VISIBLE])
                    elif scenario_case == 'interview':
                        columns_check.extend([AREA_DOMAIN, CERTIFICATE_TITLE, CANDIDATE_TYPE, BACKGROUND, SKILL_DOMAIN])
                    else:
                        columns_check.extend([AREA_DOMAIN, CERTIFICATE_TITLE, CANDIDATE_TYPE, SKILL_DOMAIN])

                for col in columns_check:
                    if col not in row_data:
                        occured_errors.append(f"Column '{col}' not found in row")
                    elif not row_data[col]:
                        occured_errors.append(f"Column '{col}' has null or empty value in row")
                    

                # If row is valid, append it to list of valid rows to be sent to API
                if len(occured_errors)> 0:
                    raise Exception(set(occured_errors))
                
                valid_rows.append(row_data)

            logger.info(f"Total valid records: {len(valid_rows)}")

            test_name_test_code_map = {}
            cnt = 1
            record_created = 0
            # Call the API for all valid rows
            for row_data in valid_rows:

                # logger.info(row_data)
                is_update = True if TEST_CODE in row_data and len(row_data[TEST_CODE])> 0 else False
                raw_data = json.dumps(row_data)
                # Format the data as per the API requirements
                # Sending the creator_id as a parameter change it later
                json_data, check_pass = format_test_orchestrated_conversation(
                    raw_data)
                # logger.info(json_data)
                # Calling the Test creation API with JSON data

                if check_pass:
                    try:

                        headers = {
                            'Content-Type': 'application/json',
                            'Authorization': f'Bearer {access_token}'
                        }

                        logger.info("[Making Request]")

                        response = requests.post(
                            API_ENDPOINT_SLACK, data=json_data, headers=headers, verify=False)

                        logger.info("[Response Received]\n")
                        
                        row_data = json.loads(raw_data)
                        title = row_data[TITLE] if not is_update else row_data['Test Code']

                        test_name_test_code_map[f"Test {cnt} {'updated' if is_update else ''}: {title}"
                                                ] = f"API call failed Details: {response.json()}" if response.status_code != 201 else response.json().get('test_code')
                        row_data = json.dumps(row_data)

                        cnt += 1
                        record_created += 1

                    except Exception as e:
                        logger.exception(e)
                        occured_errors.append(f"Error occurred; Could not update tests {e.args}" if is_update else f"Error occurred; Could not create tests {e.args}")
                        # return {
                        #     "errors": [f"Error occurred; Could not update tests {e.args}"] if is_update else [f"Error occurred; Could not create tests {e.args}"] ,
                        #     "exception": True,
                        #     "response": response
                        # }

                    # Check for successful API call
                    logger.info(f"response: {response.json()}")

                    if response.status_code != 201:
                        occured_errors.append(f"API call failed Details: {response.json()}")
                        
                else:
                    title = row_data[TITLE] if not is_update else row_data['Test Code']

                    if "last_question_for_user" in json_data:
                        occured_errors.append(json_data['last_question_for_user'])
                        test_name_test_code_map[f"Test {cnt}: {title}"
                                                ] = json_data['last_question_for_user']
                        # return {
                        #     "errors": [json_data['last_question_for_user']],
                        #     "exception": True,
                        # }
                    elif "error" in json_data:
                        occured_errors.append(json_data["error"])

                        test_name_test_code_map[f"Test {cnt}: {title}"
                                                ] = json_data["error"]
                        # return {
                        #     "errors": [json_data["error"]],
                        #     "exception": True,
                        # }
                    else:
                        occured_errors.append("Not updated For This Title, Reason: Check-in type" if is_update else "Not Created For This Title, Reason: Check-in type")

                        test_name_test_code_map[f"Test {cnt}: {title}"
                                                ] = "Not updated For This Title, Reason: Check-in type" if is_update else "Not Created For This Title, Reason: Check-in type"
                    cnt += 1

            logger.info(f"Total successful records created: {record_created}")

            # Create a csv file for test_name to test_code mapping
            with open('test_name_test_code_map.csv', 'w') as f:
                for key in test_name_test_code_map.keys():
                    f.write("%s,%s\n" % (key, test_name_test_code_map[key]))
            # Download the csv file
            with open('test_name_test_code_map.csv', 'rb') as fh:
                file_response = HttpResponse(
                    fh.read(), content_type="text/csv", status=200)
                file_response['Content-Disposition'] = 'inline; filename=' + \
                    os.path.basename('test_name_test_code_map.csv')

            # Delete the csv file
            os.remove('test_name_test_code_map.csv')

            print('occured', len(occured_errors))
            if len(occured_errors)> 0:
                return {
                "message": "Test updated successfully" if is_update else "Test created successfully",
                'errors': occured_errors,
                "exception": True,
                'file_response': file_response,
            }
            else:
                return {
                    "success": True,
                    "message": "Test updated successfully" if is_update else "Test created successfully",
                    'errors': [],
                    'file_response': file_response,
                }

        except Exception as e:
            logger.error(e)
            return {
                "errors": [f"Error occurred; Could not update tests {e.args}"] if is_update else [f"Error occurred; Could not create tests {e.args}"],
                "exception": True,
            }
    else:
        return {
            "errors": ["Invalid credentials"],
            "exception": True,
        }




def create_coaches_and_bots_from_data(file, email, password, subdomain_prefix):
    logger.info("########################## Creating Coaches and Bots from data ############################")
    url = f'{BACKEND}/api/v1/coaching-conversations/create-user-profile-and-bot/'
    data = []
    
    try:
        csv_text = TextIOWrapper(file, encoding='utf-8-sig')
        csv_reader = csv.DictReader(csv_text)
        all_rows = list(csv_reader)
        data = all_rows
    except Exception as e:
            logger.error(e)
            return {
                "errors": [f"Error occurred; Could not create tests {e.args}"],
                "exception": True,
            }
    
    # with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
    #     reader = csv.DictReader(csvfile)
    #     for row in reader:
    #         data.append(dict(row))
    # print(data)

    try:
        access_token = login_slack(email, password, subdomain_prefix)

    except Exception as e:
        logger.exception(f"failed to login : {e}")
        return {
                "errors": [f"Invalid Credential"],
                "exception": True,
            }


    headers = {
                "Authorization": f"Bearer {access_token}",
                'Content-Type': "application/json"
            }
    try:
        response = requests.post(url,data=json.dumps({'data': data}),headers=headers)
        print(f"resp: {response.json()}")
        data = response.json()['data']
        csv_file_path = 'coaches-bots-data.csv'
        field_names = list(data[0].keys())

        # Write the data to a CSV file
        with open(csv_file_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=field_names)
            writer.writeheader()
            for row in data:
                writer.writerow(row)
                
        with open(csv_file_path, 'rb') as fh:
                file_response = HttpResponse(
                    fh.read(), content_type="text/csv", status=200)
                file_response['Content-Disposition'] = 'inline; filename=' + \
                    os.path.basename(csv_file_path)

        # Delete the csv file
        os.remove(csv_file_path)

        logger.info(f'CSV file "{csv_file_path}" created successfully.')
        return {
                    "success": True,
                    "message": "Test created successfully",
                    'errors': [],
                    'file_response': file_response,
                }
    except Exception as e:
        logger.exception(f"{e}")
        return {'errors':["Error occurred; Could not create coaches and bots"], "exception": True}



s = "Section A: left-right, Up-down; Anything B: Top-Down,Here-There;"


def extract_sections(s):
    # Regular expression to match any section name and their corresponding parameters
    pattern = r"([^:]+):\s*([^;]+);"

    # Find all matches
    matches = re.findall(pattern, s)

    # Process and print the results
    sections = {}
    for match in matches:
        section_name = match[0].strip()  # Extract section name
        parameters = [param.strip() for param in match[1].split(',')]  # Extract and clean parameters
        sections[section_name] = parameters

    logger.info(f"Sections extracted: {sections}")
    return sections
    
