import json
import random
import time
import logging

from django.utils.text import slugify

from commons.anthropic import anthropic_completion
from commons.openai_gpt import gpt3_completion
from external_apis.slack_alert_api import send_slack_message
from identities.models import Identity
from skills.choices import CultureMapSkillTypeChoices
from skills.models import CultureMapSkill, SkillsRating, SkillIndex, CompetencySkillAndClientMapping
from tests.models import TestAttemptSession
from users.db import get_user_display_name
from users.models import User
import re
from commons.google_apis import text_bison_compeletion, gemini_completion
from commons.timeit import timeit
from nltk.stem import PorterStemmer
import os
from pathlib import Path
import pandas as pd
from string import Template
import json5
from tests.choices import TestAttemptSessionStatusChoices, TestTypeChoices, ScenarioCaseChoices




logger = logging.getLogger(__name__)


def is_skill_matched(skill_list, rating_list):
    """ This function is_skill_matched checks if all elements in the rating_list are present in the skill_list.

    The function first normalizes both lists by stripping leading/trailing whitespaces and converting all elements to lowercase. If all elements of rating_list are found in skill_list, the function returns True.

    If not all elements are found, the function applies the Porter Stemming algorithm to reduce all words in both lists to their root form. This is done to account for different forms of the same word (e.g., 'running' and 'runner' both stem to 'run').

    The function then checks again if all stemmed elements of rating_list are found in the stemmed skill_list. If they are, the function returns True, otherwise it returns False.

    Parameters:

    skill_list (list of str): The list of skills. Each element should be a string representing a skill.
    rating_list (list of str): The list of ratings. Each element should be a string representing a rating.
    Returns:

    bool: True if all elements in rating_list are found in skill_list (either in their original or stemmed form), False otherwise.
    Example:

    >>> is_skill_matched(['Running', 'Jumping'], ['run', 'jump'])
    True
    >>> is_skill_matched(['Running', 'Jumping'], ['run', 'swim'])
    False

    """
    # Initialize the Porter Stemmer
    skill_list = [element.strip().lower() for element in skill_list]
    rating_list = [element.strip().lower() for element in rating_list]
    if all(element in skill_list for element in rating_list):
        return True
    else:
        stemmer = PorterStemmer()

        # Get the root word for each element in the skills_list
        root_skill_list = [stemmer.stem(skill.lower()) for skill in skill_list]
        root_rating_list = [stemmer.stem(skill.lower()) for skill in rating_list]
        logger.info(f"root word ratings : {root_rating_list}")
        logger.info(f"root word ratings : {root_rating_list}")

        # Check if any rating stems do not match any of the skills stems
        if any(rat not in root_skill_list for rat in root_rating_list):
            return False
        else:
            return True


def split_skills_string(str):
    mydata = str.split('}')
    skills_rating_str = mydata[0] + '}'
    skills_rating_str = '{' + skills_rating_str.split('{')[1] 
    skills_explanation_str = mydata[1] 

    return skills_rating_str, skills_explanation_str


def to_dict(string, skills = None):
    try:
        data = {}
        for line in string.strip().split("\n"):
            if len(line.strip()) == 0:
                continue
            key, val = line.strip('- ').split(':')
            if len(key.strip()) == 0 or len(val.strip()) == 0:
                continue
            data[key.strip()] = val.strip()
        # return json.dumps(data, indent=4)
        return data
    except Exception as e:
        logger.error({"!!!!!to_dict ":"failed to convert to json","error":e,"*****alternate":"mapping skills to explanation"})
        if skills:
            try:
                for key,val in zip(skills.keys(),string.strip().split("\n\n")):
                    data[key] = val.strip('- ')
                return data
            except Exception as e:
                logger.error({"!!!!! failed to map skills to explanation ":e})
                raise e
    return None
    
def json_extraction_for_competency(text):
    """ This function, json_extraction_for_competency, is designed to extract a JSON object from a given text string.

    The function works by identifying the first and last occurrence of the curly braces { and } which are typically used to denote the start and end of a JSON object.

    The function takes one argument:

    text (str): The input string from which the JSON object is to be extracted. This string should contain a JSON object.
    The function begins by finding the index of the first occurrence of { and the last occurrence of } in the text. If both are found, it slices the text from the start index to the end index (inclusive) to extract the JSON object.

    If a JSON object is successfully extracted, the function logs the extracted JSON and returns it. If no JSON object is found, the function logs an error message and returns the original text.

    Expected output:

    If a JSON object is found, it returns the JSON object as a string.
    If no JSON object is found, it returns the original text.
    Example: text = "Hello, this is a sample text with a JSON {"key": "value"} inside it." output = json_extraction_for_competency(text) print(output) # Outputs: "{"key": "value"}" """

    start_index = text.find('{')
    end_index = text.rfind('}')

    if start_index != -1 and end_index != -1:
        text = text[start_index: end_index+1]
    
    if start_index and end_index:
        logger.info({'json': text})

        return text
    else:
        logger.error('no json found')
        return text
    

def parse_json5(json5_string):
    """
    Parses a JSON5 string and returns a Python dictionary.
    
    :param json5_string: The JSON5 formatted string to be parsed.
    :return: A Python dictionary representing the JSON5 data.
    """
    try:
        # Parse the JSON5 string
        json_object = json5.loads(json5_string)
        return json_object
    except Exception as e:
        print(f"Failed to parse JSON5 string: {e}")
        raise e
    
def json_extraction(text):
    # Improved regex pattern to match JSON objects
    pattern = r'\{(?:[^{}]|(?:\{.*?\}))*\}'

    # Use re.findall to find all JSON portions in the text
    matches = re.findall(pattern, text)

    if matches:
        for match in matches:
            try:
                # Attempt to parse each found JSON string
                json_data = parse_json5(match)
                logger.info({"json": json_data})
                return json.dumps(json_data)
            except Exception as e:
                logger.error({"error": str(e), "invalid_json": match})
                continue
        logger.info({"message": "valid json not found", "text": text})
        return text
    else:
        logger.info({"message": "json not found", "text": text})
        return text


def json_extractor_for_explaination(text):
    
    # Define a regex pattern to match JSON objects
    pattern = r'\{.*?\}'

    # Find all matches of JSON objects in the text
    json_objects = re.findall(pattern, text, re.DOTALL)

    # Initialize a list to store parsed JSON objects
    parsed_json_list = []
    updated_json = {}

    # Iterate through the found JSON objects and parse them
    for json_str in json_objects:
        try:
            parsed_json = json.loads(json_str)
            parsed_json_list.append(parsed_json)
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON: {str(e)}")
            raise e

    # Print the list of parsed JSON objects
    for parsed_json in parsed_json_list:
        for key, value in parsed_json.items():
            updated_json[key] = value

    return updated_json
        


@timeit
def evaluate_response(test_question_response, question_text, response_text, skills, test_description, test_title, test_code, session_id):
    """
    calculates skills_rating for a question.
    """
    # prompt = f'''
    # "TITLE:" {test_title};

    # "DESCRIPTION:" {test_description};

    # "QUESTION:" {question_text}; 
    
    # "ANSWER:" {response_text};

    # "Evaluation Criteria:"
    # - Relevance: Does the answer directly address the question?
    # - Accuracy: Is the information in the answer correct?
    # - Completeness: Does the answer provide a comprehensive response to the question?
    # - Clarity: Is the answer well-written and easy to understand?

    # "REQUIRED FROM LLM:" Based on the above criteria please evaluate the given answer on a scale of 0-10, with scores in increments of 0.5 for each skill in the list in JSON: "{skills}".
    
    # NOTE: Please put properties of JSON enclosed in double quotes.

    # NOTE: Please Reply in a valid JSON format only and no other format will be accepted.

    # NOTE: Don't put any other text in the reply other than the JSON. The keys in json object must be taken from {skills} only.

    # NOTE: Output Format Example: {{"skill1": "4.5", "skill2": "10", "skill3": "2.5"}}
    # '''

    prompt = f'''
    \n\nHuman:
    "TITLE:" {test_title};

    "DESCRIPTION:" {test_description};

    "QUESTION:" {question_text}; 
    
    "ANSWER:" {response_text};

    "Evaluation Criteria:"
    - Relevance: Does the answer directly address the question?
    - Accuracy: Is the information in the answer correct?
    - Completeness: Does the answer provide a comprehensive response to the question?
    - Clarity: Is the answer well-written and easy to understand?

    "REQUIRED FROM LLM:" Based on the above criteria please evaluate the given conversation i.e. all answers on a scale of 1-9, with scores in increments of 0.5 for each skill in the list in JSON: "{skills}" in such a way that no two skills can have the exact same score. 

    NOTE: Please put properties of JSON enclosed in double quotes.

    NOTE: Please Reply in a valid JSON format only and no other format will be accepted.

    NOTE: Don't put any other text in the reply other than the JSON. The keys in json object must be taken from {skills} only.

    NOTE: Check if the responses provided are somewhat relevant to the conversation or completely irrelevant. If the responses are irrelevant put "relevance" 0 otherwise 1.

    NOTE: Output Format Example: {{"skill1": "4.5", "skill2": "9", "skill3": "2.5","relevance":"1"}}

    NOTE:  For the entire question and answer conversation no two skills from {skills} can have exact same scores.

    NOTE: Do not add any English language sentence in the output.
    \n\nAssistant:

'''

    is_evaluated = True
    response = None

    max_tries = 3  # because anthropic_completion function itself retries 3 times

    while max_tries > 0:
        try:
            logger.info({"****evaluate_response ":f"trying [outer] anthropic for {1 - max_tries + 1} time"})
            response = anthropic_completion(prompt, len(skills) * 50)
            logger.info({"****evaluate_response ":f"response [outer] anthropic for {1 - max_tries + 1} time","response":response})
            response = json_extraction(response)
            response = parse_json5(response)
            for skill in response:
                response[skill] = float(response[skill])
            break
        except Exception as e:
            logger.error({"****evaluate_response ":f"failed [outer] anthropic for {1 - max_tries + 1} time","error":e})
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return response, is_evaluated

    logger.info({"****evaluate_response ":f"failed anthropic, so trying gpt"})

    is_evaluated = True
    response = None
    max_tries = 3  # because gpt3_completion function itself retries 3 times

    while max_tries > 0:
        try:
            logger.info({"****evaluate_response ":f"trying [outer] gpt for {3 - max_tries + 1} time"})
            response = gpt3_completion(prompt, stop=["USER:", "CoachBot"]).text
            logger.info({"****evaluate_response ":f"response [outer] gpt for {3 - max_tries + 1} time","response":response})
            response = json_extraction(response)
            if '"REPLY:"' in response:
                response = response.split('"REPLY:"')[1].strip()
            elif '"ANSWER:"' in response:
                response = response.split('"ANSWER:"')[1].strip()
            elif '"Anthropic Answer:"' in response:
                response = response.split('"Anthropic Answer:"')[1].strip()

            response = parse_json5(response)
            
            for skill in response:
                response[skill] = float(response[skill])

            break

        except Exception as e:
            logger.error({"****evaluate_response_skill ":f"failed [outer] gpt for {3 - max_tries + 1} time","error":e })
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue


    if is_evaluated:
        return response, is_evaluated

    # HACK in case everything fails; just evaluate as a random number
    logger.info({"****evaluate_response ":f"failed everything, so assigning default values"})
    response = {}
    for skill in skills:
        response[skill] = random.randint(3, 7)

    # send error on slack to debug this
    send_slack_message({"process": "evaluate_response",
                        "test_question_response": test_question_response.uid,
                        "error": "failed to evaluate; putting random value"})

    return response, True


@timeit
def evaluate_relevacy(test_question_response, question_text, response_text,test_description, test_title,is_free=False):
    """
    It evalutes relevancy of a Question and Answer.
    """
    prompt = f'''
    \n\nHuman:
    "TITLE:" {test_title};

    "DESCRIPTION:" {test_description};

    "QUESTION:" {question_text};

    "ANSWER:" {response_text};

    "REQUIRED FROM LLM:" Please check whether the answer provided is even slightly related to the question asked and the description provided. Assign a relevancy score between 0 to 10, 10 being highly relevant response and 0 being completely irrelevant response. ONLY when the entire answer is completely random and unrelated to the question and description give the relevancy score value as 0.
    NOTE: Please Reply in a valid JSON format only and no other format will be accepted.

    NOTE: Don't put any other text in the reply other than the JSON.

    NOTE: Output Format Example: {{"relevance":{int("1")}}}

    NOTE: Do not add any other sentence, information or explanation in the output. Only provide the output in the format given above.
    \n\nAssistant:
    '''


    if is_free:
         ##################* anthropic ###################
        is_evaluated = True
        response = None

        max_tries = 3  # because anthropic_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****evaluate_relevacy ":f"trying [outer] anthropic for {1 - max_tries + 1} time"})
                response = anthropic_completion(prompt, 100)
                logger.info({"****evaluate_relevacy ":f"response [outer] anthropic for {1 - max_tries + 1} time","response":response})
                response = json_extraction(response)
                response = parse_json5(response)
                for skill in response:
                    if int(response[skill]) == 0:
                        response[skill] = 0
                    else:
                        response[skill] = 1

                break
            except Exception as e:
                logger.error({"****evaluate_relevacy ":f"failed [outer] anthropic for {1 - max_tries + 1} time","error":e})
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue

        if is_evaluated:
            return response, is_evaluated
        else:
            return {"relevance": 1}, True
        
    else:
        

        ##################* gemini_completion ###################

        is_evaluated = True
        response = None
        max_tries = 3

        while max_tries > 0:
            try:
                logger.info({"****evaluate_relevacy ":f"trying [outer]  gemini_completion for  {3 - max_tries + 1} time"})
                response = gemini_completion(prompt)
                logger.info({"****evaluate_relevacy ":f"response [outer] gemini_completion for {3 - max_tries + 1} time","response":response})
                response = json_extraction(response)
                response = parse_json5(response)
                
                for skill in response:
                    if int(response[skill]) == 0:
                        response[skill] = 0
                    else:
                        response[skill] = 1

                break

            except Exception as e:
                logger.error({"****evaluate_relevacy ":f"failed [outer] gemini_completion for {3 - max_tries + 1} time","error":e })
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return response, is_evaluated


        ##################* gemini_completion ###################
        
        logger.info({"****evaluate_relevacy ":f"failed  gemini_completion, so trying anthropic_completion"})

        ##################* anthropic ###################
        is_evaluated = True
        response = None

        max_tries = 3  # because anthropic_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****evaluate_relevacy ":f"trying [outer] anthropic for {1 - max_tries + 1} time"})
                response = anthropic_completion(prompt, 100)
                logger.info({"****evaluate_relevacy ":f"response [outer] anthropic for {1 - max_tries + 1} time","response":response})
                response = json_extraction(response)
                response = parse_json5(response)
                for skill in response:
                    if int(response[skill]) == 0:
                        response[skill] = 0
                    else:
                        response[skill] = 1
                break
            except Exception as e:
                logger.error({"****evaluate_relevacy ":f"failed [outer] anthropic for {1 - max_tries + 1} time","error":e})
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue

        if is_evaluated:
            return response, is_evaluated

        ##################* anthropic ###################

        logger.info({"****evaluate_relevacy ":f"failed anthropic, so trying gpt_compeletion"})

        ##################* gpt ###################
        is_evaluated = True
        response = None
        max_tries = 3  # because gpt3_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****evaluate_relevacy ":f"trying [outer] gpt for {3 - max_tries + 1} time"})
                response = gpt3_completion(prompt, stop=["USER:", "CoachBot"]).text
                logger.info({"****evaluate_relevacy ":f"response [outer] gpt for {3 - max_tries + 1} time","response":response})
                response = json_extraction(response)
                response = parse_json5(response)
                
                for skill in response:
                    if int(response[skill]) == 0:
                        response[skill] = 0
                    else:
                        response[skill] = 1

                break

            except Exception as e:
                logger.error({"****evaluate_relevacy ":f"failed [outer] gpt for {3 - max_tries + 1} time","error":e })
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue

        if is_evaluated:
            return response, is_evaluated

        ##################* gpt ###################


        # HACK in case everything fails; just evaluate as a random number
        logger.info({"****evaluate_relevacy ":f"failed everything, so assigning default values"})
        response = {"relevance": 1}
        

        # send error on slack to debug this
        send_slack_message({"process": "evaluate_relevacy",
                            "test_question_response": test_question_response.uid,
                            "error": "failed to evaluate; putting random value"})

        return response, True

def get_competency_prompt_or_output(skills,is_prompt_only=False):
    """
    It fetches prompt based on competency.
    """
    os.chdir(f"{Path(__file__).resolve().parent}")
    df = pd.read_csv(r"prompts - Competency prompts.csv")
    prompts_str = ""
    outputs_dict = {}
    skills = [skill.lower().strip() for skill in skills]

    # Iterate through the rows and extract prompts and outputs based on provided skills
    for index, row in df.iterrows():
        competency_skill = row['Competency skill'].lower().strip()
        prompts = row['Prompts']
        output = row['Output']

        # Check if the competency skill is in the provided skills list
        if competency_skill in skills:
            prompts_str +=  f"{prompts}\n"
            output = output.split("\n")[1:]
            output_dict = {}
            for out in output:
                level = out.split("-")[0].strip().lower()
                desc = out.split("-")[1].strip()
                output_dict[level] = {"description":desc}
            outputs_dict[competency_skill] = output_dict

    if is_prompt_only:
        return prompts_str
    else:
        return outputs_dict


def get_competency_prompt_or_output_via_db(skills,is_prompt_only=False):
    """
    It fetches prompt based on competency.
    """
    prompts_str = ""
    outputs_dict = {}
    skills = [skill.lower().strip() for skill in skills]

    competency_prompts = CompetencySkillAndClientMapping.objects.all()

    # Iterate through the queryset and extract prompts and outputs based on provided skills
    for cp in competency_prompts:
        competency_skill = cp.competency_skill.lower().strip()
        prompts = cp.prompts
        output = cp.output

        # Check if the competency skill is in the provided skills list
        if competency_skill in skills:
            prompts_str += f"{prompts}\n"
            output_lines = output.split("\n")[1:]
            output_dict = {}
            for out in output_lines:
                level, desc = out.split("-", 1)
                output_dict[level.strip().lower()] = {"description": desc.strip()}
            outputs_dict[competency_skill] = output_dict

    if is_prompt_only:
        return prompts_str
    else:
        return outputs_dict

def validate_skills(skills):
    for skill, values in skills.items():
        try:
            level = int(values.get("level"))
            rating = int(values.get("rating"))
        except Exception as e:
            raise e

        # Check if level is between 1 and 3
        if not (0 <= level <= 3):
            raise ValueError(f"Invalid level {level} for {skill}. Level must be between 1 and 3.")
        
        # # Check if rating is between 1 and 10
        # if not (1 <= rating <= 10):
        #     raise ValueError(f"Invalid rating {rating} for {skill}. Rating must be between 1 and 10.")
    
    return True

@timeit
def evaluate_competency_data(description, conversation,test_attempt_session,skills,is_free=False):
    """
Evaluates the competency data based on the provided description, conversation, test attempt session, and skills.

This function generates a prompt based on the provided description, conversation, and skills. It then attempts to evaluate the competency data using various APIs (anthropic, gemini_completion, gpt3_completion) in a specific order until it succeeds or exhausts all options. If all attempts fail, it assigns a default value to the response.

Args:
    description (str): The description of the competency.
    conversation (str): The conversation related to the competency.
    test_attempt_session (obj): The test attempt session object.
    skills (list): A list of skills to be evaluated.
    is_free (bool, optional): A flag to determine if the evaluation should be free or not. Defaults to False.

Returns:
    tuple: A tuple containing the response and a boolean indicating if the evaluation was successful. The response is a dictionary where each key is a skill and the value is another dictionary with 'rating' and 'level' as keys. If the evaluation was not successful, the response will be a default value.

Example:
    >>> evaluate_competency_data("description", "conversation", test_attempt_session, ["skill1", "skill2"])
    ({"skill1": {"rating": "8", "level": "3"}, "skill2": {"rating": "6", "level": "2"}}, True)

Raises:
    Exception: If all attempts to evaluate the competency data fail.
"""
    
    competency_prompt = get_competency_prompt_or_output_via_db(skills=skills,is_prompt_only=True)

    prompt = """
        "DESCRIPTION:" ${discription};

        "CONVERSATION:" ${conversation};
        "Evaluation Criteria:"

        ${competency_prompts}

        "Required from LLM:" Based on the above criteria please evaluate the given conversation i.e. all answers on a scale of 1-9. Rate the skills only from a scale of 1-9. For the given responses assign a level to the skills based on the given criteria for each level of each skill. Evaluate the responses to see which of the given levels resonates most closely  to the given responses for each skill. 
        If any of the skill is not related to the given conversation, rate that skills as 0. Only when the skill is not even slightly related to the conversation give the rating as 0.

        "competency_list:" "${competency_list}"

        NOTE: Please put properties of JSON enclosed in double quotes.

        Example of JSON: {"Communication Skills": {"rating": "8", "level": "3"}, "Teamwork": {"rating": "6", "level": "2"}, "Planning and Organizing": {"rating": "7", "level": "1"}, "Achievement Focus": {"rating": "8", "level": "2"}, "Analytical Thinking": {"rating": "7", "level": "1"}}

        NOTE : Do not provide any kind of heading or introduction text in the output.

        NOTE: Do not add any English language sentence in the output.


    """
    prompt = Template(prompt).substitute(
        discription=description,
        conversation=conversation,
        competency_prompts=competency_prompt,
        competency_list=skills,
    )

    default_value = {"Communication Skills": {"rating": "3", "level": "2"},"Teamwork": {"rating": "2", "level": "1"},"Planning and Organizing": {"rating": "3", "level": "2"},"Client Focus": {"rating": "4", "level": "1"},}

    if is_free:
         ##################* anthropic ###################
        is_evaluated = True
        response = None

        max_tries = 3  # because anthropic_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****evaluate_competency_data ":f"trying [outer] anthropic for {1 - max_tries + 1} time"})
                response = anthropic_completion(prompt, 100)
                logger.info({"****evaluate_competency_data ":f"response [outer] anthropic for {1 - max_tries + 1} time","response":response})
                response = json_extraction_for_competency(response)
                response = parse_json5(response)

                validate_skills(response)
                

                break
            except Exception as e:
                logger.error({"****evaluate_competency_data ":f"failed [outer] anthropic for {1 - max_tries + 1} time","error":e})
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue

        if is_evaluated:
            return response, is_evaluated
        else:
            return default_value, True
        
    else:
        

        ##################* gemini_completion ###################

        is_evaluated = True
        response = None
        max_tries = 3

        while max_tries > 0:
            try:
                logger.info({"****evaluate_competency_data ":f"trying [outer]  gemini_completion for  {3 - max_tries + 1} time"})
                response = gemini_completion(prompt)
                logger.info({"****evaluate_competency_data ":f"response [outer] gemini_completion for {3 - max_tries + 1} time","response":response})
                response = json_extraction_for_competency(response)
                response = parse_json5(response)
                
                validate_skills(response)

                break

            except Exception as e:
                logger.error({"****evaluate_competency_data ":f"failed [outer] gemini_completion for {3 - max_tries + 1} time","error":e })
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return response, is_evaluated


        ##################* gemini_completion ###################
        
        logger.info({"****evaluate_competency_data ":f"failed  gemini_completion, so trying anthropic_completion"})

        ##################* anthropic ###################
        is_evaluated = True
        response = None

        max_tries = 3  # because anthropic_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****evaluate_competency_data ":f"trying [outer] anthropic for {1 - max_tries + 1} time"})
                response = anthropic_completion(prompt, 100)
                logger.info({"****evaluate_competency_data ":f"response [outer] anthropic for {1 - max_tries + 1} time","response":response})
                response = json_extraction_for_competency(response)
                response = parse_json5(response)
                
                validate_skills(response)
                break
            except Exception as e:
                logger.error({"****evaluate_competency_data ":f"failed [outer] anthropic for {1 - max_tries + 1} time","error":e})
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue

        if is_evaluated:
            return response, is_evaluated

        ##################* anthropic ###################

        logger.info({"****evaluate_competency_data ":f"failed anthropic, so trying gpt_compeletion"})

        ##################* gpt ###################
        is_evaluated = True
        response = None
        max_tries = 3  # because gpt3_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****evaluate_competency_data ":f"trying [outer] gpt for {3 - max_tries + 1} time"})
                response = gpt3_completion(prompt, stop=["USER:", "CoachBot"]).text
                logger.info({"****evaluate_competency_data ":f"response [outer] gpt for {3 - max_tries + 1} time","response":response})
                response = json_extraction_for_competency(response)
                response = parse_json5(response)
                
                validate_skills(response)

                break

            except Exception as e:
                logger.error({"****evaluate_competency_data ":f"failed [outer] gpt for {3 - max_tries + 1} time","error":e })
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue

        if is_evaluated:
            return response, is_evaluated

        ##################* gpt ###################


        # HACK in case everything fails; just evaluate as a random number
        logger.info({"****evaluate_competency_data ":f"failed everything, so assigning default values"})
        response = default_value
        

        # send error on slack to debug this
        send_slack_message({"process": "evaluate_competency_data",
                            "test_attempt_session": test_attempt_session.uid,
                            "error": "failed to evaluate; putting random value"})

        return response, True



@timeit
def evaluate_rating_for_process_training(test_question_response, question_text, response_text,correct_answer, test_title,is_free=False):
    """
    Evaluates the rating for a given response to a test question during a training process.

    This function uses various AI models (Anthropic, Text Bison, GPT-3) to evaluate the candidate's response to a test question. 
    The evaluation is based on a comparison between the candidate's answer and the correct answer. 
    The function tries to use the AI models in a certain order until it gets a valid evaluation. 
    If all attempts fail, it assigns a default rating and sends an error message to a Slack channel.

    Args:
        test_question_response (object): The test question response object.
        question_text (str): The text of the test question.
        response_text (str): The candidate's response to the test question.
        correct_answer (str): The correct answer to the test question.
        test_title (str): The title of the test.
        is_free (bool, optional): A flag indicating whether the evaluation is free or not. Defaults to False.

    Returns:
        tuple: A tuple containing two elements:
            - dict: A dictionary containing the evaluation result. The keys are the skills and the values are the ratings.
              Example: {"rating": 7.5}
            - bool: A flag indicating whether the evaluation was successful or not.

    Raises:
        Exception: If an error occurs during the evaluation process.

    """

    prompt = '''
    \n\nHuman:
    Question:  %s
    Correct answer:  %s
    Candidate answer:  %s

    For the given "Question", a correct answer was provided in "Correct answer". A candidate has given an answer to the question in "Candidate answer". Compare the answer given by the candidate to the correct and give a rating on the candidate answer on a scale of 1-10. 

    NOTE: Output Format Example: {"rating": "7"}
    \n\nAssistant:
    '''%(question_text,correct_answer,response_text)


    if is_free:
         ##################* anthropic ###################
        is_evaluated = True
        response = None

        max_tries = 3  # because anthropic_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****evaluate_rating_for_process_training ":f"trying [outer] anthropic for {1 - max_tries + 1} time"})
                response = anthropic_completion(prompt, 100)
                logger.info({"****evaluate_rating_for_process_training ":f"response [outer] anthropic for {1 - max_tries + 1} time","response":response})
                response = json_extraction(response)
                response = parse_json5(response)
                for skill in response:
                    response[skill] = float(response[skill])

                break
            except Exception as e:
                logger.error({"****evaluate_rating_for_process_training ":f"failed [outer] anthropic for {1 - max_tries + 1} time","error":e})
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue

        if is_evaluated:
            return response, is_evaluated
        else:
            return {"rating": 1}, True
        
    else:
        

        ##################* gemini_completion ###################

        is_evaluated = True
        response = None
        max_tries = 3

        while max_tries > 0:
            try:
                logger.info({"****evaluate_rating_for_process_training ":f"trying [outer]  gemini_completion for  {3 - max_tries + 1} time"})
                response = gemini_completion(prompt)
                logger.info({"****evaluate_rating_for_process_training ":f"response [outer] gemini_completion for {3 - max_tries + 1} time","response":response})
                response = json_extraction(response)
                response = parse_json5(response)
                
                for skill in response:
                    response[skill] = float(response[skill])

                break

            except Exception as e:
                logger.error({"****evaluate_rating_for_process_training ":f"failed [outer] gemini_completion for {3 - max_tries + 1} time","error":e })
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return response, is_evaluated


        ##################* gemini_completion ###################
        
        logger.info({"****evaluate_rating_for_process_training ":f"failed  gemini_completion, so trying anthropic_completion"})

        ##################* anthropic ###################
        is_evaluated = True
        response = None

        max_tries = 3  # because anthropic_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****evaluate_rating_for_process_training ":f"trying [outer] anthropic for {1 - max_tries + 1} time"})
                response = anthropic_completion(prompt, 100)
                logger.info({"****evaluate_rating_for_process_training ":f"response [outer] anthropic for {1 - max_tries + 1} time","response":response})
                response = json_extraction(response)
                response = parse_json5(response)
                for skill in response:
                    response[skill] = float(response[skill])

                break
            except Exception as e:
                logger.error({"****evaluate_rating_for_process_training ":f"failed [outer] anthropic for {1 - max_tries + 1} time","error":e})
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue

        if is_evaluated:
            return response, is_evaluated

        ##################* anthropic ###################

        logger.info({"****evaluate_rating_for_process_training ":f"failed anthropic, so trying gpt_compeletion"})

        ##################* gpt ###################
        is_evaluated = True
        response = None
        max_tries = 3  # because gpt3_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****evaluate_rating_for_process_training ":f"trying [outer] gpt for {3 - max_tries + 1} time"})
                response = gpt3_completion(prompt, stop=["USER:", "CoachBot"]).text
                logger.info({"****evaluate_rating_for_process_training ":f"response [outer] gpt for {3 - max_tries + 1} time","response":response})
                response = json_extraction(response)
                response = parse_json5(response)
                
                for skill in response:
                    response[skill] = float(response[skill])

                break

            except Exception as e:
                logger.error({"****evaluate_rating_for_process_training ":f"failed [outer] gpt for {3 - max_tries + 1} time","error":e })
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue

        if is_evaluated:
            return response, is_evaluated

        ##################* gpt ###################


        # HACK in case everything fails; just evaluate as a random number
        logger.info({"****evaluate_rating_for_process_training ":f"failed everything, so assigning default values"})
        response = {"rating": 1}
        

        # send error on slack to debug this
        send_slack_message({"process": "evaluate_rating_for_process_training",
                            "test_question_response": test_question_response.uid,
                            "error": "failed to evaluate; putting random value"})

        return response, True


@timeit
def evaluate_response_skill(test_attempt_session, conversation, test_title, test_description, test_code, skills, user_skill_prompt, is_free=False, company_context=None, model_order=['gemini','anthropic','gpt']):
    """
    This function evaluates a user's response to a test based on a set of skills.

    The function generates a prompt based on the test title, description, conversation, and skills. It then uses either the anthropic_completion or gemini_completion function to generate a response. If these functions fail, it falls back to gpt3_completion. If all these fail, it assigns a random score to each skill.

    Parameters:
    test_attempt_session (object): The test attempt session object.
    conversation (str): The conversation string.
    test_title (str): The title of the test.
    test_description (str): The description of the test.
    test_code (str): The code of the test.
    skills (list): A list of skills to be evaluated.
    user_skill_prompt (str): The user skill prompt.
    is_free (bool, optional): A flag to determine if the evaluation is free. Defaults to False.

    Returns:
    tuple: A tuple containing:
        - A list of dictionaries, where each dictionary represents the skills rating for a particular skill.
        - A boolean indicating whether the evaluation was successful.

    Raises:
    ValueError: If the skills found in the response are not in the skills list.

    Example:
    >>> evaluate_response_skill(test_attempt_session, "Hello, how are you?", "Test Title", "Test Description", "Test Code", ["skill1", "skill2"], "User Skill Prompt")
    ([{'skill1': 4.5, 'skill2': 9.0}], True)
    """
    skills_rating =skills

    # prompt = f'''
    # "TITLE:" {test_title};

    # "DESCRIPTION:" {test_description};

    # "CONVERSATION:" {conversation};

    # "Evaluation Criteria:"
    # - Relevance: Does the answers directly address the questions in the conversation?
    # - Accuracy: Is the information in the answers correct?
    # - Completeness: Does the answers provide a comprehensive response to the questions?
    # - Clarity: Are the answers well-written and easy to understand?

    # "REQUIRED FROM LLM:" Based on the above criteria please evaluate the given answers on a scale of 0-10, with scores in increments of 0.5 for each behaviour trait in this cultural_list in JSON. 

    # "cultural_list:" "{skills_rating}"

    # NOTE: Please put properties of JSON enclosed in double quotes.

    # Example of JSON: {{"hierarchy": "9.5", "consensual": "4", "indirect negative feedback": "4.5", "relationship based": "6", "high context communication": "2.5", "Persuasion": "5", "argumentative": "10"}}
    # '''

    # prompt = f'''
    #     "TITLE:" {test_title};

    #     "DESCRIPTION:" {test_description};

    #     "CONVERSATION:" {conversation};

    #     "Evaluation Criteria:"

    #     - Relevance: Does the answer directly address the question?

    #     - Accuracy: Is the information in the answer correct?

    #     - Completeness: Does the answer provide a comprehensive response to the question?

    #     - Clarity: Is the answer well-written and easy to understand?

    #     "REQUIRED FROM LLM:" Based on the above criteria please evaluate the given conversation i.e. all answers on a scale of 1-9, with scores in increments of 0.5 for each skill in the list in JSON: "{skills}" in such a way that no two skills can have the exact same score.

    #     NOTE: Please put properties of JSON enclosed in double quotes.

    #     NOTE: Please Reply in a valid JSON format only and no other format will be accepted.

    #     NOTE: Don't put any other text in the reply other than the JSON. The keys in json object must be taken from {skills_rating} only.

    #     NOTE: For the entire conversation no two skills from {skills_rating} can have exact same scores.

    #     NOTE: Do not add any English language sentence in the output.
        
    #     {user_skill_prompt}

    # '''

    prompt = f'''
        \n\nHuman:
        "TITLE:" {test_title};

        "DESCRIPTION:" {test_description};

        "CONVERSATION:" {conversation};

        "Evaluation Criteria:"

        - Relevance: Does the answer directly address the question?

        - Accuracy: Is the information in the answer correct?

        - Completeness: Does the answer provide a comprehensive response to the question?

        - Clarity: Is the answer well-written and easy to understand?

        "REQUIRED FROM LLM:" Based on the above criteria please evaluate the given conversation i.e. all answers on a scale of 1-9, with scores in increments of 0.5 for each skill in the list in JSON: "{skills}" in such a way that no two skills can have the exact same score.

        NOTE: Please put properties of JSON enclosed in double quotes.

        NOTE: Please Reply in a valid JSON format only and no other format will be accepted.

        NOTE: Don't put any other text in the reply other than the JSON. The keys in json object must be taken from {skills} only.

        NOTE: Give me the exact skill name as given. Do Not change the name of any of the skill.

        NOTE: Output Format Example: {{"skill1": "4.5", "skill2": "9", "skill3": "2.5"}}

        NOTE : Do not give the output as skill1 or skill2, only use the name of the skills given.

        NOTE: For the entire question and answer conversation no two skills from {skills} can have exact same scores.
        
        NOTE : Do not provide any kind of heading or introduction text in the output.

        NOTE: Do not add any English language sentence in the output.
        {user_skill_prompt}
        \n\nAssistant:
        '''
    
    code_prompt = """
        \n\nHuman:
        "TITLE:" ${title};

        "DESCRIPTION:" ${description};

        "CONVERSATION:" ${conversation};

        "skills" : ${skills_list}

        "Evaluation Criteria:"

        - Relevance: Does the answer directly address the question?

        - Accuracy: Is the information in the answer correct?

        - Completeness: Does the answer provide a comprehensive response to the question?

        - Clarity: Is the answer well-written and easy to understand?

        REQUIRED FROM LLM:
        - Always consider the Title, Description, and Conversation when rating the skills. Evaluate each skill based on the criteria provided, ensuring a comprehensive and holistic analysis.
        - Assign a unique score between 0.5 and 9.5 for each skill listed in {skills}, ensuring that no two skills receive the same score. Use decimal values for more precision (e.g., 4.2, 7.3).
        - Ensure that each skill is rated uniquely, with no repeated scores.

        Strict Constraints:
        -   No two skills should have the same score.
        -   Do not modify the provided code or include any additional information in the output.
        -   NEVER PRINT ANYTHING ELSE EXCEPT THE PRINT OUTPUT.

        format_instructions = {
            "output_format": "word",
            "explanations": False,
            "word_counts": False
        }
        **Output in JSON format**:  Ensure that the output is formatted as valid JSON.
        import json
        from typing import Dict

        ScoreDictionary = Dict[str, float]
        final_scores: ScoreDictionary = {
        "skill": float(calulated score)
        }

        print(json.dumps(final_scores))

        \n\nAssistant:
    """

    prompt = Template(code_prompt).substitute(
        title=test_title,
        description = test_description,
        conversation = conversation,
        skills_list = skills_rating,
    )

    if is_free:
        model_order = ['anthropic']

    responses = []
    is_evaluated = False
    
    model_functions = {
        "gemini": gemini_completion,
        "anthropic": anthropic_completion,
        "gpt": lambda p: gpt3_completion(p, stop=["USER:", "CoachBot"]).text,
    }
    
    for model in model_order:
        max_tries = 3
        while max_tries > 0:
            try:
                logging.info(f"[evaluate_response_skill] Trying {model} [outer] for {4 - max_tries} time")
                response = model_functions[model](prompt)
                
                skills_rating_str = json_extraction(response)
                skills_rating_json = json.loads(skills_rating_str)
                
                # if not is_skill_matched(skills, skills_rating.keys()):
                #     raise ValueError("Skills not found in the skills list.")
                skills_rating = {}
                garbage_keywords = {s.strip().lower() for s in ['Overal', 'Performance', 'Total', 'Other', 'Top']}

                for skill, rating in skills_rating_json.items():
                    if skill.strip().lower() in garbage_keywords:
                        logger.info(f"Skill '{skill}' in {garbage_keywords}")
                        continue
                    skills_rating[skill] = float(rating)
                
                responses.append(skills_rating)
                response = skills_rating
                is_evaluated = True
                break  # Exit retry loop on success
            
            except Exception as e:
                logging.error(f"[evaluate_response_skill] {model} [outer] failed for {4 - max_tries} time: {e}")
                max_tries -= 1
                time.sleep(1)
    
        if is_evaluated:
            logger.info(f"[evaluate_response_skill] Final skill rating: {responses}")
            return *responses, is_evaluated
    
    logging.info("All models failed, assigning default values")
    
    response = {skill: random.randint(3, 7) for skill in skills}
    send_slack_message({
        "process": "evaluate_response_skills",
        "test_attempt_session": test_attempt_session.uid,
        "error": "Failed to evaluate; assigning random values"
    })
    
    return response, True


@timeit
def find_top_low_skills(skill_ratings, num_top_skills=2):
    """
    This function identifies the top and lowest rated skills from a given dictionary of skill ratings.

    The function sorts the skill_ratings dictionary in descending order to find the top skills and in ascending order to find the lowest skills. The number of top and lowest skills returned is determined by the num_top_skills parameter.

    Args:
        skill_ratings (dict): A dictionary where the keys are the skill names (str) and the values are the skill ratings (int or float). 
            Example: {'python': 5, 'java': 3, 'c++': 4}
        num_top_skills (int, optional): The number of top and lowest skills to return. Defaults to 2.

    Returns:
        tuple: A tuple containing two dictionaries. The first dictionary contains the top skills and their ratings, and the second dictionary contains the lowest skills and their ratings.
            Example: ({'python': 5, 'c++': 4}, {'java': 3})

    Note:
        If there are more skills with the same rating as the last skill in the top or lowest skills, they will not be included in the result. The function strictly returns the number of skills specified by num_top_skills.
    """
    sorted_skills = sorted(skill_ratings.items(), key=lambda x: x[1], reverse=True)
    top_skills = {skill: score for skill, score in sorted_skills[:num_top_skills]}

    sorted_skills = sorted(skill_ratings.items(), key=lambda x: x[1])
    lowest_skills = {skill: score for skill, score in sorted_skills[:num_top_skills]}
    
    return top_skills , lowest_skills

@timeit
def calulate_summary_for_culture_and_normal_skill(test_attempt_session,cultural_skill, skill_rating,is_free=False):

    top_skill, low_skill = find_top_low_skills(skill_rating)
    high_cult, low_cult = find_top_low_skills(cultural_skill)

    prompt= """
    \n\nHuman:

    {Top_skills} : %s

    {Low_skills} : %s

    {Improvement} : Provide some ideas on how the user can improve the {Low_skills} in 2-3 sentences.

    {High_culture} : %s

    {Low_culture} : %s

    {Culture_summary} : Please summarize the {High_culture} and {Low_culture} and the reason for the same in 2-3 sentences and comment on the culture orientation of the responder.

    Do not provide the {High_culture}, {Low_culture} in the output.

    The output should be in the given format :

    " 1. The highest rated skills : {Top_skills}

    2. The lowest rated skills : {Low_skills}

    3. {Improvement}

    4. {Culture_summary}"

    Do not provide the High_culture, Low_culture in the output.

    NOTE : Always provide the output in the given format.

    NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output. Start directly with the summary and only provide the summary.
    NOTE : Always detact language of the conversation and entire output must be in same language.

    \n\nAssistant:
    """%(top_skill,low_skill,high_cult,low_cult)


    if is_free:
        #################################* anthropic #################################
        is_evaluated = True

        response = ""
        max_tries = 3  # because anthropic_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****calulate_summary_for_culture_and_normal_skill ":f"trying [outer] anthropic for {1 - max_tries + 1} time"})
                response = anthropic_completion(prompt, 300)
                logger.info({"****calulate_summary_for_culture_and_normal_skill ":f"response [outer] anthropic for {1 - max_tries + 1} time","response":response})

                break

            except Exception as e:
                logger.error({"****calulate_summary_for_culture_and_normal_skill ":f"failed [outer] anthropic for {1 - max_tries + 1} time","error":e})
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return response

        #################################* anthropic end #################################

        logger.info({"****calulate_summary_for_culture_and_normal_skill ":f"failed everything, so assigning default values"})

        # HACK in case everything fails; just evaluate as a random number
        response = ""

        # send error on slack to debug this
        send_slack_message({"process": "calulate_summary_for_culture_and_normal_skill",
                            "test_attempt_session": test_attempt_session.uid,
                            "error": "failed to evaluate; putting random value"})

        return response


    else:

        #################################* gemini_completion #################################
        response = None
        max_tries = 3  # because gpt3_completion function itself retries 3 times
        is_evaluated = True

        while max_tries > 0:
            try:
                logger.info({"****calulate_summary_for_culture_and_normal_skill ":f"trying gemini_completion [outer] for {3 - max_tries + 1} time"})
                response = gemini_completion(prompt)
                logger.info({"****calulate_summary_for_culture_and_normal_skill ":f"response [outer] gemini_completion for {3 - max_tries + 1} time","response":response})


                break

            except Exception as e:
                logger.error({"****calulate_summary_for_culture_and_normal_skill ":f"failed [outer] gemini_completion for {3 - max_tries + 1} time","error":e })
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return response

        #################################* gemini_completion end #################################

        logger.info({"****calulate_summary_for_culture_and_normal_skill ":f"failed gemini_completion, so trying anthropic_completion"})
        
        #################################* anthropic #################################
        is_evaluated = True

        response = ""
        max_tries = 3  # because anthropic_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****calulate_summary_for_culture_and_normal_skill ":f"trying [outer] anthropic for {1 - max_tries + 1} time"})
                response = anthropic_completion(prompt, 300)
                logger.info({"****calulate_summary_for_culture_and_normal_skill ":f"response [outer] anthropic for {1 - max_tries + 1} time","response":response})

                break

            except Exception as e:
                logger.error({"****calulate_summary_for_culture_and_normal_skill ":f"failed [outer] anthropic for {1 - max_tries + 1} time","error":e})
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return response

        #################################* anthropic end #################################

        logger.info({"****calulate_summary_for_culture_and_normal_skill ":f"failed anthropic, so trying gpt_compeletion"})

        #################################* gpt #################################
        is_evaluated = True
        response = None
        max_tries = 3  # because gpt3_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****calulate_summary_for_culture_and_normal_skill ":f"trying gpt [outer] for {3 - max_tries + 1} time"})
                response = gpt3_completion(prompt, stop=["USER:", "CoachBot"]).text
                logger.info({"****calulate_summary_for_culture_and_normal_skill ":f"response [outer] gpt for {3 - max_tries + 1} time","response":response})

                break

            except Exception as e:
                logger.error({"****calulate_summary_for_culture_and_normal_skill ":f"failed [outer] gpt for {3 - max_tries + 1} time","error":e })
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return response

        #################################* gpt end #################################
        

        logger.info({"****calulate_summary_for_culture_and_normal_skill ":f"failed everything, so assigning default values"})

        # HACK in case everything fails; just evaluate as a random number
        response = ""

        # send error on slack to debug this
        send_slack_message({"process": "calulate_summary_for_culture_and_normal_skill",
                            "test_attempt_session": test_attempt_session.uid,
                            "error": "failed to evaluate; putting random value"})

        return response



@timeit
def feedback_summary(test_attempt_session,feedbacks,is_free=False):
    prompt= """
    \n\nHuman:
    {feedbacks} : %s

    {Summary} : Summarize the entire feedback in a small single paragraph and provide feedback to the candidate. Focus on the areas that worked well and the areas the candidate can improve.

    Output format :

    "Here is your summary feedback:

    {Summary}"

    Always follow this output format in this exact manner. DO NOT add words or any other sentence on your own.

    NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output. Start directly with the summary and only provide the summary.
    NOTE : Always (must) detact language of the feedbacks context only and entire output must be in same language.

    \n\nAssistant:
    """%(feedbacks)

    if is_free:
        #################################* anthropic #################################
        is_evaluated = True

        response = ""
        max_tries = 3  # because anthropic_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****feedback_summary ":f"trying [outer] anthropic for {1 - max_tries + 1} time"})
                response = anthropic_completion(prompt, len(feedbacks.split()) + 200)
                logger.info({"****feedback_summary ":f"response [outer] anthropic for {1 - max_tries + 1} time","response":response})

                break

            except Exception as e:
                logger.error({"****feedback_summary ":f"failed [outer] anthropic for {1 - max_tries + 1} time","error":e})
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return response

        #################################* anthropic end #################################


        logger.info({"****feedback_summary ":f"failed everything, so assigning default values"})

        # HACK in case everything fails; just evaluate as a random number
        response = ""

        # send error on slack to debug this
        send_slack_message({"process": "feedback_summary",
                            "test_attempt_session": test_attempt_session.uid,
                            "error": "failed to evaluate; putting random value"})

        return response


    else:

        #################################* gemini_completion #################################
        response = None
        max_tries = 3  # because gpt3_completion function itself retries 3 times
        is_evaluated = True

        while max_tries > 0:
            try:
                logger.info({"****feedback_summary ":f"trying gemini_completion [outer] for {3 - max_tries + 1} time"})
                response = gemini_completion(prompt)
                logger.info({"****feedback_summary ":f"response [outer] gemini_completion for {3 - max_tries + 1} time","response":response})


                break

            except Exception as e:
                logger.error({"****feedback_summary ":f"failed [outer] gemini_completion for {3 - max_tries + 1} time","error":e })
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return response

        #################################* gemini_completion end #################################

        logger.info({"****feedback_summary ":f"failed gemini_completion, so trying anthropic_completion"})

        #################################* anthropic #################################
        is_evaluated = True

        response = ""
        max_tries = 3  # because anthropic_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****feedback_summary ":f"trying [outer] anthropic for {1 - max_tries + 1} time"})
                response = anthropic_completion(prompt, len(feedbacks.split()) + 200)
                logger.info({"****feedback_summary ":f"response [outer] anthropic for {1 - max_tries + 1} time","response":response})

                break

            except Exception as e:
                logger.error({"****feedback_summary ":f"failed [outer] anthropic for {1 - max_tries + 1} time","error":e})
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return response

        #################################* anthropic end #################################

        logger.info({"****feedback_summary ":f"failed anthropic, so trying gpt_compeletion"})

        #################################* gpt #################################
        is_evaluated = True
        response = None
        max_tries = 3  # because gpt3_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****feedback_summary ":f"trying gpt [outer] for {3 - max_tries + 1} time"})
                response = gpt3_completion(prompt, stop=["USER:", "CoachBot"]).text
                logger.info({"****feedback_summary ":f"response [outer] gpt for {3 - max_tries + 1} time","response":response})

                break

            except Exception as e:
                logger.error({"****feedback_summary ":f"failed [outer] gpt for {3 - max_tries + 1} time","error":e })
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return response

        #################################* gpt end #################################



        logger.info({"****feedback_summary ":f"failed everything, so assigning default values"})

        # HACK in case everything fails; just evaluate as a random number
        response = ""

        # send error on slack to debug this
        send_slack_message({"process": "feedback_summary",
                            "test_attempt_session": test_attempt_session.uid,
                            "error": "failed to evaluate; putting random value"})

        return response


def get_culture_skills(skills_type: str, only_criteria: bool = False):
    cultural_skills = {
            "Need for Structure": "Does the conversation display a need for structure? Assesses the individual's preference for clear rules, procedures, and predictability versus ambiguity and flexibility.",
            "Orientation towards Authority": "Does the conversation display orientation towards authority? Measures the individual's inherent approach to authority—respectful deference, active engagement, or challenging/resisting.",
            "Emphasis on Relationships": "Does the conversation display emphasis on relationships? Assesses the extent to which the individual prioritizes building and maintaining relationships versus focusing solely on tasks and outcomes.",
            "Direct Communication Style": "How direct is the communication style displayed in the conversation? While the manifestation of communication style will vary, the underlying preference for direct versus indirect communication tends to be more consistent.",
            "Long Term Focus": "Does the conversation display long-term focus? Assesses whether the individual's focus is primarily on immediate gratification or on long-term planning and future goals.",
            "Value Placed on Independence": "Does the conversation display a need for independence? Measures the individual's inherent preference for autonomy and self-reliance versus interdependence and collaboration.",
            "Propensity for Risk-Taking": "Does the conversation display a high-risk or low-risk-taking style? Captures the individual's inherent inclination toward risk—high tolerance versus strong aversion."
        }
    evaluation_criteria = None
    if skills_type == 'communicational':
        cultural_skills = {
            "Hierarchy": "Does the conversation look like the participants have a strict hierarchical relationship (highest score of 10) or a casual professional relationship (score of 0)?",
            "Consensual": "Does the conversation look like the respondents have respect for boundaries and empathy? (High yes score of 10 and low is 0).",
            "Indirect Negative Feedback": "Do the participants provide subtle feedback or blunt feedback? (Subtle feedback is 10 and blunt feedback is 0).",
            "Relationship-Based": "Does the conversation look like the participants focus on relationships (highest score of 10) or tasks (score of 0)?",
            "High Context Communication": "Does the conversation look like the participants focus on subtle cues (highest score of 0) or explicit verbal communication (score of 10)?",
            "Persuasion": "Does the conversation look like the participants value emotional appeals (highest score of 10) or completely rely on logic and evidence (score of 0)?",
            "Argumentative": "Does the conversation look like the participants see debate and disagreement as a competition (highest score of 0) or view it as a collaborative process to find truth (score of 10)?"
        }
    elif skills_type == 'workplace_skills':
        cultural_skills = {
            "Need for Structure": "Does the conversation display a need for structure? Assesses the individual's preference for clear rules, procedures, and predictability versus ambiguity and flexibility.",
            "Orientation towards Authority": "Does the conversation display orientation towards authority? Measures the individual's inherent approach to authority—respectful deference, active engagement, or challenging/resisting.",
            "Emphasis on Relationships": "Does the conversation display emphasis on relationships? Assesses the extent to which the individual prioritizes building and maintaining relationships versus focusing solely on tasks and outcomes.",
            "Direct Communication Style": "How direct is the communication style displayed in the conversation? While the manifestation of communication style will vary, the underlying preference for direct versus indirect communication tends to be more consistent.",
            "Long Term Focus": "Does the conversation display long-term focus? Assesses whether the individual's focus is primarily on immediate gratification or on long-term planning and future goals.",
            "Value Placed on Independence": "Does the conversation display a need for independence? Measures the individual's inherent preference for autonomy and self-reliance versus interdependence and collaboration.",
            "Propensity for Risk-Taking": "Does the conversation display a high-risk or low-risk-taking style? Captures the individual's inherent inclination toward risk—high tolerance versus strong aversion."
        }
    elif skills_type == 'ocean_model':
        cultural_skills = {
            "Openness to Experience": "Does the conversation display openness to experience? Assesses the individual's curiosity, creativity, and receptiveness to new ideas versus preference for familiarity and conventional thinking.",
            "Conscientiousness": "Does the conversation display conscientiousness? Measures the individual's organization, attention to detail, and reliability versus spontaneity and casual approach to obligations.",
            "Extraversion": "Does the conversation display extraversion? Evaluates the individual's sociability, assertiveness, and energy in social settings versus preference for solitude and quieter environments.",
            "Agreeableness": "Does the conversation display agreeableness? Assesses the individual's cooperation, consideration for others, and harmonious approach versus competitive or challenging interactions.",
            "Neuroticism": "Does the conversation display neuroticism? Measures the individual's emotional stability, resilience to stress, and ability to manage negative emotions versus tendency toward anxiety, worry, or emotional volatility."
        }
        evaluation_criteria = {"Evaluation Criteria for the Big Five Personality Traits (OCEAN)" : """
        The following criteria provide a structured framework for assessing the five major personality dimensions known as the **OCEAN** model (**Openness, Conscientiousness, Extraversion, Agreeableness, and Neuroticism**). These criteria can be used to evaluate an individual's personality traits through **conversation analysis, behavioral observation, or self-reporting**.
<br><br>
### Openness to Experience:

- **Intellectual Curiosity**: Does the conversation display interest in abstract ideas, philosophical discussions, or theoretical concepts?
  *Assesses the individual's tendency to explore new intellectual territories versus preferring practical, concrete thinking.*

- **Aesthetic Appreciation**: Does the conversation reveal sensitivity to art, beauty, or creative expression?
  *Measures the individual's receptiveness to aesthetic experiences versus indifference to artistic elements.*

- **Imagination and Fantasy**: Does the conversation demonstrate creative thinking, imaginative scenarios, or "outside-the-box" perspectives?
  *Evaluates the tendency toward creative visualization versus literal, fact-based thinking.*

- **Receptiveness to New Experiences**: Does the conversation show willingness to try unfamiliar activities or consider novel approaches?
  *Assesses openness to new experiences versus preference for familiar routines and traditional methods.*

- **Tolerance for Ambiguity**: Does the conversation display comfort with uncertainty and open-ended situations?
  *Measures preference for exploration and discovery versus need for definitive answers and closure.*

- **Intellectual Independence**: Does the conversation reveal a tendency to question established conventions or authority?
  *Evaluates the propensity to challenge traditional viewpoints versus accepting conventional wisdom.*

<br>

### Conscientiousness:

- **Organizational Tendency**: Does the conversation display evidence of systematic planning and organization?
  *Assesses the individual's preference for order and structure versus spontaneity and flexibility.*

- **Attention to Detail**: Does the conversation demonstrate thoroughness and precision in discussing topics?
  *Measures meticulousness and careful consideration versus a more casual, general approach.*

- **Goal Orientation**: Does the conversation reflect clear objectives and purposeful direction?
  *Evaluates focus on achievement and task completion versus more relaxed, process-oriented engagement.*

- **Reliability and Dependability**: Does the conversation suggest follow-through on commitments and responsibilities?
  *Assesses trustworthiness and consistency versus unpredictability or unreliability.*

- **Self-Discipline**: Does the conversation indicate ability to persist with difficult or tedious tasks?
  *Measures capacity for sustained effort versus preference for immediate gratification.*

- **Deliberativeness**: Does the conversation show careful consideration before making decisions or forming opinions?
  *Evaluates thoughtful deliberation versus impulsivity.*

<br>

### Extraversion:

- **Social Engagement**: Does the conversation display enthusiasm for social interaction and group activities?
  *Assesses preference for being with others versus solitary pursuits.*

- **Assertiveness**: Does the conversation demonstrate comfort with expressing opinions and taking the lead?
  *Measures directness and leadership orientation versus reticence and following tendencies.*

- **Energy Level**: Does the conversation reflect high animation, expressiveness, and vigor?
  *Evaluates energetic, dynamic engagement versus calm, reserved demeanor.*

- **Stimulation Seeking**: Does the conversation indicate desire for excitement and stimulating environments?
  *Assesses preference for high-energy, varied experiences versus quieter, more predictable settings.*

- **Social Confidence**: Does the conversation show ease in social situations and comfort being the center of attention?
  *Measures self-assurance in social contexts versus social inhibition.*

- **Conversational Dominance**: Does the conversation reveal a tendency to initiate and sustain dialogue?
  *Evaluates talkativeness and conversation-driving behavior versus listening and responding primarily when addressed.*


<br>

### Agreeableness:

- **Empathic Concern**: Does the conversation display understanding of and sensitivity to others' feelings?
  *Assesses emotional resonance with others versus detachment or indifference.*

- **Cooperative Orientation**: Does the conversation demonstrate willingness to accommodate others' needs and perspectives?
  *Measures collaborative approach versus competitive or self-focused orientation.*

- **Trust in Others**: Does the conversation reflect a tendency to assume others' good intentions?
  *Evaluates belief in others' benevolence versus skepticism or suspicion.*

- **Conflict Avoidance**: Does the conversation show preference for harmony and consensus over confrontation?
  *Assesses comfort with compromise versus standing firm on positions.*

- **Altruistic Tendency**: Does the conversation indicate willingness to help others without expectation of return?
  *Measures selfless concern for others' welfare versus self-interest prioritization.*

- **Forgiving Attitude**: Does the conversation display ability to let go of grievances and restore relations?
  *Evaluates tendency to forgive transgressions versus holding grudges.*

  
<br>

### Neuroticism:

- **Emotional Reactivity**: Does the conversation show intense responses to minor stressors or criticisms?
  *Assesses sensitivity to negative stimuli versus emotional stability under pressure.*

- **Anxiety Level**: Does the conversation display excessive worry about potential problems or uncertainties?
  *Measures tendency toward fearful anticipation versus calm confidence about the future.*

- **Mood Fluctuation**: Does the conversation demonstrate rapid or unpredictable changes in emotional state?
  *Evaluates emotional variability versus consistent mood.*

- **Self-Consciousness**: Does the conversation reveal heightened awareness of potential judgment or criticism?
  *Assesses concern about others' opinions versus self-assured independence.*

- **Stress Tolerance**: Does the conversation indicate difficulty coping with challenging situations?
  *Measures vulnerability to stress versus resilience and adaptability.*

- **Negative Outlook**: Does the conversation display tendencies toward pessimism or focus on negative aspects?
  *Evaluates negative bias in perceptions versus balanced or positive perspective.*


        """}

    if only_criteria:
        return evaluation_criteria

    return cultural_skills, evaluation_criteria


@timeit
def evaluate_conversation(test_attempt_session, conversation, test, is_free=False, model_order=["gemini", "anthropic", "gpt"]):
    """
    It evaluates the cultural rating for a scenario (test,trainer type)
    """
    test_title = test.title
    test_description = test.description
    # cultural_skills_and_desc, _ = get_culture_skills("ocean_model" if test.scenario_case == ScenarioCaseChoices.psychometric else "workplace_skills")
    if test.culture_skills_to_evaluate:
        evaluation_criteria = test.culture_skills_to_evaluate
        cultural_skills = test.culture_skills_to_evaluate.keys()
    else:
        skills = CultureMapSkill.objects.filter(deleted=False, tenant_id=test_attempt_session.tenant_id, test_type=test.scenario_case)
        if not skills.exists():
            skills = CultureMapSkill.objects.filter(deleted=False, tenant_id=test_attempt_session.tenant_id,test_type=ScenarioCaseChoices.others)

        evaluation_criteria = "\n".join([f"- {skill.skill}: {skill.description}" for skill in skills])
        cultural_skills = [skill.skill for skill in skills]

    logger.info(f"evaluation criteria: {evaluation_criteria} \n cultural skills: {cultural_skills}")

    prompt = f'''
        \n\nHuman:
        "TITLE:" {test_title};

        "DESCRIPTION:" {test_description};

        "CONVERSATION:" {conversation};

        "Evaluation Criteria:"
        {evaluation_criteria}
        
        "REQUIRED FROM LLM:" Based on the above criteria please evaluate the entire conversation - which is a list of all questions and answers. Rate the criteria's only from a scale of 1.5-9 in such a way that no two skills can have the exact same score, with scores in increments of 0.5 for each behavior trait listed above which corresponds to this cultural_list in JSON.

        "cultural_list:" "{cultural_skills}"

        NOTE: Please put properties of JSON enclosed in double quotes.

        Example of JSON: {{"hierarchy": "9.5", "consensual": "4", "indirect negative feedback": "4.5", "relationship-based": "6", "high context communication": "2.5", "Persuasion": "5", "argumentative": "10"}}

        NOTE: For the entire question and answer conversation no two skills from {cultural_skills} can have exact same scores.

        NOTE : Do not provide any kind of heading or introduction text in the output.

        NOTE: Do not add any English language sentence in the output.
        \n\nAssistant:
        '''
    

    code_prompt = """
        \n\nHuman:
            "TITLE:" ${title};

            "DESCRIPTION:" ${description};

            "CONVERSATION:" ${conversation};

            "cultural_list:" ${skills_list}


            "Evaluation Criteria:"
                ${evaluation_criteria}
            "REQUIRED FROM LLM:" 
            - Always consider the Title, Description, and Conversation when rating the skills. Evaluate each skill based on the criteria provided, ensuring a comprehensive and holistic analysis.
            - Assign a unique score between 0.5 and 9.5 for each skill listed in {cultural_list}, ensuring that no two skills receive the same score. Use decimal values for more precision (e.g., 4.2, 7.3).
            - Ensure that each skill is rated uniquely, with no repeated scores.

            Strict Constraints:
            -   No two skills should have the same score.
            -   Do not modify the provided code or include any additional information in the output.
            -   NEVER PRINT ANYTHING ELSE EXCEPT THE PRINT OUTPUT.

            format_instructions = {
                "output_format": "word",
                "explanations": False,
                "word_counts": False
            }
            **Output in JSON format**:  Ensure that the output is formatted as valid JSON.
            import json
            from typing import Dict

            ScoreDictionary = Dict[str, float]
            final_scores: ScoreDictionary = {
            "skill": float(calulated score)
            }
            print(json.dumps(final_scores))
        \n\nAssistant:
        """

    prompt = Template(code_prompt).substitute(
        title=test_title,
        description = test_description,
        conversation = conversation,
        skills_list = cultural_skills,
        evaluation_criteria = evaluation_criteria
    )
    if is_free:
        model_order = ['anthropic']

    responses = []
    is_evaluated = False
    
    model_functions = {
        "gemini": gemini_completion,
        "anthropic": anthropic_completion,
        "gpt": lambda p: gpt3_completion(p, stop=["USER:", "CoachBot"]).text,
    }
    
    for model in model_order:
        max_tries = 3
        while max_tries > 0:
            try:
                logging.info(f"[evaluate_conversation] Trying {model} [outer] for {4 - max_tries} time")
                response = model_functions[model](prompt)
                
                skills_rating_str = json_extraction(response)
                skills_rating = json.loads(skills_rating_str)
                
                skills_rating = {skill: float(score) for skill, score in skills_rating.items()}
                responses.append(skills_rating)
                is_evaluated = True
                break  # Exit retry loop on success
            
            except Exception as e:
                logging.error(f"[evaluate_conversation]{model}[outer] failed for {4 - max_tries} time: {e}", exc_info=True)
                max_tries -= 1
                time.sleep(1)
    
        if is_evaluated:
            return *responses, is_evaluated
    
    logging.info("All models failed, assigning default values")
    
    response = {skill: random.randint(3, 7) for skill in cultural_skills}
    send_slack_message({
        "process": "evaluate_conversation",
        "test_attempt_session": test_attempt_session.uid,
        "error": "Failed to evaluate; assigning random values"
    })
    
    return response, True



@timeit
def evaluate_group_discussion_conversation(test_attempt_session, conversation, user_persona, objective, test_code,test,is_free=False,model_order=["gemini", "anthropic", "gpt"]):
    """
    It evaluates the cultural rating for a scenario (group discussion)
    """
    cultural_skills = ['hierarchy', 'consensual', 'indirect negative feedback',
                       'relationship based', 'high context communication', 'Persuasion', 'argumentative']
    cultural_skills = [
            "Need for Structure",
            "Orientation towards Authority",
            "Emphasis on Relationships",
            "Propensity for Risk-Taking",
            "Direct Communication Style",
            "Long term focus",
            "Value Placed on Independence"
        ]
    
    if test.culture_skills_to_evaluate:
        evaluation_criteria = test.culture_skills_to_evaluate
        cultural_skills = test.culture_skills_to_evaluate.keys()
    else:
    
        skills = CultureMapSkill.objects.filter(deleted=False, tenant_id=test_attempt_session.tenant_id, test_type=test.scenario_case)
        if not skills.exists():
            skills = CultureMapSkill.objects.filter(deleted=False, tenant_id=test_attempt_session.tenant_id,test_type=ScenarioCaseChoices.others)

        evaluation_criteria = "\n".join([f"- {skill.skill}: {skill.description}" for skill in skills])
        cultural_skills = [skill.skill for skill in skills]

    logger.info(f"evaluation criteria: {evaluation_criteria} \n cultural skills: {cultural_skills}")

    # prompt = f'''
    # "Objective:" {objective};

    # "Conversation:" {conversation};

    # "REQUIRED FROM LLM:" Based on the above criteria please evaluate the "{user_persona}" on a scale of 0-10, with scores in increments of 0.5. Evaluate the conversation for the participant: "{user_persona}" and this "{user_persona}" only, in this conversation for each behaviour trait in this cultural_list in JSON. 

    # "cultural_list:" "{cultural_skills}"

    # Please put properties of JSON enclosed in double quotes.

    # Example of JSON: {{"hierarchy": "9.5", "consensual": "4", "indirect negative feedback": "4.5", "relationship based": "6", "high context communication": "2.5", "Persuasion": "5", "argumentative": "10"}}
    # '''

    # prompt = f'''
    # "Objective:" {objective};

    # "Conversation:" {conversation};

    # "REQUIRED FROM LLM:" Based on the above criteria please evaluate the "{user_persona}" only from a scale of 1.5-9, with scores in increments of 0.5. Evaluate the conversation for the participant: "{user_persona}" and this "{user_persona}" only, in this conversation for each behaviour trait in this cultural_list in JSON.

    # "cultural_list:" "{cultural_skills}"

    # Please put properties of JSON enclosed in double quotes.

    # Example of JSON: {{"hierarchy": "9.5", "consensual": "4", "indirect negative feedback": "4.5", "relationship based": "6", "high context communication": "2.5", "Persuasion": "5", "argumentative": "10"}}

    # NOTE: Do not add any English language sentence in the output.
    # '''


    prompt = f''' 
        \n\nHuman:
        "Objective:" {objective}; 
        "Conversation:" {conversation}; 
        "REQUIRED FROM LLM:" Based on the above criteria please evaluate the "{user_persona}" only from a scale of 1.5-9, with scores in increments of 0.5. Evaluate the conversation for the participant: "{user_persona}" and this "{user_persona}" only, in this conversation for each behaviour trait in this cultural_list in JSON. 
        "cultural_list:" "{cultural_skills}" 
        Please put properties of JSON enclosed in double quotes. 
        Example of JSON: {{"hierarchy": "9.5", "consensual": "4", "indirect negative feedback": "4.5", "relationship based": "6", "high context communication": "2.5", "Persuasion": "5", "argumentative": "10"}} 
        NOTE: Do not add any English language sentence in the output. 

        NOTE : Do not provide any kind of heading or introduction text in the output.
        \n\nAssistant:
    '''
    code_prompt = """
    \n\nHuman:
        "Objective:" ${objective}; 
        "Conversation:" ${conversation}; 
        "cultural_list:" ${cultural_skills};
        "user_persona": ${user_persona};

        "Evaluation Criteria:"
                ${evaluation_criteria}
        "REQUIRED FROM LLM:" 
            - Based on the above criteria please evaluate the "{user_persona}" only from a scale of 0.5-9.5. Use decimal values for more precision (e.g., 4.2, 7.3).
            - Evaluate the conversation for the participant: "{user_persona}" and this "{user_persona}" only, in this conversation for each behaviour trait in this 'cultural_list',ensuring that no two skills receive the same score.
            - Ensure that each skill is rated uniquely, with no repeated scores.

        Strict Constraints:
        -   No two skills should have the same score.
        -   Do not modify the provided code or include any additional information in the output.
        -   NEVER PRINT ANYTHING ELSE EXCEPT THE PRINT OUTPUT.

        format_instructions = {
            "output_format": "word",
            "explanations": False,
            "word_counts": False
        }
        **Output in JSON format**:  Ensure that the output is formatted as valid JSON.
        import json
        from typing import Dict

        ScoreDictionary = Dict[str, float]
        final_scores: ScoreDictionary = {
        "skill": float(calulated score)
        }
        print(json.dumps(final_scores))
        \n\nAssistant:
    """

    prompt = Template(code_prompt).substitute(
        objective=objective,
        user_persona = user_persona,
        conversation = conversation,
        cultural_skills = cultural_skills,
        evaluation_criteria = evaluation_criteria
    )

    if is_free:
        model_order = ['anthropic']
    
    skills_rating = None
    is_evaluated = True
    max_tries = 3  # Each model itself retries 3 times

    for model in model_order:
        while max_tries > 0:
            try:
                logger.info({"****evaluate_group_discussion_conversation ": f"trying [outer] {model} for {3 - max_tries + 1} time"})
                
                if model == "anthropic":
                    response = anthropic_completion(prompt, len(cultural_skills) * 100)
                elif model == "gemini":
                    response = gemini_completion(prompt)
                elif model == "gpt":
                    response = gpt3_completion(prompt, stop=["USER:", "CoachBot"]).text
                else:
                    continue
                
                logger.info({"****evaluate_group_discussion_conversation ": f"response [outer] {model} for {3 - max_tries + 1} time", "response": response})
                
                skills_rating_str = json_extraction(response)
                skills_rating = json.loads(skills_rating_str)
                
                for skill in skills_rating:
                    skills_rating[skill] = float(skills_rating[skill])
                
                return skills_rating

            except Exception as e:
                logger.error({"****evaluate_group_discussion_conversation ": f"failed [outer] {model} for {3 - max_tries + 1} time", "error": e})
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                time.sleep(1)

        if is_evaluated:
            return skills_rating

    logger.info({"****evaluate_group_discussion_conversation ": "failed everything, so assigning default values"})

    # HACK in case everything fails; just evaluate as a random number
    response = {skill: random.randint(3, 7) for skill in cultural_skills}
    
    # send error on slack to debug this
    send_slack_message({"process": "evaluate_group_discussion_conversation",
                        "test_attempt_session": test_attempt_session.uid,
                        "error": "failed to evaluate; putting random value"})

    return response


@timeit
def evaluate_skills_group_discussion_conversation(test_attempt_session, conversation, user_persona, objective, skills_to_evaluate,test,is_free=False,model_order=['gemini','anthropic','gpt']):
    """
    It evaluates the normal skills rating for a scenario (group discussion)
    """
    skills_to_evaluate = skills_to_evaluate.split(',') if isinstance(
        skills_to_evaluate, str) else skills_to_evaluate

    if isinstance(skills_to_evaluate, list):
        skills_to_evaluate = [skill.strip() for skill in skills_to_evaluate][:8]

    # prompt = f'''
    # "Objective:" {objective};

    # "Conversation:" {conversation};

    # "REQUIRED FROM LLM:" Based on the above criteria please evaluate the "{user_persona}" on a scale of 0-10, with scores in increments of 0.5. Evaluate the conversation for the participant: "{user_persona}" and this "{user_persona}" only, in this conversation for each behaviour trait in this skills_list in JSON. 

    # "skills_list:" "{skills_to_evaluate}"

    # Please put properties of JSON enclosed in double quotes.

    # Example of JSON: {{"hierarchy": "9.5", "consensual": "4", "indirect negative feedback": "4.5", "relationship based": "6", "high context communication": "2.5", "Persuasion": "5", "argumentative": "10"}}

    # NOTE: Please Reply in a JSON format only and no other format will be accepted. NO OTHER TEXT SHOULD BE PRESENT IN THE REPLY OTHER THAN THE JSON. NO INTRUCTIONS SHOULD BE PRESENT IN THE REPLY OTHER THAN THE JSON.
    # '''

    # prompt = f'''
    # "Objective:" {objective};

    # "Conversation:" {conversation};

    # "REQUIRED FROM LLM:" Based on the above criteria please evaluate the "{user_persona}" on a scale of 0-10, with scores in increments of 0.5. Evaluate the conversation for the participant: "{user_persona}" and this "{user_persona}" only in this conversation for each behaviour trait in this skills_list in JSON in such a way that no two skills can have the exact same score.

    # "skills_list:" "{skills_to_evaluate}"

    # Please put properties of JSON enclosed in double quotes.

    # Example of JSON: {{"hierarchy": "9.5", "consensual": "4", "indirect negative feedback": "4.5", "relationship based": "6", "high context communication": "2.5", "Persuasion": "5", "argumentative": "10"}}

    # NOTE: Please Reply in a JSON format only and no other format will be accepted. NO OTHER TEXT SHOULD BE PRESENT IN THE REPLY OTHER THAN THE JSON. NO INTRUCTIONS SHOULD BE PRESENT IN THE REPLY OTHER THAN THE JSON.

    # NOTE: For the entire conversation no two skills from can have exact same scores.

    # NOTE: Do not add any English language sentence in the output.'''


    prompt = f'''
    \n\nHuman:
    "Objective:" {objective};
    "Conversation:" {conversation};

    "REQUIRED FROM LLM:" Based on the above criteria please evaluate the "{user_persona}" only from a scale of 1.5-9, with scores in increments of 0.5. Evaluate the conversation for the participant: "{user_persona}" and this "{user_persona}" only, in this conversation for each behaviour trait in this skills_list in JSON. 
    "skills_list:" "{skills_to_evaluate}"
    Please put properties of JSON enclosed in double quotes.
    Always evaluate only Skills which relevant to the above conversation.
    Example of JSON: {{"hierarchy": "9.5", "consensual": "4", "indirect negative feedback": "4.5", "relationship based": "6", "high context communication": "2.5", "Persuasion": "5", "argumentative": "10"}}
    NOTE: Please Reply in a JSON format only and no other format will be accepted. NO OTHER TEXT SHOULD BE PRESENT IN THE REPLY OTHER THAN THE JSON. NO INSTRUCTIONS SHOULD BE PRESENT IN THE REPLY OTHER THAN THE JSON.

    NOTE : Do not provide any kind of heading or introduction text in the output.
    \n\nAssistant:
    '''

    code_prompt = """
    \n\nHuman:
        "Objective:" ${objective}; 
        "Conversation:" ${conversation}; 
        "user_persona": ${user_persona};
        "skills_list:" "${skill_list}";

        "Evaluation Criteria:"

            - Relevance: Does the answer directly address the question?

            - Accuracy: Is the information in the answer correct?

            - Completeness: Does the answer provide a comprehensive response to the question?

            - Clarity: Is the answer well-written and easy to understand?
        

        "REQUIRED FROM LLM:" 
            - Based on the above criteria please evaluate the "{user_persona}" only from a scale of 0.5-9.5 for each skill listed in {skills_list}. Use decimal values for more precision (e.g., 4.2, 7.3).
            - Evaluate the conversation for the participant: "{user_persona}" and this "{user_persona}" only, in this conversation for each behaviour trait in this 'skills_list',ensuring that no two skills receive the same score.
            - Ensure that each skill is rated uniquely, with no repeated scores, must be from "{skills_list}".
            - Always evaluate only Skills within "{skills_list}".

        Strict Constraints:
        -   No two skills should have the same score.
        -   Do not modify the provided code or include any additional information in the output.
        -   NEVER PRINT ANYTHING ELSE EXCEPT THE PRINT OUTPUT.

        format_instructions = {
            "output_format": "word",
            "explanations": False,
            "word_counts": False
        }
        **Output in JSON format**:  Ensure that the output is formatted as valid JSON.
        import json
        from typing import Dict

        ScoreDictionary = Dict[str, float]
        final_scores: ScoreDictionary = {
        "skill": float(calulated score)
        }
        print(json.dumps(final_scores))
        \n\nAssistant:
    """

    prompt = Template(code_prompt).substitute(
        skill_list = skills_to_evaluate,
        user_persona = user_persona,
        conversation = conversation,
        objective = objective
    )

    if is_free:
        model_order = ['anthropic']

    skills_rating = None
    response = None
    is_evaluated = False
    
    for model in model_order:
        max_tries = 3
        while max_tries > 0:
            try:
                logger.info({f"****evaluate_skills_group_discussion_conversation ":
                             f"trying [outer] {model} for {3 - max_tries + 1} time"})
                
                if model == "anthropic":
                    response = anthropic_completion(prompt, len(skills_to_evaluate) * 100)
                elif model == "gemini":
                    response = gemini_completion(prompt)
                elif model == "gpt":
                    response = gpt3_completion(prompt, stop=["USER:", "CoachBot"]).text
                
                logger.info({f"****evaluate_skills_group_discussion_conversation ":
                             f"response [outer] {model} for {3 - max_tries + 1} time",
                             "response": response})
                
                skills_rating_str = json_extraction(response)
                skills_rating_json = json.loads(skills_rating_str)
                skills_rating = {}
                garbage_keywords = {s.strip().lower() for s in ['Overal', 'Performance', 'Total', 'Other', 'Top']}

                for skill, rating in skills_rating_json.items():
                    if skill.strip().lower() in garbage_keywords:
                        logger.info(f"Skill '{skill}' in {garbage_keywords}")
                        continue
                    skills_rating[skill] = float(rating)

                is_evaluated = True
                break
            except Exception as e:
                logger.error({f"****evaluate_skills_group_discussion_conversation ":
                              f"failed [outer] {model} for {3 - max_tries + 1} time",
                              "error": e})
                max_tries -= 1
                time.sleep(1)
                continue
        
        if is_evaluated:
            return skills_rating
    
    logger.info({"****evaluate_skills_group_discussion_conversation ": "failed everything, assigning default values"})
    response = {skill: random.randint(3, 7) for skill in skills_to_evaluate}
    
    send_slack_message({"process": "evaluate_skills_group_discussion_conversation",
                         "test_attempt_session": test_attempt_session.uid,
                         "error": "failed to evaluate; assigning random value"})
    
    return response


##########################* SKILLS EXPLANATION START *##########################

@timeit
def evaluate_skills_explanation(title, description, conversation, skills_rating, test_attempt_session):
    prompt = f'''
        \n\nHuman:
        "TITLE:" {title};

        "DESCRIPTION:" {description};

        "CONVERSATION:" {conversation};

        skills_list : {skills_rating}

        The skills rating of the responder based on the given conversation is given in skills_list. Provide a note explaining the reason behind the rating of each skill and ways the responder can improve these skills in 3-4 sentences.

        NOTE : The notes should be given for each skill and they should be in bullet points. Each point should always include one sentence that will help the responder improve these skills. Each skill explanation should have only one bullet point with the explanation and ways to improve.

        NOTE : The output should always be generated in this JSON format only. DO NOT create any sub bullets for any of the point.

        NOTE : Output format should be JSON example - {{ "Collaboration": "Scored 8.0 as the manager actively sought to collaborate by gathering input from team, thanking for diverse views, and aiming for mutually acceptable solutions. Could be more proactive in driving collaboration by directly inviting team members to jointly develop solutions and set goals."}}

        NOTE : Each skill explanation should have only one bullet point with a minimum of 60 words.

        NOTE : The minimum explanation length for each skill is 60 words. No skill explanation should EVER be less than 60 words.

        NOTE : Always(must) detect language of the TITLE only and provide explanation in same language.

        \n\nAssistant:
    '''

    

    ################################* gemini_completion ################################
    skills_explanation = None
    response = None
    max_tries = 3  # because gpt3_completion function itself retries 3 times
    is_evaluated = True

    while max_tries > 0:
        try:
            logger.info({"****evaluate_skills_explanation ":f"trying [outer] gemini_completion for {3 - max_tries + 1} time"})
            response = gemini_completion(prompt)
            logger.info({"****evaluate_skills_explanation ":f"response [outer] gemini_completion for {3 - max_tries + 1} time","response":response})
            
            skills_explanation = json_extractor_for_explaination(response)
            # skills_explanation = json.loads(skills_explanation)
            if len(skills_explanation.keys()) != len(skills_rating.keys()):
                raise ValueError("skills count didn't matched")

            break

        except Exception as e:
            logger.error({"****evaluate_skills_explanation ":f"failed [outer] gemini_completion for {3 - max_tries + 1} time","error":e })
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return skills_explanation

    ################################* gemini_completion end ################################

    logger.info({"****evaluate_skills_explanation ":f"failed gemini_completion, so trying anthropic_completion"})

    ################################* anthropic ################################
    skills_explanation = None
    response = None
    is_evaluated = True
    max_tries = 3  # because anthropic_completion function itself retries 3 times

    while max_tries > 0:
        try:
            logger.info({"****evaluate_skills_explanation ":f"trying [outer] anthropic for {3 - max_tries + 1} time"})
            response = anthropic_completion(
                prompt, len(skills_rating) * 100)
            logger.info({"****evaluate_skills_explanation ":f"response [outer] anthropic for {3 - max_tries + 1} time","response":response})
            

            skills_explanation = json_extractor_for_explaination(response)
            # skills_explanation = json.loads(skills_explanation)
            if len(skills_explanation.keys()) != len(skills_rating.keys()):
                raise ValueError("skills count didn't matched")
            
            break
        except Exception as e:
            logger.error({"****evaluate_skills_explanation ":f"failed [outer] anthropic for {3 - max_tries + 1} time","error":e})
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return skills_explanation

    ################################* anthropic end ################################

    logger.info({"****evaluate_skills_explanation ":f"failed anthropic, so trying gpt"})

    ################################* gpt ################################
    skills_explanation = None
    response = None
    max_tries = 3  # because gpt3_completion function itself retries 3 times
    is_evaluated = True

    while max_tries > 0:
        try:
            logger.info({"****evaluate_skills_explanation ":f"trying [outer] gpt for {3 - max_tries + 1} time"})
            response = gpt3_completion(prompt, stop=["USER:", "CoachBot"]).text
            logger.info({"****evaluate_skills_explanation ":f"response [outer] gpt for {3 - max_tries + 1} time","response":response})
            
            skills_explanation = json_extractor_for_explaination(response)
            # skills_explanation = json.loads(skills_explanation)
            if len(skills_explanation.keys()) != len(skills_rating.keys()):
                raise ValueError("skills count didn't matched")

            break

        except Exception as e:
            logger.error({"****evaluate_skills_explanation ":f"failed [outer] gpt for {3 - max_tries + 1} time","error":e })
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return skills_explanation

    ################################* gpt end ################################



    return {}



@timeit
def evaluate_culture_skills_explanation(title, description, conversation, culture_skills_rating, test_attempt_session):
    prompt = f'''
        \n\nHuman:
        "TITLE:" {title};

        "DESCRIPTION:" {description};

        "CONVERSATION:" {conversation};

        cultural_list :  {culture_skills_rating}

        The cultural skills rating of the responder based on the given conversation is given in cultural_list. Provide a note explaining the reason behind the rating of each culture skill based on the given scenario in 3-4 sentences. Based on the given context provide an idea in which conditions the scores are likely to be higher AND in which conditions scores are likely to be lower. Each point should always provide both cases where scores can be higher or lower based on the given scenario.

        NOTE : The notes should be given for each cultural skill and they should be in bullet points.

        NOTE : The output should always be generated in this JSON format only. DO NOT create any sub bullets for any of the point.
        NOTE : Output format be in JSON example - {{"Consensual": "Scored 7.5 as the conversation shows empathy and respect for boundaries. It could be potentially rated higher if proactively seeking consensus on action plans. It could potentially be rated lower, if the conversation comes across straightforward interactions."}}


        NOTE : Each skill explanation should have only one bullet point with a minimum of 60 words.

        NOTE : The minimum explanation length for each skill is 60 words. No skill explanation should EVER be less than 60 words.
        
        NOTE : Always(must) detect language of the  TITLE only and provide explanation in same language.
        \n\nAssistant:
        '''

    

    ################################* gemini_completion ################################
    skills_explanation = None
    response = None
    max_tries = 3  # because gpt3_completion function itself retries 3 times
    is_evaluated = True

    while max_tries > 0:
        try:
            logger.info({"****evaluate_culture_skills_explanation ":f"trying [outer] gemini_completion for {3 - max_tries + 1} time"})
            response = gemini_completion(prompt)
            logger.info({"****evaluate_culture_skills_explanation ":f"response [outer] gemini_completion for {3 - max_tries + 1} time","response":response})
            
            skills_explanation = json_extractor_for_explaination(response)
            # skills_explanation = json.loads(skills_explanation)
            if len(skills_explanation.keys()) != len(culture_skills_rating.keys()):
                raise ValueError("skills count didn't matched")
            
            break

        except Exception as e:
            logger.error({"****evaluate_culture_skills_explanation ":f"failed [outer] gemini_completion for {3 - max_tries + 1} time","error":e })
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return skills_explanation

    ################################* gemini_completion end ################################

    logger.info({"****evaluate_culture_skills_explanation ":f"failed gemini_completion, so trying anthropic_completion"})

    ################################* anthropic ################################
    skills_explanation = None
    response = None
    is_evaluated = True
    max_tries = 3  # because anthropic_completion function itself retries 3 times

    while max_tries > 0:
        try:
            logger.info({"****evaluate_culture_skills_explanation ":f"trying [outer] anthropic for {3 - max_tries + 1} time"})
            response = anthropic_completion(
                prompt, len(culture_skills_rating) * 100)
            logger.info({"****evaluate_culture_skills_explanation ":f"response [outer] anthropic for {3 - max_tries + 1} time","response":response})
            

            skills_explanation = json_extractor_for_explaination(response)
            # skills_explanation = json.loads(skills_explanation)
            if len(skills_explanation.keys()) != len(culture_skills_rating.keys()):
                raise ValueError("skills count didn't matched")
            
            break
        except Exception as e:
            logger.error({"****evaluate_culture_skills_explanation ":f"failed [outer] anthropic for {3 - max_tries + 1} time","error":e})
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return skills_explanation

    ################################* anthropic end ################################

    logger.info({"****evaluate_culture_skills_explanation ":f"failed anthropic, so trying gpt"})

    ################################* gpt ################################
    skills_explanation = None
    response = None
    max_tries = 3  # because gpt3_completion function itself retries 3 times
    is_evaluated = True

    while max_tries > 0:
        try:
            logger.info({"****evaluate_culture_skills_explanation ":f"trying [outer] gpt for {3 - max_tries + 1} time"})
            response = gpt3_completion(prompt, stop=["USER:", "CoachBot"]).text
            logger.info({"****evaluate_culture_skills_explanation ":f"response [outer] gpt for {3 - max_tries + 1} time","response":response})
            
            skills_explanation = json_extractor_for_explaination(response)
            # skills_explanation = json.loads(skills_explanation)
            if len(skills_explanation.keys()) != len(culture_skills_rating.keys()):
                raise ValueError("skills count didn't matched")

            break

        except Exception as e:
            logger.error({"****evaluate_culture_skills_explanation ":f"failed [outer] gpt for {3 - max_tries + 1} time","error":e })
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return skills_explanation

    ################################* gpt end ################################


    return {}


@timeit
def evaluate_skills_explanation_conversation(objective, conversation, user_persona, skills_rating, test_attempt_session):
    prompt = f'''
        \n\nHuman:
        "Objective:" {objective};

        "Conversation:" {conversation};
        skills_list: {skills_rating}
        The skills rating of {user_persona} based on the given conversation is given in skills_list. Provide a note explaining the reason behind the rating of each skill and ways the responder can improve these skills in 3-4 sentences.
        NOTE : The notes should be given for each skill and they should be in bullet points. Each point should always include one sentence that will help the responder improve these skills. Each skill explanation should have only one bullet point with the explanation and ways to improve.
        NOTE : The output should always be generated in this JSON format only. DO NOT create any sub bullets for any of the point.
        NOTE : Output format should be Json example - {{"Collaboration": "Scored 8.0 as the manager actively sought to collaborate by gathering input from the team, thanking for diverse views, and aiming for mutually acceptable solutions. Could be more proactive in driving collaboration by directly inviting team members to jointly develop solutions and set goals."}}
        NOTE : Each skill explanation should have only one bullet point with a minimum of 60 words.
        NOTE : The minimum explanation length for each skill is 60 words. No skill explanation should EVER be less than 60 words.
        NOTE : Always(must) detect language of the Objective only and provide explanation in same language.

        \n\nAssistant:
    '''


    ################################* gemini_completion ################################
    skills_explanation = None
    response = None
    max_tries = 3  # because gpt3_completion function itself retries 3 times
    is_evaluated = True

    while max_tries > 0:
        try:
            logger.info({"****evaluate_skills_explanation_conversation ":f"trying [outer] gemini_completion for {3 - max_tries + 1} time"})
            response = gemini_completion(prompt)
            logger.info({"****evaluate_skills_explanation_conversation ":f"response [outer] gemini_completion for {3 - max_tries + 1} time","response":response})
            
            skills_explanation = json_extractor_for_explaination(response)
            # skills_explanation = json.loads(skills_explanation)
            if len(skills_explanation.keys()) != len(skills_rating.keys()):
                raise ValueError("skills count didn't matched")

            break

        except Exception as e:
            logger.error({"****evaluate_skills_explanation_conversation ":f"failed [outer] gemini_completion for {3 - max_tries + 1} time","error":e })
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return skills_explanation

    ################################* gemini_completion end ################################

    logger.info({"****evaluate_skills_explanation_conversation ":f"failed gemini_completion, so trying anthropic_completion"})

    ################################* anthropic ################################
    skills_explanation = None
    response = None
    is_evaluated = True
    max_tries = 3  # because anthropic_completion function itself retries 3 times

    while max_tries > 0:
        try:
            logger.info({"****evaluate_skills_explanation_conversation ":f"trying [outer] anthropic for {3 - max_tries + 1} time"})
            response = anthropic_completion(
                prompt, len(skills_rating) * 100)
            logger.info({"****evaluate_skills_explanation_conversation ":f"response [outer] anthropic for {3 - max_tries + 1} time","response":response})
            

            skills_explanation = json_extractor_for_explaination(response)
            # skills_explanation = json.loads(skills_explanation)
            if len(skills_explanation.keys()) != len(skills_rating.keys()):
                raise ValueError("skills count didn't matched")
            
            break
        except Exception as e:
            logger.error({"****evaluate_skills_explanation_conversation ":f"failed [outer] anthropic for {3 - max_tries + 1} time","error":e})
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return skills_explanation

    ################################* anthropic end ################################

    logger.info({"****evaluate_skills_explanation_conversation ":f"failed anthropic, so trying gpt"})

    ################################* gpt ################################
    skills_explanation = None
    response = None
    max_tries = 3  # because gpt3_completion function itself retries 3 times
    is_evaluated = True

    while max_tries > 0:
        try:
            logger.info({"****evaluate_skills_explanation_conversation ":f"trying [outer] gpt for {3 - max_tries + 1} time"})
            response = gpt3_completion(prompt, stop=["USER:", "CoachBot"]).text
            logger.info({"****evaluate_skills_explanation_conversation ":f"response [outer] gpt for {3 - max_tries + 1} time","response":response})
            
            skills_explanation = json_extractor_for_explaination(response)
            # skills_explanation = json.loads(skills_explanation)
            if len(skills_explanation.keys()) != len(skills_rating.keys()):
                raise ValueError("skills count didn't matched")

            break

        except Exception as e:
            logger.error({"****evaluate_skills_explanation_conversation ":f"failed [outer] gpt for {3 - max_tries + 1} time","error":e })
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return skills_explanation

    ################################* gpt end ################################


    return {}


@timeit
def evaluate_culture_skills_explanation_conversation(objective, conversation, user_persona, culture_skills_rating, test_attempt_session):
    prompt = f'''
        \n\nHuman:
        Culture skills explanation orchestrated 

        "Objective:" {objective}; 

        "Conversation:" {conversation}; 

        cultural_list : {culture_skills_rating}

        The cultural skills rating of {user_persona} based on the given conversation is given in cultural_list. Provide a note explaining the reason behind the rating of each culture skill based on the given scenario in 3-4 sentences. Based on the given context provide an idea in which conditions the scores are likely to be higher AND in which conditions scores are likely to be lower. Each point should always provide both cases where scores can be higher or lower based on the given scenario.

        NOTE : The notes should be given for each cultural skill and they should be in bullet points.

        NOTE : The output should always be generated in this JSON format only. DO NOT create any sub bullets for any of the point.

        NOTE : Output format should be in JSON example - {{"Consensual": "Scored 7.5 as the conversation shows empathy and respect for boundaries. It could be potentially rated higher if proactively seeking consensus on action plans. It could potentially be rated lower, if the conversation comes across straightforward interactions."}}

        NOTE : Each skill explanation should have only one bullet point with a minimum of 60 words.

        NOTE : The minimum explanation length for each skill is 60 words. No skill explanation should EVER be less than 60 words.
        NOTE : Always(must) detect language of the Objective only and provide explanation in same language.
        \n\nAssistant:
    '''


    ######################################* gemini_completion *######################################
    skills_explanation = None
    response = None
    max_tries = 3  # because gpt3_completion function itself retries 3 times
    is_evaluated = True

    while max_tries > 0:
        try:
            logger.info({"**** evaluate_culture_skills_explanation_conversation ":f"trying [outer] gemini_completion for {3 - max_tries + 1} time"})
            response = gemini_completion(prompt)
            logger.info({"**** evaluate_culture_skills_explanation_conversation ":f"response [outer] gemini_completion for {3 - max_tries + 1} time","response":response})
            
            skills_explanation = json_extractor_for_explaination(response)
            # skills_explanation = json.loads(skills_explanation)
            if len(skills_explanation.keys()) != len(culture_skills_rating.keys()):
                raise ValueError("skills count didn't matched")

            break

        except Exception as e:
            logger.error({"**** evaluate_culture_skills_explanation_conversation ":f"failed [outer] gemini_completion for {3 - max_tries + 1} time","error":e })
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return skills_explanation

    ######################################* gemini_completion end *######################################

    logger.info({"**** evaluate_culture_skills_explanation_conversation ":f"failed gemini_completion, so trying anthropic_completion"})

    ######################################* anthropic *######################################
    skills_explanation = None
    response = None
    is_evaluated = True
    max_tries = 3  # because anthropic_completion function itself retries 3 times

    while max_tries > 0:
        try:
            logger.info({"**** evaluate_culture_skills_explanation_conversation ":f"trying [outer] anthropic for {3 - max_tries + 1} time"})
            response = anthropic_completion(
                prompt, len(culture_skills_rating) * 100)
            logger.info({"**** evaluate_culture_skills_explanation_conversation ":f"response [outer] anthropic for {3 - max_tries + 1} time","response":response})
            

            skills_explanation = json_extractor_for_explaination(response)
            # skills_explanation = json.loads(skills_explanation)
            if len(skills_explanation.keys()) != len(culture_skills_rating.keys()):
                raise ValueError("skills count didn't matched")
            
            break
        except Exception as e:
            logger.error({"**** evaluate_culture_skills_explanation_conversation ":f"failed [outer] anthropic for {3 - max_tries + 1} time","error":e})
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return skills_explanation

    ######################################* anthropic end *######################################

    logger.info({"**** evaluate_culture_skills_explanation_conversation ":f"failed gpt, so trying text-bison"})

    ######################################* gpt *######################################
    skills_explanation = None
    response = None
    max_tries = 3  # because gpt3_completion function itself retries 3 times
    is_evaluated = True

    while max_tries > 0:
        try:
            logger.info({"**** evaluate_culture_skills_explanation_conversation ":f"trying [outer] gpt for {3 - max_tries + 1} time"})
            response = gpt3_completion(prompt, stop=["USER:", "CoachBot"]).text
            logger.info({"**** evaluate_culture_skills_explanation_conversation ":f"response [outer] gpt for {3 - max_tries + 1} time","response":response})
            
            skills_explanation = json_extractor_for_explaination(response)
            # skills_explanation = json.loads(skills_explanation)
            if len(skills_explanation.keys()) != len(culture_skills_rating.keys()):
                raise ValueError("skills count didn't matched")

            break

        except Exception as e:
            logger.error({"****  evaluate_culture_skills_explanation_conversation ":f"failed [outer] gpt for {3 - max_tries + 1} time","error":e })
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return skills_explanation

    ######################################* gpt end *######################################


    return {}


##########################* SKILLS EXPLANATION END *##########################

@timeit
def top_N_leadership_board(skills, N, tenant_id):
    """
    This function generates a leadership board for the top N participants based on their average skill ratings.

    The function first fetches all the `SkillsRating` objects for a given tenant. It then iterates over these objects, 
    and for each object, it fetches the corresponding `User` object (if it exists and is not excluded). 

    The function then calculates the average score for the skills specified in the `skills` parameter. If 'all' is passed 
    in the `skills` list, it calculates the average score for all the skills. The average score and other details are 
    then appended to the `participants` list.

    Finally, the function sorts the `participants` list in descending order of the average score and returns the top N 
    participants.

    Parameters:
    skills (list): A list of skills to consider for the average score calculation. If ['all'] is passed, all skills are considered.
    N (int): The number of top participants to return.
    tenant_id (str): The tenant_id to filter the `SkillsRating` objects.

    Returns:
    list: A list of dictionaries, where each dictionary contains the following keys:
        - participant_id: The id of the participant.
        - name: The display name of the participant.
        - total_questions_attempted: The total number of questions attempted by the participant.
        - total_tests_attempted: The total number of tests attempted by the participant.
        - average_score: The average score of the participant for the specified skills.
        - skills_info: A dictionary containing the skill ratings of the participant for the specified skills.

    Example:
    >>> top_N_leadership_board(['math', 'science'], 5, 'tenant1')
    [
        {
            'participant_id': 'user1',
            'name': 'John Doe',
            'total_questions_attempted': 50,
            'total_tests_attempted': 5,
            'average_score': 85.0,
            'skills_info': {'math': {'average_score': 90.0, 'total_questions': 30}, 'science': {'average_score': 80.0, 'total_questions': 20}}
        },
        ...
    ]
    """
    # Get all skills_rating objects of this tenant
    skill_rating_objects = SkillsRating.objects.filter(
        deleted=0,
        tenant_id=tenant_id
    )

    participants = []

    original_skills_required = skills

    for obj in skill_rating_objects:

        user = User.objects.filter(uid=obj.participant_id,is_excluded=0)

        if user:
            skills_info = obj.skills_info
            average_score = 0
            skills_dict = {}
            skills_to_search = original_skills_required

            if len(skills_to_search) == 1 and skills_to_search[0].lower() == 'all':
                skills_to_search = skills_info.keys()

            for skill in skills_to_search:
                if skill in skills_info:
                    average_score += skills_info[skill]['average_score']
                    skills_dict[skill] = skills_info[skill]

            participants.append({
                "participant_id": obj.participant_id,
                "name": get_user_display_name(User.objects.get(uid=obj.participant_id)),
                "total_questions_attempted": obj.total_questions_attempted,
                "total_tests_attempted": obj.total_tests_attempted,
                "average_score": average_score,
                "skills_info": skills_dict
            })

    # sort participants based on the sum of average_score of skills in skills list from the skills_info dictionary in skills_rating object
    participants = sorted(
        participants, key=lambda x: x['average_score'], reverse=True)

    return participants[:N]


@timeit
def get_participant_info(participant: User):
    """
    This function retrieves and returns detailed information about a participant.

    The function first queries the SkillsRating model to get the participant's skills information, total questions attempted, and total tests attempted. It then uses the get_user_display_name function to get the participant's display name. All this information is then packaged into a dictionary and returned.

    Args:
        participant (User): The User object for which information is to be retrieved. The User object should have a 'uid' attribute which is used to filter the SkillsRating objects.

    Returns:
        dict: A dictionary containing the following keys:
            - 'name': The display name of the user. This is obtained by calling the get_user_display_name function with the User object.
            - 'role': The role of the user, obtained directly from the User object.
            - 'skills_info': A dictionary containing the skills information of the user. If no skills information is found, an empty dictionary is returned.
            - 'total_questions_attempted': The total number of questions attempted by the user. If this information is not found, 0 is returned.
            - 'total_tests_attempted': The total number of tests attempted by the user. If this information is not found, 0 is returned.

    Example:
        >>> user = User.objects.get(uid='some-uid')
        >>> get_participant_info(user)
        {
            'name': 'John Doe',
            'role': 'admin',
            'skills_info': {'python': 5, 'java': 4},
            'total_questions_attempted': 50,
            'total_tests_attempted': 10
        }
    """
    participant_skill_rating_object = SkillsRating.objects.filter(
        deleted=0,
        participant_id=participant.uid
    ).values(
        'skills_info',
        'total_questions_attempted',
        'total_tests_attempted'
    )

    logger.info(f"participant_skill_rating obj : {participant_skill_rating_object}")
    skill_info = participant_skill_rating_object[0].get('skills_info', {}) if len(participant_skill_rating_object) > 0 else {}
    
    for skill_key in skill_info:
        score = skill_info[skill_key].get('score')
        if isinstance(score, (int, float)):
            # Keep original value but format to one decimal as a string
            skill_info[skill_key]['score'] = "{:.1f}".format(score)

    participant_info = {
        "name": get_user_display_name(participant),
        "role": participant.role,
        "skills_info": skill_info,
        "total_questions_attempted": participant_skill_rating_object[0].get('total_questions_attempted', 0) if len(participant_skill_rating_object)>0 else 0,
        "total_tests_attempted": participant_skill_rating_object[0].get('total_tests_attempted', 0) if len(participant_skill_rating_object)>0 else 0
    }

    return participant_info


@timeit
def get_top_participant_skills(skills, q_set, top_n=10):
    """
    This function retrieves the top participants based on their skills from a given queryset.

    The function first checks if the skills are provided as a string and splits them into a list if necessary. 
    It then filters the queryset for entries that are not deleted and have any of the specified skills. 
    The filtered queryset is then ordered by the average score of each skill in descending order. 
    The function finally returns the top 'n' participants based on this ordering.

    Parameters:
    skills (str or list): A string of skills separated by commas or a list of skills. 
                          Each skill is a string representing the skill name.
    q_set (QuerySet): A Django QuerySet from which to retrieve the participants.
    top_n (int, optional): The number of top participants to return. Defaults to 10.

    Returns:
    QuerySet: A QuerySet containing the top 'n' participants based on their skill average scores. 
              Each entry in the QuerySet is a dictionary with details of a participant.

    Example:
    >>> get_top_participant_skills('skill1,skill2', User.objects.all(), 5)
    <QuerySet [{'id': 1, 'name': 'User1', 'skills_info': {'skill1': {'average_score': 4.5}, 'skill2': {'average_score': 4.0}}}, ...]>
    """
    
    skills = skills.split(",") if isinstance(skills, str) else skills
    top_participant_skills = q_set.filter(
        deleted=0,
        skills_info__has_any_keys=skills
    ).order_by(
        # sum of average scores for each skill in skills list
        *[f'-skills_info__{skill}__average_score' for skill in skills]
    )[:top_n]

    return top_participant_skills


@timeit
def save_the_custom_rating(custom_rating, custom_rating_object):
    """
    To save custom rating to database
    """
    custom_rating_object.custom_rating = custom_rating
    custom_rating_object.save()


@timeit
def upsert_into_skill_index(tenant_id: str,
                            skills: list):
    """
    saving skills into skillIndex table"
    """
    if not skills:
        return

    for skill in skills:
        if not slugify(skill):
            continue

        SkillIndex.objects.get_or_create(tenant_id=tenant_id,
                                         name=skill,
                                         defaults=dict(display=skill))

def test_for_ratings():
    company_context = '''The company is using this simulation for their critical hires - to assess them if they will be really fitting to the culture and context of " Customer First" and "Overcommunicating" to keep things moving and transparent.'''

    company_context = ''' The company is using this simulation for their critical hires - to assess them if they will be really fitting to the culture and context of \" Customer First\" and \"Overcommunicating\" to keep things moving and transparent.Like in a power plant crisis situation should be over-communicating and putting the customer's interest first. '''
    company_context = None
    code_prompt = """
     \n\nHuman:
        "TITLE:" ${title};

        "DESCRIPTION:" ${description};

        "CONVERSATION:" ${conversation};

        "skills" : ${skills_list}

        "Evaluation Criteria:"

        - Relevance: Does the answer directly address the question?

        - Accuracy: Is the information in the answer correct?

        - Completeness: Does the answer provide a comprehensive response to the question?

        - Clarity: Is the answer well-written and easy to understand?

        REQUIRED FROM LLM:
        - Always consider the Title, Description, and Conversation when rating the skills. Evaluate each skill based on the criteria provided, ensuring a comprehensive and holistic analysis.
        - Assign a unique score between 0.5 and 9.5 for each skill listed in {skills}, ensuring that no two skills receive the same score. Use decimal values for more precision (e.g., 4.2, 7.3).
        - Ensure that each skill is rated uniquely, with no repeated scores.

        Strict Constraints:
        -   No two skills should have the same score.
        -   Do not modify the provided code or include any additional information in the output.
        -   NEVER PRINT ANYTHING ELSE EXCEPT THE PRINT OUTPUT.

        format_instructions = {
            "output_format": "word",
            "explanations": False,
            "word_counts": False
        }
        **Output in JSON format**:  Ensure that the output is formatted as valid JSON.
        import json
        from typing import Dict

        ScoreDictionary = Dict[str, float]
        final_scores: ScoreDictionary = {
        "skill": float(calulated score)
        }

        print(final_scores)

        \n\nAssistant:
    """

    code_prompt_culture = """
    \n\nHuman:
        "TITLE:" ${title};

        "DESCRIPTION:" ${description};

        "CONVERSATION:" ${conversation};

        "cultural_list:" ${skills_list}


        "Evaluation Criteria:"
            - Need for Structure: Does the conversation display a need for structure? Assesses the individual's preference for clear rules, procedures, and predictability versus ambiguity and flexibility.
            - Orientation towards Authority: Does the conversation display orientation towards authority? Measures the individual's inherent approach to authority—respectful deference, active engagement, or challenging/resisting.
            - Emphasis on Relationships: Does the conversation display emphasis on relationship?  Assesses the extent to which the individual prioritizes building and maintaining relationships versus focusing solely on tasks and outcomes.
            - Direct Communication Style: How direct is the communication style displayed here in the conversation? While the manifestation of communication style will vary, the underlying preference for direct versus indirect communication tends to be more consistent.
            - Long term focus: Does the conversation display long term focus? Assesses whether the individual's focus is primarily on immediate gratification or on long-term planning and future goals.
            - Value Placed on Independence: Does the conversation display need for independence? Measures the individual's inherent preference for autonomy and self-reliance versus interdependence and collaboration.
            - Propensity for Risk-Taking: Does the conversation display high-risk or low risk-taking style? Captures the individual's inherent inclination toward risk—high tolerance versus strong aversion.

        "REQUIRED FROM LLM:" 
        - Always consider the Title, Description, and Conversation when rating the skills. Evaluate each skill based on the criteria provided, ensuring a comprehensive and holistic analysis. Use decimal values for more precision (e.g., 4.2, 7.3).
        - Assign a unique score between 0.5 and 9.5 for each skill listed in {cultural_list}, ensuring that no two skills receive the same score.
        - Ensure that each skill is rated uniquely, with no repeated scores.

        Strict Constraints:
        -   No two skills should have the same score.
        -   Do not modify the provided code or include any additional information in the output.
        -   NEVER PRINT ANYTHING ELSE EXCEPT THE PRINT OUTPUT.

        format_instructions = {
            "output_format": "word",
            "explanations": False,
            "word_counts": False
        }
        **Output in JSON format**:  Ensure that the output is formatted as valid JSON.
        import json
        from typing import Dict

        ScoreDictionary = Dict[str, float]
        final_scores: ScoreDictionary = {
        "skill": float(calulated score)
        }
        print(json.dumps(final_scores))
       \n\nAssistant:
    """

    
    from tests.models import Test, TestQuestionResponse, TestQuestion
    # from commons.deepseek import deepseek_completion
    test = Test.objects.get(uid='d1bcb9eb-2574-49cb-a24c-a9e371433386')

    conversation = ""
    count = 1
    responses = TestQuestionResponse.objects.filter(test_attempt_session_id="b5bd2666-5977-4352-b15c-f164897ddeed")

    for response in responses:

        question = TestQuestion.objects.get(
            uid=response.question_id)

        question_text = question.question
        response_text = response.response_text

        conversation += f"{count}. [Question:] {question_text}\n"
        if not question.is_view_only:
            conversation += f"[Answer:] {response_text}\n\n"

        count += 1

    cultural_skills = [
            "Need for Structure",
            "Orientation towards Authority",
            "Emphasis on Relationships",
            "Propensity for Risk-Taking",
            "Direct Communication Style",
            "Long term focus",
            "Value Placed on Independence"
        ]
    prompt = Template(code_prompt_culture).substitute(
        title=test.title,
        description = test.description,
        conversation = conversation,
        skills_list = cultural_skills
    )

    feedback_prompt = """\n\nHuman:
                Title: ${test_title}. 
                Test Description: ${test_description}
                Customer question:  ${question} 
                Expert Suggestions:  ${question_context} 
                Candidate answer:  ${candidate_reply}
                CompanyContext: ${company_context}
        
                Please provide communication and subject matter feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on "Expert suggestions",  "Title" , CompanyContext,only if they are relevant to the situation. The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the responder. 
                The feedback should be structured in the following format:
                                    Key Insights: "Output text"
                                    What went well: Output text"
                                    What did not work: Output text"
                                    Sample Candidate Answer : "Output text"
                                    Counter Intuitive Insight :  "Output text"

                \n\nAssistant:
"""

    oldfeedback = """
    \n\nHuman:
                Title: ${test_title}. 
                Test Description: ${test_description}
                Customer question:  ${question} 
                Expert Suggestions:  ${question_context} 
                Candidate answer:  ${candidate_reply}
        
                Please provide communication and subject matter feedback for a candidate who has provided a "Candidate answer" as specified for the "Question". Feedback must be based on "Expert suggestions",  "Title" , only if they are relevant to the situation. The feedback should include whether right questions are asked for engagement. Please provide feedback which specifically help enhance people skills of the responder. 
The feedback should be structured in the following format:
                    Key Insights: "Output text"
                    What went well: Output text"
                    What did not work: Output text"
                    Sample Candidate Answer : "Output text"
                    Counter Intuitive Insight :  "Output text"

                \n\nAssistant:
"""


    # prompt = Template(oldfeedback).substitute(
    #     test_title=test.title,
    #     description = test.description,
    #     conversation = conversation,
    #     skills_list = test.skills_to_evaluate,
    #     company_context = company_context
    # )
    data = f"""
    Title: {test.title}
    Description: {test.description}
    conversation: {conversation}
    """
    print(data)
    result = []
    for _ in range(3):
        temp = {}
        # temp['o1'] = gpt3_completion(prompt=prompt,engine='o1',stop=['User','Coachbots'])
        # temp['gpt4-turbo'] = gpt3_completion(prompt=prompt,stop=['User','Coachbots']).text
        # temp['gpt-4o'] = gpt3_completion(prompt=prompt,engine='gpt-4o',stop=['User','Coachbots']).text
        # temp['gpt-4o-mini'] = gpt3_completion(prompt=prompt,engine='gpt-4o-mini',stop=['User','Coachbots']).text
        # temp['o1-mini'] = gpt3_completion(prompt=prompt,engine='o1-mini',stop=['User','Coachbots']).text
        # temp['o3-mini'] = gpt3_completion(prompt=prompt,engine='o3-mini',stop=['User','Coachbots']).text
        # temp['haiku'] = anthropic_completion(prompt, 4000, temp=0)
        # temp['claude-3-5-sonnet-20241022'] = anthropic_completion(prompt, 4000, models="claude-3-5-sonnet-20241022",temp=0)
        # temp['claude-3-opus-20240229'] = anthropic_completion(prompt, 4000, models="claude-3-opus-20240229",temp=0)
        # temp['claude-3-sonnet-20240229'] = anthropic_completion(prompt, 4000, models="claude-3-sonnet-20240229",temp=0)
        # temp['claude-3-haiku-20240307'] = anthropic_completion(prompt, 4000, models="claude-3-haiku-20240307",temp=0)
        temp['gemini_flash'] = json.loads(json_extraction(gemini_completion(prompt=prompt,models=['gemini-1.5-flash-001'])))
        # temp['gemini_1.5PRO'] = gemini_completion(prompt=prompt,models=['gemini-1.5-pro-001'],temperature=0)
        # temp['deepseek'] = deepseek_completion(prompt)
        # temp['gemini-2.0-flash-exp'] = gemini_completion(prompt=prompt,models=['gemini-2.0-flash-exp'],temperature=0)
        result.append(temp)

    print(result)

def categorize_skill_scores(skills, leaderboard):
    # Extract skill names
    skill_names = [skill["skill"] for skill in skills]

    # Initialize result dictionary
    result = {skill: {"1-5": 0, "6-8": 0, "9-10": 0} for skill in skill_names}

    # Categorize scores per skill
    for user in leaderboard:
        scores = user.get("scores", {})
        for skill in skill_names:
            if skill in scores:
                score = scores[skill]
                if 1 <= score <= 5:
                    result[skill]["1-5"] += 1
                elif 6 <= score <= 8:
                    result[skill]["6-8"] += 1
                elif 9 <= score <= 10:
                    result[skill]["9-10"] += 1
    

    return result

def evaluate_skills_data_client(client_users, tenant_id):
    try:
           
            user_emails = client_users.member_emails
            client_list = list(user_emails.split(","))
            skill_data = {}

            user_identities = Identity.objects.filter(
                tenant_id=tenant_id,
                identity_type="deepchat_unique_id",
                value__in=client_list,
                deleted=False
            )

            user_ids = list(user_identities.values_list('user_id', flat=True))
            users = User.objects.filter(
                tenant_id=tenant_id,
                uid__in=user_ids,
                deleted=False
            )

            user_leaderboard = []
            user_score_distribution = {
                "1-5": 0,
                "5-8": 0,
                "8-10": 0
            }

            for user in users:
                total_score = 0
                total_skills = 0
                total_skills_score = {}

                user_email = user_identities.filter(user_id=user.uid).values_list("value", flat=True).first()
                user_ratings = SkillsRating.objects.filter(participant_id=user.uid)

                for rating in user_ratings:
                    skill_dict = rating.skills_info
                    if not skill_dict:
                        continue

                    for skill_name, details in skill_dict.items():
                        avg_score = details.get("average_score", 0)
                        total_skills_score[skill_name] = avg_score
                        

                        if skill_name not in skill_data:
                            skill_data[skill_name] = {
                                "scores": []
                            }

                        skill_data[skill_name]["scores"].append(avg_score)
                        total_score += avg_score
                        total_skills += 1

                if total_skills:
                    user_avg = round(total_score / total_skills, 2)
                    user_leaderboard.append({
                        "user_id": str(user.uid),
                        "email": user_email,
                        "scores": total_skills_score,
                    })

                    if 1 <= user_avg <= 5:
                        user_score_distribution["1-5"] += 1
                    elif 5 < user_avg <= 8:
                        user_score_distribution["5-8"] += 1
                    elif 8 < user_avg <= 10:
                        user_score_distribution["8-10"] += 1

            
            # user_leaderboard.sort(key=lambda x: x["average_score"], reverse=True)

            response_skills = []
            for skill, data in skill_data.items():
                scores = data["scores"]
                avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0

                response_skills.append({
                    "skill": skill,
                    "average_score": avg_score
                })

            skill_category_distribution = categorize_skill_scores(response_skills, user_leaderboard)

            return {
                "client_users": client_list,
                "skills": response_skills,
                "leaderboard": user_leaderboard,
                "user_score_distribution": user_score_distribution,
                "skill_category_distribution": skill_category_distribution
            }
    except Exception as e:
        logger.exception(f"Error in evaluate_skills_data_client: {e}")
        return {
            "error": str(e),
            "message": "Failed to evaluate skills data for client users."
        }
    
def evaluate_culture_skills_data_client(client_users, tenant_id):
    try:
            user_emails = client_users.member_emails
            client_list = list(user_emails.split(","))
            skill_data = {}
        

            user_id = Identity.objects.filter(
            tenant_id=tenant_id,
            identity_type="deepchat_unique_id",
            value__in = client_list,
            deleted=0
            )

            user_ids = list(user_id.values_list('user_id', flat=True))
            users = User.objects.filter(
                tenant_id=tenant_id,    
                uid__in=user_ids,
                deleted=0
            )
            print(user_ids)

            user_leaderboard = []
            user_skill_info = {}

            user_score_distribution = {
                "1-5": 0,
                "5-8": 0,
                "8-10": 0
            }

            for user in users:
                total_score = 0
                total_skills = 0
                temp_user_skill_info = {}
                culture_score_distribution = {}

                test_attempt_sessions = TestAttemptSession.objects.filter(
                    participant_id=user.uid,
                    status=TestAttemptSessionStatusChoices.completed
                ).exclude(finished_at=None)

                for session in test_attempt_sessions:
                    skill_dict = session.culture_skills_rating
                    if not skill_dict:
                        continue
                    
                    total_score += sum(skill_dict.values())
                    total_skills += len(skill_dict)

                    for skill_name, avg_score in skill_dict.items():
                        # avg_score = details.get("average_score", 0)
                        # temp_user_skill_info[skill_name] = temp_user_skill_info.get(skill_name, []).append(avg_score)
                        if not isinstance(avg_score, (int, float)):
                            continue  # or raise error if unexpected

                        if skill_name not in temp_user_skill_info:
                            temp_user_skill_info[skill_name] = []

                        temp_user_skill_info[skill_name].append(avg_score)
                        print("Skill_name:",skill_name, avg_score)
                    
                        if skill_name not in skill_data:
                            skill_data[skill_name] = {
                                "scores": [],                              
                            }

                        skill_data[skill_name]["scores"].append(avg_score)

                        if skill_name not in culture_score_distribution:
                            culture_score_distribution[skill_name] = {
                                "1-5": 0,
                                "6-8": 0,
                                "9-10": 0
                            }

                        # Categorize
                        if isinstance(avg_score, (int, float)):
                            if 1 <= avg_score <= 5:
                                culture_score_distribution[skill_name]["1-5"] += 1
                            elif 6 <= avg_score <= 8:
                                culture_score_distribution[skill_name]["6-8"] += 1
                            elif 9 <= avg_score <= 10:
                                culture_score_distribution[skill_name]["9-10"] += 1
                        

                if total_skills:
                    user_email = user_id.filter(user_id=user.uid).values_list("value", flat=True).first()
                    user_avg = round(total_score / total_skills, 2)
                    user_leaderboard.append({
                        "user_id": str(user.uid),
                        "email": user_email,
                        "average_score": user_avg,
                        "scores": {skill : round(sum(ratings)/len(ratings),2)  for skill, ratings in temp_user_skill_info.items()}
                    })
                    if isinstance(user_avg, (int, float)):
                        if 1 <= user_avg <= 5:
                            user_score_distribution["1-5"] += 1
                        elif 5 < user_avg <= 8:
                            user_score_distribution["5-8"] += 1
                        elif 8 < user_avg <= 10:
                            user_score_distribution["8-10"] += 1

            # user_skill_inf0[user_id] = {skill : sum(ratings)/len(ratings)  for skill, ratings in temp_user_skill_info.items()}
            user_skill_info[str(user.uid)] = {
                    skill: round(sum(ratings) / len(ratings), 2)
                    for skill, ratings in temp_user_skill_info.items()
                }  

            # user_leaderboard.sort(key=lambda x: x["average_score"], reverse=True)


            response_skills = []
            for skill, data in skill_data.items():
                scores = data["scores"]
                avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0

                response_skills.append({
                    "skill": skill,
                    "average_score": avg_score,                    
                })

            culture_category_distribution = categorize_skill_scores(response_skills, user_leaderboard)

            return {
                "client_users": client_list,
                "skills": response_skills,
                "leaderboard": user_leaderboard,
                "user_score_distribution": user_score_distribution,
                "culture_category_distribution": culture_category_distribution,
            }
    except Exception as e:
        logger.exception(f"Error in evaluate_culture_skills_data_client: {e}")
        return {
            "error": str(e),
            "message": "Failed to evaluate culture skills data for client users."
        }
    

def get_culture_map_prompt(culture_map):
  prompt =  '''
    Culture Map: ${culture_map}
    For the given list of cultural map or dimensions, generate a JSON object where:

    The key is the cultural dimension name.

    The value is a concise evaluative question describing the scoring scale.

    Always make highest score of 10 mean the strongest presence of that trait, and score of 0 mean the opposite extreme.

    Format the text as:
    "Dimension": "Does the conversation look like the participants [description of high score 10] (highest score of 10) or [description of score 0] (score of 0)?"

    Keep it short, clear, and focused on observable aspects of the conversation.

    Example:

    {
      "Hierarchy": "Does the conversation look like the participants have a strict hierarchical relationship (highest score of 10) or a casual professional relationship (score of 0)?"
    }
    '''

  return Template(prompt).substitute(culture_map=culture_map)


def generate_culture_map(culture_map, llm_type='gemini'):
    prompt = get_culture_map_prompt(culture_map)

    if llm_type == 'gemini':
        raw_response = gemini_completion(prompt)
    else:
        raw_response = anthropic_completion(prompt)

    # Extract JSON from fenced code block
    if "```json" in raw_response:
        json_str = raw_response.split("```json")[1].split("```")[0].strip()
    else:
        json_str = raw_response.strip()

    return json.loads(json_str)