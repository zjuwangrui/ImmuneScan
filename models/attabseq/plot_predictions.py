# -*- coding: utf-8 -*-
"""
绘制预测值 vs 真实值的散点图（带边缘分布）- 优化版
Author: Generated with Claude Code
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import pearsonr, gaussian_kde
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from math import sqrt
import os
from matplotlib.patches import Rectangle
from matplotlib.colors import LinearSegmentedColormap
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体（可选，如果需要中文标签）
plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.family'] = 'sans-serif'

# 自定义配色方案
COLORS = {
    'primary': '#3498db',      # 蓝色
    'secondary': '#e74c3c',    # 红色
    'accent': '#2ecc71',       # 绿色
    'background': '#ecf0f1',   # 浅灰
    'grid': '#bdc3c7',         # 网格颜色
    'text': '#2c3e50',         # 深色文字
    'train': '#5DADE2',        # 训练集颜色
    'val': '#F1948A',          # 验证集颜色
}


def plot_predictions_enhanced(y_true, y_pred, dataset_name='Validation', save_path=None):
    """
    绘制增强版的预测值vs真实值散点图（带密度着色和KDE边缘分布）

    参数:
        y_true: 真实值数组
        y_pred: 预测值数组
        dataset_name: 数据集名称
        save_path: 保存路径
    """
    # 计算评估指标
    pearson_corr, _ = pearsonr(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    mae = mean_absolute_error(y_true, y_pred)
    rmse = sqrt(mean_squared_error(y_true, y_pred))
    n_samples = len(y_true)

    # 创建图形
    fig = plt.figure(figsize=(12, 12))
    gs = fig.add_gridspec(4, 4, hspace=0.05, wspace=0.05,
                          height_ratios=[1, 3, 0.3, 0.3],
                          width_ratios=[0.3, 3, 1, 0.3])

    # 主散点图
    ax_main = fig.add_subplot(gs[1, 1])
    # 顶部边缘分布
    ax_top = fig.add_subplot(gs[0, 1], sharex=ax_main)
    # 右侧边缘分布
    ax_right = fig.add_subplot(gs[1, 2], sharey=ax_main)

    # 选择颜色
    color = COLORS['val'] if 'Val' in dataset_name else COLORS['train']

    # === 主散点图 - 使用密度着色 ===
    # 计算点密度
    xy = np.vstack([y_pred, y_true])
    try:
        z = gaussian_kde(xy)(xy)
        # 根据密度排序，让高密度点在上面
        idx = z.argsort()
        y_pred_sorted, y_true_sorted, z_sorted = y_pred[idx], y_true[idx], z[idx]
    except:
        y_pred_sorted, y_true_sorted = y_pred, y_true
        z_sorted = np.ones_like(y_pred)

    # 绘制散点，颜色映射到密度
    scatter = ax_main.scatter(y_pred_sorted, y_true_sorted,
                             c=z_sorted, s=60,
                             cmap='viridis',
                             alpha=0.7,
                             edgecolors='white',
                             linewidth=0.5)

    # 添加颜色条
    cbar = plt.colorbar(scatter, ax=ax_main, pad=0.15, fraction=0.046)
    cbar.set_label('Density', rotation=270, labelpad=20, fontsize=11, fontweight='bold')
    cbar.ax.tick_params(labelsize=9)

    # 添加对角线（理想预测线）
    lim_min = min(y_true.min(), y_pred.min())
    lim_max = max(y_true.max(), y_pred.max())
    margin = (lim_max - lim_min) * 0.05
    lim_min -= margin
    lim_max += margin

    ax_main.plot([lim_min, lim_max], [lim_min, lim_max],
                 '--', color=COLORS['secondary'], linewidth=2.5,
                 label='Perfect Prediction', alpha=0.9, zorder=5)

    # 添加回归线
    from scipy.stats import linregress
    slope, intercept, _, _, _ = linregress(y_pred, y_true)
    line_x = np.array([lim_min, lim_max])
    line_y = slope * line_x + intercept
    ax_main.plot(line_x, line_y, '-', color=COLORS['accent'],
                linewidth=2, label=f'Fit (y={slope:.2f}x+{intercept:.2f})',
                alpha=0.8, zorder=4)

    # 设置主图样式
    ax_main.set_xlabel('Predicted Value (ΔΔG)', fontsize=14, fontweight='bold', color=COLORS['text'])
    ax_main.set_ylabel('True Value (ΔΔG)', fontsize=14, fontweight='bold', color=COLORS['text'])
    ax_main.grid(True, alpha=0.3, linestyle='--', linewidth=0.8, color=COLORS['grid'])
    ax_main.set_axisbelow(True)
    ax_main.legend(loc='upper left', fontsize=11, framealpha=0.95,
                  edgecolor=COLORS['grid'], fancybox=True, shadow=True)

    # 设置坐标轴范围
    ax_main.set_xlim(lim_min, lim_max)
    ax_main.set_ylim(lim_min, lim_max)

    # 添加评估指标框
    metrics_text = (
        f'n = {n_samples}\n'
        f'PCC = {pearson_corr:.4f}\n'
        f'R² = {r2:.4f}\n'
        f'MAE = {mae:.4f}\n'
        f'RMSE = {rmse:.4f}'
    )

    bbox_props = dict(boxstyle='round,pad=0.8',
                     facecolor='white',
                     edgecolor=COLORS['primary'],
                     linewidth=2,
                     alpha=0.95)

    ax_main.text(0.97, 0.03, metrics_text,
                transform=ax_main.transAxes,
                fontsize=12,
                verticalalignment='bottom',
                horizontalalignment='right',
                fontfamily='monospace',
                bbox=bbox_props)

    # === 顶部边缘分布 - KDE + 直方图 ===
    ax_top.hist(y_pred, bins=25, color=color, alpha=0.4,
               edgecolor='black', linewidth=1, density=True)

    # 添加KDE曲线
    try:
        kde_pred = gaussian_kde(y_pred)
        x_range = np.linspace(lim_min, lim_max, 200)
        ax_top.plot(x_range, kde_pred(x_range), color=color,
                   linewidth=2.5, label='KDE')
        ax_top.fill_between(x_range, kde_pred(x_range), alpha=0.3, color=color)
    except:
        pass

    ax_top.set_ylabel('Density', fontsize=10, fontweight='bold')
    ax_top.tick_params(labelbottom=False, labelsize=9)
    ax_top.grid(True, alpha=0.3, axis='y', linestyle='--', linewidth=0.8)
    ax_top.set_xlim(lim_min, lim_max)

    # === 右侧边缘分布 - KDE + 直方图 ===
    ax_right.hist(y_true, bins=25, orientation='horizontal',
                 color=color, alpha=0.4, edgecolor='black',
                 linewidth=1, density=True)

    # 添加KDE曲线
    try:
        kde_true = gaussian_kde(y_true)
        y_range = np.linspace(lim_min, lim_max, 200)
        ax_right.plot(kde_true(y_range), y_range, color=color,
                     linewidth=2.5, label='KDE')
        ax_right.fill_betweenx(y_range, kde_true(y_range), alpha=0.3, color=color)
    except:
        pass

    ax_right.set_xlabel('Density', fontsize=10, fontweight='bold')
    ax_right.tick_params(labelleft=False, labelsize=9)
    ax_right.grid(True, alpha=0.3, axis='x', linestyle='--', linewidth=0.8)
    ax_right.set_ylim(lim_min, lim_max)

    # 添加总标题
    fig.suptitle(f'{dataset_name} Set: Prediction vs Truth Analysis',
                 fontsize=18, fontweight='bold', y=0.98, color=COLORS['text'])

    # 保存图片
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"✓ Enhanced figure saved: {save_path}")

    plt.show()
    return fig


def plot_combined_datasets(train_true, train_pred, val_true, val_pred, save_path=None):
    """
    在同一图中绘制训练集和验证集的预测结果（优化版）

    参数:
        train_true, train_pred: 训练集真实值和预测值
        val_true, val_pred: 验证集真实值和预测值
        save_path: 保存路径
    """
    fig, axes = plt.subplots(1, 2, figsize=(18, 8))

    datasets = [
        (train_true, train_pred, 'Training', COLORS['train'], axes[0]),
        (val_true, val_pred, 'Validation', COLORS['val'], axes[1])
    ]

    for y_true, y_pred, name, color, ax in datasets:
        # 计算指标
        pearson_corr, _ = pearsonr(y_true, y_pred)
        r2 = r2_score(y_true, y_pred)
        mae = mean_absolute_error(y_true, y_pred)
        rmse = sqrt(mean_squared_error(y_true, y_pred))
        n_samples = len(y_true)

        # 密度着色散点图
        xy = np.vstack([y_pred, y_true])
        try:
            z = gaussian_kde(xy)(xy)
            idx = z.argsort()
            y_pred_sorted, y_true_sorted, z_sorted = y_pred[idx], y_true[idx], z[idx]
        except:
            y_pred_sorted, y_true_sorted = y_pred, y_true
            z_sorted = np.ones_like(y_pred)

        scatter = ax.scatter(y_pred_sorted, y_true_sorted,
                           c=z_sorted, s=70,
                           cmap='plasma',
                           alpha=0.7,
                           edgecolors='white',
                           linewidth=0.5)

        # 添加颜色条
        cbar = plt.colorbar(scatter, ax=ax, pad=0.02, fraction=0.046)
        cbar.set_label('Density', rotation=270, labelpad=15, fontsize=10)

        # 对角线
        lim_min = min(y_true.min(), y_pred.min())
        lim_max = max(y_true.max(), y_pred.max())
        margin = (lim_max - lim_min) * 0.05
        lim_min -= margin
        lim_max += margin

        ax.plot([lim_min, lim_max], [lim_min, lim_max],
               '--', color=COLORS['secondary'], linewidth=2.5,
               label='Perfect Prediction', alpha=0.9, zorder=5)

        # 回归线
        from scipy.stats import linregress
        slope, intercept, _, _, _ = linregress(y_pred, y_true)
        line_x = np.array([lim_min, lim_max])
        line_y = slope * line_x + intercept
        ax.plot(line_x, line_y, '-', color=COLORS['accent'],
               linewidth=2, label=f'Fit (y={slope:.2f}x+{intercept:.2f})',
               alpha=0.8, zorder=4)

        # 标签和标题
        ax.set_xlabel('Predicted Value (ΔΔG)', fontsize=13, fontweight='bold', color=COLORS['text'])
        ax.set_ylabel('True Value (ΔΔG)', fontsize=13, fontweight='bold', color=COLORS['text'])
        ax.set_title(f'{name} Set (n={n_samples})', fontsize=15, fontweight='bold',
                    color=COLORS['text'], pad=15)
        ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.8, color=COLORS['grid'])
        ax.set_axisbelow(True)
        ax.legend(loc='upper left', fontsize=10, framealpha=0.95,
                 edgecolor=COLORS['grid'], fancybox=True, shadow=True)

        ax.set_xlim(lim_min, lim_max)
        ax.set_ylim(lim_min, lim_max)

        # 添加指标框
        metrics_text = (
            f'PCC = {pearson_corr:.4f}\n'
            f'R² = {r2:.4f}\n'
            f'MAE = {mae:.4f}\n'
            f'RMSE = {rmse:.4f}'
        )

        bbox_props = dict(boxstyle='round,pad=0.7',
                         facecolor='white',
                         edgecolor=color,
                         linewidth=2,
                         alpha=0.95)

        ax.text(0.97, 0.03, metrics_text,
               transform=ax.transAxes,
               fontsize=11,
               verticalalignment='bottom',
               horizontalalignment='right',
               fontfamily='monospace',
               bbox=bbox_props)

    # 总标题
    fig.suptitle('Training vs Validation Set Comparison',
                fontsize=18, fontweight='bold', y=0.98, color=COLORS['text'])

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"✓ Combined figure saved: {save_path}")

    plt.show()
    return fig


def plot_residuals(y_true, y_pred, dataset_name='Validation', save_path=None):
    """
    绘制残差分析图

    参数:
        y_true: 真实值数组
        y_pred: 预测值数组
        dataset_name: 数据集名称
        save_path: 保存路径
    """
    residuals = y_true - y_pred
    color = COLORS['val'] if 'Val' in dataset_name else COLORS['train']

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # 1. 残差 vs 预测值
    ax1 = axes[0]
    ax1.scatter(y_pred, residuals, alpha=0.6, s=50, c=color,
               edgecolors='black', linewidth=0.5)
    ax1.axhline(y=0, color=COLORS['secondary'], linestyle='--', linewidth=2)
    ax1.set_xlabel('Predicted Value (ΔΔG)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Residuals (True - Predicted)', fontsize=12, fontweight='bold')
    ax1.set_title('Residual Plot', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3, linestyle='--')

    # 2. 残差分布直方图
    ax2 = axes[1]
    ax2.hist(residuals, bins=25, color=color, alpha=0.7,
            edgecolor='black', linewidth=1, density=True)
    # 添加正态分布曲线
    from scipy.stats import norm
    mu, std = residuals.mean(), residuals.std()
    x_range = np.linspace(residuals.min(), residuals.max(), 100)
    ax2.plot(x_range, norm.pdf(x_range, mu, std),
            'r-', linewidth=2.5, label=f'Normal(μ={mu:.2f}, σ={std:.2f})')
    ax2.set_xlabel('Residuals', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Density', fontsize=12, fontweight='bold')
    ax2.set_title('Residual Distribution', fontsize=14, fontweight='bold')
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3, axis='y', linestyle='--')

    # 3. Q-Q plot
    ax3 = axes[2]
    from scipy.stats import probplot
    probplot(residuals, dist="norm", plot=ax3)
    ax3.set_title('Q-Q Plot', fontsize=14, fontweight='bold')
    ax3.grid(True, alpha=0.3, linestyle='--')

    fig.suptitle(f'{dataset_name} Set: Residual Analysis',
                fontsize=16, fontweight='bold', y=1.02, color=COLORS['text'])
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"✓ Residual plot saved: {save_path}")

    plt.show()
    return fig


def main():
    """主函数：读取数据并绘图"""

    # 设置路径
    base_dir = '../output_test/predictions'
    output_dir = '../output_test/figures'

    # 创建输出目录
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print("\n" + "="*70)
    print(" " * 15 + "🎨 Enhanced Prediction Visualization")
    print("="*70)

    # 检查数据文件是否存在
    if not os.path.exists(base_dir):
        print(f"❌ Error: Predictions directory not found: {base_dir}")
        print("Please run main_test.py first to generate predictions.")
        return

    # 读取数据
    try:
        train_true = np.load(f'{base_dir}/train_true.npy')
        train_pred = np.load(f'{base_dir}/train_predict.npy')
        val_true = np.load(f'{base_dir}/val_true.npy')
        val_pred = np.load(f'{base_dir}/val_predict.npy')

        print(f"\n📊 Data loaded successfully:")
        print(f"   • Training set: {len(train_true)} samples")
        print(f"   • Validation set: {len(val_true)} samples")
        print(f"   • Total: {len(train_true) + len(val_true)} samples")

    except FileNotFoundError as e:
        print(f"❌ Error: Could not load prediction files: {e}")
        print("Please run main_test.py first to generate predictions.")
        return

    print("\n" + "-"*70)
    print("Generating plots...")
    print("-"*70 + "\n")

    # 绘图1: 验证集 - 增强版
    print("[1/5] Creating validation set enhanced plot...")
    plot_predictions_enhanced(
        val_true, val_pred,
        dataset_name='Validation',
        save_path=f'{output_dir}/validation_enhanced.png'
    )

    # 绘图2: 训练集 - 增强版
    print("\n[2/5] Creating training set enhanced plot...")
    plot_predictions_enhanced(
        train_true, train_pred,
        dataset_name='Training',
        save_path=f'{output_dir}/training_enhanced.png'
    )

    # 绘图3: 训练集和验证集对比
    print("\n[3/5] Creating combined comparison plot...")
    plot_combined_datasets(
        train_true, train_pred, val_true, val_pred,
        save_path=f'{output_dir}/combined_comparison.png'
    )

    # 绘图4: 验证集残差分析
    print("\n[4/5] Creating validation residual analysis...")
    plot_residuals(
        val_true, val_pred,
        dataset_name='Validation',
        save_path=f'{output_dir}/validation_residuals.png'
    )

    # 绘图5: 训练集残差分析
    print("\n[5/5] Creating training residual analysis...")
    plot_residuals(
        train_true, train_pred,
        dataset_name='Training',
        save_path=f'{output_dir}/training_residuals.png'
    )

    print("\n" + "="*70)
    print("✨ All plots generated successfully!")
    print("="*70)
    print(f"\n📁 Figures saved in: {output_dir}")
    print("\nGenerated files:")
    print("   1. validation_enhanced.png - Validation set with density & KDE")
    print("   2. training_enhanced.png - Training set with density & KDE")
    print("   3. combined_comparison.png - Side-by-side comparison")
    print("   4. validation_residuals.png - Validation residual analysis")
    print("   5. training_residuals.png - Training residual analysis")
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
