#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import struct
import logging
from typing import Optional, List, Tuple
from collections import deque

from protocol import MessageProtocol


class FrameSyncProcessor:
    """帧同步处理器 - 处理带帧同步头的数据流"""
    
    # 帧同步头标识
    FRAME_SYNC_HEADER = 0x1ACFFC1D
    FRAME_SYNC_BYTES = struct.pack('>I', FRAME_SYNC_HEADER)  # 大端序4字节
    
    def __init__(self, buffer_size: int = 8192):
        self.buffer_size = buffer_size
        self.ring_buffer = bytearray(buffer_size)
        self.write_pos = 0  # 写入位置
        self.read_pos = 0   # 读取位置
        self.data_length = 0  # 缓冲区中的数据长度
        
    def add_data(self, data: bytes) -> None:
        """向环形缓冲区添加数据"""
        for byte in data:
            self.ring_buffer[self.write_pos] = byte
            self.write_pos = (self.write_pos + 1) % self.buffer_size
            
            # 更新数据长度，但不能超过缓冲区大小
            if self.data_length < self.buffer_size:
                self.data_length += 1
            else:
                # 缓冲区满了，移动读取位置
                self.read_pos = (self.read_pos + 1) % self.buffer_size
    
    def find_frame_header(self) -> Optional[int]:
        """查找帧同步头，返回相对于读取位置的偏移"""
        if self.data_length < 4:
            return None
        
        # 在环形缓冲区中搜索帧同步头
        for offset in range(self.data_length - 3):
            # 读取4个字节
            pos = (self.read_pos + offset) % self.buffer_size
            header_bytes = bytearray(4)
            
            for i in range(4):
                header_bytes[i] = self.ring_buffer[(pos + i) % self.buffer_size]
            
            # 检查是否匹配帧同步头
            if bytes(header_bytes) == self.FRAME_SYNC_BYTES:
                return offset
        
        return None
    
    def extract_message(self) -> Optional[Tuple[int, bytes]]:
        """提取完整消息，返回(消息类型, 消息内容)，失败返回None"""
        # 查找帧同步头
        header_offset = self.find_frame_header()
        if header_offset is None:
            # 未找到帧头，丢弃一些旧数据
            if self.data_length > self.buffer_size // 2:
                discard_count = self.buffer_size // 4
                self._discard_data(discard_count)
                logging.debug(f"未找到帧头，丢弃 {discard_count} 字节旧数据")
            return None
        
        # 如果帧头不在开始位置，先丢弃帧头之前的数据
        if header_offset > 0:
            self._discard_data(header_offset)
            logging.debug(f"丢弃帧头前的 {header_offset} 字节数据")
        
        # 现在帧头应该在读取位置
        # 检查是否有足够数据读取消息头：帧头(4) + 类型(1) + 长度(1) = 6字节
        if self.data_length < 6:
            return None
        
        # 读取消息类型和长度
        msg_type = self.ring_buffer[(self.read_pos + 4) % self.buffer_size]
        msg_len = self.ring_buffer[(self.read_pos + 5) % self.buffer_size]
        
        # 检查是否有完整消息：帧头(4) + 完整消息长度
        total_needed = 4 + msg_len
        if self.data_length < total_needed:
            return None
        
        # 提取完整消息（不包括帧头）
        message_data = bytearray(msg_len)
        for i in range(msg_len):
            pos = (self.read_pos + 4 + i) % self.buffer_size
            message_data[i] = self.ring_buffer[pos]
        
        # 从缓冲区中移除已处理的数据
        self._discard_data(total_needed)
        
        return msg_type, bytes(message_data)
    
    def _discard_data(self, count: int) -> None:
        """丢弃指定数量的数据"""
        count = min(count, self.data_length)
        self.read_pos = (self.read_pos + count) % self.buffer_size
        self.data_length -= count
    
    def get_buffer_status(self) -> dict:
        """获取缓冲区状态"""
        return {
            'buffer_size': self.buffer_size,
            'data_length': self.data_length,
            'free_space': self.buffer_size - self.data_length,
            'usage_percent': (self.data_length / self.buffer_size) * 100
        }


class SimpleMessageProcessor:
    """简单消息处理器 - 处理无帧同步头的直接消息"""
    
    @staticmethod
    def process_direct_message(data: bytes) -> Optional[Tuple[int, bytes, bool]]:
        """
        处理直接消息（如LoRa消息）
        返回: (消息类型, 消息内容, CRC校验结果)
        """
        return MessageProtocol.unpack_message(data)


class UnifiedMessageReceiver:
    """统一消息接收器 - 自动识别和处理不同格式的消息"""
    
    def __init__(self):
        self.frame_sync_processor = FrameSyncProcessor()
        
    def process_data(self, data: bytes, source_hint: str = None) -> List[Tuple[int, bytes, bool, str]]:
        """
        处理接收到的数据
        返回: [(消息类型, 消息内容, CRC校验结果, 来源类型), ...]
        来源类型: 'host_software' 或 'lora'
        """
        messages = []
        
        # 首先尝试作为直接消息处理（LoRa格式）
        if len(data) >= 4:  # 最小消息长度
            direct_result = SimpleMessageProcessor.process_direct_message(data)
            if direct_result[0] is not None and direct_result[2]:  # 消息有效且CRC正确
                msg_type, content, crc_valid = direct_result
                messages.append((msg_type, content, crc_valid, 'lora'))
                return messages
        
        # 如果直接处理失败，尝试作为帧同步数据处理
        self.frame_sync_processor.add_data(data)
        
        # 循环提取所有可能的完整消息
        max_messages = 10  # 防止无限循环
        message_count = 0
        
        while message_count < max_messages:
            result = self.frame_sync_processor.extract_message()
            if result is None:
                break
                
            msg_type, message_data = result
            
            # 验证提取的消息
            unpacked = MessageProtocol.unpack_message(message_data)
            if unpacked[0] is not None:
                content_msg_type, content, crc_valid = unpacked
                # 验证消息类型一致性
                if msg_type == content_msg_type:
                    messages.append((msg_type, content, crc_valid, 'host_software'))
                    message_count += 1
                else:
                    logging.warning(f"消息类型不一致: 帧头={msg_type}, 内容={content_msg_type}")
            else:
                logging.warning("提取的消息格式无效")
                break
        
        return messages
    
    def get_status(self) -> dict:
        """获取接收器状态"""
        return {
            'frame_sync_buffer': self.frame_sync_processor.get_buffer_status()
        }


# 工具函数：用于测试的帧同步消息构建
def build_frame_sync_message(msg_type: int, content: bytes) -> bytes:
    """构建带帧同步头的消息"""
    # 首先构建标准消息
    standard_msg = MessageProtocol.pack_message(msg_type, content)
    
    # 添加帧同步头
    frame_sync_bytes = struct.pack('>I', FrameSyncProcessor.FRAME_SYNC_HEADER)
    
    return frame_sync_bytes + standard_msg