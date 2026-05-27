  AI_project/                                                                                                                                   
  ├── config.py                    ← 所有路径/超参集中配置                                                                                      
  ├── requirements.txt             ← pip install -r requirements.txt                                                                            
  │                                                                                                                                             
  ├── agent/                                                                                                                                    
  │   ├── agent.py                 ← Claude API tool_use 主循环 + 排名逻辑                                                                    
  │   └── run.py                   ← CLI 入口
  │
  ├── tools/
  │   ├── mutation_processor.py    ← 突变 → 9-mer 候选肽（滑窗）
  │   ├── dl_scorer.py             ← 调 AttABseq → ddG 分数
  │   ├── mcmc_optimizer.py        ← 调 ImmuneAI → SA 优化
  │   └── netmhc_validator.py      ← 调 mhcflurry → HLA 结合预测
  │
  ├── models/
  │   ├── attabseq/                ← 原 atta_less/script/，新增 predict_api.py
  │   └── immuneai/                ← 原 ImmuneAI-Screener/，已修复3处问题
  │       ├── Loss.py              ← RNN 改为懒加载 + fallback（structure_loss=0）
  │       ├── process.py           ← sys.exit() → break，Simulated_Annealing 加返回值
  │       └── main.py              ← 新增 run_immuneai()，硬编码路径改为 config 注入
  │
  ├── data/
  │   ├── attabseq/                ← CSV + npy 特征文件
  │   └── immuneai/                ← TCR + IEDB 数据库文件
  │
  └── checkpoints/
      └── attabseq/                ← 3 个预训练模型权重

  运行方式：
  # 安装依赖
  pip install -r requirements.txt
  mhcflurry-downloads fetch

  # 运行 Agent
  python agent/run.py \
    --hla "HLA-A*02:01" \
    --mutations '[{"gene":"TP53","pos":4,"wt":"R","mut":"W","context":"VVRCPHHERCSDSD"}]'