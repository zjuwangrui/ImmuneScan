#!/bin/bash
# -*- coding: utf-8 -*-
"""
AttABseq 热图分析批处理脚本
使用方法: python run_heatmap_analysis.py [模式]
模式选项:
  - heatmap: 生成热图 (默认)
  - csv: 导出CSV数据
  - all: 生成热图和CSV数据
"""

import sys
import os
from pathlib import Path

def run_heatmap_analysis():
    """运行热图分析"""
    print("🔥 开始生成热图...")
    try:
        from interpre import AttentionAnalyzer
        analyzer = AttentionAnalyzer()
        analyzer.run_analysis()
        return True
    except Exception as e:
        print(f"❌ 热图分析失败: {e}")
        return False

def run_csv_extraction():
    """运行CSV数据提取"""
    print("📊 开始提取CSV数据...")
    try:
        from interpre_csv import AttentionDataExtractor
        extractor = AttentionDataExtractor()
        extractor.run_extraction()
        return True
    except Exception as e:
        print(f"❌ CSV提取失败: {e}")
        return False

def check_dependencies():
    """检查依赖包"""
    required_packages = ['numpy', 'pandas', 'matplotlib', 'seaborn', 'torch']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ 缺少依赖包: {missing_packages}")
        print("请安装缺少的包:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def check_data_directory():
    """检查数据目录"""
    data_dir = Path('../1101analysis')
    if not data_dir.exists():
        print(f"❌ 数据目录不存在: {data_dir}")
        return False
    
    txt_files = list(data_dir.glob('*.txt'))
    if not txt_files:
        print(f"❌ 数据目录中没有找到.txt文件: {data_dir}")
        return False
    
    print(f"✅ 找到 {len(txt_files)} 个数据文件")
    return True

def main():
    """主函数"""
    print("AttABseq 热图分析工具")
    print("=" * 50)
    
    # 检查依赖
    if not check_dependencies():
        return
    
    # 检查数据目录
    if not check_data_directory():
        return
    
    # 解析命令行参数
    mode = 'heatmap'  # 默认模式
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    
    print(f"运行模式: {mode}")
    
    success = True
    
    if mode in ['heatmap', 'all']:
        success &= run_heatmap_analysis()
    
    if mode in ['csv', 'all']:
        success &= run_csv_extraction()
    
    if mode not in ['heatmap', 'csv', 'all']:
        print(f"❌ 未知模式: {mode}")
        print("可用模式: heatmap, csv, all")
        return
    
    if success:
        print("\n🎉 分析完成!")
        print("📁 输出文件位置:")
        
        if mode in ['heatmap', 'all']:
            print("  - 热图: ../interpre_heatmap/")
        
        if mode in ['csv', 'all']:
            print("  - CSV数据: ../interpre_csv/")
    else:
        print("\n❌ 分析过程中遇到错误")

if __name__ == "__main__":
    main()