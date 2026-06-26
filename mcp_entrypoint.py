"""MCP HTTP Server 入口 - 支持 Streamable HTTP 传输.

此模块实现基于 SSE (Server-Sent Events) 的 Streamable HTTP 传输，
使 MCP Server 可以被 StarAgent 等平台远程调用。
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import Response
from sse_starlette.sse import EventSourceResponse
import uvicorn

from app.mcp_server import server
from app.config.settings import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


class MCPHTTPServer:
    """MCP HTTP 服务器封装."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8001):
        self.host = host
        self.port = port
        self.app = self._create_app()
    
    def _create_app(self) -> FastAPI:
        """创建 FastAPI 应用."""
        
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """应用生命周期管理."""
            logger.info("=" * 60)
            logger.info("Prometheus MCP Server (HTTP 模式) 启动")
            logger.info("=" * 60)
            logger.info(f"监听地址: http://{self.host}:{self.port}")
            logger.info(f"Prometheus URL: {settings.prometheus_url}")
            logger.info(f"Node Exporter Port: {settings.node_exporter_port}")
            logger.info("=" * 60)
            
            yield
            
            logger.info("Prometheus MCP Server (HTTP 模式) 关闭")
        
        app = FastAPI(
            title="Prometheus MCP Server",
            description="Model Context Protocol Server for Prometheus Monitoring",
            version="1.0.0",
            lifespan=lifespan,
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        @app.get("/")
        async def root():
            """根路径."""
            return {
                "service": "prometheus-mcp-server",
                "version": "1.0.0",
                "protocol": "Model Context Protocol (MCP)",
                "transport": "Streamable HTTP (SSE)",
                "endpoints": {
                    "sse": "/sse",
                    "docs": "/docs",
                    "redoc": "/redoc"
                }
            }
        
        @app.get("/sse")
        async def sse_endpoint(request: Request):
            """
            SSE 端点 - Streamable HTTP 传输的入口.
            
            StarAgent 等 MCP 客户端将连接到此端点进行 JSON-RPC 通信。
            """
            logger.info("MCP Client 连接建立")
            
            async def event_generator():
                """SSE 事件生成器."""
                try:
                    # 创建 StreamReader/StreamWriter 用于 MCP Server
                    read_queue = asyncio.Queue()
                    write_queue = asyncio.Queue()
                    
                    # StreamReader 模拟
                    class AsyncStreamReader:
                        async def read(self, n: int = -1) -> bytes:
                            # 从 HTTP 请求流中读取数据
                            body = await request.body()
                            return body if n < 0 else body[:n]
                        
                        async def readline(self) -> bytes:
                            body = await request.body()
                            return b'\n' if not body else body.split(b'\n')[0] + b'\n'
                    
                    # StreamWriter 模拟
                    class AsyncStreamWriter:
                        def __init__(self, queue: asyncio.Queue):
                            self.queue = queue
                        
                        async def write(self, data: bytes):
                            await self.queue.put(data)
                        
                        async def drain(self):
                            pass
                        
                        def close(self):
                            pass
                    
                    reader = AsyncStreamReader()
                    writer = AsyncStreamWriter(write_queue)
                    
                    # 启动 MCP Server 协议处理
                    server_task = asyncio.create_task(
                        server.run(
                            reader,
                            writer,
                            server.create_initialization_options()
                        )
                    )
                    
                    # 发送初始化事件
                    yield {
                        "event": "connected",
                        "data": json.dumps({
                            "jsonrpc": "2.0",
                            "method": "notifications/initialized",
                            "params": {}
                        })
                    }
                    
                    # 持续发送响应
                    while True:
                        try:
                            # 等待 MCP Server 输出
                            output = await asyncio.wait_for(write_queue.get(), timeout=30.0)
                            
                            # 通过 SSE 发送
                            if output:
                                yield {
                                    "data": output.decode('utf-8')
                                }
                        
                        except asyncio.TimeoutError:
                            # 心跳保活
                            yield {"event": "keepalive", "data": ""}
                        
                        except asyncio.CancelledError:
                            logger.info("MCP Client 断开连接")
                            break
                        
                        except Exception as e:
                            logger.error(f"SSE 事件生成错误: {e}")
                            break
                    
                    # 清理
                    server_task.cancel()
                    try:
                        await server_task
                    except asyncio.CancelledError:
                        pass
                
                except Exception as e:
                    logger.exception(f"SSE 连接处理异常: {e}")
                    yield {
                        "event": "error",
                        "data": json.dumps({"error": str(e)})
                    }
            
            return EventSourceResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
        
        @app.get("/health")
        async def health_check():
            """健康检查."""
            import httpx
            
            health_info = {
                "service": "prometheus-mcp-server",
                "status": "healthy",
                "protocol": "MCP (HTTP/SSE)",
                "prometheus": "unknown",
                "timestamp": None
            }
            
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{settings.prometheus_url}/api/v1/status/config")
                    health_info["prometheus"] = "healthy" if response.status_code == 200 else "unhealthy"
            except Exception as e:
                health_info["prometheus"] = f"unreachable: {str(e)}"
            
            from datetime import datetime
            health_info["timestamp"] = datetime.now().isoformat()
            
            return health_info
        
        return app
    
    def run(self):
        """运行服务器."""
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )


def main():
    """主入口."""
    mcp_port = getattr(settings, 'mcp_port', 8001)
    mcp_host = getattr(settings, 'mcp_host', '0.0.0.0')
    
    server = MCPHTTPServer(host=mcp_host, port=mcp_port)
    server.run()


if __name__ == "__main__":
    import json
    main()