from commons.timeit import timeit
from legacybot.models import Thread, ChatConversation, LegacyBotUser, LegacyBot
from commons.utils import generic_completion
from string import Template
from tests.helpers import json_extraction
from datetime import date
import logging
import json5
import uuid
import re
logger = logging.getLogger(__name__)

@timeit
def get_or_generate_action_data(threads: Thread):
    session_per_conversation_step = 10
    logger.info(f"Processing  [get_or_generate_action_data] for threads: [{threads.count()}: {threads.values_list('uid',flat=True)}]")
    action_data = []
    if threads.count() == 0:
        return action_data
    user = LegacyBotUser.objects.get(uid=threads.first().user_id)
    bot = LegacyBot.objects.get(uid=threads.first().bot_id)
    for thread in threads.order_by('updated'):
        try:
            if user.uid != thread.user_id:
                user = LegacyBotUser.objects.get(uid=thread.user_id)
            # Fetch conversations for the thread
            conversations = ChatConversation.objects.filter(deleted=False, thread_id=thread.uid)
            conversation_count = conversations.count()

            # Skip processing if there are no conversations
            if conversation_count == 0:
                logger.warning(f"No conversation found in the thread: {thread.uid}")
                action_data.append({thread.uid: "No conversation found."})
                continue

            last_conversation = conversations.last()

            # Check if action data is already up-to-date
            if thread.action_data and thread.action_data.get('last_conversation_id') == last_conversation.uid:
                logger.info(f"Using existing action data for thread {thread.uid}")
                action_data.append({thread.uid: thread.action_data})
                continue
            # Generate new action data
            if bot.show_report:
                only_report_data = [conv.content for conv in conversations if conv.role == 'assistant' and "Top 5 Scenarios & Probabilities" in conv.content]
                if only_report_data:
                    data = {
                            'summary': only_report_data[-1],
                            'keyTakeaways': None,
                            'skillsFocus': []
                        }
                else:
                    logger.warning(f"No conversation found in the thread: {thread.uid}")
                    action_data.append({thread.uid: "No conversation found."})
                    continue
            else:
                data = generate_action_report_data(conversations=conversations)
            data.update({
                "last_conversation_id": last_conversation.uid,
                "conversationTitle": thread.chat_topic,
                "lastDate": str(last_conversation.created.date()),
                "sessionCount": conversation_count // (user.session_per_conversation_step * 2),
                "conversation_steps": conversation_count / 2
            })

            # Save the new action data to the thread
            thread.action_data = data
            thread.save(update_fields=['action_data'])

            action_data.append({thread.uid: data})

        except ChatConversation.DoesNotExist:
            logger.error(f"No conversations found for thread {thread.uid}")
        except Exception as e:
            logger.exception(f"Failed to process thread {thread.uid}: {e}", exc_info=True)
    
    return action_data

    
@timeit
def generate_action_report_data(conversations:ChatConversation):
    conv = []
    for conversation in conversations:
        conv.append({
            "role": conversation.role,
            "text": conversation.content
        })

    logger.info(f"[generate_action_report_data]: conversation: {conv}")

    prompt = """
        Analyze the following conversation between a user and an AI assistant about Python programming. Provide a structured summary with the following elements:
        1. *Summary*: A concise overview covering key Python topics, such as string manipulation, data structures, exception handling, and other discussed topics. 
        2. *Key Takeaways*: List three key takeaways in a bullet-point format (not numbered). Ensure the takeaways are informative and practical, summarizing the main points.
        3. *Skills Focus*: Identify three specific Python skills that the conversation emphasizes.
        4. *Format the output as a JSON object* with the following structure:
        - summary: A concise but thorough paragraph summarizing the conversation. NOTE : Should be within 100 words
        - keyTakeaways: A string with three bullet points takeaways, each on a new line. 
        - skillsFocus: A list of three skills relevant to the conversation.

        Use the following format for the output:

        {
        summary: "Your summary here.",
        keyTakeaways: "1. First takeaway.\n2. Second takeaway.\n3. Third takeaway.",
        skillsFocus: ["Skill 1", "Skill 2", "Skill 3"]
        }

        Conversation: 
        ${conv}
    """
    try:
        data = generic_completion(prompt=Template(prompt).substitute(conv=conv),instruction="Note: All elements must be filled.")
        data = json5.loads(json_extraction(data))
        return data
    except Exception as e:
        logger.exception(f"failed to generate action report data : {e}")
        raise ValueError(f'Failed to generate action report data : {e}')
    

def generate_bot_identifier(bot_name,assistant_id):
    # Normalize bot name: lowercase, replace spaces with hyphens, remove special characters, and limit to first 4 words
    normalized_bot_name = "-".join(
        re.sub(r"[^a-zA-Z0-9\s-]", "", bot_name).strip().lower().split()
    )
    
    
    # Combine normalized bot name and random ID
    bot_id = f"{normalized_bot_name}-{assistant_id.replace('asst_','')[:6]}"
    
    # Replace underscores with hyphens (if any were generated by normalization)
    bot_id = bot_id.replace("_", "-")
    
    return bot_id

def calculate_session_info(user:LegacyBotUser , thread_ids:list):
    qouta_exceeded, sessionCount, conversation_steps = False, 0, 0
    today_data = {}
    try:
        conversations = ChatConversation.objects.filter(thread_id__in=thread_ids)
        conversation_count = conversations.count()
        # Prevent division by zero
        if user.session_per_conversation_step > 0:
            sessionCount = conversation_count // (user.session_per_conversation_step * 2)
        else:
            sessionCount = 0  # Default value when session_per_conversation_step is zero

        
        # Check if the user has unlimited sessions
        unlimited_session = user.max_session == -1  # Explicitly checking for -1
        conversation_steps = conversation_count / 2

        # Determine if quota is exceeded

        todays_conversations = conversations.filter(created__date = date.today())
        todays_conversation_count = todays_conversations.count()
        if user.session_per_conversation_step > 0:
            today_session_count = todays_conversation_count // (user.session_per_conversation_step * 2)
        else:
            today_session_count = 0  # Default value when session_per_conversation_step is zero

        qouta_exceeded = False if unlimited_session else today_session_count >= user.max_session

        today_data = {
            "conversation_count": todays_conversation_count,
            "session_count": today_session_count,
            "conversation_steps": todays_conversation_count / 2
        }

    except Exception as e:
        logger.exception(f"Failed to calculate session info for user {user}: {e}")

    return qouta_exceeded, sessionCount, conversation_steps, today_data

