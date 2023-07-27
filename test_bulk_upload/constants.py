   

    
def get_skills(candidate_type):
    MANAGER = [
    "Communication",
    "Unflappability",
    "Problem solving",
    "Social skills",
    "Collaboration",
    "Accountable",
    "Improve lives around you",
    "Negotiation",
    "Get the best from others",
    "Flexible",
    "Coaching",
    "Methodical Approach",
    "Empathy",
    "Decisiveness",
    "Self Assurance",
    "Clarity and Concision"
]

    SALES_MANAGER = [
            "Communication",
            "Presence",
            "Ability to inspire",
            "Persuasion",
            "Strategic Thinking",
            "Negotiation",
            "Presentation skills",
            "Problem solving",
            "Methodical Approach",
            "Time management",
            "Storytelling",
            "Standards",
            "Tenacity",
            "Patience",
            "Curiosity",
            "Passion"
]

    CUSTOMER_SERVICES =  [
    "Communication",
    "Presence",
    "Social Skills",
    "Coaching",
    "Flexible",
    "Ability to Confront others",
    "Collaboration",
    "Ability to pivot",
    "Problem solving",
    "Accountable",
    "Clarity and Concision",
    "Focused",
    "Empathy",
    "Proactive",
    "Willingness to Learn",
    "Decisiveness"
]


    if candidate_type == 'Manager':
        return MANAGER
    elif candidate_type == 'Sales manager':
        return SALES_MANAGER
    elif candidate_type == 'Customer service':
        return CUSTOMER_SERVICES
    else:
        return []


class ManagerSkills:
    PEOPLE = {
        "Communication": "Communication skills are the ability to express oneself clearly and effectively. It is the skill of conveying information clearly and efficiently to ensure effective understanding and collaboration.",
        "Unflappability": "Unflappability is the ability to remain calm, collected and decisive in stressful or difficult situations. A new manager especially needs to cultivate unflappability to effectively lead their team through challenges. When faced with an angry customer, unflappable managers listen carefully without becoming defensive and take logical next steps to resolve the issue. In meetings with upper management to discuss problems cropping up in the team or missing deadlines, unflappable managers clearly and concisely lay out the circumstances while offering potential solutions instead of making excuses. Unflappable managers inspire confidence in their team members during chaotic times. They provide reassurance and direction while modeling a problem-solving mindset that helps the team remain productive under pressure. By practicing presence of mind and emotional control in even minor management situations, new leaders can strengthen their ability to remain focused and effective when challenges inevitably arise.",
        "Problem solving": "Problem solving is the ability to identify and solve problems. It is the aptitude to analyze challenges, devise innovative solutions, and make sound decisions to achieve desired outcomes.",
        "Social skills": "Social skills are the ability to interact and communicate effectively with others. These measure the proficiency in understanding social cues and navigating various social situations with ease.",
    }

    PARTNERSHIP = {
        "Collaboration": "Collaboration is the ability to work together with others to achieve a common goal. It includes working harmoniously with others, leveraging diverse perspectives, and combining efforts effectively.",
        "Accountable": "Being accountable as a new manager means taking responsibility for your actions and those of your team. You must create an environment where your direct reports understand that taking ownership of tasks and follow through is expected and rewarded. When problems or errors do arise within the team, demonstrate accountability by owning the issue, communicating it with transparency to stakeholders, and working to resolve it in a timely manner. An accountable manager inspires responsibility in others through both words and actions. Make it normal practice to never assign blame but rather view challenges as opportunities for the whole team to improve their systems and processes going forward. Accountability will build trust with your team and those you report to, showing that as a new manager you can be relied upon to achieve goals and deliver results.",
        "Improve lives around you": "As a new manager, one of the most important skills you must cultivate is the ability to improve the lives of those around you. This involves developing people by providing clear direction, regular feedback, and opportunities for growth. It means fostering a positive work environment where team members feel respected, valued, and included. It could involve championing work-life balance initiatives and flexible work arrangements where reasonable. It may mean helping individuals solve problems at work that are spilling into their personal lives. At the core, improving lives means being sensitive to the challenges and needs of your team members, and using your position and influence to make positive changes both big and small that make their work experience more fulfilling and enjoyable. Developing this people-centric, humanistic approach will serve you well as a leader and help take your team's performance to the next level.",
        "Negotiation": "Negotiation skills are the ability to reach an agreement that is mutually beneficial.",
    }

    PROCESS = {
        "Get the best from others": "Getting the best from others involves recognizing each person's unique strengths and motivations, then creating an environment where they can achieve their best work. This may mean giving autonomy to self-directed workers while providing structure and mentoring for those who need more guidance. It involves listening closely to team members' ideas, giving meaningful feedback and praise to build confidence, and showing flexibility to allow people's best thinking to emerge. Aligning each individual's work to the larger goals fosters motivation. Small gestures, like remembering birthdays or personal accomplishments, signal care for the whole person and inspire loyalty and discretionary effort. Together these actions get the very best thinking and performance from each team member.",
        "Flexible": "A new manager needs to learn to be flexible. This skill involves being adaptable to changes and able to perform various duties as needed. The team and projects under a manager continue to evolve quickly requiring the manager to adjust accordingly. Examples of flexibility include supporting team members who face difficult tasks by jumping in when needed, being open to new tactics and methods suggested by the team, and not becoming stuck in one preferred way of doing things. During inevitable roadblocks, a flexible manager explores various solutions instead of insisting on only one approach. Flexible managers recognize different team members have unique strengths, allowing staff to contribute in ways that play to those strengths. In all situations, a flexible manager learns to go with the flow, adjust on the fly, and roll with the inevitable punches that come with a dynamic work environment.",
        "Coaching": "Coaching is the ability to help others develop their skills and abilities.It includes the practice of guiding and developing individuals, unlocking their potential and fostering continuous growth.",
        "Methodical Approach": "A methodical approach refers to bringing organization, structure, and discipline to work. A new manager requires a methodical approach to prioritize tasks, develop routines, and implement systems. An example would be creating a structured weekly schedule that includes time for administrative duties, employee meetings, and strategic planning. The manager develops routines such as having one-on-ones with team members at the same time each week. Systems are implemented to track projects, assignments, and key metrics. Checklists are created for recurring tasks like onboarding new hires or conducting performance evaluations. Having a methodical approach helps reduce stress and promote efficiency by establishing good habits and organized processes from the start of supervision. It gives clarity and transparency to employees so they understand expectations and what is required to accomplish goals.",
    }

    PERSONALITY = {
        "Empathy": "Empathy is the ability to understand and share the feelings of others. It is the capacity to understand perspectives of others, promoting compassion and strong interpersonal connections.",
        "Decisiveness": "Decisiveness is the ability to make decisions quickly and effectively. It is the skill of making well-considered and timely choices, crucial for effective leadership and problem-solving.",
        "Self assurance": "Self assurance as a skill is vital for a new manager to develop. Self-assured managers trust in their own capabilities and expertise, allowing them to navigate difficult situations and motivate their team with confidence. An otherwise talented manager who lacks self-assurance may be reluctant to make decisions, delegate work, or address performance issues for fear of being wrong or disliked. However, a self-assured new manager who believes in their own leadership abilities will confidently identify priorities, assign responsibilities, resolve conflicts, and provide guidance that breeds productivity and trust within their team. They own their mistakes and shortcomings without doubt, taking responsibility to correct course and learn from failures. Examples of self-assured behaviors include speaking firmly without hesitation, actively listening to opinions without defensiveness, giving clear directives decisively, and providing consistent positive reinforcement to build team morale.",
        "Clarity and Concision": "As a new manager, clarity and conciseness in your communication will be essential skills to develop. Your team will look to you for guidance and direction on priorities, responsibilities, and expectations. You must be able to clearly articulate goals, assign tasks, and provide feedback in a straightforward yet succinct manner. Avoid wordiness, vagueness, and ambiguous language. Edit your communications to be as brief as possible while still getting your entire intended message across. Identify the most important points and structure your discussions around those. Practice distilling complex ideas into their essential elements. Ask others to provide feedback on whether your instructions and explanations are easy to comprehend and follow. With clarity and conciseness in your role as a new manager, you will communicate most efficiently and effectively with your team, ensuring common understanding and proper execution of your directives.",
    }


class SalesManagerSkills:
    PEOPLE = {
        "Communication": "Communication skills are the ability to express oneself clearly and effectively. It is the skill of conveying information clearly and efficiently to ensure effective understanding and collaboration.",
        "Presence": "Presence as it relates to a new manager's training needs can be defined as the ability to command attention and generate confidence through one's actions, words, and overall personality. Having presence means that when a new manager walks into a room, meets with direct reports, or facilitates a meeting, a calm authority and self-assurance automatically emanates from them. Strong presence comes from understanding one's own strengths, weaknesses, and emotions so that communication with team members feels natural and authentic rather than forced or contrived. New managers can develop presence through practicing active listening to gain insights without judgment, speaking concisely yet genuinely from the heart to build resonance with others, and staying grounded in core values while responding flexibly to situations with adaptability and humor. These skills allow a new manager's innate personality and competencies to shine through and truly lead their team through the force of their authentic presence.",
        "Ability to inspire": "The ability to inspire one's team is an essential skill for a new manager. It involves motivating, encouraging, and energizing employees to achieve goals and unlock their potential. An inspiring manager listens deeply to team member concerns, acknowledges their efforts, and uses positive, forward-looking language that builds trust. They connect each employee's work to the larger goals of the team and organization to give broader purpose. An inspiring manager leads by example with proactive communication, a positive attitude, and a willingness to help others succeed. They create an encouraging, innovative environment where employees feel empowered, build confidence, and shape the overall company culture by passing on inspiration to their own colleagues. In this way, a manager with the ability to inspire has a multiplier effect, motivating entire teams and cascading inspiration throughout an organization.",
        "Persuasion": "Persuasion is the ability to influence others to see things your way. It is the art of convincing others through compelling arguments and empathy, influencing their decisions positively.",
    }

    PARTNERSHIP = {
        "Strategic thinking": "Strategic Thinking is the ability to see the big picture and develop long-term plans. It requires the ability to see the big picture, identify opportunities, and develop creative solutions to problems.",
        "Negotiation skills": "Negotiation skills are the ability to reach mutually beneficial agreements with others. It involves reaching agreements where all parties feel satisfied, finding common ground through compromise and empathy.",
        "Presentation skills": "Presentation skills  are the ability to communicate effectively in front of an audience. They require the ability to organize and deliver information in a clear and engaging way.",
        "Problem solving": "Problem-solving is  the ability to identify and solve problems effectively.",
    }

    PROCESS = {
        "Methodical Approach": "A methodical approach refers to bringing organization, structure, and discipline to work. A new manager requires a methodical approach to prioritize tasks, develop routines, and implement systems. An example would be creating a structured weekly schedule that includes time for administrative duties, employee meetings, and strategic planning. The manager develops routines such as having one-on-ones with team members at the same time each week. Systems are implemented to track projects, assignments, and key metrics. Checklists are created for recurring tasks like onboarding new hires or conducting performance evaluations. Having a methodical approach helps reduce stress and promote efficiency by establishing good habits and organized processes from the start of supervision. It gives clarity and transparency to employees so they understand expectations and what is required to accomplish goals.",
        "Time management": "Time management skills are the ability to use time effectively to achieve goals. It requires the ability to prioritize tasks, set deadlines, and manage distractions.",
        "Storytelling": "Storytelling is the ability to communicate a message or idea through a story. It requires the ability to create engaging stories that capture the attention of the audience.",
        "Standards": "As a new manager, understanding and adhering to organizational standards will be critical to your success. Standards set consistent expectations for performance and allow work processes to operate efficiently and effectively across teams. You'll need to familiarize yourself with all pertinent policies and procedures regarding issues like employee conduct, work scheduling, customer service, data security and privacy, quality control standards in your department's products or services, health and safety protocols, and financial controls. Ensuring your team complies with and follows these standards will help create accountability, reduce errors and rework, improve customer satisfaction, lower costs, cultivate a culture of best practices, and boost morale. Leading by example and providing clear guidance on standards will also demonstrate your commitment to meeting the organization's objectives.",
    }
    PERSONALITY = {
        "Tenacity": "Tenacity, defined as persistence in doing something despite difficulty or delay in achieving success, is an essential skill for any new manager. A manager faces challenges every day - from balancing workloads to developing team motivation- and tenacity will help them persevere through problems and obstacles. A new manager with tenacity continues forward progress even when initiatives fail or team members lack motivation. They adapt their approach and try again with renewed focus. An example of tenacity would be a manager whose team is unable to meet an important deadline. A manager high in tenacity would refuse to accept failure, motivate team members to work longer hours, adjust responsibilities to maximize strengths, and take any other steps needed to ensure the deadline is met. With time and experience, that same manager would learn from the situation to prevent future challenges, steadily improving the effectiveness and productivity of their team through tenacious problem solving and grit.",
        "Patience": "Patience is the ability to wait for something without getting upset or frustrated. It requires the ability to control emotions, stay focused, and avoid making impulsive decisions.",
        "Curiosity": "Curiosity is the desire to learn new things. It requires the ability to ask questions, seek out new information, and be open to new experiences.",
        "Passion": "Passion is the enthusiasm and excitement you have for something. It requires the ability to be motivated, focused, and driven to succeed.",
    }

class CustomerServiceSkills:
    PEOPLE = {
        "Communication": "Communication skills are the ability to express oneself clearly and effectively. It is the skill of conveying information clearly and efficiently to ensure effective understanding and collaboration.",
        "Presence": "Presence as it relates to a new manager's training needs can be defined as the ability to command attention and generate confidence through one's actions, words, and overall personality. Having presence means that when a new manager walks into a room, meets with direct reports, or facilitates a meeting, a calm authority and self-assurance automatically emanates from them. Strong presence comes from understanding one's own strengths, weaknesses, and emotions so that communication with team members feels natural and authentic rather than forced or contrived. New managers can develop presence through practicing active listening to gain insights without judgment, speaking concisely yet genuinely from the heart to build resonance with others, and staying grounded in core values while responding flexibly to situations with adaptability and humor. These skills allow a new manager's innate personality and competencies to shine through and truly lead their team through the force of their authentic presence.",
        "Social skills": "Social skills are the ability to interact and communicate effectively with others. These measure the proficiency in understanding social cues and navigating various social situations with ease.",
        "Coaching": "Coaching is the ability to help others develop their skills and abilities.It includes the practice of guiding and developing individuals, unlocking their potential and fostering continuous growth.",
    }
    PARTNERSHIP = {
        "Flexible": "A new manager needs to learn to be flexible. This skill involves being adaptable to changes and able to perform various duties as needed. The team and projects under a manager continue to evolve quickly requiring the manager to adjust accordingly. Examples of flexibility include supporting team members who face difficult tasks by jumping in when needed, being open to new tactics and methods suggested by the team, and not becoming stuck in one preferred way of doing things. During inevitable roadblocks, a flexible manager explores various solutions instead of insisting on only one approach. Flexible managers recognize different team members have unique strengths, allowing staff to contribute in ways that play to those strengths. In all situations, a flexible manager learns to go with the flow, adjust on the fly, and roll with the inevitable punches that come with a dynamic work environment.",
        "Ability to Confront others": "As a new manager, the ability to confront others in a constructive manner is a crucial skill to develop. This involves bringing up difficult issues or performance problems with employees in a direct but sensitive way. Starting the conversation by making it clear you want to have an open discussion to resolve any obstacles can help set the right tone. Be specific about the concerns while focusing on behaviors that can be improved. Offer recommendations and solutions to address the issues. Request the employee's input and ideas to engage them in finding effective solutions together. Following up with clarity around expectations and next steps helps solidify the discussion and make sure everyone is on the same page moving forward. This kind of confrontation, when done respectfully and transparently, can improve communication and ultimately strengthen employee relationships and performance.",
        "Collaboration": "Collaboration is the ability to work together with others to achieve a common goal. It includes working harmoniously with others, leveraging diverse perspectives, and combining efforts effectively.",
        "Ability to pivot": "While managing teams, a new ability managers must develop is pivoting quickly to changing circumstances. Pivoting refers to a manager's flexibility and agility to adapt their team's goals, priorities, and strategies in response to internal changes within their organization or external changes in market conditions and the competitive landscape. Good examples of pivoting include: when a key project is delayed or cancelled, a manager needs to swiftly realign their team to their next highest priority initiative; if revenue goals are not being met, the manager must work with their team to identify a new sales approach or marketing campaign to stir demand; and when a crucial vendor relationship is disrupted, the manager and team must nimbly determine an alternative sourcing or supplier option to get the business back on track. The ability to assess situations accurately, decide on the needed adjustments rapidly, clearly communicate the new plans to the team, and motivate the team to implement the pivot successfully are hallmarks of an agile and adaptive modern manager.",
    }
    PROCESS = {
        "Problem Solving": "Problem-solving is the ability to identify and solve problems effectively. It is essential for making decisions, resolving conflicts, and improving processes.",
        "Accountable": "Being accountable as a new manager means taking responsibility for your actions and those of your team. You must create an environment where your direct reports understand that taking ownership of tasks and follow through is expected and rewarded. When problems or errors do arise within the team, demonstrate accountability by owning the issue, communicating it with transparency to stakeholders, and working to resolve it in a timely manner. An accountable manager inspires responsibility in others through both words and actions. Make it normal practice to never assign blame but rather view challenges as opportunities for the whole team to improve their systems and processes going forward. Accountability will build trust with your team and those you report to, showing that as a new manager you can be relied upon to achieve goals and deliver results.",
        "Clarity and Concision": "As a new manager, clarity and conciseness in your communication will be essential skills to develop. Your team will look to you for guidance and direction on priorities, responsibilities, and expectations. You must be able to clearly articulate goals, assign tasks, and provide feedback in a straightforward yet succinct manner. Avoid wordiness, vagueness, and ambiguous language. Edit your communications to be as brief as possible while still getting your entire intended message across. Identify the most important points and structure your discussions around those. Practice distilling complex ideas into their essential elements. Ask others to provide feedback on whether your instructions and explanations are easy to comprehend and follow. With clarity and conciseness in your role as a new manager, you will communicate most efficiently and effectively with your team, ensuring common understanding and proper execution of your directives.",
        "Focused": "As a new manager, being focused is essential for success. A focused manager prioritizes key goals and objectives and limits distractions that hinder progress. They concentrate efforts and resources on the tasks and teams that will make the biggest impact. A focused manager decides what needs their most deliberate and undivided attention, whether it be implementing a new strategy, improving a critical process, or mentoring a high-potential employee. They then resolutely avoid spreading themselves too thin by saying 'no' to peripheral requests that take them away from their top priorities. Having laser focus allows a new manager to make faster progress, see better results, and develop momentum that fuels success and higher performance for both themselves and their team. Staying focused as a manager takes discipline, practice and a willingness to sometimes frustrate others by concentrating on what truly matters most.",
    }
    PERSONALITY = {
        "Empathy": "Empathy is the ability to understand and share the feelings of others. It is the capacity to understand perspectives of others, promoting compassion and strong interpersonal connections.",
        "Proactive": "A proactive new manager exhibits the ability to anticipate issues and opportunities, and take initiative to address them before problems arise. This involves thinking ahead to identify potential obstacles and find solutions in advance. The manager does not wait passively for problems to appear and then simply react to them. Instead, the manager scans the environment for warning signs, thinks creatively about possible risks or challenges that lie ahead, and develops contingency plans proactively. The manager understands that taking the initiative to reduce uncertainties and eliminate potential barriers early on helps the team and project run more smoothly with fewer setbacks. By thinking and acting proactively, the new manager can minimize crisis management and firefighting, better utilizing the time and resources of the team.",
        "Willingness to Learn": "Willingness to learn relates to the openness and enthusiasm that a new manager brings to the task of developing new insights, skills, and perspectives needed to succeed in their managerial role. They understand that there will be many areas where they need to grow and improve, as management presents new challenges different from individual contributor roles. A willingess to learn means humbly seeking feedback from team members, bosses, mentors, and peers in order identify areas for improvement. It requires maintaining a growth mindset that skills can be developed through effort and practice. An eager attitude toward training programs, reading relevant books, and exposure to new ideas signals to the team that the manager values stepping outside of their comfort zone to become the leader the team needs. A new manager's willingness to learn and adapt quickly becomes an inspiration for their team members to do the likewise.",
        "Decisiveness": "Decisiveness is the ability to make decisions quickly and effectively. It is the skill of making well-considered and timely choices, crucial for effective leadership and problem-solving.",
    }


def get_skills_by_candidate_type(candidate_type):
    if candidate_type.capitalize() == 'Manager':
        return ManagerSkills
    elif candidate_type.capitalize() == 'Sales manager':
        return SalesManagerSkills
    elif candidate_type.capitalize() == 'Customer services':
        return CustomerServiceSkills