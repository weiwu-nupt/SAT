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
    """��Ϣ������"""
    
    def __init__(self, message_queue: queue.Queue):
        self.message_queue = message_queue
        self.running = False
        self.thread = None
        
        # ��ʼ��LoRa������
        self.lora_processor = LoRaProcessor()
        
        # �洢UDP���������ã����ڷ�����Ϣ
        self.udp_servers = {}
        
    def set_udp_servers(self, servers: Dict[MessageSource, 'UDPServer']):
        """����UDP����������"""
        self.udp_servers = servers
        
        # ����LoRa����������Ϣ���ͽӿ�
        def send_message(target_addr, msg_type, content):
            if MessageSource.LORA in self.udp_servers:
                self.udp_servers[MessageSource.LORA].send_message(target_addr, msg_type, content)
        
        self.lora_processor.set_message_sender(send_message)
        
        # ������Ӧ������
        self._response_server = self.udp_servers.get(MessageSource.HOST_SOFTWARE)
        
    def start(self):
        """������Ϣ������"""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._process_messages, daemon=True)
        self.thread.start()
        
        # ����LoRa������
        self.lora_processor.start()
        
        logging.info("��Ϣ������������")
    
    def stop(self):
        """ֹͣ��Ϣ������"""
        self.running = False
        
        # ֹͣLoRa������
        self.lora_processor.stop()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        logging.info("��Ϣ��������ֹͣ")
    
    def set_node_type(self, node_type: str):
        """���ýڵ�����"""
        self.lora_processor.set_node_type(node_type)
    
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
        logging.info(f"������λ����Ϣ: ����=0x{message.msg_type:02X}, "
                    f"����={len(message.data)} bytes from {message.addr}")
        
        try:
            if message.msg_type == MessageType.CMD_SET_NODE_TYPE:  # ���ýڵ�����
                if len(message.data) >= 1:
                    node_type = message.data[0]
                    if node_type == 0x00:
                        self.lora_processor.set_node_type("mother")
                    elif node_type == 0x01:
                        self.lora_processor.set_node_type("cluster")
                        self.lora_processor.set_node_type("normal")
                    
                    # ����ȷ����Ϣ
                    self._send_response(message.addr, MessageType.CMD_SET_NODE_TYPE, b'\x00')
                    
            elif message.msg_type == MessageType.CMD_SET_NETWORK_CONFIG:  # �����������
                self._handle_network_config(message.data)
                self._send_response(message.addr, MessageType.CMD_SET_NETWORK_CONFIG, b'\x00')
                
            elif message.msg_type == MessageType.CMD_QUERY_STATUS:  # ��ѯ�ڵ�״̬
                self._send_node_status(message.addr)
                
            elif message.msg_type == MessageType.CMD_START_NETWORK:  # ��������
                self.lora_processor.link_sta = 1
                self._send_response(message.addr, MessageType.CMD_START_NETWORK, b'\x00')
                
            elif message.msg_type == MessageType.CMD_STOP_NETWORK:  # ֹͣ����
                self.lora_processor.link_sta = 0
                self._send_response(message.addr, MessageType.CMD_STOP_NETWORK, b'\x00')
                
            else:
                logging.warning(f"δ֪��λ������: 0x{message.msg_type:02X}")
                
        except Exception as e:
            logging.error(f"������λ����Ϣʧ��: {e}")
        
    def _handle_gateway_message(self, message: UDPMessage):
        """����������Ϣ"""
        logging.info(f"����������Ϣ: ����=0x{message.msg_type:02X}, "
                    f"����={len(message.data)} bytes from {message.addr}")
        
        try:
            if message.msg_type == MessageType.NETMGR_NETWORK_MGMT:  # ���������Ϣ
                self._handle_network_management(message.data)
                
            elif message.msg_type == MessageType.NETMGR_NODE_CONFIG:  # �ڵ�������Ϣ
                self._handle_node_configuration(message.data)
                
            elif message.msg_type == MessageType.NETMGR_DATA_FORWARD:  # ����ת����Ϣ
                self._handle_data_forwarding(message.data)
                
            else:
                logging.warning(f"δ֪������Ϣ����: 0x{message.msg_type:02X}")
                
        except Exception as e:
            logging.error(f"����������Ϣʧ��: {e}")
        
    def _handle_lora_message(self, message: UDPMessage):
        """����LoRa��Ϣ"""
        logging.info(f"����LoRa��Ϣ: ����=0x{message.msg_type:02X}, "
                    f"����={len(message.data)} bytes from {message.addr}")
        
        try:
            # ����Ϣ����ת��Ϊ�б��ʽ������ԭʼLoRa�����߼�
            recv_data = [message.msg_type] + [len(message.data) + 4] + list(message.data)
            
            # ����LoRa�������Ľ�������
            self.lora_processor.lora_recv_data['recv_dat'] = recv_data
            self.lora_processor.lora_recv_data['recv_time'] = int(message.timestamp.timestamp() * 1000)
            
            # ����Ӧ���־
            self.lora_processor.send_con['recv_send_en'] = True
            self.lora_processor.send_con['fram_type'] = message.msg_type
            
            logging.debug(f"����LoRa֡: ����=0x{message.msg_type:02X}, ����Ӧ����")
            
        except Exception as e:
            logging.error(f"����LoRa��Ϣʧ��: {e}")
    
    def _send_response(self, target_addr: tuple, msg_type: int, content: bytes):
        """������Ӧ��Ϣ"""
        try:
            # ���Ҷ�Ӧ��UDP������������Ӧ
            if self._response_server:
                self._response_server.send_message(target_addr, msg_type, content)
            else:
                logging.warning("�޷�������Ӧ��δ�ҵ���Ӧ������")
        except Exception as e:
            logging.error(f"������Ӧʧ��: {e}")
    
    def _send_node_status(self, target_addr: tuple):
        """���ͽڵ�״̬"""
        try:
            # ����״̬����
            lora_processor = self.lora_processor
            status_data = struct.pack('BBBBBB',
                lora_processor.local_id,           # �ڵ�ID
                lora_processor.sys_para['node_mod'], # �ڵ�����
                lora_processor.link_sta,           # ��·״̬
                lora_processor.sys_para['mother_id'], # ĸ��ID
                lora_processor.sys_para['net_mod'],  # ����ģʽ
                self.message_queue.qsize()         # ���д�С
            )
            
            self._send_response(target_addr, MessageType.CMD_QUERY_STATUS, status_data)
            logging.info(f"���ͽڵ�״̬�� {target_addr}")
            
        except Exception as e:
            logging.error(f"���ͽڵ�״̬ʧ��: {e}")
    
    def _handle_network_config(self, config_data: bytes):
        """������������"""
        if len(config_data) >= 4:
            net_id = config_data[0]
            mother_id = config_data[1]
            gateway_id = config_data[2]
            local_id = config_data[3]
            
            # ����LoRa����������
            self.lora_processor.sys_para['net_id'] = net_id
            self.lora_processor.sys_para['mother_id'] = mother_id
            self.lora_processor.sys_para['gateway_id'] = gateway_id
            self.lora_processor.local_id = local_id
            
            logging.info(f"������������: ����ID={net_id}, ĸ��ID={mother_id}, ����ID={local_id}")
    
    def _handle_network_management(self, data: bytes):
        """�������������Ϣ"""
        if len(data) >= 1:
            mgmt_cmd = data[0]
            if mgmt_cmd == 0x01:  # ��������
                self.lora_processor.link_sta = 1
                logging.info("�������: ��������")
            elif mgmt_cmd == 0x02:  # ֹͣ����
                self.lora_processor.link_sta = 0
                logging.info("�������: ֹͣ����")
            elif mgmt_cmd == 0x03:  # ĸ��ѡ��
                self.lora_processor.sys_para['net_mod'] = 6
                logging.info("�������: ����ĸ��ѡ��")
    
    def _handle_node_configuration(self, data: bytes):
        """����ڵ�����"""
        if len(data) >= 4:
            node_id = data[0]
            operation = data[1]
            param1 = data[2]
            param2 = data[3]
            
            logging.info(f"�ڵ�����: ID={node_id}, ����={operation}")
    
    def _handle_data_forwarding(self, data: bytes):
        """��������ת��"""
        if len(data) >= 2:
            target_id = data[0]
            data_len = data[1]
            
            if len(data) >= 2 + data_len:
                # �����������ݷ���
                self.lora_processor.netman_recv_dat = list(data[:2+data_len])
                self.lora_processor.netman_new_dat = True
                
                logging.info(f"����ת��: Ŀ��ID={target_id}, ���ݳ���={data_len}")
    
    def get_lora_processor(self):
        """��ȡLoRa������ʵ��"""
        return self.lora_processor
    
    def get_status(self):
        """��ȡ������״̬"""
        return {
            'running': self.running,
            'queue_size': self.message_queue.qsize(),
            'lora_processor_running': self.lora_processor.running,
            'node_id': self.lora_processor.local_id,
            'node_type': self.lora_processor.sys_para['node_mod'],
            'link_status': self.lora_processor.link_sta
        }