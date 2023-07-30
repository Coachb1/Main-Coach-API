import requests
import json

import settings

from commons.http_apis import HTTPHelper
from commons.timeit import timeit


class WhatsappApi(object):

    @timeit
    def send_whatsapp_report(self, phone_number, report_url):
        url = settings.WHATSAPP_API_BASE_URL
        api_key = settings.WHATSAPP_API_KEY

        headers = {"Content-Type": "application/json"}

        data = {
            "apiKey": api_key,
            "campaignName": "Feedback Report Link",
            "destination": phone_number,
            "userName": "Samarth",
            "templateParams": [
                report_url
            ]
        }

        response = requests.post(url, headers=headers, json=data)
        return response


whatsapp_api = WhatsappApi()
