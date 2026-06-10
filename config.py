import os
import logging
from dotenv import load_dotenv

# 加载环境变量（override=True 强制覆盖已存在的环境变量）
# 注意：此文件是配置的单一入口点，其他模块不应再调用 load_dotenv()
_load_dotenv_done = False
if not _load_dotenv_done:
    load_dotenv(override=True)
    _load_dotenv_done = True

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# DeepSeek API配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").strip()

# 默认AI模型名称（支持任何OpenAI兼容的模型）
DEFAULT_MODEL_NAME = os.getenv("DEFAULT_MODEL_NAME", "deepseek-v4-pro").strip()

# API调用配置
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "120"))  # API超时时间（秒）- Mimo API较慢，需要更长超时
API_MAX_RETRIES = int(os.getenv("API_MAX_RETRIES", "3"))  # 最大重试次数

# 数据缓存配置
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))  # 缓存有效期（秒）

# 其他配置
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")

# 股票数据源配置
DEFAULT_PERIOD = "1y"  # 默认获取1年数据
DEFAULT_INTERVAL = "1d"  # 默认日线数据

# MiniQMT量化交易配置
MINIQMT_CONFIG = {
    'enabled': os.getenv("MINIQMT_ENABLED", "false").lower() == "true",
    'account_id': os.getenv("MINIQMT_ACCOUNT_ID", ""),
    'host': os.getenv("MINIQMT_HOST", "127.0.0.1"),
    'port': int(os.getenv("MINIQMT_PORT", "58610")),
}

# TDX股票数据API配置项目地址github.com/oficcejo/tdx-api
TDX_CONFIG = {
    'enabled': os.getenv("TDX_ENABLED", "false").lower() == "true",
    'base_url': os.getenv("TDX_BASE_URL", "http://192.168.1.222:8181"),
}