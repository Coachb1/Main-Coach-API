import requests
import json

from django.conf import settings

from commons.http_apis import HTTPHelper
from commons.timeit import timeit
from external_apis.slack_alert_api import send_slack_message


class CoachMetricApi(object):
    http_helper = HTTPHelper(base_url=settings.COACH_METRIC_BASE_URL)

    @timeit
    def get_speech_metrics_from_audio(self, file_url,transcript):
        try:
            response = self._get_speech_metrics_from_audio(file_url,transcript)
            if not response:
                raise ValueError("empty speech metrics received")
        except Exception as e:
            send_slack_message({"file_url": file_url, "error": str(e)})
            raise e

        return response

    def _get_speech_metrics_from_audio(self, file_url,transcript):
        url = self.http_helper.get_url("metrics/audio/")

        response = self.http_helper.post(
            url=url,
            json={
                "file_url": file_url,
                "transcript": transcript
            }
        )

        return response.json()

    @timeit
    def get_speech_metrics_from_video(self, file_url,transcript):
        try:
            response = self._get_speech_metrics_from_video(file_url,transcript)
            if not response:
                raise ValueError("empty speech metrics received")
        except Exception as e:
            send_slack_message({"file_url": file_url, "error": str(e)})
            raise e

        return response

    def _get_speech_metrics_from_video(self, file_url,transcript):
        url = self.http_helper.get_url("metrics/video/")

        response = self.http_helper.post(
            url=url,
            json={
                "file_url": file_url,
                "transcript": transcript
            }
        )

        return response.json()


coach_metric_api = CoachMetricApi()
