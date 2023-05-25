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

    response = anthropic_completion(prompt, len(skills) * 20)

    return json.loads(response)


def top_N_leadership_board(skills, N, tenant_id):
    top_participants = SkillsRating.objects.filter(
        deleted=0,
        skills_info__has_any_keys=skills,
        tenant_id=tenant_id
    ).order_by(
        # sum of average scores for each skill in skills list
        *[f'-skills_info__{skill}__average_score' for skill in skills]
    )[:N]

    # get participants name 
    for participant in top_participants:
        participant.name = get_user_display_name(User.objects.get(uid=participant.participant_id))

    return top_participants


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
