import json
import time

from django.utils.text import slugify

from commons.anthropic import anthropic_completion
from commons.openai_gpt import gpt4_completion
from skills.models import SkillsRating, SkillIndex
from users.db import get_user_display_name
from users.models import User


def evaluate_response(question_text, response_text, skills, test_description, test_title):
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

    "REQUIRED FROM ANTHROPIC:" Based on the above criteria please evaluate the given answer on a scale of 0-10, with scores in increments of 0.5 for each skill in the list in JSON: "{skills}".
    
    NOTE: Please put properties of JSON enclosed in double quotes.

    NOTE: Please Reply in a JSON format only and no other format will be accepted.

    NOTE: Don't put any other text in the reply other than the JSON. The keys in json object must be choosen from {skills} only.

    NOTE: Output Format Example: {{"skill1": "4.5", "skill2": "10", "skill3": "2.5"}}
    '''

    is_evaluated = True
    response = None

    max_tries = 3

    while max_tries > 0:
        try:
            response = anthropic_completion(prompt, len(skills) * 50)
            response = json.loads(response)
            for skill in response:
                response[skill] = float(response[skill])

            break

        except json.decoder.JSONDecodeError or ValueError:
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return response, is_evaluated

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

        except json.decoder.JSONDecodeError or ValueError:
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return response, is_evaluated

    response = {}
    for skill in skills:
        response[skill] = 5

    return response, True


def evaluate_conversation(conversation, test_title, test_description):

    cultural_skills = ['hierarchy', 'consensual', 'indirect negative feedback',
                       'relationship based', 'high context communication', 'Persuasion', 'argumentative']

    prompt = f'''
    "TITLE:" {test_title};

    "DESCRIPTION:" {test_description};

    "CONVERSATION:" {conversation};

    "Evaluation Criteria:"
    - Relevance: Does the answers directly address the questions in the conversation?
    - Accuracy: Is the information in the answers correct?
    - Completeness: Does the answers provide a comprehensive response to the questions?
    - Clarity: Are the answers well-written and easy to understand?

    "Required from anthropic:" Based on the above criteria please evaluate the given answers on a scale of 0-10, with scores in increments of 0.5 for each behaviour trait in this cultural_list in JSON. 

    "cultural_list:" "{cultural_skills}"

    NOTE: Please put properties of JSON enclosed in double quotes.

    Example of JSON: {{"hierarchy": "9.5", "consensual": "4", "indirect negative feedback": "4.5", "relationship based": "6", "high context communication": "2.5", "Persuasion": "5", "argumentative": "10"}}
    '''

    is_evaluated = True

    response = {}
    max_tries = 3

    while max_tries > 0:
        try:
            response = anthropic_completion(prompt, len(cultural_skills) * 50)
            response = json.loads(response)
            for skill in response:
                response[skill] = float(response[skill])

            break

        except json.decoder.JSONDecodeError or ValueError:
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return response, is_evaluated

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

        except json.decoder.JSONDecodeError or ValueError:
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return response, is_evaluated

    response = {}
    for skill in cultural_skills:
        response[skill] = 5

    return response, True


def evaluate_group_discussion_conversation(conversation, user_persona, objective):
    cultural_skills = ['hierarchy', 'consensual', 'indirect negative feedback',
                       'relationship based', 'high context communication', 'Persuasion', 'argumentative']

    prompt = f'''
    "Objective:" {objective};

    "Conversation:" {conversation};

    "Required from anthropic:" Based on the above criteria please evaluate the "{user_persona}" on a scale of 0-10, with scores in increments of 0.5. Evaluate the conversation for the participant: "{user_persona}" and this "{user_persona}" only, in this conversation for each behaviour trait in this cultural_list in JSON. 

    "cultural_list:" "{cultural_skills}"

    Please put properties of JSON enclosed in double quotes.

    Example of JSON: {{"hierarchy": "9.5", "consensual": "4", "indirect negative feedback": "4.5", "relationship based": "6", "high context communication": "2.5", "Persuasion": "5", "argumentative": "10"}}
    '''

    response = None
    is_evaluated = True
    max_tries = 3

    while max_tries > 0:
        try:
            response = anthropic_completion(prompt, len(cultural_skills) * 50)
            response = json.loads(response)
            for skill in response:
                response[skill] = float(response[skill])

            break

        except json.decoder.JSONDecodeError or ValueError:
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

    while max_tries > 0:
        try:
            response = gpt4_completion(prompt, stop=["USER:", "CoachBot"]).text
            if '"REPLY:"' in response:
                response = response.split('"REPLY:"')[1].strip()
            response = json.loads(response)
            for skill in response:
                response[skill] = float(response[skill])

            break

        except json.decoder.JSONDecodeError or ValueError:
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return response

    response = {}
    for skill in cultural_skills:
        response[skill] = 5

    return response


def evaluate_skills_group_discussion_conversation(conversation, user_persona, objective):
    normal_skills = ["good", "very good", 'bad']

    prompt = f'''
    "Objective:" {objective};

    "Conversation:" {conversation};

    "Required from anthropic:" Based on the above criteria please evaluate the "{user_persona}" on a scale of 0-10, with scores in increments of 0.5. Evaluate the conversation for the participant: "{user_persona}" and this "{user_persona}" only, in this conversation for each behaviour trait in this cultural_list in JSON. 

    "cultural_list:" "{normal_skills}"

    Please put properties of JSON enclosed in double quotes.

    Example of JSON: {{"hierarchy": "9.5", "consensual": "4", "indirect negative feedback": "4.5", "relationship based": "6", "high context communication": "2.5", "Persuasion": "5", "argumentative": "10"}}
    '''

    response = None
    is_evaluated = True
    max_tries = 3

    while max_tries > 0:
        try:
            response = anthropic_completion(prompt, len(normal_skills) * 50)
            response = json.loads(response)
            for skill in response:
                response[skill] = float(response[skill])

            break

        except json.decoder.JSONDecodeError or ValueError:
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

    while max_tries > 0:
        try:
            response = gpt4_completion(prompt, stop=["USER:", "CoachBot"]).text
            if '"REPLY:"' in response:
                response = response.split('"REPLY:"')[1].strip()
            response = json.loads(response)
            for skill in response:
                response[skill] = float(response[skill])

            break

        except json.decoder.JSONDecodeError or ValueError:
            max_tries -= 1
            if max_tries == 0:
                is_evaluated = False
                break

            time.sleep(1)
            continue

    if is_evaluated:
        return response

    response = {}
    for skill in normal_skills:
        response[skill] = 5

    return response


def top_N_leadership_board(skills, N, tenant_id):
    # Get all skills_rating objects of this tenant
    skill_rating_objects = SkillsRating.objects.filter(
        deleted=0,
        tenant_id=tenant_id
    )

    participants = []

    for obj in skill_rating_objects:

        skills_info = obj.skills_info
        average_score = 0
        skills_dict = {}

        if len(skills) == 1 and skills[0].lower() == 'all':
            skills = skills_info.keys()

        for skill in skills:
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
