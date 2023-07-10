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
                    engine='text-davinci-003',
                    temp=0,
                    top_p=1.0,
                    max_tokens=4000,
                    freq_pen=0.0,
                    pres_pen=0.0) -> GPTResponse:
    logger.info(f"prompt: {prompt}")
    prompt_tokens = num_tokens_for_prompt(prompt)

    max_retry = 3
    retry = 0
    prompt = prompt.encode(encoding='ASCII', errors='ignore').decode()
    while True:
        try:
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
            logger.exception('Error communicating with OpenAI err: %s', e)

            retry += 1
            if retry >= max_retry:
                raise e

            time.sleep(1)




@timeit
def gpt_wishper_api(url):
    try:
        response = requests.get(url)
        audio_data = response.content
        text = ''
        with tempfile.NamedTemporaryFile(suffix=".mp3") as temp_file:
            # Write the audio data to the temporary file
            temp_file.write(audio_data)
            temp_file.seek(0)
            
            transcription = openai.Audio.transcribe("whisper-1", temp_file)
            text = transcription['text']
        return text
    
    except Exception as e:
        raise(e)