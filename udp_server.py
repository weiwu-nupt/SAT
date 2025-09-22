#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import threading
import queue
import logging
from datetime import datetime

from protocol import MessageProtocol, MessageSource, UDPMessage


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
                    # ������Ϣ��ʽ
                    msg_type, content, crc_valid = MessageProtocol.unpack_message(data)
                    
                    if not crc_valid:
                        logging.warning(f"�յ�CRCУ��ʧ�ܵ���Ϣ from {addr}")
                        continue
                    
                    message = UDPMessage(
                        source=self.source,
                        data=content,  # �洢�����������
                        addr=addr,
                        timestamp=datetime.now()
                    )
                    
                    # �����Ϣ������Ϣ
                    message.msg_type = msg_type
                    
                    # ����Ϣ�������
                    try:
                        self.message_queue.put(message, timeout=0.1)
                        logging.debug(f"�յ����� {self.source.value} ����Ϣ: ����=0x{msg_type:02X}, "
                                    f"����={len(content)} bytes from {addr}")
                    except queue.Full:
                        logging.warning(f"��Ϣ������������������ {self.source.value} ����Ϣ")
                        
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logging.error(f"{self.source.value} UDP����������: {e}")
    
    def send_message(self, target_addr: tuple, msg_type: int, content: bytes):
        """������Ϣ��ָ����ַ"""
        try:
            packed_msg = MessageProtocol.pack_message(msg_type, content)
            self.socket.sendto(packed_msg, target_addr)
            logging.debug(f"������Ϣ: ����=0x{msg_type:02X}, Ŀ��={target_addr}")
        except Exception as e:
            logging.error(f"������Ϣʧ��: {e}")
    
    def broadcast_message(self, msg_type: int, content: bytes, port: int = None):
        """�㲥��Ϣ"""
        if port is None:
            port = self.port
        
        try:
            packed_msg = MessageProtocol.pack_message(msg_type, content)
            
            # ���ù㲥
            broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            broadcast_socket.sendto(packed_msg, ('255.255.255.255', port))
            broadcast_socket.close()
            
            logging.debug(f"�㲥��Ϣ: ����=0x{msg_type:02X}, �˿�={port}")
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