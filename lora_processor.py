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
    """邻居节点状态管理"""
    node_sta: int = 0  # 节点状态：0-不在线，1-发送入网应答注册，2-在网正常，3-潜伏，4-静默
    node_position: int = 2  # 节点属性：0母星，1簇首，2-常规
    mac_addr: List[int] = field(default_factory=lambda: [0, 0, 0])  # 节点MAC地址
    node_ability: int = 0  # 节点能力
    freq_rang: int = 0  # 节点信号频率范围
    node_pow: int = 0  # 节点信号功率，支撑自适应链路
    VGA: int = 0  # 节点信号功率范围
    pos_x: int = 0  # 空间坐标x (10米基本单位)
    pos_y: int = 0  # 空间坐标y
    pos_z: int = 0  # 空间坐标z
    cluster_id: int = 0  # 节点所在簇ID
    node_det_num: int = 3  # 节点在网连续检测次数，初始值3
    node_det_tim: int = 0  # 节点检测时间
    node_SF: int = 7  # 节点扩频因子
    node_healty_sta: int = 0  # 节点健康状态


@dataclass
class NodeOperationStatus:
    """节点操作状态"""
    node_ope_en: bool = False
    node_opedata: List[int] = field(default_factory=lambda: [0] * 6)


@dataclass
class DistanceStatus:
    """测距状态"""
    node_dis_en: bool = False
    des_nod_id: int = 0


@dataclass
class NodeAskStatus:
    """节点询问状态"""
    node_ask_en: bool = False
    node_opedata: int = 0x08


@dataclass
class NodeMotherStatus:
    """节点母星状态"""
    netman_link: List[int] = field(default_factory=lambda: [0] * 128)
    mother_score: List[int] = field(default_factory=lambda: [0] * 128)


class LoRaProcessor:
    """LoRa消息处理器 - 基于组网模式的处理逻辑
    
    与项目架构集成：
    - 通过message_processor接收UDP消息
    - 通过udp_servers发送响应消息
    - 支持配置文件驱动的参数设置
    """
    
    def __init__(self, message_sender: Optional[Callable] = None):
        self.running = False
        self.thread = None
        self.message_sender = message_sender  # 消息发送接口，连接到UDP服务器
        
        # SF表，基于信噪比映射到扩频因子
        self.SF_table = [12, 11, 10, 9, 8, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7]
        
        # 初始化系统参数（与config.ini配置对应）
        self.sys_para = {
            'net_id': 0x0001,  # 网络ID
            'net_mod': 0,  # 网络模式: 0-物联网方式，3-低功耗模式，6-母星丢失模式，7-簇首调度模式，8-母星丢失状态
            'node_mod': 2,  # 节点模式: 0-母星，1-簇首，2-普通节点
            'mother_id': 0,  # 母星ID固定为0
            'gateway_id': 0xFE,  # 网管ID
            'clust_id': 0x80,  # 簇首ID
            'clust_numb': 0,  # 簇内节点数
            'clust_node_id': [0] * 32,  # 簇内节点ID列表
            'work_mod': 0,  # 工作模式
            'convert_mod': 0,  # 系统工作在切换模式
            'sig_det_time': 0,  # 信号检测时间
            'sys_sig_mod': 0,  # 上报信号方式，常规还是自适应
            'wake_mod': 1,  # 空口唤醒模式，0常规空口唤醒模式，1短周期空口唤醒模式
            'un_permit': 1,  # 异常上报允许
            'perm_period': 10,  # 异常上报许周期（计数到0，发送异常询问）
            'node_sta_det': 0,  # 节点状态检测
            'node_num': 0,  # 系统节点数目
            'max_id': 0x7E,  # 系统最大节点ID
            'SF_base_forw': 7,  # 组网基本SF
            'SF_high_forw': 12,  # 最高允许SF
            'SF_base_backw': 7,  # 基础SF，反向
            'clust_SF_base_forw': 7,  # 簇基本SF，前向
            'clust_SF_base_backw': 7,  # 簇基本SF，反向
            'sys_fram_period': 3600,  # 系统帧周期长度
            'burst_time_base': 10,  # 物联网突发对对齐时间
            'fre_backw': 470000000,  # 反向频率
            'bw_backw': 0,  # 反向带宽
            'cr_backw': 1,  # 反向编码率
            'clust_bw_forw': 0,  # 簇前向带宽
            'clust_bw_backw': 0,  # 簇反向带宽
            'clust_cr_backw': 1,  # 簇反向编码率
        }
        
        # 节点参数（对应config.ini的NODE_CONFIG部分）
        self.local_id = 0x10  # 本机节点ID，从配置文件读取
        self.node_para = {
            'mac_addr': [0x12, 0x34, 0x56],  # MAC地址
            'node_ability': 0x01,  # 节点能力
            'Freq_range': 0x01,  # 频率范围
            'max_Pow': 20,  # 最大功率
            'Pow_att': 1,  # 功率变化
            'locat_x': 1000,  # 空间坐标x (10米单位)
            'locat_y': 2000,  # 空间坐标y
            'locat_z': 100,   # 空间坐标z
            'pow_set': 14,    # 节点功率等级
        }
        
        # 信号参数（对应config.ini的LORA_PARAMS部分）
        self.send_sig_para = {
            'sig_fre': 470000000,  # 发送频率
            'sig_SF': 7,           # 发送扩频因子
            'sig_CR': 1,           # 发送编码率
            'sig_bw': 0,           # 带宽
            'sig_pow': 14          # 发送功率
        }
        
        self.recv_sig_para = {
            'sig_fre': 470000000,  # 接收频率
            'sig_SF': 7,           # 接收扩频因子
            'sig_CR': 1,           # 接收编码率
            'sig_bw': 0            # 带宽
        }
        
        # 发送控制状态
        self.send_con = {
            'recv_send_en': False,  # 接收数据需要应答
            'fram_type': 0,         # 帧类型
            'unnormal_send_en': False,  # 异常数据应答
            'netman_send_en': False,    # 网管发送使能
            'poll_ok': True,            # 轮询OK标志
            'currend_id': 0,            # 当前节点ID
            'poll_new_send': False      # 新的轮询发送
        }
        
        # LoRa发送数据结构
        self.lora_send_data = {
            'pay_len': 0,
            'send_dat': [0] * 256,
            'send_time': 0,
            'send_time_en': False,
            'send_time_stamp': 0
        }
        
        # LoRa接收数据结构
        self.lora_recv_data = {
            'recv_dat': [0] * 256,
            'recv_time': 0,
            'recv_ok_time': 0,
            'recv_length': 0,
            'recv_SNR': 0  # 信噪比
        }
        
        # 节点状态
        self.link_sta = 0  # 0-空闲，1-信号搜索，2-获得同步，3-发送入网消息，4-完成入网，5-母星丢失
        self.mother_poll_sta = 1  # 母星轮询状态
        self.cluster_poll_sta = 0  # 簇首轮询状态
        self.traffic_send_en = False
        self.netman_link_sta = True  # 网管连接状态
        self.to_convert_mother_id = False  # 需要切换到母星状态
        
        # 时间相关
        self.second_count = 0
        self.mil_sec_count = 0
        self.sys_base_time = 0
        self.next_base_time = 3600  # 下一个时间基准
        self.sys_time_offset = 0
        self.time_out = 1000  # 超时检测
        self.re_enter_time = 0  # 重新入网时间
        
        # 轮询相关
        self.poll_node_id = 0
        self.poll_cluster_id = 0
        
        # 网络管理数据
        self.netman_new_dat = False
        self.netman_recv_dat = [0] * 1024
        self.netman_send_en = False
        self.receive_to_netman = False
        
        # 业务数据
        self.traffic_data = {
            'traffic_pack': 0,
            'data_num': 0,
            'traffic_dat': [0] * 1024,
            'dest_id': 0
        }
        
        # 节点数据（对应config.ini的TIMING_PARAMS部分）
        self.node_data = {
            'node_data': [0] * 32,
            'node_period': 60,  # 节点状态数据上报周期(秒)
            'node_time': 0,     # 节点时间
            'paload_unnormal': False,
            'sat_data': [0] * 32,
            'sat_period': 300,  # 卫星状态数据上报周期(秒)
            'sat_time': 0,
            'payload_data': [0] * 32,
            'paload_period': 120,  # 载荷数据上报周期(秒)
            'paload_time': 0
        }
        
        # 邻居节点状态管理 (最大支持128个节点)
        self.neighbor_node_sta = [NeighborNodeStatus() for _ in range(128)]
        
        # 节点操作状态管理
        self.node_ope_sta = [NodeOperationStatus() for _ in range(128)]
        
        # 测距状态管理
        self.distanc_sta = [DistanceStatus() for _ in range(128)]
        
        # 节点询问状态管理
        self.node_ask_sta = [NodeAskStatus() for _ in range(128)]
        
        # 母星状态管理
        self.node_mother_sta = NodeMotherStatus()
        
        # 统计信息
        self.recv_totle_num = 0      # 接收总帧数
        self.recv_fram_err = 0       # 错误帧计数
        self.recv_fram_num = 0       # 正确帧计数
        self.recv_fram_self = 0      # 本节点计数
        self.user_det_tim = 0        # 用户检测时间
        
        # 临时变量
        self.temp = 0
        self.temp1 = 0
        self.temp2 = 0
        self.temp3 = 0
        self.i = 0
        self.j = 0
        self.k = 0
    
    def set_message_sender(self, sender: Callable):
        """设置消息发送接口，与UDP服务器集成"""
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
        """设置节点类型（与main.py中的配置对应）"""
        if node_type == "mother":
            self.sys_para['node_mod'] = 0
            self.local_id = 0  # 母星ID固定为0
            self.sys_para['mother_id'] = 0
            logging.info("节点类型设置为：母星 (ID=0)")
        elif node_type == "cluster":
            self.sys_para['node_mod'] = 1  
            self.local_id = self.sys_para['clust_id']
            logging.info("节点类型设置为：簇首")
        else:
            self.sys_para['node_mod'] = 2
            logging.info("节点类型设置为：普通节点")
    
    def set_local_id(self, node_id: int):
        """设置本地节点ID"""
        if 0 <= node_id <= 0x7E:
            self.local_id = node_id
            logging.info(f"节点ID设置为：{node_id}")
        else:
            logging.warning(f"无效的节点ID：{node_id}，应在0-126之间")
    
    def process_received_message(self, raw_data: bytes, recv_time: int = None):
        """处理接收到的消息（从message_processor调用）"""
        # 直接处理已解包的消息数据
        if len(raw_data) < 2:
            logging.warning("接收到长度不足的消息")
            return
        
        # 更新接收数据结构
        self.lora_recv_data['recv_dat'] = list(raw_data) + [0] * (256 - len(raw_data))
        self.lora_recv_data['recv_length'] = len(raw_data)
        self.lora_recv_data['recv_time'] = recv_time or int(time.time() * 1000)
        
        # 更新统计信息
        self.recv_totle_num += 1
        self.recv_fram_num += 1
        self.user_det_tim = 1
        
        # 处理具体消息
        self.send_con['fram_type'] = raw_data[0]
        self._lora_fram_proc()
    
    def send_lora_message(self, msg_type: int, target_addr: tuple = None):
        """发送LoRa消息（通过UDP服务器）"""
        if not self.message_sender:
            logging.warning("消息发送接口未设置")
            return
        
        try:
            # 将发送数据转换为bytes格式
            content = bytes(self.lora_send_data['send_dat'][:self.lora_send_data['pay_len']])
            
            # 如果没有指定目标地址，使用广播地址
            if target_addr is None:
                target_addr = ('255.255.255.255', 8003)  # LoRa端口广播
            
            # 通过message_sender发送（这将调用UDP服务器的发送方法）
            self.message_sender(target_addr, msg_type, content)
            logging.debug(f"发送LoRa消息: 类型=0x{msg_type:02X}, 长度={len(content)}")
            
        except Exception as e:
            logging.error(f"发送LoRa消息失败: {e}")
    
    def _lora_send_proc(self):
        """LoRa发送处理主循环 - 基于原C代码的完整实现"""
        while self.running:
            try:
                # 模拟时间计数器
                self.second_count += 1
                self.mil_sec_count = (self.mil_sec_count + 100) % 1000
                if self.mil_sec_count == 0:
                    self.second_count += 1
                
                if self.send_con['recv_send_en']:  # 接收数据需要应答
                    self._handle_received_message_response()
                elif self.send_con['unnormal_send_en']:  # 应急数据应答，这里暂时定义为入网注册消息
                    self._handle_emergency_response()
                elif self.netman_new_dat:  # 网络数据发送，簇调整消息+业务数据+母星切换（网管发起）
                    self._handle_network_management_data()
                elif self.sys_para['net_mod'] == 6:  # 母星丢失模式,前若干个用户都不存在，定时监测发送
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
                elif self.sys_para['net_mod'] in [0, 3]:  # 物联网模式
                    self._handle_iot_mode()
                
                # 用户退出检测
                self._user_exit_detection()
                
                # 模拟处理间隔
                time.sleep(1)  # 1秒间隔
                
            except Exception as e:
                logging.error(f"LoRa发送处理出错: {e}")
                time.sleep(1)
    
    def _handle_received_message_response(self):
        """处理接收数据应答 - 对应原C代码的recv_send_en分支"""
        fram_type = self.send_con['fram_type']
        
        if fram_type == 0x11:  # 接收到测距调度消息，发起测距申请
            self._build_ranging_request()
        elif fram_type == 0x12:  # 接收到测距申请，发送测距应答消息
            self._build_ranging_response()
        elif fram_type == 0x13:  # 接收到测距应答消息，进行测距消息上报
            self._build_ranging_report()
        elif fram_type == 0x02:  # 接收到注册消息
            self._build_register_response()
        elif fram_type == 0x03:  # 接收到注册应答消息,接收程序屏蔽
            self._lora_mac_ack(self.sys_para['mother_id'])
        elif fram_type == 0x04:  # 节点模式控制消息，发送应答帧（确认或者状态数据），簇首的状态
            self._lora_mac_ack(self.sys_para['gateway_id'])
        elif fram_type == 0x05:  # 簇操作操作，不需要应答，由接收进行屏蔽
            self._lora_mac_ack(self.sys_para['gateway_id'])
        elif fram_type == 0x20:  # 询问消息,节点应答
            self._handle_inquiry_message()
        elif fram_type == 0x23:  # 接收到节点状态数据
            self._handle_node_status_response()
        elif fram_type == 0x26:  # 物联网模式接收接收到平台数据上报,母星进行应答，非物联网模式由接收屏蔽，
            self._handle_platform_data_response()
        elif fram_type == 0x27:  # 物联网模式下发送链路状态消息，暂时保留
            self._handle_link_status_response()
        elif fram_type == 0x30:  # 接收到母星切换消息，有接收屏蔽
            pass  # 由接收处理
        elif fram_type == 0x31:  # 母星丢失选举模式
            self._handle_mother_election_response()
        
        self.send_con['recv_send_en'] = False
    
    def _build_ranging_request(self):
        """构建测距申请消息"""
        self.lora_send_data['pay_len'] = 16
        self.lora_send_data['send_dat'][0] = 0x12
        self.lora_send_data['send_dat'][1] = self.lora_send_data['pay_len']
        self.lora_send_data['send_dat'][2] = self.local_id
        self.lora_send_data['send_dat'][3] = self.lora_recv_data['recv_dat'][4]
        self.lora_send_data['send_dat'][4] = 0  # 消息序号保留
        self.lora_send_data['send_dat'][5] = 0  # 测距消息类型，保留
        
        for i in range(7, 15):
            self.lora_send_data['send_dat'][i] = 0
        
        self.send_lora_message(MessageType.LORA_RANGING_APPLY)
        logging.debug("构建并发送测距申请消息")
    
    def _build_ranging_response(self):
        """构建测距应答消息"""
        self.lora_send_data['pay_len'] = 16
        self.lora_send_data['send_dat'][0] = 0x13
        self.lora_send_data['send_dat'][1] = self.lora_send_data['pay_len']
        self.lora_send_data['send_dat'][2] = self.local_id
        self.lora_send_data['send_dat'][3] = self.lora_recv_data['recv_dat'][4]
        self.lora_send_data['send_dat'][4] = 0  # 消息序号保留
        self.lora_send_data['send_dat'][5] = 0  # 测距消息类型，保留
        
        # 设置接收时间戳
        recv_time = self.lora_recv_data['recv_time']
        self.lora_send_data['send_dat'][7] = (recv_time >> 24) & 0xff
        self.lora_send_data['send_dat'][8] = (recv_time >> 16) & 0xff
        self.lora_send_data['send_dat'][9] = (recv_time >> 8) & 0xff
        self.lora_send_data['send_dat'][10] = recv_time & 0xff
        
        # 发送时间戳，由FPGA更新
        for i in range(11, 15):
            self.lora_send_data['send_dat'][i] = 0
        
        self.send_lora_message(MessageType.LORA_RANGING_RSP)
        logging.debug("构建并发送测距应答消息")
    
    def _build_ranging_report(self):
        """构建测距报告消息"""
        # 计算测距结果
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
        self.lora_send_data['send_dat'][4] = 0  # 消息序号保留
        self.lora_send_data['send_dat'][5] = 0  # 测距消息类型，保留
        
        self.lora_send_data['send_dat'][7] = (temp >> 24) & 0xff
        self.lora_send_data['send_dat'][8] = (temp >> 16) & 0xff
        self.lora_send_data['send_dat'][9] = (temp >> 8) & 0xff
        self.lora_send_data['send_dat'][10] = temp & 0xff
        
        for i in range(11, 15):
            self.lora_send_data['send_dat'][i] = 0  # 发送时间戳，由FPGA更新
        
        self.send_lora_message(MessageType.LORA_RANGING_RSP)
        logging.debug("构建并发送测距报告消息")
    
    # 继续实现其他核心方法...
    def get_node_status(self) -> Dict:
        """获取节点状态信息（与main.py中的接口对应）"""
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
        """发送MAC层应答"""
        self.lora_send_data['pay_len'] = 9
        self.lora_send_data['send_dat'][0] = 0x01  # 帧类型
        self.lora_send_data['send_dat'][1] = 0x09  # 数据长度
        self.lora_send_data['send_dat'][2] = dest_id
        self.lora_send_data['send_dat'][3] = self.local_id
        self.lora_send_data['send_dat'][4] = self.send_con['fram_type']  # 应答帧类型
        self.lora_send_data['send_dat'][5] = 0x00
        self.lora_send_data['send_dat'][6] = 0x01  # 肯定应答
        self.lora_send_data['send_dat'][7] = 0x00  # CRC
        self.lora_send_data['send_dat'][8] = 0x00
        
        self.send_lora_message(0x01)
        logging.debug(f"发送MAC应答到节点: {dest_id}")
    
    def _build_register_response(self):
        """构建入网注册应答消息"""
        self.lora_send_data['pay_len'] = 30
        self.lora_send_data['send_dat'][0] = 0x03  # 入网注册应答消息
        self.lora_send_data['send_dat'][1] = 18
        self.lora_send_data['send_dat'][2] = self.local_id
        self.lora_send_data['send_dat'][3] = self.lora_recv_data['recv_dat'][5]  # MAC地址
        self.lora_send_data['send_dat'][4] = self.lora_recv_data['recv_dat'][6]
        self.lora_send_data['send_dat'][5] = self.lora_recv_data['recv_dat'][7]
        self.lora_send_data['send_dat'][6] = 2  # 普通节点
        self.lora_send_data['send_dat'][7] = 0  # 簇ID无效
        self.lora_send_data['send_dat'][8] = 0  # 簇首ID无效
        self.lora_send_data['send_dat'][9] = 0  # 节点常态模式
        
        # 其他字段设为无效
        for i in range(10, 16):
            self.lora_send_data['send_dat'][i] = 0xff
        
        self.send_lora_message(MessageType.LORA_REGISTER_RSP)
        logging.debug("构建并发送入网注册应答消息")
    
    def _handle_inquiry_message(self):
        """处理询问消息,节点应答"""
        temp = self.lora_recv_data['recv_dat'][4]  # 读取接收消息的轮询方式，判断如何应答
        
        if temp & 0x40:  # 判断是否有簇首数据
            if self.sys_para['clust_id'] == self.local_id:  # 只有簇首节点可以应答
                self.cluster_poll_sta = 1  # 标识簇轮询开启
                self._build_cluster_inquiry_response()
        elif (temp & 0x1) and self.traffic_data['traffic_pack']:  # 询问业务数据,且有业务数据
            self.traffic_send_en = True
            self._build_business_inquiry_response()
        elif temp & 0x4:  # 判断是否有平台数据发送
            self._build_platform_inquiry_response()
        elif temp & 0x8:  # 判断是否有载荷数据发送
            self._build_payload_inquiry_response()
        elif temp & 0x10:  # 判断是否有链路数据发送
            self._build_link_inquiry_response()
        else:  # 节点状态数据
            self._build_node_status_inquiry_response()
        
        self.send_con['netman_send_en'] = False
    
    def _build_cluster_inquiry_response(self):
        """构建簇首询问应答"""
        self.lora_send_data['pay_len'] = 11
        self.lora_send_data['send_dat'][0] = 0x21
        self.lora_send_data['send_dat'][1] = 11
        self.lora_send_data['send_dat'][2] = self.lora_recv_data['recv_dat'][3]  # 获取目的地址
        self.lora_send_data['send_dat'][3] = self.local_id
        self.lora_send_data['send_dat'][4] = self.sys_para['clust_numb']
        temp = self.sys_para['clust_numb'] * 1000  # 按照每个节点需要发送10秒估计
        self.lora_send_data['send_dat'][5] = (temp >> 8) & 0xff
        self.lora_send_data['send_dat'][6] = temp & 0xff
        self.lora_send_data['send_dat'][7] = 0
        self.lora_send_data['send_dat'][8] = 0
        
        self.send_lora_message(MessageType.LORA_INQUIRY_RSP)
    
    def _build_business_inquiry_response(self):
        """构建业务数据询问应答"""
        self.traffic_send_en = True
        self.lora_send_data['pay_len'] = 11
        self.lora_send_data['send_dat'][0] = 0x21
        self.lora_send_data['send_dat'][1] = 12
        self.lora_send_data['send_dat'][2] = self.lora_recv_data['recv_dat'][3]  # 获取目的地址
        self.lora_send_data['send_dat'][3] = self.local_id
        self.lora_send_data['send_dat'][4] = (self.traffic_data['traffic_pack'] >> 8) & 0xff
        self.lora_send_data['send_dat'][5] = self.traffic_data['traffic_pack'] & 0xff
        temp = self.traffic_data['traffic_pack'] * 100  # 按照每帧1s时间上报的
        self.lora_send_data['send_dat'][6] = (temp >> 8) & 0xff
        self.lora_send_data['send_dat'][7] = temp & 0xff
        self.lora_send_data['send_dat'][8] = 0
        self.lora_send_data['send_dat'][9] = 0
        
        self.send_lora_message(MessageType.LORA_INQUIRY_RSP)
    
    def _build_node_status_inquiry_response(self):
        """构建节点状态询问应答"""
        self.lora_send_data['pay_len'] = 27
        self.lora_send_data['send_dat'][0] = 0x23  # 帧类型
        self.lora_send_data['send_dat'][1] = 27   # 数据长度
        self.lora_send_data['send_dat'][2] = 0xfe
        self.lora_send_data['send_dat'][3] = self.local_id
        
        for i in range(4, 25):  # 需要核实
            self.lora_send_data['send_dat'][i] = (
                self.node_data['node_data'][i] if i < len(self.node_data['node_data']) else 0
            )
        
        self.send_lora_message(MessageType.LORA_NODE_STATUS)
    
    def _handle_emergency_response(self):
        """处理应急数据应答，这里暂时定义为入网注册消息"""
        if self.link_sta == 1:  # 用户已获得系统同步，申请入网
            self._build_network_registration_request()
            self.link_sta = 2
        elif self.node_data['paload_unnormal']:  # 载荷异常数据
            self._build_abnormal_payload_data()
    
    def _build_network_registration_request(self):
        """构建入网注册请求消息"""
        self.lora_send_data['pay_len'] = 30
        self.lora_send_data['send_dat'][0] = 0x02  # 入网注册消息
        self.lora_send_data['send_dat'][1] = 30
        self.lora_send_data['send_dat'][2] = (self.sys_para['net_id'] >> 8) & 0xff
        self.lora_send_data['send_dat'][3] = self.sys_para['net_id'] & 0xff
        self.lora_send_data['send_dat'][4] = self.local_id
        self.lora_send_data['send_dat'][5] = self.node_para['node_ability']  # 节点能力
        self.lora_send_data['send_dat'][6] = self.node_para['Freq_range']    # 频率
        self.lora_send_data['send_dat'][7] = self.node_para['max_Pow']       # 最大功率
        self.lora_send_data['send_dat'][8] = self.node_para['Pow_att']       # 功率变化
        
        # 空间坐标
        coords = ['locat_x', 'locat_y', 'locat_z']
        for i, coord in enumerate(coords):
            base_idx = 9 + i * 3
            coord_val = self.node_para[coord]
            self.lora_send_data['send_dat'][base_idx] = (coord_val >> 16) & 0xff
            self.lora_send_data['send_dat'][base_idx + 1] = (coord_val >> 8) & 0xff
            self.lora_send_data['send_dat'][base_idx + 2] = coord_val & 0xff
        
        # 安全数据
        security_data = [0x12, 0x34, 0x56, 0x78, 0x34, 0x56]
        for i, val in enumerate(security_data):
            self.lora_send_data['send_dat'][18 + i] = val
        
        self.send_lora_message(MessageType.LORA_REGISTER_REQ)
        self.link_sta = 2
    
    def _handle_mother_polling(self):
        """处理母星轮询，发送系统广播消息"""
        self._build_broadcast_message(0x00)
        self.mother_poll_sta = 2  # 切换到状态2，发送本地业务
    
    def _build_broadcast_message(self, target_id: int):
        """构建广播消息"""
        if self.sys_para['net_mod'] < 6:  # 物联网+低功耗模式，母星地址是0,0时隙发送广播消息，否则不存在0的ID用户
            if target_id == 0:
                if ((self.next_base_time - self.second_count < 1) and 
                    self.mil_sec_count > 995):
                    self.sys_base_time = self.next_base_time
                    self.sys_time_offset = 0
                    self.next_base_time += self.sys_para['sys_fram_period']  # 计算下一个时间基准
                    self.lora_send_data['send_time'] = 0
                else:
                    return
            else:  # 10ms对齐
                self.sys_time_offset = self.mil_sec_count // 10 + 1
                if self.sys_time_offset < 100:
                    temp = self.second_count
                else:
                    self.sys_time_offset -= 100
                    temp = self.second_count + 1
                
                self.lora_send_data['send_time'] = self.sys_time_offset * 400000
                self.sys_time_offset = (temp << 8) + (self.sys_time_offset & 0xff)
        else:  # 10ms对齐
            self.sys_time_offset = self.mil_sec_count // 10 + 1
            if self.sys_time_offset < 100:
                self.sys_base_time = self.second_count
            else:
                self.sys_time_offset -= 100
                self.sys_base_time = self.second_count + 1
            
            self.lora_send_data['send_time'] = self.sys_time_offset * 400000
        
        # 构建广播消息内容
        self.lora_send_data['pay_len'] = 29
        self.lora_send_data['send_dat'][0] = 0x00  # 广播消息
        self.lora_send_data['send_dat'][1] = 29    # 长度
        self.lora_send_data['send_dat'][2] = (self.sys_para['net_id'] >> 8) & 0xff
        self.lora_send_data['send_dat'][3] = self.sys_para['net_id'] & 0xff
        self.lora_send_data['send_dat'][4] = 0     # 目前仅支持母星发送
        
        # 时间同步信息
        self.lora_send_data['send_dat'][5] = (self.sys_base_time >> 8) & 0xff
        self.lora_send_data['send_dat'][6] = self.sys_base_time & 0xff
        self.lora_send_data['send_dat'][7] = (self.sys_time_offset >> 16) & 0xff
        self.lora_send_data['send_dat'][8] = (self.sys_time_offset >> 8) & 0xff
        self.lora_send_data['send_dat'][9] = self.sys_time_offset & 0xff
        
        # 网络参数配置
        self.lora_send_data['send_dat'][10] = (self.sys_para['net_mod'] + 
                                               (self.sys_para['sig_det_time'] << 4))
        
        if self.sys_para['convert_mod'] & 0x60:
            self.sys_para['convert_mod'] -= 0x10
        else:
            self.sys_para['convert_mod'] = 0
        
        self.lora_send_data['send_dat'][11] = (self.sys_para['convert_mod'] + 
                                               (self.sys_para['sys_sig_mod'] << 7))
        
        # 频率和编码参数
        self.lora_send_data['send_dat'][12] = (self.sys_para['fre_backw'] >> 8) & 0xff
        self.lora_send_data['send_dat'][13] = self.sys_para['fre_backw'] & 0xff
        self.lora_send_data['send_dat'][14] = (self.sys_para['SF_base_backw'] + 
                                               (self.sys_para['bw_backw'] << 4) + 
                                               (self.sys_para['cr_backw'] << 6))
        self.lora_send_data['send_dat'][15] = (self.sys_para['clust_bw_forw'] + 
                                               (self.sys_para['clust_bw_backw'] << 4))
        self.lora_send_data['send_dat'][16] = ((self.sys_para['clust_bw_backw'] << 4) + 
                                               (self.sys_para['clust_cr_backw'] << 6))
        
        # 系统参数
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
        logging.debug(f"构建并发送广播消息，目标ID: {target_id}")
    
    def _lora_fram_proc(self):
        """LoRa帧处理 - 对应原C代码的lora_fram_proc函数"""
        # 更新统计信息
        self.recv_totle_num += 1
        
        # 帧类型处理
        fram_type = self.send_con['fram_type']
        
        if fram_type == 0x00 and self.local_id != self.sys_para['mother_id']:
            self._process_broadcast_message()
        elif fram_type == 0x01:  # 接收通用应答消息
            self._process_general_ack()
        elif fram_type == 0x02:  # 接收到注册消息
            self._process_registration_request()
        elif fram_type == 0x03:  # 接收到注册应答消息
            self._process_registration_response()
        elif fram_type == 0x04:  # 接收节点模式控制消息
            self._process_node_control()
        elif fram_type == 0x05:  # 接收簇控制消息，广播消息，不需要应答
            self._process_cluster_control()
        # ... 继续添加其他消息类型处理
    
    def _process_broadcast_message(self):
        """处理系统广播消息"""
        self.recv_fram_self += 1  # 本节点计数
        
        if self.link_sta == 0:  # 未入网，获得系统同步，更改端机状态
            self._sync_with_network()
        elif self.link_sta == 2:  # 已经进行过申请，但未能接收到应答，判定申请失败
            self.link_sta = 1
        elif self.link_sta == 3:  # 收到应答，但未接收到轮询，等待一个轮巡周期
            self.link_sta = 4
        elif self.link_sta == 4:  # 收到应答，但未接收到轮询，恢复到同步态
            self.link_sta = 1
        
        # 进行时间调整
        self._update_local_time()
        
        # 标记母星已检测、簇首已检测
        self.neighbor_node_sta[self.sys_para['mother_id']].node_det_tim = 1
    
    def _sync_with_network(self):
        """与网络同步"""
        self.link_sta = 1  # 接收系统广播消息，获得时间同步
        
        # 更改本地参数
        recv_data = self.lora_recv_data['recv_dat']
        self.sys_para['net_id'] = (recv_data[2] << 8) + recv_data[3]
        
        if recv_data[5] == 0:  # 母星ID
            self.sys_para['mother_id'] = recv_data[4]
        
        self.sys_para['node_mod'] = 2  # 普通节点
        self.sys_para['net_mod'] = recv_data[13] & 0x1F  # 网络工作模式
        self.sys_para['gateway_id'] = 0xfe  # 网管ID，固定
        self.sys_para['convert_mod'] = recv_data[14]  # 系统工作在切换模式
        
        # 更新更多网络参数...
        self._update_network_parameters()
    
    def _user_exit_detection(self):
        """用户退出检测"""
        if self.sys_para['net_mod'] in [0, 3]:  # 低功耗+物联网模式
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
    
    # 辅助方法
    def set_traffic_data(self, data: bytes):
        """设置业务数据"""
        if len(data) <= 1024:
            self.traffic_data['traffic_dat'][:len(data)] = list(data)
            self.traffic_data['traffic_pack'] = len(data)
            self.traffic_data['data_num'] = 0
            logging.debug(f"设置业务数据，长度: {len(data)}")
        else:
            logging.warning(f"业务数据长度超限: {len(data)}")
    
    def set_node_abnormal_payload(self, abnormal: bool = True):
        """设置节点载荷异常状态"""
        self.node_data['paload_unnormal'] = abnormal
        if abnormal:
            self.send_con['unnormal_send_en'] = True
        logging.debug(f"设置载荷异常状态: {abnormal}")
    
    def trigger_emergency_send(self):
        """触发应急发送"""
        self.send_con['unnormal_send_en'] = True
        logging.debug("触发应急发送")

    def _handle_mother_business_data(self):
        """处理母星本地业务数据"""
        if self.traffic_data['traffic_pack']:
            self.traffic_send_en = True
            if self.traffic_data['traffic_pack'] == self.traffic_data['data_num']:
                self.traffic_data['traffic_pack'] = 0
                self.poll_node_id = 0
                self.poll_cluster_id = 0
                
                if self.sys_para['net_mod'] == 7:  # 如果数据需要应答，则需要调整位置
                    self.mother_poll_sta = 3  # 簇首调度模式
                else:
                    self.mother_poll_sta = 4
                self.send_con['poll_ok'] = True
            
            # 复制业务数据
            for i in range(self.lora_send_data['pay_len'] - 2):
                self.lora_send_data['send_dat'][i] = self.traffic_data['traffic_dat'][i]
        
        logging.debug("处理母星本地业务数据")
    
    def _handle_cluster_head_polling(self):
        """处理簇首轮询"""
        if self.send_con['poll_ok']:  # 发送簇轮询消息
            if self.poll_node_id == 1:  # 间隔发送应急时隙
                self.poll_node_id = 0
                self._build_emergency_slot_message()
                self.send_con['poll_ok'] = False
            elif self.poll_cluster_id < self.sys_para['clust_numb']:
                self._build_cluster_poll_message()
                self.send_con['poll_ok'] = False
                self.poll_cluster_id += 1
                self.poll_node_id += 1
            else:
                self.mother_poll_sta = 5  # 切换到测距操作单元
    
    def _build_emergency_slot_message(self):
        """构建应急时隙消息"""
        self.lora_send_data['pay_len'] = 9
        self.lora_send_data['send_dat'][0] = 0x20
        self.lora_send_data['send_dat'][1] = 9
        self.lora_send_data['send_dat'][2] = 0xff  # 应急时隙发送
        self.lora_send_data['send_dat'][3] = self.local_id
        self.lora_send_data['send_dat'][4] = 0x00
        self.lora_send_data['send_dat'][5] = 0
        self.lora_send_data['send_dat'][6] = 0
        
        self.send_lora_message(MessageType.LORA_INQUIRY)
        logging.debug("构建应急时隙消息")
    
    def _build_cluster_poll_message(self):
        """构建簇首轮询消息"""
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
        logging.debug("构建簇首轮询消息")
    
    def _handle_node_polling(self):
        """处理节点轮询"""
        if self.send_con['poll_ok']:
            while True:
                if self.neighbor_node_sta[self.poll_node_id].node_sta == 2:  # 节点正常在网
                    if self.poll_cluster_id == self.sys_para['perm_period']:
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
    
    def _build_node_poll_message(self):
        """构建节点轮询消息"""
        self.lora_send_data['pay_len'] = 9
        self.lora_send_data['send_dat'][0] = 0x20
        self.lora_send_data['send_dat'][1] = 9
        self.lora_send_data['send_dat'][2] = self.poll_node_id  # 当前轮询节点ID
        self.poll_cluster_id += 1
        self.poll_node_id += 1
        
        # 需要判别是否是网管发起的某查询
        if self.node_ask_sta[self.local_id].node_ask_en:  # 网管发起轮询
            self.lora_send_data['send_dat'][3] = 0xfe
            self.lora_send_data['send_dat'][4] = self.node_ope_sta[0].node_opedata[0]
        else:
            self.lora_send_data['send_dat'][3] = self.local_id
            self.lora_send_data['send_dat'][4] = self.node_ask_sta[0].node_opedata + 1
        
        # 更新询问数据
        if self.node_ask_sta[0].node_opedata == 2:
            self.node_ask_sta[0].node_opedata = 0x8
        else:
            self.node_ask_sta[0].node_opedata = self.node_ask_sta[0].node_opedata >> 1
        
        self.lora_send_data['send_dat'][5] = 0
        self.lora_send_data['send_dat'][6] = 0
        
        self.send_lora_message(MessageType.LORA_INQUIRY)
        self.send_con['poll_ok'] = False
        logging.debug("构建节点轮询消息")
    
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
    
    def _build_ranging_command(self):
        """构建测距指令"""
        self.lora_send_data['pay_len'] = 10
        self.lora_send_data['send_dat'][0] = 0x11
        self.lora_send_data['send_dat'][1] = 10
        self.lora_send_data['send_dat'][2] = self.poll_node_id  # 当前轮询节点ID
        self.lora_send_data['send_dat'][3] = 0xfe
        self.lora_send_data['send_dat'][4] = self.distanc_sta[self.poll_node_id].des_nod_id
        self.lora_send_data['send_dat'][5] = 0  # 测距次数
        self.lora_send_data['send_dat'][6] = 0
        self.lora_send_data['send_dat'][7] = 0
        
        self.send_lora_message(MessageType.LORA_RANGING_REQ)
        self.send_con['poll_ok'] = False
        logging.debug("构建测距指令")
    
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
    
    def _build_status_setting_command(self):
        """构建状态设置指令"""
        self.lora_send_data['pay_len'] = 12
        self.lora_send_data['send_dat'][0] = 0x04
        self.lora_send_data['send_dat'][1] = 12
        self.lora_send_data['send_dat'][2] = self.poll_node_id  # 当前轮询节点ID
        self.lora_send_data['send_dat'][3] = 0xfe
        
        # 复制操作数据
        for i in range(6):
            self.lora_send_data['send_dat'][4 + i] = self.node_ope_sta[self.poll_node_id].node_opedata[i]
        
        self.lora_send_data['send_dat'][10] = 0
        self.lora_send_data['send_dat'][11] = 0
        
        self.send_lora_message(MessageType.LORA_NODE_CONTROL)
        self.send_con['poll_ok'] = False
        logging.debug("构建状态设置指令")
    
    def _handle_cluster_business_data(self):
        """处理簇首业务数据"""
        if self.traffic_data['traffic_pack']:
            self.traffic_send_en = True
            
            if self.traffic_data['traffic_pack'] == self.traffic_data['data_num']:
                self.traffic_data['traffic_pack'] = 0
                self.cluster_poll_sta = 2  # 业务数据发送完成，切换到轮询状态
            else:
                self.lora_send_data['pay_len'] = self.traffic_data['traffic_dat'][1]
                # 复制业务数据
                for i in range(self.lora_send_data['pay_len']):
                    self.lora_send_data['send_dat'][i] = self.traffic_data['traffic_dat'][i]
                
                self.send_con['poll_ok'] = False
                self.traffic_data['data_num'] += 1
        
        logging.debug("处理簇首业务数据")
    
    def _handle_cluster_node_polling(self):
        """处理簇首节点轮询"""
        if self.send_con['poll_ok']:
            while True:
                if self.poll_node_id < len(self.sys_para['clust_node_id']):
                    cluster_node_id = self.sys_para['clust_node_id'][self.poll_node_id]
                    if self.neighbor_node_sta[cluster_node_id].node_sta:  # 判断节点是否在网
                        break
                self.poll_node_id += 1
                if self.poll_node_id > 0x7e:  # 达到最大节点ID
                    self.cluster_poll_sta = 3  # 切换到状态汇聚操作
                    break
            
            if (self.poll_node_id <= 0x7e and 
                self.poll_node_id < len(self.sys_para['clust_node_id'])):
                self._build_cluster_node_poll_message()
    
    def _build_cluster_node_poll_message(self):
        """构建簇首节点轮询消息"""
        self.lora_send_data['pay_len'] = 9
        self.lora_send_data['send_dat'][0] = 0x20
        self.lora_send_data['send_dat'][1] = 9
        self.lora_send_data['send_dat'][2] = self.poll_node_id  # 当前轮询节点ID
        self.lora_send_data['send_dat'][3] = self.local_id
        self.lora_send_data['send_dat'][4] = self.node_ask_sta[0].node_opedata + 1
        
        # 更新询问数据
        if self.node_ask_sta[0].node_opedata == 2:
            self.node_ask_sta[0].node_opedata = 0x8
        else:
            self.node_ask_sta[0].node_opedata = self.node_ask_sta[0].node_opedata >> 1
        
        self.lora_send_data['send_dat'][5] = 0
        self.lora_send_data['send_dat'][6] = 0
        
        self.send_lora_message(MessageType.LORA_INQUIRY)
        self.send_con['poll_ok'] = False
        logging.debug("构建簇首节点轮询消息")
    
    def _handle_cluster_status_aggregation(self):
        """处理簇首状态汇聚"""
        self.lora_send_data['send_dat'][0] = 0x25
        self.lora_send_data['send_dat'][2] = self.sys_para['mother_id']  # 目标母星ID
        self.lora_send_data['send_dat'][3] = self.local_id
        self.lora_send_data['send_dat'][4] = self.sys_para['clust_numb']
        self.lora_send_data['send_dat'][5] = self.local_id  # 节点ID
        self.lora_send_data['send_dat'][6] = 0xf  # 本节点状态
        
        j = 8
        for i in range(1, self.sys_para['clust_numb']):
            if i < len(self.sys_para['clust_node_id']):
                cluster_node_id = self.sys_para['clust_node_id'][i]
                self.lora_send_data['send_dat'][j] = cluster_node_id  # 节点ID
                self.lora_send_data['send_dat'][j + 1] = self.neighbor_node_sta[cluster_node_id].node_healty_sta  # 节点状态
                j += 2
        
        self.node_ask_sta[0].node_opedata = self.node_ask_sta[0].node_opedata >> 1
        j += 2
        
        self.lora_send_data['pay_len'] = j  # 帧数据长度
        self.lora_send_data['send_dat'][1] = self.lora_send_data['pay_len']
        
        self.send_lora_message(MessageType.LORA_CLUSTER_STATUS)
        self.cluster_poll_sta = 0  # 簇首发送应答，结束当前轮询
        logging.debug("构建簇首状态汇聚消息")
    
    def _handle_iot_mode(self):
        """处理物联网模式"""
        if self.sys_para['node_mod'] == 0:  # 母星
            self._build_broadcast_message(0x00)  # 母星发送广播消息，系统静默和潜伏
        elif self.link_sta == 4:  # 其他节点
            self._handle_node_periodic_transmission()
        elif self.link_sta == 2:  # 已经获得同步，发送入网注册消息
            self._build_network_registration_request()
    
    def _handle_node_periodic_transmission(self):
        """处理节点周期性传输"""
        temp = self.sys_base_time + self.local_id * 5
        if self.second_count > temp:
            if self.node_data['node_period']:  # 发送节点状态
                if temp < self.second_count:
                    temp += self.node_data['node_period']
                    
                    self.lora_send_data['pay_len'] = 27  # 数据长度
                    self.lora_send_data['send_dat'][0] = 0x23  # 帧类型
                    
                    for i in range(4, 25):
                        self.lora_send_data['send_dat'][i] = (
                            self.node_data['node_data'][i] if i < len(self.node_data['node_data']) else 0
                        )
                    
                    self.send_lora_message(MessageType.LORA_NODE_STATUS)
                
                # 检查是否需要发送卫星数据
                if (self.lora_send_data['pay_len'] and 
                    self.node_data['sat_period'] and 
                    self.node_data['sat_time'] < self.second_count):
                    self._build_satellite_data()
                
                # 检查是否需要发送载荷数据
                if (self.lora_send_data['pay_len'] == 0 and 
                    self.node_data['paload_period'] and 
                    self.node_data['paload_time'] < self.second_count):
                    self._build_payload_data()
    
    def _build_satellite_data(self):
        """构建卫星数据"""
        self.node_data['sat_time'] += self.node_data['sat_period']
        self.lora_send_data['pay_len'] = 18
        self.lora_send_data['send_dat'][0] = 0x26
        self.lora_send_data['send_dat'][1] = 11
        self.lora_send_data['send_dat'][2] = self.lora_recv_data['recv_dat'][3]  # 获取目的地址
        self.lora_send_data['send_dat'][3] = self.local_id
        
        for i in range(4, 18):
            self.lora_send_data['send_dat'][i] = (
                self.node_data['sat_data'][i] if i < len(self.node_data['sat_data']) else 0
            )
        
        self.send_lora_message(MessageType.LORA_PLATFORM_DATA)
        logging.debug("构建卫星数据")
    
    def _build_payload_data(self):
        """构建载荷数据"""
        self.node_data['paload_time'] += self.node_data['paload_period']
        self.lora_send_data['pay_len'] = 18
        self.lora_send_data['send_dat'][0] = 0x26
        self.lora_send_data['send_dat'][1] = 11
        self.lora_send_data['send_dat'][2] = self.lora_recv_data['recv_dat'][3]  # 获取目的地址
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
        logging.debug("构建载荷数据")
    
    def _handle_network_management_data(self):
        """处理网络管理数据"""
        self.lora_send_data['pay_len'] = self.netman_recv_dat[1]
        
        for i in range(self.netman_recv_dat[1]):
            self.lora_send_data['send_dat'][i] = self.netman_recv_dat[i]
        
        # 业务数据搬移完毕，通知网关发送新的业务
        self.netman_new_dat = False
        logging.debug("处理网络管理数据")
    
    def _handle_mother_lost_mode(self):
        """处理母星丢失模式"""
        temp = self.lora_recv_data['recv_ok_time'] + self.time_out
        if self.second_count > temp:
            self.lora_send_data['pay_len'] = 14
            self.lora_send_data['send_dat'][0] = 0x1A
            self.lora_send_data['send_dat'][1] = 14
            self.lora_send_data['send_dat'][2] = self.local_id
            self.lora_send_data['send_dat'][3] = 0
            self.lora_send_data['send_dat'][4] = 234  # 后期设计专门的意愿算法
            self.lora_send_data['send_dat'][5] = self.node_para['node_ability']
            
            # 填充固定值
            fixed_values = [0x12, 0x34, 0x56, 0x78, 0x90, 0xef]
            for i, val in enumerate(fixed_values):
                if i + 6 < 12:
                    self.lora_send_data['send_dat'][i + 6] = val
            
            self.send_lora_message(MessageType.LORA_MOTHER_ELECTION)
            logging.debug("处理母星丢失模式")
    
    def _handle_node_status_response(self):
        """处理节点状态响应"""
        # 物联网模式，母星需要应答
        if (self.sys_para['net_mod'] < 6) and (self.sys_para['node_mod'] == 0):
            self._build_broadcast_message(self.send_con['currend_id'])
            self.send_con['netman_send_en'] = False
        logging.debug("处理节点状态响应")
    
    def _handle_platform_data_response(self):
        """处理平台数据响应"""
        # 物联网模式，母星需要应答
        if (self.sys_para['net_mod'] < 6) and (self.sys_para['node_mod'] == 0):
            self._build_broadcast_message(self.send_con['currend_id'])
            self.send_con['netman_send_en'] = False
        logging.debug("处理平台数据响应")
    
    def _handle_link_status_response(self):
        """处理链路状态响应"""
        # 物联网模式，母星需要应答
        if (self.sys_para['net_mod'] < 6) and (self.sys_para['node_mod'] == 0):
            self._build_broadcast_message(self.send_con['currend_id'])
            self.send_con['netman_send_en'] = False
        logging.debug("处理链路状态响应")
    
    def _handle_mother_election_response(self):
        """处理母星选举响应"""
        if self.lora_recv_data['recv_dat'][2] == self.local_id - 1:  # 上一个发送数据的前一个ID
            self.lora_send_data['pay_len'] = 14
            self.lora_send_data['send_dat'][0] = 0x1A
            self.lora_send_data['send_dat'][1] = 14
            self.lora_send_data['send_dat'][2] = self.local_id
            self.lora_send_data['send_dat'][3] = 0
            self.lora_send_data['send_dat'][4] = 234  # 后期设计专门的意愿算法
            self.lora_send_data['send_dat'][5] = self.node_para['node_ability']
            
            # 填充固定值
            fixed_values = [0x12, 0x34, 0x56, 0x78, 0x90, 0xef]
            for i, val in enumerate(fixed_values):
                if i + 6 < 12:
                    self.lora_send_data['send_dat'][i + 6] = val
            
            self.send_lora_message(MessageType.LORA_MOTHER_ELECTION)
        elif self.local_id > self.lora_recv_data['recv_dat'][2]:
            self.time_out = (self.local_id - self.lora_recv_data['recv_dat'][3]) * 100  # 超时检测
        
        logging.debug("处理母星选举响应")
    
    def _build_platform_inquiry_response(self):
        """构建平台数据询问响应"""
        self.lora_send_data['pay_len'] = 18
        self.lora_send_data['send_dat'][0] = 0x26
        self.lora_send_data['send_dat'][1] = 11
        self.lora_send_data['send_dat'][2] = self.lora_recv_data['recv_dat'][3]  # 获取目的地址
        self.lora_send_data['send_dat'][3] = self.local_id
        
        for i in range(4, 18):
            self.lora_send_data['send_dat'][i] = (
                self.node_data['sat_data'][i] if i < len(self.node_data['sat_data']) else 0
            )
        
        self.send_lora_message(MessageType.LORA_PLATFORM_DATA)
        logging.debug("构建平台数据询问响应")
    
    def _build_payload_inquiry_response(self):
        """构建载荷数据询问响应"""
        self.lora_send_data['pay_len'] = 18
        self.lora_send_data['send_dat'][0] = 0x26
        self.lora_send_data['send_dat'][1] = 11
        self.lora_send_data['send_dat'][2] = self.lora_recv_data['recv_dat'][3]  # 获取目的地址
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
        logging.debug("构建载荷数据询问响应")
    
    def _build_link_inquiry_response(self):
        """构建链路数据询问响应"""
        # 保留，需要对邻居节点的功率进行排序
        logging.debug("构建链路数据询问响应 - 功能保留")
    
    def _build_abnormal_payload_data(self):
        """构建异常载荷数据"""
        self.lora_send_data['pay_len'] = 18
        self.lora_send_data['send_dat'][0] = 0x26
        self.lora_send_data['send_dat'][1] = 11
        self.lora_send_data['send_dat'][2] = self.lora_recv_data['recv_dat'][3]  # 获取目的地址
        self.lora_send_data['send_dat'][3] = self.local_id
        self.lora_send_data['send_dat'][4] = 2  # 异常标志
        
        for i in range(5, 18):
            self.lora_send_data['send_dat'][i] = (
                self.node_data['payload_data'][i] if i < len(self.node_data['payload_data']) else 0
            )
        
        self.send_lora_message(MessageType.LORA_PLATFORM_DATA)
        self.node_data['paload_unnormal'] = False
        logging.debug("构建异常载荷数据")
    
    def _process_general_ack(self):
        """处理通用应答消息"""
        if ((self.lora_recv_data['recv_dat'][2] == 0xfe) and 
            (self.local_id == self.sys_para['mother_id'])):  # 接收地址是网管，本机是母星
            
            # 母星更改节点状态的特殊处理
            fram_type = self.lora_recv_data['recv_dat'][4]
            node_id = self.lora_recv_data['recv_dat'][3]
            
            if fram_type == 0x03:  # 注册应答消息
                if self.neighbor_node_sta[node_id].node_sta == 1:
                    self.neighbor_node_sta[node_id].node_sta = 2
            elif fram_type == 0x04:  # 节点操作，更改状态
                ope_data = self.node_ope_sta[node_id].node_opedata[0]
                if ope_data == 0:    # 常态
                    self.neighbor_node_sta[node_id].node_sta = 2
                elif ope_data == 1:  # 静默
                    self.neighbor_node_sta[node_id].node_sta = 3
                elif ope_data == 2:  # 潜伏
                    self.neighbor_node_sta[node_id].node_sta = 4
                else:                # 离网
                    self.neighbor_node_sta[node_id].node_sta = 0
            
            self.netman_send_en = True    # 透传到网关
            self.send_con['poll_ok'] = True  # 操作结束，需要切换到新的节点
        
        logging.debug("处理通用应答消息")
    
    def _process_registration_request(self):
        """处理注册请求"""
        # 检测网管是否在线，若在线同时转发到网管，暂时保留
        if self.local_id == self.sys_para['mother_id']:  # 本机是母星，母星处理该消息
            recv_data = self.lora_recv_data['recv_dat']
            
            # 验证安全数据
            if ((recv_data[21] == 0x12) or (recv_data[22] == 0x34) or 
                (recv_data[23] == 0x56) or (recv_data[24] == 0x78)):
                
                node_id = recv_data[4]
                node_status = self.neighbor_node_sta[node_id]
                
                # 更新节点状态信息
                node_status.node_sta = 1
                node_status.node_position = 2
                node_status.mac_addr = [recv_data[5], recv_data[6], recv_data[7]]
                node_status.node_ability = recv_data[8]
                node_status.freq_rang = recv_data[9]
                node_status.node_pow = self.lora_recv_data['recv_SNR']  # 使用信噪比
                node_status.VGA = recv_data[11]
                
                # 空间坐标
                node_status.pos_x = ((recv_data[12] << 16) + (recv_data[13] << 8) + recv_data[14])
                node_status.pos_y = ((recv_data[15] << 16) + (recv_data[16] << 8) + recv_data[17])
                node_status.pos_z = ((recv_data[18] << 16) + (recv_data[19] << 8) + recv_data[20])
                
                # 其他参数
                node_status.cluster_id = 0
                node_status.node_det_num = 3
                node_status.node_det_tim = 1
                node_status.node_SF = self.sys_para['SF_base_backw']
                node_status.node_sta = 0x00
                
                self.send_con['recv_send_en'] = True
        
        self.netman_send_en = True  # 透传到网关
        logging.debug("处理注册请求")
    
    def _process_registration_response(self):
        """处理注册应答"""
        # MAC地址匹配，更改状态
        recv_data = self.lora_recv_data['recv_dat']
        if ((recv_data[4] == self.node_para['mac_addr'][2]) and 
            (recv_data[5] == self.node_para['mac_addr'][1]) and 
            (recv_data[6] == self.node_para['mac_addr'][0])):
            
            self.link_sta = 3  # 节点正确入网
            self.neighbor_node_sta[self.sys_para['mother_id']].node_det_num = 3
            self.send_con['recv_send_en'] = True  # 数据需要应答，通用ACK
        
        logging.debug("处理注册应答")
    
    def _process_node_control(self):
        """处理节点控制"""
        # ID匹配，更改本地数据上报时间设置
        if self.lora_recv_data['recv_dat'][2] == self.local_id:
            recv_data = self.lora_recv_data['recv_dat']
            
            self.sys_para['node_mod'] = recv_data[4]  # 节点属性
            self.link_sta = recv_data[5] + 4          # 节点状态
            self.re_enter_time = (recv_data[6] << 8) + recv_data[7]  # 重入网时间
            
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
        logging.debug("处理节点控制")
    
    def _process_cluster_control(self):
        """处理簇控制"""
        # 广播消息，不需要应答
        recv_data = self.lora_recv_data['recv_dat']
        cluster_count = recv_data[4]  # 配置的簇的数目
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
                        self.sys_para['node_mod'] = 1  # 簇首ID
                        found_cluster = True
                    else:
                        self.sys_para['node_mod'] = 2  # 普通节点
                else:
                    if found_cluster:
                        self.sys_para['clust_node_id'][k-1] = recv_data[j]
                j += 1
            
            if found_cluster:  # 查找到簇
                self.sys_para['clust_id'] = (temp1 >> 24) & 0xff
                self.sys_para['clust_numb'] = node_count - 1
                self.cluster_poll_sta = 0
                break
        
        logging.debug("处理簇控制")
    
    def _update_local_time(self):
        """更新本地时间"""
        # 进行时间调整，从广播消息中提取时间信息
        recv_data = self.lora_recv_data['recv_dat']
        
        # 提取时间基准和偏移量
        sys_base_time = (recv_data[5] << 8) + recv_data[6]
        sys_time_offset = ((recv_data[7] << 16) + (recv_data[8] << 8) + recv_data[9])
        
        # 更新本地时间参数
        self.sys_base_time = sys_base_time
        self.sys_time_offset = sys_time_offset
        
        logging.debug("更新本地时间")
    
    def _update_network_parameters(self):
        """更新网络参数"""
        recv_data = self.lora_recv_data['recv_dat']
        
        # 更新网络配置参数
        self.sys_para['clust_id'] = 0xf0  # 保留
        self.sys_para['node_num'] = recv_data[22]
        self.sys_para['max_id'] = recv_data[23]
        
        # 更新SF参数
        self.sys_para['SF_base_forw'] = recv_data[18] & 0xf
        self.sys_para['SF_high_forw'] = (recv_data[18] >> 4) & 0xf
        self.sys_para['clust_SF_base_forw'] = recv_data[19] & 0xf
        self.sys_para['clust_SF_base_backw'] = (recv_data[19] >> 4) & 0xf
        
        # 系统信号模式
        self.sys_para['sys_sig_mod'] = (self.sys_para['SF_base_forw'] > 
                                       self.sys_para['SF_high_forw'])
        
        # 其他参数
        self.sys_para['wake_mod'] = 1
        self.sys_para['un_permit'] = 1
        self.sys_para['perm_period'] = recv_data[20]
        
        # 系统时间参数
        self.sys_base_time = 0
        self.sys_time_offset = 0
        self.sys_para['sys_fram_period'] = (recv_data[15] << 8) + recv_data[16]
        self.sys_para['burst_time_base'] = recv_data[17]
        
        logging.debug("更新网络参数")
    
    def _user_exit_detection_main(self):
        """母星、簇首用户退出检测"""
        for i in range(128):
            if self.neighbor_node_sta[i].node_sta == 2:  # 节点是正常状态，进行检测
                if self.neighbor_node_sta[i].node_det_tim:  # 正确检测到信号
                    self.neighbor_node_sta[i].node_det_tim = 0
                    sf_index = min(self.neighbor_node_sta[i].node_pow, len(self.SF_table) - 1)
                    temp_sf = self.SF_table[sf_index]
                    
                    if temp_sf >= self.neighbor_node_sta[i].node_SF:  # 信噪比变小，需要调增SF
                        if self.neighbor_node_sta[i].node_SF < self.sys_para['SF_base_backw']:
                            self.neighbor_node_sta[i].node_SF += 1
                        self.neighbor_node_sta[i].node_det_num = 3
                    elif temp_sf < self.neighbor_node_sta[i].node_SF:  # 信噪比变大，需要调减SF
                        if self.neighbor_node_sta[i].node_det_num > 8:
                            if self.neighbor_node_sta[i].node_SF > 7:
                                self.neighbor_node_sta[i].node_SF -= 1
                            self.neighbor_node_sta[i].node_det_num = 3
                        else:
                            self.neighbor_node_sta[i].node_det_num += 1
                
                elif self.neighbor_node_sta[i].node_det_num > 0:  # 未正确检测到应答信号
                    self.neighbor_node_sta[i].node_det_num -= 1
                    
                    if self.neighbor_node_sta[i].node_SF < self.sys_para['SF_base_backw']:
                        self.neighbor_node_sta[i].node_SF += 1
                    
                    if self.neighbor_node_sta[i].node_det_num == 0:
                        self.neighbor_node_sta[i].node_sta = 0  # 节点不在网
                        self.neighbor_node_sta[i].node_SF = self.sys_para['SF_base_backw']
            
            elif self.neighbor_node_sta[i].node_sta == 1:  # 节点是入网状态，但未接收到应答
                self.neighbor_node_sta[i].node_sta = 0  # 节点不在网
        
        logging.debug("母星用户退出检测完成")
    
    def _user_exit_detection_user(self):
        """普通节点用户退出检测"""
        mother_id = self.sys_para['mother_id']
        
        if self.neighbor_node_sta[mother_id].node_det_tim:  # 检测到母星信号
            self.neighbor_node_sta[mother_id].node_det_num = 3
            self.neighbor_node_sta[mother_id].node_det_tim = 0
        elif self.user_det_tim:  # 未接收到母星信号，但检测到其他用户信号
            self.neighbor_node_sta[mother_id].node_det_num += 1
            self.user_det_tim = 0
            if self.neighbor_node_sta[mother_id].node_det_num == 6:
                self.link_sta = 0  # 未检测到母星信号，用户离网
        else:  # 未接收到母星信号，未检测到其他用户信号
            if self.neighbor_node_sta[mother_id].node_det_num == 0:
                self.link_sta = 5
                self.sys_para['net_mod'] = 8  # 母星丢失状态
            self.neighbor_node_sta[mother_id].node_det_num -= 1
        
        logging.debug("普通节点用户退出检测完成")