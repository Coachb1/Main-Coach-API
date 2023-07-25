   

    
def get_skills(candidate_type):
    MANAGER = ["Communication",
        "Empathy",
        "Delegation",
        "Collaboration",
        "Accountability",
        "Adaptability",
        "Influence",
        "Decisivenes",
        "Coaching",
        "Conflict resolution",
        "Problem solving",
        "Planning",
        "Self awareness",
        "Clarity",
        "Negotiation",
        "Social skills"
]

    SALES_MANAGER = ["Active listening",
                "Communication",
                "Planning",
                "Time management",
                "Resilience",
                "Strategic thinking",
                "Motivation",
                "Patience",
                "Persuasion",
                "Story telling",
                "Customer relationship management",
                "Presentation skills",
                "Passion",
                "Negotiation",
                "Problem solving",
                "Curiosity"
    ]

    CUSTOMER_SERVICES = [
            "Empathy",
            "Problem solving",
            "Communication",
            "Active listening",
            "Accuracy",
            "Initiative",
            "Flexibility",
            "Conflict resolution",
            "Clarity",
            "Critical thinking",
            "Social perceptiveness",
            "Coordination",
            "Active learning",
            "Instructing",
            "Adaptability",
            "Decision making"
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
        "Conflict resolution": "Conflict-resolution is the ability to manage and resolve disagreements between people. It is the capacity to address and resolve disputes constructively, promoting harmony and cooperation.",
        "Problem solving": "Problem solving is the ability to identify and solve problems. It is the aptitude to analyze challenges, devise innovative solutions, and make sound decisions to achieve desired outcomes.",
        "Social skills": "Social skills are the ability to interact and communicate effectively with others. These measure the proficiency in understanding social cues and navigating various social situations with ease.",
    }

    PARTNERSHIP = {
        "Collaboration": "Collaboration is the ability to work together with others to achieve a common goal. It includes working harmoniously with others, leveraging diverse perspectives, and combining efforts effectively.",
        "Accountability": "Accountability is the ability to take responsibility for one's actions and the consequences of those actions. It includes owning up to mistakes, following through on commitments, and being reliable.",
        "Influence": "Influence is the ability to persuade others to see things your way. It is the capability to inspire others to take specific actions or adopt viewpoints.",
        "Negotiation": "Negotiation skills are the ability to reach an agreement that is mutually beneficial.",
    }

    PROCESS = {
        "Delegation": "Delegation is the ability to assign tasks to others and hold them accountable. It is the skill of entrusting tasks and responsibilities to others based on their strengths, fostering productivity and teamwork.",
        "Adaptability": "Adaptability is the ability to adjust to change. It is the ability to adjust and thrive in dynamic environments, embracing change and learning from new situations.",
        "Coaching": "Coaching is the ability to help others develop their skills and abilities.It includes the practice of guiding and developing individuals, unlocking their potential and fostering continuous growth.",
        "Planning": "Planning is the ability to set goals and develop a plan to achieve them. It may include strategically mapping out objectives, tasks, and timelines to ensure well-organized and successful project execution.",
    }

    PERSONALITY = {
        "Empathy": "Empathy is the ability to understand and share the feelings of others. It is the capacity to understand perspectives of others, promoting compassion and strong interpersonal connections.",
        "Decisiveness": "Decisiveness is the ability to make decisions quickly and effectively. It is the skill of making well-considered and timely choices, crucial for effective leadership and problem-solving.",
        "Self awareness": "Self Awareness is the ability to understand your own strengths, weaknesses, and motivations. It is the conscious understanding of one's emotions, leading to personal growth and improved relationships.",
        "Clarity": "Clarity is the ability to communicate your thoughts and ideas in a clear and concise way. It is the quality of conveying ideas and information in a concise, precise, and understandable manner, avoiding ambiguity and misunderstanding.",
    }


class SalesManagerSkills:
    PEOPLE = {
        "Communication": "Communication skills are the ability to express oneself clearly and effectively. It is the skill of conveying information clearly and efficiently to ensure effective understanding and collaboration.",
        "Active listening": "Active listening is the ability to focus on what someone is saying, understand their point of view, and respond appropriately.",
        "Motivation": "Motivation is the ability to set goals and work towards them with determination and energy. It helps people overcome challenges, stay focused, and achieve their full potential.",
        "Persuasion": "Persuasion is the ability to influence others to see things your way. It is the art of convincing others through compelling arguments and empathy, influencing their decisions positively.",
    }

    PARTNERSHIP = {
        "Strategic thinking": "Strategic Thinking is the ability to see the big picture and develop long-term plans. It requires the ability to see the big picture, identify opportunities, and develop creative solutions to problems.",
        "Negotiation skills": "Negotiation skills are the ability to reach mutually beneficial agreements with others. It involves reaching agreements where all parties feel satisfied, finding common ground through compromise and empathy.",
        "Presentation skills": "Presentation skills  are the ability to communicate effectively in front of an audience. They require the ability to organize and deliver information in a clear and engaging way.",
        "Problem solving": "Problem-solving is  the ability to identify and solve problems effectively.",
    }

    PROCESS = {
        "Planning": "Planning skills are the ability to set goals and develop a plan to achieve them. It requires the ability to think ahead, set realistic goals, and develop a plan to achieve them.",
        "Time management": "Time management skills are the ability to use time effectively to achieve goals. It requires the ability to prioritize tasks, set deadlines, and manage distractions.",
        "Storytelling": "Storytelling is the ability to communicate a message or idea through a story. It requires the ability to create engaging stories that capture the attention of the audience.",
        "Customer Relationship Management": "Customer relationship management is the skill of managing customer interactions to build relationships and increase sales. It requires the ability to understand customer needs, provide excellent service, and build long-term relationships.",
    }
    PERSONALITY = {
        "Resilience": "Resilience is the ability to bounce back from setbacks and challenges. It requires the ability to stay positive, learn from mistakes, and adapt to change",
        "Patience": "Patience is the ability to wait for something without getting upset or frustrated. It requires the ability to control emotions, stay focused, and avoid making impulsive decisions.",
        "Curiosity": "Curiosity is the desire to learn new things. It requires the ability to ask questions, seek out new information, and be open to new experiences.",
        "Passion": "Passion is the enthusiasm and excitement you have for something. It requires the ability to be motivated, focused, and driven to succeed.",
    }

class CustomerServiceSkills:
    PEOPLE = {
        "Communication": "Communication skills are the ability to express oneself clearly and effectively. It is the skill of conveying information clearly and efficiently to ensure effective understanding and collaboration.",
        "Active Listening": "Active listening is the ability to focus on what someone is saying, understand their point of view, and respond appropriately.",
        "Social Perceptiveness": "Social Perceptiveness  is the ability to understand and respond to the emotions, motivations, and needs of others. This skill is important for building relationships, resolving conflicts, and providing effective customer service.",
        "Instructing": "Instructing is the ability to clearly and concisely explain concepts and procedures to others. It is the ability to teach and explain concepts clearly to others, making complex ideas easy to understand and follow.",
    }
    PARTNERSHIP = {
        "Flexibility": "Flexibility is the ability to adapt to change and new situations. It is essential for dealing with unexpected challenges, working in a fast-paced environment, and meeting changing customer needs.",
        "Conflict Resolution": "Conflict resolution is the ability to plan and organize activities effectively. It involves managing disagreements and finding solutions that satisfy all parties involved, fostering a harmonious environment.",
        "Coordination": "Coordination is the ability to plan and organize activities effectively. It involves organizing tasks and resources efficiently, ensuring all elements work together cohesively to achieve objectives.",
        "Adaptability": "Adaptability is the ability to adjust to change. It is the ability to adjust and thrive in dynamic environments, embracing change and learning from new situations.",
    }
    PROCESS = {
        "Problem Solving": "Problem-solving is the ability to identify and solve problems effectively. It is essential for making decisions, resolving conflicts, and improving processes.",
        "Accuracy": "Accuracy is the ability to produce work that is free of errors. It involves ensuring precision and correctness in tasks and information, minimizing errors and enhancing reliability.",
        "Clarity": "Clarity is the ability to communicate your thoughts and ideas in a clear and concise way. It is the quality of conveying ideas and information in a concise, precise, and understandable manner, avoiding ambiguity and misunderstanding.",
        "Critical Thinking": "Critical Thinking is the ability to think logically and rationally to solve problems. It involves evaluating information objectively, making well-informed decisions based on evidence and sound reasoning.",
    }
    PERSONALITY = {
        "Empathy": "Empathy is the ability to understand and share the feelings of others. It is the capacity to understand perspectives of others, promoting compassion and strong interpersonal connections.",
        "Initiative": "Initiative is the ability to take action without being asked. It includes taking proactive steps and showing willingness to start tasks independently, driving progress and innovation.",
        "Active Learning": "Active Learning is the ability to learn new things quickly and effectively. It includes continuously seeking knowledge and skills through engaging in new experiences and educational opportunities.",
        "Decision Making": "Decision-making is the ability to make sound decisions in a timely manner. This involves assessing options, weighing pros and cons, and choosing the best course of action based on judgment and analysis.",
    }


def get_skills_by_candidate_type(candidate_type):
    if candidate_type.capitalize() == 'Manager':
        return ManagerSkills
    elif candidate_type.capitalize() == 'Sales manager':
        return SalesManagerSkills
    elif candidate_type.capitalize() == 'Customer services':
        return CustomerServiceSkills