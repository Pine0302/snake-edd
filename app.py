from fastapi import FastAPI, Request, Response, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse, HTMLResponse
from typing import Optional, Dict, List, Any
import json
from datetime import datetime, date
import uvicorn
import hashlib
import time

from config import APP_HOST, APP_PORT, CORP_ID
from db import db
from wechat import wechat_api
from message_parser import message_parser

# 辅助函数
def get_record_type_emoji(record_type):
    """获取记录类型对应的emoji"""
    emoji_map = {
        '吃': '🍼',
        '大便': '💩',
        '小便': '💦',
        '睡': '😴',
        '体温': '🌡️',
        '吃药': '💊',
        '其他': '📝'
    }
    return emoji_map.get(record_type, '📝')

def generate_daily_report(date_str):
    """生成指定日期的日报内容"""
    grouped_records = db.get_daily_records(date_str)
    
    if not grouped_records:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        date_display = date_obj.strftime('%Y年%m月%d日')
        return f"未找到 {date_display} 的记录！"
    
    # 构建日报回复
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    date_display = date_obj.strftime('%Y年%m月%d日')
    
    report = f"📅 {date_display}日报 📅\n"
    report += f"{'='*30}\n\n"
    
    # 按类型输出记录
    for record_type, records in grouped_records.items():
        # 添加记录类型标题
        type_emoji = get_record_type_emoji(record_type)
        report += f"{type_emoji} {record_type}记录 ({len(records)}条):\n"
        
        # 添加记录详情
        for idx, rec in enumerate(records, 1):
            time_str = rec['record_time'].strftime('%H:%M')
            amount_str = ""
            if rec['amount']:
                if rec['amount_unit']:
                    amount_str = f" {rec['amount']}{rec['amount_unit']}"
                else:
                    amount_str = f" {rec['amount']}"
            report += f"  {idx}. {time_str}{amount_str}\n"
        
        report += "\n"
    
    # 添加汇总信息
    total_records = sum(len(records) for records in grouped_records.values())
    report += f"{'='*30}\n"
    report += f"共记录 {total_records} 条信息"
    
    return report

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
                print(f"记录详情: 时间={record.record_time}, 类型={record.record_type}, 是否删除指令={record.is_delete_command}, 是否日报查询={record.is_daily_report_command}", flush=True)
                
                # 检查是否是日报查询指令
                if record.is_daily_report_command and record.report_date:
                    print(f"检测到日报查询指令，查询日期: {record.report_date}", flush=True)
                    # 获取指定日期的记录
                    grouped_records = db.get_daily_records(record.report_date)
                    
                    if grouped_records:
                        # 构建日报回复
                        date_obj = datetime.strptime(record.report_date, '%Y-%m-%d')
                        date_str = date_obj.strftime('%Y年%m月%d日')
                        
                        reply = f"📅 {date_str}日报 📅\n"
                        reply += f"{'='*30}\n\n"
                        
                        # 按类型输出记录
                        for record_type, records in grouped_records.items():
                            # 添加记录类型标题
                            type_emoji = get_record_type_emoji(record_type)
                            reply += f"{type_emoji} {record_type}记录 ({len(records)}条):\n"
                            
                            # 添加记录详情
                            for idx, rec in enumerate(records, 1):
                                time_str = rec['record_time'].strftime('%H:%M')
                                amount_str = ""
                                if rec['amount']:
                                    if rec['amount_unit']:
                                        amount_str = f" {rec['amount']}{rec['amount_unit']}"
                                    else:
                                        amount_str = f" {rec['amount']}"
                                reply += f"  {idx}. {time_str}{amount_str}\n"
                            
                            reply += "\n"
                        
                        # 添加汇总信息
                        total_records = sum(len(records) for records in grouped_records.values())
                        reply += f"{'='*30}\n"
                        reply += f"共记录 {total_records} 条信息"
                        
                        # 发送回复
                        user_id = from_user_name
                        print(f"发送日报给用户ID: {user_id}", flush=True)
                        if wechat_api.send_message(user_id, reply):
                            print("成功发送日报", flush=True)
                        else:
                            print("发送日报失败", flush=True)
                    else:
                        # 没有找到记录
                        date_obj = datetime.strptime(record.report_date, '%Y-%m-%d')
                        date_str = date_obj.strftime('%Y年%m月%d日')
                        reply = f"未找到 {date_str} 的记录！"
                        wechat_api.send_message(from_user_name, reply)
                        print(f"未找到日期 {record.report_date} 的记录", flush=True)
                
                # 检查是否是请求日报链接
                elif content in ["日报链接", "获取日报链接", "日报url", "日报URL"]:
                    print(f"检测到日报链接请求", flush=True)
                    
                    # 生成今天的日期和token
                    today = datetime.now().date().strftime('%Y-%m-%d')
                    token = hashlib.md5(f"baby_report_{today}".encode()).hexdigest()[:10]
                    
                    # 构建链接
                    base_url = f"http://{APP_HOST}:{APP_PORT}"
                    view_link = f"{base_url}/daily-report?date={today}&token={token}"
                    send_link = f"{base_url}/daily-report?date={today}&token={token}&user_id={from_user_name}"
                    
                    # 构建回复
                    reply = f"📱 今日日报链接 📱\n\n"
                    reply += f"1. 查看日报:\n{view_link}\n\n"
                    reply += f"2. 发送日报到企业微信:\n{send_link}\n\n"
                    reply += f"3. 获取更多链接选项:\n{base_url}/report-link\n\n"
                    reply += "提示: 链接当天有效，每天更新"
                    
                    # 发送回复
                    user_id = from_user_name
                    print(f"发送日报链接给用户ID: {user_id}", flush=True)
                    if wechat_api.send_message(user_id, reply):
                        print("成功发送日报链接", flush=True)
                    else:
                        print("发送日报链接失败", flush=True)
                
                # 检查是否是删除指令
                elif record.is_delete_command:
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
                        
                        # 添加数量信息
                        if result.get('amount'):
                            amount_str = result.get('amount')
                            if result.get('amount_unit'):
                                amount_str += result.get('amount_unit')
                            reply += f"\n数量：{amount_str}"
                        
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
                        amount_unit=record.amount_unit,
                        description=record.description
                    )
                    
                    if result:
                        record_id = result['id']
                        is_update = result.get('is_update', False)
                        
                        print(f"记录已{'更新' if is_update else '插入'}数据库，ID: {record_id}", flush=True)
                        # 构建回复消息
                        reply = f"记录{'更新' if is_update else '添加'}成功！\n时间：{record.record_time.strftime('%Y-%m-%d %H:%M')}\n类型：{record.record_type}"
                        
                        # 添加数量信息
                        formatted_amount = record.get_formatted_amount()
                        if formatted_amount:
                            reply += f"\n数量：{formatted_amount}"
                        
                        # 如果是更新记录，添加被覆盖的信息
                        if is_update:
                            old_amount = result.get('old_amount')
                            old_amount_unit = result.get('old_amount_unit')
                            old_description = result.get('old_description')
                            
                            reply += "\n\n覆盖了之前的记录："
                            if old_amount:
                                old_formatted_amount = f"{old_amount}{old_amount_unit}" if old_amount_unit else old_amount
                                reply += f"\n原数量：{old_formatted_amount}"
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

@app.get("/daily-report", response_class=HTMLResponse)
async def get_daily_report(
    date: Optional[str] = None,
    user_id: Optional[str] = None,
    token: Optional[str] = None
):
    """获取日报的API端点"""
    try:
        # 验证token (简单实现，实际应用中应使用更安全的方式)
        today = datetime.now().date().strftime('%Y-%m-%d')
        expected_token = hashlib.md5(f"baby_report_{today}".encode()).hexdigest()[:10]
        
        if token != expected_token:
            return HTMLResponse(content="<h1>无效的访问令牌</h1>", status_code=403)
        
        # 如果未指定日期，默认使用今天
        if not date:
            date = today
        
        # 生成日报内容
        report_content = generate_daily_report(date)
        
        # 如果指定了用户ID，发送消息到企业微信
        if user_id:
            wechat_api.send_message(user_id, report_content)
            return HTMLResponse(content=f"""
            <html>
                <head>
                    <title>日报已发送</title>
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                        .container {{ max-width: 600px; margin: 0 auto; }}
                        .success {{ color: green; }}
                        pre {{ white-space: pre-wrap; background: #f5f5f5; padding: 15px; border-radius: 5px; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1 class="success">日报已发送！</h1>
                        <p>日报内容已发送到企业微信。</p>
                        <h2>日报内容预览：</h2>
                        <pre>{report_content}</pre>
                    </div>
                </body>
            </html>
            """)
        
        # 否则直接显示日报内容
        return HTMLResponse(content=f"""
        <html>
            <head>
                <title>婴儿日报 - {date}</title>
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                    .container {{ max-width: 600px; margin: 0 auto; }}
                    h1 {{ color: #2c3e50; }}
                    pre {{ white-space: pre-wrap; background: #f5f5f5; padding: 15px; border-radius: 5px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>婴儿日报</h1>
                    <pre>{report_content}</pre>
                </div>
            </body>
        </html>
        """)
    except Exception as e:
        return HTMLResponse(content=f"<h1>生成日报时出错</h1><p>{str(e)}</p>", status_code=500)

@app.get("/report-link", response_class=HTMLResponse)
async def get_report_link():
    """获取今日日报链接的API端点"""
    try:
        # 生成今天的日期和token
        today = datetime.now().date().strftime('%Y-%m-%d')
        token = hashlib.md5(f"baby_report_{today}".encode()).hexdigest()[:10]
        
        # 构建链接
        base_url = f"http://{APP_HOST}:{APP_PORT}"
        view_link = f"{base_url}/daily-report?date={today}&token={token}"
        send_link = f"{base_url}/daily-report?date={today}&token={token}&user_id="
        
        return HTMLResponse(content=f"""
        <html>
            <head>
                <title>婴儿日报链接</title>
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                    .container {{ max-width: 600px; margin: 0 auto; }}
                    h1 {{ color: #2c3e50; }}
                    .link-box {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                    .link {{ word-break: break-all; }}
                    label {{ display: block; margin-bottom: 5px; font-weight: bold; }}
                    input {{ width: 100%; padding: 8px; margin-bottom: 10px; }}
                    button {{ background: #3498db; color: white; border: none; padding: 10px 15px; border-radius: 5px; cursor: pointer; }}
                    button:hover {{ background: #2980b9; }}
                </style>
                <script>
                    function generatePersonalLink() {{
                        const userId = document.getElementById('userId').value;
                        if (userId) {{
                            const baseLink = "{send_link}";
                            const fullLink = baseLink + userId;
                            document.getElementById('personalLink').textContent = fullLink;
                            document.getElementById('personalLinkBox').style.display = 'block';
                        }}
                    }}
                </script>
            </head>
            <body>
                <div class="container">
                    <h1>婴儿日报链接</h1>
                    
                    <h2>查看今日日报</h2>
                    <div class="link-box">
                        <p>点击下面的链接查看今日日报：</p>
                        <p><a href="{view_link}" target="_blank" class="link">{view_link}</a></p>
                    </div>
                    
                    <h2>发送日报到企业微信</h2>
                    <div>
                        <p>输入用户ID，生成发送链接：</p>
                        <input type="text" id="userId" placeholder="输入企业微信用户ID，如：ShenChaoSong">
                        <button onclick="generatePersonalLink()">生成链接</button>
                        
                        <div id="personalLinkBox" style="display: none;" class="link-box">
                            <p>点击下面的链接将今日日报发送到该用户的企业微信：</p>
                            <p><a href="#" id="personalLink" target="_blank" class="link"></a></p>
                        </div>
                    </div>
                </div>
            </body>
        </html>
        """)
    except Exception as e:
        return HTMLResponse(content=f"<h1>生成链接时出错</h1><p>{str(e)}</p>", status_code=500)

if __name__ == '__main__':
    # 启动FastAPI应用
    uvicorn.run("app:app", host=APP_HOST, port=int(APP_PORT), reload=True) 