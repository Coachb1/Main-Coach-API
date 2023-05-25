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
from users.models import User


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
    participant_name = User.objects.get(uid=participant_id).name
    test_started_at = test_attempt_session.started_at

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

    t = render_to_string(
        f"pdf_generator/reports/report.html",
        {'qa': qa, 'participant_name': participant_name, 'test_started_at': test_started_at})

    css = os.path.join(settings.TEMPLATES_DIR, 'pdf_generator',
                       'reports', 'static', 'styles_report.css')

    pdf = convert_html_to_pdf(t, css)

    with tempfile.NamedTemporaryFile() as pdf_file:
        pdf_file.write(pdf)
        pdf_file.content_type = "application/pdf"
        pdf_file.size = len(pdf)

        doc = create_document(
            tenant=tenant,
            owner_type=DocOwnerTypeChoice.system,
            owner_id=tenant.uid,
            display_name=f"report_{test_attempt_session.uid}.pdf",
            doc_type=DocTypeChoice.REPORT,
            file=pdf_file
        )

    TestAttemptSession.objects.filter(
        uid=test_attempt_session.uid
    ).update(
        report_doc_id=doc.uid
    )

    return get_document_url(doc)


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

    return get_document_url(doc)

def get_leaderboard_report(skills, tenant_id):

    participants_skill_scores = top_N_leadership_board(skills, 10, tenant_id=tenant_id)

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

    return get_document_url(doc)