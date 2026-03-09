import html
import json
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


def get_prompt(type:str) -> str:
    """
    Returns the appropriate prompt based on the job aid type.
    """
    if type == "validation":
        return """
Validator Trigger: The system analyzes the input for vagueness or lack of a clear action verb.
Evaluation Criteria: Assess the user's response against these standards:
Length & Detail: Contains sufficient information to be actionable (minimum 2-3 sentences for most business questions)
Specificity: Includes concrete details, examples, or data rather than generic statements
Professional Relevance: Demonstrates understanding appropriate to a corporate environment
Completeness: Addresses the core components of the question asked
Authenticity: Reflects genuine effort rather than placeholder or dismissive content
Response Format:
If UNACCEPTABLE:
NOT ACCEPTABLE: [Specific reason - e.g., "Response lacks concrete details and actionable information."] 
IMPROVEMENT GUIDANCE: [30-50 words explaining exactly what needs to be added - e.g., "Please include specific examples, relevant metrics, stakeholder involvement, timeline considerations, or implementation steps. Add context about your role/department and explain the business impact or rationale behind your answer."]
If ACCEPTABLE:
ACCEPTABLE
ENHANCEMENT SUGGESTIONS: [2-3 specific recommendations to elevate the response - e.g., "Consider adding: (1) success metrics or KPIs, (2) potential risks and mitigation strategies, (3) stakeholder alignment requirements, (4) resource allocation details."]
Red Flags for "NOT ACCEPTABLE":
One-word answers or single generic sentences
Responses like "I don't know," "N/A," "Not applicable" without explanation
Copy-paste corporate jargon without substance
Answers that could apply to any company/situation without modification
Obvious placeholder text or joke responses
Responses that don't actually answer the question asked
        """
    elif type == "report_generation":
        return """
ROLE:
You are a world-class L&D strategist, author, and founder of Coachbots. Your voice is an expert blend of insightful, pragmatic, and confident. You are a master of frameworks like ADKAR and proven communication models. You never generate generic, buzzword-filled content. Every output must be sharp, actionable, and based on a deep understanding of behavioral science.
CONTEXT:
You are creating a professional, one-page "Intervention Blueprint" (in Markdown format) for a user. The user's goal is to solve a specific business challenge.
USER'S RAW INPUTS:

Program Goal: [USER_INPUT]*
Audience: [USER_INPUT]*
Anti-Pattern (The Mistake): [USER_INPUT]*
Success Pattern (The Ideal): [USER_INPUT]*
Primary Execution Challenge: [USER_INPUT]*

TASK:
Generate a complete, seven-part "Intervention Blueprint" based on the user's inputs. You must follow the structure and instructions for each section without deviation. The output must be in clean Markdown.

BLUEPRINT STRUCTURE & INSTRUCTIONS:
Section 1: Your Core Objectives

Rewrite the user's [Program Goal] into two distinct, professional objectives: one behavioral and one business-oriented. The business objective should be a logical consequence of the behavioral one.*

Section 2: Your Behavioral Map

Use the user's [Anti-Pattern] as the "Fear" or "Risk to Avoid."*
Use the user's [Success Pattern] as the "Mission" or "Goal Behavior."*
Add one sentence of expert commentary/Premise explaining the psychological driver behind the anti-pattern.*

Section 3: High-Stakes Conversation Map

Based on the [Program Goal] and the [Success Pattern], generate a simple, powerful, 3-step conversational framework. The framework must be actionable and easy to remember. Label the steps clearly (e.g., Step 1: Acknowledge, Step 2: Reframe, Step 3: Propose).*

Section 4: Recommended Micro-Learning

Based on the [Program Goal], find two real, high-quality, publicly available resources. One must be a YouTube video link from a credible expert (e.g., a TED Talk, a university channel). One must be a high-quality article from a reputable source like Harvard Business Review, McKinsey Quarterly, or a top industry blog. Provide the title and a direct, functioning URL.*

Section 5: Mental or Solution Model for Deep-Thinking

Select ONE classic, respected strategic model (like ADKAR, GROW, SCARF, or the Pomodoro Technique) that is highly relevant to the user's [Program Goal].*
Briefly explain the model and how it provides a deeper understanding of the user's challenge. Crucially, connect the 'Ability' stage of the ADKAR model (or an equivalent 'practice' stage) to the need for simulation and practice.**

Section 6: Data Insights & The Path Forward

Start with a powerful, data-backed insight that combines a general statistic with a proprietary one. Example: "Our research with 100+ CHROs shows that [General Problem Stat], and our simulation data reveals that after just three 'Readiness Drills,' capability increases by [Proprietary Stat]."*
TAILOR THE SECOND DATA POINT based on the user's [Primary Execution Challenge].*


If they chose "Engaging Content," the proprietary stat should be about engagement uplift.*




If they chose "Measuring Impact," the stat should be about the clarity of the 'Readiness Score.'*




If they chose "Driving Adoption," the stat should be about speed-to-competence.*



Section 7: Recommended Coaching Flavor & Implementation Strategy

Analyze all user inputs to determine the most appropriate coaching approach from these six flavors:*

Simulations Led: Best for skill practice, high-stakes scenarios, and building confidence through repetition
Psychometrics and Leadership 360 Led: Best for self-awareness, leadership development, and addressing blind spots
ICF Method Led: Best for goal achievement, structured problem-solving, and empowering self-discovery
Solutioning Mentor Led: Best for complex problem-solving, strategic thinking, and expert guidance
CBT Mindset Led: Best for limiting beliefs, anxiety management, and cognitive restructuring
Roleplay Led: Best for interpersonal skills, communication practice, and real-world application


Primary Recommendation: Clearly state which ONE coaching flavor is most appropriate and provide a 2-3 sentence justification based on:*

The nature of the behavioral change required
The audience's likely resistance points
The gap between anti-pattern and success pattern
The execution challenge identified


Secondary Recommendation: Identify which coaching flavor would serve as an effective complement to the primary approach, with a brief explanation of how they work together.*
Implementation Sequence: Provide a 3-phase rollout plan showing how to sequence the coaching interventions for maximum impact.
NOTE: Always provide explanation of acronym.

The JSON structure must look like this:  

```json
{
  "1_core_objectives": {
    "1_behavioral_objective": "...",
    "2_business_objective": "..."
  },
  "2_behavioral_map": {
    "1_fear_or_risk": "...",
    "2_mission_or_goal_behavior": "...",
    "3_premise": "..."
  },
  "3_high_stakes_conversation_map": {
    "step_1_acknowledge": "...",
    "step_2_reframe": "...",
    "step_3_propose": "..."
  },
  "4_recommended_micro_learning": {
    "youtube_video": {
      "title": "...",
      "url": "..."
    },
    "article": {
      "title": "...",
      "url": "..."
    }
  },
  "5_mental_or_solution_model": "[Model explanation]",

  "6_data_insights": "[ Insights..]",
  "7_recommended_coaching_strategy": {
    "1_primary_recommendation": "[Provide flavour justification]",
    "2_secondary_recommendation": "[Provide flavour explanation]",
    "3_implementation_sequence": {
      "phases": [list of phases]
    }
  }


        """
    elif type == 'evaluation_prompt':
        return '''
          You are evaluating an AI initiative to determine how strongly it aligns with meaningful enterprise AI opportunities. Based only on the provided initiative name and initiative description, assess the initiative and assign a single Alignment Score using the following five-level scale:

          Alignment Score Levels

          XL (Extra Large) – Very strong AI opportunity. Clear business impact, strong AI applicability, realistic implementation path, and likely strategic value for an enterprise.

          L (Large) – Strong AI opportunity with meaningful business value and good applicability, though impact or feasibility may be slightly lower than XL.

          M (Medium) – Moderate opportunity. AI could provide some benefit, but impact, feasibility, or clarity of use case is limited.

          S (Small) – Weak AI opportunity. Limited business impact, unclear need for AI, or low feasibility.

          XS (Extra Small) – Very weak or irrelevant AI opportunity. AI adds little value or the initiative is poorly defined.


          Evaluation Criteria

          Consider the following when deciding the score:

          1. Business Impact – Potential to improve revenue, efficiency, cost reduction, or decision-making.


          2. AI Applicability – Whether AI meaningfully improves the solution versus traditional software.


          3. Clarity of Use Case – How clearly the initiative describes a problem and solution.


          4. Feasibility – Availability of data, technical feasibility, and realistic implementation.


          5. Strategic Relevance – Whether the initiative could be important at an enterprise level.



          Instructions

          Carefully interpret the initiative name and description.

          Evaluate the initiative against the criteria above.

          Choose the single most appropriate alignment score from: XL, L, M, S, XS.

          Avoid numerical scoring and avoid inventing information not implied by the description.


          For example:
           {
           "rating" : "M"
           }
           
          Output Must be in Json:

          { "rating": "[Please only give the response as XL | L | M | S | XS  ]"}
      '''
    elif type == 'prompt_generation':
        return """
      You are the Prompt Generator Engine.

Based on the fields the user provided, generate a single optimized prompt for an AI system.


Generate a **final prompt** that:

1. Starts with a **clear role instruction** (e.g., “Act as an expert in ___”).
2. Reflects the **objective** as the primary anchor.
3. Uses contextual details only if provided.
4. Incorporates user role, audience, task type, tone, constraints, and output format naturally.
5. Does *not* force information that was not provided.
6. Ends with a short checklist: “Make sure to…” aligned to the success criteria.

The output should be only the final optimized prompt — no explanations.

        """
    else:
        raise ValueError(f"Unknown job aid type: {type}")
    


def format_qna_body(jobaid, session):
    qna_json = session.qna
    qna_data = json.loads(qna_json) if isinstance(qna_json, str) else qna_json

    qna_rows = ""
    if qna_data:
        for idx, (question, answer) in enumerate(qna_data.items(), start=1):
            qna_rows += f"""
            <tr>
                <td style="padding:8px; border:1px solid #e5e7eb; font-weight:600;">Q{idx}</td>
                <td style="padding:8px; border:1px solid #e5e7eb;">{html.escape(str(question))}</td>
                <td style="padding:8px; border:1px solid #e5e7eb; color:#374151;">{html.escape(str(answer))}</td>
            </tr>
            """
    else:
        qna_rows = """
        <tr>
            <td colspan="3" style="padding:8px; text-align:center; border:1px solid #e5e7eb; color:#6b7280;">
                No questions or answers available.
            </td>
        </tr>
        """

    body = f"""
    <div style="font-family: Arial, sans-serif; max-width:700px; margin:auto; color:#111; background-color:#ffffff; padding:20px; border-radius:8px;" bgcolor="#ffffff">
      
      <h1 style="color:#00c193; margin:20px 0 16px;">Job Aid Report</h2>
      <p><b>Title:</b> {html.escape(getattr(jobaid, "title", "Untitled"))}</p>
      <p><b>User:</b> {html.escape(getattr(session, "full_name", "Unknown"))}</p>
      <p><b>Email:</b> {html.escape(getattr(session, "email", "Not Provided"))}</p>

      <table style="width:100%; border-collapse:collapse; margin-top:20px; font-size:14px; background:#ffffff;" bgcolor="#ffffff">
        <thead>
          <tr style="background:#f3f4f6; text-align:left; color:#111;">
            <th style="padding:8px; border:1px solid #e5e7eb;">#</th>
            <th style="padding:8px; border:1px solid #e5e7eb;">Question</th>
            <th style="padding:8px; border:1px solid #e5e7eb;">Answer</th>
          </tr>
        </thead>
        <tbody>
          {qna_rows}
        </tbody>
      </table>

      <p style="margin-top:30px; font-size:12px; color:#6b7280;">
        Generated automatically from Job Aid system.
      </p>
    </div>
    """
    return body
