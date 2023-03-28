import logging

from commons.threadlocal import get_trace_id


class TraceIdFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = get_trace_id()
        return True
