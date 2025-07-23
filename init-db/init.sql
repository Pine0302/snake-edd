-- 创建婴儿记录表
CREATE TABLE IF NOT EXISTS baby_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    record_time DATETIME NOT NULL,
    record_type ENUM('吃', '大便', '小便', '睡', '体温', '吃药', '其他') NOT NULL,
    amount VARCHAR(50),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建索引
CREATE INDEX idx_record_time ON baby_records(record_time);
CREATE INDEX idx_record_type ON baby_records(record_type);

-- 插入一些测试数据
INSERT INTO baby_records (record_time, record_type, amount, description)
VALUES
    (NOW() - INTERVAL 1 DAY, '吃', '120毫升', '吃奶粉120毫升'),
    (NOW() - INTERVAL 1 DAY - INTERVAL 3 HOUR, '大便', '一坨', '拉了一坨黄色的便便'),
    (NOW() - INTERVAL 1 DAY - INTERVAL 5 HOUR, '小便', '1次', '尿尿一次'),
    (NOW() - INTERVAL 2 DAY, '睡', '2小时', '午睡2小时'),
    (NOW() - INTERVAL 2 DAY - INTERVAL 6 HOUR, '体温', '36.5℃', '正常体温36.5度'),
    (NOW() - INTERVAL 3 DAY, '吃药', '1次', '吃了退烧药'); 