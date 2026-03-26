# Movie Recommendation System - Implementation Plan

## Goal Description
Build a feature-rich full-stack Movie Recommendation System using Flask, MySQL Workbench, HTML/CSS/JS, the TMDB API, and Groq API (for AI Chatbot). The system will use an existing Machine Learning backend (KNN + TF-IDF pickle files) for core recommendations and provide extensive User CRUD operations, TMDB features (Trending, Actor pages, Box Office, HD Posters), and Smart features (Mood-based mapping, Comparison, Random picker).

---

## User Review Required

> [!IMPORTANT]
> **API Keys and Database Setup**
> Before we start coding, we need to ensure the following are ready:
> 1. **MySQL Database**: Have you set up a MySQL database in Workbench? If so, what are the credentials (username/password) to connect locally, or will we use a `.env` file?
> 2. **API Keys**: You mentioned having the TMDB API key. Do you also have the Groq API key ready for the chatbot? We will store them in a `.env` file for security.

> [!WARNING]
> **Pickle Files Format**
> We're relying on [movies_df.pkl](file:///c:/Users/HP/Desktop/Anti-Project/movies_df.pkl) and [knn_model.pkl](file:///c:/Users/HP/Desktop/Anti-Project/knn_model.pkl). I will need to briefly inspect the structure of [movies_df.pkl](file:///c:/Users/HP/Desktop/Anti-Project/movies_df.pkl) in the first coding step to ensure I map the movie titles/IDs correctly when querying the TMDB API for posters and trailers. 

---

## Architecture & Database Schema

### Tech Stack
- **Backend**: Flask (Python)
- **Database**: MySQL Server (via `mysql-connector-python` or `SQLAlchemy`)
- **Frontend**: Vanilla HTML/CSS/JS (with high-quality styling and responsive design)
- **ML Engine**: `scikit-learn` / `pandas` (for loading existing [.pkl](file:///c:/Users/HP/Desktop/Anti-Project/tfidf.pkl) files)
- **APIs**: TMDB API (Movie data), Groq API (CineBot Chatbot)

### MySQL Database Schema Proposal
We will create a database named `movie_recommender_db`.

1. **`Users` Table**
   - `id` (INT, PK, Auto Increment)
   - `username` (VARCHAR, Unique)
   - `email` (VARCHAR, Unique)
   - `password_hash` (VARCHAR)
   - `is_admin` (BOOLEAN)
   - `created_at` (TIMESTAMP)

2. **`Ratings` Table**
   - `id` (INT, PK, Auto Increment)
   - `user_id` (INT, FK -> Users.id)
   - `movie_id` (INT, TMDB or Dataset ID)
   - `rating_value` (FLOAT)
   - `created_at` (TIMESTAMP)

3. **`Watchlist` Table**
   - `id` (INT, PK, Auto Increment)
   - `user_id` (INT, FK -> Users.id)
   - `movie_id` (INT, TMDB or Dataset ID)
   - `movie_title` (VARCHAR)
   - `is_watched` (BOOLEAN)
   - `added_at` (TIMESTAMP)

4. **`Reviews` Table**
   - `id` (INT, PK, Auto Increment)
   - `user_id` (INT, FK -> Users.id)
   - `movie_id` (INT, TMDB or Dataset ID)
   - `review_text` (TEXT)
   - `created_at` (TIMESTAMP)

*(Note: Movie metadata will largely be pulled dynamically from [movies_df.pkl](file:///c:/Users/HP/Desktop/Anti-Project/movies_df.pkl) and TMDB to save DB space, but the admin panel can have a custom `Movies` table if you want to manually insert independent movies).*

---

## Feature Implementation Strategy

### 1. Foundation & Core Engine
- Initialize Flask App (`app.py`, `models.py`, `routes.py`).
- Create `utils/ml_engine.py` to load [.pkl](file:///c:/Users/HP/Desktop/Anti-Project/tfidf.pkl) files and expose a `recommend_movies(movie_name)` function.
- Create `utils/tmdb_api.py` to fetch posters, trailers, and cast dynamically using the movie titles from the ML recommendations.

### 2. User Authentication & CRUD
- Build HTML templates for Login/Register.
- Configure Flask-Session/Flask-Login to manage user states.
- Develop the User Profile page and Dashboard (using **Chart.js** for visual rating breakdowns).
- Create API endpoints (`/api/watchlist/add`, `/api/rating/update`) so Javascript can interact via fetch/AJAX without reloading the page.

### 3. TMDB API Features & Smart Filters
- **Trending/Box Office**: Fetch direct endpoints from TMDB (`/trending/movie/week`).
- **Mood Filter**: Map moods to TMDB Genre IDs (e.g., Happy -> Comedy/Animation, Scared -> Horror).
- **Movie Comparison**: UI to search two movies, fetch data for both via TMDB, and display side-by-side stats.

### 4. CineBot (AI Chatbot)
- Integrate a floating UI component on the bottom right of the screen.
- Attach a Javascript event listener to handle chat toggling.
- Create a Flask route `/api/chat` that takes user input, injects a system prompt (e.g., "You are CineBot, a helpful movie assistant..."), sends it to Groq API, and returns the response.

---

## Verification Plan

### Automated/Unit Tests
- **Database Connection Test**: Write a script `test_db.py` to verify MySQL connections and table creations.
- **ML Engine Test**: Write a unit test `test_recommendation.py` to pass a known movie (like "Batman") to the ML function and ensure it returns 10 valid movie names.
- **API Tests**: Use `requests` to test TMDB integration and Groq API keys to ensure they are functioning and returning JSON.

### Manual Verification
- **Auth Flow**: Manually register a test user, log in, check session cookies, log out.
- **Watchlist & Ratings**: Manually add a movie to the watchlist, rate it, and check the database via MySQL Workbench to ensure the rows were created perfectly.
- **Responsive UI**: Test the deployment on localhost at different browser widths (Mobile, Tablet, Desktop) using Chrome Developer Tools.
- **CineBot Test**: Open the chat window, ask "SRK ki best movies batao", verify Groq responds correctly in the chat UI without page reloads.
