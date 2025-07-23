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
    try:
        # 获取消息内容
        xml_content = await request.body()
        xml_content = xml_content.decode('utf-8')
        
        # 如果配置了加密，需要解密消息
        if wechat_api.crypto and msg_signature:
            # 这里应该从XML中提取加密的消息内容，然后解密
            # 简化处理，假设已经解密
            pass
        
        # 解析消息
        message = wechat_api.parse_message(xml_content)
        
        # 仅处理文本消息
        if message.get('MsgType') == 'text':
            content = message.get('Content', '')
            
            # 解析消息内容
            record = message_parser.parse_message(content)
            
            if record:
                # 存入数据库
                record_id = db.insert_record(
                    record_time=record.record_time,
                    record_type=record.record_type,
                    amount=record.amount,
                    description=record.description
                )
                
                if record_id:
                    # 构建回复消息
                    reply = f"记录成功！\n时间：{record.record_time.strftime('%Y-%m-%d %H:%M')}\n类型：{record.record_type}"
                    if record.amount:
                        reply += f"\n数量：{record.amount}"
                    
                    # 发送回复
                    # 注意：实际应用中需要获取正确的群聊ID
                    chat_id = message.get('FromUserName', 'your_chat_id')
                    wechat_api.send_message(chat_id, reply)
                else:
                    print("记录插入数据库失败")
            else:
                print(f"无法解析消息: {content}")
        
        # 返回成功响应
        return PlainTextResponse("success")
    except Exception as e:
        print(f"处理消息异常: {e}")
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
        print("数据库初始化失败")
    else:
        print("应用初始化成功")

if __name__ == '__main__':
    # 启动FastAPI应用
    uvicorn.run("app:app", host=APP_HOST, port=int(APP_PORT), reload=True) 