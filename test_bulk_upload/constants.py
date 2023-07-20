   

    
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
    elif candidate_type == 'Sales Manager':
        return SALES_MANAGER
    elif candidate_type == 'Customer Service':
        return CUSTOMER_SERVICES
