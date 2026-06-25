# Prometheus MCP Server Extended

基于 Prometheus 的节点性能指标查询服务，支持实时指标采集和历史趋势查询。

## 功能特性

- **实时指标查询**: 传入节点名/IP，返回当前 CPU、内存、IO、负载、TCP 等实时指标
- **趋势数据查询**: 传入节点名/IP + 时间范围，返回历史趋势数据
- **多指标支持**: CPU、内存、磁盘 IO、系统负载、TCP 连接等
- **RESTful API**: 标准 REST 接口，支持 JSON 格式响应
- **Swagger 文档**: 自动生成 API 文档

## 快速开始

### 1. 安装依赖

```bash
cd prometheus-mcp-server
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 创建 .env 文件
cat > .env << EOF
PROMETHEUS_URL=http://localhost:9090
NODE_EXPORTER_PORT=9100
API_PORT=8000
EOF
```

### 3. 启动服务

```bash
# 开发模式
python -m app.main

# 或使用 uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 访问 API 文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API 接口

### 实时指标查询

```bash
GET /api/v1/metrics/realtime?node=node-01&ip=192.168.1.10
```

响应示例：
```json
{
  "node": "node-01",
  "ip": "192.168.1.10",
  "timestamp": "2026-06-25T12:00:00",
  "cpu": {
    "usage_percent": 25.5,
    "cores": 4,
    "user_percent": 10.0,
    "system_percent": 5.0,
    "iowait_percent": 2.0
  },
  "memory": {
    "total_bytes": 8589934592,
    "used_bytes": 4294967296,
    "available_bytes": 4294967296,
    "usage_percent": 50.0
  },
  "disk_io": {
    "read_bytes_per_sec": 1024.0,
    "write_bytes_per_sec": 512.0,
    "read_iops": 10.0,
    "write_iops": 5.0
  },
  "load": {
    "load_1m": 2.5,
    "load_5m": 3.0,
    "load_15m": 3.5
  },
  "tcp": {
    "connections_established": 100,
    "listen_overflows": 0
  }
}
```

### 趋势数据查询

```bash
GET /api/v1/metrics/trend?node=node-01&ip=192.168.1.10&start_time=2026-06-25T00:00:00Z&end_time=2026-06-25T23:59:59Z&step=5m
```

响应示例：
```json
{
  "node": "node-01",
  "ip": "192.168.1.10",
  "time_range": {
    "start": "2026-06-25T00:00:00Z",
    "end": "2026-06-25T23:59:59Z",
    "step": "5m"
  },
  "cpu_trend": [
    {"timestamp": "2026-06-25T00:00:00", "value": 25.5},
    {"timestamp": "2026-06-25T00:05:00", "value": 26.0}
  ],
  "memory_trend": [...],
  "disk_io_trend": [...],
  "load_trend": [...],
  "tcp_trend": [...]
}
```

## Docker 部署

```bash
# 构建镜像
docker build -t prometheus-mcp-server:latest .

# 运行容器
docker run -d \
  --name prometheus-mcp-server \
  -p 8000:8000 \
  -e PROMETHEUS_URL=http://prometheus:9090 \
  prometheus-mcp-server:latest

# 或使用 docker-compose
docker-compose up -d
```

## Kubernetes 部署

```bash
# 应用配置
kubectl apply -f kubernetes/deployment.yaml

# 检查状态
kubectl get pods -l app=prometheus-mcp-server
kubectl get services
```

## 前置条件

1. **Prometheus**: 需要运行 Prometheus 服务（默认端口 9090）
2. **Node Exporter**: 目标节点需要部署 Node Exporter（默认端口 9100）

### Node Exporter 安装

```bash
# Docker 方式
docker run -d \
  --name node-exporter \
  -p 9100:9100 \
  -v /proc:/host/proc:ro \
  -v /sys:/host/sys:ro \
  prom/node-exporter \
  --path.procfs=/host/proc \
  --path.sysfs=/host/sys

# 或直接安装
wget https://github.com/prometheus/node_exporter/releases/download/v1.6.0/node_exporter-1.6.0.linux-amd64.tar.gz
tar xzf node_exporter-*.tar.gz
./node_exporter
```

## 配置说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `PROMETHEUS_URL` | `http://localhost:9090` | Prometheus 服务地址 |
| `NODE_EXPORTER_PORT` | `9100` | Node Exporter 端口 |
| `API_PORT` | `8000` | API 服务端口 |
| `DEFAULT_STEP` | `1m` | 默认采样间隔 |
| `REALTIME_CACHE_TTL` | `30` | 实时数据缓存时间（秒） |

## 测试

```bash
# 运行测试
pytest tests/ -v

# 或使用 unittest
python -m pytest tests/test_services.py -v
```

## 项目结构

```
prometheus-mcp-server/
├── app/
│   ├── api/
│   │   └── routes.py          # API 路由
│   ├── services/
│   │   ├── realtime_collector.py    # 实时采集服务
│   │   └── trend_query_service.py   # 趋势查询服务
│   ├── models/
│   │   └── schemas.py         # 数据模型
│   ├── config/
│   │   └── settings.py        # 配置管理
│   └── main.py                # FastAPI 入口
├── tests/
│   └── test_services.py       # 测试文件
├── kubernetes/
│   └── deployment.yaml        # Kubernetes 配置
├── Dockerfile                 # Docker 镜像配置
├── docker-compose.yml         # Docker Compose 配置
├── prometheus.yml             # Prometheus 配置
├── requirements.txt           # Python 依赖
└── README.md                  # 项目说明
```

## 许可证

MIT License