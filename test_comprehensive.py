"""
综合测试 - 所有模块
"""

import os
import sys

# Clear proxy
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(key, None)

import logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s [%(levelname)s] %(message)s')

sys.path.insert(0, '.')

print('=' * 60)
print('Comprehensive System Test')
print('=' * 60)

# 1. Factor Library
print('\n[1] Factor Library...')
from quant_factors.extended_factor_library import ExtendedFactorLibrary
lib = ExtendedFactorLibrary()
print(f'  Total factors: {lib.get_factor_count()}')

# 2. Market State Identifier
print('\n[2] Market State Identifier...')
from market_state_identifier import MarketStateIdentifier
import pandas as pd
import numpy as np

identifier = MarketStateIdentifier()

# Generate test data
dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='B')
np.random.seed(42)
prices = 3000 * np.cumprod(1 + np.random.normal(0.0003, 0.015, len(dates)))
index_data = pd.DataFrame({'close': prices}, index=dates)

market_state = identifier.identify_market_state(index_data)
print(f'  Market state: {market_state["state_info"]["name"]}')
print(f'  Confidence: {market_state["confidence"]*100:.1f}%')

# 3. Dynamic Weight Adjuster
print('\n[3] Dynamic Weight Adjuster...')
from dynamic_weight_adjuster import DynamicWeightAdjuster
adjuster = DynamicWeightAdjuster()
weights = adjuster.adjust_weights(market_state)
print(f'  Weights: {weights}')

# 4. Backtest Engine
print('\n[4] Backtest Engine...')
from backtest.backtest_engine import BacktestEngine

engine = BacktestEngine(initial_capital=1000000)

# Generate test stock data
test_data = {}
for code in ['600519', '000858', '300750']:
    np.random.seed(hash(code) % 2**32)
    stock_prices = 100 * np.cumprod(1 + np.random.normal(0.0005, 0.02, len(dates)))
    test_data[code] = pd.DataFrame({
        'date': dates,
        'open': stock_prices * (1 + np.random.uniform(-0.01, 0.01, len(dates))),
        'high': stock_prices * (1 + np.random.uniform(0, 0.02, len(dates))),
        'low': stock_prices * (1 + np.random.uniform(-0.02, 0, len(dates))),
        'close': stock_prices,
        'volume': np.random.randint(1000000, 10000000, len(dates)),
    })

def simple_signal(daily_data, date):
    return {code: {'score': np.random.random(), 'signal': 'buy'} for code in daily_data}

results = engine.run_backtest(test_data, simple_signal, '2024-01-01', '2024-12-31', 'monthly', 3)
print(f'  Total return: {results["total_return"]*100:.2f}%')
print(f'  Sharpe ratio: {results["sharpe_ratio"]:.2f}')

# 5. ML Factor Generator
print('\n[5] ML Factor Generator...')
from ml_factor_generator import MLFactorGenerator
ml_gen = MLFactorGenerator()
ml_factors = ml_gen.generate_factors(test_data)
print(f'  Generated {len(ml_factors)} ML factors')

# 6. Data Source Manager
print('\n[6] Data Source Manager...')
from backtest.data_source_manager import DataSourceManager
ds = DataSourceManager()
df = ds.get_stock_history('600519', days=30)
if df is not None and not df.empty:
    print(f'  Got {len(df)} days of data for 600519')

print('\n' + '=' * 60)
print('All tests completed!')
print('=' * 60)
