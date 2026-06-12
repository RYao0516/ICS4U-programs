import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client

app = Flask(__name__)
# 生产环境建议在 Render 环境变量中设置 FLASK_SECRET_KEY
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-key-2026")

# 强制硬编码配置，确保不会出现 "url is required" 报错
SUPABASE_URL = "https://yfycdaoxlevyiuqaonbs.supabase.co"
SUPABASE_KEY = "sb_publishable_T_IGIGMN2-Ll4p0yOumE4Q_Le91Q1Fx"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
BUCKET_NAME = "video" # 确保 Supabase 后台存储桶名称为 video

@app.route('/')
def index():
    return redirect(url_for('home')) if 'username' in session else redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        res = supabase.table("users").select("*").eq("username", username).execute()
        if res.data and res.data[0]['password'] == password:
            session['username'] = username
            return redirect(url_for('home'))
        flash("❌ 账号或密码错误")
    return render_template('login.html')

@app.route('/home')
def home():
    if 'username' not in session: return redirect(url_for('login'))
    tab = request.args.get('tab', 'explore')
    
    # 获取用户信息
    u_res = supabase.table("users").select("*").eq("username", session['username']).execute()
    user_info = u_res.data[0] if u_res.data else {"username": session['username'], "avatar_url": None}
    
    # 核心查询逻辑：根据 tab 过滤
    if tab == 'my_studio':
        v_res = supabase.table("videos").select("*").eq("username", session['username']).order("created_at", desc=True).execute()
    else:
        v_res = supabase.table("videos").select("*").order("created_at", desc=True).execute()
        
    return render_template('home.html', username=session['username'], user_info=user_info, videos=v_res.data or [], current_tab=tab)

@app.route('/upload', methods=['POST'])
def upload_video():
    if 'username' not in session: return redirect(url_for('login'))
    u_res = supabase.table("users").select("avatar_url").eq("username", session['username']).execute()
    avatar = u_res.data[0].get('avatar_url') if u_res.data else None
    
    title = request.form.get('title')
    file = request.files.get('file')
    
    if file and title:
        fname = f"{uuid.uuid4()}{os.path.splitext(file.filename)[1]}"
        supabase.storage.from_(BUCKET_NAME).upload(fname, file.read(), {"content-type": file.content_type})
        url = supabase.storage.from_(BUCKET_NAME).get_public_url(fname)
        supabase.table("videos").insert({"username": session['username'], "title": title, "video_url": url, "filename": fname, "avatar_url": avatar}).execute()
    return redirect(url_for('home', tab='my_studio'))

@app.route('/delete/<int:video_id>', methods=['POST'])
def delete_video(video_id):
    v = supabase.table("videos").select("*").eq("id", video_id).execute().data[0]
    if v['username'] == session['username']:
        supabase.storage.from_(BUCKET_NAME).remove([v['filename']])
        supabase.table("videos").delete().eq("id", video_id).execute()
    return redirect(url_for('home', tab='my_studio'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)