# 评委体验：高德 API Key 配置教程

当前体验版在本机运行。无需 Key 即可体验行程编辑、预算、多语言界面和演示路线；如需获取高德在线路线，请按下面的步骤使用自己的 Web服务 Key。

后续计划接入统一服务器。服务上线并发布完成接入的版本后，评委将无需自行申请或配置高德 Key。**当前服务器尚未接入，真实在线路线仍需按本教程配置。**

## 1. 申请正确的 Key

打开[高德开放平台控制台](https://console.amap.com/dev/key)，登录并完成控制台要求的账号认证。

1. 在“应用管理 → 我的应用”创建一个应用，名称可填 `InboundRoute`。
2. 在应用中添加 Key，服务平台选择 **Web服务**，用于步行、驾车和公交路线计算。
3. 按控制台提示确认路径规划服务可用、账户权限和额度满足体验需要。
4. IP 白名单用于限制请求的公网出口 IP。个人本机测试时可留空；已经填写的白名单会限制名单之外的网络。不要填 `127.0.0.1` 或局域网 IP 来代替公网出口 IP。[高德白名单说明](https://lbs.amap.com/faq/webservice/webservice-api/basic-configuration/43238)
5. 当前程序未实现 Web服务的 `sig` 数字签名。请选择未启用数字签名的独立测试 Key；已启用签名的 Key 不能直接用于本教程。
6. 创建后复制 Key，保存在自己的电脑上。

路线计算使用的 **Web服务** Key，与显示官方底图的 **Web端(JS API)** Key 是两种配置，不能互换。[高德 Web服务 Key 申请说明](https://lbs.amap.com/api/webservice/create-project-and-key)

## 2. 在项目文件夹打开 PowerShell

解压仓库 ZIP，进入能看到 `start_software.py` 的文件夹。在资源管理器地址栏输入 `powershell` 并回车，即可在该目录打开 PowerShell。

需要 Python 3.10 或更新版本。先运行：

```powershell
python --version
```

如果软件已经运行，请到原启动窗口按 **Ctrl+C**，等待退出后再配置。另一个 `start.bat` 管理窗口也应先关闭。

## 3. 输入 Key，并切换到真实路线

在 PowerShell 中运行以下命令，提示出现后粘贴自己的 **Web服务 Key** 并回车。实际 Key 不会写进下面的命令文本，也不会由本教程写入配置文件：

```powershell
$env:AMAP_WEB_KEY = Read-Host "请输入你的高德 Web服务 Key"
$env:PYTHONIOENCODING = "utf-8"
```

继续复制执行下面的整段命令。它把路线模块切换为高德，并设置上海公交查询；其他模块的配置不变。旧的路线 Key 和代理地址会从该模块配置中清除，确保使用本次输入的 Key 直接调用高德。

```powershell
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
@'
from pathlib import Path
from core.manager import Manager

manager = Manager(Path.cwd())
try:
    config = manager.config("route_adapter")
    config["provider"] = "amap"
    amap = config.setdefault("providers", {}).setdefault("amap", {})
    for field in ("api_key", "key", "base_url"):
        amap.pop(field, None)
    amap.update({"city": "上海", "timeout_seconds": 8})
    manager.configure("route_adapter", config)
    print("路线配置已保存")
finally:
    manager.close()
'@ | python -X utf8 -
```

看到“路线配置已保存”后继续。若提示“请先停止模块再修改配置”，先停止原来的软件，再重试本节。

## 4. 验证连接并启动

在**同一个 PowerShell 窗口**运行：

```powershell
python -X utf8 tools/smoke_amap.py --modes walk,taxi,transit --require-key
```

该检查会对每种交通方式各请求一次。`status: passed` 表示取得了有效路线；`failed` 表示需要按返回的诊断排查。输出不会包含 Key 或完整请求 URL。

检查通过后，在同一窗口启动：

```powershell
python -X utf8 start_software.py --all
```

浏览器打开行程工作台后，新建或打开行程，添加景点并重新计算交通，检查路线来源为 `amap`。不能仅凭模块显示“运行中”判断 Key 的权限、额度和网络一定正常。

## 5. 可选：使用高德官方底图

默认地图展示不要求配置 JS API Key。需要切换到高德官方 JS API 时，再申请一个服务平台为 **Web端(JS API)** 的 Key，并取得它对应的安全密钥 `securityJsCode`。参见[高德 JS API 准备说明](https://lbs.amap.com/api/javascript-api-v2/prerequisites)。

先按 Ctrl+C 停止软件，在刚才的 PowerShell 窗口执行：

```powershell
$env:AMAP_JS_KEY = Read-Host "请输入你的高德 Web端(JS API) Key"
$env:AMAP_SECURITY_CODE = Read-Host "请输入该 JS API Key 对应的安全密钥"
$env:MAP_PROVIDER = "amap"
python -X utf8 start_software.py --all
```

JS API Key 的域名白名单与 Web服务 Key 的 IP 白名单不同。本机页面使用 `127.0.0.1`；域名配置及地图报错的详细说明见[地图接入指引](高德地图接入指引.md)。JS API Key 及安全密钥会提供给本机浏览器加载地图，截图和分享时请避免泄露。

## 6. 下次启动与常见问题

上述 `$env:` 配置只在当前 PowerShell 窗口及它启动的程序中有效。关闭窗口后不会永久保存 Key。下次使用真实路线时，在项目目录重新打开 PowerShell，执行第 3 节的 Key 输入命令，再执行第 4 节的启动命令。路线模块配置已保存，不必重复执行配置脚本。

如果需要官方底图，也需重新输入第 5 节的两个值。直接双击批处理文件不会继承另一个 PowerShell 窗口中的临时 Key。

| 现象或错误码 | 处理方式 |
| --- | --- |
| 找不到 `python` | 安装 Python 3.10+ 并加入 PATH，重新打开 PowerShell |
| `skipped` 或“未设置 AMAP_WEB_KEY” | 在当前窗口重新输入 Web服务 Key |
| `10001` | 核对 Key 是否完整、有效 |
| `10005` / `INVALID_USER_IP` | 核对公网出口 IP 与白名单，个人测试可按第 1 节留空 |
| `10007` | 该 Key 启用了数字签名，当前接入不支持 `sig` |
| `10009` | 平台类型不匹配；路线需要 Web服务 Key |
| `10002` / `10012` | 核对服务权限；`10002` 也可能是接口路径错误 |
| 检查通过，但工作台仍提示缺 Key | 停止旧软件，在输入 Key 的同一窗口重新启动 |
| `INVALID_USER_SCODE` / `INVALID_USER_DOMAIN` | 核对 JS API 安全密钥或域名白名单，详见地图接入指引 |

完整含义见[高德官方错误码说明](https://lbs.amap.com/api/webservice/guide/tools/info/)。请勿把 Key、含密钥的截图或本机配置上传到公开 GitHub；反馈时只提供报错文字和操作步骤。

## 后续服务器接入后的体验

计划由统一服务器保存高德服务凭据并转发请求，评委使用发布版中预设的服务地址。完成服务器部署、客户端接入和验证后，评委将无需自行配置高德 Key；如使用 IP 白名单，将配置服务器的固定公网出口 IP。

这是后续接入计划，不代表当前仓库已经提供公共在线服务。服务上线时会更新本教程和仓库首页，明确可直接使用的版本。
