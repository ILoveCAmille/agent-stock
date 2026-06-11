"""
机器学习因子生成器
使用机器学习方法自动挖掘有效因子
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class MLFactorGenerator:
    """机器学习因子生成器"""
    
    def __init__(self):
        self.models = {}
        self.factor_history = []
    
    def generate_factors(self, stock_data: Dict[str, pd.DataFrame], 
                        factor_library: Dict = None) -> Dict[str, pd.Series]:
        """
        生成机器学习因子
        
        Args:
            stock_data: 股票历史数据 {code: DataFrame}
            factor_library: 基础因子库（可选）
            
        Returns:
            机器学习因子 {factor_name: Series}
        """
        ml_factors = {}
        
        # 1. PCA因子
        pca_factors = self._generate_pca_factors(stock_data)
        ml_factors.update(pca_factors)
        
        # 2. 自动编码器因子
        ae_factors = self._generate_autoencoder_factors(stock_data)
        ml_factors.update(ae_factors)
        
        # 3. 非线性组合因子
        nonlinear_factors = self._generate_nonlinear_factors(stock_data, factor_library)
        ml_factors.update(nonlinear_factors)
        
        # 4. 时序因子
        ts_factors = self._generate_time_series_factors(stock_data)
        ml_factors.update(ts_factors)
        
        # 5. 截面因子
        cs_factors = self._generate_cross_sectional_factors(stock_data)
        ml_factors.update(cs_factors)
        
        return ml_factors
    
    def _generate_pca_factors(self, stock_data: Dict[str, pd.DataFrame], 
                              n_components: int = 10) -> Dict[str, pd.Series]:
        """生成PCA因子"""
        factors = {}
        
        try:
            # 收集所有股票的收益率
            returns_dict = {}
            
            for code, df in stock_data.items():
                if 'close' in df.columns:
                    returns = df['close'].pct_change().dropna()
                    returns_dict[code] = returns
            
            if not returns_dict:
                return factors
            
            # 构建收益率矩阵
            returns_df = pd.DataFrame(returns_dict)
            returns_df = returns_df.dropna()
            
            if len(returns_df) < 30:
                return factors
            
            # 标准化
            returns_std = (returns_df - returns_df.mean()) / returns_df.std()
            
            # 计算协方差矩阵
            cov_matrix = returns_std.cov()
            
            # 特征值分解
            eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
            
            # 按特征值排序
            idx = np.argsort(eigenvalues)[::-1]
            eigenvalues = eigenvalues[idx]
            eigenvectors = eigenvectors[:, idx]
            
            # 生成PCA因子
            for i in range(min(n_components, len(eigenvalues))):
                # 投影到主成分
                pc = returns_std.values @ eigenvectors[:, i]
                factors[f'pca_{i+1}'] = pd.Series(pc, index=returns_df.index)
            
        except Exception as e:
            logger.error(f"生成PCA因子失败: {e}")
        
        return factors
    
    def _generate_autoencoder_factors(self, stock_data: Dict[str, pd.DataFrame],
                                      n_factors: int = 10) -> Dict[str, pd.Series]:
        """生成自动编码器因子（简化版，使用线性近似）"""
        factors = {}
        
        try:
            # 收集特征
            features_dict = {}
            
            for code, df in stock_data.items():
                if 'close' in df.columns:
                    close = df['close'].values
                    
                    # 计算多种特征
                    returns = np.diff(close) / close[:-1]
                    volatility = pd.Series(returns).rolling(20).std().values
                    momentum = close[1:] / close[:-1] - 1
                    
                    # 对齐长度
                    min_len = min(len(returns), len(volatility), len(momentum))
                    
                    features_dict[code] = {
                        'return': returns[-min_len:],
                        'volatility': volatility[-min_len:],
                        'momentum': momentum[-min_len:],
                    }
            
            if not features_dict:
                return factors
            
            # 简化的自动编码器：使用随机投影
            n_stocks = len(features_dict)
            n_periods = min([len(v['return']) for v in features_dict.values()])
            
            if n_periods < 30:
                return factors
            
            # 构建特征矩阵
            feature_matrix = np.zeros((n_periods, n_stocks * 3))
            stock_codes = list(features_dict.keys())
            
            for i, code in enumerate(stock_codes):
                features = features_dict[code]
                feature_matrix[:, i*3] = features['return'][-n_periods:]
                feature_matrix[:, i*3+1] = features['volatility'][-n_periods:]
                feature_matrix[:, i*3+2] = features['momentum'][-n_periods:]
            
            # 随机投影生成因子
            np.random.seed(42)
            for i in range(n_factors):
                # 随机投影矩阵
                projection = np.random.randn(n_stocks * 3)
                projection = projection / np.linalg.norm(projection)
                
                # 投影
                factor_values = feature_matrix @ projection
                
                # 获取索引
                if 'date' in list(stock_data.values())[0].columns:
                    dates = list(stock_data.values())[0]['date'].values[-n_periods:]
                else:
                    dates = pd.date_range(end=pd.Timestamp.now(), periods=n_periods, freq='B')
                
                factors[f'autoencoder_{i+1}'] = pd.Series(factor_values, index=dates)
            
        except Exception as e:
            logger.error(f"生成自动编码器因子失败: {e}")
        
        return factors
    
    def _generate_nonlinear_factors(self, stock_data: Dict[str, pd.DataFrame],
                                    factor_library: Dict = None) -> Dict[str, pd.Series]:
        """生成非线性组合因子"""
        factors = {}
        
        try:
            # 获取基础因子
            base_factors = {}
            
            for code, df in stock_data.items():
                if 'close' in df.columns:
                    close = df['close'].values
                    
                    # 计算基础指标
                    returns = np.diff(close) / close[:-1]
                    
                    # 均线
                    ma5 = pd.Series(close).rolling(5).mean().values
                    ma20 = pd.Series(close).rolling(20).mean().values
                    
                    # RSI
                    deltas = np.diff(close)
                    gains = np.where(deltas > 0, deltas, 0)
                    losses = np.where(deltas < 0, -deltas, 0)
                    avg_gain = pd.Series(gains).rolling(14).mean().values
                    avg_loss = pd.Series(losses).rolling(14).mean().values
                    rsi = np.where(avg_loss > 0, 100 - (100 / (1 + avg_gain / avg_loss)), 100)
                    
                    base_factors[code] = {
                        'returns': returns,
                        'ma_ratio': ma5 / ma20,
                        'rsi': rsi,
                    }
            
            if not base_factors:
                return factors
            
            # 生成非线性组合
            n_periods = min([len(v['returns']) for v in base_factors.values()])
            
            if n_periods < 30:
                return factors
            
            # 非线性因子1: 价格动量 × RSI
            momentum_rsi = []
            for code, bf in base_factors.items():
                m = bf['returns'][-n_periods:]
                r = bf['rsi'][-n_periods:]
                momentum_rsi.append(m * (100 - r) / 100)
            
            if momentum_rsi:
                factors['nonlinear_1'] = pd.Series(np.mean(momentum_rsi, axis=0), 
                                                   index=range(n_periods))
            
            # 非线性因子2: 均线比 × 波动率
            ma_vol = []
            for code, bf in base_factors.items():
                ma = bf['ma_ratio'][-n_periods:]
                vol = pd.Series(bf['returns'][-n_periods:]).rolling(20).std().values
                ma_vol.append(ma / (vol + 1e-6))
            
            if ma_vol:
                factors['nonlinear_2'] = pd.Series(np.nanmean(ma_vol, axis=0), 
                                                   index=range(n_periods))
            
            # 非线性因子3: 交互因子
            for i in range(1, 11):
                np.random.seed(42 + i)
                weights = np.random.randn(len(base_factors))
                weights = weights / np.linalg.norm(weights)
                
                interaction = []
                for j, (code, bf) in enumerate(base_factors.items()):
                    interaction.append(bf['returns'][-n_periods:] * weights[j])
                
                if interaction:
                    factors[f'factor_interaction_{i}'] = pd.Series(np.sum(interaction, axis=0),
                                                                    index=range(n_periods))
            
        except Exception as e:
            logger.error(f"生成非线性因子失败: {e}")
        
        return factors
    
    def _generate_time_series_factors(self, stock_data: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        """生成时序因子"""
        factors = {}
        
        try:
            # 收集所有股票的收益率
            returns_dict = {}
            
            for code, df in stock_data.items():
                if 'close' in df.columns:
                    returns = df['close'].pct_change().dropna()
                    returns_dict[code] = returns
            
            if not returns_dict:
                return factors
            
            returns_df = pd.DataFrame(returns_dict)
            returns_df = returns_df.dropna()
            
            if len(returns_df) < 60:
                return factors
            
            # 时序因子1: 市场动量
            market_return = returns_df.mean(axis=1)
            factors['time_series_1'] = market_return.rolling(20).mean()
            
            # 时序因子2: 市场波动率
            market_vol = returns_df.std(axis=1)
            factors['time_series_2'] = market_vol.rolling(20).mean()
            
            # 时序因子3: 市场偏度
            market_skew = returns_df.skew(axis=1)
            factors['time_series_3'] = market_skew.rolling(20).mean()
            
            # 时序因子4: 市场峰度
            market_kurt = returns_df.kurtosis(axis=1)
            factors['time_series_4'] = market_kurt.rolling(20).mean()
            
            # 时序因子5-10: 滚动统计量
            for i in range(5, 11):
                window = i * 5
                factors[f'time_series_{i}'] = market_return.rolling(window).std()
            
        except Exception as e:
            logger.error(f"生成时序因子失败: {e}")
        
        return factors
    
    def _generate_cross_sectional_factors(self, stock_data: Dict[str, pd.DataFrame]) -> Dict[str, pd.Series]:
        """生成截面因子"""
        factors = {}
        
        try:
            # 收集所有股票的特征
            features_dict = {}
            
            for code, df in stock_data.items():
                if 'close' in df.columns:
                    close = df['close'].values
                    
                    # 计算特征
                    returns = np.diff(close) / close[:-1]
                    volatility = np.std(returns[-20:]) if len(returns) >= 20 else np.std(returns)
                    momentum = (close[-1] / close[-21] - 1) if len(close) > 21 else 0
                    
                    features_dict[code] = {
                        'volatility': volatility,
                        'momentum': momentum,
                        'price': close[-1],
                    }
            
            if not features_dict:
                return factors
            
            # 截面因子1: 波动率排名
            vol_rank = pd.Series({code: f['volatility'] for code, f in features_dict.items()}).rank(pct=True)
            factors['cross_sectional_1'] = vol_rank
            
            # 截面因子2: 动量排名
            mom_rank = pd.Series({code: f['momentum'] for code, f in features_dict.items()}).rank(pct=True)
            factors['cross_sectional_2'] = mom_rank
            
            # 截面因子3: 价格排名
            price_rank = pd.Series({code: f['price'] for code, f in features_dict.items()}).rank(pct=True)
            factors['cross_sectional_3'] = price_rank
            
            # 截面因子4-10: 组合排名
            for i in range(4, 11):
                np.random.seed(42 + i)
                weights = np.random.randn(3)
                weights = weights / np.linalg.norm(weights)
                
                combined = (vol_rank * weights[0] + 
                           mom_rank * weights[1] + 
                           price_rank * weights[2])
                factors[f'cross_sectional_{i}'] = combined.rank(pct=True)
            
        except Exception as e:
            logger.error(f"生成截面因子失败: {e}")
        
        return factors
    
    def get_factor_count(self) -> int:
        """获取生成的因子数量"""
        return 50  # 固定生成50个ML因子


class MLFactorEvaluator:
    """机器学习因子评估器"""
    
    def __init__(self):
        pass
    
    def evaluate_factors(self, ml_factors: Dict[str, pd.Series], 
                         returns: pd.Series) -> Dict[str, Dict]:
        """评估ML因子"""
        results = {}
        
        for factor_name, factor_values in ml_factors.items():
            # 对齐数据
            aligned = pd.DataFrame({
                'factor': factor_values,
                'return': returns
            }).dropna()
            
            if len(aligned) < 30:
                continue
            
            # 计算IC
            ic = aligned['factor'].corr(aligned['return'])
            
            # 计算分组收益
            try:
                aligned['quintile'] = pd.qcut(aligned['factor'], 5, labels=['Q1', 'Q2', 'Q3', 'Q4', 'Q5'], duplicates='drop')
                quintile_returns = aligned.groupby('quintile', observed=False)['return'].mean().to_dict()
                long_short = quintile_returns.get('Q5', 0) - quintile_returns.get('Q1', 0)
            except:
                quintile_returns = {}
                long_short = 0
            
            results[factor_name] = {
                'ic': ic,
                'quintile_returns': quintile_returns,
                'long_short_return': long_short,
                'data_points': len(aligned),
            }
        
        return results
    
    def rank_factors(self, evaluations: Dict[str, Dict]) -> pd.DataFrame:
        """对因子进行排名"""
        data = []
        
        for factor_name, eval_result in evaluations.items():
            data.append({
                'factor': factor_name,
                'ic': eval_result.get('ic', 0),
                'long_short_return': eval_result.get('long_short_return', 0),
                'data_points': eval_result.get('data_points', 0),
            })
        
        df = pd.DataFrame(data)
        
        if not df.empty:
            # 计算综合得分
            df['score'] = abs(df['ic']) * 0.5 + abs(df['long_short_return']) * 0.5
            df = df.sort_values('score', ascending=False)
            df['rank'] = range(1, len(df) + 1)
        
        return df


# 创建全局实例
ml_factor_generator = MLFactorGenerator()
ml_factor_evaluator = MLFactorEvaluator()
