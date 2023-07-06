from django.shortcuts import render, HttpResponse
import json

from test_bulk_upload.scripts import create_test_slack, create_test_web
from .forms import UploadFileForm_slack, UploadFileForm_web
from django.conf import settings
import os



def bulk_test_upload(request):
    # css_file = os.path.join(settings.TEMPLATES_DIR, 'test_bulk_upload',
    #                    'static', 'css', 'index.css')
    # print(css_file)
    # context = {"css_file" : css_file}
    return render(request, 'test_bulk_upload/templates/index.html')


def test_create_web(request):
    form = UploadFileForm_web()
    return render(request, 'test_bulk_upload/templates/create_test.html', {'urlSlug': "process-file-web", 'form': form})


def test_create_slack(request):
    form = UploadFileForm_slack()
    return render(request, 'test_bulk_upload/templates/create_test.html', {'urlSlug': "process-file-slack", 'form': form})


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
