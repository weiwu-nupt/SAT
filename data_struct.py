from dataclasses import dataclass, field
from typing import List
import numpy as np

# =================== ȫ�ֱ������� ===================

# ϵͳ��������
PI = 32768
recv_thred = 32000  # �źż���������
TIME_BASE = 100  # ����ʱ�䴦��λΪ100ms����ƵĻ���ʱ�䵥λΪ10ms,����400000��ʱ��
c_speed = 300000  # km/s

# �ڵ㹤��ģʽ��״̬
node_work_mod = 0  # �ڵ㹤��ģʽ��0 - ����ģʽ�� 1 - ����ģʽ
link_sta = 0  # �ڵ�����״̬��0 - ���У�1 - �ź�����״̬��2-���ʱ��ͬ����3-����������Ϣ��4-���յ�Ӧ����Ϣ���������5-ĸ�Ƕ�ʧ��6����
sending_state = 0  # 0 δ�����źţ�1���������źţ�2�źŷ��ͣ�3 �źŷ������
cluster_receiv_mod = 0  # ����ģʽ�½����źŷ�ʽ��0���մ��źţ�1���Խ���ĸ���ź�
recv_power = 0  # �����źŹ���

polling_state = 0  # ����ѯ�ʷ���״̬
clust_operate = 0  # ������ѯģʽ
mod_convert = 0  # ϵͳģʽ�л�״̬
mother_sat_convert = 0  # ����ĸ���л�״̬
clust_polling = 0  # ĸ�Ǵ���ѯ���ǽڵ���ѯ
clust_polling_id = 0  # ����ѯID, ��ID > 0x80
node_poliing_id = 0  # �ڵ���ѯID���ڵ�ID 0~127
traffic_send_en = 0  # ��ʾ�֣�����ָʾ��ǰ��ҵ�����ݷ���״̬

time_out = 0  # ��ʱ����

send_fram_num = 0  # �������ݰ���Ŀ
recv_fram_err = 0  # ���յĴ���֡����
recv_fram_num = 0  # ��ȷ����֡����
recv_totle_num = 0  # �ܵĽ���֡����
recv_fram_self = 0  # ���ڵ���ȷ֡����

to_convert_mother_id = 0

# =================== ���ݽṹ���� ===================

@dataclass
class SysParaDef:
    """����״̬����"""
    net_mod: int = 0  # ������ģʽ��0-6����ģʽ��7-���׵���ģʽ��8-����֯��ģʽ��
    node_mod: int = 0  # �ڵ�ģʽ��ĸ�ǡ����ס���ͨ�ڵ�
    net_id: int = 0  # ����ID
    mother_id: int = 0  # ĸ��ID
    gateway_id: int = 0  # ����ID
    node_num: int = 0  # ϵͳ�ڵ���Ŀ
    max_id: int = 0  # ϵͳ���ڵ�ID
    
    fre_forw: int = 0  # ǰ��Ƶ��
    bw_forw: int = 0  # ǰ���źŴ���
    cr_forw: int = 0  # ǰ���źű���
    SF_base_forw: int = 0  # ��������SF
    SF_high_forw: int = 0  # �������SF
    
    fre_backw: int = 0  # ����Ƶ��
    bw_backw: int = 0  # �����źŴ���
    cr_backw: int = 0  # �����źű���
    SF_base_backw: int = 0  # ��������SF
    SF_high_backw: int = 0  # �������SF
    
    clust_id: int = 0  # ����ID
    clust_numb: int = 0  # �ؽڵ���
    clust_node_id: List[int] = field(default_factory=lambda: [0] * 32)  # ���ڽڵ�ID
    
    clust_fre_forw: int = 0  # ǰ��Ƶ��
    clust_bw_forw: int = 0  # ǰ���źŴ���
    clust_cr_forw: int = 0  # ǰ���źŴ���
    clust_SF_base_forw: int = 0  # ��������SF
    
    clust_fre_backw: int = 0  # ����Ƶ��
    clust_bw_backw: int = 0  # �����źŴ���
    clust_cr_backw: int = 0  # �����źŴ���
    clust_SF_base_backw: int = 0  # ��������SF
    
    sys_sig_mod: int = 0  # �ź�ģʽ��0��ͳ�źţ�1����Ӧ�źŸ�ʽ
    convert_mod: int = 0  # �㲥��Ϣ�ڵ�״̬�л�ָʾ
    
    wake_mod: int = 0  # �տڻ���ģʽ
    perm_period: int = 0  # �쳣�ϱ�������
    
    sys_fram_period: int = 0  # ϵͳ֡���ڳ���
    burst_time_base: int = 0  # ѯ��ͻ���Զ���ʱ��
    
    sig_det_time: int = 0  # �źż��ʱ�䣬��λ����
    node_sta_det: int = 3  # �ڵ�״̬��������Ĭ��3
    
    un_permit: int = 0  # �쳣�ϱ�����


@dataclass
class NodeAbilityDef:
    """�ڵ����"""
    mac_addr: List[int] = field(default_factory=lambda: [0] * 3)  # MAC��ַ
    ip_addr: List[int] = field(default_factory=lambda: [0] * 4)  # IP��ַ��������
    sig_mod: int = 0  # �����ź�ģʽ��0 ���棬1 ����Ӧ
    data_mod: int = 0  # ���ݰ׻�����
    pps_mod: int = 0  # �ⲿ�ο�
    link_numb: int = 0  # ����֧�ֵ��ⲿ��������
    low_SF: int = 6  # ���SF��6
    high_SF: int = 12  # ���SF��12
    Freq_range: int = 0  # Ƶ����Ӧ��Χ
    max_Pow: int = 0  # ����������
    wake_period: int = 0  # �źŻ�������
    wake_time: int = 0  # �źŻ���ʱ��
    node_ability: int = 0  # �ڵ�����
    Pow_att: int = 0  # �����˥����Χ30dB
    locat_x: int = 0  # �ռ�����x
    locat_y: int = 0  # �ռ�����y
    locat_z: int = 0  # �ռ�����z


# ȫ��ʵ��
local_id = 0  # �����ڵ�ID
sys_para = SysParaDef()  # ϵͳ����
node_para = NodeAbilityDef()  # �ڵ����


@dataclass
class LoraSigDef:
    """�źŲ���"""
    sig_fre: int = 0  # 100Hz
    sig_bw: int = 0  # 0 - 125kHz,1 - 250kHz,2 - 500kHz, 3 - 1MHz
    sig_pow: int = 0  # �������źŹ���
    sig_SF: int = 0  # 6~12
    sig_CR: int = 0  # 0-4/5,1-4/6,2-4/7,3-4/8
    head_mod: int = 0  # 1 to enable head
    CRC_head: int = 0  # ͷ���ݰ�CRC����ʹ��
    CRC_data: int = 0  # ����CRCʹ��
    dat_wit: int = 0  # �źŰ׻�ʹ��
    sig_ldr: int = 0  # ��������ģʽ
    sig_mod: int = 0  # �źŷ�ʽ��1Ϊ�Զ����SF��0Ϊ����
    FPGA_int: int = 0  # 1 FPGAʵ�ֽ�֯����


send_sig_para = LoraSigDef()  # �����źŲ���
recv_sig_para = LoraSigDef()  # �����źŲ���


@dataclass
class LoraSendDef:
    """�������ݲ���"""
    adpt_SF: int = 0  # ����ӦSF
    adpt_CR: int = 0  # ����Ӧ������
    pay_len: int = 0  # ���ݳ���
    sym_len: int = 0  # ���ų���
    head_crc: int = 0  # head data CRC
    send_time_en: int = 0  # ��ʱ����ʹ��
    send_time: int = 0  # ��ʱ����ʱ��
    send_time_stamp: int = 0  # ����ʱ���
    send_dat: List[int] = field(default_factory=lambda: [0] * 256)  # ��������


Lora_send_data = LoraSendDef()  # �������ݲ���


@dataclass
class RecvDatprocDef:
    """�������ݴ���"""
    recv_new: int = 0  # �½�������
    recv_length: int = 0  # ��ǰ������Ϣ����
    recv_time: int = 0  # �����ź�ʱ���
    recv_ok_time: int = 0  # �����ź�ʱ��
    recv_SNR: int = 0  # �����ź������
    recv_dat: List[int] = field(default_factory=lambda: [0] * 256)  # ���ݴ�������


Lora_recv_data = RecvDatprocDef()


# ƽ̨�غɽӿ�
sat_recv_dat = [0] * 256  # ����ƽ̨��������
sat_send_dat = [0] * 256  # ����ƽ̨��������
satint_send_en = 0  # ����ƽ̨���ݷ���ʹ��


@dataclass
class DataDef:
    """���ݶ���"""
    node_data: List[int] = field(default_factory=lambda: [0] * 32)  # �ڵ�״̬����
    node_period: int = 0  # �ڵ�״̬�����ϱ�����
    node_time: int = 0  # ��һ�������ϱ�ʱ��
    
    sat_data: List[int] = field(default_factory=lambda: [0] * 32)  # ��״̬����
    sat_period: int = 0  # ����״̬�����ϱ�����
    sat_time: int = 0  # ��һ�������ϱ�ʱ��
    
    payload_data: List[int] = field(default_factory=lambda: [0] * 32)  # �غ�����
    payload_len: int = 0  # ���ݳ���
    paload_period: int = 0  # �غ�����״̬�����ϱ�����
    paload_time: int = 0  # ��һ�������ϱ�ʱ��
    paload_unnormal: int = 0  # �غ������쳣��ʶ


node_data = DataDef()  # �ڵ����ݲ���

# FPGA����
fpga_opmod = 0  # FPGA�Ĵ�����дģʽ��0 ����1д
fpga_opnum = 0  # FPGA���ݶ�д����

# ���ܽӿ�
netman_send_en = 0  # �������ӿ����ݷ���ʹ��
netman_link_sta = 0  # ��������״̬��0 δ���ӣ�1����
netman_new_dat = 0  # ��������Ҫ��Lora��·����
receive_to_netman = 0  # ����������Ҫ�ش�������

netman_recv_dat = [0] * 1024  # �ӹ���Ԫ��������
netman_send_dat = [0] * 1024  # ���͵�����Ԫ


@dataclass
class NodeOperateDef:
    """�ڵ��������"""
    node_ope_en: int = 0  # �ڵ����ʹ��
    source_id: int = 0  # ѯ��id
    node_opedata: List[int] = field(default_factory=lambda: [0] * 5)  # ������


@dataclass
class MeasDisDef:
    """�����������"""
    node_dis_en: int = 0  # �ڵ�������ʹ��
    des_nod_id: int = 0  # Ŀ�Ľڵ�ID
    node_dis_dat: int = 0  # �ڵ�����������


@dataclass
class NodeAskDef:
    """�ڵ�ѯ�ʶ���"""
    node_ask_en: int = 0  # �ڵ����ʹ��
    source_id: int = 0  # ѯ��id
    node_opedata: int = 0  # ������


@dataclass
class TrafficDataDef:
    """ҵ�����ݶ���"""
    traffic_pack: int = 0
    data_num: int = 0
    traffic_dat: List[int] = field(default_factory=lambda: [0] * 1024)


traffic_data = TrafficDataDef()
distanc_sta = [MeasDisDef() for _ in range(128)]  # �ڵ�������
node_ask_sta = [NodeAskDef() for _ in range(128)]  # �ڵ�ѯ��
node_ope_sta = [NodeOperateDef() for _ in range(128)]  # �ڵ����״̬�洢


@dataclass
class NetnodeTabDef:
    """�����ھ�״̬"""
    node_sta: int = 0  # �ڵ�״̬��0-�����ߣ�1-��������Ӧ��ע�ᣬ2-����������3-Ǳ�� 4-��Ĭ
    node_position: int = 0  # �ڵ����ԣ�0ĸ�ǣ�1���ף�2-����
    cluster_id: int = 0  # �ڵ����ڴ�ID
    mac_addr: List[int] = field(default_factory=lambda: [0] * 3)  # MAC��ַ
    node_ability: int = 0  # �ڵ�����
    freq_rang: int = 0  # Ƶ�ʷ�Χ
    node_pow: int = 0  # �ڵ��źŹ���
    VGA: int = 0
    pos_x: int = 0  # λ��x
    pos_y: int = 0  # λ��y
    pos_z: int = 0  # λ��z
    node_det_num: int = 3  # �ڵ�������������������ʼֵ3
    node_det_tim: int = 0  # �ڵ���ʱ��
    node_SF: int = 0  # SFֵ
    node_healty_sta: int = 0  # �ڵ㽡��״̬


neighbor_node_sta = [NetnodeTabDef() for _ in range(128)]  # ����ڵ�״̬��


@dataclass
class MotherSelectDef:
    """ĸ��ѡ����"""
    netman_link: List[int] = field(default_factory=lambda: [0] * 128)  # �������״̬
    mother_score: List[int] = field(default_factory=lambda: [0] * 128)  # ĸ����Ը����
    local_link: int = 0  # ���ڵ�����������ӵ�״̬


node_mother_sta = MotherSelectDef()

# ʱ����ر���
second_count = 0  # �����ϼ���
sub_sec_count = 0  # �����¼���
mil_sec_count = 0  # �������
sub_sec_offset = 0  # �����²���ƫ��

sys_base_time = 0  # ϵͳʱ���׼
next_base_time = 0  # ��һ��ϵͳʱ��
sys_time_offset = 0  # ʱ��ƫ��

re_enter_time = 0  # �ڵ�����ʱ��

securit_data = 0x12345678  # �̶�ֵ

# =================== FPGA ��ַ���� ===================

FPGA_sys_con_addr = 0x0000
FPGA_sys_ver_addr = 0x0001
FPGA_sys_clk_addr = 0x0002  # system clock
FPGA_sys_sclk_addr = 0x0002  # mdelay time
FPGA_sts_count_addr = 0x0003  # system counter

FPGA_send_base_addr = 0x0200
FPGA_Inte_base_addr = 0x0600
FPGA_send_contr_addr = 0x0000  # ���Ϳ��ƼĴ���
FPGA_send_amp_addr = 0x0001  # �źŷ���
FPGA_send_time_addr = 0x0002  # ����ʱ���
FPGA_send_netid_addr = 0x0003  # ����ID
FPGA_send_waitc_addr = 0x0004  # �ȴ�������
FPGA_send_head_addr = 0x0005  # ��ͷ����
FPGA_send_len_addr = 0x0006  # ���ų��ȼĴ���
FPGA_send_data_addr = 0x0007  # ���ݼĴ���
FPGA_send_sendsta_addr = 0x0008  # ����״̬�Ĵ���

FPGA_recv_base_addr = 0x0400
FPGA_recv_contr_addr = 0x0000  # ���տ��ƼĴ���
FPGA_recv_capt_addr = 0x0000  # ��������
FPGA_recv_netid_addr = 0x0000  # ����ID
FPGA_recv_waitc_addr = 0x0000  # �ȴ�������
FPGA_recv_dlen_addr = 0x0000  # �������ݳ���
FPGA_recv_data_addr = 0x0000  # �������ݼĴ���
FPGA_recv_time_addr = 0x0000  # ����ʱ����Ĵ���


@dataclass
class SendConDef:
    """���Ϳ��ƶ���"""
    poll_ok: int = 0  # ��ǰ�ڵ㡢����ѯ����
    currend_id: int = 0  # ��ǰ��ѯID
    recv_send_en: int = 0  # ����������ҪӦ��
    fram_type: int = 0  # �������ݷ�ʽ��
    time_send_en: int = 0  # ����ʱ϶��ѯʹ��
    unnormal_send_en: int = 0  # �غ������쳣����ʹ��
    netman_send_en: int = 0  # �������ݷ���ʹ��


send_con = SendConDef()  # ���Ϳ���״̬�Ĵ������


@dataclass
class InitDataDef:
    """��ʼ�����ݶ���"""
    node_work_mode: int = 1  # Ĭ��Ϊ����ģʽ
    node_time_mode: int = 0  # �������ⲿʱ��ͬ��
    node_net_pos: int = 2  # ����ڵ�λ��
    net_forward_SF: int = 12  # ��ʼ��ǰ��SF
    net_forward_CR: int = 3  # ��ʼ��ǰ��CR
    net_forward_fre: int = 12000000  # ��ʼ��ǰ��Ƶ�ʣ���λΪ100Hz
    net_backward_SF: int = 12  # ��ʼ������SF
    net_backward_CR: int = 3  # ��ʼ������CR
    net_backward_fre: int = 12000000  # ��ʼ������Ƶ��
    node_sigform: int = 1  # �źŸ�ʽ
    node_CRC_form: int = 0  # ����CRC��ֹ


init_data = InitDataDef()

# ѭ������
i = 0
j = 0
k = 0
temp = 0
temp1 = 0
temp2 = 0
temp3 = 0

poll_cluster_id = 0  # ��ǰ��ѯ��ID
poll_node_id = 0  # ��ǰ��ѯ�ڵ�ID
wait_ack_sta = 0  # �ȴ�Ӧ��״̬
mother_poll_sta = 0  # ĸ����ѯ״̬
cluster_poll_sta = 0  # ������ѯ״̬
multi_send_num = 0  # ��η������ݵĴ�������

work_mod_convert = 0  # ϵͳ�������л�ģʽ


@dataclass
class LoraSigDef2:
    """Lora�źŲ���2"""
    send_CRC_data: int = 0  # ����CRC���̶�Ϊ0
    send_sig_ldr: int = 0  # ������չģʽ���̶�Ϊ0
    send_head_mod: int = 1  # �Ƿ������ͷ���̶�Ϊ1
    send_CRC_head: int = 1  # ͷ����У��ʹ��,�̶�Ϊ1
    send_cont: int = 0  # ��������ʹ��
    send_FPGA_int: int = 0  # FPGA���뽻֯
    
    recv_CRC_data: int = 0  # ����CRC���̶�Ϊ0
    recv_sig_ldr: int = 0  # ������չģʽ���̶�Ϊ0
    recv_head_mod: int = 1  # �Ƿ������ͷ���̶�Ϊ1
    recv_CRC_head: int = 1  # ͷ����У��ʹ��,�̶�Ϊ1
    recv_cont: int = 0  # ����������ʹ��
    recv_agc_en: int = 0  # AGC ʹ��
    recv_FPGA_int: int = 0  # FPGA���뽻֯
    
    FPGA_sendxorrecv: int = 0  # �ź��շ�����
    SFD_ser_num: int = 0  # ����SFD��Ŀ
    
    recv_chan_det: int = 0  # �ŵ�״̬���ʹ��
    dat_white: int = 0  # ���ݰ׻�ʹ��
    inter_syn: int = 0  # �����ź�ͬ��ʹ��
    
    precode_num: int = 0  # ǰ��������
    syn_word0: int = 0  # ͬ����
    syn_word1: int = 0
    
    send_pow: int = 0  # �ź��������
    
    int_sf: int = 0  # �����ź�SF
    int_pow: int = 0  # �����źŹ���
    
    noise_pow: int = 0  # �����źŹ���
    noise_mod: int = 0  # �����ź�ģʽ


Lora_para = LoraSigDef2()

# ��ʼ������
white_data = [0x00] * 256
SF_table = [12,12,12,12,12,11,11,11,11,10,10,10,10,9,9,9,9,9,8,8,8,8,7,7,7,7,6,6,6,6] + [0] * 97  # ���뵽127
to_int_RF_fre = 0  # ʹ��Ƶ�ʳ�ʼ��
to_int_fpga = 0  # ��ʼ��FPGA