import requests
import pytz
import sys
import hmac
import hashlib
import datetime
import os
from dotenv import load_dotenv
from .models import LLMMappingTable, SessionNotesRecommendations, MentorDetails, UserActionInfo, UserIDP
from tests.helpers import create_scenario_from_site_context
import json
import logging
from users.models import UserAttribute
from email_sender.helpers import send_session_notes_email
from commons.anthropic import anthropic_completion
from apis.accounts.serializers import UserIDPSerializers
from string import Template
from commons.utils import generic_completion
import re
from tests.choices import TestTypeChoices
from settings import FRONTEND_BASE_URL
from users.models import User, CoachCoacheeConnection, CoachCoacheeMentorMenteeProfile, SignatureBot, BotAttribute
from .prompts import get_focus_prompt, get_goals_prompt, get_priority_prompt
from email_sender.helpers import send_email_with_html_template
from users.db import get_user_by_id, get_user_display_name
from utilities.models import BotEngagement
from commons.notifications import send_error_notification
from commons.google_apis import gemini_completion





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


def save_session_notes(user_id,mentor_id,tenant_id,context,access_token, simulation_codes=None):
    """
    This function is used to save session notes and recommendations for a specific mentor-mentee pair.

    The function first checks if the mentor and mentee are connected. If they are not, an error message is returned.
    If they are connected, a new SessionNotesRecommendations object is created with the provided session notes.
    The function then increments the session_notes_count for the user.
    If an access token is provided, the function generates a scenario from the session notes and saves it as a recommendation.
    Finally, the function attempts to send an email to the mentor and mentee with the session notes.

    Parameters:
    - user_id (str): The ID of the user (mentee).
    - mentor_id (str): The ID of the mentor.
    - tenant_id (str): The ID of the tenant.
    - context (str): The session notes to be saved.
    - access_token (str): The access token for authentication.

    Returns:
    - A list containing a dictionary with the session notes, creation date, update date, and recommendations, if successful.
    - An empty list and a dictionary containing an error message, if unsuccessful.

    Example Usage:
    save_session_notes("user123", "mentor123", "tenant123", "These are the session notes.", "access_token")
    """

    commentor = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,tenant_id=tenant_id,user_id=mentor_id).first()
    reciever = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,tenant_id=tenant_id,user_id=user_id).first()
    logger.info(f"coach: {commentor}, coachee: {reciever}")
    connections = CoachCoacheeConnection.objects.filter(deleted=False,tenant_id=tenant_id,coach_id=commentor.uid,coachee_id=reciever.uid)
    
    if connections.count() == 0:
        connections = CoachCoacheeConnection.objects.filter(deleted=False,tenant_id=tenant_id,coach_id=reciever.uid,coachee_id=commentor.uid)

    if connections.count() == 0:
        return [],{"error": "This user is not in your connection list" } 
    
    mentor, is_created = MentorDetails.objects.get_or_create(mentor_id=mentor_id,tenant_id=tenant_id)

    # mentees_ids = ""
    # if mentor.mentee_ids :
    #     ids = mentor.mentee_ids.split(',')
    #     # ids.append(user_id)
    #     # ids = set(ids)
    #     # mentees_ids = ",".join(list(ids))
        
    #     if user_id not in ids:
    #         return [],{"error": "this user is not in your mentee list" } 
    # else:
    #     return [], {"error": "no users in your mentee list"}
        
    # mentor.mentee_ids = mentees_ids
    # mentor.save(update_fields = ['mentee_ids'])


    session_notes = SessionNotesRecommendations.objects.create(
        tenant_id = tenant_id,
        mentor_id = mentor_id,
        mentee_id = user_id,
        session_notes = context,
        created_date = datetime.datetime.utcnow(),
        simulation_codes = simulation_codes,
        )
    
    save_user_action_info(tenant_id,user_id,"session_notes_count")
    
    # if access_token:
    #     logger.info(f"commentor: {commentor.profile_type},reciever:{reciever.profile_type}")
    #     if reciever.profile_type != "coach":

    #         context = json.dumps({"title":"","data":{"information":context}})
    #         try:
    #             recomm = create_scenario_from_site_context('',access_token,tenant_id,context)
    #             session_notes.recommendations = recomm['test_code']
    #             session_notes.save(update_fields=['recommendations'])
    #         except Exception as e:
    #             logger.error({"Error":e},exc_info=True)

    # sending email 
    try:
        
        mentor = UserAttribute.objects.get(user_id=session_notes.mentor_id).attributes
        mentee = UserAttribute.objects.get(user_id=session_notes.mentee_id).attributes
        mentor_name = get_user_display_name(get_user_by_id(user_id=session_notes.mentor_id))
        mentor_email = mentor.get('email',None)
        mentee_name = get_user_display_name(get_user_by_id(user_id=session_notes.mentee_id))
        mentee_email = mentee.get('email',None)
        
        to_email = [mentor_email,mentee_email]
        send_session_notes_email(to_email,mentor_email,mentor_name,mentee_email,mentee_name,session_notes.session_notes)
        logger.info("email sent..")
    except Exception as e:
        logger.error(f'failed to send email. {e}')
        send_error_notification("save_session_notes",f"failed to send email: {e}",{"mentor_id":mentor_id,"mentee_id":user_id,"tenant_id":tenant_id,"context":context})
    
    
    return [{"context": session_notes.session_notes,"date" : session_notes.created_date,"updated":session_notes.updated_date,"recommendations": session_notes.recommendations}], {}
    

    
def get_session_notes(user_id,mentor_id):
    """
    Fetches session notes and recommendations for a specific user or mentor.

    This function retrieves session notes and recommendations from the SessionNotesRecommendations model. 
    It filters the data based on either the user_id (mentee) or mentor_id provided as input. 
    For each session note, it also fetches the corresponding mentor or mentee's email and display name from the UserAttribute model.

    Args:
        user_id (str): The unique identifier of the user (mentee). If provided, the function will fetch session notes where the user is the mentee.
        mentor_id (str): The unique identifier of the mentor. If provided, the function will fetch session notes where the user is the mentor.

    Note: At least one of user_id or mentor_id must be provided. If both are provided, the function will prioritize the user_id.

    Returns:
        list: A list of dictionaries, where each dictionary represents a session note. Each dictionary contains the following keys:
            - 'context': The session note text.
            - 'date': The date the session note was created.
            - 'updated': The date the session note was last updated.
            - 'recommendations': The recommendations text.
            - 'mentor_email_id' or 'mentee_email_id': The email of the mentor or mentee, depending on whether user_id or mentor_id was provided.
            - 'mentor_name' or 'mentee_name': The display name of the mentor or mentee, depending on whether user_id or mentor_id was provided.

    Example:
        >>> get_session_notes(user_id='123', mentor_id=None)
        [{'context': 'Session note 1', 'date': datetime.datetime(2022, 1, 1, 0, 0), 'updated': datetime.datetime(2022, 1, 2, 0, 0), 'recommendations': 'Recommendation 1', 'mentor_email_id': 'mentor@example.com', 'mentor_name': 'Mentor Name'}]
    """

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
            "simulation_codes": session_note.simulation_codes
        }
        if user_id:
            
            mentor = UserAttribute.objects.get(user_id=session_note.mentor_id)
            email = mentor.attributes.get("email",None)
            note['mentor_email_id'] = email
            note['mentor_name'] = get_user_display_name(get_user_by_id(user_id=mentor.user_id))

        elif mentor_id:
            mentee = UserAttribute.objects.get(user_id=session_note.mentee_id)
            email = mentee.attributes.get("email",None)
            note['mentee_email_id'] = email
            note['mentee_name'] = get_user_display_name(get_user_by_id(user_id=mentee.user_id))
            
        data.append(note)

    return data


def get_session_notes_data(tenant_id):
    """
    Fetches session notes and recommendations for a specific tenant.

    This function retrieves session notes and recommendations from the SessionNotesRecommendations model. 
    It filters the data based on the tenant_id provided as input. 
    For each session note, it also fetches the corresponding mentor and mentee's email and name from the UserAttribute model.

    Args:
        tenant_id (str): The unique identifier of the tenant. The function will fetch session notes associated with this tenant.

    Returns:
        list: A list of dictionaries, where each dictionary represents a session note. Each dictionary contains the following keys:
            - 'id': The unique identifier of the session note.
            - 'created': The date the session note was created.
            - 'updated': The date the session note was last updated.
            - 'context': The session note text.
            - 'recommendations': The recommendations text.
            - 'mentor_name': The name of the mentor.
            - 'mentor_email': The email of the mentor.
            - 'mentee_name': The name of the mentee.
            - 'mentee_email': The email of the mentee.

    Note: If the function fails to fetch the mentor or mentee's attributes, it logs the exception and continues to the next session note.

    Example:
        >>> get_session_notes_data(tenant_id='123')
        [{'id': 1, 'created': datetime.datetime(2022, 1, 1, 0, 0), 'updated': datetime.datetime(2022, 1, 2, 0, 0), 'context': 'Session note 1', 'recommendations': 'Recommendation 1', 'mentor_name': 'Mentor Name', 'mentor_email': 'mentor@example.com', 'mentee_name': 'Mentee Name', 'mentee_email': 'mentee@example.com'}]
    """

    session_notes = SessionNotesRecommendations.objects.filter(tenant_id=tenant_id)
    data = []
    for notes in session_notes:
        temp = {
            "id": notes.id,
            "created":notes.created_date,
            "updated": notes.updated_date,
            "context": notes.session_notes,
            "recommendations": notes.recommendations,
            "simulation_codes": notes.simulation_codes,
        }
        try:
            mentor = UserAttribute.objects.get(user_id=notes.mentor_id)
            mentee = UserAttribute.objects.get(user_id=notes.mentee_id)
            temp["mentor_name"] = get_user_display_name(get_user_by_id(user_id=notes.mentor_id))
            temp["mentor_email"] = mentor.get('email',None)
            temp["mentee_name"] = get_user_display_name(get_user_by_id(user_id=notes.mentee_id))
            temp["mentee_email"] = mentee.get('email',None)

        except Exception as e:
            logger.exception(f"failed to fetch attributes: {e}")
            

        data.append(temp)

    return data

def update_session_notes(session_note_id,recommendations,simulation_codes=None):
    "it updates recommendations into session_notes"

    session_note = SessionNotesRecommendations.objects.get(id=session_note_id)

    session_note.recommendations = recommendations
    if simulation_codes:
        session_note.simulation_codes = simulation_codes
    session_note.updated_date = datetime.datetime.utcnow()
    session_note.save(update_fields=['recommendations',"updated_date","simulation_codes"])

    return {"message": "recommandations updated"}


def get_fitness_analysis_score(coach_data, conversation_data):
    """
    This function is designed to analyze the compatibility between a coach and a coachee based on their conversation data and the coach's information. 

    The function constructs a prompt that includes the coach's data and the conversation data. The prompt is then passed to the `anthropic_completion` function, which is expected to return a fitment score in JSON format. The score is a measure of the compatibility between the coach and the coachee, based on their values, personality, ideas, experiences, and expectations.

    Parameters:
    coach_data (str): A string containing the coach's information.
    conversation_data (str): A string containing the conversation data between the coach and the coachee.

    Returns:
    str: A string in JSON format containing the fitment score. The score is a number between 0 and 10, with 10 indicating the highest compatibility. The JSON string should be in the format: {"Fitment score":"<score>"}

    Example:
    >>> get_fitness_analysis_score("Coach Info", "Conversation Info")
    '{"Fitment score":"7"}'
    """
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


def save_user_action_info(tenant_id,user_id,for_,bot_id=None):
    """
    Save user action information.

    Parameters:
    - tenant_id (str): The tenant_id.
    - user_id (str): The user ID.
    - for_ (str): The field to update in the UserActionInfo model.
    - bot_id (str, optional): The bot ID. Defaults to None.
    if bot_id then text value will be save.

    Returns:
    None

    """
    try:
        action_info, is_created = UserActionInfo.objects.get_or_create(
                        deleted = False,
                        tenant_id = tenant_id,
                        user_id = user_id,
                    )
    except Exception as e:
        logger.exception(f"failed to save user action info: {e}")
        action_info = UserActionInfo.objects.filter(
                        deleted = False,
                        tenant_id = tenant_id,
                        user_id = user_id,
                    ).last()

    if bot_id:
        value = getattr(action_info, for_)
        bot_ids = bot_id
        if value:
            bot_ids = value + f",{bot_id}"
            bot_ids = set(bot_ids.split(","))
            bot_ids = ",".join(bot_ids)
            
        setattr(action_info, for_, bot_ids )
    else:
        setattr(action_info, for_, getattr(action_info, for_) + 1)  # increasing fields by 1

    action_info.save(update_fields=[for_])


def save_bot_engagement(tenant_id,bot_id,user_id,field_name):
    today_date = datetime.datetime.now().date()

    bot_engagement, is_created = BotEngagement.objects.get_or_create(
        tenant_id=tenant_id,
        deleted = False,
        user_id = user_id,
        interacted_on = today_date,
        bot_id = bot_id
    )

    setattr(bot_engagement, field_name, getattr(bot_engagement, field_name) + 1) 
    bot_engagement.save()

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

def process_idp(idp_data,user_id,tenant_id,access_token,only_data=False, idp_id = None):
    """
    Process the Individual Development Plan (IDP) for a user.

    Args:
        idp_data (dict): A dictionary containing the IDP data.
        user_id (str): The ID of the user.
        tenant_id (str): The ID of the tenant.
        access_token (str): The access token for authentication.
        only_data (bool, optional): If True, only return the IDP data. Defaults to False.
        idp_id (str, optional): The ID of the IDP. Defaults to None.

    Returns:
        tuple: A tuple containing the processed IDP data and a boolean indicating success.

    Raises:
        Exception: If any error occurs during the processing.

    Detailed Explanation:
    This function is responsible for processing the Individual Development Plan (IDP) for a user. It takes in the IDP data,
    user ID, tenant ID, access token, and optional parameters. The IDP data is a dictionary containing various fields such as
    strengths, weaknesses, opportunities, threats, key focus areas, goals, priorities, learning histories, key skills, and user name.

    If the `only_data` parameter is True, the function will return the IDP data as a serialized object. If the `idp_id` parameter
    is provided, it will try to fetch the IDP object from the database and return its serialized data. If the IDP is not found,
    it will return an error message.

    If the `only_data` parameter is False, the function will create a new IDP object in the database with the provided data.
    It will then try to fetch recommendations for books, skills, and other resources based on the IDP data. If any error occurs
    during the recommendation fetching process, it will log the error and send an email notification. If the required number
    of scenarios are not generated, it will log the error and send an email notification.

    Finally, it will save the IDP object with the recommendations and scenarios, and send an email notification to the user
    with a link to view the IDP report.

    Example:
    >>> idp_data = {
    ...     'strengths': 'communication, leadership',
    ...     'weakness': 'time management',
    ...     'opportunities': 'networking',
    ...     'threats': 'competition',
    ...     'key_focus_areas': 'project management',
    ...     'goals': 'career advancement',
    ...     'priorities': 'personal growth',
    ...     'learning_histories': 'online courses',
    ...     'key_skills': 'problem solving',
    ...     'user_name': 'John Doe'
    ... }
    >>> user_id = '12345'
    >>> tenant_id = '67890'
    >>> access_token = 'abcdef'
    >>> only_data = False
    >>> idp_id = None
    >>> process_idp(idp_data, user_id, tenant_id, access_token, only_data, idp_id)
    ({'id': 1, 'tenant_id': '67890', 'user_id': '12345', 'strengths': 'communication, leadership', 'weakness': 'time management', 'opportunities': 'networking', 'threats': 'competition', 'key_focus_areas': 'project management', 'goals': 'career advancement', 'priorities': 'personal growth', 'learning_histories': 'online courses', 'key_skills': 'problem solving', 'user_name': 'John Doe', 'book_recommendations': 'book1,book2', 'recommended_hbr': 'hbr1,hbr2', 'recommended_ted_talk': 'tedtalk1,tedtalk2', 'report': 'https://example.com/idpReport?uid=1', 'learning_communities': 'community1,community2', 'course_recommendations': 'course1,course2', 'recommended_scenarios': {'communication': {'dynamic': {'title': 'Communication Dynamic Discussion', 'data': {'information': 'communication'}}}, 'leadership': {'simulation': {'title': 'Leadership Simulation', 'data': {'information': 'leadership'}}}}, 'total_scenarios_created': 2, 'success': True}, True)
    """
    logger.info(f"*********************************************** idp_id: {idp_id}, user_id: {user_id}, tenant_id: {tenant_id}")
    if only_data:
        if idp_id:
            try:
                user_idp = UserIDP.objects.get(deleted=False,tenant_id=tenant_id, uid=idp_id, success=True)
                serializer = UserIDPSerializers(user_idp)
                return serializer.data, True
            except Exception as e:
                logger.error({"Error":e},exc_info=True)
                return {"error": "IDP not found"}, False

        user_idps = UserIDP.objects.filter(deleted=False,tenant_id=tenant_id,user_id=user_id, success=True)
        if user_idps.count() < 1:
            return {"error": "No IDPs found"}, False
        serializer = UserIDPSerializers(user_idps,many=True)
        return serializer.data, True

    else:
        try:
            user = User.objects.get(deleted=False,tenant_id=tenant_id,uid=user_id)
            user_att = UserAttribute.objects.get(deleted=False,tenant_id=tenant_id,user_id=user.uid).attributes
        except Exception as e:
            logger.error({"Error":e},exc_info=True)
            return {"error": "User not found"}, False
        
        strengths = idp_data.get('strengths')
        weakness = idp_data.get('weakness')
        opportunities = idp_data.get('opportunities')
        threats = idp_data.get('threats')
        key_focus_areas = idp_data.get('key_focus_areas')
        goals = idp_data.get('goals')
        priorities = idp_data.get('priorities')
        learning_histories = idp_data.get('learning_histories')
        key_skills = idp_data.get('key_skills')
        user_name = idp_data.get('user_name')

        user_idp = UserIDP.objects.create(
            tenant_id = tenant_id,
            user_id = user_id,
            strengths = strengths,
            weakness=weakness,
            opportunities=opportunities,
            threats=threats,
            key_focus_areas=key_focus_areas,
            goals=goals,
            priorities=priorities,
            learning_histories=learning_histories,
            key_skills=key_skills,
            user_name=user_name,

        )

        for i in range(2):
            logger.info(f" Trying fetching recommendation book, skills etc for {i+1} time")
            try:
                hard_skills = get_hard_skills(key_focus_areas,learning_histories,key_skills,goals,priorities)
                soft_skills = get_soft_skills(key_focus_areas,learning_histories,key_skills,goals,priorities)
                user_idp.skill_gap_for_development = hard_skills
                user_idp.leadership_skill_focus_area = soft_skills
                hard_soft_skills = hard_skills + "," + soft_skills
                book_recomm = get_recommendation("book",hard_soft_skills)
                course_recomm = get_course_recommendation(learning_histories,key_skills,hard_soft_skills)
                hbr_recomm = get_recommendation("hbr",hard_soft_skills)
                tedtalk_recomm = get_recommendation("ted_talk",hard_soft_skills)
                learning_communities = get_recommendation("learning_communities",hard_soft_skills)

                user_idp.book_recommendations = book_recomm
                user_idp.recommended_hbr = hbr_recomm
                user_idp.recommended_ted_talk = tedtalk_recomm
                user_idp.report=f"{FRONTEND_BASE_URL}/idpReport?uid={user_idp.uid}"
                user_idp.learning_communities = learning_communities

                user_idp.course_recommendations = course_recomm

                # recommendations = [book_recomm,hbr_recomm,tedtalk_recomm,course_recomm]
                
                user_idp.save()
                break
            except Exception as e:
                logger.exception(f"Failed to fetch recommendations and soft and hard skills: {e} for {i+1} time")
                if i+1 == 2:
                    subject = "Failed to generate IDP"
                    try:
                        user_attribute = UserAttribute.objects.get(deleted=False,tenant_id=tenant_id,user_id=user_id)
                        user_email = user_attribute.attributes.get("email",None)
                    except Exception as e:
                        logger.error({"Error":e},exc_info=True)
                        user_email = ""
                    html = f"""
                        <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Failed to generate IDP:{user_idp.uid}, user: {user_id}, user_email: {user_email} </p>
                        """

                    send_email_with_html_template(subject=subject,html_content=html)
                    # send_email_with_html_template(subject=subject,html_content=html,to_email='ansariaadil611@gmail.com')
                    return {"error": "in book recommendation, skills etc couldn't generate"}, False
                continue


        tests = {}
        skills = hard_soft_skills.split(',')
        total_scenarios_created = 0

        for i in range(2):
            
            for skill in [[i.strip() for i in hard_skills.split(',')][0],[i.strip() for i in soft_skills.split(',')][0]]:
                temp = {}

                # for i in range(1,6):
                # dynamic_discussion = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': skill}}),type_of_test=TestTypeChoices.dynamic_discussion_thread)
                # logger.info({f"scenario - {skill}": dynamic_discussion})
                # if dynamic_discussion.get("title",None):
                #     total_scenarios_created += 1
                #     temp[f"dynamic"] = dynamic_discussion

                simulation = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': skill}}))
                logger.info({f"scenario - {skill}": simulation})

                if simulation.get("title",None):
                    total_scenarios_created += 1
                    temp[f"simulation"] = simulation
                
                tests[skill] = temp

            
            temp_data = {}
            # focus oriented tests
            # dynamic_discussion = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': ''}}),type_of_test=TestTypeChoices.dynamic_discussion_thread,custom_prompt=get_focus_prompt(key_focus_areas,'dynamic'))
            # if dynamic_discussion.get("title",None):
            #     total_scenarios_created += 1

            #     temp_data[f"dynamic"] = dynamic_discussion

            simulation = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': key_focus_areas}}))
            if simulation.get("title",None):
                total_scenarios_created += 1
                temp_data[f"simulation"] = simulation

            tests["focus_areas"] = temp_data

            logger.info(f"************** after focus areas tests: {tests}")

            temp_data = {}

            # goals oriented tests
            # dynamic_discussion = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': ''}}),type_of_test=TestTypeChoices.dynamic_discussion_thread,custom_prompt=get_goals_prompt(goals,'dynamic'))
            # if dynamic_discussion.get("title",None):
            #     total_scenarios_created += 1
            #     temp_data[f"dynamic"] = dynamic_discussion

            simulation = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': goals}}),)
            if simulation.get("title",None):
                total_scenarios_created += 1
                temp_data[f"simulation"] = simulation

            tests["goals_areas"] = temp_data

            logger.info(f"************** after goals areas tests: {tests}")

            temp_data = {}

            # priority oriented tests
            # dynamic_discussion = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': ''}}),type_of_test=TestTypeChoices.dynamic_discussion_thread,custom_prompt=get_priority_prompt(priorities,'dynamic'))
            # if dynamic_discussion.get("title",None):
            #     total_scenarios_created += 1
            #     temp_data[f"dynamic"] = dynamic_discussion

            simulation = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': priorities}}))
            if simulation.get("title",None):
                total_scenarios_created += 1
                temp_data[f"simulation"] = simulation

            tests["priority_areas"] = temp_data

            logger.info(f"************** after priority areas tests: {tests}")

            # if total_scenarios_created <=6:
            #     if i+1 == 2:
            #         subject = "Failed to generate required Scenarios For IDP"
            #         html = f"""
            #             <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Failed to generate scenarios of IDP:{user_idp.uid}, user: {user_id}</p>
            #             <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Created Scenarios:{tests}</p>

            #             """

            #         send_email_with_html_template(subject=subject,html_content=html)
            #         return {"error": f"Failed to generate enough scenraios : {total_scenarios_created}"}, False
            #     continue

            break



        user_idp.recommended_scenarios = tests
        user_idp.total_scenarios_created = total_scenarios_created
        user_idp.success = True

        user_idp.save()

        # sending email
        subject = "Individual Development Plan (IDP)"
        html = f"""
                    <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: 100%;" width="100%">
                            <tr>
                            <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">
                                <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Your IDP is ready. The detailed report can be viewed here:</p>
                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" class="btn btn-primary" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; box-sizing: border-box; width: 100%;" width="100%">
                        <tbody>
                            <tr>
                            <td align="left" style="font-family: sans-serif; font-size: 14px; vertical-align: top; padding-bottom: 15px;" valign="top">
                                <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: auto;">
                                <tbody>
                                    <tr>
                                    <td style="font-family: sans-serif; font-size: 14px; vertical-align: top; border-radius: 5px; text-align: center; background-color: #3498db;" valign="top" align="center" bgcolor="#3498db"> <a href="{user_idp.report}" target="_blank" style="border: solid 1px #3498db; border-radius: 5px; box-sizing: border-box; cursor: pointer; display: inline-block; font-size: 14px; font-weight: bold; margin: 0; padding: 12px 25px; text-decoration: none; text-transform: capitalize; background-color: #3498db; border-color: #3498db; color: #ffffff;">Get Report</a> </td>
                                    </tr>
                                </tbody>
                                </table>
                            </td>
                            </tr>
                        </tbody>
                        </table>
                            </td>
                            </tr>
                    </table>
                    """
        # user_att = UserAttribute.objects.get(deleted=False,tenant_id=tenant_id,user_id=user.uid).attributes
        emails = [user_att['email'],"coachbots@googlegroups.com"]
        for email in emails:
            send_email_with_html_template(subject=subject,html_content=html,to_email=email,title=f'Hey {user_name}!')


        return UserIDPSerializers(user_idp).data, True
    
def regenerate_idp_or_scenarios(idp_id, access_token, tenant_id):
    """
    This function regenerates Individual Development Plan (IDP) or scenarios for a user based on the user's IDP details.

    Parameters:
    - idp_id (str): The unique identifier of the user's IDP.
    - access_token (str): The access token for authentication.
    - tenant_id (str): The tenant identifier.

    The function performs the following steps:
    1. Retrieves the user's IDP based on the provided idp_id.
    2. Extracts the key focus areas, goals, priorities, soft skills, hard skills, and recommended scenarios from the user's IDP.
    3. Identifies the scenarios that failed to be created in the previous run.
    4. For each failed scenario, it attempts to create a new scenario. If the scenario is related to a skill, it creates a dynamic discussion and a simulation scenario. If the scenario is related to focus areas, goals areas, or priority areas, it creates a custom scenario based on the respective prompt.
    5. Updates the user's IDP with the newly created scenarios.

    Returns:
    - A tuple containing the serialized data of the updated user's IDP and a boolean indicating the success of the operation.

    Example Usage:
    regenerate_idp_or_scenarios("1234", "access_token", "tenant_id")
    """

    user_idp = UserIDP.objects.get(uid=idp_id)
    key_focus_areas = user_idp.key_focus_areas
    goals = user_idp.goals,
    priorities = user_idp.priorities
    soft_skills = user_idp.skill_gap_for_development.split(',')
    hard_skills = user_idp.leadership_skill_focus_area.split(',')
    skills = soft_skills + hard_skills
    tests = user_idp.recommended_scenarios
    scenarios_list = list(["priority_areas","goals_areas","focus_areas"]) + skills
    created_scenario_list = list(tests.keys())

    failed_scenarios = [ scenario for scenario in scenarios_list if scenario not in created_scenario_list]
    

    logger.info(f"******* failed scenarios ***** : {failed_scenarios}")
    for failed_scenario in failed_scenarios:
        temp = {}

        # for i in range(1,6):
        if failed_scenario in skills:
            skill = failed_scenario
            dynamic_discussion = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': skill}}),type_of_test=TestTypeChoices.dynamic_discussion_thread)
            logger.info({f"scenario - {skill}": dynamic_discussion})
            if dynamic_discussion.get("title",None):
                temp[f"dynamic"] = dynamic_discussion
            simulation = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': skill}}))
            logger.info({f"scenario - {skill}": simulation})

            if simulation.get("title",None):
                temp[f"simulation"] = simulation
            
            tests[skill] = temp

        if failed_scenario == "focus_areas":
            temp_data = {}
            # focus oriented tests
            dynamic_discussion = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': ''}}),type_of_test=TestTypeChoices.dynamic_discussion_thread,custom_prompt=get_focus_prompt(key_focus_areas,'dynamic'))
            if dynamic_discussion.get("title",None):

                temp_data[f"dynamic"] = dynamic_discussion

            simulation = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': ''}}),custom_prompt=get_focus_prompt(key_focus_areas,'simulation'))
            if simulation.get("title",None):
                temp_data[f"simulation"] = simulation

            tests["focus_areas"] = temp_data

            logger.info(f"************** after focus areas tests: {tests}")

        if failed_scenario == "goals_areas":

            temp_data = {}

            # goals oriented tests
            dynamic_discussion = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': ''}}),type_of_test=TestTypeChoices.dynamic_discussion_thread,custom_prompt=get_goals_prompt(goals,'dynamic'))
            if dynamic_discussion.get("title",None):
                temp_data[f"dynamic"] = dynamic_discussion

            simulation = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': ''}}),custom_prompt=get_goals_prompt(goals,'simulation'))
            if simulation.get("title",None):
                temp_data[f"simulation"] = simulation

            tests["goals_areas"] = temp_data

            logger.info(f"************** after goals areas tests: {tests}")

        if failed_scenario == "priority_areas":
            temp_data = {}

            # priority oriented tests
            dynamic_discussion = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': ''}}),type_of_test=TestTypeChoices.dynamic_discussion_thread,custom_prompt=get_priority_prompt(priorities,'dynamic'))
            if dynamic_discussion.get("title",None):
                temp_data[f"dynamic"] = dynamic_discussion

            simulation = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': ''}}),custom_prompt=get_priority_prompt(priorities,'simulation'))
            if simulation.get("title",None):
                temp_data[f"simulation"] = simulation

            tests["priority_areas"] = temp_data

            logger.info(f"************** after priority areas tests: {tests}")

    user_idp.recommended_scenarios = tests
    user_idp.save()

    return UserIDPSerializers(user_idp).data, True
  
def contains_skill(input_string):
    # Define the pattern to search for any of the skills
    pattern = r"Skill\d|skill\d"
    # Search for the pattern in the input string
    if re.search(pattern, input_string):
        return True
    return False
    
def get_hard_skills(focus_areas,learning_history,existing_skills,goals,priorities):
    """Generates Hard skill using generic completion method."""
    prompt = """
            \n\nHuman:
            {Key Focus areas}: ${focus_areas}

            {Learning history}: ${learning_history}

            {Existing key skills}: ${existing_skills}

            {Goals}: ${goals}

            {Priorities} : ${priorities}

            This is the persons learning history {Learning history} and their Existing key skills {Existing key skills}. Please give me the upto 2 to 5 technical or hard skills related to their career this person should prioritize to achieve their goals {Goals} based on their immediate focus areas {Key Focus areas}, priorities {Priorities}. These skills should be achievable and actionable to address any identified skill gaps. The skills should be directly related to their career or goals.
            Only give me the name of up to two skills and not more than five skills.
            Output format : {{Skill1, Skill2, Skill3, Skill4, Skill5}}
            DO not give a reason or explanation.
            Do not include any introductory sentence.
            Always remember to not mention Skill1, Skill2, Skill3, Skill4, Skill5 in the responses.
            NOTE: Never mention Skill1, Skill2, Skill3, Skill4, Skill5
            \n\nAssistant:
            """
    
    prompt = Template(prompt).substitute(
        focus_areas=focus_areas,
        learning_history=learning_history,
        existing_skills=existing_skills,
        goals=goals,
        priorities=priorities
    )
    logger.info(f"****Hard skills prommpt : {prompt}")

    data = ""
    for i in range(2):
        # data = anthropic_completion(prompt=prompt,max_tokens=1000).replace("{","").replace("}","")
        data = generic_completion(prompt=prompt).replace("{","").replace("}","")
        print(data)
        if contains_skill(data):
            continue
        break


    return data

def get_soft_skills(focus_areas,learning_history,existing_skills,goals,priorities):
    """Generates Soft skill using generic completion method."""

    prompt = """
             \n\nHuman:
            {Key Focus areas}: ${focus_areas}

            {Learning history}: ${learning_history}

            {Existing key skills}: ${existing_skills}

            {Goals}: ${goals}

            {Priorities} : ${priorities}

            This is the person's learning history {Learning history} and their Existing key skills {Existing key skills }. Please give me up to 2 to 5 soft skills or leadership skills related to their career this person should prioritize to achieve their long term goals {Goals} based on their immediate focus areas {Key Focus areas}, priorities {Priorities}. These skills should be achievable and actionable.
         
            Only give me the name of up to two skills and not more than five skills.
            Output format : {{Skill1, Skill2, Skill3, Skill4, Skill5}}
            DO not give a reason or explanation.
            Do not include any introductory sentence.
            Always remember to not mention Skill1, Skill2, Skill3, Skill4, Skill5 in the responses.
            NOTE: Never mention Skill1, Skill2, Skill3, Skill4, Skill5

            \n\nAssistant:
            """
    
    prompt = Template(prompt).substitute(
        focus_areas=focus_areas,
        learning_history=learning_history,
        existing_skills=existing_skills,
        goals=goals,
        priorities=priorities
    )

    logger.info(f"****Soft skills prommpt : {prompt}")
    # data = generic_completion(prompt=prompt).replace("{","").replace("}","")
    data = ""
    for i in range(2):
        # data = anthropic_completion(prompt=prompt,max_tokens=1000).replace("{","").replace("}","")
        data = generic_completion(prompt=prompt).replace("{","").replace("}","")
        print(data)
        if contains_skill(data):
            continue
        break


    return data

def get_recommendation(prompt_type,hard_soft_skills):
    """
    This function generates a recommendation for resources (books, HBR articles, or TED Talks) to improve certain skills.

    The function first determines the type of resource based on the `prompt_type` parameter. It then constructs a prompt string that requests recommendations for improving the skills specified in `hard_soft_skills`. This prompt is passed to the `generic_completion` function, which generates a text completion based on the prompt.

    Args:
        prompt_type (str): The type of resource for which recommendations are requested. This should be one of the following: 'book', 'hbr', or 'ted_talk'.
        hard_soft_skills (str): A string containing the skills for which improvement resources are requested. The skills should be listed in a comma-separated format.

    Returns:
        str: A string containing the generated recommendations. The recommendations are formatted as a list, with each item in the list corresponding to a skill and the recommended resource for improving that skill.

    Example:
        >>> get_recommendation('book', 'communication, leadership')
        '1. Communication - Book name and description.
         2. Leadership - Book name and description.'
    """
    # function body here    prompt = ""
    if prompt_type == "book":
        prompt = """
        \n\nHuman:
        {skill_gaps}: ${hard_soft_skills}
        Please provide book recommendations to improve these skills {skill_gaps}. Provide the book name, author and a small description of 80 words.
        Output Format:
        1. Skill1 - Book name and description.
        2. Skill2 - Book name and description.
        3. Skill3 - Book name and description.
        4. Skill4 - Book name and description.

        Always give the output in the given format.
        Do not include any introductory sentence or any conclusion.
        Always remeber to not mention Skill1 , Skill2, Skill3, Skill4 in the responses.
        NOTE: Never mention Skill1 , Skill2, Skill3, Skill4

        \n\nAssistant:

        """
    elif prompt_type == "hbr":
        prompt = """
            \n\nHuman:
            {skill_gaps}: ${hard_soft_skills}
            Please provide HBR Article recommendations to improve these skills {skill_gaps}. Provide the title of the video, the author and a small description of 80 words.
            Output Format:
            1. Skill1 - Video Title  and description.
            2. Skill2 - Video Title and description.
            3. Skill3 - Video Title and description.
            4. Skill4 - Video Title and description.

            Always give the output in the given format.
            Do not include any introductory sentence or any conclusion.
            Always remeber to not mention Skill1 , Skill2, Skill3, Skill4 in the responses.
            NOTE: Never mention Skill1 , Skill2, Skill3, Skill4
            \n\nAssistant:
            """
    elif prompt_type == "ted_talk":
        prompt = """
            \n\nHuman:
            {skill_gaps}: ${hard_soft_skills}
            Please provide Ted Talk video recommendations to improve these skills {skill_gaps}. Provide the title of the video, the speaker and a small description of 80 words.
            Output Format:
            1. Skill1 - Video Title  and description.
            2. Skill2 - Video Title and description.
            3. Skill3 - Video Title and description.
            4. Skill4 - Video Title and description.

            Always give the output in the given format.
            Do not include any introductory sentence or any conclusion.
            Always remeber to not mention Skill1 , Skill2, Skill3, Skill4 in the responses.
            NOTE: Never mention Skill1 , Skill2, Skill3, Skill4


            \n\nAssistant:
            """
        
    elif prompt_type == 'learning_communities':
        prompt = """
        {skill_gaps}: ${hard_soft_skills}
        Please provide learning communities to improve these skills {skill_gaps}. Provide the name of the learning community, the hosting site and a small description of 80 words.
        Output Format:
        1. Skill1 - Name, the hosting site and description.
        2. Skill2 - Name, the hosting site and description.
        3. Skill3 - Name, the hosting site and description.
        4. Skill4 - Name, the hosting site and description.

        Always give the output in the given format.
        Do not include any introductory sentence or any conclusion.
        If the skills does not have any online community, please respond with "No learning communities found."
        Always remeber to not mention Skill1 , Skill2, Skill3, Skill4 in the responses.
        NOTE: Never mention Skill1 , Skill2, Skill3, Skill4
        """

    prompt = Template(prompt).substitute(hard_soft_skills=hard_soft_skills)
    logger.info(f"****Recommendation prommpt : {prompt}")

    # data = generic_completion(prompt=prompt)
    data = ""
    for i in range(2):
        # data = anthropic_completion(prompt=prompt,max_tokens=1000)
        data = generic_completion(prompt=prompt)
        print(data)
        if contains_skill(data):
            continue
        break

    logger.info(f"{prompt_type.replace('_',' ').capitalize()} : {data}")


    return data

def get_course_recommendation(learning_history,existing_skills,hard_soft_skills):
    prompt = """
    \n\nHuman:
    {Learning history}: ${learning_history}
    {Existing key skills}: ${existing_skills}
    {skill_gaps}: ${hard_soft_skills}

    This is the person's learning history {Learning history} and their Existing key skills {Existing key skills }. Please provide courses from Coursera to improve these skills {skill_gaps}. Provide the name of the course.
    Output Format :
    1. Skill1 - Course name, source of the course and description.
    2. Skill2 - Course name, source of the course  and description.
    3. Skill3 - Course name, source of the course and description.
    4. Skill4 - Course name, source of the course  and description.

    Always give the output in the given format.
    Do not include any introductory sentence or any conclusion.
    Always remeber to not mention Skill1 , Skill2, Skill3, Skill4 in the responses.
    NOTE: Never mention Skill1 , Skill2, Skill3, Skill4

    \n\nAssistant:

    """

    prompt = Template(prompt).substitute(hard_soft_skills=hard_soft_skills,
                                         existing_skills=existing_skills,
                                         learning_history=learning_history)

    logger.info(f"****Course prommpt : {prompt}")
    # data = generic_completion(prompt=prompt)
    data = ""
    for i in range(2):
        # data = anthropic_completion(prompt=prompt,max_tokens=1000)
        data = generic_completion(prompt=prompt)
        print(data)
        if contains_skill(data):
            continue
        break

    return data



def extract_topics_info(text):
    # Define a regular expression pattern for extracting topics
    pattern = re.compile(r"(\d+)\.\s*(.*?)-\s*(.*)", re.IGNORECASE | re.DOTALL)

    # Find all matches in the text
    matches = pattern.findall(text)

    # Initialize a list to store extracted information for each topic
    topics_info = []

    # Iterate through matches and extract information
    for match in matches:
        topic_number = match[0].strip()
        topic_title = match[1].strip()
        topic_description = match[2].strip()

        # Add the extracted information to the list
        topics_info.append({
            "number": topic_number,
            "title": topic_title,
            "description": topic_description
        })

    return topics_info


def custom_sort_reverse(data:list, first_sort_field:str, second_sort_field:str):
    """
    This function sorts a list of dictionaries in descending order based on two fields. 

    The function uses a modified version of the bubble sort algorithm. It first sorts the data based on the 'first_sort_field'. 
    If two dictionaries have the same 'first_sort_field', it then sorts them based on the 'second_sort_field'. 

    Parameters:
    data (list): A list of dictionaries that needs to be sorted. Each dictionary should contain the keys specified by 'first_sort_field' and 'second_sort_field'.
    first_sort_filed (str): The primary key based on which the data should be sorted.
    second_sort_field (str): The secondary key which is used for sorting when the 'first_sort_field' is the same for two dictionaries.

    Returns:
    list: A sorted list of dictionaries in descending order. The primary sorting is done based on 'first_sort_field' and secondary sorting is done based on 'second_sort_field'.

    Example:
    >>> data = [{'name': 'John', 'age': 30}, {'name': 'Jane', 'age': 30}, {'name': 'Doe', 'age': 25}]
    >>> custom_sort_reverse(data, 'age', 'name')
    [{'name': 'Jane', 'age': 30}, {'name': 'John', 'age': 30}, {'name': 'Doe', 'age': 25}]
    """
    n = len(data)
    
    for i in range(n):
        for j in range(0, n-i-1):
            if data[j][first_sort_field] < data[j+1][first_sort_field] or \
               (data[j][first_sort_field] == data[j+1][first_sort_field] and data[j][second_sort_field] > data[j+1][second_sort_field]):
                # Swap if first_sort_filed is smaller or if first_sort_filed is equal, but user_name is greater
                data[j], data[j+1] = data[j+1], data[j]
                
    return data


def cal_score_for_fitment(user_response,bot_id,tenant_id):
    signature_bot = SignatureBot.objects.get(deleted=False,tenant_id=tenant_id, bot_id=bot_id)
    bot_att = BotAttribute.objects.get(tenant_id=tenant_id, bot_id=signature_bot.uid)
    mentor_answers = []
    fitment_measures = bot_att.fitment_data['fitment_measures']
    count_matching_answers = 0
    for ans in bot_att.fitment_answers['mentor_answer']:
        ans = str(ans).strip().lower()
        if ans == 'true' or ans == 'yes' or ans == 'y':
            ans = 'yes'
        elif ans == 'false' or ans == 'no' or ans == 'n':
            ans = 'no'

        mentor_answers.append(ans)
        

    try:
        user_response = json.loads(user_response)
    except: 
        user_response = user_response


    for index, qna in user_response.items():
        if int(index) == 1:
            if mentor_answers[0] == 'someone junior' and str(qna['cochee']).lower() == 'someone senior':
                count_matching_answers += 1

            elif mentor_answers[0] == 'any level' and str(qna['cochee']).lower() == 'any level':
                count_matching_answers += 1

        else:
            mentee_ans = str(qna['cochee']).lower()
            if mentee_ans == 'true' or mentee_ans == 'yes' or mentee_ans == 'y':
                mentee_ans = 'yes'
            elif mentee_ans == 'false' or mentee_ans == 'no' or mentee_ans == 'n':
                mentee_ans = 'no'
                
            if mentee_ans in mentor_answers:
                count_matching_answers += 1

    msg = ''
    score = {}
    # Classify based on percentage
    if count_matching_answers in [0,1]:
        msg = fitment_measures['bottom']
        score['bottom'] = msg
        score['msg'] = msg
        score['score'] = count_matching_answers
    elif count_matching_answers == 2:
        msg = fitment_measures['mid']
        score['mid'] = msg
        score['msg'] = msg
        score['score'] = count_matching_answers
    elif count_matching_answers == 3:
        msg = fitment_measures['top']
        score['top'] = msg
        score['msg'] = msg
        score['score'] = count_matching_answers

    logger.info(f"=======================================score: {score}")

    return score


def generate_email(name,suffix,domain='coachbots.com'):
    # Convert name to lowercase and remove any leading or trailing whitespace
    name = name.strip().lower()
    
    # Replace spaces with dots
    name = name.replace(' ', '.')
    
    # Generate a unique email address by appending a number
    # until it becomes unique
    email = name + str(suffix) + f'@{domain}'
    
    return email

def get_llm_order(bot_type, tenant_id, feature_type=None):
    """
    Returns LLM order in format:
    {
      "providers": ["gemini", "openai", "anthropic"],
      "models": {
        "gemini": ["gemini-2.5-flash", "gemini-2.0-flash"],
        "openai": ["gpt-4o", "gpt-4o-mini"],
        "anthropic": ["claude-3-sonnet"]
      }
    }
    """
    try:
        default = {
            "providers": ['gemini', 'gpt', 'anthropic'],
            "models": {
                "gemini": ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-2.0-flash-lite-001'],
                "gpt": ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'],
                "anthropic": ['claude-3-5-sonnet-20240620', 'claude-3-opus-20240229', 'claude-3-haiku-20240307']
            }
        }

        provider_alias = {
            "gpt": "gpt",
            "gemini": "gemini",
            "anthropic": "anthropic"
        }

        query = LLMMappingTable.objects.filter(deleted=False, tenant_id=tenant_id)

        if feature_type:
            query = query.filter(feature_type=feature_type)
        else:
            query = query.filter(bot_type=bot_type)


        mapping = query.first()
        if not mapping:
            logger.error('No mapping found')
            return default

        # Get providers from mapping table (order preserved)
        raw_providers = [mapping.llm1, mapping.llm2, mapping.llm3]
        providers = []
        for p in raw_providers:
            if p:
                provider = provider_alias.get(p, p)
                if provider not in providers:
                    providers.append(provider)

        # Get models for each provider from related LLMMappingModels table
        models_map = {}
        related_models = mapping.models.all()  # related_name="models"

        for provider in providers:
            models_map[provider] = []
            # Find rows for this provider
            for m in related_models.filter(llm_type__in=[provider, provider_alias.get(provider, provider)]):
                if m.model_order:
                    # Split comma-separated string and strip spaces
                    ordered_models = [model.strip() for model in m.model_order.split(",") if model.strip()]
                    models_map[provider].extend(ordered_models)

        return {
            "providers": providers,
            "models": models_map
        }

    except Exception as e:
        logger.exception(f"[get_llm_order] {e}")
        return default
