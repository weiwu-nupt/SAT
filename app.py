#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import struct
import threading
import queue
import time
from typing import NamedTuple, Optional, Tuple
from enum import Enum
import logging

# ��������ģ��
from config import (
    load_config_from_file, 
    sys_para, 
    node_para, 
    local_id,
    network_config, 
    udp_config, 
    system_config, 
    debug_config
)

# ������־
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MessageSource(Enum):
    """��Ϣ��Դö��"""
    PLATE = "plate"
    NET = "net" 
    LORA = "lora"

class ParsedMessage(NamedTuple):
    """���������Ϣ�ṹ"""
    source: MessageSource
    message_type: Optional[int]
    length: Optional[int]
    content: bytes
    crc: Optional[int]
    raw_data: bytes
    client_address: Tuple[str, int]

class MessageQueue:
    """�̰߳�ȫ����Ϣ����"""
    def __init__(self, maxsize: int = 1000):
        self._queue = queue.Queue(maxsize=maxsize)
    
    def put(self, message: ParsedMessage, block: bool = True, timeout: Optional[float] = None):
        """�����Ϣ������"""
        try:
            self._queue.put(message, block=block, timeout=timeout)
            logger.debug(f"��Ϣ�Ѽ������: {message.source.value}")
        except queue.Full:
            logger.error(f"��Ϣ������������������ {message.source.value} ����Ϣ")
    
    def get(self, block: bool = True, timeout: Optional[float] = None) -> ParsedMessage:
        """�Ӷ��л�ȡ��Ϣ"""
        return self._queue.get(block=block, timeout=timeout)
    
    def qsize(self) -> int:
        """��ȡ���д�С"""
        return self._queue.qsize()
    
    def empty(self) -> bool:
        """�������Ƿ�Ϊ��"""
        return self._queue.empty()

class MessageParser:
    """��Ϣ������"""
    
    PLATE_SYNC_HEADER = 0x1ACFFC1D  # 4�ֽ�֡ͬ��ͷ
    
    @staticmethod
    def crc16(data: bytes) -> int:
        """����CRC16У��ֵ����ʵ�֣��ɸ��ݾ���Э�������"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc
    
    @classmethod
    def parse_plate_message(cls, data: bytes, client_addr: Tuple[str, int]) -> Optional[ParsedMessage]:
        """����plate��Ϣ"""
        if len(data) < 4:
            logger.warning(f"Plate��Ϣ���Ȳ���4�ֽ�: {len(data)}")
            return None
        
        # ���֡ͬ��ͷ
        sync_header = struct.unpack('>I', data[:4])[0]  # ��������4�ֽ�
        if sync_header != cls.PLATE_SYNC_HEADER:
            logger.warning(f"Plate��Ϣ֡ͬ��ͷ����: 0x{sync_header:08X}")
            return None
        
        content = data[4:]  # ȥ��֡ͬ��ͷ������
        
        return ParsedMessage(
            source=MessageSource.PLATE,
            message_type=None,
            length=len(content),
            content=content,
            crc=None,
            raw_data=data,
            client_address=client_addr
        )
    
    @classmethod
    def parse_net_lora_message(cls, data: bytes, source: MessageSource, 
                              client_addr: Tuple[str, int]) -> Optional[ParsedMessage]:
        """����NET/LORA��Ϣ"""
        if len(data) < 4:  # ��С���ȣ���Ϣ����(1) + ����(1) + CRC(2)
            logger.warning(f"{source.value}��Ϣ���Ȳ���4�ֽ�: {len(data)}")
            return None
        
        # ������Ϣͷ
        message_type = data[0]
        message_length = data[1]
        
        # ��֤��Ϣ����
        expected_total_length = message_length + 4  # ��Ϣ���� + ����(1) + ����(1) + CRC(2)
        if len(data) != expected_total_length:
            logger.warning(f"{source.value}��Ϣ���Ȳ�ƥ��: ����{expected_total_length}, ʵ��{len(data)}")
            return None
        
        # ��ȡ��Ϣ���ݺ�CRC
        content = data[2:2+message_length] if message_length > 0 else b''
        crc_bytes = data[-2:]
        received_crc = struct.unpack('>H', crc_bytes)[0]  # ��������CRC
        
        # ��֤CRC������Ϣ���͡����ȡ����ݽ���У�飩
        check_data = data[:-2]  # ����CRC����������
        calculated_crc = cls.crc16(check_data)
        
        if received_crc != calculated_crc:
            logger.warning(f"{source.value}��ϢCRCУ��ʧ��: ����0x{received_crc:04X}, ����0x{calculated_crc:04X}")
            return None
        
        return ParsedMessage(
            source=source,
            message_type=message_type,
            length=message_length,
            content=content,
            crc=received_crc,
            raw_data=data,
            client_address=client_addr
        )

class UDPServer:
    """UDP������"""
    
    def __init__(self, host: str = None):
        # ʹ�������ļ��е�IP��ַ�����û����ʹ��Ĭ��ֵ
        self.host = host if host else (network_config.local_ip if network_config.local_ip else 'localhost')
        
        # ʹ��ϵͳ�����еĶ��д�С
        queue_size = system_config.max_queue_size if system_config.max_queue_size > 0 else 1000
        self.message_queue = MessageQueue(maxsize=queue_size)
        
        self.running = False
        self.sockets = {}
        self.threads = []
        
        # �������ļ���ȡ�˿�����
        self.ports = {
            MessageSource.PLATE: udp_config.plat_port,
            MessageSource.NET: udp_config.net_port,
            MessageSource.LORA: udp_config.lora_port
        }
        
        # ���������׽���
        self.send_socket = None
    
    def create_socket(self, port: int) -> socket.socket:
        """����UDP�׽���"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, port))
        return sock
    
    def handle_client(self, source: MessageSource):
        """�����ض��˿ڵĿͻ�������"""
        port = self.ports[source]
        sock = self.create_socket(port)
        self.sockets[source] = sock
        
        logger.info(f"{source.value}�����������������˿� {port}")
        
        # ���ý��ջ�������С
        buffer_size = system_config.buffer_size if system_config.buffer_size > 0 else 4096
        
        while self.running:
            try:
                # ���ó�ʱ�Ա㶨�ڼ��running״̬
                sock.settimeout(1.0)
                data, client_addr = sock.recvfrom(buffer_size)
                
                logger.debug(f"�յ����� {source.value} ������: {len(data)} �ֽڣ��ͻ���: {client_addr}")
                
                # ������Ϣ
                if source == MessageSource.PLATE:
                    message = MessageParser.parse_plate_message(data, client_addr)
                else:
                    message = MessageParser.parse_net_lora_message(data, source, client_addr)
                
                # �����������Ϣ�������
                if message:
                    self.message_queue.put(message, block=False)
                    logger.info(f"�ɹ���������� {source.value} ��Ϣ")
                
            except socket.timeout:
                continue  # ��ʱ����ѭ�����running״̬
            except Exception as e:
                if self.running:  # ֻ������״̬�¼�¼����
                    logger.error(f"{source.value}�������������: {e}")
        
        sock.close()
        logger.info(f"{source.value}�������ѹر�")
    
    def start(self):
        """����������"""
        if self.running:
            logger.warning("�������Ѿ�������")
            return
        
        self.running = True
        logger.info("��������UDP������...")
        
        # ���������׽���
        self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.send_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Ϊÿ���˿ڴ��������߳�
        for source in MessageSource:
            thread = threading.Thread(
                target=self.handle_client, 
                args=(source,),
                name=f"UDP-{source.value}",
                daemon=True
            )
            thread.start()
            self.threads.append(thread)
        
        logger.info("����UDP������������")
    
    def stop(self):
        """ֹͣ������"""
        if not self.running:
            logger.warning("������δ������")
            return
        
        logger.info("����ֹͣUDP������...")
        self.running = False
        
        # �ȴ������߳̽���
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=2.0)
        
        # �ر��׽���
        for sock in self.sockets.values():
            sock.close()
        
        # �رշ����׽���
        if self.send_socket:
            self.send_socket.close()
            self.send_socket = None
        
        self.threads.clear()
        self.sockets.clear()
        logger.info("UDP��������ֹͣ")
    
    def get_message(self, timeout: Optional[float] = None) -> Optional[ParsedMessage]:
        """��ȡ�����е���Ϣ"""
        try:
            return self.message_queue.get(block=True, timeout=timeout)
        except queue.Empty:
            return None
    
    def send_plate_message(self, content: bytes, target_ip: str, target_port: int = None) -> bool:
        """����Plate��Ϣ����֡ͬ��ͷ��"""
        if not self.send_socket:
            logger.error("�����׽���δ��ʼ��")
            return False
        
        try:
            # ���֡ͬ��ͷ
            sync_header = struct.pack('>I', MessageParser.PLATE_SYNC_HEADER)
            message = sync_header + content
            
            port = target_port if target_port else self.ports[MessageSource.PLATE]
            bytes_sent = self.send_socket.sendto(message, (target_ip, port))
            
            logger.debug(f"����Plate��Ϣ�� {target_ip}:{port}, ����: {bytes_sent} �ֽ�")
            return True
            
        except Exception as e:
            logger.error(f"����Plate��Ϣʧ��: {e}")
            return False
    
    def send_net_lora_message(self, message_type: int, content: bytes, 
                             target_ip: str, target_port: int = None, 
                             source: MessageSource = MessageSource.NET) -> bool:
        """����NET/LORA��Ϣ����CRCУ�飩"""
        if not self.send_socket:
            logger.error("�����׽���δ��ʼ��")
            return False
        
        try:
            # ������Ϣ
            message_length = len(content)
            if message_length > 255:
                logger.error(f"��Ϣ���ݹ���: {message_length} > 255")
                return False
            
            # ��װ��Ϣ������(1) + ����(1) + ����(n)
            message_data = struct.pack('BB', message_type, message_length) + content
            
            # ����CRC
            crc = MessageParser.crc16(message_data)
            
            # ���CRC����Ϣ + CRC(2)
            full_message = message_data + struct.pack('>H', crc)
            
            port = target_port if target_port else self.ports[source]
            bytes_sent = self.send_socket.sendto(full_message, (target_ip, port))
            
            logger.debug(f"����{source.value}��Ϣ�� {target_ip}:{port}, "
                        f"����:{message_type}, ����:{bytes_sent} �ֽ�, CRC:0x{crc:04X}")
            return True
            
        except Exception as e:
            logger.error(f"����{source.value}��Ϣʧ��: {e}")
            return False
    
    def send_to_gateway(self, message_type: int, content: bytes) -> bool:
        """������Ϣ������"""
        return self.send_net_lora_message(
            message_type, content, 
            network_config.gateway_ip, 
            self.ports[MessageSource.NET], 
            MessageSource.NET
        )
    
    def broadcast_message(self, message_type: int, content: bytes, 
                         broadcast_ip: str = "255.255.255.255") -> bool:
        """�㲥��Ϣ"""
        if not self.send_socket:
            logger.error("�����׽���δ��ʼ��")
            return False
        
        try:
            # ���ù㲥
            self.send_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            # �����ж˿ڹ㲥
            success_count = 0
            for source in [MessageSource.NET, MessageSource.LORA]:
                if self.send_net_lora_message(message_type, content, 
                                            broadcast_ip, self.ports[source], source):
                    success_count += 1
            
            logger.info(f"�㲥��Ϣ��ɣ��ɹ�: {success_count}/2")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"�㲥��Ϣʧ��: {e}")
            return False

class MessageProcessor:
    """��Ϣ������"""
    
    def __init__(self, server: UDPServer):
        self.server = server
        self.running = False
        self.thread = None
    
    def process_message(self, message: ParsedMessage):
        """����������Ϣ��������ʵ�����ҵ���߼���"""
        logger.info(f"���� {message.source.value} ��Ϣ:")
        logger.info(f"  �ͻ��˵�ַ: {message.client_address}")
        logger.info(f"  ���ݳ���: {len(message.content)} �ֽ�")
        
        # ��������˵���ģʽ����ӡ������Ϣ
        if debug_config.enable_debug:
            logger.debug(f"  ԭʼ����: {message.raw_data}")
            if debug_config.print_hex:
                logger.debug(f"  ʮ������: {message.raw_data.hex()}")
        
        if message.source == MessageSource.PLATE:
            logger.info(f"  Plate��Ϣ����: {message.content.hex() if message.content else 'empty'}")
        else:
            logger.info(f"  ��Ϣ����: {message.message_type}")
            logger.info(f"  ��������: {message.length}")
            logger.info(f"  CRCУ��: 0x{message.crc:04X}")
            logger.info(f"  ��Ϣ����: {message.content.hex() if message.content else 'empty'}")
        
        # ����������������ò������в�ͬ�Ĵ���
        if sys_para.net_mod == 7:  # ���׵���ģʽ
            self._handle_cluster_head_mode(message)
        elif sys_para.net_mod == 8:  # ����֯��ģʽ
            self._handle_self_organize_mode(message)
        else:  # ����������ģʽ
            self._handle_normal_mode(message)
        
        # TODO: ������������ҵ�����߼�
        
        # ʾ����������Ϣ���ݽ�����Ӧ
        self._send_response(message)
    
    def _send_response(self, message: ParsedMessage):
        """ʾ����Ӧ����"""
        try:
            if message.source == MessageSource.PLATE:
                # �ظ�Plate��Ϣ
                response = b"Plate response: " + message.content[:10]  # �ظ�ǰ10�ֽ�
                self.server.send_plate_message(response, message.client_address[0])
                
            elif message.source == MessageSource.NET:
                # �ظ�NET��Ϣ
                response_content = f"NET response to type {message.message_type}".encode('utf-8')
                self.server.send_net_lora_message(
                    message_type=0xFF,  # ��Ӧ��Ϣ����
                    content=response_content,
                    target_ip=message.client_address[0],
                    source=MessageSource.NET
                )
                
            elif message.source == MessageSource.LORA:
                # �ظ�LORA��Ϣ
                response_content = f"LORA response to type {message.message_type}".encode('utf-8')
                self.server.send_net_lora_message(
                    message_type=0xFF,  # ��Ӧ��Ϣ����
                    content=response_content,
                    target_ip=message.client_address[0],
                    source=MessageSource.LORA
                )
                
        except Exception as e:
            logger.error(f"������Ӧʧ��: {e}")
    
    def _handle_cluster_head_mode(self, message: ParsedMessage):
        """������׵���ģʽ"""
        logger.info("������׵���ģʽ��Ϣ")
        # ����ʹ�� sys_para.clust_id, sys_para.clust_numb �Ȳ���
        
    def _handle_self_organize_mode(self, message: ParsedMessage):
        """��������֯��ģʽ"""
        logger.info("��������֯��ģʽ��Ϣ")
        
    def _handle_normal_mode(self, message: ParsedMessage):
        """������ͨ������ģʽ"""
        logger.info(f"����ģʽ{sys_para.net_mod}��Ϣ")
        
    def start_processing(self):
        """������Ϣ�����߳�"""
        if self.running:
            logger.warning("��Ϣ�������Ѿ�������")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._process_loop, name="MessageProcessor", daemon=True)
        self.thread.start()
        logger.info("��Ϣ������������")
    
    def stop_processing(self):
        """ֹͣ��Ϣ����"""
        if not self.running:
            logger.warning("��Ϣ������δ������")
            return
        
        logger.info("����ֹͣ��Ϣ������...")
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        logger.info("��Ϣ��������ֹͣ")
    
    def _process_loop(self):
        """��Ϣ����ѭ��"""
        # ʹ�������ļ��еĴ�����
        process_interval = system_config.process_interval if system_config.process_interval > 0 else 0.001
        
        while self.running:
            try:
                message = self.server.get_message(timeout=1.0)
                if message:
                    self.process_message(message)
                # ��Ӵ�����
                if process_interval > 0:
                    time.sleep(process_interval)
            except Exception as e:
                logger.error(f"��Ϣ�������: {e}")

def main():
    """������"""
    # ���ȼ��������ļ�
    if not load_config_from_file("config.ini"):
        logger.error("�����ļ�����ʧ�ܣ�ʹ��Ĭ������")
    else:
        logger.info("�����ļ����سɹ�")
        logger.info(f"�����ڵ�ID: {local_id}")
        logger.info(f"����ģʽ: {sys_para.net_mod} (0-6:������ģʽ, 7:���׵���, 8:����֯��)")
        logger.info(f"�ڵ�ģʽ: {sys_para.node_mod} (0:ĸ��, 1:����, 2:��ͨ�ڵ�)")
        logger.info(f"����IP: {network_config.local_ip}")
        logger.info(f"MAC��ַ: {[hex(x) for x in node_para.mac_addr]}")
    
    # ��������������־����
    log_level = getattr(logging, system_config.log_level.upper(), logging.INFO)
    logging.getLogger().setLevel(log_level)
    
    # ����UDP��������ʹ�������ļ��е�IP��ַ
    server = UDPServer()
    
    # ������Ϣ������
    processor = MessageProcessor(server)
    
    try:
        # ����������
        server.start()
        
        # ������Ϣ������
        processor.start_processing()
        
        logger.info("ϵͳ������ɣ��� Ctrl+C �˳�")
        logger.info(f"�˿�����: Plate={udp_config.plat_port}, "
                   f"Net={udp_config.net_port}, "
                   f"Lora={udp_config.lora_port}")
        logger.info(f"������ַ: {network_config.local_ip}")
        
        # ��ѭ�� - �������þ����Ƿ����״̬��Ϣ
        if debug_config.enable_debug or system_config.log_level.upper() == 'DEBUG':
            # ����ģʽ�¶������״̬
            while True:
                time.sleep(5)
                queue_size = server.message_queue.qsize()
                logger.info(f"��ǰ������Ϣ��: {queue_size}")
                logger.debug(f"ϵͳ���� - ����ģʽ:{sys_para.net_mod}, �ڵ���:{sys_para.node_num}")
        else:
            # ����ģʽ�¾�Ĭ�ȴ���ֻ������Ϣʱ�����
            try:
                while True:
                    time.sleep(10)  # �ϳ���˯�߼��
                    # �������һЩ��Ҫ��ϵͳ���
                    if not processor.running or not server.running:
                        logger.warning("��⵽�����쳣ֹͣ")
                        break
            except KeyboardInterrupt:
                raise  # �����׳�������㴦��
    
    except KeyboardInterrupt:
        logger.info("�յ��˳��ź�")
    
    finally:
        # ������Դ
        processor.stop_processing()
        server.stop()
        logger.info("�����˳�")

if __name__ == "__main__":
    main()