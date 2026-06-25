"""趋势数据查询服务."""

import httpx
import logging
from typing import Dict, List, Optional
from datetime import datetime
import asyncio

from app.config.settings import settings
from app.models.schemas import TimeSeriesPoint, TrendMetricsResponse

logger = logging.getLogger(__name__)


class TrendQueryService:
    """趋势数据查询服务"""
    
    def __init__(self, prometheus_url: str = None):
        self.prometheus_url = prometheus_url or settings.prometheus_url
        self.node_exporter_port = settings.node_exporter_port
        self.timeout = settings.prometheus_timeout
    
    def _get_instance_label(self, ip: str) -> str:
        """构建 instance 标签"""
        return f"{ip}:{self.node_exporter_port}"
    
    def _parse_time(self, time_str: str) -> int:
        """解析 ISO 时间格式为 Unix 时间戳"""
        dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        return int(dt.timestamp())
    
    def _format_time_series(self, result: List) -> List[TimeSeriesPoint]:
        """格式化时间序列数据"""
        points = []
        if result:
            for value in result.get("values", []):
                timestamp = datetime.fromtimestamp(value[0]).isoformat()
                try:
                    val = float(value[1])
                except (ValueError, TypeError):
                    val = 0.0
                points.append(TimeSeriesPoint(timestamp=timestamp, value=val))
        return points
    
    async def _query_range(self, query: str, start: int, end: int, step: str) -> List[TimeSeriesPoint]:
        """执行范围查询"""
        url = f"{self.prometheus_url}/api/v1/query_range"
        params = {
            "query": query,
            "start": start,
            "end": end,
            "step": step
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") == "success" and data.get("data", {}).get("result"):
                    result = data["data"]["result"][0]
                    return self._format_time_series(result)
                return []
        except Exception as e:
            logger.error(f"Prometheus range query failed: {query}, error: {e}")
            return []
    
    def _build_cpu_query(self, instance: str) -> str:
        """构建 CPU 使用率查询"""
        return f'''
        100 - (avg by(instance) (
            irate(node_cpu_seconds_total{{instance="{instance}",mode="idle"}}[1m])
        ) * 100)
        '''
    
    def _build_memory_query(self, instance: str) -> str:
        """构建内存使用率查询"""
        return f'''
        100 - (node_memory_MemAvailable_bytes{{instance="{instance}"}} 
        / node_memory_MemTotal_bytes{{instance="{instance}"}} * 100)
        '''
    
    def _build_disk_io_query(self, instance: str) -> str:
        """构建磁盘 IO 查询（总读写速度）"""
        return f'''
        sum(irate(node_disk_read_bytes_total{{instance="{instance}"}}[1m]))
        + sum(irate(node_disk_written_bytes_total{{instance="{instance}"}}[1m]))
        '''
    
    def _build_load_query(self, instance: str) -> str:
        """构建系统负载查询"""
        return f'node_load1{{instance="{instance}"}}'
    
    def _build_tcp_query(self, instance: str) -> str:
        """构建 TCP 连接数查询"""
        return f'node_netstat_Tcp_CurrEstab{{instance="{instance}"}}'
    
    async def query_trend(self, node: str, ip: str, 
                         start_time: str, end_time: str, 
                         step: str = "1m") -> TrendMetricsResponse:
        """查询时间范围内的趋势数据"""
        instance = self._get_instance_label(ip)
        start = self._parse_time(start_time)
        end = self._parse_time(end_time)
        
        logger.info(f"Querying trend metrics for node={node}, ip={ip}, "
                   f"start={start_time}, end={end_time}, step={step}")
        
        # 并行查询所有指标趋势
        cpu_trend, memory_trend, disk_io_trend, load_trend, tcp_trend = await asyncio.gather(
            self._query_range(self._build_cpu_query(instance), start, end, step),
            self._query_range(self._build_memory_query(instance), start, end, step),
            self._query_range(self._build_disk_io_query(instance), start, end, step),
            self._query_range(self._build_load_query(instance), start, end, step),
            self._query_range(self._build_tcp_query(instance), start, end, step)
        )
        
        return TrendMetricsResponse(
            node=node,
            ip=ip,
            time_range={
                "start": start_time,
                "end": end_time,
                "step": step
            },
            cpu_trend=cpu_trend,
            memory_trend=memory_trend,
            disk_io_trend=disk_io_trend,
            load_trend=load_trend,
            tcp_trend=tcp_trend
        )
    
    async def query_specific_metric_trend(
        self, ip: str, metric_type: str,
        start_time: str, end_time: str, 
        step: str = "1m"
    ) -> List[TimeSeriesPoint]:
        """查询特定指标的趋势数据"""
        instance = self._get_instance_label(ip)
        start = self._parse_time(start_time)
        end = self._parse_time(end_time)
        
        # 根据指标类型选择查询
        query_map = {
            "cpu": self._build_cpu_query(instance),
            "memory": self._build_memory_query(instance),
            "disk_io": self._build_disk_io_query(instance),
            "load": self._build_load_query(instance),
            "tcp": self._build_tcp_query(instance)
        }
        
        query = query_map.get(metric_type)
        if not query:
            logger.error(f"Unknown metric type: {metric_type}")
            return []
        
        return await self._query_range(query, start, end, step)