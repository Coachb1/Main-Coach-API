from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from commons.timeit import timeit
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.corpus import wordnet
from nltk.stem import WordNetLemmatizer


# Ensure you have the required NLTK data files
import nltk

nltk.download('averaged_perceptron_tagger')
nltk.download('wordnet')


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


def get_wordnet_pos(word):
    """Map POS tag to first character lemmatize() accepts."""
    tag = nltk.pos_tag([word])[0][1][0].upper()
    tag_dict = {"J": wordnet.ADJ,
                "N": wordnet.NOUN,
                "V": wordnet.VERB,
                "R": wordnet.ADV}
    return tag_dict.get(tag, wordnet.NOUN)

def recommend_coach_keyword(coachee, coaches):
    stop_words = set(stopwords.words('english'))
    lemmatizer = WordNetLemmatizer()
    
    # Tokenize, filter out stopwords, and lemmatize the coachee's problem statement
    problem_words = word_tokenize(coachee['problem'].lower())
    problem_keywords = [lemmatizer.lemmatize(word, get_wordnet_pos(word)) 
                        for word in problem_words if word.isalnum() and word not in stop_words]
    print(f"problem keywords: {set(problem_keywords)}")
    
    coach_scores = {coach: 0 for coach in coaches}
    matched_keywords = {coach: [] for coach in coaches}
    
    for coach, bio in coaches.items():
        # Tokenize, filter out stopwords, and lemmatize the coach's bio
        bio_words = word_tokenize(bio.lower())
        bio_keywords = set([lemmatizer.lemmatize(word, get_wordnet_pos(word)) 
                            for word in bio_words if word.isalnum() and word not in stop_words])
        print(f"{coach}: {bio_keywords}")
        
        # Count keyword matches
        for keyword in set(problem_keywords):
            if keyword in bio_keywords:
                coach_scores[coach] += 1
                matched_keywords[coach].append(keyword)

    # Sort coaches by score in descending order
    recommended_coaches = sorted(coach_scores.items(), key=lambda item: item[1], reverse=True)
    recommended_coaches = [coach for coach in recommended_coaches if coach[1] > 0]

    print(f"Matched keywords for problem '{coachee['problem']}':\n{matched_keywords}")
    return recommended_coaches