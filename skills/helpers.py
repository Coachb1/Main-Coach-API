import json
import random
import time
import logging

from django.utils.text import slugify

from commons.anthropic import anthropic_completion
from commons.openai_gpt import gpt4_completion
from external_apis.slack_alert_api import send_slack_message
from skills.models import SkillsRating, SkillIndex
from users.db import get_user_display_name
from users.models import User


logger = logging.getLogger(__name__)


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

    NOTE: Check if the response provided is relevant to the question or irrelevant. If the response is irrelevant put "relevance" 0 otherwise 1.

    NOTE: Output Format Example: {{"skill1": "4.5", "skill2": "9", "skill3": "2.5","relevance":"1"}}

    NOTE:  For the entire question and answer conversation no two skills from {skills} can have exact same scores.

    NOTE: Do not add any English language sentence in the output.


'''

    is_evaluated = True
    response = None

    max_tries = 1  # because anthropic_completion function itself retries 3 times

    while max_tries > 0:
        try:
            response = anthropic_completion(prompt, len(skills) * 50)
            response = json.loads(response)
            for skill in response:
                response[skill] = float(response[skill])
            break
        except:
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return response, is_evaluated

    is_evaluated = True
    response = None
    max_tries = 1  # because gpt4_completion function itself retries 3 times

    while max_tries > 0:
        try:
            response = gpt4_completion(prompt, stop=["USER:", "CoachBot"]).text
            if '"REPLY:"' in response:
                response = response.split('"REPLY:"')[1].strip()
            response = json.loads(response)
            for skill in response:
                response[skill] = float(response[skill])

            break

        except:
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    try:
        logger.info({
            'message': '#### Got Skills Rating for session ###',
            'SESSION_ID': session_id,
            'TEST_CODE': test_code,
            'SKILLS_Rating': response
            })
    except:
        pass

    if is_evaluated:
        return response, is_evaluated

    # HACK in case everything fails; just evaluate as a random number
    response = {}
    for skill in skills:
        response[skill] = random.randint(3, 7)

    # send error on slack to debug this
    send_slack_message({"process": "evaluate_response",
                        "test_question_response": test_question_response.uid,
                        "error": "failed to evaluate; putting random value"})

    return response, True

def evaluate_response_skill(test_attempt_session, conversation, test_title, test_description, test_code,skills):
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

    prompt = f'''
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

        NOTE: Don't put any other text in the reply other than the JSON. The keys in json object must be taken from {skills_rating} only.

        NOTE: For the entire conversation no two skills from {skills_rating} can have exact same scores.

        NOTE: Do not add any English language sentence in the output.

    '''

    is_evaluated = True

    response = {}
    max_tries = 1  # because anthropic_completion function itself retries 3 times

    while max_tries > 0:
        try:
            response = anthropic_completion(prompt, len(skills_rating) * 50)
            response = json.loads(response)
            for skill in response:
                response[skill] = float(response[skill])

            break

        except:
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    try:
        logger.info({
                    'message': '#### Got skill Rating from anthropic ###',
                    'SESSION_ID': test_attempt_session.uid,
                    'TEST_CODE': test_code,
                    'SKILLS_RATING': response
                    })
    except Exception as e:
        pass

    if is_evaluated:
        return response, is_evaluated

    response = None
    max_tries = 1  # because gpt4_completion function itself retries 3 times
    is_evaluated = True

    while max_tries > 0:
        try:
            response = gpt4_completion(prompt, stop=["USER:", "CoachBot"]).text
            if '"REPLY:"' in response:
                response = response.split('"REPLY:"')[1].strip()
            response = json.loads(response)
            for skill in response:
                response[skill] = float(response[skill])

            break

        except:
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    try:
        logger.info({
                    'message': '#### Got skill Rating from open ai after angropic failed ###',
                    'SESSION_ID': test_attempt_session.uid,
                    'TEST_CODE': test_code,
                    'SKILLS_RATING': response
                    })
    except Exception as e:
        pass

    if is_evaluated:
        return response, is_evaluated

    # HACK in case everything fails; just evaluate as a random number
    response = {}
    for skill in skills_rating:
        response[skill] = random.randint(3, 7)

    # send error on slack to debug this
    send_slack_message({"process": "evaluate_response_skills",
                        "test_attempt_session": test_attempt_session.uid,
                        "error": "failed to evaluate; putting random value"})

    return response, True


def evaluate_conversation(test_attempt_session, conversation, test_title, test_description, test_code):

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

    prompt = f'''
        "TITLE:" {test_title};

        "DESCRIPTION:" {test_description};

        "CONVERSATION:" {conversation};

        "Evaluation Criteria:"
        - Hierarchy:  Does the conversation look like the participants have strict hierarchical relationship (highest score of 10) or casual professional relationship ( scores 0)?
        - Consensual: Does the conversation looks like the respondents have respect for boundary and empathy? ( High yes score 10 and the low is 0) 
        - Indirect negative feedback: Do the participants provide a subtle feedback or a blunt feedback? (Subtle feedback is 10 and blunt feedback is 0)
        - Relationship-based: Does the conversation look like the participants focus on relationships (highest score of 10) or tasks (scores 0)?    
        - High context communication:  Does the conversation look like the participants focus on subtle cues (highest score of 0) or explicit verbal communication (scores 10)? 
        - Persuasion : Does the conversation look like the participants value emotional appeals (highest score of 10) or completely rely on logic and evidence (scores 0)?  
        - Argumentative : Does the conversation look like the participants see debate and disagreement as a competition (highest score of 0) or view it as a collaborative process to find truth (scores 10)? 

        "Required from anthropic:" Based on the above criteria please evaluate the entire conversation - which is a list of all questions and answers. Rate the criteria's only from a scale of 1.5-9 in such a way that no two skills can have the exact same score, with scores in increments of 0.5 for each behavior trait listed above which corresponds to this cultural_list in JSON.
        "cultural_list:" "{cultural_skills}"

        NOTE: Please put properties of JSON enclosed in double quotes.

        Example of JSON: {{"hierarchy": "9.5", "consensual": "4", "indirect negative feedback": "4.5", "relationship-based": "6", "high context communication": "2.5", "Persuasion": "5", "argumentative": "10"}}

        NOTE: For the entire conversation no two skills from {cultural_skills} can have exact same scores.

        NOTE: Do not add any English language sentence in the output.

    '''

    is_evaluated = True

    response = {}
    max_tries = 1  # because anthropic_completion function itself retries 3 times

    while max_tries > 0:
        try:
            response = anthropic_completion(prompt, len(cultural_skills) * 50)
            response = json.loads(response)
            for skill in response:
                response[skill] = float(response[skill])

            break

        except:
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    try:
        logger.info({
                    'message': '#### Got culture Rating from anthropic ###',
                    'SESSION_ID': test_attempt_session.uid,
                    'TEST_CODE': test_code,
                    'CULTURE_SKILLS': response
                    })
    except Exception as e:
        pass

    if is_evaluated:
        return response, is_evaluated

    response = None
    max_tries = 1  # because gpt4_completion function itself retries 3 times
    is_evaluated = True

    while max_tries > 0:
        try:
            response = gpt4_completion(prompt, stop=["USER:", "CoachBot"]).text
            if '"REPLY:"' in response:
                response = response.split('"REPLY:"')[1].strip()
            response = json.loads(response)
            for skill in response:
                response[skill] = float(response[skill])

            break

        except:
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    try:
        logger.info({
                    'message': '#### Got culture Rating from open ai after angropic failed ###',
                    'SESSION_ID': test_attempt_session.uid,
                    'TEST_CODE': test_code,
                    'CULTURE_SKILLS': response
                    })
    except Exception as e:
        pass

    if is_evaluated:
        return response, is_evaluated

    # HACK in case everything fails; just evaluate as a random number
    response = {}
    for skill in cultural_skills:
        response[skill] = random.randint(3, 7)

    # send error on slack to debug this
    send_slack_message({"process": "evaluate_conversation",
                        "test_attempt_session": test_attempt_session.uid,
                        "error": "failed to evaluate; putting random value"})

    return response, True


def evaluate_group_discussion_conversation(test_attempt_session, conversation, user_persona, objective, test_code):
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

    prompt = f'''
    "Objective:" {objective};

    "Conversation:" {conversation};

    "Required from anthropic:" Based on the above criteria please evaluate the "{user_persona}" only from a scale of 1.5-9, with scores in increments of 0.5. Evaluate the conversation for the participant: "{user_persona}" and this "{user_persona}" only, in this conversation for each behaviour trait in this cultural_list in JSON.

    "cultural_list:" "{cultural_skills}"

    Please put properties of JSON enclosed in double quotes.

    Example of JSON: {{"hierarchy": "9.5", "consensual": "4", "indirect negative feedback": "4.5", "relationship based": "6", "high context communication": "2.5", "Persuasion": "5", "argumentative": "10"}}

    NOTE: Do not add any English language sentence in the output.
    '''

    response = None
    is_evaluated = True
    max_tries = 1  # because anthropic_completion function itself retries 3 times

    while max_tries > 0:
        try:
            response = anthropic_completion(prompt, len(cultural_skills) * 50)
            response = json.loads(response)
            for skill in response:
                response[skill] = float(response[skill])

            break

        except:
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    try:
        logger.info({
                    'message': '#### Got culture Rating for session ###',
                    'SESSION_ID': test_attempt_session.uid,
                    'TEST_CODE': test_code,
                    'CULTURE_rating': response
                    })
    except Exception as e:
        pass
        

    if is_evaluated:
        return response

    is_evaluated = True
    response = None
    max_tries = 1  # because gpt4_completion function itself retries 3 times

    while max_tries > 0:
        try:
            response = gpt4_completion(prompt, stop=["USER:", "CoachBot"]).text
            if '"REPLY:"' in response:
                response = response.split('"REPLY:"')[1].strip()
            response = json.loads(response)
            for skill in response:
                response[skill] = float(response[skill])

            break

        except:
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return response

    # HACK in case everything fails; just evaluate as a random number
    response = {}
    for skill in cultural_skills:
        response[skill] = random.randint(3, 7)

    # send error on slack to debug this
    send_slack_message({"process": "evaluate_group_discussion_conversation",
                        "test_attempt_session": test_attempt_session.uid,
                        "error": "failed to evaluate; putting random value"})

    return response


def evaluate_skills_group_discussion_conversation(test_attempt_session, conversation, user_persona, objective, skills_to_evaluate):
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

    prompt = f'''
    "Objective:" {objective};

    "Conversation:" {conversation};

    "Required from anthropic:" Based on the above criteria please evaluate the "{user_persona}" on a scale of 0-10, with scores in increments of 0.5. Evaluate the conversation for the participant: "{user_persona}" and this "{user_persona}" only in this conversation for each behaviour trait in this skills_list in JSON in such a way that no two skills can have the exact same score.

    "skills_list:" "{skills_to_evaluate}"

    Please put properties of JSON enclosed in double quotes.

    Example of JSON: {{"hierarchy": "9.5", "consensual": "4", "indirect negative feedback": "4.5", "relationship based": "6", "high context communication": "2.5", "Persuasion": "5", "argumentative": "10"}}

    NOTE: Please Reply in a JSON format only and no other format will be accepted. NO OTHER TEXT SHOULD BE PRESENT IN THE REPLY OTHER THAN THE JSON. NO INTRUCTIONS SHOULD BE PRESENT IN THE REPLY OTHER THAN THE JSON.

    NOTE: For the entire conversation no two skills from can have exact same scores.

    NOTE: Do not add any English language sentence in the output.'''

    response = None
    is_evaluated = True
    max_tries = 1  # because anthropic_completion function itself retries 3 times

    while max_tries > 0:
        try:
            response = anthropic_completion(
                prompt, len(skills_to_evaluate) * 50)
            response = json.loads(response)
            for skill in response:
                response[skill] = float(response[skill])
            break
        except:
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return response

    response = None
    max_tries = 1  # because gpt4_completion function itself retries 3 times
    is_evaluated = True

    while max_tries > 0:
        try:
            response = gpt4_completion(prompt, stop=["USER:", "CoachBot"]).text
            if '"REPLY:"' in response:
                response = response.split('"REPLY:"')[1].strip()
            response = json.loads(response)
            for skill in response:
                response[skill] = float(response[skill])

            break

        except:
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return response

    # HACK in case everything fails; just evaluate as a random number
    response = {}
    for skill in skills_to_evaluate:
        response[skill] = random.randint(3, 7)

    # send error on slack to debug this
    send_slack_message({"process": "evaluate_skills_group_discussion_conversation",
                        "test_attempt_session": test_attempt_session.uid,
                        "error": "failed to evaluate; putting random value"})

    return response


def top_N_leadership_board(skills, N, tenant_id):
    # Get all skills_rating objects of this tenant
    skill_rating_objects = SkillsRating.objects.filter(
        deleted=0,
        tenant_id=tenant_id
    )

    participants = []

    original_skills_required = skills

    for obj in skill_rating_objects:

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
        "skills_info": participant_skill_rating_object[0]['skills_info'],
        "total_questions_attempted": participant_skill_rating_object[0]['total_questions_attempted'],
        "total_tests_attempted": participant_skill_rating_object[0]['total_tests_attempted']
    }

    return participant_info


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


def save_the_custom_rating(custom_rating, custom_rating_object):
    custom_rating_object.custom_rating = custom_rating
    custom_rating_object.save()


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
