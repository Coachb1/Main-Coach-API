import datetime


def video_script_prompt(objective,type_of_prompt='normal_video_script'):
  today_date = datetime.datetime.now().strftime("%Y-%m-%d")
  return f"""
    You are tasked with creating a video script. Please adhere *strictly* to the following requirements:

    **INPUT (User Must Provide):**
    1.  `\"{objective}\"`: Clearly define the central theme, argument, or scenario the video script should focus on. This is the core message Jay will deliver.
    2.  `[{today_date}]`: Specify the current month and year (e.g., "October 2024"). This will be used to define the end date for case study searches.

    **OUTPUT REQUIREMENTS:**

    1.  **Format:** A single-speaker narration script for a video.
    2.  **Speaker:** The script must be written from the perspective of "Jay," an AI Coach.
    3.  **Opening Line:** The script *must* begin *exactly* with: `Hey this is Jay. Your AI Coach.` (No variations allowed).
    4.  **Tone & Style:**
        *   **Opinionated & Strong:** Present a clear, potentially controversial stance on the `\"{objective}\"`.
        *   **Engaging Hook:** Start strong to grab attention immediately. Aim for language that sparks curiosity or challenges common assumptions, suitable for platforms like LinkedIn or YouTube, but maintaining professionalism for an enterprise audience.
        *   **Authoritative & Coaching:** Jay should sound knowledgeable and directive, as expected from a coach in a management development context.
    5.  **Content - Case Studies:**
        *   Include **three (3) real-life examples/case studies** that strongly illustrate the point being made about the `\"{objective}\"`.
        *   **Recency:** These examples *must* reference events, decisions, or published outcomes that occurred between **January 1, 2023, and the `[April,30 2025]` provided by the user.**
        *   **Verifiability:** For each example, include specific details (e.g., company name, specific initiative, reported outcome, relevant timeframe) and **cite a verifiable public reference** (e.g., reputable news article link, official company press release link, widely reported event). The reference should allow someone to cross-verify the claim. *Note: Finding 3 perfectly fitting, publicly referenced examples within this specific recent timeframe can be challenging; prioritize accuracy and relevance.*
    6.  **Target Audience:** The script's complexity, language, and examples should be suitable for **Management Development Programs within enterprise companies.**
    7.  **Length & Pacing:** Aim for a script that can be delivered naturally in **under 2 minutes**. This typically translates to approximately **250-300 words**. Keep all sentences brief—ideally under **10-15 words.** *Do NOT mention the word count anywhere in the generated script itself.*
    8.  **Exclusions:**
        *   Do **NOT** include any title for the video script.
        *   Do **NOT** include typical YouTube/video calls to action (e.g., "like, share, subscribe," "hit the bell icon," "link in description").
        *   Do **NOT** include any closing remarks or sign-offs (e.g., "Thanks for watching," "See you next time," "This has been Jay"). The script should end after the main content/final point is delivered.

      """
def get_scenario_prompt(scenario_type,information,skill_count=2,question_count=3,create_skill=False):
    prompt = ""
    if scenario_type == 'normal_static':
      prompt = """
        \n\nHuman:
        {Information} -
        %s -
        Read this {information} thoroughly. Now, based on this information and your understanding, create an advanced and detailed scenario to practice the skills related to {skill_domain}. The scenario should be in the {department} department of a {industry} company. After creating the situation, provide these:
        Description - Define the situation and the problem. The problem should be related to the {information} provided. The description should always involve a conversation based on the context of the {information}. Make the description specific based on the information, focusing on relevant details. Provide the name of the individual in a leadership role based on the information, but never provide the name of the other person involved. The description should detail the situation that led to the issue, and it should not include dialogues. It should always be from a third-person perspective. Provide the description in 100 to 200 words. Avoid adding any conclusions. The situation should not be related to writing emails. description in markdown la.
        Always replace the terms with those relevant to the {information}, ensuring the scenario is based on the specifics of the context and is open-ended for further exploration.
        Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
        Title must follow this Format:
            "[Short 3-4 word core areas] ( High Level Skill : skill1, skill2)"
            Example format:
                  "AI-Powered E-commerce Chatbots (High-Level Skill: NLP, Dialogflow)"

        Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.
        Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions.

        KLP - With each question add one or two line takeaway for providing feedback. The takeaways should be related to the question it is provided with.
        KLS - With each question, add the skill(s) that are highlly relevant to the scenario. All skills should be from the {skill_domain} only and must be taken from {targated skills} if defined.  And For every question choose exactly {%s} skill(s) and not more or less than {%s} should be chosen for each question. The skills for all the questions should be unique. Each question shall have a unique skill. Split compound skill words into separate words with proper capitalization. Each question must have a completely unique set of skills — no skill should repeat in any other question.
        Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
        At the end of the scenario description please provide a short executive summary that contains the data driven background information NOT captured the situation that the user can levearge to answer any questions related to the scenario.
        In every response, you must:
        Clearly state your role as X.
        Identify Y as the person asking
        The Question, Custom Prompt, KLP, KLS should be numbered.
        Here the format looks like :
        "Title:",
        "Description:”,
        “Statement:",
        "Background:",
        "Question 1:",
        "Prompt 1:",
        "Takeaway 1:" ,
        "Skills 1:" repeated for {%s} question(s). Do not include any {responder} response. NOTE: If {targated skills} are present then skills must be from the {targated skills}.
        'The Question, Prompt, Takeaway, Skills should be numbered.'
        NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
        NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
        NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated. Skill must be only maixmum two words.
        NOTE: KLS - The Skills should be highly relevant to the scenario and {skill_domain}(90 percent or more relevant).
        NOTE: "Rating" must be included.
        NOTE : Make sure the simulation is very advanced and tough.
        NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
        NOTE: Never miss Title, Description, Statement and other variables.
        NOTE: Do not mention "X" or "Y".
        NOTE: must Follow the OUTPUT Format.
        \n\nAssistant:

    """
    elif scenario_type == 'whatsapp_normal_static':
      prompt = '''
      \n\nHuman:
        {Information} - %s-
        Read this {information} thoroughly. Now, based on this information and your understanding, create an advanced and detailed scenario to practice the skills related to {skill_domain}. The scenario should be in the {department} department of a {industry} company. After creating the situation, provide these:
        Description - Define the situation and the problem within {50} words. The problem should be related to the {information} provided. The description should always involve a conversation based on the context of the {information}. Make the description specific based on the information, focusing on relevant details. Provide the name of the individual in a leadership role based on the information, but never provide the name of the other person involved. The description should detail the situation that led to the issue, and it should not include dialogues. It should always be from a third-person perspective. Provide the description in 100 to 200 words. Avoid adding any conclusions. The situation should not be related to writing emails.        Always replace the terms with those relevant to the {information}, ensuring the scenario is based on the specifics of the context and is open-ended for further exploration. It shall always remain between two specific individuals, as determined by the context provided in the {information}.
        Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
        Title must follow this Format:
            "[Short 3-4 word core areas] ( High Level Skill : skill1, skill2)"
            Example format:
                  "AI-Powered E-commerce Chatbots (High-Level Skill: NLP, Dialogflow)"
        Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the problem. NEVER respond to the questions.
        Custom prompt - With each question, add a prompt asking for feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
        KLP - With each question add one or two line takeaways for providing feedback. The takeaways should be related to the question it is supplied with.
        KLS - With each question, add the skill(s) that are highlly relevant to the scenario. All skills should be from the {skill_domain} only and must be taken from {targated skills} if defined.  And For every question choose exactly {%s} skill(s) and not more or less than {%s} should be chosen for each question. The skills for all the questions should be unique. Each question shall have a unique skill. Skill must be only maixmum two words. Each question must have a completely unique set of skills — no skill should repeat in any other question.
        Always use indian names in the role play, also mention what role the user will be playing while answering the questions in the description.
        Always use name in each question. The role play shall also have element of a other person who will be asking the questions.
        Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
        The Question, Custom Prompt, KLP, KLS should be numbered.
        Here the format looks like :
        "Title:",
        "Description:”,
        “Statement:",
        "Question 1:",
        "Prompt 1:",
        "Takeaway 1:" ,
        "Skills 1:" repeated for {%s} question(s). Do not include any {responder} response. NOTE: If {targated skills} are present then skills must be from the {targated skills}.
        'The Question, Prompt, Takeaway, Skills should be numbered.'
        NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
        NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
        NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated.
        NOTE: "Rating" must be included.
        NOTE: Make sure the roleplay is very advanced and tough.
        NOTE: Always use a name in each question. The role play shall also have the element of an other person who will be asking the questions.
        NOTE: Always mention in the context what role the user will be playing the role while answering.
        NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
        NOTE: Never miss Title, Description, Statement and other variables.
        NOTE: Do not mention "X" or "Y".
        NOTE: must Follow the OUTPUT Format.
        \n\nAssistant:

      '''
    elif scenario_type == 'role_play_static':
      prompt= """
        \n\nHuman:
        {Information} - %s-
        Read this {information} thoroughly. Now, based on this information and your understanding, create an advanced and detailed scenario to practice the skills related to {skill_domain}. The scenario should be in the {department} department of a {industry} company. After creating the situation, provide these:
        Description - Define the situation and the problem. The problem should be related to the {information} provided. The description should always involve a conversation based on the context of the {information}. Make the description specific based on the information, focusing on relevant details. Provide the name of the individual in a leadership role based on the information, but never provide the name of the other person involved. The description should detail the situation that led to the issue, and it should not include dialogues. It should always be from a third-person perspective. Provide the description in 100 to 200 words. Avoid adding any conclusions. The situation should not be related to writing emails.        Always replace the terms with those relevant to the {information}, ensuring the scenario is based on the specifics of the context and is open-ended for further exploration. It shall always remain between two specific individuals, as determined by the context provided in the {information}.
        Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
        Title must follow this Format:
            "[Short 3-4 word core areas] ( High Level Skill : skill1, skill2)"
            Example format:
                  "AI-Powered E-commerce Chatbots (High-Level Skill: NLP, Dialogflow)"
        Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the problem. NEVER respond to the questions.
        Custom prompt - With each question, add a prompt asking for feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
        KLP - With each question add one or two line takeaways for providing feedback. The takeaways should be related to the question it is supplied with.
        KLS - With each question, add the skill(s) that are highlly relevant to the scenario. All skills should be from the {skill_domain} only and must be taken from {targated skills} if defined.  And For every question choose exactly {%s} skill(s) and not more or less than {%s} should be chosen for each question. The skills for all the questions should be unique throughout all questions. Each question shall have unique skills. Skill must be only maixmum two words. Each question must have a completely unique set of skills — no skill should repeat in any other question.
        Always use indian names in the role play, also mention what role the user will be playing while answering the questions in the description.
        Always use name in each question. The role play shall also have element of a other person who will be asking the questions.
        Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
        The Question, Custom Prompt, KLP, KLS should be numbered.
        Here the format looks like :
        "Title:",
        "Description:”,
        “Statement:",
        "Question 1:",
        "Prompt 1:",
        "Takeaway 1:" ,
        "Skills 1:" repeated for {%s} question(s). Do not include any {responder} response. NOTE: If {targated skills} are present then skills must be from the {targated skills}.
        'The Question, Prompt, Takeaway, Skills should be numbered.'
        NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
        NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
        NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated.
        NOTE: "Rating" must be included.
        NOTE: Make sure the roleplay is very advanced and tough.
        NOTE: Always use a name in each question. The role play shall also have the element of an other person who will be asking the questions.
        NOTE: Always mention in the context what role the user will be playing the role while answering.
        NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
        NOTE: Never miss Title, Description, Statement and other variables.
        NOTE: Do not mention "X" or "Y".
        NOTE: must Follow the OUTPUT Format.
        \n\nAssistant:
        """
    elif scenario_type == "case_static":
      prompt = """
        \n\nHuman:
        {Information} - %s
        Read this {information} thoroughly. Now, based on this information and your understanding, create an advanced and detailed scenario to practice the skills related to {skill_domain}. The scenario should be in the {department} department of a {industry} company. After creating the situation, provide these:
        Description - Define the situation and the problem. The problem should be related to the {information} provided. The description should always involve a conversation based on the context of the {information}. Make the description specific based on the information, focusing on relevant details. Provide the name of the individual in a leadership role based on the information, but never provide the name of the other person involved. The description should detail the situation that led to the issue, and it should not include dialogues. It should always be from a third-person perspective. Provide the description in 100 to 200 words. Avoid adding any conclusions. The situation should not be related to writing emails.        Always replace the terms with those relevant to the {information}, ensuring the scenario is based on the specifics of the context and is open-ended for further exploration.
        Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
        Title must follow this Format:
            "[Short 3-4 word core areas] ( High Level Skill : skill1, skill2)"
            Example format:
                  "AI-Powered E-commerce Chatbots (High-Level Skill: NLP, Dialogflow)"
        Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.
        Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide a feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
        KLP - With each question add one or two line takeaway for providing feedback. The takeaways should be related to the question it is provided with.
        KLS - With each question, add the skill(s) that are highlly relevant to the scenario. All skills should be from the {skill_domain} only and must be taken from {targated skills} if defined.  And For every question choose exactly {%s} skill(s) and not more or less than {%s} should be chosen for each question. The skills for all the questions should be unique. Each question shall have a unique skill. Skill must be only maixmum two words. Each question must have a completely unique set of skills — no skill should repeat in any other question.
        Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
        Always Use a literary genre to generate the response in high literature.
        Literary genres encompass a wide spectrum of styles and themes, ranging from the imaginative realms of fiction, poetry, drama, and fantasy to the factual landscapes of non-fiction, biography, and autobiography. Mystery, science fiction, romance, historical fiction, and horror delve into specific narrative territories, while thriller, adventure, satire, comedy, tragedy, and epic offer diverse storytelling approaches. Additionally, fables, fairy tales, mythology, and folklore explore cultural narratives and traditions. Genres like dystopian, gothic, bildungsroman (coming-of-age), absurdist, and magical realism push the boundaries of conventional storytelling, while realistic fiction and experimental literature offer unique perspectives on reality and form. Each genre contributes to the rich tapestry of literary expression, offering readers a multitude of worlds and experiences to explore.
        In every response, you must:
        Clearly state your role as X.
        Identify Y as the person asking
        The Question, Custom Prompt, KLP, KLS should be numbered.
        Here the format looks like :
        "Title:",
        "Description:”,
        “Statement:",
        "Question 1:",
        "Prompt 1:",
        "Takeaway 1:" ,
        "Skills 1:" repeated for {%s} question(s). Do not include any {responder} response. NOTE: If {targated skills} are present then skills must be from the {targated skills}.
        'The Question, Prompt, Takeaway, Skills should be numbered.'
        NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
        NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
        NOTE: "Rating" must be included.
        NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated.
        NOTE : Make sure the simulation is very advanced and tough.
        NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
        NOTE: Always use suitable literary genre to genre create the response.
        NOTE: Never miss Title, Description, Statement and other variables.
        NOTE: Do not mention "X" or "Y".
        NOTE: must Follow the OUTPUT Format.
        \n\nAssistant:

        """

    elif scenario_type == "interview_static":
      prompt = """
        \n\nHuman:
        {Information} - %s
        Read this {information} thoroughly. Now, based on this information and your understanding, create an advanced and detailed scenario to practice the skills related to {skill_domain}. The scenario should be in the {department} department of a {industry} company. After creating the situation, provide these:
        Description - Define the situation and the problem. The problem should be related to the {information} provided. The description should always involve a conversation based on the context of the {information}. Make the description specific based on the information, focusing on relevant details. Provide the name of the individual in a leadership role based on the information, but never provide the name of the other person involved. The description should detail the situation that led to the issue, and it should not include dialogues. It should always be from a third-person perspective. Provide the description in 100 to 200 words. Avoid adding any conclusions. The situation should not be related to writing emails.        Always replace the terms with those relevant to the {information}, ensuring the scenario is based on the specifics of the context and is open-ended for further exploration.
        Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
        Title must follow this Format:
            "[Short 3-4 word core areas] ( High Level Skill : skill1, skill2)"
            Example format:
                  "AI-Powered E-commerce Chatbots (High-Level Skill: NLP, Dialogflow)"
        Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.
        Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide a feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
        KLP - With each question add one or two line takeaway for providing feedback. The takeaways should be related to the question it is provided with.
        KLS - With each question, add the skill(s) that are highlly relevant to the scenario. All skills should be from the {skill_domain} only and must be taken from {targated skills} if defined.  And For every question choose exactly {%s} skill(s) and not more or less than {%s} should be chosen for each question. The skills for all the questions should be unique. Each question shall have a unique skill. Skill must be only maixmum two words. Each question must have a completely unique set of skills — no skill should repeat in any other question.
        Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
        Always use a interview to generate the response for communication and information gathering.
        An interview is a formal conversation between an interviewer and an interviewee, typically in a professional setting, to assess the interviewee's suitability for a particular role or to gather information. It is a common practice in the corporate world and other professional settings, where employers or hiring managers conduct interviews to evaluate potential candidates for employment.
        In every response, you must:
        Clearly state your role as X.
        Identify Y as the person asking
        The Question, Custom Prompt, KLP, KLS should be numbered.
        Here the format looks like :
        "Title:",
        "Description:”,
        “Statement:",
        "Question 1:",
        "Prompt 1:",
        "Takeaway 1:" ,
        "Skills 1:" repeated for {%s} question(s). Do not include any {responder} response. NOTE: If {targated skills} are present then skills must be from the {targated skills}.
        'The Question, Prompt, Takeaway, Skills should be numbered.'
        NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
        NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
        NOTE: "Rating" must be included.
        NOTE : Make sure the simulation is very advanced and tough.
        NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated.
        NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
        NOTE: Always use interview for communication and information gathering.
        NOTE: Never miss Title, Description, Statement and other variables.
        NOTE: Do not mention "X" or "Y".
        NOTE: must Follow the OUTPUT Format.
        \n\nAssistant:
        """
    elif scenario_type == 'checkin_static':
      prompt = """

          \n\nHuman:
          {Information} - %s
          Read this {information} thoroughly. Now, based on this information and your understanding, create an advanced and detailed scenario to practice the skills related to {skill_domain}. The scenario should be in the {department} department of a {industry} company. After creating the situation, provide these:
          Description - Define the situation and the problem. The problem should be related to the {information} provided. The description should always involve a conversation based on the context of the {information}. Make the description specific based on the information, focusing on relevant details. Provide the name of the individual in a leadership role based on the information, but never provide the name of the other person involved. The description should detail the situation that led to the issue, and it should not include dialogues. It should always be from a third-person perspective. Provide the description in 100 to 200 words. Avoid adding any conclusions. The situation should not be related to writing emails.        Always replace the terms with those relevant to the {information}, ensuring the scenario is based on the specifics of the context and is open-ended for further exploration.
          Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description related to the check-in.
          Title must follow this Format:
            "[Short 3-4 word core areas] ( High Level Skill : skill1, skill2)"
            Example format:
                  "AI-Powered E-commerce Chatbots (High-Level Skill: NLP, Dialogflow)"
          Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.
          Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide a feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
          KLP - With each question add one or two line takeaway for providing feedback. The takeaways should be related to the question it is provided with.
          KLS - With each question, add the skill(s) that are highlly relevant to the scenario. All skills should be from the {skill_domain} only and must be taken from {targated skills} if defined. And For every question choose exactly {%s} skill(s) and not more or less than {%s} should be chosen for each question. The skills for all the questions should be unique. Each question shall have a unique skill. Skill must be only maixmum two words. Each question must have a completely unique set of skills — no skill should repeat in any other question.
          Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
          Always use a check-in to generate the response for communication and information gathering.
          Check-in in a corporate setting refers to the process of employees or participants recording their arrival at the workplace, a meeting, a conference, or any other professional gathering. This practice allows for improved attendance tracking, resource allocation, and streamlined communication within the enterprise.
          In every response, you must:
          Clearly state your role as X.
          Identify Y as the person asking
          The Question, Custom Prompt, KLP, KLS should be numbered.
          Here the format looks like :
          "Title:",
          "Description:”,
          “Statement:",
          "Question 1:",
          "Prompt 1:",
          "Takeaway 1:" ,
          "Skills 1:" repeated for {%s} question(s). Do not include any {responder} response. NOTE: If {targated skills} are present then skills must be from the {targated skills}.
          'The Question, Prompt, Takeaway, Skills should be numbered.'
          NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
          NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable like an check-in.
          . Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
          NOTE: "Rating" must be included.
          NOTE : Make sure the simulation is very advanced and tough.
          NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
          NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated.
          NOTE: Always use check-in for communication and information gathering.
          NOTE: Never miss Title, Description, Statement and other variables.
          NOTE: Do not mention "X" or "Y".
          NOTE: must Follow the OUTPUT Format.
          \n\nAssistant:

          """
    elif scenario_type == "static_hard":
      prompt = '''
      \n\nHuman:
            {Information} -
            %s -
            Read this {information} thoroughly. Now, based on this information and your understanding, create an advanced and detailed scenario to practice the skills related to {skill_domain}. The scenario should be in the {department} department of a {industry} company. After creating the situation, provide these:
            Description - Define the situation and the problem, and the problem focuses exclusively on hard skills. The problem should be related to the {information} provided. The description should always involve a conversation based on the context of the {information}. Make the description specific based on the information, focusing on relevant details. Provide the name of the individual in a leadership role based on the information, but never provide the name of the other person involved. The description should detail the situation that led to the issue, and it should not include dialogues. It should always be from a third-person perspective. Provide the description in 100 to 200 words. Avoid adding any conclusions. The situation should not be related to writing emails.        Always replace the terms with those relevant to the {information}, ensuring the scenario is based on the specifics of the context and is open-ended for further exploration.
            Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
            Title must follow this Format:
            "[Short 3-4 word core areas] ( High Level Skill : skill1, skill2)"
            Example format:
                  "AI-Powered E-commerce Chatbots (High-Level Skill: NLP, Dialogflow)"
            Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.Question shall focus exclusively on hard skills
            Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
            KLP - With each question add one or two line takeaways for providing feedback. The takeaways should be related to the question it is provided with.
            KLS - With each question, add the skill(s) that are highlly relevant to the scenario. All skills should be from the {skill_domain} only and must be taken from {targated skills} if defined.  And For every question choose exactly {%s} skill(s) and not more or less than {%s} should be chosen for each question. The skills for all the questions should be unique. Each question shall have a unique skill and focus exclusively on hard skills. Skill must be only maixmum two words. Each question must have a completely unique set of skills — no skill should repeat in any other question.
            Always end the description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
            In every response, you must:
            Clearly state your role as X as in (information).
            Identify Y as the person asking as in (information)
            The Question, Custom Prompt, KLP, KLS should be numbered.
            Here the format looks like :
            "Title:",
            "Description:”,
            “Statement:",
            "Question 1:",
            "Prompt 1:",
            "Takeaway 1:" ,
            "Skills 1:" repeated for {%s} question(s). Do not include any {responder} response. NOTE: If {targated skills} are present then skills must be from the {targated skills}.
            'The Question, Prompt, Takeaway, Skills should be numbered.'

            NOTE: Description, questions, and skills should focus exclusively on hard skills.
            NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
            NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
            NOTE: KLS - Always each question shall have a unique skill. Thes skill shall be comma separated. AND shall not repeat from (information).
            NOTE: "Rating" must be included.
            NOTE : Make sure the simulation is very advanced and tough.
            NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description] as in (information). Your intent is to achieve Z.
            NOTE: Never miss Title, Description, Statement and other variables.
            NOTE: must Follow the OUTPUT Format.
            \n\nAssistant:


      '''
    elif scenario_type == 'static_soft':
      prompt = """
            (information: %s)

            Carefully review and analyze the provided {information}. Based on this assessment, create a rigorous, high-level simulation that serves as an extended version of the previous scenario, diving deeper into the required skills and interactions. This new scenario must specifically address new areas for candidates to explore, ensuring a targeted approach to tackling an entirely new challenge.

            Key Requirements:
              Create a brand new scenaio in the same industry. Target ONLY soft skills that are not covered in the {information} context.
              Note: Never change the Industry Domain of the scenario.

            Deliver the extended scenario accordingly

            Read this {information} thoroughly. Now, based on this information and your understanding, create an advanced and detailed scenario to practice the skills related to {skill_domain}. The scenario should be in the {department} department of a {industry} company. After creating the situation, provide these:
            Description - Define the situation and the problem, and the problem focuses exclusively on soft skills. The problem should be related to the {information} provided. The description should always involve a conversation based on the context of the {information}. Make the description specific based on the information, focusing on relevant details. Provide the name of the individual in a leadership role based on the information, but never provide the name of the other person involved. The description should detail the situation that led to the issue, and it should not include dialogues. It should always be from a third-person perspective. Provide the description in 100 to 200 words. Avoid adding any conclusions. The situation should not be related to writing emails.        Always replace the terms with those relevant to the {information}, ensuring the scenario is based on the specifics of the context and is open-ended for further exploration.
            Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
            Title must follow this Format:
              "[Short 3-4 word core areas] ( High Level Skill : skill1, skill2)"
              Example format:
                    "AI-Powered E-commerce Chatbots (High-Level Skill: NLP, Dialogflow)"
            Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.Question shall focus exclusively on soft skills
            Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
            KLP - With each question add one or two line takeaways for providing feedback. The takeaways should be related to the question it is provided with.
            KLS - With each question, add the skill(s) that are highlly relevant to the scenario. All skills should be from the {skill_domain} only and must be taken from {targated skills} if defined.  And For every question choose exactly {%s} skill(s) and not more or less than {%s} should be chosen for each question. The skills for all the questions should be unique. Each question shall have a unique skill and focus exclusively on soft skills. Skill must be only maixmum two words. Each question must have a completely unique set of skills — no skill should repeat in any other question.
            Always end the description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
            In every response, you must:
            Clearly state your role as X as in (information).
            Identify Y as the person asking as in (information)
            The Question, Custom Prompt, KLP, KLS should be numbered.
            Here the format looks like :
            "Title:",
            "Description:”,
            “Statement:",
            "Question 1:",
            "Prompt 1:",
            "Takeaway 1:" ,
            "Skills 1:" repeated for {%s} question(s). Do not include any {responder} response. NOTE: If {targated skills} are present then skills must be from the {targated skills}.
            'The Question, Prompt, Takeaway, Skills should be numbered.'

            NOTE: Description, questions, and skills should focus exclusively on soft skills.
            NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
            NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
            NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated. AND shall not repeat from (SKILLS) instead use different skills.
            NOTE: "Rating" must be included.
            NOTE : Make sure the simulation is very advanced and tough.
            NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description] as in (information). Your intent is to achieve Z.
            NOTE: Never miss Title, Description, Statement and other variables.
            NOTE: Always use the same targeted skill(s) from (targeted_Skills), if available. Fill the skill_list or KLS as applicable using these (targeted skills). Generate every scenario strictly using only this skill(s).
            NOTE: must Follow the OUTPUT Format.
            \n\nAssistant:

      """
    elif scenario_type == 'static_role_play_soft':
      prompt = """
      \n\nHuman:
                {Information} - %s-
                Read this {information} thoroughly. Now, based on this information and your understanding, create an advanced and detailed scenario to practice the skills related to {skill_domain}. The scenario should be in the {department} department of a {industry} company. After creating the situation, provide these:
                Description - Define the situation and the problem, and the problem focuses exclusively on soft skills. The problem should be related to the {information} provided. The description should always involve a conversation based on the context of the {information}. Make the description specific based on the information, focusing on relevant details. Provide the name of the individual in a leadership role based on the information, but never provide the name of the other person involved. The description should detail the situation that led to the issue, and it should not include dialogues. It should always be from a third-person perspective. Provide the description in 100 to 200 words. Avoid adding any conclusions. The situation should not be related to writing emails.        Always replace the terms with those relevant to the {information}, ensuring the scenario is based on the specifics of the context and is open-ended for further exploration. It shall always remain between two specific individuals, as determined by the context provided in the {information}.
                Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.

                Title must follow this Format:
                  "[Short 3-4 word core areas] ( High Level Skill : skill1, skill2)"
                  Example format:
                        "AI-Powered E-commerce Chatbots (High-Level Skill: NLP, Dialogflow)"
                Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the problem. NEVER respond to the questions. Question shall focus exclusively on soft skills
                Custom prompt - With each question, add a prompt asking for feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}
                KLP - With each question add one or two line takeaways for providing feedback. The takeaways should be related to the question it is supplied with.
                KLS - With each question, add the skill(s) that are highlly relevant to the scenario. All skills should be from the {skill_domain} only and must be taken from {targated skills} if defined.  And For every question choose exactly {%s} skill(s) and not more or less than {%s} should be chosen for each question. The skills for all the questions should be unique. Each question shall have a unique skill and focus exclusively on soft skills. Skill must be only maixmum two words. Each question must have a completely unique set of skills — no skill should repeat in any other question.
                Always use indian names in the role play, also mention what role the user will be playing while answering the questions in the description.
                Always use name in each question. The role play shall also have element of a other person who will be asking the questions.
                Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
                The Question, Custom Prompt, KLP, KLS should be numbered.
                Here the format looks like :
                "Title:",
                "Description:”,
                “Statement:",
                "Question 1:",
                "Prompt 1:",
                "Takeaway 1:" ,
                "Skills 1:" repeated for {%s} question(s). Do not include any {responder} response. NOTE: If {targated skills} are present then skills must be from the {targated skills}.
                'The Question, Prompt, Takeaway, Skills should be numbered.'

                NOTE: Description, questions, and skills should focus exclusively on soft skills.
                NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
                NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
                NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated.
                NOTE: "Rating" must be included.
                NOTE: Make sure the roleplay is very advanced and tough.
                NOTE: Always use a name in each question. The role play shall also have the element of an other person who will be asking the questions.
                NOTE: Always mention in the context what role the user will be playing the role while answering.
                NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
                NOTE: Never miss Title, Description, Statement and other variables.
                NOTE: Always use the same targeted skill(s) from (targeted_Skills), if available. Fill the skill_list or KLS as applicable using these (targeted skills). Generate every scenario strictly using only this skill(s).
                NOTE: must Follow the OUTPUT Format.
                \n\nAssistant:

      """

    elif scenario_type == 'static_role_play_hard':
      prompt = """
      \n\nHuman:
                {Information} - %s-
                Read this {information} thoroughly. Now, based on this information and your understanding, create an advanced and detailed scenario to practice the skills related to {skill_domain}. The scenario should be in the {department} department of a {industry} company. After creating the situation, provide these:
                Description - Define the situation and the problem, and the problem focuses exclusively on hard skills. The problem should be related to the {information} provided. The description should always involve a conversation based on the context of the {information}. Make the description specific based on the information, focusing on relevant details. Provide the name of the individual in a leadership role based on the information, but never provide the name of the other person involved. The description should detail the situation that led to the issue, and it should not include dialogues. It should always be from a third-person perspective. Provide the description in 100 to 200 words. Avoid adding any conclusions. The situation should not be related to writing emails.        Always replace the terms with those relevant to the {information}, ensuring the scenario is based on the specifics of the context and is open-ended for further exploration. It shall always remain between two specific individuals, as determined by the context provided in the {information}.
                Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
                Title must follow this Format:
                  "[Short 3-4 word core areas] ( High Level Skill : skill1, skill2)"
                  Example format:
                        "AI-Powered E-commerce Chatbots (High-Level Skill: NLP, Dialogflow)"
                Questions - Develop a set of {%s} question(s) ONLY based on the situation. The questions should be related to the problem. NEVER respond to the questions. Question shall focus exclusively on hard skills
                Custom prompt - With each question, add a prompt asking for feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {Please provide feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}

                KLP - With each question add one or two line takeaways for providing feedback. The takeaways should be related to the question it is supplied with.
                KLS - With each question, add the skill(s) that are highlly relevant to the scenario. All skills should be from the {skill_domain} only and must be taken from {targated skills} if defined. And For every question choose exactly {%s} skill(s) and not more or less than {%s} should be chosen for each question. The skills for all the questions should be unique. Each question shall have a unique skil and focus exclusively on hard skills. Skill must be only maixmum two words. Each question must have a completely unique set of skills — no skill should repeat in any other question.
                Always use indian names in the role play, also mention what role the user will be playing while answering the questions in the description.
                Always use name in each question. The role play shall also have element of a other person who will be asking the questions.
                Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
                The Question, Custom Prompt, KLP, KLS should be numbered.
                Here the format looks like :
                "Title:",
                "Description:”,
                “Statement:",
                "Question 1:",
                "Prompt 1:",
                "Takeaway 1:" ,
                "Skills 1:" repeated for {%s} question(s). Do not include any {responder} response. NOTE: If {targated skills} are present then skills must be from the {targated skills}.
                'The Question, Prompt, Takeaway, Skills should be numbered.'

                NOTE: Description, questions, and skills should focus exclusively on hard skills.
                NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.
                NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - for example: "Rating : 6". Rating Must be in output. Do not include any other explanation.
                NOTE: KLS - Always each question shall have a unique skill. The skill shall be comma separated.
                NOTE: "Rating" must be included.
                NOTE: Make sure the roleplay is very advanced and tough.
                NOTE: Always use a name in each question. The role play shall also have the element of an other person who will be asking the questions.
                NOTE: Always mention in the context what role the user will be playing the role while answering.
                NOTE: Never miss this, Always end description with this approach and mention this in the “statement”: You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve Z.
                NOTE: Never miss Title, Description, Statement and other variables.

                \n\nAssistant:



      """
    elif scenario_type == 'dynamic_start_with_user':
      prompt = """
      \n\nHuman:
      {Information} - %s

      Read the provided *{information}* thoroughly. Make sure to note the "start-with-user" field, which determines the direction of the conversation. For example, if it shows "customer-sales", then the customer is the responder and the salesperson is the asker. If it shows "sales-customer", then the salesperson is the responder and the customer is the asker. If it shows "team-manager", the team member is the responder and the manager is the asker. If it shows "manager-team", the manager is the responder and the team member is the asker.
      Use this information to construct a realistic, advanced, and specific conversation scenario following the instructions below.
      Description:
      Create a situation that involves a live conversation between two individuals, based on the context given in the *{information}*. The narrative must be written entirely in third person and should clearly state the their roles. Define the situation and the problem. The problem must be directly relevant to the {information}.
      Include rich, specific details such as the setting, context, goals, and underlying tensions. The scenario must stem from a live, real-time conversation and must not involve emails, written exchanges, or hypothetical outcomes. The final output should be between 100 and 200 words, focusing only on the situation and the issue at hand. Do not include dialogue, conclusions, or resolutions.
      The scenario must remain open-ended to allow room for further exploration. All terms and context must be adapted specifically to the {information} provided, ensuring full alignment with the described roles and situation.
      According to the description always end description with this approach and mention this : You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve the {intent}.
      In every response, you must:
      Clearly state your role as X.
      Identify Y as the person asking
      Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
      Title must follow this Format:
            "[Short 3-4 word core areas] ( High Level Skill : skill1, skill2)"
            Example format:
                  "AI-Powered E-commerce Chatbots (High-Level Skill: NLP, Dialogflow)"

      Prompts - As given in the output format.


      Here the format looks like :
      {
        "Title": "GIVE TITLE",
        "Context": "GIVE DESCRIPTION",
        "Candidate Type": based on information who will respond” ,
        "Scenario Case": "dynamic_discussion",
        "Email Address List": "mail@coachbots.com",
        "Certificate Title": "SAME AS TITLE",
        "Area/Domain": "BASED ON TITLE AND DESCRIPTION",
        "start with user": "based on information",
        "skill_list": "add the skill(s) that are highlly relevant to the scenario. All skills should be from the {skill_domain} only and must be taken from {targated skills} if defined.  And For every question choose exactly {8} skill(s) and not more or less than {8} should be chosen for each question. The skills for all the questions should be unique. Each question shall have a unique skill. A comma seprated list of skills should be provided. Skill must be only maixmum two words.",
        "is_dynamic_thread": true,
        "Responder": "the second person name who will ask the questions",
        "Person 0": "the second person name who will ask the questions :",
        "0": "Please respond in order to continue.",
        "1": "Now the second person name who will ask the questions will respond to this remark as a Selfish type of person.",
        "2": "Please respond in order to continue.",
        "3": "Now the second person name who will ask the questions will respond to this remark as a Insincere type of person.",
        "4": "Conclude the discussion as a participant.",
      }


      Do not include any response.
      Always provide the output in the given format.

      NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.

      NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - "Rating : 6". Do not include any other explanation.

      NOTE : Make sure the situation is very advanced and tough.

      NOTE : there must be only one manager in picture.

      NOTE : Never miss the Title, Description, Questions.
      NOTE: Do not mention literal "X", "Y".
      NOTE: If {targated skills} are present then "skill_list" must be from the {targated skills}.

      \n\nAssistant:

      """


      return f"{prompt}"%(information)

    if scenario_type == 'normal_dynamic_test':
        prompt = '''
            \n\nHuman:
                          {Information} - (%s)

                          Read this {information} thoroughly. Now, based on this information and your understanding, create an advanced and detailed scenario to practice the skills related to {skill_domain}. The scenario should be in the {department} department of a {industry} company. After creating the situation, provide these:

                          Description - Define the situation and the problem. The problem should be related to the {information} provided. The description should always involve a conversation based on the context of the {information}. Make the description specific based on the information, focusing on relevant details. Provide the name of the individual in a leadership role based on the information, but never provide the name of the other person involved. The description should detail the situation that led to the issue, and it should not include dialogues. It should always be from a third-person perspective. Provide the description in 100 to 200 words. Avoid adding any conclusions. The situation should not be related to writing emails.
                          Always replace the terms with those relevant to the {information}, ensuring the scenario is based on the specifics of the context and is open-ended for further exploration.
                          According to the description always end description with this approach and mention this : You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve the {intent}.
                          In every response, you must:
                          Clearly state your role as X.
                          Identify Y as the person asking
                          Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
                          Title must follow this Format:
                            "[Short 3-4 word core areas] ( High Level Skill : skill1, skill2)"
                            Example format:
                                  "AI-Powered E-commerce Chatbots (High-Level Skill: NLP, Dialogflow)"
                          Questions - Give me the first question based on the situation in description .The question should be deep, thoughtful and realistic. Give the name of person asking the question. Keep it less than 35 words. NEVER provide a response to the question. Never start with any introduction sentences. Start with the question directly.
                          use this template strictly to generate Questions: ""Thank for connecting. I am looking forward to learning more about the {intent}."". Strictly follow this template structure and do not print any sentence with a question mark.

                          KLS - With each question, add the skill(s) that are highlly relevant to the scenario. All skills should be from the {skill_domain} only and must be taken from {targated skills} if defined.  And For every question choose exactly {8} skill(s) and not more or less than {8} should be chosen for each question. The skills for all the questions should be unique. Each question shall have a unique skill. A comma seprated list of skills should be provided. Skill must be only maixmum two words.
                          Output format - Y: question?
                          For example - Ajay: question?

                          Prompts - As given in the output format.

                          Here the format looks like :

                          Title:
                          Description:
                          Questions:
                          Skills:
                          Prompts: - ["Please respond in order to continue.",
                          "Respond as {Y}",
                          ]


                          Note: Add in prompts set of above ["Please respond in order to continue.",
                          "Respond as {Y}",
                          ] for {%s} and at last add "Conclude the discussion as a participant."

                          Write the manager's name in place of {Y}. The Y should always be the same. Do not make any changes in the given format. .

                          Do not include any response.
                          Always provide the output in the given format.
                          NOTE: If {targated skills} are present then "Skills" must be from the {targated skills}.

                          NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.

                          NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - "Rating : 6". Do not include any other explanation.

                          NOTE : Make sure the situation is very advanced and tough.

                          NOTE : there must be only one manager in picture.

                          NOTE : Never miss the Title, Description, Questions, Skills.
                          NOTE: Do not mention literal "X", "Y".
                          NOTE: must Follow the OUTPUT Format.

                          \n\nAssistant:



          '''

        return f"{prompt}"%(information,question_count*2-2)

    if scenario_type == 'normal_dynamic_test_hard':
        prompt = '''
          \n\nHuman:
                        {Information} - (%s)

                        Read this {information} thoroughly. Now, based on this information and your understanding, create an advanced and detailed scenario to practice the skills related to {skill_domain}. The scenario should be in the {department} department of a {industry} company. After creating the situation, provide these:
                        Description - Define the situation and the problem and the problem focuses exclusively on hard skills. The problem should be related to the {information} provided. The description should always involve a conversation based on the context of the {information}. Make the description specific based on the information, focusing on relevant details. Provide the name of the individual in a leadership role based on the information, but never provide the name of the other person involved. The description should detail the situation that led to the issue, and it should not include dialogues. It should always be from a third-person perspective. Provide the description in 100 to 200 words. Avoid adding any conclusions. The situation should not be related to writing emails.        Always replace the terms with those relevant to the {information}, ensuring the scenario is based on the specifics of the context and is open-ended for further exploration.
                        According to the description always end description with this approach and mention this : You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve the {intent}.
                        In every response, you must:
                        Clearly state your role as X.
                        Identify Y as the person asking
                        Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
                        Title must follow this Format:
                          "[Short 3-4 word core areas] ( High Level Skill : skill1, skill2)"
                          Example format:
                                "AI-Powered E-commerce Chatbots (High-Level Skill: NLP, Dialogflow)"
                        Questions - Give me the first question based on the situation in description .The question should be deep, thoughtful and realistic. Give the name of person asking the question. Keep it less than 35 words. NEVER provide a response to the question. Question shall focus exclusively on hard skills. Never start with any introduction sentences. Start with the question directly.
                        use this template strictly to generate Questions: ""Thank for connecting. I am looking forward to learning more about the {intent}."". Strictly follow this template structure and do not print any sentence with a question mark.

                        KLS - With each question, add the skill(s) that are highlly relevant to the scenario. All skills should be from the {skill_domain} only and must be taken from {targated skills} if defined.  And For every question choose exactly {8} skill(s) and not more or less than {8} should be chosen for each question. The skills for all the questions should be unique. Each question shall have a unique skill. and focus exclusively on hard skills. A comma seprated list of skills should be provided. Skill must be only maixmum two words.
                        Output format - Y: question?
                        For example - Ajay: question?

                        Prompts - As given in the output format.

                        Here the format looks like :

                        Title:
                        Description:
                        Questions:
                        Skills:
                        Prompts: - ["Please respond in order to continue.",
                        "Respond as {Y}",
                        ]


                        Note: Add in prompts set of above ["Please respond in order to continue.",
                        "Respond as {Y}",
                        ] for {%s} and at last add "Conclude the discussion as a participant."

                        Write the manager's name in place of {Y}. The Y should always be the same. Do not make any changes in the given format. .

                        Do not include any response.
                        Always provide the output in the given format.
                        NOTE: Description, questions, and Skills should focus exclusively on hard skills.
                        NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.

                        NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - "Rating : 6". Do not include any other explanation.

                        NOTE : Make sure the situation is very advanced and tough.

                        NOTE : there must be only one manager in picture.

                        NOTE : Never miss the Title, Description, Questions, Skills.
                        NOTE: Do not mention literal "X", "Y".
                        NOTE: If {targated skills} are present then "Skills" must be from the {targated skills}.
                        NOTE: must Follow the OUTPUT Format.

                        \n\nAssistant:


        '''

        return f"{prompt}"%(information,question_count*2-2)

    if scenario_type == 'normal_dynamic_test_soft':
        prompt = '''
                        \n\nHuman:
                        {Information} - (%s)

                        Read this {information} thoroughly. Now, based on this information and your understanding, create an advanced and detailed scenario to practice the skills related to {skill_domain}. The scenario should be in the {department} department of a {industry} company. After creating the situation, provide these:
                        Description - Define the situation and the problem and the problem focuses exclusively on soft skills. The problem should be related to the {information} provided. The description should always involve a conversation based on the context of the {information}. Make the description specific based on the information, focusing on relevant details. Provide the name of the individual in a leadership role based on the information, but never provide the name of the other person involved. The description should detail the situation that led to the issue, and it should not include dialogues. It should always be from a third-person perspective. Provide the description in 100 to 200 words. Avoid adding any conclusions. The situation should not be related to writing emails.        Always replace the terms with those relevant to the {information}, ensuring the scenario is based on the specifics of the context and is open-ended for further exploration.
                        According to the description always end description with this approach and mention this : You are X, interacting with Y. Y will ask you questions related to [description]. Your intent is to achieve the {intent}.
                        In every response, you must:
                        Clearly state your role as X.
                        Identify Y as the person asking
                        Title - Give a specific and relevant title for this description. The title should NEVER be less than 8 words. The title should always be directly related to the given description. Make it very specific to the description.
                        Title must follow this Format:
                            "[Short 3-4 word core areas] ( High Level Skill : skill1, skill2)"
                            Example format:
                                  "AI-Powered E-commerce Chatbots (High-Level Skill: NLP, Dialogflow)"
                        Questions - Give me the first question based on the situation in description .The question should be deep, thoughtful and realistic. Give the name of person asking the question. Keep it less than 35 words. NEVER provide a response to the question. Question shall focus exclusively on soft skills. Never start with any introduction sentences. Start with the question directly.
                        use this template strictly to generate Questions: ""Thank for connecting. I am looking forward to learning more about the {intent}."". Strictly follow this template structure and do not print any sentence with a question mark.

                        KLS - With each question, add the skill(s) that are highlly relevant to the scenario. All skills should be from the {skill_domain} only and must be taken from {targated skills} if defined.  And For every question choose exactly {8} skill(s) and not more or less than {8} should be chosen for each question. The skills for all the questions should be unique. Each question shall have a unique skill. and focus exclusively on soft skills. A comma seprated list of skills should be provided. Skill must be only maixmum two words.
                        Output format - Y: question?
                        For example - Ajay: question?

                        Prompts - As given in the output format.skill_list

                        Here the format looks like :

                        Title:
                        Description:
                        Questions:
                        Skills:
                        Prompts: - ["Please respond in order to continue.",
                        "Respond as {Y}",
                        ]


                        Note: Add in prompts set of above ["Please respond in order to continue.",
                        "Respond as {Y}",
                        ] for {%s} and at last add "Conclude the discussion as a participant."

                        Write the manager's name in place of {Y}. The Y should always be the same. Do not make any changes in the given format. .

                        Do not include any response.
                        Always provide the output in the given format.
                        NOTE: Description, questions, and Skills should focus exclusively on soft skills.
                        NOTE: The title should NEVER be less than 8 words. Make the title detailed for the description.

                        NOTE : Based on this information {information} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - "Rating : 6". Do not include any other explanation.

                        NOTE : Make sure the situation is very advanced and tough.

                        NOTE : there must be only one manager in picture.

                        NOTE : Never miss the Title, Description, Questions, Skills.
                        NOTE: Do not mention literal "X", "Y".
                        NOTE: If {targated skills} are present then "Skills" must be from the {targated skills}.
                        NOTE: must Follow the OUTPUT Format.
                        \n\nAssistant:


        '''

        return f"{prompt}"%(information,question_count*2-2)


    return f"{prompt}"%(information, question_count, skill_count, skill_count, question_count)



from string import Template


def get_game_prompt(industry, information, num_of_questions, question_type, candidate_type):
  prompt = '''
    Create a large "${Industry}" corporate scenario is less than 100 words with a title upto 8-12 words that related to : (${information}).

    Further create ${num_of_questions} MCQ questions with 4 options each that are related to the paragraph that the user must answer as a new manager tasked with solving the issue at hand.
    The Questions must have 4 options and will have ${question_type} right answer - however they should not be straightforward and it may appear other choices are right as well.
    Always end the description with As a ${candidate_type} select the right option for the questions presented below.

    GIVE IN THIS VALID JSON FORMAT:
    json ```
    {
      "title": "title goes here",
      "description": "decrtiption title goes here",
      "is_single_select": "TRUE or FALSE",
      "questions" :[
        {
          ""context"": {
            ""section"": ""Section Text""
          },
          ""details"": {
            ""question"": ""Question Text""
          },
          ""content"": {
            ""instruction"": ""Choose one or more options from A, B, C or D"",
            ""options"": {

                ""A"": ""Option A"",
                ""B"": ""Option B"",
                ""C"": ""Option C"",
                ""D"": ""Option D""

            }
          }
        },
      ],
    }
    ```

    (If the prompt mentions "single," then the value of "is_single_select" should be "TRUE" instead.)
    (If the prompt mentions "multiple," then the value of "is_single_select" should be "FALSE" instead.)
    NOTE: All keys required in output format.

    '''

  return Template(prompt).substitute(Industry=industry, information=information, num_of_questions=num_of_questions, question_type=question_type, candidate_type=candidate_type)

def format_game_custom_prompt(is_single_select, questions, title, description, num_of_questions=None, static=True):
  instruction = "Choose one option from A, B, C or D" if is_single_select else "Choose one or more options from A, B, C or D"
  if static:
    questions = "\n\n".join([str(i) for i in questions])
    custom_prompt = """
    **Prompt Guidelines:**

    1. **Display the End Game Message**: Ensure the final message appears as specified, substituting 'x' with the player's total score and replacing '[Game Name]' with the actual game title:
      - Congratulations 🎉. You have completed the [Game Name]. You have achieved a score of [x out of 100].

    2. **No clipping or trucation of text**: Ensure that each option is presented in its entirety, without any clipping or truncation of text. Do not hallucinate or invent options; present only the options exactly as provided in the game design.

    3. **Demand Correct Input for Progression**: Require players to input a valid choice precisely to advance to subsequent levels. Repeat the prompt until a correct input is received.

    4. **Display the Feedback**: Upon game completion, provide approximately 50 words of feedback summarizing the impact of the user's choices on the outcome. Briefly suggest alternative strategies for potentially improved results in future playthroughs.

    5. **Always Present Full Level Details**: Consistently show all levels and options exactly as scripted. Complete all levels and only give feedback as last. Every level and option must be displayed in full, without omission or partial rendering of any text.

    6. **Start with Level Prompt**: When the command """"START"""" is given, begin immediately with the first level.

    7. **Output in JSON format**:  Ensure that the game’s output is formatted as valid JSON. Below is the structure:
    json
    if game not ended:
      ``` json
      {
        ""context"": {
          ""section"": ""Section Text""
        },
        ""details"": {
          ""question"": ""Question Text""
        },
        ""content"": {
          ""instruction"": ""${instruction}"",
          ""options"": {

              ""A"": ""Option A"",
              ""B"": ""Option B"",
              ""C"": ""Option C"",
              ""D"": ""Option D""

          }
        }
      }
    ```
    if game ended:
    json
    {
    ""end_message"" : ""[End Game Message]"",
    ""feedback"": ""[Feedback Text]""
    }


    Let's continue with the game using these guidelines.

    ---
    ## Title:
    ${title}

    ## Overview & Gameplay Objectives:
    ${description}

    ---
    if game not ended:
    Ensure that the game’s output is formatted as valid JSON. Below is the structure:
    json
    if game not ended:
    ```json
    ${questions}
    ```
    ---

    ## End Game Message:
    Congratulations 🎉. You have completed the [Game Name]. You have achieved a score of [x out of 100].

    ## Feedback:
    Provide 50 words of feedback regarding the answers of the options chosen by the user, and suggest if they could have done anything better."
    """

    return Template(custom_prompt).substitute(instruction=instruction,questions=questions,title=title,description=description)
  else:
    custom_prompt = """
    **Prompt Guidelines:**

    1. **Display the End Game Message**: Ensure the final message appears as specified, substituting 'x' with the player's total score and replacing '[Game Name]' with the actual game title:
      - Congratulations 🎉. You have completed the [Game Name]. You have achieved a score of [x out of 100].

    2. **No clipping or trucation of text**: Ensure that each option is presented in its entirety, without any clipping or truncation of text. Do not hallucinate or invent options; present only the options exactly as provided in the game design.

    3. **Demand Correct Input for Progression**: Require players to input a valid choice precisely to advance to subsequent levels. Repeat the prompt until a correct input is received.

    4. **Display the Feedback**: Upon game completion, provide approximately 50 words of feedback summarizing the impact of the user's choices on the outcome. Briefly suggest alternative strategies for potentially improved results in future playthroughs.

    5. **Always Present Full Level Details**: Consistently show all levels and options exactly as scripted. Complete all levels and only give feedback as last. Every level and option must be displayed in full, without omission or partial rendering of any text.

    6. **Start with Level Prompt**: When the command """"START"""" is given, begin immediately with the first level.

    7. **Output in JSON format**:  Ensure that the game’s output is formatted as valid JSON. Below is the structure:
    json
    if game not ended:
      ``` json
    {
        ""context"": {
          ""section"": ""Section Text""
        },
        ""details"": {
          ""question"": ""Question Text""
        },
        ""content"": {
          ""instruction"": ""${instruction}"",
          ""options"": {

              ""A"": ""Option A"",
              ""B"": ""Option B"",
              ""C"": ""Option C"",
              ""D"": ""Option D""

          }questions
        }
      }
    ```
    if game ended:
    json
    {
    ""end_message"" : ""[End Game Message]"",
    ""feedback"": ""[Feedback Text]""
    }

    8. **Craft Challenging Decision Options**: Offer related and nuanced options prompting strategic contemplation for informed decision-making.

    9. **Total Number of Levels** = ${number_of_level}

    Let's continue with the game using these guidelines.

    ---

    "## Title:
    ""${title}""
    ## Overview & Gameplay Objectives:
    ${description}
    ---
    if game not ended:
    Ensure that the game’s output is formatted as valid JSON. Below is the structure:
    json
    if game not ended:
      ```json
    {
        ""context"": {
          ""section"": ""Section Text""
        },
        ""details"": {
          ""question"": ""Question Text""
        },
        ""content"": {
          ""instruction"": ""${instruction}"",
          ""options"": {

              ""A"": ""Option A"",
              ""B"": ""Option B"",
              ""C"": ""Option C"",
              ""D"": ""Option D""

          }
        }
      }
```
    ---

    ## End Game Message:
    Congratulations 🎉. You have completed the [Game Name]. You have achieved a score of [x out of 100].

    ## Feedback:
    Provide 50 words of feedback regarding the answers of the options chosen by the user, and suggest if they could have done anything better.


        """

    return Template(custom_prompt).substitute(instruction=instruction,title=title,description=description,number_of_level=num_of_questions)


def feedback_video_script_template(responder, asker,department, industry, objective, domain_skill, klps, dynamic=False):
    script = f"""
        Hey, This is Maya. your feedback coach. Thank you for completing your roleplay simulation. Putting yourself in the shoes of the {responder} in the {department} Department of the {industry} can be challenging! When you are dealing with such situations with your {asker} do this.  Always take a pause. See what are the key skills you must possess. And how you should demonstrate them. In other words - what to say. And how to say it. To unpack it further here are the basics: {objective}. Your level II skill details you can find in the report.
    """
    klps_script = f"""
    The key learning points here : "
    {klps} ".
    Don't forget to check out the details in the report!"""

    if dynamic:
      klps_script = """
        The key learning points here : "${klps} ".
      Don't forget to check out the details in the report!
      """
    return script + "\n" + klps_script
