import os
import tempfile

import pdfkit
from django.conf import settings
from django.template.loader import render_to_string

from documents.choices import DocOwnerTypeChoice, DocTypeChoice
from documents.helpers import create_document, get_document_url_from_doc_id, get_document_url
from skills.helpers import get_participant_info, top_N_leadership_board
from tenants.helpers import tenant_from_tenant_id
from tests.db_helpers import get_test_questions_from_test
from tests.models import Test, TestQuestion, TestAttemptSession, TestQuestionResponse
from users.db import get_user_display_name, get_user_by_id

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import io
import urllib, base64

options = {
    'page-size': 'Letter',
    'encoding': "UTF-8",
    'enable-local-file-access': "",
}


def convert_html_to_pdf(html_str, css_file):
    return pdfkit.from_string(html_str, False, options, css=css_file)


def get_flash_cards_from_test(test: Test):
    if test.flash_card_doc_id:
        return [get_document_url_from_doc_id(test.flash_card_doc_id)]

    tenant = tenant_from_tenant_id(test.tenant_id)
    test_question_list = get_test_questions_from_test(test)

    css_file = os.path.join(settings.TEMPLATES_DIR,
                            'pdf_generator',
                            'flash_cards',
                            'static',
                            'card',
                            'styles_pdf.css')

    test_question_flash_card_doc_id_map = {}

    flash_card_html_strings = []
    flash_cards = []

    for question in test_question_list:
        flash_card_html = render_to_string(
            "pdf_generator/flash_cards/flash_card_1.html", {"heading": test.title,
                                                            "text": question.key_learning_point}
        )

        flash_card_html_strings.append(flash_card_html)

    pdf = convert_html_to_pdf("\n".join(flash_card_html_strings), css_file)

    with tempfile.NamedTemporaryFile() as pdf_file:
        pdf_file.write(pdf)
        pdf_file.content_type = "application/pdf"
        pdf_file.size = len(pdf)

        doc = create_document(
            tenant=tenant,
            owner_type=DocOwnerTypeChoice.system,
            owner_id=tenant.uid,
            display_name=f"flash_card_{test.uid}.pdf",
            doc_type=DocTypeChoice.FLASH_CARD,
            file=pdf_file
        )

        Test.objects.filter(
            uid=test.uid
        ).update(
            flash_card_doc_id=doc.uid
        )

    # saved_flash_cards = []
    # for flash_card in flash_cards:
    #     question_uid, pdf_data = flash_card
    #     with tempfile.NamedTemporaryFile() as pdf_file:
    #         pdf_file.write(pdf_data)
    #         pdf_file.content_type = content_type
    #         pdf_file.size = len(pdf_data)

    #         doc = create_document(
    #             tenant=tenant,
    #             owner_type=DocOwnerTypeChoice.system,
    #             owner_id=tenant.uid,
    #             display_name=f"flash_card_{question_uid}.{file_format}",
    #             doc_type=DocTypeChoice.FLASH_CARD,
    #             file=pdf_file
    #         )

    #     saved_flash_cards.append((question_uid, doc.uid))

    return [get_document_url(doc)]


def get_report_from_test_attempt_session(test_attempt_session: TestAttemptSession):
    if test_attempt_session.report_doc_id:
        return get_document_url_from_doc_id(test_attempt_session.report_doc_id)

    tenant = tenant_from_tenant_id(test_attempt_session.tenant_id)
    test_id = test_attempt_session.test_id
    # test = Test.objects.get(uid=test_id)
    participant_id = test_attempt_session.participant_id
    participant_name = get_user_display_name(get_user_by_id(participant_id))
    test_started_at = test_attempt_session.started_at.strftime("%d %b %Y")

    questions = TestQuestion.objects.filter(test_id=test_id)
    participant_responses = TestQuestionResponse.objects.filter(
        test_attempt_session_id=test_attempt_session.uid)

    qa = []

    for question in questions:
        question_id = question.uid
        question_text = question.question

        participant_response = None

        # get the response of the participant
        for response in participant_responses:
            if response.question_id == question_id:
                participant_response = response
                break

        if participant_response is None:
            continue

        response_text = participant_response.response_text
        feedback_text = participant_response.feedback_text

        qa.append({
            "question_text": question_text,
            "response_text": response_text,
            "feedback_text": feedback_text
        })

    uri = get_test_attempt_session_skills_graph(test_attempt_session)

    t = render_to_string(
        f"pdf_generator/reports/report.html",
        {
            'qa': qa, 
            'participant_name': participant_name, 
            'test_started_at': test_started_at,
            'uri': uri
        })

    css = os.path.join(settings.TEMPLATES_DIR, 'pdf_generator',
                       'reports', 'static', 'styles_report.css')

    pdf = convert_html_to_pdf(t, css)

    # with tempfile.NamedTemporaryFile() as pdf_file:
    #     pdf_file.write(pdf)
    #     pdf_file.content_type = "application/pdf"
    #     pdf_file.size = len(pdf)

    #     doc = create_document(
    #         tenant=tenant,
    #         owner_type=DocOwnerTypeChoice.system,
    #         owner_id=tenant.uid,
    #         display_name=f"report_{test_attempt_session.uid}.pdf",
    #         doc_type=DocTypeChoice.REPORT,
    #         file=pdf_file
    #     )

    # TestAttemptSession.objects.filter(
    #     uid=test_attempt_session.uid
    # ).update(
    #     report_doc_id=doc.uid
    # )

    # save to local file
    with open(f"report_{test_attempt_session.uid}.pdf", "wb") as f:
        f.write(pdf)

    return 'get_document_url(doc)'


def get_participant_report(user) -> str:
    participant_info = get_participant_info(user)

    participant_name = participant_info['name']

    css = os.path.join(settings.TEMPLATES_DIR, 'pdf_generator',
                       'reports', 'static', 'styles_report.css')

    t = render_to_string(
        f"pdf_generator/reports/participant_report.html", {'participant_name': participant_name,
                                                           'participant_info': participant_info})

    pdf = convert_html_to_pdf(t, css)

    with tempfile.NamedTemporaryFile() as pdf_file:
        pdf_file.write(pdf)
        pdf_file.content_type = "application/pdf"
        pdf_file.size = len(pdf)

        doc = create_document(
            tenant=tenant_from_tenant_id(user.tenant_id),
            owner_type=DocOwnerTypeChoice.user,
            owner_id=user.uid,
            display_name=f"participant_report_{participant_name}.pdf",
            doc_type=DocTypeChoice.PARTICIPANT_REPORT,
            file=pdf_file
        )

    # save in local
    # with open(f"/tmp/participant_report_{participant_name}.pdf", "wb") as f:
    #     f.write(pdf)

    return get_document_url(doc)


def get_leaderboard_report(skills, tenant_id):
    participants_skill_scores = top_N_leadership_board(skills, 20, tenant_id=tenant_id)

    # TODO: Placeholder logic: To be removed soon
    while len(participants_skill_scores) < 20:
        participants_skill_scores.append({
            "name": "PLACEHOLDER",
            "skills_info": {
                    "skill_1": {
                        "score": 0,
                        "average_score": 0,
                        "question_count": 0,
                },
                "skill_2": {
                    "score": 0,
                    "average_score": 0,
                    "question_count": 0,
                },
            }
        })

    css = os.path.join(settings.TEMPLATES_DIR, 'pdf_generator',
                       'reports', 'static', 'styles_report.css')

    t = render_to_string(
        f"pdf_generator/reports/leaderboard_report.html", {'participants_skill_scores': participants_skill_scores})

    pdf = convert_html_to_pdf(t, css)

    with tempfile.NamedTemporaryFile() as pdf_file:
        pdf_file.write(pdf)
        pdf_file.content_type = "application/pdf"
        pdf_file.size = len(pdf)

        doc = create_document(
            tenant=tenant_from_tenant_id(tenant_id),
            owner_type=DocOwnerTypeChoice.system,
            owner_id=tenant_id,
            display_name=f"leaderboard_report_{tenant_id}.pdf",
            doc_type=DocTypeChoice.LEADERBOARD_REPORT,
            file=pdf_file
        )

    # # save to local file
    # with open(f"leaderboard_report_{tenant_id}.pdf", "wb") as f:
    #     f.write(pdf)

    return get_document_url(doc)

# function to get a graph of skills for a test attempt session
def get_test_attempt_session_skills_graph(test_attempt_session: TestAttemptSession) -> str:

    # get the skills_rating for the test_attempt_session
    skills_rating = test_attempt_session.skills_rating

    # skills_rating looks like: {'skill_name': skill_score}
    # skill_score is a float value between 0 and 5

    # get the skills from the skills_rating
    skills = list(skills_rating.keys())

    # get the skill_scores from the skills_rating
    skill_scores = list(skills_rating.values())

    # get the x axis values
    x = np.arange(len(skills))

    # bars should have space in between so that the skill names are visible so show skill names vertically
    plt.xticks(rotation=90)

    # get the y axis values
    y = skill_scores

    green_colors = ['mediumseagreen' for i in range(len(skills))]
    yellow_colors = ['gold' for i in range(len(skills))]
    red_colors = ['salmon' for i in range(len(skills))]

    green_height = [5 for i in range(len(skills))]
    yellow_height = [4 for i in range(len(skills))]
    red_height = [2 for i in range(len(skills))]

    # set color for all the bars as: sinlge bar should have 3 colors: red, yellow and green
    # red from 0-2, yellow from 2-4 and green from 4-5
    plt.bar(x, green_height, color=green_colors)
    plt.bar(x, yellow_height, color=yellow_colors)
    plt.bar(x, red_height, color=red_colors)

    # plot the line graph
    plt.plot(x, y, color='blue', marker='o')

    # add the title as "Skill distribution Matrix" large font size and bold
    plt.title('Skill distribution Matrix', fontsize=16, fontweight='bold')
    # add the x axis label
    plt.xlabel('Skills', fontweight='bold')
    # add the y axis label
    plt.ylabel('Skill Rating', fontweight='bold')

    plt.xticks(x, skills)

    # Y ticks should be from 'very bad', 'bad', 'average', 'good', 'very good'
    plt.yticks([1, 2, 3, 4, 5], ['very bad', 'bad', 'average', 'good', 'very good'])

    # tight layout
    plt.tight_layout()

    fig = plt.gcf()

    # convert the graph to png
    buf = io.BytesIO()

    fig.savefig(buf, format='png')

    buf.seek(0)

    # encode the png file to base64
    string = base64.b64encode(buf.read())

    # decode the base64 encoded png file to utf-8
    uri = urllib.parse.quote(string)

    plt.close()

    # return the decoded png file
    return uri
