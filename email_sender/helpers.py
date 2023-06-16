import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

LOGIN_EMAIL = "deb@coachbots.com"
FROM_EMAIL = "mail@coachbots.com"
APP_PASSWORD = "daD4QnY3OJBGMVEj"


def send_email(to_email, subject, message):
    from_password = APP_PASSWORD
    from_email = FROM_EMAIL

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email

    msg.attach(MIMEText(message, 'html'))
    msg_str = msg.as_string()

    # login to server
    server = smtplib.SMTP('smtp-relay.sendinblue.com', 587)
    server.starttls()
    server.login(LOGIN_EMAIL, from_password)
    server.sendmail(from_email, to_email, msg_str)
    server.quit()
