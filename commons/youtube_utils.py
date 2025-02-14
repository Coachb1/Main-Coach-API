from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
from commons.timeit import timeit
import requests
import logging
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)



def format_youtube_link(youtube_link: str, only_video_id: bool = False) -> str:
    """
    Converts a YouTube link to its standard format (https://www.youtube.com/watch?v=video_id).
    
    Supports both "youtu.be" shortened links and standard YouTube links.
    
    Args:
        youtube_link (str): The YouTube link to be formatted.
        only_video_id (bool): If True, returns only the video ID.
    
    Returns:
        str: The formatted YouTube link or just the video ID if only_video_id is True.
    
    Example:
        >>> format_youtube_link("https://youtu.be/dQw4w9WgXcQ")
        'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        
        >>> format_youtube_link("https://www.youtube.com/watch?v=dQw4w9WgXcQ", only_video_id=True)
        'dQw4w9WgXcQ'
    """

    parsed_url = urlparse(youtube_link)

    # Handle "youtu.be" short links
    if parsed_url.netloc == "youtu.be":
        video_id = parsed_url.path.lstrip("/")
    
    # Handle standard YouTube links
    elif only_video_id and parsed_url.netloc in ("www.youtube.com", "youtube.com") and "v" in parse_qs(parsed_url.query):
        video_id = parse_qs(parsed_url.query)["v"][0]
    
    else:
        return youtube_link  # Return original if format is unrecognized

    return f"https://www.youtube.com/watch?v={video_id}"


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
    retry = 3
    while True:
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
        except Exception as e:
            logger.exception(f"failed get_youtube-transcript: {e}, {e.args}")
            if retry <=1 :
                return None
            
            retry -= 1
    
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
        print(f"result: {result}")
        for resp in result[0].get('transcription'):
            print(resp)
            if resp.get('subtitle'):
                transcript += resp['subtitle'] + " "
        logger.info(f"repidapi_stt: {transcript}")
        return  transcript
    except Exception as error:
        logger.exception(f"failed to extract from repidapi_stt: {error}")
        return None