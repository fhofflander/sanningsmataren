from __future__ import annotations

import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .errors import AnalysisCancelled
from .factcheck_video import (
    VideoRenderProgress,
    create_fact_checked_video,
    suggested_factchecked_output,
)
from .media import is_url


class FactCheckVideoDialog:
    def __init__(
        self,
        parent: tk.Tk,
        *,
        initial_source: str = "",
        output_dir: Path | None = None,
    ) -> None:
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title("Skapa faktagranskad film")
        self.window.geometry("860x610")
        self.window.minsize(760, 540)
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.last_output: Path | None = None
        target_dir = output_dir or Path.home() / "Documents"

        self.source_var = tk.StringVar(value=initial_source)
        self.json_var = tk.StringVar()
        self.output_var = tk.StringVar(
            value=str(suggested_factchecked_output(initial_source, target_dir))
        )
        self.status_var = tk.StringVar(value="Redo")
        self.progress_text_var = tk.StringVar(value="Välj video och faktagransknings-JSON.")

        self._build_ui()
        self.window.protocol("WM_DELETE_WINDOW", self._close)
        self.window.after(100, self._poll_events)
        self.window.transient(parent)
        self.window.lift()

    def _build_ui(self) -> None:
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        main = ttk.Frame(self.window, padding=20)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(4, weight=1)

        ttk.Label(main, text="Skapa faktagranskad film", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            main,
            text=(
                "Originalvideon placeras till vänster och faktagranskningen i en "
                "läsbar panel till höger. Renderingen sker helt lokalt."
            ),
            style="Subtitle.TLabel",
            wraplength=790,
        ).grid(row=1, column=0, sticky="w", pady=(3, 14))

        files = ttk.LabelFrame(main, text="Filer", style="Card.TLabelframe")
        files.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        files.columnconfigure(1, weight=1)
        ttk.Label(files, text="Video eller URL").grid(row=0, column=0, sticky="w")
        ttk.Entry(files, textvariable=self.source_var).grid(
            row=0, column=1, sticky="ew", padx=10
        )
        ttk.Button(files, text="Välj fil …", command=self._browse_source).grid(
            row=0, column=2
        )
        ttk.Label(files, text="Faktagranskning JSON").grid(
            row=1, column=0, sticky="w", pady=(9, 0)
        )
        ttk.Entry(files, textvariable=self.json_var).grid(
            row=1, column=1, sticky="ew", padx=10, pady=(9, 0)
        )
        ttk.Button(files, text="Välj JSON …", command=self._browse_json).grid(
            row=1, column=2, pady=(9, 0)
        )
        ttk.Label(files, text="Spara MP4 som").grid(
            row=2, column=0, sticky="w", pady=(9, 0)
        )
        ttk.Entry(files, textvariable=self.output_var).grid(
            row=2, column=1, sticky="ew", padx=10, pady=(9, 0)
        )
        ttk.Button(files, text="Välj plats …", command=self._browse_output).grid(
            row=2, column=2, pady=(9, 0)
        )

        controls = ttk.Frame(main)
        controls.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        controls.columnconfigure(0, weight=1)
        self.open_button = ttk.Button(
            controls, text="Öppna film", command=self._open_result, state="disabled"
        )
        self.open_button.grid(row=0, column=1)
        self.folder_button = ttk.Button(
            controls, text="Visa i mapp", command=self._open_folder, state="disabled"
        )
        self.folder_button.grid(row=0, column=2, padx=(8, 0))
        self.cancel_button = ttk.Button(
            controls, text="Avbryt", command=self._cancel, state="disabled"
        )
        self.cancel_button.grid(row=0, column=3, padx=(18, 0))
        self.start_button = ttk.Button(
            controls,
            text="Skapa film",
            style="Primary.TButton",
            command=self._start,
        )
        self.start_button.grid(row=0, column=4, padx=(8, 0))

        status = ttk.LabelFrame(main, text="Renderingsstatus", style="Card.TLabelframe")
        status.grid(row=4, column=0, sticky="nsew")
        status.columnconfigure(0, weight=1)
        status.rowconfigure(3, weight=1)
        ttk.Label(status, textvariable=self.status_var, style="Status.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.progress = ttk.Progressbar(status, mode="determinate", maximum=100)
        self.progress.grid(row=1, column=0, sticky="ew", pady=(8, 3))
        ttk.Label(
            status, textvariable=self.progress_text_var, style="Hint.TLabel"
        ).grid(row=2, column=0, sticky="w", pady=(0, 8))
        self.log = tk.Text(
            status,
            height=8,
            wrap="word",
            state="disabled",
            bg="#0f172a",
            fg="#e2e8f0",
            insertbackground="#e2e8f0",
            relief="flat",
            padx=10,
            pady=8,
            font=("Consolas", 9),
        )
        self.log.grid(row=3, column=0, sticky="nsew")
        self._log("Väntar på video och faktagranskningsfil.")

    def _browse_source(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self.window,
            title="Välj originalvideo",
            filetypes=(
                ("Videofiler", "*.mp4 *.mkv *.mov *.avi *.webm"),
                ("Alla filer", "*.*"),
            ),
        )
        if selected:
            self.source_var.set(selected)
            current_parent = Path(self.output_var.get()).expanduser().parent
            self.output_var.set(
                str(suggested_factchecked_output(selected, current_parent))
            )

    def _browse_json(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self.window,
            title="Välj faktagransknings-JSON",
            filetypes=(("JSON", "*.json"), ("Alla filer", "*.*")),
        )
        if selected:
            self.json_var.set(selected)

    def _browse_output(self) -> None:
        selected = filedialog.asksaveasfilename(
            parent=self.window,
            title="Spara faktagranskad film",
            defaultextension=".mp4",
            initialfile=Path(self.output_var.get()).name,
            initialdir=str(Path(self.output_var.get()).expanduser().parent),
            filetypes=(("MP4-video", "*.mp4"),),
        )
        if selected:
            self.output_var.set(selected)

    def _start(self) -> None:
        source = self.source_var.get().strip()
        json_text = self.json_var.get().strip()
        output_text = self.output_var.get().strip()
        errors: list[str] = []
        if not source:
            errors.append("Välj en originalvideo eller ange en URL.")
        elif not is_url(source) and not Path(source).expanduser().is_file():
            errors.append("Originalvideon finns inte.")
        if not json_text or not Path(json_text).expanduser().is_file():
            errors.append("Välj en befintlig faktagransknings-JSON.")
        if not output_text:
            errors.append("Välj var MP4-filen ska sparas.")
        elif Path(output_text).suffix.casefold() != ".mp4":
            errors.append("Resultatfilen måste ha filändelsen .mp4.")
        if source and output_text and not is_url(source):
            if Path(source).expanduser().resolve() == Path(output_text).expanduser().resolve():
                errors.append("Resultatfilen får inte skriva över originalvideon.")
        if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
            errors.append("FFmpeg och FFprobe måste finnas i PATH.")
        if errors:
            messagebox.showerror(
                "Kan inte skapa filmen", "\n\n".join(errors), parent=self.window
            )
            return

        self.cancel_event.clear()
        self.last_output = None
        self._set_busy(True)
        self._log("Startar en ny videorendering.")
        self.worker = threading.Thread(
            target=self._run_job,
            args=(source, Path(json_text), Path(output_text)),
            daemon=True,
            name="factcheck-video-render",
        )
        self.worker.start()

    def _run_job(self, source: str, json_path: Path, output: Path) -> None:
        try:
            with tempfile.TemporaryDirectory(prefix="factcheck-video-") as temporary:
                result = create_fact_checked_video(
                    source,
                    json_path.expanduser().resolve(),
                    output.expanduser().resolve(),
                    Path(temporary),
                    progress=lambda update: self.events.put(("progress", update)),
                    should_cancel=self.cancel_event.is_set,
                )
            self.events.put(("done", result))
        except AnalysisCancelled as error:
            self.events.put(("cancelled", str(error)))
        except Exception as error:
            self.events.put(("error", str(error)))

    def _poll_events(self) -> None:
        if not self.window.winfo_exists():
            return
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "progress" and isinstance(payload, VideoRenderProgress):
                    self.status_var.set(payload.message)
                    self.progress_text_var.set(payload.message)
                    if payload.ratio is None:
                        self.progress.configure(mode="indeterminate")
                        self.progress.start(12)
                    else:
                        self.progress.stop()
                        self.progress.configure(
                            mode="determinate", value=payload.ratio * 100
                        )
                elif kind == "done":
                    self.last_output = Path(str(payload))
                    self._set_busy(False)
                    self.progress.configure(value=100)
                    self.status_var.set("Filmen är klar")
                    self.progress_text_var.set(str(self.last_output))
                    self._log(f"Klar: {self.last_output}")
                    self.open_button.configure(state="normal")
                    self.folder_button.configure(state="normal")
                    messagebox.showinfo(
                        "Filmen är klar",
                        f"Den faktagranskade filmen har sparats här:\n{self.last_output}",
                        parent=self.window,
                    )
                elif kind == "cancelled":
                    self._set_busy(False)
                    self.status_var.set("Avbruten")
                    self.progress_text_var.set(str(payload))
                    self._log(str(payload))
                elif kind == "error":
                    self._set_busy(False)
                    self.status_var.set("Fel")
                    self.progress_text_var.set("Renderingen misslyckades.")
                    self._log(f"Fel: {payload}")
                    messagebox.showerror(
                        "Videorenderingen misslyckades", str(payload), parent=self.window
                    )
        except queue.Empty:
            pass
        self.window.after(100, self._poll_events)

    def _set_busy(self, busy: bool) -> None:
        self.start_button.configure(state="disabled" if busy else "normal")
        self.cancel_button.configure(state="normal" if busy else "disabled")
        if busy:
            self.progress.configure(mode="indeterminate", value=0)
            self.progress.start(12)
            self.status_var.set("Förbereder …")
        else:
            self.progress.stop()

    def _cancel(self) -> None:
        if self.worker is None or not self.worker.is_alive():
            return
        self.cancel_event.set()
        self.cancel_button.configure(state="disabled")
        self.status_var.set("Avbryter …")
        self._log("Avbrott begärt.")

    def _log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{timestamp}] {message}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _open_result(self) -> None:
        if self.last_output and self.last_output.is_file():
            _open_path(self.last_output)

    def _open_folder(self) -> None:
        if not self.last_output:
            return
        if sys.platform == "win32":
            subprocess.Popen(["explorer.exe", "/select,", str(self.last_output)])
        else:
            _open_path(self.last_output.parent)

    def _close(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            close = messagebox.askyesno(
                "Rendering pågår",
                "En rendering pågår. Vill du avbryta och stänga fönstret?",
                parent=self.window,
            )
            if not close:
                return
            self.cancel_event.set()
        self.window.destroy()


def _open_path(path: Path) -> None:
    if sys.platform == "win32":
        import os

        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
