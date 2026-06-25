#!/usr/bin/env python3
"""
A股智能选股器 - 每日自动筛选
支持多策略选股，输出格式兼容 daily_stock_analysis
"""

import akshare as ak
import pandas as pd
from datetime import datetime
import os
import json

# ============ 选股条件配置（可按需修改） ============
SCREENING_CRITERIA = {
    # 基础过滤条件
    "filter_enabled": True,
    "min_pe": 5,
    "max_pe": 50,
    "min_pb": 0.5,
    "max_pb": 5,
    "min_roe": 5,           # 净资产收益率 >= 5%
    "min_dividend": 1,       # 股息率 >= 1%
    
    # 技术面条件
    "min_price_change": -5,  # 涨幅下限
    "max_price_change": 9.9, # 涨幅上限
    "min_volume_ratio": 1.5, # 量比 >= 1.5
    "min_turnover": 3,       # 换手率 >= 3%
    
    # 排序规则
    "sort_by": "涨跌幅",      # 按涨幅排序
    "sort_ascending": False,
    "max_stocks": 20,        # 最多筛选出多少只
}


def get_stock_data():
    """获取东方财富A股实时行情"""
    print("📡 正在获取东方财富A股实时行情...")
    try:
        df = ak.stock_zh_a_spot_em()
        print(f"   ✅ 成功获取 {len(df)} 只股票数据")
        return df
    except Exception as e:
        print(f"   ❌ 获取数据失败: {e}")
        return None


def filter_stocks(df, criteria):
    """根据条件筛选股票"""
    if not criteria["filter_enabled"]:
        return df
    
    original_count = len(df)
    
    # 市盈率筛选
    if criteria["min_pe"] or criteria["max_pe"]:
        pe_col = "市盈率"
        if pe_col in df.columns:
            df = df.copy()
            df[pe_col] = pd.to_numeric(df[pe_col], errors='coerce')
            if criteria["min_pe"]:
                df = df[df[pe_col] >= criteria["min_pe"]]
            if criteria["max_pe"]:
                df = df[df[pe_col] <= criteria["max_pe"]]
    
    # 市净率筛选
    if criteria["min_pb"] or criteria["max_pb"]:
        pb_col = "市净率"
        if pb_col in df.columns:
            df = df.copy()
            df[pb_col] = pd.to_numeric(df[pb_col], errors='coerce')
            if criteria["min_pb"]:
                df = df[df[pb_col] >= criteria["min_pb"]]
            if criteria["max_pb"]:
                df = df[df[pb_col] <= criteria["max_pb"]]
    
    # 涨跌幅筛选
    if criteria["min_price_change"] or criteria["max_price_change"]:
        change_col = "涨跌幅"
        if change_col in df.columns:
            df = df.copy()
            df[change_col] = pd.to_numeric(df[change_col], errors='coerce')
            if criteria["min_price_change"]:
                df = df[df[change_col] >= criteria["min_price_change"]]
            if criteria["max_price_change"]:
                df = df[df[change_col] <= criteria["max_price_change"]]
    
    # 量比筛选
    if criteria["min_volume_ratio"]:
        vr_col = "量比"
        if vr_col in df.columns:
            df = df.copy()
            df[vr_col] = pd.to_numeric(df[vr_col], errors='coerce')
            df = df[df[vr_col] >= criteria["min_volume_ratio"]]
    
    # 换手率筛选
    if criteria["min_turnover"]:
        turnover_col = "换手率"
        if turnover_col in df.columns:
            df = df.copy()
            df[turnover_col] = pd.to_numeric(df[turnover_col], errors='coerce')
            df = df[df[turnover_col] >= criteria["min_turnover"]]
    
    print(f"   📊 筛选后: {len(df)} / {original_count} 只股票")
    return df


def format_stock_list(df):
    """格式化股票代码为 daily_stock_analysis 格式"""
    codes = []
    for _, row in df.iterrows():
        code = str(row.get("代码", ""))
        if not code:
            continue
        # 沪市以6开头，深市以0、3开头
        if code.startswith("6"):
            codes.append(f"sh{code}")
        elif code.startswith(("0", "3")):
            codes.append(f"sz{code}")
    return ",".join(codes)


def save_results(stock_list, df, output_file="selected_stocks.txt"):
    """保存选股结果"""
    # 保存纯股票列表
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# 选股时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# 筛选条件: {json.dumps(SCREENING_CRITERIA, ensure_ascii=False, indent=2)}\n")
        f.write(f"# 股票数量: {len(stock_list.split(','))}\n")
        f.write(f"\nSTOCK_LIST={stock_list}\n")
    
    # 保存带详细信息的CSV
    csv_file = output_file.replace(".txt", "_detail.csv")
    if len(df) > 0:
        # 选择关键列
        key_cols = ["代码", "名称", "最新价", "涨跌幅", "成交量", "成交额", "市盈率", "市净率", "换手率"]
        available_cols = [c for c in key_cols if c in df.columns]
        df[available_cols].head(SCREENING_CRITERIA["max_stocks"]).to_csv(csv_file, index=False, encoding="utf-8-sig")
        print(f"   ✅ 详细结果已保存到 {csv_file}")
    
    return stock_list


def main():
    print("=" * 60)
    print("🔍 A股智能选股器")
    print(f"⏰ 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 1. 获取数据
    df = get_stock_data()
    if df is None or len(df) == 0:
        print("❌ 获取数据失败，退出")
        return
    
    # 2. 筛选
    print("\n⚙️ 开始筛选股票...")
    filtered_df = filter_stocks(df, SCREENING_CRITERIA)
    
    if len(filtered_df) == 0:
        print("⚠️ 没有符合条件的股票")
        # 输出一个默认股票列表，避免空运行
        default_stocks = "sh600519,sh600036,sz000858"
        save_results(default_stocks, pd.DataFrame())
        return
    
    # 3. 排序并限制数量
    if SCREENING_CRITERIA["sort_by"] in filtered_df.columns:
        filtered_df = filtered_df.sort_values(
            SCREENING_CRITERIA["sort_by"], 
            ascending=SCREENING_CRITERIA["sort_ascending"]
        )
    
    filtered_df = filtered_df.head(SCREENING_CRITERIA["max_stocks"])
    
    # 4. 格式化
    stock_list = format_stock_list(filtered_df)
    
    # 5. 保存
    print("\n💾 保存结果...")
    save_results(stock_list, filtered_df)
    
    # 6. 输出预览
    print("\n📊 筛选结果预览:")
    print("-" * 60)
    preview_cols = ["代码", "名称", "最新价", "涨跌幅", "市盈率"]
    available_preview = [c for c in preview_cols if c in filtered_df.columns]
    print(filtered_df[available_preview].to_string(index=False))
    
    print("\n✅ 选股完成!")
    print(f"📝 股票列表: {stock_list}")


if __name__ == "__main__":
    main()
