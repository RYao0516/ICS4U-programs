import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, session
from supabase import create_client, Client

app = Flask(__name__)

# --- 直接硬编码密钥 (仅为确保演示成功) ---
# 注意：演示后请务必通过环境变量管理，不要将此文件直接提交到公开的 GitHub 仓库！
SUPABASE_URL = "https://yfycdaoxlevyiuqaonbs.supabase.co"
SUPABASE_KEY = "sb_publishable_T_IGIGMN2-Ll4p0yOumE4Q_Le91Q1Fx"
app.secret_key = "vibeshare-secret-2026"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
BUCKET_NAME = "video"

# --- 兜底路由 ---
@app.route('/favicon.ico')
def favicon(): return '', 204

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # 检查用户名是否已存在
        check = supabase.table("users").select("username").eq("username", username).execute()
        if check.data:
            return "Username already exists!", 400
        
        # 存入数据库
        res = supabase.table("users").insert({
            "username": username,
            "password": password
        }).execute()
        
        return redirect(url_for('login'))
        
    return render_template('register.html')

# --- 核心路由 ---
@app.route('/')
def index():
    return redirect(url_for('home')) if 'username' in session else redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        res = supabase.table("users").select("*").eq("username", username).execute()
        if res.data and res.data[0].get('password') == password:
            session['username'] = username
            return redirect(url_for('home'))
        return "Invalid login", 401
    return render_template('login.html')

@app.route('/home')
def home():
    if 'username' not in session: return redirect(url_for('login'))
    tab = request.args.get('tab', 'explore')
    u_res = supabase.table("users").select("*").eq("username", session['username']).execute()
    user_info = u_res.data[0] if u_res.data else {"username": session['username'], "avatar_url": None}
    
    if tab == 'my_studio':
        res = supabase.table("videos").select("*").eq("username", session['username']).order("created_at", desc=True).execute()
    else:
        res = supabase.table("videos").select("*").order("created_at", desc=True).execute()
    return render_template('home.html', user_info=user_info, videos=res.data or [], current_tab=tab)

@app.route('/upload', methods=['POST'])
def upload_video():
    if 'username' not in session: return redirect(url_for('login'))
    title, file = request.form.get('title'), request.files.get('file')
    if file and title:
        fname = f"{uuid.uuid4()}{os.path.splitext(file.filename)[1]}"
        supabase.storage.from_(BUCKET_NAME).upload(fname, file.read(), {"content-type": file.content_type})
        url = supabase.storage.from_(BUCKET_NAME).get_public_url(fname)
        supabase.table("videos").insert({"username": session['username'], "title": title, "video_url": url, "filename": fname}).execute()
    return redirect(url_for('home', tab='my_studio'))

@app.route('/profile', methods=['GET', 'POST'])
def edit_profile():
    if 'username' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        file = request.files.get('avatar')
        if file and file.filename:
            fname = f"avatar-{session['username']}-{uuid.uuid4()}"
            supabase.storage.from_(BUCKET_NAME).upload(fname, file.read(), {"content-type": file.content_type})
            url = supabase.storage.from_(BUCKET_NAME).get_public_url(fname)
            supabase.table("users").update({"avatar_url": url}).eq("username", session['username']).execute()
        return redirect(url_for('home'))
    res = supabase.table("users").select("*").eq("username", session['username']).execute()
    return render_template('profile.html', user_info=res.data[0] if res.data else {})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)