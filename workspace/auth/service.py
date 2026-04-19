"""
认证服务
"""
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
import uuid

from .models import User, LoginAttempt
from .utils import PasswordValidator, JWTManager, validate_email, validate_username


class AuthService:
    """认证服务类"""
    
    def __init__(self, jwt_secret: str = "your-secret-key-change-in-production"):
        """
        初始化认证服务
        
        Args:
            jwt_secret: JWT密钥
        """
        self.password_validator = PasswordValidator()
        self.jwt_manager = JWTManager(jwt_secret)
        
        # 模拟数据库存储（实际项目中应使用真实数据库）
        self.users_db = {}
        self.login_attempts_db = []
        
        # 初始化一些测试用户
        self._init_test_users()
    
    def _init_test_users(self):
        """初始化测试用户"""
        test_users = [
            {
                'id': 1,
                'username': 'admin',
                'email': 'admin@example.com',
                'password': 'Admin@123',
                'created_at': datetime.now()
            },
            {
                'id': 2,
                'username': 'testuser',
                'email': 'test@example.com',
                'password': 'Test@123',
                'created_at': datetime.now()
            }
        ]
        
        for user_data in test_users:
            password_hash = self.password_validator.hash_password(user_data['password'])
            user = User(
                id=user_data['id'],
                username=user_data['username'],
                email=user_data['email'],
                password_hash=password_hash,
                created_at=user_data['created_at']
            )
            self.users_db[user_data['id']] = user
            self.users_db[user_data['username']] = user
            self.users_db[user_data['email']] = user
    
    def register_user(self, username: str, email: str, password: str) -> Tuple[bool, str, Optional[User]]:
        """
        注册新用户
        
        Args:
            username: 用户名
            email: 邮箱
            password: 密码
            
        Returns:
            (是否成功, 消息, 用户对象)
        """
        # 验证用户名格式
        is_valid, msg = validate_username(username)
        if not is_valid:
            return False, msg, None
        
        # 验证邮箱格式
        if not validate_email(email):
            return False, "邮箱格式不正确", None
        
        # 验证密码强度
        is_valid, msg = self.password_validator.validate_strength(password)
        if not is_valid:
            return False, msg, None
        
        # 检查用户名是否已存在
        if username in self.users_db:
            return False, "用户名已存在", None
        
        # 检查邮箱是否已存在
        if email in self.users_db:
            return False, "邮箱已注册", None
        
        # 创建新用户
        user_id = max([user.id for user in self.users_db.values() if isinstance(user, User)], default=0) + 1
        password_hash = self.password_validator.hash_password(password)
        created_at = datetime.now()
        
        user = User(
            id=user_id,
            username=username,
            email=email,
            password_hash=password_hash,
            created_at=created_at
        )
        
        # 保存用户
        self.users_db[user_id] = user
        self.users_db[username] = user
        self.users_db[email] = user
        
        return True, "注册成功", user
    
    def login(self, identifier: str, password: str, ip_address: Optional[str] = None, 
              user_agent: Optional[str] = None) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        用户登录
        
        Args:
            identifier: 用户名或邮箱
            password: 密码
            ip_address: IP地址（可选）
            user_agent: 用户代理（可选）
            
        Returns:
            (是否成功, 消息, 包含token和用户信息的字典)
        """
        # 查找用户
        user = self.users_db.get(identifier)
        if not user or not isinstance(user, User):
            # 记录失败的登录尝试
            self._record_login_attempt(None, False, ip_address, user_agent)
            return False, "用户名或密码错误", None
        
        # 验证密码
        if not self.password_validator.verify_password(password, user.password_hash):
            # 记录失败的登录尝试
            self._record_login_attempt(user.id, False, ip_address, user_agent)
            return False, "用户名或密码错误", None
        
        # 检查用户是否激活
        if not user.is_active:
            self._record_login_attempt(user.id, False, ip_address, user_agent)
            return False, "用户账户已被禁用", None
        
        # 更新最后登录时间
        user.last_login = datetime.now()
        
        # 创建JWT token
        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "email": user.email
        }
        access_token = self.jwt_manager.create_access_token(token_data)
        
        # 记录成功的登录尝试
        self._record_login_attempt(user.id, True, ip_address, user_agent)
        
        # 返回结果
        result = {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user.to_dict()
        }
        
        return True, "登录成功", result
    
    def _record_login_attempt(self, user_id: Optional[int], success: bool, 
                             ip_address: Optional[str], user_agent: Optional[str]):
        """
        记录登录尝试
        
        Args:
            user_id: 用户ID
            success: 是否成功
            ip_address: IP地址
            user_agent: 用户代理
        """
        attempt_id = len(self.login_attempts_db) + 1
        attempt = LoginAttempt(
            id=attempt_id,
            user_id=user_id if user_id else 0,
            attempt_time=datetime.now(),
            success=success,
            ip_address=ip_address,
            user_agent=user_agent
        )
        self.login_attempts_db.append(attempt)
    
    def verify_token(self, token: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        验证JWT token
        
        Args:
            token: JWT token
            
        Returns:
            (是否有效, 消息, token载荷)
        """
        is_valid, payload = self.jwt_manager.verify_token(token)
        if not is_valid:
            return False, payload.get("error", "Token验证失败"), None
        
        # 检查用户是否存在且激活
        user_id = int(payload.get("sub", 0))
        user = self.users_db.get(user_id)
        if not user or not isinstance(user, User) or not user.is_active:
            return False, "用户不存在或已被禁用", None
        
        return True, "Token验证成功", payload
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        根据ID获取用户
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户对象或None
        """
        user = self.users_db.get(user_id)
        if user and isinstance(user, User):
            return user
        return None
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """
        根据用户名获取用户
        
        Args:
            username: 用户名
            
        Returns:
            用户对象或None
        """
        user = self.users_db.get(username)
        if user and isinstance(user, User):
            return user
        return None
    
    def update_user_password(self, user_id: int, old_password: str, new_password: str) -> Tuple[bool, str]:
        """
        更新用户密码
        
        Args:
            user_id: 用户ID
            old_password: 旧密码
            new_password: 新密码
            
        Returns:
            (是否成功, 消息)
        """
        user = self.get_user_by_id(user_id)
        if not user:
            return False, "用户不存在"
        
        # 验证旧密码
        if not self.password_validator.verify_password(old_password, user.password_hash):
            return False, "旧密码不正确"
        
        # 验证新密码强度
        is_valid, msg = self.password_validator.validate_strength(new_password)
        if not is_valid:
            return False, msg
        
        # 更新密码
        new_password_hash = self.password_validator.hash_password(new_password)
        user.password_hash = new_password_hash
        
        return True, "密码更新成功"
    
    def deactivate_user(self, user_id: int) -> Tuple[bool, str]:
        """
        禁用用户账户
        
        Args:
            user_id: 用户ID
            
        Returns:
            (是否成功, 消息)
        """
        user = self.get_user_by_id(user_id)
        if not user:
            return False, "用户不存在"
        
        user.is_active = False
        return True, "用户账户已禁用"
    
    def activate_user(self, user_id: int) -> Tuple[bool, str]:
        """
        激活用户账户
        
        Args:
            user_id: 用户ID
            
        Returns:
            (是否成功, 消息)
        """
        user = self.get_user_by_id(user_id)
        if not user:
            return False, "用户不存在"
        
        user.is_active = True
        return True, "用户账户已激活"
    
    def get_login_attempts(self, user_id: Optional[int] = None, limit: int = 10) -> list[LoginAttempt]:
        """
        获取登录尝试记录
        
        Args:
            user_id: 用户ID（可选）
            limit: 返回记录数量限制
            
        Returns:
            登录尝试记录列表
        """
        attempts = self.login_attempts_db
        
        if user_id is not None:
            attempts = [a for a in attempts if a.user_id == user_id]
        
        # 按时间倒序排序
        attempts.sort(key=lambda x: x.attempt_time, reverse=True)
        
        return attempts[:limit]