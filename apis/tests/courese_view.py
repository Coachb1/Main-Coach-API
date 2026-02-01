

from ast import Module
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Max
from collections import defaultdict
import logging

from sqlalchemy import Identity

from apis.tests.serializers import CoursePackageSerializer, CourseSerializer, ModuleForLaterSerializer, ModuleLikeSerializer, ModuleProgressSerializer, UserProgressSerializer
from commons.viewset import ApiViewSet
from tests.helpers import merge_user_progress
from tests.models import Course, CoursePackage, ModuleForLater, ModuleLike, ModuleProgress, UserProgress
from users.models import ClientUserInfo, User
from drf_spectacular.utils import extend_schema, OpenApiResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, inline_serializer
from rest_framework import serializers

logger = logging.getLogger(__name__)


class CourseViewSet(ApiViewSet,
                  mixins.ListModelMixin,
                  mixins.RetrieveModelMixin,
                  mixins.UpdateModelMixin):
    """
    ViewSet for managing Courses and tracking user progress.

    Provides endpoints to list, retrieve, and update courses. It also includes
    actions for tracking user progress within courses and modules, managing
    course packages, and handling user interactions like 'likes' and
    'listen later' on modules.
    """

    queryset = Course.objects.all()
    serializer_class = CourseSerializer


    def _error_response(self, message, code=status.HTTP_400_BAD_REQUEST):
        """Helper to return consistent error responses."""
        return Response({"error": message}, status=code)

    @extend_schema(
        summary="Fetch course",
        description="Retrieve course details using course_uid.",
        parameters=[
            OpenApiParameter("course_uid", OpenApiTypes.STR, required=True),
        ],
        responses={
            200: OpenApiResponse(response=CourseSerializer(many=True)),
            400: OpenApiResponse(description="Missing course_uid"),
            404: OpenApiResponse(description="Course not found"),
        },
        tags=["Courses"],
    )
    @action(methods=["GET"], detail=False, url_path="fetch-course")
    def fetch_course(self, request, *args, **kwargs):
        """
        Fetch courses based on query parameters:
        - course_uid → Specific course
        - client_name → Courses linked to client
        - None → Courses without a client
        """
        course_uid = request.query_params.get("course_uid")

        try:
            if not course_uid:
                return self._error_response('course_uid required!', status.HTTP_400_BAD_REQUEST)

            courses = Course.objects.filter(uid=course_uid)
            
            if not courses.exists():
                return self._error_response("Course not found", status.HTTP_404_NOT_FOUND)

            serializer = self.get_serializer(courses, many=True)
            return Response({"courses": serializer.data}, status=status.HTTP_200_OK)

        except Exception as exc:
            logger.exception("Error in fetch_courses: %s", exc)
            return self._error_response("Unexpected server error", status.HTTP_500_INTERNAL_SERVER_ERROR)

    
    @extend_schema(
        methods=["GET"],
        summary="Get course progress",
        description="Fetch a user's progress for a specific course.",
        parameters=[
            OpenApiParameter("user_uid", OpenApiTypes.STR, required=True),
            OpenApiParameter("course_id", OpenApiTypes.STR, required=True),
        ],
        responses={200: UserProgressSerializer},
        tags=["Courses"],
    )
    @extend_schema(
        methods=["POST"],
        summary="Update module progress",
        description="Update progress for a module inside a course.",
        request=inline_serializer(
            name="UpdateModuleProgressRequest",
            fields={
                "user_uid": serializers.CharField(),
                "course_id": serializers.CharField(),
                "module": serializers.DictField(),
            },
        ),
        responses={200: UserProgressSerializer},
        tags=["Courses"],
    )
    @action(detail=False, methods=["GET", "POST"], url_path="course-progress")
    def get_progress(self, request):
        """
        Get a user's progress in a specific course.
        Requires: user_uid, course_id
        """

        if request.method == 'GET':
            user_uid = request.query_params.get("user_uid")
            course_id = request.query_params.get("course_id")

            if not user_uid or not course_id:
                return self._error_response('Both user_uid and course_id are required', status.HTTP_400_BAD_REQUEST)

            user = get_object_or_404(User, uid=user_uid)
            course = get_object_or_404(Course, uid=course_id)

            progress, created = UserProgress.objects.get_or_create(user=user, course=course)

            serializer = UserProgressSerializer(progress)
            return Response(serializer.data, status=status.HTTP_200_OK)

        elif request.method == 'POST':
            user_uid = request.data.get("user_uid")
            course_id = request.data.get("course_id")
            module = request.data.get("module")

            module_id = module.get('module_id', None)
            status_value = module.get("status", "not_started")
            module_completion_percentage = module.get('completed_in_percentage', 0)
            played_audio = module.get('played_audio', None)  # <-- NEW
            logger.info(f" data: {request.data}, status= {status_value}, completion= {module_completion_percentage}")

            if not all([user_uid, course_id, module_id, status_value]):
                return Response(
                    {"error": "user_uid, course_id, module_id, and status are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            if status_value not in ['in_progress', 'completed']:
                return self._error_response("status must be within ['in_progress', 'completed']", status.HTTP_400_BAD_REQUEST)

            user = get_object_or_404(User, uid=user_uid)
            course = get_object_or_404(Course, uid=course_id)
            module = get_object_or_404(Module, uid=module_id, course=course)

            user_progress, _ = UserProgress.objects.get_or_create(user=user, course=course)

            module_progress, _ = ModuleProgress.objects.get_or_create(
                user_progress=user_progress, module=module
            )

            # Update status & timestamps
            update_fields = []

            if module_progress.status != 'completed':
                module_progress.status = status_value
                update_fields.append('status')

            if status_value == "in_progress" and not module_progress.start_time:
                module_progress.start_time = timezone.now()
                update_fields.append('start_time')
            if status_value == "completed" and not module_progress.end_time:
                module_progress.end_time = timezone.now()
                update_fields.append('end_time')

            if module_completion_percentage is not None:
                module_progress.completed_in_percentage = module_completion_percentage
                update_fields.append('completed_in_percentage')

            if played_audio is not None:  # <-- NEW
                module_progress.played_audio = played_audio
                update_fields.append('played_audio')
                
            logger.info(f"updated_fields: {update_fields}, {module_progress.start_time}")
            module_progress.save(update_fields=update_fields)

            # Auto-update course-level completion
            all_completed = user_progress.module_progress.filter(
                status="completed"
            ).count() == course.modules.count()
            user_progress.modules_completed = all_completed
            if all_completed:
                user_progress.end_time = timezone.now()
            user_progress.save()

            serializer = UserProgressSerializer(user_progress)
            return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Get course package",
        description="Retrieve course package data with optional user progress merge.",
        parameters=[
            OpenApiParameter("package_id", OpenApiTypes.STR, required=True),
            OpenApiParameter("client_name", OpenApiTypes.STR),
            OpenApiParameter("user_id_for_progress", OpenApiTypes.STR),
        ],
        responses={200: OpenApiResponse(description="Package data with optional progress")},
        tags=["Courses"],
    )
    @action(detail=False, methods=["GET"], url_path="course-package")
    def get_course_package(self, request):

        package_id = request.query_params.get("package_id")
        client_name = request.query_params.get("client_name")
        user_id = request.query_params.get('user_id_for_progress')
        if not package_id:
            return Response(
                {"error": "package_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        client = None
        if client_name:
            client = ClientUserInfo.objects.filter(
                name__iexact=client_name
            ).first()
            if not client:
                return self._error_response("Client not found", status.HTTP_404_NOT_FOUND)

            

        package = get_object_or_404(
            CoursePackage, uid=package_id, deleted=False
        )

        serializer = CoursePackageSerializer(package).data

        data = {
            "package_data": serializer
        }
        
        if user_id:
            user = get_object_or_404(User, uid=user_id, deleted=False)
            courses = package.courses.all()

            progress = UserProgress.objects.filter(user=user, course__in=courses)

            progress_serializer = UserProgressSerializer(progress, many=True).data
            data['package_data'] = merge_user_progress(serializer, progress_serializer)


        return Response(data['package_data'], status=status.HTTP_200_OK)

    @extend_schema(
        summary="Get module progress for user",
        parameters=[
            OpenApiParameter("module_id", OpenApiTypes.STR, required=True),
            OpenApiParameter("user_id", OpenApiTypes.STR, required=True),
        ],
        responses={200: ModuleProgressSerializer},
        tags=["Course Modules"],
    )
    @action(detail=False, methods=["GET"], url_path="module-user-data")
    def get_module(self, request):
        try: 
            module_id = request.query_params.get('module_id')
            user_id = request.query_params.get('user_id')
            if not module_id or not user_id:
                return Response(
                    {"error": "module_id and user_id are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user = get_object_or_404(User, uid=user_id, deleted=False)
            module = get_object_or_404(Module, uid=module_id, deleted=False)
            progress = ModuleProgress.objects.filter(user_progress__user=user, module=module).first()
            serializer = ModuleProgressSerializer(progress)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"failed to call [module-user-data], {e}")
            return Response({'error': f"failed to call [module-user-data], {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _get_user_and_module(self, request, module_id, from_query=False):
        """Helper to fetch user and module"""
        user_id = request.query_params.get("user_id") if from_query else request.data.get("user_id")
        if not user_id:
            raise ValidationError({"error": "user_id is required"})

        user = get_object_or_404(User, uid=user_id, deleted=False)
        module = get_object_or_404(Module, uid=module_id)
        return user, module

    # ---------- MODULE LIKE ----------

    @extend_schema(
        methods=["GET"],
        summary="Check module like",
        parameters=[
            OpenApiParameter("user_id", OpenApiTypes.STR),
            OpenApiParameter("client_only_likes", OpenApiTypes.BOOL),
        ],
        responses={200: OpenApiResponse(description="Like status / total likes")},
        tags=["Course Modules"],
    )
    @extend_schema(
        methods=["POST"],
        summary="Toggle module like",
        request=inline_serializer(
            name="ModuleLikeRequest",
            fields={
                "user_id": serializers.CharField(required=False),
                "likes": serializers.IntegerField(required=False),
                "client_only_likes": serializers.BooleanField(required=False),
            },
        ),
        responses={
            200: OpenApiResponse(description="Unliked / total likes updated"),
            201: ModuleLikeSerializer,
        },
        tags=["Course Modules"],
    )
    @action(detail=False, methods=["get", "post"], url_path=r"modules/(?P<module_id>[^/.]+)/like")
    def module_like(self, request, module_id=None):
        """
        GET  -> Check if user liked the module
        POST -> Toggle like (like/unlike)
        """
        if request.method == "GET":
            client_only_likes = request.query_params.get("client_only_likes", False) # here we will increase decrease total_like  not user specific like
            if client_only_likes:
                # If client_only_likes is True, we return total likes for the module
                module = get_object_or_404(Module, uid=module_id)
                progress = ModuleProgress.objects.filter(module=module).first()
                if not progress:
                    return Response({"total_likes": 0}, status=status.HTTP_200_OK)
                return Response({"total_likes": progress.total_likes}, status=status.HTTP_200_OK)
            user, module = self._get_user_and_module(request, module_id, from_query=True)
            like = ModuleLike.objects.filter(module=module, user=user).first()
            if not like:
                return Response({"liked": False}, status=status.HTTP_200_OK)
            return Response(ModuleLikeSerializer(like).data, status=status.HTTP_200_OK)

        elif request.method == "POST":
            client_only_likes = request.data.get("client_only_likes", False) # True for module-wide likes, False for user-specific likes
            likes = request.data.get("likes", 1) # 1 for like, -1 for unlike            
            if client_only_likes:
                module = get_object_or_404(Module, uid=module_id)
                module.total_likes = max(0, module.total_likes + likes)
                module.save(update_fields=['total_likes'])
                return Response({"message": "Total likes updated"}, status=status.HTTP_200_OK)
            
            user, module = self._get_user_and_module(request, module_id)
            like, created = ModuleLike.objects.get_or_create(user=user, module=module)
            if not created:
                like.delete()
                return Response({"message": "Unliked"}, status=status.HTTP_200_OK)
            return Response(ModuleLikeSerializer(like).data, status=status.HTTP_201_CREATED)

    # ---------- LISTEN LATER ----------
    @extend_schema(
        methods=["GET"],
        summary="Check listen later status",
        parameters=[OpenApiParameter("user_id", OpenApiTypes.STR, required=True)],
        responses={200: ModuleForLaterSerializer},
        tags=["Course Modules"],
    )
    @extend_schema(
        methods=["POST"],
        summary="Toggle listen later",
        request=inline_serializer(
            name="ListenLaterRequest",
            fields={"user_id": serializers.CharField()},
        ),
        responses={200: OpenApiResponse(description="Removed"), 201: ModuleForLaterSerializer},
        tags=["Course Modules"],
    )
    @action(detail=False, methods=["get", "post"], url_path=r"modules/(?P<module_id>[^/.]+)/later")
    def listen_later(self, request, module_id=None):
        """
        GET  -> Check if module is in Listen Later
        POST -> Toggle Listen Later (save/remove)
        """
        if request.method == "GET":
            user, _ = self._get_user_and_module(request, module_id, from_query=True)
            entry = ModuleForLater.objects.filter(user=user, module__uid=module_id).first()
            if not entry:
                return Response({"saved": False}, status=status.HTTP_200_OK)
            return Response(ModuleForLaterSerializer(entry).data, status=status.HTTP_200_OK)

        elif request.method == "POST":
            user, module = self._get_user_and_module(request, module_id)
            entry, created = ModuleForLater.objects.get_or_create(user=user, module=module)
            if not created:
                entry.delete()
                return Response({"message": "Removed from Listen Later"}, status=status.HTTP_200_OK)
            return Response(ModuleForLaterSerializer(entry).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Get liked & saved modules",
        parameters=[
            OpenApiParameter("course_id", OpenApiTypes.STR, required=True),
            OpenApiParameter("user_id", OpenApiTypes.STR, required=True),
        ],
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    name="LikedLaterResponse",
                    fields={
                        "liked": ModuleLikeSerializer(many=True),
                        "later": ModuleForLaterSerializer(many=True),
                    },
                )
            )
        },
        tags=["Course Modules"],
    )
    @action(detail=False, methods=["GET"], url_path=r"get-liked-and-for-later-modules")
    def get_liked_and_later_modules(self, request):
        try:
            course_id = request.query_params.get("course_id")
            user_id = request.query_params.get("user_id")

            if not course_id or not user_id:
                return Response(
                    {"error": "course_id and user_id are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            course = get_object_or_404(Course, uid=course_id, deleted=False)
            user = get_object_or_404(User, uid=user_id, deleted=False)
            liked = ModuleLike.objects.filter(user=user, module__course=course)
            later = ModuleForLater.objects.filter(user=user, module__course=course)

            return Response({"liked": ModuleLikeSerializer(liked, many=True).data, "later": ModuleForLaterSerializer(later, many=True).data}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching liked and saved modules: {e}")
            return Response({"error": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(
        summary="Course leaderboard report",
        description="Returns ranked progress report for users in a course package.",
        parameters=[
            OpenApiParameter("package_course_id", OpenApiTypes.STR, required=True),
            OpenApiParameter("client_id", OpenApiTypes.STR),
        ],
        responses={200: OpenApiResponse(description="Paginated leaderboard report")},
        tags=["Course Reports"],
    )
    @action(detail=False, methods=["get"], url_path="course-report")
    def report(self, request):
        """
        Returns paginated report: name, email (via get_email), completed module names,
        last activity, and rank — filtered by course package and optional client_id.
        """

        package_course_id = request.query_params.get("package_course_id")
        client_id = request.query_params.get("client_id")

        if not package_course_id:
            return Response(
                {"error": "package_course_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        course_package = get_object_or_404(
            CoursePackage, uid=package_course_id, deleted=False
        )

        # Base queryset
        progresses = ModuleProgress.objects.filter(
            user_progress__course__packages=course_package
        ).select_related(
            "user_progress__user", "module"
        ).annotate(
            last_activity=Max("end_time")
        )

        # Build map
        report_map = {}
        for progress in progresses:
            user = progress.user_progress.user
            uid = user.id
            if client_id:
                    user_client = progress.user_progress.user.get_client()
                    if not user_client or str(user_client.uid) != str(client_id):
                        continue  # Skip users belonging to another client
            if uid not in report_map:
                report_map[uid] = {
                    "id": uid,
                    "name": user.name,
                    "email": user.get_email(),
                    "completed_modules": set(),
                    "last_activity": progress.last_activity,
                }

            if progress.status == "completed":
                report_map[uid]["completed_modules"].add(progress.module.title)

            if progress.last_activity and (
                not report_map[uid]["last_activity"]
                or progress.last_activity > report_map[uid]["last_activity"]
            ):
                report_map[uid]["last_activity"] = progress.last_activity

        # List + ranking
        report_data = []
        for user_data in report_map.values():
            report_data.append(
                {
                    "id": user_data["id"],
                    "name": user_data["name"],
                    "email": user_data["email"],
                    "completed_modules": ", ".join(user_data["completed_modules"]),
                    "last_activity": user_data["last_activity"],
                    "module_count": len(user_data["completed_modules"]),
                }
            )

        report_data.sort(key=lambda x: x["module_count"], reverse=True)

        current_rank = 1
        previous_count = None
        for idx, user in enumerate(report_data):
            if previous_count is None or user["module_count"] < previous_count:
                current_rank = idx + 1
            user["rank"] = current_rank
            previous_count = user["module_count"]
            del user["module_count"]

        # Pagination
        page = self.paginate_queryset(report_data)
        if page is not None:
            return self.get_paginated_response(page)

        return Response(report_data)

    @extend_schema(
        summary="AI Pulse report",
        description="Returns module demand analytics per client.",
        parameters=[
            OpenApiParameter("package_course_id", OpenApiTypes.STR, required=True),
            OpenApiParameter("client_name", OpenApiTypes.STR, required=True),
        ],
        responses={200: OpenApiResponse(description="AI Pulse data")},
        tags=["Course Reports"],
    )
    @action(methods=["GET"], detail=False, url_path="ai-pulse-report-data")
    def ai_pulse(self, request, *args, **kwargs):
        try:
            package_course_id = request.query_params.get("package_course_id")
            client_name = request.query_params.get("client_name")

            if not package_course_id or not client_name:
                return Response(
                    {"error": "package_course_id and client_name are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            client = get_object_or_404(ClientUserInfo, client_name=client_name.strip(),deleted=False).member_emails
            modules_data = []
            if  client:
                users_ids = list(Identity.objects.filter(deleted=False, value__in=[email.strip() for email in client.split(',') if email.strip()]).values_list('user_id', flat=True))
                users = User.objects.filter(uid__in=users_ids)
                package = get_object_or_404(
                                        CoursePackage, uid=package_course_id, deleted=False
                                    )
                # ✅ Get course list from the package properly
                courses = package.courses.all()

                # ✅ Get all "later" modules for all courses in the package
                later_modules = (
                    ModuleForLater.objects
                    .select_related("module", "user", "module__course")  # optimization
                    .filter(module__course__in=courses, user__in=users)
                )

                modules_data = defaultdict(lambda: {
                    "case": None,
                    "industry": None,
                    "function": None,
                    "businessOutcome": None,
                    "requestUsers": set(),
                })

                for lm in later_modules:
                    user_client = lm.user.get_client()
                    if not user_client or user_client.client_name != client_name:
                        continue  # Skip users from other clients

                    module = lm.module
                    uid = module.uid

                    modules_data[uid]["case"] = module.title
                    modules_data[uid]["industry"] = getattr(module, "tag", None)
                    modules_data[uid]["function"] = getattr(module, "function", None)
                    modules_data[uid]["businessOutcome"] = getattr(module, "business_outcome", None)

                    modules_data[uid]["requestUsers"].add(lm.user.get_email())

            # Convert to desired format
            data = []
            for module_info in modules_data.values():
                users = list(module_info["requestUsers"])
                data.append({
                    "case": module_info["case"],
                    "industry": module_info["industry"],
                    "function": module_info["function"],
                    "businessOutcome": module_info["businessOutcome"],
                    "discussionRequests": len(users),
                    "requestUsers": users
                })

            return Response({"data": data}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error in get_library_bot_actions_per_month: {e}")
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )