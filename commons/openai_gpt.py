import dataclasses
import logging
import re
import time

import openai
import tiktoken
from django.conf import settings

from commons.timeit import timeit

import requests
import tempfile
import random

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
    response = openai.Embedding.create(input=content, engine=engine)
    vector = response['data'][0]['embedding']
    return vector


@timeit
def gpt3_completion(prompt,
                    stop,
                    engine='gpt-4-1106-preview',
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
    while True:
        try:
            logger.info({"**** gpt3_completion":f"trying gpt for {retry} time"})
            response = openai.Completion.create(
                engine=engine,
                prompt=prompt,
                temperature=temp,
                max_tokens=max_tokens - prompt_tokens,
                top_p=top_p,
                frequency_penalty=freq_pen,
                presence_penalty=pres_pen,
                stop=stop)
            text = response['choices'][0]['text'].strip()
            text = re.sub('[\r\n]+', '\n', text)
            text = re.sub('[\t ]+', ' ', text)

            logger.info(f"text: {text}")
            return GPTResponse(raw=response, text=text)
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
    try:
        response = requests.get(url)
        audio_data = response.content
        text = ''
        suffix = '.mp3'
        if '.m4a' in url:
            suffix = '.m4a'
        with tempfile.NamedTemporaryFile(suffix=suffix) as temp_file:
            # Write the audio data to the temporary file
            temp_file.write(audio_data)
            temp_file.seek(0)
            
            transcription = openai.Audio.transcribe("whisper-1", temp_file, language="en")
            text = transcription['text']
        return text
    
    except Exception as e:
        raise(e)