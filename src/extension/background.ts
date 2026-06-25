import { savePendingSelection } from "../lib/extensionStorage";

const CONTEXT_MENU_ID = "sanningsmataren-check-selection";
const PANEL_PATH = "extension/popup.html";

interface TabInfo {
  id?: number;
  title?: string;
  url?: string;
  windowId?: number;
}

function createContextMenu(): void {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: CONTEXT_MENU_ID,
      title: "Granska markerad text med Sanningsmätaren",
      contexts: ["selection"],
    });
  });
}

function notifyPendingSelectionChanged(): void {
  chrome.runtime.sendMessage(
    { type: "SM_PENDING_SELECTION_CHANGED" },
    () => void chrome.runtime?.lastError,
  );
}

async function enableSidePanelAction(): Promise<void> {
  if (!chrome.sidePanel?.setPanelBehavior) return;
  await chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
}

async function openReviewPanel(tab?: TabInfo): Promise<void> {
  if (chrome.sidePanel?.open) {
    if (tab?.id) {
      await chrome.sidePanel.open({ tabId: tab.id });
      return;
    }
    if (tab?.windowId) {
      await chrome.sidePanel.open({ windowId: tab.windowId });
      return;
    }
  }

  chrome.windows.create({
    url: chrome.runtime.getURL(PANEL_PATH),
    type: "popup",
    width: 460,
    height: 720,
    focused: true,
  });
}

void enableSidePanelAction();

chrome.runtime.onInstalled.addListener(() => {
  createContextMenu();
  void enableSidePanelAction();
});

chrome.contextMenus.onClicked.addListener(
  async (
    info: {
      menuItemId: string;
      selectionText?: string;
      pageUrl?: string;
    },
    tab?: TabInfo,
  ) => {
    if (info.menuItemId !== CONTEXT_MENU_ID || !info.selectionText?.trim()) {
      return;
    }

    await savePendingSelection({
      text: info.selectionText,
      url: info.pageUrl ?? tab?.url,
      title: tab?.title,
      source: "context-menu",
    });
    notifyPendingSelectionChanged();
    await openReviewPanel(tab);
  },
);

chrome.runtime.onMessage.addListener(
  (
    message: {
      type?: string;
      text?: string;
      url?: string;
      title?: string;
    },
    sender: { tab?: TabInfo },
    sendResponse: (response: { ok: boolean; error?: string }) => void,
  ) => {
    if (message?.type !== "SM_OPEN_SELECTION") return false;

    void (async () => {
      try {
        if (!message.text?.trim()) {
          sendResponse({ ok: false, error: "Ingen markerad text." });
          return;
        }

        await savePendingSelection({
          text: message.text,
          url: message.url,
          title: message.title,
          source: "selection-bubble",
        });
        notifyPendingSelectionChanged();
        await openReviewPanel(sender.tab);
        sendResponse({ ok: true });
      } catch (e) {
        sendResponse({ ok: false, error: (e as Error).message });
      }
    })();

    return true;
  },
);
