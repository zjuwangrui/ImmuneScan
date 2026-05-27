 ImmuneAI-Screener (ImmuneAI-Screener/)

  目标：从头设计能被 T 细胞识别、并与特定 HLA 等位基因（如 HLA-A*0201）结合的多肽序列（肽段幻觉生成）。

  算法流程

  初始化氨基酸频率矩阵（BLOSUM62 + IEDB 数据库）
    → 模拟退火优化（Simulated Annealing）
    → 多目标损失：TCR 相似度 + IEDB 数据库相似度 + CDR 匹配度
    → 输出最优 9-mer 肽段序列

  ---
  两个项目的关系

  ImmuneAI-Screener                    AttABseq
  设计候选肽段序列    →    预测与 TCR/抗体的结合亲和力变化
  （生成阶段）                        （评估阶段）

  两者可串联使用：先用 ImmuneAI 生成候选肽，再用 AttABseq 评估结合能力，形成生成-评估闭环。

  ---
  技术栈总结

  - 框架：PyTorch（Transformer + 1D CNN）
  - 生信工具：NCBI BLAST（PSSM 生成）
  - 优化器：RAdam + Lookahead
  - 可解释性：注意力权重热图（Seaborn/Matplotlib）
  - 评估指标：Pearson 相关系数、MAE、RMSE、R²