from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db import get_db_connection

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# ═══════════════════════════════════════════
# HARDCODED ADMIN CREDENTIALS (2 admins only)
# ═══════════════════════════════════════════
ADMIN_CREDENTIALS = {
    'pranjal': generate_password_hash('pranju16'),
    'nandini': generate_password_hash('nandu09')
}


def admin_required(f):
    """Decorator to protect admin routes."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Please log in as admin.', 'error')
            return redirect(url_for('admin.admin_login'))
        return f(*args, **kwargs)
    return decorated


# ═══════════════════════════════════════════
# AUTH ROUTES
# ═══════════════════════════════════════════

@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        
        if username in ADMIN_CREDENTIALS and check_password_hash(ADMIN_CREDENTIALS[username], password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            flash(f'Welcome back, {username.capitalize()}!', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Invalid admin credentials.', 'error')
    
    return render_template('admin_login.html')


@admin_bp.route('/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    flash('Logged out from admin panel.', 'success')
    return redirect(url_for('admin.admin_login'))


# ═══════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════

@admin_bp.route('/')
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    conn = get_db_connection()
    stats = {}
    recent_activity = []
    genre_stats = []
    
    if conn:
        cursor = conn.cursor(dictionary=True)
        
        # Total counts
        cursor.execute("SELECT COUNT(*) as count FROM users")
        stats['users'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM ratings")
        stats['ratings'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM reviews")
        stats['reviews'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM watchlist")
        stats['watchlist'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM admin_movies")
        stats['movies'] = cursor.fetchone()['count']
        
        # Average rating
        cursor.execute("SELECT ROUND(AVG(rating_value), 1) as avg FROM ratings")
        row = cursor.fetchone()
        stats['avg_rating'] = row['avg'] if row['avg'] else 0
        
        # Recent users (last 5)
        cursor.execute("SELECT username, email, created_at FROM users ORDER BY created_at DESC LIMIT 5")
        recent_users = cursor.fetchall()
        for u in recent_users:
            recent_activity.append({'type': 'user', 'text': f"New user: {u['username']}", 'date': u['created_at']})
        
        # Recent reviews (last 5)
        cursor.execute("""
            SELECT r.review_text, r.created_at, u.username, r.movie_id 
            FROM reviews r JOIN users u ON r.user_id = u.id 
            ORDER BY r.created_at DESC LIMIT 5
        """)
        recent_reviews = cursor.fetchall()
        for rv in recent_reviews:
            recent_activity.append({'type': 'review', 'text': f"{rv['username']} reviewed movie #{rv['movie_id']}", 'date': rv['created_at']})
        
        # Recent ratings (last 5)
        cursor.execute("""
            SELECT ra.rating_value, ra.created_at, u.username, ra.movie_id 
            FROM ratings ra JOIN users u ON ra.user_id = u.id 
            ORDER BY ra.created_at DESC LIMIT 5
        """)
        recent_ratings = cursor.fetchall()
        for rt in recent_ratings:
            recent_activity.append({'type': 'rating', 'text': f"{rt['username']} rated movie #{rt['movie_id']} — ⭐{rt['rating_value']}", 'date': rt['created_at']})
        
        # Sort activity by date
        recent_activity.sort(key=lambda x: x['date'], reverse=True)
        recent_activity = recent_activity[:10]
        
        # Rating distribution for chart
        cursor.execute("""
            SELECT FLOOR(rating_value) as score, COUNT(*) as count 
            FROM ratings GROUP BY FLOOR(rating_value) ORDER BY score
        """)
        stats['rating_dist'] = cursor.fetchall()
        
        cursor.close()
        conn.close()
    
    return render_template('admin.html', section='dashboard', stats=stats, 
                           recent_activity=recent_activity, admin_name=session.get('admin_username', 'Admin'))


# ═══════════════════════════════════════════
# USER MANAGEMENT
# ═══════════════════════════════════════════

@admin_bp.route('/users')
@admin_required
def users():
    conn = get_db_connection()
    users_list = []
    search = request.args.get('search', '')
    
    if conn:
        cursor = conn.cursor(dictionary=True)
        if search:
            cursor.execute("""
                SELECT u.*, 
                    (SELECT COUNT(*) FROM ratings WHERE user_id = u.id) as rating_count,
                    (SELECT COUNT(*) FROM reviews WHERE user_id = u.id) as review_count,
                    (SELECT COUNT(*) FROM watchlist WHERE user_id = u.id) as watchlist_count
                FROM users u 
                WHERE u.username LIKE %s OR u.email LIKE %s
                ORDER BY u.created_at DESC
            """, (f'%{search}%', f'%{search}%'))
        else:
            cursor.execute("""
                SELECT u.*, 
                    (SELECT COUNT(*) FROM ratings WHERE user_id = u.id) as rating_count,
                    (SELECT COUNT(*) FROM reviews WHERE user_id = u.id) as review_count,
                    (SELECT COUNT(*) FROM watchlist WHERE user_id = u.id) as watchlist_count
                FROM users u ORDER BY u.created_at DESC
            """)
        users_list = cursor.fetchall()
        cursor.close()
        conn.close()
    
    return render_template('admin.html', section='users', users=users_list, search=search,
                           admin_name=session.get('admin_username', 'Admin'))


@admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash('User deleted successfully.', 'success')
    return redirect(url_for('admin.users'))


# ═══════════════════════════════════════════
# MOVIE MANAGEMENT
# ═══════════════════════════════════════════

@admin_bp.route('/movies')
@admin_required
def movies():
    conn = get_db_connection()
    movies_list = []
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admin_movies ORDER BY created_at DESC")
        movies_list = cursor.fetchall()
        cursor.close()
        conn.close()
    
    return render_template('admin.html', section='movies', movies=movies_list,
                           admin_name=session.get('admin_username', 'Admin'))


@admin_bp.route('/movies/add', methods=['POST'])
@admin_required
def add_movie():
    title = request.form.get('title', '').strip()
    genre = request.form.get('genre', '').strip()
    cast_names = request.form.get('cast_names', '').strip()
    director = request.form.get('director', '').strip()
    release_year = request.form.get('release_year', '')
    description = request.form.get('description', '').strip()
    rating = request.form.get('rating', 0)
    trailer_link = request.form.get('trailer_link', '').strip()
    poster_url = request.form.get('poster_url', '').strip()
    language = request.form.get('language', 'English').strip()
    
    if not title:
        flash('Movie title is required.', 'error')
        return redirect(url_for('admin.movies'))
    
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO admin_movies (title, genre, cast_names, director, release_year, 
                                      description, rating, trailer_link, poster_url, language)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (title, genre, cast_names, director, 
              int(release_year) if release_year else None,
              description, float(rating) if rating else 0, 
              trailer_link, poster_url, language))
        conn.commit()
        cursor.close()
        conn.close()
        flash(f'Movie "{title}" added successfully!', 'success')
    
    return redirect(url_for('admin.movies'))


@admin_bp.route('/movies/edit/<int:movie_id>', methods=['POST'])
@admin_required
def edit_movie(movie_id):
    title = request.form.get('title', '').strip()
    genre = request.form.get('genre', '').strip()
    cast_names = request.form.get('cast_names', '').strip()
    director = request.form.get('director', '').strip()
    release_year = request.form.get('release_year', '')
    description = request.form.get('description', '').strip()
    rating = request.form.get('rating', 0)
    trailer_link = request.form.get('trailer_link', '').strip()
    poster_url = request.form.get('poster_url', '').strip()
    language = request.form.get('language', 'English').strip()
    
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE admin_movies SET title=%s, genre=%s, cast_names=%s, director=%s, 
            release_year=%s, description=%s, rating=%s, trailer_link=%s, poster_url=%s, language=%s
            WHERE id=%s
        """, (title, genre, cast_names, director,
              int(release_year) if release_year else None,
              description, float(rating) if rating else 0,
              trailer_link, poster_url, language, movie_id))
        conn.commit()
        cursor.close()
        conn.close()
        flash(f'Movie "{title}" updated!', 'success')
    
    return redirect(url_for('admin.movies'))


@admin_bp.route('/movies/delete/<int:movie_id>', methods=['POST'])
@admin_required
def delete_movie(movie_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM admin_movies WHERE id = %s", (movie_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Movie deleted.', 'success')
    return redirect(url_for('admin.movies'))


# ═══════════════════════════════════════════
# RATINGS MANAGEMENT
# ═══════════════════════════════════════════

@admin_bp.route('/ratings')
@admin_required
def ratings():
    conn = get_db_connection()
    ratings_list = []
    rating_stats = {}
    
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT r.*, u.username 
            FROM ratings r JOIN users u ON r.user_id = u.id 
            ORDER BY r.created_at DESC
        """)
        ratings_list = cursor.fetchall()
        
        # Most rated movies (by movie_id count)
        cursor.execute("""
            SELECT movie_id, COUNT(*) as count, ROUND(AVG(rating_value),1) as avg_rating
            FROM ratings GROUP BY movie_id ORDER BY count DESC LIMIT 10
        """)
        rating_stats['most_rated'] = cursor.fetchall()
        
        cursor.close()
        conn.close()
    
    return render_template('admin.html', section='ratings', ratings=ratings_list, rating_stats=rating_stats,
                           admin_name=session.get('admin_username', 'Admin'))


@admin_bp.route('/ratings/delete/<int:rating_id>', methods=['POST'])
@admin_required
def delete_rating(rating_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ratings WHERE id = %s", (rating_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Rating deleted.', 'success')
    return redirect(url_for('admin.ratings'))


# ═══════════════════════════════════════════
# REVIEWS MANAGEMENT
# ═══════════════════════════════════════════

@admin_bp.route('/reviews')
@admin_required
def reviews():
    conn = get_db_connection()
    reviews_list = []
    
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT rv.*, u.username
            FROM reviews rv JOIN users u ON rv.user_id = u.id
            ORDER BY rv.created_at DESC
        """)
        reviews_list = cursor.fetchall()
        cursor.close()
        conn.close()
    
    return render_template('admin.html', section='reviews', reviews=reviews_list,
                           admin_name=session.get('admin_username', 'Admin'))


@admin_bp.route('/reviews/delete/<int:review_id>', methods=['POST'])
@admin_required
def delete_review(review_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM reviews WHERE id = %s", (review_id,))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Review deleted.', 'success')
    return redirect(url_for('admin.reviews'))


# ═══════════════════════════════════════════
# ANALYTICS
# ═══════════════════════════════════════════

@admin_bp.route('/analytics')
@admin_required
def analytics():
    conn = get_db_connection()
    analytics_data = {}
    
    if conn:
        cursor = conn.cursor(dictionary=True)
        
        # Most watchlisted movies
        cursor.execute("""
            SELECT movie_id, movie_title, COUNT(*) as count
            FROM watchlist GROUP BY movie_id, movie_title 
            ORDER BY count DESC LIMIT 10
        """)
        analytics_data['most_watchlisted'] = cursor.fetchall()
        
        # Most watched (completed) movies
        cursor.execute("""
            SELECT movie_id, movie_title, COUNT(*) as count
            FROM watchlist WHERE watched = TRUE 
            GROUP BY movie_id, movie_title 
            ORDER BY count DESC LIMIT 10
        """)
        analytics_data['most_watched'] = cursor.fetchall()
        
        # Users with most activity
        cursor.execute("""
            SELECT u.username,
                (SELECT COUNT(*) FROM ratings WHERE user_id = u.id) as ratings,
                (SELECT COUNT(*) FROM reviews WHERE user_id = u.id) as reviews,
                (SELECT COUNT(*) FROM watchlist WHERE user_id = u.id) as watchlist
            FROM users u
            ORDER BY (
                (SELECT COUNT(*) FROM ratings WHERE user_id = u.id) +
                (SELECT COUNT(*) FROM reviews WHERE user_id = u.id) +
                (SELECT COUNT(*) FROM watchlist WHERE user_id = u.id)
            ) DESC LIMIT 10
        """)
        analytics_data['top_users'] = cursor.fetchall()
        
        # Rating distribution
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN rating_value BETWEEN 1 AND 2 THEN '1-2 ⭐'
                    WHEN rating_value BETWEEN 2 AND 4 THEN '2-4 ⭐'
                    WHEN rating_value BETWEEN 4 AND 6 THEN '4-6 ⭐'
                    WHEN rating_value BETWEEN 6 AND 8 THEN '6-8 ⭐'
                    ELSE '8-10 ⭐'
                END as bracket,
                COUNT(*) as count
            FROM ratings GROUP BY bracket ORDER BY bracket
        """)
        analytics_data['rating_brackets'] = cursor.fetchall()
        
        # Signups over time (by month)
        cursor.execute("""
            SELECT DATE_FORMAT(created_at, '%Y-%m') as month, COUNT(*) as count
            FROM users GROUP BY month ORDER BY month DESC LIMIT 12
        """)
        analytics_data['signups'] = cursor.fetchall()
        
        cursor.close()
        conn.close()
    
    return render_template('admin.html', section='analytics', analytics=analytics_data,
                           admin_name=session.get('admin_username', 'Admin'))
