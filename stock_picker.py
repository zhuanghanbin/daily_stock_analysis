#!/usr/bin/env python3
"""
A股智能选股器 V2 - 增强版
- 多数据源支持（东方财富 + 腾讯财经 + 新浪财经）
- 自动重试机制
- 失败自动切换数据源
"""

import akshare as ak
import pandas as pd
import time
import random
import json
from datetime import datetime

# ============ 选股条件配置 ============
SCREENING_CRITERIA = {
    "filter_enabled": True,
    "min_pe": 5,
    "max_pe": 50,
    "min_pb": 0.5,
    "max_pb": 5,
    "min_roe": 5,
    "min_dividend": 1,
    "min_price_change": -3,      # 涨幅下限调宽
    "max_price_change": 9.9,
    "min_volume_ratio": 1.2,     # 量比稍微调低
    "min_turnover": 2,
    "sort_by": "涨跌幅",
    "sort_ascending": False,
    "max_stocks": 20,
}


def get_stock_data_with_retry(max_retries=3, retry_delay=5):
    """多数据源获取 + 自动重试"""
    
    data_sources = [
        ("东方财富", get_stock_data_eastmoney),
        ("腾讯财经", get_stock_data_tencent),
        ("新浪财经", get_stock_data_sina),
    ]
    
    for source_name, source_func in data_sources:
        for attempt in range(max_retries):
            try:
                print(f"\n📡 尝试从【{source_name}】获取数据... (第{attempt + 1}次)")
                df = source_func()
                if df is not None and len(df) > 1000:
                    print(f"   ✅ 成功从 {source_name} 获取 {len(df)} 只股票")
                    return df
            except Exception as e:
                print(f"   ❌ 获取失败: {e}")
            
            if attempt < max_retries - 1:
                wait_time = retry_delay + random.uniform(1, 3)
                print(f"   ⏳ 等待 {wait_time:.1f} 秒后重试...")
                time.sleep(wait_time)
        
        print(f"⚠️ {source_name} 数据源不可用，切换到下一个...")
    
    print("❌ 所有数据源都失败了")
    return None


def get_stock_data_eastmoney():
    """东方财富数据源"""
    df = ak.stock_zh_a_spot_em()
    return df


def get_stock_data_tencent():
    """腾讯财经数据源"""
    # 腾讯财经的实时行情
    df = ak.stock_zh_a_spot_cons_sina()
    return df


def get_stock_data_sina():
    """新浪财经数据源"""
    # 新浪财经实时行情
    df = ak.stock_zh_a_spot()
    return df


def filter_stocks(df, criteria):
    """根据条件筛选股票"""
    if not criteria["filter_enabled"]:
        return df
    
    original_count = len(df)
    
    # 遍历所有条件
    conditions = [
        ("市盈率", "min_pe", lambda x, m: x >= m),
        ("市盈率", "max_pe", lambda x, m: x <= m),
        ("市净率", "min_pb", lambda x, m: x >= m),
        ("市净率", "max_pb", lambda x, m: x <= m),
        ("涨跌幅", "min_price_change", lambda x, m: x >= m),
        ("涨跌幅", "max_price_change", lambda x, m: x <= m),
        ("量比", "min_volume_ratio", lambda x, m: x >= m),
        ("换手率", "min_turnover", lambda x, m: x >= m),
    ]
    
    for col, key, op in conditions:
        if criteria.get(key):
            if col in df.columns:
                df = df.copy()
                df[col] = pd.to_numeric(df[col], errors='coerce')
                df = df[df[col].apply(lambda x: op(x, criteria[key]) if pd.notna(x) else False)]
    
    print(f"   📊 筛选后: {len(df)} / {original_count} 只股票")
    return df


def format_stock_list(df):
    """格式化股票代码"""
    codes = []
    for _, row in df.iterrows():
        code = str(row.get("代码", "")) or str(row.get("symbol", ""))
        if not code:
            continue
        code = code.replace("sh", "").replace("sz", "").replace(".", "")
        if code.startswith("6"):
            codes.append(f"sh{code}")
        elif code.startswith(("0", "3")):
            codes.append(f"sz{code}")
    return ",".join(codes)


def save_results(stock_list, df):
    """保存结果"""
    with open("selected_stocks.txt", "w", encoding="utf-8") as f:
        f.write(f"# 选股时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# STOCK_LIST={stock_list}\n")
    
    if len(df) > 0:
        key_cols = ["代码", "名称", "最新价", "涨跌幅", "市盈率", "换手率"]
        available = [c for c in key_cols if c in df.columns]
        df[available].head(SCREENING_CRITERIA["max_stocks"]).to_csv(
            "selected_stocks_detail.csv", index=False, encoding="utf-8-sig"
        )
    
    return stock_list


def main():
    print("=" * 60)
    print("🔍 A股智能选股器 V2")
    print(f"⏰ 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 1. 获取数据（带重试）
    df = get_stock_data_with_retry(max_retries=3, retry_delay=3)
    
    if df is None:
        print("\n⚠️ 无法获取数据，使用默认股票列表演示")
        default_stocks = "sh600519,sh600036,sz000858,sh601318,sz002594"
        save_results(default_stocks, pd.DataFrame())
        print(f"📝 演示股票列表: {default_stocks}")
        return
    
    # 2. 筛选
    print("\n⚙️ 开始筛选股票...")
    filtered_df = filter_stocks(df, SCREENING_CRITERIA)
    
    if len(filtered_df) == 0:
        print("⚠️ 没有符合条件的股票，使用默认列表")
        default_stocks = "sh600519,sh600036,sz000858"
        save_results(default_stocks, pd.DataFrame())
        return
    
    # 3. 排序
    if SCREENING_CRITERIA["sort_by"] in filtered_df.columns:
        filtered_df = filtered_df.sort_values(
            SCREENING_CRITERIA["sort_by"],
            ascending=SCREENING_CRITERIA["sort_ascending"]
        )
    
    filtered_df = filtered_df.head(SCREENING_CRITERIA["max_stocks"])
    
    # 4. 格式化并保存
    stock_list = format_stock_list(filtered_df)
    save_results(stock_list, filtered_df)
    
    # 5. 预览
    print("\n📊 筛选结果预览:")
    print("-" * 60)
    preview_cols = ["代码", "名称", "最新价", "涨跌幅", "市盈率"]
    available_preview = [c for c in preview_cols if c in filtered_df.columns]
    print(filtered_df[available_preview].to_string(index=False))
    
    print(f"\n✅ 选股完成! 共 {len(stock_list.split(','))} 只股票")
    print(f"📝 {stock_list}")


if __name__ == "__main__":
    main()
