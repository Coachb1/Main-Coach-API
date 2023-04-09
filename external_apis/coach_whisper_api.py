from django.conf import settings

from commons.http_apis import HTTPHelper
from commons.timeit import timeit


class CoachWhisperApi(object):
    http_helper = HTTPHelper(base_url=settings.COACH_WHISPER_BASE_URL)

    @timeit
    def get_transcribe_from_audio(self, audio_url) -> str:
        url = self.http_helper.get_url("transcribe/")

        response = self.http_helper.post(
            url=url,
            json={
                "file_url": audio_url
            }
        )

        return response.json().get("text")


coach_whisper_api = CoachWhisperApi()
