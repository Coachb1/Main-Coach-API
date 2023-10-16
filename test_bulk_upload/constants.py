

def get_skills(candidate_type):
    MANAGER = [
        "Communication",
        "Objection handling",
        "Problem solving",
        "Social skills",
        "Collaboration",
        "Accountable",
        "Improve lives around you",
        "Negotiation",
        "Get the best from others",
        "Flexible",
        "Coaching",
        "Methodical approach",
        "Empathy",
        "Decisiveness",
        "Self assurance",
        "Clarity and concision"
    ]

    SALES_MANAGER = [
        "Communication",
        "Presence",
        "Ability to inspire",
        "Persuasion",
        "Strategic thinking",
        "Negotiation",
        "Presentation skills",
        "Problem solving",
        "Methodical approach",
        "Time management",
        "Storytelling",
        "Standards",
        "Tenacity",
        "Patience",
        "Curiosity",
        "Passion"
    ]

    CUSTOMER_SERVICES = [
        "Communication",
        "Presence",
        "Social skills",
        "Coaching",
        "Flexible",
        "Ability to confront others",
        "Collaboration",
        "Ability to pivot",
        "Problem solving",
        "Accountable",
        "Clarity and concision",
        "Focused",
        "Empathy",
        "Proactive",
        "Willingness to learn",
        "Decisiveness"
    ]

    EMPLOYEE = [
        "Communication",
        "Objection handling",
        "Problem solving",
        "Social skills",
        "Collaboration",
        "Accountable",
        "Improve lives around you",
        "Negotiation",
        "Get the best from others",
        "Flexible",
        "Coaching",
        "Methodical approach",
        "Empathy",
        "Decisiveness",
        "Self assurance",
        "Clarity and concision"
    ]

    if candidate_type == 'Manager':
        return MANAGER
    elif candidate_type == 'Sales manager':
        return SALES_MANAGER
    elif candidate_type == 'Customer service':
        return CUSTOMER_SERVICES
    elif candidate_type == 'Employee':
        return EMPLOYEE
    else:
        return []


class ManagerSkills:
    PEOPLE = {
        "Communication": "Communication skills are the ability to express oneself clearly and effectively. It is the skill of conveying information clearly and efficiently to ensure effective understanding and collaboration.",
        "Objection handling": "Objection handling is the ability to successfully navigate and respond to concerns or pushback raised by employees over new initiatives, proposals, or directives from management.",
        "Problem solving": "Problem solving is the ability to identify and solve problems. It is the aptitude to analyze challenges, devise innovative solutions, and make sound decisions to achieve desired outcomes.",
        "Social skills": "Build rapport and relate well to people from diverse backgrounds; emotionally intelligent.",
    }

    PARTNERSHIP = {
        "Collaboration": "Collaboration is the ability to work together with others to achieve a common goal. It includes working harmoniously with others, leveraging diverse perspectives, and combining efforts effectively.",
        "Accountable": "Being accountable involves taking ownership, responsibly addressing challenges, and transparently delivering on commitments, fostering trust and results.",
        "Improve lives around you": "Proactively seek out opportunities to have a positive impact on others through acts of service, mentorship, or community leadership.",
        "Negotiation": "Negotiation skills are the ability to reach an agreement that is mutually beneficial.",
    }

    PROCESS = {
        "Get the best from others": "Motivate and empower people around you to achieve their full potential through encouragement, effective delegation, and providing support.",
        "Flexible": "Adapt readily to changing priorities, environments, or requirements; willing and able to modify approaches to achieve goals.",
        "Coaching": "Coaching is the ability to help others develop their skills and abilities.It includes the practice of guiding and developing individuals, unlocking their potential and fostering continuous growth.",
        "Methodical approach": "Adopt a systematic, step-by-step approach to ensure tasks are completed thoroughly, accurately, and efficiently.",
    }

    PERSONALITY = {
        "Empathy": "Empathy is the ability to understand and share the feelings of others. It is the capacity to understand perspectives of others, promoting compassion and strong interpersonal connections.",
        "Decisiveness": "Decisiveness is the ability to make decisions quickly and effectively. It is the skill of making well-considered and timely choices, crucial for effective leadership and problem-solving.",
        "Self assurance": "Project confidence in your abilities and decisions; willing to take calculated risks and responsibility for outcomes.",
        "Clarity and concision": "Clarity and concision is the ability to communicate information clearly and precisely, focusing on essential points while avoiding unnecessary complexity or ambiguity.",
    }


class SalesManagerSkills:
    PEOPLE = {
        "Communication": "Communication skills are the ability to express oneself clearly and effectively. It is the skill of conveying information clearly and efficiently to ensure effective understanding and collaboration.",
        "Presence": "Presence as it relates to a new manager's training needs can be defined as the ability to command attention and generate confidence through one's actions, words, and overall personality. Having presence means that when a new manager walks into a room, meets with direct reports, or facilitates a meeting, a calm authority and self-assurance automatically emanates from them. Strong presence comes from understanding one's own strengths, weaknesses, and emotions so that communication with team members feels natural and authentic rather than forced or contrived. New managers can develop presence through practicing active listening to gain insights without judgment, speaking concisely yet genuinely from the heart to build resonance with others, and staying grounded in core values while responding flexibly to situations with adaptability and humor. These skills allow a new manager's innate personality and competencies to shine through and truly lead their team through the force of their authentic presence.",
        "Ability to inspire": "Energize and motivate others through passion, vision, and leading by example.",
        "Persuasion": "Persuasion is the ability to influence others to see things your way. It is the art of convincing others through compelling arguments and empathy, influencing their decisions positively.",
    }

    PARTNERSHIP = {
        "Strategic thinking ": "Strategic Thinking  is the ability to see the big picture and develop long-term plans. It requires the ability to see the big picture, identify opportunities, and develop creative solutions to problems.",
        "Negotiation skills": "Negotiation skills are the ability to reach mutually beneficial agreements with others. It involves reaching agreements where all parties feel satisfied, finding common ground through compromise and empathy.",
        "Presentation skills": "Presentation skills  are the ability to communicate effectively in front of an audience. They require the ability to organize and deliver information in a clear and engaging way.",
        "Problem solving": "Problem-solving is  the ability to identify and solve problems effectively.",
    }

    PROCESS = {
        "Methodical approach": "A Methodical Approach refers to bringing organization, structure, and discipline to work. A new manager requires a methodical approach to prioritize tasks, develop routines, and implement systems. An example would be creating a structured weekly schedule that includes time for administrative duties, employee meetings, and strategic planning. The manager develops routines such as having one-on-ones with team members at the same time each week. Systems are implemented to track projects, assignments, and key metrics. Checklists are created for recurring tasks like onboarding new hires or conducting performance evaluations. Having a methodical approach helps reduce stress and promote efficiency by establishing good habits and organized processes from the start of supervision. It gives clarity and transparency to employees so they understand expectations and what is required to accomplish goals.",
        "Time management": "Time management skills are the ability to use time effectively to achieve goals. It requires the ability to prioritize tasks, set deadlines, and manage distractions.",
        "Storytelling": "Storytelling is the ability to communicate a message or idea through a story. It requires the ability to create engaging stories that capture the attention of the audience.",
        "Standards": "As a new manager, understanding and adhering to organizational standards will be critical to your success. Standards set consistent expectations for performance and allow work processes to operate efficiently and effectively across teams. You'll need to familiarize yourself with all pertinent policies and procedures regarding issues like employee conduct, work scheduling, customer service, data security and privacy, quality control standards in your department's products or services, health and safety protocols, and financial controls. Ensuring your team complies with and follows these standards will help create accountability, reduce errors and rework, improve customer satisfaction, lower costs, cultivate a culture of best practices, and boost morale. Leading by example and providing clear guidance on standards will also demonstrate your commitment to meeting the organization's objectives.",
    }
    PERSONALITY = {
        "Tenacity": "Persist in the face of obstacles and setbacks until the desired outcome is achieved; unwavering resolve and determination. ",
        "Patience": "Patience is the ability to wait for something without getting upset or frustrated. It requires the ability to control emotions, stay focused, and avoid making impulsive decisions.",
        "Curiosity": "Curiosity is the desire to learn new things. It requires the ability to ask questions, seek out new information, and be open to new experiences.",
        "Passion": "Passion is the enthusiasm and excitement you have for something. It requires the ability to be motivated, focused, and driven to succeed.",
    }


class CustomerServiceSkills:
    PEOPLE = {
        "Communication": "Communication skills are the ability to express oneself clearly and effectively. It is the skill of conveying information clearly and efficiently to ensure effective understanding and collaboration.",
        "Presence": "Presence as it relates to a new manager's training needs can be defined as the ability to command attention and generate confidence through one's actions, words, and overall personality. Having presence means that when a new manager walks into a room, meets with direct reports, or facilitates a meeting, a calm authority and self-assurance automatically emanates from them. Strong presence comes from understanding one's own strengths, weaknesses, and emotions so that communication with team members feels natural and authentic rather than forced or contrived. New managers can develop presence through practicing active listening to gain insights without judgment, speaking concisely yet genuinely from the heart to build resonance with others, and staying grounded in core values while responding flexibly to situations with adaptability and humor. These skills allow a new manager's innate personality and competencies to shine through and truly lead their team through the force of their authentic presence.",
        "Social skills": "Build rapport and relate well to people from diverse backgrounds; emotionally intelligent.",
        "Coaching": "Coaching is the ability to help others develop their skills and abilities.It includes the practice of guiding and developing individuals, unlocking their potential and fostering continuous growth.",
    }
    PARTNERSHIP = {
        "Flexible": "Adapt readily to changing priorities, environments, or requirements; willing and able to modify approaches to achieve goals.",
        "Ability to confront others": "As a new manager, the ability to confront others in a constructive manner is a crucial skill to develop. This involves bringing up difficult issues or performance problems with employees in a direct but sensitive way. Starting the conversation by making it clear you want to have an open discussion to resolve any obstacles can help set the right tone. Be specific about the concerns while focusing on behaviors that can be improved. Offer recommendations and solutions to address the issues. Request the employee's input and ideas to engage them in finding effective solutions together. Following up with clarity around expectations and next steps helps solidify the discussion and make sure everyone is on the same page moving forward. This kind of confrontation, when done respectfully and transparently, can improve communication and ultimately strengthen employee relationships and performance.",
        "Collaboration": "Collaboration is the ability to work together with others to achieve a common goal. It includes working harmoniously with others, leveraging diverse perspectives, and combining efforts effectively.",
        "Ability to pivot": "Adjust plans and priorities nimbly when circumstances change to achieve intended outcomes.",
    }
    PROCESS = {
        "Problem solving": "Problem-solving is the ability to identify and solve problems effectively. It is essential for making decisions, resolving conflicts, and improving processes.",
        "Accountable": "Being accountable as a new manager means taking responsibility for your actions and those of your team. You must create an environment where your direct reports understand that taking ownership of tasks and follow through is expected and rewarded. When problems or errors do arise within the team, demonstrate accountability by owning the issue, communicating it with transparency to stakeholders, and working to resolve it in a timely manner. An accountable manager inspires responsibility in others through both words and actions. Make it normal practice to never assign blame but rather view challenges as opportunities for the whole team to improve their systems and processes going forward. Accountability will build trust with your team and those you report to, showing that as a new manager you can be relied upon to achieve goals and deliver results.",
        "Clarity and concision": "Ability to articulate information succinctly and comprehensibly. By communicating clearly and avoiding jargon, agents can resolve customer queries effectively, ensuring a positive and efficient support experience.",
        "Focused": "Give full attention and effort to the task at hand; minimize distractions.",
    }
    PERSONALITY = {
        "Empathy": "Empathy is the ability to understand and share the feelings of others. It is the capacity to understand perspectives of others, promoting compassion and strong interpersonal connections.",
        "Proactive": "Anticipate challenges and opportunities and take initiative to address them.",
        "Willingness to learn": "Eagerly absorb new information and skills through proactive self-education.",
        "Decisiveness": "Decisiveness is the ability to make decisions quickly and effectively. It is the skill of making well-considered and timely choices, crucial for effective leadership and problem-solving.",
    }


class EmployeeSkills:
    PEOPLE = {
        "Communication": "Communication skills are the ability to express oneself clearly and effectively. It is the skill of conveying information clearly and efficiently to ensure effective understanding and collaboration.",
        "Objection handling": "Objection handling is the ability to successfully navigate and respond to concerns or pushback raised by employees over new initiatives, proposals, or directives from management.",
        "Problem solving": "Problem solving is the ability to identify and solve problems. It is the aptitude to analyze challenges, devise innovative solutions, and make sound decisions to achieve desired outcomes.",
        "Social skills": "Build rapport and relate well to people from diverse backgrounds; emotionally intelligent.",
    }

    PARTNERSHIP = {
        "Collaboration": "Collaboration is the ability to work together with others to achieve a common goal. It includes working harmoniously with others, leveraging diverse perspectives, and combining efforts effectively.",
        "Accountable": "Being accountable involves taking ownership, responsibly addressing challenges, and transparently delivering on commitments, fostering trust and results.",
        "Improve lives around you": "Proactively seek out opportunities to have a positive impact on others through acts of service, mentorship, or community leadership.",
        "Negotiation": "Negotiation skills are the ability to reach an agreement that is mutually beneficial.",
    }

    PROCESS = {
        "Get the best from others": "Motivate and empower people around you to achieve their full potential through encouragement, effective delegation, and providing support.",
        "Flexible": "Adapt readily to changing priorities, environments, or requirements; willing and able to modify approaches to achieve goals.",
        "Coaching": "Coaching is the ability to help others develop their skills and abilities.It includes the practice of guiding and developing individuals, unlocking their potential and fostering continuous growth.",
        "Methodical approach": "Adopt a systematic, step-by-step approach to ensure tasks are completed thoroughly, accurately, and efficiently.",
    }

    PERSONALITY = {
        "Empathy": "Empathy is the ability to understand and share the feelings of others. It is the capacity to understand perspectives of others, promoting compassion and strong interpersonal connections.",
        "Decisiveness": "Decisiveness is the ability to make decisions quickly and effectively. It is the skill of making well-considered and timely choices, crucial for effective leadership and problem-solving.",
        "Self assurance": "Project confidence in your abilities and decisions; willing to take calculated risks and responsibility for outcomes.",
        "Clarity and concision": "Clarity and concision is the ability to communicate information clearly and precisely, focusing on essential points while avoiding unnecessary complexity or ambiguity.",
    }




def get_skills_by_candidate_type(candidate_type):
    if candidate_type.capitalize() == 'Manager':
        return ManagerSkills
    elif candidate_type.capitalize() == 'Sales manager':
        return SalesManagerSkills
    elif candidate_type.capitalize() == 'Customer services':
        return CustomerServiceSkills
    elif candidate_type.capitalize() == 'Employee':
        return EmployeeSkills


updated_skills = {
                "Teamwork": "Teamwork",
                "Unflappability": "Calmness",
                "Goal-oriented focus": "Driven",
                "Ability to handle surprises": "Resilient",
                "Tenacity": "Tenacity",
                "Empathy": "Empathy",
                "Methodical approach": "Organize",
                "Willingness to learn": "Curious",
                "Communication": "Interact",
                "Business Acumen": "Savvy",
                "Social Selling": "Social",
                "Storytelling": "Narrative",
                "Active Listening": "Focus",
                "Objection Handling": "Persuade",
                "Presentation Skills": "Present",
                "Presentation": "Present",
                "Judgment": "Judgment",
                "Collaboration": "Collab",
                "Clarity and Concision": "Clarity",
                "Friendliness": "Friendly",
                "Confidence": "Confident",
                "Open-Mindedness": "Receptive",
                "Respect": "Respect",
                "Feedback": "Feedback",
                "Picking the Right Medium": "Relevant",
                "Being Assertive": "Assertive",
                "Asking Questions": "Question",
                "Use Humor appropriately and effectively": "Witty",
                "Inclusive Language": "Inclusion",
                "Tone and Volume": "Pitch",
                "Self-motivated": "Motivate",
                "Standards": "Standard",
                "Accountable": "Reliable",
                "Courage": "Courage",
                "Engaged": "Engaged",
                "Character": "Morality",
                "Humor": "Humor",
                "Passion": "Passion",
                "Integrity": "Honesty",
                "Likable": "Likable",
                "Ethical": "Ethical",
                "Loyal": "Loyal",
                "Emotional intelligence": "Emotional",
                "Understanding of opportunity cost": "Wisdom",
                "Humility": "Humility",
                "Discipline": "Control",
                "Perspective": "Objective",
                "Risk management": "Caution",
                "Self-assurance": "Confident",
                "Self-Assurance": "Confident",
                "Maturity": "Maturity",
                "Relationship building": "Network",
                "Social skills": "Social",
                "Speaking skills": "Speaking",
                "Honesty & Transparency": "Sincere",
                "Reasonable": "Reason",
                "Boldness": "Boldness",
                "Presence": "Presence",
                "Authenticity": "Authentic",
                "Ability to confront others": "Direct",
                "Negotiation skills": "Negotiate",
                "Negotiation": "Negotiate",
                "Ability to teach": "Instruct",
                "Interested in feedback": "Feedback",
                "Trust in your team": "Belief",
                "Ability to inspire": "Inspire",
                "ID team strengths": "Valuing",
                "Sharing your vision": "Vision",
                "Turning vision into reality": "Execute",
                "Get the best from others": "Motivate",
                "Understand what motivates others": "Insight",
                "Takes responsibility": "Responsible",
                "Rewarding": "Honoring",
                "Evaluative": "Evaluate",
                "Coaching": "Coach",
                "Enable others to act": "Empower",
                "Set Expectations": "Set goal",
                "Fair": "Fair",
                "Urgency": "Urgency",
                "Decisiveness": "Decide",
                "Commitment to vision": "Dedicate",
                "Consistency": "Constant",
                "Does not fear mistakes/risk": "Take risk",
                "Ability to pivot": "Pivot",
                "Open minded": "Receptive",
                "Tough-minded": "Stubborn",
                "Resourceful": "Innovate",
                "Faces obstacles with grace": "Grace",
                "Street smart": "Smart",
                "Make good decisions": "Wisdom",
                "Strategic thinking": "Strategic",
                "Proactive": "Proactive",
                "Flexible": "Flexible",
                "Manage setbacks": "Persevere",
                "Organized": "Organize",
                "Creative": "Creative",
                "Intuition": "Intuition",
                "Seeks out advice": "Teachable",
                "Pursue new experiences": "Explorer",
                "Reading": "Reading",
                "Competence": "Competent",
                "Focused": "Focused",
                "Intentional Learner": "Learner",
                "Enjoys The Ride": "Positive",
                "Improve lives around you": "Helpful",
                "Foster potential": "Guide",
                "Belief that success if shared": "Selfless",
                "Help others succeed": "Support",
                "Performance driven": "Ambition",
                "Servant/Service": "Serving",
                "Assertive": "Assertive",
                "Conviction": "Convince",
                "Patience": "Patience",
                "High-energy": "Dynamic",
                "Problem solving skills": "Solver",
                "Problem solving": "Solver",
                "Attentiveness": "Attentive",
                "Creativity and resourcefulness": "Inventive",
                "Persuasion skills": "Persuade",
                "Persuasion": "Persuade",
                "Time management skills": "Efficient",
                "Time management": "Efficient",
                "Knowledge of Pay Equity Laws": "Equity",
                "DEI Strategy Development": "DEI plan",
                "Inclusive Interviewing": "Inclusive",
                "Mentorship": "Mentoring",
                "Feedback Mechanism Implementation": "Implement",
                "Leadership Commitment": "Commit"
            }