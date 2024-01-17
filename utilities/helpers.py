import requests
import pytz
import sys
import hmac
import hashlib
import datetime
import os
from dotenv import load_dotenv
from .models import SessionNotesRecommendations, MentorDetails, UserActionInfo
from tests.helpers import create_scenario_from_site_context
import json
import logging
from users.models import UserAttribute
from email_sender.helpers import send_session_notes_email
from commons.anthropic import anthropic_completion




logger = logging.getLogger(__name__)


load_dotenv()

def get_h(sid):
        def HMAC_SHA256(private_key="", message="", time=""):
            message += ":"

            if time:
                message += str(time)
            else:
                message += str(datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'))

            return hmac.new(str.encode(private_key), str.encode(message), hashlib.sha256).hexdigest()

        private_key = os.getenv('JOTURL_PRIVATE_KEY')
        gmt_datetime = str(datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'))

        return str(HMAC_SHA256(private_key, sid, gmt_datetime))

def get_pass_for_sid():
    try:
        def HMAC_SHA256(private_key="", message="", time=""):
            message += ":"

            if time:
                message += str(time)
            else:
                message += str(datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'))

            return hmac.new(str.encode(private_key), str.encode(message), hashlib.sha256).hexdigest()


        public_key = os.getenv("JOTURL_PUBLIC_KEY")
        private_key = os.getenv("JOTURL_PRIVATE_KEY")
        gmt_datetime = str(datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'))


        return HMAC_SHA256(private_key, public_key, gmt_datetime)

    except Exception as e:
        print(e)
        sys.exit(0)


def get_sid(email):
    password = get_pass_for_sid()
    url = f"https://joturl.com/a/i1/users/login?username={email}&password={password}"
    resp = requests.get(url)
    res = resp.json()
    session_id = res['result']['session_id']
    return session_id


def save_session_notes(user_id,mentor_id,tenant_id,context,access_token):
    
    mentor, is_created = MentorDetails.objects.get_or_create(mentor_id=mentor_id,tenant_id=tenant_id)

    mentees_ids = ""
    if mentor.mentee_ids :
        ids = mentor.mentee_ids.split(',')
        # ids.append(user_id)
        # ids = set(ids)
        # mentees_ids = ",".join(list(ids))
        
        if user_id not in ids:
            return [],{"error": "this user is not in your mentee list" } 
    else:
        return [], {"error": "no users in your mentee list"}
        
    # mentor.mentee_ids = mentees_ids
    # mentor.save(update_fields = ['mentee_ids'])


    session_notes = SessionNotesRecommendations.objects.create(
        tenant_id = tenant_id,
        mentor_id = mentor_id,
        mentee_id = user_id,
        session_notes = context,
        created_date = datetime.datetime.utcnow()
        )
    
    
    if access_token:
        context = json.dumps({"title":"","data":{"information":context}})
        try:
            recomm = create_scenario_from_site_context('',access_token,tenant_id,context)
            session_notes.recommendations = recomm['test_code']
            session_notes.save(update_fields=['recommendations'])
        except Exception as e:
            logger.error({"Error":e},exc_info=True)


    # sending email 
    try:
        mentor = UserAttribute.objects.get(user_id=session_notes.mentor_id)
        mentee = UserAttribute.objects.get(user_id=session_notes.mentee_id)
        mentor_name = mentor.get('name',None)
        mentor_email = mentor.get('email',None)
        mentee_name = mentee.get('name',None)
        mentee_email = mentee.get('email',None)
        
        to_email = [mentor_email,mentee_email]
        send_session_notes_email(to_email,mentor_email,mentor_name,mentee_email,mentee_name,session_notes.session_notes)
        logger.info("email sent..")
    except Exception as e:
        logger.error(f'failed to send email. {e}')
    
    
    return [{"context": session_notes.session_notes,"date" : session_notes.created_date,"updated":session_notes.updated_date,"recommendations": session_notes.recommendations}], {}
    

    
def get_session_notes(user_id,mentor_id):

    if user_id:
        session_notes = SessionNotesRecommendations.objects.filter(mentee_id = user_id)
    elif mentor_id:
        session_notes = SessionNotesRecommendations.objects.filter(mentor_id = mentor_id)

    data = []

    for session_note in session_notes:
        note = {
            "context": session_note.session_notes,
            "date" : session_note.created_date,
            "updated": session_note.updated_date,
            "recommendations": session_note.recommendations,
        }
        if user_id:
            mentor = UserAttribute.objects.get(user_id=session_note.mentor_id)
            email = mentor.attributes.get("email",None)
            name = mentor.attributes.get('name',None)
            note['mentor_email_id'] = email
            note['mentor_name'] = name

        elif mentor_id:
            mentee = UserAttribute.objects.get(user_id=session_note.mentee_id)
            email = mentee.attributes.get("email",None)
            name = mentee.attributes.get('name',None)
            note['mentee_email_id'] = email
            note['mentee_name'] = name
            
        data.append(note)

    return data


def get_session_notes_data(tenant_id):

    session_notes = SessionNotesRecommendations.objects.filter(tenant_id=tenant_id)
    data = []
    for notes in session_notes:
        temp = {
            "id": notes.id,
            "created":notes.created_date,
            "updated": notes.updated_date,
            "context": notes.session_notes,
            "recommendations": notes.recommendations
        }
        try:
            mentor = UserAttribute.objects.get(user_id=notes.mentor_id)
            mentee = UserAttribute.objects.get(user_id=notes.mentee_id)
            temp["mentor_name"] = mentor.get('name',None)
            temp["mentor_email"] = mentor.get('email',None)
            temp["mentee_name"] = mentee.get('name',None)
            temp["mentee_email"] = mentee.get('email',None)

        except Exception as e:
            logger.exception(f"failed to fetch attributes: {e}")
            

        data.append(temp)

    return data

def update_session_notes(session_note_id,recommendations):

    session_note = SessionNotesRecommendations.objects.get(id=session_note_id)

    session_note.recommendations = recommendations
    session_note.updated_date = datetime.datetime.utcnow()
    session_note.save(update_fields=['recommendations',"updated_date"])

    return {"message": "recommandations updated"}


def get_fitness_analysis_score(coach_data, conversation_data):
    prompt = f"""
    {{Coach_Information}} - {coach_data}
    Conversation: {conversation_data}

    Based on the conversation, check whether the coach and coachee are a suitable fit for each other based on their values, personality, ideas, experiences and expectations. Assign a score out of 10 to determine the compatibility between the coach and coachee. 

    NOTE: Please Reply in a valid JSON format only and no other format will be accepted.

    NOTE: Don't put any other text in the reply other than the JSON.

    NOTE: Output Format Example: {{"Fitment score":"1"}}

    NOTE: Do not add any other sentence, information or explanation in the output. Only provide the output in the format given above.
    """

    logger.info(f"Fitment Prompt: {prompt}")

    response = anthropic_completion(prompt,5000)
    return response


def save_user_action_info(tenant,user_id,for_):
    action_info, is_created = UserActionInfo.objects.get_or_create(
                    tenant_id = tenant.uid,
                    user_id = user_id,
                )

    setattr(action_info, for_, getattr(action_info, for_) + 1)  # increasing fields by 1
    action_info.save(update_fields=[for_])

def extract_fields(data:dict):
    extracted_fields = []
    for key, value in data.items():
        field = {"name": key}
        if isinstance(value, list):
            field["type"] = "dropdown"
            field['options'] = value
        elif "boolean" in value:
            field["type"] = "bool"
        else:
            field["type"] = "text"
            field['placeholder'] = value
        extracted_fields.append(field)

    return extracted_fields