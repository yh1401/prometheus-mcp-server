"""实时指标采集服务."""

import httpx
import logging
from typing import Dict, Optional, Any
from datetime import datetime
from functools import lru_cache
import asyncio

from app.config.settings import settings
from app.models.schemas import (
    CPUMetrics, MemoryMetrics, DiskIOMetrics, 
    LoadMetrics, TCPMetrics, RealtimeMetricsResponse
)

logger = logging.getLogger(__name__)


class RealtimeCollector:
    """实时指标采集器"""
    
    def __init__(self, prometheus_url: str = None):
        self.prometheus_url = prometheus_url or settings.prometheus_url
        self.node_exporter_port = settings.node_exporter_port
        self.timeout = settings.prometheus_timeout
        self._cache: Dict[str, Dict] = {}
        self._cache_ttl = settings.realtime_cache_ttl
    
    def _get_instance_label(self, ip: str) -> str:
        """构建 instance 标签"""
        return f"{ip}:{self.node_exporter_port}"
    
    async def _query_prometheus(self, query: str) -> Optional[float]:
        """执行单个 PromQL 查询"""
        url = f"{self.prometheus_url}/api/v1/query"
        params = {"query": query}
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") == "success" and data.get("data", {}).get("result"):
                    result = data["data"]["result"][0]
                    return float(result["value"][1])
                return None
        except Exception as e:
            logger.error(f"Prometheus query failed: {query}, error: {e}")
            return None
    
    async def _query_cpu(self, instance: str) -> CPUMetrics:
        """查询 CPU 指标"""
        # CPU 使用率（排除 idle）
        cpu_usage_query = f'''
        100 - (avg by(instance) (
            irate(node_cpu_seconds_total{{instance="{instance}",mode="idle"}}[1m])
        ) * 100)
        '''
        
        # CPU 核心数
        cpu_cores_query = f'''
        count(node_cpu_seconds_total{{instance="{instance}",mode="idle"}})
        '''
        
        # 用户态使用率
        cpu_user_query = f'''
        avg by(instance) (
            irate(node_cpu_seconds_total{{instance="{instance}",mode="user"}}[1m])
        ) * 100
        '''
        
        # 系统态使用率
        cpu_system_query = f'''
        avg by(instance) (
            irate(node_cpu_seconds_total{{instance="{instance}",mode="system"}}[1m])
        ) * 100
        '''
        
        # IO等待
        cpu_iowait_query = f'''
        avg by(instance) (
            irate(node_cpu_seconds_total{{instance="{instance}",mode="iowait"}}[1m])
        ) * 100
        '''
        
        # 并行查询
        usage, cores, user, system, iowait = await asyncio.gather(
            self._query_prometheus(cpu_usage_query),
            self._query_prometheus(cpu_cores_query),
            self._query_prometheus(cpu_user_query),
            self._query_prometheus(cpu_system_query),
            self._query_prometheus(cpu_iowait_query)
        )
        
        return CPUMetrics(
            usage_percent=usage or 0.0,
            cores=int(cores or 1),
            user_percent=user,
            system_percent=system,
            iowait_percent=iowait
        )
    
    async def _query_memory(self, instance: str) -> MemoryMetrics:
        """查询内存指标"""
        # 总内存
        mem_total_query = f'node_memory_MemTotal_bytes{{instance="{instance}"}}'
        
        # 可用内存
        mem_available_query = f'node_memory_MemAvailable_bytes{{instance="{instance}"}}'
        
        # 已用内存
        mem_used_query = f'''
        node_memory_MemTotal_bytes{{instance="{instance}"}} 
        - node_memory_MemAvailable_bytes{{instance="{instance}"}}
        '''
        
        # 缓存
        mem_cached_query = f'node_memory_Cached_bytes{{instance="{instance}"}}'
        
        # 缓冲
        mem_buffered_query = f'node_memory_Buffers_bytes{{instance="{instance}"}}'
        
        # 并行查询
        total, available, used, cached, buffered = await asyncio.gather(
            self._query_prometheus(mem_total_query),
            self._query_prometheus(mem_available_query),
            self._query_prometheus(mem_used_query),
            self._query_prometheus(mem_cached_query),
            self._query_prometheus(mem_buffered_query)
        )
        
        total_bytes = total or 0
        available_bytes = available or 0
        used_bytes = used or (total_bytes - available_bytes)
        
        usage_percent = (used_bytes / total_bytes * 100) if total_bytes > 0 else 0
        
        return MemoryMetrics(
            total_bytes=int(total_bytes),
            used_bytes=int(used_bytes),
            available_bytes=int(available_bytes),
            usage_percent=usage_percent,
            cached_bytes=int(cached) if cached else None,
            buffered_bytes=int(buffered) if buffered else None
        )
    
    async def _query_disk_io(self, instance: str) -> DiskIOMetrics:
        """查询磁盘 IO 指标"""
        # 读速度
        read_bytes_query = f'''
        sum(irate(node_disk_read_bytes_total{{instance="{instance}"}}[1m]))
        '''
        
        # 写速度
        write_bytes_query = f'''
        sum(irate(node_disk_written_bytes_total{{instance="{instance}"}}[1m]))
        '''
        
        # 读 IOPS
        read_iops_query = f'''
        sum(irate(node_disk_reads_completed_total{{instance="{instance}"}}[1m]))
        '''
        
        # 写 IOPS
        write_iops_query = f'''
        sum(irate(node_disk_writes_completed_total{{instance="{instance}"}}[1m]))
        '''
        
        # 磁盘利用率
        disk_util_query = f'''
        avg(irate(node_disk_io_time_seconds_total{{instance="{instance}"}}[1m]) * 100)
        '''
        
        # 并行查询
        read_bytes, write_bytes, read_iops, write_iops, disk_util = await asyncio.gather(
            self._query_prometheus(read_bytes_query),
            self._query_prometheus(write_bytes_query),
            self._query_prometheus(read_iops_query),
            self._query_prometheus(write_iops_query),
            self._query_prometheus(disk_util_query)
        )
        
        return DiskIOMetrics(
            read_bytes_per_sec=read_bytes or 0.0,
            write_bytes_per_sec=write_bytes or 0.0,
            read_iops=read_iops or 0.0,
            write_iops=write_iops or 0.0,
            disk_utilization=disk_util
        )
    
    async def _query_load(self, instance: str) -> LoadMetrics:
        """查询系统负载指标"""
        load_1m_query = f'node_load1{{instance="{instance}"}}'
        load_5m_query = f'node_load5{{instance="{instance}"}}'
        load_15m_query = f'node_load15{{instance="{instance}"}}'
        
        # CPU 核心数（用于计算每核心负载）
        cpu_cores_query = f'''
        count(node_cpu_seconds_total{{instance="{instance}",mode="idle"}})
        '''
        
        # 并行查询
        load_1m, load_5m, load_15m, cores = await asyncio.gather(
            self._query_prometheus(load_1m_query),
            self._query_prometheus(load_5m_query),
            self._query_prometheus(load_15m_query),
            self._query_prometheus(cpu_cores_query)
        )
        
        cores_int = int(cores or 1)
        load_per_core = (load_1m / cores_int) if load_1m and cores_int > 0 else None
        
        return LoadMetrics(
            load_1m=load_1m or 0.0,
            load_5m=load_5m or 0.0,
            load_15m=load_15m or 0.0,
            load_per_core=load_per_core
        )
    
    async def _query_tcp(self, instance: str) -> TCPMetrics:
        """查询 TCP 指标"""
        # 已建立连接数
        connections_query = f'node_netstat_Tcp_CurrEstab{{instance="{instance}"}}'
        
        # 活跃连接数
        active_query = f'''
        node_netstat_Tcp_ActiveOpens{{instance="{instance}"}} 
        + node_netstat_Tcp_PassiveOpens{{instance="{instance}"}}
        '''
        
        # 监听溢出
        overflow_query = f'node_netstat_Tcp_ListenOverflows{{instance="{instance}"}}'
        
        # 监听丢弃
        drops_query = f'node_netstat_Tcp_ListenDrops{{instance="{instance}"}}'
        
        # 重传
        retransmits_query = f'node_netstat_Tcp_RetransSegs{{instance="{instance}"}}'
        
        # 并行查询
        connections, active, overflow, drops, retransmits = await asyncio.gather(
            self._query_prometheus(connections_query),
            self._query_prometheus(active_query),
            self._query_prometheus(overflow_query),
            self._query_prometheus(drops_query),
            self._query_prometheus(retransmits_query)
        )
        
        return TCPMetrics(
            connections_established=int(connections or 0),
            connections_active=int(active) if active else None,
            listen_overflows=int(overflow or 0),
            listen_drops=int(drops) if drops else None,
            retransmits=int(retransmits) if retransmits else None
        )
    
    async def collect(self, node: str, ip: str) -> RealtimeMetricsResponse:
        """采集节点实时性能指标"""
        instance = self._get_instance_label(ip)
        timestamp = datetime.now().isoformat()
        
        logger.info(f"Collecting realtime metrics for node={node}, ip={ip}, instance={instance}")
        
        # 并行采集所有指标
        cpu, memory, disk_io, load, tcp = await asyncio.gather(
            self._query_cpu(instance),
            self._query_memory(instance),
            self._query_disk_io(instance),
            self._query_load(instance),
            self._query_tcp(instance)
        )
        
        return RealtimeMetricsResponse(
            node=node,
            ip=ip,
            timestamp=timestamp,
            cpu=cpu,
            memory=memory,
            disk_io=disk_io,
            load=load,
            tcp=tcp
        )