#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import configparser
import logging
from typing import Dict, Any


class ConfigManager:
    """���ù�����"""
    
    def __init__(self, config_file: str = 'config.ini'):
        self.config = configparser.ConfigParser()
        self.config_file = config_file
        self.load_config()
    
    def load_config(self):
        """���������ļ�"""
        try:
            self.config.read(self.config_file, encoding='utf-8')
        except Exception as e:
            logging.error(f"���������ļ�ʧ��: {e}")
            # ʹ��Ĭ������
            self._create_default_config()
    
    def _create_default_config(self):
        """����Ĭ������"""
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
            'mother_id': '0',  # ĸ��ID�̶�Ϊ0
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
        """��ȡ�˿ں�"""
        return self.config.getint('UDP_PORTS', port_name)
    
    def get_bind_ip(self) -> str:
        """��ȡ��IP"""
        return self.config.get('NETWORK', 'bind_ip')
    
    def get_node_config(self) -> Dict[str, Any]:
        """��ȡ�ڵ�����"""
        return {
            'node_type': self.config.get('NODE_CONFIG', 'node_type'),
            'local_id': self.config.getint('NODE_CONFIG', 'local_id'),
            'network_id': self.config.getint('NODE_CONFIG', 'network_id'),
            'mother_id': self.config.getint('NODE_CONFIG', 'mother_id'),
            'gateway_id': self.config.getint('NODE_CONFIG', 'gateway_id'),
            'cluster_id': self.config.getint('NODE_CONFIG', 'cluster_id')
        }
    
    def get_lora_params(self) -> Dict[str, Any]:
        """��ȡLoRa����"""
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
        """��ȡʱ�����"""
        return {
            'node_status_period': self.config.getint('TIMING', 'node_status_period'),
            'satellite_status_period': self.config.getint('TIMING', 'satellite_status_period'),
            'payload_period': self.config.getint('TIMING', 'payload_period'),
            'system_frame_period': self.config.getint('TIMING', 'system_frame_period')
        }
    
    def save_config(self):
        """�������õ��ļ�"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            logging.info(f"�����ѱ��浽 {self.config_file}")
        except Exception as e:
            logging.error(f"���������ļ�ʧ��: {e}")
    
    def update_node_config(self, **kwargs):
        """���½ڵ�����"""
        for key, value in kwargs.items():
            if key in ['local_id', 'network_id', 'mother_id', 'gateway_id', 'cluster_id']:
                self.config.set('NODE_CONFIG', key, str(value))
            elif key == 'node_type':
                self.config.set('NODE_CONFIG', key, value)
        logging.info(f"�ڵ������Ѹ���: {kwargs}")
    
    def setup_logging(self):
        """������־ϵͳ"""
        log_level = getattr(logging, self.config.get('LOGGING', 'log_level', fallback='INFO'))
        log_file = self.config.get('LOGGING', 'log_file', fallback='backend.log')
        
        # ������е�handlers
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        
        # �����µ���־ϵͳ
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        logging.info(f"��־ϵͳ�ѳ�ʼ��������: {self.config.get('LOGGING', 'log_level')}")