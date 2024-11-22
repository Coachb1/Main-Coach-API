import logging

from commons.timeit import timeit
from commons.anthropic import anthropic_completion
from commons.openai_gpt import gpt3_completion
from commons.google_apis import text_bison_compeletion, gemini_completion
import re
from utilities.models import BotEngagement
import string


logger = logging.getLogger(__name__)

@timeit
def generic_completion(prompt, tokens=1200, fallback_text=None, is_free=False, llm_order=None, instruction=None, temp=0.9,top_p=1):
    """
    Generates text completions based on a given prompt.

    Args:
        prompt (str): The prompt for which completions are requested.
        tokens (int, optional): The maximum number of tokens to generate in the completions. Defaults to 1200.
        fallback_text (str, optional): The fallback text to use if completions cannot be generated. Defaults to None.
        is_free (bool): A flag indicating if the completions should be generated for free or not.
        llm_order (list, optional): A list specifying the order of LLMs to use eg: ['gemini', 'anthropic', 'gpt']. Defaults to None.

    Returns:
        str: The generated completions based on the given prompt.
    """
    response_text = fallback_text

    # Define the default order of LLMs if not provided
    default_order_free = ['anthropic', 'gemini']
    default_order_paid = ['gemini', 'anthropic', 'gpt']

    # Use the provided order or default order
    if is_free:
        llm_order = default_order_free
    else:
        llm_order = llm_order if llm_order and len(llm_order) > 0 else default_order_paid

    def call_llm(llm, prompt, tokens):
        if llm == 'anthropic':
            return anthropic_completion(prompt, tokens)
        elif llm == 'gemini':
            return gemini_completion(prompt=prompt,instruction=instruction,temperature=temp,top_p=top_p)
        elif llm == 'gpt':
            return gpt3_completion(prompt=prompt, stop=["USER:", "CoachBot"], temp=temp, top_p=top_p).text
        return None

    for llm in llm_order:
        try:
            response_text = call_llm(llm, prompt, tokens)
            if response_text and len(response_text.strip()) > 0:
                break
        except Exception as e:
            logger.exception(f"Failed with {llm}: {e}")

    return response_text if response_text and len(response_text.strip()) > 0 else fallback_text


# @timeit
# def generic_completion(prompt, tokens=1200, fallback_text=None, is_free=False):
#     """
#     Generates text completions based on a given prompt.

#     Args:
#         prompt (str): The prompt for which completions are requested.
#         tokens (int, optional): The maximum number of tokens to generate in the completions. Defaults to 1200.
#         fallback_text (str, optional): The fallback text to use if completions cannot be generated. Defaults to None.
#         is_free (bool): A flag indicating if the completions should be generated for free or not.

#     Returns:
#         str: The generated completions based on the given prompt.
#     """
#     response_text = fallback_text
#     if is_free:
#         try:
#             response_text = anthropic_completion(prompt, tokens)
#             if len(response_text.strip()) == 0:
#                 response_text = gemini_completion(prompt)
#         except Exception as e:
#             logger.exception(f"failed generic Completion: {e}")
#             response_text = fallback_text

#     else:
#         bison_feedback = gemini_completion(prompt)
#         if not bison_feedback or len(bison_feedback.strip()) == 0:
#             try:
#                 response_text = anthropic_completion(prompt, tokens)
#                 if len(response_text.strip()) == 0:
#                     raise ValueError("Got empty response")
#             except Exception as e:
#                 logger.exception(e)
#                 try:
#                     response_text = gpt3_completion(prompt, stop=["USER:", "CoachBot"]).text
#                     if len(response_text.strip()) == 0:
#                         raise ValueError("Got empty response")
#                 except Exception as e:
#                     response_text = fallback_text
#         else:
#             response_text = bison_feedback

#     return response_text



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


def get_bot_engagements(tenant_id,bot_id,by_date=None,by_user=None):
    """
    get bot enagement using bot uid. It is here for bot enagement api
    """
    bot_engagements = BotEngagement.objects.filter(deleted=False,tenant_id=tenant_id,bot_id=bot_id)
    if by_date:
        bot_engagements = bot_engagements.filter(interacted_on=by_date)
    if by_user:
        bot_engagements = bot_engagements.filter(user_id=by_user)
    
    bot_result = []
    total_with_questions = 0
    total_without_questions = 0
    for bot_engagement in bot_engagements:

        temp = {
            'bot_id': bot_id,
            'user_id': bot_engagement.user_id,
            'interacted_on': bot_engagement.interacted_on,
            'num_button_clicked': bot_engagement.num_of_clicked_button,
            'num_of_attempted_sessions': bot_engagement.num_of_bot_sessions,
            'attempted_bot_questions': bot_engagement.attempted_bot_questions
        }
        bot_result.append(temp)
        total_with_questions += sum([bot_engagement.num_of_clicked_button,bot_engagement.num_of_bot_sessions,bot_engagement.attempted_bot_questions])
        total_without_questions += sum([bot_engagement.num_of_clicked_button,bot_engagement.num_of_bot_sessions])


    data = {
        "results": bot_result,
        'total_engagement_with_question_count': total_with_questions,
        'total_without_question_count': total_without_questions
    }

    return data



def remove_punctuations(text):
    # Create translation table to map punctuations to None
    translator = str.maketrans('', '', string.punctuation)
    # Remove punctuations using translate method
    return text.translate(translator)


def get_list_from_string(string:str,
                         delimiter:str = ','
                         )->list:
    """
    This function splits a string into a list based on a given delimiter.
    """
    return list(set([i for i in [value.strip() for value in string.strip().split(delimiter) if len(value.strip()) > 0]] if string else []))
