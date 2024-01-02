import requests
import pytz
import sys
import hmac
import hashlib
import datetime
import os
from dotenv import load_dotenv
from .models import SessionNotesRecommendations, MentorDetails
from tests.helpers import create_scenario_from_site_context
import json
import logging
from users.models import UserAttribute



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
        ids.append(user_id)
        ids = set(ids)
        mentees_ids = ",".join(list(ids))
    else:
        mentees_ids = user_id
        
    mentor.mentee_ids = mentees_ids
    mentor.save(update_fields = ['mentee_ids'])


    session_notes = SessionNotesRecommendations.objects.create(
        tenant_id = tenant_id,
        mentor_id = mentor_id,
        mentee_id = user_id,
        session_notes = context,
        created_date = datetime.datetime.utcnow().date(),
        updated_date = datetime.datetime.utcnow().date()
        )
    
    
    if access_token:
        context = json.dumps({"title":"","data":{"information":context}})
        try:
            recomm = create_scenario_from_site_context('',access_token,tenant_id,context)
            session_notes.recommendations = recomm['test_code']
            session_notes.save(update_fields=['recommendations'])
        except Exception as e:
            logger.error({"Error":e},exc_info=True)
    
    return [{"context": session_notes.session_notes,"date" : datetime.datetime.utcnow().date(),"recommendations": session_notes.recommendations}]
    

    
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
            "recommendations": session_note.recommendations,
        }
        if user_id:
            mentor = UserAttribute.objects.get(user_id=session_note.mentee_id)
            email = mentor.attributes.get("email",None)
            name = mentor.attributes.get('name',None)
            note['mentor_email_id'] = email
            note['mentor_name'] = name
        data.append(note)

    return data

