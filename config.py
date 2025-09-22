#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import configparser
import logging
from typing import Dict, Any


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: str = 'config.ini'):
        self.config = configparser.ConfigParser()
        self.config_file = config_file
        self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        try:
            self.config.read(self.config_file, encoding='utf-8')
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            # 使用默认配置
            self._create_default_config()
    
    def _create_default_config(self):
        """创建默认配置"""
        self.config['UDP_PORTS'] = {
            'host_software_port': '8001',
            'gateway_port': '8002',
            'lora_port': '8003'
        }
        self.config['NETWORK'] = {
            'bind_ip': '0.0.0.0'
        }
        self.config['LOGGING'] = {
            'log_level': 'INFO',
            'log_file': 'backend.log'
        }
        self.config['NODE_CONFIG'] = {
            'node_type': 'normal',
            'local_id': '16',
            'network_id': '1',
            'mother_id': '0',  # 母星ID固定为0
            'gateway_id': '254',
            'cluster_id': '128'
        }
        self.config['LORA_PARAMS'] = {
            'forward_frequency': '12000000',
            'backward_frequency': '12000000',
            'forward_sf': '12',
            'backward_sf': '12',
            'forward_cr': '3',
            'backward_cr': '3',
            'bandwidth': '0',
            'power_level': '14'
        }
        self.config['TIMING'] = {
            'node_status_period': '60',
            'satellite_status_period': '300',
            'payload_period': '120',
            'system_frame_period': '1000'
        }
    
    def get_port(self, port_name: str) -> int:
        """获取端口号"""
        return self.config.getint('UDP_PORTS', port_name)
    
    def get_bind_ip(self) -> str:
        """获取绑定IP"""
        return self.config.get('NETWORK', 'bind_ip')
    
    def get_node_config(self) -> Dict[str, Any]:
        """获取节点配置"""
        return {
            'node_type': self.config.get('NODE_CONFIG', 'node_type'),
            'local_id': self.config.getint('NODE_CONFIG', 'local_id'),
            'network_id': self.config.getint('NODE_CONFIG', 'network_id'),
            'mother_id': self.config.getint('NODE_CONFIG', 'mother_id'),
            'gateway_id': self.config.getint('NODE_CONFIG', 'gateway_id'),
            'cluster_id': self.config.getint('NODE_CONFIG', 'cluster_id')
        }
    
    def get_lora_params(self) -> Dict[str, Any]:
        """获取LoRa参数"""
        return {
            'forward_frequency': self.config.getint('LORA_PARAMS', 'forward_frequency'),
            'backward_frequency': self.config.getint('LORA_PARAMS', 'backward_frequency'),
            'forward_sf': self.config.getint('LORA_PARAMS', 'forward_sf'),
            'backward_sf': self.config.getint('LORA_PARAMS', 'backward_sf'),
            'forward_cr': self.config.getint('LORA_PARAMS', 'forward_cr'),
            'backward_cr': self.config.getint('LORA_PARAMS', 'backward_cr'),
            'bandwidth': self.config.getint('LORA_PARAMS', 'bandwidth'),
            'power_level': self.config.getint('LORA_PARAMS', 'power_level')
        }
    
    def get_timing_params(self) -> Dict[str, Any]:
        """获取时序参数"""
        return {
            'node_status_period': self.config.getint('TIMING', 'node_status_period'),
            'satellite_status_period': self.config.getint('TIMING', 'satellite_status_period'),
            'payload_period': self.config.getint('TIMING', 'payload_period'),
            'system_frame_period': self.config.getint('TIMING', 'system_frame_period')
        }
    
    def save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            logging.info(f"配置已保存到 {self.config_file}")
        except Exception as e:
            logging.error(f"保存配置文件失败: {e}")
    
    def update_node_config(self, **kwargs):
        """更新节点配置"""
        for key, value in kwargs.items():
            if key in ['local_id', 'network_id', 'mother_id', 'gateway_id', 'cluster_id']:
                self.config.set('NODE_CONFIG', key, str(value))
            elif key == 'node_type':
                self.config.set('NODE_CONFIG', key, value)
        logging.info(f"节点配置已更新: {kwargs}")
    
    def setup_logging(self):
        """设置日志系统"""
        log_level = getattr(logging, self.config.get('LOGGING', 'log_level', fallback='INFO'))
        log_file = self.config.get('LOGGING', 'log_file', fallback='backend.log')
        
        # 清除现有的handlers
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        
        # 配置新的日志系统
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        logging.info(f"日志系统已初始化，级别: {self.config.get('LOGGING', 'log_level')}")