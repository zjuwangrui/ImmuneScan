# -*- coding: utf-8 -*-
"""
@Time: Created on 2024/01/10
@author: AttABseq Team
@Filename: interpre.py
@Software: PyCharm
@Description: 注意力机制热图可视化分析脚本
根据1101analysis目录中的注意力权重数据生成热图
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import torch
import os
import re
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# 设置matplotlib中文显示
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class AttentionAnalyzer:
    """注意力权重分析器"""
    
    def __init__(self, analysis_dir='../1101analysis', output_dir='../interpre_heatmap'):
        self.analysis_dir = Path(analysis_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # 创建子目录
        (self.output_dir / 'attention_heatmaps').mkdir(exist_ok=True)
        (self.output_dir / 'comparison_heatmaps').mkdir(exist_ok=True)
        (self.output_dir / 'mutation_effects').mkdir(exist_ok=True)
        
        print(f"分析目录: {self.analysis_dir}")
        print(f"输出目录: {self.output_dir}")
    
    def parse_attention_file(self, file_path):
        """解析注意力权重文件"""
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            data_blocks = []
            current_block = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    if current_block:
                        data_blocks.append(current_block)
                        current_block = []
                    continue
                current_block.append(line)
            
            if current_block:
                data_blocks.append(current_block)
            
            # 解析每个数据块
            parsed_data = []
            for block in data_blocks:
                if len(block) >= 2:
                    # 第一行是标签（tensor格式）
                    label_line = block[0]
                    if 'tensor(' in label_line:
                        # 提取张量中的数值
                        label_match = re.search(r'tensor\(\[(.*?)\]', label_line)
                        if label_match:
                            label_values = [float(x.strip()) for x in label_match.group(1).split(',')]
                        else:
                            label_values = [0.0]
                    else:
                        label_values = [0.0]
                    
                    # 第二行开始是注意力权重矩阵
                    matrix_lines = block[1:]
                    attention_matrix = []
                    
                    for matrix_line in matrix_lines:
                        if matrix_line.startswith('[[') and matrix_line.endswith(']]'):
                            # 解析矩阵数据
                            matrix_str = matrix_line[2:-2]  # 去掉外层括号
                            try:
                                # 分割行
                                rows = matrix_str.split('], [')
                                matrix = []
                                for row in rows:
                                    row_values = [float(x.strip()) for x in row.split(',')]
                                    matrix.append(row_values)
                                attention_matrix = np.array(matrix)
                                break
                            except:
                                continue
                    
                    if len(attention_matrix) > 0:
                        parsed_data.append({
                            'labels': label_values,
                            'attention_matrix': attention_matrix
                        })
            
            return parsed_data
            
        except Exception as e:
            print(f"解析文件 {file_path} 时出错: {e}")
            return []
    
    def get_file_pairs(self):
        """获取文件对应关系"""
        files = list(self.analysis_dir.glob('*.txt'))
        
        epochs = set()
        for f in files:
            # 提取epoch编号
            match = re.search(r'(\d+)\.txt$', f.name)
            if match:
                epochs.add(int(match.group(1)))
        
        file_pairs = {}
        for epoch in sorted(epochs):
            pair = {}
            for prefix in ['ab', 'ag', 'ab_mut', 'ag_mut']:
                file_path = self.analysis_dir / f'{prefix}{epoch}.txt'
                if file_path.exists():
                    pair[prefix] = file_path
            
            if len(pair) >= 2:  # 至少有两个文件才算有效
                file_pairs[epoch] = pair
        
        return file_pairs
    
    def plot_attention_heatmap(self, attention_matrix, title, save_path, labels=None):
        """绘制单个注意力热图"""
        plt.figure(figsize=(12, 10))
        
        # 如果矩阵太大，进行降采样
        if attention_matrix.shape[0] > 100 or attention_matrix.shape[1] > 100:
            step = max(attention_matrix.shape[0] // 50, attention_matrix.shape[1] // 50, 1)
            attention_matrix = attention_matrix[::step, ::step]
        
        # 创建热图
        sns.heatmap(attention_matrix, 
                   cmap='YlOrRd', 
                   cbar=True,
                   xticklabels=False,
                   yticklabels=False,
                   square=False)
        
        plt.title(title, fontsize=16, pad=20)
        plt.xlabel('序列位置', fontsize=12)
        plt.ylabel('序列位置', fontsize=12)
        
        if labels:
            plt.figtext(0.02, 0.02, f'Labels: {labels}', fontsize=10)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
    
    def plot_comparison_heatmap(self, matrix1, matrix2, title1, title2, save_path, labels1=None, labels2=None):
        """绘制对比热图"""
        fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(18, 6))
        
        # 确保矩阵大小一致
        min_shape = (min(matrix1.shape[0], matrix2.shape[0]), 
                    min(matrix1.shape[1], matrix2.shape[1]))
        matrix1_crop = matrix1[:min_shape[0], :min_shape[1]]
        matrix2_crop = matrix2[:min_shape[0], :min_shape[1]]
        
        # 计算差异矩阵
        diff_matrix = matrix2_crop - matrix1_crop
        
        # 绘制第一个矩阵
        sns.heatmap(matrix1_crop, ax=ax1, cmap='Blues', 
                   xticklabels=False, yticklabels=False, cbar=True)
        ax1.set_title(title1, fontsize=14)
        
        # 绘制第二个矩阵
        sns.heatmap(matrix2_crop, ax=ax2, cmap='Reds', 
                   xticklabels=False, yticklabels=False, cbar=True)
        ax2.set_title(title2, fontsize=14)
        
        # 绘制差异矩阵
        sns.heatmap(diff_matrix, ax=ax3, cmap='RdBu_r', center=0,
                   xticklabels=False, yticklabels=False, cbar=True)
        ax3.set_title('差异 (突变型 - 野生型)', fontsize=14)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
    
    def analyze_single_epoch(self, epoch, file_dict):
        """分析单个epoch的数据"""
        print(f"\n分析 Epoch {epoch}...")
        
        # 解析各个文件的数据
        data = {}
        for prefix, file_path in file_dict.items():
            parsed = self.parse_attention_file(file_path)
            if parsed:
                data[prefix] = parsed[0]  # 取第一个数据块
        
        if not data:
            print(f"Epoch {epoch}: 没有有效数据")
            return
        
        # 绘制个体热图
        for prefix, file_data in data.items():
            matrix = file_data['attention_matrix']
            labels = file_data['labels']
            
            title = f'Epoch {epoch} - {prefix.upper()} 注意力权重'
            save_path = self.output_dir / 'attention_heatmaps' / f'epoch_{epoch}_{prefix}_attention.png'
            
            self.plot_attention_heatmap(matrix, title, save_path, labels)
        
        # 绘制对比热图（野生型 vs 突变型）
        if 'ab' in data and 'ab_mut' in data:
            self.plot_comparison_heatmap(
                data['ab']['attention_matrix'],
                data['ab_mut']['attention_matrix'],
                'AB 野生型',
                'AB 突变型',
                self.output_dir / 'comparison_heatmaps' / f'epoch_{epoch}_ab_comparison.png',
                data['ab']['labels'],
                data['ab_mut']['labels']
            )
        
        if 'ag' in data and 'ag_mut' in data:
            self.plot_comparison_heatmap(
                data['ag']['attention_matrix'],
                data['ag_mut']['attention_matrix'],
                'AG 野生型',
                'AG 突变型',
                self.output_dir / 'comparison_heatmaps' / f'epoch_{epoch}_ag_comparison.png',
                data['ag']['labels'],
                data['ag_mut']['labels']
            )
    
    def plot_epoch_evolution(self, file_pairs):
        """绘制不同epoch的注意力演化"""
        print("\n绘制注意力权重演化图...")
        
        epochs = sorted(file_pairs.keys())[:5]  # 最多取前5个epoch
        
        for prefix in ['ab', 'ag', 'ab_mut', 'ag_mut']:
            fig, axes = plt.subplots(1, len(epochs), figsize=(4*len(epochs), 4))
            if len(epochs) == 1:
                axes = [axes]
            
            valid_epochs = []
            for i, epoch in enumerate(epochs):
                if prefix in file_pairs[epoch]:
                    data = self.parse_attention_file(file_pairs[epoch][prefix])
                    if data:
                        matrix = data[0]['attention_matrix']
                        
                        # 降采样以便显示
                        if matrix.shape[0] > 50:
                            step = matrix.shape[0] // 30
                            matrix = matrix[::step, ::step]
                        
                        sns.heatmap(matrix, ax=axes[i], cmap='viridis',
                                   xticklabels=False, yticklabels=False, cbar=False)
                        axes[i].set_title(f'Epoch {epoch}', fontsize=12)
                        valid_epochs.append(epoch)
            
            # 隐藏空的子图
            for i in range(len(valid_epochs), len(epochs)):
                axes[i].set_visible(False)
            
            plt.suptitle(f'{prefix.upper()} 注意力权重演化', fontsize=16)
            plt.tight_layout()
            
            save_path = self.output_dir / 'mutation_effects' / f'{prefix}_evolution.png'
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()
    
    def generate_summary_report(self, file_pairs):
        """生成分析总结报告"""
        print("\n生成分析报告...")
        
        report_path = self.output_dir / 'analysis_report.txt'
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("AttABseq 注意力机制分析报告\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"分析数据来源: {self.analysis_dir}\n")
            f.write(f"分析的epoch数量: {len(file_pairs)}\n")
            f.write(f"输出目录: {self.output_dir}\n\n")
            
            f.write("文件统计:\n")
            for epoch, files in file_pairs.items():
                f.write(f"  Epoch {epoch}: {list(files.keys())}\n")
            
            f.write("\n生成的热图类型:\n")
            f.write("  1. 单独注意力热图 (attention_heatmaps/)\n")
            f.write("  2. 野生型vs突变型对比热图 (comparison_heatmaps/)\n")
            f.write("  3. 注意力演化图 (mutation_effects/)\n\n")
            
            f.write("分析说明:\n")
            f.write("  - 热图颜色越深表示注意力权重越高\n")
            f.write("  - 对比图中蓝色为野生型，红色为突变型\n")
            f.write("  - 差异图中红色表示突变增强注意力，蓝色表示减弱\n")
        
        print(f"分析报告已保存到: {report_path}")
    
    def run_analysis(self):
        """运行完整分析"""
        print("开始AttABseq注意力机制热图分析...")
        
        # 获取文件对应关系
        file_pairs = self.get_file_pairs()
        
        if not file_pairs:
            print("错误: 未找到有效的分析文件!")
            return
        
        print(f"找到 {len(file_pairs)} 个epoch的数据文件")
        
        # 分析每个epoch
        for epoch in sorted(file_pairs.keys()):
            self.analyze_single_epoch(epoch, file_pairs[epoch])
        
        # 绘制演化图
        self.plot_epoch_evolution(file_pairs)
        
        # 生成报告
        self.generate_summary_report(file_pairs)
        
        print(f"\n✅ 分析完成! 所有热图已保存到: {self.output_dir}")
        print(f"📊 共生成 {len(list(self.output_dir.rglob('*.png')))} 个热图文件")


def main():
    """主函数"""
    print("AttABseq 注意力机制热图分析工具")
    print("=" * 50)
    
    # 创建分析器实例
    analyzer = AttentionAnalyzer()
    
    # 运行分析
    analyzer.run_analysis()


if __name__ == "__main__":
    main()