from django.conf import settings

from commons.http_apis import HTTPHelper
from commons.timeit import timeit
from external_apis.slack_alert_api import send_slack_message


class CoachWhisperApi(object):
    http_helper = HTTPHelper(base_url=settings.COACH_WHISPER_BASE_URL)

    @timeit
    def get_transcribe_from_audio(self, audio_url) -> str:
        try:
            response = self._get_transcribe_from_audio(audio_url)
            if not response:
                raise ValueError("empty transcript received")
        except Exception as e:
            send_slack_message({"audio_url": audio_url, "error": str(e)})
            raise e

        return response

    def _get_transcribe_from_audio(self, audio_url) -> str:
        url = self.http_helper.get_url("transcribe/")

        response = self.http_helper.post(
            url=url,
            json={
                "file_url": audio_url
            }
        )

        return response.json().get("text")


coach_whisper_api = CoachWhisperApi()
