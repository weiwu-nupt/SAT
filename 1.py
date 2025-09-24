#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import time
import threading
from typing import Dict, Optional
from enum import IntEnum

# 导入配置和数据结构
from config import sys_para, node_para, local_id
from data_struct import send_con, Lora_send_data, Lora_recv_data

logger = logging.getLogger(__name__)

class MessageType:
    """消息类型常量定义"""
    # LoRa消息类型
    LORA_BROADCAST = 0x01          # 系统广播消息
    LORA_REGISTER_REQ = 0x02       # 入网注册请求
    LORA_REGISTER_RSP = 0x03       # 入网注册应答
    LORA_NODE_CONTROL = 0x04       # 节点控制消息
    LORA_CLUSTER_OP = 0x05         # 簇操作消息
    LORA_RANGING_REQ = 0x11        # 测距调度消息
    LORA_RANGING_APPLY = 0x12      # 测距申请消息
    LORA_RANGING_RSP = 0x13        # 测距应答消息
    LORA_INQUIRY = 0x20            # 询问消息
    LORA_INQUIRY_RSP = 0x21        # 询问应答消息
    LORA_TRAFFIC_DATA = 0x22       # 业务数据消息
    LORA_NODE_STATUS = 0x23        # 节点状态消息
    LORA_CLUSTER_STATUS = 0x25     # 簇状态消息
    LORA_PLATFORM_DATA = 0x26      # 平台数据消息
    LORA_LINK_DATA = 0x27          # 链路数据消息
    LORA_MOTHER_SWITCH = 0x30      # 母星切换消息
    LORA_MOTHER_ELECTION = 0x31    # 母星选举消息
    
    # 控制消息类型
    CMD_SET_NODE_TYPE = 0x01       # 设置节点类型
    CMD_SET_NETWORK_CONFIG = 0x02  # 设置网络参数
    CMD_QUERY_STATUS = 0x03        # 查询节点状态
    CMD_START_NETWORK = 0x04       # 启动组网
    CMD_STOP_NETWORK = 0x05        # 停止组网
    
    # 网管消息类型
    NETMGR_NETWORK_MGMT = 0x10     # 网络管理消息
    NETMGR_NODE_CONFIG = 0x11      # 节点配置消息
    NETMGR_DATA_FORWARD = 0x12     # 数据转发消息

class LoRaProcessor:
    """LoRa处理器 - 保持原有处理逻辑"""

    def __init__(self):
        # 全局变量引用
        self.send_con = send_con
        self.lora_send_data = Lora_send_data
        self.lora_recv_data = Lora_recv_data
        self.local_id = local_id
        self.sys_para = sys_para
        self.node_para = node_para
        
        # 状态变量 - 保持原有命名
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
        """启动LoRa处理器"""
        if self.running:
            logger.warning("LoRa处理器已在运行")
            return
        
        self.running = True
        self.send_thread = threading.Thread(target=self._lora_send_proc, daemon=True)
        self.send_thread.start()
        
        logger.info("LoRa处理器启动成功")
    
    def stop(self):
        """停止LoRa处理器"""
        if not self.running:
            return
        
        self.running = False
        if self.send_thread and self.send_thread.is_alive():
            self.send_thread.join(timeout=2.0)
        
        logger.info("LoRa处理器已停止")
    
    def _lora_send_proc(self):
        """LoRa发送处理主循环 - 保持原有逻辑"""
        while self.running:
            try:     
                if self.send_con.recv_send_en:  # 接收数据需要应答
                    self._handle_received_message_response()
                elif send_con.unnormal_send_en:  # 应急数据应答，这里暂时定义为入网注册消息
                    self._handle_emergency_response()
                elif self.netman_new_dat:  # 网络数据发送，簇调整消息+业务数据+母星切换（网管发起）
                    self._handle_network_management_data()
                elif self.sys_para.net_mod == 6:  # 母星丢失模式,前若干个用户都不存在，定时监测发送
                    self._handle_mother_lost_mode()
                elif self.mother_poll_sta == 1:  # 母星轮训，发送系统广播消息，需要进行时间对齐检测
                    self._handle_mother_polling()
                elif self.mother_poll_sta == 2:  # 发送母星本地业务数据
                    self._handle_mother_business_data()
                elif self.mother_poll_sta == 3:  # 发起簇首轮询
                    self._handle_cluster_head_polling()
                elif self.mother_poll_sta == 4:  # 发起节点轮询
                    self._handle_node_polling()
                elif self.mother_poll_sta == 5:  # 发起距离测量
                    self._handle_ranging_operations()
                elif self.mother_poll_sta == 6:  # 发起状态参数设置
                    self._handle_status_parameter_setting()
                elif self.cluster_poll_sta == 1:  # 簇首的操作
                    self._handle_cluster_business_data()
                elif self.cluster_poll_sta == 2:  # 节点轮询
                    self._handle_cluster_node_polling()
                elif self.cluster_poll_sta == 3:  # 采用簇首节点状态上报汇聚消息发送应答
                    self._handle_cluster_status_aggregation()
                elif self.sys_para.net_mod in [0, 3]:  # 物联网模式
                    self._handle_iot_mode()
                
                # 用户退出检测
                self._user_exit_detection()
                
                # 防止CPU占用过高
                time.sleep(0.01)
                
            except Exception as e:
                logger.error(f"LoRa发送处理出错: {e}")
                time.sleep(0.1)

    def _handle_received_message_response(self):
        """处理接收数据应答 - 保持原有逻辑"""
        fram_type = self.send_con.fram_type
        
        if fram_type == 0x11:  # 接收到测距调度消息，发起测距申请
            self._build_ranging_request()
        elif fram_type == 0x12:  # 接收到测距申请，发送测距应答消息
            self._build_ranging_response()
        elif fram_type == 0x13:  # 接收到测距应答消息，进行测距消息上报
            self._build_ranging_report()
        elif fram_type == 0x02:  # 接收到注册消息
            self._build_register_response()
        elif fram_type == 0x03:  # 接收到注册应答消息,接收程序屏蔽
            self._lora_mac_ack(self.sys_para.mother_id)
        elif fram_type == 0x04:  # 节点模式控制消息，发送应答帧（确认或者状态数据），簇首的状态
            self._lora_mac_ack(self.sys_para.gateway_id)
        elif fram_type == 0x05:  # 簇操作操作，不需要应答，由接收进行屏蔽
            self._lora_mac_ack(self.sys_para.gateway_id)
        elif fram_type == 0x20:  # 询问消息,节点应答
            self._handle_inquiry_message()
        elif fram_type == 0x23:  # 接收到节点状态数据
            self._handle_node_status_response()
        elif fram_type == 0x26:  # 物联网模式接收接收到平台数据上报,母星进行应答，非物联网模式由接收屏蔽，
            self._handle_platform_data_response()
        elif fram_type == 0x27:  # 物联网模式下发送链路状态消息，暂时保留
            self._handle_link_status_response()
        elif fram_type == 0x30:  # 接收到母星切换消息，有接收屏蔽
            pass  # 保留
        elif fram_type == 0x31:  # 母星丢失选举模式
            self._handle_mother_election_response()
        else:
            logger.warning(f"未处理的消息类型: 0x{fram_type:02X}")
        
        self.send_con.recv_send_en = False

    def _build_ranging_request(self):
        """构建测距申请消息 - 保持原有逻辑"""
        self.lora_send_data.pay_len = 16
        self.lora_send_data.send_dat[0] = 0x12
        self.lora_send_data.send_dat[1] = 16
        self.lora_send_data.send_dat[2] = self.local_id
        self.lora_send_data.send_dat[3] = self.lora_recv_data.recv_dat[4]
        
        for i in range(4, 15):
            self.lora_send_data.send_dat[i] = 0
        
        self.send_lora_message(MessageType.LORA_RANGING_APPLY)
        logger.debug("构建并发送测距申请消息")
    
    def _build_ranging_response(self):
        """构建测距应答消息 - 保持原有逻辑"""
        self.lora_send_data.pay_len = 16
        self.lora_send_data.send_dat[0] = 0x13
        self.lora_send_data.send_dat[1] = 16
        self.lora_send_data.send_dat[2] = self.local_id
        self.lora_send_data.send_dat[3] = self.lora_recv_data.recv_dat[4]
        self.lora_send_data.send_dat[4] = 0  
        self.lora_send_data.send_dat[5] = 0  
        self.lora_send_data.send_dat[6] = 0  
        
        # 设置接收时间戳
        recv_time = self.lora_recv_data.recv_time
        self.lora_send_data.send_dat[7] = (recv_time >> 24) & 0xff
        self.lora_send_data.send_dat[8] = (recv_time >> 16) & 0xff
        self.lora_send_data.send_dat[9] = (recv_time >> 8) & 0xff
        self.lora_send_data.send_dat[10] = recv_time & 0xff
        
        # 发送时间戳，由FPGA更新
        for i in range(11, 15):
            self.lora_send_data.send_dat[i] = 0
        
        self.send_lora_message(MessageType.LORA_RANGING_RSP)
        logger.debug("构建并发送测距应答消息")
    
    def _build_ranging_report(self):
        """构建测距报告消息 - 保持原有逻辑"""
        # 计算测距结果
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
        self.lora_send_data.send_dat[4] = 0  # 消息序号保留
        self.lora_send_data.send_dat[5] = 0  # 测距消息类型，保留
        self.lora_send_data.send_dat[6] = 0  # 预留
        
        self.lora_send_data.send_dat[7] = (temp >> 24) & 0xff
        self.lora_send_data.send_dat[8] = (temp >> 16) & 0xff
        self.lora_send_data.send_dat[9] = (temp >> 8) & 0xff
        self.lora_send_data.send_dat[10] = temp & 0xff
        
        for i in range(11, 15):
            self.lora_send_data.send_dat[i] = 0  # 发送时间戳，由FPGA更新
        
        self.send_lora_message(MessageType.LORA_RANGING_RSP)
        logger.debug("构建并发送测距报告消息")
    
    def _build_register_response(self):
        """构建入网注册应答消息 - 保持原有逻辑"""
        self.lora_send_data.pay_len = 30
        self.lora_send_data.send_dat[0] = 0x03  # 入网注册应答消息
        self.lora_send_data.send_dat[1] = 18
        self.lora_send_data.send_dat[2] = self.local_id
        self.lora_send_data.send_dat[3] = self.lora_recv_data.recv_dat[5]  # MAC地址
        self.lora_send_data.send_dat[4] = self.lora_recv_data.recv_dat[6]
        self.lora_send_data.send_dat[5] = self.lora_recv_data.recv_dat[7]
        self.lora_send_data.send_dat[6] = 2  # 普通节点
        self.lora_send_data.send_dat[7] = 0  # 簇ID无效
        self.lora_send_data.send_dat[8] = 0  # 簇首ID无效
        self.lora_send_data.send_dat[9] = 0  # 节点常态模式
        
        # 其他字段设为无效
        for i in range(10, 16):
            self.lora_send_data.send_dat[i] = 0xff
        
        self.send_lora_message(MessageType.LORA_REGISTER_RSP)
        logger.debug("构建并发送入网注册应答消息")

    def _lora_mac_ack(self, dest_id: int):
        """发送MAC层应答 - 保持原有逻辑"""
        self.lora_send_data.pay_len = 9
        self.lora_send_data.send_dat[0] = 0x01  # 帧类型
        self.lora_send_data.send_dat[1] = 0x09  # 数据长度
        self.lora_send_data.send_dat[2] = dest_id
        self.lora_send_data.send_dat[3] = self.local_id
        self.lora_send_data.send_dat[4] = self.send_con.fram_type  # 应答帧类型
        self.lora_send_data.send_dat[5] = 0x00
        self.lora_send_data.send_dat[6] = 0x01  # 肯定应答
        self.lora_send_data.send_dat[7] = 0x00  # CRC
        self.lora_send_data.send_dat[8] = 0x00
        
        self.send_lora_message(0x01)
        logger.debug(f"发送MAC应答到节点: {dest_id}")

    def _handle_inquiry_message(self):
        """处理询问消息 - 保持原有逻辑"""
        # 构建询问应答消息（这里需要根据你的具体实现补充）
        logger.debug("处理询问消息")
        # TODO: 添加你的原始处理逻辑

    def _handle_node_status_response(self):
        """处理节点状态响应 - 保持原有逻辑"""
        # 物联网模式，母星需要应答
        if (self.sys_para.net_mod < 6) and (self.sys_para.node_mod == 0):
            self._build_broadcast_message(getattr(self.send_con, 'currend_id', 0))
            if hasattr(self.send_con, 'netman_send_en'):
                self.send_con.netman_send_en = False
        logger.debug("处理节点状态响应")
    
    def _handle_platform_data_response(self):
        """处理平台数据响应 - 保持原有逻辑"""
        # 物联网模式，母星需要应答
        if (self.sys_para.net_mod < 6) and (self.sys_para.node_mod == 0):
            self._build_broadcast_message(getattr(self.send_con, 'currend_id', 0))
            if hasattr(self.send_con, 'netman_send_en'):
                self.send_con.netman_send_en = False
        logger.debug("处理平台数据响应")
    
    def _handle_link_status_response(self):
        """处理链路状态响应 - 保持原有逻辑"""
        # 物联网模式，母星需要应答
        if (self.sys_para.net_mod < 6) and (self.sys_para.node_mod == 0):
            self._build_broadcast_message(getattr(self.send_con, 'currend_id', 0))
            if hasattr(self.send_con, 'netman_send_en'):
                self.send_con.netman_send_en = False
        logger.debug("处理链路状态响应")

    def _handle_mother_election_response(self):
        """处理母星选举响应 - 保持原有逻辑"""
        if self.lora_recv_data.recv_dat[2] == self.local_id - 1:  # 上一个发送数据的前一个ID
            self.lora_send_data.pay_len = 14
            self.lora_send_data.send_dat[0] = 0x1A
            self.lora_send_data.send_dat[1] = 14
            self.lora_send_data.send_dat[2] = self.local_id
            self.lora_send_data.send_dat[3] = 0
            self.lora_send_data.send_dat[4] = 234  # 后期设计专门的意愿算法
            self.lora_send_data.send_dat[5] = self.node_para.node_ability
            
            # 填充固定值
            fixed_values = [0x12, 0x34, 0x56, 0x78, 0x90, 0xef]
            for i, val in enumerate(fixed_values):
                if i + 6 < 12:
                    self.lora_send_data.send_dat[i + 6] = val
            
            self.send_lora_message(MessageType.LORA_MOTHER_ELECTION)
        elif self.local_id > self.lora_recv_data.recv_dat[2]:
            self.time_out = (self.local_id - self.lora_recv_data.recv_dat[3]) * 100  # 超时检测
        
        logger.debug("处理母星选举响应")

    def _handle_emergency_response(self):
        """处理应急数据应答，这里暂时定义为入网注册消息"""
        if self.link_sta == 1:  # 用户已获得系统同步，申请入网
            self._build_network_registration_request()
            self.link_sta = 2
        elif self.node_data['paload_unnormal']:  # 载荷异常数据
            self._build_abnormal_payload_data()

    def _build_abnormal_payload_data(self):
        """构建异常载荷数据"""
        self.lora_send_data.pay_len = 18
        self.lora_send_data.send_dat[0] = 0x26  # 平台数据消息类型
        self.lora_send_data.send_dat[1] = 11    # 数据长度
        self.lora_send_data.send_dat[2] = self.lora_recv_data.recv_dat[3]  # 获取目的地址
        self.lora_send_data.send_dat[3] = self.local_id                   # 源地址
        self.lora_send_data.send_dat[4] = 2     # 异常标志
    
        # 填充载荷数据
        payload_data = self.node_data.get('payload_data', [])
        for i in range(5, 18):
            self.lora_send_data.send_dat[i] = (
                payload_data[i] if i < len(payload_data) else 0
            )
    
        self.send_lora_message(0x26)  # LORA_PLATFORM_DATA
        self.node_data['paload_unnormal'] = False
        logger.debug("构建异常载荷数据")

    def _handle_network_management_data(self):
        """处理网络管理数据"""
        data_length = self.netman_recv_dat[1]
        self.lora_send_data.pay_len = data_length
    
        # 复制网管数据到发送缓冲区
        for i in range(data_length):
            self.lora_send_data.send_dat[i] = self.netman_recv_dat[i]
    
        # 业务数据搬移完毕，通知网关发送新的业务
        self.netman_new_dat = False
        logger.debug("处理网络管理数据")

    def _handle_mother_lost_mode(self):
        """处理母星丢失模式"""
        timeout_threshold = self.lora_recv_data.recv_ok_time + self.time_out
    
        if self.second_count > timeout_threshold:
            # 构建母星选举消息
            self.lora_send_data.pay_len = 14
            self.lora_send_data.send_dat[0] = 0x31  # 母星选举消息
            self.lora_send_data.send_dat[1] = 14    # 消息长度
            self.lora_send_data.send_dat[2] = self.local_id  # 源ID
            self.lora_send_data.send_dat[3] = 0     # 目标ID
            self.lora_send_data.send_dat[4] = 234   # 后期设计专门的意愿算法
            self.lora_send_data.send_dat[5] = self.node_para.node_ability
        
            # 填充固定标识值
            fixed_values = [0x12, 0x34, 0x56, 0x78, 0x90, 0xef]
            for i, val in enumerate(fixed_values):
                if i + 6 < 12:
                    self.lora_send_data.send_dat[i + 6] = val
        
            self.send_lora_message(0x31)  # LORA_MOTHER_ELECTION
            logger.debug("处理母星丢失模式")

    def _handle_mother_polling(self):
        """处理母星轮询，发送系统广播消息"""
        self._build_broadcast_message(0x00)
        self.mother_poll_sta = 2  # 切换到状态2，发送本地业务

    def _build_broadcast_message(self, target_id: int):
        """构建广播消息"""
        # 物联网+低功耗模式，母星地址是0,0时隙发送广播消息，否则不存在0的ID用户
        if self.sys_para.net_mod < 6:
            if target_id == 0:
                # 时间对齐检测
                if ((self.next_base_time - self.second_count < 1) and 
                    self.mil_sec_count > 995):
                    self.sys_base_time = self.next_base_time
                    self.sys_time_offset = 0
                    self.next_base_time += self.sys_para.sys_fram_period  # 计算下一个时间基准
                    self.lora_send_data.send_time = 0
                else:
                    return
            else:  # 10ms对齐
                self.sys_time_offset = self.mil_sec_count // 10 + 1
                if self.sys_time_offset < 100:
                    temp = self.second_count
                else:
                    self.sys_time_offset -= 100
                    temp = self.second_count + 1
            
                self.lora_send_data.send_time = self.sys_time_offset * 400000
                self.sys_time_offset = (temp << 8) + (self.sys_time_offset & 0xff)
        else:  # 10ms对齐
            self.sys_time_offset = self.mil_sec_count // 10 + 1
            if self.sys_time_offset < 100:
                self.sys_base_time = self.second_count
            else:
                self.sys_time_offset -= 100
                self.sys_base_time = self.second_count + 1
        
            self.lora_send_data.send_time = self.sys_time_offset * 400000
    
        # 构建广播消息内容
        self.lora_send_data.pay_len = 29
        self.lora_send_data.send_dat[0] = 0x00  # 广播消息
        self.lora_send_data.send_dat[1] = 29    # 长度
    
        # 网络ID
        self.lora_send_data.send_dat[2] = (self.sys_para.net_id >> 8) & 0xff
        self.lora_send_data.send_dat[3] = self.sys_para.net_id & 0xff
        self.lora_send_data.send_dat[4] = 0     # 目前仅支持母星发送
    
        # 时间同步信息
        self.lora_send_data.send_dat[5] = (self.sys_base_time >> 8) & 0xff
        self.lora_send_data.send_dat[6] = self.sys_base_time & 0xff
        self.lora_send_data.send_dat[7] = (self.sys_time_offset >> 16) & 0xff
        self.lora_send_data.send_dat[8] = (self.sys_time_offset >> 8) & 0xff
        self.lora_send_data.send_dat[9] = self.sys_time_offset & 0xff
    
        # 网络参数配置
        self.lora_send_data.send_dat[10] = (self.sys_para.net_mod + 
                                           (self.sys_para.sig_det_time << 4))
    
        # 转换模式处理
        if self.sys_para.convert_mod & 0x60:
            self.sys_para.convert_mod -= 0x10
        else:
            self.sys_para.convert_mod = 0
    
        self.lora_send_data.send_dat[11] = (self.sys_para.convert_mod + 
                                           (self.sys_para.sys_sig_mod << 7))
    
        # 频率和编码参数
        self.lora_send_data.send_dat[12] = (self.sys_para.fre_backw >> 8) & 0xff
        self.lora_send_data.send_dat[13] = self.sys_para.fre_backw & 0xff
        self.lora_send_data.send_dat[14] = (self.sys_para.SF_base_backw + 
                                           (self.sys_para.bw_backw << 4) + 
                                           (self.sys_para.cr_backw << 6))
        self.lora_send_data.send_dat[15] = (self.sys_para.clust_bw_forw + 
                                           (self.sys_para.clust_bw_backw << 4))
        self.lora_send_data.send_dat[16] = ((self.sys_para.clust_bw_backw << 4) + 
                                           (self.sys_para.clust_cr_backw << 6))
    
        # 系统参数
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
    
        # 设置发送时间
        self.lora_send_data.send_time_en = True
        send_time = locals().get('temp', self.second_count)
        self.lora_send_data.send_time = send_time
    
        self.send_lora_message(0x00)  # LORA_BROADCAST
        logger.debug(f"构建并发送广播消息，目标ID: {target_id}")

    def _handle_mother_business_data(self):
        """处理母星本地业务数据"""
        if self.traffic_data['traffic_pack']:
            self.traffic_send_en = True
        
            if self.traffic_data['traffic_pack'] == self.traffic_data['data_num']:
                # 数据发送完成
                self.traffic_data['traffic_pack'] = 0
                self.poll_node_id = 0
                self.poll_cluster_id = 0
            
                if self.sys_para.net_mod == 7:  # 如果数据需要应答，则需要调整位置
                    self.mother_poll_sta = 3  # 簇首调度模式
                else:
                    self.mother_poll_sta = 4
                self.send_con['poll_ok'] = True
        
            # 复制业务数据
            data_length = self.lora_send_data.pay_len - 2
            for i in range(data_length):
                self.lora_send_data.send_dat[i] = self.traffic_data['traffic_dat'][i]
    
        logger.debug("处理母星本地业务数据")

    def _handle_cluster_head_polling(self):
        """处理簇首轮询"""
        if self.send_con['poll_ok']:  # 发送簇轮询消息
            if self.poll_node_id == 1:  # 间隔发送应急时隙
                self.poll_node_id = 0
                self._build_emergency_slot_message()
                self.send_con['poll_ok'] = False
            elif self.poll_cluster_id < self.sys_para.clust_numb:
                self._build_cluster_poll_message()
                self.send_con['poll_ok'] = False
                self.poll_cluster_id += 1
                self.poll_node_id += 1
            else:
                self.mother_poll_sta = 5  # 切换到测距操作单元

    def _handle_node_polling(self):
        """处理节点轮询"""
        if self.send_con['poll_ok']:
            while True:
                if self.neighbor_node_sta[self.poll_node_id].node_sta == 2:  # 节点正常在网
                    if self.poll_cluster_id == self.sys_para.perm_period:
                        self.poll_cluster_id = 0
                        self._build_emergency_slot_message()
                        break
                    else:
                        self._build_node_poll_message()
                        break
                else:
                    self.poll_node_id += 1
                    if self.poll_node_id >= 0x7e:  # 达到最大节点ID
                        self.mother_poll_sta = 5  # 切换到测距操作单元
                        break

    def _handle_ranging_operations(self):
        """处理测距操作"""
        if self.send_con['poll_ok']:
            while True:
                if self.distanc_sta[self.poll_node_id].node_dis_en:  # 判断节点是否需要测距
                    break
                self.poll_node_id += 1
                if self.poll_node_id > 0x7e:  # 达到最大节点ID
                    self.mother_poll_sta = 6  # 切换到状态设置操作单元
                    break
        
            if (self.poll_node_id <= 0x7e and 
                self.distanc_sta[self.poll_node_id].node_dis_en):
                self._build_ranging_command()

    def _handle_status_parameter_setting(self):
        """处理状态参数设置"""
        if self.send_con['poll_ok']:
            while True:
                if self.node_ope_sta[self.poll_node_id].node_ope_en:  # 判断节点是否需要操作
                    break
                self.poll_node_id += 1
                if self.poll_node_id > 0x7e:  # 达到最大节点ID
                    self.mother_poll_sta = 1  # 数据操作完成，开启新的周期
                    break
        
            if (self.poll_node_id <= 0x7e and 
                self.node_ope_sta[self.poll_node_id].node_ope_en):
                self._build_status_setting_command()

    def _handle_cluster_business_data(self):
        """处理簇首业务数据"""
        if self.traffic_data['traffic_pack']:
            self.traffic_send_en = True
        
            if self.traffic_data['traffic_pack'] == self.traffic_data['data_num']:
                self.traffic_data['traffic_pack'] = 0
                self.cluster_poll_sta = 2  # 业务数据发送完成，切换到轮询状态
            else:
                self.lora_send_data.pay_len = self.traffic_data['traffic_dat'][1]
            
                # 复制业务数据
                for i in range(self.lora_send_data.pay_len):
                    self.lora_send_data.send_dat[i] = self.traffic_data['traffic_dat'][i]
            
                self.send_con['poll_ok'] = False
                self.traffic_data['data_num'] += 1
    
        logger.debug("处理簇首业务数据")

    def _handle_cluster_node_polling(self):
        """处理簇首节点轮询"""
        if self.send_con['poll_ok']:
            while True:
                if self.poll_node_id < len(self.sys_para.clust_node_id):
                    cluster_node_id = self.sys_para.clust_node_id[self.poll_node_id]
                    if self.neighbor_node_sta[cluster_node_id].node_sta:  # 判断节点是否在网
                        break
                self.poll_node_id += 1
                if self.poll_node_id > 0x7e:  # 达到最大节点ID
                    self.cluster_poll_sta = 3  # 切换到状态汇聚操作
                    break
        
            if (self.poll_node_id <= 0x7e and 
                self.poll_node_id < len(self.sys_para.clust_node_id)):
                self._build_cluster_node_poll_message()

    def _handle_cluster_status_aggregation(self):
        """处理簇首状态汇聚"""
        self.lora_send_data.send_dat[0] = 0x25  # 簇状态消息
        self.lora_send_data.send_dat[2] = self.sys_para.mother_id  # 目标母星ID
        self.lora_send_data.send_dat[3] = self.local_id            # 源ID
        self.lora_send_data.send_dat[4] = self.sys_para.clust_numb # 簇节点数
        self.lora_send_data.send_dat[5] = self.local_id            # 节点ID
        self.lora_send_data.send_dat[6] = 0xf                      # 本节点状态
    
        # 填充簇内节点状态
        data_index = 8
        for i in range(1, self.sys_para.clust_numb):
            if i < len(self.sys_para.clust_node_id):
                cluster_node_id = self.sys_para.clust_node_id[i]
                self.lora_send_data.send_dat[data_index] = cluster_node_id  # 节点ID
                node_health_status = self.neighbor_node_sta[cluster_node_id].node_healty_sta
                self.lora_send_data.send_dat[data_index + 1] = node_health_status  # 节点状态
                data_index += 2
    
        # 处理节点询问状态
        self.node_ask_sta[0].node_opedata = self.node_ask_sta[0].node_opedata >> 1
        data_index += 2
    
        # 设置帧数据长度
        self.lora_send_data.pay_len = data_index
        self.lora_send_data.send_dat[1] = self.lora_send_data.pay_len
    
        self.send_lora_message(0x25)  # LORA_CLUSTER_STATUS
        self.cluster_poll_sta = 0  # 簇首发送应答，结束当前轮询
        logger.debug("构建簇首状态汇聚消息")

    def _handle_iot_mode(self):
        """处理物联网模式"""
        if self.sys_para.node_mod == 0:  # 母星
            self._build_broadcast_message(0x00)  # 母星发送广播消息，系统静默和潜伏
        elif self.link_sta == 4:  # 其他节点
            self._handle_node_periodic_transmission()
        elif self.link_sta == 2:  # 已经获得同步，发送入网注册消息
            self._build_network_registration_request()

    def _handle_node_periodic_transmission(self):
        """处理节点周期性传输"""
        transmission_time = self.sys_base_time + self.local_id * 5
    
        if self.second_count > transmission_time:
            if self.node_data['node_period']:  # 发送节点状态
                if transmission_time < self.second_count:
                    transmission_time += self.node_data['node_period']
                
                    # 构建节点状态消息
                    self.lora_send_data.pay_len = 27  # 数据长度
                    self.lora_send_data.send_dat[0] = 0x23  # 帧类型：节点状态
                
                    # 填充节点数据
                    node_data = self.node_data.get('node_data', [])
                    for i in range(4, 25):
                        self.lora_send_data.send_dat[i] = (
                            node_data[i] if i < len(node_data) else 0
                        )
                
                    self.send_lora_message(0x23)  # LORA_NODE_STATUS
            
                # 检查是否需要发送卫星数据
                if (self.lora_send_data.pay_len and 
                    self.node_data['sat_period'] and 
                    self.node_data['sat_time'] < self.second_count):
                    self._build_satellite_data()
            
                # 检查是否需要发送载荷数据
                if (self.lora_send_data.pay_len == 0 and 
                    self.node_data['paload_period'] and 
                    self.node_data['paload_time'] < self.second_count):
                    self._build_payload_data()

    def _build_network_registration_request(self):
        """构建入网注册请求消息"""
        self.lora_send_data.pay_len = 30
        self.lora_send_data.send_dat[0] = 0x02  # 入网注册消息
        self.lora_send_data.send_dat[1] = 30    # 消息长度
    
        # 网络ID
        self.lora_send_data.send_dat[2] = (self.sys_para.net_id >> 8) & 0xff
        self.lora_send_data.send_dat[3] = self.sys_para.net_id & 0xff
    
        # 节点信息
        self.lora_send_data.send_dat[4] = self.local_id                    # 本地ID
        self.lora_send_data.send_dat[5] = self.node_para.node_ability      # 节点能力
        self.lora_send_data.send_dat[6] = self.node_para.Freq_range        # 频率范围
        self.lora_send_data.send_dat[7] = self.node_para.max_Pow           # 最大功率
        self.lora_send_data.send_dat[8] = self.node_para.Pow_att           # 功率衰减
    
        # 空间坐标 (每个坐标3字节)
        coordinates = [
            ('locat_x', 9),   # X坐标，索引9-11
            ('locat_y', 12),  # Y坐标，索引12-14  
            ('locat_z', 15)   # Z坐标，索引15-17
        ]
    
        for coord_name, base_index in coordinates:
            coord_value = getattr(self.node_para, coord_name)
            self.lora_send_data.send_dat[base_index] = (coord_value >> 16) & 0xff
            self.lora_send_data.send_dat[base_index + 1] = (coord_value >> 8) & 0xff
            self.lora_send_data.send_dat[base_index + 2] = coord_value & 0xff
    
        # 安全数据 (6字节)
        security_data = [0x12, 0x34, 0x56, 0x78, 0x34, 0x56]
        for i, value in enumerate(security_data):
            self.lora_send_data.send_dat[18 + i] = value
    
        self.send_lora_message(0x02)  # LORA_REGISTER_REQ
        self.link_sta = 2
        logger.debug("构建入网注册请求消息")

    def _user_exit_detection(self):
        """用户退出检测"""
        # 低功耗+物联网模式
        if self.sys_para.net_mod in [0, 3]:
            if self.second_count > self.next_base_time:
                self.next_base_time = self.sys_base_time + self.sys_para.sys_fram_period
            
                if self.local_id == self.sys_para.mother_id:
                    self._user_exit_detection_main()  # 母星检测
                else:
                    self._user_exit_detection_user()  # 用户节点检测
    
        # 母星丢失模式或簇首调度模式
        elif self.sys_para.net_mod in [6, 7]:
            if self.local_id == self.sys_para.mother_id:
                if self.mother_poll_sta == 1:
                    self._user_exit_detection_main()  # 母星轮询状态时检测
            else:
                if self.second_count > self.next_base_time:
                    self.next_base_time = self.sys_base_time + self.sys_para.sys_fram_period
                    self._user_exit_detection_user()  # 用户节点定期检测

    def get_node_status(self) -> Dict:
        """获取节点状态信息（与main.py中的接口对应）"""
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

# 使用示例
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建LoRa处理器
    lora_processor = LoRaProcessor()
    
    try:
        # 启动处理器
        lora_processor.start()
        
        logger.info("LoRa处理器运行中，按Ctrl+C退出...")
        while True:
            time.sleep(1)
            # 显示当前状态
            status = lora_processor.get_node_status()
            if status['second_count'] % 10 == 0 and status['second_count'] > 0:
                logger.info(f"运行状态: 接收帧={status['recv_fram_num']}, "
                           f"错误帧={status['recv_fram_err']}, "
                           f"运行时间={status['second_count']}s")
    
    except KeyboardInterrupt:
        logger.info("收到退出信号")
    finally:
        lora_processor.stop()
        logger.info("LoRa处理器已停止")