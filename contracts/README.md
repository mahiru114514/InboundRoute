# 数据与模块契约

此目录包含软件使用的数据定义、生成类型及模块服务注册工具。体验软件请从仓库首页的 [启动说明](../README.md) 开始；本目录主要用于维护源码。

- `schemas/`：行程、景点、路线、车站和推荐方案的数据定义。
- `generated/`：生成的 TypeScript 类型、Python 模型及字段说明。
- `runtime/`：模块服务注册与依赖等待工具。
- `examples/`：数据示例。
- [模块运行规范](MODULE_RUNTIME.md)：端口、注册表、服务认证与依赖。
- [时间字段约定](TIME_BASELINE.md)：UTC 时间戳与上海本地日期。
- [字段说明](generated/README.md)：生成的数据字段表。

维护时修改 `schemas/`，再运行生成脚本；请勿直接修改 `generated/`。在项目根目录执行：

```bash
python contracts/scripts/validate.py
python contracts/scripts/generate.py --check
python contracts/scripts/check_runtime.py
```

修改数据定义后，运行 `python contracts/scripts/generate.py` 更新生成文件。
