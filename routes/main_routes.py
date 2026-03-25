from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from functools import wraps
import sys
import os
import requests

# Add parent directory to path to allow absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.ml_engine import get_recommendations
from utils.tmdb_api import get_full_movie_details, get_trending_movies
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
    error = None
    
    if search_query:
        result = get_recommendations(search_query)
        if "error" in result:
            error = result["error"]
        else:
            recommendations = result.get("recommendations", [])
            
    trending_movies = get_trending_movies()
                
    return render_template('index.html', recommendations=recommendations, trending_movies=trending_movies, search_query=search_query, error=error)

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
        cursor.execute("SELECT movie_id, movie_title FROM watchlist WHERE user_id = %s ORDER BY added_at DESC", (user_id,))
        watchlist_items = cursor.fetchall()
        
        # We need fetching basic details like poster for the UI grid.
        for item in watchlist_items:
            details = get_full_movie_details(item['movie_id'])
            if details:
                movies.append({
                    'id': item['movie_id'],
                    'title': item['movie_title'],
                    'poster_url': details.get('poster_url'),
                    'rating': round(details.get('vote_average', 0), 1)
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
