"""综合测试执行脚本.

执行所有测试并生成详细测试报告。
"""

import subprocess
import sys
import json
from datetime import datetime
from pathlib import Path


def run_tests():
    """运行所有测试."""
    print("=" * 80)
    print("开始执行 MCP Server 综合测试")
    print("=" * 80)
    
    test_results = {
        "timestamp": datetime.now().isoformat(),
        "tests": {}
    }
    
    # 测试套件列表
    test_suites = [
        ("单元测试", "tests/test_mcp_server.py"),
        ("集成测试", "tests/test_integration.py"),
        ("服务测试", "tests/test_services.py"),
        ("Mock测试", "tests/test_mock.py")
    ]
    
    for suite_name, test_file in test_suites:
        print(f"\n{'=' * 80}")
        print(f"运行测试套件: {suite_name}")
        print(f"测试文件: {test_file}")
        print(f"{'=' * 80}\n")
        
        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short"],
            capture_output=True,
            text=True
        )
        
        # 解析测试结果
        output = result.stdout + result.stderr
        
        # 统计测试数量
        passed = output.count("PASSED")
        failed = output.count("FAILED")
        errors = output.count("ERROR")
        skipped = output.count("SKIPPED")
        
        test_results["tests"][suite_name] = {
            "file": test_file,
            "exit_code": result.returncode,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "skipped": skipped,
            "output": output
        }
        
        print(f"\n{suite_name} 测试完成:")
        print(f"  通过: {passed}")
        print(f"  失败: {failed}")
        print(f"  错误: {errors}")
        print(f"  跳过: {skipped}")
        print(f"  退出码: {result.returncode}")
    
    # 汇总结果
    print(f"\n{'=' * 80}")
    print("测试汇总")
    print(f"{'=' * 80}\n")
    
    total_passed = sum(s["passed"] for s in test_results["tests"].values())
    total_failed = sum(s["failed"] for s in test_results["tests"].values())
    total_errors = sum(s["errors"] for s in test_results["tests"].values())
    total_skipped = sum(s["skipped"] for s in test_results["tests"].values())
    total_tests = total_passed + total_failed + total_errors
    
    print(f"总测试数: {total_tests}")
    print(f"  通过: {total_passed}")
    print(f"  失败: {total_failed}")
    print(f"  错误: {total_errors}")
    print(f"  跳过: {total_skipped}")
    
    success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
    print(f"  通过率: {success_rate:.2f}%")
    
    test_results["summary"] = {
        "total": total_tests,
        "passed": total_passed,
        "failed": total_failed,
        "errors": total_errors,
        "skipped": total_skipped,
        "success_rate": success_rate
    }
    
    # 生成测试报告
    report_path = Path("test_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(test_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n测试报告已保存: {report_path.absolute()}")
    
    # 生成人类可读的报告
    human_report_path = Path("test_report.txt")
    with open(human_report_path, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("Prometheus MCP Server - 综合测试报告\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"测试时间: {test_results['timestamp']}\n")
        f.write(f"项目: Prometheus MCP Server (方案一实现)\n")
        f.write(f"版本: 1.0.0\n\n")
        
        f.write("=" * 80 + "\n")
        f.write("测试汇总\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"总测试数: {total_tests}\n")
        f.write(f"  通过: {total_passed}\n")
        f.write(f"  失败: {total_failed}\n")
        f.write(f"  错误: {total_errors}\n")
        f.write(f"  跳过: {total_skipped}\n")
        f.write(f"  通过率: {success_rate:.2f}%\n\n")
        
        for suite_name, result in test_results["tests"].items():
            f.write("=" * 80 + "\n")
            f.write(f"{suite_name}\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"文件: {result['file']}\n")
            f.write(f"通过: {result['passed']}\n")
            f.write(f"失败: {result['failed']}\n")
            f.write(f"错误: {result['errors']}\n")
            f.write(f"跳过: {result['skipped']}\n")
            f.write(f"退出码: {result['exit_code']}\n\n")
            
            if result['output']:
                f.write("测试输出:\n")
                f.write("-" * 80 + "\n")
                f.write(result['output'][:2000])  # 限制长度
                if len(result['output']) > 2000:
                    f.write("\n... (输出已截断)")
                f.write("\n\n")
        
        f.write("=" * 80 + "\n")
        f.write("测试结论\n")
        f.write("=" * 80 + "\n\n")
        
        if total_failed == 0 and total_errors == 0:
            f.write("✅ 所有测试通过，系统符合预期。\n\n")
        else:
            f.write("⚠️  存在测试失败或错误，需要修复。\n\n")
        
        f.write("=" * 80 + "\n")
    
    print(f"人类可读报告已保存: {human_report_path.absolute()}")
    
    # 显示测试结论
    print(f"\n{'=' * 80}")
    print("测试结论")
    print(f"{'=' * 80}\n")
    
    if total_failed == 0 and total_errors == 0:
        print("✅ 所有测试通过，系统符合预期。")
        return True
    else:
        print("⚠️  存在测试失败或错误，需要修复。")
        return False


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)