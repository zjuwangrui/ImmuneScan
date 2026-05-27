# -*- coding: utf-8 -*-
"""
@Time:Created on 2021/9/17
@author: Ruofan Jin
@Filename: model_test.py (测试版模型 - 支持动态网络维度)
@Software: PyCharm
"""
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import math
from math import sqrt
import numpy as np
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from Radam import *
from lookahead import Lookahead
from scipy.stats import pearsonr
import os


class SelfAttention(nn.Module):
    def __init__(self, hid_dim, n_heads, dropout, device):
        super().__init__()

        self.hid_dim = hid_dim
        self.n_heads = n_heads

        assert hid_dim % n_heads == 0

        self.w_q = nn.Linear(hid_dim, hid_dim)
        self.w_k = nn.Linear(hid_dim, hid_dim)
        self.w_v = nn.Linear(hid_dim, hid_dim)
        self.fc = nn.Linear(hid_dim, hid_dim)
        self.do = nn.Dropout(dropout)
        self.scale = torch.sqrt(torch.FloatTensor([hid_dim // n_heads])).to(device)

    def forward(self, query, key, value, mask=None, return_attention=False):
        bsz = query.shape[0]

        Q = self.w_q(query)
        K = self.w_k(key)
        V = self.w_v(value)

        Q = Q.view(bsz, -1, self.n_heads, self.hid_dim // self.n_heads).permute(0, 2, 1, 3)
        K = K.view(bsz, -1, self.n_heads, self.hid_dim // self.n_heads).permute(0, 2, 1, 3)
        V = V.view(bsz, -1, self.n_heads, self.hid_dim // self.n_heads).permute(0, 2, 1, 3)

        energy = torch.matmul(Q, K.permute(0, 1, 3, 2)) / self.scale

        if mask is not None:
            energy = energy.masked_fill(mask == 0, -1e10)

        attention = self.do(F.softmax(energy, dim=-1))

        x = torch.matmul(attention, V)
        x = x.permute(0, 2, 1, 3).contiguous()
        x = x.view(bsz, -1, self.n_heads * (self.hid_dim // self.n_heads))
        x = self.fc(x)

        if return_attention:
            return x, attention
        return x


class Encoder(nn.Module):
    """protein feature extraction."""
    def __init__(self, protein_dim, hid_dim, n_layers, kernel_size, dropout, device):
        super().__init__()

        assert kernel_size % 2 == 1, "Kernel size must be odd (for now)"

        self.input_dim = protein_dim
        self.hid_dim = hid_dim
        self.kernel_size = kernel_size
        self.dropout = dropout
        self.n_layers = n_layers
        self.device = device
        self.scale = torch.sqrt(torch.FloatTensor([0.5])).to(device)
        self.convs = nn.ModuleList([nn.Conv1d(hid_dim, 2*hid_dim, kernel_size, padding=(kernel_size-1)//2) for _ in range(self.n_layers)])
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(self.input_dim, self.hid_dim)
        self.gn = nn.GroupNorm(8, hid_dim * 2)
        self.ln = nn.LayerNorm(hid_dim)

    def forward(self, protein):
        conv_input = self.fc(protein)
        conv_input = conv_input.permute(0, 2, 1)
        
        for i, conv in enumerate(self.convs):
            conved = (F.glu(conv(self.dropout(conv_input)), dim=1) + conv_input) * self.scale
            conv_input = conved

        conved = conved.permute(0, 2, 1)
        conved = self.ln(conved)
        return conved


class PositionwiseFeedforward(nn.Module):
    def __init__(self, hid_dim, pf_dim, dropout):
        super().__init__()
        self.hid_dim = hid_dim
        self.pf_dim = pf_dim
        self.fc_1 = nn.Conv1d(hid_dim, pf_dim, 1)
        self.fc_2 = nn.Conv1d(pf_dim, hid_dim, 1)
        self.do = nn.Dropout(dropout)

    def forward(self, x):
        x = x.permute(0, 2, 1)
        x = self.fc_2(self.do(F.relu(self.fc_1(x))))
        x = x.permute(0, 2, 1)
        return x


class DecoderLayer(nn.Module):
    def __init__(self, hid_dim, n_heads, pf_dim, self_attention, positionwise_feedforward, dropout, device):
        super().__init__()
        self.ln = nn.LayerNorm(hid_dim)
        self.sa = self_attention(hid_dim, n_heads, dropout, device)
        self.ea = self_attention(hid_dim, n_heads, dropout, device)
        self.pf = positionwise_feedforward(hid_dim, pf_dim, dropout)
        self.do = nn.Dropout(dropout)
        
    def forward(self, trg, src, trg_mask=None, src_mask=None, return_attention=False):
        trg = self.ln(trg + self.do(self.sa(trg, trg, trg, trg_mask)))
        if return_attention:
            ea_out, cross_attn = self.ea(trg, src, src, src_mask, return_attention=True)
            trg = self.ln(trg + self.do(ea_out))
            trg = self.ln(trg + self.do(self.pf(trg)))
            return trg, cross_attn
        else:
            trg = self.ln(trg + self.do(self.ea(trg, src, src, src_mask)))
            trg = self.ln(trg + self.do(self.pf(trg)))
            return trg


class Decoder(nn.Module):
    """compound feature extraction."""
    def __init__(self, atom_dim, hid_dim, n_layers, n_heads, pf_dim, decoder_layer, self_attention,
                 positionwise_feedforward, dropout, device):
        super().__init__()
        self.ln = nn.LayerNorm(hid_dim)
        self.output_dim = atom_dim
        self.hid_dim = hid_dim
        self.n_layers = n_layers
        self.n_heads = n_heads
        self.pf_dim = pf_dim
        self.decoder_layer = decoder_layer
        self.self_attention = self_attention
        self.positionwise_feedforward = positionwise_feedforward
        self.dropout = dropout
        self.device = device
        self.sa = self_attention(hid_dim, n_heads, dropout, device)
        self.layers = nn.ModuleList([decoder_layer(hid_dim, n_heads, pf_dim, self_attention, positionwise_feedforward, dropout, device) for _ in range(n_layers)])
        self.ft = nn.Linear(atom_dim, hid_dim)
        self.do = nn.Dropout(dropout)
        # 这些fc层在Decoder中不使用，为了兼容保留
        self.fc_1 = nn.Linear(hid_dim, 64)
        self.fc_2 = nn.Linear(64, 16)
        self.fc_3 = nn.Linear(16, 1)
        self.gn = nn.GroupNorm(8, 64)

    def forward(self, trg, src, trg_mask=None, src_mask=None, return_attention=False):
        cross_attentions = []

        for layer in self.layers:
            if return_attention:
                trg, cross_attn = layer(trg, src, trg_mask, src_mask, return_attention=True)
                cross_attentions.append(cross_attn)
            else:
                trg = layer(trg, src, trg_mask, src_mask)

        norm = F.softmax(torch.norm(trg, dim=2), dim=1)
        norm1 = torch.norm(trg, dim=2)
        summ = torch.zeros((trg.shape[0], self.hid_dim)).to(self.device)
        for i in range(norm.shape[0]):
            for j in range(norm.shape[1]):
                v = trg[i, j, ]
                v = v * norm[i, j]
                summ[i, ] += v

        if return_attention:
            # 对多头注意力进行平均，得到 [batch, n_layers, trg_len, src_len]
            return summ, norm1, cross_attentions
        return summ, norm1


class TestPredictor(nn.Module):
    """测试版Predictor - 支持动态网络维度"""
    def __init__(self, encoder, decoder, device, hid_dim, ags_dim=20):
        super().__init__()

        self.encoder = encoder
        self.decoder = decoder
        self.device = device
        self.hid_dim = hid_dim  # 保存hid_dim用于动态计算
        self.weight = nn.Parameter(torch.FloatTensor(ags_dim, ags_dim))
        self.init_weight()
        self.do = nn.Dropout(0.1)
        
        # 动态调整全连接层维度 - 基于hid_dim参数
        self.fc_1 = nn.Linear(hid_dim*2, hid_dim)      # 输入: hid_dim*2, 输出: hid_dim
        self.fc_2 = nn.Linear(hid_dim*2, hid_dim//2)   # 输入: hid_dim*2, 输出: hid_dim//2
        self.fc_3 = nn.Linear(hid_dim//2, 16)          # 输入: hid_dim//2, 输出: 16
        self.fc_4 = nn.Linear(16, 1)                   # 输入: 16, 输出: 1
        
        print(f"TestPredictor initialized with hid_dim={hid_dim}")
        print(f"  fc_1: {hid_dim*2} -> {hid_dim}")
        print(f"  fc_2: {hid_dim*2} -> {hid_dim//2}")
        print(f"  fc_3: {hid_dim//2} -> 16")
        print(f"  fc_4: 16 -> 1")

    def init_weight(self):
        stdv = 1. / math.sqrt(self.weight.size(1))
        self.weight.data.uniform_(-stdv, stdv)

    def make_masks(self, p11n, p21n, p11_max_len, p21_max_len):
        N = len(p11n)
        p11_mask = torch.zeros((N, p11_max_len))
        p21_mask = torch.zeros((N, p21_max_len))
        for i in range(N):
            p11_mask[i, :p11n[i]] = 1
            p21_mask[i, :p21n[i]] = 1
        p11_mask = p11_mask.unsqueeze(1).unsqueeze(3).to(self.device)
        p21_mask = p21_mask.unsqueeze(1).unsqueeze(2).to(self.device)
        return p11_mask, p21_mask

    def forward(self, ag_s, ab_s, ag_m_s, ab_m_s, ag_s_num, ab_s_num, ag_m_s_num, ab_m_s_num, itera, correct_interaction, return_attention=False):
        ag_s_max_len = ag_s.shape[1]
        ab_s_max_len = ab_s.shape[1]
        ag_m_s_max_len = ag_m_s.shape[1]
        ab_m_s_max_len = ab_m_s.shape[1]

        ag_s_mask, ab_s_mask = self.make_masks(ag_s_num, ab_s_num, ag_s_max_len, ab_s_max_len)
        ag_m_s_mask, ab_m_s_mask = self.make_masks(ag_m_s_num, ab_m_s_num, ag_m_s_max_len, ab_m_s_max_len)

        enc_ag_s = self.encoder(ag_s)
        enc_ab_s = self.encoder(ab_s)
        enc_ag_m_s = self.encoder(ag_m_s)
        enc_ab_m_s = self.encoder(ab_m_s)

        if return_attention:
            ag_ab, ag_ab_norm, ag_ab_attns = self.decoder(enc_ag_s, enc_ab_s, ag_s_mask, ab_s_mask, return_attention=True)
            ab_s_mask_change = ab_s_mask.permute(0, 1, 3, 2)
            ag_s_mask_change = ag_s_mask.permute(0, 1, 3, 2)
            ab_ag, ab_ag_norm, ab_ag_attns = self.decoder(enc_ab_s, enc_ag_s, ab_s_mask_change, ag_s_mask_change, return_attention=True)

            ag_ab_m, ag_ab_m_norm, ag_ab_m_attns = self.decoder(enc_ag_m_s, enc_ab_m_s, ag_m_s_mask, ab_m_s_mask, return_attention=True)
            ab_m_s_mask_change = ab_m_s_mask.permute(0, 1, 3, 2)
            ag_m_s_mask_change = ag_m_s_mask.permute(0, 1, 3, 2)
            ab_ag_m, ab_ag_m_norm, ab_ag_m_attns = self.decoder(enc_ab_m_s, enc_ag_m_s, ab_m_s_mask_change, ag_m_s_mask_change, return_attention=True)
        else:
            ag_ab, ag_ab_norm = self.decoder(enc_ag_s, enc_ab_s, ag_s_mask, ab_s_mask)
            ab_s_mask_change = ab_s_mask.permute(0, 1, 3, 2)
            ag_s_mask_change = ag_s_mask.permute(0, 1, 3, 2)
            ab_ag, ab_ag_norm = self.decoder(enc_ab_s, enc_ag_s, ab_s_mask_change, ag_s_mask_change)

            ag_ab_m, ag_ab_m_norm = self.decoder(enc_ag_m_s, enc_ab_m_s, ag_m_s_mask, ab_m_s_mask)
            ab_m_s_mask_change = ab_m_s_mask.permute(0, 1, 3, 2)
            ag_m_s_mask_change = ag_m_s_mask.permute(0, 1, 3, 2)
            ab_ag_m, ab_ag_m_norm = self.decoder(enc_ab_m_s, enc_ag_m_s, ab_m_s_mask_change, ag_m_s_mask_change)

        # 使用动态维度的全连接层
        complex_wt = self.do(F.relu(self.fc_1(torch.cat([ag_ab, ab_ag], -1))))
        complex_mut = self.do(F.relu(self.fc_1(torch.cat([ag_ab_m, ab_ag_m], -1))))
        final2 = self.do(F.relu(self.fc_2(torch.cat([complex_wt, complex_mut], -1))))
        final2 = self.do(F.relu(self.fc_3(final2)))
        final2 = self.do(F.relu(self.fc_4(final2)))
        final2 = final2.view(-1)

        if return_attention:
            return final2, {
                'ag_ab_attns': ag_ab_attns,
                'ab_ag_attns': ab_ag_attns,
                'ag_ab_m_attns': ag_ab_m_attns,
                'ab_ag_m_attns': ab_ag_m_attns,
                'ag_s_num': ag_s_num,
                'ab_s_num': ab_s_num,
                'ag_m_s_num': ag_m_s_num,
                'ab_m_s_num': ab_m_s_num
            }
        return final2

    def __call__(self, data, itera, train=True, return_attention=False):
        ag_s, ab_s, ag_m_s, ab_m_s, correct_interaction, ag_s_num, ab_s_num, ag_m_s_num, ab_m_s_num = data

        Loss = nn.MSELoss()
        correct_interaction = correct_interaction.to(torch.float32)

        if return_attention:
            result = self.forward(ag_s, ab_s, ag_m_s, ab_m_s, ag_s_num, ab_s_num, ag_m_s_num, ab_m_s_num, itera, correct_interaction, return_attention=True)
            predicted_interaction = result[0]
            attention_dict = result[1]
            if train:
                loss = Loss(predicted_interaction, correct_interaction)
                loss = loss.float()
                return loss, correct_interaction, predicted_interaction, attention_dict
            else:
                return correct_interaction, predicted_interaction, attention_dict
        else:
            predicted_interaction = self.forward(ag_s, ab_s, ag_m_s, ab_m_s, ag_s_num, ab_s_num, ag_m_s_num, ab_m_s_num, itera, correct_interaction)
            if train:
                loss = Loss(predicted_interaction, correct_interaction)
                loss = loss.float()
                return loss, correct_interaction, predicted_interaction
            else:
                return correct_interaction, predicted_interaction


# 从原model.py复制的pack函数
def pack(ag_s, ab_s, ag_m_s, ab_m_s, labels, device):
    ag_s_len = 0
    ab_s_len = 0
    ag_m_s_len = 0
    ab_m_s_len = 0
    N = len(labels)

    ag_s_num = []
    for ag in ag_s:
        ag_s_num.append(ag.shape[0])
        if ag.shape[0] >= ag_s_len:
            ag_s_len = ag.shape[0]
    ab_s_num = []
    for ab in ab_s:
        ab_s_num.append(ab.shape[0])
        if ab.shape[0] >= ab_s_len:
            ab_s_len = ab.shape[0]
    ag_m_s_num = []
    for agm in ag_m_s:
        ag_m_s_num.append(agm.shape[0])
        if agm.shape[0] >= ag_m_s_len:
            ag_m_s_len = agm.shape[0]
    ab_m_s_num = []
    for abm in ab_m_s:
        ab_m_s_num.append(abm.shape[0])
        if abm.shape[0] >= ab_m_s_len:
            ab_m_s_len = abm.shape[0]

    ag_s_new = torch.zeros((N, ag_s_len, 20), device=device)
    i = 0
    for ag in ag_s:
        ag = torch.tensor(ag)
        a_len = ag.shape[0]
        ag_s_new[i, :a_len, :] = ag
        i += 1
    ab_s_new = torch.zeros((N, ab_s_len, 20), device=device)
    i = 0
    for ab in ab_s:
        ab = torch.tensor(ab)
        a_len = ab.shape[0]
        ab_s_new[i, :a_len, :] = ab
        i += 1

    ag_m_s_new = torch.zeros((N, ag_m_s_len, 20), device=device)
    i = 0
    for agm in ag_m_s:
        agm = torch.tensor(agm)
        a_len = agm.shape[0]
        ag_m_s_new[i, :a_len, :] = agm
        i += 1
    ab_m_s_new = torch.zeros((N, ab_m_s_len, 20), device=device)
    i = 0
    for abm in ab_m_s:
        abm = torch.tensor(abm)
        a_len = abm.shape[0]
        ab_m_s_new[i, :a_len, :] = abm
        i += 1

    labels_new = torch.zeros(N, dtype=torch.float, device=device)
    i = 0
    for label in labels:
        labels_new[i] = label
        i += 1

    return (ag_s_new, ab_s_new, ag_m_s_new, ab_m_s_new, labels_new,
            ag_s_num, ab_s_num, ag_m_s_num, ab_m_s_num)


class Trainer(object):
    def __init__(self, model, lr, weight_decay, batch):
        self.model = model
        weight_p, bias_p = [], []
        for p in self.model.parameters():
            if p.dim() > 1:
                nn.init.kaiming_uniform_(p)
        for name, p in self.model.named_parameters():
            if 'bias' in name:
                bias_p += [p]
            else:
                weight_p += [p]
        self.optimizer_inner = RAdam([{'params': weight_p, 'weight_decay': weight_decay}, {'params': bias_p, 'weight_decay': 0}], lr=lr)
        self.optimizer = Lookahead(self.optimizer_inner, k=5, alpha=0.5)
        self.batch = batch

    def train(self, dataset, device, itera):
        self.model.train()
        N = len(dataset)
        i = 0
        iteration = 0
        self.optimizer.zero_grad()
        ag_s, ab_s, ag_m_s, ab_m_s, labels = [], [], [], [], []
        train_correct_fold = torch.zeros((1,0), device=device)
        train_predict_fold = torch.zeros((1,0), device=device)
        lo = []
        for data in dataset:
            i = i+1
            ag, ab, agm, abm, label = data
            ag_s.append(ag)
            ab_s.append(ab)
            ag_m_s.append(agm)
            ab_m_s.append(abm)
            labels.append(label)
            correct_labels = torch.zeros((1,0), device=device)
            predicted_labels = torch.zeros((1,0), device=device)
            if i % self.batch == 0 or i == N:
                iteration += 1
                data_pack = pack(ag_s, ab_s, ag_m_s, ab_m_s, labels, device)
                loss, correct, predicted = self.model(data_pack, itera)
                correct = correct.view(1,-1)
                predicted = predicted.view(1,-1)
                correct_labels = torch.cat([correct_labels,correct], dim=-1)
                predicted_labels = torch.cat([predicted_labels,predicted], dim=-1)
                train_correct_fold = torch.cat([train_correct_fold,correct], dim=-1)
                train_predict_fold = torch.cat([train_predict_fold,predicted], dim=-1)
                lo.append(loss)
                loss.backward()

                ag_s, ab_s, ag_m_s, ab_m_s, labels = [], [], [], [], []
                self.optimizer.step()
                self.optimizer.zero_grad()
            else:
                continue
            
        Loss = nn.MSELoss()
        loss_train_1 = Loss(train_correct_fold, train_predict_fold)
        loss_train = sum(lo)/iteration
        return loss_train, train_correct_fold, train_predict_fold


def get_corr(fake_Y, Y):
    fake_Y, Y = fake_Y.reshape(-1), Y.reshape(-1)
    fake_Y_mean, Y_mean = torch.mean(fake_Y.float()), torch.mean(Y.float())
    corr = (torch.sum((fake_Y - fake_Y_mean) * (Y - Y_mean))) / (
        torch.sqrt(torch.sum((fake_Y - fake_Y_mean) ** 2)) * torch.sqrt(torch.sum((Y - Y_mean) ** 2)))
    return corr


class Tester(object):
    def __init__(self, model):
        self.model = model

    def test(self, dataset, itera):
        self.model.eval()
        N = len(dataset)
        device = self.model.device
        T = torch.zeros((1,0), device=device)
        Y = torch.zeros((1,0), device=device)
        with torch.no_grad():
            for data in dataset:
                ag_s, ab_s, ag_m_s, ab_m_s, labels = [], [], [], [], []
                ag, ab, agm, abm, label = data
                ag_s.append(ag)
                ab_s.append(ab)
                ag_m_s.append(agm)
                ab_m_s.append(abm)
                labels.append(label)
                data = pack(ag_s, ab_s, ag_m_s, ab_m_s, labels, self.model.device)
                correct, predicted = self.model(data, itera, train=False)
                correct = correct.view(1,-1)
                predicted = predicted.view(1,-1)
                T = torch.cat([T,correct], dim=-1)
                Y = torch.cat([Y,predicted], dim=-1)
        T = T.squeeze()
        Y = Y.squeeze()
        print('true:', T)
        print('predict:', Y)
        
        # 将张量移到CPU上进行评估指标计算
        T_cpu = T.cpu()
        Y_cpu = Y.cpu()
        
        pccs = get_corr(T_cpu, Y_cpu)
        mae = mean_absolute_error(T_cpu.numpy(), Y_cpu.numpy())
        mse = mean_squared_error(T_cpu.numpy(), Y_cpu.numpy())
        rmse = sqrt(mean_squared_error(T_cpu.numpy(), Y_cpu.numpy()))
        r2 = r2_score(T_cpu.numpy(), Y_cpu.numpy())
        Loss = nn.MSELoss()
        loss = Loss(T, Y)
        return pccs, mae, mse, rmse, r2, loss, T_cpu.numpy(), Y_cpu.numpy()

    def save_pccs(self,pccs,filename):
        with open(filename, 'a') as f:
            f.write('\t'.join(map(str,pccs)) + '\n')

    def save_model(self, model, filename):
        torch.save(model.state_dict(), filename)