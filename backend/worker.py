#!/usr/bin/env python
"""OCR Worker for processing images using Tongyi Qianwen API."""

import os
import json
import time
import sys
import pika
import logging
from typing import Dict, Any, Optional
import base64
import config  # 导入配置模块
# 使用OpenAI兼容模式客户端
from openai import OpenAI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("ocr_worker")

# Persistent directories (same as in main.py)
BASE_DATA_DIR = "persistent_data"
UPLOAD_DIR = os.path.join(BASE_DATA_DIR, "uploads")
RESULTS_DIR = os.path.join(BASE_DATA_DIR, "results")

# Make sure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# 加载配置
app_config = config.get_config()

class TongyiOCRClient:
    """Client for Tongyi Qianwen OCR API."""
    
    def __init__(self, api_key: str, base_url: str = None, model_name: str = None):
        """Initialize with API key and optional settings."""
        self.api_key = api_key
        
        # 修复API URL - 强制使用compatible-mode
        base_url_from_config = app_config.get("api_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        
        # 确保URL正确格式化为兼容模式
        if "dashscope.aliyuncs.com" in base_url_from_config and not base_url_from_config.endswith("/compatible-mode/v1"):
            base_url_from_config = "https://dashscope.aliyuncs.com/compatible-mode/v1"
                
        # 优先使用提供的参数，然后是配置文件，最后是默认值
        self.base_url = base_url or base_url_from_config
        self.model_name = model_name or app_config.get("model_name", "qwen-vl-ocr")
        
        logger.info(f"初始化OCR客户端: API URL={self.base_url}, 模型名称={self.model_name}")
        
        # 初始化OpenAI客户端
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        logger.info("OpenAI客户端初始化完成")
        
    def encode_image(self, image_path: str) -> str:
        """将图片转换为base64编码"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
        
    def recognize_image(self, image_path: str) -> Dict[str, Any]:
        """
        Recognize text in an image using Tongyi Qianwen OCR API.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dict containing the recognition results
        """
        try:
            # 获取图片格式
            image_format = os.path.splitext(image_path)[1].lower().replace('.', '')
            if image_format not in ['png', 'jpg', 'jpeg', 'webp']:
                # 默认使用jpeg格式
                image_format = 'jpeg'
                
            # 读取图片并转为base64格式
            base64_image = self.encode_image(image_path)
            
            logger.info(f"发送请求到通义千问API (OpenAI兼容模式):")
            logger.info(f"  - 基础URL: {self.base_url}")
            logger.info(f"  - 模型名称: {self.model_name}")
            logger.info(f"  - 图片格式: {image_format}")
            logger.info(f"  - 图片路径: {image_path}")
            
            # 直接使用初始化时创建的客户端
            # 调用通义千问OCR模型
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/{image_format};base64,{base64_image}",
                                },
                            },
                            {"type": "text", "text": "Read all the text in the image."},
                        ],
                    }
                ],
            )
            
            # 提取识别结果
            result = {
                "success": True,
                "text": completion.choices[0].message.content,
                "raw_response": completion.model_dump()
            }
            return result
            
        except Exception as e:
            logger.error(f"通义千问OCR识别异常: {str(e)}")
            return {
                "error": True,
                "message": f"OCR识别失败: {str(e)}"
            }


def process_message(ch, method, properties, body):
    """处理从RabbitMQ接收的消息"""
    try:
        task_data = json.loads(body)
        logger.info(f"收到任务: {task_data}")
        
        # 获取任务数据
        api_key = task_data.get("api_key", "")
        image_path = task_data.get("image_path", "")
        task_id = task_data.get("task_id", "")
        
        if not api_key:
            logger.error("错误: 缺少API密钥")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return
        
        if not image_path:
            logger.error("错误: 缺少图片路径")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return
            
        logger.info(f"使用配置文件中的设置处理任务")
        
        try:
            # 初始化OCR客户端，仅传递API密钥，其他设置将从配置文件中获取
            client = TongyiOCRClient(api_key=api_key)
            
            # 处理图片
            try:
                logger.info(f"开始识别图片: {image_path}")
                result = client.recognize_image(image_path)
                logger.info(f"成功识别图片: {image_path}")
                
                # 防止生成uploads/.jpg.txt文件的额外检查
                txt_path = image_path + ".txt"
                if os.path.exists(txt_path):
                    try:
                        os.remove(txt_path)
                        logger.info(f"删除了旧版本生成的文本文件: {txt_path}")
                    except Exception as e:
                        logger.error(f"无法删除旧版本文本文件: {str(e)}")
                
                if result.get("success"):
                    # 将结果写入results目录下
                    if task_id:
                        # 创建JSON结果文件用于API返回
                        result_json_path = os.path.join(RESULTS_DIR, f"{task_id}.json")
                        with open(result_json_path, "w", encoding="utf-8") as f:
                            # 创建简化的结果JSON
                            result_data = {
                                "text": result["text"],
                                "completed_at": time.time()
                            }
                            json.dump(result_data, f, ensure_ascii=False)
                        logger.info(f"已创建结果JSON文件: {result_json_path}")
                else:
                    logger.error(f"图片识别失败: {result.get('message', '未知错误')}")
                    
                    # 写入错误信息到结果文件
                    if task_id:
                        result_json_path = os.path.join(RESULTS_DIR, f"{task_id}.json")
                        with open(result_json_path, "w", encoding="utf-8") as f:
                            # 创建错误结果JSON
                            result_data = {
                                "error": True,
                                "message": result.get('message', '未知错误'),
                                "completed_at": time.time()
                            }
                            json.dump(result_data, f, ensure_ascii=False)
                        logger.info(f"已创建错误结果JSON文件: {result_json_path}")
                
            except Exception as e:
                logger.error(f"图片处理失败: {str(e)}")
                
                # 创建错误结果文件
                if task_id:
                    result_json_path = os.path.join(RESULTS_DIR, f"{task_id}.json")
                    with open(result_json_path, "w", encoding="utf-8") as f:
                        result_data = {
                            "error": True,
                            "message": f"图片处理失败: {str(e)}",
                            "completed_at": time.time()
                        }
                        json.dump(result_data, f, ensure_ascii=False)
                    logger.info(f"已创建错误结果JSON文件: {result_json_path}")
                
        except Exception as e:
            logger.error(f"初始化OCR客户端失败: {str(e)}")
            
            # 创建错误结果文件
            if task_id:
                result_json_path = os.path.join(RESULTS_DIR, f"{task_id}.json")
                with open(result_json_path, "w", encoding="utf-8") as f:
                    result_data = {
                        "error": True,
                        "message": f"初始化OCR客户端失败: {str(e)}",
                        "completed_at": time.time()
                    }
                    json.dump(result_data, f, ensure_ascii=False)
                logger.info(f"已创建错误结果JSON文件: {result_json_path}")
        
        # 确认消息已处理
        ch.basic_ack(delivery_tag=method.delivery_tag)
        
    except json.JSONDecodeError:
        logger.error("无效的JSON格式")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"处理消息时出错: {str(e)}")
        ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    """Main function to start the worker."""
    try:
        # 获取最新配置
        app_config = config.refresh_config()
        rabbitmq_host = app_config["rabbitmq_host"]
        rabbitmq_port = int(app_config["rabbitmq_port"])
        rabbitmq_queue = app_config["rabbitmq_queue"]
        worker_concurrency = int(app_config.get("worker_concurrency", 3))  # 获取并发数配置
        
        # Connect to RabbitMQ
        logger.info(f"Connecting to RabbitMQ at {rabbitmq_host}:{rabbitmq_port}")
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=rabbitmq_host,
                port=rabbitmq_port,
                heartbeat=600,
                blocked_connection_timeout=300
            )
        )
        channel = connection.channel()
        
        # Declare the queue
        channel.queue_declare(queue=rabbitmq_queue, durable=True)
        
        # Set QoS prefetch (控制worker的并发处理能力)
        channel.basic_qos(prefetch_count=worker_concurrency)
        logger.info(f"Worker并发处理能力设置为: {worker_concurrency}")
        
        # Define the callback
        channel.basic_consume(
            queue=rabbitmq_queue,
            on_message_callback=process_message
        )
        
        logger.info(f"Worker启动，等待处理队列'{rabbitmq_queue}'中的消息...")
        
        # Start consuming
        channel.start_consuming()
        
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
        try:
            connection.close()
        except:
            pass
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 