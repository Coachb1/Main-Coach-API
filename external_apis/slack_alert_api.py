import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def send_slack_message(data):
    url = settings.SLACK_MESSAGE_WEBHOOK_URL

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
