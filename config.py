import configparser
import logging
from dataclasses import dataclass, field
from typing import List, Optional
import os
from data_struct import SysParaDef, NodeAbilityDef

# 配置日志
logger = logging.getLogger(__name__)

@dataclass
class NetworkConfig:
    """网络配置"""
    local_ip: str = ""  # 本机IP地址
    gateway_ip: str = ""  # 网关IP地址

@dataclass
class UDPConfig:
    """UDP端口配置"""
    plat_port: int = 8001  # 上位机软件端口
    net_port: int = 8002   # 网关端口
    lora_port: int = 8003  # LoRa端口

# 全局实例
sys_para = SysParaDef()  # 系统参数
node_para = NodeAbilityDef()  # 节点参数
network_config = NetworkConfig()  # 网络配置
udp_config = UDPConfig()  # UDP配置

class ConfigManager:
    """配置文件管理器"""
    
    def __init__(self, config_file: str = "config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        
    def load_config_from_file(self) -> bool:
        """从文件加载配置"""
        try:
            if not os.path.exists(self.config_file):
                logger.error(f"配置文件不存在: {self.config_file}")
                return False
            
            self.config.read(self.config_file, encoding='utf-8')
            logger.info(f"成功读取配置文件: {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"读取配置文件失败: {e}")
            return False
    
    def _safe_get_int(self, section: str, option: str, default: int = 0) -> int:
        """安全获取整数配置值"""
        try:
            return self.config.getint(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
            logger.warning(f"配置项 [{section}].{option} 获取失败，使用默认值 {default}: {e}")
            return default
    
    def _safe_get_float(self, section: str, option: str, default: float = 0.0) -> float:
        """安全获取浮点数配置值"""
        try:
            return self.config.getfloat(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
            logger.warning(f"配置项 [{section}].{option} 获取失败，使用默认值 {default}: {e}")
            return default
    
    def _safe_get_str(self, section: str, option: str, default: str = "") -> str:
        """安全获取字符串配置值"""
        try:
            return self.config.get(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError) as e:
            logger.warning(f"配置项 [{section}].{option} 获取失败，使用默认值 '{default}': {e}")
            return default
    
    def _safe_get_bool(self, section: str, option: str, default: bool = False) -> bool:
        """安全获取布尔配置值"""
        try:
            return self.config.getboolean(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
            logger.warning(f"配置项 [{section}].{option} 获取失败，使用默认值 {default}: {e}")
            return default
    
    def _safe_get_int_list(self, section: str, option: str, size: int, default: int = 0) -> List[int]:
        """安全获取整数列表配置值"""
        try:
            value_str = self.config.get(section, option)
            # 支持多种分隔符：逗号、空格、分号
            values = []
            for sep in [',', ' ', ';']:
                if sep in value_str:
                    values = [int(x.strip()) for x in value_str.split(sep) if x.strip()]
                    break
            else:
                # 如果没有分隔符，尝试按单个值处理
                values = [int(value_str.strip())] if value_str.strip() else []
            
            # 确保列表长度符合要求
            result = [default] * size
            for i, val in enumerate(values[:size]):
                result[i] = val
            
            return result
            
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
            logger.warning(f"配置项 [{section}].{option} 获取失败，使用默认值列表: {e}")
            return [default] * size
    
    def _safe_get_hex_list(self, section: str, option: str, size: int, default: int = 0) -> List[int]:
        """安全获取十六进制列表配置值"""
        try:
            value_str = self.config.get(section, option)
            # 支持多种分隔符：逗号、空格、分号
            values = []
            for sep in [',', ' ', ';']:
                if sep in value_str:
                    values = [int(x.strip(), 16) for x in value_str.split(sep) if x.strip()]
                    break
            else:
                # 如果没有分隔符，尝试按单个值处理
                values = [int(value_str.strip(), 16)] if value_str.strip() else []
            
            # 确保列表长度符合要求
            result = [default] * size
            for i, val in enumerate(values[:size]):
                result[i] = val
            
            return result
            
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError) as e:
            logger.warning(f"配置项 [{section}].{option} 获取失败，使用默认值列表: {e}")
            return [default] * size
    
    def load_network_config(self) -> NetworkConfig:
        """加载网络配置"""
        global network_config
        
        network_config.local_ip = self._safe_get_str('NETWORK', 'local_ip', '127.0.0.1')
        network_config.gateway_ip = self._safe_get_str('NETWORK', 'gateway_ip', '127.0.0.1')
        
        logger.info("网络配置加载完成")
        return network_config
    
    def load_udp_config(self) -> UDPConfig:
        """加载UDP配置"""
        global udp_config
        
        udp_config.plat_port = self._safe_get_int('UDP', 'plat_port', 8001)
        udp_config.net_port = self._safe_get_int('UDP', 'net_port', 8002)
        udp_config.lora_port = self._safe_get_int('UDP', 'lora_port', 8003)
        
        logger.info("UDP配置加载完成")
        return udp_config
    
    def load_system_parameters(self) -> SysParaDef:
        """加载系统参数"""
        global sys_para
        
        # NODE段参数
        sys_para.net_mod = self._safe_get_int('NODE', 'net_mod', 0)
        sys_para.node_mod = self._safe_get_int('NODE', 'node_mod', 0)
        sys_para.node_num = self._safe_get_int('NODE', 'node_num', 0)
        sys_para.net_id = self._safe_get_int('NODE', 'net_id', 0)
        sys_para.max_id = self._safe_get_int('NODE', 'max_id', 0)
        
        # FORWARD_LINK段参数
        sys_para.fre_forw = self._safe_get_int('FORWARD_LINK', 'fre_forw', 0)
        sys_para.bw_forw = self._safe_get_int('FORWARD_LINK', 'bw_forw', 0)
        sys_para.cr_forw = self._safe_get_int('FORWARD_LINK', 'cr_forw', 0)
        sys_para.SF_base_forw = self._safe_get_int('FORWARD_LINK', 'SF_base_forw', 0)
        sys_para.SF_high_forw = self._safe_get_int('FORWARD_LINK', 'SF_high_forw', 0)
        
        # BACKWARD_LINK段参数
        sys_para.fre_backw = self._safe_get_int('BACKWARD_LINK', 'fre_backw', 0)
        sys_para.bw_backw = self._safe_get_int('BACKWARD_LINK', 'bw_backw', 0)
        sys_para.cr_backw = self._safe_get_int('BACKWARD_LINK', 'cr_backw', 0)
        sys_para.SF_base_backw = self._safe_get_int('BACKWARD_LINK', 'SF_base_backw', 0)
        sys_para.SF_high_backw = self._safe_get_int('BACKWARD_LINK', 'SF_high_backw', 0)
        
        # CLUSTER段参数
        sys_para.clust_id = self._safe_get_int('CLUSTER', 'clust_id', 0)
        sys_para.clust_numb = self._safe_get_int('CLUSTER', 'clust_numb', 0)
        sys_para.clust_node_id = self._safe_get_int_list('CLUSTER', 'clust_node_id', 32, 0)
        
        # CLUSTER_FORWARD段参数
        sys_para.clust_fre_forw = self._safe_get_int('CLUSTER_FORWARD', 'clust_fre_forw', 0)
        sys_para.clust_bw_forw = self._safe_get_int('CLUSTER_FORWARD', 'clust_bw_forw', 0)
        sys_para.clust_cr_forw = self._safe_get_int('CLUSTER_FORWARD', 'clust_cr_forw', 0)
        sys_para.clust_SF_base_forw = self._safe_get_int('CLUSTER_FORWARD', 'clust_SF_base_forw', 0)
        
        # CLUSTER_BACKWARD段参数
        sys_para.clust_fre_backw = self._safe_get_int('CLUSTER_BACKWARD', 'clust_fre_backw', 0)
        sys_para.clust_bw_backw = self._safe_get_int('CLUSTER_BACKWARD', 'clust_bw_backw', 0)
        sys_para.clust_cr_backw = self._safe_get_int('CLUSTER_BACKWARD', 'clust_cr_backw', 0)
        sys_para.clust_SF_base_backw = self._safe_get_int('CLUSTER_BACKWARD', 'clust_SF_base_backw', 0)
        
        # SIGNAL段参数
        sys_para.sys_sig_mod = self._safe_get_int('SIGNAL', 'sys_sig_mod', 0)
        sys_para.convert_mod = self._safe_get_int('SIGNAL', 'convert_mod', 0)
        sys_para.wake_mod = self._safe_get_int('SIGNAL', 'wake_mod', 0)
        sys_para.perm_period = self._safe_get_int('SIGNAL', 'perm_period', 0)
        
        # TIMING段参数
        sys_para.sys_fram_period = self._safe_get_int('TIMING', 'sys_fram_period', 0)
        sys_para.burst_time_base = self._safe_get_int('TIMING', 'burst_time_base', 0)
        sys_para.sig_det_time = self._safe_get_int('TIMING', 'sig_det_time', 0)
        sys_para.node_sta_det = self._safe_get_int('TIMING', 'node_sta_det', 3)
        
        logger.info("系统参数加载完成")
        return sys_para
    
    def load_node_parameters(self) -> NodeAbilityDef:
        """加载节点参数"""
        global node_para
        
        # NODE_ABILITY段参数
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
        
        # POSITION段参数
        node_para.locat_x = self._safe_get_int('POSITION', 'locat_x', 0)
        node_para.locat_y = self._safe_get_int('POSITION', 'locat_y', 0)
        node_para.locat_z = self._safe_get_int('POSITION', 'locat_z', 0)
        
        logger.info("节点参数加载完成")
        return node_para

def load_config_from_file(config_file: str = "config.ini") -> bool:
    """
    从配置文件加载所有参数
    
    Args:
        config_file: 配置文件路径
    
    Returns:
        bool: 加载是否成功
    """
    try:
        config_manager = ConfigManager(config_file)
        
        # 加载配置文件
        if not config_manager.load_config_from_file():
            return False
        
        # 加载各类参数
        config_manager.load_network_config()
        config_manager.load_udp_config()
        config_manager.load_system_parameters()
        config_manager.load_node_parameters()
        
        logger.info("所有配置参数加载完成")
        return True
        
    except Exception as e:
        logger.error(f"配置加载过程中发生错误: {e}")
        return False