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
MEDIA_LINK = 'ML'
CLIENT = "Client Name"
START_WITH_USER = "start with user"



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
            "gpt_prompt_override": "",
            "questions": [],
        }

        if IS_DYNAMIC in input_dict:
            if input_dict[IS_DYNAMIC] and len(input_dict[IS_DYNAMIC].strip()) > 0:
                is_dynamic = input_dict[IS_DYNAMIC].strip().lower()

                if is_dynamic == "true":
                    output_dict["test_type"] = TestTypeChoices.dynamic_discussion
                    output_dict["interaction_mode"] = 'audio'
                    
        if CLIENT in input_dict:
            if input_dict[CLIENT] and len(input_dict[CLIENT].strip()) > 0 :
                output_dict['client_name'] = input_dict[CLIENT].strip().capitalize()


        if IS_GAME_TYPE in input_dict:
            if input_dict[IS_GAME_TYPE] and len(input_dict[IS_GAME_TYPE].strip()) > 0:
                is_game_type = input_dict[IS_GAME_TYPE].strip().lower()

                if is_game_type == "true":
                    output_dict['is_game_type'] = True
                elif is_game_type == "false":
                    output_dict['is_game_type'] = False
                else:
                    output_dict['is_game_type'] = False
        
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
            "gpt_prompt_override": "",
            "questions": []
        }

        if IS_GAME_TYPE in input_dict:
            if input_dict[IS_GAME_TYPE] and len(input_dict[IS_GAME_TYPE].strip()) > 0:
                is_game_type = input_dict[IS_GAME_TYPE].strip().lower()

                if is_game_type == "true":
                    output_dict['is_game_type'] = True
                elif is_game_type == "false":
                    output_dict['is_game_type'] = False
                else:
                    output_dict['is_game_type'] = False

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
        skills_list = list(skills_list)

        defined_skills_list = [ skill['name'].strip().capitalize() for skill in pre_defined_skills ]

        unmatched_skills = []
        for skills in skills_list:
            if skills not in defined_skills_list:
                unmatched_skills.append(skills)

        if len(unmatched_skills) > 0:
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
                    "media_link" : input_dict.get(f"{MEDIA_LINK} {key[len(QUESTION) + 1:]}", '')

                }

                if test_type == "view":
                    question['is_view_only'] = True
                elif test_type == "single":
                    question['is_view_only'] = True

                output_dict["questions"].append(question)

        if test_type == 'single' and len(output_dict["questions"]) > 1:
            output_dict["questions"][-1]["is_view_only"] = False

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
                        if not row_data[key]:
                            raise Exception(
                                f"Column '{key}' has null or empty value in row")
                    elif key.startswith(KLS) or key.startswith(KLP):
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
