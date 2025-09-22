#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import threading
import queue
import logging
from datetime import datetime

from protocol import MessageProtocol, MessageSource, UDPMessage
from frame_sync import UnifiedMessageReceiver


class UDPServer:
    """UDP�������� - ֧��֡ͬ����ֱ����Ϣ��ʽ"""
    
    def __init__(self, port: int, source: MessageSource, message_queue: queue.Queue, bind_ip: str = '0.0.0.0'):
        self.port = port
        self.source = source
        self.message_queue = message_queue
        self.bind_ip = bind_ip
        self.socket = None
        self.running = False
        self.thread = None
        
        # ���ݶ˿�����ѡ����ʽ
        if source == MessageSource.HOST_SOFTWARE:
            # ��λ���˿�ʹ��ͳһ��Ϣ��������֧��֡ͬ����
            self.message_receiver = UnifiedMessageReceiver()
            self.use_frame_sync = True
        else:
            # LoRa�����ض˿�ʹ��ֱ�Ӵ���
            self.message_receiver = None
            self.use_frame_sync = False
        
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
            
            sync_info = "֧��֡ͬ��" if self.use_frame_sync else "ֱ����Ϣ"
            logging.info(f"{self.source.value} UDP�����������ڶ˿� {self.port} ({sync_info})")
            
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
                    self._process_received_data(data, addr)
                        
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logging.error(f"{self.source.value} UDP����������: {e}")
    
    def _process_received_data(self, data: bytes, addr: tuple):
        """������յ�������"""
        if self.use_frame_sync:
            # ʹ��ͳһ��Ϣ����������֧��֡ͬ����
            messages = self.message_receiver.process_data(data)
            
            for msg_type, content, crc_valid, detected_source in messages:
                if not crc_valid:
                    logging.warning(f"�յ�CRCУ��ʧ�ܵ���Ϣ from {addr}, ���Դ: {detected_source}")
                    continue
                
                # ������Ϣ����
                message = UDPMessage(
                    source=self.source,
                    data=content,
                    addr=addr,
                    timestamp=datetime.now(),
                    msg_type=msg_type
                )
                
                # ��Ӽ�⵽����ϢԴ��Ϣ
                message.detected_source = detected_source
                
                self._enqueue_message(message, addr, msg_type, len(content), detected_source)
                
        else:
            # ֱ����Ϣ����LoRa/���أ�
            msg_type, content, crc_valid = MessageProtocol.unpack_message(data)
            
            if not crc_valid:
                logging.warning(f"�յ�CRCУ��ʧ�ܵ���Ϣ from {addr}")
                return
            
            if msg_type is None:
                logging.warning(f"�յ���Ч��ʽ��Ϣ from {addr}")
                return
            
            message = UDPMessage(
                source=self.source,
                data=content,
                addr=addr,
                timestamp=datetime.now(),
                msg_type=msg_type
            )
            
            self._enqueue_message(message, addr, msg_type, len(content), "direct")
    
    def _enqueue_message(self, message: UDPMessage, addr: tuple, msg_type: int, content_len: int, msg_format: str):
        """����Ϣ�������"""
        try:
            self.message_queue.put(message, timeout=0.1)
            logging.debug(f"�յ����� {self.source.value} ����Ϣ: ����=0x{msg_type:02X}, "
                        f"����={content_len} bytes from {addr}, ��ʽ={msg_format}")
        except queue.Full:
            logging.warning(f"��Ϣ������������������ {self.source.value} ����Ϣ")
    
    def send_message(self, target_addr: tuple, msg_type: int, content: bytes):
        """������Ϣ��ָ����ַ"""
        try:
            if self.use_frame_sync:
                # ��λ���˿ڷ��ʹ�֡ͬ��ͷ����Ϣ
                from frame_sync import build_frame_sync_message
                packed_msg = build_frame_sync_message(msg_type, content)
            else:
                # LoRa/���ض˿ڷ���ֱ����Ϣ
                packed_msg = MessageProtocol.pack_message(msg_type, content)
                
            self.socket.sendto(packed_msg, target_addr)
            format_info = "֡ͬ����ʽ" if self.use_frame_sync else "ֱ�Ӹ�ʽ"
            logging.debug(f"������Ϣ: ����=0x{msg_type:02X}, Ŀ��={target_addr}, ��ʽ={format_info}")
        except Exception as e:
            logging.error(f"������Ϣʧ��: {e}")
    
    def broadcast_message(self, msg_type: int, content: bytes, port: int = None):
        """�㲥��Ϣ"""
        if port is None:
            port = self.port
        
        try:
            if self.use_frame_sync:
                from frame_sync import build_frame_sync_message
                packed_msg = build_frame_sync_message(msg_type, content)
            else:
                packed_msg = MessageProtocol.pack_message(msg_type, content)
            
            # ���ù㲥
            broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            broadcast_socket.sendto(packed_msg, ('255.255.255.255', port))
            broadcast_socket.close()
            
            format_info = "֡ͬ����ʽ" if self.use_frame_sync else "ֱ�Ӹ�ʽ"
            logging.debug(f"�㲥��Ϣ: ����=0x{msg_type:02X}, �˿�={port}, ��ʽ={format_info}")
        except Exception as e:
            logging.error(f"�㲥��Ϣʧ��: {e}")
    
    def get_local_address(self):
        """��ȡ���ص�ַ"""
        if self.socket:
            return self.socket.getsockname()
        return None
    
    def is_running(self):
        """���������Ƿ�������"""
        return self.running and self.thread and self.thread.is_alive()
    
    def get_status(self):
        """��ȡ������״̬"""
        status = {
            'running': self.is_running(),
            'address': self.get_local_address(),
            'source': self.source.value,
            'frame_sync_enabled': self.use_frame_sync
        }
        
        if self.use_frame_sync and self.message_receiver:
            status['receiver_status'] = self.message_receiver.get_status()
        
        return status