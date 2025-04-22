# Fast OCR

A web application for OCR built with FastAPI (backend) and React (frontend), using Tongyi Qianwen API for recognition and RabbitMQ for asynchronous processing.

## Project Structure

```
fast_ocr/
├── backend/        # FastAPI application
│   ├── config/     # 配置目录，存储配置文件
│   ├── main.py     # 主API服务
│   ├── worker.py   # OCR worker (RabbitMQ消费者)
│   ├── config.py   # 配置管理模块
│   ├── config_tool.py # 配置管理工具
│   ├── start_workers.py # 多进程worker启动脚本
│   ├── test_batch_upload.py # 批量上传测试脚本
│   └── requirements.txt
├── frontend/       # React application
│   └── (React project files will go here)
├── persistent_data/ # 持久化数据存储
│   ├── uploads/    # 上传的图片
│   └── results/    # OCR结果
├── .gitignore
└── README.md
```

## Setup

### 前提条件

1. Python 3.7+
2. Node.js 14+
3. RabbitMQ服务 (可以使用Docker)

### RabbitMQ

使用Docker启动RabbitMQ:

```bash
# 拉取镜像
docker pull rabbitmq:3-management

# 启动容器
docker run -d --name fast-ocr-rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```

RabbitMQ管理界面可以在 http://localhost:15672 访问 (用户名/密码: guest/guest)

### Backend

1.  Navigate to the `backend` directory:
    ```bash
    cd backend
    ```
2.  Create a virtual environment (optional but recommended):
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

4.  配置系统设置：
    
    可以使用配置工具设置通义千问API密钥和其他设置：
    ```bash
    # 查看当前配置
    python config_tool.py --show
    
    # 交互式更新配置
    python config_tool.py --update
    
    # 直接设置API Key
    python config_tool.py --set api_key YOUR_API_KEY
    
    # 直接设置多项配置
    python config_tool.py --set api_key YOUR_API_KEY --set api_url YOUR_API_URL
    ```
    
    配置文件存储在 `config/app_config.json`，包括以下设置：
    - `api_key`: 通义千问API密钥
    - `api_url`: 通义千问API URL
    - `model_name`: 使用的模型名称
    - `rabbitmq_host`: RabbitMQ服务器地址
    - `rabbitmq_port`: RabbitMQ端口
    - `rabbitmq_queue`: 使用的队列名称
    - `worker_concurrency`: Worker进程并发处理数量（默认3）

5.  Run the FastAPI server:
    ```bash
    uvicorn main:app --reload --port 8080
    ```
    The API will be available at `http://127.0.0.1:8080`.

6.  启动OCR worker（两种方式）:
    ```bash
    cd backend
    # 激活相同的虚拟环境
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    
    # 方式1：单进程worker
    python worker.py
    
    # 方式2：多进程worker（推荐用于生产环境）
    python start_workers.py  # 使用配置文件中的并发设置
    # 或指定进程数量
    python start_workers.py -n 5  # 启动5个worker进程
    ```

### Frontend

1.  Navigate to the `frontend` directory:
    ```bash
    cd frontend
    ```
2.  Install dependencies:
    ```bash
    npm install
    ```
3.  Start the development server:
    ```bash
    npm run dev
    ```
    The frontend will be available at `http://localhost:5173`.

## API使用流程

1. 确保通过配置工具或`POST /config`接口配置通义千问API Key
2. 使用`POST /upload`上传图片文件，获取任务ID
3. 使用`GET /result/{task_id}`查询处理结果
4. 使用`GET /history`查看历史记录

## 批量处理与并发

系统支持批量上传和并发处理：

1. **批量上传图片**:
   ```bash
   # 使用curl批量上传
   curl -X POST -F "files=@image1.jpg" -F "files=@image2.jpg" -F "files=@image3.jpg" http://localhost:8080/upload
   
   # 或使用测试脚本
   python backend/test_batch_upload.py -n 5  # 上传5张图片
   ```

2. **并发处理控制**:
   - 在`config/app_config.json`中设置`worker_concurrency`值
   - 或启动多个worker进程以获得更高的并行度

3. **测试并行处理性能**:
   ```bash
   # 指定并发度及图片数量
   python backend/test_batch_upload.py -n 10 -s http://localhost:8080 -d /path/to/images
   ```

## Features

*   图片上传 (支持单张/批量)
*   使用通义千问API进行OCR识别
*   左右分栏显示原图和识别结果
*   通过UI配置API参数
*   识别历史记录
*   使用RabbitMQ进行异步处理
*   配置持久化存储
*   并发OCR处理（单进程多任务或多进程）
*   清晰的目录结构（uploads目录存储原图，results目录存储结果） 