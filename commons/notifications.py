from email_sender.helpers import send_generic_email
import datetime

def send_error_notification(module,msg,data):
    content = "Module: " + module + "\n at => " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n" + "*"*20 + msg + "*"*20 + "<br/><br/>"
    content += "Data: " + str(data) + "\n" 
    to_emails = ["aadil611ofc@gmail.com", "info@coachbots.com", "bagoriarajan@gmail.com"]

    for email in to_emails:
        send_generic_email("Error Notification", content, email)
