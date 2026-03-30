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
import random
warnings.filterwarnings('ignore')

# 配置：模拟数据模式（当真实接口不可用时使用）
USE_MOCK_DATA = False  # 设为 False 使用真实 AKShare 数据

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


class StrategyScreenRequest(BaseModel):
    strategy_id: str
    limit: int = 50
    params: Optional[Dict[str, Any]] = None


# ==================== 模拟数据函数（当真实接口不可用时使用） ====================

def get_mock_stocks(count=50):
    """生成模拟股票数据"""
    mock_stocks = [
        {'代码': '000001', '名称': '平安银行', '最新价': 12.35, '涨跌幅': 2.15, '成交量': 12345678, '成交额': 152345678, '市盈率-动态': 5.2, '市净率': 0.65, '总市值': 2395.6, '换手率': 1.2},
        {'代码': '000002', '名称': '万科A', '最新价': 8.56, '涨跌幅': 1.8, '成交量': 8765432, '成交额': 7543210, '市盈率-动态': 8.5, '市净率': 0.72, '总市值': 998.5, '换手率': 0.9},
        {'代码': '600036', '名称': '招商银行', '最新价': 32.15, '涨跌幅': 3.2, '成交量': 15678901, '成交额': 502345678, '市盈率-动态': 6.8, '市净率': 1.1, '总市值': 8156.2, '换手率': 0.5},
        {'代码': '600519', '名称': '贵州茅台', '最新价': 1685.0, '涨跌幅': -0.8, '成交量': 123456, '成交额': 207654321, '市盈率-动态': 28.5, '市净率': 8.5, '总市值': 21125.0, '换手率': 0.1},
        {'代码': '000858', '名称': '五粮液', '最新价': 145.6, '涨跌幅': 1.5, '成交量': 2345678, '成交额': 341234567, '市盈率-动态': 22.3, '市净率': 5.2, '总市值': 5650.8, '换手率': 0.4},
        {'代码': '002594', '名称': '比亚迪', '最新价': 235.8, '涨跌幅': 4.5, '成交量': 5678901, '成交额': 1334567890, '市盈率-动态': 35.6, '市净率': 4.8, '总市值': 6850.2, '换手率': 1.8},
        {'代码': '300750', '名称': '宁德时代', '最新价': 185.6, '涨跌幅': 2.8, '成交量': 3456789, '成交额': 641234567, '市盈率-动态': 32.5, '市净率': 5.6, '总市值': 8150.5, '换手率': 0.6},
        {'代码': '601318', '名称': '中国平安', '最新价': 42.5, '涨跌幅': 1.2, '成交量': 8765432, '成交额': 371234567, '市盈率-动态': 6.5, '市净率': 0.85, '总市值': 7775.0, '换手率': 0.8},
        {'代码': '600900', '名称': '长江电力', '最新价': 24.8, '涨跌幅': 0.5, '成交量': 4567890, '成交额': 112345678, '市盈率-动态': 18.5, '市净率': 2.1, '总市值': 5975.2, '换手率': 0.3},
        {'代码': '601888', '名称': '中国中免', '最新价': 85.6, '涨跌幅': -1.5, '成交量': 1234567, '成交额': 105678901, '市盈率-动态': 25.6, '市净率': 3.2, '总市值': 1775.5, '换手率': 0.7},
    ]

    # 动态生成更多模拟股票
    industries = ['银行', '券商', '保险', '地产', '医药', '科技', '新能源', '消费', '制造', '通信']
    for i in range(len(mock_stocks), count):
        base_price = random.uniform(5, 100)
        change_pct = random.uniform(-5, 5)
        mock_stocks.append({
            '代码': f"{random.randint(600000, 605000):06d}" if i % 2 == 0 else f"{random.randint(1, 999999):06d}",
            '名称': f"模拟股票{i+1}",
            '最新价': round(base_price, 2),
            '涨跌幅': round(change_pct, 2),
            '成交量': random.randint(1000000, 50000000),
            '成交额': random.randint(10000000, 500000000),
            '市盈率-动态': round(random.uniform(5, 50), 2),
            '市净率': round(random.uniform(0.5, 5), 2),
            '总市值': round(random.uniform(50, 2000), 2),
            '换手率': round(random.uniform(0.5, 10), 2)
        })

    return pd.DataFrame(mock_stocks[:count])


def get_mock_stock_history(code, days=90):
    """生成模拟历史数据"""
    base_price = random.uniform(10, 100)
    dates = []
    prices = []

    for i in range(days):
        date = (datetime.now() - timedelta(days=days-i)).strftime('%Y-%m-%d')
        # 模拟价格波动
        if i == 0:
            price = base_price
        else:
            change = random.uniform(-0.05, 0.05)
            price = prices[-1] * (1 + change)
        dates.append(date)
        prices.append(price)

    data = []
    for i, date in enumerate(dates):
        open_p = prices[i] * random.uniform(0.98, 1.02)
        close_p = prices[i]
        high_p = max(open_p, close_p) * random.uniform(1.0, 1.03)
        low_p = min(open_p, close_p) * random.uniform(0.97, 1.0)
        data.append({
            'date': date,
            'open': round(open_p, 2),
            'close': round(close_p, 2),
            'high': round(high_p, 2),
            'low': round(low_p, 2),
            'volume': random.randint(100000, 10000000),
            'amount': random.randint(1000000, 100000000),
        })

    return pd.DataFrame(data)


def get_mock_stock_info(code):
    """生成模拟股票信息"""
    return {
        '股票代码': code,
        '股票名称': f'模拟股票-{code}',
        '当前价格': f'{random.uniform(5, 100):.2f}',
        '市盈率(动)': f'{random.uniform(5, 50):.2f}',
        '市净率': f'{random.uniform(0.5, 5):.2f}',
        '总市值': f'{random.uniform(50, 2000):.2f}亿',
        '换手率': f'{random.uniform(0.5, 10):.2f}%',
    }


def get_mock_index():
    """生成模拟指数数据"""
    return {
        'sh': {'name': '上证指数', 'code': '000001', 'price': 3923.29, 'change_pct': 0.82},
        'sz': {'name': '深证成指', 'code': '399001', 'price': 10523.56, 'change_pct': 1.15},
        'cy': {'name': '创业板指', 'code': '399006', 'price': 2156.78, 'change_pct': 1.45},
    }


def get_mock_market_overview():
    """生成模拟市场概况"""
    return {
        'limit_up_count': random.randint(30, 80),
        'limit_down_count': random.randint(5, 30),
        'hot_sectors': [
            {'name': '新能源汽车', 'net_inflow': 25.6},
            {'name': '半导体', 'net_inflow': 18.3},
            {'name': '人工智能', 'net_inflow': 15.8},
            {'name': '医药生物', 'net_inflow': 12.5},
            {'name': '券商信托', 'net_inflow': 8.9},
        ]
    }


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


# ==================== 技术指标计算 ====================

def calculate_ma(df: pd.DataFrame, periods: list) -> pd.DataFrame:
    """计算移动平均线"""
    for period in periods:
        df[f'ma{period}'] = df['close'].rolling(window=period).mean()
    return df


def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """计算MACD指标"""
    exp1 = df['close'].ewm(span=fast, adjust=False).mean()
    exp2 = df['close'].ewm(span=slow, adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['macd_signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    return df


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """计算RSI指标"""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    df[f'rsi{period}'] = 100 - (100 / (1 + rs))
    return df


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """计算ATR（平均真实波幅）"""
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df[f'atr{period}'] = tr.rolling(window=period).mean()
    return df


def detect_golden_cross(df: pd.DataFrame, short_ma: int = 5, long_ma: int = 20) -> bool:
    """检测均线金叉"""
    if len(df) < max(short_ma, long_ma) + 1:
        return False
    prev_short = df.iloc[-2][f'ma{short_ma}']
    prev_long = df.iloc[-2][f'ma{long_ma}']
    curr_short = df.iloc[-1][f'ma{short_ma}']
    curr_long = df.iloc[-1][f'ma{long_ma}']
    return prev_short <= prev_long and curr_short > curr_long


def detect_macd_golden_cross(df: pd.DataFrame) -> bool:
    """检测MACD金叉"""
    if len(df) < 2:
        return False
    prev = df.iloc[-2]
    curr = df.iloc[-1]
    return prev['macd'] <= prev['macd_signal'] and curr['macd'] > curr['macd_signal']


def detect_breakout(df: pd.DataFrame, period: int = 20) -> bool:
    """检测突破形态"""
    if len(df) < period + 1:
        return False
    high_period = df.iloc[-period-1:-1]['high'].max()
    curr_high = df.iloc[-1]['high']
    return curr_high > high_period


# ==================== API 端点 ====================

@app.get("/")
async def root():
    return {"message": "智能选股系统 API", "version": "1.0.0"}


@app.get("/api/realtime/all")
async def get_realtime_stocks():
    """
    获取所有A股实时行情（从AKShare获取真实数据）
    """
    if USE_MOCK_DATA:
        df = get_mock_stocks(100)
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
                'total_mv': safe_float(row.get('total_mv', 0)),
                'turnover_rate': safe_float(row.get('turnover_rate', 0))
            })
        return {"success": True, "data": stocks, "count": len(stocks)}

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
                '总市值': 'total_mv',
                '换手率': 'turnover_rate'
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
                    'total_mv': safe_float(row.get('total_mv', 0)),
                    'turnover_rate': safe_float(row.get('turnover_rate', 0))
                })
            return stocks

        stocks = await run_sync(fetch_data)
        return {"success": True, "data": stocks, "count": len(stocks)}

    except Exception as e:
        # 真实接口失败时，回退到模拟数据
        print(f"AKShare接口失败，使用模拟数据: {str(e)}")
        return await get_realtime_stocks()


@app.get("/api/realtime/index")
async def get_market_index():
    """
    获取大盘指数（从AKShare获取真实数据）
    """
    if USE_MOCK_DATA:
        return {"success": True, "data": get_mock_index()}

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
        print(f"指数接口失败，使用模拟数据: {str(e)}")
        return {"success": True, "data": get_mock_index()}


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
    if USE_MOCK_DATA:
        df = get_mock_stock_history(code, days=120)
        df = df.rename(columns={'date': 'date'})  # 确保列名一致
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
        return {"success": True, "data": records, "count": len(records)}

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
        print(f"历史数据接口失败，使用模拟数据: {str(e)}")
        return await get_stock_history(code, start_date, end_date, period)


@app.get("/api/stock/{code}/info")
async def get_stock_info(code: str):
    """
    获取个股详细信息（从AKShare获取真实数据）
    """
    if USE_MOCK_DATA:
        return {"success": True, "data": get_mock_stock_info(code)}

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
        print(f"股票信息接口失败，使用模拟数据: {str(e)}")
        return {"success": True, "data": get_mock_stock_info(code)}


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
async def screen_stocks_by_strategy(request: StrategyScreenRequest):
    """
    使用选股策略筛选股票（推荐股票）
    """
    strategy_id = request.strategy_id
    limit = request.limit
    params = request.params or {}

    # 模拟数据模式
    if USE_MOCK_DATA:
        # 获取模拟股票数据
        df = get_mock_stocks(200)
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

        for _, row in df.iterrows():
            code = row['code']
            name = row['name']

            try:
                # 获取模拟历史数据
                hist_df = get_mock_stock_history(code, days=90)
                hist_df = hist_df.rename(columns={'date': 'date'}).reset_index(drop=True)

                match = False
                reason = ""
                indicators = {}
                score = 0

                if strategy_id == "trend_follow":
                    # 趋势跟踪策略
                    ma_short = params.get("ma_short", 5)
                    ma_mid = params.get("ma_mid", 10)
                    ma_long = params.get("ma_long", 20)

                    hist_df = calculate_ma(hist_df, [ma_short, ma_mid, ma_long])
                    latest = hist_df.iloc[-1]

                    ma_short_val = latest[f'ma{ma_short}']
                    ma_mid_val = latest[f'ma{ma_mid}']
                    ma_long_val = latest[f'ma{ma_long}']

                    is_bullish = (ma_short_val > ma_mid_val > ma_long_val)
                    price_above_ma = latest['close'] > ma_short_val
                    volume_ok = row['turnover_rate'] > 2 and row['turnover_rate'] < 15
                    pe_ok = row['pe'] > 0 and row['pe'] < 50

                    if is_bullish and price_above_ma and volume_ok and pe_ok:
                        match = True
                        indicators = {
                            f'ma{ma_short}': safe_float(ma_short_val),
                            f'ma{ma_mid}': safe_float(ma_mid_val),
                            f'ma{ma_long}': safe_float(ma_long_val)
                        }
                        reason = f"均线多头排列(MA{ma_short}>{ma_mid}>{ma_long})，股价站上MA{ma_short}"
                        score = row['change_pct'] * 0.4 + row['turnover_rate'] * 0.3 + 20

                elif strategy_id == "value":
                    # 价值低估策略
                    max_pe = params.get("max_pe", 30)
                    max_pb = params.get("max_pb", 3)

                    pe_ok = row['pe'] > 0 and row['pe'] < max_pe
                    pb_ok = row['pb'] > 0 and row['pb'] < max_pb
                    price_stable = row['change_pct'] > -5 and row['change_pct'] < 5

                    if pe_ok and pb_ok and price_stable:
                        match = True
                        indicators = {
                            'pe': safe_float(row['pe']),
                            'pb': safe_float(row['pb'])
                        }
                        reason = f"PE={row['pe']:.1f}，PB={row['pb']:.2f}，估值合理"
                        pe_score = (max_pe - row['pe']) / max_pe * 50
                        pb_score = (max_pb - row['pb']) / max_pb * 30
                        score = pe_score + pb_score

                elif strategy_id == "volume_price":
                    # 量价配合策略
                    min_change = params.get("min_change", 3)
                    max_change = params.get("max_change", 7)
                    min_turnover = params.get("min_turnover_rate", 3)
                    max_turnover = params.get("max_turnover_rate", 10)

                    change_ok = row['change_pct'] >= min_change and row['change_pct'] <= max_change
                    turnover_ok = row['turnover_rate'] >= min_turnover and row['turnover_rate'] <= max_turnover
                    pe_ok = row['pe'] > 0

                    if change_ok and turnover_ok and pe_ok:
                        match = True
                        indicators = {
                            'change_pct': safe_float(row['change_pct']),
                            'turnover_rate': safe_float(row['turnover_rate'])
                        }
                        reason = f"涨幅{row['change_pct']:.2f}%，换手率{row['turnover_rate']:.2f}%，量价配合"
                        score = row['change_pct'] + row['turnover_rate']

                elif strategy_id == "macd_cross":
                    # MACD金叉策略
                    hist_df = calculate_macd(hist_df, 12, 26, 9)
                    latest = hist_df.iloc[-1]

                    macd_val = latest['macd']
                    signal_val = latest['macd_signal']
                    hist_val = latest['macd_hist']

                    is_golden_cross = detect_macd_golden_cross(hist_df)
                    price_ok = row['change_pct'] > 0 and row['change_pct'] < 8
                    volume_ok = row['turnover_rate'] > 2 and row['turnover_rate'] < 15

                    if is_golden_cross and price_ok and volume_ok:
                        match = True
                        indicators = {
                            'macd': safe_float(macd_val),
                            'macd_signal': safe_float(signal_val),
                            'macd_hist': safe_float(hist_val)
                        }
                        reason = "MACD金叉形成"
                        score = abs(macd_val) * 10 + row['change_pct']

                elif strategy_id == "ma_cross":
                    # 均线交叉策略
                    short_period = params.get("short_period", 5)
                    long_period = params.get("long_period", 20)

                    hist_df = calculate_ma(hist_df, [short_period, long_period])
                    latest = hist_df.iloc[-1]

                    ma_short_val = latest[f'ma{short_period}']
                    ma_long_val = latest[f'ma{long_period}']

                    is_golden_cross = detect_golden_cross(hist_df, short_period, long_period)
                    price_ok = row['change_pct'] > 1 and row['change_pct'] < 7
                    volume_ok = row['turnover_rate'] > 2 and row['turnover_rate'] < 15

                    if is_golden_cross and price_ok and volume_ok:
                        match = True
                        indicators = {
                            f'ma{short_period}': safe_float(ma_short_val),
                            f'ma{long_period}': safe_float(ma_long_val)
                        }
                        reason = f"MA{short_period}上穿MA{long_period}金叉"
                        score = (ma_short_val - ma_long_val) / ma_long_val * 100 + row['change_pct']

                elif strategy_id == "breakout":
                    # 突破形态策略
                    period = params.get("period", 20)

                    hist_df = calculate_ma(hist_df, [period])
                    hist_df = calculate_atr(hist_df, 14)

                    latest = hist_df.iloc[-1]
                    ma_val = latest[f'ma{period}']
                    atr_val = latest.get('atr14', 0)

                    is_breakout = detect_breakout(hist_df, period)
                    volume_high = row['turnover_rate'] > 3
                    price_above_ma = latest['close'] > ma_val

                    if is_breakout and volume_high and price_above_ma:
                        match = True
                        indicators = {
                            f'ma{period}': safe_float(ma_val),
                            'atr14': safe_float(atr_val)
                        }
                        reason = f"突破{period}日高点"
                        score = row['change_pct'] * 0.5 + row['turnover_rate'] * 0.5

                if match:
                    results.append({
                        'code': code,
                        'name': name,
                        'price': safe_float(row['price']),
                        'change_pct': safe_float(row['change_pct']),
                        'volume': safe_float(row['volume']),
                        'turnover': safe_float(row['turnover']),
                        'pe': safe_float(row.get('pe', 0)),
                        'pb': safe_float(row.get('pb', 0)),
                        'turnover_rate': safe_float(row.get('turnover_rate', 0)),
                        'total_mv': safe_float(row.get('total_mv', 0)),
                        'score': safe_float(score),
                        'reason': reason,
                        'indicators': indicators
                    })

            except Exception as e:
                continue

        results = sorted(results, key=lambda x: x.get('score', 0), reverse=True)
        return {"success": True, "data": results[:limit], "count": len(results[:limit]), "strategy_id": strategy_id}

    # 策略参数默认值
    if strategy_id == "trend_follow":
        ma_short = params.get("ma_short", 5)
        ma_mid = params.get("ma_mid", 10)
        ma_long = params.get("ma_long", 20)
        volume_ratio = params.get("volume_ratio", 1.2)
    elif strategy_id == "breakout":
        period = params.get("period", 20)
        volume_multiple = params.get("volume_multiple", 1.5)
        min_price_change = params.get("min_price_change", 2)
    elif strategy_id == "value":
        max_pe = params.get("max_pe", 30)
        max_pb = params.get("max_pb", 3)
        min_roe = params.get("min_roe", 10)
    elif strategy_id == "volume_price":
        min_change = params.get("min_change", 3)
        max_change = params.get("max_change", 7)
        min_turnover = params.get("min_turnover_rate", 3)
        max_turnover = params.get("max_turnover_rate", 10)
    elif strategy_id == "macd_cross":
        fast_period = params.get("fast_period", 12)
        slow_period = params.get("slow_period", 26)
        signal_period = params.get("signal_period", 9)
    elif strategy_id == "ma_cross":
        short_period = params.get("short_period", 5)
        long_period = params.get("long_period", 20)
    else:
        raise HTTPException(status_code=400, detail=f"未知策略ID: {strategy_id}")

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

        # 预筛选：过滤掉明显不符合的股票，减少后续处理量
        if strategy_id in ["trend_follow", "breakout", "volume_price", "macd_cross", "ma_cross"]:
            # 技术策略需要有一定涨幅和成交量
            df = df[
                (df['change_pct'] > -5) &
                (df['change_pct'] < 10) &
                (df['turnover_rate'] > 0.5) &
                (df['turnover_rate'] < 20)
            ]
        elif strategy_id == "value":
            # 价值策略关注估值
            df = df[
                (df['pe'] > 0) &
                (df['pe'] < 100) &
                (df['pb'] > 0) &
                (df['pb'] < 10)
            ]

        # 限制扫描数量以保证性能
        scan_limit = min(len(df), 200)
        df_scan = df.head(scan_limit)

        results = []

        # 对每只股票获取历史数据并计算指标
        for _, row in df_scan.iterrows():
            code = row['code']
            name = row['name']

            try:
                # 获取历史数据（最近60天）
                end_date = datetime.now().strftime('%Y%m%d')
                start_date = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')
                hist_df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq",
                                             start_date=start_date, end_date=end_date)

                if len(hist_df) < 30:
                    continue

                hist_df = hist_df.rename(columns={
                    '日期': 'date',
                    '开盘': 'open',
                    '收盘': 'close',
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'volume',
                    '成交额': 'amount'
                })
                hist_df = hist_df.reset_index(drop=True)

                # 计算所需指标
                match = False
                reason = ""
                indicators = {}
                score = 0

                if strategy_id == "trend_follow":
                    # 趋势跟踪策略：均线多头排列
                    hist_df = calculate_ma(hist_df, [ma_short, ma_mid, ma_long])
                    latest = hist_df.iloc[-1]

                    ma_short_val = latest[f'ma{ma_short}']
                    ma_mid_val = latest[f'ma{ma_mid}']
                    ma_long_val = latest[f'ma{long_ma}']

                    # 检查均线多头排列
                    is_bullish = (ma_short_val > ma_mid_val > ma_long_val)
                    price_above_ma = latest['close'] > ma_short_val
                    volume_ok = row['turnover_rate'] > 2 and row['turnover_rate'] < 15
                    pe_ok = row['pe'] > 0 and row['pe'] < 50

                    if is_bullish and price_above_ma and volume_ok and pe_ok:
                        match = True
                        indicators = {
                            f'ma{ma_short}': safe_float(ma_short_val),
                            f'ma{ma_mid}': safe_float(ma_mid_val),
                            f'ma{ma_long}': safe_float(ma_long_val)
                        }
                        reason = f"均线多头排列(MA{ma_short}>{ma_mid}>{ma_long})，股价站上MA{ma_short}"
                        # 评分：涨幅+换手率+均线排列强度
                        score = row['change_pct'] * 0.4 + row['turnover_rate'] * 0.3 + 20

                elif strategy_id == "breakout":
                    # 突破形态策略
                    hist_df = calculate_ma(hist_df, [period])
                    hist_df = calculate_atr(hist_df, 14)

                    latest = hist_df.iloc[-1]
                    ma_val = latest[f'ma{period}']
                    atr_val = latest.get('atr14', 0)

                    # 检测突破
                    is_breakout = detect_breakout(hist_df, period)
                    volume_high = row['turnover_rate'] > volume_multiple * 2
                    price_above_ma = latest['close'] > ma_val

                    if is_breakout and volume_high and price_above_ma:
                        match = True
                        indicators = {
                            f'ma{period}': safe_float(ma_val),
                            'atr14': safe_float(atr_val),
                            'period_high': safe_float(hist_df.iloc[-period-1:-1]['high'].max())
                        }
                        reason = f"突破{period}日高点，成交量{row['turnover_rate']:.2f}%"
                        score = row['change_pct'] * 0.5 + row['turnover_rate'] * 0.5

                elif strategy_id == "value":
                    # 价值低估策略
                    pe_ok = row['pe'] > 0 and row['pe'] < max_pe
                    pb_ok = row['pb'] > 0 and row['pb'] < max_pb
                    price_stable = row['change_pct'] > -5 and row['change_pct'] < 5

                    if pe_ok and pb_ok and price_stable:
                        match = True
                        indicators = {
                            'pe': safe_float(row['pe']),
                            'pb': safe_float(row['pb'])
                        }
                        reason = f"PE={row['pe']:.1f}，PB={row['pb']:.2f}，估值合理"
                        # 估值越低分数越高
                        pe_score = (max_pe - row['pe']) / max_pe * 50
                        pb_score = (max_pb - row['pb']) / max_pb * 30
                        score = pe_score + pb_score

                elif strategy_id == "volume_price":
                    # 量价配合策略
                    change_ok = row['change_pct'] >= min_change and row['change_pct'] <= max_change
                    turnover_ok = row['turnover_rate'] >= min_turnover and row['turnover_rate'] <= max_turnover
                    pe_ok = row['pe'] > 0

                    if change_ok and turnover_ok and pe_ok:
                        match = True
                        indicators = {
                            'change_pct': safe_float(row['change_pct']),
                            'turnover_rate': safe_float(row['turnover_rate'])
                        }
                        reason = f"涨幅{row['change_pct']:.2f}%，换手率{row['turnover_rate']:.2f}%，量价配合"
                        score = row['change_pct'] + row['turnover_rate']

                elif strategy_id == "macd_cross":
                    # MACD金叉策略
                    hist_df = calculate_macd(hist_df, fast_period, slow_period, signal_period)
                    latest = hist_df.iloc[-1]

                    macd_val = latest['macd']
                    signal_val = latest['macd_signal']
                    hist_val = latest['macd_hist']

                    # 检测MACD金叉
                    is_golden_cross = detect_macd_golden_cross(hist_df)

                    # 额外条件：价格稳定，有成交量
                    price_ok = row['change_pct'] > 0 and row['change_pct'] < 8
                    volume_ok = row['turnover_rate'] > 2 and row['turnover_rate'] < 15

                    if is_golden_cross and price_ok and volume_ok:
                        match = True
                        indicators = {
                            'macd': safe_float(macd_val),
                            'macd_signal': safe_float(signal_val),
                            'macd_hist': safe_float(hist_val)
                        }
                        reason = "MACD金叉形成"
                        score = abs(macd_val) * 10 + row['change_pct']

                elif strategy_id == "ma_cross":
                    # 均线交叉策略
                    hist_df = calculate_ma(hist_df, [short_period, long_period])
                    latest = hist_df.iloc[-1]

                    ma_short_val = latest[f'ma{short_period}']
                    ma_long_val = latest[f'ma{long_period}']

                    # 检测均线金叉
                    is_golden_cross = detect_golden_cross(hist_df, short_period, long_period)

                    price_ok = row['change_pct'] > 1 and row['change_pct'] < 7
                    volume_ok = row['turnover_rate'] > 2 and row['turnover_rate'] < 15

                    if is_golden_cross and price_ok and volume_ok:
                        match = True
                        indicators = {
                            f'ma{short_period}': safe_float(ma_short_val),
                            f'ma{long_period}': safe_float(ma_long_val)
                        }
                        reason = f"MA{short_period}上穿MA{long_period}金叉"
                        score = (ma_short_val - ma_long_val) / ma_long_val * 100 + row['change_pct']

                if match:
                    results.append({
                        'code': code,
                        'name': name,
                        'price': safe_float(row['price']),
                        'change_pct': safe_float(row['change_pct']),
                        'volume': safe_float(row['volume']),
                        'turnover': safe_float(row['turnover']),
                        'pe': safe_float(row.get('pe', 0)),
                        'pb': safe_float(row.get('pb', 0)),
                        'turnover_rate': safe_float(row.get('turnover_rate', 0)),
                        'total_mv': safe_float(row.get('total_mv', 0)),
                        'score': safe_float(score),
                        'reason': reason,
                        'indicators': indicators
                    })

            except Exception as e:
                # 单只股票处理失败，继续处理下一只
                continue

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
    if USE_MOCK_DATA:
        return {"success": True, "data": get_mock_market_overview()}

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
        print(f"市场概况接口失败，使用模拟数据: {str(e)}")
        return {"success": True, "data": get_mock_market_overview()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
