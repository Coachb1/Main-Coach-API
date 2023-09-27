from google.cloud import speech
import os
from pathlib import Path
import logging
from commons.timeit import timeit

logger = logging.getLogger(__name__)




def get_uri(url):
    # to get uri form url 

    uri = url.split("https://storage.googleapis.com/")[1]
    uri = uri.split('?')[0]
    uri = "gs://"+uri
    return uri

@timeit
def speech_to_text(url):
    try:
        os.chdir(f"{Path(__file__).resolve().parent}")
        client = speech.SpeechClient.from_service_account_file(r'bucketaccess.json')
        uri = get_uri(url)

        audio = speech.RecognitionAudio(uri = uri)
        config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
        sample_rate_hertz=16000,  
        language_code="en-US",   
        enable_automatic_punctuation=True
            )
        # Perform the speech-to-text conversion
        # audio_text = client.long_running_recognize(config=config, audio=audio)
        operation = client.long_running_recognize(config=config, audio=audio)

        logger.info("Waiting for operation to complete...")
        response = operation.result(timeout=90)

        transcript_builder = []
        # Each result is for a consecutive portion of the audio. Iterate through
        # them to get the transcripts for the entire audio file.
        for result in response.results:
            # The first alternative is the most likely one for this portion.
            transcript_builder.append(f"{result.alternatives[0].transcript}")

        transcript = "".join(transcript_builder)
        logger.info({"getting transcript sucessfull Transcript:": transcript})

        return transcript
        
    except Exception as e :
        logger.error({"Google speech to text failed with error": e})
        raise e