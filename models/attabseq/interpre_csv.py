# -*- coding: utf-8 -*-
"""
@Time: Created on 2024/01/10  
@author: AttABseq Team
@Filename: interpre_csv.py
@Software: PyCharm
@Description: 注意力权重数据提取和CSV导出脚本
从1101analysis目录提取注意力数据并保存为CSV格式
"""

import numpy as np
import pandas as pd
import torch
import os
import re
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')


class AttentionDataExtractor:
    """注意力数据提取器"""
    
    def __init__(self, analysis_dir='../1101analysis', output_dir='../interpre_csv'):
        self.analysis_dir = Path(analysis_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        print(f"数据目录: {self.analysis_dir}")
        print(f"输出目录: {self.output_dir}")
    
    def parse_attention_file(self, file_path):
        """解析注意力权重文件并提取统计信息"""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # 提取所有tensor标签
            tensor_pattern = r'tensor\(\[(.*?)\]'
            tensor_matches = re.findall(tensor_pattern, content)
            
            labels = []
            for match in tensor_matches:
                try:
                    values = [float(x.strip()) for x in match.split(',')]
                    labels.extend(values)
                except:
                    continue
            
            # 提取注意力权重矩阵的统计信息
            matrix_pattern = r'\[\[(.*?)\]\]'
            matrix_matches = re.findall(matrix_pattern, content, re.DOTALL)
            
            matrix_stats = []
            for i, matrix_str in enumerate(matrix_matches):
                try:
                    # 提取数值
                    numbers = re.findall(r'(\d+\.\d+)', matrix_str)
                    if numbers:
                        values = [float(x) for x in numbers]
                        
                        stats = {
                            'matrix_id': i,
                            'mean_attention': np.mean(values),
                            'std_attention': np.std(values),
                            'max_attention': np.max(values),
                            'min_attention': np.min(values),
                            'num_elements': len(values)
                        }
                        matrix_stats.append(stats)
                except Exception as e:
                    continue
            
            return labels, matrix_stats
            
        except Exception as e:
            print(f"解析文件 {file_path} 时出错: {e}")
            return [], []
    
    def extract_all_data(self):
        """提取所有文件的数据"""
        all_data = []
        
        # 获取所有txt文件
        files = list(self.analysis_dir.glob('*.txt'))
        
        for file_path in files:
            # 解析文件名
            file_name = file_path.stem
            match = re.match(r'([a-z_]+)(\d+)', file_name)
            
            if match:
                prefix = match.group(1)
                epoch = int(match.group(2))
                
                # 解析文件内容
                labels, matrix_stats = self.parse_attention_file(file_path)
                
                # 为每个矩阵创建记录
                for stats in matrix_stats:
                    record = {
                        'file_name': file_name,
                        'file_type': prefix,
                        'epoch': epoch,
                        'sample_labels': str(labels) if labels else '',
                        **stats
                    }
                    all_data.append(record)
        
        return all_data
    
    def export_to_csv(self):
        """导出数据到CSV"""
        print("开始提取注意力权重数据...")
        
        # 提取所有数据
        data = self.extract_all_data()
        
        if not data:
            print("未找到有效数据!")
            return
        
        # 创建DataFrame
        df = pd.DataFrame(data)
        
        # 保存详细数据
        detailed_csv = self.output_dir / 'attention_detailed.csv'
        df.to_csv(detailed_csv, index=False, encoding='utf-8')
        print(f"详细数据已保存到: {detailed_csv}")
        
        # 创建汇总统计
        summary_stats = df.groupby(['file_type', 'epoch']).agg({
            'mean_attention': ['mean', 'std'],
            'max_attention': ['mean', 'max'],
            'min_attention': ['mean', 'min'],
            'num_elements': 'mean'
        }).round(6)
        
        summary_stats.columns = ['_'.join(col).strip() for col in summary_stats.columns]
        summary_stats = summary_stats.reset_index()
        
        summary_csv = self.output_dir / 'attention_summary.csv'
        summary_stats.to_csv(summary_csv, index=False, encoding='utf-8')
        print(f"汇总统计已保存到: {summary_csv}")
        
        # 生成分析报告
        self.generate_data_report(df)
        
        return df
    
    def generate_data_report(self, df):
        """生成数据报告"""
        report_path = self.output_dir / 'data_report.txt'
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("AttABseq 注意力权重数据提取报告\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"总记录数: {len(df)}\n")
            f.write(f"文件类型: {sorted(df['file_type'].unique())}\n")
            f.write(f"Epoch范围: {df['epoch'].min()} - {df['epoch'].max()}\n\n")
            
            f.write("各类型文件统计:\n")
            type_counts = df['file_type'].value_counts()
            for file_type, count in type_counts.items():
                f.write(f"  {file_type}: {count} 个记录\n")
            
            f.write("\n注意力权重统计:\n")
            f.write(f"  平均注意力权重: {df['mean_attention'].mean():.6f}\n")
            f.write(f"  最大注意力权重: {df['max_attention'].max():.6f}\n")
            f.write(f"  最小注意力权重: {df['min_attention'].min():.6f}\n")
            
        print(f"数据报告已保存到: {report_path}")
    
    def run_extraction(self):
        """运行数据提取"""
        print("AttABseq 注意力权重数据提取工具")
        print("=" * 50)
        
        df = self.export_to_csv()
        
        if df is not None:
            print(f"\n✅ 数据提取完成!")
            print(f"📁 输出目录: {self.output_dir}")
            print(f"📊 总共处理了 {len(df)} 条记录")


def main():
    """主函数"""
    extractor = AttentionDataExtractor()
    extractor.run_extraction()


if __name__ == "__main__":
    main()