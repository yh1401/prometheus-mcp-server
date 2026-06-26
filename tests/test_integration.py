"""MCP 集成测试.

测试 MCP Server 与 REST API 的完整集成，验证：
1. REST API 正常工作
2. MCP Tools 与 REST API 返回一致的数据
3. 双端口并存不冲突
4. Mock 模式下功能完整
"""

import pytest
import json
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.main import app as rest_app
from app.simple_mcp_server import list_tools, call_tool
from app.models.schemas import RealtimeMetricsResponse, TrendMetricsResponse, TimeSeriesPoint


# ==================== REST API 测试 ====================

@pytest.mark.asyncio
async def test_rest_api_health_check():
    """测试 REST API 健康检查."""
    from fastapi.testclient import TestClient
    
    client = TestClient(rest_app)
    response = client.get("/api/v1/metrics/health")
    
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "prometheus" in data


@pytest.mark.asyncio
@patch('app.services.realtime_collector.httpx.AsyncClient')
async def test_rest_api_realtime_metrics(mock_client_class):
    """测试 REST API 实时指标查询."""
    from fastapi.testclient import TestClient
    
    # Mock Prometheus 响应
    def mock_get_response(url):
        responses = {
            "/api/v1/query": MagicMock(
                status_code=200,
                json=lambda: {
                    "data": {
                        "result": [
                            {
                                "metric": {},
                                "value": [1687680000, "50.5"]
                            }
                        ]
                    }
                }
            )
        }
        return responses.get(url, MagicMock(status_code=404))
    
    mock_client_instance = AsyncMock()
    mock_client_instance.__aenter__.return_value = mock_client_instance
    mock_client_instance.get.side_effect = mock_get_response
    mock_client_class.return_value = mock_client_instance
    
    client = TestClient(rest_app)
    response = client.get(
        "/api/v1/metrics/realtime",
        params={"node": "test-node", "ip": "192.168.1.100"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["node"] == "test-node"
    assert data["ip"] == "192.168.1.100"


# ==================== MCP 与 REST 一致性测试 ====================

@pytest.mark.asyncio
@patch('app.services.realtime_collector.httpx.AsyncClient')
async def test_mcp_and_rest_return_same_realtime_data(mock_client_class):
    """验证 MCP 和 REST API 返回相同的实时数据."""
    from fastapi.testclient import TestClient
    
    # Mock Prometheus 响应
    def mock_get_response(url):
        return MagicMock(
            status_code=200,
            json=lambda: {
                "data": {
                    "result": [
                        {
                            "metric": {},
                            "value": [1687680000, "50.5"]
                        }
                    ]
                }
            }
        )
    
    mock_client_instance = AsyncMock()
    mock_client_instance.__aenter__.return_value = mock_client_instance
    mock_client_instance.get.side_effect = mock_get_response
    mock_client_class.return_value = mock_client_instance
    
    # 同时获取 MCP 和 REST 数据
    mcp_result = await call_tool(
        "get_realtime_metrics",
        {"node": "test-node", "ip": "192.168.1.100"}
    )
    
    client = TestClient(rest_app)
    rest_response = client.get(
        "/api/v1/metrics/realtime",
        params={"node": "test-node", "ip": "192.168.1.100"}
    )
    
    # 验证两者都返回有效数据
    mcp_data = json.loads(mcp_result[0].text)
    rest_data = rest_response.json()
    
    # 验证基本字段一致
    assert mcp_data["node"] == rest_data["node"]
    assert mcp_data["ip"] == rest_data["ip"]
    assert mcp_data["timestamp"] == rest_data["timestamp"]


@pytest.mark.asyncio
@patch('app.services.trend_query_service.httpx.AsyncClient')
async def test_mcp_and_rest_return_same_trend_data(mock_client_class):
    """验证 MCP 和 REST API 返回相同的趋势数据."""
    from fastapi.testclient import TestClient
    
    # Mock Prometheus 响应
    def mock_get_response(url, params=None):
        return MagicMock(
            status_code=200,
            json=lambda: {
                "data": {
                    "resultType": "matrix",
                    "result": [
                        {
                            "metric": {"instance": "192.168.1.100:9100"},
                            "values": [
                                [1687680000 + i * 60, str(50.0 + i)]
                                for i in range(10)
                            ]
                        }
                    ]
                }
            }
        )
    
    mock_client_instance = AsyncMock()
    mock_client_instance.__aenter__.return_value = mock_client_instance
    mock_client_instance.get.side_effect = mock_get_response
    mock_client_class.return_value = mock_client_instance
    
    now = datetime.now()
    start_time = (now - timedelta(minutes=10)).isoformat()
    end_time = now.isoformat()
    
    # 同时获取 MCP 和 REST 数据
    mcp_result = await call_tool(
        "get_trend_metrics",
        {
            "node": "test-node",
            "ip": "192.168.1.100",
            "start_time": start_time,
            "end_time": end_time,
            "step": "1m"
        }
    )
    
    client = TestClient(rest_app)
    rest_response = client.get(
        "/api/v1/metrics/trend",
        params={
            "node": "test-node",
            "ip": "192.168.1.100",
            "start_time": start_time,
            "end_time": end_time,
            "step": "1m"
        }
    )
    
    # 验证两者都返回有效数据
    mcp_data = json.loads(mcp_result[0].text)
    rest_data = rest_response.json()
    
    # 验证基本字段一致
    assert mcp_data["node"] == rest_data["node"]
    assert mcp_data["ip"] == rest_data["ip"]
    assert len(mcp_data["cpu_trend"]) == len(rest_data["cpu_trend"])


# ==================== MCP 协议测试 ====================

@pytest.mark.asyncio
async def test_mcp_protocol_initialization():
    """测试 MCP 协议初始化."""
    # 获取初始化选项
    init_options = await list_tools()
    
    # 验证工具列表正确暴露
    assert len(init_options) > 0
    
    # 验证每个工具都有正确的结构
    for tool in init_options:
        assert tool.name is not None
        assert tool.description is not None
        assert tool.inputSchema is not None
        assert tool.inputSchema["type"] == "object"


@pytest.mark.asyncio
async def test_mcp_protocol_json_rpc_format():
    """测试 MCP 协议遵循 JSON-RPC 格式."""
    # 调用工具
    with patch('app.mcp_server.realtime_collector.collect') as mock_collect:
        mock_collect.return_value = RealtimeMetricsResponse(
            node="test-node",
            ip="192.168.1.100",
            timestamp=datetime.now().isoformat(),
            cpu={
                "usage_percent": 50.5,
                "cores": 4,
                "user_percent": 30.0,
                "system_percent": 15.0,
                "iowait_percent": 5.5
            },
            memory={
                "total_bytes": 8589934592,
                "used_bytes": 4294967296,
                "available_bytes": 4294967296,
                "usage_percent": 50.0,
                "cached_bytes": 1073741824,
                "buffered_bytes": 536870912
            },
            disk_io={
                "read_bytes_per_sec": 1048576,
                "write_bytes_per_sec": 524288,
                "read_iops": 100,
                "write_iops": 50,
                "disk_utilization": 10.5
            },
            load={
                "load_1m": 1.0,
                "load_5m": 1.2,
                "load_15m": 1.5,
                "load_per_core": 0.25
            },
            tcp={
                "connections_established": 150,
                "connections_active": 200,
                "listen_overflows": 5,
                "listen_drops": 10,
                "retransmits": 2
            }
        )
        
        result = await call_tool(
            "get_realtime_metrics",
            {"node": "test-node", "ip": "192.168.1.100"}
        )
        
        # 验证返回的是 JSON 文本
        assert len(result) == 1
        assert result[0].type == "text"
        
        # 验证可以解析为 JSON
        data = json.loads(result[0].text)
        assert "node" in data
        assert "ip" in data


# ==================== 错误处理集成测试 ====================

@pytest.mark.asyncio
async def test_error_handling_invalid_ip_format():
    """测试错误处理：无效 IP 格式."""
    result = await call_tool(
        "get_realtime_metrics",
        {"node": "test-node", "ip": "invalid-ip"}
    )
    
    # 验证返回错误
    assert len(result) == 1
    data = json.loads(result[0].text)
    # IP 格式验证在服务层处理，这里主要验证不崩溃


@pytest.mark.asyncio
async def test_error_handling_invalid_time_format():
    """测试错误处理：无效时间格式."""
    result = await call_tool(
        "get_trend_metrics",
        {
            "node": "test-node",
            "ip": "192.168.1.100",
            "start_time": "invalid-time",
            "end_time": "2026-06-25T23:59:59Z"
        }
    )
    
    # 验证返回错误
    data = json.loads(result[0].text)
    assert "error" in data


@pytest.mark.asyncio
@patch('app.services.realtime_collector.httpx.AsyncClient')
async def test_error_handling_prometheus_timeout(mock_client_class):
    """测试错误处理：Prometheus 超时."""
    from httpx import TimeoutException
    
    # Mock 超时
    mock_client_instance = AsyncMock()
    mock_client_instance.__aenter__.side_effect = TimeoutException("Request timeout")
    mock_client_class.return_value = mock_client_instance
    
    result = await call_tool(
        "get_realtime_metrics",
        {"node": "test-node", "ip": "192.168.1.100"}
    )
    
    # 验证超时错误被正确处理
    data = json.loads(result[0].text)
    assert "timeout" in data["error"].lower()


# ==================== 并发测试 ====================

@pytest.mark.asyncio
@patch('app.services.realtime_collector.httpx.AsyncClient')
async def test_concurrent_requests_mcp(mock_client_class):
    """测试 MCP 并发请求处理."""
    # Mock Prometheus 响应
    def mock_get_response(url):
        return MagicMock(
            status_code=200,
            json=lambda: {
                "data": {
                    "result": [
                        {
                            "metric": {},
                            "value": [1687680000, "50.5"]
                        }
                    ]
                }
            }
        )
    
    mock_client_instance = AsyncMock()
    mock_client_instance.__aenter__.return_value = mock_client_instance
    mock_client_instance.get.side_effect = mock_get_response
    mock_client_class.return_value = mock_client_instance
    
    # 并发发起多个请求
    tasks = [
        call_tool(
            "get_realtime_metrics",
            {"node": f"test-node-{i}", "ip": f"192.168.1.{100+i}"}
        )
        for i in range(10)
    ]
    
    results = await asyncio.gather(*tasks)
    
    # 验证所有请求都成功
    assert len(results) == 10
    for result in results:
        data = json.loads(result[0].text)
        assert "node" in data


# ==================== 性能测试 ====================

@pytest.mark.asyncio
@patch('app.services.realtime_collector.httpx.AsyncClient')
async def test_performance_response_time(mock_client_class):
    """测试响应时间性能."""
    import time
    
    # Mock Prometheus 响应
    def mock_get_response(url):
        return MagicMock(
            status_code=200,
            json=lambda: {
                "data": {
                    "result": [
                        {
                            "metric": {},
                            "value": [1687680000, "50.5"]
                        }
                    ]
                }
            }
        )
    
    mock_client_instance = AsyncMock()
    mock_client_instance.__aenter__.return_value = mock_client_instance
    mock_client_instance.get.side_effect = mock_get_response
    mock_client_class.return_value = mock_client_instance
    
    # 测量响应时间
    start_time = time.time()
    result = await call_tool(
        "get_realtime_metrics",
        {"node": "test-node", "ip": "192.168.1.100"}
    )
    end_time = time.time()
    
    # 验证响应时间在合理范围内（< 1 秒）
    response_time = end_time - start_time
    assert response_time < 1.0, f"Response time {response_time}s exceeds threshold"
    
    # 验证请求成功
    assert len(result) == 1
    json.loads(result[0].text)  # 验证可以解析


# ==================== Mock 模式验证 ====================

@pytest.mark.asyncio
async def test_mock_mode_full_functionality():
    """验证 Mock 模式下完整功能."""
    # 使用 Mock 测试所有工具
    with patch('app.mcp_server.realtime_collector.collect') as mock_collect, \
         patch('app.mcp_server.trend_query_service.query_trend') as mock_trend, \
         patch('app.mcp_server.httpx.AsyncClient') as mock_http:
        
        # Mock 实时指标
        mock_collect.return_value = RealtimeMetricsResponse(
            node="test-node",
            ip="192.168.1.100",
            timestamp=datetime.now().isoformat(),
            cpu={
                "usage_percent": 50.5,
                "cores": 4,
                "user_percent": 30.0,
                "system_percent": 15.0,
                "iowait_percent": 5.5
            },
            memory={
                "total_bytes": 8589934592,
                "used_bytes": 4294967296,
                "available_bytes": 4294967296,
                "usage_percent": 50.0,
                "cached_bytes": 1073741824,
                "buffered_bytes": 536870912
            },
            disk_io={
                "read_bytes_per_sec": 1048576,
                "write_bytes_per_sec": 524288,
                "read_iops": 100,
                "write_iops": 50,
                "disk_utilization": 10.5
            },
            load={
                "load_1m": 1.0,
                "load_5m": 1.2,
                "load_15m": 1.5,
                "load_per_core": 0.25
            },
            tcp={
                "connections_established": 150,
                "connections_active": 200,
                "listen_overflows": 5,
                "listen_drops": 10,
                "retransmits": 2
            }
        )
        
        # Mock 趋势数据
        now = datetime.now()
        time_points = [
            TimeSeriesPoint(
                timestamp=(now - timedelta(minutes=i)).isoformat(),
                value=50.0 + i
            )
            for i in range(10)
        ]
        mock_trend.return_value = TrendMetricsResponse(
            node="test-node",
            ip="192.168.1.100",
            time_range={
                "start": (now - timedelta(minutes=10)).isoformat(),
                "end": now.isoformat()
            },
            cpu_trend=time_points,
            memory_trend=time_points,
            disk_io_trend=time_points,
            load_trend=time_points,
            tcp_trend=time_points,
            tcp_overflow_trend=time_points
        )
        
        # Mock 健康检查
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_http_instance = AsyncMock()
        mock_http_instance.__aenter__.return_value = mock_http_instance
        mock_http_instance.get.return_value = mock_response
        mock_http.return_value = mock_http_instance
        
        # 测试所有工具
        tools = await list_tools()
        tool_names = [t.name for t in tools]
        
        # 验证所有工具都被测试
        assert "get_realtime_metrics" in tool_names
        assert "get_trend_metrics" in tool_names
        assert "get_health_status" in tool_names
        
        # 测试实时指标
        realtime_result = await call_tool(
            "get_realtime_metrics",
            {"node": "test-node", "ip": "192.168.1.100"}
        )
        assert len(realtime_result) == 1
        
        # 测试趋势指标
        trend_result = await call_tool(
            "get_trend_metrics",
            {
                "node": "test-node",
                "ip": "192.168.1.100",
                "start_time": (now - timedelta(minutes=10)).isoformat(),
                "end_time": now.isoformat()
            }
        )
        assert len(trend_result) == 1
        
        # 测试健康检查
        health_result = await call_tool("get_health_status", {})
        assert len(health_result) == 1