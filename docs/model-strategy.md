# 🧠 OpenClaw 多Agent智慧模型调用方案

> 研究日期：2025年3月9日
> 适用版本：OpenClaw 2026.3.x
> 目标：为5个Agent打造最优模型分配策略，降低成本同时提升性能

---

## 📊 一、国内主流大模型横向对比

### 1.1 模型综合对比表

| 提供商 | 模型 | 输入价格 | 输出价格 | 上下文 | 推理能力 | 速度 | 特点 |
|--------|------|----------|----------|--------|----------|------|------|
| **Moonshot** | kimi-k2.5 | ¥0/免费 | ¥0/免费 | 256K | ⭐⭐⭐⭐⭐ | 中 | 超长上下文，中文优秀 |
| **Moonshot** | kimi-k2-thinking | ¥0/免费 | ¥0/免费 | 256K | ⭐⭐⭐⭐⭐ | 慢 | 深度推理，适合复杂分析 |
| **DeepSeek** | deepseek-v3 | ¥2/百万 | ¥8/百万 | 64K | ⭐⭐⭐⭐⭐ | 快 | 性价比之王，代码强 |
| **DeepSeek** | deepseek-r1 | ¥4/百万 | ¥16/百万 | 64K | ⭐⭐⭐⭐⭐ | 中 | 推理模型，数学逻辑强 |
| **通义千问** | qwen-max | ¥20/百万 | ¥60/百万 | 32K | ⭐⭐⭐⭐ | 快 | 阿里生态，工具丰富 |
| **通义千问** | qwen-coder | 免费* | 免费* | 128K | ⭐⭐⭐⭐ | 快 | 代码专用，OAuth免费 |
| **智谱GLM** | glm-5 | ¥15/百万 | ¥60/百万 | 128K | ⭐⭐⭐⭐ | 中 | 中文理解好 |
| **MiniMax** | M2.5 | $0.3/百万 | $1.2/百万 | 200K | ⭐⭐⭐⭐⭐ | 快 | 多语言代码强 |
| **MiniMax** | M2.5-highspeed | $0.3/百万 | $1.5/百万 | 200K | ⭐⭐⭐⭐ | 极快 | 高速版 |
| **OpenRouter** | 聚合多模型 | 按模型 | 按模型 |  varies | varies | varies | 统一入口 |

*注：Qwen Coder通过OAuth免费额度2000请求/天

### 1.2 模型能力雷达图分析

```
                    推理能力
                       ⬆️
           代码能力 ←   → 中文理解
                       ⬇️
                    性价比

Moonshot K2.5:    推理★★★★★ 中文★★★★★ 代码★★★★  性价比★★★★★ (免费)
DeepSeek V3:      推理★★★★★ 中文★★★★  代码★★★★★ 性价比★★★★★ (超便宜)
DeepSeek R1:      推理★★★★★ 中文★★★★  代码★★★★  性价比★★★★  
Qwen Max:         推理★★★★  中文★★★★★ 代码★★★★  性价比★★
MiniMax M2.5:     推理★★★★★ 中文★★★★  代码★★★★★ 性价比★★★★
```

---

## 🎯 二、Agent任务特点与模型匹配

### 2.1 各Agent任务分析

| Agent | 主要职责 | 任务复杂度 | 调用频率 | 上下文需求 | 关键要求 |
|-------|----------|------------|----------|------------|----------|
| **main** | 日常对话、任务分发 | 中 | 高 | 中 | 响应快、通用能力强 |
| **chairman** | 战略决策、融资分析 | 极高 | 低 | 高 | 推理强、深度分析 |
| **quant** | 量化分析、报告生成 | 高 | 中 | 高 | 数学强、代码能力 |
| **life** | 天气新闻、早报 | 低 | 高 | 低 | 便宜/免费、速度快 |
| **distill** | 知识蒸馏、记忆提炼 | 中 | 低 | 中 | 成本低、输出稳定 |

### 2.2 推荐模型分配方案

#### 🏆 最优配置（性能优先）

| Agent | 主模型 | 备用模型 | 理由 |
|-------|--------|----------|------|
| **main** | `moonshot/kimi-k2.5` | `deepseek/deepseek-v3` | 免费+响应快，备用便宜 |
| **chairman** | `deepseek/deepseek-r1` | `moonshot/kimi-k2-thinking` | 深度推理，战略分析 |
| **quant** | `deepseek/deepseek-v3` | `minimax/MiniMax-M2.5` | 代码+数学强，性价比高 |
| **life** | `qwen-portal/coder-model` | `moonshot/kimi-k2.5` | 免费额度，轻量任务 |
| **distill** | `deepseek/deepseek-v3` | `qwen-portal/coder-model` | 便宜稳定，输出可控 |

#### 💰 成本优化配置（省钱优先）

| Agent | 主模型 | 备用模型 | 预估成本/月 |
|-------|--------|----------|-------------|
| **main** | `deepseek/deepseek-v3` | `qwen-portal/coder-model` | ¥10-20 |
| **chairman** | `deepseek/deepseek-r1` | `moonshot/kimi-k2-thinking` | ¥30-50 |
| **quant** | `deepseek/deepseek-v3` | `deepseek/deepseek-chat` | ¥20-40 |
| **life** | `qwen-portal/coder-model` | - | ¥0 |
| **distill** | `qwen-portal/coder-model` | - | ¥0 |

---

## 💸 三、成本预估对比

### 3.1 当前配置成本（全用 Moonshot K2.5）

| 项目 | 估算 | 说明 |
|------|------|------|
| Moonshot K2.5 | ¥0/月 | 目前免费额度 |
| 调用限制 | 未知 | 免费额度可能有RPM限制 |
| **月度总计** | **¥0** | 但有稳定性风险 |

### 3.2 优化后配置成本（混合策略）

| Agent | 日均调用 | 平均Token | 模型 | 单价 | 日成本 | 月成本 |
|-------|----------|-----------|------|------|--------|--------|
| main | 50次 | 5K | deepseek-v3 | ¥2/1M | ¥0.5 | ¥15 |
| chairman | 5次 | 20K | deepseek-r1 | ¥4/1M | ¥0.4 | ¥12 |
| quant | 10次 | 15K | deepseek-v3 | ¥2/1M | ¥0.3 | ¥9 |
| life | 20次 | 3K | qwen(免费) | ¥0 | ¥0 | ¥0 |
| distill | 2次 | 10K | deepseek-v3 | ¥2/1M | ¥0.04 | ¥1.2 |
| **总计** | - | - | - | - | **¥1.24** | **¥37.2** |

### 3.3 成本对比总结

| 方案 | 月度成本 | 稳定性 | 性能 | 推荐度 |
|------|----------|--------|------|--------|
| 现状（全Moonshot） | ¥0 | ⚠️ 中 | ⭐⭐⭐⭐⭐ | 临时方案 |
| 优化后（混合） | ¥37 | ✅ 高 | ⭐⭐⭐⭐⭐ | **推荐** |
| 全DeepSeek | ¥50-80 | ✅ 高 | ⭐⭐⭐⭐⭐ | 备选 |
| 全付费高端 | ¥300+ | ✅ 高 | ⭐⭐⭐⭐⭐ | 土豪方案 |

---

## ⚡ 四、动态路由策略

### 4.1 任务复杂度分级

```python
# 自动路由逻辑伪代码
def route_task(agent_id, message, context_tokens):
    complexity = analyze_complexity(message, context_tokens)
    
    if agent_id == "chairman":
        if complexity > 0.8:
            return "deepseek/deepseek-r1"  # 深度推理
        else:
            return "deepseek/deepseek-v3"
    
    elif agent_id == "quant":
        if "代码" in message or "策略" in message:
            return "deepseek/deepseek-v3"  # 代码强
        else:
            return "minimax/MiniMax-M2.5"
    
    elif agent_id == "life":
        return "qwen-portal/coder-model"  # 免费
    
    elif agent_id == "distill":
        return "deepseek/deepseek-v3"  # 便宜稳定
    
    else:  # main
        if complexity > 0.7:
            return "moonshot/kimi-k2.5"
        else:
            return "deepseek/deepseek-v3"
```

### 4.2 OpenClaw 原生动态路由配置

OpenClaw 支持通过 `fallbacks` 和 `models` 配置实现智能路由：

```json5
{
  agents: {
    defaults: {
      model: {
        primary: "deepseek/deepseek-v3",
        fallbacks: ["moonshot/kimi-k2.5", "qwen-portal/coder-model"]
      }
    }
  }
}
```

---

## 🛠️ 五、OpenClaw 配置命令

### 5.1 安装和认证各模型提供商

```bash
# 1. 配置 DeepSeek（强烈推荐）
openclaw onboard --auth-choice apiKey --token-provider deepseek --token "sk-your-deepseek-key"

# 2. 配置 Qwen（免费额度）
openclaw plugins enable qwen-portal-auth
openclaw gateway restart
openclaw models auth login --provider qwen-portal --set-default

# 3. 配置 MiniMax（可选）
openclaw plugins enable minimax-portal-auth
openclaw onboard --auth-choice minimax-portal

# 4. 配置 Moonshot（已有，备用）
# 已配置，无需操作
```

### 5.2 完整配置方案（复制到 openclaw.json）

```json5
{
  // 环境变量
  env: {
    MOONSHOT_API_KEY: "${MOONSHOT_API_KEY}",
    DEEPSEEK_API_KEY: "sk-your-deepseek-key",
  },
  
  // Agent 配置
  agents: {
    defaults: {
      model: {
        primary: "deepseek/deepseek-v3",
        fallbacks: ["moonshot/kimi-k2.5"]
      },
      workspace: "/root/.openclaw/workspace",
      compaction: { mode: "safeguard" },
      maxConcurrent: 4,
    },
    list: [
      {
        id: "main",
        name: "微感超人",
        agentDir: "/root/.openclaw/agents/main/agent",
        model: {
          primary: "deepseek/deepseek-v3",
          fallbacks: ["moonshot/kimi-k2.5", "qwen-portal/coder-model"]
        }
      },
      {
        id: "chairman",
        name: "公司助理",
        workspace: "/root/.openclaw/workspace-chairman",
        agentDir: "/root/.openclaw/agents/chairman/agent",
        model: {
          primary: "deepseek/deepseek-r1",  // 深度推理
          fallbacks: ["moonshot/kimi-k2-thinking"]
        }
      },
      {
        id: "quant",
        name: "量化助手",
        agentDir: "/root/.openclaw/agents/quant/agent",
        model: {
          primary: "deepseek/deepseek-v3",  // 代码+数学
          fallbacks: ["minimax/MiniMax-M2.5"]
        }
      },
      {
        id: "life",
        name: "生活助手",
        agentDir: "/root/.openclaw/agents/life/agent",
        model: {
          primary: "qwen-portal/coder-model",  // 免费
          fallbacks: ["moonshot/kimi-k2.5"]
        }
      },
      {
        id: "distill",
        name: "知识蒸馏",
        agentDir: "/root/.openclaw/agents/distill/agent",
        model: {
          primary: "deepseek/deepseek-v3",  // 便宜稳定
          fallbacks: ["qwen-portal/coder-model"]
        }
      }
    ]
  },
  
  // 模型提供商配置
  models: {
    mode: "merge",
    providers: {
      moonshot: {
        baseUrl: "https://api.moonshot.cn/v1",
        apiKey: "${MOONSHOT_API_KEY}",
        api: "openai-completions",
        models: [
          {
            id: "kimi-k2.5",
            name: "Kimi K2.5",
            reasoning: false,
            input: ["text"],
            cost: { input: 0, output: 0 },
            contextWindow: 256000,
            maxTokens: 8192,
          },
          {
            id: "kimi-k2-thinking",
            name: "Kimi K2 Thinking",
            reasoning: true,
            input: ["text"],
            cost: { input: 0, output: 0 },
            contextWindow: 256000,
            maxTokens: 8192,
          }
        ]
      },
      deepseek: {
        baseUrl: "https://api.deepseek.com/v1",
        apiKey: "${DEEPSEEK_API_KEY}",
        api: "openai-completions",
        models: [
          {
            id: "deepseek-v3",
            name: "DeepSeek V3",
            reasoning: false,
            input: ["text"],
            cost: { input: 2, output: 8 },  // ¥/百万token
            contextWindow: 64000,
            maxTokens: 8192,
          },
          {
            id: "deepseek-r1",
            name: "DeepSeek R1",
            reasoning: true,
            input: ["text"],
            cost: { input: 4, output: 16 },
            contextWindow: 64000,
            maxTokens: 8192,
          }
        ]
      }
    }
  }
}
```

### 5.3 快速切换命令

```bash
# 查看当前模型
openclaw models list

# 临时切换模型（当前会话）
openclaw models set deepseek/deepseek-v3

# 为特定agent设置模型
openclaw config set agents.list[0].model.primary deepseek/deepseek-v3

# 查看agent配置
openclaw config get agents.list
```

---

## 🧪 六、蒸馏任务轻量化方案

### 6.1 蒸馏任务特点

- **输入**：长文本（聊天记录、记忆片段）
- **输出**：结构化摘要（MEMORY.md格式）
- **要求**：成本低、输出稳定、格式一致
- **频率**：每天1-2次

### 6.2 推荐方案

| 方案 | 模型 | 成本 | 说明 |
|------|------|------|------|
| **首选** | `deepseek/deepseek-v3` | ¥2/百万 | 便宜稳定，格式控制好 |
| **免费** | `qwen-portal/coder-model` | ¥0 | 免费额度足够 |
| **本地** | `ollama/llama3.1:8b` | ¥0 | 隐私好，需硬件 |

### 6.3 蒸馏Prompt优化

```markdown
# 记忆蒸馏指令模板

你是一个记忆整理助手。请将以下聊天记录整理为结构化的记忆条目。

要求：
1. 提取关键事实、决策、偏好
2. 按类别分组（工作/生活/学习/人际关系）
3. 使用简洁的 bullet points
4. 去除闲聊和重复内容
5. 保持客观，不添加推测

输出格式：
- **日期**: YYYY-MM-DD
- **类别**: [工作/生活/学习/其他]
- **内容**: 简洁描述
- **重要性**: [高/中/低]

聊天记录：
{chat_history}
```

---

## 📈 七、监控与优化建议

### 7.1 成本监控命令

```bash
# 查看模型使用情况
openclaw status --all

# 查看会话token消耗
openclaw sessions list --limit 10

# 查看特定agent的使用统计
# （需配合日志分析）
grep "token" ~/.openclaw/logs/*.log | tail -50
```

### 7.2 自动优化策略

1. **定时降级**：夜间低峰期自动切换到 cheaper 模型
2. **缓存命中**：重复查询优先使用缓存响应
3. **Token压缩**：长上下文自动摘要后再发送
4. **失败回退**：主模型失败时自动降级到备用

### 7.3 推荐迭代路径

```
Phase 1 (现在): 全 Moonshot K2.5 (免费)
    ↓
Phase 2 (1周后): 接入 DeepSeek V3 (主力) + Moonshot (备用)
    ↓
Phase 3 (1月后): 完整5-Agent差异化配置
    ↓
Phase 4 (持续): 基于使用数据动态优化
```

---

## 📝 八、立即执行清单

### 8.1 今天完成

- [ ] 注册 DeepSeek API (https://platform.deepseek.com)
- [ ] 启用 Qwen OAuth 插件
- [ ] 备份当前 openclaw.json
- [ ] 配置 DeepSeek 提供商

### 8.2 本周完成

- [ ] 测试各Agent在新模型下的表现
- [ ] 调整 Prompt 适配不同模型特性
- [ ] 设置成本监控告警
- [ ] 编写模型切换 SOP

### 8.3 持续优化

- [ ] 每月Review成本报告
- [ ] 跟踪新模型发布（DeepSeek V4、Kimi K3等）
- [ ] 根据业务变化调整Agent配置

---

## 💡 九、关键决策建议

### 9.1 立即决策

| 决策项 | 建议 | 理由 |
|--------|------|------|
| **主力模型** | DeepSeek V3 | 性价比最优，代码强 |
| **推理任务** | DeepSeek R1 | 深度思考，战略分析 |
| **免费备用** | Qwen Coder | 2000请求/天够用 |
| **长上下文** | Moonshot K2.5 | 256K上下文，免费 |

### 9.2 风险提示

1. **免费额度风险**：Moonshot 免费政策可能调整，需准备付费方案
2. **API稳定性**：国内模型偶尔有不稳定，必须配置 fallback
3. **成本控制**：建议设置月度预算上限（如¥100）
4. **数据隐私**：敏感任务建议使用本地模型或私有化部署

---

## 📚 十、参考资源

- [DeepSeek API文档](https://platform.deepseek.com)
- [Moonshot API文档](https://platform.moonshot.cn)
- [Qwen免费额度](https://portal.qwen.ai)
- [MiniMax定价](https://platform.minimax.io)
- [OpenClaw模型配置](https://docs.openclaw.ai/providers/models)

---

*方案制定：微感超人*  
*版本：v1.0*  
*更新日期：2025-03-09*
