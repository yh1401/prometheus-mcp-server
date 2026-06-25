"""API 路由."""

from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional
from datetime import datetime

from app.models.schemas import (
    RealtimeMetricsResponse, TrendMetricsResponse, 
    ErrorResponse, TimeSeriesPoint
)
from app.services.realtime_collector import RealtimeCollector
from app.services.trend_query_service import TrendQueryService
from app.config.settings import settings

router = APIRouter(prefix="/api/v1/metrics", tags=["Metrics"])

# 服务实例
realtime_collector = RealtimeCollector()
trend_query_service = TrendQueryService()


@router.get(
    "/realtime",
    response_model=RealtimeMetricsResponse,
    summary="获取节点实时性能指标",
    description="传入节点名和IP，返回当前CPU、内存、IO、负载、TCP等实时指标"
)
async def get_realtime_metrics(
    node: str = Query(..., description="节点名称", example="node-01"),
    ip: str = Query(..., description="节点IP地址", example="192.168.1.10")
):
    """
    获取节点实时性能指标
    
    - **node**: 节点名称
    - **ip**: 节点IP地址（需要部署 Node Exporter）
    
    返回指标包括：
    - CPU 使用率、核心数、用户态/系统态/IO等待
    - 内存总量、已用、可用、使用率、缓存、缓冲
    - 磁盘读写速度、IOPS、利用率
    - 系统负载 1/5/15分钟、每核心负载
    - TCP 连接数、溢出、丢弃、重传
    """
    try:
        result = await realtime_collector.collect(node, ip)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="Failed to collect realtime metrics",
                detail=str(e),
                timestamp=datetime.now().isoformat()
            ).dict()
        )


@router.get(
    "/trend",
    response_model=TrendMetricsResponse,
    summary="获取节点历史趋势数据",
    description="传入节点名、IP和时间范围，返回历史趋势数据"
)
async def get_trend_metrics(
    node: str = Query(..., description="节点名称", example="node-01"),
    ip: str = Query(..., description="节点IP地址", example="192.168.1.10"),
    start_time: str = Query(
        ..., 
        description="开始时间 ISO 格式", 
        example="2026-06-25T00:00:00Z"
    ),
    end_time: str = Query(
        ..., 
        description="结束时间 ISO 格式", 
        example="2026-06-25T23:59:59Z"
    ),
    step: str = Query("1m", description="采样间隔", example="5m")
):
    """
    获取节点历史趋势数据
    
    - **node**: 节点名称
    - **ip**: 节点IP地址
    - **start_time**: 开始时间（ISO 格式）
    - **end_time**: 结束时间（ISO 格式）
    - **step**: 采样间隔（如 1m, 5m, 1h）
    
    返回时间序列数据包括：
    - CPU 使用率趋势
    - 内存使用率趋势
    - 磁盘 IO 趋势
    - 系统负载趋势
    - TCP 连接趋势（CurrEstab）
    - TCP 溢出趋势（ListenOverflows）
    """
    try:
        result = await trend_query_service.query_trend(
            node, ip, start_time, end_time, step
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="Failed to query trend metrics",
                detail=str(e),
                timestamp=datetime.now().isoformat()
            ).dict()
        )


@router.get(
    "/trend/{metric_type}",
    response_model=List[TimeSeriesPoint],
    summary="获取特定指标的历史趋势",
    description="查询特定类型指标的历史趋势数据"
)
async def get_specific_metric_trend(
    metric_type: str,
    ip: str = Query(..., description="节点IP地址", example="192.168.1.10"),
    start_time: str = Query(..., description="开始时间 ISO 格式"),
    end_time: str = Query(..., description="结束时间 ISO 格式"),
    step: str = Query("1m", description="采样间隔")
):
    """
    获取特定指标的历史趋势
    
    - **metric_type**: 指标类型 (cpu, memory, disk_io, load, tcp)
    - **ip**: 节点IP地址
    - **start_time**: 开始时间
    - **end_time**: 结束时间
    - **step**: 采样间隔
    """
    valid_types = ["cpu", "memory", "disk_io", "load", "tcp"]
    if metric_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric_type: {metric_type}. Valid types: {valid_types}"
        )
    
    try:
        result = await trend_query_service.query_specific_metric_trend(
            ip, metric_type, start_time, end_time, step
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="Failed to query specific metric trend",
                detail=str(e),
                timestamp=datetime.now().isoformat()
            ).dict()
        )


@router.get(
    "/health",
    summary="健康检查",
    description="检查服务和 Prometheus 连接状态"
)
async def health_check():
    """健康检查接口"""
    import httpx
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.prometheus_url}/api/v1/status/config")
            prometheus_status = "healthy" if response.status_code == 200 else "unhealthy"
    except Exception:
        prometheus_status = "unreachable"
    
    return {
        "status": "healthy",
        "prometheus": prometheus_status,
        "timestamp": datetime.now().isoformat()
    }