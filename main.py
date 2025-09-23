import socket
import struct
import threading
import queue
import time
from typing import NamedTuple, Optional, Tuple
from enum import Enum
import logging
from util import calculate_crc16

# 导入配置模块
from config import (
    load_config_from_file, 
    sys_para, 
    node_para, 
    network_config, 
    udp_config
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MessageSource(Enum):
    """消息来源枚举"""
    PLATE = "plate"
    NET = "net" 
    LORA = "lora"

class ParsedMessage(NamedTuple):
    """解析后的消息结构"""
    source: MessageSource
    message_type: int
    length: int
    raw_data: bytes
    client_address: Tuple[str, int]

class MessageQueue:
    """线程安全的消息队列"""
    def __init__(self, maxsize: int = 4096):
        self._queue = queue.Queue(maxsize=maxsize)
    
    def put(self, message: ParsedMessage, block: bool = True, timeout: Optional[float] = None):
        """添加消息到队列"""
        try:
            self._queue.put(message, block=block, timeout=timeout)
            logger.debug(f"消息已加入队列: {message.source.value}")
        except queue.Full:
            logger.error(f"消息队列已满，丢弃来自 {message.source.value} 的消息")
    
    def get(self, block: bool = True, timeout: Optional[float] = None) -> ParsedMessage:
        """从队列获取消息"""
        return self._queue.get(block=block, timeout=timeout)
    
    def qsize(self) -> int:
        """获取队列大小"""
        return self._queue.qsize()
    
    def empty(self) -> bool:
        """检查队列是否为空"""
        return self._queue.empty()

class MessageParser:
    """消息解析器"""
    
    PLATE_SYNC_HEADER = 0x1ACFFC1D  # 4字节帧同步头
    
    @classmethod
    def parse_plate_message(cls, data: bytes, client_addr: Tuple[str, int]) -> Optional[ParsedMessage]:
        """解析plate消息"""
        if len(data) < 4:
            logger.warning(f"Plate消息长度不足4字节: {len(data)}")
            return None
        
        # 检查帧同步头
        sync_header = struct.unpack('>I', data[:4])[0]  # 大端序解析4字节
        if sync_header != cls.PLATE_SYNC_HEADER:
            logger.warning(f"Plate消息帧同步头错误: 0x{sync_header:08X}")
            return None
        
        data = data[4:]  # 去掉帧同步头的内容

        message_type = data[0]
        message_length = data[1]

        # 验证消息长度
        expected_total_length = message_length + 4  # 消息内容 + 类型(1) + 长度(1) + CRC(2)
        if len(data) != expected_total_length:
            logger.warning(f"Plate消息长度不匹配: 期望{expected_total_length}, 实际{len(data)}")
            return None

        # 提取消息内容和CRC
        content = data[2:2+message_length] if message_length > 0 else b''
        crc_bytes = data[-2:]
        received_crc = struct.unpack('>H', crc_bytes)[0]  # 大端序解析CRC
        
        # 验证CRC（对消息类型、长度、内容进行校验）
        check_data = data[:-2]  # 除了CRC的所有数据
        calculated_crc = calculate_crc16(check_data)
        
        if received_crc != calculated_crc:
            logger.warning(f"Plate消息CRC校验失败: 接收0x{received_crc:04X}, 计算0x{calculated_crc:04X}")
            return None
        
        return ParsedMessage(
            source=MessageSource.PLATE,
            message_type=message_type,
            length=message_length,
            raw_data=data,
            client_address=client_addr
        )
    
    @classmethod
    def parse_net_lora_message(cls, data: bytes, source: MessageSource, 
                              client_addr: Tuple[str, int]) -> Optional[ParsedMessage]:
        """解析NET/LORA消息"""
        if len(data) < 4:  # 最小长度：消息类型(1) + 长度(1) + CRC(2)
            logger.warning(f"{source.value}消息长度不足4字节: {len(data)}")
            return None
        
        # 解析消息头
        message_type = data[0]
        message_length = data[1]
        
        # 验证消息长度
        expected_total_length = message_length + 4  # 消息内容 + 类型(1) + 长度(1) + CRC(2)
        if len(data) != expected_total_length:
            logger.warning(f"{source.value}消息长度不匹配: 期望{expected_total_length}, 实际{len(data)}")
            return None
        
        # 提取消息内容和CRC
        content = data[2:2+message_length] if message_length > 0 else b''
        crc_bytes = data[-2:]
        received_crc = struct.unpack('>H', crc_bytes)[0]  # 大端序解析CRC
        
        # 验证CRC（对消息类型、长度、内容进行校验）
        check_data = data[:-2]  # 除了CRC的所有数据
        calculated_crc = calculate_crc16(check_data)
        
        if received_crc != calculated_crc:
            logger.warning(f"{source.value}消息CRC校验失败: 接收0x{received_crc:04X}, 计算0x{calculated_crc:04X}")
            return None
        
        return ParsedMessage(
            source=source,
            message_type=message_type,
            length=message_length,
            raw_data=data,
            client_address=client_addr
        )

class UDPServer:
    """UDP服务器"""
    
    def __init__(self, host: str = None):
        # 使用配置文件中的IP地址，如果没有则使用默认值
        self.host = host if host else (network_config.local_ip if network_config.local_ip else 'localhost')
        
        self.message_queue = MessageQueue(maxsize=4096)
        
        self.running = False
        self.sockets = {}
        self.threads = []
        
        # 从配置文件读取端口配置
        self.ports = {
            MessageSource.PLATE: udp_config.plat_port,
            MessageSource.NET: udp_config.net_port,
            MessageSource.LORA: udp_config.lora_port
        }

        # 创建发送套接字
        self.send_socket = None

    def create_socket(self, port: int) -> socket.socket:
        """创建UDP套接字"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, port))
        return sock
    
    def handle_client(self, source: MessageSource):
        """处理特定端口的客户端连接"""
        port = self.ports[source]
        sock = self.create_socket(port)
        self.sockets[source] = sock
        
        logger.info(f"{source.value}服务器启动，监听端口 {port}")
        
        # 设置接收缓冲区大小
        buffer_size = 4096
        
        while self.running:
            try:
                # 设置超时以便定期检查running状态
                sock.settimeout(1.0)
                data, client_addr = sock.recvfrom(buffer_size)
                
                logger.debug(f"收到来自 {source.value} 的数据: {len(data)} 字节，客户端: {client_addr}")
                
                # 解析消息
                if source == MessageSource.PLATE:
                    message = MessageParser.parse_plate_message(data, client_addr)
                else:
                    message = MessageParser.parse_net_lora_message(data, source, client_addr)
                
                # 将解析后的消息放入队列
                if message:
                    self.message_queue.put(message, block=False)
                    logger.info(f"成功解析并入队 {source.value} 消息")
                
            except socket.timeout:
                continue  # 超时继续循环检查running状态
            except Exception as e:
                if self.running:  # 只在运行状态下记录错误
                    logger.error(f"{source.value}服务器处理错误: {e}")
        
        sock.close()
        logger.info(f"{source.value}服务器已关闭")
    
    def start(self):
        """启动服务器"""
        if self.running:
            logger.warning("服务器已经在运行")
            return
        
        self.running = True
        logger.info("正在启动UDP服务器...")

        # 创建发送套接字
        self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.send_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # 为每个端口创建处理线程
        for source in MessageSource:
            thread = threading.Thread(
                target=self.handle_client, 
                args=(source,),
                name=f"UDP-{source.value}",
                daemon=True
            )
            thread.start()
            self.threads.append(thread)
        
        logger.info("所有UDP服务器已启动")
    
    def stop(self):
        """停止服务器"""
        if not self.running:
            logger.warning("服务器未在运行")
            return
        
        logger.info("正在停止UDP服务器...")
        self.running = False
        
        # 等待所有线程结束
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=2.0)
        
        # 关闭套接字
        for sock in self.sockets.values():
            sock.close()

        # 关闭发送套接字
        if self.send_socket:
            self.send_socket.close()
            self.send_socket = None
        
        self.threads.clear()
        self.sockets.clear()
        logger.info("UDP服务器已停止")
    
    def get_message(self, timeout: Optional[float] = None) -> Optional[ParsedMessage]:
        """获取队列中的消息"""
        try:
            return self.message_queue.get(block=True, timeout=timeout)
        except queue.Empty:
            return None
    
    def send_plate_message(self, content: bytes, target_ip: str, target_port: int = None) -> bool:
        """发送Plate消息（带帧同步头）"""
        if not self.send_socket:
            logger.error("发送套接字未初始化")
            return False
        
        try:
            # 添加帧同步头
            sync_header = struct.pack('>I', MessageParser.PLATE_SYNC_HEADER)
            message = sync_header + content

             # 计算CRC
            crc = calculate_crc16(content)
            
            # 添加CRC：消息 + CRC(2)
            full_message = message + struct.pack('>H', crc)
            
            port = target_port if target_port else self.ports[MessageSource.PLATE]
            bytes_sent = self.send_socket.sendto(full_message, (target_ip, port))
            
            logger.debug(f"发送Plate消息到 {target_ip}:{port}, 长度: {bytes_sent} 字节")
            return True
            
        except Exception as e:
            logger.error(f"发送Plate消息失败: {e}")
            return False
    
    def send_net_message(self, message_type: int, content: bytes, 
                             target_ip: str, target_port: int = None, 
                             source: MessageSource = MessageSource.NET) -> bool:
        """发送NET消息"""
        """content是除了crc的所有内容"""
        if not self.send_socket:
            logger.error("发送套接字未初始化")
            return False
        
        try:    
            # 计算CRC
            crc = calculate_crc16(content)
            
            # 添加CRC：消息 + CRC(2)
            full_message = content + struct.pack('>H', crc)
            
            port = target_port if target_port else self.ports[source]
            bytes_sent = self.send_socket.sendto(full_message, (target_ip, port))
            
            logger.debug(f"发送{source.value}消息到 {target_ip}:{port}, "
                        f"类型:{message_type}, 长度:{bytes_sent} 字节, CRC:0x{crc:04X}")
            return True
            
        except Exception as e:
            logger.error(f"发送{source.value}消息失败: {e}")
            return False
    
    def send_lora_message(self, message_type: int, content: bytes, 
                             target_ip: str, target_port: int = None, 
                             source: MessageSource = MessageSource.LORA) -> bool:
        """发送LORA消息"""
        """content是除了crc的所有内容"""
        if not self.send_socket:
            logger.error("发送套接字未初始化")
            return False
        
        try:    
            # 计算CRC
            crc = calculate_crc16(content)
            
            # 添加CRC：消息 + CRC(2)
            full_message = content + struct.pack('>H', crc)
            
            port = target_port if target_port else self.ports[source]
            bytes_sent = self.send_socket.sendto(full_message, (target_ip, port))
            
            logger.debug(f"发送{source.value}消息到 {target_ip}:{port}, "
                        f"类型:{message_type}, 长度:{bytes_sent} 字节, CRC:0x{crc:04X}")
            return True
            
        except Exception as e:
            logger.error(f"发送{source.value}消息失败: {e}")
            return False

class MessageProcessor:
    """消息处理器"""
    
    def __init__(self, server: UDPServer):
        self.server = server
        self.running = False
        self.thread = None
    
    def process_message(self, message: ParsedMessage):
        """处理具体的消息（在这里实现你的业务逻辑）"""
        logger.info(f"处理 {message.source.value} 消息:")
        logger.info(f"  客户端地址: {message.client_address}")
        logger.info(f"  数据长度: {len(message.content)} 字节")
        
        if message.source == MessageSource.PLATE:
            logger.info(f"  Plate消息内容: {message.content.hex() if message.content else 'empty'}")
        else:
            logger.info(f"  消息类型: {message.message_type}")
            logger.info(f"  声明长度: {message.length}")
            logger.info(f"  CRC校验: 0x{message.crc:04X}")
            logger.info(f"  消息内容: {message.content.hex() if message.content else 'empty'}")
        
        # 可以在这里根据配置参数进行不同的处理
        if sys_para.net_mod == 7:  # 簇首调度模式
            self._handle_cluster_head_mode(message)
        elif sys_para.net_mod == 8:  # 自组织网模式
            self._handle_self_organize_mode(message)
        else:  # 其他物联网模式
            self._handle_normal_mode(message)
        
        # TODO: 在这里添加你的业务处理逻辑
    
    def _handle_cluster_head_mode(self, message: ParsedMessage):
        """处理簇首调度模式"""
        logger.info("处理簇首调度模式消息")
        # 可以使用 sys_para.clust_id, sys_para.clust_numb 等参数
        
    def _handle_self_organize_mode(self, message: ParsedMessage):
        """处理自组织网模式"""
        logger.info("处理自组织网模式消息")
        
    def _handle_normal_mode(self, message: ParsedMessage):
        """处理普通物联网模式"""
        logger.info(f"处理模式{sys_para.net_mod}消息")
        
    def start_processing(self):
        """启动消息处理线程"""
        if self.running:
            logger.warning("消息处理器已经在运行")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._process_loop, name="MessageProcessor", daemon=True)
        self.thread.start()
        logger.info("消息处理器已启动")
    
    def stop_processing(self):
        """停止消息处理"""
        if not self.running:
            logger.warning("消息处理器未在运行")
            return
        
        logger.info("正在停止消息处理器...")
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        logger.info("消息处理器已停止")
    
    def _process_loop(self):
        """消息处理循环"""
        # 使用配置文件中的处理间隔
        process_interval =  0.001
        
        while self.running:
            try:
                message = self.server.get_message(timeout=1.0)
                if message:
                    self.process_message(message)
                # 添加处理间隔
                if process_interval > 0:
                    time.sleep(process_interval)
            except Exception as e:
                logger.error(f"消息处理错误: {e}")

def main():
    """主函数"""
    # 首先加载配置文件
    load_config_from_file("config.ini")

    # 创建UDP服务器，使用配置文件中的IP地址
    server = UDPServer()
    
    # 创建消息处理器
    processor = MessageProcessor(server)
    
    try:
        # 启动服务器
        server.start()
        
        # 启动消息处理器
        processor.start_processing()
        
        logger.info("系统启动完成，按 Ctrl+C 退出")
        logger.info(f"端口配置: Plate={udp_config.plat_port}, "
                   f"Net={udp_config.net_port}, "
                   f"Lora={udp_config.lora_port}")
        logger.info(f"监听地址: {network_config.local_ip}")

    except KeyboardInterrupt:
        logger.info("收到退出信号")
    
    finally:
        # 清理资源
        processor.stop_processing()
        server.stop()
        logger.info("程序退出")

if __name__ == "__main__":
    main()