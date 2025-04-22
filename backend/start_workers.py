#!/usr/bin/env python
"""
启动多个OCR worker进程的脚本
"""
import os
import sys
import time
import argparse
import subprocess
import config

def start_workers(num_workers):
    """启动指定数量的worker进程"""
    processes = []
    
    print(f"准备启动 {num_workers} 个OCR worker进程...")
    
    # 获取当前脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    worker_script = os.path.join(script_dir, "worker.py")
    
    # 确保worker.py存在
    if not os.path.exists(worker_script):
        print(f"错误: 找不到worker脚本: {worker_script}")
        sys.exit(1)
    
    # 启动worker进程
    for i in range(num_workers):
        try:
            process = subprocess.Popen(
                [sys.executable, worker_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            processes.append(process)
            print(f"已启动worker进程 #{i+1}, PID: {process.pid}")
            # 稍微等待以避免同时连接RabbitMQ
            time.sleep(0.5)
        except Exception as e:
            print(f"启动worker进程 #{i+1} 时出错: {e}")
    
    print(f"成功启动 {len(processes)} 个worker进程")
    
    try:
        # 等待用户中断
        print("按 Ctrl+C 停止所有worker...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n收到中断信号，正在停止所有worker进程...")
        for i, process in enumerate(processes):
            print(f"正在停止worker进程 #{i+1}, PID: {process.pid}")
            process.terminate()
        
        # 给进程一些时间来优雅地退出
        time.sleep(2)
        
        # 检查是否有进程仍在运行，如果有则强制终止
        for i, process in enumerate(processes):
            if process.poll() is None:
                print(f"强制终止worker进程 #{i+1}, PID: {process.pid}")
                process.kill()
        
        print("所有worker进程已停止")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="启动多个OCR worker进程")
    parser.add_argument("-n", "--num-workers", type=int, default=0,
                        help="要启动的worker进程数量 (默认: 根据配置文件)")
    args = parser.parse_args()
    
    # 如果未指定worker数量，从配置中获取并行数
    if args.num_workers <= 0:
        app_config = config.get_config()
        num_workers = int(app_config.get("worker_concurrency", 3))
    else:
        num_workers = args.num_workers
    
    start_workers(num_workers) 