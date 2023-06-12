import base64
import urllib
import io
import numpy as np
import matplotlib.pyplot as plt
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
from skills.models import CustomRating

import matplotlib
matplotlib.use('Agg')

matplotlib.use('Agg')

options = {
    'page-size': 'Letter',
    'encoding': "UTF-8",
    'enable-local-file-access': "",
}


def convert_html_to_pdf(html_str, css_file):
    return pdfkit.from_string(html_str, False, options, css=css_file)


def get_flash_cards_from_test(test: Test, only_data=False):
    if test.flash_card_doc_id and not only_data:
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

    data = []

    if only_data:
        for question in test_question_list:
            data.append(
                {"heading": test.title, "text": question.key_learning_point})

        return data

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


def get_report_from_test_attempt_session(test_attempt_session: TestAttemptSession, only_data=False):
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
    all_speech_metrics = []

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

        # Check if participant response object has speech_metrics or not
        if participant_response.speech_metrics:
            speech_metrics = participant_response.speech_metrics

            # We only need ['energy_grade', 'fluency_grade', 'confidence_grade', 'pace'] from speech_metrics
            speech_metrics = {k: v for k, v in speech_metrics.items(
            ) if k in ['energy_grade', 'fluency_grade', 'confidence_grade', 'pace']}

            # Convert the Keys to human readable format
            speech_metrics = {k.replace("_", " ").title(
            ): v for k, v in speech_metrics.items()}

            # Add the speech_metrics to the list of all_speech_metrics
            all_speech_metrics.append(speech_metrics)

            qa.append({
                "question_text": question_text,
                "response_text": response_text,
                "feedback_text": feedback_text,
                "speech_metrics": speech_metrics
            })

        else:
            qa.append({
                "question_text": question_text,
                "response_text": response_text,
                "feedback_text": feedback_text,
            })

    # Get the averaged speech metrics for the test attempt session
    speech_metrics_avg = {}
    for metric in all_speech_metrics:
        for k, v in metric.items():
            if k in speech_metrics_avg:
                speech_metrics_avg[k] += v
            else:
                speech_metrics_avg[k] = v

    if participant_responses[0].speech_metrics:
        for k, v in speech_metrics_avg.items():
            speech_metrics_avg[k] = v / len(participant_responses)

    if only_data:
        skills_graph_data = get_test_attempt_session_skills_graph(
            test_attempt_session, only_data=True)
        culture_graph_data = get_test_attempt_session_culture_skills_graph(
            test_attempt_session, only_data=True)
        return {'qa': qa, 'participant_name': participant_name, 'test_started_at': test_started_at, 'skills_graph_data': skills_graph_data, 'culture_graph_data': culture_graph_data, 'speech_metrics_avg': speech_metrics_avg}

    uri = get_test_attempt_session_skills_graph(test_attempt_session)
    culture_uri = get_test_attempt_session_culture_skills_graph(
        test_attempt_session)

    t = render_to_string(
        f"pdf_generator/reports/report.html",
        {
            'qa': qa,
            'participant_name': participant_name,
            'test_started_at': test_started_at,
            'uri': uri,
            'culture_uri': culture_uri,
            'speech_metrics_avg': speech_metrics_avg,
        })

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

    # # save to local file
    # with open(f"report_{test_attempt_session.uid}.pdf", "wb") as f:
    #     f.write(pdf)

    return get_document_url(doc)


def get_participant_report(user, only_data=False):
    participant_info = get_participant_info(user)

    participant_name = participant_info['name']

    css = os.path.join(settings.TEMPLATES_DIR, 'pdf_generator',
                       'reports', 'static', 'styles_report.css')

    if CustomRating.objects.filter(tenant_id=user.tenant_id, deleted=0).exists():
        custom_rating = CustomRating.objects.get(
            tenant_id=user.tenant_id, deleted=0).custom_rating
    else:
        custom_rating = {
            "1": "Non Manager",
            "2": "Beginner Manager",
            "3": "Average Manager",
            "4": "Good Manager",
            "5": "Super Manager"
        }

    if only_data:
        skills_info = []
        for skill in participant_info['skills_info']:
            skills_info.append(
                {"skill": skill,
                 "score": participant_info['skills_info'][skill]['score'],
                 "average_score": participant_info['skills_info'][skill]['average_score'],
                 "question_count": participant_info['skills_info'][skill]['question_count']
                 })

        participant_info['skills_info'] = skills_info

        return {'participant_name': participant_name, 'participant_info': participant_info, 'custom_rating': custom_rating}

    t = render_to_string(
        f"pdf_generator/reports/participant_report.html", {'participant_name': participant_name,
                                                           'participant_info': participant_info,
                                                           'custom_rating': custom_rating})

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
    # with open(f"./participant_report_{participant_name}.pdf", "wb") as f:
    #     f.write(pdf)

    return get_document_url(doc)


def get_leaderboard_report(skills, tenant_id, only_data=False):
    participants_skill_scores = top_N_leadership_board(
        skills, 20, tenant_id=tenant_id)

    if CustomRating.objects.filter(tenant_id=tenant_id, deleted=0).exists():
        custom_rating_object = CustomRating.objects.get(
            tenant_id=tenant_id, deleted=0)
        custom_rating = custom_rating_object.custom_rating

    else:
        custom_rating = {
            "1": "Non Manager",
            "2": "Beginner Manager",
            "3": "Average Manager",
            "4": "Good Manager",
            "5": "Super Manager"
        }

    # TODO: Placeholder logic: To be removed soon
    # participants_skill_scores = []
    # while len(participants_skill_scores) < 19:
    #     participants_skill_scores.append({
    #         "name": "PLACEHOLDER",
    #         "skills_info": {
    #                 "skill_1": {
    #                     "score": 0,
    #                     "average_score": 0,
    #                     "question_count": 0,
    #             },
    #             "skill_2": {
    #                 "score": 0,
    #                 "average_score": 0,
    #                 "question_count": 0,
    #             },
    #         }
    #     })

    if only_data:

        # for every participant in participants_skill_scores, get the skills_info and convert it into list of skills
        for participant in participants_skill_scores:
            skills_info = participant['skills_info']
            skills_info_list = []
            for skill in skills_info:
                skills_info_list.append(
                    {"skill": skill,
                     "score": skills_info[skill]['score'],
                     "average_score": skills_info[skill]['average_score'],
                     "question_count": skills_info[skill]['question_count']
                     })

            participant['skills_info'] = skills_info_list

        return {'participants_skill_scores': participants_skill_scores, 'custom_rating': custom_rating}

    css = os.path.join(settings.TEMPLATES_DIR, 'pdf_generator',
                       'reports', 'static', 'styles_report.css')

    t = render_to_string(
        f"pdf_generator/reports/leaderboard_report.html", {'participants_skill_scores': participants_skill_scores, 'custom_rating': custom_rating})

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


def get_test_attempt_session_skills_graph(test_attempt_session: TestAttemptSession, only_data=False) -> str:

    # get the skills_rating for the test_attempt_session
    skills_rating = test_attempt_session.skills_rating

    # Y ticks should be from 'very bad', 'bad', 'average', 'good', 'very good'
    # Super Manager , Good manager,  Average Manager , Beginning Manager , Non Manager.
    if CustomRating.objects.filter(tenant_id=test_attempt_session.tenant_id).exists():
        custom_rating = CustomRating.objects.get(
            tenant_id=test_attempt_session.tenant_id).custom_rating
    else:
        custom_rating = {
            "1": "Non Manager",
            "2": "Beginner Manager",
            "3": "Average Manager",
            "4": "Good Manager",
            "5": "Super Manager"
        }

    if only_data:
        return {'skills_rating': skills_rating, 'custom_rating': custom_rating}

    # skills_rating looks like: {'skill_name': skill_score}
    # skill_score is a float value between 0 and 5

    # get the skills from the skills_rating
    skills = list(skills_rating.keys())

    # get the skill_scores from the skills_rating
    skill_scores = list(skills_rating.values())

    # shorten the skill names
    skills = [f"{skill[:6]}..." for skill in skills]

    # get the x axis values
    x = np.arange(len(skills))

    # bars should have space in between so that the skill names are visible so show skill names vertically
    plt.xticks(rotation=45, ha='right')

    # get the y axis values
    y = skill_scores

    green_colors = ['gainsboro' for i in range(len(skills))]
    yellow_colors = ['gainsboro' for i in range(len(skills))]
    red_colors = ['gainsboro' for i in range(len(skills))]

    green_height = [5 for i in range(len(skills))]
    yellow_height = [4 for i in range(len(skills))]
    red_height = [2 for i in range(len(skills))]

    # set color for all the bars as: sinlge bar should have 3 colors: red, yellow and green
    # red from 0-2, yellow from 2-4 and green from 4-5

    plt.bar(x, green_height, color=green_colors, width=0.5)
    plt.bar(x, yellow_height, color=yellow_colors, width=0.5)
    plt.bar(x, red_height, color=red_colors, width=0.5)

    # plot the line graph
    plt.plot(x, y, color='blue', marker='o')

    # add the title as "Skill distribution Matrix" large font size and bold
    plt.title('Skill distribution Matrix', fontsize=16, fontweight='bold')
    # Add space between title and graph
    plt.subplots_adjust(top=2)
    # add the x axis label
    plt.xlabel('Skills', fontweight='bold')
    # add the y axis label
    plt.ylabel('Skill Rating', fontweight='bold')

    plt.xticks(x, skills)

    # get sorted values of custom_rating dictionary by key
    custom_rating = {k: v for k, v in sorted(
        custom_rating.items(), key=lambda item: item[0])}

    # get the y ticks
    skills_y_ticks = list(custom_rating.values())

    plt.yticks([1, 2, 3, 4, 5], skills_y_ticks)

    # tight layout
    plt.tight_layout()

    plt.gca().spines['right'].set_visible(False)
    plt.gca().spines['top'].set_visible(False)

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


def get_test_attempt_session_culture_skills_graph(test_attempt_session: TestAttemptSession, only_data=False):

    culture_skills_rating = test_attempt_session.culture_skills_rating

    # skills_rating looks like: {'skill_name': skill_score}
    # skill_score is a float value between 0 and 5

    # get the skills from the skills_rating
    culture_skills = list(culture_skills_rating.keys())

    culture_label_left = []
    culture_label_right = []

    convert_to_label = {'hierarchy': ('Leading\n(egaliterian)', '(hierarchial)'),
                        'consensual': ('Deciding\n(consensual)', '(top down)'),
                        'indirect negative feedback': ('Evaluating\n(direct \nnegative feedback)', '(indirect \nnegative feedback)'),
                        'relationship based': ('Trusting\n(task-based)', '(relationship-based)'),
                        'high context communication': ('Communicating\n(low-context)', '(high-context)'),
                        'Persuasion': ('Disagreeing\n(confrontational)', '(avoids\nconfrontation)'),
                        'argumentative': ('Influence\n(compliant)', '(argumentative)')}

    if only_data:
        return {'culture_skills_rating': culture_skills_rating, 'convert_to_label': convert_to_label}

    for skill in culture_skills:
        if skill == 'consensual':
            culture_skills_rating[skill] = 5 - culture_skills_rating[skill] + 1

        elif skill == 'Persuasion':
            culture_skills_rating[skill] = 5 - culture_skills_rating[skill] + 1

        culture_label_left.append(convert_to_label[skill][0])
        culture_label_right.append(f"- {convert_to_label[skill][1]}")

    # get the skill_scores from the skills_rating
    culture_skill_scores = list(culture_skills_rating.values())

    y = [5 for a in culture_skill_scores]
    widths = [0.5 for a in culture_skill_scores]

    # Create the horizontal bars
    plt.barh(culture_label_left, y, color='gainsboro', height=widths)

    plt.suptitle('Culture Map', fontsize=16, fontweight='bold')
    plt.title('7 Dimensions of behavioral attributes')

    # Add labels to the ends of the horizontal bars
    for i in range(len(culture_label_left)):
        # plt.text(-1.2, i, culture_label_left[i])
        plt.text(5, i, culture_label_right[i], va='center')

    plt.plot(culture_skill_scores, range(len(culture_label_left)),
             '-o', markersize=20, color='orange')
    # plt.axis('off')
    plt.gca().spines['right'].set_visible(False)
    plt.gca().spines['top'].set_visible(False)
    plt.gca().spines['left'].set_visible(False)
    plt.gca().spines['bottom'].set_visible(False)

    # remove x axis labels
    plt.xticks([])

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
