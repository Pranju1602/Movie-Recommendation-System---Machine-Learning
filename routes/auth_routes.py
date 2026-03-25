from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import os
import sys

# Add parent directory to path to allow absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.db import get_db_connection

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", 
                               (username, email, hashed_password))
                conn.commit()
                flash("Registration successful! Please sign in.", "success")
                return redirect(url_for('auth.login'))
            except mysql.connector.IntegrityError:
                flash("Email or Username already exists.", "danger")
            finally:
                cursor.close()
                conn.close()

    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()

            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                flash("Logged in successfully!", "success")
                return redirect(url_for('main.home'))
            else:
                flash("Invalid email or password", "danger")

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('main.home'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        flash("Please log in to view your profile.", "danger")
        return redirect(url_for('auth.login'))
        
    user_id = session['user_id']
    conn = get_db_connection()
    user_data = {}
    stats = {'watchlist_count': 0, 'ratings_count': 0, 'reviews_count': 0}
    
    if request.method == 'POST':
        new_username = request.form.get('username')
        new_email = request.form.get('email')
        
        if conn and new_username and new_email:
            cursor = conn.cursor()
            try:
                # Check if email or username already exists for OTHER users
                cursor.execute("SELECT id FROM users WHERE (email = %s OR username = %s) AND id != %s", (new_email, new_username, user_id))
                if cursor.fetchone():
                    flash("Username or Email is already taken by another account.", "danger")
                else:
                    cursor.execute("UPDATE users SET username = %s, email = %s WHERE id = %s", (new_username, new_email, user_id))
                    conn.commit()
                    session['username'] = new_username  # update session
                    flash("Profile updated successfully!", "success")
            except Exception as e:
                flash("Error updating profile.", "danger")
                print(f"Profile update error: {e}")
            finally:
                cursor.close()
                
    if conn:
        cursor = conn.cursor(dictionary=True)
        # Fetch user basis
        cursor.execute("SELECT username, email, created_at FROM users WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
        if user_data:
            user_data['member_since'] = user_data['created_at'].strftime("%B %Y")
            
        # Fetch stats
        cursor.execute("SELECT COUNT(*) as c FROM watchlist WHERE user_id = %s", (user_id,))
        stats['watchlist_count'] = cursor.fetchone()['c']
        
        cursor.execute("SELECT COUNT(*) as c FROM ratings WHERE user_id = %s", (user_id,))
        stats['ratings_count'] = cursor.fetchone()['c']
        
        cursor.execute("SELECT COUNT(*) as c FROM reviews WHERE user_id = %s", (user_id,))
        stats['reviews_count'] = cursor.fetchone()['c']
        
        cursor.close()
        conn.close()
        
    return render_template('profile.html', user=user_data, stats=stats)

@auth_bp.route('/profile/delete', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    user_id = session['user_id']
    conn = get_db_connection()
    
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()
            session.clear()
            flash("Your account and all associated data have been permanently deleted.", "success")
        except Exception as e:
            flash("Error deleting account.", "danger")
            print(f"Account delete error: {e}")
        finally:
            cursor.close()
            conn.close()
            
    return redirect(url_for('main.home'))
