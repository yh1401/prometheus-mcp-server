"""配置管理模块."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""
    
    # Prometheus 配置
    prometheus_url: str = "http://localhost:9090"
    node_exporter_port: int = 9100
    prometheus_timeout: float = 30.0
    
    # API 配置
    api_port: int = 8000
    api_host: str = "0.0.0.0"
    
    # 查询配置
    default_step: str = "1m"
    realtime_cache_ttl: int = 30  # 实时数据缓存时间（秒）
    
    # 认证配置（可选）
    api_key: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 全局配置实例
settings = Settings()