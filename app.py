from flask import (
    Flask, render_template, request, redirect, url_for, flash
)
import mysql.connector
from mysql.connector import IntegrityError
import os, time
from werkzeug.utils import secure_filename
from datetime import datetime
import base64
import matplotlib.pyplot as plt
from io import BytesIO




# -------------------------------------------------
# Configuration
# -------------------------------------------------
app = Flask(__name__)
app.secret_key = "REPLACE_WITH_SECURE_KEY"

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Kan@3182",
    "database": "spotify"
}

# static/uploads folder
UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED = {"png", "jpg", "jpeg", "gif"}

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def db():
    """Context-managed DB connection."""
    return mysql.connector.connect(**DB_CONFIG)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED


def save_image(file):
    """Save uploaded thumbnails safely with unique names."""
    if not file or file.filename == "":
        return None
    if not allowed_file(file.filename):
        return None

    base = secure_filename(file.filename)
    new_name = f"{int(time.time())}_{base}"
    path = os.path.join(app.config["UPLOAD_FOLDER"], new_name)
    file.save(path)
    return new_name


# -------------------------------------------------
# Home
# -------------------------------------------------
@app.route("/")
def index():
    conn = db()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT 
            (SELECT COUNT(*) FROM songs) AS songs,
            (SELECT COUNT(*) FROM artists) AS artists,
            (SELECT COUNT(*) FROM genres) AS genres,
            (SELECT COUNT(*) FROM playlists) AS playlists
    """)
    stats = cur.fetchone()
    cur.close()
    conn.close()

    return render_template("index.html", **stats)

def create_plot():
    """Convert matplotlib fig to base64 image."""
    buffer = BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight')
    buffer.seek(0)
    img = base64.b64encode(buffer.getvalue()).decode('utf-8')
    buffer.close()
    plt.close()
    return img


@app.route("/analytics")
def analytics():
    conn = db()
    cur = conn.cursor(dictionary=True)

    # 1️⃣ Songs per Genre
    cur.execute("""
        SELECT g.name AS genre, COUNT(*) AS total
        FROM songs s
        JOIN genres g ON s.genre_id = g.id
        GROUP BY g.name
    """)
    genre_data = cur.fetchall()
    genres = [row['genre'] for row in genre_data]
    genre_counts = [row['total'] for row in genre_data]

    plt.figure(figsize=(8,5))
    plt.bar(genres, genre_counts)
    plt.title("Songs per Genre")
    plt.xlabel("Genre")
    plt.ylabel("Total Songs")
    genre_chart = create_plot()

    # 2️⃣ Songs per Artist
    cur.execute("""
        SELECT a.name AS artist, COUNT(*) AS total
        FROM songs s
        JOIN artists a ON s.artist_id = a.id
        GROUP BY a.name
        ORDER BY total DESC
        LIMIT 10
    """)
    artist_data = cur.fetchall()
    artists = [row['artist'] for row in artist_data]
    artist_counts = [row['total'] for row in artist_data]

    plt.figure(figsize=(8,6))
    plt.barh(artists, artist_counts)
    plt.title("Top Artists by Number of Songs")
    plt.xlabel("Total Songs")
    artist_chart = create_plot()

    # 3️⃣ Playlist distribution
    cur.execute("""
        SELECT name, COUNT(ps.song_id) AS total
        FROM playlists p
        LEFT JOIN playlist_songs ps ON p.id = ps.playlist_id
        GROUP BY p.id
    """)
    playlist_data = cur.fetchall()
    playlist_names = [row['name'] for row in playlist_data]
    playlist_counts = [row['total'] for row in playlist_data]

    plt.figure(figsize=(7,7))
    plt.pie(playlist_counts, labels=playlist_names, autopct="%1.1f%%")
    plt.title("Songs Distribution Across Playlists")
    playlist_chart = create_plot()

    # 4️⃣ Avg song duration per genre
    cur.execute("""
        SELECT g.name AS genre, AVG(s.duration_seconds) AS avg_duration
        FROM songs s
        JOIN genres g ON s.genre_id = g.id
        GROUP BY g.name
    """)
    avg_data = cur.fetchall()
    avg_genres = [row['genre'] for row in avg_data]
    avg_duration = [row['avg_duration'] for row in avg_data]

    plt.figure(figsize=(8,5))
    plt.bar(avg_genres, avg_duration)
    plt.title("Average Song Duration per Genre")
    plt.ylabel("Seconds")
    avg_duration_chart = create_plot()

    # 5️⃣ Top 5 Most Played Songs
    cur.execute("""
        SELECT s.title, COUNT(*) AS plays
        FROM listen_events le
        JOIN songs s ON le.song_id = s.id
        GROUP BY s.id
        ORDER BY plays DESC
        LIMIT 5
    """)
    top_data = cur.fetchall()
    top_titles = [row['title'] for row in top_data]
    top_plays = [row['plays'] for row in top_data]

    plt.figure(figsize=(8,5))
    plt.bar(top_titles, top_plays)
    plt.title("Top 5 Most Played Songs")
    plt.ylabel("Play Count")
    top_songs_chart = create_plot()

    cur.close()
    conn.close()

    return render_template(
        "analytics.html",
        genre_chart=genre_chart,
        artist_chart=artist_chart,
        playlist_chart=playlist_chart,
        avg_duration_chart=avg_duration_chart,
        top_songs_chart=top_songs_chart
    )

@app.route("/analytics/top_users")
def analytics_top_users():
    conn = db()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT u.username, COUNT(*) AS play_count
        FROM listen_events le
        JOIN users u ON le.user_id = u.id
        GROUP BY u.id
        ORDER BY play_count DESC
        LIMIT 10
    """)
    data = cur.fetchall()

    # Plot
    names = [d["username"] for d in data]
    counts = [d["play_count"] for d in data]

    plt.figure(figsize=(8,5))
    plt.bar(names, counts)
    plt.xticks(rotation=45)
    plt.title("Top 10 Users — Most Songs Played")
    plt.xlabel("User")
    plt.ylabel("Play Count")

    buffer = BytesIO()
    plt.tight_layout()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    graph = base64.b64encode(buffer.getvalue()).decode()
    plt.close()

    return render_template("analytics_top_users.html", graph=graph, data=data)




@app.route("/analytics/artist_comparison")
def artist_comparison():
    conn = db()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT a.name AS artist, COUNT(*) AS plays
        FROM listen_events le
        JOIN songs s ON le.song_id = s.id
        JOIN artists a ON s.artist_id = a.id
        GROUP BY a.id
        ORDER BY plays DESC
        LIMIT 10
    """)
    data = cur.fetchall()

    artists = [d["artist"] for d in data]
    plays = [d["plays"] for d in data]

    plt.figure(figsize=(8,5))
    plt.barh(artists, plays)
    plt.title("Top Artists (by Plays)")
    plt.xlabel("Total Plays")

    buffer = BytesIO()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    graph = base64.b64encode(buffer.getvalue()).decode()
    plt.close()

    return render_template("analytics_artist_comparison.html", graph=graph, data=data)



# -------------------------------------------------
# Songs / Artists / Genres list endpoints
# -------------------------------------------------
@app.route("/songs")
def songs():
    conn = db()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT s.id, s.title, s.duration_seconds, s.release_year,
               a.name AS artist, g.name AS genre
        FROM songs s
        LEFT JOIN artists a ON s.artist_id = a.id
        LEFT JOIN genres g ON s.genre_id = g.id
        ORDER BY s.title
    """)

    all_songs = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("songs.html", songs=all_songs)


@app.route("/artists")
def artists():
    conn = db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, name FROM artists ORDER BY name;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("artists.html", artists=rows)


@app.route("/genres")
def genres():
    conn = db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, name FROM genres ORDER BY name;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("genres.html", genres=rows)

# -------------------------------------------------
# View All Playlist Songs (Table)
# -------------------------------------------------
@app.route("/playlist_songs")
def playlist_songs():
    conn = db()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT 
            p.id AS playlist_id,
            p.name AS playlist_name,
            s.title AS song_title,
            a.name AS artist,
            g.name AS genre
        FROM playlist_songs ps
        JOIN playlists p ON ps.playlist_id = p.id
        JOIN songs s ON ps.song_id = s.id
        LEFT JOIN artists a ON s.artist_id = a.id
        LEFT JOIN genres g ON s.genre_id = g.id
        ORDER BY p.name, s.title
    """)
    data = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("playlist_songs.html", playlist_songs=data)




# -------------------------------------------------
# Search
# -------------------------------------------------
@app.route("/search", methods=["GET"])
def search():
    q = request.args.get("q", "")

    conn = db()
    cur = conn.cursor(dictionary=True)

    # -------- SONGS --------
    cur.execute("""
        SELECT 
            s.id,
            s.title,
            a.id AS artist_id,
            a.name AS artist_name,
            g.id AS genre_id,
            g.name AS genre_name
        FROM songs s
        LEFT JOIN artists a ON s.artist_id = a.id
        LEFT JOIN genres g ON s.genre_id = g.id
        WHERE s.title LIKE %s
    """, (f"%{q}%",))
    songs = cur.fetchall()

    # Get artist_ids and genre_ids from matched songs
    artist_ids = list({s["artist_id"] for s in songs if s["artist_id"]})
    genre_ids = list({s["genre_id"] for s in songs if s["genre_id"]})

    # -------- ARTISTS of matched songs --------
    artists = []
    if artist_ids:
        format_ids = ",".join(["%s"] * len(artist_ids))
        cur.execute(f"SELECT * FROM artists WHERE id IN ({format_ids})", artist_ids)
        artists = cur.fetchall()

    # -------- GENRES of matched songs --------
    genres = []
    if genre_ids:
        format_ids = ",".join(["%s"] * len(genre_ids))
        cur.execute(f"SELECT * FROM genres WHERE id IN ({format_ids})", genre_ids)
        genres = cur.fetchall()

    cur.close()
    conn.close()

    results = {
        "songs": songs,
        "artists": artists,
        "genres": genres
    }

    return render_template("search.html", results=results, q=q)

# -------------------------------------------------
# Stats Page
# -------------------------------------------------
@app.route("/stats")
def stats():
    conn = db()
    cur = conn.cursor(dictionary=True)

    # top songs
    cur.execute("""
        SELECT s.id, s.title, a.name AS artist, COUNT(le.id) AS plays
        FROM songs s
        LEFT JOIN listen_events le ON s.id = le.song_id
        LEFT JOIN artists a ON s.artist_id = a.id
        GROUP BY s.id
        ORDER BY plays DESC LIMIT 10
    """)
    top_songs = cur.fetchall()

    # top artists
    cur.execute("""
        SELECT a.id, a.name, COUNT(le.id) AS plays
        FROM artists a
        LEFT JOIN songs s ON s.artist_id = a.id
        LEFT JOIN listen_events le ON s.id = le.song_id
        GROUP BY a.id
        ORDER BY plays DESC LIMIT 10
    """)
    top_artists = cur.fetchall()

    # recent plays
    cur.execute("""
        SELECT le.id, le.played_at, u.username, s.title
        FROM listen_events le
        LEFT JOIN users u ON le.user_id = u.id
        LEFT JOIN songs s ON le.song_id = s.id
        ORDER BY le.played_at DESC LIMIT 10
    """)
    recent = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("stats.html",
                           top_songs=top_songs,
                           top_artists=top_artists,
                           recent_listens=recent)


# -------------------------------------------------
# Playlist List
# -------------------------------------------------
@app.route("/playlists")
def playlists():
    conn = db()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT p.id, p.user_id, p.name, p.thumbnail, p.created_at,
               COUNT(ps.song_id) AS total_songs
        FROM playlists p
        LEFT JOIN playlist_songs ps ON p.id = ps.playlist_id
        GROUP BY p.id
        ORDER BY p.created_at DESC
    """)
    rows = cur.fetchall()

    cur.close()
    conn.close()

    # Ensure default thumbnail
    for r in rows:
        if not r["thumbnail"]:
            r["thumbnail"] = "default.jpg"

    return render_template("playlists.html", playlists=rows)


# -------------------------------------------------
# Create Playlist
# -------------------------------------------------
@app.route("/create_playlist", methods=["GET", "POST"])
def create_playlist():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        user_id = int(request.form.get("user_id", 1))

        file = request.files.get("thumbnail")
        filename = save_image(file) or "default.jpg"

        conn = db()
        cur = conn.cursor()

        try:
            cur.execute("""
                INSERT INTO playlists (user_id, name, thumbnail)
                VALUES (%s, %s, %s)
            """, (user_id, name, filename))
            conn.commit()
            flash("Playlist created successfully!", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Error: {e}", "danger")

        cur.close()
        conn.close()
        return redirect(url_for("playlists"))

    # GET → load users
    conn = db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, username FROM users ORDER BY username;")
    users = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("create_playlist.html", users=users)


# -------------------------------------------------
# Playlist Details
# -------------------------------------------------
@app.route("/playlist/<int:pid>")
def playlist_details(pid):
    conn = db()
    cur = conn.cursor(dictionary=True)

    # playlist info
    cur.execute("""
        SELECT p.id, p.user_id, p.name AS playlist_name,
               p.thumbnail, p.created_at, u.username
        FROM playlists p
        LEFT JOIN users u ON p.user_id = u.id
        WHERE p.id = %s
    """, (pid,))
    playlist = cur.fetchone()

    if not playlist:
        flash("Playlist not found.", "warning")
        return redirect(url_for("playlists"))

    if not playlist["thumbnail"]:
        playlist["thumbnail"] = "default.jpg"

    # songs in playlist
    cur.execute("""
        SELECT s.id, s.title, a.name AS artist, g.name AS genre,
               s.release_year, s.duration_seconds
        FROM playlist_songs ps
        JOIN songs s ON ps.song_id = s.id
        LEFT JOIN artists a ON s.artist_id = a.id
        LEFT JOIN genres g ON s.genre_id = g.id
        WHERE ps.playlist_id = %s
        ORDER BY s.title
    """, (pid,))
    playlist_songs = cur.fetchall()

    # songs available to add
    cur.execute("""
        SELECT id, title FROM songs
        WHERE id NOT IN (
            SELECT song_id FROM playlist_songs WHERE playlist_id = %s
        )
        ORDER BY title
    """, (pid,))
    available = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "playlist_details.html",
        playlist=playlist,
        playlist_songs=playlist_songs,
        available_songs=available
    )


@app.route("/remove_song/<int:playlist_id>/<int:song_id>")
def remove_song(playlist_id, song_id):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM playlist_songs
        WHERE playlist_id = %s AND song_id = %s
    """, (playlist_id, song_id))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(f"/edit_playlist/{playlist_id}")


@app.route("/add_song/<int:playlist_id>/<int:song_id>")
def add_song(playlist_id, song_id):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO playlist_songs (playlist_id, song_id)
        VALUES (%s, %s)
    """, (playlist_id, song_id))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(f"/edit_playlist/{playlist_id}")


# -------------------------------------------------
# Delete Playlist
# -------------------------------------------------
@app.route("/playlists/<int:pid>/delete", methods=["POST"])
def delete_playlist(pid):
    conn = db()
    cur = conn.cursor()
    cur.execute("DELETE FROM playlist_songs WHERE playlist_id=%s;", (pid,))
    cur.execute("DELETE FROM playlists WHERE id=%s;", (pid,))
    conn.commit()
    cur.close()
    conn.close()

    flash("Playlist deleted.", "success")
    return redirect(url_for("playlists"))


@app.route("/edit_playlist/<int:pid>", methods=["GET", "POST"])
def edit_playlist(pid):
    conn = db()
    cur = conn.cursor(dictionary=True)

    # Load playlist
    cur.execute("SELECT * FROM playlists WHERE id=%s", (pid,))
    playlist = cur.fetchone()

    if not playlist:
        flash("Playlist not found.", "warning")
        return redirect(url_for("playlists"))

    # Handle POST updates
    if request.method == "POST":
        new_name = request.form.get("name", "").strip()
        file = request.files.get("thumbnail")

        filename = playlist["thumbnail"]
        saved = save_image(file)
        if saved:
            filename = saved

        cur2 = conn.cursor()
        cur2.execute(
            "UPDATE playlists SET name=%s, thumbnail=%s WHERE id=%s;",
            (new_name, filename, pid)
        )
        conn.commit()
        cur2.close()

        flash("Playlist updated!", "success")
        return redirect(url_for("edit_playlist", pid=pid))

    # Get songs currently in playlist
    cur.execute("""
        SELECT s.id, s.title
        FROM playlist_songs ps
        JOIN songs s ON ps.song_id = s.id
        WHERE ps.playlist_id = %s
        ORDER BY s.title
    """, (pid,))
    songs_in = cur.fetchall()

    # Get songs not in playlist
    cur.execute("""
        SELECT id, title
        FROM songs
        WHERE id NOT IN (
            SELECT song_id FROM playlist_songs WHERE playlist_id = %s
        )
        ORDER BY title
    """, (pid,))
    songs_out = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "edit_playlist.html",
        playlist=playlist,
        songs_in=songs_in,
        songs_out=songs_out
    )


# -------------------------------------------------
# Utility
# -------------------------------------------------
@app.route("/ping")
def ping():
    return "pong"


# -------------------------------------------------
# Run
# -------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
