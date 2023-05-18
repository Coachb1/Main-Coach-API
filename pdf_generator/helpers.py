import os
import tempfile

import pdfkit
from django.conf import settings
from django.template.loader import render_to_string

from documents.choices import DocOwnerTypeChoice, DocTypeChoice
from documents.helpers import create_document, get_document_url_from_doc_id
from tenants.helpers import tenant_from_tenant_id
from tests.db_helpers import get_test_questions_from_test
from tests.models import Test, TestQuestion

options = {
    'page-size': 'Letter',
    'encoding': "UTF-8",
    'enable-local-file-access': "",
}


def convert_html_to_pdf(html_str, css_file):
    return pdfkit.from_string(html_str, False, options, css=css_file)


def get_flash_cards_from_test(test: Test):
    tenant = tenant_from_tenant_id(test.tenant_id)
    test_question_list = get_test_questions_from_test(test)

    css_file = os.path.join(settings.TEMPLATES_DIR,
                            'pdf_generator',
                            'flash_cards',
                            'static',
                            'card',
                            'styles_pdf.css')

    test_question_flash_card_doc_id_map = {}
    flash_cards = []
    for question in test_question_list:
        if question.flash_card_doc_id:
            test_question_flash_card_doc_id_map[question.uid] = question.flash_card_doc_id
            continue

        flash_card_html = render_to_string(
            "pdf_generator/flash_cards/flash_card_1.html", {"heading": test.title,
                                                            "text": question.key_learning_point}
        )

        flash_cards.append((question.uid, convert_html_to_pdf(flash_card_html, css_file)))

    saved_flash_cards = []
    for flash_card in flash_cards:
        question_uid, pdf_data = flash_card
        with tempfile.NamedTemporaryFile() as pdf_file:
            pdf_file.write(pdf_data)
            pdf_file.content_type = "application/pdf"
            pdf_file.size = len(pdf_data)

            doc = create_document(
                tenant=tenant,
                owner_type=DocOwnerTypeChoice.system,
                owner_id=tenant.uid,
                display_name=f"flash_card_{question_uid}",
                doc_type=DocTypeChoice.FLASH_CARD,
                file=pdf_file
            )

        saved_flash_cards.append((question_uid, doc.uid))

    for saved_flash_card in saved_flash_cards:
        question_uid, doc_uid = saved_flash_card

        test_question_flash_card_doc_id_map[question_uid] = doc_uid

        TestQuestion.objects.filter(
            uid=question_uid
        ).update(
            flash_card_doc_id=doc_uid
        )

    flash_card_urls = []
    for doc_uid in test_question_flash_card_doc_id_map.values():
        flash_card_urls.append(
            get_document_url_from_doc_id(doc_uid)
        )

    return flash_card_urls
