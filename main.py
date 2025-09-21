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
    """��Ϣ��Դö��"""
    HOST_SOFTWARE = "host_software"
    GATEWAY = "gateway"
    LORA = "lora"


@dataclass
class UDPMessage:
    """UDP��Ϣ������"""
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
    """���ù�����"""
    
    def __init__(self, config_file: str = 'config.ini'):
        self.config = configparser.ConfigParser()
        self.config_file = config_file
        self.load_config()
    
    def load_config(self):
        """���������ļ�"""
        try:
            self.config.read(self.config_file, encoding='utf-8')
        except Exception as e:
            logging.error(f"���������ļ�ʧ��: {e}")
            # ʹ��Ĭ������
            self._create_default_config()
    
    def _create_default_config(self):
        """����Ĭ������"""
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
        """��ȡ�˿ں�"""
        return self.config.getint('UDP_PORTS', port_name)
    
    def get_bind_ip(self) -> str:
        """��ȡ��IP"""
        return self.config.get('NETWORK', 'bind_ip')


class UDPServer:
    """UDP��������"""
    
    def __init__(self, port: int, source: MessageSource, message_queue: queue.Queue, bind_ip: str = '0.0.0.0'):
        self.port = port
        self.source = source
        self.message_queue = message_queue
        self.bind_ip = bind_ip
        self.socket = None
        self.running = False
        self.thread = None
        
    def start(self):
        """����UDP������"""
        if self.running:
            return
            
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.bind_ip, self.port))
            self.socket.settimeout(1.0)  # ���ó�ʱ���������Źر�
            
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            
            logging.info(f"{self.source.value} UDP�����������ڶ˿� {self.port}")
            
        except Exception as e:
            logging.error(f"���� {self.source.value} UDP������ʧ��: {e}")
            raise
    
    def stop(self):
        """ֹͣUDP������"""
        self.running = False
        if self.socket:
            self.socket.close()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        logging.info(f"{self.source.value} UDP��������ֹͣ")
    
    def _run(self):
        """UDP��������ѭ��"""
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
                    
                    # ����Ϣ�������
                    try:
                        self.message_queue.put(message, timeout=0.1)
                        logging.debug(f"�յ����� {self.source.value} ����Ϣ: {len(data)} bytes from {addr}")
                    except queue.Full:
                        logging.warning(f"��Ϣ������������������ {self.source.value} ����Ϣ")
                        
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logging.error(f"{self.source.value} UDP����������: {e}")


class MessageProcessor:
    """��Ϣ������"""
    
    def __init__(self, message_queue: queue.Queue):
        self.message_queue = message_queue
        self.running = False
        self.thread = None
        
    def start(self):
        """������Ϣ������"""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._process_messages, daemon=True)
        self.thread.start()
        logging.info("��Ϣ������������")
    
    def stop(self):
        """ֹͣ��Ϣ������"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        logging.info("��Ϣ��������ֹͣ")
    
    def _process_messages(self):
        """��Ϣ������ѭ��"""
        while self.running:
            try:
                message = self.message_queue.get(timeout=1)
                self._handle_message(message)
                self.message_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logging.error(f"������Ϣʱ����: {e}")
    
    def _handle_message(self, message: UDPMessage):
        """��������Ϣ"""
        try:
            # ������Ϣ��Դ���в�ͬ�Ĵ���
            if message.source == MessageSource.HOST_SOFTWARE:
                self._handle_host_software_message(message)
            elif message.source == MessageSource.GATEWAY:
                self._handle_gateway_message(message)
            elif message.source == MessageSource.LORA:
                self._handle_lora_message(message)
            else:
                logging.warning(f"δ֪��Ϣ��Դ: {message.source}")
                
        except Exception as e:
            logging.error(f"���� {message.source.value} ��Ϣʧ��: {e}")
    
    def _handle_host_software_message(self, message: UDPMessage):
        """������λ�������Ϣ"""
        logging.info(f"������λ����Ϣ: {len(message.data)} bytes from {message.addr}")
        # TODO: ʵ�־������λ����Ϣ�����߼�
        
    def _handle_gateway_message(self, message: UDPMessage):
        """����������Ϣ"""
        logging.info(f"����������Ϣ: {len(message.data)} bytes from {message.addr}")
        # TODO: ʵ�־����������Ϣ�����߼�
        
    def _handle_lora_message(self, message: UDPMessage):
        """����LoRa��Ϣ"""
        logging.info(f"����LoRa��Ϣ: {len(message.data)} bytes from {message.addr}")
        # TODO: ʵ�־����LoRa��Ϣ�����߼�


class BackendServer:
    """��̨����������"""
    
    def __init__(self, config_file: str = 'config.ini'):
        self.config_manager = ConfigManager(config_file)
        self.message_queue = queue.Queue(maxsize=1000)  # ���ö�������С
        self.servers = {}
        self.message_processor = MessageProcessor(self.message_queue)
        
        # ������־
        self._setup_logging()
        
    def _setup_logging(self):
        """������־"""
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
        """������̨������"""
        try:
            bind_ip = self.config_manager.get_bind_ip()
            
            # ����������UDP������
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
            
            # ������Ϣ������
            self.message_processor.start()
            
            logging.info("��̨�����������ɹ�")
            
        except Exception as e:
            logging.error(f"������̨������ʧ��: {e}")
            self.stop()
            raise
    
    def stop(self):
        """ֹͣ��̨������"""
        logging.info("����ֹͣ��̨������...")
        
        # ֹͣ����UDP������
        for server in self.servers.values():
            server.stop()
        
        # ֹͣ��Ϣ������
        self.message_processor.stop()
        
        logging.info("��̨��������ֹͣ")
    
    def get_queue_size(self) -> int:
        """��ȡ��ǰ���д�С"""
        return self.message_queue.qsize()


def main():
    """������"""
    server = None
    try:
        server = BackendServer()
        server.start()
        
        # ��ѭ��
        while True:
            try:
                # ����������һЩ����߼�
                queue_size = server.get_queue_size()
                if queue_size > 0:
                    logging.debug(f"��ǰ���д�С: {queue_size}")
                
                # ÿ����һ��
                threading.Event().wait(1)
                
            except KeyboardInterrupt:
                logging.info("�յ�ֹͣ�ź�")
                break
                
    except Exception as e:
        logging.error(f"�������г���: {e}")
    finally:
        if server:
            server.stop()


if __name__ == "__main__":
    main()