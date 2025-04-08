import requests
import json

import settings

from commons.http_apis import HTTPHelper
from commons.timeit import timeit


class WhatsappApi(object):

    @timeit
    def send_whatsapp_report(self, phone_number, report_url, title):
        """
        Sends a WhatsApp report to a specified phone number.

        Args:
            phone_number (str): The phone number to which the WhatsApp report should be sent.
            report_url (str): The URL of the report that will be included in the WhatsApp message.
            title (str): The title of the report.

        Returns:
            requests.Response: The response object from the WhatsApp API request.
        
        
        """
        url = settings.WHATSAPP_API_BASE_URL
        api_key = settings.WHATSAPP_API_KEY

        headers = {"Content-Type": "application/json"}

        data = {
            "apiKey": api_key,
            "campaignName": "newtemplateforreport",
            "destination": phone_number,
            "userName": "Samarth",
            "templateParams": [
                title,
                report_url
            ]
        }

        response = requests.post(url, headers=headers, json=data)
        print(response.json())
        return response


whatsapp_api = WhatsappApi()
