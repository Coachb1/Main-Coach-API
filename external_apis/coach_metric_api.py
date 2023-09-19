import requests
import json

from django.conf import settings

from commons.http_apis import HTTPHelper
from commons.timeit import timeit
from external_apis.slack_alert_api import send_slack_message

default_metrics = {
                    'energy_grade': 4,
                    'fluency_grade': 5,
                    'confidence_grade': 3,
                    'pace': 150,
                    'sentiment_percentage': "30%",
                    'power_word_density': 0,
                    'filler_words_score': 0,
                    'volume': 50,
                    'silence_number': 1,
                    "pitch": 165.0,
                    "transcript": "Transcription couldn't be generated",
                    "energy_cohort": "C",
                    "silence_length": 0,
                    "people_quotient": 0.0,
                    "confidence_cohort": "C",
                    "energy_percentage": 50,
                    "filler_words_cohort": 0,
                    "confidence_percentage": 55.0,
                    "sales_quotient_percentile": 0.0,
                    "aggregate_energy_percentage": 45.0,
                    "learner_quotient_percentile": 0.0,
                    "manager_quotient_percentile": 0.0,
                    "aggregate_fluency_percentage": 75.0,
                    "leadership_quotient_percentile": 0.0,
                    "aggregate_confidence_percentage": 55.0,
                    "power_word_percentage": '20%',
                    "filler_word_percentage": "9%",
                    "fluency_percentage": "50%"
                }

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
