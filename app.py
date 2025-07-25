from fastapi import FastAPI, Request, Response, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from typing import Optional, Dict, List, Any
import json
from datetime import datetime
import uvicorn

from config import APP_HOST, APP_PORT, CORP_ID
from db import db
from wechat import wechat_api
from message_parser import message_parser

app = FastAPI(
    title="婴儿日常记录系统",
    description="通过企业微信群接收婴儿日常记录并存储到数据库",
    version="1.0.0"
)

@app.get("/", response_class=PlainTextResponse)
def index():
    """首页"""
    return '婴儿日常记录服务已启动'

@app.get("/wechat/callback")
async def wechat_callback_get(
    msg_signature: str = Query(""),
    timestamp: str = Query(""),
    nonce: str = Query(""),
    echostr: str = Query("")
):
    """处理企业微信回调验证请求"""
    return PlainTextResponse(wechat_api.verify_url(msg_signature, timestamp, nonce, echostr))

@app.post("/wechat/callback")
async def wechat_callback_post(
    request: Request,
    msg_signature: str = Query(""),
    timestamp: str = Query(""),
    nonce: str = Query("")
):
    """处理企业微信消息接收"""
    print("\n\n=== 开始处理微信消息回调 ===", flush=True)
    print(f"请求参数: msg_signature={msg_signature}, timestamp={timestamp}, nonce={nonce}", flush=True)
    try:
        # 获取消息内容
        xml_content = await request.body()
        print("收到原始XML消息:", flush=True)
        print(xml_content, flush=True)
        xml_content_str = xml_content.decode('utf-8')
        print("解码后的XML:", flush=True)
        print(xml_content_str, flush=True)
        
        # 解析出原始XML
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_content_str)
        
        # 如果配置了加密，需要解密消息
        decrypted_xml = None
        if msg_signature:
            print(f"检测到签名消息，msg_signature={msg_signature}", flush=True)
            print(f"timestamp={timestamp}, nonce={nonce}", flush=True)
            
            # 从XML中提取加密的消息内容
            encrypt_elem = root.find(".//Encrypt")
            if encrypt_elem is not None and encrypt_elem.text:
                encrypted_msg = encrypt_elem.text
                print(f"提取的加密消息: {encrypted_msg[:30]}...", flush=True)
                
                # 验证签名
                from config import TOKEN, CORP_ID
                print(f"TOKEN={TOKEN}, CORP_ID={CORP_ID}", flush=True)
                
                import hashlib
                array = [TOKEN, timestamp, nonce, encrypted_msg]
                array.sort()
                str_to_sign = ''.join(array)
                signature = hashlib.sha1(str_to_sign.encode('utf-8')).hexdigest()
                
                print(f"计算的签名: {signature}", flush=True)
                print(f"接收的签名: {msg_signature}", flush=True)
                
                if signature == msg_signature:
                    print("签名验证成功，开始解密", flush=True)
                    
                    # 检查加密模块
                    if wechat_api.crypto:
                        print("加密模块已初始化，开始解密", flush=True)
                        # 解密消息
                        decrypted_content = wechat_api.crypto.decrypt(encrypted_msg)
                        if decrypted_content:
                            print("解密成功！", flush=True)
                            decrypted_xml = decrypted_content.decode('utf-8')
                            print("解密后的XML:", flush=True)
                            print(decrypted_xml, flush=True)
                            
                            # 使用解密后的内容更新xml_content
                            xml_content_str = decrypted_xml
                        else:
                            print("解密失败！", flush=True)
                    else:
                        print("错误：加密模块未初始化", flush=True)
                else:
                    print("签名验证失败", flush=True)
        
        # 解析消息
        message = wechat_api.parse_message(xml_content_str)
        print("解析后的消息:", flush=True)
        print(message, flush=True)
        # 仅处理文本消息
        if message.get('MsgType') == 'text':
            content = message.get('Content', '')
            print(f"接收到文本消息: '{content}'", flush=True)
            
            # 调试: 简单回显收到的消息内容
            from_user_name = message.get('FromUserName', '')
            to_user_name = message.get('ToUserName', '')
            print(f"发送者: {from_user_name}, 接收者: {to_user_name}", flush=True)
            
            # 测试简单回复
            # if content and from_user_name:
            #     reply = f"我收到了您的消息: {content}"
            #     print(f"准备回复给用户 {from_user_name}: {reply}", flush=True)
                
            #     # 企业微信解析后的FromUserName是发送者的UserID
            #     # 确保使用正确的用户ID发送回复
            #     user_id = from_user_name
            #     print(f"发送给用户ID: {user_id}", flush=True)
                
            #     # 发送回复
            #     if wechat_api.send_message(user_id, reply):
            #         print("回复消息已发送成功", flush=True)
            #     else:
            #         print("回复消息发送失败", flush=True)
            
            # 尝试解析消息内容
            record = message_parser.parse_message(content)
            
            if record:
                print(f"成功解析消息为记录: {record.record_type}", flush=True)
                print(f"记录详情: 时间={record.record_time}, 类型={record.record_type}, 是否删除指令={record.is_delete_command}", flush=True)
                
                # 检查是否是删除指令
                if record.is_delete_command:
                    print(f"检测到删除指令，准备删除记录: {record.record_time}, {record.record_type}", flush=True)
                    # 删除记录
                    result = db.delete_record(
                        record_time=record.record_time,
                        record_type=record.record_type
                    )
                    
                    if result:
                        record_id = result['id']
                        print(f"记录已标记为删除，ID: {record_id}", flush=True)
                        
                        # 构建回复消息
                        reply = f"记录删除成功！\n时间：{record.record_time.strftime('%Y-%m-%d %H:%M')}\n类型：{record.record_type}"
                        if result.get('amount'):
                            reply += f"\n数量：{result.get('amount')}"
                        
                        # 发送回复
                        user_id = from_user_name
                        print(f"发送删除确认给用户ID: {user_id}", flush=True)
                        if wechat_api.send_message(user_id, reply):
                            print("成功回复删除确认", flush=True)
                        else:
                            print("发送删除确认失败", flush=True)
                    else:
                        # 未找到要删除的记录
                        reply = f"未找到要删除的记录！\n时间：{record.record_time.strftime('%Y-%m-%d %H:%M')}\n类型：{record.record_type}"
                        user_id = from_user_name
                        wechat_api.send_message(user_id, reply)
                        print("未找到要删除的记录", flush=True)
                else:
                    print(f"不是删除指令，准备插入/更新记录", flush=True)
                    # 存入数据库
                    result = db.insert_record(
                        record_time=record.record_time,
                        record_type=record.record_type,
                        amount=record.amount,
                        description=record.description
                    )
                    
                    if result:
                        record_id = result['id']
                        is_update = result.get('is_update', False)
                        
                        print(f"记录已{'更新' if is_update else '插入'}数据库，ID: {record_id}", flush=True)
                        # 构建回复消息
                        reply = f"记录{'更新' if is_update else '添加'}成功！\n时间：{record.record_time.strftime('%Y-%m-%d %H:%M')}\n类型：{record.record_type}"
                        if record.amount:
                            reply += f"\n数量：{record.amount}"
                        
                        # 如果是更新记录，添加被覆盖的信息
                        if is_update:
                            old_amount = result.get('old_amount')
                            old_description = result.get('old_description')
                            reply += "\n\n覆盖了之前的记录："
                            if old_amount:
                                reply += f"\n原数量：{old_amount}"
                            if old_description and old_description != record.description:
                                reply += f"\n原描述：{old_description}"
                        
                        # 发送回复
                        user_id = from_user_name  # 使用FromUserName作为用户ID
                        print(f"发送记录确认给用户ID: {user_id}", flush=True)
                        if wechat_api.send_message(user_id, reply):
                            print("成功回复记录确认", flush=True)
                        else:
                            print("发送记录确认失败", flush=True)
                    else:
                        print("记录插入数据库失败", flush=True)
            else:
                print(f"无法解析消息为记录: {content}", flush=True)
        
        # 记录处理完成
        print("=== 消息处理完成 ===\n", flush=True)
        
        # 返回成功响应
        return PlainTextResponse("success")
    except Exception as e:
        print(f"处理消息异常: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return PlainTextResponse("success")  # 企业微信要求始终返回success

class RecordQueryParams:
    def __init__(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        type: Optional[str] = None,
        limit: int = 100
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.record_type = type
        self.limit = limit

@app.get("/api/records")
async def get_records(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 100
):
    """获取记录API"""
    try:
        params = RecordQueryParams(
            start_date=start_date,
            end_date=end_date,
            type=type,
            limit=limit
        )
        
        records = db.get_records(
            start_date=params.start_date,
            end_date=params.end_date,
            record_type=params.record_type,
            limit=params.limit
        )
        
        # 格式化日期时间
        for record in records:
            if 'record_time' in record:
                record['record_time'] = record['record_time'].strftime('%Y-%m-%d %H:%M:%S')
            if 'created_at' in record:
                record['created_at'] = record['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return {
            'code': 0,
            'message': 'success',
            'data': records
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                'code': 500,
                'message': str(e),
                'data': []
            }
        )

class MessageRequest:
    def __init__(self, message: str):
        self.message = message

@app.post("/api/test_parser")
async def test_parser(request: Request):
    """测试消息解析API"""
    try:
        data = await request.json()
        message = data.get('message', '')
        
        record = message_parser.parse_message(message)
        
        if record:
            return {
                'code': 0,
                'message': 'success',
                'data': {
                    'record_time': record.record_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'record_type': record.record_type,
                    'amount': record.amount,
                    'description': record.description
                }
            }
        else:
            return JSONResponse(
                status_code=400,
                content={
                    'code': 400,
                    'message': '无法解析消息',
                    'data': None
                }
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                'code': 500,
                'message': str(e),
                'data': None
            }
        )

@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    # 初始化数据库
    if not db.init_db():
        print("数据库初始化失败", flush=True)
    else:
        print("应用初始化成功", flush=True)
    
    # 检查加密模块
    from config import ENCODING_AES_KEY, CORP_ID
    print(f"企业ID: {CORP_ID}", flush=True)
    print(f"加密密钥长度: {len(ENCODING_AES_KEY) if ENCODING_AES_KEY else 0}", flush=True)
    print(f"加密模块状态: {'已初始化' if wechat_api.crypto else '未初始化'}", flush=True)

if __name__ == '__main__':
    # 启动FastAPI应用
    uvicorn.run("app:app", host=APP_HOST, port=int(APP_PORT), reload=True) 