# Quality Mispricing

这是一个半自动投资研究流水线：每天先扫描 S&P 500 价格数据，再对持仓、观察名单和预筛候选抓完整财务，计算趋势/相对强弱/估值与安全边际、保存可追溯快照，并生成带来源链接的中文晨报。

它只做研究筛选，不下单；`BUY_CANDIDATE` 必须通过 SEC 一手数据交叉验证，最终决定始终由人做。

## 每天会产出什么

- `reports/latest.md`：最新晨报，包含市场扫描漏斗、持仓提醒、买入候选、观察名单、明确不买、人工动作和来源。
- `reports/latest.json`：相同结果的结构化版本，便于后续接网页或通知。
- `data/quality_mispricing.sqlite3`：每次运行的市场、财务、分析和持仓快照，以及成功/失败记录。
- `reports/runner-YYYYMMDD.log`：每日运行日志。
- `data/quality_mispricing.sqlite3` 中的深度研究队列：仅当候选通过更严格门槛时才创建一项 AI Berkshire 研究任务。

## 首次设置

```bash
cd /path/to/quality-mispricing
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp config.example.json config.json
```

编辑 `portfolio.csv`，每行填写：

```csv
ticker,shares,average_cost,target_weight,max_weight,add_style
MSFT,6,373,0.08,0.10,HYBRID
```

编辑 `config.json` 的观察名单、现金和账户总值。若 `total_account_value` 为 `null`，系统用“持仓市值 + 现金”计算权重。

要启用 SEC 一手财报校验，运行前设置真实联系邮箱：

```bash
export SEC_USER_AGENT="QualityMispricing your-real-email@example.com"
```

没有这个变量时流水线仍会运行，但不会把任何股票标成 `BUY_CANDIDATE`。

## 运行与检查

```bash
.venv/bin/python scripts/daily_runner.py
.venv/bin/python run.py --status
.venv/bin/python run.py --offline
```

`--offline` 只读本地缓存，用于网络故障时验证整条流水线。首次运行不能离线。调试时可加 `--skip-sec`，正式晨报不建议跳过 SEC。

## 每天自动运行

Codex 的 `Quality Mispricing 早报` 已设为工作日新加坡时间 07:30 调用：

```text
.venv/bin/python scripts/daily_runner.py
```

`daily_runner.py` 有非阻塞文件锁，重复触发不会并发抓取。若电脑在该时间离线，任务会记录失败原因；本地缓存仍可用 `--offline` 复核。

## 计算口径

- 漏斗：S&P 500 全池批量抓价格；流动性不足或 52 周回撤小于 10% 的股票不进入当日深度研究。预筛分只分配研究资源，不是买入评分。
- 趋势：50/200 日均线，只作仓位语境，不作为公司质量证据。
- 相对强弱：股票 3/6 个月收益减去 SPY 同期收益。
- 指数增强：按当前组合静态权重计算核心指数仓、主动增强仓、现金/未配置、Beta、相关性、跟踪误差和 3/6/12 个月超额收益；只监控偏离，不自动调仓。
- 市场恐惧：52 周高点回撤，并结合相对强弱展示。
- 估值：年度稀释 EPS 对应财年末价格得到历史 P/E 中位数，再做 Bear/Base/Bull 情景；异常乐观的 forward EPS 会按已观察增长率封顶。
- 财务交叉验证：SEC XBRL 为一手来源，Yahoo Finance/yfinance 为独立数据源；同期间差异超过 1% 会标记复核。
- 风险门槛：质量、财务恶化、杠杆、数据验证和安全边际均是硬门槛；评分不能绕过门槛。
- 深度研究晋级：最多每天 1 只，要求 `BUY_CANDIDATE`、SEC 验证通过、无风险标记、综合分至少 85、Base 安全边际至少 25%；同一股票 30 天不会重复创建任务。任务交由 AI Berkshire 做一手资料、反方论点、反向 DCF 和业务驱动估值，不能自动下单。

查看待完成的深度研究任务：

```bash
.venv/bin/python scripts/research_queue.py
```

研究任务可输出为方便 Codex 接手的 Markdown 简报；完成一份已保存、带来源的报告后才可标记完成：

```bash
.venv/bin/python scripts/research_queue.py --format markdown
.venv/bin/python scripts/complete_research_task.py TASK_ID reports/deep-research/TICKER-YYYYMMDD.md
```

## 架构借鉴

项目借鉴了公开项目的分层思想，没有复制其业务代码：

- [OpenBB](https://github.com/OpenBB-finance/OpenBB)：数据提供层与研究逻辑分离。
- [yfinance](https://github.com/ranaroussi/yfinance)：市场数据接入。
- [edgartools](https://github.com/dgunning/edgartools)：SEC 数据规范化思路。
- [QuantStats](https://github.com/ranaroussi/quantstats)：收益与风险指标的组织方式。
- [skfolio](https://github.com/skfolio/skfolio)：借鉴 Benchmark Tracker、跟踪误差约束和走样本外验证的原则；当前只实现透明的监控指标，不引入其大型优化依赖。
- [PyPortfolioOpt](https://github.com/PyPortfolio/PyPortfolioOpt)：借鉴权重上限和正则化思想；当前不使用对预期收益高度敏感的均值方差自动配仓。

当前覆盖美股和 SEC。A 股、港股需要增加相应交易所/公告一手来源后再开放同等级信号。
