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
    """UDP服务器类 - 支持帧同步和直接消息格式"""
    
    def __init__(self, port: int, source: MessageSource, message_queue: queue.Queue, bind_ip: str = '0.0.0.0'):
        self.port = port
        self.source = source
        self.message_queue = message_queue
        self.bind_ip = bind_ip
        self.socket = None
        self.running = False
        self.thread = None
        
        # 根据端口类型选择处理方式
        if source == MessageSource.HOST_SOFTWARE:
            # 上位机端口使用统一消息接收器（支持帧同步）
            self.message_receiver = UnifiedMessageReceiver()
            self.use_frame_sync = True
        else:
            # LoRa和网关端口使用直接处理
            self.message_receiver = None
            self.use_frame_sync = False
        
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
            
            sync_info = "支持帧同步" if self.use_frame_sync else "直接消息"
            logging.info(f"{self.source.value} UDP服务器启动在端口 {self.port} ({sync_info})")
            
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
                    self._process_received_data(data, addr)
                        
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logging.error(f"{self.source.value} UDP服务器错误: {e}")
    
    def _process_received_data(self, data: bytes, addr: tuple):
        """处理接收到的数据"""
        if self.use_frame_sync:
            # 使用统一消息接收器处理（支持帧同步）
            messages = self.message_receiver.process_data(data)
            
            for msg_type, content, crc_valid, detected_source in messages:
                if not crc_valid:
                    logging.warning(f"收到CRC校验失败的消息 from {addr}, 检测源: {detected_source}")
                    continue
                
                # 创建消息对象
                message = UDPMessage(
                    source=self.source,
                    data=content,
                    addr=addr,
                    timestamp=datetime.now(),
                    msg_type=msg_type
                )
                
                # 添加检测到的消息源信息
                message.detected_source = detected_source
                
                self._enqueue_message(message, addr, msg_type, len(content), detected_source)
                
        else:
            # 直接消息处理（LoRa/网关）
            msg_type, content, crc_valid = MessageProtocol.unpack_message(data)
            
            if not crc_valid:
                logging.warning(f"收到CRC校验失败的消息 from {addr}")
                return
            
            if msg_type is None:
                logging.warning(f"收到无效格式消息 from {addr}")
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
        """将消息加入队列"""
        try:
            self.message_queue.put(message, timeout=0.1)
            logging.debug(f"收到来自 {self.source.value} 的消息: 类型=0x{msg_type:02X}, "
                        f"长度={content_len} bytes from {addr}, 格式={msg_format}")
        except queue.Full:
            logging.warning(f"消息队列已满，丢弃来自 {self.source.value} 的消息")
    
    def send_message(self, target_addr: tuple, msg_type: int, content: bytes):
        """发送消息到指定地址"""
        try:
            if self.use_frame_sync:
                # 上位机端口发送带帧同步头的消息
                from frame_sync import build_frame_sync_message
                packed_msg = build_frame_sync_message(msg_type, content)
            else:
                # LoRa/网关端口发送直接消息
                packed_msg = MessageProtocol.pack_message(msg_type, content)
                
            self.socket.sendto(packed_msg, target_addr)
            format_info = "帧同步格式" if self.use_frame_sync else "直接格式"
            logging.debug(f"发送消息: 类型=0x{msg_type:02X}, 目标={target_addr}, 格式={format_info}")
        except Exception as e:
            logging.error(f"发送消息失败: {e}")
    
    def broadcast_message(self, msg_type: int, content: bytes, port: int = None):
        """广播消息"""
        if port is None:
            port = self.port
        
        try:
            if self.use_frame_sync:
                from frame_sync import build_frame_sync_message
                packed_msg = build_frame_sync_message(msg_type, content)
            else:
                packed_msg = MessageProtocol.pack_message(msg_type, content)
            
            # 设置广播
            broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            broadcast_socket.sendto(packed_msg, ('255.255.255.255', port))
            broadcast_socket.close()
            
            format_info = "帧同步格式" if self.use_frame_sync else "直接格式"
            logging.debug(f"广播消息: 类型=0x{msg_type:02X}, 端口={port}, 格式={format_info}")
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
    
    def get_status(self):
        """获取服务器状态"""
        status = {
            'running': self.is_running(),
            'address': self.get_local_address(),
            'source': self.source.value,
            'frame_sync_enabled': self.use_frame_sync
        }
        
        if self.use_frame_sync and self.message_receiver:
            status['receiver_status'] = self.message_receiver.get_status()
        
        return status