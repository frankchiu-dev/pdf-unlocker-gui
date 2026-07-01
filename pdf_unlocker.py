#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF 解鎖小工具
------------------------------------------------------------
把整個資料夾裡的 PDF 移除「密碼」與「權限限制」，
另存成一份乾淨、不需密碼的新 PDF（原始檔不會被更動）。

可處理兩種鎖：
  1. 開啟密碼：打開檔案就要輸入密碼，需要填入正確密碼。
  2. 權限密碼：開檔不用密碼，但被禁止列印／複製／編輯，通常留空即可解除。

使用前請先安裝套件（終端機執行一次就好）：
    pip install pikepdf

執行方式：
    python pdf_unlocker.py
    python pdf_unlocker.py 資料夾路徑
    python pdf_unlocker.py 資料夾路徑 輸出資料夾

重要界線：
    這個工具只適合處理你有合法權限的 PDF。
    它不會破解未知密碼，也不提供暴力猜密碼功能。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import pikepdf
except ImportError:
    sys.exit("找不到 pikepdf 套件，請先在終端機執行： pip install pikepdf")


def normalize_folder_path(value: str | Path) -> Path:
    """
    清理使用者從檔案總管或聊天視窗複製來的路徑。

    支援：
        "D:\\檔案"
        「D:\\檔案」
        D：\\檔案
    """
    text = str(value).strip().strip("\ufeff\u200e\u200f")
    quote_pairs = {
        '"': '"',
        "'": "'",
        "「": "」",
        "『": "』",
        "“": "”",
        "‘": "’",
    }

    changed = True
    while changed and len(text) >= 2:
        changed = False
        for left, right in quote_pairs.items():
            if text.startswith(left) and text.endswith(right):
                text = text[1:-1].strip().strip("\ufeff\u200e\u200f")
                changed = True
                break

    text = (
        text.replace("：", ":")
        .replace("＼", "\\")
        .replace("／", "/")
    )
    text = os.path.expandvars(text)
    return Path(text).expanduser()


def unlock_pdf(input_path: str | Path, output_path: str | Path, password: str = ""):
    """
    解開單一 PDF，輸出一份無加密的新檔。

    回傳：
        ("ok", "完成")
        ("wrong_password", "需要密碼或密碼錯誤")
        ("error", 錯誤訊息)
    """
    try:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with pikepdf.open(input_path, password=password) as pdf:
            # save 時不帶 encryption 參數，輸出的就是完全沒有加密的 PDF。
            pdf.save(output_path)
        return ("ok", "完成")
    except pikepdf.PasswordError:
        return ("wrong_password", "需要密碼或密碼錯誤")
    except Exception as exc:  # noqa: BLE001 需要把實際錯誤完整回報給使用者。
        return ("error", str(exc))


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _find_pdfs(input_dir: Path, output_dir: Path) -> list[Path]:
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()

    pdfs: list[Path] = []
    for path in input_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() != ".pdf":
            continue
        if _is_relative_to(path.resolve(), output_dir):
            continue
        pdfs.append(path)

    return sorted(pdfs)


def _unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = os.path.normcase(str(path.resolve()))
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _common_parent(paths: list[Path]) -> Path | None:
    if not paths:
        return None

    parents = [str(path.parent.resolve()) for path in paths]
    try:
        return Path(os.path.commonpath(parents))
    except ValueError:
        return paths[0].parent.resolve()


def collect_pdfs_from_paths(paths: list[str | Path], output_dir: str | Path | None = None) -> list[Path]:
    output_path = normalize_folder_path(output_dir).resolve() if output_dir else None
    pdfs: list[Path] = []

    for raw_path in paths:
        path = normalize_folder_path(raw_path).resolve()
        if path.is_dir():
            for pdf_path in sorted(path.rglob("*")):
                if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
                    continue
                if output_path and _is_relative_to(pdf_path.resolve(), output_path):
                    continue
                pdfs.append(pdf_path)
        elif path.is_file() and path.suffix.lower() == ".pdf":
            if output_path and _is_relative_to(path.resolve(), output_path):
                continue
            pdfs.append(path)

    return _unique_paths(pdfs)


def _dedupe_output_path(path: Path, used_paths: set[str]) -> Path:
    path_key = os.path.normcase(str(path.resolve()))
    if path_key not in used_paths:
        used_paths.add(path_key)
        return path

    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        candidate_key = os.path.normcase(str(candidate.resolve()))
        if candidate_key not in used_paths:
            used_paths.add(candidate_key)
            return candidate
        counter += 1


def unlock_pdf_files(
    pdf_paths: list[str | Path],
    output_dir: str | Path,
    password: str = "",
    base_dir: str | Path | None = None,
    log=print,
    progress=None,
):
    output_dir = normalize_folder_path(output_dir).resolve()
    pdfs = collect_pdfs_from_paths(pdf_paths, output_dir)
    stats = {"total": len(pdfs), "ok": 0, "wrong_password": 0, "error": 0}

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # noqa: BLE001 需要讓 GUI 顯示實際原因。
        stats["error"] = 1
        log(f"無法建立輸出資料夾：{output_dir}")
        log(str(exc))
        return stats

    if base_dir:
        base_path = normalize_folder_path(base_dir).resolve()
    else:
        base_path = _common_parent(pdfs)

    log(f"輸出資料夾：{output_dir}")

    if not pdfs:
        log("沒有可處理的 PDF。請拖入 PDF 檔，或拖入含 PDF 的資料夾。")
        return stats

    log(f"已選取 {len(pdfs)} 個 PDF，開始處理…\n")
    used_outputs: set[str] = set()

    for index, pdf_path in enumerate(pdfs, start=1):
        if base_path:
            try:
                rel = pdf_path.relative_to(base_path)
            except ValueError:
                rel = Path(pdf_path.name)
        else:
            rel = Path(pdf_path.name)

        out_path = output_dir / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if out_path.resolve() == pdf_path.resolve():
            out_path = out_path.with_name(out_path.stem + "_unlocked.pdf")
        out_path = _dedupe_output_path(out_path, used_outputs)

        status, message = unlock_pdf(pdf_path, out_path, password)
        stats[status] += 1

        mark = {"ok": "✓", "wrong_password": "✗", "error": "✗"}[status]
        log(f"  {mark} {pdf_path.name}  —  {message}")
        if progress:
            progress(index, len(pdfs), Path(pdf_path.name), status)

    log(
        f"\n處理完畢：成功 {stats['ok']}、"
        f"密碼問題 {stats['wrong_password']}、其他錯誤 {stats['error']}。"
    )
    log(f"乾淨的檔案放在：{output_dir}")
    return stats


def unlock_folder(
    input_dir: str | Path,
    output_dir: str | Path,
    password: str = "",
    log=print,
    progress=None,
):
    """
    批次處理一個資料夾內所有 PDF（含子資料夾）。

    log 是一個會收到字串的函式，預設印到終端機；GUI 會換成寫進畫面。
    回傳統計 dict。
    """
    input_dir = normalize_folder_path(input_dir).resolve()
    output_dir = normalize_folder_path(output_dir).resolve()
    stats = {"total": 0, "ok": 0, "wrong_password": 0, "error": 0}

    if not input_dir.exists():
        log(f"來源資料夾不存在：{input_dir}")
        return stats

    if not input_dir.is_dir():
        log(f"來源路徑不是資料夾：{input_dir}")
        return stats

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # noqa: BLE001 需要讓 GUI 顯示實際原因。
        stats["error"] = 1
        log(f"無法建立輸出資料夾：{output_dir}")
        log(str(exc))
        return stats

    pdfs = _find_pdfs(input_dir, output_dir)
    stats["total"] = len(pdfs)

    log(f"來源資料夾：{input_dir}")
    log(f"輸出資料夾：{output_dir}")

    if not pdfs:
        log("找不到任何 PDF。請確認檔案副檔名是 .pdf，或 PDF 沒有放在輸出資料夾裡。")
        return stats

    log(f"找到 {len(pdfs)} 個 PDF，開始處理…\n")

    for index, pdf_path in enumerate(pdfs, start=1):
        rel = pdf_path.relative_to(input_dir)
        out_path = output_dir / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if out_path.resolve() == pdf_path.resolve():
            out_path = out_path.with_name(out_path.stem + "_unlocked.pdf")

        status, message = unlock_pdf(pdf_path, out_path, password)
        stats[status] += 1

        mark = {"ok": "✓", "wrong_password": "✗", "error": "✗"}[status]
        log(f"  {mark} {rel}  —  {message}")
        if progress:
            progress(index, len(pdfs), rel, status)

    log(
        f"\n處理完畢：成功 {stats['ok']}、"
        f"密碼問題 {stats['wrong_password']}、其他錯誤 {stats['error']}。"
    )
    log(f"乾淨的檔案放在：{output_dir}")
    return stats


def _enable_windows_dpi_awareness() -> None:
    if sys.platform != "win32":
        return

    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:  # noqa: BLE001 Windows 版本或狀態不同時改用舊 API。
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def resource_path(filename: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    direct_path = base / filename
    if direct_path.exists():
        return direct_path
    return base / "assets" / filename


def launch_gui():
    _enable_windows_dpi_awareness()

    import threading
    import tkinter as tk
    import tkinter.font as tkfont
    from tkinter import filedialog, scrolledtext, ttk

    root = tk.Tk()
    dpi_scale = max(root.winfo_fpixels("1i") / 96, 1)
    root.tk.call("tk", "scaling", root.winfo_fpixels("1i") / 72)
    root.title("PDF 解鎖小工具")
    root.geometry(f"{int(760 * dpi_scale)}x{int(600 * dpi_scale)}")
    root.minsize(int(640 * dpi_scale), int(500 * dpi_scale))

    try:
        ttk.Style(root).theme_use("vista")
    except tk.TclError:
        pass

    for font_name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(font_name).configure(family="Microsoft JhengHei UI", size=10)

    pad = {"padx": 12, "pady": 6}
    in_var = tk.StringVar()
    out_var = tk.StringVar()
    pwd_var = tk.StringVar()
    show_pwd = tk.BooleanVar(value=False)

    frm = ttk.Frame(root, padding=12)
    frm.pack(fill="both", expand=True)
    frm.columnconfigure(1, weight=1)

    ttk.Label(frm, text="來源資料夾").grid(row=0, column=0, sticky="w", **pad)
    ttk.Entry(frm, textvariable=in_var).grid(row=0, column=1, sticky="ew", **pad)

    def pick_in():
        selected_dir = filedialog.askdirectory(title="選擇放 PDF 的資料夾")
        if selected_dir:
            in_var.set(selected_dir)
            if not out_var.get():
                out_var.set(str(Path(selected_dir) / "unlocked"))

    ttk.Button(frm, text="瀏覽…", command=pick_in).grid(row=0, column=2, **pad)

    ttk.Label(frm, text="輸出資料夾").grid(row=1, column=0, sticky="w", **pad)
    ttk.Entry(frm, textvariable=out_var).grid(row=1, column=1, sticky="ew", **pad)

    def pick_out():
        selected_dir = filedialog.askdirectory(title="選擇輸出資料夾")
        if selected_dir:
            out_var.set(selected_dir)

    ttk.Button(frm, text="瀏覽…", command=pick_out).grid(row=1, column=2, **pad)

    ttk.Label(frm, text="開啟密碼").grid(row=2, column=0, sticky="w", **pad)
    pwd_entry = ttk.Entry(frm, textvariable=pwd_var, show="•")
    pwd_entry.grid(row=2, column=1, sticky="ew", **pad)

    def toggle_pwd():
        pwd_entry.config(show="" if show_pwd.get() else "•")

    ttk.Checkbutton(frm, text="顯示", variable=show_pwd, command=toggle_pwd).grid(
        row=2,
        column=2,
        **pad,
    )

    ttk.Label(
        frm,
        text="只是被禁止列印／複製的檔案，密碼留空即可；需要密碼才能開啟的檔案才要填。",
        foreground="#666",
        wraplength=590,
        justify="left",
    ).grid(row=3, column=0, columnspan=3, sticky="w", padx=12)

    log_box = scrolledtext.ScrolledText(frm, height=14, state="disabled", wrap="word")
    log_box.grid(row=5, column=0, columnspan=3, sticky="nsew", padx=12, pady=(10, 6))
    frm.rowconfigure(5, weight=1)

    def log(msg):
        def append():
            log_box.config(state="normal")
            log_box.insert("end", msg + "\n")
            log_box.see("end")
            log_box.config(state="disabled")

        root.after(0, append)

    run_btn = ttk.Button(frm, text="開始解鎖")
    run_btn.grid(row=6, column=0, columnspan=3, pady=(0, 4))

    def run():
        in_text = in_var.get()
        if not in_text.strip():
            log("請先選擇一個來源資料夾。")
            return

        in_dir = normalize_folder_path(in_text)
        out_text = out_var.get().strip()
        out_dir = normalize_folder_path(out_text) if out_text else in_dir / "unlocked"

        if not in_dir.exists():
            log(f"來源資料夾不存在：{in_dir}")
            return

        if not in_dir.is_dir():
            log(f"來源路徑不是資料夾：{in_dir}")
            return

        run_btn.config(state="disabled", text="處理中…")
        log_box.config(state="normal")
        log_box.delete("1.0", "end")
        log_box.config(state="disabled")

        def worker():
            try:
                unlock_folder(in_dir, out_dir, pwd_var.get(), log=log)
            finally:
                root.after(
                    0,
                    lambda: run_btn.config(state="normal", text="開始解鎖"),
                )

        threading.Thread(target=worker, daemon=True).start()

    run_btn.config(command=run)
    root.mainloop()


def launch_gui_modern():
    _enable_windows_dpi_awareness()

    import threading
    import tkinter as tk
    import tkinter.font as tkfont
    from tkinter import filedialog, ttk

    root = tk.Tk()
    dpi_scale = max(root.winfo_fpixels("1i") / 96, 1)
    root.tk.call("tk", "scaling", root.winfo_fpixels("1i") / 72)
    root.title("PDF 解鎖工具")
    root.geometry(f"{int(900 * dpi_scale)}x{int(680 * dpi_scale)}")
    root.minsize(int(760 * dpi_scale), int(560 * dpi_scale))

    icon_path = resource_path("pdf_unlocker.ico")
    if icon_path.exists():
        try:
            root.iconbitmap(icon_path)
        except tk.TclError:
            pass

    colors = {
        "bg": "#F4F7FB",
        "panel": "#FFFFFF",
        "panel_alt": "#F8FAFC",
        "text": "#172033",
        "muted": "#667085",
        "accent": "#2563EB",
        "accent_dark": "#1D4ED8",
        "success": "#057A55",
        "warning": "#B54708",
        "error": "#B42318",
    }
    root.configure(bg=colors["bg"])

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    for font_name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(font_name).configure(family="Microsoft JhengHei UI", size=10)

    style.configure(".", font=("Microsoft JhengHei UI", 10))
    style.configure("App.TFrame", background=colors["bg"])
    style.configure("Panel.TFrame", background=colors["panel"], relief="flat")
    style.configure("PanelAlt.TFrame", background=colors["panel_alt"], relief="flat")
    style.configure(
        "Title.TLabel",
        background=colors["bg"],
        foreground=colors["text"],
        font=("Microsoft JhengHei UI", 22, "bold"),
    )
    style.configure(
        "Subtitle.TLabel",
        background=colors["bg"],
        foreground=colors["muted"],
        font=("Microsoft JhengHei UI", 10),
    )
    style.configure(
        "Section.TLabel",
        background=colors["panel"],
        foreground=colors["text"],
        font=("Microsoft JhengHei UI", 12, "bold"),
    )
    style.configure(
        "Label.TLabel",
        background=colors["panel"],
        foreground=colors["text"],
        font=("Microsoft JhengHei UI", 10, "bold"),
    )
    style.configure("Muted.TLabel", background=colors["panel"], foreground=colors["muted"])
    style.configure(
        "MetricValue.TLabel",
        background=colors["panel_alt"],
        foreground=colors["text"],
        font=("Microsoft JhengHei UI", 18, "bold"),
    )
    style.configure(
        "MetricLabel.TLabel",
        background=colors["panel_alt"],
        foreground=colors["muted"],
        font=("Microsoft JhengHei UI", 9),
    )
    style.configure(
        "Status.TLabel",
        background="#EAF1FF",
        foreground=colors["accent_dark"],
        font=("Microsoft JhengHei UI", 10, "bold"),
        padding=(12, 5),
    )
    style.configure(
        "Success.TLabel",
        background="#E8F6EF",
        foreground=colors["success"],
        font=("Microsoft JhengHei UI", 10, "bold"),
        padding=(12, 5),
    )
    style.configure(
        "Warning.TLabel",
        background="#FFF4E5",
        foreground=colors["warning"],
        font=("Microsoft JhengHei UI", 10, "bold"),
        padding=(12, 5),
    )
    style.configure(
        "Error.TLabel",
        background="#FEECEC",
        foreground=colors["error"],
        font=("Microsoft JhengHei UI", 10, "bold"),
        padding=(12, 5),
    )
    style.configure("TEntry", padding=(10, 8))
    style.configure("TCheckbutton", background=colors["panel"], foreground=colors["text"])
    style.configure(
        "Primary.TButton",
        background=colors["accent"],
        foreground="#FFFFFF",
        borderwidth=0,
        focusthickness=0,
        padding=(18, 10),
        font=("Microsoft JhengHei UI", 10, "bold"),
    )
    style.map(
        "Primary.TButton",
        background=[("active", colors["accent_dark"]), ("disabled", "#A9BDE8")],
        foreground=[("disabled", "#FFFFFF")],
    )
    style.configure(
        "Secondary.TButton",
        background="#E9EEF7",
        foreground=colors["text"],
        borderwidth=0,
        focusthickness=0,
        padding=(14, 9),
    )
    style.map("Secondary.TButton", background=[("active", "#DDE6F3"), ("disabled", "#EEF2F7")])
    style.configure(
        "Slim.TButton",
        background="#EEF2F7",
        foreground=colors["text"],
        borderwidth=0,
        focusthickness=0,
        padding=(10, 7),
    )
    style.map("Slim.TButton", background=[("active", "#E2E8F0")])
    style.configure(
        "Blue.Horizontal.TProgressbar",
        troughcolor="#E7ECF5",
        background=colors["accent"],
        bordercolor="#E7ECF5",
        lightcolor=colors["accent"],
        darkcolor=colors["accent"],
    )

    in_var = tk.StringVar()
    out_var = tk.StringVar()
    pwd_var = tk.StringVar()
    show_pwd = tk.BooleanVar(value=False)
    status_var = tk.StringVar(value="準備就緒")
    total_var = tk.StringVar(value="0")
    ok_var = tk.StringVar(value="0")
    password_var = tk.StringVar(value="0")
    error_var = tk.StringVar(value="0")
    progress_var = tk.DoubleVar(value=0)
    progress_text_var = tk.StringVar(value="尚未開始")

    shell = ttk.Frame(root, style="App.TFrame", padding=(24, 22, 24, 18))
    shell.pack(fill="both", expand=True)
    shell.columnconfigure(0, weight=1)
    shell.rowconfigure(2, weight=1)

    header = ttk.Frame(shell, style="App.TFrame")
    header.grid(row=0, column=0, sticky="ew")
    header.columnconfigure(0, weight=1)

    title_area = ttk.Frame(header, style="App.TFrame")
    title_area.grid(row=0, column=0, sticky="w")
    ttk.Label(title_area, text="PDF 解鎖工具", style="Title.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(
        title_area,
        text="批次處理資料夾，原始檔會保留不變。",
        style="Subtitle.TLabel",
    ).grid(row=1, column=0, sticky="w", pady=(2, 0))

    status_label = ttk.Label(header, textvariable=status_var, style="Status.TLabel")
    status_label.grid(row=0, column=1, sticky="e", padx=(16, 0))

    setup_panel = ttk.Frame(shell, style="Panel.TFrame", padding=(18, 16))
    setup_panel.grid(row=1, column=0, sticky="ew", pady=(18, 14))
    setup_panel.columnconfigure(1, weight=1)

    ttk.Label(setup_panel, text="資料夾設定", style="Section.TLabel").grid(
        row=0,
        column=0,
        columnspan=3,
        sticky="w",
        pady=(0, 12),
    )

    ttk.Label(setup_panel, text="來源", style="Label.TLabel").grid(
        row=1,
        column=0,
        sticky="w",
        padx=(0, 14),
        pady=6,
    )
    source_entry = ttk.Entry(setup_panel, textvariable=in_var)
    source_entry.grid(row=1, column=1, sticky="ew", pady=6)

    ttk.Label(setup_panel, text="輸出", style="Label.TLabel").grid(
        row=2,
        column=0,
        sticky="w",
        padx=(0, 14),
        pady=6,
    )
    output_entry = ttk.Entry(setup_panel, textvariable=out_var)
    output_entry.grid(row=2, column=1, sticky="ew", pady=6)

    ttk.Label(setup_panel, text="密碼", style="Label.TLabel").grid(
        row=3,
        column=0,
        sticky="w",
        padx=(0, 14),
        pady=6,
    )
    pwd_entry = ttk.Entry(setup_panel, textvariable=pwd_var, show="•")
    pwd_entry.grid(row=3, column=1, sticky="ew", pady=6)

    def toggle_pwd():
        pwd_entry.config(show="" if show_pwd.get() else "•")

    ttk.Checkbutton(
        setup_panel,
        text="顯示",
        variable=show_pwd,
        command=toggle_pwd,
    ).grid(row=3, column=2, sticky="w", padx=(12, 0), pady=6)

    ttk.Label(
        setup_panel,
        text="權限限制檔可留空；開啟密碼檔需填正確密碼。",
        style="Muted.TLabel",
    ).grid(row=4, column=1, columnspan=2, sticky="w", pady=(4, 0))

    content = ttk.Frame(shell, style="App.TFrame")
    content.grid(row=2, column=0, sticky="nsew")
    content.columnconfigure(0, weight=0)
    content.columnconfigure(1, weight=1)
    content.rowconfigure(0, weight=1)

    summary_panel = ttk.Frame(content, style="Panel.TFrame", padding=(16, 16))
    summary_panel.grid(row=0, column=0, sticky="ns", padx=(0, 14))
    summary_panel.columnconfigure(0, weight=1)

    ttk.Label(summary_panel, text="處理狀態", style="Section.TLabel").grid(
        row=0,
        column=0,
        sticky="w",
        pady=(0, 12),
    )

    metric_frame = ttk.Frame(summary_panel, style="Panel.TFrame")
    metric_frame.grid(row=1, column=0, sticky="ew")
    metric_frame.columnconfigure(0, weight=1)
    metric_frame.columnconfigure(1, weight=1)

    def metric(parent, row, column, label, variable):
        box = ttk.Frame(parent, style="PanelAlt.TFrame", padding=(14, 12))
        box.grid(
            row=row,
            column=column,
            sticky="nsew",
            padx=(0 if column == 0 else 8, 8 if column == 0 else 0),
            pady=(0, 8),
        )
        ttk.Label(box, textvariable=variable, style="MetricValue.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(box, text=label, style="MetricLabel.TLabel").grid(row=1, column=0, sticky="w", pady=(3, 0))

    metric(metric_frame, 0, 0, "PDF", total_var)
    metric(metric_frame, 0, 1, "成功", ok_var)
    metric(metric_frame, 1, 0, "密碼", password_var)
    metric(metric_frame, 1, 1, "錯誤", error_var)

    progress_bar = ttk.Progressbar(
        summary_panel,
        variable=progress_var,
        maximum=100,
        style="Blue.Horizontal.TProgressbar",
    )
    progress_bar.grid(row=2, column=0, sticky="ew", pady=(14, 4))
    ttk.Label(summary_panel, textvariable=progress_text_var, style="Muted.TLabel").grid(
        row=3,
        column=0,
        sticky="w",
    )

    action_frame = ttk.Frame(summary_panel, style="Panel.TFrame")
    action_frame.grid(row=4, column=0, sticky="ew", pady=(20, 0))
    action_frame.columnconfigure(0, weight=1)
    action_frame.columnconfigure(1, weight=1)

    log_panel = ttk.Frame(content, style="Panel.TFrame", padding=(16, 16))
    log_panel.grid(row=0, column=1, sticky="nsew")
    log_panel.columnconfigure(0, weight=1)
    log_panel.rowconfigure(1, weight=1)

    log_header = ttk.Frame(log_panel, style="Panel.TFrame")
    log_header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
    log_header.columnconfigure(0, weight=1)
    ttk.Label(log_header, text="紀錄", style="Section.TLabel").grid(row=0, column=0, sticky="w")

    log_box = tk.Text(
        log_panel,
        height=16,
        state="disabled",
        wrap="word",
        bg="#0F172A",
        fg="#E5E7EB",
        insertbackground="#E5E7EB",
        selectbackground="#334155",
        relief="flat",
        bd=0,
        padx=14,
        pady=12,
        font=("Consolas", 10),
    )
    log_box.grid(row=1, column=0, sticky="nsew")
    log_scroll = ttk.Scrollbar(log_panel, orient="vertical", command=log_box.yview)
    log_scroll.grid(row=1, column=1, sticky="ns")
    log_box.configure(yscrollcommand=log_scroll.set)

    def set_status(text, style_name="Status.TLabel"):
        status_var.set(text)
        status_label.configure(style=style_name)

    def log(msg):
        def append():
            log_box.config(state="normal")
            log_box.insert("end", msg + "\n")
            log_box.see("end")
            log_box.config(state="disabled")

        root.after(0, append)

    def clear_log():
        log_box.config(state="normal")
        log_box.delete("1.0", "end")
        log_box.config(state="disabled")

    def current_paths():
        in_text = in_var.get()
        if not in_text.strip():
            return None, None

        in_dir = normalize_folder_path(in_text)
        out_text = out_var.get().strip()
        out_dir = normalize_folder_path(out_text) if out_text else in_dir / "unlocked"
        return in_dir, out_dir

    def update_counts(total=0, ok=0, password=0, error=0):
        total_var.set(str(total))
        ok_var.set(str(ok))
        password_var.set(str(password))
        error_var.set(str(error))

    def set_progress(done, total, rel=None):
        percent = 0 if total == 0 else (done / total) * 100
        progress_var.set(percent)
        if rel is None:
            progress_text_var.set("尚未開始" if total == 0 else f"已處理 {done} ／ {total}")
        else:
            progress_text_var.set(f"已處理 {done} ／ {total}：{rel}")

    def refresh_preview():
        paths = current_paths()
        if paths == (None, None):
            update_counts()
            set_progress(0, 0)
            set_status("請選擇來源", "Warning.TLabel")
            return

        in_dir, out_dir = paths
        if not in_dir.exists():
            update_counts()
            set_progress(0, 0)
            set_status("來源不存在", "Error.TLabel")
            return

        if not in_dir.is_dir():
            update_counts()
            set_progress(0, 0)
            set_status("來源不是資料夾", "Error.TLabel")
            return

        pdfs = _find_pdfs(in_dir, out_dir)
        update_counts(total=len(pdfs))
        set_progress(0, len(pdfs))
        if pdfs:
            set_status(f"找到 {len(pdfs)} 個 PDF", "Success.TLabel")
        else:
            set_status("沒有 PDF", "Warning.TLabel")

    def pick_in():
        selected_dir = filedialog.askdirectory(title="選擇放 PDF 的資料夾")
        if selected_dir:
            in_var.set(selected_dir)
            if not out_var.get():
                out_var.set(str(Path(selected_dir) / "unlocked"))
            refresh_preview()

    def pick_out():
        selected_dir = filedialog.askdirectory(title="選擇輸出資料夾")
        if selected_dir:
            out_var.set(selected_dir)
            refresh_preview()

    ttk.Button(setup_panel, text="選擇", style="Slim.TButton", command=pick_in).grid(
        row=1,
        column=2,
        sticky="ew",
        padx=(12, 0),
        pady=6,
    )
    ttk.Button(setup_panel, text="選擇", style="Slim.TButton", command=pick_out).grid(
        row=2,
        column=2,
        sticky="ew",
        padx=(12, 0),
        pady=6,
    )

    def open_output_folder():
        paths = current_paths()
        if paths == (None, None):
            log("請先選擇來源資料夾。")
            return

        _, out_dir = paths
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            os.startfile(str(out_dir))
        except Exception as exc:  # noqa: BLE001 需要顯示給使用者。
            log(f"無法開啟輸出資料夾：{out_dir}")
            log(str(exc))

    def set_buttons_running(is_running):
        state = "disabled" if is_running else "normal"
        run_btn.config(state=state, text="處理中…" if is_running else "開始解鎖")
        scan_btn.config(state=state)
        open_btn.config(state=state)
        clear_btn.config(state=state)

    def run():
        paths = current_paths()
        if paths == (None, None):
            set_status("請選擇來源", "Warning.TLabel")
            log("請先選擇一個來源資料夾。")
            return

        in_dir, out_dir = paths
        if not in_dir.exists():
            set_status("來源不存在", "Error.TLabel")
            log(f"來源資料夾不存在：{in_dir}")
            return

        if not in_dir.is_dir():
            set_status("來源不是資料夾", "Error.TLabel")
            log(f"來源路徑不是資料夾：{in_dir}")
            return

        clear_log()
        update_counts()
        set_progress(0, 0)
        set_status("處理中", "Status.TLabel")
        set_buttons_running(True)
        counts = {"total": 0, "ok": 0, "wrong_password": 0, "error": 0}

        def progress(done, total, rel, status):
            counts["total"] = total
            counts[status] += 1

            def apply_progress():
                update_counts(
                    total=counts["total"],
                    ok=counts["ok"],
                    password=counts["wrong_password"],
                    error=counts["error"],
                )
                set_progress(done, total, rel)

            root.after(0, apply_progress)

        def worker():
            try:
                stats = unlock_folder(
                    in_dir,
                    out_dir,
                    pwd_var.get(),
                    log=log,
                    progress=progress,
                )

                def done():
                    update_counts(
                        total=stats["total"],
                        ok=stats["ok"],
                        password=stats["wrong_password"],
                        error=stats["error"],
                    )
                    set_progress(stats["total"], stats["total"])
                    if stats["error"]:
                        set_status("完成，有錯誤", "Error.TLabel")
                    elif stats["wrong_password"]:
                        set_status("完成，有密碼問題", "Warning.TLabel")
                    elif stats["ok"]:
                        set_status("完成", "Success.TLabel")
                    else:
                        set_status("沒有 PDF", "Warning.TLabel")

                root.after(0, done)
            finally:
                root.after(0, lambda: set_buttons_running(False))

        threading.Thread(target=worker, daemon=True).start()

    scan_btn = ttk.Button(action_frame, text="掃描", style="Secondary.TButton", command=refresh_preview)
    scan_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=(0, 8))
    open_btn = ttk.Button(action_frame, text="開啟輸出", style="Secondary.TButton", command=open_output_folder)
    open_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=(0, 8))
    clear_btn = ttk.Button(action_frame, text="清除紀錄", style="Secondary.TButton", command=clear_log)
    clear_btn.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
    run_btn = ttk.Button(action_frame, text="開始解鎖", style="Primary.TButton", command=run)
    run_btn.grid(row=2, column=0, columnspan=2, sticky="ew")

    source_entry.bind("<FocusOut>", lambda _event: refresh_preview())
    output_entry.bind("<FocusOut>", lambda _event: refresh_preview())
    source_entry.bind("<Return>", lambda _event: refresh_preview())
    output_entry.bind("<Return>", lambda _event: refresh_preview())

    log("準備就緒。")
    root.mainloop()


def launch_gui_premium():
    _enable_windows_dpi_awareness()

    import threading
    import tkinter as tk
    from tkinter import filedialog

    try:
        import customtkinter as ctk
    except ImportError:
        launch_gui_modern()
        return

    try:
        from tkinterdnd2 import COPY, DND_FILES, TkinterDnD

        dnd_available = True
    except ImportError:
        COPY = "copy"
        DND_FILES = "DND_Files"
        TkinterDnD = None
        dnd_available = False

    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    app = ctk.CTk()
    if dnd_available:
        try:
            TkinterDnD.require(app)
        except Exception:
            dnd_available = False

    app.title("PDF 解鎖工具")
    app.geometry("1040x740")
    app.minsize(920, 640)

    icon_path = resource_path("pdf_unlocker.ico")
    if icon_path.exists():
        try:
            app.iconbitmap(icon_path)
        except tk.TclError:
            pass

    palette = {
        "bg": "#EEF2F7",
        "surface": "#FFFFFF",
        "surface_soft": "#F8FAFC",
        "nav": "#101828",
        "nav_soft": "#1D2939",
        "text": "#182230",
        "muted": "#667085",
        "line": "#E4E7EC",
        "primary": "#2563EB",
        "primary_hover": "#1D4ED8",
        "cyan": "#0891B2",
        "success": "#059669",
        "warning": "#D97706",
        "danger": "#DC2626",
        "log_bg": "#0B1220",
        "log_text": "#E5E7EB",
    }

    app.configure(fg_color=palette["bg"])
    app.grid_columnconfigure(1, weight=1)
    app.grid_rowconfigure(0, weight=1)

    in_var = ctk.StringVar()
    out_var = ctk.StringVar()
    pwd_var = ctk.StringVar()
    show_pwd_var = ctk.BooleanVar(value=False)

    state = {
        "running": False,
        "total": 0,
        "ok": 0,
        "wrong_password": 0,
        "error": 0,
        "drop_mode": False,
        "drop_sources": [],
        "drop_pdfs": [],
    }

    def font(size, weight="normal"):
        return ctk.CTkFont(family="Microsoft JhengHei UI", size=size, weight=weight)

    sidebar = ctk.CTkFrame(app, width=270, corner_radius=0, fg_color=palette["nav"])
    sidebar.grid(row=0, column=0, sticky="nsew")
    sidebar.grid_propagate(False)
    sidebar.grid_columnconfigure(0, weight=1)
    sidebar.grid_rowconfigure(5, weight=1)

    brand = ctk.CTkFrame(sidebar, fg_color="transparent")
    brand.grid(row=0, column=0, sticky="ew", padx=24, pady=(28, 12))
    ctk.CTkLabel(
        brand,
        text="PDF 解鎖工具",
        font=font(22, "bold"),
        text_color="#FFFFFF",
        anchor="w",
    ).pack(anchor="w")
    ctk.CTkLabel(
        brand,
        text="本機批次處理，原檔保留。",
        font=font(12),
        text_color="#AEB7C7",
        anchor="w",
    ).pack(anchor="w", pady=(6, 0))

    status_badge = ctk.CTkLabel(
        sidebar,
        text="準備就緒",
        height=34,
        corner_radius=8,
        fg_color=palette["nav_soft"],
        text_color="#D6E4FF",
        font=font(13, "bold"),
    )
    status_badge.grid(row=1, column=0, sticky="ew", padx=24, pady=(18, 14))

    hint_panel = ctk.CTkFrame(sidebar, corner_radius=8, fg_color=palette["nav_soft"])
    hint_panel.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 18))
    ctk.CTkLabel(
        hint_panel,
        text="使用方式",
        font=font(13, "bold"),
        text_color="#FFFFFF",
        anchor="w",
    ).pack(anchor="w", padx=16, pady=(14, 6))
    ctk.CTkLabel(
        hint_panel,
        text="可直接拖 PDF 到右側，也可選整個資料夾。需要時輸入密碼，最後按開始解鎖。",
        font=font(12),
        text_color="#C7D0DE",
        wraplength=195,
        justify="left",
    ).pack(anchor="w", padx=16, pady=(0, 14))

    action_panel = ctk.CTkFrame(sidebar, fg_color="transparent")
    action_panel.grid(row=6, column=0, sticky="ew", padx=24, pady=(0, 24))
    action_panel.grid_columnconfigure(0, weight=1)

    main = ctk.CTkFrame(app, corner_radius=0, fg_color=palette["bg"])
    main.grid(row=0, column=1, sticky="nsew")
    main.grid_columnconfigure(0, weight=1)
    main.grid_rowconfigure(4, weight=1)

    header = ctk.CTkFrame(main, fg_color="transparent")
    header.grid(row=0, column=0, sticky="ew", padx=28, pady=(28, 12))
    header.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        header,
        text="把 PDF 密碼與權限限制移除",
        font=font(24, "bold"),
        text_color=palette["text"],
        anchor="w",
    ).grid(row=0, column=0, sticky="w")
    ctk.CTkLabel(
        header,
        text="輸出會放在新資料夾，不會覆蓋原始檔。",
        font=font(13),
        text_color=palette["muted"],
        anchor="w",
    ).grid(row=1, column=0, sticky="w", pady=(4, 0))

    drop_zone = ctk.CTkFrame(
        main,
        corner_radius=10,
        fg_color="#F8FAFF",
        border_width=2,
        border_color="#C7D7FE",
    )
    drop_zone.grid(row=1, column=0, sticky="ew", padx=28, pady=(8, 16))
    drop_zone.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(
        drop_zone,
        text="＋",
        width=54,
        height=54,
        corner_radius=10,
        fg_color="#DBEAFE",
        text_color=palette["primary"],
        font=font(28, "bold"),
    ).grid(row=0, column=0, rowspan=2, sticky="w", padx=(18, 14), pady=18)
    drop_title = ctk.CTkLabel(
        drop_zone,
        text="把 PDF 拖到這裡",
        font=font(17, "bold"),
        text_color=palette["text"],
        anchor="w",
    )
    drop_title.grid(row=0, column=1, sticky="ew", pady=(18, 2))
    drop_subtitle = ctk.CTkLabel(
        drop_zone,
        text="可拖入單一 PDF、多個 PDF，或含 PDF 的資料夾。",
        font=font(12),
        text_color=palette["muted"],
        anchor="w",
    )
    drop_subtitle.grid(row=1, column=1, sticky="ew", pady=(0, 18))

    setup = ctk.CTkFrame(main, corner_radius=8, fg_color=palette["surface"])
    setup.grid(row=2, column=0, sticky="ew", padx=28, pady=(0, 16))
    setup.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(
        setup,
        text="資料夾與密碼",
        font=font(16, "bold"),
        text_color=palette["text"],
        anchor="w",
    ).grid(row=0, column=0, columnspan=3, sticky="w", padx=20, pady=(18, 12))

    def make_entry(parent, variable, show=None):
        return ctk.CTkEntry(
            parent,
            textvariable=variable,
            height=42,
            corner_radius=8,
            border_width=1,
            border_color=palette["line"],
            fg_color="#FFFFFF",
            text_color=palette["text"],
            placeholder_text_color="#98A2B3",
            font=font(13),
            show=show,
        )

    ctk.CTkLabel(setup, text="來源", font=font(13, "bold"), text_color=palette["text"]).grid(
        row=1,
        column=0,
        sticky="w",
        padx=(20, 14),
        pady=7,
    )
    source_entry = make_entry(setup, in_var)
    source_entry.grid(row=1, column=1, sticky="ew", pady=7)

    ctk.CTkLabel(setup, text="輸出", font=font(13, "bold"), text_color=palette["text"]).grid(
        row=2,
        column=0,
        sticky="w",
        padx=(20, 14),
        pady=7,
    )
    output_entry = make_entry(setup, out_var)
    output_entry.grid(row=2, column=1, sticky="ew", pady=7)

    ctk.CTkLabel(setup, text="密碼", font=font(13, "bold"), text_color=palette["text"]).grid(
        row=3,
        column=0,
        sticky="w",
        padx=(20, 14),
        pady=7,
    )
    pwd_entry = make_entry(setup, pwd_var, show="•")
    pwd_entry.grid(row=3, column=1, sticky="ew", pady=7)

    def clear_drop_mode():
        state["drop_mode"] = False
        state["drop_sources"] = []
        state["drop_pdfs"] = []
        drop_title.configure(text="把 PDF 拖到這裡")
        drop_subtitle.configure(text="可拖入單一 PDF、多個 PDF，或含 PDF 的資料夾。")
        drop_zone.configure(fg_color="#F8FAFF", border_color="#C7D7FE")

    def current_output_dir(default_base: Path | None = None):
        out_text = out_var.get().strip()
        if out_text:
            return normalize_folder_path(out_text)
        if default_base:
            return default_base / "unlocked"
        if in_var.get().strip():
            return normalize_folder_path(in_var.get()) / "unlocked"
        return None

    def current_paths():
        if not in_var.get().strip():
            return None, None
        input_dir = normalize_folder_path(in_var.get())
        output_dir = current_output_dir(input_dir)
        return input_dir, output_dir

    def set_status(text, color=None):
        status_badge.configure(text=text, fg_color=color or palette["nav_soft"])

    def append_log(message):
        def apply():
            log_box.configure(state="normal")
            log_box.insert("end", message + "\n")
            log_box.see("end")
            log_box.configure(state="disabled")

        app.after(0, apply)

    def clear_log():
        log_box.configure(state="normal")
        log_box.delete("1.0", "end")
        log_box.configure(state="disabled")

    def set_counts(total=0, ok=0, wrong_password=0, error=0):
        state["total"] = total
        state["ok"] = ok
        state["wrong_password"] = wrong_password
        state["error"] = error
        total_value.configure(text=str(total))
        ok_value.configure(text=str(ok))
        password_value.configure(text=str(wrong_password))
        error_value.configure(text=str(error))

    def set_progress(done=0, total=0, rel=None):
        ratio = 0 if total == 0 else min(done / total, 1)
        progress_bar.set(ratio)
        if rel:
            progress_label.configure(text=f"已處理 {done} ／ {total}：{rel}")
        elif total:
            progress_label.configure(text=f"已處理 {done} ／ {total}")
        else:
            progress_label.configure(text="尚未開始")

    def refresh_preview():
        if state["drop_mode"]:
            output_dir = current_output_dir(_common_parent(state["drop_pdfs"]))
            pdfs = collect_pdfs_from_paths(state["drop_sources"], output_dir)
            state["drop_pdfs"] = pdfs
            set_counts(total=len(pdfs))
            set_progress(0, len(pdfs))
            if pdfs:
                set_status(f"已拖入 {len(pdfs)} 個 PDF", palette["success"])
                drop_title.configure(text=f"已拖入 {len(pdfs)} 個 PDF")
                drop_subtitle.configure(text="可繼續拖入檔案，或按「開始解鎖」。")
                drop_zone.configure(fg_color="#ECFDF3", border_color="#86EFAC")
            else:
                set_status("沒有 PDF", palette["warning"])
                drop_title.configure(text="沒有可處理的 PDF")
                drop_subtitle.configure(text="請拖入 PDF 檔，或拖入含 PDF 的資料夾。")
                drop_zone.configure(fg_color="#FFF7ED", border_color="#FDBA74")
            return

        paths = current_paths()
        if paths == (None, None):
            set_counts()
            set_progress()
            set_status("請選擇來源", palette["warning"])
            return

        input_dir, output_dir = paths
        if not input_dir.exists():
            set_counts()
            set_progress()
            set_status("來源不存在", palette["danger"])
            return

        if not input_dir.is_dir():
            set_counts()
            set_progress()
            set_status("來源不是資料夾", palette["danger"])
            return

        pdfs = _find_pdfs(input_dir, output_dir)
        set_counts(total=len(pdfs))
        set_progress(0, len(pdfs))
        if pdfs:
            set_status(f"找到 {len(pdfs)} 個 PDF", palette["success"])
        else:
            set_status("沒有 PDF", palette["warning"])

    def choose_source():
        selected_dir = filedialog.askdirectory(title="選擇放 PDF 的資料夾")
        if selected_dir:
            clear_drop_mode()
            in_var.set(selected_dir)
            if not out_var.get().strip():
                out_var.set(str(Path(selected_dir) / "unlocked"))
            refresh_preview()

    def choose_output():
        selected_dir = filedialog.askdirectory(title="選擇輸出資料夾")
        if selected_dir:
            out_var.set(selected_dir)
            refresh_preview()

    def parse_dropped_paths(data):
        try:
            return [Path(item) for item in app.tk.splitlist(data)]
        except tk.TclError:
            return [Path(data)]

    def handle_drop(event):
        if state["running"]:
            return COPY

        dropped_paths = parse_dropped_paths(event.data)
        pdfs = collect_pdfs_from_paths(dropped_paths, current_output_dir(_common_parent(state["drop_pdfs"])))
        if not pdfs:
            state["drop_mode"] = True
            state["drop_sources"] = dropped_paths
            state["drop_pdfs"] = []
            in_var.set("拖放模式：沒有可處理的 PDF")
            refresh_preview()
            append_log("拖入的項目裡沒有 PDF。")
            return COPY

        merged_sources = [*state["drop_sources"], *dropped_paths] if state["drop_mode"] else dropped_paths
        output_default_base = _common_parent(pdfs)
        if output_default_base and not out_var.get().strip():
            out_var.set(str(output_default_base / "unlocked"))

        state["drop_mode"] = True
        state["drop_sources"] = merged_sources
        state["drop_pdfs"] = collect_pdfs_from_paths(merged_sources, current_output_dir(output_default_base))
        in_var.set(f"拖放模式：{len(state['drop_pdfs'])} 個 PDF")
        refresh_preview()
        append_log(f"已拖入 {len(state['drop_pdfs'])} 個 PDF。")
        return COPY

    def handle_drag_enter(_event):
        if not state["running"]:
            drop_zone.configure(fg_color="#EFF6FF", border_color=palette["primary"])
        return COPY

    def handle_drag_leave(_event):
        refresh_preview()
        return COPY

    def toggle_password():
        pwd_entry.configure(show="" if show_pwd_var.get() else "•")

    ctk.CTkButton(
        setup,
        text="選擇來源",
        width=104,
        height=42,
        corner_radius=8,
        fg_color=palette["surface_soft"],
        hover_color="#E8EEF7",
        text_color=palette["text"],
        font=font(13, "bold"),
        command=choose_source,
    ).grid(row=1, column=2, padx=(12, 20), pady=7)

    ctk.CTkButton(
        setup,
        text="選擇輸出",
        width=104,
        height=42,
        corner_radius=8,
        fg_color=palette["surface_soft"],
        hover_color="#E8EEF7",
        text_color=palette["text"],
        font=font(13, "bold"),
        command=choose_output,
    ).grid(row=2, column=2, padx=(12, 20), pady=7)

    ctk.CTkSwitch(
        setup,
        text="顯示",
        variable=show_pwd_var,
        command=toggle_password,
        progress_color=palette["primary"],
        button_color="#FFFFFF",
        text_color=palette["text"],
        font=font(13),
    ).grid(row=3, column=2, padx=(12, 20), pady=7)

    ctk.CTkLabel(
        setup,
        text="權限限制檔可留空；開啟密碼檔才需要填正確密碼。",
        font=font(12),
        text_color=palette["muted"],
    ).grid(row=4, column=1, columnspan=2, sticky="w", pady=(0, 18))

    summary = ctk.CTkFrame(main, fg_color="transparent")
    summary.grid(row=3, column=0, sticky="ew", padx=28, pady=(0, 16))
    for column in range(4):
        summary.grid_columnconfigure(column, weight=1)

    def stat_card(column, title, value, color):
        card = ctk.CTkFrame(summary, corner_radius=8, fg_color=palette["surface"])
        card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 10, 0))
        ctk.CTkLabel(
            card,
            text=title,
            font=font(12, "bold"),
            text_color=palette["muted"],
            anchor="w",
        ).pack(anchor="w", padx=16, pady=(14, 2))
        value_label = ctk.CTkLabel(card, text="0", font=font(26, "bold"), text_color=color, anchor="w")
        value_label.pack(anchor="w", padx=16, pady=(0, 14))
        return value_label

    total_value = stat_card(0, "PDF", total_var if False else "0", palette["text"])
    ok_value = stat_card(1, "成功", "0", palette["success"])
    password_value = stat_card(2, "密碼", "0", palette["warning"])
    error_value = stat_card(3, "錯誤", "0", palette["danger"])

    lower = ctk.CTkFrame(main, fg_color="transparent")
    lower.grid(row=4, column=0, sticky="nsew", padx=28, pady=(0, 24))
    lower.grid_columnconfigure(0, weight=1)
    lower.grid_rowconfigure(1, weight=1)

    progress_card = ctk.CTkFrame(lower, corner_radius=8, fg_color=palette["surface"])
    progress_card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
    progress_card.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(
        progress_card,
        text="處理進度",
        font=font(15, "bold"),
        text_color=palette["text"],
        anchor="w",
    ).grid(row=0, column=0, sticky="w", padx=18, pady=(16, 8))
    progress_bar = ctk.CTkProgressBar(
        progress_card,
        height=12,
        corner_radius=6,
        fg_color="#E5EAF2",
        progress_color=palette["primary"],
    )
    progress_bar.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))
    progress_bar.set(0)
    progress_label = ctk.CTkLabel(
        progress_card,
        text="尚未開始",
        font=font(12),
        text_color=palette["muted"],
        anchor="w",
    )
    progress_label.grid(row=2, column=0, sticky="w", padx=18, pady=(0, 16))

    log_card = ctk.CTkFrame(lower, corner_radius=8, fg_color=palette["surface"])
    log_card.grid(row=1, column=0, sticky="nsew")
    log_card.grid_columnconfigure(0, weight=1)
    log_card.grid_rowconfigure(1, weight=1)
    ctk.CTkLabel(
        log_card,
        text="處理紀錄",
        font=font(15, "bold"),
        text_color=palette["text"],
        anchor="w",
    ).grid(row=0, column=0, sticky="w", padx=18, pady=(16, 10))
    log_box = ctk.CTkTextbox(
        log_card,
        corner_radius=8,
        border_width=0,
        fg_color=palette["log_bg"],
        text_color=palette["log_text"],
        font=("Consolas", 12),
        wrap="word",
    )
    log_box.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
    log_box.configure(state="disabled")

    def open_output_folder():
        if state["drop_mode"]:
            output_dir = current_output_dir(_common_parent(state["drop_pdfs"]))
        else:
            paths = current_paths()
            output_dir = paths[1] if paths != (None, None) else None

        if output_dir is None:
            append_log("請先選擇來源資料夾。")
            return

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            os.startfile(str(output_dir))
        except Exception as exc:  # noqa: BLE001 需要顯示給使用者。
            append_log(f"無法開啟輸出資料夾：{output_dir}")
            append_log(str(exc))

    def set_running(is_running):
        state["running"] = is_running
        widget_state = "disabled" if is_running else "normal"
        start_button.configure(state=widget_state, text="處理中…" if is_running else "開始解鎖")
        scan_button.configure(state=widget_state)
        open_button.configure(state=widget_state)
        clear_button.configure(state=widget_state)

    def start_unlock():
        if state["drop_mode"]:
            pdfs = collect_pdfs_from_paths(
                state["drop_sources"],
                current_output_dir(_common_parent(state["drop_pdfs"])),
            )
            state["drop_pdfs"] = pdfs
            output_dir = current_output_dir(_common_parent(pdfs))
            if not pdfs:
                set_status("沒有 PDF", palette["warning"])
                append_log("沒有可處理的 PDF。請拖入 PDF 檔，或拖入含 PDF 的資料夾。")
                return
            if output_dir is None:
                set_status("請選擇輸出", palette["warning"])
                append_log("請先選擇輸出資料夾。")
                return

            clear_log()
            set_counts()
            set_progress()
            set_status("處理中", palette["primary"])
            set_running(True)
            counts = {"total": 0, "ok": 0, "wrong_password": 0, "error": 0}

            def progress(done, total, rel, status):
                counts["total"] = total
                counts[status] += 1

                def apply():
                    set_counts(
                        total=counts["total"],
                        ok=counts["ok"],
                        wrong_password=counts["wrong_password"],
                        error=counts["error"],
                    )
                    set_progress(done, total, rel)

                app.after(0, apply)

            def worker():
                try:
                    stats = unlock_pdf_files(
                        pdfs,
                        output_dir,
                        pwd_var.get(),
                        log=append_log,
                        progress=progress,
                    )

                    def done():
                        set_counts(
                            total=stats["total"],
                            ok=stats["ok"],
                            wrong_password=stats["wrong_password"],
                            error=stats["error"],
                        )
                        set_progress(stats["total"], stats["total"])
                        if stats["error"]:
                            set_status("完成，有錯誤", palette["danger"])
                        elif stats["wrong_password"]:
                            set_status("完成，有密碼問題", palette["warning"])
                        elif stats["ok"]:
                            set_status("完成", palette["success"])
                        else:
                            set_status("沒有 PDF", palette["warning"])

                    app.after(0, done)
                finally:
                    app.after(0, lambda: set_running(False))

            threading.Thread(target=worker, daemon=True).start()
            return

        paths = current_paths()
        if paths == (None, None):
            set_status("請選擇來源", palette["warning"])
            append_log("請先選擇一個來源資料夾。")
            return

        input_dir, output_dir = paths
        if not input_dir.exists():
            set_status("來源不存在", palette["danger"])
            append_log(f"來源資料夾不存在：{input_dir}")
            return

        if not input_dir.is_dir():
            set_status("來源不是資料夾", palette["danger"])
            append_log(f"來源路徑不是資料夾：{input_dir}")
            return

        clear_log()
        set_counts()
        set_progress()
        set_status("處理中", palette["primary"])
        set_running(True)
        counts = {"total": 0, "ok": 0, "wrong_password": 0, "error": 0}

        def progress(done, total, rel, status):
            counts["total"] = total
            counts[status] += 1

            def apply():
                set_counts(
                    total=counts["total"],
                    ok=counts["ok"],
                    wrong_password=counts["wrong_password"],
                    error=counts["error"],
                )
                set_progress(done, total, rel)

            app.after(0, apply)

        def worker():
            try:
                stats = unlock_folder(
                    input_dir,
                    output_dir,
                    pwd_var.get(),
                    log=append_log,
                    progress=progress,
                )

                def done():
                    set_counts(
                        total=stats["total"],
                        ok=stats["ok"],
                        wrong_password=stats["wrong_password"],
                        error=stats["error"],
                    )
                    set_progress(stats["total"], stats["total"])
                    if stats["error"]:
                        set_status("完成，有錯誤", palette["danger"])
                    elif stats["wrong_password"]:
                        set_status("完成，有密碼問題", palette["warning"])
                    elif stats["ok"]:
                        set_status("完成", palette["success"])
                    else:
                        set_status("沒有 PDF", palette["warning"])

                app.after(0, done)
            finally:
                app.after(0, lambda: set_running(False))

        threading.Thread(target=worker, daemon=True).start()

    scan_button = ctk.CTkButton(
        action_panel,
        text="掃描 PDF",
        height=42,
        corner_radius=8,
        fg_color=palette["nav_soft"],
        hover_color="#26364C",
        font=font(13, "bold"),
        command=refresh_preview,
    )
    scan_button.grid(row=0, column=0, sticky="ew", pady=(0, 10))
    open_button = ctk.CTkButton(
        action_panel,
        text="開啟輸出資料夾",
        height=42,
        corner_radius=8,
        fg_color=palette["nav_soft"],
        hover_color="#26364C",
        font=font(13, "bold"),
        command=open_output_folder,
    )
    open_button.grid(row=1, column=0, sticky="ew", pady=(0, 10))
    clear_button = ctk.CTkButton(
        action_panel,
        text="清除紀錄",
        height=42,
        corner_radius=8,
        fg_color=palette["nav_soft"],
        hover_color="#26364C",
        font=font(13, "bold"),
        command=clear_log,
    )
    clear_button.grid(row=2, column=0, sticky="ew", pady=(0, 14))
    start_button = ctk.CTkButton(
        action_panel,
        text="開始解鎖",
        height=48,
        corner_radius=8,
        fg_color=palette["primary"],
        hover_color=palette["primary_hover"],
        font=font(15, "bold"),
        command=start_unlock,
    )
    start_button.grid(row=3, column=0, sticky="ew")

    source_entry.bind("<FocusOut>", lambda _event: refresh_preview())
    output_entry.bind("<FocusOut>", lambda _event: refresh_preview())
    source_entry.bind("<Return>", lambda _event: refresh_preview())
    output_entry.bind("<Return>", lambda _event: refresh_preview())

    if dnd_available:
        for widget in (drop_zone, drop_title, drop_subtitle):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<DropEnter>>", handle_drag_enter)
            widget.dnd_bind("<<DropLeave>>", handle_drag_leave)
            widget.dnd_bind("<<Drop>>", handle_drop)
    else:
        drop_subtitle.configure(text="目前環境沒有拖放元件；仍可用「選擇來源」。")

    append_log("準備就緒。")
    app.mainloop()


def main():
    if len(sys.argv) > 1 and not getattr(sys, "frozen", False):
        in_dir = normalize_folder_path(sys.argv[1])
        out_dir = normalize_folder_path(sys.argv[2]) if len(sys.argv) > 2 else in_dir / "unlocked"
        pwd = input("若 PDF 有開啟密碼請輸入，沒有就直接按 Enter： ").strip()
        unlock_folder(in_dir, out_dir, pwd)
    else:
        launch_gui_premium()


if __name__ == "__main__":
    main()
