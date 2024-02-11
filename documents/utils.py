from commons.anthropic import anthropic_completion


def get_summary(transcript, choice = "short"):
    short_summary_prompt = f"""
    Transcript : ${transcript}

    Give me a 200-word summary of the given Transcript. Do not leave any details. Give the summary in 5 bullet points. 
    Note: 1) Do not mention the transcript, just give the summary.
    2) The summary should never be less than 200 words.
    3) Do not add any introductory sentences, just give the summary.
    """


    long_summary_prompt = f"""

    Expand Summary -
    Transcript : ${transcript}

    Give me an extra long and very detailed summary of the given Transcript. Do not leave out any details. Do not mention the transcript, just give the summary.
    Note: 1) Do not mention the transcript, just give the summary.
    2) The summary should never be less than 500 words.
    3) Do not add any introductory sentences, just give the summary.
    """

    prompt = short_summary_prompt if choice == "short" else long_summary_prompt
    summary = anthropic_completion(prompt,500)
    summary = summary.split(":")[-1].strip()
    return summary