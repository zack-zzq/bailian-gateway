# Bailian Gateway

OpenAI 兼容的阿里云百炼大模型网关，支持自动模型降级。

当百炼平台开启"免费额度用完即止"后，某个模型的免费额度用完会返回 `403 AllocationQuota.FreeTierOnly` 错误。该网关会自动捕获此错误，并按照预配置的优先级顺序切换到下一个可用模型，直到找到一个还有免费额度的模型来处理请求。

## 特性

- ✅ 完全兼容 OpenAI API 格式（`/v1/chat/completions`）
- ✅ 支持 Streaming（SSE）和非 Streaming 模式
- ✅ 自动按优先级降级模型
- ✅ 内存缓存已用尽的模型 ID，避免重复请求
- ✅ Docker 容器化部署
- ✅ GitHub Actions 自动构建推送到 GHCR

## 快速开始

### 本地运行

1. 安装 [uv](https://docs.astral.sh/uv/)

2. 配置环境变量：
   ```bash
   cp .env.example .env
   # 编辑 .env，填入你的 API Key 和模型列表
   ```

3. 启动网关：
   ```bash
   uv run python -m bailian_gateway
   ```

4. 测试请求：
   ```bash
   curl http://localhost:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model":"auto","messages":[{"role":"user","content":"你好"}]}'
   ```

### Docker 部署

```bash
docker compose up -d
```

或者使用预构建镜像：

```bash
docker run -d \
  -p 8000:8000 \
  -e OPENAI_API_KEY=sk-your-key \
  -e OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1 \
  -e MODEL_PRIORITY=qwen-turbo,qwen-plus,qwen-max \
  ghcr.io/zack-zzq/bailian-gateway:main
```

## 环境变量

| 变量 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `OPENAI_API_KEY` | ✅ | - | 百炼平台 API Key |
| `OPENAI_BASE_URL` | ❌ | `https://dashscope.aliyuncs.com/compatible-mode/v1` | API 基础 URL |
| `MODEL_PRIORITY` | ✅ | - | 模型 ID 列表，逗号分隔，优先级从高到低 |
| `PORT` | ❌ | `8000` | 网关监听端口 |
| `HOST` | ❌ | `0.0.0.0` | 网关监听地址 |

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/chat/completions` | POST | 代理 Chat Completions 请求 |
| `/v1/models` | GET | 列出当前可用模型 |
| `/health` | GET | 健康检查（含可用/已用尽模型信息） |

## 工作原理

```
用户请求 → 网关 → 模型A（额度用尽）→ 模型B（额度用尽）→ 模型C（正常）→ 返回用户
                    ↓ 加入黑名单            ↓ 加入黑名单
```

1. 用户发送 OpenAI 格式的请求到网关
2. 网关按优先级从高到低尝试配置的模型 ID
3. 如果百炼返回 `AllocationQuota.FreeTierOnly`（403），标记该模型为已用尽并尝试下一个
4. 已用尽的模型会被缓存，后续请求直接跳过
5. 找到可用模型后，将响应透传给用户（Streaming 同样支持）

## License

MIT
