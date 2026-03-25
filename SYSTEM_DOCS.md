# 量化交易系统 & OpenClaw 配置文档

最后更新：2026-03-15

## 一、服务器基本信息

- 系统：Ubuntu（腾讯云 VM-0-3）
- 量化系统路径：/root/quant-system/
- OpenClaw 配置路径：/root/.openclaw/
- OpenClaw 版本：2026.3.8 (3caab92)
- Gateway 端口：18789（0.0.0.0）
- 模型提供商：moonshot（主）、deepseek（备）
- 默认模型：moonshot/kimi-k2.5

## 二、系统进程管理

启动 OpenClaw Gateway：
  pkill -f "openclaw" && sleep 3
  nohup openclaw gateway --port 18789 >> /root/openclaw.log 2>&1 &
  sleep 6 && netstat -tlnp | grep 18789

查看运行状态：
  ps aux | grep openclaw | grep -v grep
  tail -30 /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log

服务重启：
  systemctl restart openclaw-gateway.service

## 三、QQ Bot 配置

插件：@tencent-connect/openclaw-qqbot v1.5.7
路径：/root/.openclaw/extensions/openclaw-qqbot/
Token：102843347:kdWQKE82wrmhcXSNJFB73zvrolifcZWU

群绑定列表：
  quant      量化一群   940510271
  chairman   主席群     176032278
  main       行政管理   947124826
  financing  融资       592975210
  intel      研究员     710819444
  intel      情报       882765441
  marketing  市场       730867418
  brand      品牌       795906473
  legal      法务       887445700

## 四、Agent 配置

配置目录：/root/.openclaw/agents/{agentId}/AGENTS.md

各 Agent 说明：
  quant      /root/quant-system   read,write,exec,process,web_search
  chairman   /root                read,web_search
  main       /root                read,write,web_search
  financing  /root                read,web_search
  intel      /root                read,web_search,web_fetch
  marketing  /root                read,web_search
  brand      /root                read,web_search
  legal      /root                read,web_search

Quant Agent 指令：
  持仓 / 仓位   -> 读取 portfolio_state.json
  系统状态      -> 检查运行进程
  止损 / 风控   -> 运行 risk_manager_v2.check_all_positions()
  行情 / 价格   -> moma_data.get_realtime_quotes()
  拉黑 XXXXXX  -> blacklist_manager.add(code)

## 五、量化系统文件结构

/root/quant-system/
  intraday_v4_2.py       主交易程序（已集成风控）
  stock_selector_v2.py   选股模块（15:05 自动运行）
  moma_data.py           行情数据（已修复，含 AKShare fallback）
  blacklist_manager.py   黑名单管理（新建 2026-03-15）
  risk_manager_v2.py     ATR 动态止损（新建 2026-03-15）
  portfolio_state.json   持仓状态
  watch_list.json        监控列表（已修复为 dict 格式）
  config.json            系统配置
  blacklist.json         黑名单数据（运行时生成）
  SYSTEM_DOCS.md         本文档

## 六、定时任务 Crontab

  每5分钟            heartbeat.log
  工作日 09:25       intraday_v4_2.py（开盘交易）
  工作日 15:05       stock_selector_v2.py（收盘选股）
  工作日 20:00       intraday_v4_2.py --end-of-day（收盘汇总）

待完成：为4条任务添加 QQ Bot 失败告警

## 七、持仓快照（2026-03-15）

  002737   300股   成本 13.476   现价 12.69   浮亏 -233.10   止损 12.398
  601116   100股   成本 15.200   现价 14.68   浮亏  -52.00   止损 13.984
  现金     94304.00
  总资产   99579.00

## 八、数据层

  AKShare v1.16.92    主要行情、涨停池、K线   正常
  Tencent Finance     实时行情（有边界检查）   部分可用
  MomaAPI             情绪数据（已修复）       正常
  Tushare             备用                     待验证

## 九、OpenClaw 配置文件

路径：/root/.openclaw/openclaw.json
备份规则：每次修改前自动备份，保留最新2份
查看备份：ls /root/.openclaw/openclaw.json.*

## 十、待办事项

P2 本周：
  [ ] crontab 4条任务添加 QQ Bot 失败告警
  [ ] 验证 AKShare K线数据接入 ATR 止损（交易日测试）
  [ ] 扩展 quant Agent 更多指令

P3 本月：
  [ ] 接入基本面因子（ROE>15%，PE低于行业均值）
  [ ] 激活 Streamlit app.py（SSH隧道访问）
  [ ] 历史回测 2020-2025（目标年化>8%，夏普>0.8，最大回撤<25%）
