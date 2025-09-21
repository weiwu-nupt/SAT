import asyncio
import socket
import threading
import queue
import configparser
import logging
import json
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any


class MessageSource(Enum):
    """消息来源枚举"""
    HOST_SOFTWARE = "host_software"
    GATEWAY = "gateway"
    LORA = "lora"


@dataclass
class UDPMessage:
    """UDP消息数据类"""
    source: MessageSource
    data: bytes
    addr: tuple
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'source': self.source.value,
            'data': self.data.decode('utf-8', errors='ignore'),
            'addr': self.addr,
            'timestamp': self.timestamp.isoformat()
        }


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: str = 'config.ini'):
        self.config = configparser.ConfigParser()
        self.config_file = config_file
        self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        try:
            self.config.read(self.config_file, encoding='utf-8')
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            # 使用默认配置
            self._create_default_config()
    
    def _create_default_config(self):
        """创建默认配置"""
        self.config['UDP_PORTS'] = {
            'host_software_port': '8001',
            'gateway_port': '8002',
            'lora_port': '8003'
        }
        self.config['NETWORK'] = {
            'bind_ip': '0.0.0.0'
        }
        self.config['LOGGING'] = {
            'log_level': 'INFO',
            'log_file': 'backend.log'
        }
    
    def get_port(self, port_name: str) -> int:
        """获取端口号"""
        return self.config.getint('UDP_PORTS', port_name)
    
    def get_bind_ip(self) -> str:
        """获取绑定IP"""
        return self.config.get('NETWORK', 'bind_ip')


class UDPServer:
    """UDP服务器类"""
    
    def __init__(self, port: int, source: MessageSource, message_queue: queue.Queue, bind_ip: str = '0.0.0.0'):
        self.port = port
        self.source = source
        self.message_queue = message_queue
        self.bind_ip = bind_ip
        self.socket = None
        self.running = False
        self.thread = None
        
    def start(self):
        """启动UDP服务器"""
        if self.running:
            return
            
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.bind_ip, self.port))
            self.socket.settimeout(1.0)  # 设置超时，便于优雅关闭
            
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            
            logging.info(f"{self.source.value} UDP服务器启动在端口 {self.port}")
            
        except Exception as e:
            logging.error(f"启动 {self.source.value} UDP服务器失败: {e}")
            raise
    
    def stop(self):
        """停止UDP服务器"""
        self.running = False
        if self.socket:
            self.socket.close()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        logging.info(f"{self.source.value} UDP服务器已停止")
    
    def _run(self):
        """UDP服务器主循环"""
        while self.running:
            try:
                data, addr = self.socket.recvfrom(4096)
                if data:
                    message = UDPMessage(
                        source=self.source,
                        data=data,
                        addr=addr,
                        timestamp=datetime.now()
                    )
                    
                    # 将消息放入队列
                    try:
                        self.message_queue.put(message, timeout=0.1)
                        logging.debug(f"收到来自 {self.source.value} 的消息: {len(data)} bytes from {addr}")
                    except queue.Full:
                        logging.warning(f"消息队列已满，丢弃来自 {self.source.value} 的消息")
                        
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logging.error(f"{self.source.value} UDP服务器错误: {e}")


class MessageProcessor:
    """消息处理器"""
    
    def __init__(self, message_queue: queue.Queue):
        self.message_queue = message_queue
        self.running = False
        self.thread = None
        
    def start(self):
        """启动消息处理器"""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._process_messages, daemon=True)
        self.thread.start()
        logging.info("消息处理器已启动")
    
    def stop(self):
        """停止消息处理器"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        logging.info("消息处理器已停止")
    
    def _process_messages(self):
        """消息处理主循环"""
        while self.running:
            try:
                message = self.message_queue.get(timeout=1)
                self._handle_message(message)
                self.message_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"处理消息时出错: {e}")
    
    def _handle_message(self, message: UDPMessage):
        """处理单个消息"""
        try:
            # 根据消息来源进行不同的处理
            if message.source == MessageSource.HOST_SOFTWARE:
                self._handle_host_software_message(message)
            elif message.source == MessageSource.GATEWAY:
                self._handle_gateway_message(message)
            elif message.source == MessageSource.LORA:
                self._handle_lora_message(message)
            else:
                logging.warning(f"未知消息来源: {message.source}")
                
        except Exception as e:
            logging.error(f"处理 {message.source.value} 消息失败: {e}")
    
    def _handle_host_software_message(self, message: UDPMessage):
        """处理上位机软件消息"""
        logging.info(f"处理上位机消息: {len(message.data)} bytes from {message.addr}")
        # TODO: 实现具体的上位机消息处理逻辑
        
    def _handle_gateway_message(self, message: UDPMessage):
        """处理网关消息"""
        logging.info(f"处理网关消息: {len(message.data)} bytes from {message.addr}")
        # TODO: 实现具体的网关消息处理逻辑
        
    def _handle_lora_message(self, message: UDPMessage):
        """处理LoRa消息"""
        logging.info(f"处理LoRa消息: {len(message.data)} bytes from {message.addr}")
        # TODO: 实现具体的LoRa消息处理逻辑


class BackendServer:
    """后台服务器主类"""
    
    def __init__(self, config_file: str = 'config.ini'):
        self.config_manager = ConfigManager(config_file)
        self.message_queue = queue.Queue(maxsize=1000)  # 设置队列最大大小
        self.servers = {}
        self.message_processor = MessageProcessor(self.message_queue)
        
        # 设置日志
        self._setup_logging()
        
    def _setup_logging(self):
        """设置日志"""
        log_level = getattr(logging, self.config_manager.config.get('LOGGING', 'log_level', fallback='INFO'))
        log_file = self.config_manager.config.get('LOGGING', 'log_file', fallback='backend.log')
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
    
    def start(self):
        """启动后台服务器"""
        try:
            bind_ip = self.config_manager.get_bind_ip()
            
            # 创建并启动UDP服务器
            server_configs = [
                ('host_software_port', MessageSource.HOST_SOFTWARE),
                ('gateway_port', MessageSource.GATEWAY),
                ('lora_port', MessageSource.LORA)
            ]
            
            for port_name, source in server_configs:
                port = self.config_manager.get_port(port_name)
                server = UDPServer(port, source, self.message_queue, bind_ip)
                server.start()
                self.servers[source] = server
            
            # 启动消息处理器
            self.message_processor.start()
            
            logging.info("后台服务器启动成功")
            
        except Exception as e:
            logging.error(f"启动后台服务器失败: {e}")
            self.stop()
            raise
    
    def stop(self):
        """停止后台服务器"""
        logging.info("正在停止后台服务器...")
        
        # 停止所有UDP服务器
        for server in self.servers.values():
            server.stop()
        
        # 停止消息处理器
        self.message_processor.stop()
        
        logging.info("后台服务器已停止")
    
    def get_queue_size(self) -> int:
        """获取当前队列大小"""
        return self.message_queue.qsize()


def main():
    """主函数"""
    server = None
    try:
        server = BackendServer()
        server.start()
        
        # 主循环
        while True:
            try:
                # 这里可以添加一些监控逻辑
                queue_size = server.get_queue_size()
                if queue_size > 0:
                    logging.debug(f"当前队列大小: {queue_size}")
                
                # 每秒检查一次
                threading.Event().wait(1)
                
            except KeyboardInterrupt:
                logging.info("收到停止信号")
                break
                
    except Exception as e:
        logging.error(f"程序运行出错: {e}")
    finally:
        if server:
            server.stop()


if __name__ == "__main__":
    main()