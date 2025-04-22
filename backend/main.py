from fastapi import FastAPI, HTTPException, File, UploadFile
import uvicorn
from pydantic import BaseModel
from typing import Dict, List, Optional
import shutil
import os
import uuid # For generating unique IDs
import json # For loading/saving JSON
import pika # For RabbitMQ
import time
import config # 导入配置模块

# --- 配置管理模型 --- 
class ApiConfig(BaseModel):
    api_key: Optional[str] = None
    api_url: Optional[str] = None
    model_name: Optional[str] = None
    rabbitmq_host: Optional[str] = None
    rabbitmq_port: Optional[str] = None
    rabbitmq_queue: Optional[str] = None

# --- Persistent Storage Directories ---
BASE_DATA_DIR = "persistent_data"
UPLOAD_DIR = os.path.join(BASE_DATA_DIR, "uploads")
RESULTS_DIR = os.path.join(BASE_DATA_DIR, "results")

# Create directories if they don't exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# --- FastAPI App ---
app = FastAPI(
    title="Fast OCR API",
    description="API for the Fast OCR application, handling image uploads and OCR results.",
    version="0.1.0",
)

@app.get("/")
async def read_root():
    return {"message": "Welcome to Fast OCR API"}

# --- Configuration Endpoints ---
@app.post("/config", status_code=200)
async def update_config(api_config: ApiConfig):
    """更新API配置并保存到配置文件"""
    # 将非None值提取到字典中
    update_values = {k: v for k, v in api_config.dict().items() if v is not None}
    
    # 使用配置模块更新配置
    updated_config = config.update_config(update_values)
    
    print(f"Configuration updated: {updated_config}")
    return {"message": "Configuration updated successfully."}

@app.get("/config")
async def get_config():
    """获取当前API配置"""
    # 从配置模块获取最新配置
    current_config = config.get_config()
    return current_config

# --- RabbitMQ Functions ---
def publish_to_rabbitmq(task_data: dict) -> bool:
    """
    Publishes a task to RabbitMQ queue.
    
    Args:
        task_data: Dictionary containing task information (task_id, file_path, etc.)
        
    Returns:
        bool: True if successful, False otherwise.
    """
    # 从配置获取RabbitMQ设置
    current_config = config.get_config()
    
    try:
        # Connect to RabbitMQ
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=current_config["rabbitmq_host"],
                port=int(current_config["rabbitmq_port"])
            )
        )
        channel = connection.channel()
        
        # Declare the queue (creates it if it doesn't exist)
        channel.queue_declare(queue=current_config["rabbitmq_queue"], durable=True)
        
        # Convert task data to JSON
        message_body = json.dumps(task_data)
        
        # Publish the message
        channel.basic_publish(
            exchange='',
            routing_key=current_config["rabbitmq_queue"],
            body=message_body,
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
                content_type='application/json'
            )
        )
        
        print(f"[x] Sent task {task_data['task_id']} to RabbitMQ")
        connection.close()
        return True
        
    except Exception as e:
        print(f"Error publishing to RabbitMQ: {e}")
        return False

# --- Image Upload Endpoint ---
@app.post("/upload")
async def upload_images(files: List[UploadFile] = File(...)):
    """Receives images, saves them, generates task IDs, and sends tasks to RabbitMQ."""
    if not files:
        raise HTTPException(status_code=400, detail="No files were uploaded.")
    
    # 获取当前配置
    current_config = config.get_config()
    
    if not current_config.get("api_key"):
        raise HTTPException(status_code=400, detail="API Key not configured.")

    tasks_info = []
    rabbitmq_failures = []

    for file in files:
        if not file.content_type or not file.content_type.startswith('image/'):
            print(f"Skipping non-image or invalid file: {file.filename}")
            continue

        try:
            # Generate a unique task ID
            task_id = str(uuid.uuid4())
            
            # Create a unique filename to avoid collisions
            file_extension = os.path.splitext(file.filename)[1]
            persistent_filename = f"{task_id}{file_extension}"
            persistent_file_path = os.path.join(UPLOAD_DIR, persistent_filename)

            # Save the uploaded file to the persistent location
            with open(persistent_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # Prepare task data - 只传递必要参数
            task_info = {
                "task_id": task_id,
                "original_filename": file.filename,
                "image_path": persistent_file_path,  # 修改为image_path，与worker.py一致
                "api_key": current_config["api_key"],  # 这个会发送给worker进行处理
                "status": "queued",
                "timestamp": time.time()
            }
            
            # Send to RabbitMQ
            if publish_to_rabbitmq(task_info):
                # 不再创建meta文件，让worker直接创建结果文件
                
                # Add to response
                tasks_info.append({
                    "task_id": task_id,
                    "filename": file.filename,
                    "status": "queued"
                })
            else:
                rabbitmq_failures.append(file.filename)
                # Leave the file, but don't add to successful tasks

        except Exception as e:
            print(f"Error processing file {file.filename}: {e}")
            # Could add to a failed list here for reporting back
        finally:
            await file.close()

    if not tasks_info and rabbitmq_failures:
        raise HTTPException(status_code=500, detail=f"Could not queue any tasks due to RabbitMQ connection issues.")
    elif not tasks_info:
        raise HTTPException(status_code=400, detail="No valid image files were processed.")

    # Return task IDs for the frontend
    response = {
        "message": f"Successfully queued {len(tasks_info)} images for OCR processing.",
        "tasks": tasks_info
    }
    
    if rabbitmq_failures:
        response["failures"] = rabbitmq_failures
        response["message"] += f" Failed to queue {len(rabbitmq_failures)} files due to RabbitMQ issues."
        
    return response

# --- History & Result Endpoints ---
@app.get("/history")
async def get_history():
    """Returns the history of OCR tasks."""
    try:
        all_files = os.listdir(RESULTS_DIR)
        # 查找结果文件（不包括_meta文件）
        result_files = [f for f in all_files if f.endswith('.json') and not f.endswith('_meta.json')]
        
        history = []
        for result_file in result_files:
            task_id = result_file.replace('.json', '')
            result_path = os.path.join(RESULTS_DIR, result_file)
            
            try:
                with open(result_path, 'r') as f:
                    result_data = json.load(f)
                
                # 从结果文件获取信息
                # 获取原始图片文件名
                upload_files = os.listdir(UPLOAD_DIR)
                filename = "Unknown"
                for f in upload_files:
                    if f.startswith(task_id) and f != f"{task_id}.txt":
                        filename = f
                        break
                
                # 创建历史项
                history_item = {
                    "task_id": task_id,
                    "filename": filename,
                    "timestamp": result_data.get("completed_at", 0),
                    "status": "completed"
                }
                history.append(history_item)
            except Exception as e:
                print(f"Error reading result for {task_id}: {e}")
        
        # 按时间戳排序（最新的优先）
        history.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return {"history": history}
    
    except Exception as e:
        print(f"Error reading history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve history")

@app.get("/result/{task_id}")
async def get_result(task_id: str):
    """Retrieves the OCR result for a specific task."""
    result_path = os.path.join(RESULTS_DIR, f"{task_id}.json")
    
    # 检查结果文件是否存在
    if not os.path.exists(result_path):
        # 检查上传文件是否存在
        uploaded_files = os.listdir(UPLOAD_DIR)
        file_exists = False
        filename = "Unknown"
        
        for f in uploaded_files:
            if f.startswith(task_id) and not f.endswith('.txt'):
                file_exists = True
                filename = f
                break
        
        if file_exists:
            # 文件已上传但结果还未生成
            return {
                "task_id": task_id,
                "status": "processing",
                "filename": filename,
                "timestamp": time.time(),
                "message": "OCR processing in progress"
            }
        else:
            # 任务不存在
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")
    
    try:
        # 加载结果
        with open(result_path, 'r') as f:
            result_data = json.load(f)
        
        # 获取原始文件名
        upload_files = os.listdir(UPLOAD_DIR)
        filename = "Unknown"
        for f in upload_files:
            if f.startswith(task_id) and not f.endswith('.txt'):
                filename = f
                break
        
        return {
            "task_id": task_id,
            "status": "completed",
            "filename": filename,
            "timestamp": result_data.get("completed_at", 0),
            "result": result_data
        }
    
    except Exception as e:
        print(f"Error retrieving result for {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving task information: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True) 