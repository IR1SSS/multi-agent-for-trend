# Trend LLM Cleaning Skill 调用说明

## 这个模块是做什么的

它不是新的 crawler，也不是新的 handoff export，也不再依赖独立的清洗脚本入口。

它复用 `app.agents.cleaning_agent.CleaningAgent`，把一条已经完成抓取的 `crawl task` 接到标准后处理链路：

`T1 确定性清洗 -> T2 LLM 清洗增强 -> T3 trend_signal 生成`

适合团队在下面两种场景直接复用：

- 工程同学要把抓回来的原始数据做标准清洗
- 需要单独回测某个 `task_id` 的清洗和 signal 结果

## 输入前提

- 已经有可用的 PostgreSQL 数据
- 对应平台原始表里已经有这次抓取的数据
- `BeautyQA-TrendAgent/backend/.env` 已配置 `LLM_API_KEY`
- 已知一条可用的 `task_id + platform + keyword`

## 标准运行命令

从仓库根目录执行：

```bash
cd /Users/liuzhicheng/1data/workspace2026/LN-projs/BeautyModel-Lab/BeautyQA-TrendAgent/backend
PYTHONPATH=. ../../.venv/bin/python -m app.agents.cleaning_agent \
  --task-id 123 \
  --platform dy \
  --keyword "油敷法"
```

如果只想跑清洗，不生成 `trend_signal`：

```bash
cd /Users/liuzhicheng/1data/workspace2026/LN-projs/BeautyModel-Lab/BeautyQA-TrendAgent/backend
PYTHONPATH=. ../../.venv/bin/python -m app.agents.cleaning_agent \
  --task-id 123 \
  --platform dy \
  --keyword "油敷法" \
  --skip-signal
```

如果想限制原始样本量做 debug：

```bash
cd /Users/liuzhicheng/1data/workspace2026/LN-projs/BeautyModel-Lab/BeautyQA-TrendAgent/backend
PYTHONPATH=. ../../.venv/bin/python -m app.agents.cleaning_agent \
  --task-id 123 \
  --platform dy \
  --keyword "油敷法" \
  --max-raw-items 20
```

## 输出会写到哪里

- 清洗后的本地 JSON：
  - `BeautyQA-TrendAgent/backend/data/cleaned/<platform>/`
- 生成的 `trend_signal` JSON：
  - `BeautyQA-TrendAgent/backend/data/trend_signal/<platform>/`
- 这次 skill 的执行报告：
  - `BeautyQA-TrendAgent/backend/data/runtime_runs/cleaning_skill/`

## 返回结果怎么看

重点看三块：

- `stage_report.t1_deterministic_cleaning`
  - 看抓到多少、去空多少、去重多少、最终保留多少
- `stage_report.t2_llm_enrichment`
  - 看 LLM 成功多少、fallback 多少、noise 丢掉多少
- `stage_report.t3_signal_generation`
  - 看是否生成了 `trend_signal`、生成了多少条

再看：

- `outputs.cleaned_json_path`
- `outputs.trend_signal_json_path`
- `status.success`

## 当前边界

这个 skill 当前只负责后处理，不负责：

- 创建 crawl task
- 启动 crawler
- 导出 QA handoff `current/`

如果要把结果推到 QA handoff，后续还是走 `INT-003 export`。
