# -*- coding: utf-8 -*-
"""
@Time:Created on 2021/9/17
@author: Ruofan Jin
@Filename: main_test.py (快速测试版)
@Software: PyCharm
"""
import pandas as pd
import torch
from numpy import *
import numpy as np
import random
import time
# 导入测试版模型文件
from model_test import *
import timeit
import matplotlib.pyplot as plt
from pytorchtools import EarlyStopping
#from data import diction,dataset
import sys   #导入sys模块
sys.path.append("../")
from data.load import split


def get_test_config():
    """
    获取测试配置参数 - 方便调试
    可以在这里修改网络参数进行快速测试
    """
    config = {
        # 数据参数
        'n_samples': 100,        # 使用的样本数量
        'train_ratio': 0.8,      # 训练集比例
        
        # 网络架构参数
        'hid_dim': 64,           # 隐藏层维度 (原为256)
        'n_layers': 2,           # 网络层数 (原为3)
        'n_heads': 4,            # 注意力头数 (原为8)
        'pf_dim': 32,            # 前馈网络维度 (原为64)
        'kernel_size': 5,        # 卷积核大小 (原为7)
        
        # 训练参数
        'batch_size': 2,         # 批次大小 (原为8)
        'learning_rate': 0.001,  # 学习率 (原为0.0001)
        'epochs': 10,            # 训练轮数 (原为150)
        'patience': 3,           # 早停耐心值 (原为7)
        
        # 其他参数
        'dropout': 0.1,
        'weight_decay': 1e-4,
    }
    return config


def print_config(config):
    """打印配置信息"""
    print("\n=== 测试配置参数 ===")
    print(f"数据: {config['n_samples']}个样本, 训练比例: {config['train_ratio']}")
    print(f"网络: hid_dim={config['hid_dim']}, layers={config['n_layers']}, heads={config['n_heads']}")
    print(f"训练: batch={config['batch_size']}, lr={config['learning_rate']}, epochs={config['epochs']}")
    print("========================\n")


def load_tensor(file_name, dtype):
    return [dtype(d).to(device) for d in np.load(file_name + '.npy', allow_pickle=True)]



if __name__ == "__main__":
    # 获取配置参数
    config = get_test_config()
    print_config(config)
    
    SEED = 1234
    random.seed(SEED)
    torch.manual_seed(SEED)

    """CPU or GPU"""
    if torch.cuda.is_available():
        device = torch.device('cuda')
        print('The code uses GPU...')
    else:
        device = torch.device('cpu')
        print('The code uses CPU!!!')

    """Load preprocessed data."""
    csv = pd.read_csv('../data/AB1101order.csv',usecols=['PDB','Mutation','antibody_light_seq','antibody_heavy_seq','antigen_a_seq','antigen_b_seq','antibody_light_seq_mut','antibody_heavy_seq_mut','antigen_a_seq_mut','antigen_b_seq_mut', 'ddG'])
    
    # 快速测试：使用配置中指定的样本数量
    csv = csv.head(config['n_samples'])
    print(f"Using {len(csv)} samples for quick testing...")
    
    names = csv['PDB'].tolist()
    abls = csv['antibody_light_seq'].tolist()
    abhs = csv['antibody_heavy_seq'].tolist()
    agas = csv['antigen_a_seq'].tolist()
    agbs = csv['antigen_b_seq'].tolist()
    abls_m = csv['antibody_light_seq_mut'].tolist()
    abhs_m = csv['antibody_heavy_seq_mut'].tolist()
    agas_m = csv['antigen_a_seq_mut'].tolist()
    agbs_m = csv['antigen_b_seq_mut'].tolist()
    labels = csv['ddG'].tolist()

    interactions = np.array(labels)
    
    # 加载对应的数据切片
    antibodies_full = np.load('../data/antibody.npy', allow_pickle=True)
    antigens_full = np.load('../data/antigen.npy', allow_pickle=True)
    antibodies_mut_full = np.load('../data/antibody_mut.npy', allow_pickle=True)
    antigens_mut_full = np.load('../data/antigen_mut.npy', allow_pickle=True)
    
    # 只取前100条数据
    antibodies = antibodies_full[:100]
    antigens = antigens_full[:100]
    antibodies_mut = antibodies_mut_full[:100]
    antigens_mut = antigens_mut_full[:100]

    """Start training."""
    print('Training...')

    # 基于配置的简单划分
    n_samples = len(interactions)
    n_train = int(config['train_ratio'] * n_samples)
    train_index = list(range(n_train))
    val_index = list(range(n_train, n_samples))
    
    print(f"Training samples: {len(train_index)}, Validation samples: {len(val_index)}")

    """ create model ,trainer and tester """
    # 使用配置参数创建模型
    antibody_dim = 20
    antigen_dim = 20
    hid_dim = config['hid_dim']
    n_layers = config['n_layers'] 
    n_heads = config['n_heads']
    pf_dim = config['pf_dim']
    dropout = config['dropout']
    batch = config['batch_size']
    lr = config['learning_rate']
    weight_decay = config['weight_decay']
    decay_interval = 5
    lr_decay = 1
    iteration = config['epochs']
    kernel_size = config['kernel_size']
    minloss = 1000
    best_pearson = -1000
    best_r2 = -1000

    print(f"Creating model with dynamic dimensions...")
    print(f"Network: hid_dim={hid_dim}, layers={n_layers}, heads={n_heads}, kernel={kernel_size}")
    print(f"Training: batch={batch}, lr={lr}, epochs={iteration}")

    # 创建测试版模型 - 传入hid_dim参数
    encoder = Encoder(antibody_dim, hid_dim, n_layers, kernel_size, dropout, device)
    decoder = Decoder(antigen_dim, hid_dim, n_layers, n_heads, pf_dim, DecoderLayer, SelfAttention, PositionwiseFeedforward, dropout, device)

    # 使用TestPredictor并传入hid_dim参数
    model = TestPredictor(encoder, decoder, device, hid_dim)
    model.to(device)

    trainer = Trainer(model, lr, weight_decay, batch)
    tester = Tester(model)

    # 创建测试输出目录
    import os
    test_output_dir = '../output_test'
    if not os.path.exists(test_output_dir):
        os.makedirs(test_output_dir)
        os.makedirs(f'{test_output_dir}/loss_min_result')
        os.makedirs(f'{test_output_dir}/loss_min_model')
        os.makedirs(f'{test_output_dir}/best_pcc_result')
        os.makedirs(f'{test_output_dir}/best_pcc_model')
        os.makedirs(f'{test_output_dir}/best_r2_result')
        os.makedirs(f'{test_output_dir}/best_r2_model')

    antigens_train, antigens_val = np.array(antigens)[train_index], np.array(antigens)[val_index]  # ag
    antibodies_train, antibodies_val = np.array(antibodies)[train_index], np.array(antibodies)[val_index]  # ab
    antigens_mut_train, antigens_mut_val = np.array(antigens_mut)[train_index], np.array(antigens_mut)[val_index]  # ag_mut
    antibodies_mut_train, antibodies_mut_val = np.array(antibodies_mut)[train_index], np.array(antibodies_mut)[val_index]  # ab_mut
    interactions_train, interactions_val = np.array(interactions)[train_index], np.array(interactions)[val_index]  # Y

    dataset_train = list(zip(antigens_train, antibodies_train, antigens_mut_train, antibodies_mut_train, interactions_train))
    dataset_val = list(zip(antigens_val, antibodies_val, antigens_mut_val, antibodies_mut_val, interactions_val))

    """Output files."""
    file_loss_min_PCCS = f'{test_output_dir}/loss_min_result/RECORD.txt'
    file_loss_min_model = f'{test_output_dir}/loss_min_model/model'
    file_best_pcc_PCCS = f'{test_output_dir}/best_pcc_result/RECORD.txt'
    file_best_pcc_model = f'{test_output_dir}/best_pcc_model/model'
    file_best_r2_PCCS = f'{test_output_dir}/best_r2_result/RECORD.txt'
    file_best_r2_model = f'{test_output_dir}/best_r2_model/model'
    
    PCCS = ('Epoch\tTime(sec)\tLoss_train\tLoss_val\tpearson\tmae\tmse\trmse\tr2')
    print(PCCS)

    with open(file_loss_min_PCCS, 'w') as f:
        f.write(PCCS + '\n')
    with open(file_best_pcc_PCCS, 'w') as f:
        f.write(PCCS + '\n')
    with open(file_best_r2_PCCS, 'w') as f:
        f.write(PCCS + '\n')

    start = timeit.default_timer()
        
    # 使用配置中的早停参数
    early_stopping = EarlyStopping(patience=config['patience'], verbose=True)
    
    print("Starting quick test training...")
    for epoch in range(1, iteration + 1):

        print(f'Epoch: {epoch}/{iteration}')
        loss_train_fold, y_train_true, y_train_predict = trainer.train(dataset_train, device, epoch)
        pccs_val, mae_val, mse_val, rmse_val, r2_val, loss_val_fold, y_val_true, y_val_predict = tester.test(dataset_val, epoch)
        
        print(f'Results - Loss: {loss_val_fold:.4f}, Pearson: {pccs_val:.4f}, MAE: {mae_val:.4f}, R2: {r2_val:.4f}')
        
        end = timeit.default_timer()
        time = end - start
            
        early_stopping(loss_val_fold.tolist(), model, file_loss_min_model)
        if early_stopping.early_stop:
            print('Early stopping!')
            break

        PCCS = [epoch, time, loss_train_fold.tolist(), loss_val_fold.tolist(), pccs_val.tolist(), mae_val, mse_val, rmse_val, r2_val]
        
        if loss_val_fold.tolist() < minloss:
            tester.save_pccs(PCCS, file_loss_min_PCCS)
            tester.save_model(model, file_loss_min_model)
            minloss = loss_val_fold.tolist()
            print(f"New best loss: {minloss:.4f}")
        
        if pccs_val.tolist() > best_pearson:
            tester.save_pccs(PCCS, file_best_pcc_PCCS)
            tester.save_model(model, file_best_pcc_model)
            best_pearson = pccs_val.tolist()
            print(f"New best Pearson: {best_pearson:.4f}")
        
        if r2_val > best_r2:
            tester.save_pccs(PCCS, file_best_r2_PCCS)
            tester.save_model(model, file_best_r2_model)
            best_r2 = r2_val
            print(f"New best R2: {best_r2:.4f}")

        print('\t'.join(map(str, PCCS)))
    
    print("\nQuick test training completed!")
    print(f"Best Loss: {minloss:.4f}")
    print(f"Best Pearson: {best_pearson:.4f}")
    print(f"Best R2: {best_r2:.4f}")
    print(f"Results saved in: {test_output_dir}")

    # ========== 保存最终的预测值和真实值用于绘图 ==========
    print("\n" + "="*50)
    print("Saving predictions for visualization...")
    print("="*50)

    # 使用最佳R2模型进行最终预测
    model.load_state_dict(torch.load(file_best_r2_model))
    model.eval()

    # 获取训练集和验证集的预测值
    with torch.no_grad():
        # 验证集预测
        _, _, _, _, _, _, y_val_true_final, y_val_predict_final = tester.test(dataset_val, iteration)

        # 训练集预测（不需要反向传播）
        T_train = torch.zeros((1,0), device=device)
        Y_train = torch.zeros((1,0), device=device)
        for data in dataset_train:
            ag_s, ab_s, ag_m_s, ab_m_s, labels = [], [], [], [], []
            ag, ab, agm, abm, label = data
            ag_s.append(ag)
            ab_s.append(ab)
            ag_m_s.append(agm)
            ab_m_s.append(abm)
            labels.append(label)
            from model_test import pack
            data_pack = pack(ag_s, ab_s, ag_m_s, ab_m_s, labels, device)
            correct, predicted = model(data_pack, iteration, train=False)
            T_train = torch.cat([T_train, correct.view(1,-1)], dim=-1)
            Y_train = torch.cat([Y_train, predicted.view(1,-1)], dim=-1)

        y_train_true_final = T_train.squeeze().cpu().numpy()
        y_train_predict_final = Y_train.squeeze().cpu().numpy()

    # 保存预测结果
    predictions_dir = f'{test_output_dir}/predictions'
    if not os.path.exists(predictions_dir):
        os.makedirs(predictions_dir)

    # 保存为numpy数组
    np.save(f'{predictions_dir}/train_true.npy', y_train_true_final)
    np.save(f'{predictions_dir}/train_predict.npy', y_train_predict_final)
    np.save(f'{predictions_dir}/val_true.npy', y_val_true_final)
    np.save(f'{predictions_dir}/val_predict.npy', y_val_predict_final)

    # 同时保存为CSV格式（方便查看）
    train_df = pd.DataFrame({
        'true_value': y_train_true_final,
        'predicted_value': y_train_predict_final,
        'dataset': 'train'
    })
    val_df = pd.DataFrame({
        'true_value': y_val_true_final,
        'predicted_value': y_val_predict_final,
        'dataset': 'validation'
    })
    combined_df = pd.concat([train_df, val_df], ignore_index=True)
    combined_df.to_csv(f'{predictions_dir}/predictions.csv', index=False)

    print(f"Predictions saved to: {predictions_dir}")
    print(f"  - Train samples: {len(y_train_true_final)}")
    print(f"  - Validation samples: {len(y_val_true_final)}")
    print(f"  - Total samples: {len(combined_df)}")

    # ========== 注意力权重矩阵提取 ==========
    print("\n" + "="*50)
    print("Extracting attention weights...")
    print("="*50)

    # 创建注意力输出目录
    attention_dir = '../output_test/attention_matrices'
    if not os.path.exists(attention_dir):
        os.makedirs(attention_dir)

    # 提取验证集的注意力权重
    model.eval()
    all_attention_data = []

    with torch.no_grad():
        for idx, data in enumerate(dataset_val[:5]):  # 只提取前5个样本作为示例
            ag_s, ab_s, ag_m_s, ab_m_s, labels = [], [], [], [], []
            ag, ab, agm, abm, label = data
            ag_s.append(ag)
            ab_s.append(ab)
            ag_m_s.append(agm)
            ab_m_s.append(abm)
            labels.append(label)

            from model_test import pack
            data_pack = pack(ag_s, ab_s, ag_m_s, ab_m_s, labels, device)

            # 获取注意力权重
            correct, predicted, attention_dict = model(data_pack, itera=0, train=False, return_attention=True)

            # 处理注意力矩阵
            ag_ab_attns = attention_dict['ag_ab_attns']  # 抗原看抗体
            ab_ag_attns = attention_dict['ab_ag_attns']  # 抗体看抗原
            ag_s_num = attention_dict['ag_s_num'][0]
            ab_s_num = attention_dict['ab_s_num'][0]

            # 平均所有层和所有头的注意力
            # ag_ab_attns是一个列表，每个元素是 [batch=1, n_heads, ag_len, ab_len]
            ag_ab_attn_avg = torch.stack([attn.mean(dim=1) for attn in ag_ab_attns]).mean(dim=0)  # [1, ag_len, ab_len]
            ab_ag_attn_avg = torch.stack([attn.mean(dim=1) for attn in ab_ag_attns]).mean(dim=0)  # [1, ab_len, ag_len]

            # 取第一个batch（因为batch=1）
            ag_ab_attn = ag_ab_attn_avg[0]  # [ag_len, ab_len]
            ab_ag_attn = ab_ag_attn_avg[0]  # [ab_len, ag_len]

            # 裁剪到实际序列长度
            ag_ab_attn = ag_ab_attn[:ag_s_num, :ab_s_num]  # [真实ag_len, 真实ab_len]
            ab_ag_attn = ab_ag_attn[:ab_s_num, :ag_s_num]  # [真实ab_len, 真实ag_len]

            # 计算交叉注意力：抗原i和抗体j残基的归一化注意力权重
            # ag_ab_attn[i, j] = 抗原i看抗体j的注意力
            # ab_ag_attn[j, i] = 抗体j看抗原i的注意力
            # 交叉注意力矩阵 = ag_ab_attn * ab_ag_attn.T
            cross_attention = ag_ab_attn * ab_ag_attn.t()

            # Min-Max归一化到[0, 1]区间
            min_val = cross_attention.min()
            max_val = cross_attention.max()
            if max_val - min_val > 1e-10:
                cross_attention_normalized = (cross_attention - min_val) / (max_val - min_val)
            else:
                cross_attention_normalized = torch.zeros_like(cross_attention)

            # 转换为numpy并保存
            cross_attention_np = cross_attention_normalized.cpu().numpy()

            # 获取对应的PDB ID和序列信息
            sample_idx = val_index[idx]
            pdb_id = names[sample_idx]

            # 保存数据
            attention_data = {
                'pdb_id': pdb_id,
                'sample_idx': sample_idx,
                'ag_length': ag_s_num,
                'ab_length': ab_s_num,
                'cross_attention_matrix': cross_attention_np,
                'ag_ab_attention': ag_ab_attn.cpu().numpy(),
                'ab_ag_attention': ab_ag_attn.cpu().numpy(),
                'true_ddG': label,
                'predicted_ddG': predicted.item()
            }

            all_attention_data.append(attention_data)

            # 保存单个矩阵
            np.save(f'{attention_dir}/cross_attention_{pdb_id}_sample{idx}.npy', cross_attention_np)

            # 保存详细信息到文本文件
            with open(f'{attention_dir}/attention_info_{pdb_id}_sample{idx}.txt', 'w') as f:
                f.write(f"PDB ID: {pdb_id}\n")
                f.write(f"Sample Index: {sample_idx}\n")
                f.write(f"Antigen Length: {ag_s_num}\n")
                f.write(f"Antibody Length: {ab_s_num}\n")
                f.write(f"True ddG: {label:.4f}\n")
                f.write(f"Predicted ddG: {predicted.item():.4f}\n")
                f.write(f"Cross Attention Matrix Shape: {cross_attention_np.shape}\n")
                f.write(f"\nMatrix statistics:\n")
                f.write(f"  Min: {cross_attention_np.min():.6f}\n")
                f.write(f"  Max: {cross_attention_np.max():.6f}\n")
                f.write(f"  Mean: {cross_attention_np.mean():.6f}\n")
                f.write(f"  Std: {cross_attention_np.std():.6f}\n")

            print(f"Sample {idx+1}: {pdb_id} - Attention matrix saved ({ag_s_num}x{ab_s_num})")

    # 保存汇总信息
    import pickle
    with open(f'{attention_dir}/all_attention_data.pkl', 'wb') as f:
        pickle.dump(all_attention_data, f)

    print(f"\nAttention matrices saved to: {attention_dir}")
    print(f"Total samples processed: {len(all_attention_data)}")