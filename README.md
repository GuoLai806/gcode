# GCode - 终端 AI 编程助手

一个功能丰富、架构清晰的终端 AI 编码助手，从零构建，深度学习 Agent 架构。

## 本轮工程升级（2026-11-06）

主任务与子任务使用同一 Agent 执行循环；执行目录通过任务局部上下文传递，权限检查与文件 I/O 使用同一路径。运行、共享任务、邮箱、工具回执及 token 用量写入 SQLite WAL。结果不明的写操作会保留回执并停止后续写入，重启不自动重放。恢复核对入口为 `python -m gcode.runtime.recover --help`。

压缩先保存完整原始历史和检查点，再替换上下文投影。摘要必须正常结束并包含九个有序非空部分；真实用户段落按最后一次出现的顺序保留，超过 30,000 字符时拒绝压缩并保留原历史。格式检查不能证明摘要语义完整，原始历史仍需保留。大工具结果按 SHA-256 保存，Bash stdout/stderr 流式落盘，工件清理目前只生成计划。

父子共享 token 预算，缺失 provider 用量会暂停后续请求；预算检查发生在请求之间，不是对在途请求的硬限额。子任务继承父权限上限，工具与文件缓存独立；没有可验证授权传递的终端队友暂时拒绝启动。Worktree 清理要求登记并封存的进程清单、退出确认和重新校验过的清理计划，自动清理关闭。这些是应用层约束，不构成操作系统沙箱。

可选本机 Computer Use 使用独立编写的 stdio sidecar。它不会捆绑 Pi 私有源码或原生程序，使用者须显式配置自己可用的本机桥；默认只读，子任务不开放桌面写入。实际完成过一项真实模型只读定位，以及两次恢复原状的界面切换；尚无完整跨应用任务成功率或速度 A/B 结论。配置与边界见 [CU 使用说明](docs/development/reliable-harness-20261105/cu-setup.md)。

```sh
gcode --max-total-tokens 1000000
gcode -p "读取当前项目并给出修改建议" --max-total-tokens 100000
gcode --cu-config /absolute/path/to/private-cu-config.json
```

详细决定、测试、迁移和回退见 [用户版交付说明](docs/development/reliable-harness-20261105/PLAN-FOR-YOU.md) 与 [执行版](docs/development/reliable-harness-20261105/PLAN-FOR-AI.md)。旧功能列表描述原有接口，不代表三种团队后端或每种操作系统均完成本轮验收。

## 特性

### 智能 Agent 系统
- **ReAct 范式实现**：Think -> Act -> Observe 循环，让 AI 自主思考和行动
- **多轮对话管理**：完整的对话历史、上下文压缩、长期记忆
- **流式响应**：实时看到 AI 的思考过程和工具调用

### 强大的工具系统
- **6 大内置工具**：ReadFile、WriteFile、EditFile、Bash、Glob、Grep
- **Function Calling 协议**：标准化的工具调用接口
- **MCP 集成**：支持 Model Context Protocol，接入外部工具生态
- **技能系统**：可扩展的自定义技能包（Skill）

### 多 Agent 协作
- **子任务分发**：SubAgent 独立执行子任务，隔离上下文
- **团队协作模式**：多 Agent 并行工作，共享任务列表和消息邮箱
- **团队执行后端**：当前加固与验收针对 In-process；终端后端缺少授权传递时拒绝启动
- **Git Worktree 隔离**：可选独立分支；创建与清理均校验状态

### 权限检查

显式拒绝规则优先；危险命令和路径范围检查之后处理 Plan 模式约束，再判断明确允许、极小的准确命令集合和权限模式。需要交互确认而无法向用户确认的后台任务会拒绝执行。`awk`、`find -exec`、`sed -i`、`xargs`、`tee`、`npx` 等不因命令前缀自动放行。应用层规则不构成操作系统沙箱。

### 智能上下文管理
- **两层压缩策略**
  - 第 1 层：大结果存磁盘（几乎零损失）
  - 第 2 层：摘要旧消息 + 保留近期原文（中等损失）
- **决策冻结机制**：同一历史只生成一次结果投影，避免反复截断引起前缀漂移；成本效果需独立测量
- **Token 预算管理**：单条 50K 字符限制，聚合 200K 字符上限

## 快速开始

### 环境要求

- Python >= 3.11
- 当前加固路径需要 POSIX 文件锁与进程组；本轮实测 macOS Apple Silicon。Linux 未完成本轮验收，Windows 需要平台适配。

### 安装

```bash
# 克隆项目
git clone https://github.com/GuoLai806/gcode.git
cd gcode

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -e .

# 验证安装
gcode --help
```

### 配置

编辑 `~/.gcode/config.yaml`：

```yaml
providers:
  - name: my-provider
    protocol: openai-compat  # 或 anthropic / openai
    base_url: https://your-api-endpoint/v1
    api_key: "your-api-key"
    model: "your-model-name"

permission_mode: default  # default / accept-edits / plan / bypass
```

### 启动

```bash
# 启动交互式终端
gcode
```

## 架构设计

### 五层架构

```
+-------------------------------------+
|           交互层 (Interaction)       |
|        Textual TUI / 命令行界面      |
+-------------------------------------+
|          对话层 (Conversation)       |
|   消息管理 / 上下文压缩 / 记忆系统   |
+-------------------------------------+
|            引擎层 (Engine)           |
|    Agent Loop / ReAct 循环 / 事件流 |
+-------------------------------------+
|            工具层 (Tools)            |
|   内置工具 / MCP 适配器 / 技能系统   |
+-------------------------------------+
|            安全层 (Security)         |
|   权限检查 / 路径沙箱 / 命令过滤     |
+-------------------------------------+
```

### 核心循环：Agent Loop

```python
async def run(self, conversation) -> AsyncIterator[AgentEvent]:
    while True:
        iteration += 1

        # 1. turn_start hook
        # 2. 消费通知队列
        # 3. 自动上下文压缩
        # 4. pre_send hook
        # 5. 构建系统提示词
        # 6. Plan Mode 注入
        # 7. 获取工具 schema，调 LLM
        # 8. 消费流式响应
        # 9. max_tokens 恢复
        # 10. 没有工具调用 -> 结束
        # 11. 分批执行工具
        # 12. 连续未知工具检查
        # 13. turn_end hook
```

### 目录结构

```
gcode/
├── agent.py              # Agent 核心逻辑与主循环
├── app.py                # Textual TUI 应用入口
├── client.py             # LLM 客户端适配
├── config.py             # 配置管理
├── conversation.py       # 对话管理与序列化
│
├── permissions/          # 权限系统
│   ├── checker.py        # 权限检查器（5层防御链）
│   ├── dangerous.py      # 危险命令检测
│   ├── modes.py          # 权限模式矩阵
│   ├── rules.py          # 规则引擎
│   └── sandbox.py        # PathSandbox 路径检查
│
├── tools/                # 工具系统
│   ├── base.py           # Tool 抽象基类
│   ├── __init__.py       # ToolRegistry 注册中心
│   ├── read_file.py      # 文件读取
│   ├── write_file.py     # 文件写入
│   ├── edit_file.py      # 文件编辑
│   ├── bash.py           # 命令执行
│   ├── glob.py           # 文件搜索
│   └── grep.py           # 内容搜索
│
├── context/              # 上下文管理
│   └── manager.py        # 两层压缩 + 决策冻结
│
├── teams/                # 多 Agent 团队
│   ├── manager.py        # 团队生命周期管理
│   ├── mailbox.py        # 异步消息通信
│   ├── coordinator.py    # Lead 协调者模式
│   ├── spawn_tmux.py     # Tmux 后端
│   └── spawn_inprocess.py # 进程内后端
│
├── skills/               # 技能系统
│   ├── loader.py         # Skill 加载器
│   ├── executor.py       # 执行器（inline/fork）
│   └── builtins/         # 内置技能
│
├── hooks/                # Hook 系统
│   ├── engine.py         # Hook 引擎
│   ├── conditions.py     # 条件匹配
│   └── executors.py      # 执行器
│
├── mcp/                  # MCP 协议
│   ├── client.py         # MCP 客户端
│   ├── manager.py        # 服务器管理
│   └── tool_wrapper.py   # 工具包装器
│
├── memory/               # 记忆系统
│   ├── auto_memory.py    # 自动记忆提取
│   ├── recall.py         # 记忆检索
│   └── session.py        # 会话持久化
│
├── commands/             # 命令系统
│   ├── registry.py       # 命令注册中心
│   └── handlers/         # 命令处理器
│
└── worktree/             # Git 工作树
    ├── manager.py        # Worktree 管理
    └── session.py        # 会话隔离
```

## 核心模块详解

### 1. Agent Loop 与 ReAct 范式
- **文件**: `gcode/agent.py`
- **原理**: 基于 ReAct（Reasoning + Acting）范式的自主循环
- **特点**: async generator 事件流驱动、StreamCollector 解耦流消费逻辑、4 种停止条件

### 2. 工具注册与执行框架
- **目录**: `gcode/tools/`
- **设计**: ABC 抽象基类 + Pydantic 参数校验、Schema 自动生成、Registry 注册中心

### 3. 五层权限防御链
- **目录**: `gcode/permissions/`
- **层级**: Plan Mode 例外 -> 安全白名单 -> 危险黑名单 -> PathSandbox -> 规则引擎 -> HITL 确认

### 4. 上下文压缩与溢写
- **文件**: `gcode/context/manager.py`
- **策略**: Layer 1 单条 >50KB 存盘 + Layer 2 Auto-Compact 摘要旧消息

### 5. 多 Agent 团队协作
- **目录**: `gcode/teams/`
- **模式**: SubAgent 星型拓扑 + Agent Team 网状结构
- **后端**: Tmux / iTerm2 / In-process 自动检测

### 6. System Prompt 组装管线
- **文件**: `gcode/prompts/system_prompt.py`
- **结构**: 7 段固定段落 + 3 段条件段落 + Hook 注入

### 7. MCP 协议集成
- **目录**: `gcode/mcp/`
- **支持**: stdio 和 streamable HTTP 两种传输模式

### 8. 技能系统（Skill）
- **目录**: `gcode/skills/`
- **模式**: inline（直接执行）/ fork（子进程执行）

## 配置说明

### 配置文件位置
- 全局配置：`~/.gcode/config.yaml`
- 项目配置：`.gcode/config.yaml`（项目根目录）
- 本地权限规则：`.gcode/permissions.local.yaml`

### 完整配置示例

```yaml
providers:
  - name: doubao
    protocol: openai-compat
    base_url: https://ark.cn-beijing.volces.com/api/coding/v3
    api_key: "your-api-key"
    model: Doubao-Seed-2.0-Code

permission_mode: default

mcp_servers:
  - name: context7
    command: npx
    args: ["-y", "@upstash/context7-mcp"]
```

### 权限模式说明

| 模式 | 读操作 | 写操作 | 命令执行 | 适用场景 |
|------|--------|--------|----------|----------|
| `default` | 自动放行 | 需确认 | 需确认 | 日常使用 |
| `accept_edits` | 自动放行 | 自动放行 | 需确认 | 快速迭代 |
| `plan` | 自动放行 | 需确认 | 需确认 | 计划模式 |
| `bypass` | 自动放行 | 自动放行 | 自动放行 | 信任环境 |

## 技术栈

| 类别 | 技术 | 版本要求 |
|------|------|----------|
| 语言 | Python | >= 3.11 |
| TUI 框架 | Textual | >= 2.1.0 |
| LLM SDK | Anthropic | >= 0.42.0 |
| LLM SDK | OpenAI | >= 1.60.0 |
| 数据验证 | Pydantic | >= 2.0 |
| 配置解析 | PyYAML | >= 6.0 |
| HTTP 客户端 | httpx | >= 0.27.0 |
| MCP 协议 | mcp | >= 1.12.0 |

## 开发指南

### 代码规范
- **语言版本**: Python 3.11+
- **类型标注**: PEP 604 语法（`X | Y` 而非 `Union[X, Y]`）
- **命名风格**: snake_case（变量/函数）、PascalCase（类）、UPPER_CASE（常量）
- **异步编程**: 全面使用 asyncio，避免同步阻塞

### 运行测试

```bash
pip install -e ".[dev]"
pytest
```
