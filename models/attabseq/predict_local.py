# -*- coding: utf-8 -*-
"""
@Time:Created on 2019/9/17 8:54
@author: LiFan Chen
@Filename: predict.py (本地环境修复版)
@Software: PyCharm
"""
import pandas as pd
import torch
from numpy import *
import numpy as np
import random
import time
from model import *
import timeit
import matplotlib.pyplot as plt
from sklearn.model_selection import KFold
import os
import argparse
import sys
sys.path.append("../")
from data.load import split


def load_tensor(file_name, dtype):
    return [dtype(d).to(device) for d in np.load(file_name + '.npy', allow_pickle=True)]


if __name__ == "__main__":
    SEED = 42
    random.seed(SEED)
    torch.manual_seed(SEED)

    """CPU or GPU"""
    if torch.cuda.is_available():
        device = torch.device('cuda:0')
        print('The code uses GPU...')
    else:
        device = torch.device('cpu')
        print('The code uses CPU!!!')

    """Load preprocessed data."""
    # 修复：使用本地数据路径和文件名
    data_dir = '../data'
    print(f"Loading data from: {data_dir}")
    
    # 检查文件是否存在
    required_files = ['antibody.npy', 'antibody_mut.npy', 'antigen.npy', 'antigen_mut.npy']
    for file_name in required_files:
        file_path = os.path.join(data_dir, file_name)
        if not os.path.exists(file_path):
            print(f"ERROR: Required file not found: {file_path}")
            print("Please ensure all data files are present in the data directory.")
            exit(1)
        else:
            print(f"✓ Found: {file_name}")
    
    # 加载数据文件（使用本地文件名）
    antibodies = np.load(os.path.join(data_dir, 'antibody.npy'), allow_pickle=True)
    antibodies_mut = np.load(os.path.join(data_dir, 'antibody_mut.npy'), allow_pickle=True)
    antigens = np.load(os.path.join(data_dir, 'antigen.npy'), allow_pickle=True)
    antigens_mut = np.load(os.path.join(data_dir, 'antigen_mut.npy'), allow_pickle=True)
    
    # 从CSV文件获取标签（因为没有Y.npy文件）
    csv_file = os.path.join(data_dir, 'AB1101order.csv')
    if os.path.exists(csv_file):
        print(f"✓ Loading labels from: {csv_file}")
        csv_data = pd.read_csv(csv_file, usecols=['ddG'])
        interactions = np.array(csv_data['ddG'].tolist())
    else:
        print(f"ERROR: CSV file not found: {csv_file}")
        exit(1)
    
    print(f"Data loaded successfully:")
    print(f"  - Antibodies: {len(antibodies)} samples")
    print(f"  - Antigens: {len(antigens)} samples") 
    print(f"  - Labels: {len(interactions)} samples")

    """ create model ,trainer and tester """
    antibody_dim = 20
    antigen_dim = 20
    hid_dim = 256
    n_layers = 3
    n_heads = 8
    pf_dim = 64
    dropout = 0.1
    batch = 8
    lr = 0.00001
    weight_decay = 1e-4
    decay_interval = 5
    lr_decay = 1
    iteration = 10  # 减少迭代次数用于测试
    kernel_size = 7

    print("Creating model...")
    encoder = Encoder(antibody_dim, hid_dim, n_layers, kernel_size, dropout, device)
    decoder = Decoder(antigen_dim, hid_dim, n_layers, n_heads, pf_dim, DecoderLayer, SelfAttention, PositionwiseFeedforward, dropout, device)

    model = Predictor(encoder, decoder, device)
    
    # 修复：检查并加载本地模型文件
    model_dir = '../output1101'
    possible_model_paths = [
        os.path.join(model_dir, 'best_pcc_model', 'model'),
        os.path.join(model_dir, 'best_r2_model', 'model'),
        os.path.join(model_dir, 'loss_min_model', 'model')
    ]
    
    model_loaded = False
    for model_path in possible_model_paths:
        if os.path.exists(model_path):
            try:
                print(f"Loading model from: {model_path}")
                model.load_state_dict(torch.load(model_path, map_location=device))
                model_loaded = True
                print("✓ Model loaded successfully!")
                break
            except Exception as e:
                print(f"Failed to load model from {model_path}: {e}")
                continue
    
    if not model_loaded:
        print("WARNING: No trained model found. Using randomly initialized model.")
        print("Available model paths checked:")
        for path in possible_model_paths:
            print(f"  - {path} (exists: {os.path.exists(path)})")
    
    model.to(device)
    trainer = Trainer(model, lr, weight_decay, batch)
    tester = Tester(model)

    """Start prediction/testing."""
    print('Starting prediction...')

    # 修复：使用本地输出路径
    output_dir = '../output_predict'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")
    
    file_PCCS = os.path.join(output_dir, 'RECORD.txt')
    PCCS_header = ('Epoch\tTime(sec)\tLoss_val\tpearson\tmae\tmse\trmse\tr2')
    print(PCCS_header)

    with open(file_PCCS, 'w') as f:
        f.write(PCCS_header + '\n')

    start = timeit.default_timer()

    # 简化：使用固定的数据划分而不是随机划分
    n_samples = min(len(antibodies), len(antigens), len(interactions))
    print(f"Using {n_samples} samples for prediction")
    
    # 使用后20%的数据作为测试集
    test_start = int(0.8 * n_samples)
    test_indices = list(range(test_start, n_samples))
    
    print(f"Test set: {len(test_indices)} samples (indices {test_start}-{n_samples-1})")

    for epoch in range(1, iteration + 1):
        print(f"\nEpoch {epoch}/{iteration}")
        
        # 准备测试数据
        antigens_test = np.array(antigens)[test_indices]
        antibodies_test = np.array(antibodies)[test_indices]
        antigens_mut_test = np.array(antigens_mut)[test_indices]
        antibodies_mut_test = np.array(antibodies_mut)[test_indices]
        interactions_test = np.array(interactions)[test_indices]
        
        dataset_test = list(zip(antigens_test, antibodies_test, antigens_mut_test, antibodies_mut_test, interactions_test))

        # 进行预测测试
        pccs_val, mae_val, mse_val, rmse_val, r2_val, loss_val_fold, y_val_true, y_val_predict = tester.test(dataset_test, epoch)

        end = timeit.default_timer()
        elapsed_time = end - start

        # 记录结果
        PCCS = [epoch, elapsed_time, loss_val_fold.tolist(), pccs_val.tolist(), mae_val, mse_val, rmse_val, r2_val]
        tester.save_pccs(PCCS, file_PCCS)

        print(f"Results: Loss={loss_val_fold:.4f}, Pearson={pccs_val:.4f}, MAE={mae_val:.4f}, R2={r2_val:.4f}")
        print('\t'.join(map(str, PCCS)))

    print(f"\nPrediction completed! Results saved to: {file_PCCS}")