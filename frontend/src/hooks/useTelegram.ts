import { useEffect, useMemo, useState } from "react";

type TelegramWebApp = typeof window.Telegram.WebApp;

const getWebApp = (): TelegramWebApp | null => {
  if (typeof window === "undefined") return null;
  return window.Telegram?.WebApp ?? null;
};

export const useTelegram = () => {
  const webApp = useMemo(() => getWebApp(), []);
  const [colorScheme, setColorScheme] = useState(webApp?.colorScheme || "light");

  useEffect(() => {
    if (!webApp) return;
    webApp.ready();
    webApp.expand();
    const onThemeChanged = () => setColorScheme(webApp.colorScheme);
    webApp.onEvent("themeChanged", onThemeChanged);
    return () => webApp.offEvent("themeChanged", onThemeChanged);
  }, [webApp]);

  return {
    webApp,
    colorScheme,
    initData: webApp?.initData || "",
    initDataUnsafe: webApp?.initDataUnsafe,
  };
};

