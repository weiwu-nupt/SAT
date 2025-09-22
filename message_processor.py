#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import queue
import threading
import logging
import struct
from typing import Dict

from protocol import MessageSource, MessageType, UDPMessage
from lora_processor import LoRaProcessor


class MessageProcessor:
    """消息处理器"""
    
    def __init__(self, message_queue: queue.Queue):
        self.message_queue = message_queue
        self.running = False
        self.thread = None
        
        # 初始化LoRa处理器
        self.lora_processor = LoRaProcessor()
        
        # 存储UDP服务器引用，用于发送消息
        self.udp_servers = {}
        
    def set_udp_servers(self, servers: Dict[MessageSource, 'UDPServer']):
        """设置UDP服务器引用"""
        self.udp_servers = servers
        
        # 设置LoRa处理器的消息发送接口
        def send_message(target_addr, msg_type, content):
            if MessageSource.LORA in self.udp_servers:
                self.udp_servers[MessageSource.LORA].send_message(target_addr, msg_type, content)
        
        self.lora_processor.set_message_sender(send_message)
        
        # 设置响应服务器
        self._response_server = self.udp_servers.get(MessageSource.HOST_SOFTWARE)
        
    def start(self):
        """启动消息处理器"""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._process_messages, daemon=True)
        self.thread.start()
        
        # 启动LoRa处理器
        self.lora_processor.start()
        
        logging.info("消息处理器已启动")
    
    def stop(self):
        """停止消息处理器"""
        self.running = False
        
        # 停止LoRa处理器
        self.lora_processor.stop()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        logging.info("消息处理器已停止")
    
    def set_node_type(self, node_type: str):
        """设置节点类型"""
        self.lora_processor.set_node_type(node_type)
    
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
        logging.info(f"处理上位机消息: 类型=0x{message.msg_type:02X}, "
                    f"长度={len(message.data)} bytes from {message.addr}")
        
        try:
            if message.msg_type == MessageType.CMD_SET_NODE_TYPE:  # 设置节点类型
                if len(message.data) >= 1:
                    node_type = message.data[0]
                    if node_type == 0x00:
                        self.lora_processor.set_node_type("mother")
                    elif node_type == 0x01:
                        self.lora_processor.set_node_type("cluster")
                        self.lora_processor.set_node_type("normal")
                    
                    # 发送确认消息
                    self._send_response(message.addr, MessageType.CMD_SET_NODE_TYPE, b'\x00')
                    
            elif message.msg_type == MessageType.CMD_SET_NETWORK_CONFIG:  # 设置网络参数
                self._handle_network_config(message.data)
                self._send_response(message.addr, MessageType.CMD_SET_NETWORK_CONFIG, b'\x00')
                
            elif message.msg_type == MessageType.CMD_QUERY_STATUS:  # 查询节点状态
                self._send_node_status(message.addr)
                
            elif message.msg_type == MessageType.CMD_START_NETWORK:  # 启动组网
                self.lora_processor.link_sta = 1
                self._send_response(message.addr, MessageType.CMD_START_NETWORK, b'\x00')
                
            elif message.msg_type == MessageType.CMD_STOP_NETWORK:  # 停止组网
                self.lora_processor.link_sta = 0
                self._send_response(message.addr, MessageType.CMD_STOP_NETWORK, b'\x00')
                
            else:
                logging.warning(f"未知上位机命令: 0x{message.msg_type:02X}")
                
        except Exception as e:
            logging.error(f"处理上位机消息失败: {e}")
        
    def _handle_gateway_message(self, message: UDPMessage):
        """处理网关消息"""
        logging.info(f"处理网关消息: 类型=0x{message.msg_type:02X}, "
                    f"长度={len(message.data)} bytes from {message.addr}")
        
        try:
            if message.msg_type == MessageType.NETMGR_NETWORK_MGMT:  # 网络管理消息
                self._handle_network_management(message.data)
                
            elif message.msg_type == MessageType.NETMGR_NODE_CONFIG:  # 节点配置消息
                self._handle_node_configuration(message.data)
                
            elif message.msg_type == MessageType.NETMGR_DATA_FORWARD:  # 数据转发消息
                self._handle_data_forwarding(message.data)
                
            else:
                logging.warning(f"未知网关消息类型: 0x{message.msg_type:02X}")
                
        except Exception as e:
            logging.error(f"处理网关消息失败: {e}")
        
    def _handle_lora_message(self, message: UDPMessage):
        """处理LoRa消息"""
        logging.info(f"处理LoRa消息: 类型=0x{message.msg_type:02X}, "
                    f"长度={len(message.data)} bytes from {message.addr}")
        
        try:
            # 将消息内容转换为列表格式，兼容原始LoRa处理逻辑
            recv_data = [message.msg_type] + [len(message.data) + 4] + list(message.data)
            
            # 更新LoRa处理器的接收数据
            self.lora_processor.lora_recv_data['recv_dat'] = recv_data
            self.lora_processor.lora_recv_data['recv_time'] = int(message.timestamp.timestamp() * 1000)
            
            # 设置应答标志
            self.lora_processor.send_con['recv_send_en'] = True
            self.lora_processor.send_con['fram_type'] = message.msg_type
            
            logging.debug(f"接收LoRa帧: 类型=0x{message.msg_type:02X}, 触发应答处理")
            
        except Exception as e:
            logging.error(f"处理LoRa消息失败: {e}")
    
    def _send_response(self, target_addr: tuple, msg_type: int, content: bytes):
        """发送响应消息"""
        try:
            # 查找对应的UDP服务器发送响应
            if self._response_server:
                self._response_server.send_message(target_addr, msg_type, content)
            else:
                logging.warning("无法发送响应：未找到响应服务器")
        except Exception as e:
            logging.error(f"发送响应失败: {e}")
    
    def _send_node_status(self, target_addr: tuple):
        """发送节点状态"""
        try:
            # 构建状态数据
            lora_processor = self.lora_processor
            status_data = struct.pack('BBBBBB',
                lora_processor.local_id,           # 节点ID
                lora_processor.sys_para['node_mod'], # 节点类型
                lora_processor.link_sta,           # 链路状态
                lora_processor.sys_para['mother_id'], # 母星ID
                lora_processor.sys_para['net_mod'],  # 网络模式
                self.message_queue.qsize()         # 队列大小
            )
            
            self._send_response(target_addr, MessageType.CMD_QUERY_STATUS, status_data)
            logging.info(f"发送节点状态到 {target_addr}")
            
        except Exception as e:
            logging.error(f"发送节点状态失败: {e}")
    
    def _handle_network_config(self, config_data: bytes):
        """处理网络配置"""
        if len(config_data) >= 4:
            net_id = config_data[0]
            mother_id = config_data[1]
            gateway_id = config_data[2]
            local_id = config_data[3]
            
            # 更新LoRa处理器配置
            self.lora_processor.sys_para['net_id'] = net_id
            self.lora_processor.sys_para['mother_id'] = mother_id
            self.lora_processor.sys_para['gateway_id'] = gateway_id
            self.lora_processor.local_id = local_id
            
            logging.info(f"更新网络配置: 网络ID={net_id}, 母星ID={mother_id}, 本地ID={local_id}")
    
    def _handle_network_management(self, data: bytes):
        """处理网络管理消息"""
        if len(data) >= 1:
            mgmt_cmd = data[0]
            if mgmt_cmd == 0x01:  # 启动网络
                self.lora_processor.link_sta = 1
                logging.info("网络管理: 启动组网")
            elif mgmt_cmd == 0x02:  # 停止网络
                self.lora_processor.link_sta = 0
                logging.info("网络管理: 停止组网")
            elif mgmt_cmd == 0x03:  # 母星选举
                self.lora_processor.sys_para['net_mod'] = 6
                logging.info("网络管理: 启动母星选举")
    
    def _handle_node_configuration(self, data: bytes):
        """处理节点配置"""
        if len(data) >= 4:
            node_id = data[0]
            operation = data[1]
            param1 = data[2]
            param2 = data[3]
            
            logging.info(f"节点配置: ID={node_id}, 操作={operation}")
    
    def _handle_data_forwarding(self, data: bytes):
        """处理数据转发"""
        if len(data) >= 2:
            target_id = data[0]
            data_len = data[1]
            
            if len(data) >= 2 + data_len:
                # 设置网络数据发送
                self.lora_processor.netman_recv_dat = list(data[:2+data_len])
                self.lora_processor.netman_new_dat = True
                
                logging.info(f"数据转发: 目标ID={target_id}, 数据长度={data_len}")
    
    def get_lora_processor(self):
        """获取LoRa处理器实例"""
        return self.lora_processor
    
    def get_status(self):
        """获取处理器状态"""
        return {
            'running': self.running,
            'queue_size': self.message_queue.qsize(),
            'lora_processor_running': self.lora_processor.running,
            'node_id': self.lora_processor.local_id,
            'node_type': self.lora_processor.sys_para['node_mod'],
            'link_status': self.lora_processor.link_sta
        }