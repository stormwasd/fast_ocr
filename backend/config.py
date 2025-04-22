"""
配置管理模块 - 负责加载和保存系统配置
"""
import os
import json
from typing import Dict, Any, Optional

# 配置文件路径
CONFIG_DIR = "config"
CONFIG_FILE = os.path.join(CONFIG_DIR, "app_config.json")

# 默认配置
DEFAULT_CONFIG = {
    "api_key": "",
    "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model_name": "qwen-vl-ocr",
    "rabbitmq_host": "localhost",
    "rabbitmq_port": "5672",
    "rabbitmq_queue": "ocr_tasks",
    "worker_concurrency": 3  # 默认worker并发数
}

# 确保配置目录存在
os.makedirs(CONFIG_DIR, exist_ok=True)

def load_config() -> Dict[str, Any]:
    """从配置文件加载配置，如果文件不存在则创建默认配置文件"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 合并默认配置，确保所有必要的配置项都存在
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                return config
        else:
            # 配置文件不存在，创建默认配置
            save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG.copy()
    except Exception as e:
        print(f"加载配置时出错: {e}")
        return DEFAULT_CONFIG.copy()

def save_config(config: Dict[str, Any]) -> bool:
    """保存配置到文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"保存配置时出错: {e}")
        return False

def update_config(new_config: Dict[str, Any]) -> Dict[str, Any]:
    """更新部分配置并保存"""
    current_config = load_config()
    # 只更新提供的配置项
    for key, value in new_config.items():
        if key in current_config:
            current_config[key] = value
    save_config(current_config)
    return current_config

# 全局配置实例，程序启动时加载
config = load_config()

def get_config() -> Dict[str, Any]:
    """获取当前配置"""
    return config

def refresh_config() -> Dict[str, Any]:
    """从文件刷新配置"""
    global config
    config = load_config()
    return config 