from django.shortcuts import render



# Create your views here.
from django.http import JsonResponse
# from demo_app.models import Task
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def process_data(request):
    if request.method == 'POST':
        data = request.POST.get('data', "")

        # Queue the task by creating a Task object
        # Task.objects.create(data=data)

        return JsonResponse({'message': 'Task queued for processing'})
    else:
        return JsonResponse({'error': 'Only POST requests are supported'})