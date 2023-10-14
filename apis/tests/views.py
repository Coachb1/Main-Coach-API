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
from tests.helpers import create_test, get_test_report, generate_test_from_objective_anthropic
from tests.models import Test
from users.permissions import IsAuthenticatedUser
from learner_path.helpers import get_learner_path
from email_sender.helpers import send_learner_path_email
from users.models import User, UserAttribute
from utilities.models import SpecialTypeTests
from django.db.models import Q

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
        all_skills_qs = Test.objects.filter(tenant_id=tenant_id).values_list('skills_to_evaluate')
        all_skills = set()
        for skills in all_skills_qs:
            if skills[0]:
                all_skills.update(skills[0].split(','))
                
        all_goals_qs = Test.objects.filter(tenant_id=tenant_id).values_list('goals')
        all_goals = set()
        for goals in all_goals_qs:
            if goals[0]:
                all_goals.update(goals[0].split(','))
        
        all_roles_qs = Test.objects.filter(tenant_id=tenant_id).values_list('candidate_type')
        all_roles = set()
        for roles in all_roles_qs:
            if roles[0]:
                all_roles.add(roles[0])
        
        all_courses_qs = Test.objects.filter(tenant_id=tenant_id).values_list('course')
        all_courses = set()
        for courses in all_courses_qs:
            if courses[0]:
                all_courses.add(courses[0])
        
        all_industry_qs = Test.objects.filter(tenant_id=tenant_id).values_list('industry')
        all_industry = set()
        for industry in all_industry_qs:
            if industry[0]:
                all_industry.add(industry[0])
        
        all_exp_level_qs = Test.objects.filter(tenant_id=tenant_id).values_list('exp_level')
        all_exp_level = set()
        for exp_level in all_exp_level_qs:
            if exp_level[0]:
                all_exp_level.add(exp_level[0])

        all_format_qs = Test.objects.filter(tenant_id=tenant_id).values_list('test_type')
        all_format = set()
        for format in all_format_qs:    
            if format[0]:
                all_format.add(format[0])


        data = {
            "skills": list(all_skills),
            "goals": list(all_goals),
            "role": list(all_roles),
            "course": list(all_courses),
            "industry": list(all_industry),
            "exp_level": list(all_exp_level),
            "format": list(all_format)
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
        format = request.query_params.get("tformat")
        page = request.query_params.get("page")

        logger.info(f"***********************Request received for get_tests_by_choice***********************{request.query_params}")
        logger.info({"skill": skill, "goal": goal, "role": role, "course": course, "industry": industry, "exp_level": exp_level, "format": format})

        try:
            tests = Test.objects.filter(tenant_id=tenant_id).order_by('title')

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
                if format is not None and format != '':
                    tests = tests.filter(test_type__icontains=format)

            if tests.count() == 0:
                tests = tests.filter(Q(skill__icontains=skill) | Q(goal__icontains=goal) | Q(role__icontains=role) | Q(course__icontains=course) | Q(industry__icontains=industry) | Q(exp_level__icontains=exp_level) | Q(format__icontains=format))
            
            
            
            

            data = []
            for test in tests:
                data.append({
                    "title": test.title,
                    "code" : test.test_code
                })

            if page is not None and page != '':
                page = int(page)
                data = data[(page-1)*10:page*10]

            return Response({"data": data, 'status': "ok"},status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception({"!!!!!!!!!!!Error!!!!!!!!!!!!": e})
            return Response({"data": [], 'status': "error"},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        # return Response({"status": "ok"},status=status.HTTP_200_OK)