"""
认证API接口
使用FastAPI框架
"""
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, validator
from typing import Optional, Dict, Any
import uvicorn

from .service import AuthService


# 数据模型
class RegisterRequest(BaseModel):
    """注册请求"""
    username: str
    email: EmailStr
    password: str
    
    @validator('username')
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError('用户名长度至少3个字符')
        if len(v) > 30:
            raise ValueError('用户名长度不能超过30个字符')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('密码长度至少8个字符')
        return v


class LoginRequest(BaseModel):
    """登录请求"""
    identifier: str  # 用户名或邮箱
    password: str


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str
    new_password: str


class TokenResponse(BaseModel):
    """Token响应"""
    access_token: str
    token_type: str
    user: Dict[str, Any]


class UserResponse(BaseModel):
    """用户信息响应"""
    id: int
    username: str
    email: str
    created_at: str
    last_login: Optional[str]
    is_active: bool


class MessageResponse(BaseModel):
    """消息响应"""
    message: str
    success: bool


# 创建FastAPI应用
app = FastAPI(
    title="用户认证API",
    description="用户注册、登录、认证API接口",
    version="1.0.0"
)

# 创建API路由组
from fastapi import APIRouter
api_router = APIRouter(prefix="/api")

# 创建认证服务实例
auth_service = AuthService()

# 安全方案
security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    获取当前用户（依赖注入）
    
    Args:
        credentials: 认证凭证
        
    Returns:
        用户信息
        
    Raises:
        HTTPException: 认证失败
    """
    token = credentials.credentials
    is_valid, message, payload = auth_service.verify_token(token)
    
    if not is_valid:
        raise HTTPException(status_code=401, detail=message)
    
    return payload


@app.get("/")
async def root():
    """根路径"""
    return {"message": "用户认证API服务运行中", "version": "1.0.0"}


@api_router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest, user_request: Request):
    """
    用户注册
    
    Args:
        request: 注册请求
        user_request: 请求对象（用于获取IP等信息）
    """
    ip_address = user_request.client.host if user_request.client else None
    user_agent = user_request.headers.get("user-agent")
    
    success, message, user = auth_service.register_user(
        username=request.username,
        email=request.email,
        password=request.password
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    # 自动登录新注册的用户
    login_success, login_message, login_result = auth_service.login(
        identifier=request.username,
        password=request.password,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    if not login_success:
        raise HTTPException(status_code=500, detail=f"注册成功但自动登录失败: {login_message}")
    
    return login_result


@api_router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, user_request: Request):
    """
    用户登录
    
    Args:
        request: 登录请求
        user_request: 请求对象（用于获取IP等信息）
    """
    ip_address = user_request.client.host if user_request.client else None
    user_agent = user_request.headers.get("user-agent")
    
    success, message, result = auth_service.login(
        identifier=request.identifier,
        password=request.password,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    if not success:
        raise HTTPException(status_code=401, detail=message)
    
    return result


@api_router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    获取当前用户信息
    
    Args:
        current_user: 当前用户（通过依赖注入获取）
    """
    user_id = int(current_user.get("sub", 0))
    user = auth_service.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return user.to_dict()


@api_router.post("/change-password", response_model=MessageResponse)
async def change_password(
    request: ChangePasswordRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    修改密码
    
    Args:
        request: 修改密码请求
        current_user: 当前用户
    """
    user_id = int(current_user.get("sub", 0))
    
    success, message = auth_service.update_user_password(
        user_id=user_id,
        old_password=request.old_password,
        new_password=request.new_password
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return MessageResponse(message=message, success=True)


@api_router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "auth-api"}


@api_router.get("/test-users")
async def get_test_users():
    """获取测试用户信息（仅用于测试）"""
    test_users = []
    for key, value in auth_service.users_db.items():
        if isinstance(value, auth_service.__class__.__module__ + '.User'):
            # 这里需要导入User类
            from .models import User
            if isinstance(value, User):
                test_users.append({
                    "id": value.id,
                    "username": value.username,
                    "email": value.email,
                    "is_active": value.is_active
                })
    
    # 去重
    unique_users = []
    seen_ids = set()
    for user in test_users:
        if user["id"] not in seen_ids:
            seen_ids.add(user["id"])
            unique_users.append(user)
    
    return {"test_users": unique_users}

# 包含API路由
app.include_router(api_router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)