from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import time

def recommend_coach_tfidf(coachee:dict, coaches:dict): 
    documents = [coachee['problem']] + list(coaches.values())
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(documents)
    
    coachee_vector = tfidf_matrix[0:1]
    coach_vectors = tfidf_matrix[1:]

    similarities = cosine_similarity(coachee_vector, coach_vectors).flatten()
    sorted_indices = np.argsort(similarities)[::-1]

    recommended_coaches = [(list(coaches.keys())[index], similarities[index]) for index in sorted_indices]
    recommended_coaches = [coach for coach in recommended_coaches if coach[1] > 0]

    print(recommended_coaches)
    return recommended_coaches[:10]