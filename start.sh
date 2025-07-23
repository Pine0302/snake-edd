#!/bin/bash

# 创建日志目录
mkdir -p logs

# 检查.env文件是否存在
if [ ! -f .env ]; then
    echo "未找到.env文件，正在从示例文件创建..."
    if [ -f env.example ]; then
        cp env.example .env
        echo "已创建.env文件，请编辑配置信息后重新运行此脚本"
        exit 1
    else
        echo "错误：未找到env.example文件"
        exit 1
    fi
fi

# 检查MySQL连接
echo "正在检查MySQL连接..."
DB_HOST=$(grep DB_HOST .env | cut -d '=' -f2)
DB_PORT=$(grep DB_PORT .env | cut -d '=' -f2)
DB_USER=$(grep DB_USER .env | cut -d '=' -f2)
DB_PASSWORD=$(grep DB_PASSWORD .env | cut -d '=' -f2)
DB_NAME=$(grep DB_NAME .env | cut -d '=' -f2)

# 尝试连接MySQL
echo "尝试连接MySQL数据库: $DB_HOST:$DB_PORT..."
if command -v mysql >/dev/null 2>&1; then
    mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" -e "SELECT 1" >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "MySQL连接成功！"
        
        # 检查数据库是否存在
        mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" -e "USE $DB_NAME" >/dev/null 2>&1
        if [ $? -ne 0 ]; then
            echo "数据库 $DB_NAME 不存在，正在创建..."
            mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" -e "CREATE DATABASE $DB_NAME CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            
            # 导入初始化SQL
            if [ -f init-db/init.sql ]; then
                echo "正在导入初始化SQL..."
                mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" < init-db/init.sql
            fi
        fi
    else
        echo "警告: 无法连接到MySQL数据库，请检查配置"
        echo "应用可能无法正常工作，除非您已手动创建了数据库"
    fi
else
    echo "警告: 未找到mysql命令，无法检查数据库连接"
    echo "请确保数据库已正确配置"
fi

# 启动Docker容器
echo "正在启动应用..."
docker-compose up -d

# 检查容器状态
echo "正在检查容器状态..."
sleep 5
docker-compose ps

echo "应用启动完成！"
echo "API文档地址: http://localhost:5000/docs"
echo "企业微信回调地址: http://your-server-ip:5000/wechat/callback" 