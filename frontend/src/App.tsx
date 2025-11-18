import { useCallback, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import dayjs from "dayjs";
import api, { API_BASE_URL, initApiClient } from "./api/client";
import { useTelegram } from "./hooks/useTelegram";
import {
  ApiFile,
  ApiTask,
  ApiUser,
  OverviewStats,
  TaskLogEntry,
  TaskProgress,
  TaskStatus,
  UserStatsPoint,
} from "./types";

type Tab = "dashboard" | "tasks" | "files" | "admin";

const marketplacesOptions = [
  "wildberries",
  "ozon",
  "avito",
  "yandex_market",
  "mr-moto",
];

const validateInitData = (value: string) => {
  if (!value) {
    throw new Error("initData пустой. Откройте приложение из Telegram.");
  }
  if (!value.includes("hash=") || !value.includes("auth_date=")) {
    throw new Error("initData выглядит подозрительно.");
  }
};

const formatBytes = (bytes: number) => {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
};

const wsUrlFromApi = (initData: string) => {
  const url = new URL(API_BASE_URL);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/api/ws/tasks";
  url.searchParams.set("init_data", initData);
  return url.toString();
};

const App = () => {
  const { webApp, colorScheme, initData, initDataUnsafe } = useTelegram();
  const [user, setUser] = useState<ApiUser | null>(null);
  const [tasks, setTasks] = useState<ApiTask[]>([]);
  const [progressMap, setProgressMap] = useState<Record<string, TaskProgress>>({});
  const [files, setFiles] = useState<ApiFile[]>([]);
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [userStats, setUserStats] = useState<UserStatsPoint[]>([]);
  const [userList, setUserList] = useState<ApiUser[]>([]);
  const [systemLogs, setSystemLogs] = useState<TaskLogEntry[]>([]);
  const [adminTasks, setAdminTasks] = useState<ApiTask[]>([]);
  const [activeTab, setActiveTab] = useState<Tab>("dashboard");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [parseForm, setParseForm] = useState({
    query: "",
    marketplaces: marketplacesOptions.slice(0, 2),
    max_products: 50,
  });
  const [uploading, setUploading] = useState(false);
  const [taskLoading, setTaskLoading] = useState(false);

  const confirmAction = useCallback(
    (message: string) =>
      new Promise<boolean>((resolve) => {
        if (!webApp?.showConfirm) {
          // eslint-disable-next-line no-alert
          resolve(window.confirm(message));
          return;
        }
        webApp.showConfirm(message, (ok) => resolve(Boolean(ok)));
      }),
    [webApp]
  );

  const safeInitData = useMemo(
    () => initData || import.meta.env.VITE_DEV_INIT_DATA || "",
    [initData]
  );

  useEffect(() => {
    document.documentElement.dataset.theme = colorScheme;
  }, [colorScheme]);

  useEffect(() => {
    if (!safeInitData || user) return;
    const bootstrap = async () => {
      try {
        validateInitData(safeInitData);
        initApiClient(safeInitData);
        await api.post("/auth/validate", {
          init_data: safeInitData,
        });
        const me = await api.get<ApiUser>("/users/me");
        setUser(me.data);
      } catch (err: any) {
        setError(err.message || "Не удалось инициализировать приложение");
      } finally {
        setLoading(false);
      }
    };
    bootstrap();
  }, [safeInitData, user]);

  const fetchTasks = useCallback(async () => {
    const { data } = await api.get<{ items: ApiTask[] }>("/tasks");
    setTasks(data.items);
  }, []);

  const fetchFiles = useCallback(async () => {
    const { data } = await api.get<{ items: ApiFile[] }>("/files");
    setFiles(data.items);
  }, []);

  const fetchAdminData = useCallback(async () => {
    const [statsRes, userStatsRes, usersRes, logsRes, adminTasksRes] = await Promise.all([
      api.get<OverviewStats>("/admin/stats/overview"),
      api.get<UserStatsPoint[]>("/admin/stats/users"),
      api.get<{ items: ApiUser[] }>("/admin/users"),
      api.get<{ items: TaskLogEntry[] }>("/admin/logs"),
      api.get<{ items: ApiTask[] }>("/admin/tasks"),
    ]);
    setStats(statsRes.data);
    setUserStats(userStatsRes.data);
    setUserList(usersRes.data.items);
    setSystemLogs(logsRes.data.items.slice(0, 20));
    setAdminTasks(adminTasksRes.data.items);
  }, []);

  useEffect(() => {
    if (!user) return;
    fetchTasks().catch(console.error);
    fetchFiles().catch(console.error);
    if (user.role === "ADMIN") {
      fetchAdminData().catch(console.error);
    }
  }, [user, fetchTasks, fetchFiles, fetchAdminData]);

  useEffect(() => {
    if (!safeInitData) return;
    const ws = new WebSocket(wsUrlFromApi(safeInitData));
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        setProgressMap((prev) => ({
          ...prev,
          [payload.task_id]: {
            status: payload.status,
            progress: payload.progress,
            payload: payload.payload,
          },
        }));
      } catch (err) {
        console.error("WS parse error", err);
      }
    };
    return () => ws.close();
  }, [safeInitData]);

  useEffect(() => {
    if (!webApp) return;
    const handler = () => {
      setActiveTab("dashboard");
      webApp.BackButton.hide();
    };
    if (activeTab !== "dashboard") {
      webApp.BackButton.show();
      webApp.BackButton.onClick(handler);
    } else {
      webApp.BackButton.hide();
    }
    return () => webApp.BackButton.offClick(handler);
  }, [webApp, activeTab]);

  useEffect(() => {
    if (!webApp) return;
    const handleMainButton = () => {
      void handleCreateTask();
    };
    if (activeTab === "tasks") {
      webApp.MainButton.setParams({ text: "Запустить парсинг", is_active: true });
      webApp.MainButton.show();
      webApp.MainButton.onClick(handleMainButton);
    } else {
      webApp.MainButton.hide();
    }
    return () => webApp.MainButton.offClick(handleMainButton);
  }, [webApp, activeTab, parseForm]);

  const handleCreateTask = useCallback(async () => {
    if (!parseForm.query.trim()) {
      webApp?.HapticFeedback?.notificationOccurred("warning");
      return;
    }
    try {
      setTaskLoading(true);
      await api.post("/tasks/parse", parseForm);
      webApp?.HapticFeedback?.impactOccurred("heavy");
      await fetchTasks();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
      webApp?.HapticFeedback?.notificationOccurred("error");
    } finally {
      setTaskLoading(false);
    }
  }, [parseForm, fetchTasks, webApp]);

  const handleUpload = useCallback(
    async (file?: File) => {
      if (!file) return;
      const formData = new FormData();
      formData.append("file", file);
      try {
        setUploading(true);
        await api.post("/files/upload", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        webApp?.HapticFeedback?.impactOccurred("medium");
        await fetchFiles();
      } catch (err: any) {
        setError(err.response?.data?.detail || err.message);
        webApp?.HapticFeedback?.notificationOccurred("error");
      } finally {
        setUploading(false);
      }
    },
    [fetchFiles, webApp]
  );

  const handleDeleteTask = async (taskId: string) => {
    if (!(await confirmAction("Отменить задачу?"))) return;
    await api.delete(`/tasks/${taskId}`);
    await fetchTasks();
  };

  const handleDeleteFile = async (fileId: string) => {
    if (!(await confirmAction("Удалить файл?"))) return;
    await api.delete(`/files/${fileId}`);
    await fetchFiles();
  };

  const renderTasks = () => (
    <div className="grid">
      <div className="card">
        <h3>Новая задача</h3>
        <input
          placeholder="Название или SKU"
          value={parseForm.query}
          onChange={(e) => setParseForm({ ...parseForm, query: e.target.value })}
        />
        <label>Маркетплейсы</label>
        <div className="grid two">
          {marketplacesOptions.map((site) => (
            <button
              key={site}
              className={clsx(
                "chip",
                parseForm.marketplaces.includes(site) && "chip--active"
              )}
              onClick={() =>
                setParseForm((prev) => {
                  const exists = prev.marketplaces.includes(site);
                  const next = exists
                    ? prev.marketplaces.filter((s) => s !== site)
                    : [...prev.marketplaces, site];
                  return { ...prev, marketplaces: next };
                })
              }
            >
              {site}
            </button>
          ))}
        </div>
        <label>Максимум товаров</label>
        <input
          type="number"
          value={parseForm.max_products}
          min={10}
          max={1000}
          onChange={(e) =>
            setParseForm({ ...parseForm, max_products: Number(e.target.value) })
          }
        />
        <button disabled={taskLoading} onClick={() => void handleCreateTask()}>
          {taskLoading ? "Запуск..." : "Запустить парсинг"}
        </button>
      </div>

      <div className="grid">
        {tasks.map((task) => {
          const progress = progressMap[task.id];
          const pct = progress?.progress ?? task.progress_percentage;
          return (
            <div key={task.id} className="card">
              <div className="task-head">
                <span>{task.task_type}</span>
                <span className={`status status--${task.status}`}>
                  {task.status}
                </span>
              </div>
              <div className="progress">
                <div className="progress-bar" style={{ width: `${pct}%` }} />
              </div>
              <small>
                Создана: {dayjs(task.created_at).format("DD.MM HH:mm")}
              </small>
              {task.error_message && (
                <p className="error">Ошибка: {task.error_message}</p>
              )}
              <div className="task-actions">
                <button onClick={() => handleDeleteTask(task.id)}>Отменить</button>
                <button
                  onClick={() =>
                    api.post(`/tasks/${task.id}/restart`).then(fetchTasks)
                  }
                  disabled={task.status !== "failed"}
                >
                  Перезапустить
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );

  const renderFiles = () => (
    <div className="grid">
      <div className="card">
        <h3>Загрузить файл</h3>
        <input
          type="file"
          accept=".xml,.xlsx,.mxl"
          onChange={(e) => void handleUpload(e.target.files?.[0] || undefined)}
          disabled={uploading}
        />
        {uploading && <small>Загрузка...</small>}
      </div>

      {files.map((file) => (
        <div key={file.id} className="card">
          <strong>{file.filename}</strong>
          <p>{formatBytes(file.file_size)}</p>
          <small>Дата: {dayjs(file.upload_date).format("DD.MM HH:mm")}</small>
          <div className="task-actions">
            <button
              onClick={async () => {
                const { data } = await api.get<{ url: string }>(
                  `/files/${file.id}/download`
                );
                window.open(data.url, "_blank");
              }}
            >
              Скачать
            </button>
            <button onClick={() => void handleDeleteFile(file.id)}>Удалить</button>
          </div>
        </div>
      ))}
    </div>
  );

  const renderDashboard = () => (
    <div className="grid">
      <div className="card">
        <h2>Добро пожаловать 👋</h2>
        <p>
          {user?.first_name || user?.username}, запускайте задачи парсинга и
          отслеживайте прогресс в реальном времени.
        </p>
      </div>
      {tasks.slice(0, 3).map((task) => (
        <div key={task.id} className="card">
          <strong>{task.task_type}</strong>
          <p>Статус: {task.status}</p>
          <p>Прогресс: {task.progress_percentage}%</p>
        </div>
      ))}
    </div>
  );

  const renderAdmin = () => (
    <div className="grid">
      {stats && (
        <div className="grid two">
          <div className="card">
            <span>Активные пользователи</span>
            <strong>{stats.active_users}</strong>
          </div>
          <div className="card">
            <span>Задач выполнено</span>
            <strong>{stats.completed_tasks}</strong>
          </div>
          <div className="card">
            <span>Всего задач</span>
            <strong>{stats.total_tasks}</strong>
          </div>
          <div className="card">
            <span>Хранилище</span>
            <strong>{stats.storage_usage_mb.toFixed(1)} MB</strong>
          </div>
        </div>
      )}

      <div className="card">
        <h3>Пользователи</h3>
        {userList.map((u) => (
          <div key={u.telegram_id} className="user-row">
            <span>
              {u.username || u.first_name} · {u.role}
            </span>
            <button
              onClick={async () => {
                const nextRole = u.role === "ADMIN" ? "USER" : "ADMIN";
                if (
                  !(await confirmAction(`Изменить роль пользователя на ${nextRole}?`))
                ) {
                  return;
                }
                await api.put(`/admin/users/${u.telegram_id}`, { role: nextRole });
                await fetchAdminData();
              }}
            >
              {u.role === "ADMIN" ? "Назначить USER" : "Назначить ADMIN"}
            </button>
          </div>
        ))}
      </div>

      <div className="card">
        <h3>Задачи системы</h3>
        {adminTasks.slice(0, 5).map((task) => (
          <div key={task.id} className="task-head">
            <span>{task.task_type}</span>
            <span>{task.status}</span>
          </div>
        ))}
      </div>

      <div className="card">
        <h3>Логи</h3>
        {systemLogs.map((log) => (
          <div key={log.id} className="log-row">
            <span>
              [{log.level}] {log.message}
            </span>
            <small>{dayjs(log.created_at).format("DD.MM HH:mm")}</small>
          </div>
        ))}
      </div>

      <div className="card">
        <h3>Динамика пользователей</h3>
        {userStats.slice(-7).map((point) => (
          <div key={point.date} className="task-head">
            <span>{dayjs(point.date).format("DD.MM")}</span>
            <small>+{point.new_users} / активных {point.active_users}</small>
          </div>
        ))}
      </div>
    </div>
  );

  if (loading) {
    return (
      <div className="card" style={{ margin: 16 }}>
        Загрузка...
      </div>
    );
  }

  if (error) {
    return (
      <div className="card" style={{ margin: 16 }}>
        <h3>Ошибка</h3>
        <p>{error}</p>
      </div>
    );
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: "dashboard", label: "Главная" },
    { id: "tasks", label: "Задачи" },
    { id: "files", label: "Файлы" },
  ];

  if (user?.role === "ADMIN") {
    tabs.push({ id: "admin", label: "Админ" });
  }

  return (
    <div className={clsx("app", colorScheme)}>
      <header className="card" style={{ margin: 16 }}>
        <div>
          <h2>Parser BestMoto</h2>
          <p>{user?.username || user?.first_name}</p>
        </div>
        <small>Статус: {user?.role}</small>
      </header>

      <nav className="tab-bar">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={clsx("tab", activeTab === tab.id && "tab--active")}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <main style={{ padding: 16 }}>
        {activeTab === "dashboard" && renderDashboard()}
        {activeTab === "tasks" && renderTasks()}
        {activeTab === "files" && renderFiles()}
        {activeTab === "admin" && user?.role === "ADMIN" && renderAdmin()}
      </main>
    </div>
  );
};

export default App;

