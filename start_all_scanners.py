"""
启动所有选股扫描器
1. 个人投资风格选股
2. 最优因子选股
"""

import os
import sys
import threading
import logging
from datetime import datetime

# Clear proxy
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(key, None)
os.environ['NO_PROXY'] = '*'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, '.')


def run_personal_style_scanner():
    """运行个人投资风格选股"""
    try:
        from trend_stock_scanner import TrendStockScanner
        scanner = TrendStockScanner()
        scanner.run()
    except Exception as e:
        logger.error(f"个人风格选股扫描器错误: {e}")


def run_optimal_factor_scanner():
    """运行最优因子选股"""
    try:
        from optimal_factor_scanner import OptimalFactorStockScanner
        scanner = OptimalFactorStockScanner()
        scanner.run()
    except Exception as e:
        logger.error(f"最优因子选股扫描器错误: {e}")


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("量化选股系统启动")
    logger.info("=" * 60)
    logger.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("")
    logger.info("选股策略:")
    logger.info("  1. 个人投资风格选股 (大盘判断 + 板块轮动 + 新闻扫描)")
    logger.info("  2. 最优因子选股 (价值 + 质量 + 波动 + 动量)")
    logger.info("")
    logger.info("推送频率: 每10分钟")
    logger.info("推送邮箱: 3102189887@qq.com")
    logger.info("=" * 60)
    
    # 创建线程
    thread1 = threading.Thread(target=run_personal_style_scanner, daemon=True, name="PersonalStyle")
    thread2 = threading.Thread(target=run_optimal_factor_scanner, daemon=True, name="OptimalFactor")
    
    # 启动线程
    thread1.start()
    logger.info("[启动] 个人投资风格选股扫描器")
    
    thread2.start()
    logger.info("[启动] 最优因子选股扫描器")
    
    logger.info("")
    logger.info("所有扫描器已启动，正在运行中...")
    logger.info("按 Ctrl+C 停止")
    
    # 保持主线程运行
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\n系统正在停止...")
        logger.info("再见!")


if __name__ == '__main__':
    main()
