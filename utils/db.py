import mysql.connector
import os

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', ''),
            database=os.getenv('DB_NAME', 'movie_recommender_db')
        )
        return connection
    except mysql.connector.Error as err:
        print(f"Database Connection Error: {err}")
        return None

def init_db():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        
        # Create Users table if not exists (User already created this, but good to ensure)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE,
                email VARCHAR(100) UNIQUE,
                password VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create Watchlist table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                movie_id INT,
                movie_title VARCHAR(255),
                watched BOOLEAN DEFAULT FALSE,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE KEY unique_user_movie (user_id, movie_id)
            )
        """)
        
        # Add watched column if table already exists without it
        try:
            cursor.execute("ALTER TABLE watchlist ADD COLUMN watched BOOLEAN DEFAULT FALSE")
            conn.commit()
        except:
            pass
        
        # Create Ratings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ratings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                movie_id INT,
                rating_value FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE KEY unique_user_movie_rating (user_id, movie_id)
            )
        """)
        
        # Create Reviews table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                movie_id INT,
                review_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # Create Admin Movies table (custom movies added by admin)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_movies (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                genre VARCHAR(255),
                cast_names TEXT,
                director VARCHAR(255),
                release_year INT,
                description TEXT,
                rating FLOAT DEFAULT 0,
                trailer_link VARCHAR(500),
                poster_url VARCHAR(500),
                language VARCHAR(50) DEFAULT 'English',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        print("Database initialized successfully.")
