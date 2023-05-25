from commons.anthropic import anthropic_completion
import json
from django.db.models import Sum

from skills.models import SkillsRating
from users.models import User

from tests.models import TestAttemptSession
from tests.choices import TestAttemptSessionStatusChoices

def evaluate_response(question_text, response_text, skills):
    prompt = f'''
    "Question:" {question_text}; "Answer:" {response_text};
    "Required from anthropic:" Rate this answer as "very good", "good", "average", "bad", "very bad" in terms for each skill in the list in JSON: "{skills}" Reply "very good", "good", "average", "bad", "very bad" for each skill from the list in a JSON format
    '''

    response = anthropic_completion(prompt, len(skills) * 20)

    return json.loads(response)

def top_N_leadership_board(skills, N):

    top_participants = SkillsRating.objects.filter(
        deleted=0,
        skills_info__has_any_keys=skills
    ).values(
        'participant_id',
        'tenant_id',
        # average scores for each skill in skills list
        *[f'skills_info__{skill}__average_score' for skill in skills]
            ).order_by(
        # sum of average scores for each skill in skills list
        *[f'-skills_info__{skill}__average_score' for skill in skills]
    )[:N]
    
    return top_participants

def top_participants_for_test(test_id):

    # Get objects of TestAttemptSession for the test_id and status=completed and sorted by test_score
    test_attempt_sessions = TestAttemptSession.objects.filter(
        deleted=0,
        test_id=test_id,
        status=TestAttemptSessionStatusChoices.completed
    ).order_by(
        '-test_score'
    )

    return test_attempt_sessions

def get_participant_info(participant_id):

    # get user from participant_id as uid
    participant = User.objects.get(uid=participant_id)

    participant_skill_rating_object = SkillsRating.objects.filter(
        deleted=0,
        participant_id=participant_id
    ).values(
        'skills_info',
        'total_questions_attempted',
        'total_tests_attempted'
    )

    participant_info = {
        "name": participant.name,
        "role": participant.role,
        "skills_info": participant_skill_rating_object[0]['skills_info'],
        "total_questions_attempted": participant_skill_rating_object[0]['total_questions_attempted'],
        "total_tests_attempted": participant_skill_rating_object[0]['total_tests_attempted']
    }


    return participant_info

