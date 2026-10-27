import argparse
import sys
from datetime import datetime
from pathlib import Path

from .storyboard import demo, dumps, load


def main():
    parser = argparse.ArgumentParser(description="AI 短视频制作助手：分镜 → 画面 / 配音 / 字幕 → MP4")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("gui", help="打开中文桌面界面")
    plan_cmd = commands.add_parser("plan", help="用模型接口生成分镜")
    plan_cmd.add_argument("topic", help="视频主题与要求")
    plan_cmd.add_argument("-o", "--output", default="storyboard.json")
    for name, help_text in [("demo", "不调用 AI，直接制作示例视频"), ("render", "根据 JSON 分镜制作视频")]:
        cmd = commands.add_parser(name, help=help_text)
        if name == "render":
            cmd.add_argument("storyboard")
        cmd.add_argument("-o", "--output", help="新的输出文件夹；已存在时拒绝覆盖")
        cmd.add_argument("--profile", choices=["vertical", "landscape", "preview"], default="vertical")
        cmd.add_argument("--font", help="中文字体 .ttf / .ttc / .otf 路径")
        cmd.add_argument("--voice", help="开启在线配音，如 zh-CN-XiaoxiaoNeural；不填则静音")
    args = parser.parse_args()
    try:
        if args.command in (None, "gui"):
            from .gui import launch
            launch()
        elif args.command == "plan":
            from .planner import plan
            result = dumps(plan(args.topic))
            with Path(args.output).open("x", encoding="utf-8") as stream:
                stream.write(result)
            print(f"分镜已保存：{args.output}")
        else:
            from .render import render
            data = demo() if args.command == "demo" else load(args.storyboard)
            output = args.output or str(Path("renders") / datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
            render(data, output, profile=args.profile, font=args.font, voice=args.voice)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
