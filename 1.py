#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import time
import threading
from typing import Dict, Optional
from enum import IntEnum

# �������ú����ݽṹ
from config import sys_para, node_para, local_id
from data_struct import send_con, Lora_send_data, Lora_recv_data

logger = logging.getLogger(__name__)

class MessageType:
    """��Ϣ���ͳ�������"""
    # LoRa��Ϣ����
    LORA_BROADCAST = 0x01          # ϵͳ�㲥��Ϣ
    LORA_REGISTER_REQ = 0x02       # ����ע������
    LORA_REGISTER_RSP = 0x03       # ����ע��Ӧ��
    LORA_NODE_CONTROL = 0x04       # �ڵ������Ϣ
    LORA_CLUSTER_OP = 0x05         # �ز�����Ϣ
    LORA_RANGING_REQ = 0x11        # ��������Ϣ
    LORA_RANGING_APPLY = 0x12      # ���������Ϣ
    LORA_RANGING_RSP = 0x13        # ���Ӧ����Ϣ
    LORA_INQUIRY = 0x20            # ѯ����Ϣ
    LORA_INQUIRY_RSP = 0x21        # ѯ��Ӧ����Ϣ
    LORA_TRAFFIC_DATA = 0x22       # ҵ��������Ϣ
    LORA_NODE_STATUS = 0x23        # �ڵ�״̬��Ϣ
    LORA_CLUSTER_STATUS = 0x25     # ��״̬��Ϣ
    LORA_PLATFORM_DATA = 0x26      # ƽ̨������Ϣ
    LORA_LINK_DATA = 0x27          # ��·������Ϣ
    LORA_MOTHER_SWITCH = 0x30      # ĸ���л���Ϣ
    LORA_MOTHER_ELECTION = 0x31    # ĸ��ѡ����Ϣ
    
    # ������Ϣ����
    CMD_SET_NODE_TYPE = 0x01       # ���ýڵ�����
    CMD_SET_NETWORK_CONFIG = 0x02  # �����������
    CMD_QUERY_STATUS = 0x03        # ��ѯ�ڵ�״̬
    CMD_START_NETWORK = 0x04       # ��������
    CMD_STOP_NETWORK = 0x05        # ֹͣ����
    
    # ������Ϣ����
    NETMGR_NETWORK_MGMT = 0x10     # ���������Ϣ
    NETMGR_NODE_CONFIG = 0x11      # �ڵ�������Ϣ
    NETMGR_DATA_FORWARD = 0x12     # ����ת����Ϣ

class LoRaProcessor:
    """LoRa������ - ����ԭ�д����߼�"""

    def __init__(self):
        # ȫ�ֱ�������
        self.send_con = send_con
        self.lora_send_data = Lora_send_data
        self.lora_recv_data = Lora_recv_data
        self.local_id = local_id
        self.sys_para = sys_para
        self.node_para = node_para
        
        # ״̬���� - ����ԭ������
        self.running = False
        self.send_thread = None
        self.mother_poll_sta = 0
        self.cluster_poll_sta = 0
        self.link_sta = 0
        self.recv_fram_num = 0
        self.recv_fram_err = 0
        self.second_count = 0
        self.time_out = 0
        self.netman_new_dat = False
    
    def start(self):
        """����LoRa������"""
        if self.running:
            logger.warning("LoRa��������������")
            return
        
        self.running = True
        self.send_thread = threading.Thread(target=self._lora_send_proc, daemon=True)
        self.send_thread.start()
        
        logger.info("LoRa�����������ɹ�")
    
    def stop(self):
        """ֹͣLoRa������"""
        if not self.running:
            return
        
        self.running = False
        if self.send_thread and self.send_thread.is_alive():
            self.send_thread.join(timeout=2.0)
        
        logger.info("LoRa��������ֹͣ")
    
    def _lora_send_proc(self):
        """LoRa���ʹ�����ѭ�� - ����ԭ���߼�"""
        while self.running:
            try:     
                if self.send_con.recv_send_en:  # ����������ҪӦ��
                    self._handle_received_message_response()
                elif send_con.unnormal_send_en:  # Ӧ������Ӧ��������ʱ����Ϊ����ע����Ϣ
                    self._handle_emergency_response()
                elif self.netman_new_dat:  # �������ݷ��ͣ��ص�����Ϣ+ҵ������+ĸ���л������ܷ���
                    self._handle_network_management_data()
                elif self.sys_para.net_mod == 6:  # ĸ�Ƕ�ʧģʽ,ǰ���ɸ��û��������ڣ���ʱ��ⷢ��
                    self._handle_mother_lost_mode()
                elif self.mother_poll_sta == 1:  # ĸ����ѵ������ϵͳ�㲥��Ϣ����Ҫ����ʱ�������
                    self._handle_mother_polling()
                elif self.mother_poll_sta == 2:  # ����ĸ�Ǳ���ҵ������
                    self._handle_mother_business_data()
                elif self.mother_poll_sta == 3:  # ���������ѯ
                    self._handle_cluster_head_polling()
                elif self.mother_poll_sta == 4:  # ����ڵ���ѯ
                    self._handle_node_polling()
                elif self.mother_poll_sta == 5:  # ����������
                    self._handle_ranging_operations()
                elif self.mother_poll_sta == 6:  # ����״̬��������
                    self._handle_status_parameter_setting()
                elif self.cluster_poll_sta == 1:  # ���׵Ĳ���
                    self._handle_cluster_business_data()
                elif self.cluster_poll_sta == 2:  # �ڵ���ѯ
                    self._handle_cluster_node_polling()
                elif self.cluster_poll_sta == 3:  # ���ô��׽ڵ�״̬�ϱ������Ϣ����Ӧ��
                    self._handle_cluster_status_aggregation()
                elif self.sys_para.net_mod in [0, 3]:  # ������ģʽ
                    self._handle_iot_mode()
                
                # �û��˳����
                self._user_exit_detection()
                
                # ��ֹCPUռ�ù���
                time.sleep(0.01)
                
            except Exception as e:
                logger.error(f"LoRa���ʹ������: {e}")
                time.sleep(0.1)

    def _handle_received_message_response(self):
        """�����������Ӧ�� - ����ԭ���߼�"""
        fram_type = self.send_con.fram_type
        
        if fram_type == 0x11:  # ���յ���������Ϣ������������
            self._build_ranging_request()
        elif fram_type == 0x12:  # ���յ�������룬���Ͳ��Ӧ����Ϣ
            self._build_ranging_response()
        elif fram_type == 0x13:  # ���յ����Ӧ����Ϣ�����в����Ϣ�ϱ�
            self._build_ranging_report()
        elif fram_type == 0x02:  # ���յ�ע����Ϣ
            self._build_register_response()
        elif fram_type == 0x03:  # ���յ�ע��Ӧ����Ϣ,���ճ�������
            self._lora_mac_ack(self.sys_para.mother_id)
        elif fram_type == 0x04:  # �ڵ�ģʽ������Ϣ������Ӧ��֡��ȷ�ϻ���״̬���ݣ������׵�״̬
            self._lora_mac_ack(self.sys_para.gateway_id)
        elif fram_type == 0x05:  # �ز�������������ҪӦ���ɽ��ս�������
            self._lora_mac_ack(self.sys_para.gateway_id)
        elif fram_type == 0x20:  # ѯ����Ϣ,�ڵ�Ӧ��
            self._handle_inquiry_message()
        elif fram_type == 0x23:  # ���յ��ڵ�״̬����
            self._handle_node_status_response()
        elif fram_type == 0x26:  # ������ģʽ���ս��յ�ƽ̨�����ϱ�,ĸ�ǽ���Ӧ�𣬷�������ģʽ�ɽ������Σ�
            self._handle_platform_data_response()
        elif fram_type == 0x27:  # ������ģʽ�·�����·״̬��Ϣ����ʱ����
            self._handle_link_status_response()
        elif fram_type == 0x30:  # ���յ�ĸ���л���Ϣ���н�������
            pass  # ����
        elif fram_type == 0x31:  # ĸ�Ƕ�ʧѡ��ģʽ
            self._handle_mother_election_response()
        else:
            logger.warning(f"δ�������Ϣ����: 0x{fram_type:02X}")
        
        self.send_con.recv_send_en = False

    def _build_ranging_request(self):
        """�������������Ϣ - ����ԭ���߼�"""
        self.lora_send_data.pay_len = 16
        self.lora_send_data.send_dat[0] = 0x12
        self.lora_send_data.send_dat[1] = 16
        self.lora_send_data.send_dat[2] = self.local_id
        self.lora_send_data.send_dat[3] = self.lora_recv_data.recv_dat[4]
        
        for i in range(4, 15):
            self.lora_send_data.send_dat[i] = 0
        
        self.send_lora_message(MessageType.LORA_RANGING_APPLY)
        logger.debug("���������Ͳ��������Ϣ")
    
    def _build_ranging_response(self):
        """�������Ӧ����Ϣ - ����ԭ���߼�"""
        self.lora_send_data.pay_len = 16
        self.lora_send_data.send_dat[0] = 0x13
        self.lora_send_data.send_dat[1] = 16
        self.lora_send_data.send_dat[2] = self.local_id
        self.lora_send_data.send_dat[3] = self.lora_recv_data.recv_dat[4]
        self.lora_send_data.send_dat[4] = 0  
        self.lora_send_data.send_dat[5] = 0  
        self.lora_send_data.send_dat[6] = 0  
        
        # ���ý���ʱ���
        recv_time = self.lora_recv_data.recv_time
        self.lora_send_data.send_dat[7] = (recv_time >> 24) & 0xff
        self.lora_send_data.send_dat[8] = (recv_time >> 16) & 0xff
        self.lora_send_data.send_dat[9] = (recv_time >> 8) & 0xff
        self.lora_send_data.send_dat[10] = recv_time & 0xff
        
        # ����ʱ�������FPGA����
        for i in range(11, 15):
            self.lora_send_data.send_dat[i] = 0
        
        self.send_lora_message(MessageType.LORA_RANGING_RSP)
        logger.debug("���������Ͳ��Ӧ����Ϣ")
    
    def _build_ranging_report(self):
        """������౨����Ϣ - ����ԭ���߼�"""
        # ��������
        temp2 = ((self.lora_recv_data.recv_dat[7] << 24) + 
                (self.lora_recv_data.recv_dat[8] << 16) + 
                (self.lora_recv_data.recv_dat[9] << 8) + 
                self.lora_recv_data.recv_dat[10])
        
        temp3 = ((self.lora_recv_data.recv_dat[11] << 24) + 
                (self.lora_recv_data.recv_dat[12] << 16) + 
                (self.lora_recv_data.recv_dat[13] << 8) + 
                self.lora_recv_data.recv_dat[14])
        
        temp = ((self.lora_recv_data.recv_time - self.lora_send_data.send_time) - 
                (temp3 - temp2)) >> 1
        
        self.lora_send_data.pay_len = 16
        self.lora_send_data.send_dat[0] = 0x13
        self.lora_send_data.send_dat[1] = self.lora_send_data.pay_len
        self.lora_send_data.send_dat[2] = self.local_id
        self.lora_send_data.send_dat[3] = self.lora_recv_data.recv_dat[4]
        self.lora_send_data.send_dat[4] = 0  # ��Ϣ��ű���
        self.lora_send_data.send_dat[5] = 0  # �����Ϣ���ͣ�����
        self.lora_send_data.send_dat[6] = 0  # Ԥ��
        
        self.lora_send_data.send_dat[7] = (temp >> 24) & 0xff
        self.lora_send_data.send_dat[8] = (temp >> 16) & 0xff
        self.lora_send_data.send_dat[9] = (temp >> 8) & 0xff
        self.lora_send_data.send_dat[10] = temp & 0xff
        
        for i in range(11, 15):
            self.lora_send_data.send_dat[i] = 0  # ����ʱ�������FPGA����
        
        self.send_lora_message(MessageType.LORA_RANGING_RSP)
        logger.debug("���������Ͳ�౨����Ϣ")
    
    def _build_register_response(self):
        """��������ע��Ӧ����Ϣ - ����ԭ���߼�"""
        self.lora_send_data.pay_len = 30
        self.lora_send_data.send_dat[0] = 0x03  # ����ע��Ӧ����Ϣ
        self.lora_send_data.send_dat[1] = 18
        self.lora_send_data.send_dat[2] = self.local_id
        self.lora_send_data.send_dat[3] = self.lora_recv_data.recv_dat[5]  # MAC��ַ
        self.lora_send_data.send_dat[4] = self.lora_recv_data.recv_dat[6]
        self.lora_send_data.send_dat[5] = self.lora_recv_data.recv_dat[7]
        self.lora_send_data.send_dat[6] = 2  # ��ͨ�ڵ�
        self.lora_send_data.send_dat[7] = 0  # ��ID��Ч
        self.lora_send_data.send_dat[8] = 0  # ����ID��Ч
        self.lora_send_data.send_dat[9] = 0  # �ڵ㳣̬ģʽ
        
        # �����ֶ���Ϊ��Ч
        for i in range(10, 16):
            self.lora_send_data.send_dat[i] = 0xff
        
        self.send_lora_message(MessageType.LORA_REGISTER_RSP)
        logger.debug("��������������ע��Ӧ����Ϣ")

    def _lora_mac_ack(self, dest_id: int):
        """����MAC��Ӧ�� - ����ԭ���߼�"""
        self.lora_send_data.pay_len = 9
        self.lora_send_data.send_dat[0] = 0x01  # ֡����
        self.lora_send_data.send_dat[1] = 0x09  # ���ݳ���
        self.lora_send_data.send_dat[2] = dest_id
        self.lora_send_data.send_dat[3] = self.local_id
        self.lora_send_data.send_dat[4] = self.send_con.fram_type  # Ӧ��֡����
        self.lora_send_data.send_dat[5] = 0x00
        self.lora_send_data.send_dat[6] = 0x01  # �϶�Ӧ��
        self.lora_send_data.send_dat[7] = 0x00  # CRC
        self.lora_send_data.send_dat[8] = 0x00
        
        self.send_lora_message(0x01)
        logger.debug(f"����MACӦ�𵽽ڵ�: {dest_id}")

    def _handle_inquiry_message(self):
        """����ѯ����Ϣ - ����ԭ���߼�"""
        # ����ѯ��Ӧ����Ϣ��������Ҫ������ľ���ʵ�ֲ��䣩
        logger.debug("����ѯ����Ϣ")
        # TODO: ������ԭʼ�����߼�

    def _handle_node_status_response(self):
        """����ڵ�״̬��Ӧ - ����ԭ���߼�"""
        # ������ģʽ��ĸ����ҪӦ��
        if (self.sys_para.net_mod < 6) and (self.sys_para.node_mod == 0):
            self._build_broadcast_message(getattr(self.send_con, 'currend_id', 0))
            if hasattr(self.send_con, 'netman_send_en'):
                self.send_con.netman_send_en = False
        logger.debug("����ڵ�״̬��Ӧ")
    
    def _handle_platform_data_response(self):
        """����ƽ̨������Ӧ - ����ԭ���߼�"""
        # ������ģʽ��ĸ����ҪӦ��
        if (self.sys_para.net_mod < 6) and (self.sys_para.node_mod == 0):
            self._build_broadcast_message(getattr(self.send_con, 'currend_id', 0))
            if hasattr(self.send_con, 'netman_send_en'):
                self.send_con.netman_send_en = False
        logger.debug("����ƽ̨������Ӧ")
    
    def _handle_link_status_response(self):
        """������·״̬��Ӧ - ����ԭ���߼�"""
        # ������ģʽ��ĸ����ҪӦ��
        if (self.sys_para.net_mod < 6) and (self.sys_para.node_mod == 0):
            self._build_broadcast_message(getattr(self.send_con, 'currend_id', 0))
            if hasattr(self.send_con, 'netman_send_en'):
                self.send_con.netman_send_en = False
        logger.debug("������·״̬��Ӧ")

    def _handle_mother_election_response(self):
        """����ĸ��ѡ����Ӧ - ����ԭ���߼�"""
        if self.lora_recv_data.recv_dat[2] == self.local_id - 1:  # ��һ���������ݵ�ǰһ��ID
            self.lora_send_data.pay_len = 14
            self.lora_send_data.send_dat[0] = 0x1A
            self.lora_send_data.send_dat[1] = 14
            self.lora_send_data.send_dat[2] = self.local_id
            self.lora_send_data.send_dat[3] = 0
            self.lora_send_data.send_dat[4] = 234  # �������ר�ŵ���Ը�㷨
            self.lora_send_data.send_dat[5] = self.node_para.node_ability
            
            # ���̶�ֵ
            fixed_values = [0x12, 0x34, 0x56, 0x78, 0x90, 0xef]
            for i, val in enumerate(fixed_values):
                if i + 6 < 12:
                    self.lora_send_data.send_dat[i + 6] = val
            
            self.send_lora_message(MessageType.LORA_MOTHER_ELECTION)
        elif self.local_id > self.lora_recv_data.recv_dat[2]:
            self.time_out = (self.local_id - self.lora_recv_data.recv_dat[3]) * 100  # ��ʱ���
        
        logger.debug("����ĸ��ѡ����Ӧ")

    def _handle_emergency_response(self):
        """����Ӧ������Ӧ��������ʱ����Ϊ����ע����Ϣ"""
        if self.link_sta == 1:  # �û��ѻ��ϵͳͬ������������
            self._build_network_registration_request()
            self.link_sta = 2
        elif self.node_data['paload_unnormal']:  # �غ��쳣����
            self._build_abnormal_payload_data()

    def _build_abnormal_payload_data(self):
        """�����쳣�غ�����"""
        self.lora_send_data.pay_len = 18
        self.lora_send_data.send_dat[0] = 0x26  # ƽ̨������Ϣ����
        self.lora_send_data.send_dat[1] = 11    # ���ݳ���
        self.lora_send_data.send_dat[2] = self.lora_recv_data.recv_dat[3]  # ��ȡĿ�ĵ�ַ
        self.lora_send_data.send_dat[3] = self.local_id                   # Դ��ַ
        self.lora_send_data.send_dat[4] = 2     # �쳣��־
    
        # ����غ�����
        payload_data = self.node_data.get('payload_data', [])
        for i in range(5, 18):
            self.lora_send_data.send_dat[i] = (
                payload_data[i] if i < len(payload_data) else 0
            )
    
        self.send_lora_message(0x26)  # LORA_PLATFORM_DATA
        self.node_data['paload_unnormal'] = False
        logger.debug("�����쳣�غ�����")

    def _handle_network_management_data(self):
        """���������������"""
        data_length = self.netman_recv_dat[1]
        self.lora_send_data.pay_len = data_length
    
        # �����������ݵ����ͻ�����
        for i in range(data_length):
            self.lora_send_data.send_dat[i] = self.netman_recv_dat[i]
    
        # ҵ�����ݰ�����ϣ�֪ͨ���ط����µ�ҵ��
        self.netman_new_dat = False
        logger.debug("���������������")

    def _handle_mother_lost_mode(self):
        """����ĸ�Ƕ�ʧģʽ"""
        timeout_threshold = self.lora_recv_data.recv_ok_time + self.time_out
    
        if self.second_count > timeout_threshold:
            # ����ĸ��ѡ����Ϣ
            self.lora_send_data.pay_len = 14
            self.lora_send_data.send_dat[0] = 0x31  # ĸ��ѡ����Ϣ
            self.lora_send_data.send_dat[1] = 14    # ��Ϣ����
            self.lora_send_data.send_dat[2] = self.local_id  # ԴID
            self.lora_send_data.send_dat[3] = 0     # Ŀ��ID
            self.lora_send_data.send_dat[4] = 234   # �������ר�ŵ���Ը�㷨
            self.lora_send_data.send_dat[5] = self.node_para.node_ability
        
            # ���̶���ʶֵ
            fixed_values = [0x12, 0x34, 0x56, 0x78, 0x90, 0xef]
            for i, val in enumerate(fixed_values):
                if i + 6 < 12:
                    self.lora_send_data.send_dat[i + 6] = val
        
            self.send_lora_message(0x31)  # LORA_MOTHER_ELECTION
            logger.debug("����ĸ�Ƕ�ʧģʽ")

    def _handle_mother_polling(self):
        """����ĸ����ѯ������ϵͳ�㲥��Ϣ"""
        self._build_broadcast_message(0x00)
        self.mother_poll_sta = 2  # �л���״̬2�����ͱ���ҵ��

    def _build_broadcast_message(self, target_id: int):
        """�����㲥��Ϣ"""
        # ������+�͹���ģʽ��ĸ�ǵ�ַ��0,0ʱ϶���͹㲥��Ϣ�����򲻴���0��ID�û�
        if self.sys_para.net_mod < 6:
            if target_id == 0:
                # ʱ�������
                if ((self.next_base_time - self.second_count < 1) and 
                    self.mil_sec_count > 995):
                    self.sys_base_time = self.next_base_time
                    self.sys_time_offset = 0
                    self.next_base_time += self.sys_para.sys_fram_period  # ������һ��ʱ���׼
                    self.lora_send_data.send_time = 0
                else:
                    return
            else:  # 10ms����
                self.sys_time_offset = self.mil_sec_count // 10 + 1
                if self.sys_time_offset < 100:
                    temp = self.second_count
                else:
                    self.sys_time_offset -= 100
                    temp = self.second_count + 1
            
                self.lora_send_data.send_time = self.sys_time_offset * 400000
                self.sys_time_offset = (temp << 8) + (self.sys_time_offset & 0xff)
        else:  # 10ms����
            self.sys_time_offset = self.mil_sec_count // 10 + 1
            if self.sys_time_offset < 100:
                self.sys_base_time = self.second_count
            else:
                self.sys_time_offset -= 100
                self.sys_base_time = self.second_count + 1
        
            self.lora_send_data.send_time = self.sys_time_offset * 400000
    
        # �����㲥��Ϣ����
        self.lora_send_data.pay_len = 29
        self.lora_send_data.send_dat[0] = 0x00  # �㲥��Ϣ
        self.lora_send_data.send_dat[1] = 29    # ����
    
        # ����ID
        self.lora_send_data.send_dat[2] = (self.sys_para.net_id >> 8) & 0xff
        self.lora_send_data.send_dat[3] = self.sys_para.net_id & 0xff
        self.lora_send_data.send_dat[4] = 0     # Ŀǰ��֧��ĸ�Ƿ���
    
        # ʱ��ͬ����Ϣ
        self.lora_send_data.send_dat[5] = (self.sys_base_time >> 8) & 0xff
        self.lora_send_data.send_dat[6] = self.sys_base_time & 0xff
        self.lora_send_data.send_dat[7] = (self.sys_time_offset >> 16) & 0xff
        self.lora_send_data.send_dat[8] = (self.sys_time_offset >> 8) & 0xff
        self.lora_send_data.send_dat[9] = self.sys_time_offset & 0xff
    
        # �����������
        self.lora_send_data.send_dat[10] = (self.sys_para.net_mod + 
                                           (self.sys_para.sig_det_time << 4))
    
        # ת��ģʽ����
        if self.sys_para.convert_mod & 0x60:
            self.sys_para.convert_mod -= 0x10
        else:
            self.sys_para.convert_mod = 0
    
        self.lora_send_data.send_dat[11] = (self.sys_para.convert_mod + 
                                           (self.sys_para.sys_sig_mod << 7))
    
        # Ƶ�ʺͱ������
        self.lora_send_data.send_dat[12] = (self.sys_para.fre_backw >> 8) & 0xff
        self.lora_send_data.send_dat[13] = self.sys_para.fre_backw & 0xff
        self.lora_send_data.send_dat[14] = (self.sys_para.SF_base_backw + 
                                           (self.sys_para.bw_backw << 4) + 
                                           (self.sys_para.cr_backw << 6))
        self.lora_send_data.send_dat[15] = (self.sys_para.clust_bw_forw + 
                                           (self.sys_para.clust_bw_backw << 4))
        self.lora_send_data.send_dat[16] = ((self.sys_para.clust_bw_backw << 4) + 
                                           (self.sys_para.clust_cr_backw << 6))
    
        # ϵͳ����
        self.lora_send_data.send_dat[17] = (self.sys_para.sys_fram_period >> 8) & 0xff
        self.lora_send_data.send_dat[18] = self.sys_para.sys_fram_period & 0xff
        self.lora_send_data.send_dat[19] = self.sys_para.burst_time_base
        self.lora_send_data.send_dat[20] = self.sys_para.perm_period
        self.lora_send_data.send_dat[21] = self.sys_para.node_sta_det
        self.lora_send_data.send_dat[22] = self.sys_para.node_num
        self.lora_send_data.send_dat[23] = self.sys_para.max_id
        self.lora_send_data.send_dat[24] = target_id
        self.lora_send_data.send_dat[25] = 0
        self.lora_send_data.send_dat[26] = 0
    
        # ���÷���ʱ��
        self.lora_send_data.send_time_en = True
        send_time = locals().get('temp', self.second_count)
        self.lora_send_data.send_time = send_time
    
        self.send_lora_message(0x00)  # LORA_BROADCAST
        logger.debug(f"���������͹㲥��Ϣ��Ŀ��ID: {target_id}")

    def _handle_mother_business_data(self):
        """����ĸ�Ǳ���ҵ������"""
        if self.traffic_data['traffic_pack']:
            self.traffic_send_en = True
        
            if self.traffic_data['traffic_pack'] == self.traffic_data['data_num']:
                # ���ݷ������
                self.traffic_data['traffic_pack'] = 0
                self.poll_node_id = 0
                self.poll_cluster_id = 0
            
                if self.sys_para.net_mod == 7:  # ���������ҪӦ������Ҫ����λ��
                    self.mother_poll_sta = 3  # ���׵���ģʽ
                else:
                    self.mother_poll_sta = 4
                self.send_con['poll_ok'] = True
        
            # ����ҵ������
            data_length = self.lora_send_data.pay_len - 2
            for i in range(data_length):
                self.lora_send_data.send_dat[i] = self.traffic_data['traffic_dat'][i]
    
        logger.debug("����ĸ�Ǳ���ҵ������")

    def _handle_cluster_head_polling(self):
        """���������ѯ"""
        if self.send_con['poll_ok']:  # ���ʹ���ѯ��Ϣ
            if self.poll_node_id == 1:  # �������Ӧ��ʱ϶
                self.poll_node_id = 0
                self._build_emergency_slot_message()
                self.send_con['poll_ok'] = False
            elif self.poll_cluster_id < self.sys_para.clust_numb:
                self._build_cluster_poll_message()
                self.send_con['poll_ok'] = False
                self.poll_cluster_id += 1
                self.poll_node_id += 1
            else:
                self.mother_poll_sta = 5  # �л�����������Ԫ

    def _handle_node_polling(self):
        """����ڵ���ѯ"""
        if self.send_con['poll_ok']:
            while True:
                if self.neighbor_node_sta[self.poll_node_id].node_sta == 2:  # �ڵ���������
                    if self.poll_cluster_id == self.sys_para.perm_period:
                        self.poll_cluster_id = 0
                        self._build_emergency_slot_message()
                        break
                    else:
                        self._build_node_poll_message()
                        break
                else:
                    self.poll_node_id += 1
                    if self.poll_node_id >= 0x7e:  # �ﵽ���ڵ�ID
                        self.mother_poll_sta = 5  # �л�����������Ԫ
                        break

    def _handle_ranging_operations(self):
        """���������"""
        if self.send_con['poll_ok']:
            while True:
                if self.distanc_sta[self.poll_node_id].node_dis_en:  # �жϽڵ��Ƿ���Ҫ���
                    break
                self.poll_node_id += 1
                if self.poll_node_id > 0x7e:  # �ﵽ���ڵ�ID
                    self.mother_poll_sta = 6  # �л���״̬���ò�����Ԫ
                    break
        
            if (self.poll_node_id <= 0x7e and 
                self.distanc_sta[self.poll_node_id].node_dis_en):
                self._build_ranging_command()

    def _handle_status_parameter_setting(self):
        """����״̬��������"""
        if self.send_con['poll_ok']:
            while True:
                if self.node_ope_sta[self.poll_node_id].node_ope_en:  # �жϽڵ��Ƿ���Ҫ����
                    break
                self.poll_node_id += 1
                if self.poll_node_id > 0x7e:  # �ﵽ���ڵ�ID
                    self.mother_poll_sta = 1  # ���ݲ�����ɣ������µ�����
                    break
        
            if (self.poll_node_id <= 0x7e and 
                self.node_ope_sta[self.poll_node_id].node_ope_en):
                self._build_status_setting_command()

    def _handle_cluster_business_data(self):
        """�������ҵ������"""
        if self.traffic_data['traffic_pack']:
            self.traffic_send_en = True
        
            if self.traffic_data['traffic_pack'] == self.traffic_data['data_num']:
                self.traffic_data['traffic_pack'] = 0
                self.cluster_poll_sta = 2  # ҵ�����ݷ�����ɣ��л�����ѯ״̬
            else:
                self.lora_send_data.pay_len = self.traffic_data['traffic_dat'][1]
            
                # ����ҵ������
                for i in range(self.lora_send_data.pay_len):
                    self.lora_send_data.send_dat[i] = self.traffic_data['traffic_dat'][i]
            
                self.send_con['poll_ok'] = False
                self.traffic_data['data_num'] += 1
    
        logger.debug("�������ҵ������")

    def _handle_cluster_node_polling(self):
        """������׽ڵ���ѯ"""
        if self.send_con['poll_ok']:
            while True:
                if self.poll_node_id < len(self.sys_para.clust_node_id):
                    cluster_node_id = self.sys_para.clust_node_id[self.poll_node_id]
                    if self.neighbor_node_sta[cluster_node_id].node_sta:  # �жϽڵ��Ƿ�����
                        break
                self.poll_node_id += 1
                if self.poll_node_id > 0x7e:  # �ﵽ���ڵ�ID
                    self.cluster_poll_sta = 3  # �л���״̬��۲���
                    break
        
            if (self.poll_node_id <= 0x7e and 
                self.poll_node_id < len(self.sys_para.clust_node_id)):
                self._build_cluster_node_poll_message()

    def _handle_cluster_status_aggregation(self):
        """�������״̬���"""
        self.lora_send_data.send_dat[0] = 0x25  # ��״̬��Ϣ
        self.lora_send_data.send_dat[2] = self.sys_para.mother_id  # Ŀ��ĸ��ID
        self.lora_send_data.send_dat[3] = self.local_id            # ԴID
        self.lora_send_data.send_dat[4] = self.sys_para.clust_numb # �ؽڵ���
        self.lora_send_data.send_dat[5] = self.local_id            # �ڵ�ID
        self.lora_send_data.send_dat[6] = 0xf                      # ���ڵ�״̬
    
        # �����ڽڵ�״̬
        data_index = 8
        for i in range(1, self.sys_para.clust_numb):
            if i < len(self.sys_para.clust_node_id):
                cluster_node_id = self.sys_para.clust_node_id[i]
                self.lora_send_data.send_dat[data_index] = cluster_node_id  # �ڵ�ID
                node_health_status = self.neighbor_node_sta[cluster_node_id].node_healty_sta
                self.lora_send_data.send_dat[data_index + 1] = node_health_status  # �ڵ�״̬
                data_index += 2
    
        # ����ڵ�ѯ��״̬
        self.node_ask_sta[0].node_opedata = self.node_ask_sta[0].node_opedata >> 1
        data_index += 2
    
        # ����֡���ݳ���
        self.lora_send_data.pay_len = data_index
        self.lora_send_data.send_dat[1] = self.lora_send_data.pay_len
    
        self.send_lora_message(0x25)  # LORA_CLUSTER_STATUS
        self.cluster_poll_sta = 0  # ���׷���Ӧ�𣬽�����ǰ��ѯ
        logger.debug("��������״̬�����Ϣ")

    def _handle_iot_mode(self):
        """����������ģʽ"""
        if self.sys_para.node_mod == 0:  # ĸ��
            self._build_broadcast_message(0x00)  # ĸ�Ƿ��͹㲥��Ϣ��ϵͳ��Ĭ��Ǳ��
        elif self.link_sta == 4:  # �����ڵ�
            self._handle_node_periodic_transmission()
        elif self.link_sta == 2:  # �Ѿ����ͬ������������ע����Ϣ
            self._build_network_registration_request()

    def _handle_node_periodic_transmission(self):
        """����ڵ������Դ���"""
        transmission_time = self.sys_base_time + self.local_id * 5
    
        if self.second_count > transmission_time:
            if self.node_data['node_period']:  # ���ͽڵ�״̬
                if transmission_time < self.second_count:
                    transmission_time += self.node_data['node_period']
                
                    # �����ڵ�״̬��Ϣ
                    self.lora_send_data.pay_len = 27  # ���ݳ���
                    self.lora_send_data.send_dat[0] = 0x23  # ֡���ͣ��ڵ�״̬
                
                    # ���ڵ�����
                    node_data = self.node_data.get('node_data', [])
                    for i in range(4, 25):
                        self.lora_send_data.send_dat[i] = (
                            node_data[i] if i < len(node_data) else 0
                        )
                
                    self.send_lora_message(0x23)  # LORA_NODE_STATUS
            
                # ����Ƿ���Ҫ������������
                if (self.lora_send_data.pay_len and 
                    self.node_data['sat_period'] and 
                    self.node_data['sat_time'] < self.second_count):
                    self._build_satellite_data()
            
                # ����Ƿ���Ҫ�����غ�����
                if (self.lora_send_data.pay_len == 0 and 
                    self.node_data['paload_period'] and 
                    self.node_data['paload_time'] < self.second_count):
                    self._build_payload_data()

    def _build_network_registration_request(self):
        """��������ע��������Ϣ"""
        self.lora_send_data.pay_len = 30
        self.lora_send_data.send_dat[0] = 0x02  # ����ע����Ϣ
        self.lora_send_data.send_dat[1] = 30    # ��Ϣ����
    
        # ����ID
        self.lora_send_data.send_dat[2] = (self.sys_para.net_id >> 8) & 0xff
        self.lora_send_data.send_dat[3] = self.sys_para.net_id & 0xff
    
        # �ڵ���Ϣ
        self.lora_send_data.send_dat[4] = self.local_id                    # ����ID
        self.lora_send_data.send_dat[5] = self.node_para.node_ability      # �ڵ�����
        self.lora_send_data.send_dat[6] = self.node_para.Freq_range        # Ƶ�ʷ�Χ
        self.lora_send_data.send_dat[7] = self.node_para.max_Pow           # �����
        self.lora_send_data.send_dat[8] = self.node_para.Pow_att           # ����˥��
    
        # �ռ����� (ÿ������3�ֽ�)
        coordinates = [
            ('locat_x', 9),   # X���꣬����9-11
            ('locat_y', 12),  # Y���꣬����12-14  
            ('locat_z', 15)   # Z���꣬����15-17
        ]
    
        for coord_name, base_index in coordinates:
            coord_value = getattr(self.node_para, coord_name)
            self.lora_send_data.send_dat[base_index] = (coord_value >> 16) & 0xff
            self.lora_send_data.send_dat[base_index + 1] = (coord_value >> 8) & 0xff
            self.lora_send_data.send_dat[base_index + 2] = coord_value & 0xff
    
        # ��ȫ���� (6�ֽ�)
        security_data = [0x12, 0x34, 0x56, 0x78, 0x34, 0x56]
        for i, value in enumerate(security_data):
            self.lora_send_data.send_dat[18 + i] = value
    
        self.send_lora_message(0x02)  # LORA_REGISTER_REQ
        self.link_sta = 2
        logger.debug("��������ע��������Ϣ")

    def _user_exit_detection(self):
        """�û��˳����"""
        # �͹���+������ģʽ
        if self.sys_para.net_mod in [0, 3]:
            if self.second_count > self.next_base_time:
                self.next_base_time = self.sys_base_time + self.sys_para.sys_fram_period
            
                if self.local_id == self.sys_para.mother_id:
                    self._user_exit_detection_main()  # ĸ�Ǽ��
                else:
                    self._user_exit_detection_user()  # �û��ڵ���
    
        # ĸ�Ƕ�ʧģʽ����׵���ģʽ
        elif self.sys_para.net_mod in [6, 7]:
            if self.local_id == self.sys_para.mother_id:
                if self.mother_poll_sta == 1:
                    self._user_exit_detection_main()  # ĸ����ѯ״̬ʱ���
            else:
                if self.second_count > self.next_base_time:
                    self.next_base_time = self.sys_base_time + self.sys_para.sys_fram_period
                    self._user_exit_detection_user()  # �û��ڵ㶨�ڼ��

    def get_node_status(self) -> Dict:
        """��ȡ�ڵ�״̬��Ϣ����main.py�еĽӿڶ�Ӧ��"""
        return {
            'local_id': self.local_id,
            'node_mod': self.sys_para.node_mod,
            'net_mod': self.sys_para.net_mod,
            'link_sta': self.link_sta,
            'mother_id': self.sys_para.mother_id,
            'cluster_id': self.sys_para.clust_id,
            'running': self.running,
            'recv_fram_num': self.recv_fram_num,
            'recv_fram_err': self.recv_fram_err,
            'second_count': self.second_count,
            'mother_poll_sta': self.mother_poll_sta,
            'cluster_poll_sta': self.cluster_poll_sta
        }

# ʹ��ʾ��
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # ����LoRa������
    lora_processor = LoRaProcessor()
    
    try:
        # ����������
        lora_processor.start()
        
        logger.info("LoRa�����������У���Ctrl+C�˳�...")
        while True:
            time.sleep(1)
            # ��ʾ��ǰ״̬
            status = lora_processor.get_node_status()
            if status['second_count'] % 10 == 0 and status['second_count'] > 0:
                logger.info(f"����״̬: ����֡={status['recv_fram_num']}, "
                           f"����֡={status['recv_fram_err']}, "
                           f"����ʱ��={status['second_count']}s")
    
    except KeyboardInterrupt:
        logger.info("�յ��˳��ź�")
    finally:
        lora_processor.stop()
        logger.info("LoRa��������ֹͣ")