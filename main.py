#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import queue
import threading
import logging
import signal
import sys
from typing import Dict, Any

from config import ConfigManager
from protocol import MessageSource
from udp_server import UDPServer
from message_processor import MessageProcessor


class BackendServer:
    """后台服务器主类"""
    
    def __init__(self, config_file: str = 'config.ini'):
        self.config_manager = ConfigManager(config_file)
        self.message_queue = queue.Queue(maxsize=1000)  # 设置队列最大大小
        self.servers = {}
        self.message_processor = MessageProcessor(self.message_queue)
        self.running = False
        
        # 设置日志
        self.config_manager.setup_logging()
        
        # 从配置文件初始化节点
        self._init_node_from_config()
        
        # 设置信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        logging.info(f"收到信号 {signum}，准备关闭服务器...")
        self.stop()
        sys.exit(0)
        
    def _init_node_from_config(self):
        """从配置文件初始化节点"""
        try:
            # 获取节点配置
            node_config = self.config_manager.get_node_config()
            lora_params = self.config_manager.get_lora_params()
            timing_params = self.config_manager.get_timing_params()
            
            # 设置节点类型
            node_type = node_config['node_type']
            self.message_processor.set_node_type(node_type)
            
            # 配置LoRa处理器
            lora_processor = self.message_processor.lora_processor
            
            # 基本配置
            lora_processor.local_id = node_config['local_id']
            lora_processor.sys_para.update({
                'net_id': node_config['network_id'],
                'mother_id': node_config['mother_id'],
                'gateway_id': node_config['gateway_id'],
                'clust_id': node_config['cluster_id']
            })
            
            # LoRa参数配置
            lora_processor.send_sig_para = {
                'sig_fre': lora_params['forward_frequency'],
                'sig_SF': lora_params['forward_sf'],
                'sig_CR': lora_params['forward_cr'],
                'sig_bw': lora_params['bandwidth'],
                'sig_pow': lora_params['power_level']
            }
            
            lora_processor.recv_sig_para = {
                'sig_fre': lora_params['backward_frequency'],
                'sig_SF': lora_params['backward_sf'],
                'sig_CR': lora_params['backward_cr'],
                'sig_bw': lora_params['bandwidth']
            }
            
            # 时序参数配置
            lora_processor.node_data.update({
                'node_period': timing_params['node_status_period'],
                'sat_period': timing_params['satellite_status_period'],
                'paload_period': timing_params['payload_period']
            })
            
            logging.info(f"节点初始化完成: 类型={node_type}, ID={node_config['local_id']}")
            
        except Exception as e:
            logging.error(f"节点初始化失败: {e}")
            raise
    
    def start(self):
        """启动后台服务器"""
        if self.running:
            logging.warning("服务器已经在运行中")
            return
            
        try:
            bind_ip = self.config_manager.get_bind_ip()
            
            # 创建并启动UDP服务器
            server_configs = [
                ('host_software_port', MessageSource.HOST_SOFTWARE),
                ('gateway_port', MessageSource.GATEWAY),
                ('lora_port', MessageSource.LORA)
            ]
            
            for port_name, source in server_configs:
                port = self.config_manager.get_port(port_name)
                server = UDPServer(port, source, self.message_queue, bind_ip)
                server.start()
                self.servers[source] = server
            
            # 设置消息处理器的UDP服务器引用
            self.message_processor.set_udp_servers(self.servers)
            
            # 启动消息处理器
            self.message_processor.start()
            
            self.running = True
            
            # 打印启动信息
            node_config = self.config_manager.get_node_config()
            logging.info("=" * 60)
            logging.info("UDP后台服务器启动成功")
            logging.info("=" * 60)
            logging.info(f"节点类型: {node_config['node_type']}")
            logging.info(f"节点ID: {node_config['local_id']}")
            logging.info(f"母星ID: {node_config['mother_id']}")
            logging.info(f"网关ID: {node_config['gateway_id']}")
            logging.info("消息格式: [类型(1字节)][长度(1字节)][内容][CRC(2字节)]")
            logging.info("=" * 60)
            logging.info("端口监听:")
            for source, server in self.servers.items():
                logging.info(f"  {source.value}: {server.get_local_address()}")
            logging.info("=" * 60)
            
        except Exception as e:
            logging.error(f"启动后台服务器失败: {e}")
            self.stop()
            raise
    
    def stop(self):
        """停止后台服务器"""
        if not self.running:
            return
            
        logging.info("正在停止后台服务器...")
        self.running = False
        
        # 停止所有UDP服务器
        for server in self.servers.values():
            server.stop()
        
        # 停止消息处理器
        self.message_processor.stop()
        
        logging.info("后台服务器已停止")
    
    def get_queue_size(self) -> int:
        """获取当前队列大小"""
        return self.message_queue.qsize()
    
    def get_node_status(self) -> Dict[str, Any]:
        """获取节点状态"""
        lora_processor = self.message_processor.lora_processor
        return {
            'local_id': lora_processor.local_id,
            'node_type': lora_processor.sys_para['node_mod'],
            'link_status': lora_processor.link_sta,
            'mother_id': lora_processor.sys_para['mother_id'],
            'network_mode': lora_processor.sys_para['net_mod'],
            'queue_size': self.get_queue_size(),
            'servers_status': {source.value: server.is_running() for source, server in self.servers.items()}
        }
    
    def set_node_mode(self, mode: int):
        """设置节点网络模式"""
        self.message_processor.lora_processor.sys_para['net_mod'] = mode
        logging.info(f"设置网络模式为: {mode}")
    
    def trigger_network_join(self):
        """触发入网流程"""
        self.message_processor.lora_processor.link_sta = 1
        logging.info("触发节点入网流程")
    
    def run_forever(self):
        """运行服务器直到手动停止"""
        try:
            self.start()
            
            # 主循环
            while self.running:
                try:
                    # 监控系统状态
                    queue_size = self.get_queue_size()
                    if queue_size > 800:  # 队列接近满载时告警
                        logging.warning(f"消息队列接近满载: {queue_size}/1000")
                    
                    # 检查服务器状态
                    for source, server in self.servers.items():
                        if not server.is_running():
                            logging.error(f"{source.value} 服务器已停止运行")
                    
                    # 每5秒检查一次
                    threading.Event().wait(5)
                    
                except KeyboardInterrupt:
                    logging.info("收到停止信号")
                    break
                    
        except Exception as e:
            logging.error(f"程序运行出错: {e}")
        finally:
            self.stop()


def print_usage():
    """打印使用说明"""
    print("""
UDP LoRa 后台服务器
==================

使用方法:
    python main.py [配置文件]

参数:
    配置文件    可选，默认为 config.ini

功能说明:
    - 监听3个UDP端口：上位机软件、网关、LoRa
    - 支持标准消息格式：[类型][长度][内容][CRC]
    - 支持LoRa组网协议：测距、注册、轮询等
    - 支持母星、簇首、普通节点三种模式

配置文件示例:
    [NODE_CONFIG]
    node_type = mother    # 节点类型：mother/cluster/normal
    local_id = 0         # 本地ID（母星为0）
    
按 Ctrl+C 停止服务器
""")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='UDP LoRa 后台服务器')
    parser.add_argument('config', nargs='?', default='config.ini', 
                       help='配置文件路径 (默认: config.ini)')
    parser.add_argument('--help-usage', action='store_true', 
                       help='显示详细使用说明')
    
    args = parser.parse_args()
    
    if args.help_usage:
        print_usage()
        return
    
    server = None
    try:
        # 创建并运行服务器
        server = BackendServer(args.config)
        server.run_forever()
        
    except FileNotFoundError:
        print(f"错误: 配置文件 '{args.config}' 不存在")
        print("请创建配置文件或使用 --help-usage 查看说明")
    except Exception as e:
        print(f"启动失败: {e}")
        if server:
            server.stop()


if __name__ == "__main__":
    main()