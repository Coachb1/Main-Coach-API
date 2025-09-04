import dataclasses
import logging
import re
import time
import os

import openai
import tiktoken
from django.conf import settings

from commons.timeit import timeit

import requests
import tempfile
import random
from commons.notifications import send_error_notification

logger = logging.getLogger(__name__)

openai.api_key = settings.OPENAI_API_KEY

gpt2encoding = tiktoken.get_encoding("p50k_base")


@dataclasses.dataclass
class GPTResponse:
    raw: dict
    text: str


def num_tokens_for_prompt(prompt: str):
    return len(gpt2encoding.encode(prompt))


def gpt3_embedding(content, engine='text-embedding-ada-002'):
    content = content.encode(encoding='ASCII', errors='ignore').decode()
    response = openai.embeddings.create(input=content, engine=engine)
    vector = response['data'][0]['embedding']
    return vector


@timeit
def gpt3_completion(prompt,
                    stop,
                    engine='gpt-4-turbo',
                    temp=0,
                    top_p=1.0,
                    max_tokens=4000,
                    freq_pen=0.0,
                    pres_pen=0.0) -> GPTResponse:
    """
    Generates text completions based on a given prompt using the OpenAI API.

    Args:
        prompt (str): The initial text prompt for generating completions.
        stop (str): The stop condition that determines when to stop generating text.
        engine (str, optional): The engine to use for text generation (default is 'text-davinci-003').
        temp (float, optional): The temperature parameter for controlling the randomness of the generated text (default is 0).
        top_p (float, optional): The top-p parameter for controlling the diversity of the generated text (default is 1.0).
        max_tokens (int, optional): The maximum number of tokens to generate (default is 4000).
        freq_pen (float, optional): The frequency penalty for discouraging repetitive completions (default is 0.0).
        pres_pen (float, optional): The presence penalty for discouraging completions that don't match the prompt (default is 0.0).

    Returns:
        GPTResponse: An object containing the raw API response and the generated text.
    """
    logger.info(f"prompt: {prompt}")
    prompt_tokens = num_tokens_for_prompt(prompt)
    max_retry = 3
    retry = 0
    prompt = prompt.encode(encoding='ASCII', errors='ignore').decode()
    is_error_noti_sent = False
    if isinstance(engine, str):
        engine = [model.strip() for model in engine.split(',')]

    while True:
        for model in engine:
            try:
                logger.info({"**** gpt3_completion":f"trying gpt for {retry} time for {model}"})
                try:
                    response = openai.chat.completions.create(
                        model=model,
                        messages=[{
                        "role": "user",
                        "content": [
                            {
                            "type": "text",
                            "text": prompt
                            }
                        ]
                        }],
                        temperature=temp,
                        max_tokens=max_tokens - prompt_tokens,
                        top_p=top_p,
                        frequency_penalty=freq_pen,
                        presence_penalty=pres_pen,
                        stop=stop)
                except Exception as e:
                    logger.exception(f"{e}")
                    response = openai.chat.completions.create(
                    model=engine,
                    messages=[{
                    "role": "user",
                    "content": [
                        {
                        "type": "text",
                        "text": prompt
                        }
                    ]
                    }],
                    stop=stop)
                text = response.choices[0].message.content.strip()
                text = re.sub('[\r\n]+', '\n', text)
                text = re.sub('[\t ]+', ' ', text)

                logger.info(f"text: {text}")
                return GPTResponse(raw=response.to_json(), text=text)
            
            except openai.RateLimitError as e:
                logger.error({"****gpt3_completion ":f"failed gpt for {retry} time reason 429"})
                logger.exception('Error communicating with OpenAI err: %s', e)

                if not is_error_noti_sent:
                    send_error_notification("gpt completion", "429 error occured", e.args)
                    is_error_noti_sent = True

                retry += 1
                if retry >= max_retry:
                    raise e

                time.sleep(random.randint(1,3))
                
            except Exception as e:
                logger.error({"****gpt3_completion ":f"failed gpt for {retry} time"})
                logger.exception('Error communicating with OpenAI err: %s', e)

                retry += 1
                if retry >= max_retry:
                    raise e

                time.sleep(random.randint(1,3))




@timeit
def gpt_wishper_api(url):
    """
    Transcribes the audio file located at the specified URL and returns the transcribed text.

    Args:
        url (str): The URL of the audio file to be transcribed.

    Returns:
        str: The transcribed text from the audio file.

    Raises:
        Exception: If an error occurs during the transcription process.
    """
    file_path = ""
    try:
        response = requests.get(url)
        audio_data = response.content
        text = ''
        formats = ['.flac', '.m4a', '.mp3', '.mp4', '.mpeg', '.mpga', '.oga', '.ogg', '.wav', '.webm']
        # Find first matching suffix
        suffix = next((fmt for fmt in formats if fmt in url.lower()), None)

        if suffix:
            print(f"Detected format: {suffix}")
        else:
            print("No matching format found in URL, defaulting to .mp4")
            suffix = '.mp4'
        random_string = ''.join(
            [str(random.choice(['A','B','C','D',1,2,3,4,5,6,7,8,9])) for _ in range(6)]
            )
        file_path = f"audio_file_wishper_{random_string}{suffix}"
        with open(file_path,'wb') as temp_file:
            # Write the audio data to the temporary file
            temp_file.write(audio_data)
            temp_file.seek(0)
            # transcription = openai.audio.transcriptions.create(model="whisper-1", file=temp_file, language="en")
            # text = transcription['text']
            # print(text)

        with open(file_path, 'rb') as f:
            transcription = openai.audio.transcriptions.create(model="whisper-1", file=f, language="en")
            text = transcription.text
        
        if os.path.exists(file_path):
            os.remove(file_path)
        return text
    
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)

        raise(e)