"""
认证工具函数
"""
import re
import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


class PasswordValidator:
    """密码验证器"""
    
    @staticmethod
    def validate_strength(password: str) -> tuple[bool, str]:
        """
        验证密码强度
        
        Args:
            password: 密码字符串
            
        Returns:
            (是否有效, 错误信息)
        """
        if len(password) < 8:
            return False, "密码长度至少8个字符"
        
        if len(password) > 64:
            return False, "密码长度不能超过64个字符"
        
        # 检查是否包含至少一个数字
        if not re.search(r'\d', password):
            return False, "密码必须包含至少一个数字"
        
        # 检查是否包含至少一个小写字母
        if not re.search(r'[a-z]', password):
            return False, "密码必须包含至少一个小写字母"
        
        # 检查是否包含至少一个大写字母
        if not re.search(r'[A-Z]', password):
            return False, "密码必须包含至少一个大写字母"
        
        # 检查是否包含至少一个特殊字符
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "密码必须包含至少一个特殊字符"
        
        return True, "密码强度符合要求"
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        哈希密码
        
        Args:
            password: 明文密码
            
        Returns:
            哈希后的密码
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """
        验证密码
        
        Args:
            password: 明文密码
            hashed_password: 哈希密码
            
        Returns:
            是否匹配
        """
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))


class JWTManager:
    """JWT Token管理器"""
    
    def __init__(self, secret_key: str, algorithm: str = 'HS256'):
        """
        初始化JWT管理器
        
        Args:
            secret_key: 密钥
            algorithm: 加密算法
        """
        self.secret_key = secret_key
        self.algorithm = algorithm
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """
        创建访问token
        
        Args:
            data: 要编码的数据
            expires_delta: 过期时间间隔
            
        Returns:
            JWT token字符串
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=1)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def decode_token(self, token: str) -> Dict[str, Any]:
        """
        解码token
        
        Args:
            token: JWT token字符串
            
        Returns:
            解码后的数据
            
        Raises:
            jwt.ExpiredSignatureError: token过期
            jwt.InvalidTokenError: token无效
        """
        return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
    
    def verify_token(self, token: str) -> tuple[bool, Optional[Dict[str, Any]]]:
        """
        验证token
        
        Args:
            token: JWT token字符串
            
        Returns:
            (是否有效, 解码后的数据或错误信息)
        """
        try:
            payload = self.decode_token(token)
            return True, payload
        except jwt.ExpiredSignatureError:
            return False, {"error": "Token已过期"}
        except jwt.InvalidTokenError:
            return False, {"error": "无效的Token"}


def validate_email(email: str) -> bool:
    """
    验证邮箱格式
    
    Args:
        email: 邮箱地址
        
    Returns:
        是否有效
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_username(username: str) -> tuple[bool, str]:
    """
    验证用户名格式
    
    Args:
        username: 用户名
        
    Returns:
        (是否有效, 错误信息)
    """
    if len(username) < 3:
        return False, "用户名长度至少3个字符"
    
    if len(username) > 30:
        return False, "用户名长度不能超过30个字符"
    
    # 只允许字母、数字、下划线和连字符
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False, "用户名只能包含字母、数字、下划线和连字符"
    
    return True, "用户名格式正确"