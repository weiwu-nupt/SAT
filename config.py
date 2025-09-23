import configparser
import logging
from dataclasses import dataclass, field
from typing import List, Optional
import os
from data_struct import SysParaDef, NodeAbilityDef

# ������־
logger = logging.getLogger(__name__)

@dataclass
class NetworkConfig:
    """��������"""
    local_ip: str = ""  # ����IP��ַ
    gateway_ip: str = ""  # ����IP��ַ

@dataclass
class UDPConfig:
    """UDP�˿�����"""
    plat_port: int = 8001  # ��λ������˿�
    net_port: int = 8002   # ���ض˿�
    lora_port: int = 8003  # LoRa�˿�

# ȫ��ʵ��
sys_para = SysParaDef()  # ϵͳ����
node_para = NodeAbilityDef()  # �ڵ����
network_config = NetworkConfig()  # ��������
udp_config = UDPConfig()  # UDP����

class ConfigManager:
    """�����ļ�������"""
    
    def __init__(self, config_file: str = "config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        
    def load_config_from_file(self) -> bool:
        """���ļ���������"""
        try:
            if not os.path.exists(self.config_file):
                logger.error(f"�����ļ�������: {self.config_file}")
                return False
            
            self.config.read(self.config_file, encoding='utf-8')
            logger.info(f"�ɹ���ȡ�����ļ�: {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"��ȡ�����ļ�ʧ��: {e}")
            return False
    
    def _safe_get_int(self, section: str, option: str, default: int = 0) -> int:
        """��ȫ��ȡ��������ֵ"""
        try:
            return self.config.getint(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
            logger.warning(f"������ [{section}].{option} ��ȡʧ�ܣ�ʹ��Ĭ��ֵ {default}: {e}")
            return default
    
    def _safe_get_float(self, section: str, option: str, default: float = 0.0) -> float:
        """��ȫ��ȡ����������ֵ"""
        try:
            return self.config.getfloat(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
            logger.warning(f"������ [{section}].{option} ��ȡʧ�ܣ�ʹ��Ĭ��ֵ {default}: {e}")
            return default
    
    def _safe_get_str(self, section: str, option: str, default: str = "") -> str:
        """��ȫ��ȡ�ַ�������ֵ"""
        try:
            return self.config.get(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError) as e:
            logger.warning(f"������ [{section}].{option} ��ȡʧ�ܣ�ʹ��Ĭ��ֵ '{default}': {e}")
            return default
    
    def _safe_get_bool(self, section: str, option: str, default: bool = False) -> bool:
        """��ȫ��ȡ��������ֵ"""
        try:
            return self.config.getboolean(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
            logger.warning(f"������ [{section}].{option} ��ȡʧ�ܣ�ʹ��Ĭ��ֵ {default}: {e}")
            return default
    
    def _safe_get_int_list(self, section: str, option: str, size: int, default: int = 0) -> List[int]:
        """��ȫ��ȡ�����б�����ֵ"""
        try:
            value_str = self.config.get(section, option)
            # ֧�ֶ��ַָ��������š��ո񡢷ֺ�
            values = []
            for sep in [',', ' ', ';']:
                if sep in value_str:
                    values = [int(x.strip()) for x in value_str.split(sep) if x.strip()]
                    break
            else:
                # ���û�зָ��������԰�����ֵ����
                values = [int(value_str.strip())] if value_str.strip() else []
            
            # ȷ���б��ȷ���Ҫ��
            result = [default] * size
            for i, val in enumerate(values[:size]):
                result[i] = val
            
            return result
            
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
            logger.warning(f"������ [{section}].{option} ��ȡʧ�ܣ�ʹ��Ĭ��ֵ�б�: {e}")
            return [default] * size
    
    def _safe_get_hex_list(self, section: str, option: str, size: int, default: int = 0) -> List[int]:
        """��ȫ��ȡʮ�������б�����ֵ"""
        try:
            value_str = self.config.get(section, option)
            # ֧�ֶ��ַָ��������š��ո񡢷ֺ�
            values = []
            for sep in [',', ' ', ';']:
                if sep in value_str:
                    values = [int(x.strip(), 16) for x in value_str.split(sep) if x.strip()]
                    break
            else:
                # ���û�зָ��������԰�����ֵ����
                values = [int(value_str.strip(), 16)] if value_str.strip() else []
            
            # ȷ���б��ȷ���Ҫ��
            result = [default] * size
            for i, val in enumerate(values[:size]):
                result[i] = val
            
            return result
            
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
            logger.warning(f"������ [{section}].{option} ��ȡʧ�ܣ�ʹ��Ĭ��ֵ�б�: {e}")
            return [default] * size
    
    def load_network_config(self) -> NetworkConfig:
        """������������"""
        global network_config
        
        network_config.local_ip = self._safe_get_str('NETWORK', 'local_ip', '127.0.0.1')
        network_config.gateway_ip = self._safe_get_str('NETWORK', 'gateway_ip', '127.0.0.1')
        
        logger.info("�������ü������")
        return network_config
    
    def load_udp_config(self) -> UDPConfig:
        """����UDP����"""
        global udp_config
        
        udp_config.plat_port = self._safe_get_int('UDP', 'plat_port', 8001)
        udp_config.net_port = self._safe_get_int('UDP', 'net_port', 8002)
        udp_config.lora_port = self._safe_get_int('UDP', 'lora_port', 8003)
        
        logger.info("UDP���ü������")
        return udp_config
    
    def load_system_parameters(self) -> SysParaDef:
        """����ϵͳ����"""
        global sys_para
        
        # NODE�β���
        sys_para.net_mod = self._safe_get_int('NODE', 'net_mod', 0)
        sys_para.node_mod = self._safe_get_int('NODE', 'node_mod', 0)
        sys_para.node_num = self._safe_get_int('NODE', 'node_num', 0)
        sys_para.net_id = self._safe_get_int('NODE', 'net_id', 0)
        sys_para.max_id = self._safe_get_int('NODE', 'max_id', 0)
        
        # FORWARD_LINK�β���
        sys_para.fre_forw = self._safe_get_int('FORWARD_LINK', 'fre_forw', 0)
        sys_para.bw_forw = self._safe_get_int('FORWARD_LINK', 'bw_forw', 0)
        sys_para.cr_forw = self._safe_get_int('FORWARD_LINK', 'cr_forw', 0)
        sys_para.SF_base_forw = self._safe_get_int('FORWARD_LINK', 'SF_base_forw', 0)
        sys_para.SF_high_forw = self._safe_get_int('FORWARD_LINK', 'SF_high_forw', 0)
        
        # BACKWARD_LINK�β���
        sys_para.fre_backw = self._safe_get_int('BACKWARD_LINK', 'fre_backw', 0)
        sys_para.bw_backw = self._safe_get_int('BACKWARD_LINK', 'bw_backw', 0)
        sys_para.cr_backw = self._safe_get_int('BACKWARD_LINK', 'cr_backw', 0)
        sys_para.SF_base_backw = self._safe_get_int('BACKWARD_LINK', 'SF_base_backw', 0)
        sys_para.SF_high_backw = self._safe_get_int('BACKWARD_LINK', 'SF_high_backw', 0)
        
        # CLUSTER�β���
        sys_para.clust_id = self._safe_get_int('CLUSTER', 'clust_id', 0)
        sys_para.clust_numb = self._safe_get_int('CLUSTER', 'clust_numb', 0)
        sys_para.clust_node_id = self._safe_get_int_list('CLUSTER', 'clust_node_id', 32, 0)
        
        # CLUSTER_FORWARD�β���
        sys_para.clust_fre_forw = self._safe_get_int('CLUSTER_FORWARD', 'clust_fre_forw', 0)
        sys_para.clust_bw_forw = self._safe_get_int('CLUSTER_FORWARD', 'clust_bw_forw', 0)
        sys_para.clust_cr_forw = self._safe_get_int('CLUSTER_FORWARD', 'clust_cr_forw', 0)
        sys_para.clust_SF_base_forw = self._safe_get_int('CLUSTER_FORWARD', 'clust_SF_base_forw', 0)
        
        # CLUSTER_BACKWARD�β���
        sys_para.clust_fre_backw = self._safe_get_int('CLUSTER_BACKWARD', 'clust_fre_backw', 0)
        sys_para.clust_bw_backw = self._safe_get_int('CLUSTER_BACKWARD', 'clust_bw_backw', 0)
        sys_para.clust_cr_backw = self._safe_get_int('CLUSTER_BACKWARD', 'clust_cr_backw', 0)
        sys_para.clust_SF_base_backw = self._safe_get_int('CLUSTER_BACKWARD', 'clust_SF_base_backw', 0)
        
        # SIGNAL�β���
        sys_para.sys_sig_mod = self._safe_get_int('SIGNAL', 'sys_sig_mod', 0)
        sys_para.convert_mod = self._safe_get_int('SIGNAL', 'convert_mod', 0)
        sys_para.wake_mod = self._safe_get_int('SIGNAL', 'wake_mod', 0)
        sys_para.perm_period = self._safe_get_int('SIGNAL', 'perm_period', 0)
        
        # TIMING�β���
        sys_para.sys_fram_period = self._safe_get_int('TIMING', 'sys_fram_period', 0)
        sys_para.burst_time_base = self._safe_get_int('TIMING', 'burst_time_base', 0)
        sys_para.sig_det_time = self._safe_get_int('TIMING', 'sig_det_time', 0)
        sys_para.node_sta_det = self._safe_get_int('TIMING', 'node_sta_det', 3)
        
        logger.info("ϵͳ�����������")
        return sys_para
    
    def load_node_parameters(self) -> NodeAbilityDef:
        """���ؽڵ����"""
        global node_para
        
        # NODE_ABILITY�β���
        node_para.mac_addr = self._safe_get_hex_list('NODE_ABILITY', 'mac_addr', 3, 0)
        node_para.sig_mod = self._safe_get_int('NODE_ABILITY', 'sig_mod', 0)
        node_para.data_mod = self._safe_get_int('NODE_ABILITY', 'data_mod', 0)
        node_para.pps_mod = self._safe_get_int('NODE_ABILITY', 'pps_mod', 0)
        node_para.link_numb = self._safe_get_int('NODE_ABILITY', 'link_numb', 0)
        node_para.low_SF = self._safe_get_int('NODE_ABILITY', 'low_SF', 6)
        node_para.high_SF = self._safe_get_int('NODE_ABILITY', 'high_SF', 12)
        node_para.Freq_range = self._safe_get_int('NODE_ABILITY', 'Freq_range', 0)
        node_para.max_Pow = self._safe_get_int('NODE_ABILITY', 'max_Pow', 0)
        node_para.wake_period = self._safe_get_int('NODE_ABILITY', 'wake_period', 0)
        node_para.wake_time = self._safe_get_int('NODE_ABILITY', 'wake_time', 0)
        node_para.node_ability = self._safe_get_int('NODE_ABILITY', 'node_ability', 0)
        node_para.Pow_att = self._safe_get_int('NODE_ABILITY', 'Pow_att', 0)
        
        # POSITION�β���
        node_para.locat_x = self._safe_get_int('POSITION', 'locat_x', 0)
        node_para.locat_y = self._safe_get_int('POSITION', 'locat_y', 0)
        node_para.locat_z = self._safe_get_int('POSITION', 'locat_z', 0)
        
        logger.info("�ڵ�����������")
        return node_para

def load_config_from_file(config_file: str = "config.ini") -> bool:
    """
    �������ļ��������в���
    
    Args:
        config_file: �����ļ�·��
    
    Returns:
        bool: �����Ƿ�ɹ�
    """
    try:
        config_manager = ConfigManager(config_file)
        
        # ���������ļ�
        if not config_manager.load_config_from_file():
            return False
        
        # ���ظ������
        config_manager.load_network_config()
        config_manager.load_udp_config()
        config_manager.load_system_parameters()
        config_manager.load_node_parameters()
        
        logger.info("�������ò����������")
        return True
        
    except Exception as e:
        logger.error(f"���ü��ع����з�������: {e}")
        return False