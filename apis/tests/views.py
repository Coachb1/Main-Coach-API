from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apis.tests.filtersets import TestFilterSet
from apis.tests.serializers import CreateTestSerializer
from apis.tests.serializers import TestDisplaySerializer
from apis.tests.serializers import LearnerPathSerializer
from apis.tests.serializers import TestFromObjectiveSerializer
from clients.permissions import IsAuthenticatedClient
from commons.viewset import ApiViewSet
from mindmap.helpers import get_mindmap_url_from_test
from pdf_generator.helpers import get_flash_cards_from_test
from tests.helpers import create_test, get_test_report, generate_test_from_objective_anthropic , admin_panel_updates, update_prompt_user_attributes
from tests.models import Test, TestQuestionResponse, TestAttemptSession, TestQuestion
from users.permissions import IsAuthenticatedUser
from learner_path.helpers import get_learner_path
from email_sender.helpers import send_learner_path_email
from users.models import User, UserAttribute
from utilities.models import SpecialTypeTests
from django.db.models import Q
from skills.constants import skills as all_skills_present
from tests.choices import TestTypeChoices, ScenarioCaseChoices

from commons.anthropic import anthropic_completion
from commons.openai_gpt import gpt3_completion
from commons.google_apis import text_bison_compeletion
import time
import base64
from tests.helpers import create_scenario_from_site_context, fetch_test_codes_by_site_context

import logging

logger = logging.getLogger(__name__)


class TestViewSet(ApiViewSet,
                  mixins.ListModelMixin,
                  mixins.RetrieveModelMixin):
    queryset = Test.objects.filter(deleted=0)
    serializer_class = TestDisplaySerializer
    permission_classes = (IsAuthenticatedClient, IsAuthenticatedUser)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = TestFilterSet
    ordering_fields = ("id",)
    lookup_field = "uid"

    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=self.request.tenant.uid)

    def create(self, request, *args, **kwargs):
        serializer = CreateTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data["creator_id"] is None:
            serializer.validated_data["creator_id"] = request.auth_user.uid

        test, test_questions = create_test(
            tenant=request.tenant,
            **serializer.validated_data
        )

        return Response(self.serializer_class(instance=test).data, status=status.HTTP_201_CREATED)

    @action(methods=["GET"], detail=True, url_path="flash-cards")
    def get_test_flash_cards(self, request, *args, **kwargs):
        test = self.get_object()
        flash_card_urls = get_flash_cards_from_test(test)
        return Response({"flash_cards": flash_card_urls}, status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=True, url_path="mindmap")
    def get_test_mindmap(self, request, *args, **kwargs):
        test = self.get_object()
        url = get_mindmap_url_from_test(test)
        return Response({"url": url}, status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=True, url_path="report")
    def get_test_report_pdf_view(self, request, *args, **kwargs):
        test = self.get_object()

        report_url = get_test_report(test)

        return Response({"report_url": report_url})

    @action(methods=["GET"], detail=True, url_path="flash-cards-data")
    def get_test_flash_cards_data(self, request, *args, **kwargs):
        test = self.get_object()
        data = get_flash_cards_from_test(test, only_data=True)
        return Response({"data": data}, status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=True, url_path="mindmap-data")
    def get_test_mindmap_data(self, request, *args, **kwargs):
        test = self.get_object()
        data = get_mindmap_url_from_test(test, only_data=True)
        return Response({"data": data}, status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=True, url_path="report-data")
    def get_test_report_frontend(self, request, *args, **kwargs):
        test = self.get_object()

        data = get_test_report(test, only_data=True)
        tenant = request.tenant
        data['logo'] = tenant.logo

        return Response({"data": data, "status": "completed"})

    @action(methods=["GET"], detail=False, url_path="learner-path")
    def get_learner_path(self, request, *args, **kwargs):
        serializer_class = LearnerPathSerializer(data=request.data)
        serializer_class.is_valid(raise_exception=True)

        tenant = request.tenant

        objective = serializer_class.validated_data["objective"]
        candidate_type = serializer_class.validated_data["candidate_type"]
        candidate_id = serializer_class.validated_data["candidate_id"]

        user = User.objects.get(uid=candidate_id, tenant_id=tenant.uid)

        tenant_aware_query_set = self.queryset.filter(tenant_id=tenant.uid)

        tests = get_learner_path(
            tenant_aware_query_set, objective, candidate_type)

        send_learner_path_email(tests, user)

        return Response(self.serializer_class(instance=tests, many=True).data, status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=False, url_path="test-from-objective")
    def generate_test_from_objective(self, request, *args, **kwargs):
        serializer_class = TestFromObjectiveSerializer(data=request.data)
        serializer_class.is_valid(raise_exception=True)

        tenant = request.tenant

        objective = serializer_class.validated_data["objective"]

        potential_test = generate_test_from_objective_anthropic(objective)

        return Response(potential_test, status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=False, url_path="get-special-category")
    def get_tenant_special_case_test_category(self, request, *args, **kwargs):
        tenant_id=self.request.tenant.uid
        case_type = request.query_params.get("case_type")

        case_tests = SpecialTypeTests.objects.filter(tenant_id=tenant_id,case_type=case_type).order_by('title')
        data = set()
        for case_test in case_tests:
            data.add(case_test.category)

        return Response({"data": list(data), 'status': "ok"},status=status.HTTP_200_OK)
    
    @action(methods=["GET"], detail=False, url_path="get-special-case-tests")
    def get_tenant_special_case_test(self, request, *args, **kwargs):
        tenant_id=self.request.tenant.uid
        case_category = request.query_params.get("case_category")

        case_tests = SpecialTypeTests.objects.filter(tenant_id=tenant_id,category=case_category).order_by('title')
        data = []
        for case_test in case_tests:
            data.append({
                "title": case_test.title,
                "code" : case_test.test_code
            })

        return Response({"data": data, 'status': "ok"},status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=False, url_path="get-test-previlage-user")
    def get_test_previlage(self, request, *args, **kwargs):
        user_id = request.query_params.get("user_id")

        user_att = UserAttribute.objects.get(user_id = user_id)

        active = False
        test_list = []
        if user_att:
            if user_att.test_previlage :
                active = True
                test_list = [ test_code.strip() for test_code in user_att.test_previlage.split(',')]

        return Response({"data": test_list,'active': active, 'status': "ok"},status=status.HTTP_200_OK)



    @action(methods=["GET"], detail=False, url_path="get-selection-options")
    def get_selection_options(self, request, *args, **kwargs):
        tenant_id = self.request.tenant.uid
        all_skills_qs = Test.objects.filter(tenant_id=tenant_id,deleted=0).values_list('skills_to_evaluate')
        all_skills = set()
        up_skill_names = [skill.strip().capitalize() for skill in [s['name'] for s in all_skills_present]]

        for skills in all_skills_qs:
            if skills[0]:
                skill_name_list = [sk.strip().capitalize() for sk in skills[0].split(',') if sk.strip().capitalize() in up_skill_names ]
                all_skills.update(skill_name_list)
                
        all_goals_qs = Test.objects.filter(tenant_id=tenant_id,deleted=0).values_list('goals')
        all_goals = set()
        for goals in all_goals_qs:
            if goals[0]:
                all_goals.update(goals[0].split(','))
        
        all_roles_qs = Test.objects.filter(tenant_id=tenant_id,deleted=0).values_list('candidate_type')
        all_roles = set()
        for roles in all_roles_qs:
            if roles[0]:
                all_roles.add(roles[0])
        
        all_courses_qs = Test.objects.filter(tenant_id=tenant_id,deleted=0).values_list('course')
        all_courses = set()
        for courses in all_courses_qs:
            if courses[0]:
                all_courses.add(courses[0])
        
        all_industry_qs = Test.objects.filter(tenant_id=tenant_id,deleted=0).values_list('industry')
        all_industry = set()
        for industry in all_industry_qs:
            if industry[0]:
                all_industry.add(industry[0])
        
        all_exp_level_qs = Test.objects.filter(tenant_id=tenant_id,deleted=0).values_list('exp_level')
        all_exp_level = set()
        for exp_level in all_exp_level_qs:
            if exp_level[0]:
                all_exp_level.add(exp_level[0])

        all_format_qs = Test.objects.filter(tenant_id=tenant_id,deleted=0).values_list('test_type')
        all_format = set()
        for format in all_format_qs:    
            if format[0]:
                all_format.add(format[0])


        data = {
            "skills": list(all_skills)[:100],
            "goals": list(all_goals),
            "role": list(all_roles),
            "course": list(all_courses),
            "industry": list(all_industry),
            "exp_level": list(all_exp_level),
            # "format": list(all_format)
        }

        return Response({"data": data, 'status': "ok"},status=status.HTTP_200_OK)

    
    @action(methods=["GET"], detail=False, url_path="get-tests-by-choice")
    def get_tests_by_choice(self, request, *args, **kwargs):
        # return Response("Ok")
        tenant_id = self.request.tenant.uid
        skill = request.query_params.get("skill")
        goal = request.query_params.get("goal")
        role = request.query_params.get("role")
        course = request.query_params.get("course")
        industry = request.query_params.get("industry")
        exp_level = request.query_params.get("exp_level")
        tformat = request.query_params.get("tformat")
        page = request.query_params.get("page")

        logger.info(f"***********************Request received for get_tests_by_choice***********************{request.query_params}")
        logger.info({"skill": skill, "goal": goal, "role": role, "course": course, "industry": industry, "exp_level": exp_level, "format": tformat})

        try:
            tests = Test.objects.filter(tenant_id=tenant_id,deleted=0).order_by('title')

            if course is not None and course != '':
                tests = tests.filter(course=course)
            else:
                # tests = tests.filter(skills_to_evaluate__icontains=skill,goals__icontains=goal, candidate_type__icontains=role, industry__icontains=industry, exp_level__icontains=exp_level, test_type__icontains=format)
                if skill is not None and skill != '':
                    tests = tests.filter(skills_to_evaluate__icontains=skill)
                if goal is not None and goal != '':
                    tests = tests.filter(goals__icontains=goal)
                if role is not None and role != '':
                    tests = tests.filter(candidate_type__icontains=role)
                if industry is not None and industry != '':
                    tests = tests.filter(industry__icontains=industry)
                if exp_level is not None and exp_level != '':
                    tests = tests.filter(exp_level__icontains=exp_level)
                if tformat is not None and tformat != '':
                    tests = tests.filter(test_type__icontains=tformat)

                if tests.count() == 0:
                    query = Q()

                    # Check and add conditions for each field if it is not None
                    if skill is not None:
                        query |= Q(skills_to_evaluate__icontains=skill)
                    if tformat is not None:
                        query |= Q(test_type__icontains=tformat)
                    if goal is not None:
                        query |= Q(goals__icontains=goal)
                    if industry is not None:
                        query |= Q(industry__icontains=industry)
                    if exp_level is not None:
                        query |= Q(exp_level__icontains=exp_level)
                    if role is not None:
                        query |= Q(candidate_type__icontains=role)

                    # Apply the filter with the constructed query
                    tests = tests.filter(query)
            
            
            

            data = []
            cnt = 1
            for test in tests:
                data.append({
                    "title": test.title,
                    "code" : test.test_code,
                    "count": cnt
                })
                cnt += 1

            if page is not None and page != '':
                page = int(page)
                has_more_pages = (page*10) < len(data)
                data = data[(page-1)*10:page*10]

            return Response({"data": {"data": data, "has_more_pages": has_more_pages}, 'status': "ok"},status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception({"!!!!!!!!!!!Error!!!!!!!!!!!!": e})
            return Response({"data": [], 'status': "error"},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        # return Response({"status": "ok"},status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=False, url_path="check-duplicate-response")
    def check_duplicate_response(self, request, *args, **kwargs):

        try:
            question_id = request.query_params.get("question_id")
            test_attempt_session_id = request.query_params.get("test_attempt_session_id")

            question_response = TestQuestionResponse.objects.filter(question_id=question_id,
                                                                    test_attempt_session_id=test_attempt_session_id,
                                                                    deleted=0)
            
            check_duplicate = False

            if question_response.count() > 0:
                check_duplicate = True
        


            return Response({"duplicate_check": check_duplicate,"status": "sent"}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"status": "error"}, status=status.HTTP_200_OK)


    @action(methods=['POST'],detail=False,url_path="updates-admin-panel")
    def set_admin_controls(self,request, *args, **kwargs):
        tenant = self.request.tenant.uid
        interaction_per_month = request.query_params.get('interaction_per_month')
        interaction_repeatation = request.query_params.get('interaction_repeatation')
        logo_url = request.query_params.get('logo_url')
        user_id = request.query_params.get('user_id')
        test_codes = request.query_params.get('test_codes')


        test_code = request.query_params.get('test_code')
        test_type = request.query_params.get('test_type')
        scenario_case = request.query_params.get('scenario_case')
        interaction_mode = request.query_params.get("interaction_mode")

        

        admin_panel_updates(interaction_per_month,interaction_repeatation,logo_url,tenant,test_codes,user_id,test_type,scenario_case,test_code,interaction_mode)

        return Response({"status": "updated"}, status=status.HTTP_200_OK)
    
    @action(methods=['GET'],detail=False,url_path="get-test-scenario-case")
    def get_test_scanrio_case(self,request, *args, **kwargs):

        test_types = dict(TestTypeChoices.values)
        scenario_cases = dict(ScenarioCaseChoices.values)

        return Response({"data":{"test_types":test_types,"scenario_cases": scenario_cases},"status": "updated"}, status=status.HTTP_200_OK)

    @action(methods=['POST'],detail=False,url_path="user-attributes-prompt-updation")
    def user_att_prmpt_updation(self,request, *args, **kwargs):

        user_id = request.query_params.get('user_id')
        difficulty_level = request.query_params.get('difficulty_level')
        easy_feedback_prompt = request.query_params.get('easy_feedback_prompt')
        midium_feedback_prompt = request.query_params.get('midium_feedback_prompt')
        critical_feedback_prompt = request.query_params.get('critical_feedback_prompt')
        custom_feedback_prompt_1 = request.query_params.get('custom_feedback_prompt_1')
        custom_feedback_prompt_2 = request.query_params.get('custom_feedback_prompt_2')
        easy_skill_prompt = request.query_params.get('easy_skill_prompt')
        midium_skill_prompt = request.query_params.get('midium_skill_prompt')
        critical_skill_prompt = request.query_params.get('critical_skill_prompt')
        custom_skill_prompt_1 = request.query_params.get('custom_skill_prompt_1')
        custom_skill_prompt_2 = request.query_params.get('custom_skill_prompt_2')


        var_list= [("difficulty_level",difficulty_level),
                ("easy_feedback_prompt",easy_feedback_prompt),
                ("midium_feedback_prompt",midium_feedback_prompt),
                ("critical_feedback_prompt",critical_feedback_prompt),
                ("custom_feedback_prompt_1",custom_feedback_prompt_1),
                ("custom_feedback_prompt_2",custom_feedback_prompt_2),
                ("easy_skill_prompt",easy_skill_prompt),
                ("midium_skill_prompt",midium_skill_prompt),
                ("critical_skill_prompt",critical_skill_prompt),
                ("custom_skill_prompt_1",custom_skill_prompt_1),
                ("custom_skill_prompt_2",custom_skill_prompt_2)]

        update_prompt_user_attributes(user_id,dict(var_list))

        return Response({"status": "updated"}, status=status.HTTP_200_OK)
    

    @action(methods=['GET'],detail=False,url_path="get_normal_test_csv")
    def get_normal_test_csv(self,request, *args, **kwargs):
        tenant_id = self.request.tenant.uid
        title = request.query_params.get('title',None)
        test_type = request.query_params.get('test_type',None)
        interaction_mode = request.query_params.get('interaction_mode',None)
        scenario_case = request.query_params.get('scenario_case',None)
        num_questions = request.query_params.get('num_questions',None)
        candidate_type = request.query_params.get('candidate_type',None)

        tests = Test.objects.filter(deleted=0,tenant_id=tenant_id,test_type=test_type)
        test_list = []

        if candidate_type:
            tests = tests.filter(candidate_type=candidate_type)
        if interaction_mode:
            tests = tests.filter(interaction_mode=interaction_mode)
        if scenario_case:
            tests = tests.filter(scenario_case=scenario_case)
        if title :
            tests = tests.filter(title=title)

        cnt = 1
        csv_heading = "Title,Test code,Test description,Description Media,Ted talks and HBR Case,is checkin type,is_email_type,Candidate Type,Email Address List,Interaction Mode,Test Type,Scenario Case"
        for test in tests:
            temp={}
            questions = TestQuestion.objects.filter(test_id=test.uid)

            num_questions = int(num_questions)
            if questions.count() == num_questions :
                
                temp["Test code"] = test.test_code
                temp["Title"] = test.title
                temp["Test description"] = test.description
                temp["Description Media"] = test.description_media
                temp["Ted talks and HBR Case"] = test.tedtalk_and_hbr_case
                temp["is checkin type"] = test.is_checkin_type
                temp["is_email_type"] = test.is_email_type
                temp["Candidate Type"] = test.candidate_type
                temp["Email Address List"] = test.email_address_list
                temp["Interaction Mode"] = test.interaction_mode
                temp["Test Type"] = test.test_type
                temp["Scenario Case"] = test.scenario_case

                for question in questions:
                    if cnt == 1:
                        csv_heading += f",Question {question.question_number},Custom Prompt {question.question_number},KLP {question.question_number},KLS {question.question_number}"
                    
                    temp[f"Question {question.question_number}"] = question.question
                    temp[f"Custom Prompt {question.question_number}"] = question.gpt_prompt_override
                    temp[f"KLP {question.question_number}"] = question.key_learning_point
                    temp[f"KLS {question.question_number}"] = question.key_learning_skills

                    

                test_list.append(temp)

                
                cnt += 1
                

        return Response({"heading": csv_heading,'test_list':test_list}, status=status.HTTP_200_OK)
    

    @action(methods=['GET'],detail=False,url_path="get_group_discussion_test_csv")
    def get_group_discussion_test_csv(self,request, *args, **kwargs):
        tenant_id = self.request.tenant.uid
        test_type = request.query_params.get('test_type',None)
        interaction_mode = request.query_params.get('interaction_mode',None)
        scenario_case = request.query_params.get('scenario_case',None)
        num_questions = request.query_params.get('num_questions',None)
        candidate_type = request.query_params.get('candidate_type',None)
        bots = request.query_params.get('bots',None)
        is_start_with_user = request.query_params.get('is_start_with_user',None)

        tests = Test.objects.filter(deleted=0,tenant_id=tenant_id,test_type=test_type)
        test_list = []

        if candidate_type:
            tests = tests.filter(candidate_type=candidate_type)
        
        if interaction_mode:
            tests = tests.filter(interaction_mode=interaction_mode)
        if scenario_case:
            tests = tests.filter(scenario_case=scenario_case)
        

        cnt = 1
        csv_heading = "Test Code,Title,Context,Description Media,Ted talks and HBR Case,is checkin type,Candidate Type,Email Address List,Interaction Mode,Test Type,Scenario Case"
        for test in tests:
            
            temp={}
            
            questions = TestQuestion.objects.filter(test_id=test.uid)


            num_questions = int(num_questions)
            if questions.count() == num_questions :
                
                temp["Test Code"] = test.test_code
                temp["Title"] = test.title
                temp["Context"] = test.description
                temp["Description Media"] = test.description_media
                temp["Ted talks and HBR Case"] = test.tedtalk_and_hbr_case
                temp["is checkin type"] = test.is_checkin_type
                temp["Candidate Type"] = test.candidate_type
                temp["Email Address List"] = test.email_address_list
                temp["Interaction Mode"] = test.interaction_mode
                temp["Test Type"] = test.test_type
                temp["Scenario Case"] = test.scenario_case


                orch_details = test.orchestrated_conversation_details

                if 'start_with_user' in orch_details:
                    if is_start_with_user == 'false':
                        continue
                elif 'start_with_user' not in orch_details:
                    if is_start_with_user == 'true':
                        continue


                if len(orch_details['initial_messages']) == int(bots):
                    for index,msg in enumerate(orch_details['initial_messages']):
                        if cnt == 1:
                            csv_heading += f",Pesron {index}"
                        temp[f'Person {index}'] = msg
                else:
                    continue



                if test_type in ['dynamic_discussion',"dynamic_discussion_thread"]:
                    if test_type == 'dynamic_discussion':
                        if cnt == 1:
                            csv_heading += ',is_dynamic_discussion'
                        temp['is_dynamic_discussion'] = True
                    elif test_type == 'dynamic_discussion_thread':
                        if cnt == 1:
                            csv_heading += ',is_dynamic_discussion_thread'
                        temp['is_dynamic_discussion_thread'] = True

                    if is_start_with_user == 'true':
                        if cnt == 1:
                            csv_heading += f',start with user'
                        temp[',start with user'] = orch_details['start_with_user']

                
                    


                for question in questions:
                    question_no = question.question_number

                    if cnt == 1:
                        csv_heading += f",{question_no-1}"

                    temp[f'{question_no-1}'] = question.question

                test_list.append(temp)

                cnt += 1
                

        return Response({"heading": csv_heading,'test_list':test_list}, status=status.HTTP_200_OK)

    @action(methods=['GET'],detail=False,url_path="get-free-type-test")
    def get_free_type_test(self,request, *args, **kwargs):

        tenant_id = self.request.tenant.uid
        sub_tenant_id = request.query_params.get('sub_tenant_id',None)
        skill_name = request.query_params.get('skill')

        tests = Test.objects.filter(tenant_id=tenant_id,deleted=0,is_free=1)

        if sub_tenant_id:
            tests = tests.filter(sub_tenant_id=sub_tenant_id)

        tests = tests.filter(skills_to_evaluate__icontains=skill_name.capitalize())

        test_details = []
        for test in tests:
            test_details.append({
                "test_title": test.title,
                "test_code": test.test_code
            })

        return Response(data=test_details,status=status.HTTP_200_OK)
    

    @action(methods=['POST'], detail=False, url_path="get_or_create_test_scenarios_by_site")
    def get_or_create_test_scenarios_by_site(self, request, *args, **kwargs):
        """
        Get or create test scenarios based on a given site URL and mode.

        :param request: the HTTP request object
        :param url: a string representing the URL of the site
        :param mode: a string representing the mode ('A' or 'B')
        :param access_token: a string representing the access token for the site
        :return: the created scenario as a response
        """    
        tenant_id = self.request.tenant.uid
        url = request.query_params.get('url')
        mode = request.query_params.get('mode')
        access_token = request.query_params.get('access_token')
        context = request.query_params.get('information',None)

        # print("%"*100,f"              {mode}  {url}   {key} : {secret}             ","%"*100)
        if mode == 'A':
            scenario = create_scenario_from_site_context(url, access_token, tenant_id, context)
            return Response(data=[scenario], status=status.HTTP_200_OK)
        else:
            scenario = fetch_test_codes_by_site_context(url,tenant_id, context)
            return Response(data=scenario, status=status.HTTP_200_OK)





