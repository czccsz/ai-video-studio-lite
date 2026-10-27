"""Tk desktop front end; workers communicate with Tk only through a queue."""

import json
import os
import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .planner import plan
from .render import render
from .storyboard import demo, dumps, load, validate


class Studio:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.buttons = []
        root.title("映简 · AI 短视频制作助手")
        root.geometry("1000x820")
        root.minsize(820, 650)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", padding=8)
        frame = ttk.Frame(root, padding=22)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="映简  /  AI VIDEO STUDIO", font=("Microsoft YaHei UI", 20, "bold")).pack(anchor="w")
        ttk.Label(frame, text="把主题变成分镜，把分镜变成视频。先试用示例，再接入你自己的 AI。", padding=(0, 8)).pack(anchor="w")
        config = ttk.LabelFrame(frame, text="AI 接口（仅生成分镜时需要；密钥不保存）", padding=10)
        config.pack(fill="x", pady=8)
        self.base = tk.StringVar(value=os.getenv("AI_BASE_URL", "https://api.deepseek.com"))
        self.model = tk.StringVar(value=os.getenv("AI_MODEL", ""))
        self.key = tk.StringVar(value=os.getenv("AI_API_KEY", ""))
        for row, (label, variable) in enumerate([("基础地址", self.base), ("模型名称", self.model), ("接口密钥", self.key)]):
            ttk.Label(config, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=3)
            ttk.Entry(config, textvariable=variable, show="•" if row == 2 else "").grid(row=row, column=1, sticky="ew")
        config.columnconfigure(1, weight=1)
        ttk.Label(frame, text="1. 输入视频主题").pack(anchor="w", pady=(8, 4))
        self.topic = ttk.Entry(frame)
        self.topic.insert(0, "用 30 秒向新手讲清楚：怎么用 AI 提高办公效率")
        self.topic.pack(fill="x")
        controls = ttk.Frame(frame)
        controls.pack(fill="x", pady=8)
        self.button(controls, "AI 生成分镜", self.generate)
        self.button(controls, "加载示例", lambda: self.set_script(demo()))
        self.button(controls, "导入分镜", self.import_script)
        self.button(controls, "保存分镜", self.save_script)
        ttk.Label(frame, text="2. 检查并编辑分镜（可给每个分镜添加 image 字段，填写图片完整路径）").pack(anchor="w", pady=(6, 4))
        self.editor = scrolledtext.ScrolledText(frame, height=13, wrap="word", font=("Consolas", 11), undo=True)
        self.editor.pack(fill="both", expand=True)
        self.set_script(demo())
        options = ttk.Frame(frame)
        options.pack(fill="x", pady=10)
        self.profile = tk.StringVar(value="vertical")
        ttk.Label(options, text="画面").pack(side="left")
        ttk.Combobox(options, textvariable=self.profile, values=["vertical", "landscape", "preview"], state="readonly", width=12).pack(side="left", padx=8)
        self.voiced = tk.BooleanVar(value=False)
        ttk.Checkbutton(options, text="在线中文配音（旁白会发送到语音服务）", variable=self.voiced).pack(side="left", padx=10)
        self.button(options, "选择中文字体", self.select_font)
        self.font = None
        self.button(options, "导出 MP4", self.export)
        ttk.Label(frame, text="竖屏 720×1280 · 横屏为居中卡片 · preview 为快速预览 · 字幕按分镜显示").pack(anchor="w")
        self.status = tk.StringVar(value="已加载离线示例。可以直接点击“导出 MP4”。")
        ttk.Label(frame, textvariable=self.status, wraplength=900, padding=(0, 10)).pack(anchor="w")
        root.after(100, self.poll)

    def button(self, parent, label, command):
        button = ttk.Button(parent, text=label, command=command)
        button.pack(side="left", padx=(0, 8))
        self.buttons.append(button)

    def set_script(self, data):
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", dumps(data))

    def read_script(self):
        return validate(json.loads(self.editor.get("1.0", "end")))

    def worker(self, action, kind):
        for button in self.buttons:
            button.configure(state="disabled")
        self.status.set("正在处理，请稍候……")
        def task():
            try:
                self.events.put((kind, action()))
            except Exception as exc:
                self.events.put(("error", str(exc)))
            finally:
                self.events.put(("done", None))
        threading.Thread(target=task, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "script":
                    self.set_script(value)
                    self.status.set("分镜已生成，请检查内容后再导出。")
                elif kind == "video":
                    self.status.set(f"导出完成：{value}")
                    messagebox.showinfo("视频已导出", f"文件位置：\n{value}")
                elif kind == "progress":
                    self.status.set(value)
                elif kind == "error":
                    self.status.set(value)
                    messagebox.showerror("操作未完成", value)
                elif kind == "done":
                    for button in self.buttons:
                        button.configure(state="normal")
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def generate(self):
        topic, base, model, key = self.topic.get(), self.base.get(), self.model.get(), self.key.get()
        self.worker(lambda: plan(topic, base_url=base, model=model, api_key=key), "script")

    def import_script(self):
        path = filedialog.askopenfilename(filetypes=[("JSON 分镜", "*.json")])
        if path:
            try:
                self.set_script(load(path))
            except Exception as exc:
                messagebox.showerror("无法导入", str(exc))

    def save_script(self):
        try:
            content = dumps(self.read_script())
            path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON 分镜", "*.json")])
            if path:
                Path(path).write_text(content, encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("无法保存", str(exc))

    def select_font(self):
        path = filedialog.askopenfilename(filetypes=[("字体文件", "*.ttf *.ttc *.otf")])
        if path:
            self.font = path
            self.status.set(f"已选择字体：{Path(path).name}")

    def export(self):
        try:
            data = self.read_script()
        except Exception as exc:
            messagebox.showerror("请检查分镜 JSON", str(exc))
            return
        folder = filedialog.askdirectory(title="选择保存位置（会创建独立的时间文件夹）")
        if not folder:
            return
        output = Path(folder) / datetime.now().strftime("video-%Y%m%d-%H%M%S-%f")
        profile, font = self.profile.get(), self.font
        voice = "zh-CN-XiaoxiaoNeural" if self.voiced.get() else None
        self.worker(lambda: render(data, output, profile=profile, font=font, voice=voice,
                                  progress=lambda message: self.events.put(("progress", message))), "video")


def launch():
    root = tk.Tk()
    Studio(root)
    root.mainloop()
