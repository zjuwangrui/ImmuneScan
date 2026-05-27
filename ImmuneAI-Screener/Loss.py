import numpy as np
import os
from arg_parse import get_args
from addition_func import normalize

import torch
import torch.nn as nn
import torch.nn.functional as F
import collections

args = get_args()

# 氨基酸频率字典（损失函数依赖）
AA_freq = {
    "A": 0.07421620506799341,
    "R": 0.05161448614128464,
    "N": 0.044645808512757915,
    "D": 0.05362600083855441,
    "C": 0.02468745716794485,
    "Q": 0.03425965059141602,
    "E": 0.0543119256845875,
    "G": 0.074146941452645,
    "H": 0.026212984805266227,
    "I": 0.06791736761895376,
    "L": 0.09890786849715096,
    "K": 0.05815568230307968,
    "M": 0.02499019757964311,
    "F": 0.04741845974228475,
    "P": 0.038538003320306206,
    "S": 0.05722902947649442,
    "T": 0.05089136455028703,
    "W": 0.013029956129972148,
    "Y": 0.03228151231375858,
    "V": 0.07291909820561925,
}

# ========== 核心工具函数 ==========
def try_gpu(i=0):
    if torch.cuda.device_count() >= i + 1:
        return torch.device(f'cuda:{i}')
    return torch.device('cpu')

# 词汇表类（模型预测依赖，需和训练时一致）
class Vocab:
    def __init__(self, tokens=None, min_freq=0, reserved_tokens=None):
        if tokens is None:
            tokens = []
        if reserved_tokens is None:
            reserved_tokens = []
        
        counter = counter_corpus(tokens)
        self._token_freqs = sorted(counter.items(), key=lambda x: x[1], reverse=True)
        self.idx_to_token = ['<unk>'] + reserved_tokens
        self.token_to_idx = {token: idx for idx, token in enumerate(self.idx_to_token)}
        
        for token, freq in self._token_freqs:
            if freq < min_freq:
                break
            if token not in self.token_to_idx:
                self.idx_to_token.append(token)
                self.token_to_idx[token] = len(self.idx_to_token) - 1
    
    def __len__(self):
        return len(self.idx_to_token)
    
    def __getitem__(self, tokens):
        if not isinstance(tokens, (list, tuple)):
            return self.token_to_idx.get(tokens, self.unk)
        return [self.__getitem__(token) for token in tokens]
    
    @property
    def unk(self):
        return 0

def counter_corpus(tokens):
    if len(tokens) == 0 or isinstance(tokens[0], list):
        tokens = [token for line in tokens for token in line]
    return collections.Counter(tokens)

def read_sequence(directory, file):
    with open(os.path.join(directory, file), 'r') as f:
        return f.readlines()
    
def tokenize(lines):
    alltoken = []
    for line in lines:
        if list(line)[0] == '#':
            continue
        else:
            alltoken.append(line.strip().split())
    return alltoken

# ========== 模型结构 ==========
class PositionWiseFFN(nn.Module):
    def __init__(self, ffn_num_input, ffn_num_hiddens, ffn_num_outputs):
        super(PositionWiseFFN, self).__init__()
        self.dense1 = nn.Linear(ffn_num_input, ffn_num_hiddens)
        self.relu = nn.ReLU()
        self.dense2 = nn.Linear(ffn_num_hiddens, ffn_num_outputs)
        
    def forward(self, X):
        return self.dense2(self.relu(self.dense1(X)))

class RNNModel(nn.Module):
    def __init__(self, rnn_layer, vocab_size, ffn_num_hiddens, 
                 linear1_num_hiddens, linear2_num_hiddens, linear3_num_hiddens,
                 dropout, **kwargs):
        super(RNNModel, self).__init__()
        self.vocab_size = vocab_size
        self.rnn = rnn_layer
        self.num_hiddens = self.rnn.hidden_size
        self.relu = nn.ReLU()
        self.ffn = PositionWiseFFN(self.num_hiddens, ffn_num_hiddens, self.num_hiddens)
        self.dropout = nn.Dropout(dropout)
        self.linear1 = nn.Linear(self.num_hiddens, linear1_num_hiddens)
        self.bn = nn.BatchNorm2d(linear1_num_hiddens)
        self.linear2 = nn.Linear(linear1_num_hiddens,linear2_num_hiddens)
        self.linear3 = nn.Linear(linear2_num_hiddens,linear3_num_hiddens)
        self.output = nn.Linear(linear3_num_hiddens,1)
    
    def forward(self, inputs, state):
        X = F.one_hot(inputs.T.long(), self.vocab_size)
        X = X.to(torch.float32)
        Y, state = self.rnn(X, state)
        Y = Y.permute(1, 0, 2)
        Y = Y.sum(dim = 1)
        output = self.linear1(self.dropout(self.ffn(Y))+Y).unsqueeze(2).unsqueeze(3)
        output = self.linear2(self.relu(self.bn(output).squeeze(3).squeeze(2)))
        output = self.output(self.relu(self.linear3(output)))
        return output, state
    
    def begin_state(self, device, batch_size=1):
        if not isinstance(self.rnn, nn.LSTM):
            return torch.zeros((self.rnn.num_layers, batch_size, self.num_hiddens), device = device)
        else:
            return (torch.zeros((self.rnn.num_layers, batch_size, self.num_hiddens), device=device),
                    torch.zeros((self.rnn.num_layers, batch_size, self.num_hiddens), device=device))

# ========== 预测函数 ==========
def predict_single(seq, net, vocab, device):
    net.eval()
    state = net.begin_state(batch_size=1, device = device)
    seq = torch.tensor(vocab[[i for i in seq]], device = device).unsqueeze(0)
    with torch.no_grad():
        y, _ = net(seq,state)
    return y.squeeze(0).numpy()

# ========== 全局模型加载（关键） ==========
# 1. 定义设备
device = try_gpu()

# 2. 构建Vocab（和训练时一致）
num_hiddens, num_layers = 64, 1
directory = 'D:/HuaweiMoveData/Users/29320/Desktop/Class-p2-week2/data'
file = 'student_train.log' 
lines = read_sequence(directory, file)
tokens = tokenize(lines)
tokens = [list(_) for _ in np.array(tokens)[:, 1]]
vocab = Vocab(tokens)

# 3. 初始化并加载模型
ffn_num_hiddens, linear1_num_hiddens, linear2_num_hiddens, linear3_num_hiddens = 32, 32, 32, 8
rnn_layer = nn.LSTM(len(vocab), num_hiddens, num_layers)
clone = RNNModel(rnn_layer, len(vocab), ffn_num_hiddens, 
               linear1_num_hiddens, linear2_num_hiddens, linear3_num_hiddens, dropout=0.5)
clone.load_state_dict(torch.load('D:/HuaweiMoveData/Users/29320/Desktop/Class-p2-week2/scripts/RNN_model.params', map_location=device))
clone.to(device)
clone.eval()

# ========== 损失函数 ==========
def explicit_pep_TCR_loss(pep_seq, cdr_seq):
    pass

def IEDB_loss(iedb_freqmat, pep_seq):
    dictionary = dict(zip(AA_freq.keys(), np.linspace(0, 19, 20, dtype=int)))
    pep_seq_num = [dictionary[i] for i in pep_seq]
    iedb_prob = [iedb_freqmat[pep_seq_num[i], i] for i in range(len(pep_seq_num))]
    loss = sum(-np.log(i) for i in iedb_prob)
    return loss

def pep_TCR_loss(prob_ref_freqmat, pep_seq, cdr_seq, TCRpos):
    if cdr_seq == None:
        pep_cdr_discrete = [
            0.4000000000000001,3.3333333333333335,1.6333333333333335,2.0,0.14285714285714285,
            1.2666666666666664,0.8437500000000001,0.4129032258064516,1.4,1.5318181818181817,
            0.4273584905660377,3.36,1.5727272727272728,1.3707317073170735,1.4407407407407407,
            0.15384615384615385,1.3511627906976744,2.5333333333333337,2.032258064516129,0.5537313432835821,
        ]
        tcr_freqmat = np.zeros((args.l, 20))
        for i in range(args.l):
            tcr_freqmat[i] = prob_ref_freqmat.T[i] * pep_cdr_discrete
        tcr_freqmat = normalize(tcr_freqmat.T, args.l)
        dictionary = dict(zip(AA_freq.keys(), np.linspace(0, 19, 20, dtype=int)))
        TCRpos = list(map(int, TCRpos.split("_")))
        pep_seq_num = [dictionary[i] for i in pep_seq]
        tcr_prob = [tcr_freqmat[pep_seq_num[i], i] for i in range(len(pep_seq_num))]
        loss = 0
        n = 0
        for i in tcr_prob:
            n += 1
            if n not in TCRpos:
                loss += 0
            else:
                loss += -np.log(i) if i != 0 else -np.log(1e-20)
        return loss
    else:
        return explicit_pep_TCR_loss(pep_seq, cdr_seq)

def compute_loss(
    iedb_freqmat,
    prob_ref_freqmat,
    pep_seq,
    logfile,
    w1=10,
    w2=-0.1,
    w3=None,
    w4=args.weight_iedb,
):
    if args.cdr_sequence == None:
        w3 = args.weight_cdr_dis
    else:
        w3 = args.weight_cdr

    cdr_loss = pep_TCR_loss(prob_ref_freqmat, pep_seq=pep_seq, cdr_seq=args.cdr_sequence, TCRpos=args.TCR_loss_pos)
    iedb_loss = IEDB_loss(iedb_freqmat, pep_seq)
    predict_single_results = predict_single(pep_seq, clone, vocab, device).item()

    print("", file=logfile)
    print("LOSS RESULTS of the {}:".format(pep_seq), file=logfile)
    if args.cdr_sequence == None:
        print("****cdr loss --> {} given no cdr".format(w3 * cdr_loss), file=logfile)
    else:
        print("****cdr loss --> {} with cdr sequence as {}".format(w3 * cdr_loss, args.cdr_sequence), file=logfile)
    print("****iedb loss --> {}".format(w4 * iedb_loss), file=logfile)
    print("****structure loss --> {}".format(predict_single_results), file=logfile)

    return w3 * cdr_loss + w4 * iedb_loss + predict_single_results