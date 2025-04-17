from django.shortcuts import render, HttpResponse
import json

from test_bulk_upload.scripts import create_test_slack, create_test_web, create_test_orchestrated_conversation_slack, create_coaches_and_bots_from_data
from .forms import UploadFileForm_slack, UploadFileForm_web
from django.conf import settings
import os
from test_bulk_upload.filler_power_words import filler_power_word
from django.http import JsonResponse
from tests.models import TestQuestionResponse
from django.views.decorators.csrf import csrf_exempt



def bulk_test_upload(request):
    return render(request, 'test_bulk_upload/templates/index.html')


def test_create_web(request):
    form = UploadFileForm_web()
    return render(request, 'test_bulk_upload/templates/create_test.html', {'urlSlug': "process-file-web", 'form': form})


def test_create_slack(request):
    form = UploadFileForm_slack()
    return render(request, 'test_bulk_upload/templates/create_test.html', {'urlSlug': "process-file-slack", 'form': form})

def test_create_orchestrated_conversation_slack(request):
    form = UploadFileForm_slack()
    return render(request, 'test_bulk_upload/templates/create_test.html', {'urlSlug': "process-orchestrated-conversation-slack-file", 'form': form})


def upload_coach_and_bots(request):
    form = UploadFileForm_slack()
    return render(request, 'test_bulk_upload/templates/upload_coach_and_bots.html', {'urlSlug': "process-coach-bots", 'form': form})


def process_coach_and_bots(request):
    if request.method == 'POST':
        file = request.FILES.get('myfile')
        email = request.POST.get('email')
        password = request.POST.get('password')
        subdomain_prefix = request.POST.get('client_domain_prefix')
        result = create_coaches_and_bots_from_data(file, email, password, subdomain_prefix)
        if (len(result['errors']) > 0):
            if result.get('file_response'):
                file_response_content = result['file_response'].content.decode('utf-8')
                result['file_response'] = file_response_content
            return HttpResponse(content=json.dumps(result), status=400)
        else:
            return result['file_response']

def process_web_file(request):
    if request.method == 'POST':
        file = request.FILES.get('myfile')
        email = request.POST.get('email')
        password = request.POST.get('password')
        result = create_test_web(file, email, password)
        if (len(result['errors']) > 0):
            return HttpResponse(content=json.dumps(result), status=400)
        else:
            return HttpResponse(content=json.dumps(result), status=200)


def process_slack_file(request):
    if request.method == 'POST':
        file = request.FILES.get('myfile')
        email = request.POST.get('email')
        password = request.POST.get('password')
        subdomain_prefix = request.POST.get('client_domain_prefix')
        result = create_test_slack(file, email, password, subdomain_prefix)

        if (len(result['errors']) > 0):
            if result.get('file_response'):
                file_response_content = result['file_response'].content.decode('utf-8')
                result['file_response'] = file_response_content
            return HttpResponse(content=json.dumps(result), status=400)
        else:
            return result['file_response']
        
def process_orchestrated_conversation_slack_file(request):
    if request.method == 'POST':
        file = request.FILES.get('myfile')
        email = request.POST.get('email')
        password = request.POST.get('password')
        subdomain_prefix = request.POST.get('client_domain_prefix')
        result = create_test_orchestrated_conversation_slack(file, email, password, subdomain_prefix)

        if (len(result['errors']) > 0):
            if result.get('file_response'):
                file_response_content = result['file_response'].content.decode('utf-8')
                result['file_response'] = file_response_content
            return HttpResponse(content=json.dumps(result), status=400)
        else:
            return result['file_response']

def get_filler_and_powerwords(request):
    interaction_session_id = request.GET.get('interaction_session_id')
    participant_responses = TestQuestionResponse.objects.filter(
        test_attempt_session_id=interaction_session_id,responder_type='user')
    allresponse = ""
    for response in participant_responses:
        allresponse += response.response_text + " "

    power_word,fill_word = filler_power_word(allresponse)

    data = {"Power Words": list(power_word),"Filler Words": list(fill_word)}
    return JsonResponse({"data":data})

@csrf_exempt
def upload_scenarios(request):
    if request.method == 'POST':
        file = request.FILES.get('myfile')
        email = request.POST.get('email')
        password = request.POST.get('password')
        subdomain_prefix = request.POST.get('client_domain_prefix')
        test_type = request.POST.get('test_type')
        if test_type == 'static':
            result = create_test_slack(file, email, password, subdomain_prefix)
        else:
            result = create_test_orchestrated_conversation_slack(file, email, password, subdomain_prefix)

        if len(result.get('errors',[]) )> 0:
            return JsonResponse({'success': False, 'errors': result['errors']}, status=400)
        else:
            file_response = result.get('file_response')

            # 🛠 Convert HttpResponse content to JSON or plain text
            if isinstance(file_response, HttpResponse):
                content = file_response.content.decode('utf-8')  # text
                try:
                    parsed_content = json.loads(content)  # JSON (optional)
                    parsed_content = {
                        'title': parsed_content,
                    }
                except json.JSONDecodeError:
                    parsed_content = content  # fallback to raw text
            else:
                parsed_content = file_response

            return JsonResponse({
                'success': True,
                'file_content': parsed_content
            }, status=200)