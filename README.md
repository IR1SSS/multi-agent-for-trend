# Multi-Agent for Trend

**领域无关的通用社媒趋势洞察系统** — 通过元数据驱动 + 可插拔 Skill 架构，将任意领域的社交媒体高噪声内容转化为结构化趋势信号，支持零代码切换领域。

## 核心亮点

- **通用领域适配**：系统不再绑定任何特定行业。用户创建新领域时，只需提供自然语言描述，LLM 自动推断关键词扩展层级、实体提取 Schema、洞察报告格式，实现零配置领域切换。
- **元数据驱动 + 可插拔 Skill**：三大核心 Skill（Expander / Cleaning / Insight）均采用策略模式，通过 `domain_config` 中的 `strategy` 字段动态选择执行策略。内置 `adaptive` 策略可让 LLM 自行推断最佳处理方式，无需人工编写领域规则。
- **LLM 全链路驱动**：从关键词扩展 → 内容清洗 → 趋势洞察，全流程由 LLM 驱动，结合 LLM-as-a-Judge 质量闸门确保输出质量。
- **多平台社媒采集**：集成 MediaCrawler，支持小红书、抖音、Bilibili、微博等主流平台，爬取平台由用户在启动 Pipeline 时自主选择。
- **领域动态隔离**：所有任务携带 `domain_id` 标签，数据库层面实现多领域逻辑隔离，支持多租户并行。

## 技术路线

```
┌─────────────────────────────────────────────────────────────────┐
│                    用户创建领域 + 描述                           │
│         (前端 Domain Management / API / JSON 配置)              │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              领域配置解析器 (Domain Config Parser)               │
│    解析 domain_config → ResolvedDomainConfig (强类型校验)       │
└──────────┬────────────────┬─────────────────┬──────────────────┘
           ▼                ▼                 ▼
  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
  │ Expander Skill │ │ Cleaning Skill │ │ Insight Skill  │
  ├────────────────┤ ├────────────────┤ ├────────────────┤
  │ adaptive       │ │ adaptive       │ │ adaptive       │
  │ hierarchical   │ │ ontology_cleaner│ │ statistics     │
  │ tech_term      │ │ judge (质量闸门)│ │ report_generator│
  └────────────────┘ └────────────────┘ └────────────────┘
           │                │                 │
           ▼                ▼                 ▼
  LLM 自动推断扩展层级  LLM 自动推断实体Schema  LLM 自动推断报告格式
```

### Adaptive 策略 — 零配置通用化的关键

当 `strategy = "adaptive"` 时，Skill 会在 system prompt 中注入领域的 `domain_description`，由 LLM 自行推断：

| Skill | LLM 自动推断内容 |
|-------|----------------|
| **Expander** | 最佳扩展层级（如美妆→品类/成分/痛点；汽车→车型/技术/场景） |
| **Cleaning** | 应提取的实体字段（如美妆→成分/肤感/功效；汽车→品牌/车型/续航） |
| **Insight** | 分析框架与报告格式（如美妆→成分合规趋势；汽车→技术成熟度曲线） |

推断结果可回写到 `domain_config`，后续运行直接复用。

## 系统架构

```
用户创建领域 (domain_name + domain_description)
  → KeywordGenerator: LLM 自动生成种子关键词
  → KeywordExpanderAgent: adaptive 扩展关键词层级
  → CrawlerAgent: 用户选择平台，调用 MediaCrawler 爬取
  → CleaningAgent: adaptive 清洗 + LLM-as-a-Judge 质量闸门
  → InsightAgent: adaptive 统计分析 + LLM 报告生成
```

### Agent 职责

| Agent | 职责 |
|-------|------|
| `KeywordExpanderAgent` | 基于 domain_config 中的 strategy 选择 Expander Skill，将种子关键词扩展为平台适配的搜索词 |
| `CrawlerAgent` | 调用 MediaCrawler 在用户指定的平台上执行爬取 |
| `CleaningAgent` | 使用 LLM 清洗原始内容，根据 strategy 选择 Cleaning Skill，支持 LLM-as-a-Judge 质量闸门 |
| `InsightAgent` | 根据 strategy 选择 Insight Skill，进行统计分析、异常检测和趋势报告生成 |

## 技术栈

### 后端与 Agent 编排
- Python 3.10+ / FastAPI / Uvicorn
- Celery / Redis
- PostgreSQL / SQLAlchemy AsyncIO / Alembic
- Pydantic / Pydantic Settings
- OpenAI-compatible SDK

### 领域元数据引擎
- Domain Metadata Models (Pydantic)
- Skill Registry + Strategy Pattern
- Domain Config Parser (JSON → ResolvedDomainConfig)
- Keyword Generator (LLM 自动生成种子关键词)

### 数据采集与处理
- MediaCrawler 集成（小红书 / 抖音 / Bilibili / 微博）
- LLM Prompt Engineering (adaptive / hierarchical / ontology_cleaner)
- 社交媒体内容清洗 + 实体抽取 + 情感分析
- 趋势分数计算（牛顿冷却衰减 + 3σ 异常检测）

### 前端与可视化
- Vue 3 / Vite / TypeScript
- Element Plus / Axios
- Domain Management (领域 CRUD + 关键词管理 + CSV 导入)
- Domain Switcher (领域切换 + 激活)

## 数据流

```
用户创建领域 + 描述
  → LLM 自动生成种子关键词
  → adaptive 扩展关键词层级
  → 用户选择平台 → MediaCrawler 爬取
  → adaptive 清洗 (LLM 自动推断实体 Schema)
  → adaptive 洞察 (LLM 自动生成趋势报告)
  → cleaned_trend_data + trend_signal
```

## 目录结构

```
.
├── backend/                          # 后端服务、Agent、Skill、领域元数据引擎
│   ├── app/
│   │   ├── agents/                   # Multi-Agent 实现
│   │   ├── api/                      # FastAPI 路由 (domains, pipeline, ...)
│   │   ├── domain_meta/              # 领域元数据引擎 (models, parser, registry, keyword_generator)
│   │   ├── skills/                   # 可插拔 Skill 实现
│   │   │   ├── expander/             # 关键词扩展 (adaptive, hierarchical, tech_term)
│   │   │   ├── cleaning/             # 数据清洗 (adaptive, ontology_cleaner, judge)
│   │   │   └── insight/              # 趋势洞察 (adaptive, statistics, report_generator)
│   │   ├── infrastructure/           # 数据库、仓储实现
│   │   ├── services/                 # Pipeline 服务
│   │   └── tasks/                    # Celery 任务
│   ├── alembic/                      # 数据库迁移
│   ├── config/domains/               # 领域配置 JSON (beauty.json, new_energy_vehicle.json)
│   └── webui/                        # Vue 前端
├── MediaCrawler-main/                # 嵌入式社交媒体爬虫
└── data/                             # 基线数据、评测集（不随仓库分发）
```

## 快速开始

### 1. 准备环境变量

```bash
cp .env.example backend/.env
```

重点配置：

```env
DATABASE_URL=postgresql+asyncpg://postgres:123456@localhost:5433/media_crawler
DATABASE_URL_SYNC=postgresql+psycopg2://postgres:123456@localhost:5433/media_crawler
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
LLM_MODEL=glm-5.1
APP_PORT=8088
```

### 2. 启动 PostgreSQL 和 Redis

```bash
cd backend
docker compose up -d
```

### 3. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 4. 初始化数据库

```bash
cd backend
set PYTHONPATH=.
alembic upgrade head
```

### 5. 启动后端服务

```bash
cd backend
set PYTHONPATH=.
uvicorn app.main:app --host 0.0.0.0 --port 8088 --reload
```

健康检查：`GET http://localhost:8088/api/health`

### 6. 启动前端

```bash
cd backend/webui
npm install
npm run dev
```

访问地址：`http://localhost:5174`

### 7. 创建领域并运行 Pipeline

通过前端 Domain Management 或 API 创建领域：

```bash
# 创建新能源汽车领域
curl -X POST http://localhost:8088/api/v1/domains \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "new_energy_vehicle",
    "display_name": "新能源汽车",
    "domain_description": "新能源汽车行业，关注电池技术、智能驾驶、充电基础设施、车型评测、政策法规等话题",
    "expander_skill": {"strategy": "adaptive"},
    "cleaning_skill": {"strategy": "adaptive"},
    "insight_skill": {"strategy": "adaptive"}
  }'

# 激活领域
curl -X POST http://localhost:8088/api/v1/domains/2/activate

# 运行 Pipeline
cd backend
python run_pipeline.py --domain new_energy_vehicle --source domain --platform xhs
```

## API 能力

| 模块 | 端点 | 说明 |
|------|------|------|
| 领域管理 | `GET /api/v1/domains` | 列出所有领域 |
| | `POST /api/v1/domains` | 创建领域（自动生成种子关键词） |
| | `GET /api/v1/domains/{id}` | 获取领域详情 |
| | `PUT /api/v1/domains/{id}` | 更新领域配置 |
| | `POST /api/v1/domains/{id}/activate` | 激活领域 |
| 关键词管理 | `POST /api/v1/domains/{id}/generate-keywords` | LLM 生成关键词 |
| | `POST /api/v1/domains/{id}/import-keywords` | CSV 导入关键词 |
| | `GET /api/v1/domains/{id}/keywords` | 查看领域关键词 |
| Pipeline | `POST /api/v1/pipeline/start` | 启动 Pipeline |
| | `GET /api/v1/pipeline/status` | 查询状态 |
| | `WS /api/v1/pipeline/ws/logs` | 实时日志流 |

## 适用场景

- 🔍 任意行业的社交媒体趋势监测（美妆 / 新能源汽车 / 游戏 / AI工具 / ...）
- 📊 跨领域趋势对比分析
- 🤖 LLM Agent 工程项目展示
- 🧹 LLM 数据清洗与结构化输出
- 📈 趋势推荐与异常信号检测原型

## 合规说明

本仓库用于研究展示和工程原型验证。任何业务敏感数据、账号 Cookie、平台内容采集和模型输出都应遵守最小必要原则、平台规则、数据授权边界和项目数据契约。
