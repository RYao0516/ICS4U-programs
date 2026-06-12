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

if not SUPABASE_URL or not SUPABASE_KEY:
    print("⚠️ Warning: Missing Supabase Environment Variables!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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
                flash("👋 Welcome back to VibeShare!")
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
        
        if username and password:
            try:
                existing = supabase.table("users").select("*").eq("username", username).execute()
                if existing.data:
                    flash("🚫 Username already exists!")
                    return render_template('register.html')
                
                # 注册时，默认 avatar_url 为空
                supabase.table("users").insert({
                    "username": username,
                    "password": password,
                    "avatar_url": None
                }).execute()
                
                flash("🎉 Registration successful! Please log in.")
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
        # 获取当前登录用户完整信息（包含头像）
        user_res = supabase.table("users").select("*").eq("username", session['username']).execute()
        current_user_info = user_res.data[0] if user_res.data else {"username": session['username'], "avatar_url": None}
        
        if current_tab == 'my_studio':
            response = supabase.table("videos").select("*").eq("username", session['username']).execute()
        else:
            response = supabase.table("videos").select("*").order("created_at", descending=True).execute()
            
        videos = response.data if response.data else []
    except Exception as e:
        print(f"Error: {e}")
        videos = []
        current_user_info = {"username": session['username'], "avatar_url": None}
        
    return render_template('home.html', username=session['username'], user_info=current_user_info, videos=videos, current_tab=current_tab)


@app.route('/profile', methods=['GET', 'POST'])
def edit_profile():
    """【全新高分功能】编辑资料：修改用户名并上传更换个人头像"""
    if 'username' not in session:
        return redirect(url_for('login'))
        
    old_username = session['username']
    
    if request.method == 'POST':
        new_username = request.form.get('username', '').strip()
        avatar_file = request.files.get('avatar')
        
        try:
            # 1. 优先处理头像上传（如果用户选了新图片）
            updated_avatar_url = None
            if avatar_file and avatar_file.filename != '':
                ext = os.path.splitext(avatar_file.filename)[1]
                unique_avatar_name = f"avatar-{uuid.uuid4()}{ext}"
                file_data = avatar_file.read()
                
                # 上传到现有的 videos 存储桶（或者你可以单独建一个 avatars 桶，用 videos 桶最省事）
                supabase.storage.from_("videos").upload(
                    path=unique_avatar_name,
                    file=file_data,
                    file_options={"content-type": avatar_file.content_type}
                )
                updated_avatar_url = supabase.storage.from_("videos").get_public_url(unique_avatar_name)

            # 2. 更新数据库逻辑
            update_data = {}
            if updated_avatar_url:
                update_data["avatar_url"] = updated_avatar_url
                
            if new_username and new_username != old_username:
                # 检查新名字是否被别人占用了
                existing = supabase.table("users").select("*").eq("username", new_username).execute()
                if existing.data:
                    flash("🚫 Username already taken!")
                    return redirect(url_for('edit_profile'))
                update_data["username"] = new_username

            if update_data:
                # 更新用户表
                supabase.table("users").update(update_data).eq("username", old_username).execute()
                
                # 【联动更新】：如果改了名字，要把该用户之前上传的所有视频的老名字同步更新！
                if "username" in update_data:
                    supabase.table("videos").update({"username": new_username}).eq("username", old_username).execute()
                    session['username'] = new_username  # 更新会话

                flash("✨ Profile updated successfully!")
            return redirect(url_for('home'))
            
        except Exception as e:
            flash(f"⚠️ Profile Update Error: {str(e)}")
            return redirect(url_for('edit_profile'))
            
    # GET 请求：获取当前用户数据渲染编辑页面
    try:
        res = supabase.table("users").select("*").eq("username", old_username).execute()
        user_info = res.data[0] if res.data else {}
    except Exception:
        user_info = {}
    return render_template('profile.html', user_info=user_info)


@app.route('/upload', methods=['POST'])
def upload_video():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    title = request.form.get('title')
    file = request.files.get('file')
    
    if file and title:
        try:
            ext = os.path.splitext(file.filename)[1]
            unique_filename = f"{uuid.uuid4()}{ext}"
            file_data = file.read()
            supabase.storage.from_("videos").upload(
                path=unique_filename,
                file=file_data,
                file_options={"content-type": file.content_type}
            )
            video_public_url = supabase.storage.from_("videos").get_public_url(unique_filename)
            
            supabase.table("videos").insert({
                "username": session['username'],
                "filename": unique_filename,
                "title": title,
                "video_url": video_public_url
            }).execute()
            
            flash("🚀 Masterpiece loaded successfully into your cloud studio!")
            return redirect(url_for('home', tab='my_studio'))
        except Exception as e:
            flash(f"⚠️ Upload Interrupted: {str(e)}")
    return redirect(url_for('home'))


@app.route('/delete/<int:video_id>', methods=['POST'])
def delete_video(video_id):
    if 'username' not in session:
        return redirect(url_for('login'))
    try:
        response = supabase.table("videos").select("*").eq("id", video_id).execute()
        video_data = response.data
        if not video_data:
            flash("❌ Video not found.")
            return redirect(url_for('home', tab='my_studio'))
        video = video_data[0]
        if video['username'] != session['username']:
            flash("🚫 Security Alert: Permission denied.")
            return redirect(url_for('home', tab='my_studio'))
            
        supabase.storage.from_("videos").remove([video['filename']])
        supabase.table("videos").delete().eq("id", video_id).execute()
        flash("🗑️ Video deleted successfully!")
    except Exception as e:
        flash(f"⚠️ Delete Error: {str(e)}")
    return redirect(url_for('home', tab='my_studio'))


@app.route('/logout')
def logout():
    session.pop('username', None)
    flash("🔒 Logged out successfully.")
    return redirect(url_for('login'))


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=True)