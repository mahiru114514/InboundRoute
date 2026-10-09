# 模块运行时契约（方案一：模块自己暴露 HTTP）

> 契约编号：**C7**（新增）　状态：**已冻结（2026-09-25 决策：方案一）**
> 依据：宿主「模块工作台」（`manager.py` / `core/`）的隔离机制是「每模块独立进程 + 模块间无法互相调用」。
> InboundRoute 的三个引擎必须互相调用，因此约定：**每个模块在自己的进程里起一个本地 HTTP 服务，模块间只通过 `http://127.0.0.1:<port>` 通信。宿主只管生命周期，不碰业务数据。**

---

## 1. 职责边界（一句话记住）

| 角色 | 负责 | **不**负责 |
| --- | --- | --- |
| 宿主（模块工作台） | 安装 / 启用 / 运行 / 停止、依赖顺序、日志、配置、健康检查展示 | 不转发业务请求、不碰行程数据、不分配端口 |
| 模块（InboundRoute 各引擎） | 自己的 HTTP 服务、自己的数据、自己的端口与令牌 | 不直接读别的模块的 `data_dir`、不 import 别的模块的 Python 代码 |
| 契约包 `contracts/` | 字段、枚举、规则、错误码、本文件的通信约定 | 不是模块，不参与运行时 |

**硬约束**：模块之间**只能通过 HTTP 通信**。禁止：
- ❌ `import` 另一个模块的 Python 代码（进程隔离，import 的是副本，状态不共享）
- ❌ 直接读写另一个模块的 `context.data_dir`
- ❌ 通过 `context.config` 传递业务数据（它只是启动时快照）

---

## 2. 端口与注册表

宿主不分配端口，所以每个服务型模块**自己占端口并登记**：

```
1. 端口来源（按优先级）：
   a. context.config["port"]        # 人类可读、可固定，便于调试
   b. 未配置或为 0 → 绑定 0 让系统分配，再读取实际端口

2. 登记：启动成功后写 data_dir/../_registry/<module_id>.json
   （即 <root>/data/_registry/ 下，所有模块共享的注册目录）

3. 就绪：注册文件写出后才开始接受业务请求；退出时删除注册文件
```

**注册文件格式（固定，不许扩展字段）**

```jsonc
{
  "module_id": "route_adapter",
  "port": 51234,
  "base_url": "http://127.0.0.1:51234",
  "token": "3f9c…（32 字节 urlsafe，启动时随机生成）",
  "pid": 12345,
  "contract_version": "0.3.2",
  "started_at": 1791853200,
  "depends_on": ["trip_engine"],
  "endpoints": ["/health", "/routes:compute", "/stations/{station_id}"]
}
```

> **`token` 是每个模块启动时随机生成的**，只登记在这一处。调用方（其他模块）启动时读注册表拿到，**不通过配置文件传递**——配置文件会被页面展示，令牌不该出现在那里。

---

## 2.5 清单里的 `service` 约定（可选，但服务型模块必须写）

宿主只读 `manifest.json` 的 `id/name/version/description/dependencies`（多出的字段会被忽略），
但**启动器 `start_software.py` 需要知道「哪些模块是服务、健康检查在哪、主界面是哪个」**。
因此服务型模块在清单里额外声明：

```jsonc
{
  "id": "web_workbench",
  "dependencies": ["trip_engine"],                    // 硬依赖：未安装则该模块拒绝启动
  "service": {
    "enabled": true,          // 是否起 HTTP 服务（false 时启动器只保证进程在跑）
    "health_path": "/health", // 健康检查路径
    "open_path": "/",         // 软件主界面路径；只有一个模块该填（启动器用它决定打开哪个页面）
    "title": "行程工作台（软件主界面）",
    "optional_dependencies": ["rules_engine", "route_adapter"]   // 可选依赖：缺失不影响启动
  }
}
```

- 不起 HTTP 的模块（如纯计算、纯定时任务）**不写** `service`，启动器只等它的进程起来。
- 该字段不属于宿主契约，宿主不会因它报错；也不参与 `dependencies` 顺序计算。
- 启动器读注册文件拿 `base_url`，拼 `open_path` 得到主界面地址——所以 `open_path` 只有主界面模块填。
- **`dependencies` 与 `optional_dependencies` 的区别**：前者缺失会让启动器**拒绝启动**该模块；后者缺失只是少一个能力，模块自己降级展示。典型例子：`web_workbench` 只要 `trip_engine` 在就能跑，规则/路线引擎未接入时界面顶部标出「未就绪」并降级，而不是启动失败。可选依赖若也在本次启动列表里，顺序仍排在被依赖方之前。

---

## 3. 必须实现的端点
### 3.1 所有服务型模块

| 端点 | 说明 |
| --- | --- |
| `GET /health` | 唯一不需要令牌的端点。返回 `{module_id, status, contract_version, ready, started_at, degraded, degraded_reason}`；`status ∈ ok/degraded/down` |

### 3.2 各模块的业务端点（与 `schemas/api.schema.json` 一致）

| 模块 | 必须提供 | 必须消费 |
| --- | --- | --- |
| `trip_engine` | `POST /trips`、`GET /trips/{id}`、`PATCH /trips/{id}`、`GET /pois`、`GET /pois/{id}`、`POST /trips/{id}/days/{d}/stops`、`DELETE …/stops/{poi_id}` | — |
| `rules_engine` | `POST /trips/{id}/rules:evaluate`、`POST /trips/{id}/conflicts/{notice_id}/confirm` | `trip_engine`：读/写行程 |
| `route_adapter` | `POST /trips/{id}/days/{d}/routes:compute`、`GET /stations/{id}`、`GET /pois/{id}/drop-off` | （内部调三方） |
| `web_workbench` | `GET /`（前端页面）、`GET /app.js`、`GET /style.css` | 上述三者全部 |
| `offline_kit` | `POST /trips/{id}/offline-package` | `trip_engine`、`route_adapter` |

> **命名约定**：动作用 `:verb` 后缀（`rules:evaluate`、`routes:compute`），与宿主自身 API 的 `/api/modules/<id>/<action>` 区分开，避免混淆。

---

## 4. 鉴权与调用规则

| 规则 | 说明 |
| --- | --- |
| 令牌传递 | 除 `/health` 外，所有请求必须带 `X-Module-Token: <token>`；令牌校验失败返回 403 |
| 调用方向 | **只有 `web_workbench` 可以代表用户调用其他模块**（它持有用户会话与前端）。引擎之间按依赖方向调用，**禁止反向调用**（`trip_engine` 不得调 `rules_engine`） |
| 宿主调用 | 宿主只读注册表拿 `base_url`，然后**只调 `/health`**（用于在管理页面显示「就绪 / 降级 / 失联」）。宿主绝不转发业务请求 |
| 同源 | 引擎的 `Host` 白名单为 `127.0.0.1:<自己的端口>` 与 `localhost:<自己的端口>`；`web_workbench` 需额外允许宿主的端口（它要展示链接或反代） |
| 令牌不落盘到配置 | 令牌只在注册文件里；`context.config` 里不允许出现令牌 |

---

## 5. 启动顺序、就绪与失败

```
宿主按 manifest.dependencies 顺序启动：
  trip_engine → (rules_engine ∥ route_adapter) → (web_workbench ∥ offline_kit)
```

| 场景 | 约定行为 |
| --- | --- |
| 依赖未就绪 | 启动时**轮询依赖的 `/health`**，最长 30s，间隔 200ms→1s 退避；超时则本模块启动失败并写明确日志（不静默） |
| 依赖等待期间重新登记 | 等待必须**每轮重读 `_registry/<id>.json`**，拿到新注册信息就改用新 `base_url` + `token`；注册文件尚未出现时继续等，不立刻判「未运行」。理由：模块重启会换端口，而上一轮遗留的注册文件仍指向已死端口——把 `base_url` 固定在第一次读到的值上会白等到超时（真实故障见 `logs/rules_engine.log` 2026-09-29 22:52：等待 53559，实际登记 53182） |
| 依赖中途退出 | 宿主已有的「依赖已停止」警告为界；**本模块不自动重启依赖**，`/health` 里把 `status` 置 `degraded`、`degraded_reason=upstream_down`，业务端点返回 503 + `UPSTREAM_*` 错误码；依赖重启后应能自动跟到新端口，不需要重启本模块 |
| 端口被占用 | 若 `config.port` 指定且被占用 → 启动失败并提示换端口；若未指定 → 用 `0` 自动分配，不冲突 |
| 注册文件残留 | 启动时若发现同 id 的残留注册文件，**先探测其 `/health`**：无响应则覆盖，有响应则报错退出（避免双实例） |

---

## 6. 契约副本：模块怎么拿到字段定义

模块被安装到 `modules/<id>/` 后，运行时**不应该依赖仓库根目录的 `contracts/`**（打包分发时不存在）。约定：

| 方式 | 说明 |
| --- | --- |
| **推荐** | 用 `contracts/scripts/generate.py` 生成物：前端用 `generated/domain.ts`，后端用生成的数据模型（见 §7 待补项）。模块只依赖生成物，不读 schema 原件 |
| 可选 | 把 `contracts/schemas/*.json` 作为**辅助文件**打进模块 ZIP（宿主安装器允许辅助文件，单文件 ≤20MB、总解压 ≤80MB） |
| 禁止 | 在模块代码里手写字段名字符串常量 —— 必须来自生成物，否则契约升级时漏改 |

---

## 7. 待补项（不阻塞开工，但要在第 1 周内完成）

| # | 事项 | 影响 | 优先级 |
| --- | --- | --- | --- |
| R-1 | `generate.py` 增加 **Python 模型生成器**（从 schema 生成 dataclasses/pydantic） | 后端三个模块的类型来源 | 高 |
| R-2 | 注册表的读写工具（各模块共用的 ~30 行代码） | 避免三个人各写一份 | 高 |
| R-3 | `MOCK` 与真实模块同签名的验证脚本 | 替换时确认零改动 | 中 |
| R-4 | 宿主的模块卡片显示端口与 `/health` 状态 | 纯展示，可选 | 低 |

> R-1/R-2 是三个人的共同前置，建议由契约负责人（你）先做掉，再放三个人并行——否则会出现三份各自实现的注册表客户端。

---

## 8. 测试约定

| 层次 | 做法 |
| --- | --- |
| 单模块单元测试 | 直接实例化服务或调用纯函数；不依赖注册表 |
| 单模块契约测试 | 启动自己的服务（`port=0`），用 `contracts/schemas/*.json` 校验自己的响应体 |
| 跨模块集成测试 | 在测试夹具里按依赖顺序启动两个服务，读注册表拿 `base_url` + `token`，断言调用链 |
| 故障注入 | 依赖不可达时断言：`/health` 变 `degraded`、业务端点返回 503 + `UPSTREAM_TIMEOUT`、有明确日志（不允许静默重试成功之外的任何行为） |

**每个模块的 PR 必须能独立跑通**：`python -m unittest discover -s modules/<id>/tests -v`，不要求全链路。这样三个人才能真正并行。
