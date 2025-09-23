#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import threading
import logging
import time
import struct
from protocol import MessageType, MessageProtocol
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class NeighborNodeStatus:
    """�ھӽڵ�״̬����"""
    node_sta: int = 0  # �ڵ�״̬��0-�����ߣ�1-��������Ӧ��ע�ᣬ2-����������3-Ǳ����4-��Ĭ
    node_position: int = 2  # �ڵ����ԣ�0ĸ�ǣ�1���ף�2-����
    mac_addr: List[int] = field(default_factory=lambda: [0, 0, 0])  # �ڵ�MAC��ַ
    node_ability: int = 0  # �ڵ�����
    freq_rang: int = 0  # �ڵ��ź�Ƶ�ʷ�Χ
    node_pow: int = 0  # �ڵ��źŹ��ʣ�֧������Ӧ��·
    VGA: int = 0  # �ڵ��źŹ��ʷ�Χ
    pos_x: int = 0  # �ռ�����x (10�׻�����λ)
    pos_y: int = 0  # �ռ�����y
    pos_z: int = 0  # �ռ�����z
    cluster_id: int = 0  # �ڵ����ڴ�ID
    node_det_num: int = 3  # �ڵ�������������������ʼֵ3
    node_det_tim: int = 0  # �ڵ���ʱ��
    node_SF: int = 7  # �ڵ���Ƶ����
    node_healty_sta: int = 0  # �ڵ㽡��״̬


@dataclass
class NodeOperationStatus:
    """�ڵ����״̬"""
    node_ope_en: bool = False
    node_opedata: List[int] = field(default_factory=lambda: [0] * 6)


@dataclass
class DistanceStatus:
    """���״̬"""
    node_dis_en: bool = False
    des_nod_id: int = 0


@dataclass
class NodeAskStatus:
    """�ڵ�ѯ��״̬"""
    node_ask_en: bool = False
    node_opedata: int = 0x08


@dataclass
class NodeMotherStatus:
    """�ڵ�ĸ��״̬"""
    netman_link: List[int] = field(default_factory=lambda: [0] * 128)
    mother_score: List[int] = field(default_factory=lambda: [0] * 128)


class LoRaProcessor:
    """LoRa��Ϣ������ - ��������ģʽ�Ĵ����߼�
    
    ����Ŀ�ܹ����ɣ�
    - ͨ��message_processor����UDP��Ϣ
    - ͨ��udp_servers������Ӧ��Ϣ
    - ֧�������ļ������Ĳ�������
    """
    
    def __init__(self, message_sender: Optional[Callable] = None):
        self.running = False
        self.thread = None
        self.message_sender = message_sender  # ��Ϣ���ͽӿڣ����ӵ�UDP������
        
        # SF�����������ӳ�䵽��Ƶ����
        self.SF_table = [12, 11, 10, 9, 8, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7]
        
        # ��ʼ��ϵͳ��������config.ini���ö�Ӧ��
        self.sys_para = {
            'net_id': 0x0001,  # ����ID
            'net_mod': 0,  # ����ģʽ: 0-��������ʽ��3-�͹���ģʽ��6-ĸ�Ƕ�ʧģʽ��7-���׵���ģʽ��8-ĸ�Ƕ�ʧ״̬
            'node_mod': 2,  # �ڵ�ģʽ: 0-ĸ�ǣ�1-���ף�2-��ͨ�ڵ�
            'mother_id': 0,  # ĸ��ID�̶�Ϊ0
            'gateway_id': 0xFE,  # ����ID
            'clust_id': 0x80,  # ����ID
            'clust_numb': 0,  # ���ڽڵ���
            'clust_node_id': [0] * 32,  # ���ڽڵ�ID�б�
            'work_mod': 0,  # ����ģʽ
            'convert_mod': 0,  # ϵͳ�������л�ģʽ
            'sig_det_time': 0,  # �źż��ʱ��
            'sys_sig_mod': 0,  # �ϱ��źŷ�ʽ�����滹������Ӧ
            'wake_mod': 1,  # �տڻ���ģʽ��0����տڻ���ģʽ��1�����ڿտڻ���ģʽ
            'un_permit': 1,  # �쳣�ϱ�����
            'perm_period': 10,  # �쳣�ϱ������ڣ�������0�������쳣ѯ�ʣ�
            'node_sta_det': 0,  # �ڵ�״̬���
            'node_num': 0,  # ϵͳ�ڵ���Ŀ
            'max_id': 0x7E,  # ϵͳ���ڵ�ID
            'SF_base_forw': 7,  # ��������SF
            'SF_high_forw': 12,  # �������SF
            'SF_base_backw': 7,  # ����SF������
            'clust_SF_base_forw': 7,  # �ػ���SF��ǰ��
            'clust_SF_base_backw': 7,  # �ػ���SF������
            'sys_fram_period': 3600,  # ϵͳ֡���ڳ���
            'burst_time_base': 10,  # ������ͻ���Զ���ʱ��
            'fre_backw': 470000000,  # ����Ƶ��
            'bw_backw': 0,  # �������
            'cr_backw': 1,  # ���������
            'clust_bw_forw': 0,  # ��ǰ�����
            'clust_bw_backw': 0,  # �ط������
            'clust_cr_backw': 1,  # �ط��������
        }
        
        # �ڵ��������Ӧconfig.ini��NODE_CONFIG���֣�
        self.local_id = 0x10  # �����ڵ�ID���������ļ���ȡ
        self.node_para = {
            'mac_addr': [0x12, 0x34, 0x56],  # MAC��ַ
            'node_ability': 0x01,  # �ڵ�����
            'Freq_range': 0x01,  # Ƶ�ʷ�Χ
            'max_Pow': 20,  # �����
            'Pow_att': 1,  # ���ʱ仯
            'locat_x': 1000,  # �ռ�����x (10�׵�λ)
            'locat_y': 2000,  # �ռ�����y
            'locat_z': 100,   # �ռ�����z
            'pow_set': 14,    # �ڵ㹦�ʵȼ�
        }
        
        # �źŲ�������Ӧconfig.ini��LORA_PARAMS���֣�
        self.send_sig_para = {
            'sig_fre': 470000000,  # ����Ƶ��
            'sig_SF': 7,           # ������Ƶ����
            'sig_CR': 1,           # ���ͱ�����
            'sig_bw': 0,           # ����
            'sig_pow': 14          # ���͹���
        }
        
        self.recv_sig_para = {
            'sig_fre': 470000000,  # ����Ƶ��
            'sig_SF': 7,           # ������Ƶ����
            'sig_CR': 1,           # ���ձ�����
            'sig_bw': 0            # ����
        }
        
        # ���Ϳ���״̬
        self.send_con = {
            'recv_send_en': False,  # ����������ҪӦ��
            'fram_type': 0,         # ֡����
            'unnormal_send_en': False,  # �쳣����Ӧ��
            'netman_send_en': False,    # ���ܷ���ʹ��
            'poll_ok': True,            # ��ѯOK��־
            'currend_id': 0,            # ��ǰ�ڵ�ID
            'poll_new_send': False      # �µ���ѯ����
        }
        
        # LoRa�������ݽṹ
        self.lora_send_data = {
            'pay_len': 0,
            'send_dat': [0] * 256,
            'send_time': 0,
            'send_time_en': False,
            'send_time_stamp': 0
        }
        
        # LoRa�������ݽṹ
        self.lora_recv_data = {
            'recv_dat': [0] * 256,
            'recv_time': 0,
            'recv_ok_time': 0,
            'recv_length': 0,
            'recv_SNR': 0  # �����
        }
        
        # �ڵ�״̬
        self.link_sta = 0  # 0-���У�1-�ź�������2-���ͬ����3-����������Ϣ��4-���������5-ĸ�Ƕ�ʧ
        self.mother_poll_sta = 1  # ĸ����ѯ״̬
        self.cluster_poll_sta = 0  # ������ѯ״̬
        self.traffic_send_en = False
        self.netman_link_sta = True  # ��������״̬
        self.to_convert_mother_id = False  # ��Ҫ�л���ĸ��״̬
        
        # ʱ�����
        self.second_count = 0
        self.mil_sec_count = 0
        self.sys_base_time = 0
        self.next_base_time = 3600  # ��һ��ʱ���׼
        self.sys_time_offset = 0
        self.time_out = 1000  # ��ʱ���
        self.re_enter_time = 0  # ��������ʱ��
        
        # ��ѯ���
        self.poll_node_id = 0
        self.poll_cluster_id = 0
        
        # �����������
        self.netman_new_dat = False
        self.netman_recv_dat = [0] * 1024
        self.netman_send_en = False
        self.receive_to_netman = False
        
        # ҵ������
        self.traffic_data = {
            'traffic_pack': 0,
            'data_num': 0,
            'traffic_dat': [0] * 1024,
            'dest_id': 0
        }
        
        # �ڵ����ݣ���Ӧconfig.ini��TIMING_PARAMS���֣�
        self.node_data = {
            'node_data': [0] * 32,
            'node_period': 60,  # �ڵ�״̬�����ϱ�����(��)
            'node_time': 0,     # �ڵ�ʱ��
            'paload_unnormal': False,
            'sat_data': [0] * 32,
            'sat_period': 300,  # ����״̬�����ϱ�����(��)
            'sat_time': 0,
            'payload_data': [0] * 32,
            'paload_period': 120,  # �غ������ϱ�����(��)
            'paload_time': 0
        }
        
        # �ھӽڵ�״̬���� (���֧��128���ڵ�)
        self.neighbor_node_sta = [NeighborNodeStatus() for _ in range(128)]
        
        # �ڵ����״̬����
        self.node_ope_sta = [NodeOperationStatus() for _ in range(128)]
        
        # ���״̬����
        self.distanc_sta = [DistanceStatus() for _ in range(128)]
        
        # �ڵ�ѯ��״̬����
        self.node_ask_sta = [NodeAskStatus() for _ in range(128)]
        
        # ĸ��״̬����
        self.node_mother_sta = NodeMotherStatus()
        
        # ͳ����Ϣ
        self.recv_totle_num = 0      # ������֡��
        self.recv_fram_err = 0       # ����֡����
        self.recv_fram_num = 0       # ��ȷ֡����
        self.recv_fram_self = 0      # ���ڵ����
        self.user_det_tim = 0        # �û����ʱ��
        
        # ��ʱ����
        self.temp = 0
        self.temp1 = 0
        self.temp2 = 0
        self.temp3 = 0
        self.i = 0
        self.j = 0
        self.k = 0
    
    def set_message_sender(self, sender: Callable):
        """������Ϣ���ͽӿڣ���UDP����������"""
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
        """���ýڵ����ͣ���main.py�е����ö�Ӧ��"""
        if node_type == "mother":
            self.sys_para['node_mod'] = 0
            self.local_id = 0  # ĸ��ID�̶�Ϊ0
            self.sys_para['mother_id'] = 0
            logging.info("�ڵ���������Ϊ��ĸ�� (ID=0)")
        elif node_type == "cluster":
            self.sys_para['node_mod'] = 1  
            self.local_id = self.sys_para['clust_id']
            logging.info("�ڵ���������Ϊ������")
        else:
            self.sys_para['node_mod'] = 2
            logging.info("�ڵ���������Ϊ����ͨ�ڵ�")
    
    def set_local_id(self, node_id: int):
        """���ñ��ؽڵ�ID"""
        if 0 <= node_id <= 0x7E:
            self.local_id = node_id
            logging.info(f"�ڵ�ID����Ϊ��{node_id}")
        else:
            logging.warning(f"��Ч�Ľڵ�ID��{node_id}��Ӧ��0-126֮��")
    
    def process_received_message(self, raw_data: bytes, recv_time: int = None):
        """������յ�����Ϣ����message_processor���ã�"""
        # ֱ�Ӵ����ѽ������Ϣ����
        if len(raw_data) < 2:
            logging.warning("���յ����Ȳ������Ϣ")
            return
        
        # ���½������ݽṹ
        self.lora_recv_data['recv_dat'] = list(raw_data) + [0] * (256 - len(raw_data))
        self.lora_recv_data['recv_length'] = len(raw_data)
        self.lora_recv_data['recv_time'] = recv_time or int(time.time() * 1000)
        
        # ����ͳ����Ϣ
        self.recv_totle_num += 1
        self.recv_fram_num += 1
        self.user_det_tim = 1
        
        # ���������Ϣ
        self.send_con['fram_type'] = raw_data[0]
        self._lora_fram_proc()
    
    def send_lora_message(self, msg_type: int, target_addr: tuple = None):
        """����LoRa��Ϣ��ͨ��UDP��������"""
        if not self.message_sender:
            logging.warning("��Ϣ���ͽӿ�δ����")
            return
        
        try:
            # ����������ת��Ϊbytes��ʽ
            content = bytes(self.lora_send_data['send_dat'][:self.lora_send_data['pay_len']])
            
            # ���û��ָ��Ŀ���ַ��ʹ�ù㲥��ַ
            if target_addr is None:
                target_addr = ('255.255.255.255', 8003)  # LoRa�˿ڹ㲥
            
            # ͨ��message_sender���ͣ��⽫����UDP�������ķ��ͷ�����
            self.message_sender(target_addr, msg_type, content)
            logging.debug(f"����LoRa��Ϣ: ����=0x{msg_type:02X}, ����={len(content)}")
            
        except Exception as e:
            logging.error(f"����LoRa��Ϣʧ��: {e}")
    
    def _lora_send_proc(self):
        """LoRa���ʹ�����ѭ�� - ����ԭC���������ʵ��"""
        while self.running:
            try:
                # ģ��ʱ�������
                self.second_count += 1
                self.mil_sec_count = (self.mil_sec_count + 100) % 1000
                if self.mil_sec_count == 0:
                    self.second_count += 1
                
                if self.send_con['recv_send_en']:  # ����������ҪӦ��
                    self._handle_received_message_response()
                elif self.send_con['unnormal_send_en']:  # Ӧ������Ӧ��������ʱ����Ϊ����ע����Ϣ
                    self._handle_emergency_response()
                elif self.netman_new_dat:  # �������ݷ��ͣ��ص�����Ϣ+ҵ������+ĸ���л������ܷ���
                    self._handle_network_management_data()
                elif self.sys_para['net_mod'] == 6:  # ĸ�Ƕ�ʧģʽ,ǰ���ɸ��û��������ڣ���ʱ��ⷢ��
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
                elif self.sys_para['net_mod'] in [0, 3]:  # ������ģʽ
                    self._handle_iot_mode()
                
                # �û��˳����
                self._user_exit_detection()
                
                # ģ�⴦����
                time.sleep(1)  # 1����
                
            except Exception as e:
                logging.error(f"LoRa���ʹ������: {e}")
                time.sleep(1)
    
    def _handle_received_message_response(self):
        """�����������Ӧ�� - ��ӦԭC�����recv_send_en��֧"""
        fram_type = self.send_con['fram_type']
        
        if fram_type == 0x11:  # ���յ���������Ϣ������������
            self._build_ranging_request()
        elif fram_type == 0x12:  # ���յ�������룬���Ͳ��Ӧ����Ϣ
            self._build_ranging_response()
        elif fram_type == 0x13:  # ���յ����Ӧ����Ϣ�����в����Ϣ�ϱ�
            self._build_ranging_report()
        elif fram_type == 0x02:  # ���յ�ע����Ϣ
            self._build_register_response()
        elif fram_type == 0x03:  # ���յ�ע��Ӧ����Ϣ,���ճ�������
            self._lora_mac_ack(self.sys_para['mother_id'])
        elif fram_type == 0x04:  # �ڵ�ģʽ������Ϣ������Ӧ��֡��ȷ�ϻ���״̬���ݣ������׵�״̬
            self._lora_mac_ack(self.sys_para['gateway_id'])
        elif fram_type == 0x05:  # �ز�������������ҪӦ���ɽ��ս�������
            self._lora_mac_ack(self.sys_para['gateway_id'])
        elif fram_type == 0x20:  # ѯ����Ϣ,�ڵ�Ӧ��
            self._handle_inquiry_message()
        elif fram_type == 0x23:  # ���յ��ڵ�״̬����
            self._handle_node_status_response()
        elif fram_type == 0x26:  # ������ģʽ���ս��յ�ƽ̨�����ϱ�,ĸ�ǽ���Ӧ�𣬷�������ģʽ�ɽ������Σ�
            self._handle_platform_data_response()
        elif fram_type == 0x27:  # ������ģʽ�·�����·״̬��Ϣ����ʱ����
            self._handle_link_status_response()
        elif fram_type == 0x30:  # ���յ�ĸ���л���Ϣ���н�������
            pass  # �ɽ��մ���
        elif fram_type == 0x31:  # ĸ�Ƕ�ʧѡ��ģʽ
            self._handle_mother_election_response()
        
        self.send_con['recv_send_en'] = False
    
    def _build_ranging_request(self):
        """�������������Ϣ"""
        self.lora_send_data['pay_len'] = 16
        self.lora_send_data['send_dat'][0] = 0x12
        self.lora_send_data['send_dat'][1] = self.lora_send_data['pay_len']
        self.lora_send_data['send_dat'][2] = self.local_id
        self.lora_send_data['send_dat'][3] = self.lora_recv_data['recv_dat'][4]
        self.lora_send_data['send_dat'][4] = 0  # ��Ϣ��ű���
        self.lora_send_data['send_dat'][5] = 0  # �����Ϣ���ͣ�����
        
        for i in range(7, 15):
            self.lora_send_data['send_dat'][i] = 0
        
        self.send_lora_message(MessageType.LORA_RANGING_APPLY)
        logging.debug("���������Ͳ��������Ϣ")
    
    def _build_ranging_response(self):
        """�������Ӧ����Ϣ"""
        self.lora_send_data['pay_len'] = 16
        self.lora_send_data['send_dat'][0] = 0x13
        self.lora_send_data['send_dat'][1] = self.lora_send_data['pay_len']
        self.lora_send_data['send_dat'][2] = self.local_id
        self.lora_send_data['send_dat'][3] = self.lora_recv_data['recv_dat'][4]
        self.lora_send_data['send_dat'][4] = 0  # ��Ϣ��ű���
        self.lora_send_data['send_dat'][5] = 0  # �����Ϣ���ͣ�����
        
        # ���ý���ʱ���
        recv_time = self.lora_recv_data['recv_time']
        self.lora_send_data['send_dat'][7] = (recv_time >> 24) & 0xff
        self.lora_send_data['send_dat'][8] = (recv_time >> 16) & 0xff
        self.lora_send_data['send_dat'][9] = (recv_time >> 8) & 0xff
        self.lora_send_data['send_dat'][10] = recv_time & 0xff
        
        # ����ʱ�������FPGA����
        for i in range(11, 15):
            self.lora_send_data['send_dat'][i] = 0
        
        self.send_lora_message(MessageType.LORA_RANGING_RSP)
        logging.debug("���������Ͳ��Ӧ����Ϣ")
    
    def _build_ranging_report(self):
        """������౨����Ϣ"""
        # ��������
        temp2 = ((self.lora_recv_data['recv_dat'][7] << 24) + 
                (self.lora_recv_data['recv_dat'][8] << 16) + 
                (self.lora_recv_data['recv_dat'][9] << 8) + 
                self.lora_recv_data['recv_dat'][10])
        
        temp3 = ((self.lora_recv_data['recv_dat'][11] << 24) + 
                (self.lora_recv_data['recv_dat'][12] << 16) + 
                (self.lora_recv_data['recv_dat'][13] << 8) + 
                self.lora_recv_data['recv_dat'][14])
        
        temp = ((self.lora_recv_data['recv_time'] - self.lora_send_data['send_time']) - 
                (temp3 - temp2)) >> 1
        
        self.lora_send_data['pay_len'] = 16
        self.lora_send_data['send_dat'][0] = 0x13
        self.lora_send_data['send_dat'][1] = self.lora_send_data['pay_len']
        self.lora_send_data['send_dat'][2] = self.local_id
        self.lora_send_data['send_dat'][3] = self.lora_recv_data['recv_dat'][4]
        self.lora_send_data['send_dat'][4] = 0  # ��Ϣ��ű���
        self.lora_send_data['send_dat'][5] = 0  # �����Ϣ���ͣ�����
        
        self.lora_send_data['send_dat'][7] = (temp >> 24) & 0xff
        self.lora_send_data['send_dat'][8] = (temp >> 16) & 0xff
        self.lora_send_data['send_dat'][9] = (temp >> 8) & 0xff
        self.lora_send_data['send_dat'][10] = temp & 0xff
        
        for i in range(11, 15):
            self.lora_send_data['send_dat'][i] = 0  # ����ʱ�������FPGA����
        
        self.send_lora_message(MessageType.LORA_RANGING_RSP)
        logging.debug("���������Ͳ�౨����Ϣ")
    
    # ����ʵ���������ķ���...
    def get_node_status(self) -> Dict:
        """��ȡ�ڵ�״̬��Ϣ����main.py�еĽӿڶ�Ӧ��"""
        return {
            'local_id': self.local_id,
            'node_mod': self.sys_para['node_mod'],
            'net_mod': self.sys_para['net_mod'],
            'link_sta': self.link_sta,
            'mother_id': self.sys_para['mother_id'],
            'cluster_id': self.sys_para['clust_id'],
            'running': self.running,
            'recv_fram_num': self.recv_fram_num,
            'recv_fram_err': self.recv_fram_err,
            'second_count': self.second_count,
            'mother_poll_sta': self.mother_poll_sta,
            'cluster_poll_sta': self.cluster_poll_sta
        }
    
    def _lora_mac_ack(self, dest_id: int):
        """����MAC��Ӧ��"""
        self.lora_send_data['pay_len'] = 9
        self.lora_send_data['send_dat'][0] = 0x01  # ֡����
        self.lora_send_data['send_dat'][1] = 0x09  # ���ݳ���
        self.lora_send_data['send_dat'][2] = dest_id
        self.lora_send_data['send_dat'][3] = self.local_id
        self.lora_send_data['send_dat'][4] = self.send_con['fram_type']  # Ӧ��֡����
        self.lora_send_data['send_dat'][5] = 0x00
        self.lora_send_data['send_dat'][6] = 0x01  # �϶�Ӧ��
        self.lora_send_data['send_dat'][7] = 0x00  # CRC
        self.lora_send_data['send_dat'][8] = 0x00
        
        self.send_lora_message(0x01)
        logging.debug(f"����MACӦ�𵽽ڵ�: {dest_id}")
    
    def _build_register_response(self):
        """��������ע��Ӧ����Ϣ"""
        self.lora_send_data['pay_len'] = 30
        self.lora_send_data['send_dat'][0] = 0x03  # ����ע��Ӧ����Ϣ
        self.lora_send_data['send_dat'][1] = 18
        self.lora_send_data['send_dat'][2] = self.local_id
        self.lora_send_data['send_dat'][3] = self.lora_recv_data['recv_dat'][5]  # MAC��ַ
        self.lora_send_data['send_dat'][4] = self.lora_recv_data['recv_dat'][6]
        self.lora_send_data['send_dat'][5] = self.lora_recv_data['recv_dat'][7]
        self.lora_send_data['send_dat'][6] = 2  # ��ͨ�ڵ�
        self.lora_send_data['send_dat'][7] = 0  # ��ID��Ч
        self.lora_send_data['send_dat'][8] = 0  # ����ID��Ч
        self.lora_send_data['send_dat'][9] = 0  # �ڵ㳣̬ģʽ
        
        # �����ֶ���Ϊ��Ч
        for i in range(10, 16):
            self.lora_send_data['send_dat'][i] = 0xff
        
        self.send_lora_message(MessageType.LORA_REGISTER_RSP)
        logging.debug("��������������ע��Ӧ����Ϣ")
    
    def _handle_inquiry_message(self):
        """����ѯ����Ϣ,�ڵ�Ӧ��"""
        temp = self.lora_recv_data['recv_dat'][4]  # ��ȡ������Ϣ����ѯ��ʽ���ж����Ӧ��
        
        if temp & 0x40:  # �ж��Ƿ��д�������
            if self.sys_para['clust_id'] == self.local_id:  # ֻ�д��׽ڵ����Ӧ��
                self.cluster_poll_sta = 1  # ��ʶ����ѯ����
                self._build_cluster_inquiry_response()
        elif (temp & 0x1) and self.traffic_data['traffic_pack']:  # ѯ��ҵ������,����ҵ������
            self.traffic_send_en = True
            self._build_business_inquiry_response()
        elif temp & 0x4:  # �ж��Ƿ���ƽ̨���ݷ���
            self._build_platform_inquiry_response()
        elif temp & 0x8:  # �ж��Ƿ����غ����ݷ���
            self._build_payload_inquiry_response()
        elif temp & 0x10:  # �ж��Ƿ�����·���ݷ���
            self._build_link_inquiry_response()
        else:  # �ڵ�״̬����
            self._build_node_status_inquiry_response()
        
        self.send_con['netman_send_en'] = False
    
    def _build_cluster_inquiry_response(self):
        """��������ѯ��Ӧ��"""
        self.lora_send_data['pay_len'] = 11
        self.lora_send_data['send_dat'][0] = 0x21
        self.lora_send_data['send_dat'][1] = 11
        self.lora_send_data['send_dat'][2] = self.lora_recv_data['recv_dat'][3]  # ��ȡĿ�ĵ�ַ
        self.lora_send_data['send_dat'][3] = self.local_id
        self.lora_send_data['send_dat'][4] = self.sys_para['clust_numb']
        temp = self.sys_para['clust_numb'] * 1000  # ����ÿ���ڵ���Ҫ����10�����
        self.lora_send_data['send_dat'][5] = (temp >> 8) & 0xff
        self.lora_send_data['send_dat'][6] = temp & 0xff
        self.lora_send_data['send_dat'][7] = 0
        self.lora_send_data['send_dat'][8] = 0
        
        self.send_lora_message(MessageType.LORA_INQUIRY_RSP)
    
    def _build_business_inquiry_response(self):
        """����ҵ������ѯ��Ӧ��"""
        self.traffic_send_en = True
        self.lora_send_data['pay_len'] = 11
        self.lora_send_data['send_dat'][0] = 0x21
        self.lora_send_data['send_dat'][1] = 12
        self.lora_send_data['send_dat'][2] = self.lora_recv_data['recv_dat'][3]  # ��ȡĿ�ĵ�ַ
        self.lora_send_data['send_dat'][3] = self.local_id
        self.lora_send_data['send_dat'][4] = (self.traffic_data['traffic_pack'] >> 8) & 0xff
        self.lora_send_data['send_dat'][5] = self.traffic_data['traffic_pack'] & 0xff
        temp = self.traffic_data['traffic_pack'] * 100  # ����ÿ֡1sʱ���ϱ���
        self.lora_send_data['send_dat'][6] = (temp >> 8) & 0xff
        self.lora_send_data['send_dat'][7] = temp & 0xff
        self.lora_send_data['send_dat'][8] = 0
        self.lora_send_data['send_dat'][9] = 0
        
        self.send_lora_message(MessageType.LORA_INQUIRY_RSP)
    
    def _build_node_status_inquiry_response(self):
        """�����ڵ�״̬ѯ��Ӧ��"""
        self.lora_send_data['pay_len'] = 27
        self.lora_send_data['send_dat'][0] = 0x23  # ֡����
        self.lora_send_data['send_dat'][1] = 27   # ���ݳ���
        self.lora_send_data['send_dat'][2] = 0xfe
        self.lora_send_data['send_dat'][3] = self.local_id
        
        for i in range(4, 25):  # ��Ҫ��ʵ
            self.lora_send_data['send_dat'][i] = (
                self.node_data['node_data'][i] if i < len(self.node_data['node_data']) else 0
            )
        
        self.send_lora_message(MessageType.LORA_NODE_STATUS)
    
    def _handle_emergency_response(self):
        """����Ӧ������Ӧ��������ʱ����Ϊ����ע����Ϣ"""
        if self.link_sta == 1:  # �û��ѻ��ϵͳͬ������������
            self._build_network_registration_request()
            self.link_sta = 2
        elif self.node_data['paload_unnormal']:  # �غ��쳣����
            self._build_abnormal_payload_data()
    
    def _build_network_registration_request(self):
        """��������ע��������Ϣ"""
        self.lora_send_data['pay_len'] = 30
        self.lora_send_data['send_dat'][0] = 0x02  # ����ע����Ϣ
        self.lora_send_data['send_dat'][1] = 30
        self.lora_send_data['send_dat'][2] = (self.sys_para['net_id'] >> 8) & 0xff
        self.lora_send_data['send_dat'][3] = self.sys_para['net_id'] & 0xff
        self.lora_send_data['send_dat'][4] = self.local_id
        self.lora_send_data['send_dat'][5] = self.node_para['node_ability']  # �ڵ�����
        self.lora_send_data['send_dat'][6] = self.node_para['Freq_range']    # Ƶ��
        self.lora_send_data['send_dat'][7] = self.node_para['max_Pow']       # �����
        self.lora_send_data['send_dat'][8] = self.node_para['Pow_att']       # ���ʱ仯
        
        # �ռ�����
        coords = ['locat_x', 'locat_y', 'locat_z']
        for i, coord in enumerate(coords):
            base_idx = 9 + i * 3
            coord_val = self.node_para[coord]
            self.lora_send_data['send_dat'][base_idx] = (coord_val >> 16) & 0xff
            self.lora_send_data['send_dat'][base_idx + 1] = (coord_val >> 8) & 0xff
            self.lora_send_data['send_dat'][base_idx + 2] = coord_val & 0xff
        
        # ��ȫ����
        security_data = [0x12, 0x34, 0x56, 0x78, 0x34, 0x56]
        for i, val in enumerate(security_data):
            self.lora_send_data['send_dat'][18 + i] = val
        
        self.send_lora_message(MessageType.LORA_REGISTER_REQ)
        self.link_sta = 2
    
    def _handle_mother_polling(self):
        """����ĸ����ѯ������ϵͳ�㲥��Ϣ"""
        self._build_broadcast_message(0x00)
        self.mother_poll_sta = 2  # �л���״̬2�����ͱ���ҵ��
    
    def _build_broadcast_message(self, target_id: int):
        """�����㲥��Ϣ"""
        if self.sys_para['net_mod'] < 6:  # ������+�͹���ģʽ��ĸ�ǵ�ַ��0,0ʱ϶���͹㲥��Ϣ�����򲻴���0��ID�û�
            if target_id == 0:
                if ((self.next_base_time - self.second_count < 1) and 
                    self.mil_sec_count > 995):
                    self.sys_base_time = self.next_base_time
                    self.sys_time_offset = 0
                    self.next_base_time += self.sys_para['sys_fram_period']  # ������һ��ʱ���׼
                    self.lora_send_data['send_time'] = 0
                else:
                    return
            else:  # 10ms����
                self.sys_time_offset = self.mil_sec_count // 10 + 1
                if self.sys_time_offset < 100:
                    temp = self.second_count
                else:
                    self.sys_time_offset -= 100
                    temp = self.second_count + 1
                
                self.lora_send_data['send_time'] = self.sys_time_offset * 400000
                self.sys_time_offset = (temp << 8) + (self.sys_time_offset & 0xff)
        else:  # 10ms����
            self.sys_time_offset = self.mil_sec_count // 10 + 1
            if self.sys_time_offset < 100:
                self.sys_base_time = self.second_count
            else:
                self.sys_time_offset -= 100
                self.sys_base_time = self.second_count + 1
            
            self.lora_send_data['send_time'] = self.sys_time_offset * 400000
        
        # �����㲥��Ϣ����
        self.lora_send_data['pay_len'] = 29
        self.lora_send_data['send_dat'][0] = 0x00  # �㲥��Ϣ
        self.lora_send_data['send_dat'][1] = 29    # ����
        self.lora_send_data['send_dat'][2] = (self.sys_para['net_id'] >> 8) & 0xff
        self.lora_send_data['send_dat'][3] = self.sys_para['net_id'] & 0xff
        self.lora_send_data['send_dat'][4] = 0     # Ŀǰ��֧��ĸ�Ƿ���
        
        # ʱ��ͬ����Ϣ
        self.lora_send_data['send_dat'][5] = (self.sys_base_time >> 8) & 0xff
        self.lora_send_data['send_dat'][6] = self.sys_base_time & 0xff
        self.lora_send_data['send_dat'][7] = (self.sys_time_offset >> 16) & 0xff
        self.lora_send_data['send_dat'][8] = (self.sys_time_offset >> 8) & 0xff
        self.lora_send_data['send_dat'][9] = self.sys_time_offset & 0xff
        
        # �����������
        self.lora_send_data['send_dat'][10] = (self.sys_para['net_mod'] + 
                                               (self.sys_para['sig_det_time'] << 4))
        
        if self.sys_para['convert_mod'] & 0x60:
            self.sys_para['convert_mod'] -= 0x10
        else:
            self.sys_para['convert_mod'] = 0
        
        self.lora_send_data['send_dat'][11] = (self.sys_para['convert_mod'] + 
                                               (self.sys_para['sys_sig_mod'] << 7))
        
        # Ƶ�ʺͱ������
        self.lora_send_data['send_dat'][12] = (self.sys_para['fre_backw'] >> 8) & 0xff
        self.lora_send_data['send_dat'][13] = self.sys_para['fre_backw'] & 0xff
        self.lora_send_data['send_dat'][14] = (self.sys_para['SF_base_backw'] + 
                                               (self.sys_para['bw_backw'] << 4) + 
                                               (self.sys_para['cr_backw'] << 6))
        self.lora_send_data['send_dat'][15] = (self.sys_para['clust_bw_forw'] + 
                                               (self.sys_para['clust_bw_backw'] << 4))
        self.lora_send_data['send_dat'][16] = ((self.sys_para['clust_bw_backw'] << 4) + 
                                               (self.sys_para['clust_cr_backw'] << 6))
        
        # ϵͳ����
        self.lora_send_data['send_dat'][17] = (self.sys_para['sys_fram_period'] >> 8) & 0xff
        self.lora_send_data['send_dat'][18] = self.sys_para['sys_fram_period'] & 0xff
        self.lora_send_data['send_dat'][19] = self.sys_para['burst_time_base']
        self.lora_send_data['send_dat'][20] = self.sys_para['perm_period']
        self.lora_send_data['send_dat'][21] = self.sys_para['node_sta_det']
        self.lora_send_data['send_dat'][22] = self.sys_para['node_num']
        self.lora_send_data['send_dat'][23] = self.sys_para['max_id']
        self.lora_send_data['send_dat'][24] = target_id
        self.lora_send_data['send_dat'][25] = 0
        self.lora_send_data['send_dat'][26] = 0
        
        self.lora_send_data['send_time_en'] = True
        self.lora_send_data['send_time'] = temp if 'temp' in locals() else self.second_count
        
        self.send_lora_message(MessageType.LORA_BROADCAST)
        logging.debug(f"���������͹㲥��Ϣ��Ŀ��ID: {target_id}")
    
    def _lora_fram_proc(self):
        """LoRa֡���� - ��ӦԭC�����lora_fram_proc����"""
        # ����ͳ����Ϣ
        self.recv_totle_num += 1
        
        # ֡���ʹ���
        fram_type = self.send_con['fram_type']
        
        if fram_type == 0x00 and self.local_id != self.sys_para['mother_id']:
            self._process_broadcast_message()
        elif fram_type == 0x01:  # ����ͨ��Ӧ����Ϣ
            self._process_general_ack()
        elif fram_type == 0x02:  # ���յ�ע����Ϣ
            self._process_registration_request()
        elif fram_type == 0x03:  # ���յ�ע��Ӧ����Ϣ
            self._process_registration_response()
        elif fram_type == 0x04:  # ���սڵ�ģʽ������Ϣ
            self._process_node_control()
        elif fram_type == 0x05:  # ���մؿ�����Ϣ���㲥��Ϣ������ҪӦ��
            self._process_cluster_control()
        # ... �������������Ϣ���ʹ���
    
    def _process_broadcast_message(self):
        """����ϵͳ�㲥��Ϣ"""
        self.recv_fram_self += 1  # ���ڵ����
        
        if self.link_sta == 0:  # δ���������ϵͳͬ�������Ķ˻�״̬
            self._sync_with_network()
        elif self.link_sta == 2:  # �Ѿ����й����룬��δ�ܽ��յ�Ӧ���ж�����ʧ��
            self.link_sta = 1
        elif self.link_sta == 3:  # �յ�Ӧ�𣬵�δ���յ���ѯ���ȴ�һ����Ѳ����
            self.link_sta = 4
        elif self.link_sta == 4:  # �յ�Ӧ�𣬵�δ���յ���ѯ���ָ���ͬ��̬
            self.link_sta = 1
        
        # ����ʱ�����
        self._update_local_time()
        
        # ���ĸ���Ѽ�⡢�����Ѽ��
        self.neighbor_node_sta[self.sys_para['mother_id']].node_det_tim = 1
    
    def _sync_with_network(self):
        """������ͬ��"""
        self.link_sta = 1  # ����ϵͳ�㲥��Ϣ�����ʱ��ͬ��
        
        # ���ı��ز���
        recv_data = self.lora_recv_data['recv_dat']
        self.sys_para['net_id'] = (recv_data[2] << 8) + recv_data[3]
        
        if recv_data[5] == 0:  # ĸ��ID
            self.sys_para['mother_id'] = recv_data[4]
        
        self.sys_para['node_mod'] = 2  # ��ͨ�ڵ�
        self.sys_para['net_mod'] = recv_data[13] & 0x1F  # ���繤��ģʽ
        self.sys_para['gateway_id'] = 0xfe  # ����ID���̶�
        self.sys_para['convert_mod'] = recv_data[14]  # ϵͳ�������л�ģʽ
        
        # ���¸����������...
        self._update_network_parameters()
    
    def _user_exit_detection(self):
        """�û��˳����"""
        if self.sys_para['net_mod'] in [0, 3]:  # �͹���+������ģʽ
            if self.second_count > self.next_base_time:
                self.next_base_time = self.sys_base_time + self.sys_para['sys_fram_period']
                if self.local_id == self.sys_para['mother_id']:
                    self._user_exit_detection_main()
                else:
                    self._user_exit_detection_user()
        elif self.sys_para['net_mod'] in [6, 7]:
            if self.local_id == self.sys_para['mother_id']:
                if self.mother_poll_sta == 1:
                    self._user_exit_detection_main()
            else:
                if self.second_count > self.next_base_time:
                    self.next_base_time = self.sys_base_time + self.sys_para['sys_fram_period']
                    self._user_exit_detection_user()
    
    # ��������
    def set_traffic_data(self, data: bytes):
        """����ҵ������"""
        if len(data) <= 1024:
            self.traffic_data['traffic_dat'][:len(data)] = list(data)
            self.traffic_data['traffic_pack'] = len(data)
            self.traffic_data['data_num'] = 0
            logging.debug(f"����ҵ�����ݣ�����: {len(data)}")
        else:
            logging.warning(f"ҵ�����ݳ��ȳ���: {len(data)}")
    
    def set_node_abnormal_payload(self, abnormal: bool = True):
        """���ýڵ��غ��쳣״̬"""
        self.node_data['paload_unnormal'] = abnormal
        if abnormal:
            self.send_con['unnormal_send_en'] = True
        logging.debug(f"�����غ��쳣״̬: {abnormal}")
    
    def trigger_emergency_send(self):
        """����Ӧ������"""
        self.send_con['unnormal_send_en'] = True
        logging.debug("����Ӧ������")

    def _handle_mother_business_data(self):
        """����ĸ�Ǳ���ҵ������"""
        if self.traffic_data['traffic_pack']:
            self.traffic_send_en = True
            if self.traffic_data['traffic_pack'] == self.traffic_data['data_num']:
                self.traffic_data['traffic_pack'] = 0
                self.poll_node_id = 0
                self.poll_cluster_id = 0
                
                if self.sys_para['net_mod'] == 7:  # ���������ҪӦ������Ҫ����λ��
                    self.mother_poll_sta = 3  # ���׵���ģʽ
                else:
                    self.mother_poll_sta = 4
                self.send_con['poll_ok'] = True
            
            # ����ҵ������
            for i in range(self.lora_send_data['pay_len'] - 2):
                self.lora_send_data['send_dat'][i] = self.traffic_data['traffic_dat'][i]
        
        logging.debug("����ĸ�Ǳ���ҵ������")
    
    def _handle_cluster_head_polling(self):
        """���������ѯ"""
        if self.send_con['poll_ok']:  # ���ʹ���ѯ��Ϣ
            if self.poll_node_id == 1:  # �������Ӧ��ʱ϶
                self.poll_node_id = 0
                self._build_emergency_slot_message()
                self.send_con['poll_ok'] = False
            elif self.poll_cluster_id < self.sys_para['clust_numb']:
                self._build_cluster_poll_message()
                self.send_con['poll_ok'] = False
                self.poll_cluster_id += 1
                self.poll_node_id += 1
            else:
                self.mother_poll_sta = 5  # �л�����������Ԫ
    
    def _build_emergency_slot_message(self):
        """����Ӧ��ʱ϶��Ϣ"""
        self.lora_send_data['pay_len'] = 9
        self.lora_send_data['send_dat'][0] = 0x20
        self.lora_send_data['send_dat'][1] = 9
        self.lora_send_data['send_dat'][2] = 0xff  # Ӧ��ʱ϶����
        self.lora_send_data['send_dat'][3] = self.local_id
        self.lora_send_data['send_dat'][4] = 0x00
        self.lora_send_data['send_dat'][5] = 0
        self.lora_send_data['send_dat'][6] = 0
        
        self.send_lora_message(MessageType.LORA_INQUIRY)
        logging.debug("����Ӧ��ʱ϶��Ϣ")
    
    def _build_cluster_poll_message(self):
        """����������ѯ��Ϣ"""
        if self.poll_cluster_id < len(self.sys_para['clust_node_id']):
            cluster_node_id = self.sys_para['clust_node_id'][self.poll_cluster_id]
        else:
            cluster_node_id = 0
        
        self.lora_send_data['pay_len'] = 9
        self.lora_send_data['send_dat'][0] = 0x20
        self.lora_send_data['send_dat'][1] = 9
        self.lora_send_data['send_dat'][2] = cluster_node_id
        self.lora_send_data['send_dat'][3] = self.local_id
        self.lora_send_data['send_dat'][4] = 0x40
        self.lora_send_data['send_dat'][5] = 0
        self.lora_send_data['send_dat'][6] = 0
        
        self.send_lora_message(MessageType.LORA_INQUIRY)
        logging.debug("����������ѯ��Ϣ")
    
    def _handle_node_polling(self):
        """����ڵ���ѯ"""
        if self.send_con['poll_ok']:
            while True:
                if self.neighbor_node_sta[self.poll_node_id].node_sta == 2:  # �ڵ���������
                    if self.poll_cluster_id == self.sys_para['perm_period']:
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
    
    def _build_node_poll_message(self):
        """�����ڵ���ѯ��Ϣ"""
        self.lora_send_data['pay_len'] = 9
        self.lora_send_data['send_dat'][0] = 0x20
        self.lora_send_data['send_dat'][1] = 9
        self.lora_send_data['send_dat'][2] = self.poll_node_id  # ��ǰ��ѯ�ڵ�ID
        self.poll_cluster_id += 1
        self.poll_node_id += 1
        
        # ��Ҫ�б��Ƿ������ܷ����ĳ��ѯ
        if self.node_ask_sta[self.local_id].node_ask_en:  # ���ܷ�����ѯ
            self.lora_send_data['send_dat'][3] = 0xfe
            self.lora_send_data['send_dat'][4] = self.node_ope_sta[0].node_opedata[0]
        else:
            self.lora_send_data['send_dat'][3] = self.local_id
            self.lora_send_data['send_dat'][4] = self.node_ask_sta[0].node_opedata + 1
        
        # ����ѯ������
        if self.node_ask_sta[0].node_opedata == 2:
            self.node_ask_sta[0].node_opedata = 0x8
        else:
            self.node_ask_sta[0].node_opedata = self.node_ask_sta[0].node_opedata >> 1
        
        self.lora_send_data['send_dat'][5] = 0
        self.lora_send_data['send_dat'][6] = 0
        
        self.send_lora_message(MessageType.LORA_INQUIRY)
        self.send_con['poll_ok'] = False
        logging.debug("�����ڵ���ѯ��Ϣ")
    
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
    
    def _build_ranging_command(self):
        """�������ָ��"""
        self.lora_send_data['pay_len'] = 10
        self.lora_send_data['send_dat'][0] = 0x11
        self.lora_send_data['send_dat'][1] = 10
        self.lora_send_data['send_dat'][2] = self.poll_node_id  # ��ǰ��ѯ�ڵ�ID
        self.lora_send_data['send_dat'][3] = 0xfe
        self.lora_send_data['send_dat'][4] = self.distanc_sta[self.poll_node_id].des_nod_id
        self.lora_send_data['send_dat'][5] = 0  # ������
        self.lora_send_data['send_dat'][6] = 0
        self.lora_send_data['send_dat'][7] = 0
        
        self.send_lora_message(MessageType.LORA_RANGING_REQ)
        self.send_con['poll_ok'] = False
        logging.debug("�������ָ��")
    
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
    
    def _build_status_setting_command(self):
        """����״̬����ָ��"""
        self.lora_send_data['pay_len'] = 12
        self.lora_send_data['send_dat'][0] = 0x04
        self.lora_send_data['send_dat'][1] = 12
        self.lora_send_data['send_dat'][2] = self.poll_node_id  # ��ǰ��ѯ�ڵ�ID
        self.lora_send_data['send_dat'][3] = 0xfe
        
        # ���Ʋ�������
        for i in range(6):
            self.lora_send_data['send_dat'][4 + i] = self.node_ope_sta[self.poll_node_id].node_opedata[i]
        
        self.lora_send_data['send_dat'][10] = 0
        self.lora_send_data['send_dat'][11] = 0
        
        self.send_lora_message(MessageType.LORA_NODE_CONTROL)
        self.send_con['poll_ok'] = False
        logging.debug("����״̬����ָ��")
    
    def _handle_cluster_business_data(self):
        """�������ҵ������"""
        if self.traffic_data['traffic_pack']:
            self.traffic_send_en = True
            
            if self.traffic_data['traffic_pack'] == self.traffic_data['data_num']:
                self.traffic_data['traffic_pack'] = 0
                self.cluster_poll_sta = 2  # ҵ�����ݷ�����ɣ��л�����ѯ״̬
            else:
                self.lora_send_data['pay_len'] = self.traffic_data['traffic_dat'][1]
                # ����ҵ������
                for i in range(self.lora_send_data['pay_len']):
                    self.lora_send_data['send_dat'][i] = self.traffic_data['traffic_dat'][i]
                
                self.send_con['poll_ok'] = False
                self.traffic_data['data_num'] += 1
        
        logging.debug("�������ҵ������")
    
    def _handle_cluster_node_polling(self):
        """������׽ڵ���ѯ"""
        if self.send_con['poll_ok']:
            while True:
                if self.poll_node_id < len(self.sys_para['clust_node_id']):
                    cluster_node_id = self.sys_para['clust_node_id'][self.poll_node_id]
                    if self.neighbor_node_sta[cluster_node_id].node_sta:  # �жϽڵ��Ƿ�����
                        break
                self.poll_node_id += 1
                if self.poll_node_id > 0x7e:  # �ﵽ���ڵ�ID
                    self.cluster_poll_sta = 3  # �л���״̬��۲���
                    break
            
            if (self.poll_node_id <= 0x7e and 
                self.poll_node_id < len(self.sys_para['clust_node_id'])):
                self._build_cluster_node_poll_message()
    
    def _build_cluster_node_poll_message(self):
        """�������׽ڵ���ѯ��Ϣ"""
        self.lora_send_data['pay_len'] = 9
        self.lora_send_data['send_dat'][0] = 0x20
        self.lora_send_data['send_dat'][1] = 9
        self.lora_send_data['send_dat'][2] = self.poll_node_id  # ��ǰ��ѯ�ڵ�ID
        self.lora_send_data['send_dat'][3] = self.local_id
        self.lora_send_data['send_dat'][4] = self.node_ask_sta[0].node_opedata + 1
        
        # ����ѯ������
        if self.node_ask_sta[0].node_opedata == 2:
            self.node_ask_sta[0].node_opedata = 0x8
        else:
            self.node_ask_sta[0].node_opedata = self.node_ask_sta[0].node_opedata >> 1
        
        self.lora_send_data['send_dat'][5] = 0
        self.lora_send_data['send_dat'][6] = 0
        
        self.send_lora_message(MessageType.LORA_INQUIRY)
        self.send_con['poll_ok'] = False
        logging.debug("�������׽ڵ���ѯ��Ϣ")
    
    def _handle_cluster_status_aggregation(self):
        """�������״̬���"""
        self.lora_send_data['send_dat'][0] = 0x25
        self.lora_send_data['send_dat'][2] = self.sys_para['mother_id']  # Ŀ��ĸ��ID
        self.lora_send_data['send_dat'][3] = self.local_id
        self.lora_send_data['send_dat'][4] = self.sys_para['clust_numb']
        self.lora_send_data['send_dat'][5] = self.local_id  # �ڵ�ID
        self.lora_send_data['send_dat'][6] = 0xf  # ���ڵ�״̬
        
        j = 8
        for i in range(1, self.sys_para['clust_numb']):
            if i < len(self.sys_para['clust_node_id']):
                cluster_node_id = self.sys_para['clust_node_id'][i]
                self.lora_send_data['send_dat'][j] = cluster_node_id  # �ڵ�ID
                self.lora_send_data['send_dat'][j + 1] = self.neighbor_node_sta[cluster_node_id].node_healty_sta  # �ڵ�״̬
                j += 2
        
        self.node_ask_sta[0].node_opedata = self.node_ask_sta[0].node_opedata >> 1
        j += 2
        
        self.lora_send_data['pay_len'] = j  # ֡���ݳ���
        self.lora_send_data['send_dat'][1] = self.lora_send_data['pay_len']
        
        self.send_lora_message(MessageType.LORA_CLUSTER_STATUS)
        self.cluster_poll_sta = 0  # ���׷���Ӧ�𣬽�����ǰ��ѯ
        logging.debug("��������״̬�����Ϣ")
    
    def _handle_iot_mode(self):
        """����������ģʽ"""
        if self.sys_para['node_mod'] == 0:  # ĸ��
            self._build_broadcast_message(0x00)  # ĸ�Ƿ��͹㲥��Ϣ��ϵͳ��Ĭ��Ǳ��
        elif self.link_sta == 4:  # �����ڵ�
            self._handle_node_periodic_transmission()
        elif self.link_sta == 2:  # �Ѿ����ͬ������������ע����Ϣ
            self._build_network_registration_request()
    
    def _handle_node_periodic_transmission(self):
        """����ڵ������Դ���"""
        temp = self.sys_base_time + self.local_id * 5
        if self.second_count > temp:
            if self.node_data['node_period']:  # ���ͽڵ�״̬
                if temp < self.second_count:
                    temp += self.node_data['node_period']
                    
                    self.lora_send_data['pay_len'] = 27  # ���ݳ���
                    self.lora_send_data['send_dat'][0] = 0x23  # ֡����
                    
                    for i in range(4, 25):
                        self.lora_send_data['send_dat'][i] = (
                            self.node_data['node_data'][i] if i < len(self.node_data['node_data']) else 0
                        )
                    
                    self.send_lora_message(MessageType.LORA_NODE_STATUS)
                
                # ����Ƿ���Ҫ������������
                if (self.lora_send_data['pay_len'] and 
                    self.node_data['sat_period'] and 
                    self.node_data['sat_time'] < self.second_count):
                    self._build_satellite_data()
                
                # ����Ƿ���Ҫ�����غ�����
                if (self.lora_send_data['pay_len'] == 0 and 
                    self.node_data['paload_period'] and 
                    self.node_data['paload_time'] < self.second_count):
                    self._build_payload_data()
    
    def _build_satellite_data(self):
        """������������"""
        self.node_data['sat_time'] += self.node_data['sat_period']
        self.lora_send_data['pay_len'] = 18
        self.lora_send_data['send_dat'][0] = 0x26
        self.lora_send_data['send_dat'][1] = 11
        self.lora_send_data['send_dat'][2] = self.lora_recv_data['recv_dat'][3]  # ��ȡĿ�ĵ�ַ
        self.lora_send_data['send_dat'][3] = self.local_id
        
        for i in range(4, 18):
            self.lora_send_data['send_dat'][i] = (
                self.node_data['sat_data'][i] if i < len(self.node_data['sat_data']) else 0
            )
        
        self.send_lora_message(MessageType.LORA_PLATFORM_DATA)
        logging.debug("������������")
    
    def _build_payload_data(self):
        """�����غ�����"""
        self.node_data['paload_time'] += self.node_data['paload_period']
        self.lora_send_data['pay_len'] = 18
        self.lora_send_data['send_dat'][0] = 0x26
        self.lora_send_data['send_dat'][1] = 11
        self.lora_send_data['send_dat'][2] = self.lora_recv_data['recv_dat'][3]  # ��ȡĿ�ĵ�ַ
        self.lora_send_data['send_dat'][3] = self.local_id
        
        if self.node_data['paload_unnormal']:
            self.lora_send_data['send_dat'][4] = 2
            self.node_data['paload_unnormal'] = False
        else:
            self.lora_send_data['send_dat'][4] = 1
        
        for i in range(5, 18):
            self.lora_send_data['send_dat'][i] = (
                self.node_data['payload_data'][i] if i < len(self.node_data['payload_data']) else 0
            )
        
        self.send_lora_message(MessageType.LORA_PLATFORM_DATA)
        logging.debug("�����غ�����")
    
    def _handle_network_management_data(self):
        """���������������"""
        self.lora_send_data['pay_len'] = self.netman_recv_dat[1]
        
        for i in range(self.netman_recv_dat[1]):
            self.lora_send_data['send_dat'][i] = self.netman_recv_dat[i]
        
        # ҵ�����ݰ�����ϣ�֪ͨ���ط����µ�ҵ��
        self.netman_new_dat = False
        logging.debug("���������������")
    
    def _handle_mother_lost_mode(self):
        """����ĸ�Ƕ�ʧģʽ"""
        temp = self.lora_recv_data['recv_ok_time'] + self.time_out
        if self.second_count > temp:
            self.lora_send_data['pay_len'] = 14
            self.lora_send_data['send_dat'][0] = 0x1A
            self.lora_send_data['send_dat'][1] = 14
            self.lora_send_data['send_dat'][2] = self.local_id
            self.lora_send_data['send_dat'][3] = 0
            self.lora_send_data['send_dat'][4] = 234  # �������ר�ŵ���Ը�㷨
            self.lora_send_data['send_dat'][5] = self.node_para['node_ability']
            
            # ���̶�ֵ
            fixed_values = [0x12, 0x34, 0x56, 0x78, 0x90, 0xef]
            for i, val in enumerate(fixed_values):
                if i + 6 < 12:
                    self.lora_send_data['send_dat'][i + 6] = val
            
            self.send_lora_message(MessageType.LORA_MOTHER_ELECTION)
            logging.debug("����ĸ�Ƕ�ʧģʽ")
    
    def _handle_node_status_response(self):
        """����ڵ�״̬��Ӧ"""
        # ������ģʽ��ĸ����ҪӦ��
        if (self.sys_para['net_mod'] < 6) and (self.sys_para['node_mod'] == 0):
            self._build_broadcast_message(self.send_con['currend_id'])
            self.send_con['netman_send_en'] = False
        logging.debug("����ڵ�״̬��Ӧ")
    
    def _handle_platform_data_response(self):
        """����ƽ̨������Ӧ"""
        # ������ģʽ��ĸ����ҪӦ��
        if (self.sys_para['net_mod'] < 6) and (self.sys_para['node_mod'] == 0):
            self._build_broadcast_message(self.send_con['currend_id'])
            self.send_con['netman_send_en'] = False
        logging.debug("����ƽ̨������Ӧ")
    
    def _handle_link_status_response(self):
        """������·״̬��Ӧ"""
        # ������ģʽ��ĸ����ҪӦ��
        if (self.sys_para['net_mod'] < 6) and (self.sys_para['node_mod'] == 0):
            self._build_broadcast_message(self.send_con['currend_id'])
            self.send_con['netman_send_en'] = False
        logging.debug("������·״̬��Ӧ")
    
    def _handle_mother_election_response(self):
        """����ĸ��ѡ����Ӧ"""
        if self.lora_recv_data['recv_dat'][2] == self.local_id - 1:  # ��һ���������ݵ�ǰһ��ID
            self.lora_send_data['pay_len'] = 14
            self.lora_send_data['send_dat'][0] = 0x1A
            self.lora_send_data['send_dat'][1] = 14
            self.lora_send_data['send_dat'][2] = self.local_id
            self.lora_send_data['send_dat'][3] = 0
            self.lora_send_data['send_dat'][4] = 234  # �������ר�ŵ���Ը�㷨
            self.lora_send_data['send_dat'][5] = self.node_para['node_ability']
            
            # ���̶�ֵ
            fixed_values = [0x12, 0x34, 0x56, 0x78, 0x90, 0xef]
            for i, val in enumerate(fixed_values):
                if i + 6 < 12:
                    self.lora_send_data['send_dat'][i + 6] = val
            
            self.send_lora_message(MessageType.LORA_MOTHER_ELECTION)
        elif self.local_id > self.lora_recv_data['recv_dat'][2]:
            self.time_out = (self.local_id - self.lora_recv_data['recv_dat'][3]) * 100  # ��ʱ���
        
        logging.debug("����ĸ��ѡ����Ӧ")
    
    def _build_platform_inquiry_response(self):
        """����ƽ̨����ѯ����Ӧ"""
        self.lora_send_data['pay_len'] = 18
        self.lora_send_data['send_dat'][0] = 0x26
        self.lora_send_data['send_dat'][1] = 11
        self.lora_send_data['send_dat'][2] = self.lora_recv_data['recv_dat'][3]  # ��ȡĿ�ĵ�ַ
        self.lora_send_data['send_dat'][3] = self.local_id
        
        for i in range(4, 18):
            self.lora_send_data['send_dat'][i] = (
                self.node_data['sat_data'][i] if i < len(self.node_data['sat_data']) else 0
            )
        
        self.send_lora_message(MessageType.LORA_PLATFORM_DATA)
        logging.debug("����ƽ̨����ѯ����Ӧ")
    
    def _build_payload_inquiry_response(self):
        """�����غ�����ѯ����Ӧ"""
        self.lora_send_data['pay_len'] = 18
        self.lora_send_data['send_dat'][0] = 0x26
        self.lora_send_data['send_dat'][1] = 11
        self.lora_send_data['send_dat'][2] = self.lora_recv_data['recv_dat'][3]  # ��ȡĿ�ĵ�ַ
        self.lora_send_data['send_dat'][3] = self.local_id
        
        if self.node_data['paload_unnormal']:
            self.lora_send_data['send_dat'][4] = 2
            self.node_data['paload_unnormal'] = False
        else:
            self.lora_send_data['send_dat'][4] = 1
        
        for i in range(5, 18):
            self.lora_send_data['send_dat'][i] = (
                self.node_data['payload_data'][i] if i < len(self.node_data['payload_data']) else 0
            )
        
        self.send_lora_message(MessageType.LORA_PLATFORM_DATA)
        logging.debug("�����غ�����ѯ����Ӧ")
    
    def _build_link_inquiry_response(self):
        """������·����ѯ����Ӧ"""
        # ��������Ҫ���ھӽڵ�Ĺ��ʽ�������
        logging.debug("������·����ѯ����Ӧ - ���ܱ���")
    
    def _build_abnormal_payload_data(self):
        """�����쳣�غ�����"""
        self.lora_send_data['pay_len'] = 18
        self.lora_send_data['send_dat'][0] = 0x26
        self.lora_send_data['send_dat'][1] = 11
        self.lora_send_data['send_dat'][2] = self.lora_recv_data['recv_dat'][3]  # ��ȡĿ�ĵ�ַ
        self.lora_send_data['send_dat'][3] = self.local_id
        self.lora_send_data['send_dat'][4] = 2  # �쳣��־
        
        for i in range(5, 18):
            self.lora_send_data['send_dat'][i] = (
                self.node_data['payload_data'][i] if i < len(self.node_data['payload_data']) else 0
            )
        
        self.send_lora_message(MessageType.LORA_PLATFORM_DATA)
        self.node_data['paload_unnormal'] = False
        logging.debug("�����쳣�غ�����")
    
    def _process_general_ack(self):
        """����ͨ��Ӧ����Ϣ"""
        if ((self.lora_recv_data['recv_dat'][2] == 0xfe) and 
            (self.local_id == self.sys_para['mother_id'])):  # ���յ�ַ�����ܣ�������ĸ��
            
            # ĸ�Ǹ��Ľڵ�״̬�����⴦��
            fram_type = self.lora_recv_data['recv_dat'][4]
            node_id = self.lora_recv_data['recv_dat'][3]
            
            if fram_type == 0x03:  # ע��Ӧ����Ϣ
                if self.neighbor_node_sta[node_id].node_sta == 1:
                    self.neighbor_node_sta[node_id].node_sta = 2
            elif fram_type == 0x04:  # �ڵ����������״̬
                ope_data = self.node_ope_sta[node_id].node_opedata[0]
                if ope_data == 0:    # ��̬
                    self.neighbor_node_sta[node_id].node_sta = 2
                elif ope_data == 1:  # ��Ĭ
                    self.neighbor_node_sta[node_id].node_sta = 3
                elif ope_data == 2:  # Ǳ��
                    self.neighbor_node_sta[node_id].node_sta = 4
                else:                # ����
                    self.neighbor_node_sta[node_id].node_sta = 0
            
            self.netman_send_en = True    # ͸��������
            self.send_con['poll_ok'] = True  # ������������Ҫ�л����µĽڵ�
        
        logging.debug("����ͨ��Ӧ����Ϣ")
    
    def _process_registration_request(self):
        """����ע������"""
        # ��������Ƿ����ߣ�������ͬʱת�������ܣ���ʱ����
        if self.local_id == self.sys_para['mother_id']:  # ������ĸ�ǣ�ĸ�Ǵ������Ϣ
            recv_data = self.lora_recv_data['recv_dat']
            
            # ��֤��ȫ����
            if ((recv_data[21] == 0x12) or (recv_data[22] == 0x34) or 
                (recv_data[23] == 0x56) or (recv_data[24] == 0x78)):
                
                node_id = recv_data[4]
                node_status = self.neighbor_node_sta[node_id]
                
                # ���½ڵ�״̬��Ϣ
                node_status.node_sta = 1
                node_status.node_position = 2
                node_status.mac_addr = [recv_data[5], recv_data[6], recv_data[7]]
                node_status.node_ability = recv_data[8]
                node_status.freq_rang = recv_data[9]
                node_status.node_pow = self.lora_recv_data['recv_SNR']  # ʹ�������
                node_status.VGA = recv_data[11]
                
                # �ռ�����
                node_status.pos_x = ((recv_data[12] << 16) + (recv_data[13] << 8) + recv_data[14])
                node_status.pos_y = ((recv_data[15] << 16) + (recv_data[16] << 8) + recv_data[17])
                node_status.pos_z = ((recv_data[18] << 16) + (recv_data[19] << 8) + recv_data[20])
                
                # ��������
                node_status.cluster_id = 0
                node_status.node_det_num = 3
                node_status.node_det_tim = 1
                node_status.node_SF = self.sys_para['SF_base_backw']
                node_status.node_sta = 0x00
                
                self.send_con['recv_send_en'] = True
        
        self.netman_send_en = True  # ͸��������
        logging.debug("����ע������")
    
    def _process_registration_response(self):
        """����ע��Ӧ��"""
        # MAC��ַƥ�䣬����״̬
        recv_data = self.lora_recv_data['recv_dat']
        if ((recv_data[4] == self.node_para['mac_addr'][2]) and 
            (recv_data[5] == self.node_para['mac_addr'][1]) and 
            (recv_data[6] == self.node_para['mac_addr'][0])):
            
            self.link_sta = 3  # �ڵ���ȷ����
            self.neighbor_node_sta[self.sys_para['mother_id']].node_det_num = 3
            self.send_con['recv_send_en'] = True  # ������ҪӦ��ͨ��ACK
        
        logging.debug("����ע��Ӧ��")
    
    def _process_node_control(self):
        """����ڵ����"""
        # IDƥ�䣬���ı��������ϱ�ʱ������
        if self.lora_recv_data['recv_dat'][2] == self.local_id:
            recv_data = self.lora_recv_data['recv_dat']
            
            self.sys_para['node_mod'] = recv_data[4]  # �ڵ�����
            self.link_sta = recv_data[5] + 4          # �ڵ�״̬
            self.re_enter_time = (recv_data[6] << 8) + recv_data[7]  # ������ʱ��
            
            if recv_data[8] > 0:
                self.node_data['node_period'] = recv_data[8] * 10
                self.node_data['node_time'] = self.second_count
            
            if recv_data[9] > 0:
                self.node_data['sat_period'] = recv_data[9] * 10
                self.node_data['sat_time'] = self.second_count
            
            if recv_data[10] > 0:
                self.node_data['paload_period'] = recv_data[10] * 10
                self.node_data['paload_time'] = self.second_count
        
        self.send_con['recv_send_en'] = True
        logging.debug("����ڵ����")
    
    def _process_cluster_control(self):
        """����ؿ���"""
        # �㲥��Ϣ������ҪӦ��
        recv_data = self.lora_recv_data['recv_dat']
        cluster_count = recv_data[4]  # ���õĴص���Ŀ
        j = 5
        
        for i in range(cluster_count):
            temp1 = ((recv_data[j] << 24) + (recv_data[j+1] << 16) + 
                    (recv_data[j+2] << 8) + recv_data[j+3])
            j += 4
            node_count = recv_data[j]
            j += 1
            found_cluster = False
            
            for k in range(node_count):
                if recv_data[j] == self.local_id:
                    if k == 0:
                        self.sys_para['node_mod'] = 1  # ����ID
                        found_cluster = True
                    else:
                        self.sys_para['node_mod'] = 2  # ��ͨ�ڵ�
                else:
                    if found_cluster:
                        self.sys_para['clust_node_id'][k-1] = recv_data[j]
                j += 1
            
            if found_cluster:  # ���ҵ���
                self.sys_para['clust_id'] = (temp1 >> 24) & 0xff
                self.sys_para['clust_numb'] = node_count - 1
                self.cluster_poll_sta = 0
                break
        
        logging.debug("����ؿ���")
    
    def _update_local_time(self):
        """���±���ʱ��"""
        # ����ʱ��������ӹ㲥��Ϣ����ȡʱ����Ϣ
        recv_data = self.lora_recv_data['recv_dat']
        
        # ��ȡʱ���׼��ƫ����
        sys_base_time = (recv_data[5] << 8) + recv_data[6]
        sys_time_offset = ((recv_data[7] << 16) + (recv_data[8] << 8) + recv_data[9])
        
        # ���±���ʱ�����
        self.sys_base_time = sys_base_time
        self.sys_time_offset = sys_time_offset
        
        logging.debug("���±���ʱ��")
    
    def _update_network_parameters(self):
        """�����������"""
        recv_data = self.lora_recv_data['recv_dat']
        
        # �����������ò���
        self.sys_para['clust_id'] = 0xf0  # ����
        self.sys_para['node_num'] = recv_data[22]
        self.sys_para['max_id'] = recv_data[23]
        
        # ����SF����
        self.sys_para['SF_base_forw'] = recv_data[18] & 0xf
        self.sys_para['SF_high_forw'] = (recv_data[18] >> 4) & 0xf
        self.sys_para['clust_SF_base_forw'] = recv_data[19] & 0xf
        self.sys_para['clust_SF_base_backw'] = (recv_data[19] >> 4) & 0xf
        
        # ϵͳ�ź�ģʽ
        self.sys_para['sys_sig_mod'] = (self.sys_para['SF_base_forw'] > 
                                       self.sys_para['SF_high_forw'])
        
        # ��������
        self.sys_para['wake_mod'] = 1
        self.sys_para['un_permit'] = 1
        self.sys_para['perm_period'] = recv_data[20]
        
        # ϵͳʱ�����
        self.sys_base_time = 0
        self.sys_time_offset = 0
        self.sys_para['sys_fram_period'] = (recv_data[15] << 8) + recv_data[16]
        self.sys_para['burst_time_base'] = recv_data[17]
        
        logging.debug("�����������")
    
    def _user_exit_detection_main(self):
        """ĸ�ǡ������û��˳����"""
        for i in range(128):
            if self.neighbor_node_sta[i].node_sta == 2:  # �ڵ�������״̬�����м��
                if self.neighbor_node_sta[i].node_det_tim:  # ��ȷ��⵽�ź�
                    self.neighbor_node_sta[i].node_det_tim = 0
                    sf_index = min(self.neighbor_node_sta[i].node_pow, len(self.SF_table) - 1)
                    temp_sf = self.SF_table[sf_index]
                    
                    if temp_sf >= self.neighbor_node_sta[i].node_SF:  # ����ȱ�С����Ҫ����SF
                        if self.neighbor_node_sta[i].node_SF < self.sys_para['SF_base_backw']:
                            self.neighbor_node_sta[i].node_SF += 1
                        self.neighbor_node_sta[i].node_det_num = 3
                    elif temp_sf < self.neighbor_node_sta[i].node_SF:  # ����ȱ����Ҫ����SF
                        if self.neighbor_node_sta[i].node_det_num > 8:
                            if self.neighbor_node_sta[i].node_SF > 7:
                                self.neighbor_node_sta[i].node_SF -= 1
                            self.neighbor_node_sta[i].node_det_num = 3
                        else:
                            self.neighbor_node_sta[i].node_det_num += 1
                
                elif self.neighbor_node_sta[i].node_det_num > 0:  # δ��ȷ��⵽Ӧ���ź�
                    self.neighbor_node_sta[i].node_det_num -= 1
                    
                    if self.neighbor_node_sta[i].node_SF < self.sys_para['SF_base_backw']:
                        self.neighbor_node_sta[i].node_SF += 1
                    
                    if self.neighbor_node_sta[i].node_det_num == 0:
                        self.neighbor_node_sta[i].node_sta = 0  # �ڵ㲻����
                        self.neighbor_node_sta[i].node_SF = self.sys_para['SF_base_backw']
            
            elif self.neighbor_node_sta[i].node_sta == 1:  # �ڵ�������״̬����δ���յ�Ӧ��
                self.neighbor_node_sta[i].node_sta = 0  # �ڵ㲻����
        
        logging.debug("ĸ���û��˳�������")
    
    def _user_exit_detection_user(self):
        """��ͨ�ڵ��û��˳����"""
        mother_id = self.sys_para['mother_id']
        
        if self.neighbor_node_sta[mother_id].node_det_tim:  # ��⵽ĸ���ź�
            self.neighbor_node_sta[mother_id].node_det_num = 3
            self.neighbor_node_sta[mother_id].node_det_tim = 0
        elif self.user_det_tim:  # δ���յ�ĸ���źţ�����⵽�����û��ź�
            self.neighbor_node_sta[mother_id].node_det_num += 1
            self.user_det_tim = 0
            if self.neighbor_node_sta[mother_id].node_det_num == 6:
                self.link_sta = 0  # δ��⵽ĸ���źţ��û�����
        else:  # δ���յ�ĸ���źţ�δ��⵽�����û��ź�
            if self.neighbor_node_sta[mother_id].node_det_num == 0:
                self.link_sta = 5
                self.sys_para['net_mod'] = 8  # ĸ�Ƕ�ʧ״̬
            self.neighbor_node_sta[mother_id].node_det_num -= 1
        
        logging.debug("��ͨ�ڵ��û��˳�������")