#!/usr/bin/env python3
# Harness: tool dispatch -- expanding what the model can reach.
"""
s02_tool_use.py - Tools

The agent loop from s01 didn't change. We just added tools to the array
and a dispatch map to route calls.

    +----------+      +-------+      +------------------+
    |   User   | ---> |  LLM  | ---> | Tool Dispatch    |
    |  prompt  |      |       |      | {                |
    +----------+      +---+---+      |   bash: run_bash |
                          ^          |   read: run_read |
                          |          |   write: run_wr  |
                          +----------+   edit: run_edit |
                          tool_result| }                |
                                     +------------------+

Key insight: "The loop didn't change at all. I just added tools."
"""

import os
import subprocess
import readline # 用于修复终端下无法使用方向键和仅能删除一半中文字符的问题
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

# 加载 .env 里的配置
load_dotenv(override=True)

# 代理相关配置（如果填了的话）
if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

# 获取我们当前运行代码的“工作目录”
WORKDIR = Path.cwd()

# 初始化大模型客户端
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
MODEL = os.environ["MODEL_ID"]

# 【系统提示词 (System Prompt)】
# 现在我们不再只让它用 bash 了，而是告诉它：“你可以使用工具们 (tools) 来解决任务。”
SYSTEM = f"You are a coding agent at {WORKDIR}. Use tools to solve tasks. Act, don't explain."


# ====== 核心安全概念：沙盒 (Sandbox) ======
def safe_path(p: str) -> Path:
    """
    【防脱逃锁】这是一个非常关键的安全函数！
    在这个程序里，我们赋予了 AI 读写文件的能力。为了防止它“发疯”或者被恶意引诱去读取、修改电脑里的系统文件
    （比如偷看你的密码本、修改系统配置），我们必须把它“关”在当前文件夹里干活！
    
    不管 AI 传来什么路径，这个函数都会检查它是不是超出了当前所在文件夹 (WORKDIR)。
    如果超出了，就会拦截并报错。
    """
    # 将传进来的相对路径转换为电脑上的绝对路径
    path = (WORKDIR / p).resolve()
    
    # 检查转换后的路径，是不是以我们的当前目录开头的？
    if not path.is_relative_to(WORKDIR):
        # 如果不是（说明它想去上级目录或别的盘），立刻抛出错误拦截！
        raise ValueError(f"Path escapes workspace: {p}")
        
    return path


# ====== 多工具的具体实现 ======

# 工具 1：执行终端命令（和 s01 里一样）
# def run_bash(command: str) -> str:
#     """执行 bash 命令，带危险词拦截。"""
#     dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
#     if any(d in command for d in dangerous):
#         return "Error: Dangerous command blocked"
#     try:
#         r = subprocess.run(command, shell=True, cwd=WORKDIR,
#                            capture_output=True, text=True, timeout=120)
#         out = (r.stdout + r.stderr).strip()
#         return out[:50000] if out else "(no output)"
#     except subprocess.TimeoutExpired:
#         return "Error: Timeout (120s)"

# 工具 2：读取文件
def run_read(path: str, limit: int = None) -> str:
    """帮 AI 阅读传进来的文件路径里的内容"""
    try:
        # 第一步：一定要先用上面的安全锁检查路径！
        text = safe_path(path).read_text()
        
        # 把文件按行切分
        lines = text.splitlines()
        
        # 如果文件太长，只读取前 limit 行（防止字数太多撑爆大模型限制）
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
            
        # 截流前 50000 个字符退还
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"Error: {e}"

# 工具 3：写入新文件
def run_write(path: str, content: str) -> str:
    """帮 AI 创建一个新文件，并把内容写进去"""
    try:
        # 安全检查路径
        fp = safe_path(path)
        # 如果这个文件所在的文件夹不存在，就自动帮它创建出这个文件夹
        fp.parent.mkdir(parents=True, exist_ok=True)
        # 写入大模型给的代码内容
        fp.write_text(content)
        # 给大模型返回个成功提示
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"

# 工具 4：精确修改文件某一段文字
def run_edit(path: str, old_text: str, new_text: str) -> str:
    """在现有文件中，把 old_text 替换成 new_text"""
    try:
        fp = safe_path(path)
        content = fp.read_text()
        # 如果找不到它想替换的老文本，诉它找不着！
        if old_text not in content:
            return f"Error: Text not found in {path}"
        # 进行文本替换（1 表示只替换第一次出现的地方），并写回文件
        fp.write_text(content.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"

# -- The dispatch map: {tool_name: handler} --
# ====== 字典分发 (Dispatch Map) ======
# 这个字典非常精妙！
# 它就像一个接线员，左边是“大模型口中的工具名字”，右边是“真正召唤执行的 Python 函数”
# **kw 意思是把大模型传过来的那一堆 JSON 参数解包，直接塞进对应的函数里
TOOL_HANDLERS = {
    # "bash":       lambda **kw: run_bash(kw["command"]),
    "read_file":  lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file":  lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
}

# ====== 上报给大模型的“工具菜单” ======
# 我们需要把这些工具的具体名字和需要的参数格式，提前通过 JSON 报告给大模型，供它挑选
TOOLS = [
    # {"name": "bash", "description": "Run a shell command.",
    #  "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
     
    {"name": "read_file", "description": "Read file contents.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}},
     
    {"name": "write_file", "description": "Write content to file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
     
    {"name": "edit_file", "description": "Replace exact text in file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
]

def normalize_messages(messages: list) -> list:
    """将内部消息列表规范化为 API 可接受的格式。"""
    normalized = []

    for msg in messages:
        # Step 1: 剥离内部字段
        clean = {"role": msg["role"]}
        if isinstance(msg.get("content"), str):
            clean["content"] = msg["content"]
        elif isinstance(msg.get("content"), list):
            clean["content"] = [
                {k: v for k, v in block.items() if k not in ("_internal", "_source", "_timestamp")}
                for block in msg["content"]
            ]
        normalized.append(clean)

    # Step 2: tool_result 配对补齐
    # 收集所有已有的 tool_result ID
    existing_results = set()
    for msg in normalized:
        if isinstance(msg.get("content"), list):
            for block in msg["content"]:
                if block.get("type") == "tool_result":
                    existing_results.add(block.get("tool_use_id"))

    # 找出缺失配对的 tool_use, 插入占位 result
    for msg in normalized:
        if msg["role"] == "assistant" and isinstance(msg.get("content"), list):
            for block in msg["content"]:
                if (block.get("type") == "tool_use"
                        and block.get("id") not in existing_results):
                    # 在下一条 user 消息中补齐
                    normalized.append({"role": "user", "content": [{
                        "type": "tool_result",
                        "tool_use_id": block["id"],
                        "content": "(cancelled)",
                    }]})

    # Step 3: 合并连续同角色消息
    merged = [normalized[0]] if normalized else []
    for msg in normalized[1:]:
        if msg["role"] == merged[-1]["role"]:
            # 合并内容
            prev = merged[-1]
            prev_content = prev["content"] if isinstance(prev["content"], list) \
                else [{"type": "text", "text": prev["content"]}]
            curr_content = msg["content"] if isinstance(msg["content"], list) \
                else [{"type": "text", "text": msg["content"]}]
            prev["content"] = prev_content + curr_content
        else:
            merged.append(msg)

    return merged

# ====== 核心灵魂：大模型的思考死循环 ======
def agent_loop(messages: list):
    """跟 s01 几乎一模一样的循环。唯一的区别是对多工具的自动处理！"""
    while True:
        # 发送聊天记录和这 4 个工具组成的“菜单”给大模型
        response = client.messages.create(
            model=MODEL, system=SYSTEM,
            messages=normalize_messages(messages),  # 规范化后再发送
            tools=TOOLS, max_tokens=8000,
        )
        
        # 将回复记录上小本本
        messages.append({"role": "assistant", "content": response.content})
        
        # 检查是否完成了任务
        if response.stop_reason != "tool_use":
            return
            
        results = []
        for block in response.content:
            # 大模型决定调用工具
            if block.type == "tool_use":
                
                # ====== 与 s01 不同的魔法部分：自动分发 ======
                # 去刚才配好的字典（接线员）里查找，看看大模型喊到的这个工具名有没有对应的处理函数？
                handler = TOOL_HANDLERS.get(block.name)
                
                # 如果这个函数存在，就把参数丢进去执行拿到 output。反之告诉它查无此工具
                output = handler(**block.input) if handler else f"Unknown tool: {block.name}"
                
                # 在屏幕上打印出 AI 正在调用的工具名字，以及结果的前 200 个字
                print(f"> {block.name}: {output[:200]}")
                
                # 把每个工具执行的结果打包起来
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})
                
        # 将一揽子执行结果发给大模型让他继续思考
        messages.append({"role": "user", "content": results})


# ====== 程序启动 ======
if __name__ == "__main__":
    history = []
    while True:
        try:
            query = input("\033[36ms02 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
            
        history.append({"role": "user", "content": query})
        
        agent_loop(history)
        
        # 提取回复并打印
        response_content = history[-1]["content"]
        if isinstance(response_content, list):
            for block in response_content:
                if hasattr(block, "text"):
                    print(block.text)
        print("-----end conversation-----")





