def run(context):
    name = str(context.config.get("name", "新朋友"))
    message = f"你好，{name}！这是通过可插拔模块生成的问候。"
    target = context.data_dir / "greeting.txt"
    target.write_text(message, encoding="utf-8")
    context.log(message)
    context.log(f"文件已保存：{target}")
