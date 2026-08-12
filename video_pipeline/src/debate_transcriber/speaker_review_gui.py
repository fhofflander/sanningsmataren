from __future__ import annotations

import tkinter as tk
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable

from PIL import Image, ImageOps, ImageTk

from .speaker_review import (
    SpeakerReviewDecision,
    SpeakerReviewChoice,
    SpeakerReviewItem,
    review_group_key,
)


@dataclass(slots=True)
class _ReviewGroup:
    key: str
    name: str
    party: str | None
    members: list[SpeakerReviewItem]
    portrait_path: Path | None
    initially_irrelevant: bool


class SpeakerReviewDialog:
    def __init__(
        self,
        parent: tk.Tk,
        items: list[SpeakerReviewItem],
        on_complete: Callable[[SpeakerReviewDecision | None], None],
    ) -> None:
        self.parent = parent
        self.items = items
        self.on_complete = on_complete
        self.window = tk.Toplevel(parent)
        self.window.title("Kontrollera personer i filmen")
        self.window.geometry("940x720")
        self.window.minsize(760, 560)
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self._cancel)
        self.name_vars: dict[str, tk.StringVar] = {}
        self.first_irrelevant_vars: dict[str, tk.BooleanVar] = {}
        self.final_irrelevant_vars: dict[str, tk.BooleanVar] = {}
        self.entry_widgets: dict[str, ttk.Combobox] = {}
        self.choice_by_name: dict[str, SpeakerReviewChoice] = {
            _normalized_name(choice.name): choice
            for item in items
            for choice in item.person_choices
        }
        self._scroll_canvas: tk.Canvas | None = None
        self._photos: list[ImageTk.PhotoImage] = []
        self._finished = False

        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        self.main = ttk.Frame(self.window, padding=18)
        self.main.grid(row=0, column=0, sticky="nsew")
        self.main.columnconfigure(0, weight=1)
        self.main.rowconfigure(2, weight=1)
        self.window.grab_set()
        self.window.lift()
        self.window.focus_force()
        self.window.bind("<MouseWheel>", self._on_mousewheel, add="+")
        self.window.bind("<Button-4>", self._on_mousewheel, add="+")
        self.window.bind("<Button-5>", self._on_mousewheel, add="+")

        if any(item.name is None for item in items):
            self._show_unidentified()
        else:
            self._show_summary()

    def cancel(self) -> None:
        self._cancel()

    def _reset_view(self) -> None:
        self._scroll_canvas = None
        for child in self.main.winfo_children():
            child.destroy()
        self._photos.clear()

    def _show_unidentified(self) -> None:
        self._reset_view()
        unknown = [item for item in self.items if item.name is None]
        ttk.Label(
            self.main,
            text="Steg 1 av 2 – Oidentifierade personer",
            style="Title.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            self.main,
            text=(
                "Välj en person som redan hittats i filmen eller skriv ett nytt "
                "namn. Du kan också markera personen som ej relevant."
            ),
            style="Subtitle.TLabel",
            wraplength=870,
        ).grid(row=1, column=0, sticky="w", pady=(3, 12))

        body = self._scrolling_body()
        for row, item in enumerate(unknown):
            card = ttk.Frame(body, padding=10, relief="solid")
            card.grid(row=row, column=0, sticky="ew", pady=(0, 8))
            card.columnconfigure(1, weight=1)
            self._portrait_label(card, item.portrait_path).grid(
                row=0, column=0, rowspan=3, padx=(0, 14), sticky="nw"
            )
            ttk.Label(
                card,
                text=f"Oidentifierad talare {row + 1}",
                font=("Segoe UI", 11, "bold"),
            ).grid(row=0, column=1, sticky="w")
            ttk.Label(
                card,
                text=self._item_detail(item),
                style="Hint.TLabel",
                wraplength=590,
            ).grid(row=1, column=1, sticky="w", pady=(2, 8))

            controls = ttk.Frame(card)
            controls.grid(row=2, column=1, sticky="ew")
            controls.columnconfigure(1, weight=1)
            ttk.Label(controls, text="Välj/skriv namn").grid(
                row=0, column=0, sticky="w"
            )
            name_var = self.name_vars.setdefault(
                item.speaker_id, tk.StringVar(value="")
            )
            names_in_film = [choice.name for choice in item.person_choices]
            entry = ttk.Combobox(
                controls,
                textvariable=name_var,
                values=names_in_film,
                state="normal",
            )
            entry.configure(
                postcommand=lambda widget=entry: self._refresh_person_choices(
                    widget
                )
            )
            entry.grid(row=0, column=1, sticky="ew", padx=(8, 16))
            self.entry_widgets[item.speaker_id] = entry
            irrelevant_var = self.first_irrelevant_vars.setdefault(
                item.speaker_id, tk.BooleanVar(value=False)
            )
            ttk.Checkbutton(
                controls,
                text="Ej relevant",
                variable=irrelevant_var,
                command=lambda speaker_id=item.speaker_id: self._toggle_name_entry(
                    speaker_id
                ),
            ).grid(row=0, column=2, sticky="e")
            self._toggle_name_entry(item.speaker_id)

        buttons = ttk.Frame(self.main)
        buttons.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        buttons.columnconfigure(0, weight=1)
        ttk.Button(buttons, text="Avbryt", command=self._cancel).grid(
            row=0, column=1
        )
        ttk.Button(
            buttons,
            text="Fortsätt till alla personer",
            style="Primary.TButton",
            command=self._validate_unknown_and_continue,
        ).grid(row=0, column=2, padx=(8, 0))

    def _show_summary(self) -> None:
        self._reset_view()
        groups = self._build_groups()
        ttk.Label(
            self.main,
            text="Steg 2 av 2 – Alla personer i filmen",
            style="Title.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            self.main,
            text=(
                "Listan är avduplicerad och sorterad efter person. De som redan "
                "markerats som ej relevanta visas inte här."
            ),
            style="Subtitle.TLabel",
            wraplength=870,
        ).grid(row=1, column=0, sticky="w", pady=(3, 12))

        body = self._scrolling_body()
        unnamed_index = 0
        for row, group in enumerate(groups):
            display_name = group.name
            if not display_name:
                unnamed_index += 1
                display_name = f"Oidentifierad talare {unnamed_index}"
            card = ttk.Frame(body, padding=10, relief="solid")
            card.grid(row=row, column=0, sticky="ew", pady=(0, 8))
            card.columnconfigure(1, weight=1)
            self._portrait_label(card, group.portrait_path).grid(
                row=0, column=0, rowspan=2, padx=(0, 14), sticky="nw"
            )
            title = display_name
            if group.party:
                title += f" ({group.party})"
            ttk.Label(card, text=title, font=("Segoe UI", 11, "bold")).grid(
                row=0, column=1, sticky="w"
            )
            seconds = sum(item.speaking_seconds for item in group.members)
            if all(item.is_gallery_person for item in group.members):
                group_detail = (
                    "Upptäckt i filmen · "
                    f"{len(group.members)} bildkluster"
                )
            else:
                group_detail = (
                    f"{_format_duration(seconds)} tal · "
                    f"{len(group.members)} röstkluster"
                )
            ttk.Label(
                card,
                text=group_detail,
                style="Hint.TLabel",
            ).grid(row=1, column=1, sticky="w", pady=(3, 0))
            irrelevant_var = tk.BooleanVar(value=group.initially_irrelevant)
            self.final_irrelevant_vars[group.key] = irrelevant_var
            check = ttk.Checkbutton(
                card, text="Ej relevant", variable=irrelevant_var
            )
            check.grid(row=0, column=2, rowspan=2, sticky="e", padx=(15, 0))
            if not group.name and group.initially_irrelevant:
                check.configure(state="disabled")

        buttons = ttk.Frame(self.main)
        buttons.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        buttons.columnconfigure(0, weight=1)
        if any(item.name is None for item in self.items):
            ttk.Button(buttons, text="Tillbaka", command=self._show_unidentified).grid(
                row=0, column=1
            )
        ttk.Button(buttons, text="Avbryt", command=self._cancel).grid(
            row=0, column=2, padx=(8, 0)
        )
        ttk.Button(
            buttons,
            text="Fortsätt analysen",
            style="Primary.TButton",
            command=self._finish,
        ).grid(row=0, column=3, padx=(8, 0))

    def _scrolling_body(self) -> ttk.Frame:
        container = ttk.Frame(self.main)
        container.grid(row=2, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)
        canvas = tk.Canvas(container, highlightthickness=0, bg="#f0f0f0")
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        self._scroll_canvas = canvas
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        body = ttk.Frame(canvas, padding=(3, 3, 8, 3))
        body.columnconfigure(0, weight=1)
        window_id = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window_id, width=event.width),
        )
        return body

    def _on_mousewheel(self, event: tk.Event) -> str | None:
        canvas = self._scroll_canvas
        if canvas is None or not canvas.winfo_exists():
            return None
        if getattr(event, "num", None) == 4:
            steps = -1
        elif getattr(event, "num", None) == 5:
            steps = 1
        else:
            delta = int(getattr(event, "delta", 0) or 0)
            if not delta:
                return None
            steps = -max(1, abs(delta) // 120) if delta > 0 else max(
                1, abs(delta) // 120
            )
        canvas.yview_scroll(steps, "units")
        return "break"

    def _portrait_label(self, parent: tk.Misc, path: Path | None) -> ttk.Label:
        if path is not None and path.is_file():
            try:
                with Image.open(path) as image:
                    portrait = ImageOps.fit(
                        image.convert("RGB"), (128, 104), method=Image.Resampling.LANCZOS
                    )
                photo = ImageTk.PhotoImage(portrait)
                self._photos.append(photo)
                return ttk.Label(parent, image=photo)
            except OSError:
                pass
        return ttk.Label(
            parent,
            text="Ingen bild",
            anchor="center",
            width=18,
            padding=(4, 38),
            relief="solid",
        )

    def _toggle_name_entry(self, speaker_id: str) -> None:
        irrelevant = self.first_irrelevant_vars[speaker_id].get()
        self.entry_widgets[speaker_id].configure(
            state="disabled" if irrelevant else "normal"
        )

    def _refresh_person_choices(self, widget: ttk.Combobox) -> None:
        names = {
            choice.name
            for item in self.items
            for choice in item.person_choices
        }
        names.update(
            value
            for variable in self.name_vars.values()
            if (value := variable.get().strip())
        )
        widget.configure(values=sorted(names, key=str.casefold))

    def _validate_unknown_and_continue(self) -> None:
        missing: list[int] = []
        unknown = [item for item in self.items if item.name is None]
        for index, item in enumerate(unknown, start=1):
            irrelevant = self.first_irrelevant_vars[item.speaker_id].get()
            name = self.name_vars[item.speaker_id].get().strip()
            if not irrelevant and not name:
                missing.append(index)
        if missing:
            messagebox.showerror(
                "Namn saknas",
                "Ange namn eller markera ej relevant för oidentifierad talare "
                + ", ".join(str(index) for index in missing)
                + ".",
                parent=self.window,
            )
            return
        self._show_summary()

    def _build_groups(self) -> list[_ReviewGroup]:
        groups: OrderedDict[str, _ReviewGroup] = OrderedDict()
        for item in self.items:
            initially_irrelevant = (
                self.first_irrelevant_vars[item.speaker_id].get()
                if item.speaker_id in self.first_irrelevant_vars
                else False
            )
            if initially_irrelevant:
                continue
            manual_name = (
                self.name_vars[item.speaker_id].get().strip()
                if item.speaker_id in self.name_vars
                else ""
            )
            name = manual_name or (item.name or "")
            key = review_group_key(item, manual_name)
            existing = groups.get(key)
            if existing is None:
                groups[key] = _ReviewGroup(
                    key=key,
                    name=name,
                    party=item.party if not manual_name else None,
                    members=[item],
                    portrait_path=item.portrait_path,
                    initially_irrelevant=initially_irrelevant,
                )
            else:
                existing.members.append(item)
                if existing.portrait_path is None:
                    existing.portrait_path = item.portrait_path
        return sorted(
            groups.values(),
            key=lambda group: (
                not bool(group.name.strip()),
                _normalized_name(group.name),
                group.key,
            ),
        )

    def _finish(self) -> None:
        groups = self._build_groups()
        decision = SpeakerReviewDecision()
        for item in self.items:
            if item.name is None:
                manual_name = self.name_vars[item.speaker_id].get().strip()
                first_irrelevant = self.first_irrelevant_vars[
                    item.speaker_id
                ].get()
                if first_irrelevant:
                    decision.irrelevant_speaker_ids.add(item.speaker_id)
                if manual_name and not first_irrelevant:
                    selected = self.choice_by_name.get(
                        _normalized_name(manual_name)
                    )
                    if selected is not None:
                        decision.selected_people_by_speaker_id[
                            item.speaker_id
                        ] = selected
                    else:
                        decision.names_by_speaker_id[item.speaker_id] = manual_name
        for group in groups:
            if self.final_irrelevant_vars[group.key].get():
                decision.irrelevant_speaker_ids.update(
                    item.speaker_id for item in group.members
                )
        self._complete(decision)

    def _cancel(self) -> None:
        if self._finished:
            return
        cancel = messagebox.askyesno(
            "Avbryt analysen",
            "Vill du avbryta analysen utan att skapa JSON-filen?",
            parent=self.window,
        )
        if cancel:
            self._complete(None)

    def _complete(self, decision: SpeakerReviewDecision | None) -> None:
        if self._finished:
            return
        self._finished = True
        try:
            self.window.grab_release()
        except tk.TclError:
            pass
        self.window.destroy()
        self.on_complete(decision)

    @staticmethod
    def _item_detail(item: SpeakerReviewItem) -> str:
        if item.is_gallery_person:
            return "Person upptäckt i filmen"
        sample = " ".join(item.sample_text.split())
        if len(sample) > 150:
            sample = sample[:147].rstrip() + "…"
        detail = f"{_format_duration(item.speaking_seconds)} tal"
        return f'{detail} · ”{sample}”' if sample else detail


def _format_duration(seconds: float) -> str:
    rounded = max(0, round(seconds))
    minutes, secs = divmod(rounded, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours} h {minutes} min"
    if minutes:
        return f"{minutes} min {secs} s"
    return f"{secs} s"


def _normalized_name(value: str) -> str:
    return " ".join(value.casefold().split())
