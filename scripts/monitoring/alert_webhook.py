#!/usr/bin/env python3
"""
alert_webhook.py - 告警 Webhook 处理器

用于接收和转发 AlgoStudio 集群告警到外部系统 (如 Slack, 飞书, 企业微信等)

用法:
    # 启动 Webhook 服务 (默认端口 8080)
    python alert_webhook.py

    # 指定端口和配置
    python alert_webhook.py --port 9000 --config alert_config.yaml

    # 测试模式 (发送测试告警)
    python alert_webhook.py --test

Webhook 请求格式:
    POST /alert
    Content-Type: application/json
    {
        "severity": "critical|warning|info",
        "message": "告警消息",
        "cluster": "集群名称",
        "timestamp": "ISO 时间戳",
        "details": {}  // 可选详细信息
    }
"""

import argparse
import json
import logging
import os
import sys
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/home/admin02/Code/Dev/AlgoStudio/logs/alerts.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# 全局配置
CONFIG = {
    "webhook_url": "",
    "slack_webhook": "",
    "feishu_webhook": "",
    "dingtalk_webhook": "",
    "forward_enabled": True
}


def load_config(config_path: str):
    """从 YAML 文件加载配置"""
    try:
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        # 提取 webhook 配置
        webhook_conf = config.get('webhook', {})
        CONFIG['webhook_url'] = webhook_conf.get('url', '')
        CONFIG['forward_enabled'] = webhook_conf.get('enabled', True)

        # 提取接收者配置
        receivers = config.get('receivers', [])
        for r in receivers:
            if r.get('type') == 'webhook':
                # 可以配置多个 webhook
                pass

        logger.info(f"配置加载成功: {config_path}")
    except Exception as e:
        logger.warning(f"配置加载失败: {e}, 使用默认配置")


def format_slack_message(alert: dict) -> dict:
    """格式化 Slack 消息"""
    severity = alert.get('severity', 'info')
    color = {
        'critical': '#FF0000',  # 红色
        'warning': '#FFA500',   # 橙色
        'info': '#00FF00'       # 绿色
    }.get(severity, '#00FF00')

    return {
        "attachments": [{
            "color": color,
            "title": f"AlgoStudio 告警: {severity.upper()}",
            "text": alert.get('message', '无消息'),
            "fields": [
                {"title": "集群", "value": alert.get('cluster', 'Unknown'), "short": True},
                {"title": "时间", "value": alert.get('timestamp', ''), "short": True}
            ],
            "footer": "AlgoStudio Alert System"
        }]
    }


def format_feishu_message(alert: dict) -> dict:
    """格式化飞书消息"""
    severity = alert.get('severity', 'info')
    emoji = {
        'critical': '🔴',
        'warning': '🟡',
        'info': '🟢'
    }.get(severity, '⚪')

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"{emoji} AlgoStudio 告警"},
                "template": "red" if severity == 'critical' else "yellow"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**级别:** {severity.upper()}\n**消息:** {alert.get('message', 'N/A')}\n**集群:** {alert.get('cluster', 'Unknown')}\n**时间:** {alert.get('timestamp', '')}"
                    }
                }
            ]
        }
    }


def format_dingtalk_message(alert: dict) -> dict:
    """格式化钉钉消息"""
    severity = alert.get('severity', 'info')

    return {
        "msgtype": "markdown",
        "markdown": {
            "title": f"AlgoStudio 告警: {severity}",
            "text": f"## AlgoStudio 告警\n\n" \
                   f"**级别:** {severity.upper()}\n\n" \
                   f"**消息:** {alert.get('message', 'N/A')}\n\n" \
                   f"**集群:** {alert.get('cluster', 'Unknown')}\n\n" \
                   f"**时间:** {alert.get('timestamp', '')}"
        }
    }


def forward_alert(alert: dict):
    """转发告警到配置的 Webhook"""
    if not CONFIG['forward_enabled']:
        return

    # Slack
    if CONFIG.get('slack_webhook'):
        try:
            data = json.dumps(format_slack_message(alert)).encode('utf-8')
            req = Request(CONFIG['slack_webhook'], data=data, headers={'Content-Type': 'application/json'})
            urlopen(req, timeout=10)
            logger.info(f"Slack 告警发送成功: {alert.get('message', '')[:50]}")
        except Exception as e:
            logger.error(f"Slack 告警发送失败: {e}")

    # 飞书
    if CONFIG.get('feishu_webhook'):
        try:
            data = json.dumps(format_feishu_message(alert)).encode('utf-8')
            req = Request(CONFIG['feishu_webhook'], data=data, headers={'Content-Type': 'application/json'})
            urlopen(req, timeout=10)
            logger.info(f"飞书告警发送成功: {alert.get('message', '')[:50]}")
        except Exception as e:
            logger.error(f"飞书告警发送失败: {e}")

    # 钉钉
    if CONFIG.get('dingtalk_webhook'):
        try:
            data = json.dumps(format_dingtalk_message(alert)).encode('utf-8')
            req = Request(CONFIG['dingtalk_webhook'], data=data, headers={'Content-Type': 'application/json'})
            urlopen(req, timeout=10)
            logger.info(f"钉钉告警发送成功: {alert.get('message', '')[:50]}")
        except Exception as e:
            logger.error(f"钉钉告警发送失败: {e}")

    # 通用 Webhook
    if CONFIG.get('webhook_url'):
        try:
            data = json.dumps(alert).encode('utf-8')
            req = Request(CONFIG['webhook_url'], data=data, headers={'Content-Type': 'application/json'})
            urlopen(req, timeout=10)
            logger.info(f"通用 Webhook 告警发送成功: {alert.get('message', '')[:50]}")
        except Exception as e:
            logger.error(f"通用 Webhook 告警发送失败: {e}")


class AlertHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""

    def log_message(self, format, *args):
        """自定义日志格式"""
        logger.info(f"{self.address_string()} - {format % args}")

    def do_GET(self):
        """处理 GET 请求"""
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
        elif self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body><h1>AlgoStudio Alert Webhook</h1></body></html>')
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        """处理 POST /alert 请求"""
        if self.path != '/alert':
            self.send_response(404)
            self.end_headers()
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            alert = json.loads(body)

            # 验证必填字段
            if 'message' not in alert:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"error": "missing message field"}')
                return

            # 设置默认值
            alert.setdefault('cluster', 'AlgoStudio')
            alert.setdefault('timestamp', datetime.now().isoformat())
            alert.setdefault('severity', 'info')

            # 记录告警
            logger.warning(f"收到告警: [{alert['severity']}] {alert['message']}")

            # 转发告警 (异步)
            thread = threading.Thread(target=forward_alert, args=(alert,))
            thread.start()

            # 响应
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "received"}')

        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(f'{{"error": "invalid json: {e}"}}'.encode())
        except Exception as e:
            logger.error(f"处理告警失败: {e}")
            self.send_response(500)
            self.end_headers()


def send_test_alert():
    """发送测试告警"""
    test_alert = {
        "severity": "warning",
        "message": "这是一条测试告警",
        "cluster": "AlgoStudio-Test",
        "timestamp": datetime.now().isoformat(),
        "details": {
            "test": True,
            "node": "test-node"
        }
    }

    logger.info("发送测试告警...")
    forward_alert(test_alert)
    print("测试告警已发送，请检查配置的 Webhook")


def main():
    parser = argparse.ArgumentParser(description='AlgoStudio Alert Webhook Server')
    parser.add_argument('--port', type=int, default=8080, help='监听端口 (默认: 8080)')
    parser.add_argument('--config', type=str, default='alert_config.yaml', help='配置文件路径')
    parser.add_argument('--test', action='store_true', help='发送测试告警并退出')
    args = parser.parse_args()

    # 加载配置
    config_path = os.path.join(os.path.dirname(__file__), args.config)
    if os.path.exists(config_path):
        load_config(config_path)
    else:
        logger.warning(f"配置文件不存在: {config_path}, 使用默认配置")

    # 测试模式
    if args.test:
        send_test_alert()
        return

    # 确保日志目录存在
    os.makedirs('/home/admin02/Code/Dev/AlgoStudio/logs', exist_ok=True)

    # 启动服务器
    server = HTTPServer(('0.0.0.0', args.port), AlertHandler)
    logger.info(f"告警 Webhook 服务已启动: http://0.0.0.0:{args.port}")
    logger.info(f"告警接收地址: http://0.0.0.0:{args.port}/alert")
    logger.info("按 Ctrl+C 停止服务")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("服务已停止")
        server.shutdown()


if __name__ == '__main__':
    main()
