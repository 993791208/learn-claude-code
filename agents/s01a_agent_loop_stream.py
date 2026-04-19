#!/usr/bin/env python3
# Harness: the loop -- the model's first connection to the real world.
"""
s01_agent_loop.py - The Agent Loop

The entire secret of an AI coding agent in one pattern:

    while stop_reason == "tool_use":
        response = LLM(messages, tools)
        execute tools
        append results

    +----------+      +-------+      +---------+
    |   User   | ---> |  LLM  | ---> |  Tool   |
    |  prompt  |      |       |      | execute |
    +----------+      +---+---+      +----+----+
                          ^               |
                          |   tool_result |
                          +---------------+
                          (loop continues)

This is the core loop: feed tool results back to the model
until the model decides to stop. Production agents layer
policy, hooks, and lifecycle controls on top.
"""

import os # 用于和操作系统交互，比如获取环境变量、执行命令、获取当前路径等
import readline # 用于修复终端下无法使用方向键和仅能删除一半中文字符的问题
import subprocess # 用于在 Python 里启动一个外部程序（比如你的电脑终端Bash）
import json # 用于把复杂的数据结构化、美化成漂亮的 JSON 格式打印出来

# ====== 辅助打印的工具函数 ======
def make_json_serializable(obj):
    """递归地把大模型返回的复杂专属对象结构，转换为普通的、可以在屏幕上好看打印的字典格式"""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    elif hasattr(obj, "to_dict"):
        return obj.to_dict()
    elif hasattr(obj, "__dict__"):
        return obj.__dict__
    elif isinstance(obj, list):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    return obj


from anthropic import Anthropic # 官方提供的用来和Claude大模型对话的工具包
from dotenv import load_dotenv # 用来读取刚才我们配置的 .env 隐藏文件里的密钥

# override=True 意思是优先使用 .env 文件里的配置，覆盖电脑原本的环境变量
load_dotenv(override=True)

# ====== 第一步：准备工作与连接大模型 ======

# 如果你在 .env 里填写了 ANTHROPIC_BASE_URL (为了使用国内的大模型或者代理)
if os.getenv("ANTHROPIC_BASE_URL"):
    # 清除默认的认证 Token，防止代理服务器报错
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

# 真正初始化一个可以和大模型通信的“客户端”
# 它会自动读取刚刚加载在系统里的 ANTHROPIC_API_KEY
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))

# 取出在 .env 里写的想用的模型名字（比如 deepseek-chat 或者 claude-3-5-sonnet）
MODEL = os.environ["MODEL_ID"]

# 【系统提示词 (System Prompt)】
# 这里我们告诉它：“你是一个写代码的AI，你当前在电脑的xxx路径下。请用bash（终端）来解决问题。多做事，少废话解释。”
SYSTEM = f"You are a coding agent at {os.getcwd()}. Use bash to solve tasks. Act, don't explain."

# 【工具箱 (Tools)】
# 告诉大模型：“除了聊天，你还可以使用这些外挂工具”。
# 这里的配置明确告诉模型：你有一个叫 "bash" 的工具，它的作用是用来执行系统终端命令的。
# 并且规定了大模型如果想用这个工具，必须传给我们一个叫做"command"（也就是它想执行的命令内容）的字符串。
TOOLS = [{
    "name": "bash",
    "description": "Run a shell command.", # 描述工具作用
    "input_schema": {                      # 描述工具需要的参数格式，JSON格式
        "type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
    },
}]


# ====== 第二步：工具的真正实现：执行终端命令 ======
def run_bash(command: str) -> str:
    """运行 bash 命令行并返回输出结果"""
    # 简单的安全过滤，阻止一些高危危险命令
    dangerous = ["rm -rf", "sudo", "shutdown", "reboot", "> /dev/"]
    # 只要它想执行的命令里包含上面的关键词之一
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked" # 直接返回报错给大模型，拒绝执行
        
    try:
        # 真正执行指令的地方
        # shell=True 表示用系统的原生终端环境
        # cwd=os.getcwd() 表示在当前所在文件夹执行
        # capture_output=True 意思是拦截黑色屏幕上的输出文本，不让它直接打印在屏幕上，而是存进变量里拿回来
        # timeout=120 防止大模型写了一个死循环程序卡住不动，强制两分钟后关掉它
        r = subprocess.run(command, shell=True, cwd=os.getcwd(),
                           capture_output=True, text=True, timeout=120)
                           
        # r.stdout 是正常打印出的字，r.stderr 是报错打出的字。把它们两部分拼在一起，并去掉前后的多余空格空行
        out = (r.stdout + r.stderr).strip()
        
        # 为了防止大模型执行了一个超级长的命令（比如打印出 100 万字的文件，会把对话内容撑爆）
        # 我们只截取前 50000 个字符还给大模型去看
        return out[:50000] if out else "(no output)" # 如果啥都没打印，返回 "(no output)" 告诉大模型指令成功了但是没提示
    except subprocess.TimeoutExpired:
        # 如果超过了 120 秒，告诉大模型命令超时了
        return "Error: Timeout (120s)"


# ====== 第三步：核心灵魂——大模型的思考死循环 ======
def agent_loop(messages: list):
    """
    这是 AI 拥有“自主行动力”的关键循环。
    参数 messages：就是一个装着你和AI所有历史聊天记录的history。
    """
    while True: # 开始死循环
    
        # 打印即将发给大模型的完整消息请求（包含所有可供大模型读取的参数）
        # print(f"\n\033[96m{'='*20} [1] 准备发给大模型的完整请求负载 (Request Payload) {'='*20}\033[0m")
        # request_payload = {
        #     "model": MODEL,
        #     "system": SYSTEM,
        #     "tools": TOOLS,
        #     "messages": messages
        # }
        # print(json.dumps(make_json_serializable(request_payload), indent=2, ensure_ascii=False))
        # print(f"\033[96m{'='*88}\033[0m\n")

        # 步骤 1：发消息给大模型（已改写为最简流式输出）
        # 利用 Anthropic 新版的 stream 管理器，自动处理最棘手的工具块拼接
        print("\033[92mAssistant: \033[0m", end="", flush=True)
        with client.messages.stream(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        ) as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)
        print() # 打完字后换行
        
        # 退出流式上下文后，直接获取后台帮我们拼接组装好的完整的回复对象
        response = stream.get_final_message()
        
        # 步骤 2：收到大模型的回复，将大模型的回复追加到messages消息历史中（以 Assistant 角色）
        # 这样下一次发给它时，它才能想起来自己刚才说过啥
        
        # 结构化打印大模型的原始回复对象
        # print(f"\n\033[95m{'='*20} [2] 大模型的思考决定与回复对象 (LLM Response) {'='*20}\033[0m")
        # print(json.dumps(make_json_serializable(response), indent=2, ensure_ascii=False))
        # print(f"\033[95m{'='*80}\033[0m\n")

        # 将大模型的回复追加进历史记录小本本里
        messages.append({"role": "assistant", "content": response.content})
        
        # 步骤 3：判断大模型要干嘛
        # 看看大模型停止思考的原因（stop_reason）是什么。
        # 如果不是 "tool_use" (我想调用工具)，说明大模型觉得自己干完活了，想直接回复人类了，不想调工具了。
        if response.stop_reason != "tool_use":
            return # 结束死循环，任务完美通过！
            
        # 步骤 4：走到这里，说明大模型主动想调用工具了！
        # 现实中它可能一次性连着调用好几个工具，所以我们建个列表 results 来保存每一个工具执行完的结果
        results = []
        for block in response.content:
            # 在它给的一堆回复段落里，挑出真正属于“工具调用”类型的数据
            if block.type == "tool_use":
                
                # 打印大模型打算调用的工具名字和参数
                command_to_run = block.input.get('command', '')
                print(f"\n\033[33m{'='*20} [3] 即将开始执行您的系统工具: bash {'='*20}\033[0m")
                print(f"\033[33m提取到的命令行参数 (Command): \n{command_to_run}\033[0m")
                print(f"\033[33m{'='*72}\033[0m\n")
                
                #拦截并询问人类用户是否授权
                user_approval = input(f"\033[31m[权限请求] 申请在你的电脑执行上方命令。\n按【回车键 (Enter)】同意执行，输入【其他字符】拒绝执行: \033[0m").strip()
                
                if user_approval == "":
                    # 人类按了回车，同意执行
                    # ==== 调起我们上面写好的那个真正去执行命令的 run_bash 函数！ ====
                    output = run_bash(command_to_run)
                else:
                    # 人类拒绝执行，直接伪造一个人工打断的报错结果，准备还给大模型
                    print("\n\033[31m[!] 您已拒绝执行此命令，正将拒绝结果返回给大模型...\033[0m")
                    output = "Error: Human user rejected and denied permission to run this command."
                
                # 打印工具在电脑上真实跑出来的长篇结果（不再截断，全部打印）
                print(f"\n\033[32m{'='*20} [4] 工具底层的真实执行输出结果 (Bash Output) {'='*20}\033[0m")
                print(f"\033[32m{output}\033[0m")
                print(f"\033[32m{'='*80}\033[0m\n")
                
                # 大模型要求的格式比较严格，我们需要把我们跑出来的真实结果打包成它认识的特定格式
                # 必须带上 tool_use_id 告诉它，这个结果是你刚才哪次调用产生的
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": output})
                                
        # 步骤 5：极其核心的一步！（模拟记忆）
        # 把刚才终端真实的执行结果 results，假装成是 用户(User) 说的话，追加写进那个历史小本本列表里。
        # 接着代码又回到了 while True 循环的开头，大模型的下一次请求由于包含了这个新追加的由于执行工具产生的历史消息，
        # 大模型一看到这个新加的结果，就会说：
        # “哦原来刚才用 bash 命令执行成了这样，接下来我该做下一步啦”
        messages.append({"role": "user", "content": results})
        
        # 结构化打印因为调用了工具而产生的执行结果反馈（作为 User 角色发回）
        # print(f"\n\033[93m{'='*20} [5] 工具结果已伪装成 User 打包好，准备作为历史再次喂给大模型 (Tool Results) {'='*20}\033[0m")
        # print(json.dumps(make_json_serializable(results), indent=2, ensure_ascii=False))
        # print(f"\033[93m{'='*98}\033[0m\n")


if __name__ == "__main__":
    # 初始化消息历史
    history = []
    
    # 又是一个死循环：这里是你（人类）与 AI 对话的轮次循环
    while True:
        try:
            # 在终端打印一个青色的提示符 "s01 >> "，然后卡在这里，等待你敲击键盘回车输入
            query = input("\033[36ms01 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            # 检测 Ctrl+C 强制打断，程序就能优雅地跳出死循环结束，不会红字报错
            break
            
        # 如果你敲了 q、exit 或者啥也没输入直接回车，也是结束退出代码
        if query.strip().lower() in ("q", "exit", ""):
            break
            
        # 将用户的输入作为 User 消息追加到历史中
        history.append({"role": "user", "content": query})
        
        # 启动 Agent 循环处理用户的请求，直到大模型给出最终结果
        agent_loop(history)
        
        # （这部分删除：因为我们在上面开启了流式输出，文字已经一点点像打字机一样打印在终端上了。
        # 这里只需要打印一个结束风格线即可。）
        print("\n\033[36m===============end conversation===============\033[0m\n\n")
