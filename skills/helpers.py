import json
import random
import time
import logging

from django.utils.text import slugify

from commons.anthropic import anthropic_completion
from commons.openai_gpt import gpt3_completion
from external_apis.slack_alert_api import send_slack_message
from skills.models import SkillsRating, SkillIndex, CompetencySkillAndClientMapping
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
def evaluate_response_skill(test_attempt_session, conversation, test_title, test_description, test_code, skills, user_skill_prompt, is_free=False):
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
        # This code is designed to run as is, and the output will be only in the print format without any explanations or word counts. 
        # Please do not modify the code or include any additional information in the output. 
        # NEVER PRINT ANYTHING ELSE EXCEPT THE PRINT OUTPUT
        # Define the format instructions
        format_instructions = {
        "output_format": "word",
        "explanations": False,
        "word_counts": False
        }
        import json
        import random
        title_var = input("${title}")
        description_var = input("${description}")
        conversation_var = input("${conversation}")
        evaluation_criteria = [
            {"name": "Relevance", "description": "Does the answer directly address the question?"},
            {"name": "Accuracy", "description": "Is the information in the answer correct?"},
            {"name": "Completeness", "description": "Does the answer provide a comprehensive response to the question?"},
            {"name": "Clarity", "description": "Is the answer well-written and easy to understand?"}
        ]
        skills_var = input("${skills_list}").split(',')
        skills_var = [skill.strip() for skill in skills_var]
        def evaluate_skills(conversation, skills):
        scores = {}
        for skill in skills:
        if skill.lower() in conversation.lower():
        scores[skill] = round(random.uniform(0.5, 10) * 2) / 2
        else:
        scores[skill] = round(random.uniform(0.5, 10) * 2) / 2
        return json.dumps(scores)
        print(evaluate_skills(conversation_var, skills_var))


    """

    prompt = Template(code_prompt).substitute(
        title=test_title,
        description = test_description,
        conversation = conversation,
        skills_list = ",".join(skills_rating),
    )

    if is_free:
        ##################* anthropic ###################
        is_evaluated = True

        responses = []
        response = {}
        max_tries = 3  # because anthropic_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****evaluate_response_skill ":f"trying [outer] anthropic for {1 - max_tries + 1} time"})
                response = anthropic_completion(prompt, len(skills_rating) * 100)
                logger.info({"****evaluate_response_skill ":f"response [outer] anthropic for {1 - max_tries + 1} time","response":response})


                skills_rating_str = json_extraction(response)

                skills_rating = json.loads(skills_rating_str)

                if not is_skill_matched(skills,skills_rating.keys()):
                    raise ValueError("Skills not found in the skills list.")

                for skill in skills_rating:
                    skills_rating[skill] = float(skills_rating[skill])
                responses.append(skills_rating)


                # skills_explanation = to_dict(skills_explanation_str,skills_rating)
                # responses.append(skills_explanation)

                break

            except Exception as e:
                logger.error({"****evaluate_response_skill ":f"failed [outer] anthropic for {1 - max_tries + 1} time","error":e})
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return *responses, is_evaluated
        else:
             # HACK in case everything fails; just evaluate as a random number
            response = {}
            for skill in skills_rating:
                response[skill] = random.randint(3, 7)

            # send error on slack to debug this
            send_slack_message({"process": "evaluate_response_skills",
                                "test_attempt_session": test_attempt_session.uid,
                                "error": "failed to evaluate; putting random value"})

            return response, {}, True
    else:



        ################################* gemini_completion ################################
        responses = []
        response = None
        max_tries = 3  # because gpt3_completion function itself retries 3 times
        is_evaluated = True

        while max_tries > 0:
            try:
                logger.info({"****evaluate_response_skill ":f"trying gemini_completion [outer] for {3 - max_tries + 1} time"})
                response = gemini_completion(prompt)
                logger.info({"****evaluate_response_skill ":f"response [outer] gemini_completion for {3 - max_tries + 1} time","response":response})


                skills_rating_str = json_extraction(response)

                skills_rating = json.loads(skills_rating_str)

                if not is_skill_matched(skills,skills_rating.keys()):  # checking if skills are from skills list
                    raise ValueError("Skills not found in the skills list.")

                for skill in skills_rating:
                    skills_rating[skill] = float(skills_rating[skill])
                responses.append(skills_rating)


                # skills_explanation = to_dict(skills_explanation_str)
                # responses.append(skills_explanation)

                break

            except Exception as e:
                logger.error({"****evaluate_response_skill ":f"failed [outer] gemini_completion for {3 - max_tries + 1} time","error":e })
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return *responses, is_evaluated

        ################################* gemini_completion end ################################
        logger.info({"****evaluate_response_skill ":f"failed gemini_completion, so trying anthropic_completion"})

        ##################* anthropic ###################
        is_evaluated = True

        responses = []
        response = {}
        max_tries = 3  # because anthropic_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****evaluate_response_skill ":f"trying [outer] anthropic for {1 - max_tries + 1} time"})
                response = anthropic_completion(prompt, len(skills_rating) * 100)
                logger.info({"****evaluate_response_skill ":f"response [outer] anthropic for {1 - max_tries + 1} time","response":response})


                skills_rating_str = json_extraction(response)

                skills_rating = json.loads(skills_rating_str)
                if not is_skill_matched(skills,skills_rating.keys()):  # checking if skills are from skills list
                    raise ValueError("Skills not found in the skills list.")

                for skill in skills_rating:
                    skills_rating[skill] = float(skills_rating[skill])
                responses.append(skills_rating)


                # skills_explanation = to_dict(skills_explanation_str,skills_rating)
                # responses.append(skills_explanation)

                break

            except Exception as e:
                logger.error({"****evaluate_response_skill ":f"failed [outer] anthropic for {1 - max_tries + 1} time","error":e})
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return *responses, is_evaluated

        ##################* anthropic end ###################

        logger.info({"****evaluate_response_skill ":f"failed anthropic, so trying gpt_compeletion"})

        ################################* gpt ################################
        responses = []
        response = None
        max_tries = 3  # because gpt3_completion function itself retries 3 times
        is_evaluated = True

        while max_tries > 0:
            try:
                logger.info({"****evaluate_response_skill ":f"trying gpt [outer] for {3 - max_tries + 1} time"})
                response = gpt3_completion(prompt, stop=["USER:", "CoachBot"]).text
                logger.info({"****evaluate_response_skill ":f"response [outer] gpt for {3 - max_tries + 1} time","response":response})


                skills_rating_str = json_extraction(response)

                skills_rating = json.loads(skills_rating_str)
                if not is_skill_matched(skills,skills_rating.keys()):  # checking if skills are from skills list
                    raise ValueError("Skills not found in the skills list.")
                
                for skill in skills_rating:
                    skills_rating[skill] = float(skills_rating[skill])
                responses.append(skills_rating)


                # skills_explanation = to_dict(skills_explanation_str,skills_rating)
                # responses.append(skills_explanation)

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
            return *responses, is_evaluated

        ################################* gpt end ################################


        logger.info({"****evaluate_response_skill ":f"failed everything, so assigning default values"})

        # HACK in case everything fails; just evaluate as a random number
        response = {}
        for skill in skills_rating:
            response[skill] = random.randint(3, 7)

        # send error on slack to debug this
        send_slack_message({"process": "evaluate_response_skills",
                            "test_attempt_session": test_attempt_session.uid,
                            "error": "failed to evaluate; putting random value"})

        return response, {}, True


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
    {feedback} : %s

    {Summary} : Summarize the entire feedback in a small single paragraph and provide feedback to the candidate. Focus on the areas that worked well and the areas the candidate can improve.

    Output format :

    "Here is your summary feedback:

    {Summary}"

    Always follow this output format in this exact manner. DO NOT add words or any other sentence on your own.

    NOTE : Never start with any kind of introductory sentence. Do not provide any kind of heading or introduction text in the output. Start directly with the summary and only provide the summary.

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


    

@timeit
def evaluate_conversation(test_attempt_session, conversation, test_title, test_description, test_code,is_free=False):
    """
    It evaluates the cultural rating for a scenario (test,trainer type)
    """
    cultural_skills = ['hierarchy', 'consensual', 'indirect negative feedback',
                       'relationship based', 'high context communication', 'Persuasion', 'argumentative']

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

    # "cultural_list:" "{cultural_skills}"

    # NOTE: Please put properties of JSON enclosed in double quotes.

    # Example of JSON: {{"hierarchy": "9.5", "consensual": "4", "indirect negative feedback": "4.5", "relationship based": "6", "high context communication": "2.5", "Persuasion": "5", "argumentative": "10"}}
    # '''

    # prompt = f'''
        # "TITLE:" {test_title};

        # "DESCRIPTION:" {test_description};

        # "CONVERSATION:" {conversation};

        # "Evaluation Criteria:"
        # - Hierarchy:  Does the conversation look like the participants have strict hierarchical relationship (highest score of 10) or casual professional relationship ( scores 0)?
        # - Consensual: Does the conversation looks like the respondents have respect for boundary and empathy? ( High yes score 10 and the low is 0) 
        # - Indirect negative feedback: Do the participants provide a subtle feedback or a blunt feedback? (Subtle feedback is 10 and blunt feedback is 0)
        # - Relationship-based: Does the conversation look like the participants focus on relationships (highest score of 10) or tasks (scores 0)?    
        # - High context communication:  Does the conversation look like the participants focus on subtle cues (highest score of 0) or explicit verbal communication (scores 10)? 
        # - Persuasion : Does the conversation look like the participants value emotional appeals (highest score of 10) or completely rely on logic and evidence (scores 0)?  
        # - Argumentative : Does the conversation look like the participants see debate and disagreement as a competition (highest score of 0) or view it as a collaborative process to find truth (scores 10)? 

        # "REQUIRED FROM LLM:" Based on the above criteria please evaluate the entire conversation - which is a list of all questions and answers. Rate the criteria's only from a scale of 1.5-9 in such a way that no two skills can have the exact same score, with scores in increments of 0.5 for each behavior trait listed above which corresponds to this cultural_list in JSON.
        # "cultural_list:" "{cultural_skills}"

        # NOTE: Please put properties of JSON enclosed in double quotes.

        # Example of JSON: {{"hierarchy": "9.5", "consensual": "4", "indirect negative feedback": "4.5", "relationship-based": "6", "high context communication": "2.5", "Persuasion": "5", "argumentative": "10"}}

        # NOTE: For the entire conversation no two skills from {cultural_skills} can have exact same scores.

        # NOTE: Do not add any English language sentence in the output.

    # '''

    prompt = f'''
        \n\nHuman:
        "TITLE:" {test_title};

        "DESCRIPTION:" {test_description};

        "CONVERSATION:" {conversation};

        "Evaluation Criteria:"

        - Hierarchy: Does the conversation look like the participants have strict hierarchical relationship (highest score of 10) or casual professional relationship (scores 0)?

        - Consensual: Does the conversation looks like the respondents have respect for boundary and empathy? ( High yes score 10 and the low is 0)

        - Indirect negative feedback: Do the participants provide a subtle feedback or a blunt feedback? (Subtle feedback is 10 and blunt feedback is 0)

        - Relationship-based: Does the conversation look like the participants focus on relationships (highest score of 10) or tasks (scores 0)?

        - High context communication: Does the conversation look like the participants focus on subtle cues (highest score of 0) or explicit verbal communication (scores 10)?

        - Persuasion : Does the conversation look like the participants value emotional appeals (highest score of 10) or completely rely on logic and evidence (scores 0)?

        - Argumentative : Does the conversation look like the participants see debate and disagreement as a competition (highest score of 0) or view it as a collaborative process to find truth (scores 10)?

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
    # This code is designed to run as is, and the output will be only in the print format without any explanations or word counts. 
    # Please do not modify the code or include any additional information in the output. 
    # NEVER PRINT ANYTHING ELSE EXCEPT THE PRINT OUTPUT
    # Define the format instructions
    format_instructions = {
    "output_format": "word",
    "explanations": False,
    "word_counts": False
    }
    import json
    import random
    title_var = input("${title}")
    description_var = input("${description}")
    conversation_var = input("${conversation}")
    evaluation_criteria = input("{
        "Hierarchy": "Does the conversation look like the participants have strict hierarchical relationship",
        "Consensual": "Does the conversation looks like the respondents have respect for boundary and empathy?",
        "Indirect negative feedback": "Do the participants provide a subtle feedback or a blunt feedback?",
        "Relationship-based": "Does the conversation look like the participants focus on relationships",
        "High context communication": "Does the conversation look like the participants focus on subtle cues",
        "Persuasion": "Does the conversation look like the participants value emotional appeals",
        "Argumentative": "Does the conversation look like the participants see debate and disagreement as a competition"}")
    culture_var = input("${culture_skills}").split(',')

    culture_var = [culture.strip() for culture in culture_var]

    def evaluate_culture(conversation, culture):
    scores = {}
    for cult in culture:
    if cult.lower() in conversation.lower():
    scores[cult] = round(random.uniform(0.5, 10) * 2) / 2
    else:
    scores[cult] = round(random.uniform(0.5, 10) * 2) / 2
    return json.dumps(scores)

    print(evaluate_culture(conversation_var, culture_var))


    """

    prompt = Template(code_prompt).substitute(
        title=test_title,
        description = test_description,
        conversation = conversation,
        culture_skills = ",".join(cultural_skills),
    )
    if is_free:
        ################################* anthropic ################################
        is_evaluated = True
        responses = []
        response = {}
        max_tries = 3  # because anthropic_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****evaluate_conversation ":f"trying [outer] anthropic for {1 - max_tries + 1} time"})
                response = anthropic_completion(prompt, len(cultural_skills) * 100)
                logger.info({"****evaluate_conversation ":f"response [outer] anthropic for {1 - max_tries + 1} time","response":response})



                skills_rating_str= json_extraction(response)

                skills_rating = json.loads(skills_rating_str)
                for skill in skills_rating:
                    skills_rating[skill] = float(skills_rating[skill])
                responses.append(skills_rating)


                # skills_explanation = to_dict(skills_explanation_str,skills_rating)
                # responses.append(skills_explanation)

                break

            except Exception as e:
                logger.error({"!!!!!!!!!!!!evaluate_conversation ":f"failed [outer] anthropic for {1 - max_tries + 1} time","error":e},exc_info=True)
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return *responses, is_evaluated
        else:
            # HACK in case everything fails; just evaluate as a random number
            response = {}
            for skill in cultural_skills:
                response[skill] = random.randint(3, 7)

            # send error on slack to debug this
            send_slack_message({"process": "evaluate_conversation",
                                "test_attempt_session": test_attempt_session.uid,
                                "error": "failed to evaluate; putting random value"})

            return response,{}, True

    else:     

        

        ################################* gemini_completion ################################
        responses = []
        response = None
        max_tries = 3  # because gpt3_completion function itself retries 3 times
        is_evaluated = True

        while max_tries > 0:
            try:
                logger.info({"****evaluate_conversation ":f"trying [outer] gemini_completion for {3 - max_tries + 1} time"})
                response = gemini_completion(prompt)
                logger.info({"****evaluate_conversation ":f"response [outer] gemini_completion for {3 - max_tries + 1} time","response":response})


                skills_rating_str = json_extraction(response)

                skills_rating = json.loads(skills_rating_str)
                for skill in skills_rating:
                    skills_rating[skill] = float(skills_rating[skill])
                responses.append(skills_rating)


                # skills_explanation = to_dict(skills_explanation_str)
                # responses.append(skills_explanation)

                break

            except Exception as e:
                logger.error({"!!!!!!!!!!!!evaluate_response_skill ":f"failed [outer] gemini_completion for {3 - max_tries + 1} time","error":e },exc_info=True)
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return *responses, is_evaluated

        ################################* gemini_completion end ################################

        logger.info({"****evaluate_conversation ":f"failed gemini_completion, so trying anthropic_completion"})

        ################################* anthropic ################################
        is_evaluated = True
        responses = []
        response = {}
        max_tries = 3  # because anthropic_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****evaluate_conversation ":f"trying [outer] anthropic for {1 - max_tries + 1} time"})
                response = anthropic_completion(prompt, len(cultural_skills) * 100)
                logger.info({"****evaluate_conversation ":f"response [outer] anthropic for {1 - max_tries + 1} time","response":response})



                skills_rating_str= json_extraction(response)

                skills_rating = json.loads(skills_rating_str)
                for skill in skills_rating:
                    skills_rating[skill] = float(skills_rating[skill])
                responses.append(skills_rating)


                # skills_explanation = to_dict(skills_explanation_str,skills_rating)
                # responses.append(skills_explanation)

                break

            except Exception as e:
                logger.error({"!!!!!!!!!!!!evaluate_conversation ":f"failed [outer] anthropic for {1 - max_tries + 1} time","error":e},exc_info=True)
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return *responses, is_evaluated

        ################################* anthropic end ################################
        
        logger.info({"****evaluate_conversation ":f"failed gpt, so trying gemini_completion"})

        ################################* gpt ################################
        responses = []
        response = None
        max_tries = 3  # because gpt3_completion function itself retries 3 times
        is_evaluated = True

        while max_tries > 0:
            try:
                logger.info({"****evaluate_conversation ":f"trying [outer] gpt for {3 - max_tries + 1} time"})
                response = gpt3_completion(prompt, stop=["USER:", "CoachBot"]).text
                logger.info({"****evaluate_conversation ":f"response [outer] gpt for {3 - max_tries + 1} time","response":response})


                skills_rating_str = json_extraction(response)

                skills_rating = json.loads(skills_rating_str)
                for skill in skills_rating:
                    skills_rating[skill] = float(skills_rating[skill])
                responses.append(skills_rating)


                # skills_explanation = to_dict(skills_explanation_str, skills_rating)
                # responses.append(skills_explanation)

                break

            except Exception as e:
                logger.error({"!!!!!!!!!!!!evaluate_response_skill ":f"failed [outer] gpt for {3 - max_tries + 1} time","error":e },exc_info=True)
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return *responses, is_evaluated

        ################################* gpt end ################################


        logger.info({"****evaluate_conversation ":f"failed everything, so assigning default values"})

        # HACK in case everything fails; just evaluate as a random number
        response = {}
        for skill in cultural_skills:
            response[skill] = random.randint(3, 7)

        # send error on slack to debug this
        send_slack_message({"process": "evaluate_conversation",
                            "test_attempt_session": test_attempt_session.uid,
                            "error": "failed to evaluate; putting random value"})

        return response,{}, True



@timeit
def evaluate_group_discussion_conversation(test_attempt_session, conversation, user_persona, objective, test_code,test,is_free=False):
    """
    It evaluates the cultural rating for a scenario (group discussion)
    """
    cultural_skills = ['hierarchy', 'consensual', 'indirect negative feedback',
                       'relationship based', 'high context communication', 'Persuasion', 'argumentative']

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
    # This code is designed to run as is, and the output will be only in the print format without any explanations or word counts. 
    # Please do not modify the code or include any additional information in the output. 
    # NEVER PRINT ANYTHING ELSE EXCEPT THE PRINT OUTPUT
    # Define the format instructions
    format_instructions = {
    "output_format": "word",
    "explanations": False,
    "word_counts": False
    }
    import json
    import random

    title = input("${title}")
    description = input("${description}")
    conversation = input("${conversation}")
    user_persona = input("${user_persona}")
    cultures_var = input("${cultural_skills}").split(',')
    cultures_list = [culture.strip() for culture in cultures_var]

    instructions = "Based on the above criteria please evaluate the '{user_persona}' only from a scale of 1.5-9, with scores in increments of 0.5. Evaluate the conversation for the '{user_persona}' and the '{user_persona}' only, in this conversation for each behaviour trait in this {cultures_list} in JSON.".format(user_persona=user_persona,cultures_list=cultures_list)

    def evaluate_cultures(conversation, cultures):
    scores = {}
    for culture in cultures:
        if culture.lower() in conversation.lower():
        scores[culture] = round(random.uniform(0.5, 10) * 2) / 2
        else:
        scores[culture] = round(random.uniform(0.5, 10) * 2) / 2
    return json.dumps(scores)

    print(evaluate_cultures(conversation, cultures_list))

    """

    prompt = Template(code_prompt).substitute(
        title = test.title,
        description = test.description,
        user_persona = user_persona,
        conversation = conversation,
        cultural_skills = ",".join(cultural_skills)
    )



    if is_free:
         ################################* anthropic ################################
        skills_rating = None
        response = None
        is_evaluated = True
        max_tries = 3  # because anthropic_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****evaluate_group_discussion_conversation ":f"trying [outer] anthropic for {1 - max_tries + 1} time"})
                response = anthropic_completion(prompt, len(cultural_skills) * 100)
                logger.info({"****evaluate_group_discussion_conversation ":f"response [outer] anthropic for {1 - max_tries + 1} time","response":response})

                skills_rating_str = json_extraction(response)

                skills_rating = json.loads(skills_rating_str)
                for skill in skills_rating:
                    skills_rating[skill] = float(skills_rating[skill])



                # skills_explanation = to_dict(skills_explanation_str, skills_rating)
                # responses.append(skills_explanation)

                break

            except Exception as e:
                logger.error({"****evaluate_group_discussion_conversation ":f"failed [outer] anthropic for {1 - max_tries + 1} time","error":e})
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return skills_rating

        ################################* anthropic end ################################

        logger.info({"****evaluate_group_discussion_conversation ":f"failed everything, so assigning default values"})

        # HACK in case everything fails; just evaluate as a random number
        response = {}
        for skill in cultural_skills:
            response[skill] = random.randint(3, 7)

        # send error on slack to debug this
        send_slack_message({"process": "evaluate_group_discussion_conversation",
                            "test_attempt_session": test_attempt_session.uid,
                            "error": "failed to evaluate_free_type; putting random value"})

        return response


    else:


        ################################* gemini_completion ################################
        skills_rating = None
        is_evaluated = True
        response = None
        max_tries = 3  # because gpt3_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****evaluate_group_discussion_conversation ":f"trying [outer] gemini_completion for {3 - max_tries + 1} time"})
                response = gemini_completion(prompt)
                logger.info({"****evaluate_group_discussion_conversation ":f"response [outer] gemini_completion for {3 - max_tries + 1} time","response":response})
                
                skills_rating_str = json_extraction(response)

                skills_rating = json.loads(skills_rating_str)
                for skill in skills_rating:
                    skills_rating[skill] = float(skills_rating[skill])



                # skills_explanation = to_dict(skills_explanation_str)
                # responses.append(skills_explanation)

                break

            except Exception as e:
                logger.error({"****evaluate_group_discussion_conversation ":f"failed [outer] gemini_completion for {3 - max_tries + 1} time","error":e })
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue

        if is_evaluated:
            return skills_rating

        ################################* gemini_completion end ################################

        logger.info({"****evaluate_group_discussion_conversation ":f"failed gemini_completion, so trying anthropic_completion"})

        ################################* anthropic ################################
        skills_rating = None
        response = None
        is_evaluated = True
        max_tries = 3  # because anthropic_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****evaluate_group_discussion_conversation ":f"trying [outer] anthropic for {1 - max_tries + 1} time"})
                response = anthropic_completion(prompt, len(cultural_skills) * 100)
                logger.info({"****evaluate_group_discussion_conversation ":f"response [outer] anthropic for {1 - max_tries + 1} time","response":response})

                skills_rating_str = json_extraction(response)

                skills_rating = json.loads(skills_rating_str)
                for skill in skills_rating:
                    skills_rating[skill] = float(skills_rating[skill])



                # skills_explanation = to_dict(skills_explanation_str, skills_rating)
                # responses.append(skills_explanation)

                break

            except Exception as e:
                logger.error({"****evaluate_group_discussion_conversation ":f"failed [outer] anthropic for {1 - max_tries + 1} time","error":e})
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return skills_rating

        ################################* anthropic end ################################
        
        logger.info({"****evaluate_group_discussion_conversation ":f"failed anthropic, so trying gpt_compeletion "})

        ################################* gpt ################################
        skills_rating = None
        is_evaluated = True
        response = None
        max_tries = 3  # because gpt3_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****evaluate_group_discussion_conversation ":f"trying [outer] gpt for {3 - max_tries + 1} time"})
                response = gpt3_completion(prompt, stop=["USER:", "CoachBot"]).text
                logger.info({"****evaluate_group_discussion_conversation ":f"response [outer] gpt for {3 - max_tries + 1} time","response":response})
                
                skills_rating_str = json_extraction(response)

                skills_rating = json.loads(skills_rating_str)
                for skill in skills_rating:
                    skills_rating[skill] = float(skills_rating[skill])
                


                # skills_explanation = to_dict(skills_explanation_str, skills_rating)
                # responses.append(skills_explanation)

                break

            except Exception as e:
                logger.error({"****evaluate_group_discussion_conversation ":f"failed [outer] gpt for {3 - max_tries + 1} time","error":e })
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue

        if is_evaluated:
            return skills_rating

        ################################* gpt end ################################


        logger.info({"****evaluate_group_discussion_conversation ":f"failed everything, so assigning default values"})

        # HACK in case everything fails; just evaluate as a random number
        response = {}
        for skill in cultural_skills:
            response[skill] = random.randint(3, 7)

        # send error on slack to debug this
        send_slack_message({"process": "evaluate_group_discussion_conversation",
                            "test_attempt_session": test_attempt_session.uid,
                            "error": "failed to evaluate; putting random value"})

        return response


@timeit
def evaluate_skills_group_discussion_conversation(test_attempt_session, conversation, user_persona, objective, skills_to_evaluate,test,is_free=False):
    """
    It evaluates the normal skills rating for a scenario (group discussion)
    """
    skills_to_evaluate = skills_to_evaluate.split(',') if isinstance(
        skills_to_evaluate, str) else skills_to_evaluate

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
    # This code is designed to run as is, and the output will be only in the print format without any explanations or word counts. 
    # Please do not modify the code or include any additional information in the output. 
    # NEVER PRINT ANYTHING ELSE EXCEPT THE PRINT OUTPUT
    # Define the format instructions
    format_instructions = {
    "output_format": "word",
    "explanations": False,
    "word_counts": False
    }
    import json
    import random
    title = input("${title}")
    description = input("${description}")
    conversation = input("${conversation}")
    user_persona = input("${user_persona}")
    skills_var = input("${skill_list}").split(',')
    skills_list = [skill.strip() for skill in skills_var]

    instructions = "Based on the above criteria, please evaluate the conversation between the '{user_persona}' and the '{user_persona}' only from a scale of 1.5-10, with scores in increments of 0.5. Evaluate the conversation for the '{user_persona}' and the '{user_persona}' only, in this conversation for each behaviour trait in this {skills_list} in JSON.".format(user_persona=user_persona, skills_list=skills_list)


    def evaluate_skills(conversation, skills):
    scores = {}
    for skill in skills:
        if skill.lower() in conversation.lower():
        scores[skill] = round(random.uniform(0.5, 10) * 2) / 2
        else:
        scores[skill] = round(random.uniform(0.5, 10) * 2) / 2
    return json.dumps(scores)

    print(evaluate_skills(conversation_var, skills_list))
    
    """

    prompt = Template(code_prompt).substitute(
        skill_list = ','.join(skills_to_evaluate),
        title = test.title,
        description = test.description,
        user_persona = user_persona,
        conversation = conversation,
    )


    if is_free:
        ################################* anthropic ################################
        skills_rating = None
        response = None
        is_evaluated = True
        max_tries = 3  # because anthropic_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****evaluate_skills_group_discussion_conversation ":f"trying [outer] anthropic for {1 - max_tries + 1} time"})
                response = anthropic_completion(
                    prompt, len(skills_to_evaluate) * 100)
                logger.info({"****evaluate_skills_group_discussion_conversation ":f"response [outer] anthropic for {1 - max_tries + 1} time","response":response})
                
                skills_rating_str = json_extraction(response)

                skills_rating = json.loads(skills_rating_str)
                for skill in skills_rating:
                    skills_rating[skill] = float(skills_rating[skill])


                # skills_explanation = to_dict(skills_explanation_str, skills_rating)
                # responses.append(skills_explanation)
                
                break
            except Exception as e:
                logger.error({"****evaluate_skills_group_discussion_conversation ":f"failed [outer] anthropic for {3 - max_tries + 1} time","error":e})
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue

        if is_evaluated:
            return skills_rating

        ################################* anthropic end ################################

        logger.info({"****evaluate_skills_group_discussion_conversation ":f"failed everything, so assigning default values"})

        # HACK in case everything fails; just evaluate as a random number
        response = {}
        for skill in skills_to_evaluate:
            response[skill] = random.randint(3, 7)

        # send error on slack to debug this
        send_slack_message({"process": "evaluate_skills_group_discussion_conversation",
                            "test_attempt_session": test_attempt_session.uid,
                            "error": "failed to evaluate free type; putting random value"})

        return response

    else:
        

        ################################* gemini_completion ################################
        skills_rating = None
        response = None
        max_tries = 3  # because gpt3_completion function itself retries 3 times
        is_evaluated = True

        while max_tries > 0:
            try:
                logger.info({"****evaluate_skills_group_discussion_conversation ":f"trying [outer] gemini_completion for {3 - max_tries + 1} time"})
                response = gemini_completion(prompt)
                logger.info({"****evaluate_skills_group_discussion_conversation ":f"response [outer] gemini_completion for {3 - max_tries + 1} time","response":response})
                
                skills_rating_str = json_extraction(response)

                skills_rating = json.loads(skills_rating_str)
                for skill in skills_rating:
                    skills_rating[skill] = float(skills_rating[skill])


                # skills_explanation = to_dict(skills_explanation_str)
                # responses.append(skills_explanation)

                break

            except Exception as e:
                logger.error({"****evaluate_skills_group_discussion_conversation ":f"failed [outer] gemini_completion for {3 - max_tries + 1} time","error":e })
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue

        if is_evaluated:
            return skills_rating

        ################################* gemini_completion end ################################

        logger.info({"****evaluate_skills_group_discussion_conversation ":f"failed gemini_completion, so trying anthropic_completion"})

        ################################* anthropic ################################
        skills_rating = None
        response = None
        is_evaluated = True
        max_tries = 3  # because anthropic_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****evaluate_skills_group_discussion_conversation ":f"trying [outer] anthropic for {1 - max_tries + 1} time"})
                response = anthropic_completion(
                    prompt, len(skills_to_evaluate) * 100)
                logger.info({"****evaluate_skills_group_discussion_conversation ":f"response [outer] anthropic for {1 - max_tries + 1} time","response":response})
                
                skills_rating_str = json_extraction(response)

                skills_rating = json.loads(skills_rating_str)
                for skill in skills_rating:
                    skills_rating[skill] = float(skills_rating[skill])


                # skills_explanation = to_dict(skills_explanation_str, skills_rating)
                # responses.append(skills_explanation)
                
                break
            except Exception as e:
                logger.error({"****evaluate_skills_group_discussion_conversation ":f"failed [outer] anthropic for {3 - max_tries + 1} time","error":e})
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue

        if is_evaluated:
            return skills_rating

        ################################* anthropic end ################################

        logger.info({"****evaluate_skills_group_discussion_conversation ":f"failed anthropic, so trying gpt"})

        ################################* gpt ################################
        skills_rating = None
        response = None
        max_tries = 3  # because gpt3_completion function itself retries 3 times
        is_evaluated = True

        while max_tries > 0:
            try:
                logger.info({"****evaluate_skills_group_discussion_conversation ":f"trying [outer] gpt for {3 - max_tries + 1} time"})
                response = gpt3_completion(prompt, stop=["USER:", "CoachBot"]).text
                logger.info({"****evaluate_skills_group_discussion_conversation ":f"response [outer] gpt for {3 - max_tries + 1} time","response":response})
                
                skills_rating_str = json_extraction(response)

                skills_rating = json.loads(skills_rating_str)
                for skill in skills_rating:
                    skills_rating[skill] = float(skills_rating[skill])


                break

            except Exception as e:
                logger.error({"****evaluate_skills_group_discussion_conversation ":f"failed [outer] gpt for {3 - max_tries + 1} time","error":e })
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue

        if is_evaluated:
            return skills_rating

        ################################* gpt end ################################


        logger.info({"****evaluate_skills_group_discussion_conversation ":f"failed everything, so assigning default values"})

        # HACK in case everything fails; just evaluate as a random number
        response = {}
        for skill in skills_to_evaluate:
            response[skill] = random.randint(3, 7)

        # send error on slack to debug this
        send_slack_message({"process": "evaluate_skills_group_discussion_conversation",
                            "test_attempt_session": test_attempt_session.uid,
                            "error": "failed to evaluate; putting random value"})

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

    participant_info = {
        "name": get_user_display_name(participant),
        "role": participant.role,
        "skills_info": participant_skill_rating_object[0].get('skills_info', {}) if len(participant_skill_rating_object)>0 else {},
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
