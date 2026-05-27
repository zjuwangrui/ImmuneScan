import numpy as np
import pandas as pd


def data(f):
    csv = pd.read_csv(f, usecols=['PDB'])
    names = csv['PDB'].tolist()
    a = names[0]
    name_class = {}
    count = 0
    for idx in range(len(names)):
        b = names[idx]
        if a == b:
            count += 1
        else:
            name_class[a] = count
            count = 1
            a = names[idx]  # 和b交换
    return name_class

# 每个order型文件的结尾都是END（列PDB）
#path = '/home/ruofan/ab645-oh-trans-1/data/'
#print(data('AB645order.csv'))


def name_index(data_index):
    index_class = {}
    number = 0
    for name in data_index:
        count = data_index[name]  # 数量
        start = number
        end = start + count - 1
        index_class[name] = (start, end)
        number += count
    return index_class


def interlist(a,b):
    ls = []
    for i in range(a,b+1):
        ls.append(i)
    return ls

def split(f, scale):  # index's list (train & test)
    data_class = data(f)
    index_class = name_index(data_class)
    
    trainidx = []
    testidx = []
    for name in index_class:
        # all interval
        start = index_class[name][0]
        end = index_class[name][1]
        # train & test split (count)
        count = data_class[name]
        test_count = int(round(count*scale,0))
        train_count = count - test_count
        # every class's inerval indexes
        trainidx_class = interlist(start, start+train_count-1)
        testidx_class = interlist(end-test_count+1, end)
        for i in trainidx_class:
            trainidx.append(i)
        for j in testidx_class:
            testidx.append(j)
    return trainidx, testidx

