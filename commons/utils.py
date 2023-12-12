import logging

from commons.timeit import timeit
from commons.anthropic import anthropic_completion
from commons.openai_gpt import gpt3_completion
from commons.google_apis import text_bison_compeletion

logger = logging.getLogger(__name__)

@timeit
def generic_completion(prompt, tokens=1200, fallback_text=None, is_free=False):
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