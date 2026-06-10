# minecraft_api.py
import asyncio
import socket
import struct
import json
from typing import Optional, Dict

async def get_bedrock_status(ip: str, port: int = 19132, timeout: int = 3) -> Optional[Dict]:
    """Получение онлайн Bedrock сервера"""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=timeout
        )
        
        ping_data = bytearray(b'\x01')
        ping_data += b'\x00' * 15
        ping_data += struct.pack('<Q', 0)
        ping_data += struct.pack('<Q', 0)
        
        writer.write(ping_data)
        await writer.drain()
        
        response = await asyncio.wait_for(reader.read(2048), timeout=timeout)
        writer.close()
        await writer.closed
        
        if len(response) > 35:
            offset = 35
            name_length = response[offset]
            offset += 1
            server_name = response[offset:offset+name_length].decode('utf-8', errors='ignore')
            offset += name_length
            
            offset += 4  # protocol
            offset += response[offset] + 1  # version
            
            online = struct.unpack('<i', response[offset:offset+4])[0]
            offset += 4
            max_players = struct.unpack('<i', response[offset:offset+4])[0]
            
            return {
                "online": online,
                "max": max_players,
                "name": server_name
            }
    except:
        pass
    return {"online": 0, "max": 0, "name": "Оффлайн"}

async def get_java_status(ip: str, port: int = 25565, timeout: int = 3) -> Optional[Dict]:
    """Получение онлайн Java сервера"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))
        
        # Handshake
        handshake = bytearray()
        handshake += b'\x00'
        handshake += b'\x04\x00\x00\x00'
        host_bytes = ip.encode('utf-8')
        handshake += bytes([len(host_bytes)]) + host_bytes
        handshake += struct.pack('>H', port)
        handshake += b'\x01'
        
        send_varint(sock, len(handshake))
        sock.send(handshake)
        
        send_varint(sock, 0x00)
        send_varint(sock, 0x00)
        
        length = read_varint(sock)
        data = b''
        while len(data) < length:
            data += sock.recv(1024)
        
        sock.close()
        
        data = data[1:]
        json_data = json.loads(data.decode('utf-8'))
        
        players = json_data.get("players", {})
        return {
            "online": players.get("online", 0),
            "max": players.get("max", 0),
            "version": json_data.get("version", {}).get("name", "?"),
            "motd": json_data.get("description", {}).get("text", "")
        }
    except:
        return {"online": 0, "max": 0, "version": "?", "motd": "Оффлайн"}

def send_varint(sock, value: int):
    while True:
        if value & ~0x7F == 0:
            sock.send(bytes([value]))
            return
        sock.send(bytes([(value & 0x7F) | 0x80]))
        value >>= 7

def read_varint(sock) -> int:
    result = 0
    shift = 0
    while True:
        byte = sock.recv(1)[0]
        result |= (byte & 0x7F) << shift
        shift += 7
        if not (byte & 0x80):
            return result
