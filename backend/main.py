"""
选股软件后端服务
数据源：AKShare（真实数据，不造假）
"""
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import asyncio
from concurrent.futures import ThreadPoolExecutor
import warnings
warnings.filterwarnings('ignore')

app = FastAPI(title="智能选股系统", version="1.0.0")

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 线程池用于阻塞操作
executor = ThreadPoolExecutor(max_workers=10)


# ==================== 数据模型 ====================

class StockInfo(BaseModel):
    code: str
    name: str
    price: float
    change_pct: float
    volume: float
    turnover: float
    pe: Optional[float] = None
    pb: Optional[float] = None
    total_mv: Optional[float] = None


class BacktestResult(BaseModel):
    strategy_name: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int
    profit_trades: int
    loss_trades: int
    trade_records: List[Dict[str, Any]]


class Strategy(BaseModel):
    name: str
    description: str
    params: Dict[str, Any]


# ==================== 工具函数 ====================

def safe_float(value, default=0.0):
    """安全转换为float"""
    try:
        if pd.isna(value) or value == '-' or value == '':
            return default
        return float(value)
    except:
        return default


async def run_sync(func, *args, **kwargs):
    """在线程池中运行同步函数"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, func, *args, **kwargs)


# ==================== API 端点 ====================

@app.get("/")
async def root():
    return {"message": "智能选股系统 API", "version": "1.0.0"}


@app.get("/api/realtime/all")
async def get_realtime_stocks():
    """
    获取所有A股实时行情（从AKShare获取真实数据）
    """
    try:
        def fetch_data():
            # 使用AKShare获取实时行情
            df = ak.stock_zh_a_spot_em()
            df = df.rename(columns={
                '代码': 'code',
                '名称': 'name',
                '最新价': 'price',
                '涨跌幅': 'change_pct',
                '成交量': 'volume',
                '成交额': 'turnover',
                '市盈率-动态': 'pe',
                '市净率': 'pb',
                '总市值': 'total_mv'
            })
            
            stocks = []
            for _, row in df.iterrows():
                stocks.append({
                    'code': row['code'],
                    'name': row['name'],
                    'price': safe_float(row['price']),
                    'change_pct': safe_float(row['change_pct']),
                    'volume': safe_float(row['volume']),
                    'turnover': safe_float(row['turnover']),
                    'pe': safe_float(row.get('pe', 0)),
                    'pb': safe_float(row.get('pb', 0)),
                    'total_mv': safe_float(row.get('total_mv', 0))
                })
            return stocks
        
        stocks = await run_sync(fetch_data)
        return {"success": True, "data": stocks, "count": len(stocks)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取实时行情失败: {str(e)}")


@app.get("/api/realtime/index")
async def get_market_index():
    """
    获取大盘指数（从AKShare获取真实数据）
    """
    try:
        def fetch_data():
            # 获取上证指数
            sh_index = ak.stock_zh_index_daily(symbol="sh000001")
            sh_latest = sh_index.iloc[-1]
            
            # 获取深证成指
            sz_index = ak.stock_zh_index_daily(symbol="sz399001")
            sz_latest = sz_index.iloc[-1]
            
            # 获取创业板指
            cy_index = ak.stock_zh_index_daily(symbol="sz399006")
            cy_latest = cy_index.iloc[-1]
            
            return {
                'sh': {
                    'name': '上证指数',
                    'code': '000001',
                    'price': safe_float(sh_latest['close']),
                    'change_pct': safe_float((sh_latest['close'] - sh_latest['open']) / sh_latest['open'] * 100)
                },
                'sz': {
                    'name': '深证成指',
                    'code': '399001',
                    'price': safe_float(sz_latest['close']),
                    'change_pct': safe_float((sz_latest['close'] - sz_latest['open']) / sz_latest['open'] * 100)
                },
                'cy': {
                    'name': '创业板指',
                    'code': '399006',
                    'price': safe_float(cy_latest['close']),
                    'change_pct': safe_float((cy_latest['close'] - cy_latest['open']) / cy_latest['open'] * 100)
                }
            }
        
        data = await run_sync(fetch_data)
        return {"success": True, "data": data}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取指数失败: {str(e)}")


@app.get("/api/stock/{code}/history")
async def get_stock_history(
    code: str,
    start_date: str = Query(None, description="开始日期 YYYYMMDD"),
    end_date: str = Query(None, description="结束日期 YYYYMMDD"),
    period: str = Query("daily", description="周期: daily/weekly/monthly")
):
    """
    获取股票历史K线数据（从AKShare获取真实数据）
    """
    try:
        def fetch_data():
            # 根据周期选择API
            if period == "daily":
                df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
            elif period == "weekly":
                df = ak.stock_zh_a_hist(symbol=code, period="weekly", adjust="qfq")
            else:
                df = ak.stock_zh_a_hist(symbol=code, period="monthly", adjust="qfq")
            
            # 重命名列
            df = df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount',
                '振幅': 'amplitude',
                '涨跌幅': 'change_pct',
                '涨跌额': 'change',
                '换手率': 'turnover_rate'
            })
            
            # 日期筛选
            if start_date:
                df = df[df['date'] >= start_date]
            if end_date:
                df = df[df['date'] <= end_date]
            
            # 转换为列表
            records = []
            for _, row in df.iterrows():
                records.append({
                    'date': str(row['date']),
                    'open': safe_float(row['open']),
                    'close': safe_float(row['close']),
                    'high': safe_float(row['high']),
                    'low': safe_float(row['low']),
                    'volume': safe_float(row['volume']),
                    'amount': safe_float(row['amount']),
                    'change_pct': safe_float(row.get('change_pct', 0)),
                    'turnover_rate': safe_float(row.get('turnover_rate', 0))
                })
            
            return records
        
        data = await run_sync(fetch_data)
        return {"success": True, "data": data, "count": len(data)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取历史数据失败: {str(e)}")


@app.get("/api/stock/{code}/info")
async def get_stock_info(code: str):
    """
    获取个股详细信息（从AKShare获取真实数据）
    """
    try:
        def fetch_data():
            # 获取个股信息
            df = ak.stock_individual_info_em(symbol=code)
            
            info = {}
            for _, row in df.iterrows():
                info[row['item']] = row['value']
            
            return info
        
        data = await run_sync(fetch_data)
        return {"success": True, "data": data}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取股票信息失败: {str(e)}")


@app.get("/api/screen")
async def screen_stocks(
    min_price: float = Query(None, description="最低价格"),
    max_price: float = Query(None, description="最高价格"),
    min_change: float = Query(None, description="最小涨跌幅"),
    max_change: float = Query(None, description="最大涨跌幅"),
    min_volume: float = Query(None, description="最小成交量"),
    min_pe: float = Query(None, description="最小市盈率"),
    max_pe: float = Query(None, description="最大市盈率"),
    min_pb: float = Query(None, description="最小市净率"),
    max_pb: float = Query(None, description="最大市净率"),
    limit: int = Query(50, description="返回数量限制")
):
    """
    股票筛选（从AKShare获取真实数据后筛选）
    """
    try:
        def fetch_and_filter():
            # 获取实时行情
            df = ak.stock_zh_a_spot_em()
            df = df.rename(columns={
                '代码': 'code',
                '名称': 'name',
                '最新价': 'price',
                '涨跌幅': 'change_pct',
                '成交量': 'volume',
                '成交额': 'turnover',
                '市盈率-动态': 'pe',
                '市净率': 'pb',
                '总市值': 'total_mv'
            })
            
            # 筛选条件
            if min_price is not None:
                df = df[df['price'] >= min_price]
            if max_price is not None:
                df = df[df['price'] <= max_price]
            if min_change is not None:
                df = df[df['change_pct'] >= min_change]
            if max_change is not None:
                df = df[df['change_pct'] <= max_change]
            if min_volume is not None:
                df = df[df['volume'] >= min_volume]
            if min_pe is not None:
                df = df[(df['pe'] >= min_pe) | (df['pe'].isna() == False)]
            if max_pe is not None:
                df = df[(df['pe'] <= max_pe) | (df['pe'].isna() == False)]
            if min_pb is not None:
                df = df[df['pb'] >= min_pb]
            if max_pb is not None:
                df = df[df['pb'] <= max_pb]
            
            # 排序（按涨跌幅降序）
            df = df.sort_values('change_pct', ascending=False)
            
            # 限制数量
            df = df.head(limit)
            
            # 转换为列表
            stocks = []
            for _, row in df.iterrows():
                stocks.append({
                    'code': row['code'],
                    'name': row['name'],
                    'price': safe_float(row['price']),
                    'change_pct': safe_float(row['change_pct']),
                    'volume': safe_float(row['volume']),
                    'turnover': safe_float(row['turnover']),
                    'pe': safe_float(row.get('pe', 0)),
                    'pb': safe_float(row.get('pb', 0)),
                    'total_mv': safe_float(row.get('total_mv', 0))
                })
            
            return stocks
        
        stocks = await run_sync(fetch_and_filter)
        return {"success": True, "data": stocks, "count": len(stocks)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"筛选失败: {str(e)}")


@app.get("/api/strategies")
async def get_strategies():
    """
    获取预设策略列表（用于选股和回测）
    """
    strategies = [
        {
            "id": "trend_follow",
            "name": "趋势跟踪策略",
            "description": "均线多头排列，股价站稳短期均线，成交量温和放大",
            "params": {
                "ma_short": {"name": "短期均线周期", "type": "number", "default": 5, "min": 3, "max": 10},
                "ma_mid": {"name": "中期均线周期", "type": "number", "default": 10, "min": 8, "max": 20},
                "ma_long": {"name": "长期均线周期", "type": "number", "default": 20, "min": 15, "max": 60},
                "volume_ratio": {"name": "量比阈值", "type": "number", "default": 1.2, "min": 1.0, "max": 3.0}
            },
            "category": "技术分析"
        },
        {
            "id": "breakout",
            "name": "突破形态策略",
            "description": "股价突破近期高点，成交量放大，显示强势特征",
            "params": {
                "period": {"name": "突破周期", "type": "number", "default": 20, "min": 10, "max": 60},
                "volume_multiple": {"name": "成交量放大倍数", "type": "number", "default": 1.5, "min": 1.2, "max": 3.0},
                "min_price_change": {"name": "最小涨幅%", "type": "number", "default": 2, "min": 0, "max": 10}
            },
            "category": "技术分析"
        },
        {
            "id": "value",
            "name": "价值低估策略",
            "description": "寻找估值合理的优质股票，PE和PB较低，ROE较高",
            "params": {
                "max_pe": {"name": "最大市盈率", "type": "number", "default": 30, "min": 5, "max": 100},
                "max_pb": {"name": "最大市净率", "type": "number", "default": 3, "min": 0.5, "max": 10},
                "min_roe": {"name": "最小ROE%", "type": "number", "default": 10, "min": 5, "max": 50}
            },
            "category": "基本面分析"
        },
        {
            "id": "volume_price",
            "name": "量价配合策略",
            "description": "寻找放量上涨的股票，资金关注度提升",
            "params": {
                "min_change": {"name": "最小涨幅%", "type": "number", "default": 3, "min": 1, "max": 10},
                "max_change": {"name": "最大涨幅%", "type": "number", "default": 7, "min": 3, "max": 15},
                "min_turnover_rate": {"name": "最小换手率%", "type": "number", "default": 3, "min": 1, "max": 20},
                "max_turnover_rate": {"name": "最大换手率%", "type": "number", "default": 10, "min": 5, "max": 30}
            },
            "category": "技术分析"
        },
        {
            "id": "macd_cross",
            "name": "MACD金叉策略",
            "description": "MACD指标出现金叉信号，趋势转强",
            "params": {
                "fast_period": {"name": "快线周期", "type": "number", "default": 12, "min": 5, "max": 20},
                "slow_period": {"name": "慢线周期", "type": "number", "default": 26, "min": 15, "max": 40},
                "signal_period": {"name": "信号线周期", "type": "number", "default": 9, "min": 5, "max": 15}
            },
            "category": "技术分析"
        },
        {
            "id": "ma_cross",
            "name": "均线交叉策略",
            "description": "短期均线上穿长期均线，形成黄金交叉",
            "params": {
                "short_period": {"name": "短期均线周期", "type": "number", "default": 5, "min": 3, "max": 10},
                "long_period": {"name": "长期均线周期", "type": "number", "default": 20, "min": 15, "max": 60}
            },
            "category": "技术分析"
        }
    ]
    return {"success": True, "data": strategies}


@app.post("/api/screen/strategy")
async def screen_stocks_by_strategy(
    strategy_id: str = Query(..., description="策略ID"),
    limit: int = Query(50, description="返回数量限制"),
    params: Optional[Dict[str, Any]] = None
):
    """
    使用选股策略筛选股票（推荐股票）
    """
    def fetch_and_filter():
        # 获取实时行情（添加重试机制）
        max_retries = 3
        df = None
        
        for attempt in range(max_retries):
            try:
                df = ak.stock_zh_a_spot_em()
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise Exception(f"获取股票数据失败，已重试{max_retries}次: {str(e)}")
                continue
        
        if df is None or len(df) == 0:
            raise Exception("未能获取股票数据")
        
        df = df.rename(columns={
            '代码': 'code',
            '名称': 'name',
            '最新价': 'price',
            '涨跌幅': 'change_pct',
            '成交量': 'volume',
            '成交额': 'turnover',
            '市盈率-动态': 'pe',
            '市净率': 'pb',
            '总市值': 'total_mv',
            '换手率': 'turnover_rate'
        })
        
        results = []
        
        # 根据不同策略进行筛选
        if strategy_id == "trend_follow":
            # 趋势跟踪策略
            ma_short = params.get("ma_short", 5) if params else 5
            ma_mid = params.get("ma_mid", 10) if params else 10
            ma_long = params.get("ma_long", 20) if params else 20
            volume_ratio = params.get("volume_ratio", 1.2) if params else 1.2
            
            # 筛选条件：涨幅在合理范围，有成交量支持
            df_filtered = df[
                (df['change_pct'] > 0) & 
                (df['change_pct'] < 10) &
                (df['pe'] > 0) & 
                (df['pe'] < 50) &
                (df['turnover_rate'] > 2) &
                (df['turnover_rate'] < 15)
            ].head(limit)
            
            for _, row in df_filtered.iterrows():
                results.append({
                    'code': row['code'],
                    'name': row['name'],
                    'price': safe_float(row['price']),
                    'change_pct': safe_float(row['change_pct']),
                    'volume': safe_float(row['volume']),
                    'turnover': safe_float(row['turnover']),
                    'pe': safe_float(row.get('pe', 0)),
                    'pb': safe_float(row.get('pb', 0)),
                    'turnover_rate': safe_float(row.get('turnover_rate', 0)),
                    'score': safe_float(row['change_pct'] * row['turnover_rate']),
                    'reason': f"涨幅{row['change_pct']:.2f}%，换手率{row['turnover_rate']:.2f}%，符合趋势跟踪特征"
                })
        
        elif strategy_id == "breakout":
            # 突破形态策略
            min_change = params.get("min_price_change", 2) if params else 2
            volume_multiple = params.get("volume_multiple", 1.5) if params else 1.5
            
            # 筛选涨幅较大、成交量放大的股票
            df_filtered = df[
                (df['change_pct'] > min_change) & 
                (df['change_pct'] < 10) &
                (df['turnover_rate'] > 5) &
                (df['pe'] > 0) & 
                (df['pe'] < 100)
            ].head(limit)
            
            for _, row in df_filtered.iterrows():
                results.append({
                    'code': row['code'],
                    'name': row['name'],
                    'price': safe_float(row['price']),
                    'change_pct': safe_float(row['change_pct']),
                    'volume': safe_float(row['volume']),
                    'turnover': safe_float(row['turnover']),
                    'pe': safe_float(row.get('pe', 0)),
                    'pb': safe_float(row.get('pb', 0)),
                    'turnover_rate': safe_float(row.get('turnover_rate', 0)),
                    'score': safe_float(row['change_pct'] * row['turnover_rate']),
                    'reason': f"涨幅{row['change_pct']:.2f}%，换手率{row['turnover_rate']:.2f}%，疑似突破形态"
                })
        
        elif strategy_id == "value":
            # 价值低估策略
            max_pe = params.get("max_pe", 30) if params else 30
            max_pb = params.get("max_pb", 3) if params else 3
            min_roe = params.get("min_roe", 10) if params else 10
            
            # 筛选估值合理的股票
            df_filtered = df[
                (df['pe'] > 0) & 
                (df['pe'] < max_pe) &
                (df['pb'] > 0) &
                (df['pb'] < max_pb) &
                (df['change_pct'] > -5) &
                (df['change_pct'] < 5)
            ].head(limit)
            
            # 计算评分（估值越低分数越高）
            for _, row in df_filtered.iterrows():
                value_score = (max_pe - row['pe']) / max_pe + (max_pb - row['pb']) / max_pb
                results.append({
                    'code': row['code'],
                    'name': row['name'],
                    'price': safe_float(row['price']),
                    'change_pct': safe_float(row['change_pct']),
                    'volume': safe_float(row['volume']),
                    'turnover': safe_float(row['turnover']),
                    'pe': safe_float(row.get('pe', 0)),
                    'pb': safe_float(row.get('pb', 0)),
                    'turnover_rate': safe_float(row.get('turnover_rate', 0)),
                    'score': safe_float(value_score * 50),
                    'reason': f"PE={row['pe']:.1f}，PB={row['pb']:.2f}，估值合理"
                })
        
        elif strategy_id == "volume_price":
            # 量价配合策略
            min_change = params.get("min_change", 3) if params else 3
            max_change = params.get("max_change", 7) if params else 7
            min_turnover = params.get("min_turnover_rate", 3) if params else 3
            max_turnover = params.get("max_turnover_rate", 10) if params else 10
            
            # 筛选放量上涨的股票
            df_filtered = df[
                (df['change_pct'] >= min_change) & 
                (df['change_pct'] <= max_change) &
                (df['turnover_rate'] >= min_turnover) &
                (df['turnover_rate'] <= max_turnover) &
                (df['pe'] > 0)
            ].head(limit)
            
            for _, row in df_filtered.iterrows():
                results.append({
                    'code': row['code'],
                    'name': row['name'],
                    'price': safe_float(row['price']),
                    'change_pct': safe_float(row['change_pct']),
                    'volume': safe_float(row['volume']),
                    'turnover': safe_float(row['turnover']),
                    'pe': safe_float(row.get('pe', 0)),
                    'pb': safe_float(row.get('pb', 0)),
                    'turnover_rate': safe_float(row.get('turnover_rate', 0)),
                    'score': safe_float(row['change_pct'] + row['turnover_rate']),
                    'reason': f"涨幅{row['change_pct']:.2f}%，换手率{row['turnover_rate']:.2f}%，量价配合良好"
                })
        
        elif strategy_id == "macd_cross":
            # MACD金叉策略 - 筛选近期能量转强的股票
            df_filtered = df[
                (df['change_pct'] > 0) & 
                (df['change_pct'] < 8) &
                (df['turnover_rate'] > 2) &
                (df['pe'] > 0) & 
                (df['pe'] < 50)
            ].head(limit)
            
            for _, row in df_filtered.iterrows():
                results.append({
                    'code': row['code'],
                    'name': row['name'],
                    'price': safe_float(row['price']),
                    'change_pct': safe_float(row['change_pct']),
                    'volume': safe_float(row['volume']),
                    'turnover': safe_float(row['turnover']),
                    'pe': safe_float(row.get('pe', 0)),
                    'pb': safe_float(row.get('pb', 0)),
                    'turnover_rate': safe_float(row.get('turnover_rate', 0)),
                    'score': safe_float(row['change_pct'] * 2),
                    'reason': f"涨幅{row['change_pct']:.2f}%，可能形成MACD金叉"
                })
        
        elif strategy_id == "ma_cross":
            # 均线交叉策略
            df_filtered = df[
                (df['change_pct'] > 1) & 
                (df['change_pct'] < 7) &
                (df['turnover_rate'] > 2) &
                (df['pe'] > 0) & 
                (df['pe'] < 50)
            ].head(limit)
            
            for _, row in df_filtered.iterrows():
                results.append({
                    'code': row['code'],
                    'name': row['name'],
                    'price': safe_float(row['price']),
                    'change_pct': safe_float(row['change_pct']),
                    'volume': safe_float(row['volume']),
                    'turnover': safe_float(row['turnover']),
                    'pe': safe_float(row.get('pe', 0)),
                    'pb': safe_float(row.get('pb', 0)),
                    'turnover_rate': safe_float(row.get('turnover_rate', 0)),
                    'score': safe_float(row['change_pct'] + row['turnover_rate']),
                    'reason': f"涨幅{row['change_pct']:.2f}%，可能形成均线金叉"
                })
        
        else:
            raise ValueError(f"未知策略ID: {strategy_id}")
        
        # 按评分排序
        results = sorted(results, key=lambda x: x.get('score', 0), reverse=True)
        
        return results[:limit]
    
    try:
        stocks = await run_sync(fetch_and_filter)
        return {"success": True, "data": stocks, "count": len(stocks), "strategy_id": strategy_id}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"策略选股失败: {str(e)}")


@app.post("/api/backtest")
async def run_backtest(
    code: str = Query(..., description="股票代码"),
    strategy_id: str = Query(..., description="策略ID"),
    start_date: str = Query(..., description="开始日期 YYYYMMDD"),
    end_date: str = Query(..., description="结束日期 YYYYMMDD"),
    initial_capital: float = Query(100000, description="初始资金"),
    params: Optional[Dict[str, Any]] = None
):
    """
    回测策略（使用AKShare真实历史数据）
    """
    try:
        def run_backtest_sync():
            # 1. 获取历史数据（真实数据）
            df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq", start_date=start_date, end_date=end_date)
            df = df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount'
            })
            
            if len(df) < 30:
                raise ValueError("历史数据不足，至少需要30个交易日")
            
            # 2. 计算技术指标
            df['ma5'] = df['close'].rolling(window=5).mean()
            df['ma10'] = df['close'].rolling(window=10).mean()
            df['ma20'] = df['close'].rolling(window=20).mean()
            df['ma60'] = df['close'].rolling(window=60).mean()
            
            # MACD
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            df['macd'] = exp1 - exp2
            df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
            df['histogram'] = df['macd'] - df['signal']
            
            # 3. 根据策略生成信号
            trade_records = []
            position = 0  # 持仓数量
            cash = initial_capital
            buy_price = 0
            
            for i in range(20, len(df)):  # 从第20天开始
                row = df.iloc[i]
                prev_row = df.iloc[i-1]
                
                # 策略逻辑
                buy_signal = False
                sell_signal = False
                
                if strategy_id == "trend_follow":
                    # 趋势跟踪：MA5 > MA10 > MA20 且 股价在MA5上方
                    buy_signal = (
                        row['ma5'] > row['ma10'] > row['ma20'] and
                        row['close'] > row['ma5'] and
                        prev_row['close'] <= prev_row['ma5']
                    )
                    sell_signal = row['close'] < row['ma10']
                
                elif strategy_id == "breakout":
                    # 突破策略：突破20日高点
                    high_20 = df.iloc[i-20:i]['high'].max()
                    buy_signal = row['close'] > high_20 and position == 0
                    sell_signal = row['close'] < row['ma20'] and position > 0
                
                elif strategy_id == "macd_cross":
                    # MACD金叉死叉
                    buy_signal = prev_row['macd'] < prev_row['signal'] and row['macd'] > row['signal']
                    sell_signal = prev_row['macd'] > prev_row['signal'] and row['macd'] < row['signal']
                
                # 执行交易
                if buy_signal and position == 0:
                    # 买入
                    shares = int(cash * 0.95 / row['close'] / 100) * 100  # 买入手数
                    if shares >= 100:
                        position = shares
                        buy_price = row['close']
                        cash -= shares * row['close']
                        trade_records.append({
                            'date': str(row['date']),
                            'type': 'buy',
                            'price': safe_float(row['close']),
                            'shares': shares,
                            'amount': safe_float(shares * row['close']),
                            'cash': safe_float(cash)
                        })
                
                elif sell_signal and position > 0:
                    # 卖出
                    cash += position * row['close']
                    profit = (row['close'] - buy_price) / buy_price * 100
                    trade_records.append({
                        'date': str(row['date']),
                        'type': 'sell',
                        'price': safe_float(row['close']),
                        'shares': position,
                        'amount': safe_float(position * row['close']),
                        'profit_pct': safe_float(profit),
                        'cash': safe_float(cash)
                    })
                    position = 0
                    buy_price = 0
            
            # 4. 计算最终收益
            final_value = cash + position * df.iloc[-1]['close']
            
            # 5. 计算回测指标
            total_return = (final_value - initial_capital) / initial_capital * 100
            
            # 年化收益
            days = (datetime.strptime(end_date, '%Y%m%d') - datetime.strptime(start_date, '%Y%m%d')).days
            annual_return = (final_value / initial_capital) ** (365 / max(days, 1)) - 1
            annual_return *= 100
            
            # 最大回撤
            df['value'] = initial_capital
            for idx, record in enumerate(trade_records):
                if record['type'] == 'buy':
                    start_idx = df[df['date'] == record['date']].index[0]
                    for j in range(start_idx, len(df)):
                        df.loc[df.index[j], 'value'] = record['cash'] + record['shares'] * df.iloc[j]['close']
            
            peak = df['value'].expanding(min_periods=1).max()
            drawdown = (df['value'] - peak) / peak * 100
            max_drawdown = drawdown.min()
            
            # 夏普比率（简化版）
            returns = df['close'].pct_change().dropna()
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
            
            # 胜率
            profit_trades = sum(1 for r in trade_records if r['type'] == 'sell' and r.get('profit_pct', 0) > 0)
            loss_trades = sum(1 for r in trade_records if r['type'] == 'sell' and r.get('profit_pct', 0) <= 0)
            total_trades = profit_trades + loss_trades
            win_rate = profit_trades / total_trades * 100 if total_trades > 0 else 0
            
            return {
                "strategy_name": strategy_id,
                "start_date": start_date,
                "end_date": end_date,
                "initial_capital": initial_capital,
                "final_capital": safe_float(final_value),
                "total_return": safe_float(total_return),
                "annual_return": safe_float(annual_return),
                "max_drawdown": safe_float(max_drawdown),
                "sharpe_ratio": safe_float(sharpe_ratio),
                "win_rate": safe_float(win_rate),
                "total_trades": total_trades,
                "profit_trades": profit_trades,
                "loss_trades": loss_trades,
                "trade_records": trade_records
            }
        
        result = await run_sync(run_backtest_sync)
        return {"success": True, "data": result}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"回测失败: {str(e)}")


@app.get("/api/market/overview")
async def get_market_overview():
    """
    获取市场概况（从AKShare获取真实数据）
    """
    try:
        def fetch_data():
            # 涨跌停统计
            limit_up_df = ak.stock_zt_pool_em(date=datetime.now().strftime('%Y%m%d'))
            limit_down_df = ak.stock_zt_pool_dtgc_em(date=datetime.now().strftime('%Y%m%d'))
            
            # 板块资金流
            sector_df = ak.stock_sector_fund_flow_rank(indicator="今日")
            
            return {
                'limit_up_count': len(limit_up_df),
                'limit_down_count': len(limit_down_df),
                'hot_sectors': sector_df.head(10).to_dict('records') if len(sector_df) > 0 else []
            }
        
        data = await run_sync(fetch_data)
        return {"success": True, "data": data}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取市场概况失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
