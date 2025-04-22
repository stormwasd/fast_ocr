#!/usr/bin/env python
"""配置工具 - 用于查看和更新配置"""

import json
import argparse
import config
import sys

def display_config(show_api_key=False):
    """显示当前配置"""
    current_config = config.get_config()
    
    print("\n===== 当前配置 =====")
    for key, value in current_config.items():
        if key == "api_key" and not show_api_key and value:
            # 隐藏API Key，只显示前四位和后四位
            if len(value) > 8:
                display_value = f"{value[:4]}...{value[-4:]}"
            else:
                display_value = "******"
            print(f"{key}: {display_value}")
        else:
            print(f"{key}: {value}")
    print("===================\n")

def update_config_interactive():
    """交互式更新配置"""
    current_config = config.get_config()
    update_data = {}
    
    print("\n===== 更新配置 =====")
    print("输入新值或按Enter跳过\n")
    
    for key, value in current_config.items():
        display_value = value if key != "api_key" else "[隐藏]"
        new_value = input(f"{key} [{display_value}]: ")
        if new_value:  # 如果用户输入了新值
            update_data[key] = new_value
    
    if update_data:
        config.update_config(update_data)
        print("\n配置已更新")
    else:
        print("\n没有进行任何更改")
    
    display_config()

def main():
    parser = argparse.ArgumentParser(description="OCR配置工具")
    parser.add_argument("--show", action="store_true", help="显示当前配置")
    parser.add_argument("--show-key", action="store_true", help="显示API Key（敏感信息）")
    parser.add_argument("--update", action="store_true", help="更新配置")
    parser.add_argument("--set", nargs=2, action="append", metavar=("KEY", "VALUE"), help="设置配置项，例如: --set api_key YOUR_KEY")
    
    args = parser.parse_args()
    
    # 如果没有参数，显示使用帮助
    if len(sys.argv) == 1:
        parser.print_help()
        return
    
    # 显示配置
    if args.show or args.show_key:
        display_config(show_api_key=args.show_key)
    
    # 通过命令行参数更新配置
    if args.set:
        update_data = {k: v for k, v in args.set}
        config.update_config(update_data)
        print("\n配置已通过命令行更新")
        display_config()
    
    # 交互式更新配置
    if args.update:
        update_config_interactive()

if __name__ == "__main__":
    main() 