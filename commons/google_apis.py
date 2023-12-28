from google.cloud import speech
import os
from pathlib import Path
import logging
from commons.timeit import timeit

import vertexai
from vertexai.language_models import TextGenerationModel
import time
import random

from google.cloud import texttospeech

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
    
@timeit
def text_bison_compeletion(prompt):

    max_retry = 3
    retry = 0
    os.chdir(f"{Path(__file__).resolve().parent}")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = 'bucketaccess.json'

    vertexai.init(project="summer-nucleus-397019", location="us-central1")
    parameters = {
        "max_output_tokens": 1024,
        "temperature": 0.2,
        "top_p": 0.8,
        "top_k": 40
    }

    while True:
        try:
            logger.info({"**** text_bison_compeletion":f"trying text_bison_compeletion for {retry} time"})
            model = TextGenerationModel.from_pretrained("text-bison@001")
            response = model.predict(
                prompt,
                **parameters
            )
            return response.text
        
        except Exception as e:
            logger.error({"****text_bison_compeletion ":f"failed text_bison_compeletion for {retry} time"})
            logger.exception('Error communicating with OpenAI err: %s', e)

            retry += 1
            if retry >= max_retry:
                raise e

            time.sleep(random.randint(1,3))

@timeit
def text_to_speech_google(text):

    try:
        os.chdir(f"{Path(__file__).resolve().parent}")
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = 'bucketaccess.json'
        client = texttospeech.TextToSpeechClient()

        input_text = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code='en-IN',
            name='en-IN-Neural2-A',
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        response = client.synthesize_speech(
            input=input_text,
            voice=voice,
            audio_config=audio_config
        )
        return response
    except Exception as e:
        logger.error(f"text_to_speech_google failed with {e}", exc_info=True)
        raise e