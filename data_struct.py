from dataclasses import dataclass, field
from typing import List
import numpy as np

# =================== 全局变量定义 ===================

# 系统常量定义
PI = 32768
recv_thred = 32000  # 信号检测基本门限
TIME_BASE = 100  # 基本时间处理单位为100ms，设计的基本时间单位为10ms,等于400000个时钟
c_speed = 300000  # km/s

# 节点工作模式和状态
node_work_mod = 0  # 节点工作模式，0 - 单机模式， 1 - 组网模式
link_sta = 0  # 节点网络状态，0 - 空闲，1 - 信号搜索状态，2-获得时间同步，3-发送入网消息，4-接收到应答消息完成入网，5-母星丢失，6离网
sending_state = 0  # 0 未发送信号，1启动发送信号，2信号发送，3 信号发送完成
cluster_receiv_mod = 0  # 簇首模式下接收信号方式，0接收簇信号，1可以接收母星信号
recv_power = 0  # 接收信号功率

polling_state = 0  # 数据询问发送状态
clust_operate = 0  # 簇首轮询模式
mod_convert = 0  # 系统模式切换状态
mother_sat_convert = 0  # 主动母星切换状态
clust_polling = 0  # 母星簇轮询还是节点轮询
clust_polling_id = 0  # 簇轮询ID, 簇ID > 0x80
node_poliing_id = 0  # 节点轮询ID，节点ID 0~127
traffic_send_en = 0  # 表示字，用于指示当前是业务数据发送状态

time_out = 0  # 超时设置

send_fram_num = 0  # 发送数据包数目
recv_fram_err = 0  # 接收的错误帧计数
recv_fram_num = 0  # 正确接收帧计数
recv_totle_num = 0  # 总的接收帧计数
recv_fram_self = 0  # 本节点正确帧计数

to_convert_mother_id = 0

# =================== 数据结构定义 ===================

@dataclass
class SysParaDef:
    """网络状态参数"""
    net_mod: int = 0  # 物联网模式（0-6各种模式，7-簇首调度模式，8-自组织网模式）
    node_mod: int = 0  # 节点模式，母星、簇首、普通节点
    net_id: int = 0  # 网络ID
    mother_id: int = 0  # 母星ID
    gateway_id: int = 0  # 网管ID
    node_num: int = 0  # 系统节点数目
    max_id: int = 0  # 系统最大节点ID
    
    fre_forw: int = 0  # 前向频率
    bw_forw: int = 0  # 前向信号带宽
    cr_forw: int = 0  # 前向信号编码
    SF_base_forw: int = 0  # 组网基本SF
    SF_high_forw: int = 0  # 最高允许SF
    
    fre_backw: int = 0  # 反向频率
    bw_backw: int = 0  # 反向信号带宽
    cr_backw: int = 0  # 反向信号编码
    SF_base_backw: int = 0  # 组网基本SF
    SF_high_backw: int = 0  # 最高允许SF
    
    clust_id: int = 0  # 簇首ID
    clust_numb: int = 0  # 簇节点数
    clust_node_id: List[int] = field(default_factory=lambda: [0] * 32)  # 簇内节点ID
    
    clust_fre_forw: int = 0  # 前向频率
    clust_bw_forw: int = 0  # 前向信号带宽
    clust_cr_forw: int = 0  # 前向信号带宽
    clust_SF_base_forw: int = 0  # 组网基本SF
    
    clust_fre_backw: int = 0  # 反向频率
    clust_bw_backw: int = 0  # 反向信号带宽
    clust_cr_backw: int = 0  # 反向信号带宽
    clust_SF_base_backw: int = 0  # 组网基本SF
    
    sys_sig_mod: int = 0  # 信号模式，0传统信号，1自适应信号格式
    convert_mod: int = 0  # 广播消息内的状态切换指示
    
    wake_mod: int = 0  # 空口唤醒模式
    perm_period: int = 0  # 异常上报许周期
    
    sys_fram_period: int = 0  # 系统帧周期长度
    burst_time_base: int = 0  # 询问突发对对齐时间
    
    sig_det_time: int = 0  # 信号检测时间，单位毫秒
    node_sta_det: int = 3  # 节点状态监测次数，默认3
    
    un_permit: int = 0  # 异常上报允许


@dataclass
class NodeAbilityDef:
    """节点参数"""
    mac_addr: List[int] = field(default_factory=lambda: [0] * 3)  # MAC地址
    ip_addr: List[int] = field(default_factory=lambda: [0] * 4)  # IP地址（保留）
    sig_mod: int = 0  # 采用信号模式，0 常规，1 自适应
    data_mod: int = 0  # 数据白化处理
    pps_mod: int = 0  # 外部参考
    link_numb: int = 0  # 卫星支持的外部链接能力
    low_SF: int = 6  # 最低SF，6
    high_SF: int = 12  # 最高SF，12
    Freq_range: int = 0  # 频率适应范围
    max_Pow: int = 0  # 最大输出功率
    wake_period: int = 0  # 信号唤醒周期
    wake_time: int = 0  # 信号唤醒时间
    node_ability: int = 0  # 节点能力
    Pow_att: int = 0  # 最大功率衰减范围30dB
    locat_x: int = 0  # 空间坐标x
    locat_y: int = 0  # 空间坐标y
    locat_z: int = 0  # 空间坐标z


# 全局实例
local_id = 0  # 本机节点ID
sys_para = SysParaDef()  # 系统参数
node_para = NodeAbilityDef()  # 节点参数


@dataclass
class LoraSigDef:
    """信号参数"""
    sig_fre: int = 0  # 100Hz
    sig_bw: int = 0  # 0 - 125kHz,1 - 250kHz,2 - 500kHz, 3 - 1MHz
    sig_pow: int = 0  # 数字域信号功率
    sig_SF: int = 0  # 6~12
    sig_CR: int = 0  # 0-4/5,1-4/6,2-4/7,3-4/8
    head_mod: int = 0  # 1 to enable head
    CRC_head: int = 0  # 头数据包CRC编码使能
    CRC_data: int = 0  # 数据CRC使能
    dat_wit: int = 0  # 信号白化使能
    sig_ldr: int = 0  # 低速数据模式
    sig_mod: int = 0  # 信号方式，1为自定义边SF，0为常规
    FPGA_int: int = 0  # 1 FPGA实现交织编码


send_sig_para = LoraSigDef()  # 发送信号参数
recv_sig_para = LoraSigDef()  # 接收信号参数


@dataclass
class LoraSendDef:
    """发送数据参数"""
    adpt_SF: int = 0  # 自适应SF
    adpt_CR: int = 0  # 自适应码速率
    pay_len: int = 0  # 数据长度
    sym_len: int = 0  # 符号长度
    head_crc: int = 0  # head data CRC
    send_time_en: int = 0  # 定时发送使能
    send_time: int = 0  # 定时发送时间
    send_time_stamp: int = 0  # 发送时间戳
    send_dat: List[int] = field(default_factory=lambda: [0] * 256)  # 发送数据


Lora_send_data = LoraSendDef()  # 发送数据参数


@dataclass
class RecvDatprocDef:
    """接收数据处理"""
    recv_new: int = 0  # 新接收数据
    recv_length: int = 0  # 当前接收消息长度
    recv_time: int = 0  # 接收信号时间戳
    recv_ok_time: int = 0  # 接收信号时间
    recv_SNR: int = 0  # 接收信号信噪比
    recv_dat: List[int] = field(default_factory=lambda: [0] * 256)  # 数据处理流程


Lora_recv_data = RecvDatprocDef()


# 平台载荷接口
sat_recv_dat = [0] * 256  # 卫星平台接收数据
sat_send_dat = [0] * 256  # 卫星平台发送数据
satint_send_en = 0  # 卫星平台数据发送使能


@dataclass
class DataDef:
    """数据定义"""
    node_data: List[int] = field(default_factory=lambda: [0] * 32)  # 节点状态数据
    node_period: int = 0  # 节点状态数据上报周期
    node_time: int = 0  # 下一次数据上报时间
    
    sat_data: List[int] = field(default_factory=lambda: [0] * 32)  # 星状态数据
    sat_period: int = 0  # 卫星状态数据上报周期
    sat_time: int = 0  # 下一次数据上报时间
    
    payload_data: List[int] = field(default_factory=lambda: [0] * 32)  # 载荷数据
    payload_len: int = 0  # 数据长度
    paload_period: int = 0  # 载荷数据状态数据上报周期
    paload_time: int = 0  # 下一次数据上报时间
    paload_unnormal: int = 0  # 载荷数据异常标识


node_data = DataDef()  # 节点数据参数

# FPGA操作
fpga_opmod = 0  # FPGA寄存器读写模式，0 读，1写
fpga_opnum = 0  # FPGA数据读写次数

# 网管接口
netman_send_en = 0  # 网络管理接口数据发送使能
netman_link_sta = 0  # 网络连接状态，0 未连接，1连接
netman_new_dat = 0  # 新数据需要在Lora链路发送
receive_to_netman = 0  # 接收数据需要回传到本地

netman_recv_dat = [0] * 1024  # 从管理单元接收数据
netman_send_dat = [0] * 1024  # 发送到管理单元


@dataclass
class NodeOperateDef:
    """节点操作定义"""
    node_ope_en: int = 0  # 节点操作使能
    source_id: int = 0  # 询问id
    node_opedata: List[int] = field(default_factory=lambda: [0] * 5)  # 操作字


@dataclass
class MeasDisDef:
    """距离测量定义"""
    node_dis_en: int = 0  # 节点距离测量使能
    des_nod_id: int = 0  # 目的节点ID
    node_dis_dat: int = 0  # 节点距离测量数据


@dataclass
class NodeAskDef:
    """节点询问定义"""
    node_ask_en: int = 0  # 节点操作使能
    source_id: int = 0  # 询问id
    node_opedata: int = 0  # 操作字


@dataclass
class TrafficDataDef:
    """业务数据定义"""
    traffic_pack: int = 0
    data_num: int = 0
    traffic_dat: List[int] = field(default_factory=lambda: [0] * 1024)


traffic_data = TrafficDataDef()
distanc_sta = [MeasDisDef() for _ in range(128)]  # 节点距离测量
node_ask_sta = [NodeAskDef() for _ in range(128)]  # 节点询问
node_ope_sta = [NodeOperateDef() for _ in range(128)]  # 节点操作状态存储


@dataclass
class NetnodeTabDef:
    """网络邻居状态"""
    node_sta: int = 0  # 节点状态，0-不在线，1-发送入网应答注册，2-在网正常，3-潜伏 4-静默
    node_position: int = 0  # 节点属性，0母星，1簇首，2-常规
    cluster_id: int = 0  # 节点所在簇ID
    mac_addr: List[int] = field(default_factory=lambda: [0] * 3)  # MAC地址
    node_ability: int = 0  # 节点能力
    freq_rang: int = 0  # 频率范围
    node_pow: int = 0  # 节点信号功率
    VGA: int = 0
    pos_x: int = 0  # 位置x
    pos_y: int = 0  # 位置y
    pos_z: int = 0  # 位置z
    node_det_num: int = 3  # 节点在网连续检测次数，初始值3
    node_det_tim: int = 0  # 节点检测时间
    node_SF: int = 0  # SF值
    node_healty_sta: int = 0  # 节点健康状态


neighbor_node_sta = [NetnodeTabDef() for _ in range(128)]  # 网络节点状态表


@dataclass
class MotherSelectDef:
    """母星选择定义"""
    netman_link: List[int] = field(default_factory=lambda: [0] * 128)  # 网络管理状态
    mother_score: List[int] = field(default_factory=lambda: [0] * 128)  # 母星意愿分数
    local_link: int = 0  # 本节点其他测控链接的状态


node_mother_sta = MotherSelectDef()

# 时间相关变量
second_count = 0  # 秒以上计数
sub_sec_count = 0  # 秒以下计数
mil_sec_count = 0  # 毫秒计数
sub_sec_offset = 0  # 秒以下参数偏差

sys_base_time = 0  # 系统时间基准
next_base_time = 0  # 下一个系统时间
sys_time_offset = 0  # 时间偏差

re_enter_time = 0  # 节点再入时间

securit_data = 0x12345678  # 固定值

# =================== FPGA 地址定义 ===================

FPGA_sys_con_addr = 0x0000
FPGA_sys_ver_addr = 0x0001
FPGA_sys_clk_addr = 0x0002  # system clock
FPGA_sys_sclk_addr = 0x0002  # mdelay time
FPGA_sts_count_addr = 0x0003  # system counter

FPGA_send_base_addr = 0x0200
FPGA_Inte_base_addr = 0x0600
FPGA_send_contr_addr = 0x0000  # 发送控制寄存器
FPGA_send_amp_addr = 0x0001  # 信号幅度
FPGA_send_time_addr = 0x0002  # 发送时间戳
FPGA_send_netid_addr = 0x0003  # 网络ID
FPGA_send_waitc_addr = 0x0004  # 等待计数器
FPGA_send_head_addr = 0x0005  # 包头数据
FPGA_send_len_addr = 0x0006  # 符号长度寄存器
FPGA_send_data_addr = 0x0007  # 数据寄存器
FPGA_send_sendsta_addr = 0x0008  # 发送状态寄存器

FPGA_recv_base_addr = 0x0400
FPGA_recv_contr_addr = 0x0000  # 接收控制寄存器
FPGA_recv_capt_addr = 0x0000  # 捕获门限
FPGA_recv_netid_addr = 0x0000  # 网络ID
FPGA_recv_waitc_addr = 0x0000  # 等待计数器
FPGA_recv_dlen_addr = 0x0000  # 接收数据长度
FPGA_recv_data_addr = 0x0000  # 接收数据寄存器
FPGA_recv_time_addr = 0x0000  # 接收时间戳寄存器


@dataclass
class SendConDef:
    """发送控制定义"""
    poll_ok: int = 0  # 当前节点、簇轮询结束
    currend_id: int = 0  # 当前轮询ID
    recv_send_en: int = 0  # 接收数据需要应答
    fram_type: int = 0  # 接收数据方式字
    time_send_en: int = 0  # 按照时隙轮询使能
    unnormal_send_en: int = 0  # 载荷数据异常发射使能
    netman_send_en: int = 0  # 网络数据发送使能


send_con = SendConDef()  # 发送控制状态寄存器相关


@dataclass
class InitDataDef:
    """初始化数据定义"""
    node_work_mode: int = 1  # 默认为单机模式
    node_time_mode: int = 0  # 不存在外部时间同步
    node_net_pos: int = 2  # 网络节点位置
    net_forward_SF: int = 12  # 初始化前向SF
    net_forward_CR: int = 3  # 初始化前向CR
    net_forward_fre: int = 12000000  # 初始化前向频率，单位为100Hz
    net_backward_SF: int = 12  # 初始化反向SF
    net_backward_CR: int = 3  # 初始化反向CR
    net_backward_fre: int = 12000000  # 初始化反向频率
    node_sigform: int = 1  # 信号格式
    node_CRC_form: int = 0  # 数据CRC禁止


init_data = InitDataDef()

# 循环变量
i = 0
j = 0
k = 0
temp = 0
temp1 = 0
temp2 = 0
temp3 = 0

poll_cluster_id = 0  # 当前轮询簇ID
poll_node_id = 0  # 当前轮询节点ID
wait_ack_sta = 0  # 等待应答状态
mother_poll_sta = 0  # 母星轮询状态
cluster_poll_sta = 0  # 簇首轮询状态
multi_send_num = 0  # 多次发送数据的次数控制

work_mod_convert = 0  # 系统工作在切换模式


@dataclass
class LoraSigDef2:
    """Lora信号参数2"""
    send_CRC_data: int = 0  # 数据CRC，固定为0
    send_sig_ldr: int = 0  # 低速扩展模式，固定为0
    send_head_mod: int = 1  # 是否包含包头；固定为1
    send_CRC_head: int = 1  # 头数据校验使能,固定为1
    send_cont: int = 0  # 连续发送使能
    send_FPGA_int: int = 0  # FPGA编码交织
    
    recv_CRC_data: int = 0  # 数据CRC，固定为0
    recv_sig_ldr: int = 0  # 低速扩展模式，固定为0
    recv_head_mod: int = 1  # 是否包含包头；固定为1
    recv_CRC_head: int = 1  # 头数据校验使能,固定为1
    recv_cont: int = 0  # 连续接收收使能
    recv_agc_en: int = 0  # AGC 使能
    recv_FPGA_int: int = 0  # FPGA编码交织
    
    FPGA_sendxorrecv: int = 0  # 信号收发关联
    SFD_ser_num: int = 0  # 搜索SFD数目
    
    recv_chan_det: int = 0  # 信道状态检测使能
    dat_white: int = 0  # 数据白化使能
    inter_syn: int = 0  # 干扰信号同步使能
    
    precode_num: int = 0  # 前导符号数
    syn_word0: int = 0  # 同步字
    syn_word1: int = 0
    
    send_pow: int = 0  # 信号输出幅度
    
    int_sf: int = 0  # 干扰信号SF
    int_pow: int = 0  # 干扰信号功率
    
    noise_pow: int = 0  # 噪声信号功率
    noise_mod: int = 0  # 噪声信号模式


Lora_para = LoraSigDef2()

# 初始化数据
white_data = [0x00] * 256
SF_table = [12,12,12,12,12,11,11,11,11,10,10,10,10,9,9,9,9,9,8,8,8,8,7,7,7,7,6,6,6,6] + [0] * 97  # 补齐到127
to_int_RF_fre = 0  # 使能频率初始化
to_int_fpga = 0  # 初始化FPGA