import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client

app = Flask(__name__)

# ========================================================
# 1. 安全与密钥配置 ( Flask Session 密钥 )
# ========================================================
try:
    # 尝试读取你原本的 local/secrets 配置
    import toml
    secrets = toml.load("secrets.toml")
    FLASK_KEY = secrets["flask"]["secret_key"]
except Exception:
    # 如果生产环境没有 secrets.toml，自适应使用预设密钥
    FLASK_KEY = os.environ.get("FLASK_SECRET_KEY", "vibeshare-default-fallback-key-2026")

app.secret_key = FLASK_KEY

# ========================================================
# 2. Supabase 云端数据库与存储引擎连接
# ========================================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("⚠️ Warning: Missing Supabase Environment Variables!")

# 初始化云端客户端
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ========================================================
# 3. 核心路由与社交平台逻辑
# ========================================================

@app.route('/')
def index():
    """根路径重定向"""
    if 'username' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录路由"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        try:
            # 从 Supabase 云端数据库查询该用户记录
            response = supabase.table("users").select("*").eq("username", username).execute()
            user_data = response.data
            
            # 严格验证密码
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
    """用户注册路由"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username and password:
            try:
                # 检查用户名是否已被注册
                existing = supabase.table("users").select("*").eq("username", username).execute()
                if existing.data:
                    flash("🚫 Username already exists. Try another one!")
                    return render_template('register.html')
                
                # 往 Supabase 云数据库写入新用户
                supabase.table("users").insert({
                    "username": username,
                    "password": password
                }).execute()
                
                flash("🎉 Registration successful! Please log in.")
                return redirect(url_for('login'))
            except Exception as e:
                flash(f"⚠️ Registration Error: {str(e)}")
        else:
            flash("❌ Please fill in all fields.")
            
    return render_template('register.html')


@app.route('/home')
def home():
    """动态主页：展示所有公网视频及个人工作室"""
    if 'username' not in session:
        return redirect(url_for('login'))
        
    current_tab = request.args.get('tab', 'explore')
    
    try:
        if current_tab == 'my_studio':
            # 只获取当前登录用户的视频
            response = supabase.table("videos").select("*").eq("username", session['username']).execute()
        else:
            # 探索大厅：拉取云端的所有公开视频
            response = supabase.table("videos").select("*").order("created_at", descending=True).execute()
            
        videos = response.data if response.data else []
    except Exception as e:
        print(f"Error fetching videos: {e}")
        videos = []
        
    return render_template('home.html', username=session['username'], videos=videos, current_tab=current_tab)


@app.route('/upload', methods=['POST'])
def upload_video():
    """云端一步到位存储：将视频射入云硬盘，链接写入云数据库"""
    if 'username' not in session:
        return redirect(url_for('login'))
        
    title = request.form.get('title')
    file = request.files.get('file')
    
    if file and title:
        try:
            # 1. 采用 UUID 为文件加密重命名，防止国际公网重名覆盖
            ext = os.path.splitext(file.filename)[1]
            unique_filename = f"{uuid.uuid4()}{ext}"
            
            # 2. 读取二进制流，发射到 Supabase 视频存储桶里
            file_data = file.read()
            supabase.storage.from_("videos").upload(
                path=unique_filename,
                file=file_data,
                file_options={"content-type": file.content_type}
            )
            
            # 3. 瞬时捕捉该视频在国际公网上的永久播放网络链接
            video_public_url = supabase.storage.from_("videos").get_public_url(unique_filename)
            
            # 4. 把用户标识、标题与视频【永久公网链接】捆绑写入云端数据库
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
            
    flash("❌ Missing video file or title.")
    return redirect(url_for('home'))


@app.route('/logout')
def logout():
    """登出路由"""
    session.pop('username', None)
    flash("🔒 Logged out successfully. See you next time!")
    return redirect(url_for('login'))

# ========================================================
# 4. 自适应多端口启动引擎
# ========================================================
if __name__ == '__main__':
    # 动态捕获 Render 分配的端口，本地默认 5001
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=True)