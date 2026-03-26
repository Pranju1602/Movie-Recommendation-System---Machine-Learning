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
            data['rating'] = round(data.get('vote_average', 0), 1)
            
            # Formatting financial and extra metadata
            data['budget_formatted'] = f"${data.get('budget'):,}" if data.get('budget') else "Unknown"
            data['revenue_formatted'] = f"${data.get('revenue'):,}" if data.get('revenue') else "Unknown"
            data['runtime_formatted'] = f"{data.get('runtime')} mins" if data.get('runtime') else "Unknown"
            companies = data.get('production_companies', [])
            data['production'] = ", ".join([c['name'] for c in companies[:3]]) if companies else "Unknown"
            data['genres_formatted'] = ", ".join([g['name'] for g in data.get('genres', [])]) if data.get('genres') else "Unknown"
            data['release_date_formatted'] = data.get('release_date', 'Unknown')
            data['popularity_formatted'] = f"{data.get('popularity', 0):.0f}"
            data['language_formatted'] = data.get('original_language', 'N/A').upper()
            
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

def get_movies_by_mood(mood):
    """Maps user mood to TMDB genre IDs and fetches popular matching movies."""
    mood_map = {
        'happy': '35|16|10751',     # Comedy, Animation, Family
        'sad': '18|10749',          # Drama, Romance
        'scared': '27|53',          # Horror, Thriller
        'excited': '28|12|878',     # Action, Adventure, Sci-Fi
        'romantic': '10749',        # Romance
        'mysterious': '9648|80'     # Mystery, Crime
    }
    
    genres = mood_map.get(mood.lower())
    if not genres:
        return []
        
    api_key = os.getenv('TMDB_API_KEY')
    if not api_key:
        return []
        
    url = f"https://api.themoviedb.org/3/discover/movie?api_key={api_key}&with_genres={genres}&sort_by=popularity.desc&page=1"
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            results = response.json().get('results', [])
            
            movies = []
            for movie in results[:10]:  # Return top 10 mood matches
                if movie.get('poster_path'):
                    movies.append({
                        'id': movie['id'],
                        'title': movie.get('title') or movie.get('original_title') or "Unknown Title",
                        'poster_path': f"https://image.tmdb.org/t/p/w500{movie['poster_path']}",
                        'rating': round(movie.get('vote_average', 0), 1)
                    })
            return movies
    except Exception as e:
        print(f"Error fetching mood movies: {e}")
    return []


# ═══════════════════════════════════════════
# BOX OFFICE SECTION — TMDB API FUNCTIONS
# ═══════════════════════════════════════════

def _format_box_office_movie(movie):
    """Helper: format a raw TMDB movie dict into a box office card dict."""
    budget = movie.get('budget', 0) or 0
    revenue = movie.get('revenue', 0) or 0
    profit = revenue - budget
    roi = round((profit / budget) * 100, 1) if budget > 0 else 0
    
    poster = f"https://image.tmdb.org/t/p/w500{movie['poster_path']}" if movie.get('poster_path') else None
    genres = ", ".join([g['name'] for g in movie.get('genres', [])]) if movie.get('genres') else movie.get('genres_text', '')
    
    return {
        'id': movie.get('id'),
        'title': movie.get('title') or movie.get('original_title') or 'Unknown',
        'poster_url': poster,
        'rating': round(movie.get('vote_average', 0), 1),
        'revenue': revenue,
        'budget': budget,
        'profit': profit,
        'roi': roi,
        'revenue_fmt': f"${revenue:,.0f}" if revenue else "N/A",
        'budget_fmt': f"${budget:,.0f}" if budget else "N/A",
        'profit_fmt': f"${profit:,.0f}" if profit != 0 else "N/A",
        'release_date': movie.get('release_date', 'N/A'),
        'genres': genres,
        'popularity': movie.get('popularity', 0),
        'language': (movie.get('original_language') or 'N/A').upper()
    }


def get_top_grossing(year=None, genre_id=None, language=None, page=1):
    """Fetch top grossing movies with optional year/genre/language filters."""
    api_key = os.getenv('TMDB_API_KEY')
    if not api_key:
        return []
    
    # Use popularity.desc — TMDB's revenue sort has data gaps
    url = f"https://api.themoviedb.org/3/discover/movie?api_key={api_key}&sort_by=popularity.desc&vote_count.gte=100&page={page}"
    
    if year:
        url += f"&primary_release_year={year}"
    if genre_id:
        url += f"&with_genres={genre_id}"
    if language:
        url += f"&with_original_language={language}"
    
    print(f"[BoxOffice] Top Grossing URL: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            results = response.json().get('results', [])
            movies = []
            for movie in results[:15]:
                if movie.get('poster_path'):
                    details = get_full_movie_details(movie['id'])
                    if details:
                        details['genres_text'] = ", ".join([g['name'] for g in details.get('genres', [])])
                        movies.append(_format_box_office_movie(details))
                if len(movies) >= 10:
                    break
            # Sort by revenue descending
            movies.sort(key=lambda x: x['revenue'], reverse=True)
            return movies
    except Exception as e:
        print(f"[BoxOffice] Error fetching top grossing: {e}")
    return []


def get_now_playing():
    """Fetch movies currently playing in theaters."""
    api_key = os.getenv('TMDB_API_KEY')
    if not api_key:
        return []
    
    url = f"https://api.themoviedb.org/3/movie/now_playing?api_key={api_key}&region=IN&page=1"
    try:
        response = requests.get(url, timeout=8)
        if response.status_code == 200:
            results = response.json().get('results', [])
            movies = []
            for movie in results[:12]:
                if movie.get('poster_path'):
                    genre_names = []
                    for gid in movie.get('genre_ids', []):
                        genre_names.append(str(gid))  # Will be resolved on frontend if needed
                    movies.append({
                        'id': movie['id'],
                        'title': movie.get('title') or movie.get('original_title') or 'Unknown',
                        'poster_url': f"https://image.tmdb.org/t/p/w500{movie['poster_path']}",
                        'rating': round(movie.get('vote_average', 0), 1),
                        'release_date': movie.get('release_date', 'N/A'),
                        'language': (movie.get('original_language') or 'N/A').upper(),
                        'popularity': movie.get('popularity', 0)
                    })
            return movies
    except Exception as e:
        print(f"[BoxOffice] Error fetching now playing: {e}")
    return []


def get_upcoming_movies():
    """Fetch upcoming movies releasing in the next few weeks."""
    api_key = os.getenv('TMDB_API_KEY')
    if not api_key:
        return []
    
    url = f"https://api.themoviedb.org/3/movie/upcoming?api_key={api_key}&region=IN&page=1"
    try:
        response = requests.get(url, timeout=8)
        if response.status_code == 200:
            results = response.json().get('results', [])
            movies = []
            for movie in results[:12]:
                if movie.get('poster_path'):
                    movies.append({
                        'id': movie['id'],
                        'title': movie.get('title') or movie.get('original_title') or 'Unknown',
                        'poster_url': f"https://image.tmdb.org/t/p/w500{movie['poster_path']}",
                        'rating': round(movie.get('vote_average', 0), 1),
                        'release_date': movie.get('release_date', 'Coming Soon'),
                        'language': (movie.get('original_language') or 'N/A').upper(),
                        'popularity': movie.get('popularity', 0)
                    })
            return movies
    except Exception as e:
        print(f"[BoxOffice] Error fetching upcoming: {e}")
    return []


def get_hidden_gems():
    """Fetch underrated movies — well-rated but NOT mainstream popular, including Bollywood."""
    api_key = os.getenv('TMDB_API_KEY')
    if not api_key:
        return []
    
    gems = []
    # Page 1: International hidden gems
    for lang_filter in ['', '&with_original_language=hi']:
        url = (f"https://api.themoviedb.org/3/discover/movie?api_key={api_key}"
               f"&sort_by=vote_average.desc&vote_count.gte=200&vote_count.lte=2000"
               f"&vote_average.gte=7.0&page=1{lang_filter}")
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                results = response.json().get('results', [])
                seen_ids = {g['id'] for g in gems}
                for movie in results[:12]:
                    if movie.get('poster_path') and movie['id'] not in seen_ids:
                        details = get_full_movie_details(movie['id'])
                        if details:
                            budget = details.get('budget', 0) or 0
                            revenue = details.get('revenue', 0) or 0
                            details['genres_text'] = ", ".join([g['name'] for g in details.get('genres', [])])
                            formatted = _format_box_office_movie(details)
                            if budget > 0 and revenue > 0:
                                formatted['gem_label'] = f"ROI: {formatted['roi']}%"
                            else:
                                formatted['gem_label'] = f"Rating: {formatted['rating']}"
                            gems.append(formatted)
                    if len(gems) >= 15:
                        break
        except Exception as e:
            print(f"[BoxOffice] Error fetching hidden gems: {e}")
    return gems[:15]


def get_biggest_flops():
    """Fetch known high-budget movies that underperformed at the box office."""
    api_key = os.getenv('TMDB_API_KEY')
    if not api_key:
        return []
    
    # Curated list of known big-budget movies — we check which ones actually flopped
    known_big_budget_ids = [
        766507,   # Shazam! Fury of the Gods
        640146,   # Ant-Man and the Wasp: Quantumania
        948713,   # The Flash (2023)
        868759,   # Ghostbusters: Frozen Empire
        786892,   # Furiosa: A Mad Max Saga
        746036,   # The Fall Guy (2024)
        614933,   # The Marvels
        338953,   # Fantastic Four
        337404,   # Cruella
        526896,   # Morbius
        576925,   # My Spy
        585083,   # Hotel Transylvania: Transformania
        639933,   # The Suicide Squad
        436270,   # Black Adam
        505642,   # Black Panther: Wakanda Forever
        667538,   # Transformers: Rise of the Beasts
        298618,   # The Flash
        353081,   # Mission: Impossible - Dead Reckoning
        447365,   # Guardians of the Galaxy Vol. 3
        1022789,  # Inside Out 2
    ]
    
    try:
        flops = []
        for mid in known_big_budget_ids:
            details = get_full_movie_details(mid)
            if details:
                budget = details.get('budget', 0) or 0
                revenue = details.get('revenue', 0) or 0
                # A flop = revenue didn't cover budget + marketing (rough rule: revenue < 2x budget)
                if budget > 10000000 and revenue > 0 and revenue < (budget * 2):
                    details['genres_text'] = ", ".join([g['name'] for g in details.get('genres', [])])
                    formatted = _format_box_office_movie(details)
                    estimated_loss = (budget * 2) - revenue
                    formatted['loss'] = f"${estimated_loss:,.0f}"
                    flops.append(formatted)
            if len(flops) >= 8:
                break
        flops.sort(key=lambda x: x['profit'])
        return flops
    except Exception as e:
        print(f"[BoxOffice] Error fetching flops: {e}")
    return []


def get_popular_successful():
    """Fetch movies that are both mega-popular AND critically acclaimed, including Bollywood."""
    api_key = os.getenv('TMDB_API_KEY')
    if not api_key:
        return []
    
    movies = []
    # Fetch Hollywood blockbusters + Bollywood hits
    for lang_filter in ['', '&with_original_language=hi']:
        url = (f"https://api.themoviedb.org/3/discover/movie?api_key={api_key}"
               f"&sort_by=popularity.desc&vote_average.gte=7.0&vote_count.gte=1000&page=1{lang_filter}")
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                results = response.json().get('results', [])
                seen_ids = {m['id'] for m in movies}
                for movie in results[:12]:
                    if movie.get('poster_path') and movie['id'] not in seen_ids:
                        details = get_full_movie_details(movie['id'])
                        if details:
                            details['genres_text'] = ", ".join([g['name'] for g in details.get('genres', [])])
                            movies.append(_format_box_office_movie(details))
                    if len(movies) >= 15:
                        break
        except Exception as e:
            print(f"[BoxOffice] Error fetching popular successful: {e}")
    return movies[:15]

