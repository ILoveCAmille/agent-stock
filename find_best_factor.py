import os
import sys

for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(key, None)

import logging
logging.basicConfig(level=logging.WARNING)

sys.path.insert(0, '.')

from quant_factors.optimal_factor_selector import OptimalFactorSelector

selector = OptimalFactorSelector()
optimal = selector.select_optimal_factors(top_n=10)

print('=' * 60)
print('TOP 10 Best Factors')
print('=' * 60)
print(f"{'Rank':<5} {'Factor':<25} {'Category':<12} {'Stability':<10} {'Drawdown':<10} {'Score':<10}")
print('-' * 60)
for f in optimal[:10]:
    print(f"{f['rank']:<5} {f['display_name']:<25} {f['category']:<12} {f['stability']:<10.3f} {f['drawdown']:<10.3f} {f['estimated_score']:<10.3f}")

print('=' * 60)
print()
best = optimal[0]
print(f"Best Factor: {best['display_name']}")
print(f"Category: {best['category']}")
print(f"Stability: {best['stability']}")
print(f"Drawdown: {best['drawdown']}")
print(f"Score: {best['estimated_score']}")
print(f"Direction: {best['direction']}")
