#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
顶会/SCI 风格的全局样式设置
在所有画图脚本中复用
"""

import matplotlib as mpl
import matplotlib.pyplot as plt


def set_paper_style():
    """
    顶会/SCI 风格的全局样式设置。
    在脚本最开始调用一次即可。
    """
    mpl.rcParams.update({
        # 图尺寸和分辨率
        "figure.figsize": (3.0, 3.0),      # 每个单图默认大小（inch）
        "figure.dpi": 300,
        "savefig.dpi": 300,
        "figure.autolayout": False,

        # 字体相关
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "mathtext.fontset": "stix",        # 数学字体更接近 Times
        "axes.unicode_minus": False,       # 允许负号

        # 线宽、坐标轴
        "axes.linewidth": 0.8,
        "axes.labelsize": 9,
        "axes.titlesize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "xtick.major.size": 3,
        "ytick.major.size": 3,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,

        # 图例
        "legend.fontsize": 8,
        "legend.frameon": False,

        # 网格（我们这里大多不用）
        "axes.grid": False,

        # 线条默认
        "lines.linewidth": 1.4,
        "lines.markersize": 4,
    })


# 定义一个统一的颜色方案（方便所有图共用）
COLORS = {
    "traj":    "#222222",   # 轨迹主线 深灰接近黑
    "start":   "#1f77b4",   # 起点 蓝
    "end":     "#ff7f0e",   # 终点 橙
    "goal":    "#2ca02c",   # 目标 绿
    "radius":  "#7f7f7f",   # 成功半径 虚线灰
}

