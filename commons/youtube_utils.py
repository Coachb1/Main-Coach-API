from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
from commons.timeit import timeit
import requests
import logging

logger = logging.getLogger(__name__)


def format_youtube_link(youtube_link):
    """ 
    This function takes a YouTube link as input and converts it into a standard YouTube link format if it's in a shortened (youtu.be) format.

    The function checks if "youtu.be" is in the input link. If it is, the function extracts the video ID from the link by splitting the link on "/" and taking the last element, then splitting that on "?" and taking the first element. This video ID is then used to construct a new link in the standard YouTube format (https://www.youtube.com/watch?v=video_id).

    If "youtu.be" is not in the input link, the function assumes that the link is already in the standard format and returns it as is.

    Args: youtube_link (str): The YouTube link to be formatted. This can be in any format that YouTube supports (e.g., youtu.be links or standard YouTube links).

    Returns: str: The YouTube link in the standard format. If the input link was in the youtu.be format, it is converted to the standard format. If the input link was already in the standard format, it is returned as is.

    Example: >>> youtube_link = "https://youtu.be/dQw4w9WgXcQ" >>> print(format_youtube_link(youtube_link)) "https://www.youtube.com/watch?v=dQw4w9WgXcQ" """

    if "youtu.be" in youtube_link:
        # Extract the video ID from the input link
        video_id = youtube_link.split("/")[-1].split("?")[0]
        # Construct the new YouTube link format
        converted_link = f"https://www.youtube.com/watch?v={video_id}"
        return converted_link
    else:
        return youtube_link

@timeit
def get_youtube_transcript(url):
    """
    This function retrieves the transcript of a YouTube video given its URL.

    The function first formats the YouTube URL to ensure it's in the standard format (https://www.youtube.com/watch?v=video_id). 
    It then parses the URL to extract the video ID, which is used to fetch the transcript using the YouTubeTranscriptApi. 
    The transcript is a list of dictionaries, each containing 'text', 'start', and 'duration' keys. 
    The function combines all the 'text' fields into a single string to form the complete transcript.

    Args:
        url (str): The URL of the YouTube video. It can be in any format that YouTube supports (e.g., youtu.be links or standard YouTube links).

    Returns:
        str: The complete transcript of the YouTube video as a single string. If the transcript cannot be fetched (e.g., due to the video not having a transcript or the URL being invalid), the function returns None.

    Example:
        >>> url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        >>> print(get_youtube_transcript(url))
        "We're no strangers to love You know the rules and so do I..."
    """
    try:
        logger.info(f"get_youtube_transcript before format: {url}")
        url = format_youtube_link(url)
        logger.info(f"get_youtube_transcript after format: {url}")
        query = urlparse(url).query
        params = parse_qs(query)
        video_id = params["v"][0]
        transcript =  YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        # combine all the text from the 'text' fields in the transcript into one large string
        complete_transcript = ' '.join([x['text'] for x in transcript])
        logger.info(f"Complete Transcript: {complete_transcript}")
        return complete_transcript
    except:
        return None
    
@timeit
def repidapi_stt(url):
    url =format_youtube_link(url)
    query = urlparse(url).query
    params = parse_qs(query)
    video_id = params["v"][0]

    url2 = f'https://youtube-transcriptor.p.rapidapi.com/transcript?video_id={video_id}'
    headers = {
        'X-RapidAPI-Key': '80c2437ae0msh8b10a7096d8c152p1e04f2jsn9e113e29af91',
        'X-RapidAPI-Host': 'youtube-transcriptor.p.rapidapi.com'
    }
    transcript = ""
    try:
        response = requests.get(url2, headers=headers)
        result = response.json()
        for resp in result[0].get('transcription'):
            transcript += resp['subtitle'] + " "
        logger.info(f"repidapi_stt: {transcript}")
        return  transcript
    except Exception as error:
        logger.exception(f"failed to extract from repidapi_stt: {error}")
        return None