#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import threading
import queue
import logging
from datetime import datetime

from protocol import MessageProtocol, MessageSource, UDPMessage


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
                    # 解析消息格式
                    msg_type, content, crc_valid = MessageProtocol.unpack_message(data)
                    
                    if not crc_valid:
                        logging.warning(f"收到CRC校验失败的消息 from {addr}")
                        continue
                    
                    message = UDPMessage(
                        source=self.source,
                        data=content,  # 存储解析后的内容
                        addr=addr,
                        timestamp=datetime.now()
                    )
                    
                    # 添加消息类型信息
                    message.msg_type = msg_type
                    
                    # 将消息放入队列
                    try:
                        self.message_queue.put(message, timeout=0.1)
                        logging.debug(f"收到来自 {self.source.value} 的消息: 类型=0x{msg_type:02X}, "
                                    f"长度={len(content)} bytes from {addr}")
                    except queue.Full:
                        logging.warning(f"消息队列已满，丢弃来自 {self.source.value} 的消息")
                        
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logging.error(f"{self.source.value} UDP服务器错误: {e}")
    
    def send_message(self, target_addr: tuple, msg_type: int, content: bytes):
        """发送消息到指定地址"""
        try:
            packed_msg = MessageProtocol.pack_message(msg_type, content)
            self.socket.sendto(packed_msg, target_addr)
            logging.debug(f"发送消息: 类型=0x{msg_type:02X}, 目标={target_addr}")
        except Exception as e:
            logging.error(f"发送消息失败: {e}")
    
    def broadcast_message(self, msg_type: int, content: bytes, port: int = None):
        """广播消息"""
        if port is None:
            port = self.port
        
        try:
            packed_msg = MessageProtocol.pack_message(msg_type, content)
            
            # 设置广播
            broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            broadcast_socket.sendto(packed_msg, ('255.255.255.255', port))
            broadcast_socket.close()
            
            logging.debug(f"广播消息: 类型=0x{msg_type:02X}, 端口={port}")
        except Exception as e:
            logging.error(f"广播消息失败: {e}")
    
    def get_local_address(self):
        """获取本地地址"""
        if self.socket:
            return self.socket.getsockname()
        return None
    
    def is_running(self):
        """检查服务器是否运行中"""
        return self.running and self.thread and self.thread.is_alive()