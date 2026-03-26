from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from functools import wraps
import sys
import os
import requests

# Add parent directory to path to allow absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.ml_engine import get_recommendations
from utils.tmdb_api import (get_full_movie_details, get_trending_movies, 
                            get_top_grossing, get_now_playing, get_upcoming_movies,
                            get_hidden_gems, get_popular_successful)
from utils.db import get_db_connection

main_bp = Blueprint('main', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "danger")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@main_bp.route('/', methods=['GET'])
@login_required
def home():
    recommendations = []
    search_query = request.args.get('q', '')
    mood_query = request.args.get('mood', '')
    error = None
    
    if search_query:
        result = get_recommendations(search_query)
        if "error" in result:
            error = result["error"]
        else:
            recommendations = result.get("recommendations", [])
    elif mood_query:
        from utils.ml_engine import get_ml_mood_recommendations
        result = get_ml_mood_recommendations(mood_query)
        if "error" in result:
            error = result["error"]
        else:
            recommendations = result.get("recommendations", [])
            
    trending_movies = get_trending_movies()
                
    return render_template('index.html', recommendations=recommendations, trending_movies=trending_movies, search_query=search_query, current_mood=mood_query, error=error)

@main_bp.route('/movie/<int:movie_id>')
@login_required
def movie_detail(movie_id):
    details = get_full_movie_details(movie_id)
    if not details:
        flash("Could not fetch movie details from TMDB.", "danger")
        return redirect(url_for('main.home'))
        
    user_id = session.get('user_id')
    in_watchlist = False
    user_rating = 0
    reviews = []
    
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        
        # Always fetch reviews globally
        cursor.execute("""
            SELECT r.review_text, r.created_at, u.username 
            FROM reviews r 
            JOIN users u ON r.user_id = u.id 
            WHERE r.movie_id = %s 
            ORDER BY r.created_at DESC
        """, (movie_id,))
        fetched_reviews = cursor.fetchall()
        for r in fetched_reviews:
            r['date'] = r['created_at'].strftime("%B %d, %Y")
        reviews = fetched_reviews
        
        # Check user-specific states
        if user_id:
            cursor.execute("SELECT id FROM watchlist WHERE user_id = %s AND movie_id = %s", (user_id, movie_id))
            if cursor.fetchone():
                in_watchlist = True
                
            cursor.execute("SELECT rating_value FROM ratings WHERE user_id = %s AND movie_id = %s", (user_id, movie_id))
            rating_row = cursor.fetchone()
            if rating_row:
                user_rating = rating_row['rating_value']
                
        cursor.close()
        conn.close()
        
    return render_template('movie_detail.html', movie=details, in_watchlist=in_watchlist, user_rating=user_rating, reviews=reviews)

@main_bp.route('/movie/<int:movie_id>/review', methods=['POST'])
@login_required
def submit_review(movie_id):
    review_text = request.form.get('review_text')
    user_id = session['user_id']
    
    if review_text and len(review_text.strip()) > 0:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO reviews (user_id, movie_id, review_text) VALUES (%s, %s, %s)", 
                               (user_id, movie_id, review_text.strip()))
                conn.commit()
                flash("Review posted successfully!", "success")
            except Exception as e:
                flash("Error posting review.", "danger")
            finally:
                cursor.close()
                conn.close()
    else:
        flash("Review cannot be empty.", "danger")
        
    return redirect(url_for('main.movie_detail', movie_id=movie_id))

@main_bp.route('/watchlist')
@login_required
def watchlist():
    user_id = session['user_id']
    conn = get_db_connection()
    movies = []
    
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT movie_id, movie_title, watched FROM watchlist WHERE user_id = %s ORDER BY added_at DESC", (user_id,))
        watchlist_items = cursor.fetchall()
        
        for item in watchlist_items:
            details = get_full_movie_details(item['movie_id'])
            if details:
                movies.append({
                    'id': item['movie_id'],
                    'title': item['movie_title'],
                    'poster_url': details.get('poster_url'),
                    'rating': round(details.get('vote_average', 0), 1),
                    'watched': bool(item['watched'])
                })
        cursor.close()
        conn.close()
        
    return render_template('watchlist.html', movies=movies)

@main_bp.route('/ratings')
@login_required
def ratings():
    user_id = session['user_id']
    conn = get_db_connection()
    movies = []
    
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT r.id as rating_record_id, r.movie_id, r.rating_value, r.created_at
            FROM ratings r 
            WHERE r.user_id = %s 
            ORDER BY r.created_at DESC
        """, (user_id,))
        rating_items = cursor.fetchall()
        
        for item in rating_items:
            details = get_full_movie_details(item['movie_id'])
            if details:
                movies.append({
                    'id': item['movie_id'],
                    'title': details.get('title', 'Unknown'),
                    'poster_url': details.get('poster_url'),
                    'user_rating': item['rating_value'],
                    'date': item['created_at'].strftime("%Y-%m-%d")
                })
        cursor.close()
        conn.close()
        
    return render_template('ratings.html', movies=movies)

@main_bp.route('/api/watchlist/toggle', methods=['POST'])
@login_required
def toggle_watchlist():
    data = request.json
    movie_id = data.get('movie_id')
    movie_title = data.get('movie_title')
    user_id = session['user_id']
    
    if not movie_id or not movie_title:
        return jsonify({"success": False, "error": "Missing data"}), 400
        
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "Database error"}), 500
        
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM watchlist WHERE user_id = %s AND movie_id = %s", (user_id, movie_id))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute("DELETE FROM watchlist WHERE id = %s", (existing[0],))
            action = "removed"
        else:
            cursor.execute("INSERT INTO watchlist (user_id, movie_id, movie_title) VALUES (%s, %s, %s)", 
                           (user_id, movie_id, movie_title))
            action = "added"
            
        conn.commit()
        return jsonify({"success": True, "action": action})
    except Exception as e:
        print(f"Watchlist Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@main_bp.route('/api/watchlist/status', methods=['POST'])
@login_required
def toggle_watch_status():
    data = request.json
    movie_id = data.get('movie_id')
    watched = data.get('watched')  # True or False
    user_id = session['user_id']
    
    if movie_id is None or watched is None:
        return jsonify({"success": False, "error": "Missing data"}), 400
        
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "DB Error"}), 500
        
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE watchlist SET watched = %s WHERE user_id = %s AND movie_id = %s", 
                       (watched, user_id, movie_id))
        conn.commit()
        return jsonify({"success": True, "watched": watched})
    except Exception as e:
        print(f"Watch Status Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@main_bp.route('/api/ratings/rate', methods=['POST'])
@login_required
def rate_movie():
    data = request.json
    movie_id = data.get('movie_id')
    rating = data.get('rating')
    user_id = session['user_id']
    
    if not movie_id or not rating:
        return jsonify({"success": False, "error": "Missing data"}), 400
        
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "DB Error"}), 500
        
    cursor = conn.cursor()
    try:
        # Upsert: Insert new rating, or update if user already rated this movie
        cursor.execute("""
            INSERT INTO ratings (user_id, movie_id, rating_value) 
            VALUES (%s, %s, %s) 
            ON DUPLICATE KEY UPDATE rating_value = VALUES(rating_value)
        """, (user_id, movie_id, rating))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        print(f"Rating Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@main_bp.route('/api/ratings/delete', methods=['POST'])
@login_required
def delete_rating():
    data = request.json
    movie_id = data.get('movie_id')
    user_id = session['user_id']
    
    if not movie_id:
        return jsonify({"success": False, "error": "Missing data"}), 400
        
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "error": "DB Error"}), 500
        
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM ratings WHERE user_id = %s AND movie_id = %s", (user_id, movie_id))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        print(f"Rating Delete Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@main_bp.route('/compare', methods=['GET', 'POST'])
@login_required
def compare_movies():
    movie1_data = None
    movie2_data = None
    query1 = ''
    query2 = ''
    error = None

    if request.method == 'POST':
        query1 = request.form.get('movie1', '').strip()
        query2 = request.form.get('movie2', '').strip()
        
        if query1 and query2:
            from utils.tmdb_api import search_tmdb_movie, get_full_movie_details
            
            m1_search = search_tmdb_movie(query1)
            m2_search = search_tmdb_movie(query2)
            
            if m1_search and m2_search:
                movie1_data = get_full_movie_details(m1_search['id'])
                movie2_data = get_full_movie_details(m2_search['id'])
            else:
                if not m1_search:
                    error = f"Could not find a match for '{query1}'"
                if not m2_search:
                    error = f"Could not find a match for '{query2}'"
        else:
            error = "Please enter both movies to compare."
            
    return render_template('compare.html', m1=movie1_data, m2=movie2_data, q1=query1, q2=query2, error=error)

@main_bp.route('/api/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message', '')
    if not user_message:
        return jsonify({"success": False, "error": "Empty message"}), 400
        
    groq_api_key = os.getenv('GROQ_API_KEY')
    if not groq_api_key:
        return jsonify({"success": False, "error": "Groq API key not configured."}), 500
        
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json"
    }
    
    system_prompt = """You are CineBot, a highly enthusiastic and incredibly knowledgeable AI movie expert for the platform CineMatch. 
Keep your answers extremely brief, punchy, and formatted beautifully (use emojis and bold text). 
If a user asks for recommendations, give them 2-3 top choices with a 1-sentence hyped-up description. You use Netflix-style terminology. Always stay in character!"""

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.7,
        "max_tokens": 512
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            bot_reply = data['choices'][0]['message']['content']
            return jsonify({"success": True, "response": bot_reply})
        else:
            return jsonify({"success": False, "error": f"Groq Error: {response.text}"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@main_bp.route('/boxoffice')
def box_office():
    """Box Office Central — 6-section page with filters."""
    # Read filter query params
    year = request.args.get('year', '')
    genre_id = request.args.get('genre', '')
    language = request.args.get('lang', '')
    
    # Fetch all sections
    top_grossing = get_top_grossing(
        year=int(year) if year else None,
        genre_id=int(genre_id) if genre_id else None,
        language=language if language else None
    )
    popular = get_popular_successful()
    gems = get_hidden_gems()
    now_playing = get_now_playing()
    upcoming = get_upcoming_movies()
    
    # Genre options for filter dropdown
    genre_options = [
        {'id': 28, 'name': 'Action'}, {'id': 12, 'name': 'Adventure'},
        {'id': 16, 'name': 'Animation'}, {'id': 35, 'name': 'Comedy'},
        {'id': 80, 'name': 'Crime'}, {'id': 18, 'name': 'Drama'},
        {'id': 14, 'name': 'Fantasy'}, {'id': 27, 'name': 'Horror'},
        {'id': 10749, 'name': 'Romance'}, {'id': 878, 'name': 'Sci-Fi'},
        {'id': 53, 'name': 'Thriller'}, {'id': 10752, 'name': 'War'}
    ]
    
    # Language options for filter dropdown 
    lang_options = [
        {'code': 'en', 'name': 'Hollywood 🇺🇸'},
        {'code': 'hi', 'name': 'Bollywood 🇮🇳'},
        {'code': 'te', 'name': 'Telugu'},
        {'code': 'ta', 'name': 'Tamil'},
        {'code': 'ml', 'name': 'Malayalam'},
        {'code': 'kn', 'name': 'Kannada'},
        {'code': 'ko', 'name': 'Korean 🇰🇷'},
        {'code': 'ja', 'name': 'Japanese 🇯🇵'}
    ]
    
    # Year range for dropdown
    import datetime
    current_year = datetime.datetime.now().year
    years = list(range(current_year, 1999, -1))
    
    return render_template('boxoffice.html',
        top_grossing=top_grossing,
        popular=popular,
        gems=gems,
        now_playing=now_playing,
        upcoming=upcoming,
        genre_options=genre_options,
        lang_options=lang_options,
        years=years,
        selected_year=year,
        selected_genre=genre_id,
        selected_lang=language
    )

