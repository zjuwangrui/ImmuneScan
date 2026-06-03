数据来源说明
每条突变来自真实的肿瘤基因组数据库（TCGA、COSMIC、UniProt P01116/P04637/P15056/P00533）：

基因	突变	蛋白位置	Context 来源	癌症类型	发生频率
KRAS	G12D	第12位 G→D	UniProt P01116, 位置5–19	胰腺癌（~40%）、结直肠癌	极高
KRAS	G12V	第12位 G→V	同上	肺腺癌、胰腺癌	极高
KRAS	Q61H	第61位 Q→H	UniProt P01116, 位置55–69	多种实体瘤	中
TP53	R175H	第175位 R→H	UniProt P04637, 位置173–187	结直肠癌、乳腺癌	极高（最常见 TP53 热点）
BRAF	V600E	第600位 V→E	UniProt P15056，DFG激酶活化环，位置594–608	黑色素瘤（~50%）、甲状腺癌	极高
EGFR	L858R	第858位 L→R	UniProt P00533，激酶活化环，位置851–865	肺腺癌（~15%）	高
Context 序列说明（以 KRAS G12D 为例）：


KLVVVGAGGVGKSAL   ← 蛋白第5–19位（UniProt P01116）
       ^
       pos=8 → 对应蛋白第12位 G (G12)
       野生型: G → 突变型: D
滑窗后每条突变可产生 3–7 个 9-mer，6条突变共产生 ~40 个候选肽。

运行结果评估标准
运行 python agent/run.py 后，对结果按三个维度判断质量：

1. HLA 结合力（IC50 / %Rank）

IC50 < 50 nM 且 %Rank < 0.5% → 强结合，是临床级别候选
IC50 < 500 nM 且 %Rank < 2% → 有效结合
KRAS G12D 和 BRAF V600E 的肽段应能看到 IC50 较低（已有文献报道 HLA-A*02:01 结合肽）
2. MCMC 优化效果

优化后 optimized_peptide 与原 peptide 不同 → MCMC 有效探索了序列空间
mcmc_loss 越低越好，合理范围 1.5–3.0
3. 生物学合理性检验

KRAS G12D/G12V 的候选肽（如 VVGADGVGK、VVGAVGVGK）已在 Moderna mRNA-4359 临床试验中使用，可与文献对比
BRAF V600E 肽段 GDFGLATEК 已在 Robbins et al. 2013 中报道为 HLA-A*02:01 结合肽