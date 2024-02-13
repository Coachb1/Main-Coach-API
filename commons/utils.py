import logging

from commons.timeit import timeit
from commons.anthropic import anthropic_completion
from commons.openai_gpt import gpt3_completion
from commons.google_apis import text_bison_compeletion
import re

logger = logging.getLogger(__name__)

@timeit
def generic_completion(prompt, tokens=1200, fallback_text=None, is_free=False):
    """
    Generates text completions based on a given prompt.

    Args:
        prompt (str): The prompt for which completions are requested.
        tokens (int, optional): The maximum number of tokens to generate in the completions. Defaults to 1200.
        fallback_text (str, optional): The fallback text to use if completions cannot be generated. Defaults to None.
        is_free (bool): A flag indicating if the completions should be generated for free or not.

    Returns:
        str: The generated completions based on the given prompt.
    """
    response_text = fallback_text
    if is_free:
        response_text = anthropic_completion(prompt, tokens)

    else:
        bison_feedback = text_bison_compeletion(prompt)
        if not bison_feedback:
            try:
                response_text = anthropic_completion(prompt, tokens)
            except Exception as e:
                logger.exception(e)
                response_text = gpt3_completion(prompt, stop=["USER:", "CoachBot"]).text
        else:
            response_text = bison_feedback

    return response_text



def extract_file_and_text(input_string):

    text = input_string.split('text_file:')
    file_name = text[0].split('file_name:')[1]
    text = text[1]

    return file_name, text