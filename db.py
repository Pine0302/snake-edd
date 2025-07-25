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
                amount_unit VARCHAR(20),
                description TEXT,
                is_deleted TINYINT(1) DEFAULT 0 COMMENT '是否删除：0-未删除，1-已删除',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
            self.cursor.execute(create_table_sql)
            
            # 检查是否需要添加is_deleted字段
            try:
                check_column_sql = """
                SELECT COUNT(*) as count FROM information_schema.columns 
                WHERE table_schema = DATABASE() 
                AND table_name = 'baby_records' 
                AND column_name = 'is_deleted'
                """
                self.cursor.execute(check_column_sql)
                result = self.cursor.fetchone()
                if result and result['count'] == 0:
                    # 添加is_deleted字段
                    alter_table_sql = """
                    ALTER TABLE baby_records 
                    ADD COLUMN is_deleted TINYINT(1) DEFAULT 0 COMMENT '是否删除：0-未删除，1-已删除'
                    """
                    self.cursor.execute(alter_table_sql)
                    print("已添加is_deleted字段到baby_records表")
            except Exception as e:
                print(f"检查字段错误: {e}")
                
            # 检查是否需要添加amount_unit字段
            try:
                check_column_sql = """
                SELECT COUNT(*) as count FROM information_schema.columns 
                WHERE table_schema = DATABASE() 
                AND table_name = 'baby_records' 
                AND column_name = 'amount_unit'
                """
                self.cursor.execute(check_column_sql)
                result = self.cursor.fetchone()
                if result and result['count'] == 0:
                    # 添加amount_unit字段
                    alter_table_sql = """
                    ALTER TABLE baby_records 
                    ADD COLUMN amount_unit VARCHAR(20) AFTER amount
                    """
                    self.cursor.execute(alter_table_sql)
                    print("已添加amount_unit字段到baby_records表")
                    
                    # 更新现有数据，将amount字段中的单位提取到amount_unit字段
                    update_sql = """
                    UPDATE baby_records 
                    SET 
                        amount_unit = CASE
                            WHEN amount LIKE '%毫升%' THEN '毫升'
                            WHEN amount LIKE '%次%' THEN '次'
                            WHEN amount LIKE '%分钟%' THEN '分钟'
                            WHEN amount LIKE '%小时%' THEN '小时'
                            WHEN amount LIKE '%℃%' THEN '℃'
                            ELSE NULL
                        END,
                        amount = CASE
                            WHEN amount LIKE '%毫升%' THEN SUBSTRING_INDEX(amount, '毫升', 1)
                            WHEN amount LIKE '%次%' THEN SUBSTRING_INDEX(amount, '次', 1)
                            WHEN amount LIKE '%分钟%' THEN SUBSTRING_INDEX(amount, '分钟', 1)
                            WHEN amount LIKE '%小时%' THEN SUBSTRING_INDEX(amount, '小时', 1)
                            WHEN amount LIKE '%℃%' THEN SUBSTRING_INDEX(amount, '℃', 1)
                            ELSE amount
                        END
                    WHERE amount IS NOT NULL AND amount_unit IS NULL
                    """
                    self.cursor.execute(update_sql)
                    updated_rows = self.cursor.rowcount
                    print(f"已更新 {updated_rows} 条记录的数量单位")
            except Exception as e:
                print(f"检查或更新字段错误: {e}")
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"初始化数据库错误: {e}")
            return False
        finally:
            self.close()
    
    def insert_record(self, record_time, record_type, amount=None, amount_unit=None, description=None):
        """插入一条婴儿记录"""
        try:
            self.connect()
            
            # 检查是否存在相同时间和类型的记录
            check_sql = """
            SELECT id, amount, amount_unit, description FROM baby_records 
            WHERE record_time = %s AND record_type = %s AND is_deleted = 0
            """
            self.cursor.execute(check_sql, (record_time, record_type))
            existing_record = self.cursor.fetchone()
            
            if existing_record:
                # 存在相同记录，进行更新
                update_sql = """
                UPDATE baby_records 
                SET amount = %s, amount_unit = %s, description = %s 
                WHERE id = %s
                """
                self.cursor.execute(update_sql, (amount, amount_unit, description, existing_record['id']))
                self.conn.commit()
                return {
                    'id': existing_record['id'],
                    'is_update': True,
                    'old_amount': existing_record['amount'],
                    'old_amount_unit': existing_record['amount_unit'],
                    'old_description': existing_record['description']
                }
            else:
                # 不存在相同记录，插入新记录
                sql = """
                INSERT INTO baby_records (record_time, record_type, amount, amount_unit, description)
                VALUES (%s, %s, %s, %s, %s)
                """
                self.cursor.execute(sql, (record_time, record_type, amount, amount_unit, description))
                self.conn.commit()
                return {
                    'id': self.cursor.lastrowid,
                    'is_update': False
                }
        except Exception as e:
            print(f"插入记录错误: {e}")
            return None
        finally:
            self.close()
            
    def delete_record(self, record_time, record_type):
        """删除一条婴儿记录（标记为已删除）"""
        try:
            self.connect()
            
            # 查找匹配的记录
            find_sql = """
            SELECT id, amount, amount_unit, description FROM baby_records 
            WHERE record_time = %s AND record_type = %s AND is_deleted = 0
            """
            self.cursor.execute(find_sql, (record_time, record_type))
            record = self.cursor.fetchone()
            
            if not record:
                print(f"未找到要删除的记录: {record_time}, {record_type}")
                return None
            
            # 标记记录为已删除
            delete_sql = """
            UPDATE baby_records SET is_deleted = 1 WHERE id = %s
            """
            self.cursor.execute(delete_sql, (record['id'],))
            self.conn.commit()
            
            return {
                'id': record['id'],
                'amount': record['amount'],
                'amount_unit': record['amount_unit'],
                'description': record['description']
            }
        except Exception as e:
            print(f"删除记录错误: {e}")
            return None
        finally:
            self.close()
            
    def get_records(self, start_date=None, end_date=None, record_type=None, limit=100):
        """获取婴儿记录"""
        try:
            self.connect()
            sql = "SELECT * FROM baby_records WHERE is_deleted = 0"
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
            
    def get_daily_records(self, date):
        """获取指定日期的所有记录，按记录类型分组"""
        try:
            self.connect()
            
            # 计算日期的开始和结束时间
            start_date = f"{date} 00:00:00"
            end_date = f"{date} 23:59:59"
            
            # 获取所有记录
            sql = """
            SELECT * FROM baby_records 
            WHERE is_deleted = 0 
            AND record_time >= %s 
            AND record_time <= %s 
            ORDER BY record_type, record_time
            """
            self.cursor.execute(sql, (start_date, end_date))
            records = self.cursor.fetchall()
            
            # 按记录类型分组
            grouped_records = {}
            for record in records:
                record_type = record['record_type']
                if record_type not in grouped_records:
                    grouped_records[record_type] = []
                grouped_records[record_type].append(record)
            
            return grouped_records
        except Exception as e:
            print(f"获取日期记录错误: {e}")
            return {}
        finally:
            self.close()

# 创建数据库实例
db = Database() 