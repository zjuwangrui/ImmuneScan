# -*- coding: utf-8 -*-
"""
最终优化版：使用百分位数缩放增强对比度
"""
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import pickle
import os

# 非交互式后端
import matplotlib
matplotlib.use('Agg')

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


def create_custom_colormap():
    """创建自定义colormap：蓝色(低) -> 白色(中) -> 红色(高)"""
    colors = ['#000080', '#0000FF', '#4169E1', '#87CEEB', '#FFFFFF',
              '#FFB6C1', '#FF6347', '#FF0000', '#8B0000']
    cmap = mcolors.LinearSegmentedColormap.from_list('custom_RdBu', colors, N=256)
    return cmap


# 加载数据
pkl_file = r'c:\Users\84766\Desktop\atta_1\output_test\attention_matrices\all_attention_data.pkl'
with open(pkl_file, 'rb') as f:
    all_data = pickle.load(f)

output_dir = r'c:\Users\84766\Desktop\atta_1\output_test\attention_visualizations_final'
os.makedirs(output_dir, exist_ok=True)

print("="*70)
print("Final Improved Heatmap Generation")
print("="*70)

# 处理第一个样本
idx = 0
data = all_data[idx]
pdb_id = data['pdb_id']
ag_length = data['ag_length']
ab_length = data['ab_length']
cross_attn = data['cross_attention_matrix']
true_ddg = data['true_ddG']
pred_ddg = data['predicted_ddG']

print(f"\nSample {idx}: {pdb_id}")
print(f"Matrix shape: {cross_attn.shape}")
print(f"Original range: [{cross_attn.min():.10f}, {cross_attn.max():.10f}]")

# 使用百分位数缩放
p05 = np.percentile(cross_attn, 5)
p95 = np.percentile(cross_attn, 95)

print(f"Percentiles:")
print(f"  5%:  {p05:.10f}")
print(f"  50%: {np.percentile(cross_attn, 50):.10f}")
print(f"  95%: {p95:.10f}")

# 方案1：百分位数裁剪后归一化
matrix_clipped = np.clip(cross_attn, p05, p95)
matrix_norm = (matrix_clipped - matrix_clipped.min()) / (matrix_clipped.max() - matrix_clipped.min())

print(f"\nAfter percentile clipping and normalization:")
print(f"  Range: [{matrix_norm.min():.6f}, {matrix_norm.max():.6f}]")
print(f"  Mean: {matrix_norm.mean():.6f}")

# 创建热图
fig, ax = plt.subplots(figsize=(20, 12))
cmap = create_custom_colormap()

im = ax.imshow(matrix_norm, cmap=cmap, aspect='auto',
               interpolation='nearest', vmin=0, vmax=1)

# 标题
title = f'Cross-Attention Heatmap: {pdb_id} (Sample {idx})\n'
title += f'Antigen ({ag_length} residues) × Antibody ({ab_length} residues)\n'
title += f'True ddG: {true_ddg:.3f} | Predicted ddG: {pred_ddg:.3f}\n'
title += f'[Percentile Scaling: 5%-95%]'
ax.set_title(title, fontsize=18, fontweight='bold', pad=25)

# 轴标签
ax.set_xlabel('Antibody Residue Index', fontsize=16, fontweight='bold')
ax.set_ylabel('Antigen Residue Index', fontsize=16, fontweight='bold')

# 颜色条
cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
cbar.set_label('Attention Weight (Percentile Scaled)\nRed=High, White=Mid, Blue=Low',
               fontsize=14, fontweight='bold')
cbar.ax.tick_params(labelsize=12)
cbar.set_ticks([0.0, 0.25, 0.5, 0.75, 1.0])
cbar.set_ticklabels(['Low\n(5%ile)', '0.25', 'Mid\n(50%ile)', '0.75', 'High\n(95%ile)'])

# 统计信息
stats_text = f'Original Matrix:\n'
stats_text += f'Min:    {cross_attn.min():.8f}\n'
stats_text += f'Max:    {cross_attn.max():.8f}\n'
stats_text += f'Mean:   {cross_attn.mean():.8f}\n'
stats_text += f'Median: {np.median(cross_attn):.8f}\n'
stats_text += f'\nScaled Matrix:\n'
stats_text += f'Range: [0.0, 1.0]\n'
stats_text += f'Mean: {matrix_norm.mean():.4f}'

props = dict(boxstyle='round', facecolor='lightyellow', alpha=0.95,
             edgecolor='black', linewidth=2.5)
ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, fontsize=13,
        verticalalignment='top', bbox=props, family='monospace')

# 找出top-10
flat = cross_attn.flatten()
top_indices = np.argsort(flat)[-10:][::-1]
top_positions = np.unravel_index(top_indices, cross_attn.shape)

top_text = 'Top-10 Positions:\n'
for i in range(min(10, len(top_indices))):
    ag_idx = top_positions[0][i]
    ab_idx = top_positions[1][i]
    val = cross_attn[ag_idx, ab_idx]
    top_text += f'{i+1}. Ag[{ag_idx:3d}]-Ab[{ab_idx:3d}]\n    = {val:.6f}\n'

props2 = dict(boxstyle='round', facecolor='lightcyan', alpha=0.95,
              edgecolor='darkblue', linewidth=2.5)
ax.text(0.98, 0.98, top_text, transform=ax.transAxes, fontsize=11,
        verticalalignment='top', horizontalalignment='right',
        bbox=props2, family='monospace')

plt.tight_layout()

# 保存
output_file = os.path.join(output_dir, f'final_heatmap_{pdb_id}_sample{idx}.png')
plt.savefig(output_file, dpi=300, bbox_inches='tight')
print(f"\n✓ Saved: {output_file}")

# 再画一个对数缩放版本
fig2, ax2 = plt.subplots(figsize=(20, 12))

# 对数缩放
matrix_log = np.log10(cross_attn + 1e-10)  # 加小值避免log(0)
matrix_log_norm = (matrix_log - matrix_log.min()) / (matrix_log.max() - matrix_log.min())

im2 = ax2.imshow(matrix_log_norm, cmap=cmap, aspect='auto',
                 interpolation='nearest', vmin=0, vmax=1)

title2 = f'Cross-Attention Heatmap (Log Scale): {pdb_id}\n'
title2 += f'Antigen ({ag_length}) × Antibody ({ab_length})\n'
title2 += f'True ddG: {true_ddg:.3f} | Predicted ddG: {pred_ddg:.3f}'
ax2.set_title(title2, fontsize=18, fontweight='bold', pad=25)

ax2.set_xlabel('Antibody Residue Index', fontsize=16, fontweight='bold')
ax2.set_ylabel('Antigen Residue Index', fontsize=16, fontweight='bold')

cbar2 = plt.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)
cbar2.set_label('Log-Scaled Attention\nRed=High, Blue=Low',
                fontsize=14, fontweight='bold')

plt.tight_layout()

output_file2 = os.path.join(output_dir, f'final_heatmap_log_{pdb_id}_sample{idx}.png')
plt.savefig(output_file2, dpi=300, bbox_inches='tight')
print(f"✓ Saved: {output_file2}")

print("\n" + "="*70)
print("✅ Final heatmaps generated!")
print("="*70)
print(f"\nFiles:")
print(f"  1. Percentile scaled: {output_file}")
print(f"  2. Log scaled:        {output_file2}")
