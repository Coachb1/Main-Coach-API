import logging

from commons.timeit import timeit
from commons.anthropic import anthropic_completion
from commons.openai_gpt import gpt3_completion
from commons.google_apis import text_bison_compeletion

logger = logging.getLogger(__name__)

@timeit
def generic_completion(prompt, tokens=1200, fallback_text=None):
    response_text = fallback_text
    gpt_feedback = gpt3_completion(prompt, stop=["USER:", "CoachBot"])
    if not gpt_feedback.text:
        try:
            response_text = text_bison_compeletion(prompt)
        except Exception as e:
            logger.exception(e)
            response_text = anthropic_completion(prompt, tokens)
    else:
        response_text = gpt_feedback.text

    return response_text