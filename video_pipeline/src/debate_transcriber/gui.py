from __future__ import annotations

import contextlib
import importlib.util
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Iterator

from .cuda_runtime import missing_cuda_libraries
from .errors import AnalysisCancelled
from .factcheck_gui import FactCheckVideoDialog
from .gui_state import (
    GuiJob,
    GuiSettings,
    load_settings,
    parse_optional_positive_int,
    save_settings,
    suggested_output,
    validate_job,
)
from .paths import default_cache_dir
from .pipeline import analyze_debate
from .progress import (
    TranscriptionProgress,
    estimate_remaining_seconds,
    format_media_time,
    format_remaining_time,
)
from .transcription import LocalTranscriber, OpenAIDiarizedTranscriber


class DebateTranscriberApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Debatt-transkriberaren – Sanningsmätaren")
        self.root.geometry("980x760")
        self.root.minsize(820, 660)
        self.cache_dir = default_cache_dir().resolve()
        self.settings_path = self.cache_dir / "gui-settings.json"
        self.settings = load_settings(self.settings_path)
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.last_output: Path | None = None
        self.advanced_visible = False
        self.advanced_window: tk.Toplevel | None = None
        self.factcheck_dialog: FactCheckVideoDialog | None = None
        self.transcription_started_at: float | None = None

        self._create_variables()
        self._configure_style()
        self._build_ui()
        self._update_mode_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._poll_events)

    def _create_variables(self) -> None:
        output_dir = (
            Path(self.settings.last_output_dir)
            if self.settings.last_output_dir
            else Path.home() / "Documents"
        )
        self.source_var = tk.StringVar()
        self.output_var = tk.StringVar(value=str(suggested_output("", output_dir)))
        self.transcriber_var = tk.StringVar(value=self.settings.transcriber)
        self.language_var = tk.StringVar(value=self.settings.language)
        self.openai_key_var = tk.StringVar(value=os.environ.get("OPENAI_API_KEY", ""))
        self.show_secrets_var = tk.BooleanVar(value=False)
        self.identity_var = tk.BooleanVar(value=self.settings.identify_speakers)
        self.ocr_var = tk.BooleanVar(value=self.settings.use_ocr)
        self.require_identity_var = tk.BooleanVar(value=self.settings.require_identity)
        self.include_former_var = tk.BooleanVar(value=self.settings.include_former)
        self.whisper_model_var = tk.StringVar(value=self.settings.whisper_model)
        self.device_var = tk.StringVar(value=self.settings.device)
        self.compute_type_var = tk.StringVar(value=self.settings.compute_type)
        self.min_speakers_var = tk.StringVar(value=self.settings.min_speakers)
        self.max_speakers_var = tk.StringVar(value=self.settings.max_speakers)
        self.extra_roster_var = tk.StringVar(value=self.settings.extra_roster)
        self.mode_note_var = tk.StringVar()
        self.credentials_note_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Redo")
        self.progress_detail_var = tk.StringVar()

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        available = style.theme_names()
        if "vista" in available:
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 21, "bold"))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground="#475569")
        style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Hint.TLabel", font=("Segoe UI", 9), foreground="#64748b")
        style.configure("Status.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure(
            "Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(18, 8)
        )
        style.configure("TButton", padding=(10, 6))
        style.configure("TEntry", padding=5)
        style.configure("Card.TLabelframe", padding=12)
        style.configure("Card.TLabelframe.Label", font=("Segoe UI", 10, "bold"))

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main = ttk.Frame(self.root, padding=(22, 18, 22, 16))
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(5, weight=1)

        header = ttk.Frame(main)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Debatt-transkriberaren", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="Video eller URL in – talare, tider och svensk transkribering ut som JSON",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Button(header, text="Hjälp", command=self._open_help).grid(
            row=0, column=1, rowspan=2, sticky="e"
        )

        source_card = ttk.LabelFrame(
            main, text="1. Välj inspelning och resultat", style="Card.TLabelframe"
        )
        source_card.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        source_card.columnconfigure(1, weight=1)
        ttk.Label(source_card, text="Video eller URL").grid(row=0, column=0, sticky="w")
        self.source_entry = ttk.Entry(source_card, textvariable=self.source_var)
        self.source_entry.grid(row=0, column=1, sticky="ew", padx=10)
        ttk.Button(source_card, text="Välj fil …", command=self._browse_source).grid(
            row=0, column=2
        )
        ttk.Label(source_card, text="Spara JSON som").grid(
            row=1, column=0, sticky="w", pady=(9, 0)
        )
        self.output_entry = ttk.Entry(source_card, textvariable=self.output_var)
        self.output_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=(9, 0))
        ttk.Button(source_card, text="Välj plats …", command=self._browse_output).grid(
            row=1, column=2, pady=(9, 0)
        )

        options = ttk.Frame(main)
        options.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        options.columnconfigure(0, weight=1, uniform="options")
        options.columnconfigure(1, weight=1, uniform="options")

        mode_card = ttk.LabelFrame(
            options, text="2. Transkribering", style="Card.TLabelframe"
        )
        mode_card.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        ttk.Radiobutton(
            mode_card,
            text="OpenAI – enklast och snabbt",
            variable=self.transcriber_var,
            value="openai",
            command=self._update_mode_ui,
        ).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            mode_card,
            text="Lokalt – inga API-nycklar",
            variable=self.transcriber_var,
            value="local",
            command=self._update_mode_ui,
        ).grid(row=1, column=0, sticky="w", pady=(5, 0))
        ttk.Label(
            mode_card,
            textvariable=self.mode_note_var,
            style="Hint.TLabel",
            wraplength=390,
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))

        identity_card = ttk.LabelFrame(
            options, text="3. Talaridentifiering", style="Card.TLabelframe"
        )
        identity_card.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self.identity_check = ttk.Checkbutton(
            identity_card,
            text="Identifiera talare från bilden",
            variable=self.identity_var,
            command=self._update_identity_ui,
        )
        self.identity_check.grid(row=0, column=0, sticky="w")
        self.ocr_check = ttk.Checkbutton(
            identity_card, text="Använd även namnskyltar (OCR)", variable=self.ocr_var
        )
        self.ocr_check.grid(row=1, column=0, sticky="w", pady=(5, 0))
        ttk.Label(
            identity_card,
            text="Osäkra personer skrivs som okända, aldrig som en gissning.",
            style="Hint.TLabel",
            wraplength=390,
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))

        credentials = ttk.LabelFrame(
            main, text="4. API-nyckel", style="Card.TLabelframe"
        )
        credentials.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        credentials.columnconfigure(1, weight=1)
        self.openai_label = ttk.Label(credentials, text="OpenAI API-nyckel")
        self.openai_label.grid(row=0, column=0, sticky="w")
        self.openai_entry = ttk.Entry(
            credentials, textvariable=self.openai_key_var, show="●"
        )
        self.openai_entry.grid(row=0, column=1, sticky="ew", padx=10)
        self.secret_toggle = ttk.Checkbutton(
            credentials,
            text="Visa",
            variable=self.show_secrets_var,
            command=self._toggle_secret_visibility,
        )
        self.secret_toggle.grid(row=0, column=2)
        ttk.Label(
            credentials,
            textvariable=self.credentials_note_var,
            style="Hint.TLabel",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))

        controls = ttk.Frame(main)
        controls.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        controls.columnconfigure(2, weight=1)
        self.advanced_button = ttk.Button(
            controls, text="Avancerat …", command=self._open_advanced
        )
        self.advanced_button.grid(row=0, column=0, sticky="w")
        self.factcheck_button = ttk.Button(
            controls,
            text="Skapa faktagranskad film …",
            command=self._open_factcheck_dialog,
        )
        self.factcheck_button.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.cancel_button = ttk.Button(
            controls, text="Avbryt", command=self._cancel, state="disabled"
        )
        self.cancel_button.grid(row=0, column=3, padx=(8, 0))
        self.start_button = ttk.Button(
            controls, text="Starta analys", style="Primary.TButton", command=self._start
        )
        self.start_button.grid(row=0, column=4, padx=(8, 0))

        status_card = ttk.LabelFrame(main, text="Körstatus", style="Card.TLabelframe")
        status_card.grid(row=5, column=0, sticky="nsew")
        status_card.columnconfigure(0, weight=1)
        status_card.rowconfigure(3, weight=1)
        status_row = ttk.Frame(status_card)
        status_row.grid(row=0, column=0, sticky="ew")
        ttk.Label(status_row, textvariable=self.status_var, style="Status.TLabel").grid(
            row=0, column=0, sticky="w"
        )

        self.progress_panel = ttk.Frame(status_card)
        self.progress_panel.grid(row=1, column=0, sticky="ew", pady=(8, 2))
        self.progress_panel.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(
            self.progress_panel, mode="indeterminate", maximum=100
        )
        self.progress.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            self.progress_panel,
            textvariable=self.progress_detail_var,
            style="Hint.TLabel",
        ).grid(row=0, column=1, sticky="e", padx=(12, 0))
        self.progress_panel.grid_remove()
        result_buttons = ttk.Frame(status_card)
        result_buttons.grid(row=2, column=0, sticky="w", pady=(8, 7))
        self.open_result_button = ttk.Button(
            result_buttons,
            text="Öppna JSON",
            command=self._open_result,
            state="disabled",
        )
        self.open_result_button.grid(row=0, column=0)
        self.open_folder_button = ttk.Button(
            result_buttons,
            text="Visa i mapp",
            command=self._open_output_folder,
            state="disabled",
        )
        self.open_folder_button.grid(row=0, column=1, padx=(8, 0))
        self.log = tk.Text(
            status_card,
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
        self._log("Välj en videofil eller klistra in en URL för att börja.")
        self._update_identity_ui()

    def _build_advanced(self, frame: ttk.LabelFrame) -> None:
        ttk.Label(frame, text="Språk").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.language_var, width=8).grid(
            row=0, column=1, sticky="w", padx=(8, 24)
        )
        ttk.Label(frame, text="Whisper-modell").grid(row=0, column=2, sticky="w")
        ttk.Combobox(
            frame,
            textvariable=self.whisper_model_var,
            values=("tiny", "base", "small", "medium", "large-v3"),
            state="readonly",
            width=12,
        ).grid(row=0, column=3, sticky="w", padx=(8, 24))
        ttk.Label(frame, text="Enhet").grid(row=0, column=4, sticky="w")
        ttk.Combobox(
            frame,
            textvariable=self.device_var,
            values=("cpu", "cuda"),
            state="readonly",
            width=8,
        ).grid(row=0, column=5, sticky="w", padx=(8, 0))

        ttk.Label(frame, text="Min talare").grid(
            row=1, column=0, sticky="w", pady=(9, 0)
        )
        ttk.Entry(frame, textvariable=self.min_speakers_var, width=8).grid(
            row=1, column=1, sticky="w", padx=(8, 24), pady=(9, 0)
        )
        ttk.Label(frame, text="Max talare").grid(
            row=1, column=2, sticky="w", pady=(9, 0)
        )
        ttk.Entry(frame, textvariable=self.max_speakers_var, width=8).grid(
            row=1, column=3, sticky="w", padx=(8, 24), pady=(9, 0)
        )
        ttk.Checkbutton(
            frame,
            text="Ta med tidigare riksdagsledamöter",
            variable=self.include_former_var,
        ).grid(row=1, column=4, columnspan=2, sticky="w", pady=(9, 0))

        ttk.Label(frame, text="Extra talarregister").grid(
            row=2, column=0, sticky="w", pady=(9, 0)
        )
        ttk.Entry(frame, textvariable=self.extra_roster_var).grid(
            row=2, column=1, columnspan=4, sticky="ew", padx=(8, 8), pady=(9, 0)
        )
        ttk.Button(frame, text="Välj …", command=self._browse_roster).grid(
            row=2, column=5, sticky="e", pady=(9, 0)
        )
        ttk.Checkbutton(
            frame,
            text="Kräv identifiering (avbryt om den inte går att köra)",
            variable=self.require_identity_var,
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(9, 0))
        ttk.Label(frame, text="Beräkningstyp").grid(
            row=3, column=3, sticky="e", pady=(9, 0)
        )
        ttk.Entry(frame, textvariable=self.compute_type_var, width=12).grid(
            row=3, column=4, columnspan=2, sticky="w", padx=(8, 0), pady=(9, 0)
        )

    def _browse_source(self) -> None:
        initial = self.settings.last_input_dir or str(Path.home())
        selected = filedialog.askopenfilename(
            title="Välj debattinspelning",
            initialdir=initial,
            filetypes=(
                (
                    "Video och ljud",
                    "*.mp4 *.mkv *.webm *.mov *.avi *.m4v *.mpeg *.mp3 *.m4a",
                ),
                ("Alla filer", "*.*"),
            ),
        )
        if selected:
            self.source_var.set(selected)
            output_dir = Path(self.output_var.get()).parent
            self.output_var.set(str(suggested_output(selected, output_dir)))

    def _browse_output(self) -> None:
        current = Path(self.output_var.get())
        selected = filedialog.asksaveasfilename(
            title="Spara transkript",
            initialdir=str(current.parent),
            initialfile=current.name,
            defaultextension=".json",
            filetypes=(("JSON", "*.json"),),
        )
        if selected:
            self.output_var.set(selected)

    def _browse_roster(self) -> None:
        selected = filedialog.askopenfilename(
            title="Välj extra talarregister",
            filetypes=(("JSON", "*.json"), ("Alla filer", "*.*")),
        )
        if selected:
            self.extra_roster_var.set(selected)

    def _update_mode_ui(self) -> None:
        openai_mode = self.transcriber_var.get() == "openai"
        self.openai_entry.configure(state="normal" if openai_mode else "disabled")
        self.openai_label.configure(state="normal" if openai_mode else "disabled")
        self.secret_toggle.configure(state="normal" if openai_mode else "disabled")
        if openai_mode:
            self.mode_note_var.set(
                "Bäst för att komma igång. Endast det komprimerade ljudet skickas till API:t."
            )
            self.credentials_note_var.set(
                "Nyckeln används bara under körningen och sparas inte av programmet."
            )
        else:
            self.mode_note_var.set(
                "Helt lokalt och utan minutavgift. Första körningen hämtar öppna modeller."
            )
            self.credentials_note_var.set(
                "Ingen nyckel behövs i lokalläget; video, ljud och text stannar på datorn."
            )

    def _update_identity_ui(self) -> None:
        state = "normal" if self.identity_var.get() else "disabled"
        self.ocr_check.configure(state=state)

    def _toggle_secret_visibility(self) -> None:
        show = "" if self.show_secrets_var.get() else "●"
        self.openai_entry.configure(show=show)

    def _open_advanced(self) -> None:
        if self.advanced_window is not None and self.advanced_window.winfo_exists():
            self.advanced_window.lift()
            self.advanced_window.focus_force()
            return
        window = tk.Toplevel(self.root)
        self.advanced_window = window
        self.advanced_visible = True
        window.title("Avancerade val")
        window.transient(self.root)
        window.resizable(False, False)
        container = ttk.Frame(window, padding=16)
        container.grid(row=0, column=0, sticky="nsew")
        advanced = ttk.LabelFrame(
            container, text="Modeller och talarregister", style="Card.TLabelframe"
        )
        advanced.grid(row=0, column=0, sticky="nsew")
        advanced.columnconfigure(1, weight=1)
        self._build_advanced(advanced)
        ttk.Button(container, text="Stäng", command=self._close_advanced).grid(
            row=1, column=0, sticky="e", pady=(12, 0)
        )
        window.protocol("WM_DELETE_WINDOW", self._close_advanced)
        window.update_idletasks()
        x = self.root.winfo_rootx() + max(
            20, (self.root.winfo_width() - window.winfo_width()) // 2
        )
        y = self.root.winfo_rooty() + 80
        window.geometry(f"+{x}+{y}")
        window.grab_set()

    def _open_factcheck_dialog(self) -> None:
        if (
            self.factcheck_dialog is not None
            and self.factcheck_dialog.window.winfo_exists()
        ):
            self.factcheck_dialog.window.lift()
            self.factcheck_dialog.window.focus_force()
            return
        output_text = self.output_var.get().strip()
        output_dir = (
            Path(output_text).expanduser().parent
            if output_text
            else Path.home() / "Documents"
        )
        self.factcheck_dialog = FactCheckVideoDialog(
            self.root,
            initial_source=self.source_var.get().strip(),
            output_dir=output_dir,
        )

    def _close_advanced(self) -> None:
        if self.advanced_window is not None and self.advanced_window.winfo_exists():
            self.advanced_window.grab_release()
            self.advanced_window.destroy()
        self.advanced_window = None
        self.advanced_visible = False

    def _collect_job(self) -> GuiJob:
        return GuiJob(
            source=self.source_var.get().strip(),
            output=self.output_var.get().strip(),
            transcriber=self.transcriber_var.get(),
            language=self.language_var.get().strip(),
            openai_key=self.openai_key_var.get().strip(),
            identify_speakers=self.identity_var.get(),
            use_ocr=self.ocr_var.get(),
            require_identity=self.require_identity_var.get(),
            include_former=self.include_former_var.get(),
            whisper_model=self.whisper_model_var.get(),
            device=self.device_var.get(),
            compute_type=self.compute_type_var.get().strip(),
            min_speakers=self.min_speakers_var.get().strip(),
            max_speakers=self.max_speakers_var.get().strip(),
            extra_roster=self.extra_roster_var.get().strip(),
        )

    def _start(self) -> None:
        job = self._collect_job()
        errors = validate_job(job)
        if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
            errors.append(
                "FFmpeg och FFprobe måste vara installerade och finnas i PATH."
            )
        if job.identify_speakers:
            missing = [
                name
                for name in ("cv2", "numpy", "onnxruntime")
                if not _module_available(name)
            ]
            if missing:
                errors.append(
                    "Bildidentifieringen saknar paket: "
                    + ", ".join(missing)
                    + ". Kör installationen igen."
                )
        if job.transcriber == "local":
            missing_local = [
                name
                for name in ("faster_whisper", "sherpa_onnx")
                if not _module_available(name)
            ]
            if missing_local:
                errors.append(
                    "Lokalläget saknar modellpaket. Kör install-local-gui.bat först."
                )
            elif job.device == "cuda":
                missing_cuda = missing_cuda_libraries()
                if missing_cuda:
                    job.device = "cpu"
                    job.compute_type = "int8"
                    self.device_var.set("cpu")
                    self.compute_type_var.set("int8")
                    names = ", ".join(missing_cuda)
                    self._log(
                        f"CUDA-bibliotek saknas ({names}). Växlar automatiskt till CPU."
                    )
                    messagebox.showwarning(
                        "CUDA saknas – använder CPU",
                        "NVIDIA/CUDA är valt, men nödvändiga bibliotek kunde inte "
                        f"läsas ({names}). Analysen fortsätter på CPU med int8.\n\n"
                        "Modellen large-v3 kan då vara långsam; välj small under "
                        "Avancerat för en snabbare körning.",
                        parent=self.root,
                    )
        if errors:
            messagebox.showerror(
                "Kan inte starta", "\n\n".join(errors), parent=self.root
            )
            return

        self._save_non_secret_settings(job)
        self.cancel_event.clear()
        self.last_output = None
        self._set_busy(True)
        self.status_var.set("Arbetar …")
        self._log("Startar en ny analys.")
        self.worker = threading.Thread(
            target=self._run_job, args=(job,), daemon=True, name="debate-analysis"
        )
        self.worker.start()

    def _run_job(self, job: GuiJob) -> None:
        try:
            with _temporary_environment(
                OPENAI_API_KEY=job.openai_key if job.transcriber == "openai" else None,
            ):
                transcriber = (
                    OpenAIDiarizedTranscriber(language=job.language)
                    if job.transcriber == "openai"
                    else LocalTranscriber(
                        language=job.language,
                        whisper_model=job.whisper_model,
                        device=job.device,
                        compute_type=job.compute_type,
                        min_speakers=parse_optional_positive_int(
                            job.min_speakers, "Minsta antal talare"
                        ),
                        max_speakers=parse_optional_positive_int(
                            job.max_speakers, "Högsta antal talare"
                        ),
                        cache_dir=self.cache_dir,
                    )
                )
                with tempfile.TemporaryDirectory(
                    prefix="debate-transcriber-"
                ) as temporary:
                    result = analyze_debate(
                        job.source,
                        output=Path(job.output).expanduser().resolve(),
                        workdir=Path(temporary),
                        cache_dir=self.cache_dir,
                        transcriber=transcriber,
                        identify_speakers=job.identify_speakers,
                        require_identity=job.require_identity,
                        use_ocr=job.use_ocr,
                        extra_roster=(
                            Path(job.extra_roster).expanduser().resolve()
                            if job.extra_roster
                            else None
                        ),
                        include_former=job.include_former,
                        progress=lambda message: self.events.put(("progress", message)),
                        transcription_progress=lambda update: self.events.put(
                            ("transcription_progress", update)
                        ),
                        should_cancel=self.cancel_event.is_set,
                    )
            self.events.put(
                (
                    "done",
                    {
                        "output": str(Path(job.output).expanduser().resolve()),
                        "warnings": result.warnings,
                        "segments": len(result.segments),
                        "speakers": len(result.speakers),
                    },
                )
            )
        except AnalysisCancelled:
            self.events.put(("cancelled", "Analysen avbröts."))
        except Exception as error:
            self.events.put(("error", str(error)))

    def _cancel(self) -> None:
        if self.worker is None or not self.worker.is_alive():
            return
        self.cancel_event.set()
        self.cancel_button.configure(state="disabled")
        self.status_var.set("Avbryter efter aktuellt steg …")
        self._log(
            "Avbrott begärt. Ett pågående modell- eller API-anrop måste slutföras först."
        )

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "progress":
                    self.status_var.set(str(payload))
                    self._log(str(payload))
                elif kind == "transcription_progress" and isinstance(
                    payload, TranscriptionProgress
                ):
                    self._show_transcription_progress(payload)
                elif kind == "done":
                    data = dict(payload)  # type: ignore[arg-type]
                    self.last_output = Path(str(data["output"]))
                    warnings = list(data["warnings"])
                    self._set_busy(False)
                    self.status_var.set("Klar med varningar" if warnings else "Klar")
                    self._log(
                        f"Klart: {data['segments']} segment och {data['speakers']} talare."
                    )
                    for warning in warnings:
                        self._log(f"Varning: {warning}")
                    self.open_result_button.configure(state="normal")
                    self.open_folder_button.configure(state="normal")
                    messagebox.showinfo(
                        "Analysen är klar",
                        f"JSON-resultatet har sparats här:\n{self.last_output}",
                        parent=self.root,
                    )
                elif kind == "cancelled":
                    self._set_busy(False)
                    self.status_var.set("Avbruten")
                    self._log(str(payload))
                elif kind == "error":
                    self._set_busy(False)
                    self.status_var.set("Fel")
                    self._log(f"Fel: {payload}")
                    messagebox.showerror(
                        "Analysen misslyckades", str(payload), parent=self.root
                    )
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _set_busy(self, busy: bool) -> None:
        self.start_button.configure(state="disabled" if busy else "normal")
        self.factcheck_button.configure(state="disabled" if busy else "normal")
        self.cancel_button.configure(state="normal" if busy else "disabled")
        if busy:
            self.transcription_started_at = None
            self.progress_detail_var.set("Förbereder analysen …")
            self.progress.configure(mode="indeterminate", value=0)
            self.progress_panel.grid()
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress_panel.grid_remove()

    def _show_transcription_progress(self, update: TranscriptionProgress) -> None:
        now = time.monotonic()
        if self.transcription_started_at is None or update.processed_seconds <= 0:
            self.transcription_started_at = now

        elapsed = max(0.0, now - self.transcription_started_at)
        remaining = estimate_remaining_seconds(elapsed, update)
        percent = round(update.percent)
        position = format_media_time(
            min(update.processed_seconds, update.total_seconds)
        )
        total = format_media_time(update.total_seconds)

        self.progress.stop()
        self.progress.configure(mode="determinate", maximum=100, value=update.percent)
        self.progress_detail_var.set(
            f"{percent} % · {position} av {total} · {format_remaining_time(remaining)}"
        )
        if update.ratio >= 1:
            self.status_var.set("Transkriberingen är klar …")
        else:
            self.status_var.set("Transkriberar filmen …")

    def _save_non_secret_settings(self, job: GuiJob | None = None) -> None:
        job = job or self._collect_job()
        source = job.source
        last_input_dir = self.settings.last_input_dir
        if source and not source.startswith(("http://", "https://")):
            last_input_dir = str(Path(source).expanduser().parent)
        output = Path(job.output).expanduser() if job.output else None
        self.settings = GuiSettings(
            transcriber=job.transcriber,
            language=job.language,
            identify_speakers=job.identify_speakers,
            use_ocr=job.use_ocr,
            require_identity=job.require_identity,
            include_former=job.include_former,
            whisper_model=job.whisper_model,
            device=job.device,
            compute_type=job.compute_type,
            min_speakers=job.min_speakers,
            max_speakers=job.max_speakers,
            last_input_dir=last_input_dir,
            last_output_dir=str(output.parent)
            if output
            else self.settings.last_output_dir,
            extra_roster=job.extra_roster,
        )
        save_settings(self.settings_path, self.settings)

    def _log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{timestamp}] {message}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _open_result(self) -> None:
        if self.last_output and self.last_output.is_file():
            _open_path(self.last_output)

    def _open_output_folder(self) -> None:
        if not self.last_output:
            return
        if sys.platform == "win32":
            subprocess.Popen(["explorer.exe", "/select,", str(self.last_output)])
        else:
            _open_path(self.last_output.parent)

    def _open_help(self) -> None:
        readme = Path(__file__).resolve().parents[2] / "README.md"
        if readme.is_file():
            _open_path(readme)
        else:
            webbrowser.open(
                "https://developers.openai.com/api/docs/guides/speech-to-text"
            )

    def _on_close(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            close = messagebox.askyesno(
                "Analys pågår",
                "En analys pågår. Vill du begära avbrott och stänga fönstret?",
                parent=self.root,
            )
            if not close:
                return
            self.cancel_event.set()
        try:
            self._save_non_secret_settings()
        except OSError:
            pass
        self.root.destroy()


@contextlib.contextmanager
def _temporary_environment(**values: str | None) -> Iterator[None]:
    missing = object()
    previous: dict[str, str | object] = {
        key: os.environ.get(key, missing) for key in values
    }
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is missing:
                os.environ.pop(key, None)
            else:
                os.environ[key] = str(value)


def _open_path(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def main() -> None:
    root = tk.Tk()
    try:
        root.iconname("Sanningsmätaren")
    except tk.TclError:
        pass
    DebateTranscriberApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
