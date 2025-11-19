declare namespace Telegram {
  type Theme = "light" | "dark";

  interface MainButton {
    setParams(params: { text?: string; is_active?: boolean }): void;
    show(): void;
    hide(): void;
    onClick(handler: () => void): void;
    offClick(handler: () => void): void;
  }

  interface BackButton {
    show(): void;
    hide(): void;
    onClick(handler: () => void): void;
    offClick(handler: () => void): void;
  }

  interface HapticFeedback {
    impactOccurred(style: "light" | "medium" | "heavy" | "rigid" | "soft"): void;
    notificationOccurred(style: "error" | "success" | "warning"): void;
  }

  interface WebApp {
    initData: string;
    initDataUnsafe: Record<string, unknown>;
    colorScheme: Theme;
    ready(): void;
    expand(): void;
    MainButton: MainButton;
    BackButton: BackButton;
    HapticFeedback?: HapticFeedback;
    showConfirm(message: string, callback: (ok: boolean) => void): void;
    onEvent(event: "themeChanged", handler: () => void): void;
    offEvent(event: "themeChanged", handler: () => void): void;
  }
}

declare global {
  interface Window {
    Telegram?: {
      WebApp: Telegram.WebApp;
    };
  }
}

export {};

