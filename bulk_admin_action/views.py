import os
from django.core.files.storage import FileSystemStorage
from django.http import FileResponse, HttpResponse
from django.shortcuts import render
import requests
from bulk_admin_action.views import CleanupFileStream, create_scenario_view
from .forms import CreateScenarioForm, TestForm, UploadCsvForm, UploadFileForm
from .tasks import process_create_upload_test_task, process_report_task, upload_scenario_task
import pandas as pd

from django.conf import settings
base_url = settings.BASE_URL


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
                return render(request, 'upload.html', {
                    'form': form,
                    'error': '❌ No file was uploaded. Please choose a file.'
                })
            
            auth = None
            if action != 'create_scenario':
                auth = webauth_login(domain, email, password, base_url)
                if not auth:
                    return render(request, 'upload.html', {
                    'form': form,
                    'error': '❌ Invalid credentials. Please check your email, domain, and password.'
                })
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
                    return render(request, 'upload.html', {
                        'form': form,
                        'error': '❌ Unable to read CSV file.'
                    })


            
            # Trigger the Celery task with all inputs
            if action == 'create_upload_test':
                validated = validate_file(df)
                if not validated:
                    return render(request, 'upload.html', {
                    'form': form,
                    'error': '❌ Invalid file format. Please upload a CSV file.'
                    })
                process_create_upload_test_task.delay(uploaded_df, llm_type, email, password, domain, auth)
                message = '✅ Create/Upload/Test processing started.'
            elif action == 'upload':
                upload_scenario_task(file_path, llm_type, email, password, domain,test_type)
                message = '✅ Upload scenario task started.'
            elif action == 'create_scenario':
                uploaded_df['df'] = df 
                zipfile_name = create_scenario_view(llm_type, uploaded_df)
                if not os.path.exists(zipfile_name):
                    return HttpResponse("❗ ZIP file not found.", status=500)
                zip_stream = CleanupFileStream(zipfile_name)
                response = FileResponse(zip_stream, as_attachment=True, filename=os.path.basename(zipfile_name))
                message = '✅ Create Scenario started.'
                return response
            elif action == 'test':
                process_report_task.delay(auth, test_codes)
                message = 'Test Report Started'
                # process_report_task.delay(auth,test_codes,uploaded_df,llm_type, email, password, domain)
                # message='Test Report Started'
                # csv_file = r'media\report\Bulk_Report.csv'
                # print(os.getcwd())
                # response=FileResponse(open(csv_file, 'rb'), as_attachment=True, filename='Bulk_report.csv')
                # print(open(csv_file, 'rb'))
                # return response
            else:
            # Form is not valid: show errors
                return render(request, 'upload.html', {
                'form': form,
                'error': '❌ Unknown action selected.'
                })
            return render(request, 'upload.html', {
                'form': sub_form(),  # Reset form
                'message': message
            })
            # form = UploadFileForm()

        return render(request, 'upload.html', {'form': form,'error': '❌ Please correct the form errors.'})
    form = sub_form(initial={'action': action})
    return render(request, 'upload.html', {'form': form,'action':action})

