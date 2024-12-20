from google.cloud import speech
import os
from pathlib import Path
import logging
from commons.timeit import timeit

import vertexai
from vertexai.language_models import TextGenerationModel
import time
import random
import re

from google.cloud import texttospeech

from vertexai.generative_models import GenerativeModel, Content, Part, SafetySetting
from vertexai import generative_models

from google.api_core.exceptions import ResourceExhausted, TooManyRequests 
from commons.notifications import send_error_notification

logger = logging.getLogger(__name__)


def remove_garbage_characters(text):
    return text.replace("*","").replace("#","").replace(">","").replace("<","")


def get_uri(url):
    """to get uri form url 
        url: string
    """

    uri = url.split("https://storage.googleapis.com/")[1]
    uri = uri.split('?')[0]
    uri = "gs://"+uri
    return uri

@timeit
def speech_to_text(url):
    """
    Convert speech from a given URL into text using the Google Cloud Speech-to-Text API.

    Args:
        url (str): The URL of the audio file to be transcribed.

    Returns:
        str: The transcribed text from the audio file.

    Raises:
        Exception: If the Google speech to text conversion fails.

    
    """
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
def text_bison_compeletion(prompt,model="text-bison@001"):
    """
    Generates text completions based on a given prompt using the TextGenerationModel from the vertexai.language_models module.

    Args:
        prompt (str): The prompt for text completion.

    Returns:
        str: The generated text completion based on the given prompt.

    Raises:
        Exception: If the maximum number of retries is reached and text generation still fails.
    """
    max_retry = 3
    retry = 0
    os.chdir(f"{Path(__file__).resolve().parent}")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = 'bucketaccess.json'

    vertexai.init(project="summer-nucleus-397019", location="asia-south1")
    parameters = {
        "max_output_tokens": 1024,
        "temperature": 0.2,
        "top_p": 0.8,
        "top_k": 40
    }

    while True:
        try:
            logger.info({"**** text_bison_compeletion":f"trying text_bison_compeletion for {retry} time"})
            model = TextGenerationModel.from_pretrained(model)
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
    """
    Converts the given text into speech using the Google Cloud Text-to-Speech API.

    Args:
        text (str): The text to be converted into speech.

    Returns:
        google.cloud.texttospeech.types.SynthesizeSpeechResponse: The response object from the Google Cloud Text-to-Speech API, which contains the synthesized speech in the specified audio encoding.

    Raises:
        Exception: If the conversion fails.

    """
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
    

def gemini_competions(prompt):
    import requests
    import json
    max_retry = 3
    retry = 0

    while True:
        try:
            logger.info({"**** gemini":f"trying gemini for {retry} time"})
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.0-pro:generateContent?key=AIzaSyBfhB_y-hjwnqpVfVuC8ctvKy4gyiTesKo"

            payload = json.dumps({
            "contents": [
                {
                "parts": [
                    {
                    "text": prompt
                    }
                ]
                }
            ]
            })
            headers = {
            'Content-Type': 'application/json'
            }

            response = requests.request("POST", url, headers=headers, data=payload)
            print(response)
            print(response.json())
            return response.json().get('candidates')[0].get("content").get("parts")[0].get("text")

        
        except Exception as e:
            logger.error({"****gemini ":f"failed gemini for {retry} time"})
            logger.exception('Error communicating with gemini err: %s', e)

            retry += 1
            if retry >= max_retry:
                raise e

            time.sleep(random.randint(1,3))

    
@timeit
def gemini_completion(prompt,max_output_tokens=8192,temperature=0.9,top_p=1,models=["gemini-1.5-flash-001","gemini-1.5-pro-001","gemini-1.0-pro"],instruction=None):
    logger.info(f"gemini_completion prompt: {prompt}, and \nmodels: {models} adn \n instruction: {instruction}")
    os.chdir(f"{Path(__file__).resolve().parent}")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r'bucketaccess.json'
    vertexai.init(project="summer-nucleus-397019", location="asia-south1")
    
    generation_config={
        "max_output_tokens": max_output_tokens,
        "temperature": temperature,
        "top_p": top_p
    }

    max_retry = 3
    for model_name in models:
        model = GenerativeModel(model_name=model_name,system_instruction=[instruction] if instruction else None)
        retry = 0
        
        while retry < max_retry:
            try:
                logger.info(f"{'='*50}")
                logger.info(f"Trying gemini_completion with model {model_name} for {retry+1} time")
                responses = model.generate_content(
                    [prompt],
                    generation_config=generation_config,
                )
                logger.info(f"<<<<<<<<< gemini completion response: {responses} >>>>>>>>>>>>>")
                logger.info(f"gemini completion text: {responses.candidates[0].content.parts[0].text}")
                return responses.candidates[0].content.parts[0].text
            
            except (ResourceExhausted, TooManyRequests) as e:
                logger.exception(f"Resource exchausted or 429 error occured. :{e}")
                send_error_notification(f"gemini-completion-{model_name}","Qouta Exceeded", e.args)
                break
            except IndexError as e:
                logger.error(f"gemini_completion failed with list index out of range error: {e}", exc_info=True)
                break  # Exit the loop to try the next model
            except Exception as e:
                logger.error(f"gemini_completion failed with {e}", exc_info=True)
                retry += 1
                if retry >= max_retry:
                    break  # Exit the loop to try the next model
                time.sleep(random.randint(1, 3))
    
    raise Exception("All models failed to generate a response.")


@timeit
def gemini_chat_completion(prompt,previous_conv:list,max_output_tokens=8192,temperature=0.9,top_p=1,top_k=1,models=["gemini-1.5-flash-001","gemini-1.5-pro-001","gemini-1.0-pro"],instructions=None):
    logger.info(f"gemini_chat_completion prompt: {prompt}, and \nmodels: {models}")
    os.chdir(f"{Path(__file__).resolve().parent}")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r'bucketaccess.json'
    vertexai.init(project="summer-nucleus-397019", location="asia-south1")
    
    generation_config={
        "max_output_tokens": max_output_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k
    }



    # Set up the model
    # generation_config = {
    # "temperature": 0.9,
    # "top_p": 1,
    # "top_k": 1,
    # "max_output_tokens": 2048,
    # }
    safety_settings = [
        SafetySetting(category='HARM_CATEGORY_HARASSMENT', threshold='BLOCK_MEDIUM_AND_ABOVE')
    ]

    # to add pdf in chat
    # document1_1 = Part.from_data(
    # mime_type="application/pdf",
    # data=base64.b64decode(encode_pdf_to_base64('Influent - The psychology of Persuasion - Robert B.Cialdini.pdf'))
    # )
    
    history = [ 
        Content(role='user',parts=[Part.from_text(prompt)])
    ]
    current_user_response = previous_conv.pop()['text']
    print(current_user_response,previous_conv)

    for conv in previous_conv:
        history.append(Content(role=conv['role'],parts=[Part.from_text(conv['text'])]))
    max_retry = 3
    for model_name in models:
        model = GenerativeModel(model_name=model_name,
                                generation_config=generation_config,
                                safety_settings=safety_settings,
                                system_instruction=instructions
                                )
        chat = model.start_chat(history=history)
        
        retry = 0
        
        while retry < max_retry:
            try:
                logger.info(f"{'='*50}")
                logger.info(f"Trying gemini_chat_completion with model {model_name} for {retry+1} time")
                responses = chat.send_message(current_user_response)

                logger.info(f"<<<<<<<<< gemini chat completion response: {responses} >>>>>>>>>>>>>")
                logger.info(f"gemini chat completion text: {responses.text}")
                logger.info(f'Chat Gemini: {chat.history}')
                return responses.candidates[0].content.parts[0].text.strip()
                # return responses.text
            
            except (ResourceExhausted, TooManyRequests) as e:
                logger.exception(f"Resource exchausted or 429 error occured. :{e}")
                send_error_notification(f"gemini-chat-completion-{model_name}","Qouta Exceeded", e.args)
                break
            except IndexError as e:
                logger.error(f"gemini_chat_completion failed with list index out of range error: {e}", exc_info=True)
                break  # Exit the loop to try the next model
            except Exception as e:
                logger.error(f"gemini_chat_completion failed with {e}", exc_info=True)
                retry += 1
                if retry >= max_retry:
                    break  # Exit the loop to try the next model
                time.sleep(random.randint(1, 3))
    
    raise Exception("All models failed to generate a response.")

