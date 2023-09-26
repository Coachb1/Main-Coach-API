from django.shortcuts import render, HttpResponse
import json

from test_bulk_upload.scripts import create_test_slack, create_test_web, create_test_orchestrated_conversation_slack
from .forms import UploadFileForm_slack, UploadFileForm_web
from django.conf import settings
import os
from test_bulk_upload.filler_power_words import filler_power_word
from django.http import JsonResponse
from tests.models import TestQuestionResponse



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