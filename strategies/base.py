"""
策略基底類別
"""
from abc import ABC, abstractmethod
import pandas as pd


class BaseStrategy(ABC):
    """所有選股策略的抽象基底"""

    name: str = ""
    description: str = ""

    @abstractmethod
    def score(self, price_df: pd.DataFrame, **kwargs) -> float:
        """
        計算個股策略分數 (0~100)
        price_df: 該股票的歷史價量資料，欄位含 date, open, high, low, close, volume
        kwargs: 其他策略所需的額外資料
        回傳: 0~100 的分數
        """
        pass

    @abstractmethod
    def details(self, price_df: pd.DataFrame, **kwargs) -> dict:
        """
        回傳策略訊號的詳細資訊 (供前端顯示)
        """
        pass

    def _clamp(self, score: float) -> float:
        """將分數限制在 0~100"""
        return max(0.0, min(100.0, score))
