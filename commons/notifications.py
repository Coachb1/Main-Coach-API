from email_sender.helpers import send_generic_email
import datetime
import os

ENV = os.getenv("ENV", "dev")

def send_error_notification(module,msg,data):
    content = "Module: " + module + "\n at => " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n" + "*"*20 + msg + "*"*20 + "<br/><br/>"
    content += "Data: " + str(data) + "\n" 
    # to_emails = ["aadil611ofc@gmail.com", "coachbots@googlegroups.com", "bagoriarajan@gmail.com"]
    to_emails = ['coachbots@googlegroups.com']

    for email in to_emails:
        send_generic_email(f"Error Notification :({ENV})", content, email)
