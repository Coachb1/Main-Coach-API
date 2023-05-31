import json

from django.utils.text import slugify

from commons.anthropic import anthropic_completion
from skills.models import SkillsRating, SkillIndex
from users.db import get_user_display_name
from users.models import User


def evaluate_response(question_text, response_text, skills):
    prompt = f'''
    "Question:" {question_text}; "Answer:" {response_text};
    "Required from anthropic:" Rate this answer as "very good", "good", "average", "bad", "very bad" in terms for each skill in the list in JSON: "{skills}" Reply "very good", "good", "average", "bad", "very bad" for each skill from the list in a JSON format
    '''

    is_evaluated = True
    response = None

    try:
        response = anthropic_completion(prompt, len(skills) * 50)
        response = json.loads(response)
        return response, is_evaluated
    except json.decoder.JSONDecodeError:
        is_evaluated = False

    return response, is_evaluated

def evaluate_conversation(conversation):

    cultural_skills = ['hierarchy', 'consensual', 'indirect negative feedback', 'relationship based', 'high context communication', 'Persuasion', 'argumentative']

    prompt = f'''
    "Conversation:" {conversation};
    "Required from anthropic:" Rate this conversation as "very good", "good", "average", "bad", "very bad" in terms for each behaviour trait in this cultural_list in JSON. 
    cultural_list: "{cultural_skills}" Reply "very good", "good", "average", "bad", "very bad" for each skill from the list in a JSON format
    Please put properties of JSON enclosed in double quotes. If you're not able to rate it then put "NA" as the rating for the respective skill.
    Example of JSON: {{"hierarchy": "very good", "consensual": "good", "indirect negative feedback": "average", "relationship based": "bad", "high context communication": "very bad", "Persuasion": "NA", "argumentative": "NA"}}
    '''

    is_evaluated = True

    try:
        response = anthropic_completion(prompt, len(cultural_skills) * 50)
        response = json.loads(response)
    except json.decoder.JSONDecodeError:
        is_evaluated = False

    # Convert "very good" to 5, "good" to 4, "average" to 3, "bad" to 2, "very bad" to 1, "NA" to 3
    for skill in response:
        if response[skill] == "very good":
            response[skill] = 5
        elif response[skill] == "good":
            response[skill] = 4
        elif response[skill] == "average":
            response[skill] = 3
        elif response[skill] == "bad":
            response[skill] = 2
        elif response[skill] == "very bad":
            response[skill] = 1
        elif response[skill] == "NA":
            response[skill] = 3

    return response, is_evaluated


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
    participants = sorted(participants, key=lambda x: x['average_score'], reverse=True)

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
