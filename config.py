import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 企业微信配置
CORP_ID = os.getenv('CORP_ID')
AGENT_ID = os.getenv('AGENT_ID', '1000002')
SECRET = os.getenv('SECRET')
TOKEN = os.getenv('TOKEN')  # 用于验证URL有效性
ENCODING_AES_KEY = os.getenv('ENCODING_AES_KEY')  # 消息加解密密钥

# 数据库配置
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'baby_records'),
    'charset': 'utf8mb4'
}

# 应用配置
APP_HOST = os.getenv('APP_HOST', '0.0.0.0')
APP_PORT = int(os.getenv('APP_PORT', 5000)) 