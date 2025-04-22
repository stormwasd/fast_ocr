#!/usr/bin/env python
"""
测试批量上传图片并观察并行处理情况
"""
import os
import sys
import time
import json
import requests
import argparse
from glob import glob

def batch_upload_images(server_url, image_dir, num_images=5):
    """批量上传图片测试并行处理"""
    # 获取图片文件
    image_files = []
    for ext in ['jpg', 'jpeg', 'png', 'webp']:
        image_files.extend(glob(os.path.join(image_dir, f"*.{ext}")))
    
    if not image_files:
        print(f"错误: 在 {image_dir} 目录中找不到图片文件")
        sys.exit(1)
    
    # 限制上传的图片数量
    image_files = image_files[:min(num_images, len(image_files))]
    print(f"找到 {len(image_files)} 个图片文件")
    
    # 准备上传
    upload_url = f"{server_url}/upload"
    files = [("files", (os.path.basename(f), open(f, "rb"), "image/jpeg")) for f in image_files]
    
    print(f"正在上传 {len(files)} 个图片...")
    start_time = time.time()
    
    try:
        response = requests.post(upload_url, files=files)
        response.raise_for_status()
        
        # 解析响应
        result = response.json()
        tasks = result.get("tasks", [])
        
        print(f"成功上传 {len(tasks)} 个图片，任务已排队")
        
        # 记录任务ID
        task_ids = [task["task_id"] for task in tasks]
        
        # 监控任务处理情况
        completed = 0
        processing = len(task_ids)
        
        print("\n开始监控任务处理情况...")
        while processing > 0:
            time.sleep(1)
            
            for task_id in task_ids:
                if task_id not in task_ids:
                    continue
                    
                # 获取任务状态
                result_url = f"{server_url}/result/{task_id}"
                response = requests.get(result_url)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("status") == "completed":
                        # 任务完成
                        print(f"任务 {task_id} 已完成")
                        task_ids.remove(task_id)
                        completed += 1
                        processing -= 1
            
            # 显示处理进度
            elapsed = time.time() - start_time
            print(f"\r处理进度: {completed}/{completed + processing} 已完成, 用时: {elapsed:.2f}秒", end="")
        
        print(f"\n\n所有任务处理完成，总用时: {time.time() - start_time:.2f}秒")
        
    except Exception as e:
        print(f"上传或监控过程中出错: {e}")
    finally:
        # 关闭所有文件
        for _, f, _ in files:
            f[1].close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="批量上传图片测试OCR并行处理")
    parser.add_argument("-s", "--server", default="http://localhost:8080",
                        help="API服务器地址 (默认: http://localhost:8080)")
    parser.add_argument("-d", "--dir", default="./persistent_data/uploads",
                        help="包含测试图片的目录 (默认: ./persistent_data/uploads)")
    parser.add_argument("-n", "--num-images", type=int, default=5,
                        help="要上传的图片数量 (默认: 5)")
    args = parser.parse_args()
    
    batch_upload_images(args.server, args.dir, args.num_images) 