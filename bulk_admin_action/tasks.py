import io
import os
from celery import shared_task
from django.conf import settings
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
from bulk_admin_action.utils import create_scenario_view
from email_sender.helpers import send_email_from_emailit, send_emailv2
from settings import BACKEND

base_url = BACKEND


@shared_task
def process_create_scenario(llm_type, uploaded_df):
    try:
        file_path = uploaded_df.get('file_path')
        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError(f"❗ File not found at path: {file_path}")

        print(f"📥 Reading uploaded file: {file_path}")
        df = pd.read_csv(file_path)

        uploaded_df['df'] = df

        zip_name = create_scenario_view(
            llm_type=llm_type,
            uploaded_df=uploaded_df
        )

        print(f"✅ Scenario ZIP ready: {zip_name}")
        return zip_name

    except Exception as e:
        print(f"❌ Error in process_create_scenario: {e}")
        raise e



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

        send_emailv2(
            to_email='bagoriarajan@gmail.com',
            subject="Bulk Report Ready",
            body="Your requested report is attached.",
            attachment_path=report_file_name
        )
        print("✅ Email sent successfully with the processed file.")
        report_file_name = os.path.relpath(report_file_name, start=settings.BASE_DIR)
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
            return True, uploaded_test
      
        except Exception as e:
            return False, [f'❌ Failed to Upload and test, Reason: {e}']
        

@shared_task
def process_report_task(auth, test_codes):
    automated_scenario = AutomatedScenarios(auth)
    automated_scenario.generate_test(
        TEST_CODES=test_codes.split(','),
        file_name='report/Bulk_Report.csv',
        IS_AUDIO=False
    )

    send_file = 'media/report/Bulk_Report.csv'

    try:
        file_path = send_file
        print(f"📁 Checking if file exists at: {file_path}")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found at {file_path}")

        # Email body content (HTML)
        email_body = """
        <h2>📊 Bulk Report Generated</h2>
        <p>Your requested report is attached.</p>
        <p>Regards,<br><strong>Coach Bot</strong></p>
        """

        # Send email with attachment
        send_emailv2(
            to_email='bagoriarajan@gmail.com',
            subject="Bulk Report Ready",
            body=email_body,
            attachment_path=file_path
        )

        print("📨 Email sent with attachment.")
        file_path = os.path.relpath(file_path, start=settings.BASE_DIR)
        return file_path

    except Exception as e:
        print(f"❌ Error in process_report_task: {e}")
        raise

    

@shared_task(bind=True)
def process_bulk_prompt_task(self, csv_path,filename, llm_type):
    df = pd.read_csv(io.StringIO(csv_path))
    zip_filename = process_files(df, filename, llm_type)
    return zip_filename