from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from commons.timeit import timeit
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.corpus import wordnet


# Ensure you have the required NLTK data files
import nltk
nltk.download('punkt')


@timeit
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

@timeit
def get_synonyms(words):
    # Ensure NLTK WordNet is downloaded once
    nltk.download('wordnet', quiet=True)
    
    synonyms = set()  # Use a set to store unique synonyms
    syn_words = {word: [] for word in words}
    for word in words:
        for synset in wordnet.synsets(word):
            for lemma in synset.lemmas():
                synonym = lemma.name().replace("_", " ")
                synonyms.add(synonym)
                syn_words[word].append(synonym)
    
    synonyms = list(synonyms)  # Convert set back to a list if needed
    print(f"get_synonyms: {syn_words}")
    return synonyms

@timeit
def recommend_coach_keyword(coachee, coaches):
    nltk.download('stopwords')
    stop_words = set(stopwords.words('english'))
    
    # Tokenize and filter out stopwords from the coachee's problem statement
    problem_words = word_tokenize(coachee['problem'].lower())
    problem_keywords = [word for word in problem_words if word.isalnum() and word not in stop_words]
    problem_keywords.extend(get_synonyms(set(problem_keywords)))
    coach_scores = {coach: 0 for coach in coaches}
    matched_keywords = {coach: [] for coach in coaches}
    
    for coach, bio in coaches.items():
        # Tokenize and filter out stopwords from the coach's bio
        bio_words = word_tokenize(bio.lower())
        bio_keywords = set([word for word in bio_words if word.isalnum() and word not in stop_words])
        
        # Count keyword matches
        for keyword in set(problem_keywords):
            if keyword in bio_keywords:
                coach_scores[coach] += 1
                matched_keywords[coach].append(keyword)

    # Sort coaches by score in descending order
    recommended_coaches = sorted(coach_scores.items(), key=lambda item: item[1], reverse=True)
    recommended_coaches = [coach for coach in recommended_coaches if coach[1] > 0]
    print(f" matched keywords for problem {coachee['problem']} :\n {matched_keywords}")
    return recommended_coaches