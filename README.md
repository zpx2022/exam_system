# 在线考试系统测试部署文档

## 1. 环境要求

- **虚拟化平台**：VMware Workstation
- **操作系统**：Ubuntu 24.04.3 
  - **下载地址**：https://releases.ubuntu.com/24.04.3/ubuntu-24.04.3-live-server-amd64.iso

## 2. 测试部署目录结构

```
test_deployment/
├── .env                # 环境变量配置
├── nginx.conf          # Nginx配置文件
├── requirements.txt    # Python依赖包
├── manage.py           # Django管理脚本
├── init_all.py         # 初始化脚本
├── apps/               # Django应用模块
├── backend/            # 后端配置
├── dist/               # 前端构建产物
├── media/              # 媒体文件目录
├── middleware/         # 自定义中间件
└── utils/              # 工具模块
```

## 3. 快速部署

### 3.1 安装环境
```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装必要软件
sudo apt install -y nginx mysql-server redis-server python3-dev default-libmysqlclient-dev build-essential
```

### 3.2 部署项目
```bash
# 创建项目目录
sudo mkdir -p /var/www/exam_system
sudo chown $USER:$USER /var/www/exam_system

# 复制项目文件
cp -r test_deployment/* /var/www/exam_system/

# 进入项目目录
cd /var/www/exam_system

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3.3 数据库配置
```bash
# 运行初始化脚本
python init_all.py
```

### 3.4 配置SSL证书
```bash
# 创建SSL证书目录
sudo mkdir -p /etc/nginx/cert

# 生成自签名证书
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/cert/server.key \
    -out /etc/nginx/cert/server.crt
```

### 3.5 启动服务
```bash
# 启动Gunicorn
gunicorn --bind 127.0.0.1:8000 --workers 5 backend.wsgi:application &

# 配置Nginx
sudo cp nginx.conf /etc/nginx/sites-available/exam_system
sudo ln -s /etc/nginx/sites-available/exam_system /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx
```

## 4. 验证部署

### 4.1 检查服务
```bash
# 检查服务状态
sudo systemctl status nginx
sudo systemctl status mysql
sudo systemctl status redis

# 检查端口
sudo netstat -tlnp | grep -E ':(80|443|8000|3306|6379)'
```

### 4.2 访问测试
https://Ubuntu虚拟机IP

