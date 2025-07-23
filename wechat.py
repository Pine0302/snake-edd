import requests
import json
import time
import hashlib
import base64
import random
import string
import struct
import socket
import xml.etree.ElementTree as ET
from config import CORP_ID, SECRET, AGENT_ID, TOKEN, ENCODING_AES_KEY

# 尝试导入加密库，如果不可用则提供警告
try:
    from Cryptodome.Cipher import AES
    HAS_CRYPTO = True
except ImportError:
    try:
        # 尝试备用导入路径
        from Crypto.Cipher import AES
        HAS_CRYPTO = True
    except ImportError:
        print("警告: 未安装加密库，消息加解密功能不可用")
        print("请安装: pip install pycryptodomex")
        HAS_CRYPTO = False

class WXBizMsgCrypt:
    """企业微信消息加解密类"""
    
    def __init__(self, encoding_aes_key):
        if not HAS_CRYPTO:
            print("加密模块未初始化，消息加解密功能不可用")
            return
            
        try:
            self.key = base64.b64decode(encoding_aes_key + "=")
            self.aes_key_len = len(self.key)
        except Exception as e:
            print(f"初始化加密模块失败: {e}")
    
    def encrypt(self, text, corp_id):
        """加密消息"""
        if not HAS_CRYPTO:
            return None
            
        try:
            # 生成随机16字节字符串作为填充
            random_str = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(16))
            text = random_str.encode('utf-8') + struct.pack("I", socket.htonl(len(text))) + text.encode('utf-8') + corp_id.encode('utf-8')
            
            # 使用PKCS#7填充
            amount_to_pad = AES.block_size - (len(text) % AES.block_size)
            if amount_to_pad == 0:
                amount_to_pad = AES.block_size
            pad = chr(amount_to_pad).encode('utf-8') * amount_to_pad
            text = text + pad
            
            # AES加密
            cipher = AES.new(self.key, AES.MODE_CBC, self.key[:16])
            encrypted = cipher.encrypt(text)
            return base64.b64encode(encrypted)
        except Exception as e:
            print(f"加密消息失败: {e}")
            return None
    
    def decrypt(self, text):
        """解密消息"""
        if not HAS_CRYPTO:
            return None
            
        try:
            # Base64解码
            text = base64.b64decode(text)
            
            # AES解密
            cipher = AES.new(self.key, AES.MODE_CBC, self.key[:16])
            decrypted = cipher.decrypt(text)
            
            # 去除填充
            pad = decrypted[-1]
            if pad < 1 or pad > 32:
                pad = 0
            decrypted = decrypted[:-pad]
            
            # 获取消息内容
            content = decrypted[16:]  # 去除随机字符串
            xml_len = socket.ntohl(struct.unpack("I", content[:4])[0])
            xml_content = content[4:4 + xml_len]
            from_corp_id = content[4 + xml_len:]
            
            return xml_content
        except Exception as e:
            print(f"解密消息失败: {e}")
            return None

class WeChatAPI:
    """企业微信API封装"""
    
    # API接口URL
    API_BASE_URL = "https://qyapi.weixin.qq.com/cgi-bin"
    
    def __init__(self):
        self.access_token = None
        self.token_expires_at = 0
        self.crypto = None
        
        # 初始化加密模块
        if ENCODING_AES_KEY and HAS_CRYPTO:
            try:
                self.crypto = WXBizMsgCrypt(ENCODING_AES_KEY)
            except Exception as e:
                print(f"警告: 初始化加密模块失败: {e}")
    
    def get_access_token(self):
        """获取或刷新访问令牌"""
        now = int(time.time())
        
        # 如果令牌未过期，直接返回
        if self.access_token and now < self.token_expires_at:
            return self.access_token
        
        # 请求新的访问令牌
        url = f"{self.API_BASE_URL}/gettoken"
        params = {
            "corpid": CORP_ID,
            "corpsecret": SECRET
        }
        
        try:
            response = requests.get(url, params=params)
            result = response.json()
            
            if result.get("errcode") == 0:
                self.access_token = result.get("access_token")
                self.token_expires_at = now + result.get("expires_in") - 200  # 提前200秒刷新
                return self.access_token
            else:
                print(f"获取访问令牌失败: {result}")
                return None
        except Exception as e:
            print(f"请求访问令牌异常: {e}")
            return None
    
    def send_message(self, chat_id, content):
        """发送消息到企业微信群"""
        token = self.get_access_token()
        if not token:
            return False
        
        url = f"{self.API_BASE_URL}/appchat/send?access_token={token}"
        data = {
            "chatid": chat_id,
            "msgtype": "text",
            "text": {
                "content": content
            },
            "safe": 0
        }
        
        try:
            response = requests.post(url, json=data)
            result = response.json()
            
            if result.get("errcode") == 0:
                return True
            else:
                print(f"发送消息失败: {result}")
                return False
        except Exception as e:
            print(f"发送消息异常: {e}")
            return False
    
    def verify_url(self, msg_signature, timestamp, nonce, echostr):
        """验证URL有效性"""
        if not TOKEN:
            print("警告: 未配置TOKEN，无法验证URL")
            return echostr
        
        # 1. 将token、timestamp、nonce三个参数进行字典序排序
        array = [TOKEN, timestamp, nonce]
        array.sort()
        
        # 2. 将三个参数字符串拼接成一个字符串进行sha1加密
        str_to_sign = ''.join(array)
        sha1 = hashlib.sha1(str_to_sign.encode('utf-8')).hexdigest()
        
        # 3. 开发者获得加密后的字符串可与signature对比，标识该请求来源于微信
        if sha1 == msg_signature:
            return echostr
        else:
            print("URL验证失败")
            return "URL验证失败"
    
    def parse_message(self, xml_content):
        """解析接收到的XML消息"""
        try:
            # 解析XML
            root = ET.fromstring(xml_content)
            
            # 提取消息内容
            message = {}
            for child in root:
                message[child.tag] = child.text
            
            return message
        except Exception as e:
            print(f"解析XML消息失败: {e}")
            return {
                "FromUserName": "unknown",
                "Content": "",
                "MsgType": "unknown",
                "CreateTime": int(time.time())
            }

# 创建企业微信API实例
wechat_api = WeChatAPI() 