def get_focus_prompt(focus_areas, type):
    simulation_prompt = """
        \n\nHuman:
        {{Information}} - %s

        Read this {{information}} thoroughly. Now based on this information and your understanding  create an advanced and tough simulation situation for the key focus areas presented in the {{information}}. After creating the situation provide these:

        Description - Define the situation, and the problem. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on data, industry, events, etc. The description should just describe the problem and what was the specific situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.  It should not be about writing an email.
        Title - Give a specific and relevant title for this description in less than 10 words.
        Questions - Develop a set of {3} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.
        Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {{Please provide a feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}}
        KLP - With each question add one or two line takeaway for providing feedback. The takeaways should be related to the question it is provided with.
        KLS - With each question, add the skill(s) that are tested. And For every question choose exactly {2} skill(s) and not more or less than {2} should be chosen for each question. The skills for all the questions should be unique.
        The Question, Custom Prompt, KLP, KLS should be numbered.

        Here the format looks like :

        "Title",

        "Description",

        "Question 1",

        "Prompt 1",

        "Takeaway 1" ,

        "Skills 1" repeated for {3} question(s). Do not include any {{responder}}response.

        'The Question, Prompt, Takeaway, Skills should be numbered.'

        NOTE : Based on this information {{information}} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - "Rating : 6". Do not include any other explanation.
        
        NOTE : Make sure the simulation is very advanced and tough.
        \n\nAssistant:

        """%(focus_areas)
    

    dynamic_prompt = """
        \n\nHuman:
        {{Information}} - %s

        Read this {{information}} thoroughly. Now based on this information and your understanding create an advanced and detailed situation for the key focus areas presented in the {{information}}. After creating the situation provide these:

        Description - Define the situation, and the problem. The problem should be a normal corporate problem. The description should always be about a conversation between the manager and a team member. Make the description specific based on data, industry, events, etc. Give the name of the manager. Never give the name of the team member. The description should just describe the problem and what was the specific situation that led to this problem. Keep the context Indian. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.  It should not be about writing an email.
        Title - Give a specific and relevant title for this description in less than 10 words.
        Questions - Give me the first question the manager will ask the team member based on the situation. The question should be deep, thoughtful and realistic. Give the name of person asking the question. Keep it less than 35 words. NEVER provide a response to the question. Never start with any introduction sentences. Start with the question directly. 
        Output format - Manager name: Question
        Prompts - As given in the output format. 

        Here the format looks like :
        Scenario 1:,

        "Title:",

        "Description:",

        "Question:",

        "Prompts:" - ["Please respond in order to continue." 
        "Respond as {{Manager name}}", 
        "Please respond in order to continue." 
        "Respond as {{Manager name}}", 
        "Please respond in order to continue." 
        "Respond as {{Manager name}}", 
        "Please respond in order to continue." 
        "Respond as {{Manager name}}", 
        "Please respond in order to continue." 
        "Respond as{{Manager name}}"
        "Conclude the discussion as a participant."]

        Write the manager's name in place of {{Manager name}}. The Manager name should always be same. Do not make any changes in the given format.  

        Do not include any response.
        Always provide the output in the given format. 

        NOTE : Based on this information {{Manager name}} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - "Rating : 6". Do not include any other explanation.
        
        NOTE : Make sure the situation is very advanced and tough.
        \n\nAssistant:
    
    """%(focus_areas)

    if type == "dynamic":
        return dynamic_prompt
    return simulation_prompt



def get_goals_prompt(goals, type):
    simulation_prompt = """
        \n\nHuman:
        {{Information}} - %s

        Read this {{information}} thoroughly. Now based on this information and your understanding  create an advanced and tough simulation situation to achieve the long term goals presented in the {{information}}. After creating the situation provide these:

        Description - Define the situation, and the problem. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on data, industry, events, etc. The description should just describe the problem and what was the specific situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.  It should not be about writing an email.
        Title - Give a specific and relevant title for this description in less than 10 words.
        Questions - Develop a set of {3} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.
        Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {{Please provide a feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}}
        KLP - With each question add one or two line takeaway for providing feedback. The takeaways should be related to the question it is provided with.
        KLS - With each question, add the skill(s) that are tested. And For every question choose exactly {2} skill(s) and not more or less than {2} should be chosen for each question. The skills for all the questions should be unique.
        The Question, Custom Prompt, KLP, KLS should be numbered.

        Here the format looks like :

        "Title",

        "Description",

        "Question 1",

        "Prompt 1",

        "Takeaway 1" ,

        "Skills 1" repeated for {3} question(s). Do not include any {{responder}} response.

        'The Question, Prompt, Takeaway, Skills should be numbered.'

        NOTE : Based on this information {{information}} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - "Rating : 6". Do not include any other explanation.
        
        NOTE : Make sure the simulation is very advanced and tough.
        \n\nAssistant:
    """%(goals)


    dynamic_prompt = """
        \n\nHuman:
        {{Information}} - %s

        Read this {{information}} thoroughly. Now based on this information and your understanding create an advanced and detailed situation to achieve the long term goals presented in the {{information}}. After creating the situation provide these:

        Description - Define the situation, and the problem. The problem should be a normal corporate problem. The description should always be about a conversation between the manager and a team member. Make the description specific based on data, industry, events, etc. Give the name of the manager. Never give the name of the team member. The description should just describe the problem and what was the specific situation that led to this problem. Keep the context Indian. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.  It should not be about writing an email.
        Title - Give a specific and relevant title for this description in less than 10 words.
        Questions - Give me the first question the manager will ask the team member based on the situation. The question should be deep, thoughtful and realistic. Give the name of person asking the question. Keep it less than 35 words. NEVER provide a response to the question. Never start with any introduction sentences. Start with the question directly. 
        Output format - Manager name: Question
        Prompts - As given in the output format. 

        Here the format looks like :
        Scenario 1:,

        "Title:",

        "Description:",

        "Question:",

        "Prompts:" - ["Please respond in order to continue." 
        "Respond as {{Manager name}}", 
        "Please respond in order to continue." 
        "Respond as {{Manager name}}", 
        "Please respond in order to continue." 
        "Respond as {{Manager name}}", 
        "Please respond in order to continue." 
        "Respond as {{Manager name}}", 
        "Please respond in order to continue." 
        "Respond as {{Manager name}}"
        "Conclude the discussion as a participant."]

        Write the manager's name in place of {{Manager name}}. The Manager name should always be same. Do not make any changes in the given format.  

        Do not include any response.
        Always provide the output in the given format. 

        NOTE : Based on this information {{information}} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - "Rating : 6". Do not include any other explanation.
        
        NOTE : Make sure the situation is very advanced and tough.
        \n\nAssistant:
    """%(goals)

    if type == "dynamic":
        return dynamic_prompt
    return simulation_prompt


def get_priority_prompt(priorities, type):
    simulation_prompt ="""
        \n\nHuman:
        {{Information}} - %s

        Read this {{information}} thoroughly. Now based on this information and your understanding  create an advanced and tough simulation situation based on the priorities presented in the {{information}}. After creating the situation provide these:

        Description - Define the situation, and the problem. Never mention any characters or character names in the description. The problem should be a normal corporate problem. Make the description specific based on data, industry, events, etc. The description should just describe the problem and what was the specific situation that led to this problem. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.  It should not be about writing an email.
        Title - Give a specific and relevant title for this description in less than 10 words.
        Questions - Develop a set of {3} question(s) ONLY based on the situation. The questions should be related to the situation. NEVER provide a response to the questions.
        Custom prompt - With each question, add a prompt that would ask feedback from Anthropic about the RESPONSE quality based on best practices. The prompt should ONLY evaluate the quality of the response. NEVER give the prompts to evaluate the questions. Example - {{Please provide a feedback on the manager's response if the manager focuses on making the team member understand the metrics instead of focusing on the results.}}
        KLP - With each question add one or two line takeaway for providing feedback. The takeaways should be related to the question it is provided with.
        KLS - With each question, add the skill(s) that are tested. And For every question choose exactly {2} skill(s) and not more or less than {2} should be chosen for each question. The skills for all the questions should be unique.
        The Question, Custom Prompt, KLP, KLS should be numbered.

        Here the format looks like :

        "Title",

        "Description",

        "Question 1",

        "Prompt 1",

        "Takeaway 1" ,

        "Skills 1" repeated for {3} question(s). Do not include any {{responder}} response.

        'The Question, Prompt, Takeaway, Skills should be numbered.'

        NOTE : Based on this information {{information}} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - "Rating : 6". Do not include any other explanation.
        
        NOTE : Make sure the simulation is very advanced and tough.
        \n\nAssistant:
    """%(priorities)

    dynamic_prompt = """
        \n\nHuman:
        {{Information}} - %s

        Read this {{information}} thoroughly. Now based on this information and your understanding create an advanced and detailed situation based on the priorities presented in the {{information}}. After creating the situation provide these:

        Description - Define the situation, and the problem. The problem should be a normal corporate problem. The description should always be about a conversation between the manager and a team member. Make the description specific based on data, industry, events, etc. Give the name of the manager. Never give the name of the team member. The description should just describe the problem and what was the specific situation that led to this problem. Keep the context Indian. No dialogues should be included. The description should ALWAYS be from the third person point of view. Provide the description in 100 to 200 words. Do not add any conclusion.  It should not be about writing an email.
        Title - Give a specific and relevant title for this description in less than 10 words.
        Questions - Give me the first question the manager will ask the team member based on the situation. The question should be deep, thoughtful and realistic. Give the name of person asking the question. Keep it less than 35 words. NEVER provide a response to the question. Never start with any introduction sentences. Start with the question directly. 
        Output format - Manager name: Question
        Prompts - As given in the output format. 

        Here the format looks like :
        Scenario 1:,

        "Title:",

        "Description:",

        "Question:",

        "Prompts:" - ["Please respond in order to continue." 
        "Respond as {{Manager name}}", 
        "Please respond in order to continue." 
        "Respond as {{Manager name}}", 
        "Please respond in order to continue." 
        "Respond as {{Manager name}}", 
        "Please respond in order to continue." 
        "Respond as {{Manager name}}", 
        "Please respond in order to continue." 
        "Respond as {{Manager name}}"
        "Conclude the discussion as a participant."]

        Write the manager's name in place of {{Manager name}}. The Manager name should always be same. Do not make any changes in the given format.  

        Do not include any response.
        Always provide the output in the given format. 

        NOTE : Based on this information {{information}} please evaluate this scenario provides a good practice to improve the skills that are given in the scenario. Evaluate whether the scenario is relevant and understandable. Give the scenario an overall rating out of 10. Just give the rating in the output in this format - "Rating : 6". Do not include any other explanation.
        
        NOTE : Make sure the situation is very advanced and tough.
        \n\nAssistant:
    """%(priorities)

    if type == "dynamic":
        return dynamic_prompt
    return simulation_prompt
