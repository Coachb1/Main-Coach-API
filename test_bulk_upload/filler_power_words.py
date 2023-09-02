
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import pandas as pd
import nltk

def filler_power_word(response):
    nltk.download('stopwords')
    stop_words = set(stopwords.words('english'))
    
    word_tokens = word_tokenize(response)
    words = []
    for w in word_tokens:
        if w not in stop_words:
            words.append(w)
    generic_power_words = pd.read_csv(r"test_bulk_upload\filler_power_word.csv").drop('Filler words', axis=1)

    power_words = []

    for i in generic_power_words.columns:
        for j in generic_power_words[i].dropna():
            
            power_words.append(j.lower())

    power_word = []

    for word in words:
        if word.lower() in power_words:
            power_word.append(word.lower())

    filler_words = pd.read_csv(r"test_bulk_upload\filler_power_word.csv")['Filler words'].dropna()

    filler_words = [w.lower() for w in filler_words]

    
    fill_word = []
    # print(words)
    for word in words:
        if word.lower() in filler_words:
            fill_word.append(word.lower())

    return set(power_word),set(fill_word)
