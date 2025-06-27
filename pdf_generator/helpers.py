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
from tests.models import (Test, TestQuestion, TestAttemptSession, 
                          TestQuestionResponse, TestAttemptSessionStatusChoices,
                          Psychometric, PsychometricReportSection, PsychometricReportSubsection,TestReportConfig)
from users.db import get_user_display_name, get_user_by_id
from skills.models import CultureMapSkill, CustomRating
from test_bulk_upload.constants import updated_skills
from tests.choices import TestTypeChoices, QuestionForChoices, TestQuestionResponseEvaluationStatusChoices
from users.models import ClientUserInfo, UserAttribute, ReportConfig
import re
from skills.helpers import get_competency_prompt_or_output, get_competency_prompt_or_output_via_db, get_culture_skills
import logging
from tests.choices import ScenarioCaseChoices
from users.helpers import get_client_info_from_user_detail
from apis.accounts.serializers import clientUserInfoSerializer,TestReportConfigSerializer
from collections import defaultdict
from commons.notifications import send_error_notification


import matplotlib
matplotlib.use('Agg')

matplotlib.use('Agg')

options = {
    'page-size': 'Letter',
    'encoding': "UTF-8",
    'enable-local-file-access': "",
}

logger = logging.getLogger(__name__)

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


def format_psychometric_items(psychometric:Psychometric):
    # Use a set to keep track of unique sections for the dimension
    sections = {}

    # Loop through each PsychometricItem in the Psychometric set
    for item in psychometric.psy_items.filter(deleted=False):
        
        # Use item.section as the dimension
        section = sections.get(item.section)
        if not section:
            section= {
                "dimension": item.section,  
                "generate_note": [],
                "parameters": []
            }

        print(f'seciton: {sections, section}')
        parameters = item.parameters
        section["generate_note"].append({
                "parameter": " vs ".join(parameters.get('parameters')),
                "description": parameters.get('description'),
                'average_value': item.average_value
            })

        parameter_data = {
                "parameterName": parameters.get('parameterName'),
                "parameters": parameters.get('parameters'),
                "ranges": []
            }
        
        for range_key, range_value in item.range_values.items():
                range_entry = {
                    "range": range_key,
                    "strengths": range_value.get("strengths", []),
                    "areas_for_improvement": range_value.get("areas_for_improvement", []),
                    "overall": range_value.get("overall", "")
                }
                parameter_data["ranges"].append(range_entry)

        section['parameters'].append(parameter_data)

        sections[f"{item.section}"] = section

    return sections.values()


def find_highest_count_range(data):
    # Define ranges as tuples of (min, max)
    if not data:
        return []
    ranges = [(0, 3), (4, 7), (8, 10)]
    
    # Dictionary to store counts for each range
    range_counts = defaultdict(int)
    
    # Iterate through nested dictionary and count values in each range
    for category, subcategory_values in data.items():
        for subcategory, value in subcategory_values.items():
            for r in ranges:
                if r[0] <= value <= r[1]:
                    range_counts[r] += 1
                    break  # Stop after finding the correct range
    
    # Find the maximum count
    print(range_counts)
    max_count = max(range_counts.values())
    
    # Get all ranges with the maximum count
    most_common_ranges = [f"{r[0]}-{r[1]}" for r, count in range_counts.items() if count == max_count]
    
    return most_common_ranges

def get_report_from_test_attempt_session(test_attempt_session: TestAttemptSession, only_data=False):

    tenant = tenant_from_tenant_id(test_attempt_session.tenant_id)
    test_id = test_attempt_session.test_id
    test = Test.objects.get(uid=test_id)
    participant_id = test_attempt_session.participant_id
    participant_name = get_user_display_name(get_user_by_id(participant_id))
    test_started_at = test_attempt_session.started_at.strftime("%d %b %Y")

    user_att = UserAttribute.objects.get(deleted=False,user_id=test_attempt_session.participant_id)
    user_email = user_att.attributes.get('email')
    test_report_config = TestReportConfig.objects.filter(deleted=False, test=test).first()
    test_report_config= TestReportConfigSerializer(test_report_config).data if test_report_config else None

    
    
    # try:
    #     client = get_client_info_from_user_detail(tenant_id=test_attempt_session.tenant_id,
    #                                                 user_uid=test_attempt_session.participant_id
    #                                                 )
    #     client_name = client.client_name if client else None
    #     client_id = client.id if client else None
    # except:
    #     client_name = None
    #     client_id = None
    
    # log tnant id, test_id, test_attempt_session_id, participant_id, participant_name, test_started_at
    logger.info(f"tenant_id: {tenant.uid}, test_id: {test_id}, test_attempt_session_id: {test_attempt_session.uid}, participant_id: {participant_id}, participant_name: {participant_name}, test_started_at: {test_started_at}")
    
    try:
        client = get_client_info_from_user_detail(tenant_id=test_attempt_session.tenant_id,
                                                    user_uid=test_attempt_session.participant_id
                                                    )
        client_name = client.client_name if client else None
        client_id = client.id if client else None
        client_info = clientUserInfoSerializer(client).data
        
    except:
        client_name = None
        client_id = None
        client_info = None

    psychometric_data = None
    psychometric_info = None
    other_psychometric_infos = {}

    cul_skills = CultureMapSkill.objects.filter(deleted=False, tenant_id=test_attempt_session.tenant_id, test_type=test.scenario_case)
    if not cul_skills.exists():
        cul_skills = CultureMapSkill.objects.filter(deleted=False, tenant_id=test_attempt_session.tenant_id,test_type=ScenarioCaseChoices.others)

    # culture_map_evaluation_criteria = get_culture_skills(
    #                 "ocean_model" if test.scenario_case == ScenarioCaseChoices.psychometric else "workplace_skills", 
    #                 only_criteria=True 
    #                 )
    culture_map_evaluation_criteria = cul_skills.first().evaluation_criteria if cul_skills.exists() else {}

    if test_attempt_session.pshycometric_data:
        psychometric_data = test_attempt_session.pshycometric_data
        psy_sections = set(test.psychometric.psy_items.filter(deleted=False).values_list('section', flat=True))
        psy_sections = [i.strip() for i in psy_sections]
        print(psy_sections, psychometric_data)
        psychometric_data = {key: value for key, value in psychometric_data.items() if key in psy_sections}
        # psychometric_data['info'] = format_psychometric_items(test.psychometric)
        psychometric_info = format_psychometric_items(test.psychometric)
        other_psychometric_infos['max_ranges'] = find_highest_count_range(psychometric_data)
        other_psychometric_infos['psychometric_report_config'] = generate_section_json(test.psychometric_report_config, test)


    questions = TestQuestion.objects.filter(test_id=test_id)
    participant_responses = TestQuestionResponse.objects.filter(
        test_attempt_session_id=test_attempt_session.uid)

    feedback_summary = test_attempt_session.feedback_summary
    skill_summary = test_attempt_session.culture_and_skill_summary
    
    # log questions, participant_responses, feedback_summary, skill_summary
    logger.info(f"questions: {questions}, participant_responses: {participant_responses}, feedback_summary: {feedback_summary}, skill_summary: {skill_summary}")
    competency_report_data = {}
    
    response_relevance = True

    for response in participant_responses:
        if not response.relevance:
            response_relevance = False
            break

    logger.info(f"test_attempt_session.competency_data: {test_attempt_session.competency_data}")
    if test_attempt_session.competency_data:
        competency_data= test_attempt_session.competency_data
        competency_skills = get_competency_prompt_or_output_via_db(skills=list(competency_data.keys()))
        level_dict = {
                "0" : "Individual Contributor",
                "1" : "Individual Contributor",
                "2" : "Middle Manager",
                "3" : "Senior Leadership"}
        

        logger.info(f"competency_data: {competency_data}, {competency_skills}")
        for key,value in competency_data.items():
            data = ''
            for key_skill,value_skill in competency_skills.items():
                if key.strip().lower() == key_skill.lower().strip():
                    data = value_skill
                    break

            if data != "":
                try:
                    level_name = level_dict[str(value['level'])]

                    level_desc = data[level_name.strip().lower()].get('description',None)
                    if level_desc:
                        value['level_desc'] = level_desc

                    competency_data[key] = value
                except Exception as e:
                    logger.exception(f"failed to get competency : {e}")
        
        competency_report_data = competency_data


    logger.info(f"scenario_case: {test.scenario_case}, is_transcript_only: {test.is_transcript_only}, only_data: {only_data}")
    if (test.scenario_case in ["process_training", ScenarioCaseChoices.psychometric] or test.is_transcript_only) and only_data:
        if CustomRating.objects.filter(tenant_id=test_attempt_session.tenant_id).exists():
            custom_rating = CustomRating.objects.get(
                tenant_id=test_attempt_session.tenant_id).custom_rating
        else:
            custom_rating = {
                "1": "Starting Point",
                "2": "Learning Phase",
                "3": "Growth Stage",
                "4": "Proficient",
                "5": "High Achiever"
            }

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

                data = {
                    "question_text": question_text,
                    "response_text": response_text,                    
                }
                if feedback_text and len(feedback_text.split()) > 10:
                    data['feedback_text'] = feedback_text
                    
                if test.scenario_case == "process_training":
                    correct_answer = question.mcq_answer
                    response_rating = participant_response.response_rating
                    data['rating'] = response_rating
                    data["correct_answer"] = correct_answer

                # Check if participant response object has speech_metrics or not
                if question.question_insight:
                    data['question_insight'] = question.question_insight
                qa.append(data)

        logger.info(f"qa: {qa}, custom_rating: {custom_rating}, scenario_case: {test.scenario_case}")
        return {"client_name":client_name,"client_id": client_id,
                "client_info": client_info,'is_transcript_only': test.is_transcript_only,
                'test_type':test.test_type,'skills_explanation':test_attempt_session.skills_explanation,
                "ui_information": test.ui_information,"certificate_details":test.certificate_details,
                'scenario_case':test.scenario_case,'culture_skills_explanation':test_attempt_session.culture_skills_explanation,
                "title":test.title,'candidate_type': test.candidate_type, 
                'test_description': test.description, 'report_description': test.report_description,
                'qa': qa,'is_email_type': test.is_email_type ,'participant_name': participant_name, 
                'test_started_at': test_started_at, 'custom_rating': custom_rating,
                'competency_data':competency_report_data, 
                'skills_graph_data': {'skills_rating': test_attempt_session.skills_rating },
                'culture_graph_data':{'culture_skills_rating':test_attempt_session.culture_skills_rating }, 
                'speech_metrics_avg': None, "response_relevance": response_relevance,
                "feedback_summary":test_attempt_session.feedback_summary,
                "skill_summary":test_attempt_session.culture_and_skill_summary,
                'pshycometric_data': psychometric_data,'psychometric_info': psychometric_info, 
                "other_psychometric_infos": other_psychometric_infos,
                "category": test.category, "interaction_code": test.test_code,
                "personality_model_data": test_attempt_session.personality_model_data,
                "culture_map_evaluation_criteria": culture_map_evaluation_criteria,
       
                "skill_domain": test.skill_domain,
                "creator_prompt_type": test.creator_prompt_type,
                "test_report_config": test_report_config,
                'feedback_video_link': test_attempt_session.feedback_video_link if test_attempt_session.feedback_video_link else test.feedback_script_video_link,
                'feedback_video_script': test_attempt_session.feedback_video_script if test_attempt_session.feedback_video_script else test.feedback_video_script_template,
                'video_script': test.video_script,
                }



    logger.info(f"test_type: {test.test_type}")
    if test.is_free and only_data:
        # for feedbackSummaryReport ( which is a demo reprot for free trial users)
        if CustomRating.objects.filter(tenant_id=test_attempt_session.tenant_id).exists():
            custom_rating = CustomRating.objects.get(
                tenant_id=test_attempt_session.tenant_id).custom_rating
        else:
            custom_rating = {
                "1": "Starting Point",
                "2": "Learning Phase",
                "3": "Growth Stage",
                "4": "Proficient",
                "5": "High Achiever"
            }

        qa = []
        start_with_user = False
        bot_name = ''
        user_persona = ''
        chat_conversation = ''
        if test.test_type in [TestTypeChoices.orchestrated_conversation,TestTypeChoices.dynamic_discussion,TestTypeChoices.dynamic_discussion_thread]:
            user_persona = test.orchestrated_conversation_details.get(
                "test_user_persona")

            chat_conversation = test.orchestrated_conversation_details.get(
                "initial_messages")
            
            conversation_list = []

            for test_response in TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session.uid,
                                                                    evaluation_status=TestQuestionResponseEvaluationStatusChoices.success,
                                                                    deleted=0).order_by('id'):

                if test_response.responder_type == QuestionForChoices.user:
                    conv_text = f"{user_persona}: {test_response.response_text}"
                else:
                    conv_text = f"{test_response.responder_display_name}: {test_response.response_text}"

                # current_conversation = current_conversation + "\n" + conv_text
                conversation_list.append(conv_text)

           
            chat_conversation += conversation_list

        if test.test_type == TestTypeChoices.orchestrated_conversation:
            
            for message in chat_conversation:
                user_name, message = message.split(":", 1)
                is_bot = False

                if user_name.strip().lower() != user_persona.strip().lower():
                    is_bot = True

                qa.append(
                    {"user_name": user_name, "message": message, "is_bot": is_bot})
        
        elif test.test_type in [ TestTypeChoices.dynamic_discussion, TestTypeChoices.dynamic_discussion_thread ]:
            data_q = {}

            start_with_user_message = test.orchestrated_conversation_details.get('start_with_user')

            test_responses = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session.uid,
                                                                evaluation_status=TestQuestionResponseEvaluationStatusChoices.success,
                                                                deleted=0).order_by('id')
            count = 1
            for test_response in test_responses:
                if test_response.responder_type == QuestionForChoices.user:
                    if count == 1:
                        if start_with_user_message is not None:
                            data_q[f"question"] = test.description
                        else:
                            data_q[f"question"] = chat_conversation[0].split(":", 1)[1].strip('" \'')
                    data_q["response"] = test_response.response_text.strip('" \'')
                    data_q["feedback"] = re.sub(r'\([^)]*\)', '',  test_response.feedback_text or "Feedback couldn't be generated.")
                    qa.append(data_q)
                    count += 1
                    data_q = {}
                
                else:
                    data_q[f"question"] = test_response.response_text.split(':')[-1].strip('" \'')

            start_with_user = False if start_with_user_message is None else True

            if start_with_user:
                bot_name = test.orchestrated_conversation_details.get('initial_messages')[0].split(":", 1)[0].strip('" \'')


        else:
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
                feedback_text = participant_response.feedback_text or "Feedback couldn't be generated"

                # Check if participant response object has speech_metrics or not
                d = {
                    "question_text": question_text,
                    "response_text": response_text,
                    "feedback_text": feedback_text,
                }
                if question.question_insight:
                    d['question_insight'] = question.question_insight
                
                qa.append(d)

        logger.info(f"qa: {qa}, custom_rating: {custom_rating}, scenario_case: {test.scenario_case}")

        return {"client_name":client_name,"client_id": client_id,"client_info": client_info,
                'is_transcript_only': test.is_transcript_only,'test_type':test.test_type,
                "ui_information": test.ui_information,"certificate_details":test.certificate_details,
                'scenario_case':test.scenario_case,"title":test.title,'candidate_type': test.candidate_type, 
                'test_description': test.description,'report_description': test.report_description,
                 'qa': qa, 'participant_name': participant_name, 'test_started_at': test_started_at, 
                 'custom_rating': custom_rating, "feedback_summary":feedback_summary,
                 "skill_summary":skill_summary,'start_with_user':start_with_user,
                 'bot_name':bot_name,'competency_data':competency_report_data,
                 'pshycometric_data': psychometric_data, 'psychometric_info': psychometric_info, 
                 'other_psychometric_infos': other_psychometric_infos,
                 "category": test.category,
                 "response_relevance":response_relevance, 
                 "interaction_code": test.test_code,
                 "personality_model_data": test_attempt_session.personality_model_data,
                 "culture_map_evaluation_criteria": culture_map_evaluation_criteria,

                "skill_domain": test.skill_domain,
                "creator_prompt_type": test.creator_prompt_type,
                "test_report_config": test_report_config,
                'feedback_video_link': test_attempt_session.feedback_video_link if test_attempt_session.feedback_video_link else test.feedback_script_video_link,
                'feedback_video_script': test_attempt_session.feedback_video_script if test_attempt_session.feedback_video_script else test.feedback_video_script_template,
                'video_script': test.video_script,

                 }


    logger.info(f"test_type : {test.test_type}, only_data: {only_data}")
    if ( test.test_type == TestTypeChoices.mcq or test.test_type == TestTypeChoices.dynamic_mcq )  and only_data:

        if CustomRating.objects.filter(tenant_id=test_attempt_session.tenant_id).exists():
            custom_rating = CustomRating.objects.get(
                tenant_id=test_attempt_session.tenant_id).custom_rating
        else:
            custom_rating = {
                "1": "Starting Point",
                "2": "Learning Phase",
                "3": "Growth Stage",
                "4": "Proficient",
                "5": "High Achiever"
            }

        qa = []
        test_responses = TestQuestionResponse.objects.filter(test_attempt_session_id=test_attempt_session.uid,
                                                                evaluation_status=TestQuestionResponseEvaluationStatusChoices.success,
                                                                deleted=0).order_by('id')
        
        logger.info(f"test_responses: {test_responses}")
        for response in test_responses:
            mcq_options = questions.get(uid=response.question_id).mcq_options
            question_text = questions.get(uid=response.question_id).question
            mcq_skill = ''
            for key, value in mcq_options.items():
                if 'opt' in value and value['opt'] == question_text:
                    mcq_skill = value.get(f'Skill {key}', None)

            d = {
                "question": question_text if test.test_type == TestTypeChoices.mcq else response.metadata['question'],
                'response': response.response_text,
                'comment': response.feedback_text or "Feedback couldn't be generated",
                'skills': mcq_skill if test.test_type == TestTypeChoices.mcq else response.mcq_skill,
                'mcq_opitons': mcq_options
            }

            if questions.get(uid=response.question_id).question_insight:
                d['question_insight'] = questions.get(uid=response.question_id).question_insight
            qa.append(d)

        focus_area = test_attempt_session.skills_explanation['mcq_skills'] if test.test_type == TestTypeChoices.dynamic_mcq else []
        
        return {"client_name":client_name,"client_id": client_id,
                "client_info": client_info,'is_transcript_only': test.is_transcript_only,
                'test_type':test.test_type,'competency_data':competency_report_data,
                "ui_information":test.ui_information,"certificate_details":test.certificate_details,
                'scenario_case':test.scenario_case,"title":test.title,
                'candidate_type': test.candidate_type, 'test_description': test.description, 
                'report_description': test.report_description,
                'qa': qa, 'participant_name': participant_name, 'test_started_at': test_started_at, 
                'custom_rating': custom_rating,"mcq_summary": test_attempt_session.mcq_summary,
                'focus_area': focus_area,'pshycometric_data': psychometric_data, 
                'psychometric_info': psychometric_info, 
                'other_psychometric_infos': other_psychometric_infos,
                "category": test.category,
                "response_relevance": response_relevance, 
                "interaction_code": test.test_code,
                "personality_model_data": test_attempt_session.personality_model_data,
                "culture_map_evaluation_criteria": culture_map_evaluation_criteria,

                "skill_domain": test.skill_domain,
                "creator_prompt_type": test.creator_prompt_type,
                "test_report_config": test_report_config,
                'feedback_video_script': test_attempt_session.feedback_video_script if test_attempt_session.feedback_video_script else test.feedback_video_script_template,
                'video_script': test.video_script,
                'feedback_video_link': test_attempt_session.feedback_video_link if test_attempt_session.feedback_video_link else test.feedback_script_video_link



                }


    qa = []
    all_speech_metrics = []

    logger.info(f"questions: {questions}, participant_responses: {participant_responses}")
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
        feedback_text = participant_response.feedback_text or "Feedback couldn't be generated"

        # Check if participant response object has speech_metrics or not
        if participant_response.speech_metrics:
            speech_metrics = participant_response.speech_metrics

            # We only need ['energy_grade', 'fluency_grade', 'confidence_grade', 'pace'] from speech_metrics
            # speech_metrics = {k: v for k, v in speech_metrics.items(
            # ) if k in ['energy_grade', 'fluency_grade', 'confidence_grade', 'pace', 'sentiment_percentage', 'power_word_density',
            #            'filler_words_score', 'volume', 'silence_number']}
            # speech_metrics = {k: f"{((v/10)*100)}%" if k in [
            #     'power_word_density', 'filler_words_score'] else v for k, v in speech_metrics.items()}

            # We only need ['pace', 'filler_word_percentage', 'power_word_percentage', 'silence_number','fluency_percentage'] from speech_metrics
            speech_metrics = {k: v for k, v in speech_metrics.items(
            ) if k in ['fluency_percentage', 'pace','power_word_percentage','filler_word_percentage', 'silence_number']}

            # Convert the Keys to human readable format
            speech_metrics = {k.replace("_", " ").title(
            ): v for k, v in speech_metrics.items()}

            # Add the speech_metrics to the list of all_speech_metrics
            all_speech_metrics.append(speech_metrics)

            d = {
                "question_text": question_text,
                "response_text": response_text,
                "feedback_text": feedback_text,
                "speech_metrics": speech_metrics
            }

            if question.question_insight:
                d['question_insight'] = question.question_insight

            qa.append(d)

        else:
            d = {
                "question_text": question_text,
                "response_text": response_text,
                "feedback_text": feedback_text,
            }

            if question.question_insight:
                d['question_insight'] = question.question_insight
            qa.append(d)

    # Get the averaged speech metrics for the test attempt session
    speech_metrics_avg = {}
    logger.info(f"all_speech_metrics: {all_speech_metrics}")
    for metric in all_speech_metrics:
        for k, v in metric.items():
            if isinstance(v, str) and "%" in v:
                try:
                    v = float(v.replace("%", ""))
                except:
                    pass

            if k in speech_metrics_avg:
                speech_metrics_avg[k] += v
            else:
                speech_metrics_avg[k] = v

    if participant_responses[0].speech_metrics:
        for k, v in speech_metrics_avg.items():
            speech_metrics_avg[k] = v / len(participant_responses)

    if only_data:

        test_title = test.title
        skill_exp = test_attempt_session.skills_explanation
        if skill_exp:
            if len(test_attempt_session.skills_rating) == len(skill_exp):
                skill_exp = skill_exp
            else:
                skill_exp = None

        culture_skill_exp = test_attempt_session.culture_skills_explanation
        if culture_skill_exp:
            if len(test_attempt_session.culture_skills_rating) == len(culture_skill_exp):
                culture_skill_exp = culture_skill_exp
            else:
                culture_skill_exp = None



        candidate_type = test.candidate_type
        if not candidate_type:
            candidate_type = 'Manager'

        is_email_type = test.is_email_type
        test_description = test.description

        ted_talk_and_hbr = ''
        test_codes = []
        

        skills_graph_data = get_test_attempt_session_skills_graph(
            test_attempt_session, only_data=True)
        culture_graph_data = get_test_attempt_session_culture_skills_graph(
            test_attempt_session, only_data=True) if test_attempt_session.culture_skills_rating else None
        
        if test.is_checkin_type:
            ted_talk_and_hbr = test.tedtalk_and_hbr_case
            test_codes = get_test_code_lowest_skill(
                skills_graph_data["skills_rating"], test_attempt_session)

        return {"client_name":client_name,"client_id": client_id,"client_info": client_info,'is_transcript_only': test.is_transcript_only,'skills_explanation':skill_exp,
                'competency_data':competency_report_data,"ui_information": test.ui_information,
                "certificate_details":test.certificate_details,'test_type':test.test_type,
                'scenario_case':test.scenario_case,'culture_skills_explanation':culture_skill_exp,
                "title":test_title,'candidate_type': candidate_type, 'test_description': test_description,
                'is_email_type': is_email_type, 'tedtalk_and_hbr': ted_talk_and_hbr, 'test_code': test_codes,
                'qa': qa, 'participant_name': participant_name, 'test_started_at': test_started_at,
                'skills_graph_data': skills_graph_data, 'culture_graph_data': culture_graph_data,
                'speech_metrics_avg': speech_metrics_avg, "response_relevance": response_relevance,
                "feedback_summary":feedback_summary,"skill_summary":skill_summary,
                "is_pitch": test.scenario_case == ScenarioCaseChoices.pitch,
                "language_skills": test_attempt_session.language_skills,
                "is_recommended": test.is_recommended,
                'pshycometric_data': psychometric_data,
                'psychometric_info': psychometric_info,
                'other_psychometric_infos': other_psychometric_infos,
                'report_description': test.report_description,
                'category': test.category, "interaction_code": test.test_code,
                "personality_model_data": test_attempt_session.personality_model_data,
                "culture_map_evaluation_criteria": culture_map_evaluation_criteria,

                "skill_domain": test.skill_domain,
                "creator_prompt_type": test.creator_prompt_type,
                "test_report_config": test_report_config,
                'feedback_video_script': test_attempt_session.feedback_video_script if test_attempt_session.feedback_video_script else test.feedback_video_script_template,
                'video_script': test.video_script,
                'feedback_video_link': test_attempt_session.feedback_video_link if test_attempt_session.feedback_video_link else test.feedback_script_video_link
                }

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
    """
    Generates a participant report.

    Args:
        user (User): The user object representing the participant for whom the report is generated.
        only_data (bool, optional): A flag indicating whether to return only the data for the report or the complete PDF document. Defaults to False.

    Returns:
        dict or str: If only_data is True, a dictionary containing the participant's name, participant information, and custom rating. If only_data is False, the URL of the saved participant report PDF document.
    """
    participant_info = get_participant_info(user)

    participant_name = participant_info['name']

    css = os.path.join(settings.TEMPLATES_DIR, 'pdf_generator',
                       'reports', 'static', 'styles_report.css')

    if CustomRating.objects.filter(tenant_id=user.tenant_id, deleted=0).exists():
        custom_rating = CustomRating.objects.get(
            tenant_id=user.tenant_id, deleted=0).custom_rating
    else:
        custom_rating = {
            "1": "Starting Point",
            "2": "Learning Phase",
            "3": "Growth Stage",
            "4": "Proficient",
            "5": "High Achiever"
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

        test_attempt_sessions = TestAttemptSession.objects.filter(deleted=0, status = TestAttemptSessionStatusChoices.completed , participant_id = user.uid).exclude(finished_at=None).order_by('-finished_at')
        print(f"***** user_id : {user.uid}, 'sessions': {test_attempt_sessions.count()}")
        test_attempt_session_list = []
        cnt = 1

        for test_attempt_session in test_attempt_sessions:
            try:
                test = Test.objects.get(uid=test_attempt_session.test_id)
                print(test.is_self_created)
            except:
                logger.exception(f"Test not found for test_attempt_session_test_id: {test_attempt_session.test_id}")
                continue
            if not test_attempt_session.report_url:
                continue

            try:
                session_info = {
                    "slno" : cnt,
                    "title": test.title,
                    "link" : test_attempt_session.report_url,
                    "date" : test_attempt_session.created.date()
                }
                test_attempt_session_list.append(session_info)
                cnt += 1

            except Exception as e:
                print(f"Exception while fetching test attempt session info: {e}")
                pass

        participant_info['test_attempt_session_list'] = test_attempt_session_list
        participant_info['total_tests_attempted'] = len(test_attempt_session_list)

        logger.info(f"participant_info : {participant_info}")
        

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
            "1": "Starting Point",
            "2": "Learning Phase",
            "3": "Growth Stage",
            "4": "Proficient",
            "5": "High Achiever"
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
    skills_rating = {key.strip('"\'' ): value for key, value in skills_rating.items()}  # to strip extra qoutes from key

    # Y ticks should be from 'very bad', 'bad', 'average', 'good', 'very good'
    # Super Manager , Good manager,  Average Manager , Beginning Manager , Non Manager.
    if CustomRating.objects.filter(tenant_id=test_attempt_session.tenant_id).exists():
        custom_rating = CustomRating.objects.get(
            tenant_id=test_attempt_session.tenant_id).custom_rating
    else:
        custom_rating = {
            "1": "Starting Point",
            "2": "Learning Phase",
            "3": "Growth Stage",
            "4": "Proficient",
            "5": "High Achiever"
        }

    if only_data:
        # updated_skills_ratings = {}
        # existing_skills = []
        # for skill, values in skills_rating.items():
        #     for old , new in updated_skills.items():
        #         if skill.strip().capitalize() == old.strip().capitalize():
        #             updated_skills_ratings[new.strip()] = values
        #             existing_skills.append(skill)
        #         else:
        #             updated_skills_ratings[skill] = values

        # for i  in existing_skills:
        #     del updated_skills_ratings[i]

        # updated_skills_ratings = update_skill_name(skills_rating)


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


def get_test_code_lowest_skill(skills_rating, test_attempt_session):

    lowest_skill = min(skills_rating, key=skills_rating.get)
    lowest_score = skills_rating[lowest_skill]
    test_codes = []
    if lowest_score < 5:
        test_query = Test.objects.filter(tenant_id=test_attempt_session.tenant_id,
                                         skills_to_evaluate__icontains=lowest_skill, is_learner_path=1, is_checkin_type=0)

        test_query = test_query.exclude(uid=test_attempt_session.test_id)

        if test_query.count() > 0:
            for test_ in test_query:
                test_codes.append(test_.test_code)

        if len(test_codes) > 2:
            test_codes = test_codes[:2]

    return test_codes

def update_skill_name(skills_rating):
    if not skills_rating:
        return None

    updated_skills_ratings = {}
    for skill, values in skills_rating.items():
        
        updated_skill = skill.strip().capitalize()
        for old,new in updated_skills.items():
            if skill.strip().capitalize() == old.strip().capitalize():
                updated_skill = new.strip().capitalize()
                break
        
                
        updated_skills_ratings[updated_skill.strip()] = values

    return updated_skills_ratings


def generate_section_json(section:PsychometricReportSection, test:Test):
    try:

        # Helper function to recursively build subsections
        def build_subsection_hierarchy(subsections, parent=None):
            hierarchy = []
            for subsection in subsections.filter(parent=parent):
                subsection_data = {
                            "value": subsection.value,
                            "subsection": build_subsection_hierarchy(subsections, subsection),
                            "footer": subsection.footer # Assuming no footer for subsections
                        }
                if subsection.range_value:
                    subsection_data["range"] = subsection.range_value
                if 'test_description if you want' in subsection.value:
                    subsection_data['value'] = test.report_description

                hierarchy.append({subsection.name :subsection_data})
            return hierarchy

        # Prepare the section's data in the desired format
        subsections = PsychometricReportSubsection.objects.filter(section=section)
        section_data = {
            section.name: {
                "value": section.value if section.value else None,
                "subsection": build_subsection_hierarchy(subsections),
                "footer": section.footer if section.footer else None
            }
        }

        # Return the JSON response
        logger.info(f'psycho report json: {section_data}')
        section_result = section_data[section.name]['subsection']
        result = {}
        for d in section_result:
            result.update(d)

        return result

    except Exception as e:
        logger.exception(f"Failed to generate json for psy report config: {e}")
        send_error_notification('generate_section_json', f"Failed to generate json for psy report config: {e}", {'psychometric_id': section.uid})
        return None
