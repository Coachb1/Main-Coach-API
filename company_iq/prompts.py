import company_iq


class CompanyIQPrompts:
    OUTLOOKPROMPT = '''
        Role & Stance
        You are acting as an Enterprise AI Adoption Analyst advising C-suite leaders and cloud GTM teams.
        Your task is not to summarize the past.
        Your task is to predict the next 12 months of AI direction for a specific company, grounded in public signals, industry patterns, and adoption constraints.

        You must be opinionated, selective, and falsifiable.


        ---

        Inputs : ${input_data}




        ---

        Output Requirements

        Produce a 12-Month AI Outlook with the following structure.
        Do not exceed 400–500 words.


        ---

        1. Executive Prediction (Non-Obvious)

        State one clear prediction about how this organization’s AI journey will evolve in the next 12 months.

        This must be a directional bet, not a hedge

        Use phrases like:

        “The most likely outcome is…”

        “The critical inflection will occur when…”

        “The risk leadership is underestimating is…”



        Avoid generic optimism.


        ---

        2. What Will Move Forward (3 items max)

        Identify up to three AI initiatives or themes that are most likely to progress meaningfully.

        For each:

        Why this and not others

        What internal force supports it (regulatory, margin pressure, talent, customer behavior)



        ---

        3. What Will Stall or Be Abandoned

        Explicitly name:

        At least one AI initiative that is likely to stall, pause, or fail

        The real reason (political, operational, cultural — not “data quality”)


        This is where credibility is built.


        ---

        4. Cloud & Technology Implications

        Describe how this outlook translates into actual cloud behavior:

        Experimentation vs production

        Spend concentration vs fragmentation

        Central IT vs business-led motion


        No vendor hype. No product names unless justified.


        ---

        5. Executive Risk & Opportunity Window

        Close with:

        One risk leadership will face if they do nothing in the next 12 months

        One opportunity that compounds if acted on early


        This should read like advice someone would pay for.


        ---

        Style Constraints

        No marketing language

        No buzzword stacking

        No “AI will transform everything” statements

        Write like a trusted internal strategist, not a vendor

        '''
    METADATAPROMPT = '''
            For the company, "${company_name}", find the following metadata from publicly available resources and adhere strictly to the format and constraint guidelines below: 
            **Constraint Guidelines:** 
            * **Output Format:** 
            Provide a direct, unadorned bulleted list. NO introductory or concluding sentences, NO descriptions, and NO symbols (e.g., $, %, etc.) unless specified.
            * **Revenue Constraint:** 
            Must be the most recent *Annual* Revenue figure, expressed ONLY as an integer count in **US Millions**. If the figure is $5.2 Billion, render it as 5200. 
            * **Employees Constraint:** 
            Must be the *most recent full-time* employee count, expressed ONLY as a single integer count. Exclude seasonal or contract staff. 
            * **Industry Constraint:** 
            Select the single best fit from this standard, comprehensive list: **Technology, Finance, Healthcare, Manufacturing, Retail, Consumer Services, Energy, Transportation/Logistics, Telecommunications, Government/Defense.
            ** **Metadata Variables and Required Format must be in json:** 
            {
            "company": "[Company registered Name]",
            "industry": "[Standard Industry from list above]",
            "hq": "[Country]",
            "revenue_us_millions": [Integer Count],
            "employees_full_time": [Integer Count],
            "ai_cloud_leadership_roles": [List up to 5 key title/leader names with their focus (e.g., * CIO/Alan Lowden - Technology Strategy)],
            "ai_digital_initiatives": [List up to 5 major programs or strategies (e.g., * Block Next Strategy, AI Tax Assist)],
            "cloud_tech_stack_signals": [List up to 5 core technologies (e.g., * Primary Cloud/Azure, Data/Cosmos DB, Languages/.NET Core)],
            "ai_use_cases": [List up to 5 specific applications with their function (e.g., * Predictive Maintenance - Reduces unplanned downtime)]
            }
        '''
    SCOREGENERATIONPROMPT = '''
        The following information is about AI landscape in Company ${company_name}: 
        "${company_info}". 
        Compare it with the top McKinsey-level landscape info and assign it a rating between 1 to 100
        outPUt must be in json format with the following structure:
        {
            "company": "[Company Name]",
            "score": [Integer between 1 and 100],
            "justification": "[Short explanation of the score]"
        }
        '''
    
company_iq_prompts = CompanyIQPrompts()