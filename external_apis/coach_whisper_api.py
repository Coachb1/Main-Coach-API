from django.conf import settings

from commons.http_apis import HTTPHelper
from commons.timeit import timeit
from external_apis.slack_alert_api import send_slack_message


class CoachWhisperApi(object):
    """
    A class that interacts with the Coach Whisper API to transcribe audio and video files.

    This class uses the HTTPHelper utility to make HTTP requests to the Coach Whisper API. It provides methods to transcribe both audio and video files. The transcription process involves sending a POST request to the API with the file URL as a parameter. The API then returns a response containing the transcription text.

    Attributes:
        http_helper (HTTPHelper): An instance of the HTTPHelper class with the base URL set to the Coach Whisper API URL.

    Methods:
        get_transcribe_from_audio(file_url: str) -> str:
            Transcribes an audio file.

            Args:
                file_url (str): The URL of the audio file to be transcribed.

            Returns:
                str: The transcription text.

            Raises:
                ValueError: If the API returns an empty transcript.
                Exception: If any error occurs during the request. The error is also sent to a Slack channel.

        get_transcribe_from_video(file_url: str) -> str:
            Transcribes a video file.

            Args:
                file_url (str): The URL of the video file to be transcribed.

            Returns:
                str: The transcription text.

            Raises:
                ValueError: If the API returns an empty transcript.
                Exception: If any error occurs during the request. The error is also sent to a Slack channel.

    Example:
        coach_whisper_api = CoachWhisperApi()
        audio_transcript = coach_whisper_api.get_transcribe_from_audio('https://example.com/audio.mp3')
        video_transcript = coach_whisper_api.get_transcribe_from_video('https://example.com/video.mp4')
    """
    http_helper = HTTPHelper(base_url=settings.COACH_WHISPER_BASE_URL)

    @timeit
    def get_transcribe_from_audio(self, file_url) -> str:
        """
        Transcribes an audio file.

            Args:
                file_url (str): The URL of the audio file to be transcribed.

            Returns:
                str: The transcription text.

            Raises:
                ValueError: If the API returns an empty transcript.
                Exception: If any error occurs during the request. The error is also sent to a Slack channel.

        """
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
        """
        Transcribes a video file.

            Args:
                file_url (str): The URL of the video file to be transcribed.

            Returns:
                str: The transcription text.

            Raises:
                ValueError: If the API returns an empty transcript.
                Exception: If any error occurs during the request. The error is also sent to a Slack channel.

        """
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
