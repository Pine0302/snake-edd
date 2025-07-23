#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from message_parser import message_parser

def test_message_parser():
    """测试消息解析器"""
    test_messages = [
        "今日9点30分拉屎一坨",
        "下午2点30吃妈奶一边",
        "早上8点体温37.5度",
        "晚上10点吃奶粉120毫升",
        "今天下午3点吃药2次",
        "宝宝今天9点睡觉睡了2小时",
        "中午12点吃辅食半碗",
        "今天早上7点尿尿一次",
        "下午4点宝宝拉了大便",
        "晚上8点小便了",
        "今天上午10点宝宝拉粑粑了",
        "下午3点15分宝宝尿湿了尿布"
    ]
    
    print("===== 消息解析测试 =====")
    for message in test_messages:
        print(f"\n原始消息: {message}")
        record = message_parser.parse_message(message)
        
        if record:
            print(f"解析结果:")
            print(f"- 时间: {record.record_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"- 类型: {record.record_type}")
            print(f"- 数量: {record.amount}")
            print(f"- 描述: {record.description}")
        else:
            print("解析失败")

if __name__ == "__main__":
    test_message_parser() 