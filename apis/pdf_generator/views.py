from django.views.generic import View
import pdfkit
from django.views import View
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.shortcuts import render
from datetime import datetime
import os
import json
from django.conf import settings
from tests.models import TestAttemptSession, TestQuestion, TestQuestionResponse, Test
from tests.choices import TestQuestionResponseEvaluationStatusChoices
from users.models import User


#
# def card(request, text, template_id):
#     return render(
#         request,
#         f"card/{template_id}.html",
#         {
#             'text': text,
#         }
#     )


class GetPDF(View):
    def get(self, request, *args, **kwargs):
        # getting text from request body
        try:
            json_string = request.body.decode('utf-8')
            text = json.loads(json_string).get('text', 'Hello, PDF-Generator!')
            # split text where *
            text = text.split('*')
        except:
            text = ['Hello, PDF-Generator!']
        t = render_to_string(
            f"card/{kwargs.get('template_id', '1')}.html", {'text': text})

        options = {
            'page-size': 'Letter',
            'encoding': "UTF-8",
            'enable-local-file-access': "",
        }

        css = os.path.join(settings.BASE_DIR, 'pdf_generator',
                           'static', 'card', 'styles_pdf.css')
        # align images in the pdf at center
        pdf = pdfkit.from_string(t, False, options, css=css)

        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{text[:6]}.pdf"'
        return response

# Generate Report of the Test Interaction given an interaction id

# uid - ba72367e-0dad-43c9-bb0d-8b9e0154315f


def generate_report(request, test_session_id):
    # get the test session object via test_session_id which is of type uid
    test_session = TestAttemptSession.objects.get(uid=test_session_id)

    # get the test id
    test_id = test_session.test_id

    # # Get title of the test from test_id
    # test_object = Test.objects.get(uid=test_id)
    # test_title = test_object.title
    # get the participant id
    participant_id = test_session.participant_id
    # get the participant name
    participant_name = User.objects.get(
        uid=participant_id).name
    # get the test started and finished time
    test_started_at = test_session.started_at
    test_finished_at = test_session.finished_at

    # get the questions, top candidate response and participant response
    questions = TestQuestion.objects.filter(test_id=test_id)

    # get the responses of the participant
    participant_responses = TestQuestionResponse.objects.filter(
        test_attempt_session_id=test_session_id)

    qa = []

    for question in questions:
        # get the question id
        question_id = question.uid
        # get the question text
        question_text = question.question
        # get the question type
        question_type = question.question_type
        # get the question media link
        question_media_link = question.media_link
        # get the question answer
        question_answer = question.subjective_answer
        # get the question mcq options
        question_mcq_options = question.mcq_options
        # get the question mcq answer
        question_mcq_answer = question.mcq_answer
        # get the question gpt prompt override
        question_gpt_prompt_override = question.gpt_prompt_override

        participant_response = None

        # get the response of the participant
        for response in participant_responses:
            if response.question_id == question_id:
                participant_response = response
                break
        if participant_response is None:
            continue
        # get the response file
        response_file = participant_response.response_file
        # get the response text
        response_text = participant_response.response_text
        # get the evaluation status
        evaluation_status = participant_response.evaluation_status
        # get the feedback text
        feedback_text = participant_response.feedback_text
        # get the metadata
        metadata = participant_response.metadata

        qa.append(
            {
                'question_id': question_id,
                'question_text': question_text,
                'question_type': question_type,
                # 'question_media_link': question_media_link,
                # 'question_answer': question_answer,
                'question_mcq_options': question_mcq_options,
                'question_mcq_answer': question_mcq_answer,
                # 'question_gpt_prompt_override': question_gpt_prompt_override,
                # 'response_file': response_file,
                'response_text': response_text,
                # 'evaluation_status': evaluation_status,
                'feedback_text': feedback_text,
                # 'metadata': metadata,
            }
        )

    t = render_to_string(
        f"card/report.html", {'qa': qa, 'participant_name': participant_name, 'test_started_at': test_started_at})

    options = {
        'page-size': 'Letter',
        'encoding': "UTF-8",
        'enable-local-file-access': "",
    }

    # css = os.path.join(settings.BASE_DIR, 'pdf_generator',
    #                    'static', 'card', 'styles_pdf.css')
    # align images in the pdf at center
    pdf = pdfkit.from_string(t, False, options)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="report.pdf"'
    return response
