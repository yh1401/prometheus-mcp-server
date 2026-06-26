"""MCP Server 单元测试.

测试 MCP Server 的核心功能，包括工具列表暴露、工具调用处理、
参数验证、错误处理等。
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.simple_mcp_server import (
    simple_server,
    list_tools,
    call_tool,
    SimpleMCPServer,
    TextContent
)
from app.models.schemas import RealtimeMetricsResponse, TrendMetricsResponse, TimeSeriesPoint


# ==================== 工具列表测试 ====================

@pytest.mark.asyncio
async def test_list_tools():
    """测试获取工具列表."""
    tools = await list_tools()
    
    # 验证工具数量
    assert len(tools) == 5
    
    # 验证必需的工具存在
    tool_names = [tool.name for tool in tools]
    assert "get_realtime_metrics" in tool_names
    assert "get_trend_metrics" in tool_names
    assert "get_specific_metric_trend" in tool_names
    assert "get_health_status" in tool_names
    assert "list_monitored_nodes" in tool_names


@pytest.mark.asyncio
async def test_realtime_metrics_tool_schema():
    """测试实时指标工具的 Schema."""
    tools = await list_tools()
    realtime_tool = next((t for t in tools if t.name == "get_realtime_metrics"), None)
    
    assert realtime_tool is not None
    assert realtime_tool.description
    
    schema = realtime_tool.inputSchema
    assert schema["type"] == "object"
    
    # 验证必需参数
    assert "node" in schema["properties"]
    assert "ip" in schema["properties"]
    assert "node" in schema["required"]
    assert "ip" in schema["required"]
    
    # 验证参数类型
    assert schema["properties"]["node"]["type"] == "string"
    assert schema["properties"]["ip"]["type"] == "string"
    assert schema["properties"]["ip"]["format"] == "ipv4"


@pytest.mark.asyncio
async def test_trend_metrics_tool_schema():
    """测试趋势指标工具的 Schema."""
    tools = await list_tools()
    trend_tool = next((t for t in tools if t.name == "get_trend_metrics"), None)
    
    assert trend_tool is not None
    assert trend_tool.description
    
    schema = trend_tool.inputSchema
    assert schema["type"] == "object"
    
    # 验证必需参数
    required = schema["required"]
    assert "node" in required
    assert "ip" in required
    assert "start_time" in required
    assert "end_time" in required
    
    # 验证可选参数
    assert "step" in schema["properties"]
    assert schema["properties"]["step"]["type"] == "string"
    
    # 验证时间格式
    assert schema["properties"]["start_time"]["format"] == "date-time"
    assert schema["properties"]["end_time"]["format"] == "date-time"


@pytest.mark.asyncio
async def test_specific_metric_trend_tool_schema():
    """测试特定指标趋势工具的 Schema."""
    tools = await list_tools()
    specific_tool = next((t for t in tools if t.name == "get_specific_metric_trend"), None)
    
    assert specific_tool is not None
    
    schema = specific_tool.inputSchema
    
    # 验证枚举值
    metric_type_prop = schema["properties"]["metric_type"]
    assert "enum" in metric_type_prop
    expected_enum = ["cpu", "memory", "disk_io", "load", "tcp"]
    assert metric_type_prop["enum"] == expected_enum


# ==================== 工具调用测试 ====================

@pytest.mark.asyncio
@patch('app.simple_mcp_server.realtime_collector.collect')
async def test_call_realtime_metrics_success(mock_collect):
    """测试成功调用实时指标查询."""
    # Mock 返回数据
    mock_result = RealtimeMetricsResponse(
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
    mock_collect.return_value = mock_result
    
    # 调用工具
    result = await call_tool(
        "get_realtime_metrics",
        {"node": "test-node", "ip": "192.168.1.100"}
    )
    
    # 验证结果
    assert len(result) == 1
    assert result[0].type == "text"
    
    # 验证 JSON 可解析
    data = json.loads(result[0].text)
    assert data["node"] == "test-node"
    assert data["ip"] == "192.168.1.100"
    assert data["cpu"]["usage_percent"] == 50.5
    
    # 验证服务被调用
    mock_collect.assert_called_once_with(node="test-node", ip="192.168.1.100")


@pytest.mark.asyncio
async def test_call_realtime_metrics_missing_params():
    """测试调用实时指标查询缺少参数."""
    result = await call_tool("get_realtime_metrics", {"node": "test-node"})
    
    assert len(result) == 1
    assert result[0].type == "text"
    
    data = json.loads(result[0].text)
    assert "error" in data
    assert "Missing required parameters" in data["error"]


@pytest.mark.asyncio
@patch('app.mcp_server.trend_query_service.query_trend')
async def test_call_trend_metrics_success(mock_query):
    """测试成功调用趋势指标查询."""
    # Mock 返回数据
    now = datetime.now()
    time_points = [
        TimeSeriesPoint(timestamp=(now - timedelta(minutes=i)).isoformat(), value=50.0 + i)
        for i in range(10)
    ]
    
    mock_result = TrendMetricsResponse(
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
    mock_query.return_value = mock_result
    
    # 调用工具
    result = await call_tool(
        "get_trend_metrics",
        {
            "node": "test-node",
            "ip": "192.168.1.100",
            "start_time": (now - timedelta(minutes=10)).isoformat(),
            "end_time": now.isoformat(),
            "step": "1m"
        }
    )
    
    # 验证结果
    assert len(result) == 1
    assert result[0].type == "text"
    
    # 验证 JSON 可解析
    data = json.loads(result[0].text)
    assert data["node"] == "test-node"
    assert len(data["cpu_trend"]) == 10
    
    # 验证服务被调用
    mock_query.assert_called_once()


@pytest.mark.asyncio
async def test_call_trend_metrics_missing_params():
    """测试调用趋势指标查询缺少参数."""
    result = await call_tool(
        "get_trend_metrics",
        {"node": "test-node", "ip": "192.168.1.100"}
    )
    
    data = json.loads(result[0].text)
    assert "error" in data
    assert "Missing required parameters" in data["error"]


@pytest.mark.asyncio
@patch('app.mcp_server.trend_query_service.query_specific_metric_trend')
async def test_call_specific_metric_trend_success(mock_query):
    """测试成功调用特定指标趋势查询."""
    # Mock 返回数据
    time_points = [
        TimeSeriesPoint(
            timestamp=(datetime.now() - timedelta(minutes=i)).isoformat(),
            value=50.0 + i
        )
        for i in range(5)
    ]
    mock_query.return_value = time_points
    
    # 调用工具
    result = await call_tool(
        "get_specific_metric_trend",
        {
            "metric_type": "cpu",
            "ip": "192.168.1.100",
            "start_time": "2026-06-25T00:00:00Z",
            "end_time": "2026-06-25T23:59:59Z",
            "step": "5m"
        }
    )
    
    # 验证结果
    assert len(result) == 1
    assert result[0].type == "text"
    
    data = json.loads(result[0].text)
    assert len(data) == 5
    assert data[0]["value"] == 50.0


@pytest.mark.asyncio
async def test_call_specific_metric_trend_invalid_metric_type():
    """测试调用特定指标趋势查询使用无效指标类型."""
    result = await call_tool(
        "get_specific_metric_trend",
        {
            "metric_type": "invalid_metric",
            "ip": "192.168.1.100",
            "start_time": "2026-06-25T00:00:00Z",
            "end_time": "2026-06-25T23:59:59Z"
        }
    )
    
    data = json.loads(result[0].text)
    assert "error" in data
    assert "Invalid metric_type" in data["error"]


@pytest.mark.asyncio
@patch('app.mcp_server.httpx.AsyncClient')
async def test_call_health_status_success(mock_client_class):
    """测试健康检查成功."""
    # Mock Prometheus 响应
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_client_instance = AsyncMock()
    mock_client_instance.__aenter__.return_value = mock_client_instance
    mock_client_instance.get.return_value = mock_response
    mock_client_class.return_value = mock_client_instance
    
    # 调用工具
    result = await call_tool("get_health_status", {})
    
    # 验证结果
    assert len(result) == 1
    assert result[0].type == "text"
    
    data = json.loads(result[0].text)
    assert "service" in data
    assert "prometheus_status" in data
    assert data["prometheus_status"] == "healthy"


@pytest.mark.asyncio
@patch('app.mcp_server.httpx.AsyncClient')
async def test_call_health_status_prometheus_down(mock_client_class):
    """测试健康检查 Prometheus 不可达."""
    # Mock 异常
    mock_client_instance = AsyncMock()
    mock_client_instance.__aenter__.side_effect = Exception("Connection refused")
    mock_client_class.return_value = mock_client_instance
    
    # 调用工具
    result = await call_tool("get_health_status", {})
    
    data = json.loads(result[0].text)
    assert "prometheus_status" in data
    assert "unreachable" in data["prometheus_status"]


@pytest.mark.asyncio
async def test_call_unknown_tool():
    """测试调用未知工具."""
    result = await call_tool("unknown_tool", {})
    
    data = json.loads(result[0].text)
    assert "error" in data
    assert "Unknown tool" in data["error"]


# ==================== 辅助函数测试 ====================

def test_format_json_response_dict():
    """测试格式化字典响应."""
    data = {"key": "value", "number": 123}
    result = format_json_response(data)
    
    assert isinstance(result, str)
    parsed = json.loads(result)
    assert parsed == data


def test_format_json_response_pydantic():
    """测试格式化 Pydantic 模型响应."""
    point = TimeSeriesPoint(timestamp="2026-06-25T00:00:00Z", value=50.0)
    result = format_json_response(point)
    
    assert isinstance(result, str)
    parsed = json.loads(result)
    assert parsed["timestamp"] == "2026-06-25T00:00:00Z"
    assert parsed["value"] == 50.0


def test_create_error_response():
    """测试创建错误响应."""
    result = create_error_response(
        error="Test error",
        detail="Detailed error message",
        timestamp="2026-06-25T00:00:00Z"
    )
    
    data = json.loads(result)
    assert data["error"] == "Test error"
    assert data["detail"] == "Detailed error message"
    assert data["timestamp"] == "2026-06-25T00:00:00Z"


def test_create_error_response_auto_timestamp():
    """测试创建错误响应自动生成时间戳."""
    result = create_error_response(error="Test error")
    
    data = json.loads(result)
    assert "timestamp" in data
    # 验证时间戳格式
    datetime.fromisoformat(data["timestamp"])