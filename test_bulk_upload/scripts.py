import csv
import re
import json
import requests
import os
from dotenv import load_dotenv
from io import TextIOWrapper
import logging
from django.http import HttpResponse
from .constants import get_skills
from settings import BACKEND
from skills.constants import skills as pre_defined_skills
from tests.models import TestTypeChoices

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

def format_test_orchestrated_conversation(raw_data):
    try:
        input_dict = json.loads(raw_data)

        output_dict = {
            "creator_id": None,
            "title": input_dict['Title'],
            "description": input_dict['Context'],
            "interaction_mode": "text",
            "email_candidate": True,
            "test_type": "orchestrated_conversation",
            "scenario_case": input_dict[SCENARIO_CASE].strip().lower(),
            "description_media": input_dict.get(DESCRIPTION_MEDIA, None),
            "gpt_prompt_override": input_dict.get(TEST_CUSTUM_PROMPT,""),
            "questions": [],
        }
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
                    output_dict["interaction_mode"] = 'audio'

        if IS_DYNAMIC_THREAD in input_dict:
            if input_dict[IS_DYNAMIC_THREAD] and len(input_dict[IS_DYNAMIC_THREAD].strip()) > 0:
                is_dynamic_thread = input_dict[IS_DYNAMIC_THREAD].strip().lower()

                if is_dynamic_thread == "true":
                    output_dict["test_type"] = TestTypeChoices.dynamic_discussion_thread
                    output_dict["interaction_mode"] = 'audio'
                    
        if CLIENT in input_dict:
            if input_dict[CLIENT] and len(input_dict[CLIENT].strip()) > 0 :
                output_dict['client_name'] = input_dict[CLIENT].strip().capitalize()

        if TED_TALK_AND_HBR_CASE in input_dict:
            if input_dict[TED_TALK_AND_HBR_CASE] and len(input_dict[TED_TALK_AND_HBR_CASE].strip()) > 0 :
                output_dict["tedtalk_and_hbr_case"] = input_dict[TED_TALK_AND_HBR_CASE]


        if IS_GAME_TYPE in input_dict:
            if input_dict[IS_GAME_TYPE] and len(input_dict[IS_GAME_TYPE].strip()) > 0:
                is_game_type = input_dict[IS_GAME_TYPE].strip().lower()

                if is_game_type == "true":
                    output_dict['is_game_type'] = True
                elif is_game_type == "false":
                    output_dict['is_game_type'] = False
                else:
                    output_dict['is_game_type'] = False

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
        
        
        if IMAGE_URL in input_dict:
            output_dict['image_url'] = input_dict.get(IMAGE_URL,None)

        if SOURCE in input_dict :
            output_dict['source'] = input_dict.get(SOURCE,None)
        
        if RATINGS in input_dict:
            output_dict['rating'] = input_dict.get(RATINGS,None)

        bot_count = sum(1 for key in input_dict.keys()
                        if key.startswith('Person'))
        if bot_count == 1:
            output_dict["is_single_bot"] = True

        if output_dict["test_type"] == TestTypeChoices.dynamic_discussion and bot_count > 1:
            return {"error": "Dynamic discussion can only have one bot"}, False

        if input_dict[IS_CHECKIN_TYPE] == 'TRUE':
            check_pass = False
        else:
            check_pass = True

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

        # skills_list = input_dict[SKILLS_TO_EVALUATE]
        # skills_list_temp = []
        # for s in skills_list.split(','):
        #     skills_list_temp.append(s.strip().capitalize())
        # skills_list = skills_list_temp

        if input_dict[IS_CHECKIN_TYPE] == 'TRUE':
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
            check_pass = True

        if input_dict[IS_CHECKIN_TYPE] and len(input_dict[IS_CHECKIN_TYPE].strip()) > 0:
            is_checkin_type = input_dict[IS_CHECKIN_TYPE].strip().lower()

            if is_checkin_type == "true":
                output_dict['is_checkin_type'] = True
            elif is_checkin_type == "false":
                output_dict['is_checkin_type'] = False
            else:
                output_dict['is_checkin_type'] = False

        if input_dict[EMAIL_ADDRESS_LIST] and len(input_dict[EMAIL_ADDRESS_LIST].strip()) > 0:

            email_list = input_dict[EMAIL_ADDRESS_LIST].split(',')
            email_list = [email.strip() for email in email_list]
            email_list = ','.join(email_list)

            output_dict['email_address_list'] = email_list

        # if input_dict[SKILLS_TO_EVALUATE] and len(input_dict[SKILLS_TO_EVALUATE].strip()) > 0:

        #     skill_list = input_dict[SKILLS_TO_EVALUATE].split(',')
        #     skill_list = [skill.strip() for skill in skill_list]
        #     skill_list = ','.join(skill_list)
        #     output_dict["skills_to_evaluate"] = skill_list

        # saving skills_to_evaluate from backend only

        candidate_type = input_dict[CANDIDATE_TYPE].capitalize()
        if not candidate_type:
            candidate_type = 'Manager'
        skills_list_candidate = set()
        for item in get_skills(candidate_type):
            skills_list_candidate.add(item.capitalize())

        evaluation_skill_list = [skill.strip() for skill in sorted(skills_list_candidate)]
        evaluation_skill_list = ','.join(evaluation_skill_list)
        output_dict["skills_to_evaluate"] = evaluation_skill_list


        if input_dict[CANDIDATE_TYPE] and len(input_dict[CANDIDATE_TYPE].strip()) > 0:
            output_dict['candidate_type'] = input_dict[CANDIDATE_TYPE].strip().lower()

        initial_messages = []
        test_main_context = input_dict['Context']
        persons = []

        for key in input_dict:
            if key.startswith('Person'):
                name = input_dict[key].split(':')[0].strip()
                persons.append(name)
                initial_messages.append(input_dict[key])
                test_main_context += input_dict[key]

        orchestrated_conversation_details = {
            "test_main_context": test_main_context,
            "test_user_persona": candidate_type,
            "objective": input_dict['Context'],
            "initial_messages": initial_messages
        }

        if START_WITH_USER in input_dict:
            if input_dict[START_WITH_USER] and len(input_dict[START_WITH_USER].strip()) > 0:
                start_with_user = input_dict[START_WITH_USER].strip().lower()
                orchestrated_conversation_details["start_with_user"] = start_with_user

        if BACKGROUND in input_dict:
            if input_dict[BACKGROUND] and len(input_dict[BACKGROUND].strip()) > 0:
                background = input_dict[BACKGROUND].strip().lower()
                orchestrated_conversation_details["background"] = background
                
        output_dict['orchestrated_conversation_details'] = orchestrated_conversation_details

        for key in input_dict:
            if key.isdigit():
                question = {
                    "question": input_dict[key],
                    "question_type": "subjective",
                    "gpt_prompt_override": "",
                    "subjective_answer": ""
                }
                # if "Please respond in order to continue" in input_dict[key]:
                #     question['question_for'] = "user"

                # else:
                #     for name in persons:
                #         if name.split()[0].lower() in input_dict[key].lower():
                #             question['question_for'] = name
                #             break

                matched_name = next((name for name in persons if name.split()[0].lower() in input_dict[key].lower()), None)
                if matched_name:
                    question['question_for'] = matched_name
                else:
                    question['question_for'] = "user"
                                
                output_dict["questions"].append(question)
        
        # checking if last column is for user or not
        last_question = output_dict['questions'][-1]
        if last_question['question_for'] != 'user':
            json_data = {"last_question_for_user": "Last question should be for user"}
            return json_data, False
        

        # checking wheater two user type coming one after other
        question_for = [q['question_for'] for q in output_dict['questions']]
        for i in range(len(question_for) - 1):
            if question_for[i] == "user" and question_for[i + 1] == "user":
                json_data = {"last_question_for_user": "Questions for user should not occur continously"}

                return json_data, False

        

        output_json = json.dumps(output_dict)

        return output_json, check_pass

    except Exception as e:
        logger.error(e)
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


def format_test_data_slack(raw_data):
    try:
        input_dict = json.loads(raw_data)

        output_dict = {
            "creator_id": None,
            "title": input_dict[TITLE],
            "description": input_dict[DESCRIPTION],
            "max_test_allowed": input_dict[MAX_TEST_ALLOWED],
            "interaction_mode": input_dict[INTERACTION_MODE].strip().lower(),
            "test_type": input_dict[TEST_TYPE].strip().lower(),
            "scenario_case": input_dict[SCENARIO_CASE].strip().lower(),
            "description_media": input_dict.get(DESCRIPTION_MEDIA, None),
            "gpt_prompt_override": input_dict.get(TEST_CUSTUM_PROMPT,""),
            "questions": [],
        }
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
        
        if IS_GAME_TYPE in input_dict:
            if input_dict[IS_GAME_TYPE] and len(input_dict[IS_GAME_TYPE].strip()) > 0:
                is_game_type = input_dict[IS_GAME_TYPE].strip().lower()

                if is_game_type == "true":
                    output_dict['is_game_type'] = True
                elif is_game_type == "false":
                    output_dict['is_game_type'] = False
                else:
                    output_dict['is_game_type'] = False


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


        if CLIENT in input_dict:
            if input_dict[CLIENT] and len(input_dict[CLIENT].strip()) > 0 :
                output_dict['client_name'] = input_dict[CLIENT].strip().capitalize()
        
        if IMAGE_URL in input_dict:
            output_dict['image_url'] = input_dict.get(IMAGE_URL,None)

        if SOURCE in input_dict :
            output_dict['source'] = input_dict.get(SOURCE,None)
        
        if RATINGS in input_dict:
            output_dict['rating'] = input_dict.get(RATINGS,None)

        test_type = input_dict[TEST_TYPE].strip().lower()

        if TED_TALK_AND_HBR_CASE in input_dict.keys():
            output_dict["tedtalk_and_hbr_case"] = input_dict[TED_TALK_AND_HBR_CASE]

        skills_list = set()
        for key in input_dict:
            if key.startswith(KLS):
                temp_skills = input_dict[key].split(',')
                for skill in temp_skills:
                    skills_list.add(skill.strip().capitalize())
            elif key.startswith('Skill'):    # for mcq type of test
                temp_skills = input_dict[key].split(',')
                for skill in temp_skills:
                    skills_list.add(skill.strip().capitalize())
        skills_list = list(skills_list)

        defined_skills_list = [ skill['name'].strip().capitalize() for skill in pre_defined_skills ]

        unmatched_skills = []
        for skills in skills_list:
            if skills not in defined_skills_list:
                unmatched_skills.append(skills)

        if len(unmatched_skills) > 0 and test_type not in (TestTypeChoices.mcq, TestTypeChoices.dynamic_mcq):
            return {"unmatched_skills": unmatched_skills, "Title": input_dict['Title']}, False

        if input_dict[IS_CHECKIN_TYPE] == 'TRUE':
            check_pass = False
        else:
            check_pass = True

        if input_dict[IS_CHECKIN_TYPE] == 'TRUE':
            candidate_type = input_dict[CANDIDATE_TYPE].capitalize()
            if not candidate_type:
                candidate_type = 'Manager'
            skills_list_candidate = set()
            for item in get_skills(candidate_type):
                skills_list_candidate.add(item.capitalize())
            skills_list_candidate = list(skills_list_candidate)
            if sorted(skills_list_candidate) == sorted(skills_list):
                check_pass = True

        skills_list = ','.join(skills_list)

        output_dict['skills_to_evaluate'] = skills_list
        if input_dict[SCENARIO_CASE] == 'process_training' or is_transcript_only:
            output_dict['skills_to_evaluate'] = "communication skills"


        if input_dict[EMAIL_ADDRESS_LIST] and len(input_dict[EMAIL_ADDRESS_LIST].strip()) > 0:

            email_list = input_dict[EMAIL_ADDRESS_LIST].split(',')
            email_list = [email.strip() for email in email_list]
            email_list = ','.join(email_list)

            output_dict['email_address_list'] = email_list

        if input_dict[SEND_ONLY_TO_EMAIL] and len(input_dict[SEND_ONLY_TO_EMAIL].strip()) > 0:
            send_only_to_email = input_dict[SEND_ONLY_TO_EMAIL].strip().lower()

            if send_only_to_email == "true":
                output_dict['send_only_to_email'] = True
            elif send_only_to_email == "false":
                output_dict['send_only_to_email'] = False
            else:
                output_dict['send_only_to_email'] = False

        if input_dict[IS_CHECKIN_TYPE] and len(input_dict[IS_CHECKIN_TYPE].strip()) > 0:
            is_checkin_type = input_dict[IS_CHECKIN_TYPE].strip().lower()

            if is_checkin_type == "true":
                output_dict['is_checkin_type'] = True
            elif is_checkin_type == "false":
                output_dict['is_checkin_type'] = False
            else:
                output_dict['is_checkin_type'] = False

        if input_dict[IS_LEARNER_PATH] and len(input_dict[IS_LEARNER_PATH].strip()) > 0:
            is_learner_path = input_dict[IS_LEARNER_PATH].strip().lower()

            if is_learner_path == "true":
                output_dict['is_learner_path'] = True
            elif is_learner_path == "false":
                output_dict['is_learner_path'] = False
            else:
                output_dict['is_learner_path'] = False

        if input_dict[IS_EMAIL_TYPE] and len(input_dict[IS_EMAIL_TYPE].strip()) > 0:
            is_email_type = input_dict[IS_EMAIL_TYPE].strip().lower()

            if is_email_type == "true":
                output_dict['is_email_type'] = True
            elif is_email_type == "false":
                output_dict['is_email_type'] = False
            else:
                output_dict['is_email_type'] = False

        if input_dict[EMAIL_CANDIDATE] and len(input_dict[EMAIL_CANDIDATE].strip()) > 0:
            email_candidate = input_dict[EMAIL_CANDIDATE].strip().lower()

            if email_candidate == "true":
                output_dict['email_candidate'] = True
            elif email_candidate == "false":
                output_dict['email_candidate'] = False
            else:
                output_dict['email_candidate'] = True

        if input_dict[CANDIDATE_TYPE] and len(input_dict[CANDIDATE_TYPE].strip()) > 0:
            output_dict['candidate_type'] = input_dict[CANDIDATE_TYPE].strip().lower()

        if input_dict[MAX_TEST_ALLOWED] and len(input_dict[MAX_TEST_ALLOWED].strip()) > 0:
            output_dict['max_test_allowed'] = int(input_dict[MAX_TEST_ALLOWED])
        else:
            output_dict['max_test_allowed'] = None

        for key in input_dict:
            if key.startswith(QUESTION):
                question = {
                    "question": input_dict[key],
                    "question_type": "subjective",
                    "gpt_prompt_override": input_dict.get(f"{CUSTOM_PROMPT} {key[len(QUESTION) + 1:]}", ''),
                    "subjective_answer": "",
                    "key_learning_point": input_dict.get(f"{KLP} {key[len(QUESTION) + 1:]}", ''),
                    "key_learning_skills": input_dict.get(f"{KLS} {key[len(QUESTION) + 1:]}", None),

                }
                if input_dict[SCENARIO_CASE] == 'process_training' or is_transcript_only:
                    question['key_learning_point'] = "No key learning point for this question"
                    question['key_learning_skills'] = "communication skills"

                if f"{MEDIA_LINK} {key[len(QUESTION) + 1:]}" in input_dict and len(input_dict[f"{MEDIA_LINK} {key[len(QUESTION) + 1:]}"]) > 0:
                    question["media_link"] = input_dict.get(f"{MEDIA_LINK} {key[len(QUESTION) + 1:]}", '')
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

                    output_dict["questions"].append(question)
        print(media_json)      
        if media_json:
            output_dict['media_props'] = media_json

        if test_type == 'single' and len(output_dict["questions"]) > 1:
            output_dict["questions"][-1]["is_view_only"] = False

        output_dict['total_question'] = int(len(output_dict['questions']))

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

        output_json = json.dumps(output_dict)

        return output_json, check_pass

    except Exception as e:
        logger.error(e)
        return None


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

    logger.info(subdomain_prefix)
    # List of column names to check for null or empty values
    columns_check = [TITLE, DESCRIPTION,
                     INTERACTION_MODE, EMAIL_ADDRESS_LIST, TEST_TYPE, SCENARIO_CASE]

    access_token = login_slack(email, password, subdomain_prefix)

    if access_token:
        logger.info("Login successful")
        valid_rows = []
        response = None

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

            # Checkoing for empty KLS and KLP and questions
            for row_data in all_rows:
                for key in row_data:
                    if key.startswith(QUESTION):
                        if not row_data[key] and (IS_IMMERSIVE not in row_data or row_data[IS_IMMERSIVE].lower() == "false" or len(row_data[IS_IMMERSIVE]) == 0):
                            raise Exception(
                                f"Column '{key}' has null or empty value in row")
                    if key.startswith(KLS) or key.startswith(KLP):
                        if not row_data[key]:
                            raise Exception(
                                f"Column '{key}' has null or empty value in row")

                # If row is valid, append it to list of valid rows to be sent to API
                valid_rows.append(row_data)

            logger.info(f"Total valid records: {len(valid_rows)}")

            test_name_test_code_map = {}
            cnt = 1
            record_created = 0

            # Call the API for all valid rows
            for row_data in valid_rows:
                # logger.info(row_data)
                raw_data = json.dumps(row_data)
                # Format the data as per the API requirements
                # Sending the creator_id as a parameter change it later
                json_data, check_pass = format_test_data_slack(raw_data)
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
                        test_name_test_code_map[f"Test {cnt}: {row_data[TITLE]}"
                                                ] = response.json().get('test_code')
                        row_data = json.dumps(row_data)

                        cnt += 1
                        record_created += 1

                    except Exception as e:
                        logger.error(e)
                        return {
                            "errors": [f"Error occurred; Could not create tests {e.args}"],
                            "exception": True,
                            "response": response
                        }

                    # Check for successful API call
                    if response.status_code != 201:
                        raise Exception("API call failed")

                else:
                    if "unmatched_skills" in json_data:
                        return {
                            "errors": [f"csv file contains Mismatching skills in test {json_data['Title']}: {', '.join(json_data['unmatched_skills'])}"],
                            "exception": True,
                        }
                        
                    test_name_test_code_map[f"Test {cnt}: {row_data[TITLE]}"
                                            ] = "Not Created For This Title"
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

            return {
                "success": True,
                "message": "Test created successfully",
                'errors': [],
                'file_response': file_response,
            }

        except Exception as e:
            logger.error(e)
            return {
                "errors": [f"Error occurred; Could not create tests {e.args}"],
                "exception": True,
            }
    else:
        return {
            "errors": ["Invalid credentials"],
            "exception": True,
        }


def create_test_orchestrated_conversation_slack(csv_file, email, password, subdomain_prefix):

    logger.info(subdomain_prefix)
    # List of column names to check for null or empty values
    columns_check = ['Title', 'Context', EMAIL_ADDRESS_LIST,
                     SCENARIO_CASE]

    access_token = login_slack(email, password, subdomain_prefix)

    if access_token:
        logger.info("Login successful")
        valid_rows = []
        response = None

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

            test_name_test_code_map = {}
            cnt = 1
            record_created = 0
            # Call the API for all valid rows
            for row_data in valid_rows:

                # logger.info(row_data)
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
                        test_name_test_code_map[f"Test {cnt}: {row_data[TITLE]}"
                                                ] = response.json().get('test_code')
                        row_data = json.dumps(row_data)

                        cnt += 1
                        record_created += 1

                    except Exception as e:
                        logger.exception(e)
                        return {
                            "errors": [f"Error occurred; Could not create tests {e.args}"],
                            "exception": True,
                            "response": response
                        }

                    # Check for successful API call
                    if response.status_code != 201:
                        raise Exception("API call failed")
                else:
                    if "last_question_for_user" in json_data:
                        return {
                            "errors": [json_data['last_question_for_user']],
                            "exception": True,
                        }
                    elif "error" in json_data:
                        return {
                            "errors": [json_data["error"]],
                            "exception": True,
                        }
                    test_name_test_code_map[f"Test {cnt}: {row_data[TITLE]}"
                                            ] = "Not Created For This Title"
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

            return {
                "success": True,
                "message": "Test created successfully",
                'errors': [],
                'file_response': file_response,
            }

        except Exception as e:
            logger.error(e)
            return {
                "errors": [f"Error occurred; Could not create tests {e.args}"],
                "exception": True,
            }
    else:
        return {
            "errors": ["Invalid credentials"],
            "exception": True,
        }
