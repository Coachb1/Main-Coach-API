import logging

import anthropic
from django.conf import settings

logger = logging.getLogger(__name__)

ANTHROPIC_KEY = settings.ANTHROPIC_KEY


def anthropic_completion(prompt, max_tokens):
    client = anthropic.Client(ANTHROPIC_KEY)

    max_retries = 3

    while True:
        try:
            response = client.completion(prompt=f'{anthropic.HUMAN_PROMPT}{prompt}{anthropic.AI_PROMPT}',
                                         model='claude-2', max_tokens_to_sample=max_tokens,
                                         stop_sequences=[anthropic.HUMAN_PROMPT])
            logger.info("anthropic_completion response %s", response)
            return response['completion']

        except Exception as e:

            if max_retries <= 0:
                logger.error("anthropic_completion error %s", e)
                raise e
                break
            else:
                max_retries -= 1


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
