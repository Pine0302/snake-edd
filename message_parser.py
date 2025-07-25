import re
from datetime import datetime, timedelta
import jieba
from pydantic import BaseModel
from typing import Optional

class BabyRecord(BaseModel):
    """婴儿记录数据模型"""
    record_time: datetime
    record_type: str
    amount: Optional[str] = None
    description: Optional[str] = None
    is_delete_command: bool = False

class MessageParser:
    """企业微信消息解析器"""
    
    # 记录类型关键词映射
    TYPE_KEYWORDS = {
        '吃': ['吃', '喝', '奶', '母乳', '奶粉', '辅食', '饭', '餐', '牛奶', '水'],
        '大便': ['大便', '拉', '拉屎', '便便', '屎', '排便', '粑粑', '臭臭', '拉了', '便秘'],
        '小便': ['小便', '尿', '尿尿', '尿布', '撒尿', '尿了'],
        '睡': ['睡', '睡觉', '午睡', '小睡', '休息'],
        '体温': ['体温', '温度', '发热', '发烧'],
        '吃药': ['吃药', '药', '服药', '用药'],
    }
    
    # 数量关键词正则表达式
    AMOUNT_PATTERNS = {
        '次数': r'(\d+)\s*(次|遍|回|坨|块|团)',
        '时长': r'(\d+)\s*(分钟|小时|秒)',
        '温度': r'(\d+\.?\d*)\s*(度|℃)',
        '毫升': r'(\d+)\s*(毫升|ml|ML)',
        '一侧': r'(一侧|左侧|右侧|一边|左边|右边)',
        '量词': r'(一|二|三|四|五|六|七|八|九|十|半|整)\s*(坨|块|团|次|片)'
    }
    
    # 删除指令正则表达式
    DELETE_PATTERN = r'(删除|去除|删掉|去掉).*?(今天|昨天|前天)?.*?(\d{1,2})[点时:：](\d{1,2})?分?.*?(吃|大便|小便|睡|体温|吃药)'
    
    def __init__(self):
        # 加载结巴分词词典
        jieba.add_word('拉屎')
        jieba.add_word('吃奶')
        jieba.add_word('妈奶')
        jieba.add_word('奶粉')
        jieba.add_word('辅食')
        jieba.add_word('尿尿')
        jieba.add_word('大便')
        jieba.add_word('小便')
        jieba.add_word('拉小便')
        jieba.add_word('拉大便')
        
        # 添加删除相关词汇
        jieba.add_word('删除')
        jieba.add_word('去除')
        jieba.add_word('删掉')
        jieba.add_word('去掉')
        
        # 添加时间表达方式
        jieba.add_word('点半')
        jieba.add_word('点十分')
        jieba.add_word('点二十分')
        jieba.add_word('点三十分')
        jieba.add_word('点四十分')
        jieba.add_word('点五十分')
        
        # 添加中文数字时间
        for h in ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十', '十一', '十二']:
            jieba.add_word(f'{h}点')
            jieba.add_word(f'{h}点半')
            for m in ['十', '二十', '三十', '四十', '五十']:
                jieba.add_word(f'{h}点{m}分')
                for d in ['一', '二', '三', '四', '五', '六', '七', '八', '九']:
                    if m == '十':
                        jieba.add_word(f'{h}点{m}{d}分')
                    else:
                        jieba.add_word(f'{h}点{m}{d}分')

        
    def parse_message(self, message: str) -> Optional[BabyRecord]:
        """解析消息内容，提取婴儿记录信息"""
        if not message or len(message) < 3:
            return None
            
        # 检查是否是删除指令
        is_delete_command = False
        
        # 方法1：使用正则表达式检测
        delete_match = re.search(self.DELETE_PATTERN, message)
        if delete_match:
            print(f"通过正则表达式检测到删除指令: {delete_match.group(0)}", flush=True)
            print(f"删除指令匹配组: {delete_match.groups()}", flush=True)
            is_delete_command = True
        
        # 方法2：简单关键词检测
        delete_keywords = ['删除', '去除', '删掉', '去掉']
        if any(keyword in message for keyword in delete_keywords):
            print(f"通过关键词检测到删除指令，包含关键词: {[k for k in delete_keywords if k in message]}", flush=True)
            # 直接将包含删除关键词的消息识别为删除指令
            is_delete_command = True
            
        # 提取时间信息
        record_time = self._extract_time(message)
        
        # 提取记录类型
        record_type = self._extract_record_type(message)
        if not record_type:
            record_type = '其他'
        
        # 提取数量信息
        amount = self._extract_amount(message, record_type)
        
        # 打印调试信息
        print(f"解析结果: 时间={record_time}, 类型={record_type}, 是否删除={is_delete_command}", flush=True)
        
        # 创建记录
        return BabyRecord(
            record_time=record_time,
            record_type=record_type,
            amount=amount,
            description=message,
            is_delete_command=is_delete_command
        )
    
    def _extract_time(self, message: str) -> datetime:
        """从消息中提取时间信息"""
        now = datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # 打印调试信息
        print(f"提取时间信息，原始消息: '{message}'", flush=True)
        
        # 中文数字转阿拉伯数字的映射
        cn_num_map = {
            '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, 
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
            '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5,
            '6': 6, '7': 7, '8': 8, '9': 9
        }
        
        # 预处理消息，将中文数字转换为阿拉伯数字
        # 处理小时
        for cn_num, arab_num in cn_num_map.items():
            # 替换"三点"这种模式
            message = re.sub(f"{cn_num}[点时]", f"{arab_num}点", message)
        
        # 处理分钟
        cn_minute_patterns = [
            # 十分
            (r'[点时][十]分', lambda m: '点10分'),
            # 十一至十九分
            (r'[点时]十([一二三四五六七八九])[分]', 
             lambda m: f"点1{cn_num_map.get(m.group(1), '')}分"),
            # 二十分
            (r'[点时][二]?[十][分]', lambda m: '点20分'),
            # 二十一至二十九分
            (r'[点时][二][十]([一二三四五六七八九])[分]', 
             lambda m: f"点2{cn_num_map.get(m.group(1), '')}分"),
            # 三十分
            (r'[点时][三]?[十][分]', lambda m: '点30分'),
            # 三十一至三十九分
            (r'[点时][三][十]([一二三四五六七八九])[分]', 
             lambda m: f"点3{cn_num_map.get(m.group(1), '')}分"),
            # 四十分
            (r'[点时][四]?[十][分]', lambda m: '点40分'),
            # 四十一至四十九分
            (r'[点时][四][十]([一二三四五六七八九])[分]', 
             lambda m: f"点4{cn_num_map.get(m.group(1), '')}分"),
            # 五十分
            (r'[点时][五]?[十][分]', lambda m: '点50分'),
            # 五十一至五十九分
            (r'[点时][五][十]([一二三四五六七八九])[分]', 
             lambda m: f"点5{cn_num_map.get(m.group(1), '')}分"),
            # 一至九分
            (r'[点时]([一二三四五六七八九])[分]', 
             lambda m: f"点{cn_num_map.get(m.group(1), '')}分"),
        ]
        
        # 应用中文分钟模式替换
        for pattern, replace_func in cn_minute_patterns:
            message = re.sub(pattern, replace_func, message)
        
        print(f"预处理后的消息: '{message}'", flush=True)
        
        # 尝试匹配常见的时间表达方式
        time_patterns = [
            # 今日/今天 HH点半 格式
            (r'今[日天]\s*(\d{1,2})[点时][半]', lambda m: today + timedelta(hours=int(m.group(1)), minutes=30)),
            # 上午/早上/早晨 HH点半 格式
            (r'(上午|早上|早晨)\s*(\d{1,2})[点时][半]', lambda m: today + timedelta(hours=int(m.group(2)), minutes=30)),
            # 下午/傍晚 HH点半 格式 (加12小时)
            (r'(下午|傍晚)\s*(\d{1,2})[点时][半]', lambda m: today + timedelta(hours=int(m.group(2)) + (0 if int(m.group(2)) >= 12 else 12), minutes=30)),
            # 晚上 HH点半 格式 (加12小时)
            (r'(晚上|夜里|夜间)\s*(\d{1,2})[点时][半]', lambda m: today + timedelta(hours=int(m.group(2)) + (0 if int(m.group(2)) >= 12 else 12), minutes=30)),
            # HH点半 格式
            (r'(\d{1,2})[点时][半]', lambda m: today + timedelta(hours=int(m.group(1)), minutes=30)),
            
            # 今日/今天 HH:MM 格式
            (r'今[日天]\s*(\d{1,2})[点时:：](\d{1,2})?', lambda m: today + timedelta(hours=int(m.group(1)), minutes=int(m.group(2) or 0))),
            # 上午/早上/早晨 HH:MM 格式
            (r'(上午|早上|早晨)\s*(\d{1,2})[点时:：](\d{1,2})?', lambda m: today + timedelta(hours=int(m.group(2)), minutes=int(m.group(3) or 0))),
            # 下午/傍晚 HH:MM 格式 (加12小时)
            (r'(下午|傍晚)\s*(\d{1,2})[点时:：](\d{1,2})?', lambda m: today + timedelta(hours=int(m.group(2)) + (0 if int(m.group(2)) >= 12 else 12), minutes=int(m.group(3) or 0))),
            # 晚上 HH:MM 格式 (加12小时)
            (r'(晚上|夜里|夜间)\s*(\d{1,2})[点时:：](\d{1,2})?', lambda m: today + timedelta(hours=int(m.group(2)) + (0 if int(m.group(2)) >= 12 else 12), minutes=int(m.group(3) or 0))),
            # HH:MM 格式
            (r'(\d{1,2})[点时:：](\d{1,2})?', lambda m: today + timedelta(hours=int(m.group(1)), minutes=int(m.group(2) or 0))),
            # HH点MM分 格式
            (r'(\d{1,2})[点时](\d{1,2})?分?', lambda m: today + timedelta(hours=int(m.group(1)), minutes=int(m.group(2) or 0))),
        ]
        
        for i, (pattern, time_func) in enumerate(time_patterns):
            match = re.search(pattern, message)
            if match:
                try:
                    extracted_time = time_func(match)
                    print(f"匹配到时间模式 {i+1}: '{pattern}', 提取时间: {extracted_time}", flush=True)
                    return extracted_time
                except (ValueError, IndexError) as e:
                    print(f"时间模式 {i+1} 处理异常: {e}", flush=True)
                    continue
        
        # 如果没有找到时间信息，默认使用当前时间
        print(f"未匹配到任何时间模式，使用当前时间: {now}", flush=True)
        return now
    
    def _extract_record_type(self, message: str) -> str:
        """从消息中提取记录类型"""
        # 分词处理
        words = jieba.lcut(message)
        print("分词结果:", flush=True)
        print(words, flush=True)
        print("原始消息:", flush=True)
        print(message, flush=True)

        # 根据关键词判断记录类型
        matched_types = []
        for record_type, keywords in self.TYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in words or keyword in message:
                    print(f"匹配到记录类型关键词: '{keyword}' -> {record_type}", flush=True)
                    matched_types.append(record_type)
                    break  # 找到一个关键词就跳出内循环
        
        # 如果找到多个类型，优先选择出现在消息前面的类型
        if matched_types:
            # 检查每个类型在消息中的位置
            type_positions = {}
            for record_type in matched_types:
                for keyword in self.TYPE_KEYWORDS[record_type]:
                    pos = message.find(keyword)
                    if pos != -1:
                        if record_type not in type_positions or pos < type_positions[record_type]:
                            type_positions[record_type] = pos
            
            # 按位置排序
            sorted_types = sorted(type_positions.items(), key=lambda x: x[1])
            if sorted_types:
                print(f"选择的记录类型: {sorted_types[0][0]}", flush=True)
                return sorted_types[0][0]
        
        print("未匹配到记录类型", flush=True)
        return None
    
    def _extract_amount(self, message: str, record_type: str) -> Optional[str]:
        """从消息中提取数量信息"""
        # 打印调试信息
        print(f"提取数量信息，记录类型: {record_type}, 消息: '{message}'", flush=True)
        
        # 根据记录类型选择合适的数量提取模式
        if record_type == '吃':
            # 尝试提取毫升数或者一侧信息
            for pattern_name in ['毫升', '一侧', '次数']:
                pattern = self.AMOUNT_PATTERNS[pattern_name]
                match = re.search(pattern, message)
                if match:
                    result = None
                    if pattern_name == '毫升':
                        result = f"{match.group(1)}毫升"
                    elif pattern_name == '一侧':
                        result = match.group(1)
                    else:
                        result = f"{match.group(1)}次"
                    print(f"匹配到数量模式 '{pattern_name}': {result}", flush=True)
                    return result
        
        elif record_type == '大便' or record_type == '小便':
            # 尝试提取次数或量词
            for pattern_name in ['次数', '量词']:
                pattern = self.AMOUNT_PATTERNS[pattern_name]
                match = re.search(pattern, message)
                if match:
                    result = None
                    if pattern_name == '次数':
                        result = f"{match.group(1)}次"
                    else:
                        result = f"{match.group(1)}{match.group(2)}"
                    print(f"匹配到数量模式 '{pattern_name}': {result}", flush=True)
                    return result
        
        elif record_type == '睡':
            # 尝试提取时长
            pattern = self.AMOUNT_PATTERNS['时长']
            match = re.search(pattern, message)
            if match:
                return f"{match.group(1)}{match.group(2)}"
        
        elif record_type == '体温':
            # 尝试提取温度
            pattern = self.AMOUNT_PATTERNS['温度']
            match = re.search(pattern, message)
            if match:
                return f"{match.group(1)}℃"
        
        # 默认返回None
        return None

# 创建消息解析器实例
message_parser = MessageParser() 