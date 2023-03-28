import logging
import uuid

from django.utils.deprecation import MiddlewareMixin

from commons.threadlocal import get_trace_id
from commons.threadlocal import set_trace_id

logger = logging.getLogger(__name__)


class LogRequestMiddleware(MiddlewareMixin):
    def process_request(self, request):
        trace_id = str(uuid.uuid4())
        set_trace_id(trace_id)

    def process_response(self, request, response):
        logger.info("request %s , response %s", request.path, response)
        response["x-trace-id"] = get_trace_id()
        return response
