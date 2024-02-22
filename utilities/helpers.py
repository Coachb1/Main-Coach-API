import requests
import pytz
import sys
import hmac
import hashlib
import datetime
import os
from dotenv import load_dotenv
from .models import SessionNotesRecommendations, MentorDetails, UserActionInfo, UserIDP
from tests.helpers import create_scenario_from_site_context
import json
import logging
from users.models import UserAttribute
from email_sender.helpers import send_session_notes_email
from commons.anthropic import anthropic_completion
from apis.accounts.serializers import UserIDPSerializers
from string import Template
from commons.utils import generic_completion
from tests.helpers import create_one_question_scenario_from_context, create_scenario_from_site_context
import re
from tests.choices import TestTypeChoices
from settings import FRONTEND_BASE_URL
from users.models import User, CoachCoacheeConnection, CoachCoacheeMentorMenteeProfile
from .prompts import get_focus_prompt, get_goals_prompt, get_priority_prompt
from email_sender.helpers import send_email_with_html_template
from users.db import get_user_by_id, get_user_display_name





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

    commentor = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,tenant_id=tenant_id,user_id=mentor_id).first()
    reciever = CoachCoacheeMentorMenteeProfile.objects.filter(deleted=False,tenant_id=tenant_id,user_id=user_id).first()
    logger.info(f"coach: {commentor.uid}, coachee: {reciever.uid}")
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
        created_date = datetime.datetime.utcnow()
        )
    
    save_user_action_info(tenant_id,user_id,"session_notes_count")
    
    if access_token:
        logger.info(f"commentor: {commentor.profile_type},reciever:{reciever.profile_type}")
        if reciever.profile_type != "coach":

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
    action_info, is_created = UserActionInfo.objects.get_or_create(
                    tenant_id = tenant_id,
                    user_id = user_id,
                )
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
            user = User.objects.get(uid=user_id)
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
                user_idp.book_recommendations = book_recomm
                user_idp.recommended_hbr = hbr_recomm
                user_idp.recommended_ted_talk = tedtalk_recomm
                user_idp.report=f"{FRONTEND_BASE_URL}/idpReport?uid={user_idp.uid}"

                user_idp.course_recommendations = course_recomm

                # recommendations = [book_recomm,hbr_recomm,tedtalk_recomm,course_recomm]
                
                user_idp.save()
                break
            except Exception as e:
                logger.exception(f"Failed to fetch recommendations and soft and hard skills: {e}")
                if i+1 == 2:
                    subject = "Failed to generate IDP"
                    html = f"""
                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: 100%;" width="100%">
                                <tr>
                                <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">
                                    <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Hey!</p>
                                    <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Failed to generate IDP:{user_idp.uid}, user: {user_id}</p>

                                    <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">- Coachbots Team</p>
                                </td>
                                </tr>
                        </table>
                        """

                    send_email_with_html_template(subject=subject,html_content=html)
                    return {"error": "in book recommendation, skills etc couldn't generate"}, False
                continue


        tests = {}
        # create_one_question_scenario_from_context(prompt_type="manager-team",information="Thought Leadership in Digital Marketing",access_token="access_token",tenant_id=tenant_id)
        skills = hard_soft_skills.split(',')
        total_scenarios_created = 0

        for i in range(2):
            
            for skill in skills:
                temp = {}

                # for i in range(1,6):
                dynamic_discussion = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': skill}}),type_of_test=TestTypeChoices.dynamic_discussion_thread)
                logger.info({f"scenario - {skill}": dynamic_discussion})
                if dynamic_discussion.get("title",None):
                    total_scenarios_created += 1
                    temp[f"dynamic"] = dynamic_discussion
                simulation = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': skill}}))
                logger.info({f"scenario - {skill}": simulation})

                if simulation.get("title",None):
                    total_scenarios_created += 1
                    temp[f"simulation"] = simulation
                
                tests[skill] = temp

            temp_data = {}
            # focus oriented tests
            dynamic_discussion = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': ''}}),type_of_test=TestTypeChoices.dynamic_discussion_thread,custom_prompt=get_focus_prompt(key_focus_areas,'dynamic'))
            if dynamic_discussion.get("title",None):
                total_scenarios_created += 1

                temp_data[f"dynamic"] = dynamic_discussion

            simulation = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': ''}}),custom_prompt=get_focus_prompt(key_focus_areas,'simulation'))
            if simulation.get("title",None):
                total_scenarios_created += 1
                temp_data[f"simulation"] = simulation

            tests["focus_areas"] = temp_data

            logger.info(f"************** after focus areas tests: {tests}")

            temp_data = {}

            # goals oriented tests
            dynamic_discussion = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': ''}}),type_of_test=TestTypeChoices.dynamic_discussion_thread,custom_prompt=get_goals_prompt(goals,'dynamic'))
            if dynamic_discussion.get("title",None):
                total_scenarios_created += 1
                temp_data[f"dynamic"] = dynamic_discussion

            simulation = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': ''}}),custom_prompt=get_goals_prompt(goals,'simulation'))
            if simulation.get("title",None):
                total_scenarios_created += 1
                temp_data[f"simulation"] = simulation

            tests["goals_areas"] = temp_data

            logger.info(f"************** after goals areas tests: {tests}")

            temp_data = {}

            # priority oriented tests
            dynamic_discussion = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': ''}}),type_of_test=TestTypeChoices.dynamic_discussion_thread,custom_prompt=get_priority_prompt(priorities,'dynamic'))
            if dynamic_discussion.get("title",None):
                total_scenarios_created += 1
                temp_data[f"dynamic"] = dynamic_discussion

            simulation = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': ''}}),custom_prompt=get_priority_prompt(priorities,'simulation'))
            if simulation.get("title",None):
                total_scenarios_created += 1
                temp_data[f"simulation"] = simulation

            tests["priority_areas"] = temp_data

            logger.info(f"************** after priority areas tests: {tests}")

            if total_scenarios_created <=6:
                if i+1 == 2:
                    subject = "Failed to generate required Scenarios For IDP"
                    html = f"""
                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: 100%;" width="100%">
                                <tr>
                                <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">
                                    <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Hey!</p>
                                    <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Failed to generate scenarios of IDP:{user_idp.uid}, user: {user_id}</p>
                                    <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Created Scenarios:{tests}</p>
                                    

                                    <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">- Coachbots Team</p>
                                </td>
                                </tr>
                        </table>
                        """

                    send_email_with_html_template(subject=subject,html_content=html)
                    return {"error": f"Failed to generate enough scenraios : {total_scenarios_created}"}, False
                continue

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
                                <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Hey! {user_name} </p>
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
                                

                                <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">- Coachbots Team</p>
                            </td>
                            </tr>
                    </table>
                    """
        user_att = UserAttribute.objects.get(deleted=False,tenant_id=tenant_id,user_id=user_id).attributes
        emails = [user_att['email'],"info@coachbots.com"]
        for email in emails:
            send_email_with_html_template(subject=subject,html_content=html,to_email=email)


        return UserIDPSerializers(user_idp).data, True
    
def regenerate_idp_or_scenarios(idp_id,access_token,tenant_id,):

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


def get_hard_skills(focus_areas,learning_history,existing_skills,goals,priorities):
    prompt = """
            \n\nHuman:
            {Key Focus areas}: ${focus_areas}

            {Learning history}: ${learning_history}

            {Existing key skills}: ${existing_skills}

            {Goals}: ${goals}

            {Priorities} : ${priorities}

            This is the persons learning history {Learning history} and their Existing key skills {Existing key skills}. Please give me the top 2 technical or hard skills related to their career this person should prioritize to achieve their goals {Goals} based on their immediate focus areas {Key Focus areas}, priorities {Priorities}. These skills should be achievable and actionable. The skills should be directly related to their career or goals.
            Only give me the name of top two skills.
            Output format : {{Skill1, Skill2}}
            DO not give a reason or explanation.
            \n\nAssistant:
            """
    
    prompt = Template(prompt).substitute(
        focus_areas=focus_areas,
        learning_history=learning_history,
        existing_skills=existing_skills,
        goals=goals,
        priorities=priorities
    )

    data = generic_completion(prompt=prompt).replace("{","").replace("}","")
    print(data)

    return data

def get_soft_skills(focus_areas,learning_history,existing_skills,goals,priorities):
    prompt = """
            \n\nHuman:
            {Key Focus areas}: ${focus_areas}

            {Learning history}: ${learning_history}

            {Existing key skills}: ${existing_skills}

            {Goals}: ${goals}

            {Priorities} : ${priorities}

            This is the person's learning history {Learning history} and their Existing key skills {Existing key skills }. Please give me the top 2 soft skills or leadership skills related to their career this person should prioritize to achieve their long term goals {Goals} based on their immediate focus areas {Key Focus areas}, priorities {Priorities}. These skills should be achievable and actionable.
            Only give me the name of top two skills.
            Output format : {{Skill1, Skill2}}
            DO not give a reason or explanation. 

            \n\nAssistant:
            """
    
    prompt = Template(prompt).substitute(
        focus_areas=focus_areas,
        learning_history=learning_history,
        existing_skills=existing_skills,
        goals=goals,
        priorities=priorities
    )

    data = generic_completion(prompt=prompt).replace("{","").replace("}","")
    print(data)

    return data

def get_recommendation(prompt_type,hard_soft_skills):
    prompt = ""
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


            \n\nAssistant:
            """

    prompt = Template(prompt).substitute(hard_soft_skills=hard_soft_skills)

    data = generic_completion(prompt=prompt)
    print(data)

    return data

def get_course_recommendation(learning_history,existing_skills,hard_soft_skills):
    prompt = """
    \n\nHuman:
    {Learning history}: ${learning_history}
    {Existing key skills}: ${existing_skills}
    {skill_gaps}: ${hard_soft_skills}

    This is the person's learning history {Learning history} and their Existing key skills {Existing key skills }. Please provide courses from Coursera to improve these skills {skill_gaps}. Provide the name of the course.
    Output Format :
    1. Skill1 - Course name
    2. Skill2 - Course name
    3. Skill3 - Course name
    4. Skill4 - Course name

    Always give the output in the given format.
    Do not include any introductory sentence or any conclusion.

    \n\nAssistant:

    """

    prompt = Template(prompt).substitute(hard_soft_skills=hard_soft_skills,
                                         existing_skills=existing_skills,
                                         learning_history=learning_history)

    data = generic_completion(prompt=prompt)
    print(data)

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


def custom_sort_reverse(data:list,first_sort_filed:str,second_sort_field:str):
    n = len(data)
    
    for i in range(n):
        for j in range(0, n-i-1):
            if data[j][first_sort_filed] < data[j+1][first_sort_filed] or \
               (data[j][first_sort_filed] == data[j+1][first_sort_filed] and data[j][second_sort_field] > data[j+1][second_sort_field]):
                # Swap if first_sort_filed is smaller or if first_sort_filed is equal, but user_name is greater
                data[j], data[j+1] = data[j+1], data[j]
                
    return data