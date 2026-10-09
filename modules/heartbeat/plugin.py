def run(context):
    interval = float(context.config.get("interval", 5))
    if not 0.1 <= interval <= 3600:
        raise ValueError("interval 必须在 0.1 到 3600 秒之间")
    message = context.config.get("message", "模块运行正常")
    count = 0
    context.log("心跳模块就绪")
    while not context.should_stop():
        count += 1
        context.log(f"{message} · 第 {count} 次心跳")
        if context.wait(interval):
            break
    context.log("已收到停止请求，心跳模块退出")
