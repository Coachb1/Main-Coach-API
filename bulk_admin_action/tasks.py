import io
import os
from celery import shared_task
from django.http import FileResponse, HttpResponse
from django.shortcuts import render
import pandas as pd
import smtplib
from email.message import EmailMessage

import requests
from bulk_admin_action.automated_scenario import AutomatedScenarios, upload_scenario
from bulk_admin_action.forms import BulkGeminiPromptProcessor
from bulk_admin_action.create_upload_test import process_create_upload_test
from bulk_admin_action.llm_playground.helper import process_files

base_url = "https://coach-api-gke-dev.coachbots.com"


@shared_task
def process_create_upload_test_task(uploaded_df_dict, llm_type, email, password, domain, auth):
    try:
        # Extract file details
        file_name = uploaded_df_dict['filename'].replace('.csv', '')
        report_file_name = f'media/Bulk Report Testing- {file_name}.csv'

        # Read CSV and store DataFrame
        df = pd.read_csv(uploaded_df_dict['file_path'])
        uploaded_df_dict['df'] = df

        # Process (assuming this returns logs and output file name)
        logs, result_file_name = process_create_upload_test(uploaded_df_dict, llm_type, email, password, domain, auth)

        # Prepare email
        msg = EmailMessage()
        msg['Subject'] = 'Processed File'
        msg['From'] = 'suvendusahoo80806@gmail.com'
        msg['To'] = 'bagoriarajan@gmail.com'
        msg.set_content('Find attached the processed CSV file.')

        with open(report_file_name, 'rb') as f:
            content = f.read()
            print(content)
            msg.add_attachment(content, maintype='application', subtype='octet-stream', filename='result.csv')

        # with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
        #     smtp.starttls()
        #     smtp.login('suvendusahoo80806@gmail.com', 'njpa qnez gdzh mjgu')  # ⚠️ Replace with secure method
        #     smtp.send_message(msg)

        print("✅ Email sent successfully with the processed file.")
        return report_file_name

    except Exception as e:
        print(f"❌ Error in task: {e}")
        raise Exception(f"Failed: {e}")

@shared_task
def upload_scenario_task(file_path, llm_type, email, password, domain,test_type):
    with open(file_path, 'rb') as f:
        try:
            uploaded_test= upload_scenario(f,email, password, domain,test_type)
            if not uploaded_test['success']:
                raise Exception(f"Failed to generate all test: {uploaded_test['errors']}")
            return True, uploaded_test['errors']
      
        except Exception as e:
            return False, [f'❌ Failed to Upload and test, Reason: {e}']
        

@shared_task
def process_report_task(auth,test_codes):
    automated_scenario = AutomatedScenarios(auth)
    automated_scenario.generate_test(TEST_CODES=test_codes.split(','),file_name='report\Bulk_Report.csv',IS_AUDIO=False)
    send_file='media/report/Bulk_Report.csv'
    try:
        file_name = send_file
        # report_file_name = f'report/Bulk_Report -{file_name}.csv'
        
        # Prepare email
        email = EmailMessage()
        email['Subject'] = 'Processed File'
        email['From'] = 'suvendusahoo80806@gmail.com'
        email['To'] = 'suvendusahoo38@gmail.com'
        email.set_content('Find attached the processed CSV file.')

        with open(file_name, 'rb') as f:
            email.add_attachment(f.read(), maintype='application', subtype='octet-stream', filename=file_name)

        # Send email using Gmail SMTP with app password
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.starttls()
            smtp.login('suvendusahoo80806@gmail.com', 'njpa qnez gdzh mjgu')  # replace securely
            smtp.send_message(email)

        print("✅ Email sent successfully with the processed file.")
        try:
            print(f"📁 Checking file exists at: {file_name}")
            print("✅ Exists:", os.path.exists(file_name))
            # if os.path.exists(file_name):
            #     os.remove(file_name)
            #     print(f"🗑️ Deleted file: {file_name}")
            # else:
            #     print(f"❌ File not found, cannot delete: {file_name}")
        except Exception as delete_error:
            print(f"❌ Failed to delete file: {delete_error}")
        return file_name

    except Exception as e:
        print(f"❌ Error in task: {e}")
        return f"Failed: {e}"  
    

@shared_task(bind=True)
def process_bulk_prompt_task(self, csv_path,filename, llm_type):
    df = pd.read_csv(io.StringIO(csv_path))
    zip_filename = process_files(df, filename, llm_type)
    return zip_filename