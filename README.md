# 钱途 CapitalVoyage

<p><img src="frontend/public/brand/qian-tu-logo.svg" alt="钱途 CapitalVoyage Logo" width="380"></p>

一个基于 ETF 实时行情的分航次资金管理与返航提醒工具。每次买入形成独立航次，独立保存成本、份额与目标收益；系统以买一价（可切换最新价）计算净收益，并在行情新鲜、份额可卖且达到目标时给出准确返航份额。

## V1 能力

- 50 万默认资金池、10 个独立舱位，支持同 ETF 多航次
- 精确 `Decimal` 账务、部分返航、一次卖出分配多个航次
- SQLite WAL、外键、持久化航次序号和并发超卖保护
- 手续费感知的净收益与 0.001 元 tick 目标价
- SSE 交易日历、Asia/Shanghai、T+0/T+1
- AKShare ETF 行情、BID1 回退 LAST、30 秒 stale 防误判
- MonitorState 状态恢复、提醒去重/cooldown、Console/飞书/ntfy
- 运行态势、航次、返航中心、航程记录、设置五个 Vue 页面
- 持仓核对只报告差异，绝不自动改账

V1 不包含 AI、自动交易、券商 API、Docker、K 线、技术指标、推荐、新闻、回测、多用户或微服务。

## 环境要求

- 已有 Conda 环境 `code_env`（当前验证 Python 3.12.14）
- Node.js >= 20（当前验证 Node 24）
- npm

不要创建 `.venv` 或新的 Conda 环境。非交互 shell 推荐使用 `conda run -n code_env ...`，避免 `conda activate` 未初始化而误用 base 环境。

## 安装

```bash
cd /Users/bianxingpeng/XP_WorkSpace/CapitalVoyage
conda run -n code_env python -m pip install -e 'backend[test]'
cd frontend
npm install
```

根目录已提供 `.env.example`。首次使用时可复制为 `.env`；当前本地已放置同等默认配置。数据库默认位于 `data/capital_voyage.db`，启动时自动建表并初始化资金池和舱位。

## 启动后端

```bash
cd /Users/bianxingpeng/XP_WorkSpace/CapitalVoyage/backend
conda run -n code_env uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- API：<http://localhost:8000>
- Swagger：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/api/health>

服务生命周期：初始化数据库 → 恢复设置/监控状态 → 启动单实例行情调度 → 立即轮询；关闭时停止调度器。AKShare 失败后保留最后行情并按 15/30/60/120/300 秒退避，旧行情会自然变为 stale。

## 启动前端

```bash
cd /Users/bianxingpeng/XP_WorkSpace/CapitalVoyage/frontend
npm run dev
```

访问 <http://localhost:5173>。Vite 会把 `/api` 代理到 `http://localhost:8000`。

## 一键启动前后端

在项目根目录执行：

```bash
./start.sh
```

脚本会复用现有 `code_env`，按需安装缺失依赖，同时启动后端 `8000` 和前端 `5173`；按 `Ctrl+C` 会同时停止两个服务。也可以通过环境变量覆盖端口，例如 `BACKEND_PORT=8100 FRONTEND_PORT=5174 ./start.sh`。

## 测试与构建

```bash
cd /Users/bianxingpeng/XP_WorkSpace/CapitalVoyage
APP_ENV=test SCHEDULER_ENABLED=false conda run -n code_env python -m pytest backend/tests

cd frontend
npm run build
```

测试覆盖 Decimal/SQLite、资金舱位、并发退出、手续费与目标价、交易日历、行情映射/freshness/退避、Monitor/Alert、返航聚合、部分退出、多航次退出、API 统一响应和完整 25,700 份闭环。

## 使用闭环

1. 在“航次”选择空闲舱位，记录真实买入价格、份额和费用。
2. 后端根据 Security 的结算模式计算可卖时间；首次标的默认 T+1。
3. 行情轮询对每个 OPEN 航次独立计算净收益。
4. “返航中心”按 ETF 聚合可返航航次和准确份额。
5. 在券商完成卖出后，手工输入真实成交与费用，并明确每个航次的分配；系统不会自动 FIFO。
6. 完全卖出后航次关闭并释放舱位；部分卖出继续保持在航。
7. 可在“航程记录”查看实现收益，在“返航中心”核对券商持仓差异。

## 账务与行情约束

- 金额、价格和收益率全程使用 Python `Decimal`；SQLite 以字符串无损保存，JSON 以字符串返回。
- `remaining_quantity` 从买入份额减去 allocation 动态计算，不在 Voyage 冗余维护。
- stale/missing quote 强制 `QUOTE_STALE`，绝不触发新的 `READY_TO_RETURN`。
- MonitorState 是运行态；Voyage 只保存 `OPEN/CLOSED/CANCELLED` 交易事实。
- 关键修改写入 AuditLog。持仓核对不会自动修正任何数据。

## 真实行情说明

已使用 AKShare `fund_etf_spot_em()` 验证 510300，字段包含名称、最新价、买一、卖一、数据日期与带时区更新时间。休市期间源行情会被正确判定为 stale；只有交易时段且更新时间未超过阈值时才视为 fresh。
