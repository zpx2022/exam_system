"""
国密加密工具模块
封装SM2、SM4、SM3算法
"""
from gmssl import sm2, sm4, sm3
from django.conf import settings
import binascii
import secrets
import hashlib


class GMCrypto:
    """国密加密工具类"""
    
    def __init__(self):
        # SM2密钥对（从settings读取）
        self.sm2_private_key = settings.SM2_PRIVATE_KEY
        self.sm2_public_key = settings.SM2_PUBLIC_KEY
        # SM4密钥（从settings读取）
        self.sm4_key = settings.SM4_KEY.encode('utf-8')
        
        # 初始化SM2实例
        self.sm2_crypt = sm2.CryptSM2(
            public_key=self.sm2_public_key,
            private_key=self.sm2_private_key
        )
        
        # 初始化SM4实例
        self.sm4_crypt = sm4.CryptSM4()
        self.sm4_crypt.set_key(self.sm4_key, sm4.SM4_ENCRYPT)
    
    def sm2_decrypt_key(self, encrypted_key_hex):
        """
        SM2解密密钥（数字信封中的密钥）
        :param encrypted_key_hex: 十六进制字符串格式的加密密钥
        :return: 解密后的密钥（十六进制字符串，用于SM4）
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            encrypted_key = binascii.unhexlify(encrypted_key_hex)
            decrypted_key = self.sm2_crypt.decrypt(encrypted_key)
            
            
            # 解密后应该是字节串
            if isinstance(decrypted_key, bytes):
                # 前端加密的是32个十六进制字符的字符串
                # 尝试多种方式处理
                
                # 方式1: 如果是16字节，直接转为32个十六进制字符
                if len(decrypted_key) == 16:
                    result = binascii.hexlify(decrypted_key).decode('utf-8')
                    return result
                
                # 方式2: 如果是32字节，尝试解码为UTF-8字符串
                if len(decrypted_key) == 32:
                    try:
                        decrypted_str = decrypted_key.decode('utf-8')
                        # 验证是否是32个十六进制字符
                        if len(decrypted_str) == 32:
                            try:
                                int(decrypted_str, 16)
                                return decrypted_str
                            except ValueError:
                                pass
                    except UnicodeDecodeError:
                        pass
                
                # 方式3: 如果是64字节或其他长度，尝试截取前16字节
                if len(decrypted_key) >= 16:
                    # 可能是某种编码导致长度翻倍，尝试取前16字节
                    result = binascii.hexlify(decrypted_key[:16]).decode('utf-8')
                    return result
                
                # 如果都不行，抛出错误
                raise ValueError(f"解密后的密钥长度不正确: {len(decrypted_key)}字节，无法处理")
            
            # 如果已经是字符串，假设是十六进制字符串
            result = str(decrypted_key)
            return result
        except Exception as e:
            logger.error(f"SM2解密失败: {str(e)}", exc_info=True)
            raise ValueError(f"SM2解密失败: {str(e)}")
    
    def sm4_encrypt_data(self, data, key=None, iv=None):
        """
        SM4加密数据（CBC模式）
        :param data: 待加密的字符串或字节串
        :param key: 可选，如果提供则使用该密钥（十六进制字符串或字节串），否则使用默认密钥
        :param iv: 可选，CBC模式的初始化向量，如果为None则自动生成
        :return: 十六进制字符串格式的密文（CBC模式返回 iv:ciphertext 格式）
        """
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        if iv is None:
            # 自动生成随机IV
            iv_bytes = secrets.token_bytes(16)
            iv_hex = binascii.hexlify(iv_bytes).decode('utf-8')
        else:
            # 使用提供的IV
            if isinstance(iv, str):
                # 十六进制字符串
                iv_bytes = binascii.unhexlify(iv)
                iv_hex = iv
            else:
                # 字节串
                iv_bytes = iv
                iv_hex = binascii.hexlify(iv_bytes).decode('utf-8')
            
            # 确保IV长度是16字节
            if len(iv_bytes) != 16:
                raise ValueError(f"SM4 IV长度错误: 期望16字节，实际{len(iv_bytes)}字节")
        
        if key:
            # 使用临时密钥
            temp_crypt = sm4.CryptSM4()
            # 确保key是字节串格式
            if isinstance(key, str):
                # 如果是字符串，假设是十六进制字符串，转为字节串
                if len(key) == 32:
                    # 十六进制字符串，转为字节串
                    key_bytes = binascii.unhexlify(key)
                else:
                    # 普通字符串，UTF-8编码
                    key_bytes = key.encode('utf-8')
            else:
                key_bytes = key
            
            # 确保密钥长度是16字节
            if len(key_bytes) != 16:
                raise ValueError(f"SM4密钥长度错误: 期望16字节，实际{len(key_bytes)}字节")
            
            temp_crypt.set_key(key_bytes, sm4.SM4_ENCRYPT)
            encrypted = temp_crypt.crypt_cbc(iv_bytes, data)
        else:
            # 使用默认密钥
            temp_crypt = sm4.CryptSM4()
            temp_crypt.set_key(self.sm4_key, sm4.SM4_ENCRYPT)
            encrypted = temp_crypt.crypt_cbc(iv_bytes, data)
        
        encrypted_hex = binascii.hexlify(encrypted).decode('utf-8')
        
        # 返回 iv:ciphertext 格式
        return f"{iv_hex}:{encrypted_hex}"
    
    def sm4_decrypt_data(self, encrypted_hex, key=None, mode='cbc'):
        """
        SM4解密数据（CBC模式）
        :param encrypted_hex: 十六进制字符串格式的密文（CBC格式为 iv:ciphertext）
        :param key: 可选，如果提供则使用该密钥（十六进制字符串或字节串），否则使用默认密钥
        :param mode: 加密模式，目前支持 'cbc'
        :return: 解密后的字符串
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            if mode.lower() == 'cbc':
                # CBC模式：格式为 iv:ciphertext
                if ':' not in encrypted_hex:
                    raise ValueError("CBC模式密文格式错误，应为 iv:ciphertext")
                
                iv_hex, ciphertext_hex = encrypted_hex.split(':', 1)
                
                # 将十六进制字符串转为字节串
                iv = binascii.unhexlify(iv_hex)
                encrypted = binascii.unhexlify(ciphertext_hex)
                
                if key:
                    # 使用临时密钥
                    temp_crypt = sm4.CryptSM4()
                    # 确保key是字节串格式
                    if isinstance(key, str):
                        if len(key) == 32:
                            key_bytes = binascii.unhexlify(key)
                        else:
                            key_bytes = key.encode('utf-8')
                    else:
                        key_bytes = key
                    
                    if len(key_bytes) != 16:
                        raise ValueError(f"SM4密钥长度错误: 期望16字节，实际{len(key_bytes)}字节")
                    
                    temp_crypt.set_key(key_bytes, sm4.SM4_DECRYPT)
                    decrypted = temp_crypt.crypt_cbc(iv, encrypted)
                else:
                    # 使用默认密钥
                    temp_crypt = sm4.CryptSM4()
                    temp_crypt.set_key(self.sm4_key, sm4.SM4_DECRYPT)
                    decrypted = temp_crypt.crypt_cbc(iv, encrypted)
            else:
                raise ValueError(f"不支持的加密模式: {mode}")
            
            # 将解密后的字节串转为字符串
            if isinstance(decrypted, bytes):
                return decrypted.decode('utf-8')
            else:
                return str(decrypted)
                
        except Exception as e:
            logger.error(f"SM4解密失败: {str(e)}", exc_info=True)
            raise ValueError(f"SM4解密失败: {str(e)}")
    
    def sm3_hash_with_salt(self, password, salt=None):
        """
        SM3哈希（带动态盐）
        :param password: 原始密码
        :param salt: 盐值，如果为None则自动生成
        :return: (哈希值, 盐值)
        """
        if salt is None:
            # 生成32字节随机盐
            salt = secrets.token_hex(16)
        
        # 密码+盐值进行SM3哈希
        data = (password + salt).encode('utf-8')
        hash_value = sm3.sm3_hash([i for i in data])
        
        # sm3_hash返回的是字符串列表，需要处理
        if isinstance(hash_value, list):
            # 如果是字符串列表，直接连接
            if isinstance(hash_value[0], str):
                hash_hex = ''.join(hash_value)
            else:
                # 如果是整数列表，转换为十六进制
                hash_hex = ''.join([f'{x:02x}' for x in hash_value])
        else:
            # 如果是字符串，直接使用
            hash_hex = hash_value if isinstance(hash_value, str) else str(hash_value)
        
        return hash_hex, salt
    
    def verify_password(self, password, stored_hash, salt):
        """
        验证密码
        :param password: 待验证的密码
        :param stored_hash: 存储的哈希值
        :param salt: 存储的盐值
        :return: True/False
        """
        hash_value, _ = self.sm3_hash_with_salt(password, salt)
        return hash_value == stored_hash


# 全局实例
gm_crypto = GMCrypto()

