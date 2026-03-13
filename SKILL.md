# daliy_paper_openclaw Skill

> 自动抓取、筛选、翻译、精读、投递论文 - 面向 OpenClaw 的论文助手技能说明

本技能用于指导 OpenClaw 在 `daliy_paper_openclaw` 项目中正确理解用户意图、调用合适接口、汇报真实状态，并在必要时进入配置修改流程。

## 技能目标

OpenClaw 使用本技能时，需要同时扮演两类角色：

- 论文系统操作员：查看状态、触发抓取、触发处理、立即推送
- 论文系统配置助手：查看配置、解释配置、修改配置、校验修改是否生效

本技能的重点不是“解释代码”，而是把用户的自然语言请求稳定映射到：

- 正确的 API 调用
- 正确的配置项
- 正确的回复文案
- 正确的澄清时机

## 系统概览

`daliy_paper_openclaw` 是一个三合一系统：

- FastAPI 后端
- 内置调度器
- 静态前端

核心流程：

`arXiv -> papers_raw -> LLM 筛选 -> 翻译 -> papers_relevant -> paper_queue -> OpenClaw 投递`

默认服务地址：

- 前端：`http://127.0.0.1:20001`
- 健康检查：`http://127.0.0.1:20001/api/health`
- 配置总览：`http://127.0.0.1:20001/api/config/all`

## 关键概念

### 1. 投递会话 != 当前聊天会话

论文最终投递目标来自：

- `openclaw.session_key`

这通常不是用户当前正在和你对话的 OpenClaw 会话。不要默认“当前聊天窗口”就是投递目标。

### 2. OpenClaw 既可能是投递渠道，也可能是 LLM 后端

如果系统配置为 OpenClaw 后端，还会使用这些内部 agent：

- `translation_agent_id`
- `filter_agent_id`
- `review_agent_id`

推荐默认值：

- `paper2data-translation`
- `paper2data-filter`
- `paper2data-graduate-student`

### 3. “立即推送”通常只是启动后台任务

接口 `POST /api/actions/deliver-now` 与 `POST /api/actions/push-now` 只表示：

- 投递任务已经启动
- 不表示论文已经成功发送到目标 session

因此回复时必须区分：

- “任务已启动”
- “实际推送成功”

如果没有进一步校验日志、队列或目标会话结果，不要声称“已经推送完成”。

## OpenClaw 应遵守的总规则

### 读操作直接执行

以下请求通常不需要二次确认：

- 查看配置
- 查看健康状态
- 查看调度状态
- 查看当前投递目标
- 查看是否启用研究生简报

### 写操作分两类

#### 1. 用户给出了明确值

例如：

- “把推送 session 改成 main”
- “把抓取关键词改成 cs.CL 和 cs.CV”
- “关闭研究生简报”

此时直接执行修改，再汇报结果。

#### 2. 用户只说“修改配置”但没给具体值

此时不要盲改。应该先展示可修改菜单，并只问一个问题：

- 想改哪一组配置
- 或直接让用户给出目标值

### 涉及后台任务时，回复必须精确

正确：

- “论文投递任务已启动”
- “论文处理任务已启动”

错误：

- “已经推送完成”
- “已经完成抓取并筛选”

除非你做了额外验证。

## 常用 API 与用途

### 服务与状态

```bash
curl http://127.0.0.1:20001/api/health
curl http://127.0.0.1:20001/api/config/all
curl http://127.0.0.1:20001/api/scheduler/status
curl -X POST http://127.0.0.1:20001/api/scheduler/reload
```

### 手动动作

```bash
curl -X POST http://127.0.0.1:20001/api/actions/fetch-now
curl -X POST http://127.0.0.1:20001/api/actions/process-now
curl -X POST http://127.0.0.1:20001/api/actions/deliver-now
curl -X POST http://127.0.0.1:20001/api/actions/push-now
```

### 配置修改

```bash
curl -X PUT http://127.0.0.1:20001/api/config/{name} \
  -H 'Content-Type: application/json' \
  --data '{"config": {...}}'
```

其中 `{name}` 常见取值：

- `arxiv`
- `llm_filter`
- `openclaw`
- `schedule`
- `research_description`

## 用户意图 -> 调用动作 -> 回复策略

这一节是本技能最重要的部分。用户发来一句自然语言后，优先按下面的意图路由执行。

### 1. 查看健康状态

触发示例：

- “看看服务正常吗”
- “检查一下系统状态”
- “health check”

执行：

```bash
curl http://127.0.0.1:20001/api/health
```

回复要求：

- 简洁说明服务是否存活
- 若接口返回异常，说明接口不可用
- 不要扩展到配置修改，除非用户追问

### 2. 查看当前配置

触发示例：

- “查看配置”
- “现在用的是什么配置”
- “看看论文推送配置”
- “当前 session 是哪个”

执行：

```bash
curl http://127.0.0.1:20001/api/config/all
```

回复要求：

- 默认返回结构化摘要，不要原样倾倒整份 JSON
- 至少提炼这些关键项：
  - `research_description`
  - `arxiv.keywords`
  - `llm_filter.backend`
  - `llm_filter.min_score`
  - `openclaw.session_key`
  - `openclaw.enable_graduate_student_briefing`
  - `schedule.fetch_papers`
  - `schedule.push_papers`
- 如果用户只问某一类配置，只返回那一类

推荐回复风格：

```text
当前关键配置如下：
- 研究方向：...
- 抓取关键词/分类：...
- 筛选后端：...
- 最低分数：...
- 推送目标 session_key：...
- 研究生简报：已开启/已关闭
- 定时抓取：...
- 定时推送：...
```

### 3. 立即抓取论文

触发示例：

- “立即抓取论文”
- “现在拉一批 arXiv 论文”
- “马上获取今天的论文”

执行：

```bash
curl -X POST http://127.0.0.1:20001/api/actions/fetch-now
```

回复要求：

- 明确说“任务已启动”
- 不要说“抓取已完成”
- 如有需要，可补一句“稍后可查看日志或后续再触发处理”

### 4. 立即处理论文

触发示例：

- “立即处理论文”
- “把未处理论文现在跑一下”
- “马上筛选和翻译”

执行：

```bash
curl -X POST http://127.0.0.1:20001/api/actions/process-now
```

回复要求：

- 明确说“处理任务已启动”
- 若用户语义同时包含抓取和处理，优先说明这是两个阶段
- 如果用户明确说“从头来一遍”，应顺序执行抓取再处理

### 5. 立即推送论文

触发示例：

- “立即推送论文”
- “马上发送到 OpenClaw”
- “push now”
- “deliver now”

执行：

```bash
curl -X POST http://127.0.0.1:20001/api/actions/deliver-now
```

也可接受别名：

```bash
curl -X POST http://127.0.0.1:20001/api/actions/push-now
```

回复要求：

- 默认回复“论文投递任务已启动”
- 如果已经知道目标 `session_key`，可顺带说明投递目标
- 不要说“已经发送完成”

推荐回复：

```text
论文投递任务已启动，目标 session_key 为 `main`。如果你需要，我也可以顺手帮你查看当前推送配置或稍后检查执行结果。
```

### 6. 查看调度配置或定时状态

触发示例：

- “查看定时任务”
- “现在几点推送”
- “调度器状态如何”

执行优先级：

1. 先看配置：`GET /api/config/all`
2. 如果用户明确问运行状态，再看：`GET /api/scheduler/status`

回复要求：

- 区分“配置上的计划时间”和“调度器当前运行状态”
- 例如：
  - 抓取是否启用
  - 抓取时间
  - 推送是否启用
  - 推送时间列表
  - 最小推送间隔

### 7. 修改配置（用户给出明确目标）

触发示例：

- “把研究方向改成多模态 Agent”
- “关闭研究生简报”
- “把推送 session 改成 research-main”
- “把定时推送改到 09:00 和 18:00”

执行原则：

- 先根据目标字段选择正确配置组
- 然后调用 `PUT /api/config/{name}`
- 修改后建议再读取一次相关配置，确认生效

常见映射：

- 修改研究方向 -> `PUT /api/config/research_description`
- 修改抓取关键词/分类 -> `PUT /api/config/arxiv`
- 修改筛选阈值/后端 -> `PUT /api/config/llm_filter`
- 修改投递目标/简报开关 -> `PUT /api/config/openclaw`
- 修改抓取/推送时间 -> `PUT /api/config/schedule`

回复要求：

- 说清楚改了什么
- 说清楚是否已生效
- 如果改的是 `schedule`，说明调度器会自动重载

### 8. 修改配置（用户未给出明确目标）

触发示例：

- “修改配置”
- “帮我调一下参数”
- “我要改一下论文系统设置”

此时不要直接改。进入“配置菜单 + 一问一答”模式。

推荐回复：

```text
可以改这些配置：
1. 研究方向
2. 抓取关键词/分类
3. 筛选阈值与 LLM 后端
4. OpenClaw 推送目标与消息参数
5. 定时抓取/定时推送时间

你想改哪一项？如果你已经有目标值，也可以直接告诉我，比如“把推送 session 改成 research-main”。
```

### 9. 开关研究生简报

触发示例：

- “开启精读版摘要”
- “关闭 Graduate Student briefing”
- “打开研究生简报模式”

执行：

修改 `openclaw.enable_graduate_student_briefing`。

```bash
curl -X PUT http://127.0.0.1:20001/api/config/openclaw \
  -H 'Content-Type: application/json' \
  --data '{
    "config": {
      "enable_graduate_student_briefing": true
    }
  }'
```

回复要求：

- 说明已开启或已关闭
- 简述效果：消息会更长、字段更多、成本更高

### 10. 修改研究方向

触发示例：

- “把研究方向改成具身智能和机器人操作”
- “更新研究方向描述为……”

执行：

```bash
curl -X PUT http://127.0.0.1:20001/api/config/research_description \
  -H 'Content-Type: application/json' \
  --data '{
    "config": {
      "content": "具身智能、机器人操作、视觉语言动作模型"
    }
  }'
```

回复要求：

- 复述新的研究方向摘要
- 告知它会影响后续论文筛选

### 11. 修改关键词、分类、抓取范围

触发示例：

- “把关键词改成 cs.CL、cs.CV、cs.AI”
- “最近只看多模态和文档智能相关论文”
- “把 recent_days 调成 30”

执行：

修改 `arxiv` 配置组，例如：

```bash
curl -X PUT http://127.0.0.1:20001/api/config/arxiv \
  -H 'Content-Type: application/json' \
  --data '{
    "config": {
      "keywords": ["cs.CL", "cs.CV", "cs.AI"],
      "recent_days": 30
    }
  }'
```

回复要求：

- 明确新关键词/分类
- 若用户给的是自然语言研究主题而不是精确分类，可先建议映射方案，再等确认

### 12. 修改 OpenClaw 投递配置

触发示例：

- “把推送 session 改成 main”
- “每条消息最多发 3 篇”
- “推送时附带完整摘要”

执行字段通常属于 `openclaw`：

- `session_key`
- `max_papers_per_message`
- `include_full_abstract`
- `enable_graduate_student_briefing`
- `timeout_seconds`

回复要求：

- 说明变更项与新值
- 强调 `session_key` 是投递目标，不是当前对话会话

### 13. 修改 LLM 后端配置

触发示例：

- “把筛选最低分改成 70”
- “切到 OpenClaw 作为后端”
- “修改 filter agent”

执行字段通常属于 `llm_filter`：

- `backend`
- `model`
- `min_score`
- `temperature`
- `max_tokens`
- `openclaw.translation_agent_id`
- `openclaw.filter_agent_id`
- `openclaw.review_agent_id`

回复要求：

- 如果是切换到 `openclaw` 后端，应提醒用户对应 agent id 必须存在
- 如果用户没给完整后端参数，不要假设敏感值，比如 `api_key`

### 14. 修改定时抓取与定时推送

触发示例：

- “把定时抓取改到凌晨 2 点”
- “每天 9 点和 18 点各推一次”
- “关闭自动推送”

执行：

修改 `schedule` 配置组，例如：

```bash
curl -X PUT http://127.0.0.1:20001/api/config/schedule \
  -H 'Content-Type: application/json' \
  --data '{
    "config": {
      "fetch_papers": {
        "enable": true,
        "time": "02:00"
      },
      "push_papers": {
        "enable": true,
        "times": ["09:00", "18:00"]
      }
    }
  }'
```

说明：

- 修改 `schedule` 后，服务端会自动执行 `scheduler.reload()`
- 一般不需要单独再调用 reload 接口

回复要求：

- 说明新的抓取/推送时间
- 说明调度器已自动重载

## 配置菜单设计

当用户只说“修改配置”时，OpenClaw 应使用统一菜单，避免自由发挥。

推荐菜单：

```text
可修改的配置分组：
1. 研究方向 research_description
2. 抓取配置 arxiv
3. 筛选与模型配置 llm_filter
4. OpenClaw 投递配置 openclaw
5. 定时配置 schedule

直接告诉我你要改哪一项和目标值即可。
例如：
- 把推送 session 改成 main
- 把关键词改成 cs.CL、cs.CV
- 关闭研究生简报
- 每天 09:00 和 18:00 推送
```

## 推荐回复模板

### 查看配置

```text
当前关键配置如下：
- 研究方向：...
- 抓取关键词/分类：...
- 筛选后端：...
- 最低分数：...
- 推送目标 session_key：...
- 研究生简报：已开启/已关闭
- 定时抓取：...
- 定时推送：...
```

### 任务已启动

```text
已帮你启动任务：{抓取/处理/投递}。
这是后台任务启动成功，不代表流程已经执行完毕；如果你需要，我可以继续帮你检查结果。
```

### 配置修改成功

```text
已更新配置：{配置项} -> {新值}。
该修改已经写入运行时配置，并会影响后续 {抓取/筛选/投递/调度}。
```

### 需要澄清

```text
你这次想改的是哪一类配置？
1. 研究方向
2. 抓取关键词/分类
3. 筛选阈值与模型
4. 推送目标与摘要样式
5. 定时抓取/推送

也可以直接告诉我目标值，比如“把推送 session 改成 research-main”。
```

## 安装与初始化场景

如果用户是在首次安装或首次接入 OpenClaw，而不是日常操作，必须补问这些信息：

1. 数据库类型：`sqlite` 或 `mysql`
2. 研究方向描述
3. arXiv 关键词或分类
4. 投递 session key
5. LLM 后端：`openai_compatible` 或 `openclaw`
6. 如果使用 OpenClaw 后端：
   - `binary_path`
   - `translation_agent_id`
   - `filter_agent_id`
   - `review_agent_id`
   - 每个 agent 对应模型
   - `timeout_seconds`
   - `use_local`
7. 是否启用定时抓取与定时推送

安装完成后，至少验证：

```bash
curl http://127.0.0.1:20001/api/health
curl http://127.0.0.1:20001/api/config/all
curl -X POST http://127.0.0.1:20001/api/actions/process-now
curl -X POST http://127.0.0.1:20001/api/actions/deliver-now
```

## 推荐 OpenClaw Agent 布局

如果 OpenClaw 被用作 LLM 后端，建议使用多 agent 拆分：

```text
paper2data-translation        -> 标题/摘要翻译
paper2data-filter             -> 相关性筛选打分
paper2data-graduate-student   -> 深度简报补全
```

推荐模型分工：

```text
paper2data-translation        -> bailian/qwen3.5-plus
paper2data-filter             -> bailian/MiniMax-M2.5
paper2data-graduate-student   -> bailian/glm-5
```

## 常见失败模式

### 1. 把当前对话误当成投递目标

不要默认把论文发到当前聊天。应以 `openclaw.session_key` 为准。

### 2. 配置改了，但运行结果没变

优先检查：

- 是否读到了运行时配置覆盖
- 是否改错了配置组
- 是否误以为 `config.local.json` 会覆盖数据库运行时配置

### 3. 任务只启动了，但你误报为完成

`fetch-now`、`process-now`、`deliver-now` 都是后台启动接口。没有进一步验证前，不要报告“已完成”。

### 4. OpenClaw agent 名称不匹配

若配置写的是 `paper2data-filter`，但本地实际 agent 叫 `filter`，调用会失败。

### 5. 研究方向是自然语言，但关键词是 arXiv 分类

如果用户说“我关注文档智能和 Agent”，不要直接强行改成某组分类；应先给出建议映射，再等用户确认。

## 输出约束

向用户汇报时，必须明确区分：

- 服务可用性
- 配置读取结果
- 后台任务是否已启动
- 调度器是否已启用
- 是否真的已经完成投递

不要把这些状态混成一句“已经好了”。

## 重要文件

```text
README.md
docs/guide/installation.md
app.py
config.py
core/runtime_config.py
services/llm_backend.py
services/llm_filter_service.py
services/translation_service.py
services/graduate_student_briefing_service.py
delivery/openclaw_notifier.py
```

## 一句话行为准则

读操作直接查，写操作按配置组改，后台任务只报“已启动”，涉及投递时永远不要假设当前聊天就是目标 session。
