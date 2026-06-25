"""
Mock 测试脚本 - 完整测试 API 功能
无需真实的 Prometheus 数据源
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from fastapi.testclient import TestClient
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.services.realtime_collector import RealtimeCollector
from app.services.trend_query_service import TrendQueryService
from app.models.schemas import (
    RealtimeMetricsResponse, 
    TrendMetricsResponse,
    TCPMetrics, CPUMetrics, MemoryMetrics, DiskIOMetrics, LoadMetrics
)


def test_realtime_collector_with_mock():
    """测试实时指标采集器 - 使用 Mock 数据"""
    print("\n" + "="*60)
    print("测试 1: 实时指标采集器")
    print("="*60)
    
    collector = RealtimeCollector(prometheus_url="http://mock:9090")
    
    # Mock Prometheus 返回数据
    mock_responses = {
        # CPU 指标
        "cpu_usage": 25.5,
        "cpu_cores": 4,
        "cpu_user": 10.0,
        "cpu_system": 5.0,
        "cpu_iowait": 2.0,
        # 内存指标
        "mem_total": 8589934592,
        "mem_available": 4294967296,
        "mem_used": 4294967296,
        "mem_cached": 2147483648,
        "mem_buffered": 1073741824,
        # 磁盘 IO 指标
        "disk_read_bytes": 1024.0,
        "disk_write_bytes": 512.0,
        "disk_read_iops": 10.0,
        "disk_write_iops": 5.0,
        "disk_util": 15.0,
        # 负载指标
        "load_1m": 2.5,
        "load_5m": 3.0,
        "load_15m": 3.5,
        # TCP 指标
        "tcp_connections": 100,
        "tcp_active": 50,
        "tcp_overflow": 5,      # TCP 溢出次数
        "tcp_drops": 0,
        "tcp_retransmits": 10
    }
    
    async def mock_query(query: str):
        """模拟 Prometheus 查询"""
        # 先检查核心数（更具体的匹配）
        if "count(node_cpu" in query:
            return 4
        elif "mode=\"idle\"" in query:
            return 74.5  # CPU 使用率 = 100 - idle
        elif "mode=\"user\"" in query:
            return 10.0
        elif "mode=\"system\"" in query:
            return 5.0
        elif "mode=\"iowait\"" in query:
            return 2.0
        elif "MemTotal" in query:
            return 8589934592
        elif "MemAvailable" in query:
            return 4294967296
        elif "Cached" in query:
            return 2147483648
        elif "Buffers" in query:
            return 1073741824
        elif "disk_read_bytes" in query:
            return 1024.0
        elif "disk_written_bytes" in query:
            return 512.0
        elif "reads_completed" in query:
            return 10.0
        elif "writes_completed" in query:
            return 5.0
        elif "disk_io_time" in query:
            return 15.0
        elif "node_load1" in query:
            return 2.5
        elif "node_load5" in query:
            return 3.0
        elif "node_load15" in query:
            return 3.5
        elif "Tcp_CurrEstab" in query:
            return 100.0
        elif "Tcp_ActiveOpens" in query or "Tcp_PassiveOpens" in query:
            return 50.0
        elif "Tcp_ListenOverflows" in query:
            return 5.0
        elif "Tcp_ListenDrops" in query:
            return 0.0
        elif "Tcp_RetransSegs" in query:
            return 10.0
        return None
    
    # Patch _query_prometheus 方法
    collector._query_prometheus = mock_query
    
    async def run_test():
        result = await collector.collect("node-01", "192.168.1.10")
        
        print(f"节点: {result.node}")
        print(f"IP: {result.ip}")
        print(f"时间戳: {result.timestamp}")
        print(f"\nCPU 指标:")
        print(f"  - 使用率: {result.cpu.usage_percent}%")
        print(f"  - 核心数: {result.cpu.cores}")
        print(f"\n内存指标:")
        print(f"  - 总内存: {result.memory.total_bytes / (1024**3):.2f} GB")
        print(f"  - 使用率: {result.memory.usage_percent:.1f}%")
        print(f"\nTCP 指标:")
        print(f"  - 已建立连接: {result.tcp.connections_established}")
        print(f"  - 监听溢出: {result.tcp.listen_overflows} <-- 关键指标")
        
        # 验证
        assert result.cpu.cores == 4
        assert result.memory.total_bytes == 8589934592
        assert result.tcp.connections_established == 100
        assert result.tcp.listen_overflows == 5  # TCP 溢出
        
        print("\n✅ 实时指标采集测试通过!")
        return result
    
    return asyncio.run(run_test())


def test_trend_query_service_with_mock():
    """测试趋势查询服务 - 使用 Mock 数据"""
    print("\n" + "="*60)
    print("测试 2: 趋势查询服务")
    print("="*60)
    
    service = TrendQueryService(prometheus_url="http://mock:9090")
    
    # Mock 时间序列数据
    async def mock_query_range(query: str, start: int, end: int, step: str):
        """模拟 Prometheus 范围查询"""
        # 生成模拟时间序列
        timestamps = list(range(start, end, 300))  # 5分钟间隔
        points = []
        
        for ts in timestamps[:10]:  # 限制 10 个点
            if "mode=\"idle\"" in query:
                value = 70.0 + (ts % 10)
            elif "MemAvailable" in query:
                value = 45.0 + (ts % 5)
            elif "disk_read" in query or "disk_written" in query:
                value = 1500.0 + (ts % 100)
            elif "node_load1" in query:
                value = 2.5 + (ts % 10) * 0.1
            elif "Tcp_CurrEstab" in query:
                value = 100.0 + (ts % 20)
            elif "Tcp_ListenOverflows" in query:
                value = (ts % 5)  # 0-4 之间的溢出次数
            else:
                value = 50.0
            
            dt = datetime.fromtimestamp(ts)
            points.append({"timestamp": dt.isoformat(), "value": value})
        
        return points
    
    # Patch _query_range 方法
    service._query_range = mock_query_range
    
    async def run_test():
        result = await service.query_trend(
            node="node-01",
            ip="192.168.1.10",
            start_time="2026-06-25T00:00:00Z",
            end_time="2026-06-25T12:00:00Z",
            step="5m"
        )
        
        print(f"节点: {result.node}")
        print(f"IP: {result.ip}")
        print(f"时间范围: {result.time_range['start']} - {result.time_range['end']}")
        print(f"\nCPU 趋势数据点数: {len(result.cpu_trend)}")
        print(f"内存趋势数据点数: {len(result.memory_trend)}")
        print(f"磁盘 IO 趋势数据点数: {len(result.disk_io_trend)}")
        print(f"负载趋势数据点数: {len(result.load_trend)}")
        print(f"\nTCP 连接趋势数据点数: {len(result.tcp_trend)}")
        print(f"TCP 溢出趋势数据点数: {len(result.tcp_overflow_trend)} <-- 关键指标")
        
        # 验证
        assert result.node == "node-01"
        assert len(result.cpu_trend) > 0
        assert len(result.memory_trend) > 0
        assert len(result.tcp_trend) > 0  # TCP 连接数
        assert len(result.tcp_overflow_trend) > 0  # TCP 溢出
        
        # 验证 TCP 溢出字段有数据
        print(f"\nTCP 溢出趋势示例:")
        for point in result.tcp_overflow_trend[:3]:
            print(f"  {point.timestamp}: {point.value} 次")
        
        print("\n✅ 趋势查询服务测试通过!")
        return result
    
    return asyncio.run(run_test())


def test_tcp_queries_different():
    """测试 TCP 连接数和溢出的查询是不同的"""
    print("\n" + "="*60)
    print("测试 3: 验证 TCP 连接数和溢出查询不同")
    print("="*60)
    
    service = TrendQueryService()
    instance = "192.168.1.10:9100"
    
    # TCP 连接数查询
    tcp_query = service._build_tcp_query(instance)
    print(f"TCP 连接数查询: {tcp_query}")
    assert "Tcp_CurrEstab" in tcp_query
    
    # TCP 溢出查询
    tcp_overflow_query = service._build_tcp_overflow_query(instance)
    print(f"TCP 溢出查询: {tcp_overflow_query}")
    assert "Tcp_ListenOverflows" in tcp_overflow_query
    
    # 验证两个查询是不同的
    assert tcp_query != tcp_overflow_query
    print("\n✅ TCP 连接数和溢出查询是不同的!")
    
    return True


def test_api_with_test_client():
    """使用 FastAPI TestClient 测试 API"""
    print("\n" + "="*60)
    print("测试 4: API 端点测试 (使用 TestClient)")
    print("="*60)
    
    client = TestClient(app)
    
    # 测试根路径
    response = client.get("/")
    print(f"\nGET / -> 状态码: {response.status_code}")
    print(f"响应: {response.json()}")
    assert response.status_code == 200
    
    # 测试健康检查
    response = client.get("/api/v1/metrics/health")
    print(f"\nGET /api/v1/metrics/health -> 状态码: {response.status_code}")
    print(f"响应: {response.json()}")
    assert response.status_code == 200
    
    print("\n✅ API 端点测试通过!")


def main():
    """运行所有测试"""
    print("\n" + "#"*60)
    print("# Prometheus MCP Server Mock 测试")
    print("# 测试目标: 验证 TCP 连接数和溢出指标都正确实现")
    print("#"*60)
    
    try:
        # 测试 1: 实时指标采集
        test_realtime_collector_with_mock()
        
        # 测试 2: 趋势查询服务
        test_trend_query_service_with_mock()
        
        # 测试 3: TCP 查询差异
        test_tcp_queries_different()
        
        # 测试 4: API 端点
        test_api_with_test_client()
        
        print("\n" + "="*60)
        print("🎉 所有测试通过!")
        print("="*60)
        print("\n功能验证总结:")
        print("  ✅ 实时指标包含 TCP 溢出 (listen_overflows)")
        print("  ✅ 趋势数据包含 TCP 连接数 (tcp_trend)")
        print("  ✅ 趋势数据包含 TCP 溢出 (tcp_overflow_trend)")
        print("  ✅ 两个 TCP 指标使用不同的 PromQL 查询")
        print("\nAPI 响应字段:")
        print("  - /realtime 返回 tcp.listen_overflows")
        print("  - /trend 返回 tcp_trend (连接数)")
        print("  - /trend 返回 tcp_overflow_trend (溢出)")
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        raise
    except Exception as e:
        print(f"\n❌ 测试错误: {e}")
        raise


if __name__ == "__main__":
    main()
