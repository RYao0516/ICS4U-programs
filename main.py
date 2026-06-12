import tomllib
import os
import sqlite3
from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ==========================================
# 1. Load Security Credentials from TOML
# ==========================================
try:
    with open("secrets.toml", "rb") as toml_file:
        secrets = tomllib.load(toml_file)
    print("Secrets status:", secrets["hidden"]["message"])
    FLASK_KEY = secrets["flask"]["secret_key"]
except Exception as e:
    print(f"Failed to read secrets.toml: {e}")
    FLASK_KEY = "fallback-secret-key-default"

# ==========================================
# 2. Flask Initialization & Path Config
# ==========================================
app = Flask(__name__)
app.secret_key = FLASK_KEY

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/uploads')
DB_PATH = os.path.join(BASE_DIR, 'instance', 'social_media.db')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # Max size 50MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# ==========================================
# 3. Database Initialization
# ==========================================
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            fullname TEXT,
            avatar TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            filename TEXT NOT NULL,
            title TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# ==========================================
# 4. TikTok-Style UI HTML Template (With Settings Support)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VibeShare - Premium Social App</title>
    <style>
        :root {
            --bg-color: #f6f8fa;
            --card-bg: #ffffff;
            --primary: #fe2c55; 
            --primary-hover: #e02447;
            --text-main: #24292f;
            --text-muted: #57606a;
            --border: #d0d7de;
        }
        
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; 
            margin: 0; 
            padding: 0;
            background-color: var(--bg-color); 
            color: var(--text-main); 
        }

        .navbar {
            position: sticky;
            top: 0;
            background: rgba(255, 255, 255, 0.9);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border);
            z-index: 1000;
        }
        .nav-container {
            max-width: 1000px;
            margin: auto;
            padding: 12px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .logo {
            font-size: 1.4rem;
            font-weight: 800;
            color: var(--text-main);
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .nav-links {
            display: flex;
            align-items: center;
            gap: 20px;
        }
        .nav-links a {
            color: var(--text-muted);
            text-decoration: none;
            font-weight: 500;
            font-size: 0.95rem;
        }
        
        /* Make Avatar Clickable and Give Hover Effect */
        .user-badge-link {
            display: flex;
            align-items: center;
            gap: 10px;
            text-decoration: none;
            color: inherit;
            cursor: pointer;
            padding: 4px 8px;
            border-radius: 20px;
            transition: background 0.2s;
        }
        .user-badge-link:hover {
            background: rgba(0, 0, 0, 0.05);
        }
        
        .avatar-img {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            object-fit: cover;
            border: 2px solid var(--primary);
        }
        .avatar-placeholder {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            background: #24292f;
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 0.9rem;
        }

        .main-content {
            max-width: 680px;
            margin: 30px auto;
            padding: 0 20px;
        }

        .flash { 
            background: #ffeef1; 
            color: var(--primary); 
            padding: 14px 18px; 
            border-radius: 8px; 
            margin-bottom: 25px; 
            border: 1px solid #ffccd4;
            font-size: 0.95rem;
            text-align: center;
            font-weight: 600;
            box-shadow: 0 2px 6px rgba(254, 44, 85, 0.1);
        }

        .tabs-bar {
            display: flex;
            border-bottom: 2px solid var(--border);
            margin-bottom: 25px;
            background: white;
            border-radius: 8px;
            overflow: hidden;
        }
        .tab-btn {
            flex: 1;
            text-align: center;
            padding: 15px;
            text-decoration: none;
            color: var(--text-muted);
            font-weight: 600;
            font-size: 1.05rem;
            transition: all 0.2s;
        }
        .tab-btn:hover {
            background: #fafafa;
            color: var(--text-main);
        }
        .tab-btn.active {
            color: var(--primary);
            border-bottom: 3px solid var(--primary);
            background: #fff5f6;
        }

        .video-card { 
            background: var(--card-bg);
            border: 1px solid var(--border); 
            margin-bottom: 24px; 
            border-radius: 12px; 
            box-shadow: 0 2px 8px rgba(0,0,0,0.04);
            overflow: hidden;
        }
        .card-header {
            padding: 16px;
            display: flex;
            align-items: center;
            gap: 12px;
            border-bottom: 1px solid #f0f2f5;
        }
        .header-info {
            flex: 1;
        }
        .card-title {
            margin: 0 0 4px 0;
            font-size: 1.15rem;
            font-weight: 700;
        }
        .card-meta {
            font-size: 0.85rem;
            color: var(--text-muted);
        }
        video { 
            width: 100%; 
            display: block;
            background: #000; 
        }

        .form-box {
            background: var(--card-bg);
            border: 1px solid var(--border);
            padding: 32px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.03);
        }
        .form-box h3 { margin-top: 0; margin-bottom: 24px; font-size: 1.5rem; text-align: center;}
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; font-weight: 600; margin-bottom: 8px; font-size: 0.9rem; }
        
        input[type="text"], input[type="password"], input[type="file"] { 
            width: 100%; 
            padding: 10px 12px; 
            border: 1px solid var(--border); 
            border-radius: 6px; 
            box-sizing: border-box;
            font-size: 0.95rem;
            background: #fafafa;
        }
        
        input[type="submit"] { 
            background: var(--primary); 
            color: white; 
            border: none; 
            padding: 12px 24px; 
            cursor: pointer; 
            border-radius: 6px; 
            font-weight: 600; 
            font-size: 1rem;
            width: 100%;
            transition: background 0.2s;
            margin-top: 10px;
        }
        input[type="submit"]:hover { background: var(--primary-hover); }
        
        .empty-state {
            text-align: center;
            padding: 50px 20px;
            color: var(--text-muted);
        }
        .gate-container {
            text-align: center;
            padding: 40px 20px;
        }
    </style>
</head>
<body>

    <nav class="navbar">
        <div class="nav-container">
            <a href="{{ url_for('home') }}" class="logo">🎵 VibeShare</a>
            <div class="nav-links">
                {% if session.get('username') %}
                    <a href="{{ url_for('settings') }}" class="user-badge-link" title="Click to edit profile settings">
                        {% if current_user and current_user['avatar'] %}
                            <img src="/static/uploads/{{ current_user['avatar'] }}" class="avatar-img" alt="avatar">
                        {% else %}
                            <div class="avatar-placeholder">{{ session['username'][0].upper() }}</div>
                        {% endif %}
                        <span style="font-size: 0.95rem; font-weight: 600;">{{ current_user['fullname'] or session['username'] }}</span>
                    </a>
                    <span style="color: var(--border)">|</span>
                    <a href="{{ url_for('logout') }}" style="font-size: 0.9rem; color: var(--primary)">Logout</a>
                {% else %}
                    <a href="{{ url_for('login') }}" style="color: var(--text-main); font-weight:600;">Sign In</a>
                    <a href="{{ url_for('register') }}" style="background: var(--primary); color: white; padding: 6px 14px; border-radius: 20px;">Sign Up</a>
                {% endif %}
            </div>
        </div>
    </nav>

    <div class="main-content">
        {% with messages = get_flashed_messages() %}
          {% if messages %}
            {% for message in messages %}
              <div class="flash">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}

        {% if page == 'settings' %}
            <div class="form-box">
                <h3 style="text-align: left; border-bottom: 2px solid var(--primary); padding-bottom: 8px;">⚙️ Account Profile Settings</h3>
                <p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 25px;">You can modify your unique handle, display name or swap out your current profile picture avatar below.</p>
                
                <form method="post" action="{{ url_for('settings') }}" enctype="multipart/form-data">
                    <div class="form-group">
                        <label>Username Handle (Must remain unique) *</label>
                        <input type="text" name="username" value="{{ current_user['username'] }}" required>
                    </div>
                    <div class="form-group">
                        <label>Display Name (Full Name)</label>
                        <input type="text" name="fullname" value="{{ current_user['fullname'] or '' }}" placeholder="Enter full name display title...">
                    </div>
                    
                    <div class="form-group" style="margin-top: 25px; background: #fafafa; padding: 15px; border: 1px dashed var(--border); border-radius: 8px;">
                        <label style="margin-bottom: 12px;">Profile Avatar Graphic</label>
                        <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 12px;">
                            {% if current_user['avatar'] %}
                                <img src="/static/uploads/{{ current_user['avatar'] }}" style="width:55px; height:55px; border-radius:50%; object-fit:cover; border:2px solid var(--primary);">
                            {% else %}
                                <div style="width:55px; height:55px; border-radius:50%; background:#24292f; color:white; display:flex; align-items:center; justify-content:center; font-weight:bold; font-size:1.2rem;">{{ current_user['username'][0].upper() }}</div>
                            {% endif %}
                            <span style="font-size:0.85rem; color:var(--text-muted)">Current profile image active. Choose a new stream below to overwrite.</span>
                        </div>
                        <input type="file" name="avatar" accept="image/*">
                    </div>
                    
                    <div style="display:flex; gap:15px; margin-top:25px;">
                        <a href="{{ url_for('home') }}" style="flex:1; text-align:center; background:#eee; color:#333; text-decoration:none; padding:12px; border-radius:6px; font-weight:600; font-size:0.95rem;">Cancel & Return</a>
                        <input type="submit" value="Save Account Updates" style="flex:2; margin-top:0;">
                    </div>
                </form>
            </div>

        {% elif not session.get('username') %}
            {% if page == 'register' %}
                <div class="form-box">
                    <h3>📝 Create Account & Profile</h3>
                    <form method="post" action="{{ url_for('register') }}" enctype="multipart/form-data">
                        <div class="form-group">
                            <label>Username (Unique Handle ID) *</label>
                            <input type="text" name="username" required placeholder="Pick a unique handle...">
                        </div>
                        <div class="form-group">
                            <label>Password *</label>
                            <input type="password" name="password" required placeholder="Create custom security keys...">
                        </div>
                        <hr style="border:0; border-top:1px solid var(--border); margin:20px 0;">
                        <div class="form-group">
                            <label>Your Display Name (Full Name)</label>
                            <input type="text" name="fullname" placeholder="e.g. Richard Henderson">
                        </div>
                        <div class="form-group">
                            <label>Upload Profile Picture (Avatar Image)</label>
                            <input type="file" name="avatar" accept="image/*">
                        </div>
                        <input type="submit" value="Complete Registration">
                    </form>
                    <p style="text-align: center; margin-top: 20px; font-size: 0.9rem; color: var(--text-muted);">
                        Already have a profile? <a href="{{ url_for('login') }}" style="color:var(--primary); font-weight: 600;">Login here</a>
                    </p>
                </div>
            {% else %}
                <div class="form-box gate-container">
                    <h2 style="margin-top: 0;">🔒 Authentication Portal</h2>
                    <p style="color: var(--text-muted); margin-bottom: 25px;">Sign in with your verified credentials to access your studio and streaming feeds.</p>
                    <form method="post" action="{{ url_for('login') }}">
                        <div class="form-group" style="text-align: left;">
                            <label>Username</label>
                            <input type="text" name="username" required placeholder="Enter username handle">
                        </div>
                        <div class="form-group" style="text-align: left;">
                            <label>Password</label>
                            <input type="password" name="password" required placeholder="Enter matching security password">
                        </div>
                        <input type="submit" value="Sign In to Platform">
                    </form>
                    <p style="margin-top: 20px; font-size: 0.9rem; color: var(--text-muted);">
                        New here? <a href="{{ url_for('register') }}" style="color:var(--primary); font-weight:600;">Create an account now</a>
                    </p>
                </div>
            {% endif %}

        {% else %}
            
            <div class="tabs-bar">
                <a href="{{ url_for('home', tab='global') }}" class="tab-btn {% if current_tab == 'global' %}active{% endif %}">🌐 Global Feed</a>
                <a href="{{ url_for('home', tab='my_studio') }}" class="tab-btn {% if current_tab == 'my_studio' %}active{% endif %}">👤 My Studio</a>
            </div>

            {% if current_tab == 'global' %}
                {% if not videos %}
                    <div class="empty-state">
                        <h3>🎬 The Global Feed is Empty</h3>
                        <p>Switch over to the "My Studio" tab to upload your very first video file!</p>
                    </div>
                {% endif %}
                {% for video in videos %}
                    <div class="video-card">
                        <div class="card-header">
                            {% if video['avatar'] %}
                               <img src="/static/uploads/{{ video['avatar'] }}" class="avatar-img" alt="avatar">
                            {% else %}
                                <div class="avatar-placeholder">{{ video['username'][0].upper() }}</div>
                            {% endif %}
                            <div class="header-info">
                                <h4 class="card-title">{{ video['title'] }}</h4>
                                <div class="card-meta">By <b>{{ video['fullname'] or video['username'] }}</b> (@{{ video['username'] }})</div>
                            </div>
                        </div>
                        <video src="/static/uploads/{{ video['filename'] }}" controls></video>
                    </div>
                {% endfor %}

            {% elif current_tab == 'my_studio' %}
                <div style="background: white; border: 1px solid var(--border); padding: 20px; border-radius: 12px; margin-bottom: 25px;">
                    <h4 style="margin-top:0; margin-bottom:15px; font-size:1.1rem;">📤 Upload New Video to Your Studio</h4>
                    <form action="{{ url_for('upload_video') }}" method="post" enctype="multipart/form-data">
                        <div class="form-group">
                            <input type="text" name="title" required placeholder="Give your studio clip a title...">
                        </div>
                        <div class="form-group" style="margin-bottom: 10px;">
                            <input type="file" name="file" accept="video/*" required>
                        </div>
                        <input type="submit" value="Publish to My Account">
                    </form>
                </div>

                <h3 style="font-size: 1.2rem; border-left: 4px solid var(--primary); padding-left: 10px; margin-bottom: 15px;">Your Published Collections</h3>
                {% if not videos %}
                    <div class="empty-state" style="padding:20px;">
                        <p style="color: var(--text-muted);">You haven't uploaded any videos yet. Use the form above to start your creator journey!</p>
                    </div>
                {% endif %}
                {% for video in videos %}
                    <div class="video-card">
                        <div class="card-header" style="background: #fafafa;">
                            <div class="header-info">
                                <h4 class="card-title">🎬 {{ video['title'] }}</h4>
                                <div class="card-meta">Status: <span style="color: green; font-weight: 600;">Live on Feed</span></div>
                            </div>
                        </div>
                        <video src="/static/uploads/{{ video['filename'] }}" controls></video>
                    </div>
                {% endfor %}
            {% endif %}

        {% endif %}
    </div>

</body>
</html>
"""

# ==========================================
# 5. Advanced Route Operations Control
# ==========================================
@app.route('/')
def home():
    current_tab = request.args.get('tab', 'global')
    current_user = None
    
    if 'username' in session:
        conn = get_db_connection()
        current_user = conn.execute('SELECT * FROM users WHERE username = ?', (session['username'],)).fetchone()
        
        if current_tab == 'my_studio':
            videos = conn.execute('SELECT * FROM videos WHERE username = ? ORDER BY id DESC', (session['username'],)).fetchall()
        else:
            videos = conn.execute('''
                SELECT videos.*, users.fullname, users.avatar 
                FROM videos 
                LEFT JOIN users ON videos.username = users.username 
                ORDER BY videos.id DESC
            ''').fetchall()
        conn.close()
    else:
        videos = []

    return render_template_string(HTML_TEMPLATE, page='home', videos=videos, current_tab=current_tab, current_user=current_user)

# 【核心新增】：用户点击头像后的专属“配置更新控制中心”
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'username' not in session:
        flash("🔒 Security Lockout: Session expired. Please log in!")
        return redirect(url_for('login'))
        
    old_username = session['username']
    conn = get_db_connection()
    current_user = conn.execute('SELECT * FROM users WHERE username = ?', (old_username,)).fetchone()
    
    if request.method == 'POST':
        new_username = request.form['username'].strip()
        fullname = request.form['fullname'].strip()
        avatar_file = request.files.get('avatar')
        
        if not new_username:
            flash("⚠️ Edit rejected: Username handle cannot be empty!")
            conn.close()
            return redirect(url_for('settings'))
            
        # 1. 查重逻辑：如果改了名字，查查新名字是不是被别人抢注了
        if new_username != old_username:
            collision_check = conn.execute('SELECT 1 FROM users WHERE username = ?', (new_username,)).fetchone()
            if collision_check:
                flash(f"❌ Operation aborted: The username '{new_username}' is already taken. Try another name!")
                conn.close()
                return redirect(url_for('settings'))
                
        # 2. 头像更新处理
        avatar_filename = current_user['avatar'] # 默认用老
        avatar_filename = current_user['avatar'] # 默认用老头像名字
        if avatar_file and avatar_file.filename != '':
            sec_filename = secure_filename(avatar_file.filename)
            avatar_filename = f"avatar_{new_username}_{sec_filename}"
            avatar_file.save(os.path.join(app.config['UPLOAD_FOLDER'], avatar_filename))
            
        # 3. 级联数据更新：同步刷新用户表，同时同步刷新视频表中的拥有者账号
        conn.execute('''
            UPDATE users 
            SET username = ?, fullname = ?, avatar = ? 
            WHERE username = ?
        ''', (new_username, fullname if fullname else None, avatar_filename, old_username))
        
        conn.execute('UPDATE videos SET username = ? WHERE username = ?', (new_username, old_username))
        conn.commit()
        conn.close()
        
        # 4. 刷新当前浏览器的登录认证 Cookie 凭证
        session['username'] = new_username
        flash("✨ Profile setting upgrades successfully synchronized!")
        return redirect(url_for('home'))
        
    conn.close()
    return render_template_string(HTML_TEMPLATE, page='settings', current_user=current_user)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        fullname = request.form['fullname'].strip()
        avatar_file = request.files.get('avatar')
        
        if not username or not password:
            flash("⚠️ Registration failed: Username and password are required fields.")
            return redirect(url_for('register'))
            
        conn = get_db_connection()
        existing_user = conn.execute('SELECT 1 FROM users WHERE username = ?', (username,)).fetchone()
        
        if existing_user:
            conn.close()
            flash(f"❌ Account creation rejected: The username '{username}' already exists. Try another identity!")
            return redirect(url_for('register'))
            
        hashed_password = generate_password_hash(password)
        
        avatar_filename = None
        if avatar_file and avatar_file.filename != '':
            sec_filename = secure_filename(avatar_file.filename)
            avatar_filename = f"avatar_{username}_{sec_filename}"
            avatar_file.save(os.path.join(app.config['UPLOAD_FOLDER'], avatar_filename))
            
        try:
            conn.execute('''
                INSERT INTO users (username, password, fullname, avatar) 
                VALUES (?, ?, ?, ?)
            ''', (username, hashed_password, fullname if fullname else None, avatar_filename))
            conn.commit()
            flash("🎉 Profile created successfully! Welcome to the hub. Log in to start.")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("❌ System collision error: This handle is not available.")
        finally:
            conn.close()
            
    return render_template_string(HTML_TEMPLATE, page='register')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if not user:
            flash("❌ Login failed: This username does not exist. Create an account first!")
        elif not check_password_hash(user['password'], password):
            flash("❌ Login failed: Incorrect password mismatch. Try again!")
        else:
            session['username'] = user['username']
            flash("🚀 Access granted! Welcome back.")
            return redirect(url_for('home'))
            
    return render_template_string(HTML_TEMPLATE, page='login')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash("Secure checkout completed. Session terminated.")
    return redirect(url_for('home'))

@app.route('/upload', methods=['POST'])
def upload_video():
    if 'username' not in session:
        flash("Access Denied. Login authentication lost!")
        return redirect(url_for('login'))
        
    title = request.form.get('title', '').strip()
    file = request.files.get('file')
    
    if not title or not file or file.filename == '':
        flash("Video title captions and file stream are required!")
        return redirect(url_for('home', tab='my_studio'))
        
    filename = secure_filename(file.filename)
    unique_filename = f"{session['username']}_{filename}"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
    
    conn = get_db_connection()
    conn.execute('INSERT INTO videos (username, filename, title) VALUES (?, ?, ?)',
                 (session['username'], unique_filename, title))
    conn.commit()
    conn.close()
    
    flash("🎉 Masterpiece loaded successfully into your studio!")
    return redirect(url_for('home', tab='my_studio'))

init_db()

# 这一步极其重要：优先读取 Render 分配的云端端口，如果读不到，则默认使用本地的 5001 端口
cloud_port = int(os.environ.get("PORT", 5001))

print("\n" + "="*50)
print(f"VibeShare Server Booting Safely on Port {cloud_port}!")
print("==================================================")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=cloud_port, debug=True)