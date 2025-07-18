import io
import os
from django.core.files.storage import FileSystemStorage
from django.http import FileResponse, HttpResponse
from django.shortcuts import render, redirect
import requests
from bulk_admin_action.llm_playground.helper import process_files
from bulk_admin_action.utils import CleanupFileStream, create_scenario_view, get_dynamic_csv, validate_file
from test_bulk_upload.scripts import login_slack
from .forms import BulkGeminiPromptProcessor, CreateScenarioForm, DynamicCsvForm, NormalCSVForm, TestForm, UploadCsvForm, UploadFileForm
from .tasks import process_bulk_prompt_task, process_create_scenario, process_create_upload_test_task, process_report_task, upload_scenario_task
import pandas as pd
from celery.result import AsyncResult

from django.views.decorators.csrf import csrf_exempt

from django.conf import settings
from django.contrib import messages
import logging
from settings import BACKEND


logger = logging.getLogger(__name__)


base_url = BACKEND


def upload_view(request):
    action = request.GET.get('action', 'create_upload_test')
    sub_form = None
    message = ''
    if action == 'create_upload_test':
        sub_form = UploadFileForm
    elif action == 'upload':
        sub_form = UploadCsvForm
    elif action == 'test':
        sub_form = TestForm
    elif action == 'create_scenario':
        sub_form = CreateScenarioForm
    print(request.method,action)
    if request.method == 'POST':
        print("POST data:", request.POST.dict())
        form = sub_form(request.POST, request.FILES)
        if form.is_valid():
            # action = form.cleaned_data.get('action')
            llm_type = form.cleaned_data.get('llm_type')
            uploaded_file = request.FILES.get('file')
            email = form.cleaned_data.get('email')
            domain = form.cleaned_data.get('domain')
            password = form.cleaned_data.get('password')
            test_type = form.cleaned_data.get('test_type')
            test_codes = form.cleaned_data.get('test_code')
            
    
            print(action,llm_type,uploaded_file, email,domain,password,test_type, test_codes)
           

            # Check if file is actually uploaded
             
            if not uploaded_file and action !='test':
                return render(request, 'bulk_admin_actions/upload.html', {
                    'form': form,
                    'error': '❌ No file was uploaded. Please choose a file.'
                })
            
            auth = None
            if action != 'create_scenario':
                auth = login_slack(subdomain_prefix=domain, email=email, password=password)
                if not auth:
                    return render(request, 'bulk_admin_actions/upload.html', {
                    'form': form,
                    'error': '❌ Invalid credentials. Please check your email, domain, and password.'
                })
                auth = f"Bearer {auth}"
            if uploaded_file:
                fs = FileSystemStorage()
                filename = fs.save(uploaded_file.name, uploaded_file)
                file_path = fs.path(filename)
                uploaded_df = {}
                uploaded_df['file_path'] = file_path
                df = pd.read_csv(file_path)
                uploaded_df['filename'] = filename
                try:
                    df = pd.read_csv(file_path)
                except Exception:
                    return render(request, 'bulk_admin_actions/upload.html', {
                        'form': form,
                        'error': '❌ Unable to read CSV file.'
                    })


            
            # Trigger the Celery task with all inputs
            if action == 'create_upload_test':
                validated = validate_file(df)
                if not validated:
                    return render(request, 'bulk_admin_actions/upload.html', {
                    'form': form,
                    'error': '❌ Invalid file format. Please upload a CSV file.'
                    })
                task = process_create_upload_test_task.delay(uploaded_df, llm_type, email, password, domain, auth)
                message = '✅ Create/Upload/Test processing started.'
                task_id = task.id

                if not task_id:
                    message = "❗ Task ID missing."
                    return render(request, 'bulk_admin_actions/bulk_task_status.html', {'message': message})

                return render(request, 'bulk_admin_actions/bulk_task_status.html', {
                    'task_id': task_id,
                    'message': 'File uploaded successfully. Processing started!',
                })
            elif action == 'upload':
                success, uploaded_test = upload_scenario_task(file_path, llm_type, email, password, domain,test_type)
                print("Upload success:", success, "uploaded_test:", uploaded_test)
                if not success:
                    return render(request, 'bulk_admin_actions/upload.html', {
                        'form': form,
                        'error': f"❌ Failed to upload scenario."
                    })
                message = '✅ Scenario uploaded successfully.'
                if 'file_content' in uploaded_test:
                    response = HttpResponse(uploaded_test['file_content'], content_type='text/csv')
                    response['Content-Disposition'] = 'attachment; filename="scenario_output.csv"'
                    return response
                else:
                    return render(request, 'bulk_admin_actions/upload.html', {
                        'form': form,
                        'error': '❌ Failed to upload scenario.'
                    })
            elif action == 'create_scenario':
                task = process_create_scenario.delay(llm_type, uploaded_df)
                task_id = task.id
                message = 'Scenario Creation Started'
                if not task_id:
                    message = "❗ Task ID missing."
                    return render(request, 'bulk_admin_actions/bulk_task_status.html', {'message': message})

                return render(request, 'bulk_admin_actions/bulk_task_status.html', {
                    'task_id': task_id,
                    'message': 'File uploaded successfully. Processing started!',
                })
                # uploaded_df['df'] = df 
                # zipfile_name = create_scenario_view(llm_type, uploaded_df)
                # if not os.path.exists(zipfile_name):
                #     return HttpResponse("❗ ZIP file not found.", status=500)
                # zip_stream = CleanupFileStream(zipfile_name)
                # response = FileResponse(zip_stream, as_attachment=True, filename=os.path.basename(zipfile_name))
                # message = '✅ Create Scenario started.'
                # return response

            elif action == 'test':
                task = process_report_task.delay(auth, test_codes)
                task_id = task.id
                message = 'Test Report Started'
                if not task_id:
                    message = "❗ Task ID missing."
                    return render(request, 'bulk_admin_actions/bulk_task_status.html', {'message': message})

                return render(request, 'bulk_admin_actions/bulk_task_status.html', {
                    'task_id': task_id,
                    'message': 'File uploaded successfully. Processing started!',
                })
            else:
                return render(request, 'bulk_admin_actions/upload.html', {
                'form': form,
                'error': '❌ Unknown action selected.'
                })

        return render(request, 'bulk_admin_actions/upload.html', {'form': form,'error': '❌ Please correct the form errors.'})
    form = sub_form(initial={'action': action})
    return render(request, 'bulk_admin_actions/upload.html', {'form': form,'action':action})


def upload_and_process_llm(request):
    message = ''
    if request.method == 'POST':
        form = BulkGeminiPromptProcessor(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data['csv_file']
            llm_type = form.cleaned_data['llm_type']
            try:
                # Your processing...
                filename = csv_file.name
                task = process_bulk_prompt_task.delay(csv_file.read().decode('utf-8'),filename,llm_type)
                task_id = task.id

                if not task_id:
                    message = "❗ Task ID missing."
                    return render(request, 'bulk_admin_actions/bulk_task_status.html', {'message': message})

                return render(request, 'bulk_admin_actions/bulk_task_status.html', {
                    'task_id': task_id,
                    'message': 'File uploaded successfully. Processing started!',
                })
            except Exception as e:
                message = f"❗ Error: {e}"
    else:
        form = BulkGeminiPromptProcessor()  # 👈 you MUST define form here for GET

    return render(request, 'bulk_admin_actions/bulkprompt.html', {
        'form': form,
        'message': message,
    })


def check_task_status(request, task_id):
    result = AsyncResult(task_id)
    task_state = result.state
    print("Checking task status for ID:", task_id, "State:", task_state)


    if task_state == 'SUCCESS':
        filepath = result.result
        print("Task completed successfully. File path:", filepath)
     

        if filepath and os.path.exists(filepath):
            try:
                response = FileResponse(open(filepath, 'rb'), as_attachment=True, filename=os.path.basename(filepath))
                os.remove(filepath)  # Optional: clean up after sending
                return response
            except Exception as e:
                logger.error(f"Error while sending file: {e}")
                return render(request, "bulk_admin_actions/check_status.html", {
                    "task_state": "FAILURE",
                    "error": "Error while sending file."
                })
        else:
            return render(request, "bulk_admin_actions/check_status.html", {
                "task_state": "FAILURE",
                "error": "File not found. It may have been deleted. please check the email."
            })

    elif task_state == 'FAILURE':
        logger.error(f"Task {task_id} failed: {result.result}")
        return render(request, "bulk_admin_actions/check_status.html", {
            "task_state": "FAILURE",
            "error": str(result.result)
        })

    elif task_state in ['PENDING', 'RETRY', 'STARTED']:
        return render(request, "bulk_admin_actions/check_status.html", {
            "task_state": task_state,
            "task_id": task_id,
        })

    else:
        return render(request, "bulk_admin_actions/check_status.html", {
            "task_state": "UNKNOWN"
        })

@csrf_exempt
def get_csv_view(request):
    if request.method == 'POST':
        form = NormalCSVForm(request.POST)

        if form.is_valid():
            data = form.cleaned_data
            access_token = login_slack(
                subdomain_prefix=data['subdomain_prefix'],
                email=data['email'],
                password=data['password']
            )
            if access_token:
                access_token = f"Bearer {access_token}"
                url = f"{base_url}/api/v1/tests/get_normal_test_csv/"
                params = {}

                for key in ['title', 'test_type', 'interaction_mode', 'scenario_case',
                            'num_questions', 'candidate_type', 'test_codes',
                            'page_name', 'competency_skills', 'tab_category',
                            'client_name', 'creator_email']:
                    value = data.get(key)
                    if value not in [None, '']:
                        params[key] = value

                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': access_token
                }

                try:
                    response = requests.get(url, params=params, headers=headers)
                    if response.status_code == 200:
                        json_data = response.json()
                        test_list = json_data.get('test_list', [])
                        if len(test_list) == 0:
                            messages.warning(request, "No tests found for the given criteria.")
                            return redirect(request.path)
                        heading = json_data.get('heading', '')

                        csv_data = heading + "\n"
                        for test in test_list:
                            df = pd.DataFrame([test])
                            csv_row = df.to_csv(index=False, header=False)
                            csv_data += csv_row

                        # Create response to download
                        csv_response = HttpResponse(csv_data, content_type='text/csv')
                        csv_response['Content-Disposition'] = 'attachment; filename=bulk_test_data.csv'
                        messages.success(request, "CSV fetched successfully!")
                        return csv_response

                    else:
                        messages.error(request, "Failed to fetch CSV. Server responded with an error.")
                        return redirect(request.path)

                except Exception as e:
                    messages.error(request, f"Exception occurred: {str(e)}")
                    return redirect(request.path)

            else:
                messages.error(request, "❗ Invalid credentials. Please check your email, password, and subdomain.")
                return redirect(request.path)

        else:
            messages.error(request, "Please correct the errors in the form.")
            return redirect(request.path)

    else:
        form = NormalCSVForm()

    return render(request, 'bulk_admin_actions/normal_csv_dw.html', {'form': form})


@csrf_exempt
def get_dynamic_csv_view(request):
    if request.method == 'POST':
        form = DynamicCsvForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data

            access_token = login_slack(
                subdomain_prefix=data['subdomain_prefix'],
                email=data['email'],
                password=data['password']
            )

            if not access_token:
                messages.error(request, "❗ Invalid credentials. Please check your email, password, and subdomain.")
                return redirect(request.path)

            auth_header = f"Bearer {access_token}"

            try:
                response_data = get_dynamic_csv(
                    test_type=data.get('test_type'),
                    interaction_mode=data.get('interaction_mode'),
                    scenario_case=data.get('scenario_case'),
                    num_questions=data.get('num_questions'),
                    candidate_type=data.get('candidate_type'),
                    test_codes=data.get('test_codes'),
                    page_name=data.get('page_name'),
                    competency_skills=data.get('competency_skills'),
                    tab_category=data.get('tab_category'),
                    auth=auth_header,
                    bots=data.get('bots'),
                    is_start_with_user=data.get('is_start_with_user')
                )

                if response_data:
                    
                    test_list = response_data.get('test_list', [])
                    if len(test_list) == 0:
                        messages.warning(request, "No tests found for the given criteria.")
                        return redirect(request.path)
                    heading = response_data.get('heading', '')

                    csv_data = heading + "\n"
                    for test in test_list:
                        df = pd.DataFrame([test])
                        csv_row = df.to_csv(index=False, header=False)
                        csv_data += csv_row

                    csv_response = HttpResponse(csv_data, content_type='text/csv')
                    csv_response['Content-Disposition'] = 'attachment; filename=dynamic_test_data.csv'
                    messages.success(request, "Dynamic CSV fetched successfully!")
                    return csv_response

                else:
                    messages.error(request, "Failed to fetch CSV. Server responded with an error.")
                    return redirect(request.path)

            except Exception as e:
                messages.error(request, f"Exception occurred: {str(e)}")
                return redirect(request.path)

        else:
            messages.error(request, "Please correct the errors in the form.")
            return redirect(request.path)

    else:
        form = DynamicCsvForm()

    return render(request, 'bulk_admin_actions/dynamic_csv_dw.html', {'form': form})


def admin_dashboard(request):
    return render(request, 'bulk_admin_actions/admin_dashboard.html')