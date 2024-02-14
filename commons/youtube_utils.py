from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
from commons.timeit import timeit


def format_youtube_link(youtube_link):
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
    try:
        url = format_youtube_link(url)
        query = urlparse(url).query
        params = parse_qs(query)
        video_id = params["v"][0]
        transcript =  YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        # combine all the text from the 'text' fields in the transcript into one large string
        complete_transcript = ' '.join([x['text'] for x in transcript])
        return complete_transcript
    except:
        return None