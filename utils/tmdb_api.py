import os
import requests

def get_movie_details(movie_id):
    """
    Fetch movie details, poster, and trailer from TMDB API using movie_id.
    """
    api_key = os.getenv('TMDB_API_KEY')
    if not api_key:
        return {'poster_path': None, 'trailer_url': None, 'rating': 'N/A', 'overview': ''}

    url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={api_key}&append_to_response=videos"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            poster_path = f"https://image.tmdb.org/t/p/w500{data.get('poster_path')}" if data.get('poster_path') else None
            
            # Find the best trailer
            trailer_url = None
            if 'videos' in data and 'results' in data['videos']:
                for video in data['videos']['results']:
                    if video['type'] == 'Trailer' and video['site'] == 'YouTube':
                        trailer_url = f"https://www.youtube.com/watch?v={video['key']}"
                        break

            return {
                'poster_path': poster_path,
                'trailer_url': trailer_url,
                'rating': round(data.get('vote_average', 0), 1),
                'overview': data.get('overview', ''),
                'title': data.get('title', ''),
                'id': movie_id
            }
    except Exception as e:
        print(f"Error fetching TMDB data for {movie_id}: {e}")
    
    return {'poster_path': None, 'trailer_url': None, 'rating': 'N/A', 'overview': '', 'title': 'Unknown', 'id': movie_id}

def search_tmdb_movie(query):
    """
    Search for a movie on TMDB by text query.
    Used as a fallback if the movie isn't in our dataset.
    Fetches full credits to support NLTK tag generation.
    """
    api_key = os.getenv('TMDB_API_KEY')
    if not api_key:
        return None

    url = f"https://api.themoviedb.org/3/search/movie?api_key={api_key}&query={query}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data['results']:
                # Return the top match but we must fetch its full details (credits)
                movie_id = data['results'][0]['id']
                details_url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={api_key}&append_to_response=credits"
                det_response = requests.get(details_url, timeout=5)
                if det_response.status_code == 200:
                    return det_response.json()
    except Exception as e:
        print(f"Error searching TMDB for {query}: {e}")
    return None

def get_full_movie_details(movie_id):
    """
    Fetch comprehensive details for the individual Movie Page.
    Includes backdrop, genres, runtime, and full cast/crew.
    """
    api_key = os.getenv('TMDB_API_KEY')
    if not api_key:
        return None
        
    url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={api_key}&append_to_response=credits,videos"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            
            # Format some useful variables
            data['poster_url'] = f"https://image.tmdb.org/t/p/w500{data.get('poster_path')}" if data.get('poster_path') else None
            data['backdrop_url'] = f"https://image.tmdb.org/t/p/original{data.get('backdrop_path')}" if data.get('backdrop_path') else None
            
            # Formatting financial and extra metadata
            data['budget_formatted'] = f"${data.get('budget'):,}" if data.get('budget') else "Unknown"
            data['revenue_formatted'] = f"${data.get('revenue'):,}" if data.get('revenue') else "Unknown"
            companies = data.get('production_companies', [])
            data['production'] = ", ".join([c['name'] for c in companies[:3]]) if companies else "Unknown"
            
            # Get Youtube Trailer
            data['trailer_key'] = None
            if 'videos' in data and 'results' in data['videos']:
                for video in data['videos']['results']:
                    if video['type'] == 'Trailer' and video['site'] == 'YouTube':
                        data['trailer_key'] = video['key']
                        break
                        
            # Get Director
            data['director'] = "Unknown"
            if 'credits' in data and 'crew' in data['credits']:
                for member in data['credits']['crew']:
                    if member['job'] == 'Director':
                        data['director'] = member['name']
                        break
                        
            # Get Top 6 Cast
            data['top_cast'] = []
            if 'credits' in data and 'cast' in data['credits']:
                data['top_cast'] = data['credits']['cast'][:6]
                for actor in data['top_cast']:
                    actor['profile_url'] = f"https://image.tmdb.org/t/p/w200{actor.get('profile_path')}" if actor.get('profile_path') else None
                    
            return data
    except Exception as e:
        print(f"Error fetching FULL TMDB data for {movie_id}: {e}")
        
    return None

def get_trending_movies():
    """Fetch the top trending movies of the week globally."""
    api_key = os.getenv('TMDB_API_KEY')
    if not api_key:
        return []
        
    url = f"https://api.themoviedb.org/3/trending/movie/week?api_key={api_key}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            results = response.json().get('results', [])
            
            # Format to match our movie card structure
            trending = []
            for movie in results[:12]:  # Get top 12 trending
                if movie.get('poster_path'):
                    trending.append({
                        'id': movie['id'],
                        'title': movie.get('title') or movie.get('original_title') or "Unknown Title",
                        'poster_path': f"https://image.tmdb.org/t/p/w500{movie['poster_path']}",
                        'rating': round(movie.get('vote_average', 0), 1)
                    })
            return trending
    except Exception as e:
        print(f"Error fetching trending movies: {e}")
    return []
