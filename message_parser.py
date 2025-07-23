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
        '次数': r'(\d+)\s*(次|遍|回)',
        '时长': r'(\d+)\s*(分钟|小时|秒)',
        '温度': r'(\d+\.?\d*)\s*(度|℃)',
        '毫升': r'(\d+)\s*(毫升|ml|ML)',
        '一侧': r'(一侧|左侧|右侧|一边|左边|右边)',
        '量词': r'(一|二|三|四|五|六|七|八|九|十|半|整)\s*(坨|块|团|次|片)'
    }
    
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
        
    def parse_message(self, message: str) -> Optional[BabyRecord]:
        """解析消息内容，提取婴儿记录信息"""
        if not message or len(message) < 3:
            return None
            
        # 提取时间信息
        record_time = self._extract_time(message)
        
        # 提取记录类型
        record_type = self._extract_record_type(message)
        if not record_type:
            record_type = '其他'
        
        # 提取数量信息
        amount = self._extract_amount(message, record_type)
        
        # 创建记录
        return BabyRecord(
            record_time=record_time,
            record_type=record_type,
            amount=amount,
            description=message
        )
    
    def _extract_time(self, message: str) -> datetime:
        """从消息中提取时间信息"""
        now = datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # 尝试匹配常见的时间表达方式
        time_patterns = [
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
        
        for pattern, time_func in time_patterns:
            match = re.search(pattern, message)
            if match:
                try:
                    return time_func(match)
                except (ValueError, IndexError):
                    continue
        
        # 如果没有找到时间信息，默认使用当前时间
        return now
    
    def _extract_record_type(self, message: str) -> str:
        """从消息中提取记录类型"""
        # 分词处理
        words = jieba.lcut(message)
        
        # 根据关键词判断记录类型
        for record_type, keywords in self.TYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in words or keyword in message:
                    return record_type
        
        return None
    
    def _extract_amount(self, message: str, record_type: str) -> Optional[str]:
        """从消息中提取数量信息"""
        # 根据记录类型选择合适的数量提取模式
        if record_type == '吃':
            # 尝试提取毫升数或者一侧信息
            for pattern_name in ['毫升', '一侧', '次数']:
                pattern = self.AMOUNT_PATTERNS[pattern_name]
                match = re.search(pattern, message)
                if match:
                    if pattern_name == '毫升':
                        return f"{match.group(1)}毫升"
                    elif pattern_name == '一侧':
                        return match.group(1)
                    else:
                        return f"{match.group(1)}次"
        
        elif record_type == '大便' or record_type == '小便':
            # 尝试提取次数或量词
            for pattern_name in ['次数', '量词']:
                pattern = self.AMOUNT_PATTERNS[pattern_name]
                match = re.search(pattern, message)
                if match:
                    if pattern_name == '次数':
                        return f"{match.group(1)}次"
                    else:
                        return f"{match.group(1)}{match.group(2)}"
        
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