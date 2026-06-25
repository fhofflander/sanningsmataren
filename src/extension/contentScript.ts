const BUTTON_ID = "sanningsmataren-selection-button";
const MIN_SELECTION_LENGTH = 12;
const MAX_SELECTION_LENGTH = 12000;
const MAX_PAGE_TEXT_LENGTH = 50000;

let selectedText = "";
let hideTimer = 0;

function normalizeText(text: string, maxLength: number): string {
  return text.replace(/\s+/g, " ").trim().slice(0, maxLength);
}

function selectionText(): string {
  return normalizeText(window.getSelection()?.toString() ?? "", MAX_SELECTION_LENGTH);
}

function pageText(): string {
  return normalizeText(document.body?.innerText ?? "", MAX_PAGE_TEXT_LENGTH);
}

function removeButton(): void {
  window.clearTimeout(hideTimer);
  document.getElementById(BUTTON_ID)?.remove();
}

function createButton(): HTMLButtonElement {
  const existing = document.getElementById(BUTTON_ID);
  if (existing instanceof HTMLButtonElement) return existing;

  const button = document.createElement("button");
  button.id = BUTTON_ID;
  button.type = "button";
  button.textContent = "Granska";
  button.setAttribute("aria-label", "Granska markerad text med Sanningsmätaren");
  Object.assign(button.style, {
    position: "fixed",
    zIndex: "2147483647",
    border: "1px solid rgba(30, 64, 175, 0.25)",
    borderRadius: "999px",
    background: "#1d4ed8",
    color: "#ffffff",
    boxShadow: "0 8px 20px rgba(15, 23, 42, 0.18)",
    cursor: "pointer",
    font: "600 12px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
    letterSpacing: "0.02em",
    padding: "7px 11px",
  });

  button.addEventListener("mousedown", (event) => event.preventDefault());
  button.addEventListener("click", () => {
    const text = selectedText || selectionText();
    if (!text) return;

    chrome.runtime.sendMessage({
      type: "SM_OPEN_SELECTION",
      text,
      url: location.href,
      title: document.title,
    });
    removeButton();
  });

  document.documentElement.appendChild(button);
  return button;
}

function selectionRect(): DOMRect | null {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0) return null;
  const range = selection.getRangeAt(0);
  const rects = Array.from(range.getClientRects()).filter(
    (rect) => rect.width > 0 && rect.height > 0,
  );
  return rects[0] ?? null;
}

function showButton(): void {
  selectedText = selectionText();
  if (selectedText.length < MIN_SELECTION_LENGTH) {
    removeButton();
    return;
  }

  const rect = selectionRect();
  if (!rect) {
    removeButton();
    return;
  }

  const button = createButton();
  const top = Math.max(8, rect.top - 42);
  const left = Math.min(
    window.innerWidth - 96,
    Math.max(8, rect.left + rect.width / 2 - 42),
  );
  button.style.top = `${top}px`;
  button.style.left = `${left}px`;

  window.clearTimeout(hideTimer);
  hideTimer = window.setTimeout(removeButton, 8000);
}

function scheduleShow(): void {
  window.setTimeout(showButton, 80);
}

document.addEventListener("mouseup", scheduleShow);
document.addEventListener("keyup", scheduleShow);
document.addEventListener("scroll", removeButton, true);

chrome.runtime.onMessage.addListener(
  (
    message: { type?: string },
    _sender: unknown,
    sendResponse: (response: { text: string; url: string; title: string }) => void,
  ) => {
    if (message?.type === "SM_GET_SELECTION") {
      sendResponse({
        text: selectionText(),
        url: location.href,
        title: document.title,
      });
      return true;
    }

    if (message?.type === "SM_GET_PAGE_TEXT") {
      sendResponse({
        text: pageText(),
        url: location.href,
        title: document.title,
      });
      return true;
    }

    return false;
  },
);
