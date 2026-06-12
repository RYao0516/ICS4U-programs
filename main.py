import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client

app = Flask(__name__)
app.secret_key = "dev-key-2026"

SUPABASE_URL = "https://yfycdaoxlevyiuqaonbs.supabase.co"
SUPABASE_KEY = "sb_publishable_T_IGIGMN2-Ll4p0yOumE4Q_Le91Q1Fx"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
BUCKET_NAME = "video"

@app.route('/upload', methods=['POST'])
def upload_video():
    if 'username' not in session: return redirect(url_for('login'))
    
    # 1. 获取当前用户头像，方便后续存入视频表
    user_res = supabase.table("users").select("avatar_url").eq("username", session['username']).execute()
    current_avatar = user_res.data[0].get('avatar_url') if user_res.data else None
    
    title = request.form.get('title')
    file = request.files.get('file')
    
    if file and title:
        try:
            fname = f"{uuid.uuid4()}{os.path.splitext(file.filename)[1]}"
            supabase.storage.from_(BUCKET_NAME).upload(fname, file.read(), {"content-type": file.content_type})
            url = supabase.storage.from_(BUCKET_NAME).get_public_url(fname)
            
            # 存入视频，包含头像 URL
            supabase.table("videos").insert({
                "username": session['username'],
                "title": title,
                "video_url": url,
                "filename": fname,
                "avatar_url": current_avatar
            }).execute()
        except Exception as e:
            print(f"上传错误: {e}")
    return redirect(url_for('home', tab='my_studio'))