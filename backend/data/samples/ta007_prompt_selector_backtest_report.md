# TA-007 Prompt Selector Backtest Report

## Date

2026-04-19

## Purpose

Verify that TrendAgent keyword expansion now uses:

- platform-specific prompt files for `xiaohongshu / douyin / bilibili`
- generic fallback for unsupported or empty platform

## Backtest Command

```bash
cd BeautyQA-TrendAgent/backend
PYTHONPATH=. ../../.venv/bin/python scripts/run_ta007_prompt_selector_backtest.py
PYTHONPATH=. ../../.venv/bin/python -m unittest tests.test_keyword_prompt_selector
```

## Selector Result

### Platform-specific prompt resolution

- `xiaohongshu` -> `config/keyword_prompts/xiaohongshu.md`
- `douyin` -> `config/keyword_prompts/douyin.md`
- `bilibili` -> `config/keyword_prompts/bilibili.md`

### Fallback result

- `weibo` -> fallback to `config/enhance_trend_keyword.md`
- empty platform -> fallback to `config/enhance_trend_keyword.md`

## Plan-Level Check

Backtest keyword:

- `快速美白`

Backtest setting:

- `enable_llm=false`

Observed result:

- `crawl_targets = [xiaohongshu, douyin, bilibili]`
- `task_candidate_count = 6`
- `expanded_keywords = [快速美白, 快速美白 风险, 快速美白 避雷]`
- `prompt_selector` metadata is exposed in the execution plan

## Test Result

- `unittest`: `3 tests / OK`

## Conclusion

`TA-007` closes the selector layer:

- prompt selection is now platform-specific
- fallback remains safe
- execution plan stays stable when LLM expansion is disabled

## Open Risk

This task improves prompt routing, not final expansion quality calibration.

Prompt wording for `xhs / dy / bili` still needs live runtime observation and later tuning.
