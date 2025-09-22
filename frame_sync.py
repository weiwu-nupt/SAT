#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import struct
import logging
from typing import Optional, List, Tuple
from collections import deque

from protocol import MessageProtocol


class FrameSyncProcessor:
    """֡ͬ�������� - �����֡ͬ��ͷ��������"""
    
    # ֡ͬ��ͷ��ʶ
    FRAME_SYNC_HEADER = 0x1ACFFC1D
    FRAME_SYNC_BYTES = struct.pack('>I', FRAME_SYNC_HEADER)  # �����4�ֽ�
    
    def __init__(self, buffer_size: int = 8192):
        self.buffer_size = buffer_size
        self.ring_buffer = bytearray(buffer_size)
        self.write_pos = 0  # д��λ��
        self.read_pos = 0   # ��ȡλ��
        self.data_length = 0  # �������е����ݳ���
        
    def add_data(self, data: bytes) -> None:
        """���λ������������"""
        for byte in data:
            self.ring_buffer[self.write_pos] = byte
            self.write_pos = (self.write_pos + 1) % self.buffer_size
            
            # �������ݳ��ȣ������ܳ�����������С
            if self.data_length < self.buffer_size:
                self.data_length += 1
            else:
                # ���������ˣ��ƶ���ȡλ��
                self.read_pos = (self.read_pos + 1) % self.buffer_size
    
    def find_frame_header(self) -> Optional[int]:
        """����֡ͬ��ͷ����������ڶ�ȡλ�õ�ƫ��"""
        if self.data_length < 4:
            return None
        
        # �ڻ��λ�����������֡ͬ��ͷ
        for offset in range(self.data_length - 3):
            # ��ȡ4���ֽ�
            pos = (self.read_pos + offset) % self.buffer_size
            header_bytes = bytearray(4)
            
            for i in range(4):
                header_bytes[i] = self.ring_buffer[(pos + i) % self.buffer_size]
            
            # ����Ƿ�ƥ��֡ͬ��ͷ
            if bytes(header_bytes) == self.FRAME_SYNC_BYTES:
                return offset
        
        return None
    
    def extract_message(self) -> Optional[Tuple[int, bytes]]:
        """��ȡ������Ϣ������(��Ϣ����, ��Ϣ����)��ʧ�ܷ���None"""
        # ����֡ͬ��ͷ
        header_offset = self.find_frame_header()
        if header_offset is None:
            # δ�ҵ�֡ͷ������һЩ������
            if self.data_length > self.buffer_size // 2:
                discard_count = self.buffer_size // 4
                self._discard_data(discard_count)
                logging.debug(f"δ�ҵ�֡ͷ������ {discard_count} �ֽھ�����")
            return None
        
        # ���֡ͷ���ڿ�ʼλ�ã��ȶ���֡ͷ֮ǰ������
        if header_offset > 0:
            self._discard_data(header_offset)
            logging.debug(f"����֡ͷǰ�� {header_offset} �ֽ�����")
        
        # ����֡ͷӦ���ڶ�ȡλ��
        # ����Ƿ����㹻���ݶ�ȡ��Ϣͷ��֡ͷ(4) + ����(1) + ����(1) = 6�ֽ�
        if self.data_length < 6:
            return None
        
        # ��ȡ��Ϣ���ͺͳ���
        msg_type = self.ring_buffer[(self.read_pos + 4) % self.buffer_size]
        msg_len = self.ring_buffer[(self.read_pos + 5) % self.buffer_size]
        
        # ����Ƿ���������Ϣ��֡ͷ(4) + ������Ϣ����
        total_needed = 4 + msg_len
        if self.data_length < total_needed:
            return None
        
        # ��ȡ������Ϣ��������֡ͷ��
        message_data = bytearray(msg_len)
        for i in range(msg_len):
            pos = (self.read_pos + 4 + i) % self.buffer_size
            message_data[i] = self.ring_buffer[pos]
        
        # �ӻ��������Ƴ��Ѵ��������
        self._discard_data(total_needed)
        
        return msg_type, bytes(message_data)
    
    def _discard_data(self, count: int) -> None:
        """����ָ������������"""
        count = min(count, self.data_length)
        self.read_pos = (self.read_pos + count) % self.buffer_size
        self.data_length -= count
    
    def get_buffer_status(self) -> dict:
        """��ȡ������״̬"""
        return {
            'buffer_size': self.buffer_size,
            'data_length': self.data_length,
            'free_space': self.buffer_size - self.data_length,
            'usage_percent': (self.data_length / self.buffer_size) * 100
        }


class SimpleMessageProcessor:
    """����Ϣ������ - ������֡ͬ��ͷ��ֱ����Ϣ"""
    
    @staticmethod
    def process_direct_message(data: bytes) -> Optional[Tuple[int, bytes, bool]]:
        """
        ����ֱ����Ϣ����LoRa��Ϣ��
        ����: (��Ϣ����, ��Ϣ����, CRCУ����)
        """
        return MessageProtocol.unpack_message(data)


class UnifiedMessageReceiver:
    """ͳһ��Ϣ������ - �Զ�ʶ��ʹ���ͬ��ʽ����Ϣ"""
    
    def __init__(self):
        self.frame_sync_processor = FrameSyncProcessor()
        
    def process_data(self, data: bytes, source_hint: str = None) -> List[Tuple[int, bytes, bool, str]]:
        """
        ������յ�������
        ����: [(��Ϣ����, ��Ϣ����, CRCУ����, ��Դ����), ...]
        ��Դ����: 'host_software' �� 'lora'
        """
        messages = []
        
        # ���ȳ�����Ϊֱ����Ϣ����LoRa��ʽ��
        if len(data) >= 4:  # ��С��Ϣ����
            direct_result = SimpleMessageProcessor.process_direct_message(data)
            if direct_result[0] is not None and direct_result[2]:  # ��Ϣ��Ч��CRC��ȷ
                msg_type, content, crc_valid = direct_result
                messages.append((msg_type, content, crc_valid, 'lora'))
                return messages
        
        # ���ֱ�Ӵ���ʧ�ܣ�������Ϊ֡ͬ�����ݴ���
        self.frame_sync_processor.add_data(data)
        
        # ѭ����ȡ���п��ܵ�������Ϣ
        max_messages = 10  # ��ֹ����ѭ��
        message_count = 0
        
        while message_count < max_messages:
            result = self.frame_sync_processor.extract_message()
            if result is None:
                break
                
            msg_type, message_data = result
            
            # ��֤��ȡ����Ϣ
            unpacked = MessageProtocol.unpack_message(message_data)
            if unpacked[0] is not None:
                content_msg_type, content, crc_valid = unpacked
                # ��֤��Ϣ����һ����
                if msg_type == content_msg_type:
                    messages.append((msg_type, content, crc_valid, 'host_software'))
                    message_count += 1
                else:
                    logging.warning(f"��Ϣ���Ͳ�һ��: ֡ͷ={msg_type}, ����={content_msg_type}")
            else:
                logging.warning("��ȡ����Ϣ��ʽ��Ч")
                break
        
        return messages
    
    def get_status(self) -> dict:
        """��ȡ������״̬"""
        return {
            'frame_sync_buffer': self.frame_sync_processor.get_buffer_status()
        }


# ���ߺ��������ڲ��Ե�֡ͬ����Ϣ����
def build_frame_sync_message(msg_type: int, content: bytes) -> bytes:
    """������֡ͬ��ͷ����Ϣ"""
    # ���ȹ�����׼��Ϣ
    standard_msg = MessageProtocol.pack_message(msg_type, content)
    
    # ���֡ͬ��ͷ
    frame_sync_bytes = struct.pack('>I', FrameSyncProcessor.FRAME_SYNC_HEADER)
    
    return frame_sync_bytes + standard_msg