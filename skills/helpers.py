import json
import random
import time
import logging

from django.utils.text import slugify

from commons.anthropic import anthropic_completion
from commons.openai_gpt import gpt3_completion
from external_apis.slack_alert_api import send_slack_message
from skills.models import SkillsRating, SkillIndex
from users.db import get_user_display_name
from users.models import User
import re
from commons.google_apis import text_bison_compeletion
from commons.timeit import timeit
from nltk.stem import PorterStemmer



logger = logging.getLogger(__name__)


def is_skill_matched(skill_list, rating_list):
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
    
def json_extraction(text):
    pattern = r'{[^}]+}'

    # Use re.search to find the JSON portion in the text
    match = re.search(pattern, text)

    if match:
        json_data = match.group()
        logger.info({"json": json_data})
        return json_data
    else:
        logger.info({"message": "json not found"})
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

    # "REQUIRED FROM ANTHROPIC:" Based on the above criteria please evaluate the given answer on a scale of 0-10, with scores in increments of 0.5 for each skill in the list in JSON: "{skills}".
    
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

    "REQUIRED FROM ANTHROPIC:" Based on the above criteria please evaluate the given conversation i.e. all answers on a scale of 1-9, with scores in increments of 0.5 for each skill in the list in JSON: "{skills}" in such a way that no two skills can have the exact same score. 

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
            response = json.loads(response)
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

            response = json.loads(response)
            
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
    
    prompt = f'''
    \n\nHuman:
    "TITLE:" {test_title};

    "DESCRIPTION:" {test_description};

    "QUESTION:" {question_text};

    "ANSWER:" {response_text};

    "REQUIRED FROM ANTHROPIC:" Please check whether the answer provided is even slightly related to the question asked and the description provided. Assign a relevancy score between 0 to 10, 10 being highly relevant response and 0 being completely irrelevant response. ONLY when the entire answer is completely random and unrelated to the question and description give the relevancy score value as 0.
    NOTE: Please Reply in a valid JSON format only and no other format will be accepted.

    NOTE: Don't put any other text in the reply other than the JSON.

    NOTE: Output Format Example: {{"relevance":"1"}}

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
                response = json.loads(response)
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
        

        ##################* text_bison_compeletion ###################

        is_evaluated = True
        response = None
        max_tries = 3

        while max_tries > 0:
            try:
                logger.info({"****evaluate_relevacy ":f"trying [outer]  text_bison_compeletion for  {3 - max_tries + 1} time"})
                response = text_bison_compeletion(prompt)
                logger.info({"****evaluate_relevacy ":f"response [outer] text_bison_compeletion for {3 - max_tries + 1} time","response":response})
                response = json_extraction(response)
                response = json.loads(response)
                
                for skill in response:
                    if int(response[skill]) == 0:
                        response[skill] = 0
                    else:
                        response[skill] = 1

                break

            except Exception as e:
                logger.error({"****evaluate_relevacy ":f"failed [outer] text_bison_compeletion for {3 - max_tries + 1} time","error":e })
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return response, is_evaluated


        ##################* text_bison_compeletion ###################
        
        logger.info({"****evaluate_relevacy ":f"failed  text_bison_compeletion, so trying anthropic_completion"})

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
                response = json.loads(response)
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
                response = json.loads(response)
                
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


@timeit
def evaluate_response_skill(test_attempt_session, conversation, test_title, test_description, test_code,skills,user_skill_prompt,is_free=False):
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

    # "Required from anthropic:" Based on the above criteria please evaluate the given answers on a scale of 0-10, with scores in increments of 0.5 for each behaviour trait in this cultural_list in JSON. 

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

    #     "REQUIRED FROM ANTHROPIC:" Based on the above criteria please evaluate the given conversation i.e. all answers on a scale of 1-9, with scores in increments of 0.5 for each skill in the list in JSON: "{skills}" in such a way that no two skills can have the exact same score.

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

        "REQUIRED FROM ANTHROPIC:" Based on the above criteria please evaluate the given conversation i.e. all answers on a scale of 1-9, with scores in increments of 0.5 for each skill in the list in JSON: "{skills}" in such a way that no two skills can have the exact same score.

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



        ################################* text_bison_compeletion ################################
        responses = []
        response = None
        max_tries = 3  # because gpt3_completion function itself retries 3 times
        is_evaluated = True

        while max_tries > 0:
            try:
                logger.info({"****evaluate_response_skill ":f"trying text_bison_compeletion [outer] for {3 - max_tries + 1} time"})
                response = text_bison_compeletion(prompt)
                logger.info({"****evaluate_response_skill ":f"response [outer] text_bison_compeletion for {3 - max_tries + 1} time","response":response})


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
                logger.error({"****evaluate_response_skill ":f"failed [outer] text_bison_compeletion for {3 - max_tries + 1} time","error":e })
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return *responses, is_evaluated

        ################################* text_bison_compeletion end ################################
        logger.info({"****evaluate_response_skill ":f"failed text_bison_compeletion, so trying anthropic_completion"})

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
def calulate_summary_for_culture_and_normal_skill(test_attempt_session,cultural_skill, skill_rating,is_free=False):
    prompt= """
    \n\nHuman:
    cultural_list: %s

    skills_list: %s

    {Top_skills} : From the skills_list get the two skills with the highest score. Write the skill name and the score in this format skill : score

    {Low_skills} : From the skills_list get the two skills with the lowest score. Write the skill name and the score in this format skill : score

    {Improvement} : Provide some ideas on how the user can improve the {Low_skills} in 2-3 sentences.

    {High_culture} : From the cultural_list get the skill with the highest score.

    {Low_culture} : From the cultural_list get the skill with the lowest score.

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
    """%(cultural_skill,skill_rating)


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

        #################################* text_bison_compeletion #################################
        response = None
        max_tries = 3  # because gpt3_completion function itself retries 3 times
        is_evaluated = True

        while max_tries > 0:
            try:
                logger.info({"****calulate_summary_for_culture_and_normal_skill ":f"trying text_bison_compeletion [outer] for {3 - max_tries + 1} time"})
                response = text_bison_compeletion(prompt)
                logger.info({"****calulate_summary_for_culture_and_normal_skill ":f"response [outer] text_bison_compeletion for {3 - max_tries + 1} time","response":response})


                break

            except Exception as e:
                logger.error({"****calulate_summary_for_culture_and_normal_skill ":f"failed [outer] text_bison_compeletion for {3 - max_tries + 1} time","error":e })
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return response

        #################################* text_bison_compeletion end #################################

        logger.info({"****calulate_summary_for_culture_and_normal_skill ":f"failed text_bison_compeletion, so trying anthropic_completion"})
        
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

        #################################* text_bison_compeletion #################################
        response = None
        max_tries = 3  # because gpt3_completion function itself retries 3 times
        is_evaluated = True

        while max_tries > 0:
            try:
                logger.info({"****feedback_summary ":f"trying text_bison_compeletion [outer] for {3 - max_tries + 1} time"})
                response = text_bison_compeletion(prompt)
                logger.info({"****feedback_summary ":f"response [outer] text_bison_compeletion for {3 - max_tries + 1} time","response":response})


                break

            except Exception as e:
                logger.error({"****feedback_summary ":f"failed [outer] text_bison_compeletion for {3 - max_tries + 1} time","error":e })
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return response

        #################################* text_bison_compeletion end #################################

        logger.info({"****feedback_summary ":f"failed text_bison_compeletion, so trying anthropic_completion"})

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

    # "Required from anthropic:" Based on the above criteria please evaluate the given answers on a scale of 0-10, with scores in increments of 0.5 for each behaviour trait in this cultural_list in JSON. 

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

        # "Required from anthropic:" Based on the above criteria please evaluate the entire conversation - which is a list of all questions and answers. Rate the criteria's only from a scale of 1.5-9 in such a way that no two skills can have the exact same score, with scores in increments of 0.5 for each behavior trait listed above which corresponds to this cultural_list in JSON.
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

        "Required from anthropic:" Based on the above criteria please evaluate the entire conversation - which is a list of all questions and answers. Rate the criteria's only from a scale of 1.5-9 in such a way that no two skills can have the exact same score, with scores in increments of 0.5 for each behavior trait listed above which corresponds to this cultural_list in JSON.

        "cultural_list:" "{cultural_skills}"

        NOTE: Please put properties of JSON enclosed in double quotes.

        Example of JSON: {{"hierarchy": "9.5", "consensual": "4", "indirect negative feedback": "4.5", "relationship-based": "6", "high context communication": "2.5", "Persuasion": "5", "argumentative": "10"}}

        NOTE: For the entire question and answer conversation no two skills from {cultural_skills} can have exact same scores.

        NOTE : Do not provide any kind of heading or introduction text in the output.

        NOTE: Do not add any English language sentence in the output.
        \n\nAssistant:
        '''
    
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

        

        ################################* text_bison_compeletion ################################
        responses = []
        response = None
        max_tries = 3  # because gpt3_completion function itself retries 3 times
        is_evaluated = True

        while max_tries > 0:
            try:
                logger.info({"****evaluate_conversation ":f"trying [outer] text_bison_compeletion for {3 - max_tries + 1} time"})
                response = text_bison_compeletion(prompt)
                logger.info({"****evaluate_conversation ":f"response [outer] text_bison_compeletion for {3 - max_tries + 1} time","response":response})


                skills_rating_str = json_extraction(response)

                skills_rating = json.loads(skills_rating_str)
                for skill in skills_rating:
                    skills_rating[skill] = float(skills_rating[skill])
                responses.append(skills_rating)


                # skills_explanation = to_dict(skills_explanation_str)
                # responses.append(skills_explanation)

                break

            except Exception as e:
                logger.error({"!!!!!!!!!!!!evaluate_response_skill ":f"failed [outer] text_bison_compeletion for {3 - max_tries + 1} time","error":e },exc_info=True)
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue


        if is_evaluated:
            return *responses, is_evaluated

        ################################* text_bison_compeletion end ################################

        logger.info({"****evaluate_conversation ":f"failed text_bison_compeletion, so trying anthropic_completion"})

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
        
        logger.info({"****evaluate_conversation ":f"failed gpt, so trying text_bison_compeletion"})

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
def evaluate_group_discussion_conversation(test_attempt_session, conversation, user_persona, objective, test_code,is_free=False):
    cultural_skills = ['hierarchy', 'consensual', 'indirect negative feedback',
                       'relationship based', 'high context communication', 'Persuasion', 'argumentative']

    # prompt = f'''
    # "Objective:" {objective};

    # "Conversation:" {conversation};

    # "Required from anthropic:" Based on the above criteria please evaluate the "{user_persona}" on a scale of 0-10, with scores in increments of 0.5. Evaluate the conversation for the participant: "{user_persona}" and this "{user_persona}" only, in this conversation for each behaviour trait in this cultural_list in JSON. 

    # "cultural_list:" "{cultural_skills}"

    # Please put properties of JSON enclosed in double quotes.

    # Example of JSON: {{"hierarchy": "9.5", "consensual": "4", "indirect negative feedback": "4.5", "relationship based": "6", "high context communication": "2.5", "Persuasion": "5", "argumentative": "10"}}
    # '''

    # prompt = f'''
    # "Objective:" {objective};

    # "Conversation:" {conversation};

    # "Required from anthropic:" Based on the above criteria please evaluate the "{user_persona}" only from a scale of 1.5-9, with scores in increments of 0.5. Evaluate the conversation for the participant: "{user_persona}" and this "{user_persona}" only, in this conversation for each behaviour trait in this cultural_list in JSON.

    # "cultural_list:" "{cultural_skills}"

    # Please put properties of JSON enclosed in double quotes.

    # Example of JSON: {{"hierarchy": "9.5", "consensual": "4", "indirect negative feedback": "4.5", "relationship based": "6", "high context communication": "2.5", "Persuasion": "5", "argumentative": "10"}}

    # NOTE: Do not add any English language sentence in the output.
    # '''


    prompt = prompt = f''' 
        \n\nHuman:
        "Objective:" {objective}; 
        "Conversation:" {conversation}; 
        "Required from anthropic:" Based on the above criteria please evaluate the "{user_persona}" only from a scale of 1.5-9, with scores in increments of 0.5. Evaluate the conversation for the participant: "{user_persona}" and this "{user_persona}" only, in this conversation for each behaviour trait in this cultural_list in JSON. 
        "cultural_list:" "{cultural_skills}" 
        Please put properties of JSON enclosed in double quotes. 
        Example of JSON: {{"hierarchy": "9.5", "consensual": "4", "indirect negative feedback": "4.5", "relationship based": "6", "high context communication": "2.5", "Persuasion": "5", "argumentative": "10"}} 
        NOTE: Do not add any English language sentence in the output. 

        NOTE : Do not provide any kind of heading or introduction text in the output.
        \n\nAssistant:
    '''


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


        ################################* text_bison_compeletion ################################
        skills_rating = None
        is_evaluated = True
        response = None
        max_tries = 3  # because gpt3_completion function itself retries 3 times

        while max_tries > 0:
            try:
                logger.info({"****evaluate_group_discussion_conversation ":f"trying [outer] text_bison_compeletion for {3 - max_tries + 1} time"})
                response = text_bison_compeletion(prompt)
                logger.info({"****evaluate_group_discussion_conversation ":f"response [outer] text_bison_compeletion for {3 - max_tries + 1} time","response":response})
                
                skills_rating_str = json_extraction(response)

                skills_rating = json.loads(skills_rating_str)
                for skill in skills_rating:
                    skills_rating[skill] = float(skills_rating[skill])



                # skills_explanation = to_dict(skills_explanation_str)
                # responses.append(skills_explanation)

                break

            except Exception as e:
                logger.error({"****evaluate_group_discussion_conversation ":f"failed [outer] text_bison_compeletion for {3 - max_tries + 1} time","error":e })
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue

        if is_evaluated:
            return skills_rating

        ################################* text_bison_compeletion end ################################

        logger.info({"****evaluate_group_discussion_conversation ":f"failed text_bison_compeletion, so trying anthropic_completion"})

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
def evaluate_skills_group_discussion_conversation(test_attempt_session, conversation, user_persona, objective, skills_to_evaluate,is_free=False):
    skills_to_evaluate = skills_to_evaluate.split(',') if isinstance(
        skills_to_evaluate, str) else skills_to_evaluate

    # prompt = f'''
    # "Objective:" {objective};

    # "Conversation:" {conversation};

    # "Required from anthropic:" Based on the above criteria please evaluate the "{user_persona}" on a scale of 0-10, with scores in increments of 0.5. Evaluate the conversation for the participant: "{user_persona}" and this "{user_persona}" only, in this conversation for each behaviour trait in this skills_list in JSON. 

    # "skills_list:" "{skills_to_evaluate}"

    # Please put properties of JSON enclosed in double quotes.

    # Example of JSON: {{"hierarchy": "9.5", "consensual": "4", "indirect negative feedback": "4.5", "relationship based": "6", "high context communication": "2.5", "Persuasion": "5", "argumentative": "10"}}

    # NOTE: Please Reply in a JSON format only and no other format will be accepted. NO OTHER TEXT SHOULD BE PRESENT IN THE REPLY OTHER THAN THE JSON. NO INTRUCTIONS SHOULD BE PRESENT IN THE REPLY OTHER THAN THE JSON.
    # '''

    # prompt = f'''
    # "Objective:" {objective};

    # "Conversation:" {conversation};

    # "Required from anthropic:" Based on the above criteria please evaluate the "{user_persona}" on a scale of 0-10, with scores in increments of 0.5. Evaluate the conversation for the participant: "{user_persona}" and this "{user_persona}" only in this conversation for each behaviour trait in this skills_list in JSON in such a way that no two skills can have the exact same score.

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

    "Required from anthropic:" Based on the above criteria please evaluate the "{user_persona}" only from a scale of 1.5-9, with scores in increments of 0.5. Evaluate the conversation for the participant: "{user_persona}" and this "{user_persona}" only, in this conversation for each behaviour trait in this skills_list in JSON. 
    "skills_list:" "{skills_to_evaluate}"
    Please put properties of JSON enclosed in double quotes.
    Example of JSON: {{"hierarchy": "9.5", "consensual": "4", "indirect negative feedback": "4.5", "relationship based": "6", "high context communication": "2.5", "Persuasion": "5", "argumentative": "10"}}
    NOTE: Please Reply in a JSON format only and no other format will be accepted. NO OTHER TEXT SHOULD BE PRESENT IN THE REPLY OTHER THAN THE JSON. NO INSTRUCTIONS SHOULD BE PRESENT IN THE REPLY OTHER THAN THE JSON.

    NOTE : Do not provide any kind of heading or introduction text in the output.
    \n\nAssistant:
    '''

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
        

        ################################* text_bison_compeletion ################################
        skills_rating = None
        response = None
        max_tries = 3  # because gpt3_completion function itself retries 3 times
        is_evaluated = True

        while max_tries > 0:
            try:
                logger.info({"****evaluate_skills_group_discussion_conversation ":f"trying [outer] text_bison_compeletion for {3 - max_tries + 1} time"})
                response = text_bison_compeletion(prompt)
                logger.info({"****evaluate_skills_group_discussion_conversation ":f"response [outer] text_bison_compeletion for {3 - max_tries + 1} time","response":response})
                
                skills_rating_str = json_extraction(response)

                skills_rating = json.loads(skills_rating_str)
                for skill in skills_rating:
                    skills_rating[skill] = float(skills_rating[skill])


                # skills_explanation = to_dict(skills_explanation_str)
                # responses.append(skills_explanation)

                break

            except Exception as e:
                logger.error({"****evaluate_skills_group_discussion_conversation ":f"failed [outer] text_bison_compeletion for {3 - max_tries + 1} time","error":e })
                max_tries -= 1
                if max_tries == 0:
                    is_evaluated = False
                    break

                time.sleep(1)
                continue

        if is_evaluated:
            return skills_rating

        ################################* text_bison_compeletion end ################################

        logger.info({"****evaluate_skills_group_discussion_conversation ":f"failed text_bison_compeletion, so trying anthropic_completion"})

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

    

    ################################* text_bison_compeletion ################################
    skills_explanation = None
    response = None
    max_tries = 3  # because gpt3_completion function itself retries 3 times
    is_evaluated = True

    while max_tries > 0:
        try:
            logger.info({"****evaluate_skills_explanation ":f"trying [outer] text_bison_compeletion for {3 - max_tries + 1} time"})
            response = text_bison_compeletion(prompt)
            logger.info({"****evaluate_skills_explanation ":f"response [outer] text_bison_compeletion for {3 - max_tries + 1} time","response":response})
            
            skills_explanation = json_extractor_for_explaination(response)
            # skills_explanation = json.loads(skills_explanation)
            if len(skills_explanation.keys()) != len(skills_rating.keys()):
                raise ValueError("skills count didn't matched")

            break

        except Exception as e:
            logger.error({"****evaluate_skills_explanation ":f"failed [outer] text_bison_compeletion for {3 - max_tries + 1} time","error":e })
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return skills_explanation

    ################################* text_bison_compeletion end ################################

    logger.info({"****evaluate_skills_explanation ":f"failed text_bison_compeletion, so trying anthropic_completion"})

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

    

    ################################* text_bison_compeletion ################################
    skills_explanation = None
    response = None
    max_tries = 3  # because gpt3_completion function itself retries 3 times
    is_evaluated = True

    while max_tries > 0:
        try:
            logger.info({"****evaluate_culture_skills_explanation ":f"trying [outer] text_bison_compeletion for {3 - max_tries + 1} time"})
            response = text_bison_compeletion(prompt)
            logger.info({"****evaluate_culture_skills_explanation ":f"response [outer] text_bison_compeletion for {3 - max_tries + 1} time","response":response})
            
            skills_explanation = json_extractor_for_explaination(response)
            # skills_explanation = json.loads(skills_explanation)
            if len(skills_explanation.keys()) != len(culture_skills_rating.keys()):
                raise ValueError("skills count didn't matched")
            
            break

        except Exception as e:
            logger.error({"****evaluate_culture_skills_explanation ":f"failed [outer] text_bison_compeletion for {3 - max_tries + 1} time","error":e })
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return skills_explanation

    ################################* text_bison_compeletion end ################################

    logger.info({"****evaluate_culture_skills_explanation ":f"failed text_bison_compeletion, so trying anthropic_completion"})

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


    ################################* text_bison_compeletion ################################
    skills_explanation = None
    response = None
    max_tries = 3  # because gpt3_completion function itself retries 3 times
    is_evaluated = True

    while max_tries > 0:
        try:
            logger.info({"****evaluate_skills_explanation_conversation ":f"trying [outer] text_bison_compeletion for {3 - max_tries + 1} time"})
            response = text_bison_compeletion(prompt)
            logger.info({"****evaluate_skills_explanation_conversation ":f"response [outer] text_bison_compeletion for {3 - max_tries + 1} time","response":response})
            
            skills_explanation = json_extractor_for_explaination(response)
            # skills_explanation = json.loads(skills_explanation)
            if len(skills_explanation.keys()) != len(skills_rating.keys()):
                raise ValueError("skills count didn't matched")

            break

        except Exception as e:
            logger.error({"****evaluate_skills_explanation_conversation ":f"failed [outer] text_bison_compeletion for {3 - max_tries + 1} time","error":e })
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return skills_explanation

    ################################* text_bison_compeletion end ################################

    logger.info({"****evaluate_skills_explanation_conversation ":f"failed text_bison_compeletion, so trying anthropic_completion"})

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


    ######################################* text_bison_compeletion *######################################
    skills_explanation = None
    response = None
    max_tries = 3  # because gpt3_completion function itself retries 3 times
    is_evaluated = True

    while max_tries > 0:
        try:
            logger.info({"**** evaluate_culture_skills_explanation_conversation ":f"trying [outer] text_bison_compeletion for {3 - max_tries + 1} time"})
            response = text_bison_compeletion(prompt)
            logger.info({"**** evaluate_culture_skills_explanation_conversation ":f"response [outer] text_bison_compeletion for {3 - max_tries + 1} time","response":response})
            
            skills_explanation = json_extractor_for_explaination(response)
            # skills_explanation = json.loads(skills_explanation)
            if len(skills_explanation.keys()) != len(culture_skills_rating.keys()):
                raise ValueError("skills count didn't matched")

            break

        except Exception as e:
            logger.error({"**** evaluate_culture_skills_explanation_conversation ":f"failed [outer] text_bison_compeletion for {3 - max_tries + 1} time","error":e })
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return skills_explanation

    ######################################* text_bison_compeletion end *######################################

    logger.info({"**** evaluate_culture_skills_explanation_conversation ":f"failed text_bison_compeletion, so trying anthropic_completion"})

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
    participant_skill_rating_object = SkillsRating.objects.filter(
        deleted=0,
        participant_id=participant.uid
    ).values(
        'skills_info',
        'total_questions_attempted',
        'total_tests_attempted'
    )


    participant_info = {
        "name": get_user_display_name(participant),
        "role": participant.role,
        "skills_info": participant_skill_rating_object[0].get('skills_info', {}),
        "total_questions_attempted": participant_skill_rating_object[0].get('total_questions_attempted', 0),
        "total_tests_attempted": participant_skill_rating_object[0].get('total_tests_attempted', 0)
    }

    return participant_info


@timeit
def get_top_participant_skills(skills, q_set, top_n=10):
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
    custom_rating_object.custom_rating = custom_rating
    custom_rating_object.save()


@timeit
def upsert_into_skill_index(tenant_id: str,
                            skills: list):
    if not skills:
        return

    for skill in skills:
        if not slugify(skill):
            continue

        SkillIndex.objects.get_or_create(tenant_id=tenant_id,
                                         name=skill,
                                         defaults=dict(display=skill))
