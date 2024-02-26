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
    """
    This function extracts the file name and text from a given input string.

    The input string is expected to be in the format 'file_name:<file_name>text_file:<text>'. The function first splits the input string by 'text_file:', resulting in a list where the first element contains 'file_name:<file_name>' and the second element contains '<text>'. 

    The function then further splits the first element of the list by 'file_name:' to extract the actual file name. The text is directly taken from the second element of the list.

    Args:
        input_string (str): A string in the format 'file_name:<file_name>text_file:<text>'

    Returns:
        tuple: A tuple where the first element is the file name (str) and the second element is the text (str).

    Example:
        >>> extract_file_and_text('file_name:example.txttext_file:This is some text.')
        ('example.txt', 'This is some text.')
    """
    text = input_string.split('text_file:')
    file_name = text[0].split('file_name:')[1]
    text = text[1]

    return file_name, text