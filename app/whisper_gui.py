#!/usr/bin/env python3
"""Small macOS Tk wrapper for the bundled infra-ingest backend."""

import os
import queue
import subprocess
import sys
import tempfile
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk


APP_RESOURCES = Path(__file__).resolve().parent
PACKAGED_BACKEND_DIR = APP_RESOURCES / "infra-ingest"
SOURCE_BACKEND_DIR = APP_RESOURCES.parent
BACKEND_DIR = PACKAGED_BACKEND_DIR if (PACKAGED_BACKEND_DIR / "main.py").exists() else SOURCE_BACKEND_DIR
BACKEND_MAIN = BACKEND_DIR / "main.py"
DEFAULT_OUTPUT = Path.home() / "Documents" / "Whisper转写笔记"
MATERIAL_TYPES = [
    ("auto", "自动识别"),
    ("research_report", "研报"),
    ("earnings_call", "财报电话会"),
    ("announcement", "公告"),
    ("expert_interview", "专家访谈"),
    ("podcast", "播客"),
    ("meeting_minutes", "会议纪要"),
]


def detect_default_output():
    """Prefer an Obsidian-like folder, otherwise use a normal Documents folder."""
    candidates = [
        Path.home() / "Documents" / "Obsidian Vault",
        Path.home() / "Documents" / "Obsidian",
        Path.home() / "Library" / "Mobile Documents" / "iCloud~md~obsidian" / "Documents",
    ]
    for path in candidates:
        if path.exists():
            return path
    DEFAULT_OUTPUT.mkdir(parents=True, exist_ok=True)
    return DEFAULT_OUTPUT


def is_url(value):
    value = value.strip().lower()
    return value.startswith("http://") or value.startswith("https://")


class MarkdownTranscriberApp:
    def __init__(self, root):
        self.root = root
        self.root.title("infra-ingest 研究工作台")
        self.root.geometry("1120x760")
        self.root.minsize(980, 680)
        self.root.configure(bg="#101214")
        self.output_queue = queue.Queue()
        self.worker = None

        self.input_mode = tk.StringVar(value="url")
        self.url_var = tk.StringVar()
        self.file_var = tk.StringVar()
        self.output_var = tk.StringVar(value=str(detect_default_output()))
        self.model_var = tk.StringVar(value="small")
        self.language_var = tk.StringVar(value="zh")
        self.material_type_var = tk.StringVar(value="自动识别")
        self.title_var = tk.StringVar()
        self.glossary_var = tk.StringVar()
        self.price_data_var = tk.StringVar()
        self.financial_data_var = tk.StringVar()
        self.event_date_var = tk.StringVar()
        self.benchmark_ticker_var = tk.StringVar()
        self.use_llm_var = tk.BooleanVar(value=False)
        self.api_key_var = tk.StringVar()
        self.base_url_var = tk.StringVar(value="https://api.deepseek.com/v1")
        self.llm_model_var = tk.StringVar(value="deepseek-chat")

        self._build_style()
        self._build_ui()
        self._poll_output()

    def _build_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background="#101214", foreground="#edf2f4")
        style.configure("TFrame", background="#101214")
        style.configure("Panel.TFrame", background="#1a1d21")
        style.configure("Soft.TFrame", background="#20242a")
        style.configure("TLabel", background="#101214", foreground="#edf2f4", font=("Helvetica Neue", 11))
        style.configure("Panel.TLabel", background="#1a1d21", foreground="#edf2f4", font=("Helvetica Neue", 11))
        style.configure("Muted.TLabel", background="#101214", foreground="#8c98a4", font=("Helvetica Neue", 10))
        style.configure("PanelMuted.TLabel", background="#1a1d21", foreground="#8c98a4", font=("Helvetica Neue", 10))
        style.configure("Title.TLabel", background="#101214", foreground="#ffffff", font=("Helvetica Neue", 24, "bold"))
        style.configure("Section.TLabel", background="#1a1d21", foreground="#ffffff", font=("Helvetica Neue", 12, "bold"))
        style.configure("Metric.TLabel", background="#20242a", foreground="#dce3ea", font=("Helvetica Neue", 10, "bold"))
        style.configure(
            "TEntry",
            fieldbackground="#101214",
            foreground="#ffffff",
            bordercolor="#343a40",
            lightcolor="#343a40",
            darkcolor="#343a40",
            insertcolor="#ffffff",
            padding=8,
        )
        style.configure(
            "TCombobox",
            fieldbackground="#101214",
            background="#101214",
            foreground="#ffffff",
            bordercolor="#343a40",
            arrowcolor="#dce3ea",
            padding=7,
        )
        style.configure("TButton", background="#2a3037", foreground="#ffffff", borderwidth=0, padding=(12, 8))
        style.map("TButton", background=[("active", "#36404a"), ("disabled", "#1a1d21")])
        style.configure(
            "Primary.TButton",
            background="#0f8b8d",
            foreground="#ffffff",
            padding=(14, 12),
            font=("Helvetica Neue", 12, "bold"),
        )
        style.map("Primary.TButton", background=[("active", "#0b7375"), ("disabled", "#283136")])
        style.configure("Ghost.TButton", background="#1a1d21", foreground="#cbd5df", padding=(10, 7))
        style.map("Ghost.TButton", background=[("active", "#222830")])
        style.configure("TCheckbutton", background="#1a1d21", foreground="#edf2f4", font=("Helvetica Neue", 11))
        style.configure("TRadiobutton", background="#1a1d21", foreground="#edf2f4", font=("Helvetica Neue", 11))
        style.configure("Horizontal.TProgressbar", troughcolor="#20242a", background="#0f8b8d", bordercolor="#20242a")

    def _build_ui(self):
        shell = ttk.Frame(self.root, padding=(24, 20, 24, 20))
        shell.pack(fill="both", expand=True)

        header = ttk.Frame(shell)
        header.pack(fill="x", pady=(0, 18))
        title_box = ttk.Frame(header)
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Label(title_box, text="infra-ingest 研究工作台", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            title_box,
            text="转写、整理、结构化笔记和初步事件研究放在一个窗口里完成。",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 0))
        ttk.Button(header, text="打开输出目录", style="Ghost.TButton", command=self.open_output_dir).pack(side="right")

        body = ttk.Frame(shell)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=0)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body, style="Panel.TFrame", padding=18)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 16))
        right = ttk.Frame(body, style="Panel.TFrame", padding=18)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(4, weight=1)
        right.columnconfigure(0, weight=1)

        self._section_title(left, "输入")
        mode_row = ttk.Frame(left, style="Panel.TFrame")
        mode_row.pack(fill="x", pady=(0, 10))
        ttk.Radiobutton(mode_row, text="在线链接", value="url", variable=self.input_mode, command=self.switch_mode).pack(side="left")
        ttk.Radiobutton(mode_row, text="本地文件", value="file", variable=self.input_mode, command=self.switch_mode).pack(side="left", padx=(16, 0))

        self.url_row = ttk.Frame(left, style="Panel.TFrame")
        self._field(self.url_row, "链接", self.url_var)

        self.file_row = ttk.Frame(left, style="Panel.TFrame")
        self._field(self.file_row, "文件", self.file_var, button_text="选择", command=self.select_file)

        self._field(left, "输出目录", self.output_var, button_text="选择", command=self.select_output)
        self._field(left, "笔记标题", self.title_var)

        self._section_title(left, "模型与资料")
        grid = ttk.Frame(left, style="Panel.TFrame")
        grid.pack(fill="x", pady=(0, 10))
        ttk.Label(grid, text="Whisper", style="PanelMuted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Combobox(grid, textvariable=self.model_var, values=["tiny", "base", "small", "medium", "large-v3"], state="readonly", width=14).grid(row=1, column=0, sticky="we", pady=(4, 0))
        ttk.Label(grid, text="语言", style="PanelMuted.TLabel").grid(row=0, column=1, sticky="w", padx=(12, 0))
        ttk.Combobox(grid, textvariable=self.language_var, values=["zh", "en", "ja", "auto"], state="readonly", width=10).grid(row=1, column=1, sticky="we", padx=(12, 0), pady=(4, 0))
        ttk.Label(grid, text="资料类型", style="PanelMuted.TLabel").grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Combobox(
            grid,
            textvariable=self.material_type_var,
            values=[label for _value, label in MATERIAL_TYPES],
            state="readonly",
            width=18,
        ).grid(row=3, column=0, columnspan=2, sticky="we", pady=(4, 0))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        self._field(left, "词表文件", self.glossary_var, button_text="选择", command=self.select_glossary)

        self._section_title(left, "量化验证")
        self._field(left, "行情 CSV", self.price_data_var, button_text="选择", command=self.select_price_data)
        self._field(left, "财务 CSV", self.financial_data_var, button_text="选择", command=self.select_financial_data)
        quant_grid = ttk.Frame(left, style="Panel.TFrame")
        quant_grid.pack(fill="x", pady=(0, 10))
        ttk.Label(quant_grid, text="事件日", style="PanelMuted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(quant_grid, textvariable=self.event_date_var).grid(row=1, column=0, sticky="we", pady=(4, 0))
        ttk.Label(quant_grid, text="基准 ticker", style="PanelMuted.TLabel").grid(row=0, column=1, sticky="w", padx=(12, 0))
        ttk.Entry(quant_grid, textvariable=self.benchmark_ticker_var).grid(row=1, column=1, sticky="we", padx=(12, 0), pady=(4, 0))
        quant_grid.columnconfigure(0, weight=1)
        quant_grid.columnconfigure(1, weight=1)

        self._section_title(left, "LLM")
        ttk.Checkbutton(left, text="启用结构化笔记", variable=self.use_llm_var, command=self.toggle_llm).pack(anchor="w", pady=(0, 8))
        self.llm_fields = ttk.Frame(left, style="Panel.TFrame")
        self._field(self.llm_fields, "API Key", self.api_key_var, show="*")
        self._field(self.llm_fields, "Base URL", self.base_url_var)
        self._field(self.llm_fields, "模型", self.llm_model_var)
        self.toggle_llm()

        self.switch_mode()

        ttk.Label(right, text="运行状态", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        stats = ttk.Frame(right, style="Soft.TFrame", padding=14)
        stats.grid(row=1, column=0, sticky="we", pady=(10, 14))
        stats.columnconfigure(0, weight=1)
        stats.columnconfigure(1, weight=1)
        stats.columnconfigure(2, weight=1)
        self._metric(stats, "输出", "Markdown")
        self._metric(stats, "索引", "SQLite FTS")
        self._metric(stats, "验证", "5/20/60日")

        self.status_label = ttk.Label(right, text="就绪。选择资料后开始处理。", style="PanelMuted.TLabel")
        self.status_label.grid(row=2, column=0, sticky="w")
        self.progress = ttk.Progressbar(right, mode="indeterminate")
        self.progress.grid(row=3, column=0, sticky="we", pady=(8, 14))

        log_header = ttk.Frame(right, style="Panel.TFrame")
        log_header.grid(row=4, column=0, sticky="nsew")
        log_header.rowconfigure(1, weight=1)
        log_header.columnconfigure(0, weight=1)
        ttk.Label(log_header, text="处理日志", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.log = scrolledtext.ScrolledText(
            log_header,
            bg="#0d0f11",
            fg="#cbd5df",
            insertbackground="#ffffff",
            relief="flat",
            height=18,
            font=("SF Mono", 10),
            padx=12,
            pady=10,
        )
        self.log.grid(row=1, column=0, sticky="nsew")

        actions = ttk.Frame(right, style="Panel.TFrame")
        actions.grid(row=5, column=0, sticky="we", pady=(14, 0))
        actions.columnconfigure(0, weight=1)
        self.run_button = ttk.Button(actions, text="开始生成研究笔记", style="Primary.TButton", command=self.start)
        self.run_button.grid(row=0, column=0, sticky="we")
        ttk.Button(actions, text="清空日志", style="Ghost.TButton", command=lambda: self.log.delete("1.0", "end")).grid(row=0, column=1, padx=(10, 0))

    def _section_title(self, parent, text):
        ttk.Label(parent, text=text, style="Section.TLabel").pack(anchor="w", pady=(14, 8))

    def _field(self, parent, label, variable, button_text=None, command=None, show=None):
        row = ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill="x", pady=(0, 10))
        ttk.Label(row, text=label, style="PanelMuted.TLabel").pack(anchor="w", pady=(0, 4))
        line = ttk.Frame(row, style="Panel.TFrame")
        line.pack(fill="x")
        ttk.Entry(line, textvariable=variable, show=show).pack(side="left", fill="x", expand=True)
        if button_text and command:
            ttk.Button(line, text=button_text, command=command).pack(side="left", padx=(8, 0))

    def _metric(self, parent, label, value):
        box = ttk.Frame(parent, style="Soft.TFrame", padding=(8, 2))
        box.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Label(box, text=label, style="PanelMuted.TLabel").pack(anchor="w")
        ttk.Label(box, text=value, style="Metric.TLabel").pack(anchor="w", pady=(2, 0))

    def switch_mode(self):
        if self.input_mode.get() == "url":
            self.url_row.pack(fill="x", pady=(0, 10))
            self.file_row.pack_forget()
        else:
            self.url_row.pack_forget()
            self.file_row.pack(fill="x", pady=(0, 10))

    def toggle_llm(self):
        if self.use_llm_var.get():
            self.llm_fields.pack(fill="x")
        else:
            self.llm_fields.pack_forget()

    def select_file(self):
        path = filedialog.askopenfilename(
            title="选择文件",
            filetypes=[
                ("常见文件", "*.mp3 *.wav *.m4a *.mp4 *.mov *.mkv *.webm *.ogg *.pdf *.docx *.pptx *.xlsx *.csv *.txt *.md *.html"),
                ("所有文件", "*.*"),
            ],
        )
        if path:
            self.input_mode.set("file")
            self.file_var.set(path)
            self.switch_mode()

    def select_output(self):
        path = filedialog.askdirectory(title="选择 Markdown 输出目录")
        if path:
            self.output_var.set(path)

    def select_glossary(self):
        path = filedialog.askopenfilename(title="选择专有名词词表", filetypes=[("文本文件", "*.txt *.md *.csv"), ("所有文件", "*.*")])
        if path:
            self.glossary_var.set(path)

    def select_price_data(self):
        path = filedialog.askopenfilename(title="选择行情 CSV", filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")])
        if path:
            self.price_data_var.set(path)

    def select_financial_data(self):
        path = filedialog.askopenfilename(title="选择财务 CSV", filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")])
        if path:
            self.financial_data_var.set(path)

    def open_output_dir(self):
        output_dir = Path(self.output_var.get().strip() or DEFAULT_OUTPUT).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        webbrowser.open(output_dir.as_uri())

    def selected_material_type(self):
        label = self.material_type_var.get()
        for value, display in MATERIAL_TYPES:
            if label == display or label == value:
                return value
        return "auto"

    def append_log(self, text):
        self.log.insert("end", text)
        self.log.see("end")

    def _poll_output(self):
        try:
            while True:
                kind, value = self.output_queue.get_nowait()
                if kind == "log":
                    self.append_log(value)
                elif kind == "done":
                    self.progress.stop()
                    self.run_button.configure(state="normal")
                    self.status_label.configure(text=value)
                    if value.startswith("完成"):
                        messagebox.showinfo("完成", value)
                    else:
                        messagebox.showerror("失败", value)
        except queue.Empty:
            pass
        self.root.after(150, self._poll_output)

    def start(self):
        source = self.url_var.get().strip() if self.input_mode.get() == "url" else self.file_var.get().strip()
        if not source:
            messagebox.showwarning("缺少输入", "请粘贴链接，或选择一个本地文件。")
            return
        if self.input_mode.get() == "file" and not Path(source).exists():
            messagebox.showwarning("文件不存在", source)
            return

        output_dir = Path(self.output_var.get().strip() or DEFAULT_OUTPUT).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        self.output_var.set(str(output_dir))

        if self.use_llm_var.get() and not self.api_key_var.get().strip():
            messagebox.showwarning("缺少 API Key", "启用 LLM 时需要填写 API Key；也可以关闭 LLM，先生成基础 Markdown。")
            return

        self.log.delete("1.0", "end")
        self.run_button.configure(state="disabled")
        self.status_label.configure(text="正在处理...")
        self.progress.start(10)
        self.worker = threading.Thread(target=self._run_backend, args=(source, output_dir), daemon=True)
        self.worker.start()

    def _run_backend(self, source, output_dir):
        config_path = None
        try:
            cmd = [
                sys.executable,
                str(BACKEND_MAIN),
                "-i",
                source,
                "-o",
                str(output_dir),
                "--model",
                self.model_var.get(),
                "--beam-size",
                "5",
            ]
            language = self.language_var.get()
            if language and language != "auto":
                cmd.extend(["--language", language])
            if self.title_var.get().strip():
                cmd.extend(["--title", self.title_var.get().strip()])
            cmd.extend(["--material-type", self.selected_material_type()])
            if self.glossary_var.get().strip():
                cmd.extend(["--glossary-file", self.glossary_var.get().strip()])
            if self.price_data_var.get().strip():
                cmd.extend(["--price-data-csv", self.price_data_var.get().strip()])
            if self.financial_data_var.get().strip():
                cmd.extend(["--financial-data-csv", self.financial_data_var.get().strip()])
            if self.event_date_var.get().strip():
                cmd.extend(["--event-date", self.event_date_var.get().strip()])
            if self.benchmark_ticker_var.get().strip():
                cmd.extend(["--benchmark-ticker", self.benchmark_ticker_var.get().strip()])
            if not self.use_llm_var.get():
                cmd.append("--no-llm")
            else:
                config_path = self._write_runtime_env(output_dir)
                cmd.extend(["--env", str(config_path)])

            env = os.environ.copy()
            env["PATH"] = f"/opt/homebrew/bin:/usr/local/bin:{env.get('PATH', '')}"
            self.output_queue.put(("log", f"命令: {' '.join(cmd)}\n\n"))
            process = subprocess.Popen(
                cmd,
                cwd=str(BACKEND_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            assert process.stdout is not None
            for line in process.stdout:
                self.output_queue.put(("log", line))
            return_code = process.wait()
            if return_code == 0:
                self.output_queue.put(("done", f"完成：Markdown 已保存到 {output_dir}"))
            else:
                self.output_queue.put(("done", f"失败：后端退出码 {return_code}，请查看日志"))
        except Exception as exc:
            self.output_queue.put(("done", f"失败：{exc}"))
        finally:
            if config_path:
                try:
                    Path(config_path).unlink(missing_ok=True)
                except Exception:
                    pass

    def _write_runtime_env(self, output_dir):
        fd, path = tempfile.mkstemp(prefix="whisper_app_", suffix=".env")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"LLM_API_KEY={self.api_key_var.get().strip()}\n")
            f.write(f"LLM_BASE_URL={self.base_url_var.get().strip()}\n")
            f.write(f"LLM_MODEL={self.llm_model_var.get().strip()}\n")
            f.write("LLM_TIMEOUT=120\n")
            f.write("LLM_TEMPERATURE=0.3\n")
            f.write(f"OBSIDIAN_VAULT_PATH={output_dir}\n")
            f.write("TARGET_FOLDER=.\n")
            language = self.language_var.get()
            if language and language != "auto":
                f.write(f"WHISPER_LANGUAGE={language}\n")
            f.write("WHISPER_BEAM_SIZE=5\n")
            f.write("WHISPER_DEVICE=cpu\n")
            f.write("WHISPER_COMPUTE_TYPE=int8\n")
        return Path(path)


if __name__ == "__main__":
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", 2.0)
    except Exception:
        pass
    app = MarkdownTranscriberApp(root)
    root.mainloop()
