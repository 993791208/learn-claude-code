# 用户认证模块

这是一个完整的用户认证系统，包含用户注册、登录、JWT token管理等功能。

## 功能特性

- ✅ 用户注册（用户名、邮箱、密码）
- ✅ 用户登录（支持用户名或邮箱登录）
- ✅ JWT token生成和验证
- ✅ 密码强度验证和加密存储（bcrypt）
- ✅ 登录尝试记录
- ✅ 用户账户激活/禁用
- ✅ RESTful API接口（FastAPI）
- ✅ 完整的输入验证
- ✅ 测试脚本

## 安装依赖

```bash
pip install -r requirements.txt
```

或者手动安装：

```bash
pip install fastapi uvicorn python-jose[cryptography] passlib[bcrypt] pydantic
```

## 快速开始

### 1. 运行测试

```bash
python test_auth.py
```

### 2. 启动API服务器

```bash
python api.py
```

服务器将在 http://localhost:8000 启动。

### 3. 访问API文档

打开浏览器访问：http://localhost:8000/docs

## API端点

### 公开端点

- `POST /register` - 用户注册
- `POST /login` - 用户登录
- `GET /health` - 健康检查
- `GET /test-users` - 获取测试用户列表

### 需要认证的端点

- `GET /me` - 获取当前用户信息
- `POST /change-password` - 修改密码

## 测试用户

系统预置了两个测试用户：

1. **用户名**: admin
   **邮箱**: admin@example.com
   **密码**: Admin@123

2. **用户名**: testuser
   **邮箱**: test@example.com
   **密码**: Test@123

## 使用示例

### 注册新用户

```bash
curl -X POST "http://localhost:8000/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "email": "newuser@example.com",
    "password": "New@Pass123"
  }'
```

### 用户登录

```bash
curl -X POST "http://localhost:8000/login" \
  -H "Content-Type: application/json" \
  -d '{
    "identifier": "admin",
    "password": "Admin@123"
  }'
```

### 获取用户信息（需要Token）

```bash
curl -X GET "http://localhost:8000/me" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 修改密码

```bash
curl -X POST "http://localhost:8000/change-password" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "old_password": "oldpassword",
    "new_password": "New@Pass123"
  }'
```

## 密码要求

- 长度：8-64个字符
- 至少包含一个数字
- 至少包含一个小写字母
- 至少包含一个大写字母
- 至少包含一个特殊字符（!@#$%^&*(),.?":{}|<>）

## 用户名要求

- 长度：3-30个字符
- 只能包含字母、数字、下划线和连字符

## 安全特性

1. **密码加密**: 使用bcrypt算法存储密码哈希
2. **JWT token**: 使用HS256算法签名，默认1小时过期
3. **输入验证**: 所有输入都经过严格验证
4. **登录限制**: 记录所有登录尝试，可用于实现登录频率限制
5. **SQL注入防护**: 使用参数化查询（在实际数据库实现中）

## 测试要点

### 边界情况测试

1. **空输入测试**
   - 空用户名、邮箱、密码
   - 只有空格的输入

2. **格式验证测试**
   - 无效邮箱格式
   - 无效用户名格式
   - 弱密码测试

3. **安全测试**
   - SQL注入尝试（如 `' OR '1'='1`）
   - XSS攻击尝试
   - 超长输入测试

4. **功能测试**
   - 重复注册测试
   - 错误密码多次尝试
   - Token过期测试
   - 禁用用户登录测试

### 性能测试

1. **并发登录测试**
2. **Token验证性能**
3. **密码哈希性能**

## 项目结构

```
auth/
├── __init__.py          # 模块初始化
├── models.py           # 数据模型
├── utils.py            # 工具函数（密码验证、JWT等）
├── service.py          # 认证服务
├── api.py              # FastAPI接口
├── test_auth.py        # 测试脚本
├── requirements.txt    # 依赖列表
└── README.md           # 本文档
```

## 扩展建议

1. **数据库集成**: 当前使用内存存储，可替换为SQLite/PostgreSQL/MySQL
2. **邮件验证**: 添加邮箱验证功能
3. **密码重置**: 添加忘记密码功能
4. **多因素认证**: 添加2FA支持
5. **OAuth集成**: 支持第三方登录（Google、GitHub等）
6. **角色权限**: 添加用户角色和权限管理
7. **审计日志**: 完整的操作日志记录

## 注意事项

1. 在生产环境中，请修改 `JWT_SECRET_KEY`
2. 建议使用环境变量管理敏感配置
3. 考虑添加速率限制防止暴力破解
4. 建议使用HTTPS传输敏感数据