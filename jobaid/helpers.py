import re

def extract_feedback_block(text: str) -> dict:
    """
    Extracts feedback components: status, message (if NOT ACCEPTABLE), and suggestions.
    Works for both 'NOT ACCEPTABLE' and 'ACCEPTABLE' blocks.
    """
    result = {}
    text = text.replace("\\n", "\n")

    # Check if it's NOT ACCEPTABLE
    not_acceptable_match = re.search(r"NOT ACCEPTABLE:\s*(.*?)\n\s*IMPROVEMENT GUIDANCE:\s*(.*)", text, re.DOTALL)
    if not_acceptable_match:
        result["status"] = "hard_block"
        result["message"] = not_acceptable_match.group(1).strip()
        result["suggestions"] = not_acceptable_match.group(2).strip()
        result["meta_data"] = text
        return result

    # Check if it's ACCEPTABLE
    acceptable_match = re.search(
        r"ACCEPTABLE\s*\n\s*ENHANCEMENT SUGGESTIONS:\s*(.*)",
        text,
        re.DOTALL,
    )
    if acceptable_match:
        result["status"] = "soft_suggestion"
        result["message"] = "Answer is acceptable but can be improved."
        result["suggestions"] = acceptable_match.group(1).strip()
        result["meta_data"] = text

        return result

    return {"status": "hard_block", "message": "Answer is not acceptable. please try again.", "suggestions": [], "meta_data": text}
