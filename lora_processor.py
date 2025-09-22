#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import threading
import logging
import time
from protocol import MessageType


class LoRaProcessor:
    """LoRa��Ϣ������ - ��������ģʽ�Ĵ����߼�"""
    
    def __init__(self, message_sender=None):
        self.running = False
        self.thread = None
        self.message_sender = message_sender  # ��Ϣ���ͽӿ�
        
        # ��ʼ��ϵͳ����
        self.sys_para = {
            'net_mod': 0,  # ����ģʽ: 0-��������ʽ��6-ĸ�Ƕ�ʧģʽ��7-���׵���ģʽ
            'node_mod': 2,  # �ڵ�ģʽ: 0-ĸ�ǣ�1-���ף�2-��ͨ�ڵ�
            'mother_id': 0,  # ĸ��ID�̶�Ϊ0
            'gateway_id': 0xFE,  # ����ID
            'clust_id': 0x80,  # ����ID
            'clust_numb': 0,  # ���ڽڵ���
        }
        
        # ��ʼ���ڵ����
        self.local_id = 0x10  # �����ڵ�ID������ͨ�������ļ�����
        
        # ���Ϳ���״̬
        self.send_con = {
            'recv_send_en': False,
            'fram_type': 0,
            'unnormal_send_en': False,
            'netman_send_en': False,
            'poll_ok': True,
            'currend_id': 0
        }
        
        # LoRa�������ݽṹ
        self.lora_send_data = {
            'pay_len': 0,
            'send_dat': [0] * 256,
            'send_time': 0,
            'send_time_stamp': 0
        }
        
        # LoRa�������ݽṹ
        self.lora_recv_data = {
            'recv_dat': [0] * 256,
            'recv_time': 0,
            'recv_ok_time': 0
        }
        
        # �ڵ�״̬
        self.link_sta = 0  # 0-���У�1-�ź�������2-���ͬ����3-����������Ϣ��4-�������
        self.mother_poll_sta = 1  # ĸ����ѯ״̬
        self.cluster_poll_sta = 0  # ������ѯ״̬
        self.traffic_send_en = False
        
        # ʱ�����
        self.second_count = 0
        self.sys_base_time = 0
        
        # ��ѯ���
        self.poll_node_id = 0
        self.poll_cluster_id = 0
        
        # �����������
        self.netman_new_dat = False
        self.netman_recv_dat = [0] * 1024
        
        # ҵ������
        self.traffic_data = {
            'traffic_pack': 0,
            'data_num': 0,
            'traffic_dat': [0] * 1024
        }
        
        # �ڵ�����
        self.node_data = {
            'node_data': [0] * 32,
            'node_period': 60,  # �ڵ�״̬�����ϱ�����(��)
            'paload_unnormal': False,
            'sat_data': [0] * 32,
            'sat_period': 300,  # ����״̬�����ϱ�����(��)
            'sat_time': 0,
            'payload_data': [0] * 32,
            'paload_period': 120,  # �غ������ϱ�����(��)
            'paload_time': 0
        }
    
    def set_message_sender(self, sender):
        """������Ϣ���ͽӿ�"""
        self.message_sender = sender
    
    def start(self):
        """����LoRa������"""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._lora_send_proc, daemon=True)
        self.thread.start()
        logging.info("LoRa������������")
    
    def stop(self):
        """ֹͣLoRa������"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        logging.info("LoRa��������ֹͣ")
    
    def set_node_type(self, node_type: str):
        """���ýڵ�����"""
        if node_type == "mother":
            self.sys_para['node_mod'] = 0
            self.local_id = 0  # ĸ��ID�̶�Ϊ0
            logging.info("�ڵ���������Ϊ��ĸ�� (ID=0)")
        elif node_type == "cluster":
            self.sys_para['node_mod'] = 1  
            self.local_id = self.sys_para['clust_id']
            logging.info("�ڵ���������Ϊ������")
        else:
            self.sys_para['node_mod'] = 2
            logging.info("�ڵ���������Ϊ����ͨ�ڵ�")
    
    def send_lora_message(self, msg_type: int, target_addr: tuple = None):
        """����LoRa��Ϣ"""
        if not self.message_sender:
            logging.warning("��Ϣ���ͽӿ�δ����")
            return
        
        try:
            # ����������ת��Ϊbytes��ʽ
            content = bytes(self.lora_send_data['send_dat'][:self.lora_send_data['pay_len']])
            
            # ���û��ָ��Ŀ���ַ��ʹ�ù㲥��ַ
            if target_addr is None:
                target_addr = ('255.255.255.255', 8003)  # LoRa�˿ڹ㲥
            
            self.message_sender(target_addr, msg_type, content)
            logging.debug(f"����LoRa��Ϣ: ����=0x{msg_type:02X}, ����={len(content)}")
            
        except Exception as e:
            logging.error(f"����LoRa��Ϣʧ��: {e}")
    
    def _lora_send_proc(self):
        """LoRa���ʹ�����ѭ�� - ����ģʽ"""
        while self.running:
            try:
                # ģ��ʱ�������
                self.second_count += 1
                
                if self.send_con['recv_send_en']:  # ����������ҪӦ��
                    self._handle_received_message()
                elif self.send_con['unnormal_send_en']:  # Ӧ������Ӧ��
                    self._handle_emergency_message()
                elif self.netman_new_dat:  # �������ݷ���
                    self._handle_network_data()
                elif self.sys_para['net_mod'] == 6:  # ĸ�Ƕ�ʧģʽ
                    self._handle_mother_lost_mode()
                elif self.mother_poll_sta == 1:  # ĸ����ѵ
                    self._handle_mother_polling()
                elif self.mother_poll_sta == 2:  # ����ĸ�Ǳ���ҵ������
                    self._handle_mother_business_data()
                elif self.mother_poll_sta in [3, 4, 5, 6]:  # ������ѯģʽ
                    self._handle_polling_modes()
                elif self.cluster_poll_sta in [1, 2, 3]:  # ���ײ���
                    self._handle_cluster_operations()
                elif self.sys_para['net_mod'] in [0, 3]:  # ������ģʽ
                    self._handle_iot_mode()
                
                # ģ�⴦����
                time.sleep(1)  # 1����
                
            except Exception as e:
                logging.error(f"LoRa���ʹ������: {e}")
                time.sleep(1)
    
    def _handle_received_message(self):
        """������յ�����ϢӦ��"""
        fram_type = self.send_con['fram_type']
        
        if fram_type == 0x11:  # ���յ���������Ϣ������������
            self._build_ranging_request()
        elif fram_type == 0x12:  # ���յ�������룬���Ͳ��Ӧ����Ϣ
            self._build_ranging_response()
        elif fram_type == 0x13:  # ���յ����Ӧ����Ϣ�����в����Ϣ�ϱ�
            self._build_ranging_report()
        elif fram_type == 0x02:  # ���յ�ע����Ϣ
            self._build_register_response()
        elif fram_type == 0x03:  # ���յ�ע��Ӧ����Ϣ
            self._handle_register_ack()
        elif fram_type == 0x04:  # �ڵ�ģʽ������Ϣ
            self._handle_node_control()
        elif fram_type == 0x20:  # ѯ����Ϣ���ڵ�Ӧ��
            self._handle_inquiry_message()
        elif fram_type == 0x23:  # ���յ��ڵ�״̬����
            self._handle_node_status()
        elif fram_type == 0x26:  # ���յ�ƽ̨�����ϱ�
            self._handle_platform_data()
        
        self.send_con['recv_send_en'] = False
    
    def _build_ranging_request(self):
        """�������������Ϣ"""
        self.lora_send_data['pay_len'] = 14  # ��������Ϣͷ�����ݳ���
        self.lora_send_data['send_dat'][0] = self.local_id
        self.lora_send_data['send_dat'][1] = self.lora_recv_data['recv_dat'][4]
        # ���㱣���ֶ�
        for i in range(2, 14):
            self.lora_send_data['send_dat'][i] = 0
        
        # ���Ͳ��������Ϣ
        self.send_lora_message(MessageType.LORA_RANGING_APPLY)
        logging.debug("���������Ͳ��������Ϣ")
    
    def _build_ranging_response(self):
        """�������Ӧ����Ϣ"""
        self.lora_send_data['pay_len'] = 14
        self.lora_send_data['send_dat'][0] = self.local_id
        self.lora_send_data['send_dat'][1] = self.lora_recv_data['recv_dat'][4]
        
        # ���ý���ʱ���
        recv_time = self.lora_recv_data['recv_time']
        self.lora_send_data['send_dat'][5] = (recv_time >> 24) & 0xff
        self.lora_send_data['send_dat'][6] = (recv_time >> 16) & 0xff
        self.lora_send_data['send_dat'][7] = (recv_time >> 8) & 0xff
        self.lora_send_data['send_dat'][8] = recv_time & 0xff
        
        # ���Ͳ��Ӧ����Ϣ
        self.send_lora_message(MessageType.LORA_RANGING_RSP)
        logging.debug("���������Ͳ��Ӧ����Ϣ")
    
    def _build_ranging_report(self):
        """������౨����Ϣ"""
        # ��������
        temp2 = (self.lora_recv_data['recv_dat'][7] << 24) + \
                (self.lora_recv_data['recv_dat'][8] << 16) + \
                (self.lora_recv_data['recv_dat'][9] << 8) + \
                self.lora_recv_data['recv_dat'][10]
        
        temp3 = (self.lora_recv_data['recv_dat'][11] << 24) + \
                (self.lora_recv_data['recv_dat'][12] << 16) + \
                (self.lora_recv_data['recv_dat'][13] << 8) + \
                self.lora_recv_data['recv_dat'][14]
        
        temp = ((self.lora_recv_data['recv_time'] - self.lora_send_data['send_time']) - 
                (temp3 - temp2)) >> 1
        
        self.lora_send_data['pay_len'] = 14
        self.lora_send_data['send_dat'][0] = self.local_id
        self.lora_send_data['send_dat'][5] = (temp >> 24) & 0xff
        self.lora_send_data['send_dat'][6] = (temp >> 16) & 0xff
        self.lora_send_data['send_dat'][7] = (temp >> 8) & 0xff
        self.lora_send_data['send_dat'][8] = temp & 0xff
        
        # ���Ͳ�౨����Ϣ
        self.send_lora_message(MessageType.LORA_RANGING_RSP)
        logging.debug("���������Ͳ�౨����Ϣ")
    
    def _build_register_response(self):
        """��������ע��Ӧ����Ϣ"""
        self.lora_send_data['pay_len'] = 16
        self.lora_send_data['send_dat'][0] = self.local_id
        self.lora_send_data['send_dat'][1] = self.lora_recv_data['recv_dat'][5]  # MAC��ַ
        self.lora_send_data['send_dat'][2] = self.lora_recv_data['recv_dat'][6]
        self.lora_send_data['send_dat'][3] = self.lora_recv_data['recv_dat'][7]
        self.lora_send_data['send_dat'][4] = 2  # ��ͨ�ڵ�
        # �����ֶ�����Ϊ��Ч
        for i in range(5, 16):
            self.lora_send_data['send_dat'][i] = 0xff if i < 12 else 0
        
        # ����ע��Ӧ����Ϣ
        self.send_lora_message(MessageType.LORA_REGISTER_RSP)
        logging.debug("��������������ע��Ӧ����Ϣ")
    
    def _handle_register_ack(self):
        """����ע��Ӧ����Ϣ"""
        logging.debug("����ע��Ӧ����Ϣ")
    
    def _handle_node_control(self):
        """����ڵ������Ϣ"""
        logging.debug("����ڵ������Ϣ")
    
    def _handle_inquiry_message(self):
        """����ѯ����Ϣ"""
        temp = self.lora_recv_data['recv_dat'][4]
        
        if temp & 0x40:  # �ж��Ƿ��д�������
            if self.sys_para['clust_id'] == self.local_id:  # ֻ�д��׽ڵ����Ӧ��
                self.cluster_poll_sta = 1
                self._build_cluster_response()
        elif (temp & 0x1) and self.traffic_data['traffic_pack']:  # ѯ��ҵ������
            self.traffic_send_en = True
            self._build_traffic_response()
        elif temp & 0x4:  # ƽ̨���ݷ���
            self._build_platform_response()
        elif temp & 0x8:  # �غ����ݷ���
            self._build_payload_response()
        else:  # �ڵ�״̬����
            self._build_node_status_response()
    
    def _build_cluster_response(self):
        """��������Ӧ��"""
        self.lora_send_data['pay_len'] = 11
        self.lora_send_data['send_dat'][0] = self.lora_recv_data['recv_dat'][3]
        self.lora_send_data['send_dat'][1] = self.local_id
        self.lora_send_data['send_dat'][2] = self.sys_para['clust_numb']
        temp = self.sys_para['clust_numb'] * 1000
        self.lora_send_data['send_dat'][3] = (temp >> 8) & 0xff
        self.lora_send_data['send_dat'][4] = temp & 0xff
        
        self.send_lora_message(MessageType.LORA_INQUIRY_RSP)
        logging.debug("��������Ӧ��")
    
    def _build_traffic_response(self):
        """����ҵ������Ӧ��"""
        self.lora_send_data['pay_len'] = 11
        self.lora_send_data['send_dat'][0] = self.lora_recv_data['recv_dat'][3]
        self.lora_send_data['send_dat'][1] = self.local_id
        self.lora_send_data['send_dat'][2] = (self.traffic_data['traffic_pack'] >> 8) & 0xff
        self.lora_send_data['send_dat'][3] = self.traffic_data['traffic_pack'] & 0xff
        
        self.send_lora_message(MessageType.LORA_INQUIRY_RSP)
        logging.debug("����ҵ������Ӧ��")
    
    def _build_platform_response(self):
        """����ƽ̨����Ӧ��"""
        self.lora_send_data['pay_len'] = 18
        self.lora_send_data['send_dat'][0] = self.lora_recv_data['recv_dat'][3]
        self.lora_send_data['send_dat'][1] = self.local_id
        
        for i in range(2, 18):
            self.lora_send_data['send_dat'][i] = self.node_data['sat_data'][i] if i < len(self.node_data['sat_data']) else 0
        
        self.send_lora_message(MessageType.LORA_PLATFORM_DATA)
        logging.debug("����ƽ̨����Ӧ��")
    
    def _build_payload_response(self):
        """�����غ�����Ӧ��"""
        self.lora_send_data['pay_len'] = 18
        self.lora_send_data['send_dat'][0] = self.lora_recv_data['recv_dat'][3]
        self.lora_send_data['send_dat'][1] = self.local_id
        
        if self.node_data['paload_unnormal']:
            self.lora_send_data['send_dat'][2] = 2
            self.node_data['paload_unnormal'] = False
        else:
            self.lora_send_data['send_dat'][2] = 1
        
        for i in range(3, 18):
            self.lora_send_data['send_dat'][i] = self.node_data['payload_data'][i] if i < len(self.node_data['payload_data']) else 0
        
        self.send_lora_message(MessageType.LORA_PLATFORM_DATA)
        logging.debug("�����غ�����Ӧ��")
    
    def _build_node_status_response(self):
        """�����ڵ�״̬Ӧ��"""
        self.lora_send_data['pay_len'] = 25
        self.lora_send_data['send_dat'][0] = 0xfe  # Ŀ���ַ
        self.lora_send_data['send_dat'][1] = self.local_id
        
        # ���ƽڵ�����
        for i in range(2, 23):
            self.lora_send_data['send_dat'][i] = self.node_data['node_data'][i] if i < len(self.node_data['node_data']) else 0
        
        self.send_lora_message(MessageType.LORA_NODE_STATUS)
        logging.debug("�����ڵ�״̬Ӧ��")
    
    def _handle_node_status(self):
        """����ڵ�״̬����"""
        if (self.sys_para['net_mod'] < 6) and (self.sys_para['node_mod'] == 0):
            self._build_broadcast_message(self.send_con['currend_id'])
            self.send_con['netman_send_en'] = False
        logging.debug("����ڵ�״̬����")
    
    def _handle_platform_data(self):
        """����ƽ̨�����ϱ�"""
        if (self.sys_para['net_mod'] < 6) and (self.sys_para['node_mod'] == 0):
            self._build_broadcast_message(self.send_con['currend_id'])
            self.send_con['netman_send_en'] = False
        logging.debug("����ƽ̨�����ϱ�")
    
    # ����ʵ������������...
    def _handle_emergency_message(self):
        """����Ӧ������Ӧ��"""
        if self.link_sta == 1:  # �û��ѻ��ϵͳͬ������������
            self._build_network_register()
            self.link_sta = 2
        elif self.node_data['paload_unnormal']:  # �غ��쳣����
            self._build_abnormal_payload()
    
    def _build_network_register(self):
        """��������ע����Ϣ"""
        self.lora_send_data['pay_len'] = 28
        self.lora_send_data['send_dat'][0] = self.sys_para.get('net_id', 0)
        self.lora_send_data['send_dat'][1] = self.local_id
        self.lora_send_data['send_dat'][2] = 0x01  # �ڵ�����
        
        # ��������ע����Ϣ
        self.send_lora_message(MessageType.LORA_REGISTER_REQ)
        logging.debug("��������������ע����Ϣ")
    
    def _build_abnormal_payload(self):
        """�����쳣�غ�����"""
        self.lora_send_data['pay_len'] = 18
        self.lora_send_data['send_dat'][0] = 0xfe
        self.lora_send_data['send_dat'][1] = self.local_id
        self.lora_send_data['send_dat'][2] = 2  # �쳣��־
        
        self.send_lora_message(MessageType.LORA_PLATFORM_DATA)
        self.node_data['paload_unnormal'] = False
        logging.debug("�����쳣�غ�����")
    
    def _handle_network_data(self):
        """�����������ݷ���"""
        self.lora_send_data['pay_len'] = self.netman_recv_dat[1]
        for i in range(self.netman_recv_dat[1]):
            self.lora_send_data['send_dat'][i] = self.netman_recv_dat[i]
        self.netman_new_dat = False
        logging.debug("�����������ݷ���")
    
    def _handle_mother_lost_mode(self):
        """����ĸ�Ƕ�ʧģʽ"""
        if self.second_count > (self.lora_recv_data['recv_ok_time'] + 10000):
            self._build_mother_election()
    
    def _build_mother_election(self):
        """����ĸ��ѡ����Ϣ"""
        self.lora_send_data['pay_len'] = 12
        self.lora_send_data['send_dat'][0] = self.local_id
        self.lora_send_data['send_dat'][1] = 0
        self.lora_send_data['send_dat'][2] = 234  # ��Ը�㷨
        self.lora_send_data['send_dat'][3] = 0x01  # �ڵ�����
        
        self.send_lora_message(MessageType.LORA_MOTHER_ELECTION)
        logging.debug("����ĸ��ѡ����Ϣ")
    
    def _handle_mother_polling(self):
        """����ĸ����ѯ"""
        self._build_broadcast_message(0x00)
        self.mother_poll_sta = 2
        logging.debug("ĸ����ѯ - ���͹㲥��Ϣ")
    
    def _build_broadcast_message(self, target_id):
        """�����㲥��Ϣ"""
        self.lora_send_data['pay_len'] = 18
        self.lora_send_data['send_dat'][0] = target_id
        self.lora_send_data['send_dat'][1] = self.local_id
        self.lora_send_data['send_dat'][2] = self.sys_para['net_mod']
        self.lora_send_data['send_dat'][3] = self.sys_para['node_mod']
        self.lora_send_data['send_dat'][4] = self.sys_para['mother_id']
        self.lora_send_data['send_dat'][5] = self.sys_para['gateway_id']
        
        self.send_lora_message(MessageType.LORA_BROADCAST)
        logging.debug(f"���������͹㲥��Ϣ��Ŀ��ID: {target_id}")
    
    def _handle_mother_business_data(self):
        """����ĸ�Ǳ���ҵ������"""
        if self.traffic_data['traffic_pack']:
            self.traffic_send_en = True
            if self.traffic_data['traffic_pack'] == self.traffic_data['data_num']:
                self.traffic_data['traffic_pack'] = 0
                self.mother_poll_sta = 3
                self.send_con['poll_ok'] = True
        logging.debug("����ĸ�Ǳ���ҵ������")
    
    def _handle_polling_modes(self):
        """���������ѯģʽ"""
        if self.mother_poll_sta == 3:
            self._handle_cluster_polling()
        elif self.mother_poll_sta == 4:
            self._handle_node_polling()
        elif self.mother_poll_sta == 5:
            self._handle_ranging_operation()
        elif self.mother_poll_sta == 6:
            self._handle_status_setting()
    
    def _handle_cluster_polling(self):
        """���������ѯ"""
        if self.send_con['poll_ok'] and self.poll_cluster_id < self.sys_para['clust_numb']:
            self._build_cluster_poll_message()
            self.poll_cluster_id += 1
        else:
            self.mother_poll_sta = 5
    
    def _build_cluster_poll_message(self):
        """����������ѯ��Ϣ"""
        self.lora_send_data['pay_len'] = 9
        self.lora_send_data['send_dat'][0] = self.sys_para.get('clust_node_id', [0])[self.poll_cluster_id] if self.poll_cluster_id < len(self.sys_para.get('clust_node_id', [])) else 0
        self.lora_send_data['send_dat'][1] = self.local_id
        self.lora_send_data['send_dat'][2] = 0x40
        
        self.send_lora_message(MessageType.LORA_INQUIRY)
        self.send_con['poll_ok'] = False
        logging.debug("����������ѯ��Ϣ")
    
    def _handle_node_polling(self):
        """����ڵ���ѯ"""
        if self.send_con['poll_ok']:
            self._build_node_poll_message()
            self.poll_node_id += 1
            if self.poll_node_id >= 0x7e:
                self.mother_poll_sta = 5
    
    def _build_node_poll_message(self):
        """�����ڵ���ѯ��Ϣ"""
        self.lora_send_data['pay_len'] = 9
        self.lora_send_data['send_dat'][0] = self.poll_node_id
        self.lora_send_data['send_dat'][1] = self.local_id
        self.lora_send_data['send_dat'][2] = 0x01
        
        self.send_lora_message(MessageType.LORA_INQUIRY)
        self.send_con['poll_ok'] = False
        logging.debug("�����ڵ���ѯ��Ϣ")
    
    def _handle_ranging_operation(self):
        """���������"""
        logging.debug("���������")
        self.mother_poll_sta = 6
    
    def _handle_status_setting(self):
        """����״̬��������"""
        logging.debug("����״̬��������")
        self.mother_poll_sta = 1  # �ص���ʼ״̬
    
    def _handle_cluster_operations(self):
        """������ײ���"""
        if self.cluster_poll_sta == 1:
            self._handle_cluster_business_data()
        elif self.cluster_poll_sta == 2:
            self._handle_cluster_node_polling()
        elif self.cluster_poll_sta == 3:
            self._handle_cluster_status_report()
    
    def _handle_cluster_business_data(self):
        """�������ҵ������"""
        if self.traffic_data['traffic_pack']:
            self.traffic_send_en = True
            if self.traffic_data['traffic_pack'] == self.traffic_data['data_num']:
                self.traffic_data['traffic_pack'] = 0
                self.cluster_poll_sta = 2
        logging.debug("�������ҵ������")
    
    def _handle_cluster_node_polling(self):
        """������׽ڵ���ѯ"""
        self.cluster_poll_sta = 3
        logging.debug("������׽ڵ���ѯ")
    
    def _handle_cluster_status_report(self):
        """�������״̬����"""
        self._build_cluster_status_message()
        self.cluster_poll_sta = 0
        logging.debug("�������״̬����")
    
    def _build_cluster_status_message(self):
        """��������״̬��Ϣ"""
        self.lora_send_data['pay_len'] = 20
        self.lora_send_data['send_dat'][0] = self.sys_para['mother_id']
        self.lora_send_data['send_dat'][1] = self.local_id
        self.lora_send_data['send_dat'][2] = self.sys_para['clust_numb']
        
        self.send_lora_message(MessageType.LORA_CLUSTER_STATUS)
        logging.debug("��������״̬��Ϣ")
    
    def _handle_iot_mode(self):
        """����������ģʽ"""
        if self.sys_para['node_mod'] == 0:  # ĸ��
            self._build_broadcast_message(0x00)
        elif self.link_sta == 4:  # �����ڵ�
            self._handle_node_periodic_send()
        elif self.link_sta == 2:  # �Ѿ����ͬ������������ע����Ϣ
            self._build_network_register()
    
    def _handle_node_periodic_send(self):
        """����ڵ������Է���"""
        temp = self.sys_base_time + self.local_id * 5
        if self.second_count > temp:
            if self.node_data['node_period']:
                self._build_node_status_message()
                
                # ����Ƿ���Ҫ������������
                if (self.node_data['sat_period'] and 
                    self.node_data['sat_time'] < self.second_count):
                    self._build_satellite_data()
                
                # ����Ƿ���Ҫ�����غ�����
                if (self.node_data['paload_period'] and 
                    self.node_data['paload_time'] < self.second_count):
                    self._build_payload_data()
    
    def _build_node_status_message(self):
        """�����ڵ�״̬��Ϣ"""
        self.lora_send_data['pay_len'] = 25
        self.lora_send_data['send_dat'][0] = 0xfe
        self.lora_send_data['send_dat'][1] = self.local_id
        
        for i in range(2, 23):
            self.lora_send_data['send_dat'][i] = self.node_data['node_data'][i] if i < len(self.node_data['node_data']) else 0
        
        self.send_lora_message(MessageType.LORA_NODE_STATUS)
        logging.debug("�����ڵ�״̬��Ϣ")
    
    def _build_satellite_data(self):
        """������������"""
        self.lora_send_data['pay_len'] = 18
        self.lora_send_data['send_dat'][0] = 0xfe
        self.lora_send_data['send_dat'][1] = self.local_id
        
        for i in range(2, 18):
            self.lora_send_data['send_dat'][i] = self.node_data['sat_data'][i] if i < len(self.node_data['sat_data']) else 0
        
        self.send_lora_message(MessageType.LORA_PLATFORM_DATA)
        self.node_data['sat_time'] += self.node_data['sat_period']
        logging.debug("������������")
    
    def _build_payload_data(self):
        """�����غ�����"""
        self.lora_send_data['pay_len'] = 18
        self.lora_send_data['send_dat'][0] = 0xfe
        self.lora_send_data['send_dat'][1] = self.local_id
        
        if self.node_data['paload_unnormal']:
            self.lora_send_data['send_dat'][2] = 2
            self.node_data['paload_unnormal'] = False
        else:
            self.lora_send_data['send_dat'][2] = 1
        
        for i in range(3, 18):
            self.lora_send_data['send_dat'][i] = self.node_data['payload_data'][i] if i < len(self.node_data['payload_data']) else 0
        
        self.send_lora_message(MessageType.LORA_PLATFORM_DATA)
        self.node_data['paload_time'] += self.node_data['paload_period']
        logging.debug("�����غ�����")