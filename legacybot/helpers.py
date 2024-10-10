from commons.timeit import timeit
from legacybot.models import Thread, ChatConversation
from commons.utils import generic_completion
from string import Template
from tests.helpers import json_extraction
import logging
import json5

logger = logging.getLogger(__name__)

@timeit
def get_or_generate_action_data(thread_id: str):
    session_per_conversation_step = 10

    try:
        # Fetch thread
        thread = Thread.objects.get(deleted=False, uid=thread_id)

        # Fetch conversations for the thread
        conversations = ChatConversation.objects.filter(thread_id=thread.uid)
        conversation_count = conversations.count()

        if conversation_count > 0:
            last_conversation = conversations.last()

            # Check if the action data is already up-to-date
            if thread.action_data and thread.action_data.get('last_conversation_id') == last_conversation.uid:
                logger.info(f"Getting existing action data: {thread.action_data}")
                return thread.action_data
            else:
                # Generate new action data
                data = generate_action_report_data(conversations=conversations)
                data.update({
                    "last_conversation_id": last_conversation.uid,
                    "conversationTitle": thread.chat_topic,
                    "lastDate": str(last_conversation.created.date()),
                    "sessionCount": conversation_count // (session_per_conversation_step * 2),
                    "conversation_steps": conversation_count / 2
                })

                # Save the new action data to the thread
                thread.action_data = data
                thread.save(update_fields=['action_data'])

                return data

        else:
            logger.info(f"No conversation found in the thread: {thread.uid}")
            raise ChatConversation.DoesNotExist

    except Thread.DoesNotExist as e:
        logger.error(f"No thread found for {thread_id}", exc_info=True)
        raise e

    

    
@timeit
def generate_action_report_data(conversations:ChatConversation):
    conv = []
    for conversation in conversations:
        conv.append({
            "role": conversation.role,
            "text": conversation.content
        })

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