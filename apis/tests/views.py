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
from tests.helpers import (create_test, update_test, get_test_report, generate_test_from_objective_anthropic , admin_panel_updates,
                            update_prompt_user_attributes, scrape_article_data, update_scenarios)
from tests.models import Test, TestQuestionResponse, TestAttemptSession, TestQuestion, UserTestConfigs
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
from tests.helpers import create_scenario_from_site_context, fetch_test_codes_by_site_context, get_low_skill_scenarios
from skills.helpers import json_extraction
from commons.langchain import download_and_transcribe_audio
import json
from collections import defaultdict
from commons.youtube_utils import get_youtube_transcript
from documents.utils import get_summary
from commons.notifications import send_error_notification
from tests.helpers import search_keywords, replace_words
from commons.cache_utils import get_cache, set_cache, delete_cache, generate_cache_key, reset_cache_with_prefix
import logging
from identities.models import Identity

logger = logging.getLogger(__name__)


class TestViewSet(ApiViewSet,
                  mixins.ListModelMixin,
                  mixins.RetrieveModelMixin,
                  mixins.UpdateModelMixin):
    """
    This code defines a class called `TestViewSet` which is a viewset for handling API requests related to tests. It includes various methods for creating, retrieving, and manipulating test data.

    Example Usage:
    - Create a new test
    - Retrieve a specific test
    - Perform various actions on a test, such as generating flash cards, getting a mindmap, generating a report, etc.

    Main functionalities:
    - Create a new test
    - Retrieve a specific test
    - Perform various actions on a test, such as generating flash cards, getting a mindmap, generating a report, etc.

    Methods:
    - get_queryset(): Returns the queryset of tests filtered by the tenant ID.
    - create(): Creates a new test based on the provided data.
    - get_test_flash_cards(): Retrieves the flash cards for a specific test.
    - get_test_mindmap(): Retrieves the mindmap for a specific test.
    - get_test_report_pdf_view(): Retrieves the report PDF for a specific test.
    - get_test_flash_cards_data(): Retrieves the flash card data for a specific test.
    - get_test_mindmap_data(): Retrieves the mindmap data for a specific test.
    - get_test_report_frontend(): Retrieves the report data for a specific test.
    - get_learner_path(): Retrieves the learner path for a specific user and objective.
    - generate_test_from_objective(): Generates a test based on a specific objective.
    - get_tenant_special_case_test_category(): Retrieves the special case test categories for a specific tenant.
    - get_tenant_special_case_test(): Retrieves the special case tests for a specific tenant and category.
    - get_test_previlage(): Retrieves the test privilege for a specific user.
    - get_selection_options(): Retrieves the selection options for filtering tests.
    - get_tests_by_choice(): Retrieves tests based on the provided filter choices.
    - check_duplicate_response(): Checks if a duplicate response exists for a specific question and test attempt session.
    - set_admin_controls(): Updates the admin controls for a specific tenant.
    - get_test_scanrio_case(): Retrieves the test scenario cases.
    - user_att_prmpt_updation(): Updates the user attribute prompts.
    - get_normal_test_csv(): Retrieves the CSV data for normal tests.
    - get_group_discussion_test_csv(): Retrieves the CSV data for group discussion tests.
    - get_free_type_test(): Retrieves the free type tests for a specific skill.
    - get_or_create_test_scenarios_by_site(): Retrieves or creates test scenarios based on a site URL and mode.

    Fields:
    - queryset: The queryset of tests filtered by the tenant ID.
    - serializer_class: The serializer class for test data.
    - permission_classes: The permission classes for accessing test data.
    - filter_backends: The filter backends for filtering test data.
    - filterset_class: The filterset class for filtering test data.
    - ordering_fields: The ordering fields for ordering test data.
    - lookup_field: The lookup field for retrieving a specific test.
    """
    queryset = Test.objects.filter(deleted=0)
    serializer_class = TestDisplaySerializer
    permission_classes = (IsAuthenticatedClient, IsAuthenticatedUser)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = TestFilterSet
    ordering_fields = ("id",)
    lookup_field = "uid"

    def get_queryset(self):
        """Returns the queryset of tests filtered by the tenant ID."""
        return super().get_queryset().filter(tenant_id=self.request.tenant.uid)

    def create(self, request, *args, **kwargs):
        serializer = CreateTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data["creator_id"] is None:
            serializer.validated_data["creator_id"] = request.auth_user.uid


        if serializer.validated_data.get('test_code'):
            test, test_questions = update_test(
                tenant=request.tenant,
                **serializer.validated_data
            )

        else:

            test, test_questions = create_test(
                tenant=request.tenant,
                **serializer.validated_data
            )

        return Response(self.serializer_class(instance=test).data, status=status.HTTP_201_CREATED)

    @action(methods=["PATCH"], detail=True, url_path="update-test")
    def update_test(self, request, *args, **kwargs):
        """
        Partially updates an existing test based on the provided data.
        """
        serializer = CreateTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        print(serializer.validated_data)

        if serializer.validated_data["creator_id"] is None:
            serializer.validated_data["creator_id"] = request.auth_user.uid

        test, test_questions = update_test(
            tenant=request.tenant,
            **serializer.validated_data
        )
 
        return Response(self.serializer_class(instance=test).data, status=status.HTTP_200_OK)
    
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

        try:
            send_learner_path_email(tests, user)
        except Exception as e:
            send_error_notification("get_learner_path", "Error in sending learner path email", e)

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
        """
        Retrieves the selection options for filtering tests based on the tenant ID.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            HttpResponse: The HTTP response object containing the selection options data.
        """
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
        """
        Checks if a duplicate response exists for a specific question and test attempt session.

        Args:
            request (HttpRequest): The HTTP request object.
            question_id (str): The ID of the question.
            test_attempt_session_id (str): The ID of the test attempt session.

        Returns:
            HttpResponse: The HTTP response object containing the result of the duplicate response check.

        Raises:
            Exception: If an error occurs during the duplicate response check.

        Example Usage:
            GET /check-duplicate-response?question_id=123&test_attempt_session_id=456

            Response:
            {
                "duplicate_check": true,
                "status": "sent"
            }
        """
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
        """
        Update the admin controls for a specific tenant.

        Args:
            request (HttpRequest): The HTTP request object.
    
        Query Parameters:
            interaction_per_month (str): The maximum number of interactions allowed per month.
            interaction_repeatation (str): The maximum number of times an interaction can be repeated.
            logo_url (str): The URL of the logo to be updated.
            user_id (str): The ID of the user for whom the admin controls are being updated.
            test_codes (str): The comma-separated list of test codes to be updated.
            test_type (str): The type of the test to be updated.
            scenario_case (str): The scenario case to be updated.
            test_code (str): The test code to be updated.
            interaction_mode (str): The interaction mode to be updated.

        Returns:
            Response: A response indicating the status of the update.
        """
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
        """
        Retrieves the test types and scenario cases available in the system.

        :param request: The HTTP request object.
        :return: A JSON response containing the test types and scenario cases available in the system.
        """
        test_types = dict(TestTypeChoices.values)
        scenario_cases = dict(ScenarioCaseChoices.values)

        return Response({"data":{"test_types":test_types,"scenario_cases": scenario_cases},"status": "updated"}, status=status.HTTP_200_OK)

    @action(methods=['POST'],detail=False,url_path="user-attributes-prompt-updation")
    def user_att_prmpt_updation(self,request, *args, **kwargs):
        """
        Update the user attribute prompts for a specific user.

        Args:
            request (HttpRequest): The HTTP request object.
            user_id (str): The ID of the user for whom the prompts need to be updated.
            difficulty_level (str): The difficulty level prompt.
            easy_feedback_prompt (str): The prompt for easy feedback.
            midium_feedback_prompt (str): The prompt for medium feedback.
            critical_feedback_prompt (str): The prompt for critical feedback.
            custom_feedback_prompt_1 (str): The prompt for custom feedback 1.
            custom_feedback_prompt_2 (str): The prompt for custom feedback 2.
            easy_skill_prompt (str): The prompt for easy skill.
            midium_skill_prompt (str): The prompt for medium skill.
            critical_skill_prompt (str): The prompt for critical skill.
            custom_skill_prompt_1 (str): The prompt for custom skill 1.
            custom_skill_prompt_2 (str): The prompt for custom skill 2.

        Returns:
            Response: A response indicating that the prompts have been updated.
        """
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
        test_codes = request.query_params.get('test_codes',None)
        page_name = request.query_params.get('page_name',None)
        competency_skills = request.query_params.get('competency_skills',None)
        tab_category = request.query_params.get('tab_category',None)
        client_name = request.query_params.get('client_name',None)

        creator_email = request.query_params.get('creator_email',None)
        
        created_by_user_id = None
        logger.info(f"******** Creator email : {creator_email}")
        if creator_email:
            identity = Identity.objects.filter(value=creator_email).last()
            created_by_user_id = identity.user_id if identity else None
            logger.info(f"******** Creator user id : {created_by_user_id}")



        test_list = []
        tests = Test.objects.filter()
        if test_codes:
            test_codes = [code.strip() for code in test_codes.split(",")]
            tests = Test.objects.filter(deleted=0,tenant_id=tenant_id,test_code__in=test_codes)

        else:
            tests = Test.objects.filter(deleted=0,tenant_id=tenant_id,test_type=test_type)

            if candidate_type:
                tests = tests.filter(candidate_type=candidate_type)
            if interaction_mode:
                tests = tests.filter(interaction_mode=interaction_mode)
            if scenario_case:
                tests = tests.filter(scenario_case=scenario_case)
            if title :
                tests = tests.filter(title=title)

            if page_name:
                tests = tests.filter(page_name=page_name)

            if competency_skills:
                tests = tests.exclude(competency_group__in=[None,""])
            if tab_category:
                tests = tests.filter(tab_category=tab_category)

            if client_name:
                tests = tests.filter(client_name=client_name)

                
            if created_by_user_id:
                tests = tests.filter(creator_user_id=created_by_user_id)



        cnt = 1
        csv_heading = "Title,Test code,Test description,Description Media,Ted talks and HBR Case,is checkin type,is_email_type,Candidate Type,Email Address List,Interaction Mode,Test Type,Scenario Case,Tab category,Competency Skills,Client Name"
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
                temp['Tab category'] = test.tab_category
                temp['Competency Skills'] = test.competency_group
                temp['Client Name'] = test.client_name

                for question in questions:
                    if cnt == 1:
                        csv_heading += f",Question {question.question_number},Custom Prompt {question.question_number},KLP {question.question_number},KLS {question.question_number}"
                    
                    temp[f"Question {question.question_number}"] = question.question
                    temp[f"Custom Prompt {question.question_number}"] = question.gpt_prompt_override
                    temp[f"KLP {question.question_number}"] = question.key_learning_point
                    temp[f"KLS {question.question_number}"] = question.key_learning_skills

                    

                test_list.append(temp)

                
                cnt += 1

                print(f'created- {test.test_code}')
                
            else:
                print(f'{test.test_code},{test.test_type}: {questions.count()}')

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


        test_codes = request.query_params.get('test_codes',None)
        page_name = request.query_params.get('page_name',None)
        competency_skills = request.query_params.get('competency_skills',None)
        tab_category = request.query_params.get('tab_category',None)
        client_name = request.query_params.get('client_name',None)

        test_list = []
        tests = Test.objects.filter()
        if test_codes:
            test_codes = [code.strip() for code in test_codes.split(",")]
            tests = Test.objects.filter(deleted=0,tenant_id=tenant_id,test_code__in=test_codes)
        else:
            tests = Test.objects.filter(deleted=0,tenant_id=tenant_id,test_type=test_type)

            if candidate_type:
                tests = tests.filter(candidate_type=candidate_type)
            
            if interaction_mode:
                tests = tests.filter(interaction_mode=interaction_mode)
            if scenario_case:
                tests = tests.filter(scenario_case=scenario_case)
            if page_name:
                tests = tests.filter(page_name=page_name)
            if competency_skills:
                tests = tests.exclude(competency_group__in=[None,""])
            if tab_category:
                tests = tests.filter(tab_category=tab_category)
            if client_name:
                tests = tests.filter(client_name=client_name)


        cnt = 1
        csv_heading = "Test Code,Title,Context,Description Media,Ted talks and HBR Case,is checkin type,Candidate Type,Email Address List,Interaction Mode,Test Type,Scenario Case,Tab category,Competency Skills,Client Name"
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
                temp['Tab category'] = test.tab_category
                temp['Competency Skills'] = test.competency_group
                temp['Client Name'] = test.client_name


                orch_details = test.orchestrated_conversation_details

                
                if 'start_with_user' in orch_details:
                    if is_start_with_user == 'false':
                        print(f"{test.test_code},start with user: {'start_with_user' in orch_details}")
                        continue
                elif 'start_with_user' not in orch_details:
                    if is_start_with_user == 'true':
                        print(f"{test.test_code},start with user: {'start_with_user' in orch_details}")
                        continue


                if len(orch_details['initial_messages']) == int(bots):
                    for index,msg in enumerate(orch_details['initial_messages']):
                        if cnt == 1:
                            csv_heading += f",Pesron {index}"
                        temp[f'Person {index}'] = msg
                else:
                    print(f"{test.test_code},{test.test_type},{questions.count()},{len(orch_details['initial_messages'])}")

                    continue


                test_type = test.test_type
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

                print(f"created {test.test_code}")
                
            else:
                print(f"{test.test_code},{test.test_type},{questions.count()}")
        return Response({"heading": csv_heading,'test_list':test_list}, status=status.HTTP_200_OK)

    @action(methods=['GET'], detail=False, url_path="get-free-type-test")
    def get_free_type_test(self, request, *args, **kwargs):
        """
        Retrieves free type tests based on the provided skill name and optional sub-tenant ID.

        :param request: The HTTP request object.
        :param sub_tenant_id: (optional) The ID of the sub-tenant. Defaults to None.
        :param skill_name: The name of the skill for which to retrieve free type tests.
        :return: A list of dictionaries containing the test title and test code for each free type test that matches the provided skill name and optional sub-tenant ID.
        """

        tenant_id = self.request.tenant.uid
        sub_tenant_id = request.query_params.get('sub_tenant_id', None)
        skill_name = request.query_params.get('skill')

        tests = Test.objects.filter(tenant_id=tenant_id, deleted=0, is_free=1)

        if sub_tenant_id:
            tests = tests.filter(sub_tenant_id=sub_tenant_id)

        tests = tests.filter(skills_to_evaluate__icontains=skill_name.capitalize())

        test_details = []
        for test in tests:
            test_details.append({
                "test_title": test.title,
                "test_code": test.test_code
            })

        return Response(data=test_details, status=status.HTTP_200_OK)
    

    @action(methods=['POST'], detail=False, url_path="get_or_create_test_scenarios_by_site")
    def get_or_create_test_scenarios_by_site(self, request, *args, **kwargs):
        """
            Retrieves or creates test scenarios based on a site URL and mode.

            Parameters:
            - request: The HTTP request object.
            - args: Additional positional arguments.
            - kwargs: Additional keyword arguments.

            Returns:
            - Response: The HTTP response object containing the test scenarios data.

            Raises:
            - N/A

            Example Usage:
            - Retrieve or create test scenarios for a specific site URL and mode.

            Notes:
            - This method is used to retrieve or create test scenarios based on a site URL and mode. It takes in various parameters such as the URL, mode, access token, context, source, creator user ID, competency, and flags for static and dynamic scenarios. It then calls the appropriate helper functions to retrieve or create the test scenarios and returns the data in the HTTP response object.

            Algorithm:
            1. Get the tenant ID from the request object.
            2. Get the URL, mode, access token, context, source, creator user ID, competency, and flags for static and dynamic scenarios from the request query parameters.
            3. If the mode is 'A':
                - Create an empty list to store the test scenarios data.
                - If the static scenario flag is True:
                    - Call the 'create_scenario_from_site_context' helper function to create a static scenario based on the site context.
                    - Append the static scenario data to the list.
                - If the dynamic scenario flag is True:
                    - Call the 'create_scenario_from_site_context' helper function to create a dynamic scenario based on the site context.
                    - Append the dynamic scenario data to the list.
                - Return the list of test scenarios data in the HTTP response object.
            4. If the mode is not 'A':
                - Call the 'fetch_test_codes_by_site_context' helper function to retrieve the test scenarios based on the site context.
                - Return the test scenarios data in the HTTP response object.
        """ 
        tenant_id = self.request.tenant.uid
        url = request.query_params.get('url')
        mode = request.query_params.get('mode')
        access_token = request.query_params.get('access_token')
        context = request.query_params.get('information',None)
        source = request.query_params.get('source',None)
        creator_user_id = request.query_params.get('creator_user_id',None)
        competency = request.query_params.get('competency',None)
        is_static = request.query_params.get('is_static',True)
        is_dynamic = request.query_params.get('is_dynamic',True)
        assign_to = request.query_params.get('assign_to')
        assigned_by = request.query_params.get("assigned_by")
        is_micro = request.query_params.get("is_micro",True)
        regeneration = request.query_params.get("regeneration",False)
        is_fetch = request.query_params.get("is_fetch",False)
        use_anthropic = request.query_params.get("use_anthropic",True)
        flavour = request.query_params.get('flavour',None)

        is_micro = False if is_micro in ['False','false',0,False] else True
        use_anthropic = False if use_anthropic in ['False','false',0,False] else True
        is_fetch = False if is_fetch in ['False','false',0,False] else True
        regeneration = False if regeneration in ['False','false',0,False] else True

        is_fetch = False if regeneration else is_fetch

        logger.info(f"{'>>>'*100} url : {url}, mode : {mode}, access_token : {access_token}, context : {context}, source : {source}, creator_user_id : {creator_user_id}, competency : {competency}, is_static : {is_static}, is_dynamic : {is_dynamic}, assign_to: {assign_to}, assigned_by: {assigned_by}, is_micro: {is_micro}, regeneration: {regeneration}, flavour: {flavour} {'>>>'*100}")

        if mode == 'A':
            logger.info("************************* MODE A *************************")
            resp_data = []
            
            if not context and url not in [None, ""]:
                if is_fetch:
                    scenario = fetch_test_codes_by_site_context(url,tenant_id,by='web_page',is_micro=is_micro)
                    logger.info(f"fetched scenarios: {scenario}")
                    if len(scenario) > 0:
                        return Response(data=scenario, status=status.HTTP_200_OK)

                article_data = scrape_article_data(url.strip())
                print('='*50)
                print(article_data)

                if not article_data:
                    return Response(data=[{'error':"Scenario generation failed because of failure of page extraction please try again."}], status=status.HTTP_400_BAD_REQUEST)

                # matches = search_keywords(article_data.get('article_content'))
                # if len(matches) > 0:
                #     return Response(data=[{'error':f"Scenario generation failed because restricted keywords found: {matches}"}], status=status.HTTP_400_BAD_REQUEST)
            
                # if not article_data.get('article_content') or  article_data.get('article_content') == "":
                #     return Response(data=[{'error':"Scenario generation failed because of failure of page extraction please try again."}], status=status.HTTP_400_BAD_REQUEST)
                
                context = json.dumps({
                    "title": article_data.get('title'),
                    "data": {'information': f"\n Description: {article_data.get('description')} \n\n Content: {article_data.get('article_content')}"}
                })

            if is_static == 'true' or is_static == True or is_static == "True":
                scenario = create_scenario_from_site_context(url, access_token, tenant_id, context, 
                                                             origin=source, competency=competency, 
                                                             creator_user_id=creator_user_id, assign_to=assign_to, 
                                                             assigned_by=assigned_by, is_micro=is_micro,
                                                             regeneration=regeneration,use_anthropic=use_anthropic,
                                                             flavour=flavour
                                                             )
                if scenario:
                    resp_data.append(scenario)
                else:
                    resp_data.append({'message':"failed to generate the scenario"})
            # if is_dynamic == 'true' or is_dynamic == True or is_dynamic == "True":
            #     dynamic_discussion = create_scenario_from_site_context(url=url, access_token=access_token, tenant_id=tenant_id,context=context,type_of_test=TestTypeChoices.dynamic_discussion_thread, 
            #                                                         origin=source, competency=None, creator_user_id=creator_user_id,assign_to=assign_to,assigned_by=assigned_by,is_micro=is_micro)
            #     if scenario:
            #         resp_data.append(dynamic_discussion)
            #     else:
            #         resp_data.append({'message':"failed to generate the dynamic_discussion"})
            return Response(data=resp_data, status=status.HTTP_201_CREATED)
        else:
            logger.info("*********************************** MODE B ********************************")
            scenario = fetch_test_codes_by_site_context(url,tenant_id)
            return Response(data=scenario, status=status.HTTP_200_OK)




    @action(methods=['GET'], detail=False, url_path="get-recommendetion-tests")
    def get_recommendation_tests(self, request, *args, **kwargs):
        """
            Retrieves recommendation tests based on the provided context.
            
            Parameters:
                request (Request): The HTTP request object.
                args (tuple): Additional positional arguments.
                kwargs (dict): Additional keyword arguments.
                
            Returns:
                Response: The HTTP response object containing the matching tests and the created scenario.
                            
            Note:
                This method uses the 'context' parameter to generate a prompt for the OpenAI GPT-3 model.
                The generated prompt is then used to get recommendation tests based on the provided context.
                The 'for' parameter can be used to specify the mode of operation, such as 'feedback_bot'.
        """
        tenant_id = self.request.tenant.uid
        context = request.query_params.get('context')
        mode = request.query_params.get('for',None)
        creator_user_id = request.query_params.get('creator_user_id')
        test_type = request.query_params.get('test_type',None)

        logger.info(f">>>>>>>>>>>>>>>>>>> request data : {request.data}, test_type: {test_type},  access_token : { request.headers.get('Authorization')}")
        access_token = request.headers.get('Authorization')

        if not context:
            return Response({"Error": "context is required"}, status=status.HTTP_400_BAD_REQUEST)

        logger.info(f">>>>>>>>>>>>>>>>>>> context : {context}")

        all_tests = Test.objects.filter(tenant_id=tenant_id,deleted=0)
        tests_data = """"""

        for test in all_tests:
            tests_data += f"{test.test_code} : {test.title}\n"

        # logger.info(f">>>>>>>>>>>>>>>>>>> tests_data : {tests_data}")

        prompt = ""
        scenario = ''
        type_of_test=TestTypeChoices.test

        if test_type == "dynamic":
            type_of_test=TestTypeChoices.dynamic_discussion_thread

        logger.info(f">>>>>>>>>>>>>>> Type of test : {type_of_test}")

        if mode == "feedback_bot":
            scenario = create_scenario_from_site_context('', access_token, tenant_id, json.dumps({'title': "",'data':{'information':context}}),is_feedback_bot=True,  type_of_test=type_of_test, creator_user_id=creator_user_id)
        else:
            scenario = create_scenario_from_site_context('', access_token, tenant_id, json.dumps({'title': "",'data':{'information':context}}), creator_user_id=creator_user_id, type_of_test=type_of_test)
        logger.info(f">>>>>>>>>>>>>>>>>>> scenario : {scenario}")

        if mode == 'feedback_bot':
            data = ''
            context = json.loads(context)
            for que, ans in context.items():
                data += f"Question: {que} , Answer: {ans}\n"

            context = data
            prompt = f"""

                \n\nHuman:

                user_input: {context}

                test_data: {tests_data}

                Based on {{user_input}} pick the best test from the {{test_data}}. Based on {{user_input}} this conversation give me the scenario from {{test_data}} that best suits the user's needs and requirements. The scenario should be directly linked to the skills or areas identified in {{user_input}}.

                NOTE : Output format : {"{"}"Q78TYZ" : "python skills improvement"{"}"}

                NOTE: just give me test_code and title in json format like {"{"}"Q78TYZ" : "python skills improvement"{"}"}

                NOTE: do not provide any other information

                NOTE : Do not provide any kind of explanation in the output.

                \n\nAssistant:

                """
            
        else:
            prompt = f"""
        \n\nHuman:
        user_input: {context}
        test_data: {tests_data}

        Based on {{user_input}} pick the best test from the {{test_data}}. Based on {{user_input}} give me the scenario from {{test_data}} that best suits the user's needs and requirements. The scenario should be directly linked to the skills or areas identified in {{user_input}}.

        NOTE : Output format : {"{"}"Q78TYZ" : "python skills improvement"{"}"}

        NOTE: just give me test_code and title in json format like {"{"}"Q78TYZ" : "python skills improvement"{"}"}

        NOTE: do not provide any other information

        NOTE : Do not provide any kind of explanation in the output.

        \n\nAssistant:
        """
            
        """  response = anthropic_completion(prompt,5000)
        logger.info(f">>>>>>>>>>>>>>>>>>> response : {response}")
        json_response = json_extraction(response)
        logger.info(f">>>>>>>>>>>>>>>>>>> json_response : {json_response}, json_data : {json.loads(json_response)}") """

        data = {
            "matching_tests": {"xyz123": "Test 1"},
            "created_scenario": {scenario['test_code']: scenario['title']},
            "success": True,
        }
        

        return Response(data, status=status.HTTP_200_OK)



    @action(methods=['GET'], detail=False, url_path="create-test-from-links")
    def create_scenario_from_links(self, request, *args, **kwargs):
        """
        Creates a scenario from the provided URL and generates a test based on the site context.

        Args:
            url

        Returns:
            Response: The HTTP response object containing the test code, title, and description of the generated scenario.

        """
        tenant_id = self.request.tenant.uid
        url = request.query_params.get('url')
        creator_user_id = request.query_params.get('creator_user_id')
        access_token = request.headers.get('Authorization')

        logger.info(f">>>>>>>>>>>> url : {url}")

        raw_scenario_data = ''
        if 'youtube' in url:
            for i in range(2):
                transcript = get_youtube_transcript(url)
                if transcript is not None:
                    break
            if transcript is None:
                transcript = download_and_transcribe_audio(url)

            summary = get_summary(transcript)
            raw_scenario_data = summary
        else:
            raw_scenario_data = scrape_article_data(url).get('article_content',None)

        logger.info(f">>>>>>>>>>>>> raw_scenario_data : {raw_scenario_data}")
        resp_data = []
        scenario = create_scenario_from_site_context('', access_token, tenant_id, json.dumps({'title': "",'data':{'information': raw_scenario_data}}),use_anthropic=True,creator_user_id=creator_user_id,scenario_summary=raw_scenario_data)
        
        resp_data.append(scenario)
        dynamic_discussion = create_scenario_from_site_context(url="", access_token=access_token, tenant_id=tenant_id,context=json.dumps({'title': "",'data':{'information': raw_scenario_data}}),type_of_test=TestTypeChoices.dynamic_discussion_thread, 
                                                                    creator_user_id=creator_user_id,
                                                                    scenario_summary=raw_scenario_data)
        resp_data.append(dynamic_discussion)

        return Response(data=resp_data, status=status.HTTP_200_OK)

    
    @action(methods=['GET'], detail=False, url_path="get-tests-by-bot")
    def get_tests_by_bot(self, request, *args, **kwargs):
        """
        Retrieves tests filtered by the provided bot name.

        Args:
            request (HttpRequest): The HTTP request object.
            bot_id (str): The name of the bot to filter the tests. eg: aravsharma-0023

        Returns:
            HttpResponse: The HTTP response object containing the filtered tests data.

        Example:
            GET /api/tests/get-tests-by-bot?bot_id=example_bot

            Response:
            [
                {
                    "title": "Test 1",
                    "description": "This is test 1",
                    "test_code": "ABC123"
                },
                {
                    "title": "Test 2",
                    "description": "This is test 2",
                    "test_code": "DEF456"
                }
            ]
        """
        bot_name = request.query_params.get("bot_id",None)

        tests = Test.objects.filter(deleted=0,tenant_id=self.request.tenant.uid,bot_name=bot_name)
        data = [{"title": test.title,"description":test.description,"test_code": test.test_code } for test in tests]

        return Response(data,status=status.HTTP_200_OK)


    @action(methods=['GET'], detail=False, url_path="get-tests-by-competency")
    def get_tests_by_competency(self, request, *args, **kwargs):
        """
        Retrives tests by competencies.
        Output: {"comp1" : [{"title": test.title,"description":test.description,"test_code": test.test_code, "test_type": test.test_type }],}
        """
        competencies = request.query_params.get("competencies",None)

        logger.info(f">>>>>>>>>>>>> competencies : {competencies}")

        
        cache_key = generate_cache_key('tests_by_competency', competencies=competencies, tenant_id=self.request.tenant.uid)

        # Try to get data from cache
        data = get_cache(cache_key)

        if data is None:
            data = {}
            if competencies:
                competencies = competencies.split(',')

                for competency in competencies:
                    competency = competency.strip()
                    tests = Test.objects.filter(deleted=0,tenant_id=self.request.tenant.uid,competency_group=competency)
                    temp_list = []
                    for test in tests:
                        if test.test_type not in [TestTypeChoices.dynamic_discussion,TestTypeChoices.dynamic_discussion_thread, TestTypeChoices.orchestrated_conversation]:
                            temp_list.append({"title": test.title,"description":test.description,"test_code": test.test_code, "test_type": test.test_type, "is_recommended": test.is_recommended, "is_micro": test.is_micro })
                        else:
                            questions = TestQuestion.objects.filter(test_id=test.uid)
                            is_micro = False if ((questions.count() + 1) / 2) > 3 else True
                            print(is_micro,questions.count())
                            temp_list.append({"title": test.title,"description":test.description,"test_code": test.test_code, "test_type": test.test_type, "is_recommended": test.is_recommended, "is_micro": is_micro })


                    data[competency] = temp_list
                # tests = Test.objects.filter(deleted=0,tenant_id=self.request.tenant.uid,competency__in=competencies)
                # data = [{"title": test.title,"description":test.description,"test_code": test.test_code } for test in tests]
            set_cache(cache_key, data)


        return Response(data,status=status.HTTP_200_OK)
    

    @action(methods=['GET'], detail=False, url_path="get-requested-tests")
    def get_requested_tests(self, request, *args, **kwargs):
        """
        Retrieves the requested tests for a specific user.

        Args:
            request (HttpRequest): The HTTP request object.
            user_id (str): The ID of the user for whom the tests are requested.

        Returns:
            HttpResponse: The HTTP response object containing the requested tests data.

        Raises:
            ValueError: If the user_id is not provided.

        Example Usage:
            GET /api/tests/get-requested-tests?user_id=123456

            Response:
            [
                {
                    "title": "Test 1",
                    "description": "This is test 1",
                    "test_code": "TST001"
                },
                {
                    "title": "Test 2",
                    "description": "This is test 2",
                    "test_code": "TST002"
                }
            ]
        """
        user_id = request.query_params.get("user_id",None)
        logger.info(f"<<<<<<<<<<<<<<<<<<<<<< user_id : {user_id} >>>>>>>>>>>>>>>>>>>>>>>")

        if not user_id:
            return Response({"Error": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        

        
        query = Q(assigned_to__isnull=False)
        query.add(Q(creator_user_id=user_id), Q.OR)
        query.add(Q(tenant_id=self.request.tenant.uid),Q.AND)

        
        tests = Test.objects.filter(query)
        tests.filter(deleted=0)
        data = [{"title": test.title,"description":test.description,"test_code": test.test_code, "is_recommended": test.is_recommended, "assigned_to": test.assigned_to, "is_assigned": test.is_assigned, "assigned_by": test.assigned_by, "creator_user_id": test.creator_user_id, "is_micro": test.is_micro,  'interaction_mode': test.interaction_mode, 'scenario_case': test.scenario_case  } for test in tests]

        return Response(data,status=status.HTTP_200_OK)
    
    @action(methods=['GET'],detail=False, url_path="get-tests-by-tab-category")
    def get_tests_by_tab_category(self,request,*args, **kwargs):
        """
        Retrieves tests based on the tab category and optionally the client name.

        This method fetches all the tests that are not deleted, belong to the current tenant, and have a non-null tab category.
        If a client name is provided in the request parameters, it further filters the tests to include only those associated with the given client name.

        The tests are then organized into a nested dictionary where the first level keys are the tab categories, the second level keys are the area domains, and the values are lists of tests. Each test is represented as a dictionary containing its title, description, test code, and test type.

        Parameters:
        request (Request): The request object. It may contain a query parameter 'client_name' to filter tests by client.

        Returns:
        Response: A response object with the status and the nested dictionary of tests. The dictionary structure is as follows:
        {
            "tab_category1": {
                "area_domain1": [
                    {
                        "title": "test1",
                        "description": "description1",
                        "test_code": "code1",
                        "test_type": "type1"
                    },
                    ...
                ],
                ...
            },
            ...
        }

        In case of an error, it returns a response with status 400 and an error message.

        Example:
        Request: GET /api/tests/get-tests-by-tab-category?client_name=client1
        Response: {
            "tab_category1": {
                "area_domain1": [
                    {
                        "title": "test1",
                        "description": "description1",
                        "test_code": "code1",
                        "test_type": "type1"
                    }
                ]
            }
        }
        """
        try:
            client_name = request.query_params.get("client_name",None)
            
            cache_key = generate_cache_key('tests_by_client', client_name=client_name, tenant_id=request.tenant.uid)
            test_dict = get_cache(cache_key)
            
            if test_dict is None:
                if client_name:
                    tests = Test.objects.filter(deleted=False, tenant_id=self.request.tenant.uid,tab_category__isnull=False,client_name=client_name)
                else:
                    tests = Test.objects.filter(deleted=False, tenant_id=self.request.tenant.uid,tab_category__isnull=False)
                test_dict = defaultdict(lambda: defaultdict(list))


                # Organizing tests into the nested dictionary
                for test in tests:
                    if test.tab_category:
                        tab_category = test.tab_category
                        sub_tab_category = test.sub_tab_category or test.area_domain
                        test_dict[tab_category][sub_tab_category].append({
                            "title": test.title,
                            "description": test.description,
                            "test_code": test.test_code,
                            "test_type": test.test_type,
                            "is_recommended": test.is_recommended,
                            "is_micro": test.is_micro,
                            "scenario_case": test.scenario_case
                        })
                # Converting defaultdict to a regular dictionary
                test_dict = dict(test_dict)
                set_cache(cache_key, test_dict)

            return Response(test_dict, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.exception({"got error in get-tests-by-tab-category api": e})
            return Response({"error": f"got error {e}"},status=status.HTTP_400_BAD_REQUEST)


    @action(methods=['PATCH'],detail=False, url_path="update_scenarios")
    def update_test_scenarios(self,request,*args, **kwargs):
        """
        ### Method: update_test_scenarios

        #### Objective:
        This method is used to update the scenarios for tests based on the provided data.

        #### Process:
        1. Extract the test data from the request.
        2. Iterate over each test data entry.
        3. Format the data by stripping any leading or trailing spaces.
        4. Call the `update_scenarios` function with the formatted data.
        5. Update the test scenarios based on the provided data.

        #### Input Requirements:
        - `test_data`: A list of dictionaries containing test data entries.
        - Each dictionary should contain keys for 'Title', 'Test description', 'Test code', 'Question', 'Custom Prompt', 'KLS', and 'KLP'.
        - The 'Question', 'Custom Prompt', 'KLS', and 'KLP' keys should have corresponding values for each question in the test.

        #### Expected Output:
        - Response: "updated" with status code 200 if the scenarios are successfully updated.
        - Error response with status code 400 if any issues occur during the update process.

        #### Example:
        Request Data:
        ```json
        {
        "test_data": [
            {
            "Title": "Test Title",
            "Test description": "Test Description",
            "Test code": "ABC123",
            "Question 1": "Question 1",
            "Custom Prompt 1": "Prompt 1",
            "KLS 1": "Skill 1",
            "KLP 1": "Learning Point 1"
            },
            {
            "Title": "Another Test",
            "Test description": "Another Description",
            "Test code": "DEF456",
            "Question 1": "Another Question",
            "Custom Prompt 1": "Another Prompt",
            "KLS 1": "Another Skill",
            "KLP 1": "Another Learning Point"
            }
        ]
        }
        Response:

        Status: 200
        Body: "updated"
        """
        try:
            data = request.data.get('test_data')
            for d in data:
                formatted_dict = {key.strip(): value for key, value in d.items()}
                # logger.info(f"===================== formatted_dict: {formatted_dict}")
                update_scenarios(formatted_dict)
                
            return Response("updated", status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception({"got error in update_scenarios api": e})
            return Response({"error": f"got error {e}"},status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['GET'],detail=False,url_path="get_low_skill_count_test")
    def get_low_skill_count_test(self,request,*args, **kwargs):
        """
        ### Method: get_low_skill_count_test

        #### Objective:
        This method retrieves scenarios for tests with a low number of unique skills based on the provided minimum skill count and test codes.

        #### Process:
        1. Extract the minimum skill count and test codes from the request query parameters.
        2. Retrieve the tenant information from the request.
        3. Call the `get_low_skill_scenarios` function with the tenant, test codes, and minimum skill count.
        4. Generate a list of scenarios with a low number of unique skills for the specified tests.

        #### Input Requirements:
        - `min_skill_count`: The minimum number of unique skills required for a test scenario.
        - `test_codes`: Comma-separated test codes for filtering specific tests.

        #### Expected Output:
        - Response: A list of dictionaries containing test scenarios with a low number of unique skills.
        - Each dictionary includes the test code, unique skills, and the count of unique skills.

        #### Example:
        Request Data:
        ```json
        {
            "min_skill_count": 4,
            "test_codes": "ABC123,DEF456"
        }
        Response:
        [
            {
                "Test Code": "ABC123",
                "Skills": "Skill1, Skill2, Skill3",
                "Skill count": 3
            },
            {
                "Test Code": "DEF456",
                "Skills": "Skill1, Skill2",
                "Skill count": 2
            }
        ]
        """
        try:
            min_skill_count = request.query_params.get('min_skill_count')
            test_codes = request.query_params.get('test_codes')
            tenant = request.tenant

            scenarios = get_low_skill_scenarios(tenant=tenant,test_codes=test_codes,min_skill_count=int(min_skill_count) if min_skill_count  else 4)

            return Response(scenarios, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception({"got error in get_low_skill_count_test api": e})
            return Response({"error": f"got error {e}"},status=status.HTTP_400_BAD_REQUEST)


    @action(methods=['POST'],detail=False, url_path="assign_simulation")
    def assing_simulation(self, request, *args, **kwargs):
        """
        ### `assign_simulation` Method Documentation:

        #### Objective:
        Assign simulations to users based on the provided test codes, assigned to, and assigned by information.

        #### Process Explanation:
        1. Extract the test codes, assigned to, and assigned by information from the request data.
        2. Iterate over each test code provided.
        3. Retrieve the corresponding test from the database based on the test code and tenant ID.
        4. Update the assigned to and assigned by fields of the test with the provided values.
        5. Save the changes to the test object.
        6. Return a success message if the assignment is completed successfully.

        #### Input Requirements:
        - `test_codes`: Comma-separated test codes for the simulations to be assigned.
        - `assigned_to`: The user ID to whom the simulations are assigned.
        - `assigned_by`: The user ID who is assigning the simulations.

        #### Expected Output:
        - If the assignment is successful, return a response with a success message.
        - If any errors occur during the assignment process, return an error response with details.

        #### Example:
        Request Data:
        ```json
        {
            "test_codes": "ABC123,DEF456",
            "assigned_to": "user123",
            "assigned_by": "admin456"
        }
        Response (Success):

        {
            "msg": "successfully assigned"
        }
        Response (Error - Test Code Not Found):

        {
            "error": "simulation not found"
        }
        Response (Error - Missing Fields):

        {
            "error": "test_codes are required"
        }
        """
        # return Response("ok")
        try:
            test_codes = request.data.get('test_codes')
            assigned_to = request.data.get('assigned_to')
            assigned_by = request.data.get('assigned_by')
            
            if test_codes is None:
                return Response({"error":"test_codes are required"},status=status.HTTP_400_BAD_REQUEST)
            
            if None in (assigned_by, assigned_to):
                return Response({"error":"both assigned_to and assigned_by fields are required"},status=status.HTTP_400_BAD_REQUEST)
            
            try:
                test_codes = [code.strip() for code in test_codes.split(",")]  # Strip and split test codes once
                logger.info(f"<<<<< test_codes : {test_codes} >>>")

                tests = Test.objects.filter(tenant_id=request.tenant.uid, deleted=False, test_code__in=test_codes)

                for test in tests:
                    current_assigned_to = set(test.assigned_to.split(",")) if test.assigned_to else set()
                    current_assigned_to.add(assigned_to)
                    test.assigned_to = ",".join(current_assigned_to)  # Convert back to string
                    test.assigned_by = assigned_by
 
                Test.objects.bulk_update(tests,['assigned_to','assigned_by']) # to bulk update test

            except Exception as e:
                logger.exception(e)
                return Response({"error":f"Failed to assign test {test_codes} to {assigned_to}: {e}"},status=status.HTTP_400_BAD_REQUEST)
            
            
            return Response({"msg":"successfully assigned"})
            
        except Exception as e:
            logger.exception(e)
            return Response({"error":f"something went wrong : {e.args}"},status=status.HTTP_400_BAD_REQUEST)


    @action(methods=['GET'],detail=False, url_path="get-tests-by-filter")
    def get_tests_by_filter(self, request, *args, **kwargs):
        """
        This function retrieves tests based on the provided filter parameters.

        Parameters:
        request (Request): The request object containing the query parameters.
        *args, **kwargs: Additional arguments and keyword arguments.

        Returns:
        Response: A response object containing a list of tests that match the filter parameters.
        If an exception occurs during the retrieval process, it returns a response with an error message.

        Raises:
        Exception: If any error occurs during the retrieval process.
        """
        try:
            filter_params = request.query_params.dict()
            # code to fetch all tests with filter_params
            tests = Test.objects.filter(**filter_params, tenant_id=request.tenant.uid, deleted=False).values("test_code", "title", "description","test_type",'client_name')
            return Response(list(tests), status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Failed to fetch tests by filter : {e}")
            return Response({"error": f"Failed to fetch tests by filter : {e.args}"}, status=status.HTTP_400_BAD_REQUEST)
        

    @action(methods=['GET'],detail=False, url_path="get-test-user-config")
    def get_test_user_config(self, request, *args, **kwargs):
        
        try:

            user_id = self.request.query_params.get('user_id')
            test_code = self.request.query_params.get('test_code')

            if not user_id and not test_code:
                return Response({'error': f"user_id and test_code is required!"}, status=status.HTTP_400_BAD_REQUEST)

            config = UserTestConfigs.objects.filter(
                tenant_id = self.request.tenant.uid,
                user_id= user_id.strip(),
                test_code= test_code.strip(),

            )
            return Response( config, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Failed to fetch test_user_config : {e}")
            return Response({"error": f"Failed to fetch test_user_config : {e.args}"}, status=status.HTTP_400_BAD_REQUEST)
        