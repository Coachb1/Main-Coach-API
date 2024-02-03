import json
import logging

import requests
from django.conf import settings

from commons.threadlocal import get_trace_id

logger = logging.getLogger(__name__)


def send_slack_message(data):
    """
    Sends a message to a Slack channel using a webhook URL.

    Args:
        data (dict): A dictionary containing the message data to be sent to Slack.

    Raises:
        Exception: If an error occurs during the request.

    """
    url = settings.SLACK_MESSAGE_WEBHOOK_URL

    data.update({"trace_id":  get_trace_id() or "na", "env": settings.ENV})

    payload = json.dumps({
        "text": json.dumps(data, default=str)
    })

    headers = {
        'Content-type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    try:
        response.raise_for_status()
    except Exception as e:
        logger.exception("failed to send to slack data: %s, err: %s", data, str(e))
