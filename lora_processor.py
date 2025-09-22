#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import threading
import logging
import time
from protocol import MessageType


class LoRaProcessor:
    """LoRa消息处理器 - 基于组网模式的处理逻辑"""
    
    def __init__(self, message_sender=None):
        self.running = False
        self.thread = None
        self.message_sender = message_sender  # 消息发送接口
        
        # 初始化系统参数
        self.sys_para = {
            'net_mod': 0,  # 网络模式: 0-物联网方式，6-母星丢失模式，7-簇首调度模式
            'node_mod': 2,  # 节点模式: 0-母星，1-簇首，2-普通节点
            'mother_id': 0,  # 母星ID固定为0
            'gateway_id': 0xFE,  # 网管ID
            'clust_id': 0x80,  # 簇首ID
            'clust_numb': 0,  # 簇内节点数
        }
        
        # 初始化节点参数
        self.local_id = 0x10  # 本机节点ID，可以通过配置文件设置
        
        # 发送控制状态
        self.send_con = {
            'recv_send_en': False,
            'fram_type': 0,
            'unnormal_send_en': False,
            'netman_send_en': False,
            'poll_ok': True,
            'currend_id': 0
        }
        
        # LoRa发送数据结构
        self.lora_send_data = {
            'pay_len': 0,
            'send_dat': [0] * 256,
            'send_time': 0,
            'send_time_stamp': 0
        }
        
        # LoRa接收数据结构
        self.lora_recv_data = {
            'recv_dat': [0] * 256,
            'recv_time': 0,
            'recv_ok_time': 0
        }
        
        # 节点状态
        self.link_sta = 0  # 0-空闲，1-信号搜索，2-获得同步，3-发送入网消息，4-完成入网
        self.mother_poll_sta = 1  # 母星轮询状态
        self.cluster_poll_sta = 0  # 簇首轮询状态
        self.traffic_send_en = False
        
        # 时间相关
        self.second_count = 0
        self.sys_base_time = 0
        
        # 轮询相关
        self.poll_node_id = 0
        self.poll_cluster_id = 0
        
        # 网络管理数据
        self.netman_new_dat = False
        self.netman_recv_dat = [0] * 1024
        
        # 业务数据
        self.traffic_data = {
            'traffic_pack': 0,
            'data_num': 0,
            'traffic_dat': [0] * 1024
        }
        
        # 节点数据
        self.node_data = {
            'node_data': [0] * 32,
            'node_period': 60,  # 节点状态数据上报周期(秒)
            'paload_unnormal': False,
            'sat_data': [0] * 32,
            'sat_period': 300,  # 卫星状态数据上报周期(秒)
            'sat_time': 0,
            'payload_data': [0] * 32,
            'paload_period': 120,  # 载荷数据上报周期(秒)
            'paload_time': 0
        }
    
    def set_message_sender(self, sender):
        """设置消息发送接口"""
        self.message_sender = sender
    
    def start(self):
        """启动LoRa处理器"""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._lora_send_proc, daemon=True)
        self.thread.start()
        logging.info("LoRa处理器已启动")
    
    def stop(self):
        """停止LoRa处理器"""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        logging.info("LoRa处理器已停止")
    
    def set_node_type(self, node_type: str):
        """设置节点类型"""
        if node_type == "mother":
            self.sys_para['node_mod'] = 0
            self.local_id = 0  # 母星ID固定为0
            logging.info("节点类型设置为：母星 (ID=0)")
        elif node_type == "cluster":
            self.sys_para['node_mod'] = 1  
            self.local_id = self.sys_para['clust_id']
            logging.info("节点类型设置为：簇首")
        else:
            self.sys_para['node_mod'] = 2
            logging.info("节点类型设置为：普通节点")
    
    def send_lora_message(self, msg_type: int, target_addr: tuple = None):
        """发送LoRa消息"""
        if not self.message_sender:
            logging.warning("消息发送接口未设置")
            return
        
        try:
            # 将发送数据转换为bytes格式
            content = bytes(self.lora_send_data['send_dat'][:self.lora_send_data['pay_len']])
            
            # 如果没有指定目标地址，使用广播地址
            if target_addr is None:
                target_addr = ('255.255.255.255', 8003)  # LoRa端口广播
            
            self.message_sender(target_addr, msg_type, content)
            logging.debug(f"发送LoRa消息: 类型=0x{msg_type:02X}, 长度={len(content)}")
            
        except Exception as e:
            logging.error(f"发送LoRa消息失败: {e}")
    
    def _lora_send_proc(self):
        """LoRa发送处理主循环 - 组网模式"""
        while self.running:
            try:
                # 模拟时间计数器
                self.second_count += 1
                
                if self.send_con['recv_send_en']:  # 接收数据需要应答
                    self._handle_received_message()
                elif self.send_con['unnormal_send_en']:  # 应急数据应答
                    self._handle_emergency_message()
                elif self.netman_new_dat:  # 网络数据发送
                    self._handle_network_data()
                elif self.sys_para['net_mod'] == 6:  # 母星丢失模式
                    self._handle_mother_lost_mode()
                elif self.mother_poll_sta == 1:  # 母星轮训
                    self._handle_mother_polling()
                elif self.mother_poll_sta == 2:  # 发送母星本地业务数据
                    self._handle_mother_business_data()
                elif self.mother_poll_sta in [3, 4, 5, 6]:  # 各种轮询模式
                    self._handle_polling_modes()
                elif self.cluster_poll_sta in [1, 2, 3]:  # 簇首操作
                    self._handle_cluster_operations()
                elif self.sys_para['net_mod'] in [0, 3]:  # 物联网模式
                    self._handle_iot_mode()
                
                # 模拟处理间隔
                time.sleep(1)  # 1秒间隔
                
            except Exception as e:
                logging.error(f"LoRa发送处理出错: {e}")
                time.sleep(1)
    
    def _handle_received_message(self):
        """处理接收到的消息应答"""
        fram_type = self.send_con['fram_type']
        
        if fram_type == 0x11:  # 接收到测距调度消息，发起测距申请
            self._build_ranging_request()
        elif fram_type == 0x12:  # 接收到测距申请，发送测距应答消息
            self._build_ranging_response()
        elif fram_type == 0x13:  # 接收到测距应答消息，进行测距消息上报
            self._build_ranging_report()
        elif fram_type == 0x02:  # 接收到注册消息
            self._build_register_response()
        elif fram_type == 0x03:  # 接收到注册应答消息
            self._handle_register_ack()
        elif fram_type == 0x04:  # 节点模式控制消息
            self._handle_node_control()
        elif fram_type == 0x20:  # 询问消息，节点应答
            self._handle_inquiry_message()
        elif fram_type == 0x23:  # 接收到节点状态数据
            self._handle_node_status()
        elif fram_type == 0x26:  # 接收到平台数据上报
            self._handle_platform_data()
        
        self.send_con['recv_send_en'] = False
    
    def _build_ranging_request(self):
        """构建测距申请消息"""
        self.lora_send_data['pay_len'] = 14  # 不包含消息头的数据长度
        self.lora_send_data['send_dat'][0] = self.local_id
        self.lora_send_data['send_dat'][1] = self.lora_recv_data['recv_dat'][4]
        # 清零保留字段
        for i in range(2, 14):
            self.lora_send_data['send_dat'][i] = 0
        
        # 发送测距申请消息
        self.send_lora_message(MessageType.LORA_RANGING_APPLY)
        logging.debug("构建并发送测距申请消息")
    
    def _build_ranging_response(self):
        """构建测距应答消息"""
        self.lora_send_data['pay_len'] = 14
        self.lora_send_data['send_dat'][0] = self.local_id
        self.lora_send_data['send_dat'][1] = self.lora_recv_data['recv_dat'][4]
        
        # 设置接收时间戳
        recv_time = self.lora_recv_data['recv_time']
        self.lora_send_data['send_dat'][5] = (recv_time >> 24) & 0xff
        self.lora_send_data['send_dat'][6] = (recv_time >> 16) & 0xff
        self.lora_send_data['send_dat'][7] = (recv_time >> 8) & 0xff
        self.lora_send_data['send_dat'][8] = recv_time & 0xff
        
        # 发送测距应答消息
        self.send_lora_message(MessageType.LORA_RANGING_RSP)
        logging.debug("构建并发送测距应答消息")
    
    def _build_ranging_report(self):
        """构建测距报告消息"""
        # 计算测距结果
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
        
        # 发送测距报告消息
        self.send_lora_message(MessageType.LORA_RANGING_RSP)
        logging.debug("构建并发送测距报告消息")
    
    def _build_register_response(self):
        """构建入网注册应答消息"""
        self.lora_send_data['pay_len'] = 16
        self.lora_send_data['send_dat'][0] = self.local_id
        self.lora_send_data['send_dat'][1] = self.lora_recv_data['recv_dat'][5]  # MAC地址
        self.lora_send_data['send_dat'][2] = self.lora_recv_data['recv_dat'][6]
        self.lora_send_data['send_dat'][3] = self.lora_recv_data['recv_dat'][7]
        self.lora_send_data['send_dat'][4] = 2  # 普通节点
        # 其他字段设置为无效
        for i in range(5, 16):
            self.lora_send_data['send_dat'][i] = 0xff if i < 12 else 0
        
        # 发送注册应答消息
        self.send_lora_message(MessageType.LORA_REGISTER_RSP)
        logging.debug("构建并发送入网注册应答消息")
    
    def _handle_register_ack(self):
        """处理注册应答消息"""
        logging.debug("处理注册应答消息")
    
    def _handle_node_control(self):
        """处理节点控制消息"""
        logging.debug("处理节点控制消息")
    
    def _handle_inquiry_message(self):
        """处理询问消息"""
        temp = self.lora_recv_data['recv_dat'][4]
        
        if temp & 0x40:  # 判断是否有簇首数据
            if self.sys_para['clust_id'] == self.local_id:  # 只有簇首节点可以应答
                self.cluster_poll_sta = 1
                self._build_cluster_response()
        elif (temp & 0x1) and self.traffic_data['traffic_pack']:  # 询问业务数据
            self.traffic_send_en = True
            self._build_traffic_response()
        elif temp & 0x4:  # 平台数据发送
            self._build_platform_response()
        elif temp & 0x8:  # 载荷数据发送
            self._build_payload_response()
        else:  # 节点状态数据
            self._build_node_status_response()
    
    def _build_cluster_response(self):
        """构建簇首应答"""
        self.lora_send_data['pay_len'] = 11
        self.lora_send_data['send_dat'][0] = self.lora_recv_data['recv_dat'][3]
        self.lora_send_data['send_dat'][1] = self.local_id
        self.lora_send_data['send_dat'][2] = self.sys_para['clust_numb']
        temp = self.sys_para['clust_numb'] * 1000
        self.lora_send_data['send_dat'][3] = (temp >> 8) & 0xff
        self.lora_send_data['send_dat'][4] = temp & 0xff
        
        self.send_lora_message(MessageType.LORA_INQUIRY_RSP)
        logging.debug("构建簇首应答")
    
    def _build_traffic_response(self):
        """构建业务数据应答"""
        self.lora_send_data['pay_len'] = 11
        self.lora_send_data['send_dat'][0] = self.lora_recv_data['recv_dat'][3]
        self.lora_send_data['send_dat'][1] = self.local_id
        self.lora_send_data['send_dat'][2] = (self.traffic_data['traffic_pack'] >> 8) & 0xff
        self.lora_send_data['send_dat'][3] = self.traffic_data['traffic_pack'] & 0xff
        
        self.send_lora_message(MessageType.LORA_INQUIRY_RSP)
        logging.debug("构建业务数据应答")
    
    def _build_platform_response(self):
        """构建平台数据应答"""
        self.lora_send_data['pay_len'] = 18
        self.lora_send_data['send_dat'][0] = self.lora_recv_data['recv_dat'][3]
        self.lora_send_data['send_dat'][1] = self.local_id
        
        for i in range(2, 18):
            self.lora_send_data['send_dat'][i] = self.node_data['sat_data'][i] if i < len(self.node_data['sat_data']) else 0
        
        self.send_lora_message(MessageType.LORA_PLATFORM_DATA)
        logging.debug("构建平台数据应答")
    
    def _build_payload_response(self):
        """构建载荷数据应答"""
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
        logging.debug("构建载荷数据应答")
    
    def _build_node_status_response(self):
        """构建节点状态应答"""
        self.lora_send_data['pay_len'] = 25
        self.lora_send_data['send_dat'][0] = 0xfe  # 目标地址
        self.lora_send_data['send_dat'][1] = self.local_id
        
        # 复制节点数据
        for i in range(2, 23):
            self.lora_send_data['send_dat'][i] = self.node_data['node_data'][i] if i < len(self.node_data['node_data']) else 0
        
        self.send_lora_message(MessageType.LORA_NODE_STATUS)
        logging.debug("构建节点状态应答")
    
    def _handle_node_status(self):
        """处理节点状态数据"""
        if (self.sys_para['net_mod'] < 6) and (self.sys_para['node_mod'] == 0):
            self._build_broadcast_message(self.send_con['currend_id'])
            self.send_con['netman_send_en'] = False
        logging.debug("处理节点状态数据")
    
    def _handle_platform_data(self):
        """处理平台数据上报"""
        if (self.sys_para['net_mod'] < 6) and (self.sys_para['node_mod'] == 0):
            self._build_broadcast_message(self.send_con['currend_id'])
            self.send_con['netman_send_en'] = False
        logging.debug("处理平台数据上报")
    
    # 继续实现其他处理方法...
    def _handle_emergency_message(self):
        """处理应急数据应答"""
        if self.link_sta == 1:  # 用户已获得系统同步，申请入网
            self._build_network_register()
            self.link_sta = 2
        elif self.node_data['paload_unnormal']:  # 载荷异常数据
            self._build_abnormal_payload()
    
    def _build_network_register(self):
        """构建入网注册消息"""
        self.lora_send_data['pay_len'] = 28
        self.lora_send_data['send_dat'][0] = self.sys_para.get('net_id', 0)
        self.lora_send_data['send_dat'][1] = self.local_id
        self.lora_send_data['send_dat'][2] = 0x01  # 节点能力
        
        # 发送入网注册消息
        self.send_lora_message(MessageType.LORA_REGISTER_REQ)
        logging.debug("构建并发送入网注册消息")
    
    def _build_abnormal_payload(self):
        """构建异常载荷数据"""
        self.lora_send_data['pay_len'] = 18
        self.lora_send_data['send_dat'][0] = 0xfe
        self.lora_send_data['send_dat'][1] = self.local_id
        self.lora_send_data['send_dat'][2] = 2  # 异常标志
        
        self.send_lora_message(MessageType.LORA_PLATFORM_DATA)
        self.node_data['paload_unnormal'] = False
        logging.debug("构建异常载荷数据")
    
    def _handle_network_data(self):
        """处理网络数据发送"""
        self.lora_send_data['pay_len'] = self.netman_recv_dat[1]
        for i in range(self.netman_recv_dat[1]):
            self.lora_send_data['send_dat'][i] = self.netman_recv_dat[i]
        self.netman_new_dat = False
        logging.debug("处理网络数据发送")
    
    def _handle_mother_lost_mode(self):
        """处理母星丢失模式"""
        if self.second_count > (self.lora_recv_data['recv_ok_time'] + 10000):
            self._build_mother_election()
    
    def _build_mother_election(self):
        """构建母星选举消息"""
        self.lora_send_data['pay_len'] = 12
        self.lora_send_data['send_dat'][0] = self.local_id
        self.lora_send_data['send_dat'][1] = 0
        self.lora_send_data['send_dat'][2] = 234  # 意愿算法
        self.lora_send_data['send_dat'][3] = 0x01  # 节点能力
        
        self.send_lora_message(MessageType.LORA_MOTHER_ELECTION)
        logging.debug("构建母星选举消息")
    
    def _handle_mother_polling(self):
        """处理母星轮询"""
        self._build_broadcast_message(0x00)
        self.mother_poll_sta = 2
        logging.debug("母星轮询 - 发送广播消息")
    
    def _build_broadcast_message(self, target_id):
        """构建广播消息"""
        self.lora_send_data['pay_len'] = 18
        self.lora_send_data['send_dat'][0] = target_id
        self.lora_send_data['send_dat'][1] = self.local_id
        self.lora_send_data['send_dat'][2] = self.sys_para['net_mod']
        self.lora_send_data['send_dat'][3] = self.sys_para['node_mod']
        self.lora_send_data['send_dat'][4] = self.sys_para['mother_id']
        self.lora_send_data['send_dat'][5] = self.sys_para['gateway_id']
        
        self.send_lora_message(MessageType.LORA_BROADCAST)
        logging.debug(f"构建并发送广播消息，目标ID: {target_id}")
    
    def _handle_mother_business_data(self):
        """处理母星本地业务数据"""
        if self.traffic_data['traffic_pack']:
            self.traffic_send_en = True
            if self.traffic_data['traffic_pack'] == self.traffic_data['data_num']:
                self.traffic_data['traffic_pack'] = 0
                self.mother_poll_sta = 3
                self.send_con['poll_ok'] = True
        logging.debug("处理母星本地业务数据")
    
    def _handle_polling_modes(self):
        """处理各种轮询模式"""
        if self.mother_poll_sta == 3:
            self._handle_cluster_polling()
        elif self.mother_poll_sta == 4:
            self._handle_node_polling()
        elif self.mother_poll_sta == 5:
            self._handle_ranging_operation()
        elif self.mother_poll_sta == 6:
            self._handle_status_setting()
    
    def _handle_cluster_polling(self):
        """处理簇首轮询"""
        if self.send_con['poll_ok'] and self.poll_cluster_id < self.sys_para['clust_numb']:
            self._build_cluster_poll_message()
            self.poll_cluster_id += 1
        else:
            self.mother_poll_sta = 5
    
    def _build_cluster_poll_message(self):
        """构建簇首轮询消息"""
        self.lora_send_data['pay_len'] = 9
        self.lora_send_data['send_dat'][0] = self.sys_para.get('clust_node_id', [0])[self.poll_cluster_id] if self.poll_cluster_id < len(self.sys_para.get('clust_node_id', [])) else 0
        self.lora_send_data['send_dat'][1] = self.local_id
        self.lora_send_data['send_dat'][2] = 0x40
        
        self.send_lora_message(MessageType.LORA_INQUIRY)
        self.send_con['poll_ok'] = False
        logging.debug("构建簇首轮询消息")
    
    def _handle_node_polling(self):
        """处理节点轮询"""
        if self.send_con['poll_ok']:
            self._build_node_poll_message()
            self.poll_node_id += 1
            if self.poll_node_id >= 0x7e:
                self.mother_poll_sta = 5
    
    def _build_node_poll_message(self):
        """构建节点轮询消息"""
        self.lora_send_data['pay_len'] = 9
        self.lora_send_data['send_dat'][0] = self.poll_node_id
        self.lora_send_data['send_dat'][1] = self.local_id
        self.lora_send_data['send_dat'][2] = 0x01
        
        self.send_lora_message(MessageType.LORA_INQUIRY)
        self.send_con['poll_ok'] = False
        logging.debug("构建节点轮询消息")
    
    def _handle_ranging_operation(self):
        """处理测距操作"""
        logging.debug("处理测距操作")
        self.mother_poll_sta = 6
    
    def _handle_status_setting(self):
        """处理状态参数设置"""
        logging.debug("处理状态参数设置")
        self.mother_poll_sta = 1  # 回到初始状态
    
    def _handle_cluster_operations(self):
        """处理簇首操作"""
        if self.cluster_poll_sta == 1:
            self._handle_cluster_business_data()
        elif self.cluster_poll_sta == 2:
            self._handle_cluster_node_polling()
        elif self.cluster_poll_sta == 3:
            self._handle_cluster_status_report()
    
    def _handle_cluster_business_data(self):
        """处理簇首业务数据"""
        if self.traffic_data['traffic_pack']:
            self.traffic_send_en = True
            if self.traffic_data['traffic_pack'] == self.traffic_data['data_num']:
                self.traffic_data['traffic_pack'] = 0
                self.cluster_poll_sta = 2
        logging.debug("处理簇首业务数据")
    
    def _handle_cluster_node_polling(self):
        """处理簇首节点轮询"""
        self.cluster_poll_sta = 3
        logging.debug("处理簇首节点轮询")
    
    def _handle_cluster_status_report(self):
        """处理簇首状态报告"""
        self._build_cluster_status_message()
        self.cluster_poll_sta = 0
        logging.debug("处理簇首状态报告")
    
    def _build_cluster_status_message(self):
        """构建簇首状态消息"""
        self.lora_send_data['pay_len'] = 20
        self.lora_send_data['send_dat'][0] = self.sys_para['mother_id']
        self.lora_send_data['send_dat'][1] = self.local_id
        self.lora_send_data['send_dat'][2] = self.sys_para['clust_numb']
        
        self.send_lora_message(MessageType.LORA_CLUSTER_STATUS)
        logging.debug("构建簇首状态消息")
    
    def _handle_iot_mode(self):
        """处理物联网模式"""
        if self.sys_para['node_mod'] == 0:  # 母星
            self._build_broadcast_message(0x00)
        elif self.link_sta == 4:  # 其他节点
            self._handle_node_periodic_send()
        elif self.link_sta == 2:  # 已经获得同步，发送入网注册消息
            self._build_network_register()
    
    def _handle_node_periodic_send(self):
        """处理节点周期性发送"""
        temp = self.sys_base_time + self.local_id * 5
        if self.second_count > temp:
            if self.node_data['node_period']:
                self._build_node_status_message()
                
                # 检查是否需要发送卫星数据
                if (self.node_data['sat_period'] and 
                    self.node_data['sat_time'] < self.second_count):
                    self._build_satellite_data()
                
                # 检查是否需要发送载荷数据
                if (self.node_data['paload_period'] and 
                    self.node_data['paload_time'] < self.second_count):
                    self._build_payload_data()
    
    def _build_node_status_message(self):
        """构建节点状态消息"""
        self.lora_send_data['pay_len'] = 25
        self.lora_send_data['send_dat'][0] = 0xfe
        self.lora_send_data['send_dat'][1] = self.local_id
        
        for i in range(2, 23):
            self.lora_send_data['send_dat'][i] = self.node_data['node_data'][i] if i < len(self.node_data['node_data']) else 0
        
        self.send_lora_message(MessageType.LORA_NODE_STATUS)
        logging.debug("构建节点状态消息")
    
    def _build_satellite_data(self):
        """构建卫星数据"""
        self.lora_send_data['pay_len'] = 18
        self.lora_send_data['send_dat'][0] = 0xfe
        self.lora_send_data['send_dat'][1] = self.local_id
        
        for i in range(2, 18):
            self.lora_send_data['send_dat'][i] = self.node_data['sat_data'][i] if i < len(self.node_data['sat_data']) else 0
        
        self.send_lora_message(MessageType.LORA_PLATFORM_DATA)
        self.node_data['sat_time'] += self.node_data['sat_period']
        logging.debug("构建卫星数据")
    
    def _build_payload_data(self):
        """构建载荷数据"""
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
        logging.debug("构建载荷数据")