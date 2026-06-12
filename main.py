import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client

app = Flask(__name__)

# ========================================================
# 1. 安全与密钥配置
# ========================================================
try:
    import toml
    secrets = toml.load("secrets.toml")
    FLASK_KEY = secrets["flask"]["secret_key"]
except Exception:
    FLASK_KEY = os.environ.get("FLASK_SECRET_KEY", "vibeshare-default-fallback-key-2026")

app.secret_key = FLASK_KEY

# ========================================================
# 2. Supabase 云端连接
# ========================================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
BUCKET_NAME = "video"  # 统一设置存储桶名称

# ========================================================
# 3. 核心路由逻辑
# ========================================================

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        try:
            response = supabase.table("users").select("*").eq("username", username).execute()
            user_data = response.data
            if user_data and user_data[0]['password'] == password:
                session['username'] = username
                return redirect(url_for('home'))
            else:
                flash("❌ Invalid username or password.")
        except Exception as e:
            flash(f"⚠️ Login Error: {str(e)}")
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        try:
            existing = supabase.table("users").select("*").eq("username", username).execute()
            if existing.data:
                flash("🚫 Username already exists!")
                return render_template('register.html')
            supabase.table("users").insert({"username": username, "password": password, "avatar_url": None}).execute()
            flash("🎉 Registration successful!")
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"⚠️ Registration Error: {str(e)}")
    return render_template('register.html')


@app.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    current_tab = request.args.get('tab', 'explore')
    try:
        user_res = supabase.table("users").select("*").eq("username", session['username']).execute()
        current_user_info = user_res.data[0] if user_res.data else {"username": session['username'], "avatar_url": None}
        
        if current_tab == 'my_studio':
            response = supabase.table("videos").select("*").eq("username", session['username']).execute()
        else:
            response = supabase.table("videos").select("*").order("created_at", descending=True).execute()
        videos = response.data if response.data else []
    except Exception:
        videos = []
        current_user_info = {"username": session['username'], "avatar_url": None}
    return render_template('home.html', username=session['username'], user_info=current_user_info, videos=videos, current_tab=current_tab)


@app.route('/profile', methods=['GET', 'POST'])
def edit_profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    old_username = session['username']
    if request.method == 'POST':
        new_username = request.form.get('username', '').strip()
        avatar_file = request.files.get('avatar')
        try:
            update_data = {}
            if avatar_file and avatar_file.filename != '':
                ext = os.path.splitext(avatar_file.filename)[1]
                unique_avatar_name = f"avatar-{uuid.uuid4()}{ext}"
                supabase.storage.from_(BUCKET_NAME).upload(path=unique_avatar_name, file=avatar_file.read(), file_options={"content-type": avatar_file.content_type})
                update_data["avatar_url"] = supabase.storage.from_(BUCKET_NAME).get_public_url(unique_avatar_name)
            
            if new_username and new_username != old_username:
                if supabase.table("users").select("*").eq("username", new_username).execute().data:
                    flash("🚫 Username taken!")
                    return redirect(url_for('edit_profile'))
                update_data["username"] = new_username
            
            if update_data:
                supabase.table("users").update(update_data).eq("username", old_username).execute()
                if "username" in update_data:
                    supabase.table("videos").update({"username": new_username}).eq("username", old_username).execute()
                    session['username'] = new_username
                flash("✨ Profile updated!")
            return redirect(url_for('home'))
        except Exception as e:
            flash(f"⚠️ Error: {str(e)}")
            return redirect(url_for('edit_profile'))
    
    res = supabase.table("users").select("*").eq("username", old_username).execute()
    return render_template('profile.html', user_info=res.data[0] if res.data else {})


@app.route('/upload', methods=['POST'])
def upload_video():
    if 'username' not in session:
        return redirect(url_for('login'))
    title, file = request.form.get('title'), request.files.get('file')
    if file and title:
        try:
            unique_filename = f"{uuid.uuid4()}{os.path.splitext(file.filename)[1]}"
            supabase.storage.from_(BUCKET_NAME).upload(path=unique_filename, file=file.read(), file_options={"content-type": file.content_type})
            supabase.table("videos").insert({"username": session['username'], "filename": unique_filename, "title": title, "video_url": supabase.storage.from_(BUCKET_NAME).get_public_url(unique_filename)}).execute()
            flash("🚀 Upload success!")
        except Exception as e:
            flash(f"⚠️ Upload Error: {str(e)}")
    return redirect(url_for('home', tab='my_studio'))


@app.route('/delete/<int:video_id>', methods=['POST'])
def delete_video(video_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    try:
        video = supabase.table("videos").select("*").eq("id", video_id).execute().data[0]
        if video['username'] == session['username']:
            supabase.storage.from_(BUCKET_NAME).remove([video['filename']])
            supabase.table("videos").delete().eq("id", video_id).execute()
            flash("🗑️ Deleted successfully!")
    except Exception as e:
        flash(f"⚠️ Delete Error: {str(e)}")
    return redirect(url_for('home', tab='my_studio'))


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5001)), debug=True)