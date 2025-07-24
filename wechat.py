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
            print("加密模块未初始化，无法解密", flush=True)
            return None
            
        try:
            print(f"开始解密，加密文本长度: {len(text)}", flush=True)
            
            # Base64解码
            text = base64.b64decode(text)
            print(f"Base64解码后长度: {len(text)}字节", flush=True)
            
            # AES解密
            cipher = AES.new(self.key, AES.MODE_CBC, self.key[:16])
            decrypted = cipher.decrypt(text)
            print(f"AES解密后长度: {len(decrypted)}字节", flush=True)
            
            # 去除PKCS#7填充
            pad = decrypted[-1]
            if isinstance(pad, str):
                pad = ord(pad)  # 如果是字符串，转换为数字
                
            print(f"填充值: {pad}", flush=True)
            if pad < 1 or pad > 32:
                print(f"填充值异常: {pad}，使用默认值0", flush=True)
                pad = 0
            
            decrypted = decrypted[:-pad] if pad > 0 else decrypted
            print(f"去除填充后长度: {len(decrypted)}字节", flush=True)
            
            # 获取消息内容
            content = decrypted[16:]  # 去除随机16字节字符串
            print(f"去除随机字符串后长度: {len(content)}字节", flush=True)
            
            # 检查长度是否足够
            if len(content) < 4:
                print("内容长度不足，无法解析消息长度", flush=True)
                return None
                
            # 获取原文长度
            xml_len = socket.ntohl(struct.unpack("I", content[:4])[0])
            print(f"消息内容长度: {xml_len}字节", flush=True)
            
            # 检查长度是否足够
            if 4 + xml_len > len(content):
                print(f"内容长度不足，需要{4 + xml_len}字节，实际只有{len(content)}字节", flush=True)
                return None
                
            # 提取XML内容和CorpID
            xml_content = content[4:4 + xml_len]
            corp_id = content[4 + xml_len:]
            
            # 打印调试信息
            print(f"解密结果: XML长度={len(xml_content)}字节, CorpID={corp_id}", flush=True)
            print(f"XML内容前100字节: {xml_content[:100]}", flush=True)
            
            return xml_content
        except Exception as e:
            print(f"解密消息失败: {e}", flush=True)
            import traceback
            traceback.print_exc()
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
    
    def send_message(self, user_id, content):
        """发送消息到企业微信用户或群聊"""
        token = self.get_access_token()
        if not token:
            print("获取访问令牌失败，无法发送消息", flush=True)
            return False
        
        # 默认使用应用消息接口向用户发送消息
        # 企业微信用户消息和群聊消息使用不同的接口
        # 企业微信的用户ID通常是用户名或userid，如 "ShenChaoSong"
        # 群聊ID通常是特定格式的字符串，如 "chatxxxxxxxxx"
        if user_id.startswith('chat'):
            # 这是群聊ID格式，使用群聊消息接口
            url = f"{self.API_BASE_URL}/appchat/send?access_token={token}"
            data = {
                "chatid": user_id,
                "msgtype": "text",
                "text": {
                    "content": content
                },
                "safe": 0
            }
            print(f"发送消息到群聊: {user_id}", flush=True)
        else:
            # 使用应用消息接口向用户发送消息
            url = f"{self.API_BASE_URL}/message/send?access_token={token}"
            data = {
                "touser": user_id,
                "msgtype": "text",
                "agentid": AGENT_ID,  # 使用应用ID
                "text": {
                    "content": content
                },
                "safe": 0
            }
            print(f"发送应用消息到用户: {user_id}", flush=True)
        
        print(f"请求URL: {url}", flush=True)
        print(f"请求数据: {data}", flush=True)
        
        try:
            response = requests.post(url, json=data)
            result = response.json()
            
            print(f"API响应: {result}", flush=True)
            
            if result.get("errcode") == 0:
                print("消息发送成功", flush=True)
                return True
            else:
                print(f"发送消息失败: {result}", flush=True)
                return False
        except Exception as e:
            print(f"发送消息异常: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return False
    
    def verify_url(self, msg_signature, timestamp, nonce, echostr):
        """验证URL有效性"""
        # 直接使用print输出到标准输出，确保Docker能捕获
        print("=== 开始URL验证 ===", flush=True)
        
        if not TOKEN:
            print("警告: 未配置TOKEN，无法验证URL", flush=True)
            return echostr
        
        # 调试信息
        print(f"验证参数: signature={msg_signature}", flush=True)
        print(f"验证参数: timestamp={timestamp}", flush=True)
        print(f"验证参数: nonce={nonce}", flush=True)
        print(f"验证参数: echostr={echostr}", flush=True)
        print(f"使用的TOKEN: {TOKEN}", flush=True)
        
        # 尝试解码echostr
        import urllib.parse
        try:
            decoded_echostr = urllib.parse.unquote(echostr)
            if decoded_echostr != echostr:
                print(f"已解码echostr: {decoded_echostr}", flush=True)
                echostr = decoded_echostr
        except Exception as e:
            print(f"解码echostr失败: {e}", flush=True)
        
        # 尝试两种不同的验证方法
        print("开始计算签名...", flush=True)
        print("尝试使用加密方式验证", flush=True)
        try:
            decrypted = self.crypto.decrypt(echostr)
            if decrypted:
                print("加密验证成功", flush=True)
                return decrypted.decode('utf-8')
        except Exception as e:
            print(f"加密验证失败: {e}", flush=True)
        
        # 直接返回echostr
        print("直接返回echostr作为最后手段", flush=True)
        return echostr
    
    def parse_message(self, xml_content):
        """解析接收到的XML消息"""
        try:
            print(f"开始解析XML消息: {xml_content[:100]}...", flush=True)
            # 解析XML
            root = ET.fromstring(xml_content)
            
            # 提取消息内容
            message = {}
            for child in root:
                message[child.tag] = child.text
                print(f"解析到字段: {child.tag} = {child.text}", flush=True)
            
            # 检查是否是加密消息
            if 'Encrypt' in message and len(message) <= 3:
                print("检测到加密消息，需要先解密", flush=True)
                
                # 如果只有加密内容，尝试解密
                if self.crypto and message.get('Encrypt'):
                    try:
                        encrypted_msg = message.get('Encrypt')
                        print(f"尝试解密消息: {encrypted_msg[:30]}...", flush=True)
                        
                        decrypted_content = self.crypto.decrypt(encrypted_msg)
                        if decrypted_content:
                            print("内部解密成功！", flush=True)
                            decrypted_xml = decrypted_content.decode('utf-8')
                            print(f"解密后的XML: {decrypted_xml[:100]}...", flush=True)
                            
                            # 递归调用自身解析解密后的内容
                            return self.parse_message(decrypted_xml)
                        else:
                            print("内部解密失败", flush=True)
                    except Exception as e:
                        print(f"内部解密异常: {e}", flush=True)
                        import traceback
                        traceback.print_exc()
            
            # 检查必要字段
            required_fields = ["FromUserName", "ToUserName", "MsgType", "CreateTime"]
            missing_fields = [field for field in required_fields if field not in message]
            if missing_fields:
                print(f"警告: 消息缺少必要字段: {missing_fields}", flush=True)
            
            return message
        except Exception as e:
            print(f"解析XML消息失败: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return {
                "FromUserName": "unknown",
                "Content": "",
                "MsgType": "unknown",
                "CreateTime": int(time.time())
            }

# 创建企业微信API实例
wechat_api = WeChatAPI() 