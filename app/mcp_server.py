"""MCP Server 模块.

基于 MCP 协议的工具暴露层，将现有的 Prometheus 监控查询能力
以标准 MCP Tools 形式提供给 StarAgent 等 AI Agent 平台。
"""

import logging
import json
from typing import Any
from datetime import datetime

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
import httpx

from app.services.realtime_collector import RealtimeCollector
from app.services.trend_query_service import TrendQueryService
from app.models.schemas import (
    RealtimeMetricsResponse, TrendMetricsResponse,
    ErrorResponse
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# 创建 MCP Server 实例
server = Server("prometheus-mcp-server", version="1.0.0")

# 服务实例
realtime_collector = RealtimeCollector()
trend_query_service = TrendQueryService()


@server.list_tools()
async def list_tools() -> list[Tool]:
    """暴露所有可用的 MCP Tools."""
    
    tools = [
        Tool(
            name="get_realtime_metrics",
            description=(
                "获取节点实时性能指标。返回当前 CPU 使用率、内存使用情况、"
                "磁盘 I/O、系统负载、TCP 连接状态等监控数据。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {
                        "type": "string",
                        "description": "节点名称，例如：node-01, server-01",
                        "examples": ["node-01", "server-01"]
                    },
                    "ip": {
                        "type": "string",
                        "description": (
                            "节点 IP 地址，该节点需部署 Node Exporter 服务，"
                            "Prometheus 正在采集其数据"
                        ),
                        "examples": ["192.168.1.10", "10.0.0.5"],
                        "format": "ipv4"
                    }
                },
                "required": ["node", "ip"],
                "additionalProperties": False
            }
        ),
        Tool(
            name="get_trend_metrics",
            description=(
                "获取节点历史趋势数据。返回指定时间范围内的性能指标趋势，"
                "包括 CPU 使用率、内存使用率、磁盘 I/O、系统负载、TCP 连接数和 TCP 溢出等。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {
                        "type": "string",
                        "description": "节点名称，例如：node-01, server-01",
                        "examples": ["node-01", "server-01"]
                    },
                    "ip": {
                        "type": "string",
                        "description": "节点 IP 地址",
                        "examples": ["192.168.1.10", "10.0.0.5"],
                        "format": "ipv4"
                    },
                    "start_time": {
                        "type": "string",
                        "description": (
                            "开始时间，ISO 8601 格式，例如：2026-06-25T00:00:00Z。"
                            "注意时间应为 UTC 时区。"
                        ),
                        "examples": ["2026-06-25T00:00:00Z", "2026-06-26T00:00:00Z"],
                        "format": "date-time"
                    },
                    "end_time": {
                        "type": "string",
                        "description": (
                            "结束时间，ISO 8601 格式，例如：2026-06-25T23:59:59Z。"
                            "注意时间应为 UTC 时区。"
                        ),
                        "examples": ["2026-06-25T23:59:59Z", "2026-06-26T23:59:59Z"],
                        "format": "date-time"
                    },
                    "step": {
                        "type": "string",
                        "description": (
                            "采样间隔，决定数据点的密度。常用值："
                            "1m（每分钟）、5m（每5分钟）、1h（每小时）"
                        ),
                        "examples": ["1m", "5m", "1h", "15m"],
                        "default": "1m"
                    }
                },
                "required": ["node", "ip", "start_time", "end_time"],
                "additionalProperties": False
            }
        ),
        Tool(
            name="get_specific_metric_trend",
            description=(
                "获取特定指标的历史趋势数据。支持查询单个指标类型的趋势，"
                "用于精细化的性能分析。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "metric_type": {
                        "type": "string",
                        "description": "指标类型",
                        "enum": ["cpu", "memory", "disk_io", "load", "tcp"],
                        "enumDescriptions": {
                            "cpu": "CPU 使用率趋势",
                            "memory": "内存使用率趋势",
                            "disk_io": "磁盘 I/O 趋势",
                            "load": "系统负载趋势",
                            "tcp": "TCP 连接数趋势"
                        }
                    },
                    "ip": {
                        "type": "string",
                        "description": "节点 IP 地址",
                        "examples": ["192.168.1.10", "10.0.0.5"],
                        "format": "ipv4"
                    },
                    "start_time": {
                        "type": "string",
                        "description": "开始时间，ISO 8601 格式",
                        "examples": ["2026-06-25T00:00:00Z"],
                        "format": "date-time"
                    },
                    "end_time": {
                        "type": "string",
                        "description": "结束时间，ISO 8601 格式",
                        "examples": ["2026-06-25T23:59:59Z"],
                        "format": "date-time"
                    },
                    "step": {
                        "type": "string",
                        "description": "采样间隔，默认 1m",
                        "examples": ["1m", "5m", "1h"],
                        "default": "1m"
                    }
                },
                "required": ["metric_type", "ip", "start_time", "end_time"],
                "additionalProperties": False
            }
        ),
        Tool(
            name="get_health_status",
            description=(
                "检查服务和 Prometheus 连接状态。用于监控 MCP Server 自身健康状态，"
                "以及与后端 Prometheus 的连接是否正常。"
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        ),
        Tool(
            name="list_monitored_nodes",
            description=(
                "列出当前监控的所有节点信息。返回 Prometheus 中已配置的 "
                "Node Exporter 目标列表，包括节点名称、IP 地址和状态。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "description": "筛选节点状态",
                        "enum": ["active", "down", "any"],
                        "enumDescriptions": {
                            "active": "仅返回在线节点",
                            "down": "仅返回离线节点",
                            "any": "返回所有节点"
                        },
                        "default": "any"
                    }
                },
                "additionalProperties": False
            }
        )
    ]
    
    logger.info(f"MCP Tools 暴露完成，共 {len(tools)} 个工具")
    return tools


def format_json_response(data: Any, indent: int = 2) -> str:
    """格式化 JSON 响应为易读字符串."""
    try:
        return json.dumps(
            data if isinstance(data, dict) or isinstance(data, list) else data.model_dump(),
            ensure_ascii=False,
            indent=indent,
            default=str
        )
    except Exception as e:
        logger.error(f"格式化 JSON 失败: {e}")
        return str(data)


def create_error_response(
    error: str,
    detail: str | None = None,
    timestamp: str | None = None
) -> str:
    """创建错误响应."""
    error_obj = ErrorResponse(
        error=error,
        detail=detail,
        timestamp=timestamp or datetime.now().isoformat()
    )
    return format_json_response(error_obj)


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """处理 MCP Tool 调用."""
    
    logger.info(f"MCP Tool 调用: {name}, 参数: {arguments}")
    
    try:
        if name == "get_realtime_metrics":
            # 参数验证
            node = arguments.get("node")
            ip = arguments.get("ip")
            
            if not node or not ip:
                error_msg = create_error_response(
                    error="Missing required parameters",
                    detail="node and ip are required parameters"
                )
                return [TextContent(type="text", text=error_msg)]
            
            # 调用现有服务
            result = await realtime_collector.collect(node=node, ip=ip)
            
            # 格式化响应
            response_text = format_json_response(result)
            logger.info(f"实时指标查询成功: node={node}, ip={ip}")
            
            return [TextContent(type="text", text=response_text)]
        
        elif name == "get_trend_metrics":
            # 参数验证
            node = arguments.get("node")
            ip = arguments.get("ip")
            start_time = arguments.get("start_time")
            end_time = arguments.get("end_time")
            step = arguments.get("step", "1m")
            
            if not all([node, ip, start_time, end_time]):
                error_msg = create_error_response(
                    error="Missing required parameters",
                    detail="node, ip, start_time, and end_time are required parameters"
                )
                return [TextContent(type="text", text=error_msg)]
            
            # 调用现有服务
            result = await trend_query_service.query_trend(
                node=node,
                ip=ip,
                start_time=start_time,
                end_time=end_time,
                step=step
            )
            
            # 格式化响应
            response_text = format_json_response(result)
            logger.info(f"趋势数据查询成功: node={node}, time_range=[{start_time}, {end_time}]")
            
            return [TextContent(type="text", text=response_text)]
        
        elif name == "get_specific_metric_trend":
            # 参数验证
            metric_type = arguments.get("metric_type")
            ip = arguments.get("ip")
            start_time = arguments.get("start_time")
            end_time = arguments.get("end_time")
            step = arguments.get("step", "1m")
            
            valid_types = ["cpu", "memory", "disk_io", "load", "tcp"]
            if metric_type not in valid_types:
                error_msg = create_error_response(
                    error="Invalid metric_type",
                    detail=f"Valid types: {valid_types}, got: {metric_type}"
                )
                return [TextContent(type="text", text=error_msg)]
            
            if not all([ip, start_time, end_time]):
                error_msg = create_error_response(
                    error="Missing required parameters",
                    detail="ip, start_time, and end_time are required parameters"
                )
                return [TextContent(type="text", text=error_msg)]
            
            # 调用现有服务
            result = await trend_query_service.query_specific_metric_trend(
                ip=ip,
                metric_type=metric_type,
                start_time=start_time,
                end_time=end_time,
                step=step
            )
            
            # 格式化响应
            response_text = format_json_response(result)
            logger.info(f"特定指标趋势查询成功: metric={metric_type}, ip={ip}")
            
            return [TextContent(type="text", text=response_text)]
        
        elif name == "get_health_status":
            # 健康检查
            from app.config.settings import settings
            
            health_info = {
                "service": "prometheus-mcp-server",
                "version": "1.0.0",
                "timestamp": datetime.now().isoformat(),
                "prometheus_url": settings.prometheus_url,
                "prometheus_status": "unknown",
                "node_exporter_port": settings.node_exporter_port
            }
            
            # 检查 Prometheus 连接
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(
                        f"{settings.prometheus_url}/api/v1/status/config"
                    )
                    if response.status_code == 200:
                        health_info["prometheus_status"] = "healthy"
                    else:
                        health_info["prometheus_status"] = f"unhealthy (HTTP {response.status_code})"
            except Exception as e:
                health_info["prometheus_status"] = f"unreachable: {str(e)}"
            
            response_text = format_json_response(health_info)
            logger.info(f"健康检查完成: {health_info['prometheus_status']}")
            
            return [TextContent(type="text", text=response_text)]
        
        elif name == "list_monitored_nodes":
            # 列出监控节点
            from app.config.settings import settings
            
            state_filter = arguments.get("state", "any")
            
            nodes_info = {
                "timestamp": datetime.now().isoformat(),
                "prometheus_url": settings.prometheus_url,
                "nodes": []
            }
            
            try:
                # 从 Prometheus 获取 targets
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        f"{settings.prometheus_url}/api/v1/targets"
                    )
                    
                    if response.status_code == 200:
                        targets_data = response.json()
                        
                        for target in targets_data.get("data", {}).get("activeTargets", []):
                            labels = target.get("labels", {})
                            health = target.get("health", "unknown")
                            last_error = target.get("lastError", "")
                            
                            # 应用状态筛选
                            if state_filter == "active" and health != "up":
                                continue
                            if state_filter == "down" and health == "up":
                                continue
                            
                            instance = labels.get("instance", "")
                            job = labels.get("job", "")
                            
                            # 解析 IP 地址
                            ip = instance.split(":")[0] if ":" in instance else instance
                            
                            node_info = {
                                "instance": instance,
                                "ip": ip,
                                "job": job,
                                "health": health,
                                "last_error": last_error if last_error else None,
                                "last_scrape": target.get("lastScrape"),
                                "scrape_duration": target.get("scrapeDuration")
                            }
                            
                            nodes_info["nodes"].append(node_info)
                        
                        logger.info(f"获取监控节点列表成功: {len(nodes_info['nodes'])} 个节点")
                    else:
                        nodes_info["error"] = f"Failed to query Prometheus: HTTP {response.status_code}"
                        
            except Exception as e:
                nodes_info["error"] = f"Error querying Prometheus: {str(e)}"
                logger.error(f"获取监控节点列表失败: {e}")
            
            response_text = format_json_response(nodes_info)
            
            return [TextContent(type="text", text=response_text)]
        
        else:
            # 未知工具
            error_msg = create_error_response(
                error="Unknown tool",
                detail=f"Tool '{name}' is not supported. Available tools: get_realtime_metrics, get_trend_metrics, get_specific_metric_trend, get_health_status, list_monitored_nodes"
            )
            logger.warning(f"未知工具调用: {name}")
            return [TextContent(type="text", text=error_msg)]
    
    except ValueError as e:
        # 参数验证错误
        error_msg = create_error_response(
            error="Invalid parameters",
            detail=str(e)
        )
        logger.error(f"参数验证错误: {e}")
        return [TextContent(type="text", text=error_msg)]
    
    except httpx.TimeoutException as e:
        # Prometheus 超时
        error_msg = create_error_response(
            error="Request timeout",
            detail=f"Prometheus request timeout: {str(e)}"
        )
        logger.error(f"Prometheus 请求超时: {e}")
        return [TextContent(type="text", text=error_msg)]
    
    except httpx.HTTPError as e:
        # HTTP 错误
        error_msg = create_error_response(
            error="HTTP error",
            detail=f"Prometheus HTTP error: {str(e)}"
        )
        logger.error(f"Prometheus HTTP 错误: {e}")
        return [TextContent(type="text", text=error_msg)]
    
    except Exception as e:
        # 未知错误
        error_msg = create_error_response(
            error="Internal error",
            detail=str(e)
        )
        logger.exception(f"工具调用异常: {name}")
        return [TextContent(type="text", text=error_msg)]


async def main():
    """启动 MCP Server（stdio 模式）。"""
    logger.info("=" * 60)
    logger.info("Prometheus MCP Server (stdio 模式) 启动")
    logger.info("=" * 60)
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())