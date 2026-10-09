# InboundRoute 契约包（Contract Pack）

> **定位**：这是**独立交付物，不是运行时模块**。它只产出「规范 + 字段表 + 校验器 + 类型」，不承载业务逻辑，不被任何模块在运行时 import（只有字段校验会用到 `validate.py`）。
> **为什么独立**：9 个开发单元全部依赖它（见 `../InboundRoute_模块开发说明书.md` §2）。它必须先冻结、单独评审、可单独发版；混进任一模块都会导致契约被业务代码污染。

## 一个人负责时的用法

按 §4 的验收清单逐张表冻结。**每冻结一张就勾掉，并把决定写进 `CHANGELOG.md`**——三个人（或更多人）之后都按这里的字段名写代码，谁也不许自己加字段。

## 1. 单一事实源

```
schemas/*.schema.json      ← 唯一权威。所有字段、类型、必填、枚举都在这里
        │
        ├─ 生成 → generated/domain.ts        前端类型（零依赖）
        ├─ 生成 → generated/models.py        后端 dataclass 模型（纯标准库）
        ├─ 生成 → generated/schema_store.py  内联 schema + validate()（模块自校验用）
        ├─ 生成 → generated/README.md        字段表文档（人读）
        └─ 约束 → runtime/registry.py        模块运行时公共库（注册表 / 端口 / 依赖等待）
```

**规则：只改 schema，不手改 generated/。** 手改会在 CI 里被 `--check` 拦下。

**放置约定**（避免东西乱放）：
- `runtime/` = 运行时工具，模块 import 它；**不依赖 `generated/`**
- `generated/` = 脚本产出，**不许手改**；**不依赖 `runtime/`**
- `scripts/_bundle.py` = 两个脚本共用的 schema 内联逻辑
- 业务逻辑、UI、规则求值一律不进本包

## 2. 目录说明

| 文件 | 内容 | 谁消费 |
| --- | --- | --- |
| `DECISIONS.md` | C1–C6 每张契约的冻结版本与**我替你做的默认决策**（标注为待产品确认） | 全员 |
| `schemas/poi.schema.json` | POI Master（含闭馆/亮灯/营业时间/分类） | B（规则）、A（详情抽屉）、数据运营 |
| `schemas/trip.schema.json` | TripInstance（行程、日程、停靠点、区段） | A、B、C |
| `schemas/route.schema.json` | RouteSegment（Route Adapter 归一化输出） | C、五（离线包） |
| `schemas/station.schema.json` | CuratedStation（核心站台库，PRD 中缺实体） | C |
| `schemas/api.schema.json` | API 端点清单、请求/响应、统一错误体 | A、B、C |
| `enums.json` | 所有枚举的唯一取值域（星期、模式、分类、降级原因…） | 全员 |
| `rules.json` | Rule-01~04 决策表（触发、硬软、优先级、提示承载、缺失行为） | B |
| `mappings.json` | 字段→文案→空值降级映射、分类→Interests 映射、三方字段映射 | A、C |
| `errors.json` | 错误码表 | 全员 |
| `TIME_BASELINE.md` | 时间基准规范（C1，最容易出错的一张） | 全员 |
| `MODULE_RUNTIME.md` | **模块运行时契约（C7）**：模块自己暴露 HTTP、端口与注册表、令牌、依赖等待、契约副本 | 全员 |
| `scripts/generate.py` | 从 schema 生成 TS 类型、字段表、**Python 模型**、schema_store | 契约负责人 |
| `scripts/validate.py` | 校验契约本身：schema 自检 + 示例 + 时间自洽 + 方案 A 回归 | CI / 契约负责人 |
| `scripts/check_runtime.py` | 校验生成物可用性：模型往返 + 注册表读写 + /health 探测 | CI / 契约负责人 |
| `scripts/_bundle.py` | schema 内联与 $defs 打平的共享实现（两个脚本共用） | 契约负责人 |
| `runtime/registry.py` | **模块运行时公共库**：注册表读写、端口绑定、/health 探测、依赖等待、带令牌调用（纯标准库） | A、B、C |
| `examples/*.json` | 合法与非法样例（Rule-01 正例、跨零点例、降级例…） | 测试 |
| `devdocs/开发者A-开发需求文档.md` | **A 的开发需求**：模块范围、契约清单、4 个交付块、AI 提示词、验收清单 | 开发者 A |
| `devdocs/开发者B-开发需求文档.md` | **B 的开发需求**：规则与时序、方案 A 四条护栏、35 条 TC、AI 提示词 | 开发者 B |
| `devdocs/开发者C-开发需求文档.md` | **C 的开发需求**：Mock 优先、降级矩阵、离线包、AI 提示词 | 开发者 C |
| `RULE_TEST_CASES.md` | 35 条 GWT 用例（B 的测试清单，含伪代码骨架） | B、测试 |
| `SOFT_RULE_DECISION.md` | C3 方案 A 的决策存档（三方案对比与被否决理由） | 全员 |

## 3. 快速开始

```bash
cd contracts
python scripts/validate.py           # 155 项：契约自身（schema 自检 + 示例 + 时间自洽 + 方案 A 回归）
python scripts/generate.py           # 从 schema 重新生成 generated/（TS 类型、字段表、Python 模型、schema_store）
python scripts/generate.py --check   # CI：确认 generated/ 与 schema 同步（不同步则失败）
python scripts/check_runtime.py      # 42 项：生成物与运行时库（模型往返 + 注册表 + /health 探测）
```

**三个脚本都必须绿**才算契约健康。CI 建议按 `validate → generate --check → check_runtime` 顺序跑。

## 4. 模块怎么用这份契约（C7 方案一）

```python
# modules/<你的模块>/plugin.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent   # <workspace>
sys.path.insert(0, str(ROOT))

from contracts.generated.models import Route          # 后端类型（dataclass）
from contracts.generated.schema_store import validate  # 响应体自校验
from contracts.runtime import registry                 # 注册表 / 端口 / 依赖等待

def run(context):
    server = registry.bind_socket(port=registry.resolve_port(context.config))
    port = server.getsockname()[1]
    token = registry.new_token()
    registry.check_no_live_instance(ROOT, "route_adapter")        # 防双实例
    registry.write(registry.build_registration("route_adapter", port, token,
                                              depends_on=["trip_engine"],
                                              endpoints=["/health", "/routes:compute"]), ROOT)
    upstream, health = registry.wait_for_registration(ROOT, "trip_engine")  # 等它就绪（超时抛错）；
                                                                           # 每轮重读注册表，
                                                                           # 依赖换端口也能跟上
    try:
        while not context.wait(1):
            ...
    finally:
        registry.remove(ROOT, "route_adapter")
```

> 契约包目录是**命名空间包**（无 `__init__.py`），所以 `sys.path` 必须指向 `<workspace>` 而不是 `contracts/`。
> 模块不要 import 别的模块的代码，也不要把业务数据塞进 `context.config`（详见 `MODULE_RUNTIME.md`）。

## 5. 冻结验收清单

| # | 契约 | 冻结标志 | 状态 |
| --- | --- | --- | --- |
| C1 | 时间基准 | `TIME_BASELINE.md` 评审通过；示例数据时间自洽 | ✅ 已冻结 |
| C2 | 实体字段表 | 4 个 schema 通过 `validate.py`；字段表文档生成无误 | ✅ 已冻结（星期 ISO） |
| C3 | 规则执行规范 | `rules.json` 决策表评审通过；执行顺序唯一确定 | ✅ 已冻结（方案 A） |
| C4 | API 契约 | `api.schema.json` + `errors.json` 评审通过 | ⚠️ 端点已定，接口风格待确认 |
| C5 | Adapter 归一化 | `route.schema.json` 覆盖三模态与降级标记 | ✅ 已冻结（CRS 责任已定） |
| C6 | 三方实测 | `mappings.json` 中标注哪些字段来自三方、哪些来自站台库 | ☐ 待实测回填 |
| C7 | 模块运行时 | `MODULE_RUNTIME.md` + `runtime/registry.py` 可用 | ✅ 已冻结（方案一 + R-1/R-2 落地） |

## 6. 与主项目的边界

- **本包不写业务逻辑**：规则求值、路线编排、UI 全在各自模块。
- **本包不含密钥与配置**：三方 key、配额策略属于运行时配置，不进契约；模块令牌只在注册文件里。
- **发版**：契约变更走 `CHANGELOG.md` + `version` 字段；破坏性变更必须升主版本并通知三个模块负责人。

