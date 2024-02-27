from users.models import CoachCoacheeConnection, CoachCoacheeMentorMenteeProfile, UserAttribute, User, \
    SignatureBot
from tests.models import TestAttemptSession
from email_sender.helpers import send_email_with_html_template
import datetime


import logging

logger = logging.getLogger(__name__)



def touch_point_for_session_weekly():
    

    logger.info("Excecuting touch_point_for_session_weekly")

    connections = CoachCoacheeConnection.objects.filter(deleted=0) # fetching all connections
    coach_ids = [connection.coach_id for connection in connections]
    coachee_profile_id = [connection.coachee_id for connection in connections]

    profile_ids = set(coach_ids + coachee_profile_id)
    user_ids = list(CoachCoacheeMentorMenteeProfile.objects.filter(uid__in=profile_ids).values_list("user_id",flat=True))
    print(f"Profile Ids and user_id:  ================================================> {profile_ids} {user_ids}")

    user_atts = list(UserAttribute.objects.filter(deleted=0,user_id__in=user_ids).values_list("attributes",flat=True))

    subject = "Touchpoint for coaching mentoring session"
    template = """
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: 100%;" width="100%">
            <tr>
            <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">
                <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Hey!</p>
                <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Dear Participants, Please remember to ger your touch point on the calendar. What else can you do :  If you would like to automatically schedule these meetings per your calendar availibility, please repond to this email and let us know! Thank you</p>

                <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">- Coachbots Team</p>
            </td> </tr>
        </table>
        """
    failed_emails =[]
    for user_att in user_atts:
        email = user_att.get('email',None)
        if email:
            try:
                send_email_with_html_template(subject=subject,html_content=template,to_email=email)
            except Exception as e:
                logger.info(f"Failed to send email to {email} in touch_point_for_session_weekly, Reason: {e}")
                failed_emails.append(email)



    if len(failed_emails) > 0:
        send_email_with_html_template(subject="Failed to send email",html_content=f"Email delivery for scheduled session touch point unsuccessful For these emails: {failed_emails}")

    

def weekly_remider_to_login():
    """
    This function sends a weekly reminder email to all users who are not deleted in the system. 

    The function first fetches all users who are not deleted. It then calculates the total number of actions performed on the platform over the past week for each tenant using the `get_total_actions_on_platform_over_week` function. 

    The function then iterates over each user, fetches their email from the UserAttribute model, and sends them an email with a reminder to login. The email includes the total number of actions performed on the platform over the past week for their tenant. 

    If the email fails to send for any reason, the function logs the error and adds the email to a list of failed emails. If there are any failed emails, the function sends an email to the system administrator with a list of the failed emails.

    This function does not require any input parameters and does not return any output. 

    Example:
    >>> weekly_remider_to_login()
    # Sends weekly reminder emails to all users and logs any failed emails.
    """

    users = User.objects.filter(deleted=0)
    tenant_ids = list(set(users.values_list("tenant_id",flat=True)))
    tenant_action_mapping = {}
    
    for tenant_id in tenant_ids:
        tenant_action_mapping[tenant_id] = get_total_actions_on_platform_over_week(tenant_id=tenant_id)

    failed_emails = []
    logger.info(f"tenant_action_mapping:=======================================================> {tenant_action_mapping}")
    subject = "We want to you back!"
    for user in users:
        user_name = user.name
        user_email = UserAttribute.objects.get(user_id=user.uid).attributes.get("email",None)
        template = f"""
                <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: 100%;" width="100%">
                    <tr>
                    <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">
                        <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Hey!</p>
                        <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Dear {user_name.capitalize()}, This week we faciltated over {tenant_action_mapping[user.tenant_id]} conversations across coach, coachees and simulations. Do remember to check out the action! Thank you </p>

                        <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">- Coachbots Team</p>
                    </td> </tr>
                </table>
                """
        if user_email:
            try:
                send_email_with_html_template(subject=subject,html_content=template,to_email=user_email)
            except Exception as e:
                logger.info(f"Failed to send email to {user_email} in weekly_remider_to_login, Reason: {e}")
                failed_emails.append(user_email)


    if len(failed_emails) > 0:
        send_email_with_html_template(subject="Failed to send email",html_content=f"Email delivery for weekly reminder to login. For these emails: {failed_emails}")




def get_total_actions_on_platform_over_week(tenant_id):
    """
    This function calculates the total number of actions performed on the platform over the past week for a specific tenant.

    The function first determines the date range for the past week (from last Monday to last Sunday). It then fetches all the approved SignatureBots for the given tenant_id that are not deleted. 

    The total number of chat attempts is calculated by counting the number of TestAttemptSessions that were created within the past week and are associated with the fetched SignatureBots. 

    The total number of test attempts is calculated by counting the number of TestAttemptSessions that were created within the past week, are not deleted, and have a non-null 'finished_at' field.

    The function finally returns the sum of total chat attempts and total test attempts.

    Parameters:
    tenant_id (str): The ID of the tenant for which the total actions are to be calculated.

    Returns:
    int: The total number of actions performed on the platform over the past week for the given tenant.

    Example:
    >>> get_total_actions_on_platform_over_week('12345')
    50
    """
    today = datetime.date.today()
    last_monday = today - datetime.timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + datetime.timedelta(days=6)
    last_monday = datetime.datetime.combine(last_monday, datetime.datetime.min.time()).replace(tzinfo=datetime.timezone.utc)

    signature_bots = SignatureBot.objects.filter(deleted=0,tenant_id=tenant_id,is_approved=1)

    total_chat_attempted = 0

    if signature_bots.count() > 0:
        total_chat_attempted = TestAttemptSession.objects.filter(deleted=0,tenant_id=tenant_id,test_id__in=list(signature_bots.values_list("uid",flat=True))).filter(created__gte=last_monday).count()

    total_test_attempted = TestAttemptSession.objects.filter(deleted=False,tenant_id=tenant_id).exclude(finished_at=None).filter(created__gte=last_monday).count()

    logger.info(f"Date: {last_monday} - {today}   ,Total: =======================> total_test_attempted: {total_test_attempted}        total_chat_attempted: {total_chat_attempted}")
    return total_chat_attempted + total_test_attempted



    


        
