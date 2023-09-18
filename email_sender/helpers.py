import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from settings import BASE_DIR
from users.models import UserAttribute
import logging

LOGIN_EMAIL = "deb@coachbots.com"
FROM_EMAIL = "mail@coachbots.com"
FROM_EMAIL_DISPLAY = "Coachbots Report <mail@coachbots.com>"
APP_PASSWORD = "daD4QnY3OJBGMVEj"


def send_email(to_email, subject, data):
    from_password = APP_PASSWORD
    from_email = FROM_EMAIL

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = FROM_EMAIL_DISPLAY
    msg['To'] = to_email


    candidate_name = f"{data['real_name']} (username: {data['candidate_name']})"

    html_body = get_html_body(
        candidate_name, data["test_name"], data["report_url"])

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


def get_html_body(candidate_name, test_name, report_url):

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
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">The  {candidate_name} has completed the interaction {test_name}. The detailed report can be viewed here:</p>
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
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">You will be able to request leaderboard reports and other simulations via the platform channels as per admin privileges. Thank you! </p>
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">- Coachbots Team</p>
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
                        <span class="apple-link" style="color: #999999; font-size: 14px; text-align: center;">(c) Coachbots 2023. Powered by Answer Cloud Technology Pvt Ltd </span>
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
                            <p style="font-family: sans-serif; font-size: 14px; font-weight: normal; margin: 0; margin-bottom: 15px;">- Coachbots Team</p>
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
                        <span class="apple-link" style="color: #999999; font-size: 14px; text-align: center;">(c) Coachbots 2023. Powered by Answer Cloud Technology Pvt Ltd </span>
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
