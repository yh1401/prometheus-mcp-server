"""测试文件."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from app.services.realtime_collector import RealtimeCollector
from app.services.trend_query_service import TrendQueryService
from app.models.schemas import RealtimeMetricsResponse, TrendMetricsResponse


class TestRealtimeCollector:
    """实时采集器测试"""
    
    @pytest.fixture
    def collector(self):
        return RealtimeCollector(prometheus_url="http://localhost:9090")
    
    @pytest.mark.asyncio
    async def test_collect_returns_valid_response(self, collector):
        """测试采集返回有效响应"""
        # Mock Prometheus 查询
        with patch.object(collector, '_query_prometheus', new_callable=AsyncMock) as mock_query:
            # 设置 mock 返回值
            mock_query.side_effect = [
                25.5,  # CPU usage
                4,     # CPU cores
                10.0,  # CPU user
                5.0,   # CPU system
                2.0,   # CPU iowait
                8589934592,  # Memory total (8GB)
                4294967296,  # Memory available (4GB)
                4294967296,  # Memory used (4GB)
                2147483648,  # Memory cached
                1073741824,  # Memory buffered
                1024.0,  # Disk read bytes
                512.0,   # Disk write bytes
                10.0,    # Disk read IOPS
                5.0,     # Disk write IOPS
                15.0,    # Disk utilization
                2.5,     # Load 1m
                3.0,     # Load 5m
                3.5,     # Load 15m
                4,       # CPU cores for load calc
                100,     # TCP connections
                50,      # TCP active
                0,       # TCP overflow
                0,       # TCP drops
                10       # TCP retransmits
            ]
            
            result = await collector.collect("node-01", "192.168.1.10")
            
            assert isinstance(result, RealtimeMetricsResponse)
            assert result.node == "node-01"
            assert result.ip == "192.168.1.10"
            assert result.cpu.usage_percent == 25.5
            assert result.cpu.cores == 4
            assert result.memory.total_bytes == 8589934592
    
    @pytest.mark.asyncio
    async def test_query_prometheus_handles_error(self, collector):
        """测试 Prometheus 查询错误处理"""
        with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Connection error")
            
            result = await collector._query_prometheus("test_query")
            assert result is None


class TestTrendQueryService:
    """趋势查询服务测试"""
    
    @pytest.fixture
    def service(self):
        return TrendQueryService(prometheus_url="http://localhost:9090")
    
    @pytest.mark.asyncio
    async def test_query_trend_returns_valid_response(self, service):
        """测试趋势查询返回有效响应"""
        # Mock 范围查询
        mock_result = {
            "values": [
                [1782361200, "25.5"],
                [1782361260, "26.0"],
                [1782361320, "27.5"]
            ]
        }
        
        with patch.object(service, '_query_range', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [
                {"timestamp": "2026-06-25T12:00:00", "value": 25.5},
                {"timestamp": "2026-06-25T12:01:00", "value": 26.0},
                {"timestamp": "2026-06-25T12:02:00", "value": 27.5}
            ]
            
            result = await service.query_trend(
                "node-01", "192.168.1.10",
                "2026-06-25T00:00:00Z", "2026-06-25T23:59:59Z", "1m"
            )
            
            assert isinstance(result, TrendMetricsResponse)
            assert result.node == "node-01"
            assert result.ip == "192.168.1.10"
    
    def test_parse_time(self, service):
        """测试时间解析"""
        result = service._parse_time("2026-06-25T12:00:00Z")
        assert isinstance(result, int)
        assert result > 0
    
    def test_get_instance_label(self, service):
        """测试 instance 标签构建"""
        result = service._get_instance_label("192.168.1.10")
        assert result == "192.168.1.10:9100"
    
    def test_build_tcp_query(self, service):
        """测试 TCP 连接数查询语句构建"""
        instance = "192.168.1.10:9100"
        query = service._build_tcp_query(instance)
        assert "Tcp_CurrEstab" in query
        assert instance in query
    
    def test_build_tcp_overflow_query(self, service):
        """测试 TCP 溢出查询语句构建"""
        instance = "192.168.1.10:9100"
        query = service._build_tcp_overflow_query(instance)
        assert "Tcp_ListenOverflows" in query
        assert instance in query


class TestAPIRoutes:
    """API 路由测试"""
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """测试健康检查"""
        from app.api.routes import health_check
        
        with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            result = await health_check()
            
            assert result["status"] == "healthy"
            assert "prometheus" in result
            assert "timestamp" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])