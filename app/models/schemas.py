"""Pydantic 数据模型."""

from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any
from datetime import datetime


# ==================== 请求模型 ====================

class RealtimeMetricsRequest(BaseModel):
    """实时指标查询请求"""
    node: str = Field(..., description="节点名称", example="node-01")
    ip: str = Field(..., description="节点IP地址", example="192.168.1.10")


class TrendMetricsRequest(BaseModel):
    """趋势数据查询请求"""
    node: str = Field(..., description="节点名称", example="node-01")
    ip: str = Field(..., description="节点IP地址", example="192.168.1.10")
    start_time: str = Field(..., description="开始时间 ISO 格式", example="2026-06-25T00:00:00Z")
    end_time: str = Field(..., description="结束时间 ISO 格式", example="2026-06-25T23:59:59Z")
    step: str = Field("1m", description="采样间隔", example="5m")
    
    @validator('start_time', 'end_time')
    def validate_time_format(cls, v):
        """验证时间格式"""
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError(f"Invalid ISO time format: {v}")
        return v


# ==================== 响应模型 ====================

class CPUMetrics(BaseModel):
    """CPU 指标"""
    usage_percent: float = Field(..., description="CPU 使用率百分比")
    cores: int = Field(..., description="CPU 核心数")
    user_percent: Optional[float] = Field(None, description="用户态使用率")
    system_percent: Optional[float] = Field(None, description="系统态使用率")
    iowait_percent: Optional[float] = Field(None, description="IO等待使用率")


class MemoryMetrics(BaseModel):
    """内存指标"""
    total_bytes: int = Field(..., description="总内存（字节）")
    used_bytes: int = Field(..., description="已用内存（字节）")
    available_bytes: int = Field(..., description="可用内存（字节）")
    usage_percent: float = Field(..., description="内存使用率百分比")
    cached_bytes: Optional[int] = Field(None, description="缓存内存（字节）")
    buffered_bytes: Optional[int] = Field(None, description="缓冲内存（字节）")


class DiskIOMetrics(BaseModel):
    """磁盘 IO 指标"""
    read_bytes_per_sec: float = Field(..., description="每秒读取字节")
    write_bytes_per_sec: float = Field(..., description="每秒写入字节")
    read_iops: float = Field(..., description="每秒读操作数")
    write_iops: float = Field(..., description="每秒写操作数")
    disk_utilization: Optional[float] = Field(None, description="磁盘利用率百分比")


class LoadMetrics(BaseModel):
    """系统负载指标"""
    load_1m: float = Field(..., description="1分钟平均负载")
    load_5m: float = Field(..., description="5分钟平均负载")
    load_15m: float = Field(..., description="15分钟平均负载")
    load_per_core: Optional[float] = Field(None, description="每核心负载")


class TCPMetrics(BaseModel):
    """TCP 指标"""
    connections_established: int = Field(..., description="已建立连接数")
    connections_active: Optional[int] = Field(None, description="活跃连接数")
    listen_overflows: int = Field(0, description="监听溢出次数")
    listen_drops: Optional[int] = Field(None, description="监听丢弃次数")
    retransmits: Optional[int] = Field(None, description="重传次数")


class TimeSeriesPoint(BaseModel):
    """时间序列数据点"""
    timestamp: str = Field(..., description="时间戳")
    value: float = Field(..., description="值")


class RealtimeMetricsResponse(BaseModel):
    """实时指标响应"""
    node: str = Field(..., description="节点名称")
    ip: str = Field(..., description="节点IP地址")
    timestamp: str = Field(..., description="采集时间")
    cpu: CPUMetrics = Field(..., description="CPU 指标")
    memory: MemoryMetrics = Field(..., description="内存指标")
    disk_io: DiskIOMetrics = Field(..., description="磁盘 IO 指标")
    load: LoadMetrics = Field(..., description="系统负载指标")
    tcp: TCPMetrics = Field(..., description="TCP 指标")


class TrendMetricsResponse(BaseModel):
    """趋势数据响应"""
    node: str = Field(..., description="节点名称")
    ip: str = Field(..., description="节点IP地址")
    time_range: Dict[str, str] = Field(..., description="时间范围")
    cpu_trend: List[TimeSeriesPoint] = Field(..., description="CPU 使用率趋势")
    memory_trend: List[TimeSeriesPoint] = Field(..., description="内存使用率趋势")
    disk_io_trend: List[TimeSeriesPoint] = Field(..., description="磁盘 IO 趋势")
    load_trend: List[TimeSeriesPoint] = Field(..., description="系统负载趋势")
    tcp_overflow_trend: List[TimeSeriesPoint] = Field(..., description="TCP 溢出趋势（ListenOverflows）")


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str = Field(..., description="错误信息")
    detail: Optional[str] = Field(None, description="详细错误信息")
    timestamp: str = Field(..., description="错误发生时间")