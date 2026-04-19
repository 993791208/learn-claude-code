"""
用户数据模型
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """用户数据类"""
    id: int
    username: str
    email: str
    password_hash: str
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat(),
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_active': self.is_active
        }


@dataclass
class LoginAttempt:
    """登录尝试记录"""
    id: int
    user_id: int
    attempt_time: datetime
    success: bool
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None