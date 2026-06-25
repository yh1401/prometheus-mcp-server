"""FastAPI 主入口."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.api.routes import router as metrics_router
from app.config.settings import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("=" * 60)
    logger.info("Prometheus MCP Server Extended 启动")
    logger.info("=" * 60)
    logger.info(f"Prometheus URL: {settings.prometheus_url}")
    logger.info(f"Node Exporter Port: {settings.node_exporter_port}")
    logger.info(f"API Port: {settings.api_port}")
    logger.info("=" * 60)
    
    yield
    
    logger.info("Prometheus MCP Server Extended 关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="Prometheus MCP Server Extended",
    description="""
    基于 Prometheus 的节点性能指标查询服务
    
    ## 功能
    
    - **实时指标查询**: 传入节点名/IP，返回当前 CPU、内存、IO、负载、TCP 等实时指标
    - **趋势数据查询**: 传入节点名/IP + 时间范围，返回历史趋势数据
    
    ## 使用说明
    
    1. 确保目标节点已部署 Node Exporter（默认端口 9100）
    2. 确保 Prometheus 已配置采集 Node Exporter 数据
    3. 使用节点 IP 地址进行查询
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(metrics_router)


@app.get("/", tags=["Root"])
async def root():
    """根路径"""
    return {
        "service": "Prometheus MCP Server Extended",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/metrics/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info"
    )