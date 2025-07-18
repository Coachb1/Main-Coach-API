import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from settings import BASE_DIR
from users.models import UserAttribute
import logging
from utilities.models import EmailSentDetails
from string import Template
import datetime
from users.db import get_user_by_id
from users.choices import BotTypeChoice

from external_apis.slack_alert_api import send_slack_message

from external_apis.slack_alert_api import send_slack_message
# from commons.notifications import send_error_notification

import logging
import os

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

logger = logging.getLogger(__name__)


def send_email_from_emailit(receiver_email, subject, body, attachment_path=None):
    # Email details
    sender_email = "mail@coachbots.com"  # actual email address (not the display name)
    display_name = "Coach Bot"
    password = "em_smtp_1Pe2EoMFxmatBWlVTTVBHEo3YDwzxxH9"
    # Set up the MIME
    message = MIMEMultipart()
    message["From"] = f"{display_name} <{sender_email}>"
    message["To"] = receiver_email
    message["Subject"] = subject

    # Attach the email body (HTML)
    message.attach(MIMEText(body, "html"))

    # Optional: Add attachment
    if attachment_path and os.path.isfile(attachment_path):
        try:
            with open(attachment_path, "rb") as file:
                part = MIMEApplication(file.read(), Name=os.path.basename(attachment_path))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
                message.attach(part)
        except Exception as e:
            logger.exception(f"Error attaching file: {e}")
            raise e

    # Send email
    try:
        with smtplib.SMTP("smtp.emailit.com", 587) as server:
            server.starttls()
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, message.as_string())
            logger.info("✅ Email sent successfully!")

    except Exception as e:
        logger.exception(f"Email sending failed: {e}")
        raise e


LOGIN_EMAIL = "deb@coachbots.com"
FROM_EMAIL = "mail@coachbots.com"
FROM_EMAIL_DISPLAY = "Coachbot Report <mail@coachbots.com>"
APP_PASSWORD = "daD4QnY3OJBGMVEj"


def send_emailv2(to_email, subject, body, attachment_path=None):
    try:
        from_password = APP_PASSWORD
        from_email = FROM_EMAIL

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = FROM_EMAIL_DISPLAY
        msg['To'] = to_email

        msg.attach(MIMEText(body, 'html'))

        # Attach the file
        if attachment_path and os.path.isfile(attachment_path):
            print(f"📎 Attaching file: {attachment_path}")
            with open(attachment_path, 'rb') as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
                msg.attach(part)

        msg_str = msg.as_string()

        # login to server
        server = smtplib.SMTP('smtp-relay.sendinblue.com', 587)
        server.starttls()
        server.login(LOGIN_EMAIL, from_password)
        server.sendmail(from_email, to_email, msg_str)
        server.quit()
    except Exception as e:
        logger.exception(f"❌ Error sending email: {e}")
        raise


def send_email(to_email, subject, data):
    """
    Sends an email to a specified recipient with a given subject and data.

    This function creates an email with a multipart MIME format with the 'alternative' subtype. 
    It sets the subject, sender, and recipient of the email. The body of the email is created 
    using the 'get_html_body' function, which takes in the candidate's real name, username, 
    test name, and report URL from the 'data' dictionary. The email body is then attached to 
    the email as a MIME text with the 'html' subtype. 

    The function then logs into the SMTP server using the LOGIN_EMAIL and APP_PASSWORD constants, 
    and sends the email from the FROM_EMAIL to the 'to_email' recipient.

    Parameters:
    to_email (str): The email address of the recipient.
    subject (str): The subject of the email.
    data (dict): A dictionary containing the following keys:
        - 'real_name' (str): The real name of the candidate.
        - 'candidate_name' (str): The username of the candidate.
        - 'test_name' (str): The name of the test.
        - 'report_url' (str): The URL of the report.

    Returns:
    None

    Example:
    send_email('test@example.com', 'Test Subject', 
               {'real_name': 'John Doe', 
                'candidate_name': 'jdoe', 
                'test_name': 'Test 1', 
                'report_url': 'http://example.com/report'})
    """
    from_password = APP_PASSWORD
    from_email = FROM_EMAIL

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = FROM_EMAIL_DISPLAY
    msg['To'] = to_email


    candidate_name = f"{data['real_name']}"

    html_body = get_html_body(
        candidate_name, data["user_email"], data["report_url"])

    msg.attach(MIMEText(html_body, 'html'))
    msg_str = msg.as_string()

    # login to server
    server = smtplib.SMTP('smtp-relay.sendinblue.com', 587)
    server.starttls()
    server.login(LOGIN_EMAIL, from_password)
    server.sendmail(from_email, to_email, msg_str)
    server.quit()


def send_generic_email(subject, content, to_email = 'coachbots@googlegroups.com'):
    from_password = APP_PASSWORD
    from_email = FROM_EMAIL

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = FROM_EMAIL_DISPLAY
    msg['To'] = to_email


    

    html_body = get_generic_email_body(content)

    msg.attach(MIMEText(html_body, 'html'))
    msg_str = msg.as_string()

    # login to server
    server = smtplib.SMTP('smtp-relay.sendinblue.com', 587)
    server.starttls()
    server.login(LOGIN_EMAIL, from_password)
    server.sendmail(from_email, to_email, msg_str)
    server.quit()

def send_learner_path_email(tests, user):
    from_password = APP_PASSWORD
    from_email = FROM_EMAIL

    user_attributes = UserAttribute.objects.get(user_id=user.uid).attributes
    to_email = user_attributes.get("profile", {}).get("email")
    user_name = f"{user_attributes.get('real_name')} (username: {user_attributes.get('name')})"
    if not user_attributes.get('real_name'):
        user_name = f"{user_attributes.get('name')} (username: {user_attributes.get('email')})"


    if to_email is None:
        logging.error(f"Email not found for user {user.uid}")
        return

    # List of tuple of (test_name, test_code)
    test_list = [(test.title, test.test_code) for test in tests]

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"Recommended Simulations for {user_name}"
    msg['From'] = FROM_EMAIL_DISPLAY
    msg['To'] = to_email

    html_body = get_html_body_learner_path(user_name,test_list)

    msg.attach(MIMEText(html_body, 'html'))
    msg_str = msg.as_string()

    # login to server
    server = smtplib.SMTP('smtp-relay.sendinblue.com', 587)
    server.starttls()
    server.login(LOGIN_EMAIL, from_password)
    server.sendmail(from_email, to_email, msg_str)
    server.quit()


def send_feedbackd_email(candidate_name, test_code, test_name, session_id, rating, feedback):
    from_password = APP_PASSWORD
    from_email = FROM_EMAIL
    to_email = [FROM_EMAIL,"coachbots@googlegroups.com"]


    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"{candidate_name} submitted a feedback for {test_code}:{test_name}"
    msg['From'] = "Coachbot Feedback <mail@coachbots.com>"
    msg['To'] = FROM_EMAIL



    html_body = get_feedback_email_body(
        candidate_name, test_code, test_name, session_id, rating, feedback)

    msg.attach(MIMEText(html_body, 'html'))
    msg_str = msg.as_string()

    # login to server
    server = smtplib.SMTP('smtp-relay.sendinblue.com', 587)
    server.starttls()
    server.login(LOGIN_EMAIL, from_password)
    for email in to_email:
        server.sendmail(from_email, email, msg_str)
    server.quit()

def send_session_notes_email(to_email,mentor_email,mentor_name,mentee_email,mentee_name,session_note):
    from_password = APP_PASSWORD
    from_email = FROM_EMAIL
    to_email.append("coachbots@googlegroups.com")


    
    # login to server
    server = smtplib.SMTP('smtp-relay.sendinblue.com', 587)
    server.starttls()
    server.login(LOGIN_EMAIL, from_password)
    for email in to_email:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"{mentor_name} submitted session notes for {mentee_name}"
        msg['From'] = "Coachbot Session Notes <mail@coachbots.com>"
        msg['To'] = email



        html_body = get_session_notes_html_body(mentor_name,mentor_email,mentee_name,mentee_email,session_note)

        msg.attach(MIMEText(html_body, 'html'))
        msg_str = msg.as_string()

        server.sendmail(from_email, email, msg_str)
    server.quit()



def send_bot_conversation_email(candidate_name, conversation, to_email,summary, simulation, signature_bot, coach_name, bot_name,allow_reply = False,no_reply=False):
    msg_str = ""
    bot_id = signature_bot.bot_id
    sent_status = ""
    try:
        from_password = APP_PASSWORD
        from_email = FROM_EMAIL


        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Transcript + Summary with bot {coach_name} at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        if no_reply:
            msg['From'] = "Coachbot  <NoReplyTranscript@coachbots.com>"
        else:
            msg['From'] = "Coachbot  <mail@coachbots.com>"

        if allow_reply:
            msg['To'] = ', '.join(to_email)

        # html_body = get_bot_conversation_email_body(candidate_name, conversation, f"summary: {summary}", f"simulation: {simulation}")
        transcript_block = get_transcript_block(conversation=conversation,summary=summary,simulation=simulation,coach_name=coach_name,bot=signature_bot)
        email_wrapper = ""
        if no_reply:
            email_wrapper = get_email_wrapper(html_content=transcript_block,title=f'Hey {candidate_name}!',note='(NOTE : Please be advised that replies to this email will not be monitored or responded to.)')
        else:    
            email_wrapper = get_email_wrapper(html_content=transcript_block,title=f'Hey {candidate_name}!',note='(NOTE : Always "reply all" to make sure the coach(mentor) and coachee(mentee) receive the emails directly.)')

        msg.attach(MIMEText(email_wrapper, 'html'))
        msg_str = msg.as_string()
        print("*"*100, to_email, candidate_name, conversation,"*"*100)

        # login to server
        server = smtplib.SMTP('smtp-relay.sendinblue.com', 587)
        server.starttls()
        server.login(LOGIN_EMAIL, from_password)
        if not allow_reply:
            for email in to_email:
                logger.info(f"sending email to {email}")
                sent_status = server.sendmail(from_email, email, msg_str)
        else:
            sent_status = server.sendmail(from_email, to_email, msg_str)
        server.quit()
        
        print("!!!!!!!!!!!!!!!!!!!!! Email sent successfully ==============> ", sent_status)
        EmailSentDetails.objects.create(subject=msg['Subject'],body=f"conversation: {conversation}\n summary: {summary} \n simulation: {simulation}",
                                        bot_name=bot_id,owner_name=coach_name,sent_by=from_email,
                                        status=sent_status, sent_to=to_email, is_sent=True)
    except Exception as e:
        EmailSentDetails.objects.create(subject=msg['Subject'],body=msg_str,
                                        bot_name=bot_id,owner_name=coach_name,sent_by=from_email,
                                        status=sent_status, sent_to=to_email, is_sent=False)
        """ send_slack_message({"module": "###############3send_bot_conversation_email################", "error": str(e)})
        print("!!!!!!!!!!!!!!!!!!!!! Erro while sending emails ==============> ", e.args) """
        # send_error_notification("send_bot_conversation_email", str(e), {"to_email": to_email, "candidate_name": candidate_name, "conversation": conversation})

def send_feedback_conversation_email(candidate_name, conversation, to_email, type_of_email, is_positive=False, candidate_email=None):
    from_password = APP_PASSWORD
    from_email = FROM_EMAIL


    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"Peer Feedback for your profile"
    msg['From'] = "Coachbot  <mail@coachbots.com>"
    msg['To'] = to_email


    html_body= ''
    if type_of_email == 'like' or type_of_email == 'dislike':
        text = f"You created feedback page for collecting peer feedback. {candidate_name} just left a critical feedback for you!"
        if type_of_email == 'like':
            text = f"You created feedback page for collecting peer feedback. {candidate_name} just left a glowing feedback for you!"
        html_body = get_like_dislike_email_body(text)
    elif type_of_email == 'feedback_conv':
        message = f"You created feedback page for collecting peer feedback. {candidate_name} just left a feedback for you!"
        # if is_positive:
        #     message = f"You created feedback page for collecting peer feedback. {candidate_name} just left a glowing feedback for you!"
        html_body = get_feedback_conv_email_body(message, conversation)

    msg.attach(MIMEText(html_body, 'html'))
    msg_str = msg.as_string()
    print("*"*100, to_email, candidate_name, conversation,"*"*100)

    # login to server
    server = smtplib.SMTP('smtp-relay.sendinblue.com', 587)
    server.starttls()
    server.login(LOGIN_EMAIL, from_password)
    server.sendmail(from_email, to_email, msg_str)
    server.quit()

def send_email_with_html_template(subject, html_content, to_email = 'coachbots@googlegroups.com',title='Hey!'):
    """
    please enter html content like this (can reference from it):
    <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: 100%;" width="100%">
        <tr>
        <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">
            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Hey!</p>
            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Rajan Liked Your Bot </p>
            

            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">- Coachbot Team</p>
        </td>
        </tr>
    </table>
    
    """
    from_password = APP_PASSWORD
    from_email = FROM_EMAIL

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = "Coachbot Notification <mail@coachbots.com>"
    msg['To'] = to_email

    html_body = email_body_templete(html_content=html_content,title=title)

    msg.attach(MIMEText(html_body, 'html'))
    msg_str = msg.as_string()

    # login to server
    server = smtplib.SMTP('smtp-relay.sendinblue.com', 587)
    server.starttls()
    server.login(LOGIN_EMAIL, from_password)
    server.sendmail(from_email, to_email, msg_str)
    server.quit()

def email_body_templete(html_content,title='Hey!'):
    """
    please enter html content like this (can reference from it):
    <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: 100%;" width="100%">
        <tr>
        <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">
            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Hey!</p>
            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Rajan Liked Your Bot </p>
            

            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">- Coachbot Team</p>
        </td>
        </tr>
    </table>
    
    """
    return get_email_wrapper(html_content=html_content, title=title)

def get_generic_email_body(content):
    return f"""
    <!doctype html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
        <title>Simple Transactional Email</title>
        <style>
    @media only screen and (max-width: 620px) {{
    table.body h1 {{
        font-size: 28px !important;
        margin-bottom: 10px !important;
    }}

    table.body p,
    table.body ul,
    table.body ol,
    table.body td,
    table.body span,
    table.body a {{
        font-size: 16px !important;
    }}

    table.body .wrapper,
    table.body .article {{
        padding: 10px !important;
    }}

    table.body .content {{
        padding: 0 !important;
    }}

    table.body .container {{
        padding: 0 !important;
        width: 100% !important;
    }}

    table.body .main {{
        border-left-width: 0 !important;
        border-radius: 0 !important;
        border-right-width: 0 !important;
    }}

    table.body .btn table {{
        width: 100% !important;
    }}

    table.body .btn a {{
        width: 100% !important;
    }}

    table.body .img-responsive {{
        height: auto !important;
        max-width: 100% !important;
        width: auto !important;
    }}
    }}
    @media all {{
    .ExternalClass {{
        width: 100%;
    }}

    .ExternalClass,
    .ExternalClass p,
    .ExternalClass span,
    .ExternalClass font,
    .ExternalClass td,
    .ExternalClass div {{
        line-height: 100%;
    }}

    .apple-link a {{
        color: inherit !important;
        font-family: inherit !important;
        font-size: inherit !important;
        font-weight: inherit !important;
        line-height: inherit !important;
        text-decoration: none !important;
    }}

    #MessageViewBody a {{
        color: inherit;
        text-decoration: none;
        font-size: inherit;
        font-family: inherit;
        font-weight: inherit;
        line-height: inherit;
    }}

    .btn-primary table td:hover {{
        background-color: #34495e !important;
    }}

    .btn-primary a:hover {{
        background-color: #34495e !important;
        border-color: #34495e !important;
    }}
    }}
    </style>
    </head>
    <body style="background-color: #f6f6f6; font-family: sans-serif; -webkit-font-smoothing: antialiased; font-size: 14px; line-height: 1.4; margin: 0; padding: 0; -ms-text-size-adjust: 100%; -webkit-text-size-adjust: 100%;">
        <span class="preheader" style="color: transparent; display: none; height: 0; max-height: 0; max-width: 0; opacity: 0; overflow: hidden; mso-hide: all; visibility: hidden; width: 0;">Interaction Report.</span>
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" class="body" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; background-color: #f6f6f6; width: 100%;" width="100%" bgcolor="#f6f6f6">
        <tr>
            <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">&nbsp;</td>
            <td class="container" style="font-family: sans-serif; font-size: 14px; vertical-align: top; display: block; max-width: 580px; padding: 10px; width: 580px; margin: 0 auto;" width="580" valign="top">
            <div class="content" style="box-sizing: border-box; display: block; margin: 0 auto; max-width: 580px; padding: 10px;">

                <!-- START CENTERED WHITE CONTAINER -->
                <table role="presentation" class="main" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; background: #ffffff; border-radius: 3px; width: 100%;" width="100%">

                <!-- START MAIN CONTENT AREA -->
                <tr>
                    <td class="wrapper" style="font-family: sans-serif; font-size: 14px; vertical-align: top; box-sizing: border-box; padding: 20px;" valign="top">
                    <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: 100%;" width="100%">
                        <tr>
                        <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Hey!</p>
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">{content} </p>
                            
            
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">- Coachbot Team</p>
                        </td>
                        </tr>
                    </table>
                    </td>
                </tr>

                <!-- END MAIN CONTENT AREA -->
                </table>
                <!-- END CENTERED WHITE CONTAINER -->

                <!-- START FOOTER -->
                <div class="footer" style="clear: both; margin-top: 10px; text-align: center; width: 100%;">
                <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: 100%;" width="100%">
                    <tr>
                    <td class="content-block" style="font-family: sans-serif; vertical-align: top; padding-bottom: 10px; padding-top: 10px; color: #999999; font-size: 12px; text-align: center;" valign="top" align="center">
                        <span class="apple-link" style="color: #999999; font-size: 14px; text-align: center;">(c) Coachbot 2023. Powered by Answer Cloud Technology Pvt Ltd </span>
                        <br>This is a transactional email received as a system user or admin. Please contact your admin or reply to this email to stop these.
                    </td>
                    </tr>
                </table>
                </div>
                <!-- END FOOTER -->

            </div>
            </td>
            <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">&nbsp;</td>
        </tr>
        </table>
    </body>
    </html>
    """


def get_like_dislike_email_body(content):
    return get_email_wrapper(html_content=content,title='Hey!')

def get_feedback_conv_email_body(message,conversation):
    data = f'<p>{message}<p><br><br>'
    for i in conversation:
        data += f'''
                <tr>
                    <td style="font-family: sans-serif; font-size: 14px; vertical-align: top; border-radius: 5px; text-align: left; background-color: #3498db;" valign="top" align="left" bgcolor="#3498db">
                        <p style="color: #ffffff; padding: 10px 15px; margin: 0;">{i['question']}</p>
                    </td>
                </tr>
                <tr>
                    <td style="font-family: sans-serif; font-size: 14px; vertical-align: top; border-radius: 5px; text-align: left; background-color: #f2f2f2;" valign="top" align="left" bgcolor="#f2f2f2">
                        <p style="color: #000000; padding: 10px 15px; margin: 0;">{i['answer']}</p>
                    </td>
                </tr>
            '''
    return get_email_wrapper(html_content=data,title=f'Hey!')

def get_bot_conversation_email_body(candidate_name,conversation, summary, simulation):
    data = ""
    for index,i in enumerate(conversation):
        if index+1 == len(conversation):
            data += f'''
                <tr>
                    <td style="font-family: sans-serif; font-size: 14px; vertical-align: top; border-radius: 5px; text-align: left; background-color: #3498db;" valign="top" align="left" bgcolor="#3498db">
                        <p style="color: #ffffff; padding: 10px 15px; margin: 0;">Coach: {i['coach']}</p>
                    </td>
                </tr>
                
            '''
        elif index+1 == 1:
            data += f'''
            
            <tr>
                <td style="font-family: sans-serif; font-size: 14px; vertical-align: top; border-radius: 5px; text-align: left; background-color: #f2f2f2;" valign="top" align="left" bgcolor="#f2f2f2">
                    <p style="color: #000000; padding: 10px 15px; margin: 0;">User: {i['user']}</p>
                </td>
            </tr>
        '''
        else:
            data += f'''
            <tr>
                <td style="font-family: sans-serif; font-size: 14px; vertical-align: top; border-radius: 5px; text-align: left; background-color: #3498db;" valign="top" align="left" bgcolor="#3498db">
                    <p style="color: #ffffff; padding: 10px 15px; margin: 0;">Coach: {i['coach']}</p>
                </td>
            </tr>
            <tr>
                <td style="font-family: sans-serif; font-size: 14px; vertical-align: top; border-radius: 5px; text-align: left; background-color: #f2f2f2;" valign="top" align="left" bgcolor="#f2f2f2">
                    <p style="color: #000000; padding: 10px 15px; margin: 0;">User: {i['user']}</p>
                </td>
            </tr>
        '''
    return f"""
    <!doctype html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
        <title>Simple Transactional Email</title>
        <style>
    @media only screen and (max-width: 620px) {{
    table.body h1 {{
        font-size: 28px !important;
        margin-bottom: 10px !important;
    }}

    table.body p,
    table.body ul,
    table.body ol,
    table.body td,
    table.body span,
    table.body a {{
        font-size: 16px !important;
    }}

    table.body .wrapper,
    table.body .article {{
        padding: 10px !important;
    }}

    table.body .content {{
        padding: 0 !important;
    }}

    table.body .container {{
        padding: 0 !important;
        width: 100% !important;
    }}

    table.body .main {{
        border-left-width: 0 !important;
        border-radius: 0 !important;
        border-right-width: 0 !important;
    }}

    table.body .btn table {{
        width: 100% !important;
    }}

    table.body .btn a {{
        width: 100% !important;
    }}

    table.body .img-responsive {{
        height: auto !important;
        max-width: 100% !important;
        width: auto !important;
    }}
    }}
    @media all {{
    .ExternalClass {{
        width: 100%;
    }}

    .ExternalClass,
    .ExternalClass p,
    .ExternalClass span,
    .ExternalClass font,
    .ExternalClass td,
    .ExternalClass div {{
        line-height: 100%;
    }}

    .apple-link a {{
        color: inherit !important;
        font-family: inherit !important;
        font-size: inherit !important;
        font-weight: inherit !important;
        line-height: inherit !important;
        text-decoration: none !important;
    }}

    #MessageViewBody a {{
        color: inherit;
        text-decoration: none;
        font-size: inherit;
        font-family: inherit;
        font-weight: inherit;
        line-height: inherit;
    }}

    .btn-primary table td:hover {{
        background-color: #34495e !important;
    }}

    .btn-primary a:hover {{
        background-color: #34495e !important;
        border-color: #34495e !important;
    }}
    }}
    </style>
    </head>
    <body style="background-color: #f6f6f6; font-family: sans-serif; -webkit-font-smoothing: antialiased; font-size: 14px; line-height: 1.4; margin: 0; padding: 0; -ms-text-size-adjust: 100%; -webkit-text-size-adjust: 100%;">
        <span class="preheader" style="color: transparent; display: none; height: 0; max-height: 0; max-width: 0; opacity: 0; overflow: hidden; mso-hide: all; visibility: hidden; width: 0;">Interaction Report.</span>
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" class="body" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; background-color: #f6f6f6; width: 100%;" width="100%" bgcolor="#f6f6f6">
        <tr>
            <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">&nbsp;</td>
            <td class="container" style="font-family: sans-serif; font-size: 14px; vertical-align: top; display: block; max-width: 580px; padding: 10px; width: 580px; margin: 0 auto;" width="580" valign="top">
            <div class="content" style="box-sizing: border-box; display: block; margin: 0 auto; max-width: 580px; padding: 10px;">

                <!-- START CENTERED WHITE CONTAINER -->
                <table role="presentation" class="main" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; background: #ffffff; border-radius: 3px; width: 100%;" width="100%">

                <!-- START MAIN CONTENT AREA -->
                <tr>
                    <td class="wrapper" style="font-family: sans-serif; font-size: 14px; vertical-align: top; box-sizing: border-box; padding: 20px;" valign="top">
                    <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: 100%;" width="100%">
                        <tr>
                        <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Hey!</p>
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">{candidate_name} interacted with bot </p>
                            (NOTE : Always reply all to make sure the coach(mentor) and coachee(mentee) receive the emails directly. Also after the email discussion is over, one participant should update the email discussion in the action items section of the platform.) <br/>
                            {summary} <br/>
                            {simulation} <br/>
                            <table role="presentation" border="0" cellpadding="0" cellspacing="0" class=" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; box-sizing: border-box; width: 100%;" width="100%">
                            <tbody>
                                <tr>
                                <td align="left" style="font-family: sans-serif; font-size: 14px; vertical-align: top; padding-bottom: 15px;" valign="top">
                                    <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: auto;">
                                    <tbody>
                                        {data}
                                    </tbody>
                                    </table>
                                </td>
                                </tr>
                            </tbody>
                            </table>
            
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">- Coachbot Team</p>
                        </td>
                        </tr>
                    </table>
                    </td>
                </tr>

                <!-- END MAIN CONTENT AREA -->
                </table>
                <!-- END CENTERED WHITE CONTAINER -->

                <!-- START FOOTER -->
                <div class="footer" style="clear: both; margin-top: 10px; text-align: center; width: 100%;">
                <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: 100%;" width="100%">
                    <tr>
                    <td class="content-block" style="font-family: sans-serif; vertical-align: top; padding-bottom: 10px; padding-top: 10px; color: #999999; font-size: 12px; text-align: center;" valign="top" align="center">
                        <span class="apple-link" style="color: #999999; font-size: 14px; text-align: center;">(c) Coachbot 2023. Powered by Answer Cloud Technology Pvt Ltd </span>
                        <br>This is a transactional email received as a system user or admin. Please contact your admin or reply to this email to stop these.
                    </td>
                    </tr>
                </table>
                </div>
                <!-- END FOOTER -->

            </div>
            </td>
            <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">&nbsp;</td>
        </tr>
        </table>
    </body>
    </html>
    """



def get_feedback_email_body(candidate_name,test_code,test_name, session_id, rating,feedback):
    return f"""
    <!doctype html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
        <title>Simple Transactional Email</title>
        <style>
    @media only screen and (max-width: 620px) {{
    table.body h1 {{
        font-size: 28px !important;
        margin-bottom: 10px !important;
    }}

    table.body p,
    table.body ul,
    table.body ol,
    table.body td,
    table.body span,
    table.body a {{
        font-size: 16px !important;
    }}

    table.body .wrapper,
    table.body .article {{
        padding: 10px !important;
    }}

    table.body .content {{
        padding: 0 !important;
    }}

    table.body .container {{
        padding: 0 !important;
        width: 100% !important;
    }}

    table.body .main {{
        border-left-width: 0 !important;
        border-radius: 0 !important;
        border-right-width: 0 !important;
    }}

    table.body .btn table {{
        width: 100% !important;
    }}

    table.body .btn a {{
        width: 100% !important;
    }}

    table.body .img-responsive {{
        height: auto !important;
        max-width: 100% !important;
        width: auto !important;
    }}
    }}
    @media all {{
    .ExternalClass {{
        width: 100%;
    }}

    .ExternalClass,
    .ExternalClass p,
    .ExternalClass span,
    .ExternalClass font,
    .ExternalClass td,
    .ExternalClass div {{
        line-height: 100%;
    }}

    .apple-link a {{
        color: inherit !important;
        font-family: inherit !important;
        font-size: inherit !important;
        font-weight: inherit !important;
        line-height: inherit !important;
        text-decoration: none !important;
    }}

    #MessageViewBody a {{
        color: inherit;
        text-decoration: none;
        font-size: inherit;
        font-family: inherit;
        font-weight: inherit;
        line-height: inherit;
    }}

    .btn-primary table td:hover {{
        background-color: #34495e !important;
    }}

    .btn-primary a:hover {{
        background-color: #34495e !important;
        border-color: #34495e !important;
    }}
    }}
    </style>
    </head>
    <body style="background-color: #f6f6f6; font-family: sans-serif; -webkit-font-smoothing: antialiased; font-size: 14px; line-height: 1.4; margin: 0; padding: 0; -ms-text-size-adjust: 100%; -webkit-text-size-adjust: 100%;">
        <span class="preheader" style="color: transparent; display: none; height: 0; max-height: 0; max-width: 0; opacity: 0; overflow: hidden; mso-hide: all; visibility: hidden; width: 0;">Interaction Report.</span>
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" class="body" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; background-color: #f6f6f6; width: 100%;" width="100%" bgcolor="#f6f6f6">
        <tr>
            <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">&nbsp;</td>
            <td class="container" style="font-family: sans-serif; font-size: 14px; vertical-align: top; display: block; max-width: 580px; padding: 10px; width: 580px; margin: 0 auto;" width="580" valign="top">
            <div class="content" style="box-sizing: border-box; display: block; margin: 0 auto; max-width: 580px; padding: 10px;">

                <!-- START CENTERED WHITE CONTAINER -->
                <table role="presentation" class="main" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; background: #ffffff; border-radius: 3px; width: 100%;" width="100%">

                <!-- START MAIN CONTENT AREA -->
                <tr>
                    <td class="wrapper" style="font-family: sans-serif; font-size: 14px; vertical-align: top; box-sizing: border-box; padding: 20px;" valign="top">
                    <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: 100%;" width="100%">
                        <tr>
                        <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Hey!</p>
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">The  {candidate_name} submitted a feedback for "{test_code}: {test_name}" Session_id: {session_id} </p>
                            <table role="presentation" border="0" cellpadding="0" cellspacing="0" class=" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; box-sizing: border-box; width: 100%;" width="100%">
                            <tbody>
                                <tr>
                                <td align="left" style="font-family: sans-serif; font-size: 14px; vertical-align: top; padding-bottom: 15px;" valign="top">
                                    <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: auto;">
                                    <tbody>
                                        <tr>
                                        <td style="font-family: sans-serif; font-size: 14px; vertical-align: top; border-radius: 5px; text-align: center; background-color: #3498db;" valign="top" align="center" bgcolor="#3498db"> <a href="#"  style="border: solid 1px #3498db; border-radius: 5px; box-sizing: border-box; cursor: none; pointer-events: none; display: inline-block; font-size: 14px; font-weight: bold; margin: 0; padding: 12px 25px; text-decoration: none; text-transform: capitalize; background-color: #3498db; border-color: #3498db; color: #ffffff;">Rating: {rating}* <br>{feedback}</a> </td>
                                        </tr>
                                    </tbody>
                                    </table>
                                </td>
                                </tr>
                            </tbody>
                            </table>
            
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">- Coachbot Team</p>
                        </td>
                        </tr>
                    </table>
                    </td>
                </tr>

                <!-- END MAIN CONTENT AREA -->
                </table>
                <!-- END CENTERED WHITE CONTAINER -->

                <!-- START FOOTER -->
                <div class="footer" style="clear: both; margin-top: 10px; text-align: center; width: 100%;">
                <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: 100%;" width="100%">
                    <tr>
                    <td class="content-block" style="font-family: sans-serif; vertical-align: top; padding-bottom: 10px; padding-top: 10px; color: #999999; font-size: 12px; text-align: center;" valign="top" align="center">
                        <span class="apple-link" style="color: #999999; font-size: 14px; text-align: center;">(c) Coachbot 2023. Powered by Answer Cloud Technology Pvt Ltd </span>
                        <br>This is a transactional email received as a system user or admin. Please contact your admin or reply to this email to stop these.
                    </td>
                    </tr>
                </table>
                </div>
                <!-- END FOOTER -->

            </div>
            </td>
            <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">&nbsp;</td>
        </tr>
        </table>
    </body>
    </html>
    """

def get_session_notes_html_body(mentor_name,mentor_email,mentee_name,mentee_email,session_note):
    return f"""
    <!doctype html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
        <title>Simple Transactional Email</title>
        <style>
    @media only screen and (max-width: 620px) {{
    table.body h1 {{
        font-size: 28px !important;
        margin-bottom: 10px !important;
    }}

    table.body p,
    table.body ul,
    table.body ol,
    table.body td,
    table.body span,
    table.body a {{
        font-size: 16px !important;
    }}

    table.body .wrapper,
    table.body .article {{
        padding: 10px !important;
    }}

    table.body .content {{
        padding: 0 !important;
    }}

    table.body .container {{
        padding: 0 !important;
        width: 100% !important;
    }}

    table.body .main {{
        border-left-width: 0 !important;
        border-radius: 0 !important;
        border-right-width: 0 !important;
    }}

    table.body .btn table {{
        width: 100% !important;
    }}

    table.body .btn a {{
        width: 100% !important;
    }}

    table.body .img-responsive {{
        height: auto !important;
        max-width: 100% !important;
        width: auto !important;
    }}
    }}
    @media all {{
    .ExternalClass {{
        width: 100%;
    }}

    .ExternalClass,
    .ExternalClass p,
    .ExternalClass span,
    .ExternalClass font,
    .ExternalClass td,
    .ExternalClass div {{
        line-height: 100%;
    }}

    .apple-link a {{
        color: inherit !important;
        font-family: inherit !important;
        font-size: inherit !important;
        font-weight: inherit !important;
        line-height: inherit !important;
        text-decoration: none !important;
    }}

    #MessageViewBody a {{
        color: inherit;
        text-decoration: none;
        font-size: inherit;
        font-family: inherit;
        font-weight: inherit;
        line-height: inherit;
    }}

    .btn-primary table td:hover {{
        background-color: #34495e !important;
    }}

    .btn-primary a:hover {{
        background-color: #34495e !important;
        border-color: #34495e !important;
    }}
    }}
    </style>
    </head>
    <body style="background-color: #f6f6f6; font-family: sans-serif; -webkit-font-smoothing: antialiased; font-size: 14px; line-height: 1.4; margin: 0; padding: 0; -ms-text-size-adjust: 100%; -webkit-text-size-adjust: 100%;">
        <span class="preheader" style="color: transparent; display: none; height: 0; max-height: 0; max-width: 0; opacity: 0; overflow: hidden; mso-hide: all; visibility: hidden; width: 0;">Interaction Report.</span>
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" class="body" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; background-color: #f6f6f6; width: 100%;" width="100%" bgcolor="#f6f6f6">
        <tr>
            <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">&nbsp;</td>
            <td class="container" style="font-family: sans-serif; font-size: 14px; vertical-align: top; display: block; max-width: 580px; padding: 10px; width: 580px; margin: 0 auto;" width="580" valign="top">
            <div class="content" style="box-sizing: border-box; display: block; margin: 0 auto; max-width: 580px; padding: 10px;">

                <!-- START CENTERED WHITE CONTAINER -->
                <table role="presentation" class="main" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; background: #ffffff; border-radius: 3px; width: 100%;" width="100%">

                <!-- START MAIN CONTENT AREA -->
                <tr>
                    <td class="wrapper" style="font-family: sans-serif; font-size: 14px; vertical-align: top; box-sizing: border-box; padding: 20px;" valign="top">
                    <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: 100%;" width="100%">
                        <tr>
                        <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Hey!</p>
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;"><b>{mentor_name}({mentor_email})</b> submitted a session note for <b>{mentee_name} ({mentee_email})</b> </p>
                            <div
                                style="font-family: Arial, sans-serif; font-size: 14px; margin-bottom: 15px;">
                                <div style="text-align: left;">
                                    <div
                                        style="display: inline-block; padding: 12px 25px; border-radius: 5px; font-weight: bold; text-transform: capitalize;">
                                        Session Note: 
                                    </div>
                                    <div
                                    style="display: inline-block; padding: 12px 25px; border-radius: 5px; text-transform: capitalize;">
                                    {session_note}</div>
                                </div>
                            </div>
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">- Coachbot Team</p>
                        </td>
                        </tr>
                    </table>
                    </td>
                </tr>

                <!-- END MAIN CONTENT AREA -->
                </table>
                <!-- END CENTERED WHITE CONTAINER -->

                <!-- START FOOTER -->
                <div class="footer" style="clear: both; margin-top: 10px; text-align: center; width: 100%;">
                <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: 100%;" width="100%">
                    <tr>
                    <td class="content-block" style="font-family: sans-serif; vertical-align: top; padding-bottom: 10px; padding-top: 10px; color: #999999; font-size: 12px; text-align: center;" valign="top" align="center">
                        <span class="apple-link" style="color: #999999; font-size: 14px; text-align: center;">(c) Coachbot 2023. Powered by Answer Cloud Technology Pvt Ltd </span>
                        <br>This is a transactional email received as a system user or admin. Please contact your admin or reply to this email to stop these.
                    </td>
                    </tr>
                </table>
                </div>
                <!-- END FOOTER -->

            </div>
            </td>
            <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">&nbsp;</td>
        </tr>
        </table>
    </body>
    </html>
    """



def get_html_body(candidate_name, user_email, report_url):
    msg = f"""
    <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Your personalized Feedback Report is now available! This comprehensive report provides valuable insights into your leadership strengths, weaknesses, and areas for growth. You have 60 days to access your report.</p>
    <table role="presentation" border="0" cellpadding="0" cellspacing="0" class="btn btn-primary" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; box-sizing: border-box; width: 100%;" width="100%">
    <tbody>
        <tr>
        <td align="left" style="font-family: sans-serif; font-size: 14px; vertical-align: top; padding-bottom: 15px;" valign="top">
            <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: auto;">
            <tbody>
                <tr>
                <td style="font-family: sans-serif; font-size: 14px; vertical-align: top; border-radius: 5px; text-align: center; background-color: #3498db;" valign="top" align="center" bgcolor="#3498db"> <a href="{report_url}" target="_blank" style="border: solid 1px #3498db; border-radius: 5px; box-sizing: border-box; cursor: pointer; display: inline-block; font-size: 14px; font-weight: bold; margin: 0; padding: 12px 25px; text-decoration: none; text-transform: capitalize; background-color: #3498db; border-color: #3498db; color: #ffffff;">Get Report</a> </td>
                </tr>
            </tbody>
            </table>
        </td>
        </tr>
    </tbody>
    </table>
    <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">We encourage you to review your report at your convenience. If you have any questions or would like to schedule a time to discuss your results in more detail, please don't hesitate to reply to this email. You can also request to schedule a meeting for a readout.</p
    """
    footer = f"""
    <p>Sincerely,</p><p>Team Coach-Bot</p><p>User Identifier Tag: {user_email}</p>
    """
    return get_email_wrapper(html_content=msg,title=f"Hey {candidate_name}!", footer=footer)

def get_html_body_learner_path(user_name,test_list):

    test_list_str = ""

    for test_name, test_code in test_list:
        test_list_str += f"<li>{test_name} : {test_code}</li><br />"

    return f"""
    <!doctype html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
        <title>Simple Transactional Email</title>
        <style>
    @media only screen and (max-width: 620px) {{
    table.body h1 {{
        font-size: 28px !important;
        margin-bottom: 10px !important;
    }}

    table.body p,
    table.body ul,
    table.body ol,
    table.body td,
    table.body span,
    table.body a {{
        font-size: 16px !important;
    }}

    table.body .wrapper,
    table.body .article {{
        padding: 10px !important;
    }}

    table.body .content {{
        padding: 0 !important;
    }}

    table.body .container {{
        padding: 0 !important;
        width: 100% !important;
    }}

    table.body .main {{
        border-left-width: 0 !important;
        border-radius: 0 !important;
        border-right-width: 0 !important;
    }}

    table.body .btn table {{
        width: 100% !important;
    }}

    table.body .btn a {{
        width: 100% !important;
    }}

    table.body .img-responsive {{
        height: auto !important;
        max-width: 100% !important;
        width: auto !important;
    }}
    }}
    @media all {{
    .ExternalClass {{
        width: 100%;
    }}

    .ExternalClass,
    .ExternalClass p,
    .ExternalClass span,
    .ExternalClass font,
    .ExternalClass td,
    .ExternalClass div {{
        line-height: 100%;
    }}

    .apple-link a {{
        color: inherit !important;
        font-family: inherit !important;
        font-size: inherit !important;
        font-weight: inherit !important;
        line-height: inherit !important;
        text-decoration: none !important;
    }}

    #MessageViewBody a {{
        color: inherit;
        text-decoration: none;
        font-size: inherit;
        font-family: inherit;
        font-weight: inherit;
        line-height: inherit;
    }}

    .btn-primary table td:hover {{
        background-color: #34495e !important;
    }}

    .btn-primary a:hover {{
        background-color: #34495e !important;
        border-color: #34495e !important;
    }}
    }}
    </style>
    </head>
    <body style="background-color: #f6f6f6; font-family: sans-serif; -webkit-font-smoothing: antialiased; font-size: 14px; line-height: 1.4; margin: 0; padding: 0; -ms-text-size-adjust: 100%; -webkit-text-size-adjust: 100%;">
        <span class="preheader" style="color: transparent; display: none; height: 0; max-height: 0; max-width: 0; opacity: 0; overflow: hidden; mso-hide: all; visibility: hidden; width: 0;">Learner Path.</span>
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" class="body" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; background-color: #f6f6f6; width: 100%;" width="100%" bgcolor="#f6f6f6">
        <tr>
            <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">&nbsp;</td>
            <td class="container" style="font-family: sans-serif; font-size: 14px; vertical-align: top; display: block; max-width: 580px; padding: 10px; width: 580px; margin: 0 auto;" width="580" valign="top">
            <div class="content" style="box-sizing: border-box; display: block; margin: 0 auto; max-width: 580px; padding: 10px;">

                <!-- START CENTERED WHITE CONTAINER -->
                <table role="presentation" class="main" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; background: #ffffff; border-radius: 3px; width: 100%;" width="100%">

                <!-- START MAIN CONTENT AREA -->
                <tr>
                    <td class="wrapper" style="font-family: sans-serif; font-size: 14px; vertical-align: top; box-sizing: border-box; padding: 20px;" valign="top">
                    <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: 100%;" width="100%">
                        <tr>
                        <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Hey!</p>
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">The Recommended Simulations for {user_name} is ready!</p>
                            <ul>
                                {test_list_str}
                            </ul>
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">Thank you! </p>
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">- Coachbot Team</p>
                        </td>
                        </tr>
                    </table>
                    </td>
                </tr>

                <!-- END MAIN CONTENT AREA -->
                </table>
                <!-- END CENTERED WHITE CONTAINER -->

                <!-- START FOOTER -->
                <div class="footer" style="clear: both; margin-top: 10px; text-align: center; width: 100%;">
                <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-collapse: separate; mso-table-lspace: 0pt; mso-table-rspace: 0pt; width: 100%;" width="100%">
                    <tr>
                    <td class="content-block" style="font-family: sans-serif; vertical-align: top; padding-bottom: 10px; padding-top: 10px; color: #999999; font-size: 12px; text-align: center;" valign="top" align="center">
                        <span class="apple-link" style="color: #999999; font-size: 14px; text-align: center;">(c) Coachbot 2023. Powered by Answer Cloud Technology Pvt Ltd </span>
                        <br>This is a transactional email received as a system user or admin. Please contact your admin or reply to this email to stop these.
                    </td>
                    </tr>
                </table>
                </div>
                <!-- END FOOTER -->

            </div>
            </td>
            <td style="font-family: sans-serif; font-size: 14px; vertical-align: top;" valign="top">&nbsp;</td>
        </tr>
        </table>
    </body>
    </html>
    """



def get_email_wrapper(html_content,title='Hey!',note="", footer="<p>Best regards,</p><p>The Team Coachbot</p>"):
            #                                                                        <img class="adapt-img" src="https://demo.stripocdn.email/content/guids/804167b6-b3bc-4fc5-a3ae-8f7638774109/images/coachbotslogo.png" alt style="display: block;" width="305">
    
    template = """
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html dir="ltr" xmlns="http://www.w3.org/1999/xhtml" xmlns:o="urn:schemas-microsoft-com:office:office">

<head>
    <meta charset="UTF-8">
    <meta content="width=device-width, initial-scale=1" name="viewport">
    <meta name="x-apple-disable-message-reformatting">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta content="telephone=no" name="format-detection">
    <title></title>
    <!--[if (mso 16)]>
    <style type="text/css">
    a {text-decoration: none;}
    </style>
    <![endif]-->
    <!--[if gte mso 9]><style>sup { font-size: 100% !important; }</style><![endif]-->
    <!--[if gte mso 9]>
<xml>
    <o:OfficeDocumentSettings>
    <o:AllowPNG></o:AllowPNG>
    <o:PixelsPerInch>96</o:PixelsPerInch>
    </o:OfficeDocumentSettings>
</xml>
<![endif]-->
    <!--[if !mso]><!-- -->
    <link href="https://fonts.googleapis.com/css2?family=Fredoka+One&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Poppins&display=swap" rel="stylesheet">
    <!--<![endif]-->
</head>

<body>
    <div dir="ltr" class="es-wrapper-color">
        <!--[if gte mso 9]>
			<v:background xmlns:v="urn:schemas-microsoft-com:vml" fill="t">
				<v:fill type="tile" color="#ebfafe"></v:fill>
			</v:background>
		<![endif]-->
        <table class="es-wrapper" width="100%" cellspacing="0" cellpadding="0">
            <tbody>
                <tr>
                    <td class="esd-email-paddings" valign="top">
                        <table cellpadding="0" cellspacing="0" class="esd-header-popover es-header" align="center">
                            <tbody>
                                <tr>
                                    <td class="esd-stripe" align="center">
                                        <table bgcolor="#ffffff" class="es-header-body" align="center" cellpadding="0" cellspacing="0" width="600">
                                            <tbody>
                                                <tr>
                                                    <td class="esd-structure es-p20t es-p20r es-p20l" align="left">
                                                        <table cellpadding="0" cellspacing="0" width="100%">
                                                            <tbody>
                                                                <tr>
                                                                    <td width="560" class="esd-container-frame" align="center" valign="top">
                                                                        <table cellpadding="0" cellspacing="0" width="100%">
                                                                            <tbody>
                                                                                <tr>
                                                                                    <td align="center" class="esd-block-text">
                                                                                        <p style="font-size: 10px;">${note}</p>
                                                                                    </td>
                                                                                </tr>
                                                                            </tbody>
                                                                        </table>
                                                                    </td>
                                                                </tr>
                                                            </tbody>
                                                        </table>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td class="es-p20t es-p20r es-p20l esd-structure" align="left">
                                                        <table cellpadding="0" cellspacing="0" width="100%">
                                                            <tbody>
                                                                <tr>
                                                                    <td width="560" class="esd-container-frame" align="center" valign="top">
                                                                        <table cellpadding="0" cellspacing="0" width="100%">
                                                                            <tbody>
                                                                                <tr>
                                                                                    <td align="center" class="esd-block-image" style="font-size: 0px;"><a target="_blank">
                                                                                    <div class="adapt-img" style="display: flex; flex-direction: row; align-items: center; justify-content: center; margin-bottom: 16px;">
                                                                                        <h1
                                                                                            id="heading"
                                                                                            style="width: fit-content; border: 2px solid #2DC092; padding: 4px !important; font-size: 20px; font-weight: 800; color: #2DC092; position: relative; z-index: 10;"
                                                                                        >
                                                                                            <span
                                                                                            style="margin-right: 4px; background-color: #2DC092; padding: 3px; font-size: 18px; font-weight: 700; color: white;"
                                                                                            >
                                                                                            COACH
                                                                                            </span>
                                                                                            BOT
                                                                                        </h1>
                                                                                    </div>
                                                                                    </a></td>
                                                                                </tr>
                                                                            </tbody>
                                                                        </table>
                                                                    </td>
                                                                </tr>
                                                            </tbody>
                                                        </table>
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td class="esd-structure es-p20t es-p20r es-p20l" align="left">
                                                        <table cellpadding="0" cellspacing="0" width="100%">
                                                            <tbody>
                                                                <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px; text-align: left;">${title}</p>

                                                                <tr>
                                                                    <td width="560" class="esd-container-frame" align="center" valign="top">
                                                                        <table cellpadding="0" cellspacing="0" width="100%">
                                                                            <tbody>
                                                                                <tr>
                                                                                    <td class="esd-block-text">
                                                                                        <div>${html_content}</div>
                                                                                    </td>
                                                                                </tr>
                                                                            </tbody>
                                                                        </table>
                                                                    </td>
                                                                </tr>
                                                            </tbody>
                                                        </table>
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                        <table cellpadding="0" cellspacing="0" class="es-content" align="center">
                            <tbody>
                                <tr>
                                    <td class="esd-stripe" align="center">
                                        <table bgcolor="#ffffff" class="es-content-body" align="center" cellpadding="0" cellspacing="0" width="600">
                                            <tbody>
                                                <tr>
                                                    <td class="esd-structure es-p20r es-p20l" align="left">
                                                        <table cellpadding="0" cellspacing="0" width="100%">
                                                            <tbody>
                                                                <tr>
                                                                    <td width="560" class="esd-container-frame" align="center" valign="top">
                                                                        <table cellpadding="0" cellspacing="0" width="100%">
                                                                            <tbody>
                                                                                <tr>
                                                                                    <td align="center" class="esd-block-spacer es-p20t es-p20b" style="font-size:0">
                                                                                        <table border="0" width="100%" height="100%" cellpadding="0" cellspacing="0">
                                                                                            <tbody>
                                                                                                <tr>
                                                                                                    <td style="border-bottom: 2px solid #e9f7e4; background: unset; height: 1px; width: 100%; margin: 0px;"></td>
                                                                                                </tr>
                                                                                            </tbody>
                                                                                        </table>
                                                                                    </td>
                                                                                </tr>
                                                                            </tbody>
                                                                        </table>
                                                                    </td>
                                                                </tr>
                                                            </tbody>
                                                        </table>
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                        <table cellpadding="0" cellspacing="0" class="es-footer esd-footer-popover" align="center">
                            <tbody>
                                <tr>
                                    <td class="esd-stripe" align="center" esd-custom-block-id="876054">
                                        <table bgcolor="#ffffff" class="es-footer-body" align="center" cellpadding="0" cellspacing="0" width="600">
                                            <tbody>
                                                <tr>
                                                    <td class="esd-structure es-p30b es-p20r es-p20l" align="left">
                                                        <table cellpadding="0" cellspacing="0" width="100%">
                                                            <tbody>
                                                                <tr>
                                                                    <td width="560" class="esd-container-frame" align="left">
                                                                        <table cellpadding="0" cellspacing="0" width="100%">
                                                                            <tbody>
                                                                                <tr>
                                                                                    <td align="left" class="esd-block-text">
                                                                                        ${footer}
                                                                                    </td>
                                                                                </tr>
                                                                                <tr>
                                                                                    <td align="center" class="esd-block-spacer es-p20t es-p20b" style="font-size:0">
                                                                                        <table border="0" width="100%" height="100%" cellpadding="0" cellspacing="0">
                                                                                            <tbody>
                                                                                                <tr>
                                                                                                    <td style="border-bottom: 2px solid #e9f7e4; background: unset; height: 1px; width: 100%; margin: 0px;"></td>
                                                                                                </tr>
                                                                                            </tbody>
                                                                                        </table>
                                                                                    </td>
                                                                                </tr>
                                                                                <tr>
                                                                                    <td align="center" class="esd-block-text">
                                                                                        <p style="line-height: 150%; font-size: 12px;">(c) Coachbot Inc. 2024. Powered by Answer Cloud Technologies Pvt Ltd.</p>
                                                                                    </td>
                                                                                </tr>
                                                                                <tr>
                                                                                    <td align="center" class="esd-block-spacer es-p10" style="font-size:0">
                                                                                        <table border="0" width="100%" height="100%" cellpadding="0" cellspacing="0">
                                                                                            <tbody>
                                                                                                <tr>
                                                                                                    <td style="border-bottom: 1px solid #cccccc; background: unset; height: 1px; width: 100%; margin: 0px;"></td>
                                                                                                </tr>
                                                                                            </tbody>
                                                                                        </table>
                                                                                    </td>
                                                                                </tr>
                                                                                <tr>
                                                                                    <td align="center" class="esd-block-text es-p30r es-p30l">
                                                                                        <p style="line-height: 150%; font-size: 12px;">This is a transactional email received as a system user or admin. This email is not monitored, please contact your admin to discuss these emails.</p>
                                                                                    </td>
                                                                                </tr>
                                                                            </tbody>
                                                                        </table>
                                                                    </td>
                                                                </tr>
                                                            </tbody>
                                                        </table>
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </td>
                </tr>
            </tbody>
        </table>
    </div>
</body>

</html>
    
    """

    template = Template(template).substitute(html_content=html_content,title=title,note=note, footer=footer)

    return template

def get_transcript_block(conversation, summary, simulation,coach_name,bot):
    if simulation:
        simulation_block = get_simulation_block(simulation)
    else:
        simulation_block = '''<tr>
            <td align="left" class="esd-block-text">
                <p>No Simulation Found!</p>
            </td>
        </tr>'''
    data = ""
    for index,i in enumerate(conversation):
        if bot.bot_type == "deep_dive":
            if index == 0:
                data += f'''
                        
                        <tr>
                            <td style="font-family: sans-serif; font-size: 14px; vertical-align: top; border-radius: 5px; text-align: left; background-color: #3498db;" valign="top" align="left" bgcolor="#3498db">
                                <p style="color: #ffffff; padding: 10px 15px; margin: 0;">Question: {i['coach']}</p>
                            </td>
                        </tr>
                        <tr>
                            <td style="font-family: sans-serif; font-size: 14px; vertical-align: top; border-radius: 5px; text-align: left; background-color: #f2f2f2;" valign="top" align="left" bgcolor="#f2f2f2">
                                <p style="color: #000000; padding: 10px 15px; margin: 0;">Answer: {i['user']}</p>
                            </td>
                        </tr>
                    '''
                
            elif index == 1:
                data += f'''
                    <tr>
                        <td style="font-family: sans-serif; font-size: 14px; vertical-align: top; border-radius: 5px; text-align: left; background-color: #3498db;" valign="top" align="left" bgcolor="#3498db">
                            <p style="color: #ffffff; padding: 10px 15px; margin: 0;">Question: {i['coach']}</p>
                        </td>
                    </tr>
                '''

            elif index == len(conversation)-2:
                    data += f'''
                        <tr>
                            <td style="font-family: sans-serif; font-size: 14px; vertical-align: top; border-radius: 5px; text-align: left; background-color: #f2f2f2;" valign="top" align="left" bgcolor="#f2f2f2">
                                <p style="color: #000000; padding: 10px 15px; margin: 0;">Answer: {i['user']}</p>
                            </td>
                        </tr>
                    '''
            elif index == len(conversation)-1:
                    data += f'''
                        <tr>
                        <td style="font-family: sans-serif; font-size: 14px; vertical-align: top; border-radius: 5px; text-align: left; background-color: #3498db;" valign="top" align="left" bgcolor="#3498db">
                            <p style="color: #ffffff; padding: 10px 15px; margin: 0;">{i['coach']}</p>
                        </td>
                    </tr>
                    '''
            else:

                data += f'''
                        <tr>
                            <td style="font-family: sans-serif; font-size: 14px; vertical-align: top; border-radius: 5px; text-align: left; background-color: #f2f2f2;" valign="top" align="left" bgcolor="#f2f2f2">
                                <p style="color: #000000; padding: 10px 15px; margin: 0;">Answer: {i['user']}</p>
                            </td>
                        </tr>
                        <tr>
                            <td style="font-family: sans-serif; font-size: 14px; vertical-align: top; border-radius: 5px; text-align: left; background-color: #3498db;" valign="top" align="left" bgcolor="#3498db">
                                <p style="color: #ffffff; padding: 10px 15px; margin: 0;">Question: {i['coach']}</p>
                            </td>
                        </tr>
                    '''
        else:
            data += f'''
            <tr>
                <td style="font-family: sans-serif; font-size: 14px; vertical-align: top; border-radius: 5px; text-align: left; background-color: #f2f2f2;" valign="top" align="left" bgcolor="#f2f2f2">
                    <p style="color: #000000; padding: 10px 15px; margin: 0;">User: {i['user']}</p>
                </td>
            </tr>
            <tr>
                <td style="font-family: sans-serif; font-size: 14px; vertical-align: top; border-radius: 5px; text-align: left; background-color: #3498db;" valign="top" align="left" bgcolor="#3498db">
                    <p style="color: #ffffff; padding: 10px 15px; margin: 0;">{coach_name}: {i['coach']}</p>
                </td>
            </tr>
        '''
    template = """
    <td class="esd-stripe" align="center">
        <table bgcolor="#ffffff" class="es-content-body" align="center" cellpadding="0" cellspacing="0" width="600">
            <tbody>
                <tr>
                    <td class="esd-structure es-p20r es-p20l" align="left">
                        <table cellpadding="0" cellspacing="0" width="100%">
                            <tbody>
                                <tr>
                                    <td width="560" class="esd-container-frame" align="center" valign="top">
                                        <table cellpadding="0" cellspacing="0" width="100%">
                                            <tbody>
                                                <tr>
                                                    <td align="center" class="esd-block-spacer es-p20t es-p20b" style="font-size:0">
                                                        <table border="0" width="100%" height="100%" cellpadding="0" cellspacing="0">
                                                            <tbody>
                                                                <tr>
                                                                    <td style="border-bottom: 2px solid rgba(0, 0, 0, 0.74); background: unset; height: 1px; width: 100%; margin: 0px;"></td>
                                                                </tr>
                                                            </tbody>
                                                        </table>
                                                    </td>
                                                </tr>
                                                <td align="center" class="esd-block-text">
                                                    <br>
                                                    <div style="font-size : 12px; font-weight: bold; background-color : #1cac88;color: white; padding: 4px; border-radius:4px; width: fit-content;">Summary</div><br>
                                                    <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px; text-align: left;">${summary}</p>
                                                </td>
                                                <tr>
                                                    <td style="border-bottom: 2px solid rgba(0, 0, 0, 0.74); background: unset; height: 1px; width: 100%; margin: 0px;"></td>
                                                </tr>
                                                <tr>
                                                    <td align="center" class="esd-block-text">
                                                        <br><div style="font-size : 12px; font-weight: bold; background-color : #1cac88;color: white; padding: 4px; border-radius:4px; width: fit-content;">Simulation</div><br>
                                                        ${simulation_block}
                                                    </td>
                                                </tr>
                                                
                                                <tr>
                                                    <td style="border-bottom: 2px solid rgba(0, 0, 0, 0.74); background: unset; height: 1px; width: 100%; margin: 0px;"></td>
                                                </tr>
                                                
                                                <tr>
                                                    <td align="center" class="esd-block-text">
                                                        <br><div style="font-size : 12px; font-weight: bold; background-color : #1cac88;color: white; padding: 4px; border-radius:4px; width: fit-content;">Transcript</div><br>
                                                        ${bot_conversation}
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td align="center" class="esd-block-spacer es-p20t es-p20b" style="font-size:0">
                                                        <table border="0" width="100%" height="100%" cellpadding="0" cellspacing="0">
                                                            <tbody>
                                                                <tr>
                                                                    <td style="border-bottom: 2px solid rgba(0, 0, 0, 0.74); background: unset; height: 1px; width: 100%; margin: 0px;"></td>
                                                                </tr>
                                                            </tbody>
                                                        </table>
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </td>
                </tr>
            </tbody>
        </table>
    </td>
        """

    template = Template(template).substitute(bot_conversation=data,summary=summary,simulation_block=simulation_block)        
    return template

def get_simulation_block(simulation):

    title = simulation.get('title',None)
    if title:
        description = simulation.get('description')
        test_code = simulation.get('test_code')
        template = """
        <tr>
            <td align="left" class="esd-block-text">
                <p>Title : ${title}<br>Description : ${description}</p>
            </td>
        </tr>
        <tr>
            <td align="center" class="esd-block-spacer es-p20t es-p20b" style="font-size:0">
                <table border="0" width="100%" height="100%" cellpadding="0" cellspacing="0">
                    <tbody>
                        <tr>
                            <td style="border-bottom: 2px solid #ffffff; background: unset; height: 1px; width: 100%; margin: 0px;"></td>
                        </tr>
                    </tbody>
                </table>
            </td>
        </tr>
        <tr>
            <td align="right" class="esd-block-text">
                <p>Simulation code : ${test_code}</p>
            </td>
        </tr>

        """
        return Template(template).substitute(
            title=title,
            description=description,
            test_code = test_code
        )
    else:
        template = """
        <tr>
            <td align="left" class="esd-block-text">
                <p>Sorry your simulation could not be generated because of insufficient data!</p>
            </td>
        </tr>
        """
        return template
    

def send_welcome_email(profile_type, user_email, user_name):
    ## sending Welcome Message to user
    subject = ""
    html_content = ""
    if profile_type in ['coach','mentor']:
        subject = f"Welcome Aboard, {user_name}!"
        html_content =f"""
        <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">
            <div style="margin: 15px;">
                <p>Congratulations and welcome to the Coachbot community!</p>
                <p>We encourage you to explore the Creator Studio, where you can create and assign tailored simulations for your coachees. This feature will empower you to curate learning experiences that address their specific needs and goals.</p>
                <p>Additionally, you can leverage the Action Plans and Session Notes sections to document and track the progress of your coaching journeys. These tools will help you provide meaningful support and guidance to your coachees.</p>
                <p>We're excited to embark on this journey with you. Let's unlock your coachees' full potential together!</p>
                <p>You may have refresh the system for the changes to reflect.</p>
            </div>
        </p>

        """
    elif profile_type in ['coachee','mentee']:
        subject = f"Welcome Aboard, {user_name}!"
        html_content = f"""
        <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">
            <div style="margin: 15px;">
                <p>Congratulations and welcome to the Coachbot community!</p>
                <p>Thank you for creating your profile - it will be live and ready to support your personal and professional development. You can always edit your information through the profile section.</p>
                <p>Your profile will now appear on your directory page, so feel free to explore and get familiar with the platform. If you need any assistance, our help mode is there to guide you.</p>
                <p>We also encourage you to try out the various simulations available in our library. These immersive experiences will help you hone your skills and prepare you for real-world challenges.</p>
                <p>We're excited to embark on this journey with you. Let's unlock your full potential together!</p>
                <p>You may have refresh the system for the changes to reflect.</p>
            </div>
        </p>
        """
    
    send_email_with_html_template(subject=subject,html_content=html_content,to_email=user_email, title=f'Dear {user_name},')

