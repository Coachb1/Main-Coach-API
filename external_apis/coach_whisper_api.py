from django.conf import settings

from commons.http_apis import HTTPHelper
from commons.timeit import timeit
from external_apis.slack_alert_api import send_slack_message


class CoachWhisperApi(object):
    http_helper = HTTPHelper(base_url=settings.COACH_WHISPER_BASE_URL)

    @timeit
    def get_transcribe_from_audio(self, file_url) -> str:
        try:
            response = self._get_transcribe_from_audio(file_url)
            if not response:
                raise ValueError("empty transcript received")
        except Exception as e:
            send_slack_message({"process": "get_transcribe_from_audio", "file_url": file_url, "error": str(e)})
            raise e

        return response

    def _get_transcribe_from_audio(self, file_url) -> str:
        url = self.http_helper.get_url("transcribe/")

        response = self.http_helper.post(
            url=url,
            json={
                "file_url": file_url
            }
        )

        return response.json().get("text")

    @timeit
    def get_transcribe_from_video(self, file_url) -> str:
        try:
            response = self._get_transcribe_from_video(file_url)
            if not response:
                raise ValueError("empty transcript received")
        except Exception as e:
            send_slack_message({"process": "get_transcribe_from_video", "file_url": file_url, "error": str(e)})
            raise e

        return response

    def _get_transcribe_from_video(self, file_url) -> str:
        url = self.http_helper.get_url("transcribe/video/")

        response = self.http_helper.post(
            url=url,
            json={
                "file_url": file_url
            }
        )

        return response.json().get("text")


coach_whisper_api = CoachWhisperApi()
