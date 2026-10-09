"""独立测试模块，仅使用 Python 标准库。"""
import json
import math
from datetime import datetime


def run(context):
    count = context.config.get("count", 10)
    interval = context.config.get("interval", 2)
    message = context.config.get("message", "你好，模块接入成功！")
    if type(count) is not int or not 1 <= count <= 1000:
        raise ValueError("count 必须是 1 到 1000 之间的整数")
    if type(interval) not in (int, float) or not math.isfinite(interval) or not 0.01 <= interval <= 60:
        raise ValueError("interval 必须是 0.01 到 60 之间的秒数")
    if not isinstance(message, str):
        raise ValueError("message 必须是文本")

    result = {"message": message, "requested": count, "completed": 0,
              "started_at": datetime.now().isoformat(timespec="seconds"), "status": "running"}
    target = context.data_dir / "result.json"

    def save():
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)

    save()
    context.log(f"接入练习开始：共 {count} 次，间隔 {interval} 秒")
    for index in range(count):
        if context.should_stop():
            break
        result["completed"] = index + 1
        context.log(f"[{index + 1}/{count}] {message}")
        save()
        if index + 1 < count and context.wait(interval):
            break
    result["status"] = "completed" if result["completed"] == count else "stopped"
    result["finished_at"] = datetime.now().isoformat(timespec="seconds")
    save()
    context.log("测试完成" if result["status"] == "completed" else "已响应停止请求")
    context.log(f"结果文件：{target}")
