# 婴儿日常记录系统

这是一个通过向企业微信自定义应用发送婴儿日常记录（吃喝拉撒等）并存储到数据库的应用程序。

## 功能特点

- 通过企业微信群接收消息
- 自动解析消息内容，识别时间、类型和数量
- 支持多种记录类型：吃、大便、小便、睡、体温、吃药等
- 数据存储到MySQL数据库
- 提供API接口查询历史记录
- 基于FastAPI框架，提供自动生成的API文档

## 系统要求

- Python 3.10+
- MySQL 5.7+
- Docker (可选，用于容器化部署)

## 安装步骤

### 使用Docker（推荐）

1. 克隆代码仓库

```bash
git clone https://github.com/yourusername/baby-records.git
cd baby-records
```

2. 配置环境变量

```bash
cp env.example .env
# 编辑 .env 文件，填写企业微信和数据库配置
```

3. 初始化外置MySQL数据库

在您的MySQL服务器上创建数据库和表：

```sql
CREATE DATABASE baby_records CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE baby_records;

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
```

4. 启动应用

```bash
docker-compose up -d
```

### 手动安装

1. 克隆代码仓库

```bash
git clone https://github.com/yourusername/baby-records.git
cd baby-records
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

3. 配置环境变量

创建 `.env` 文件，参考 `env.example` 填写相关配置：

```bash
cp env.example .env
# 编辑 .env 文件，填写企业微信和数据库配置
```

4. 初始化数据库

在您的MySQL服务器上创建数据库和表（与Docker方式相同）。

5. 启动应用

```bash
uvicorn app:app --host 0.0.0.0 --port 5000
```

## 使用方法

1. 配置企业微信回调

在企业微信管理后台，配置应用的接收消息URL：

- 登录企业微信管理后台 (https://work.weixin.qq.com/wework_admin/)
- 进入"应用管理" -> 找到您的自建应用(AgentId 1000002)
- 点击该应用，进入应用详情页
- 找到"接收消息"设置区域
- 开启"接收消息"功能，并填写以下信息：
  - URL：填写 http://your-server-ip:5000/wechat/callback (替换为您服务器的实际IP)
  - Token：自定义一个Token值（与.env文件中的TOKEN保持一致）
  - EncodingAESKey：点击"随机生成"按钮获取，并复制到.env文件的ENCODING_AES_KEY中

2. 在企业微信群中发送消息

示例消息格式：
- "今日9点30分拉屎一坨" (记录大便)
- "下午2点30吃妈奶一边" (记录吃奶)
- "早上8点体温37.5度" (记录体温)
- "今天早上7点尿尿一次" (记录小便)
- "下午4点宝宝拉了大便" (记录大便)

3. 访问API文档

应用启动后，可以通过以下地址访问自动生成的API文档：

```
http://your-server-ip:5000/docs
```

## 记录类型说明

系统支持以下几种记录类型：

1. **吃** - 关键词：吃、喝、奶、母乳、奶粉、辅食、饭、餐、牛奶、水
2. **大便** - 关键词：大便、拉、拉屎、便便、屎、排便、粑粑、臭臭、拉了、便秘
3. **小便** - 关键词：小便、尿、尿尿、尿布、撒尿、尿了
4. **睡** - 关键词：睡、睡觉、午睡、小睡、休息
5. **体温** - 关键词：体温、温度、发热、发烧
6. **吃药** - 关键词：吃药、药、服药、用药
7. **其他** - 无法识别为以上类型的记录

## API接口

### 获取记录列表

```
GET /api/records
```

参数：
- start_date: 开始日期（可选）
- end_date: 结束日期（可选）
- type: 记录类型（可选，如"吃"、"大便"、"小便"等）
- limit: 返回记录数量限制（可选，默认100）

### 测试消息解析

```
POST /api/test_parser
Content-Type: application/json

{
    "message": "今天下午3点吃奶一次"
}
```

## 项目结构

```
baby-records/
├── app.py           # 主应用程序
├── config.py        # 配置文件
├── db.py            # 数据库操作
├── message_parser.py # 消息解析器
├── wechat.py        # 企业微信API
├── requirements.txt # 项目依赖
├── Dockerfile       # Docker配置
├── docker-compose.yml # Docker Compose配置
├── start.sh         # 启动脚本
├── init-db/         # 数据库初始化脚本
└── env.example      # 环境变量示例文件
```

## 注意事项

1. 企业微信回调需要服务器有公网IP或域名
2. 请确保企业微信应用的Secret、Token和EncodingAESKey安全保存
3. 数据库需要定期备份，保护重要数据
4. 使用外置MySQL时，请确保应用容器能够访问到MySQL服务器
5. 如果MySQL服务器有防火墙，请确保开放3306端口给应用服务器

## 许可证

MIT 