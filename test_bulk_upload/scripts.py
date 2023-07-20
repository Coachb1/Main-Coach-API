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
import ast

load_dotenv()
logger = logging.getLogger(__name__)

# API endpoint URL move to env
API_ENDPOINT_LOGIN_WEB = os.getenv("API_ENDPOINT_LOGIN_WEB")
API_ENDPOINT_WEB = os.getenv("API_ENDPOINT_WEB")
API_ENDPOINT_SLACK = "http://coachbots-api-lb-1912727967.ap-south-1.elb.amazonaws.com/api/v1/tests/"
API_ENDPOINT_LOGIN_SLACK = os.getenv("API_ENDPOINT_LOGIN_SLACK")
LOCALHOST = "http://localhost:8000/api/v1/tests/"

# CONSTANTS
COURSE = "Course"  # not using as not implemented in backend
SOURCE = "Source"  # not using as not implemented in backend
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


def format_test_orchestrated_conversation(raw_data):
    try:
        input_dict = json.loads(raw_data)

        output_dict = {
            "creator_id": None,
            "title": input_dict['Title'],
            "description": input_dict['Context'],
            "interaction_mode": "text",
            "email_candidate" : True,
            "test_type": "orchestrated_conversation",
            "description_media": input_dict.get(DESCRIPTION_MEDIA, None),
            "gpt_prompt_override": "",
            "questions": [],
            "is_checkin_type": input_dict[IS_CHECKIN_TYPE],
            "skills_to_evaluate": input_dict[SKILLS_TO_EVALUATE]
        }

        bot_count = sum(1 for key in input_dict.keys() if key.startswith('Person'))
        if bot_count == 1:
            output_dict["is_single_bot"] = True

        if input_dict[EMAIL_ADDRESS_LIST] and len(input_dict[EMAIL_ADDRESS_LIST].strip()) > 0:

            email_list = input_dict[EMAIL_ADDRESS_LIST].split(',')
            email_list = [email.strip() for email in email_list]
            email_list = ','.join(email_list)

            output_dict['email_address_list'] = email_list

        initial_messages = []
        test_main_context = input_dict['Context']
        persons = []

        for key in input_dict:
            if key.startswith('Person'):
                name = input_dict[key].split(':')[0].strip()
                persons.append(name)
                initial_messages.append(input_dict[key])
                test_main_context += input_dict[key]
        

        orchestrated_conversation_details ={
            "test_main_context": test_main_context ,
            "test_user_persona": "Manager",
            "objective": input_dict['Context'],
            "initial_messages": initial_messages 
        }
        output_dict['orchestrated_conversation_details'] = orchestrated_conversation_details

        
        for key in input_dict:
            if key.isdigit():
                question = {
                    "question": input_dict[key],
                    "question_type": "subjective",
                    "gpt_prompt_override": "",
                    "subjective_answer": ""        
                 }
                if "Respond as a manager" in input_dict[key]:
                    question['question_for'] = "user"

                else:
                    for name in persons:
                        if name.split()[0].lower() in input_dict[key].lower():
                            question['question_for'] = name
                            break

                output_dict["questions"].append(question)

        output_json = json.dumps(output_dict)

        return output_json

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
            "description_media": input_dict.get(DESCRIPTION_MEDIA, None),
            "gpt_prompt_override": "",
            "questions": [],
            "is_checkin_type": input_dict[IS_CHECKIN_TYPE]
        }

        test_type = input_dict[TEST_TYPE].strip().lower()
        skills_list = set()
        for key in input_dict:
            if key.startswith(KLS):
                temp_skills = input_dict[key].split(',')
                for skill in temp_skills:
                    skills_list.add(skill.strip().capitalize())
        output_dict[SKILLS_TO_EVALUATE] = list(skills_list)

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
   
        if input_dict[MAX_TEST_ALLOWED] and len(input_dict[MAX_TEST_ALLOWED].strip()) > 0 :
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
                    "key_learning_skills": input_dict.get(f"{KLS} {key[len(QUESTION) + 1:]}", None)
                }

                if test_type == "view":
                    question['is_view_only'] = True
                elif test_type == "single":
                    question['is_view_only'] = True

                output_dict["questions"].append(question)

        if test_type == 'single' and len(output_dict["questions"]) > 1:
            output_dict["questions"][-1]["is_view_only"] = False

        output_json = json.dumps(output_dict)

        return output_json

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
        # url = "http://coachbots-api-lb-1912727967.ap-south-1.elb.amazonaws.com/api/v1/webauth/login/"
        url = "http://localhost:8000/api/v1/webauth/login/"

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
                     INTERACTION_MODE, EMAIL_ADDRESS_LIST, TEST_TYPE]

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
            check_pass = False
            record_created = 0

            # Call the API for all valid rows
            for row_data in valid_rows:

                skills_list = set()
                for key in row_data:
                    if key.startswith(KLS):
                        temp_skills = row_data[key].split(',')
                        for skill in temp_skills:
                            skills_list.add(skill.strip().capitalize())
                skills_list = list(skills_list)

                if row_data[IS_CHECKIN_TYPE] == 'TRUE':
                    candidate_type = row_data[CANDIDATE_TYPE]
                    if not candidate_type:
                        candidate_type = 'Manager'
                    skills_list_candidate = set()
                    for item in get_skills(candidate_type):
                        skills_list_candidate.add(item.capitalize())
                    skills_list_candidate = list(skills_list_candidate)
                    if sorted(skills_list_candidate) == sorted(skills_list):
                        check_pass = True

                if check_pass:
                    # logger.info(row_data)
                    raw_data = json.dumps(row_data)
                    # Format the data as per the API requirements
                    # Sending the creator_id as a parameter change it later
                    json_data = format_test_data_slack(raw_data)
                    # logger.info(json_data)
                    # Calling the Test creation API with JSON data

                    
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
                            "errors": [f"Error occurred; Could not create tests"],
                            "exception": True,
                            "response": response
                        }

                    # Check for successful API call
                    if response.status_code != 201:
                        raise Exception("API call failed")
                    
                else:
                    test_name_test_code_map[f"Test {cnt}: {row_data[TITLE]}"
                                                    ] = "Not Created For This Title"
                    cnt+=1

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
                "errors": [f"Error occurred; Could not create tests"],
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
    columns_check = ['Title', 'Context', EMAIL_ADDRESS_LIST]

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
                check_pass = False

                
                skills_list = ast.literal_eval(row_data[SKILLS_TO_EVALUATE])

                if row_data[IS_CHECKIN_TYPE] == 'TRUE':
                    candidate_type = row_data[CANDIDATE_TYPE]
                    if not candidate_type:
                        candidate_type = 'Manager'
                    skills_list_candidate = set()
                    for item in get_skills(candidate_type):
                        skills_list_candidate.add(item.capitalize())
                    skills_list_candidate = list(skills_list_candidate)
        
                    if sorted(skills_list_candidate) == sorted(skills_list):
                        check_pass = True
                
                if check_pass:
                    # logger.info(row_data)
                    raw_data = json.dumps(row_data)
                    # Format the data as per the API requirements
                    # Sending the creator_id as a parameter change it later
                    json_data = format_test_orchestrated_conversation(raw_data)
                    
                    # logger.info(json_data)
                    # Calling the Test creation API with JSON data
                    try:

                        headers = {
                            'Content-Type': 'application/json',
                            'Authorization': f'Bearer {access_token}'
                        }

                        logger.info("[Making Request]")

                        response = requests.post(
                            LOCALHOST, data=json_data, headers=headers, verify=False)

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
                            "errors": [f"Error occurred; Could not create tests"],
                            "exception": True,
                            "response": response
                        }

                    # Check for successful API call
                    if response.status_code != 201:
                        raise Exception("API call failed")
                else:
                    test_name_test_code_map[f"Test {cnt}: {row_data[TITLE]}"
                                                    ] = "Not Created For This Title"
                    cnt+=1
                    

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
                "errors": [f"Error occurred; Could not create tests"],
                "exception": True,
            }
    else:
        return {
            "errors": ["Invalid credentials"],
            "exception": True,
        }
