import pymysql
from config import DB_CONFIG

class Database:
    def __init__(self):
        self.conn = None
        self.cursor = None
    
    def connect(self):
        """连接到数据库"""
        try:
            self.conn = pymysql.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor(pymysql.cursors.DictCursor)
            return True
        except Exception as e:
            print(f"数据库连接错误: {e}")
            return False
    
    def close(self):
        """关闭数据库连接"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
    
    def init_db(self):
        """初始化数据库表结构"""
        try:
            self.connect()
            
            # 创建婴儿记录表
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS baby_records (
                id INT AUTO_INCREMENT PRIMARY KEY,
                record_time DATETIME NOT NULL,
                record_type ENUM('吃', '大便', '小便', '睡', '体温', '吃药', '其他') NOT NULL,
                amount VARCHAR(50),
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
            self.cursor.execute(create_table_sql)
            self.conn.commit()
            return True
        except Exception as e:
            print(f"初始化数据库错误: {e}")
            return False
        finally:
            self.close()
    
    def insert_record(self, record_time, record_type, amount=None, description=None):
        """插入一条婴儿记录"""
        try:
            self.connect()
            sql = """
            INSERT INTO baby_records (record_time, record_type, amount, description)
            VALUES (%s, %s, %s, %s)
            """
            self.cursor.execute(sql, (record_time, record_type, amount, description))
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            print(f"插入记录错误: {e}")
            return None
        finally:
            self.close()
    
    def get_records(self, start_date=None, end_date=None, record_type=None, limit=100):
        """获取婴儿记录"""
        try:
            self.connect()
            sql = "SELECT * FROM baby_records WHERE 1=1"
            params = []
            
            if start_date:
                sql += " AND record_time >= %s"
                params.append(start_date)
            
            if end_date:
                sql += " AND record_time <= %s"
                params.append(end_date)
            
            if record_type:
                sql += " AND record_type = %s"
                params.append(record_type)
            
            sql += " ORDER BY record_time DESC LIMIT %s"
            params.append(limit)
            
            self.cursor.execute(sql, params)
            return self.cursor.fetchall()
        except Exception as e:
            print(f"获取记录错误: {e}")
            return []
        finally:
            self.close()

# 创建数据库实例
db = Database() 