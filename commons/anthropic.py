import logging

import anthropic
from django.conf import settings
import time
import random
from commons.timeit import timeit
import json
from commons.notifications import send_error_notification

logger = logging.getLogger(__name__)

ANTHROPIC_KEY = settings.ANTHROPIC_KEY

@timeit
def anthropic_completion(prompt, max_tokens,temp=1 ,models="claude-3-haiku-20240307"):
    """
    Generate completions for a given prompt using the Anthropic API.

    Args:
        prompt (str): The prompt for which completion is requested.
        max_tokens (int): The maximum number of tokens to generate in the completion.

    Returns:
        str: The generated completion.

    Raises:
        Exception: If the maximum number of retries is reached and the API call still fails.

    """
    client = anthropic.Client(api_key=ANTHROPIC_KEY)

    max_retries = 10
    error_notification_sent = False

    while True:
        try:
            logger.info({"****evaluate_response ":f"trying anthropic for {10 - max_retries + 1} time"})
            # response = client.completions.create(prompt=f'{anthropic.HUMAN_PROMPT}{prompt}{anthropic.AI_PROMPT}',
            #                              model='claude-2', max_tokens_to_sample=max_tokens,
            #                              stop_sequences=[anthropic.HUMAN_PROMPT])
            response = client.messages.create(
                        model=models,
                        max_tokens=4096,
                        temperature=temp,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": prompt
                                    }
                                ]
                            }
                        ]
                    )
            logger.info("anthropic_completion response %s", response)
            
            return response.content[0].text
        
        except anthropic.APIError as e:
            logger.error({"****evaluate_response ":f"failed anthropic for {10 - max_retries + 1} time", "error": e})
            if max_retries <= 0:
                logger.error("anthropic_completion error %s", e)
                raise e
            else:
                max_retries -= 1

            if e.status_code == 429:  # Handling quota exceeded or rate limit error
                logger.error("Quota exceeded or too many requests, retrying after delay...")
                if not error_notification_sent:
                    send_error_notification('anthropic_completion', "429 error", e.args)
                    error_notification_sent = True
                time.sleep(2 ** (10 - max_retries + 1))  # Exponential backoff
            else:
                time.sleep(random.randint(1,3))

        except Exception as e:
            logger.error({"****evaluate_response ":f"failed anthropic for {10 - max_retries + 1} time", "error": e})
            if max_retries <= 0:
                logger.error("anthropic_completion error %s", e)
                raise e
                break
            else:
                max_retries -= 1

            time.sleep(random.randint(1,3))


prompt1 = '''
"Question:" In the recent pandemic conditions, work from home has become common. How well do you find yourself prepared to lead a remote team? "Answer:" I’ll try to lead by Conducting one-on-one and group meetings for ongoing projects more frequently while keeping them precise.

Following a structured and detailed feedback system to ensure that the team members do not repeat their mistakes.

Using project management tools to involve team members and create project status visibility.

Creating opportunities for team bonding and levity. 

"Required from anthropic:" Rate this answer as "very good", "good", "average", "bad", "very bad". In terms of "strategic thinking" Reply in “one” or “two” words.
'''

prompt2 = '''
"Question:" In the recent pandemic conditions, work from home has become common. How well do you find yourself prepared to lead a remote team? "Answer:" I’ll try to make my team send me report every hour.

"Required from anthropic:" Rate this answer as very good, good, average, bad, very bad. In terms of "leadership quality" Reply in “one” or “two” words.
'''
