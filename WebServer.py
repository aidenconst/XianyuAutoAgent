import os
import base64
import secrets
import re
from loguru import logger
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, make_response, session
from dotenv import load_dotenv
# import logging
from waitress import serve

app = Flask(__name__)
app.config['ENV_FILE'] = os.path.join(os.path.dirname(__file__), '.env')
app.config['ADMIN_USERNAME'] = os.getenv('ADMIN_USERNAME', 'aiden')
app.config['ADMIN_PASSWORD'] = os.getenv('ADMIN_PASSWORD', 'aiden')
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET', secrets.token_hex(32))

# 设置日志
# logging.basicConfig(level=logging.DEBUG)
# logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv(app.config['ENV_FILE'])

def get_env_values():
    """从.env文件获取当前环境变量值"""
    return {
        'API_KEY': os.getenv('API_KEY', ''),
        'COOKIES_STR': os.getenv('COOKIES_STR', ''),
        'AUTUORIZATION': os.getenv('AUTUORIZATION', ''),
        'TOGGLE_KEYWORDS': os.getenv('TOGGLE_KEYWORDS', ''),
        'MODEL_BASE_URL': os.getenv('MODEL_BASE_URL', ''),
        'MODEL_NAME': os.getenv('MODEL_NAME', ''),
        'ADMIN_USERNAME': app.config['ADMIN_USERNAME'],
        'ADMIN_PASSWORD': app.config['ADMIN_PASSWORD'],
    }

def save_env_values(values):
    """保存环境变量到.env文件"""
    with open(app.config['ENV_FILE'], 'w', encoding='utf-8') as f:
        for key, value in values.items():
            # 跳过管理员凭据的特殊处理
            if key not in ['ADMIN_USERNAME', 'ADMIN_PASSWORD']:
                f.write(f"{key}={value}\n")
        
        # 单独保存管理员凭据（不在表单中显示）
        f.write(f"ADMIN_USERNAME={app.config['ADMIN_USERNAME']}\n")
        f.write(f"ADMIN_PASSWORD={app.config['ADMIN_PASSWORD']}\n")
    
    # 重新加载环境变量
    load_dotenv(app.config['ENV_FILE'], override=True)

def check_auth(username, password):
    """检查用户名/密码是否有效"""
    logger.debug(f"验证用户: {username}")
    logger.debug(f"期望用户: {app.config['ADMIN_USERNAME']}")
    
    return username == app.config['ADMIN_USERNAME'] and password == app.config['ADMIN_PASSWORD']

def requires_auth(f):
    """身份验证装饰器 - 修复版本"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # 检查session中是否有登录标记
        if session.get('authenticated'):
            return f(*args, **kwargs)
            
        # 检查基本认证
        auth = request.authorization
        if auth and check_auth(auth.username, auth.password):
            session['authenticated'] = True
            session['username'] = auth.username
            return f(*args, **kwargs)
            
        # 返回401未授权响应
        return make_response(
            '需要身份验证才能访问此页面',
            401,
            {'WWW-Authenticate': 'Basic realm="Configuration Editor"'}
        )
    return decorated

@app.route('/', methods=['GET', 'POST'])
@requires_auth
def config_editor():
    """配置编辑器主页面"""
    if request.method == 'POST':
        # 处理取消按钮
        if 'cancel' in request.form:
            return redirect(url_for('config_editor'))
        
        # 处理保存按钮
        if 'save' in request.form:
            new_values = {
                'API_KEY': request.form.get('api_key', ''),
                'COOKIES_STR': request.form.get('cookies_str', ''),
                'AUTUORIZATION': request.form.get('authorization', ''),
                'TOGGLE_KEYWORDS': request.form.get('toggle_keywords', ''),
                'MODEL_BASE_URL': request.form.get('model_base_url', ''),
                'MODEL_NAME': request.form.get('model_name', ''),
            }
            save_env_values(new_values)
            return render_template('config.html', 
                                   values=get_env_values(),
                                   message="配置已成功保存！")
    
    # GET请求：显示当前配置
    return render_template('config.html', values=get_env_values())

@app.route('/change-password', methods=['POST'])
@requires_auth
def change_password():
    """更改管理员密码"""
    current_username = request.form.get('current_username')
    current_password = request.form.get('current_password')
    new_username = request.form.get('new_username')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # 验证当前凭据
    if not check_auth(current_username, current_password):
        return render_template('config.html', 
                              values=get_env_values(),
                              error="当前用户名或密码错误")
    
    # 验证新密码匹配
    if new_password != confirm_password:
        return render_template('config.html', 
                              values=get_env_values(),
                              error="新密码和确认密码不匹配")
    
    # 验证密码强度
    if len(new_password) < 10:
        return render_template('config.html', 
                              values=get_env_values(),
                              error="密码长度至少需要10个字符")
    
    # 更新凭据
    app.config['ADMIN_USERNAME'] = new_username
    app.config['ADMIN_PASSWORD'] = new_password
    
    # 保存到.env文件
    save_env_values({})
    
    # 更新session
    session['username'] = new_username
    
    # 重定向到登录页面
    return render_template('config.html', 
                          values=get_env_values(),
                          message="管理员凭据已成功更新！")

@app.route('/logout')
def logout():
    """注销用户 - 修复版本"""
    # 清除会话
    session.pop('authenticated', None)
    session.pop('username', None)
    
    # 创建一个响应对象
    response = make_response(redirect(url_for('config_editor')))
    
    # 添加清除认证缓存的头部
    response.headers['Clear-Site-Data'] = '"cache", "cookies", "storage", "executionContexts"'
    response.headers['WWW-Authenticate'] = 'Basic realm="Configuration Editor"'
    
    # 设置缓存控制头部
    response.headers['Cache-Control'] = 'no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response


def create_app():
    """应用工厂函数，用于生产环境部署"""
    # 确保管理员凭据已设置
    if not app.config['ADMIN_USERNAME'] or not app.config['ADMIN_PASSWORD']:
        default_username = 'admin'
        default_password = base64.b64encode(os.urandom(12)).decode('utf-8')[:16]
        logger.info(f"未设置管理员凭据，使用默认值: {default_username}/{default_password}")
        app.config['ADMIN_USERNAME'] = default_username
        app.config['ADMIN_PASSWORD'] = default_password
        save_env_values({})
    
    return app

def run_development_server():
    """运行开发服务器（仅用于开发环境）"""
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)

def run_server():
    app = create_app()
    logger.info("Starting production server on http://0.0.0.0:5000")
    serve(app, host='0.0.0.0', port=5000)
if __name__ == '__main__':
    # 在开发环境中使用开发服务器
    # run_development_server()
    run_server()