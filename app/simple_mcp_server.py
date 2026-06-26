"""简化版 MCP Server - 不依赖 MCP SDK.

此版本手动实现 MCP 协议的基本功能，用于在 Python 3.9 环境下
进行测试和验证。
"""

import logging
import json
from typing import Any, List, Optional
from datetime import datetime
from dataclasses import dataclass

from app.services.realtime_collector import RealtimeCollector
from app.services.trend_query_service import TrendQueryService
from app.models.schemas import RealtimeMetricsResponse, TrendMetricsResponse, ErrorResponse

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class Tool:
    """MCP Tool 定义."""
    name: str
    description: str
    inputSchema: dict


@dataclass
class TextContent:
    """MCP 文本内容."""
    type: str
    text: str


class SimpleMCPServer:
    """简化版 MCP Server."""
    
    def __init__(self):
        self.name = "prometheus-mcp-server"
        self.version = "1.0.0"
        self.collector = RealtimeCollector()
        self.trend_service = TrendQueryService()
    
    async def list_tools(self) -> List[Tool]:
        """获取工具列表."""
        return [
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
                            "description": "节点 IP 地址",
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
                    "获取节点历史趋势数据。返回指定时间范围内的性能指标趋势。"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "node": {"type": "string", "description": "节点名称"},
                        "ip": {"type": "string", "description": "节点 IP 地址"},
                        "start_time": {
                            "type": "string",
                            "description": "开始时间，ISO 8601 格式",
                            "format": "date-time"
                        },
                        "end_time": {
                            "type": "string",
                            "description": "结束时间，ISO 8601 格式",
                            "format": "date-time"
                        },
                        "step": {
                            "type": "string",
                            "description": "采样间隔",
                            "default": "1m",
                            "examples": ["1m", "5m", "1h"]
                        }
                    },
                    "required": ["node", "ip", "start_time", "end_time"],
                    "additionalProperties": False
                }
            ),
            Tool(
                name="get_specific_metric_trend",
                description="获取特定指标的历史趋势数据。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "metric_type": {
                            "type": "string",
                            "enum": ["cpu", "memory", "disk_io", "load", "tcp"]
                        },
                        "ip": {"type": "string", "description": "节点 IP 地址"},
                        "start_time": {
                            "type": "string",
                            "description": "开始时间，ISO 8601 格式"
                        },
                        "end_time": {
                            "type": "string",
                            "description": "结束时间，ISO 8601 格式"
                        },
                        "step": {
                            "type": "string",
                            "description": "采样间隔",
                            "default": "1m"
                        }
                    },
                    "required": ["metric_type", "ip", "start_time", "end_time"],
                    "additionalProperties": False
                }
            ),
            Tool(
                name="get_health_status",
                description="检查服务和 Prometheus 连接状态。",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False
                }
            ),
            Tool(
                name="list_monitored_nodes",
                description="列出当前监控的所有节点信息。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "state": {
                            "type": "string",
                            "enum": ["active", "down", "any"],
                            "default": "any"
                        }
                    },
                    "additionalProperties": False
                }
            )
        ]
    
    def format_json_response(self, data: Any, indent: int = 2) -> str:
        """格式化 JSON 响应."""
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
        self,
        error: str,
        detail: Optional[str] = None,
        timestamp: Optional[str] = None
    ) -> str:
        """创建错误响应."""
        error_obj = ErrorResponse(
            error=error,
            detail=detail,
            timestamp=timestamp or datetime.now().isoformat()
        )
        return self.format_json_response(error_obj)
    
    async def call_tool(self, name: str, arguments: dict) -> List[TextContent]:
        """处理 MCP Tool 调用."""
        
        logger.info(f"工具调用: {name}, 参数: {arguments}")
        
        try:
            if name == "get_realtime_metrics":
                node = arguments.get("node")
                ip = arguments.get("ip")
                
                if not node or not ip:
                    error_msg = self.create_error_response(
                        error="Missing required parameters",
                        detail="node and ip are required"
                    )
                    return [TextContent(type="text", text=error_msg)]
                
                result = await self.collector.collect(node=node, ip=ip)
                response_text = self.format_json_response(result)
                logger.info(f"实时指标查询成功: node={node}, ip={ip}")
                
                return [TextContent(type="text", text=response_text)]
            
            elif name == "get_trend_metrics":
                node = arguments.get("node")
                ip = arguments.get("ip")
                start_time = arguments.get("start_time")
                end_time = arguments.get("end_time")
                step = arguments.get("step", "1m")
                
                if not all([node, ip, start_time, end_time]):
                    error_msg = self.create_error_response(
                        error="Missing required parameters",
                        detail="node, ip, start_time, and end_time are required"
                    )
                    return [TextContent(type="text", text=error_msg)]
                
                result = await self.trend_service.query_trend(
                    node=node, ip=ip,
                    start_time=start_time, end_time=end_time, step=step
                )
                response_text = self.format_json_response(result)
                logger.info(f"趋势数据查询成功: node={node}")
                
                return [TextContent(type="text", text=response_text)]
            
            elif name == "get_specific_metric_trend":
                metric_type = arguments.get("metric_type")
                ip = arguments.get("ip")
                start_time = arguments.get("start_time")
                end_time = arguments.get("end_time")
                step = arguments.get("step", "1m")
                
                valid_types = ["cpu", "memory", "disk_io", "load", "tcp"]
                if metric_type not in valid_types:
                    error_msg = self.create_error_response(
                        error="Invalid metric_type",
                        detail=f"Valid types: {valid_types}"
                    )
                    return [TextContent(type="text", text=error_msg)]
                
                if not all([ip, start_time, end_time]):
                    error_msg = self.create_error_response(
                        error="Missing required parameters",
                        detail="ip, start_time, and end_time are required"
                    )
                    return [TextContent(type="text", text=error_msg)]
                
                result = await self.trend_service.query_specific_metric_trend(
                    ip=ip, metric_type=metric_type,
                    start_time=start_time, end_time=end_time, step=step
                )
                response_text = self.format_json_response(result)
                
                return [TextContent(type="text", text=response_text)]
            
            elif name == "get_health_status":
                import httpx
                from app.config.settings import settings
                
                health_info = {
                    "service": "prometheus-mcp-server",
                    "version": self.version,
                    "timestamp": datetime.now().isoformat(),
                    "prometheus_url": settings.prometheus_url,
                    "prometheus_status": "unknown"
                }
                
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        response = await client.get(f"{settings.prometheus_url}/api/v1/status/config")
                        if response.status_code == 200:
                            health_info["prometheus_status"] = "healthy"
                        else:
                            health_info["prometheus_status"] = f"unhealthy (HTTP {response.status_code})"
                except Exception as e:
                    health_info["prometheus_status"] = f"unreachable: {str(e)}"
                
                response_text = self.format_json_response(health_info)
                return [TextContent(type="text", text=response_text)]
            
            elif name == "list_monitored_nodes":
                import httpx
                from app.config.settings import settings
                
                state_filter = arguments.get("state", "any")
                nodes_info = {
                    "timestamp": datetime.now().isoformat(),
                    "prometheus_url": settings.prometheus_url,
                    "nodes": []
                }
                
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.get(f"{settings.prometheus_url}/api/v1/targets")
                        
                        if response.status_code == 200:
                            targets_data = response.json()
                            
                            for target in targets_data.get("data", {}).get("activeTargets", []):
                                labels = target.get("labels", {})
                                health = target.get("health", "unknown")
                                
                                if state_filter == "active" and health != "up":
                                    continue
                                if state_filter == "down" and health == "up":
                                    continue
                                
                                instance = labels.get("instance", "")
                                ip = instance.split(":")[0] if ":" in instance else instance
                                
                                nodes_info["nodes"].append({
                                    "instance": instance,
                                    "ip": ip,
                                    "health": health,
                                    "last_error": target.get("lastError", "")
                                })
                
                except Exception as e:
                    nodes_info["error"] = f"Error querying Prometheus: {str(e)}"
                
                response_text = self.format_json_response(nodes_info)
                return [TextContent(type="text", text=response_text)]
            
            else:
                error_msg = self.create_error_response(
                    error="Unknown tool",
                    detail=f"Tool '{name}' is not supported"
                )
                return [TextContent(type="text", text=error_msg)]
        
        except Exception as e:
            error_msg = self.create_error_response(
                error="Internal error",
                detail=str(e)
            )
            logger.exception(f"工具调用异常: {name}")
            return [TextContent(type="text", text=error_msg)]


# 全局实例
simple_server = SimpleMCPServer()

# 导出与原模块兼容的接口
async def list_tools():
    return await simple_server.list_tools()

async def call_tool(name: str, arguments: dict):
    return await simple_server.call_tool(name, arguments)