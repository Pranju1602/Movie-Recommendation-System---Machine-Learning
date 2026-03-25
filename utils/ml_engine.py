import pandas as pd
import pickle
import os
import re
import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from .tmdb_api import search_tmdb_movie, get_movie_details

# Load ML components safely
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    movies = pd.read_pickle(os.path.join(BASE_DIR, 'movies_df.pkl'))
    knn_model = pickle.load(open(os.path.join(BASE_DIR, 'knn_model.pkl'), 'rb'))
    tfidf_matrix = pickle.load(open(os.path.join(BASE_DIR, 'tfidf_matrix.pkl'), 'rb'))
    tfidf = pickle.load(open(os.path.join(BASE_DIR, 'tfidf.pkl'), 'rb'))
    ML_LOADED = True
except Exception as e:
    print(f"Error loading ML models: {e}")
    ML_LOADED = False

# Ensure NLTK datasets are downloaded
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)
try:
    nltk.data.find('corpora/wordnet')
except LookupError:
    nltk.download('wordnet', quiet=True)
    nltk.download('omw-1.4', quiet=True)

stop_words = set(stopwords.words('english'))
lemmatizer = WordNetLemmatizer()

def preprocess_text(text):
    text = str(text).lower()
    text = re.sub(r'[^a-zA-Z\s]', '', text)
    words = text.split()
    words = [word for word in words if word not in stop_words]
    words = [lemmatizer.lemmatize(word) for word in words]
    return " ".join(words)

def create_tags_from_api(movie_data):
    genres = " ".join([g['name'] for g in movie_data.get('genres', [])])
    overview = movie_data.get('overview', '')
    tagline = movie_data.get('tagline', '')
    
    credits = movie_data.get('credits', {})
    cast = " ".join([c['name'] for c in credits.get('cast', [])[:5]])
    
    crew = ""
    for member in credits.get('crew', []):
        if member.get('job') == "Director":
            crew += member['name'] + " "

    raw_tags = f"{genres} {overview} {tagline} {cast} {crew}"
    return preprocess_text(raw_tags)

def get_recommendations(movie_name):
    """
    Finds 10 related movies. 
    1) Tries to find the movie in the loaded dataset.
    2) If not found, uses TMDB API to get its overview, vectorizes it, and finds similar movies in dataset.
    """
    if not ML_LOADED:
        return {"error": "Machine Learning models failed to load. Check pickle files."}

    movie_name_lower = movie_name.lower().strip()
    
    # Try to find exact or partial match in dataset
    match = movies[movies['title'].str.lower() == movie_name_lower]
    
    vector = None
    if not match.empty:
        # Movie found in dataset
        idx = match.index[0]
        vector = tfidf_matrix[idx]
    else:
        # Fallback to TMDB Search
        print(f"'{movie_name}' not in dataset. Fetching from TMDB to find similar...")
        tmdb_data = search_tmdb_movie(movie_name)
        if tmdb_data:
            text_to_vectorize = create_tags_from_api(tmdb_data)
            vector = tfidf.transform([text_to_vectorize])
        else:
            return {"error": f"Movie '{movie_name}' could not be found anywhere."}
    
    # Use KNN to find 11 nearest neighbors (if found in dataset, the first one is itself)
    distances, indices = knn_model.kneighbors(vector, n_neighbors=11)
    
    recommended_movies = []
    
    # Extract results
    for i in range(1, len(indices[0])): # skip index 0 if it's the exact same movie
        idx = indices[0][i]
        movie_record = movies.iloc[idx]
        movie_id = movie_record['id']
        title = movie_record['title']
        
        # Fetch high-quality poster and trailer from TMDB using the dataset ID
        details = get_movie_details(movie_id)
        
        recommended_movies.append({
            'id': movie_id,
            'title': title,
            'poster_path': details.get('poster_path'),
            'rating': details.get('rating'),
            'trailer_url': details.get('trailer_url')
        })
        
        # Stop at 10 recommendations
        if len(recommended_movies) == 10:
            break
            
    return {"success": True, "recommendations": recommended_movies}

def get_ml_mood_recommendations(mood):
    """
    Translates raw emotions into a highly weighted set of descriptive genres and themes,
    vectorizes them natively via the TF-IDF engine, and pulls the nearest semantic neighbors from the local dataset.
    """
    if not ML_LOADED:
        return {"error": "Machine Learning models failed to load. Check pickle files."}
        
    mood_map = {
        'happy': "comedy family animation funny cheerful uplifting feel-good hilarious laugh lighthearted",
        'sad': "drama romance tragedy emotional heartbreaking tearjerker depressing melancholic grief",
        'excited': "action adventure thriller explosive fast-paced adrenaline epic breathtaking fight superhero",
        'scared': "horror thriller scary terrifying creepy ghosts supernatural suspense murder chilling",
        'relaxed': "documentary nature gentle calm peaceful slow-paced thoughtful ambient soothing",
        'romantic': "romance love story romantic-comedy relationships couples intimate passionate wedding",
        'bored': "mystery sci-fi fantasy mind-bending twist unpredictable thrilling engaging captivating puzzle",
        'curious': "documentary history historical biography true story science exploration investigative factual"
    }
    
    keywords = mood_map.get(mood.lower())
    if not keywords:
        return {"error": f"Mood '{mood}' is not mapped to any keywords."}
        
    text_to_vectorize = preprocess_text(keywords)
    vector = tfidf.transform([text_to_vectorize])
    
    # Use KNN to find 10 nearest neighbors to this specific thematic centroid
    distances, indices = knn_model.kneighbors(vector, n_neighbors=10)
    
    recommended_movies = []
    
    # Extract results
    for i in range(len(indices[0])): 
        idx = indices[0][i]
        movie_record = movies.iloc[idx]
        movie_id = movie_record['id']
        title = movie_record['title']
        
        # Fetch high-quality poster and trailer from TMDB using the dataset ID
        details = get_movie_details(movie_id)
        
        recommended_movies.append({
            'id': movie_id,
            'title': title,
            'poster_path': details.get('poster_path'),
            'rating': details.get('rating'),
            'trailer_url': details.get('trailer_url')
        })
            
    return {"success": True, "recommendations": recommended_movies}
