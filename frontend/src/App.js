import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useCallback, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import dayjs from "dayjs";
import api, { API_BASE_URL, initApiClient } from "./api/client";
import { useTelegram } from "./hooks/useTelegram";
const marketplacesOptions = [
    "wildberries",
    "ozon",
    "avito",
    "yandex_market",
    "mr-moto",
];
const validateInitData = (value) => {
    if (!value) {
        throw new Error("initData пустой. Откройте приложение из Telegram.");
    }
    if (!value.includes("hash=") || !value.includes("auth_date=")) {
        throw new Error("initData выглядит подозрительно.");
    }
};
const formatBytes = (bytes) => {
    if (bytes === 0)
        return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
};
const wsUrlFromApi = (initData) => {
    const url = new URL(API_BASE_URL);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = "/api/ws/tasks";
    url.searchParams.set("init_data", initData);
    return url.toString();
};
const App = () => {
    const { webApp, colorScheme, initData, initDataUnsafe } = useTelegram();
    const [user, setUser] = useState(null);
    const [tasks, setTasks] = useState([]);
    const [progressMap, setProgressMap] = useState({});
    const [files, setFiles] = useState([]);
    const [stats, setStats] = useState(null);
    const [userStats, setUserStats] = useState([]);
    const [userList, setUserList] = useState([]);
    const [systemLogs, setSystemLogs] = useState([]);
    const [adminTasks, setAdminTasks] = useState([]);
    const [activeTab, setActiveTab] = useState("dashboard");
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [parseForm, setParseForm] = useState({
        query: "",
        marketplaces: marketplacesOptions.slice(0, 2),
        max_products: 50,
    });
    const [uploading, setUploading] = useState(false);
    const [taskLoading, setTaskLoading] = useState(false);
    const confirmAction = useCallback((message) => new Promise((resolve) => {
        if (!webApp?.showConfirm) {
            // eslint-disable-next-line no-alert
            resolve(window.confirm(message));
            return;
        }
        webApp.showConfirm(message, (ok) => resolve(Boolean(ok)));
    }), [webApp]);
    const safeInitData = useMemo(() => initData || import.meta.env.VITE_DEV_INIT_DATA || "", [initData]);
    useEffect(() => {
        document.documentElement.dataset.theme = colorScheme;
    }, [colorScheme]);
    useEffect(() => {
        if (!safeInitData || user)
            return;
        const bootstrap = async () => {
            try {
                validateInitData(safeInitData);
                initApiClient(safeInitData);
                await api.post("/auth/validate", {
                    init_data: safeInitData,
                });
                const me = await api.get("/users/me");
                setUser(me.data);
            }
            catch (err) {
                setError(err.message || "Не удалось инициализировать приложение");
            }
            finally {
                setLoading(false);
            }
        };
        bootstrap();
    }, [safeInitData, user]);
    const fetchTasks = useCallback(async () => {
        const { data } = await api.get("/tasks");
        setTasks(data.items);
    }, []);
    const fetchFiles = useCallback(async () => {
        const { data } = await api.get("/files");
        setFiles(data.items);
    }, []);
    const fetchAdminData = useCallback(async () => {
        const [statsRes, userStatsRes, usersRes, logsRes, adminTasksRes] = await Promise.all([
            api.get("/admin/stats/overview"),
            api.get("/admin/stats/users"),
            api.get("/admin/users"),
            api.get("/admin/logs"),
            api.get("/admin/tasks"),
        ]);
        setStats(statsRes.data);
        setUserStats(userStatsRes.data);
        setUserList(usersRes.data.items);
        setSystemLogs(logsRes.data.items.slice(0, 20));
        setAdminTasks(adminTasksRes.data.items);
    }, []);
    useEffect(() => {
        if (!user)
            return;
        fetchTasks().catch(console.error);
        fetchFiles().catch(console.error);
        if (user.role === "ADMIN") {
            fetchAdminData().catch(console.error);
        }
    }, [user, fetchTasks, fetchFiles, fetchAdminData]);
    useEffect(() => {
        if (!safeInitData)
            return;
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
            }
            catch (err) {
                console.error("WS parse error", err);
            }
        };
        return () => ws.close();
    }, [safeInitData]);
    useEffect(() => {
        if (!webApp)
            return;
        const handler = () => {
            setActiveTab("dashboard");
            webApp.BackButton.hide();
        };
        if (activeTab !== "dashboard") {
            webApp.BackButton.show();
            webApp.BackButton.onClick(handler);
        }
        else {
            webApp.BackButton.hide();
        }
        return () => webApp.BackButton.offClick(handler);
    }, [webApp, activeTab]);
    useEffect(() => {
        if (!webApp)
            return;
        const handleMainButton = () => {
            void handleCreateTask();
        };
        if (activeTab === "tasks") {
            webApp.MainButton.setParams({ text: "Запустить парсинг", is_active: true });
            webApp.MainButton.show();
            webApp.MainButton.onClick(handleMainButton);
        }
        else {
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
        }
        catch (err) {
            setError(err.response?.data?.detail || err.message);
            webApp?.HapticFeedback?.notificationOccurred("error");
        }
        finally {
            setTaskLoading(false);
        }
    }, [parseForm, fetchTasks, webApp]);
    const handleUpload = useCallback(async (file) => {
        if (!file)
            return;
        const formData = new FormData();
        formData.append("file", file);
        try {
            setUploading(true);
            await api.post("/files/upload", formData, {
                headers: { "Content-Type": "multipart/form-data" },
            });
            webApp?.HapticFeedback?.impactOccurred("medium");
            await fetchFiles();
        }
        catch (err) {
            setError(err.response?.data?.detail || err.message);
            webApp?.HapticFeedback?.notificationOccurred("error");
        }
        finally {
            setUploading(false);
        }
    }, [fetchFiles, webApp]);
    const handleDeleteTask = async (taskId) => {
        if (!(await confirmAction("Отменить задачу?")))
            return;
        await api.delete(`/tasks/${taskId}`);
        await fetchTasks();
    };
    const handleDeleteFile = async (fileId) => {
        if (!(await confirmAction("Удалить файл?")))
            return;
        await api.delete(`/files/${fileId}`);
        await fetchFiles();
    };
    const renderTasks = () => (_jsxs("div", { className: "grid", children: [_jsxs("div", { className: "card", children: [_jsx("h3", { children: "\u041D\u043E\u0432\u0430\u044F \u0437\u0430\u0434\u0430\u0447\u0430" }), _jsx("input", { placeholder: "\u041D\u0430\u0437\u0432\u0430\u043D\u0438\u0435 \u0438\u043B\u0438 SKU", value: parseForm.query, onChange: (e) => setParseForm({ ...parseForm, query: e.target.value }) }), _jsx("label", { children: "\u041C\u0430\u0440\u043A\u0435\u0442\u043F\u043B\u0435\u0439\u0441\u044B" }), _jsx("div", { className: "grid two", children: marketplacesOptions.map((site) => (_jsx("button", { className: clsx("chip", parseForm.marketplaces.includes(site) && "chip--active"), onClick: () => setParseForm((prev) => {
                                const exists = prev.marketplaces.includes(site);
                                const next = exists
                                    ? prev.marketplaces.filter((s) => s !== site)
                                    : [...prev.marketplaces, site];
                                return { ...prev, marketplaces: next };
                            }), children: site }, site))) }), _jsx("label", { children: "\u041C\u0430\u043A\u0441\u0438\u043C\u0443\u043C \u0442\u043E\u0432\u0430\u0440\u043E\u0432" }), _jsx("input", { type: "number", value: parseForm.max_products, min: 10, max: 1000, onChange: (e) => setParseForm({ ...parseForm, max_products: Number(e.target.value) }) }), _jsx("button", { disabled: taskLoading, onClick: () => void handleCreateTask(), children: taskLoading ? "Запуск..." : "Запустить парсинг" })] }), _jsx("div", { className: "grid", children: tasks.map((task) => {
                    const progress = progressMap[task.id];
                    const pct = progress?.progress ?? task.progress_percentage;
                    return (_jsxs("div", { className: "card", children: [_jsxs("div", { className: "task-head", children: [_jsx("span", { children: task.task_type }), _jsx("span", { className: `status status--${task.status}`, children: task.status })] }), _jsx("div", { className: "progress", children: _jsx("div", { className: "progress-bar", style: { width: `${pct}%` } }) }), _jsxs("small", { children: ["\u0421\u043E\u0437\u0434\u0430\u043D\u0430: ", dayjs(task.created_at).format("DD.MM HH:mm")] }), task.error_message && (_jsxs("p", { className: "error", children: ["\u041E\u0448\u0438\u0431\u043A\u0430: ", task.error_message] })), _jsxs("div", { className: "task-actions", children: [_jsx("button", { onClick: () => handleDeleteTask(task.id), children: "\u041E\u0442\u043C\u0435\u043D\u0438\u0442\u044C" }), _jsx("button", { onClick: () => api.post(`/tasks/${task.id}/restart`).then(fetchTasks), disabled: task.status !== "failed", children: "\u041F\u0435\u0440\u0435\u0437\u0430\u043F\u0443\u0441\u0442\u0438\u0442\u044C" })] })] }, task.id));
                }) })] }));
    const renderFiles = () => (_jsxs("div", { className: "grid", children: [_jsxs("div", { className: "card", children: [_jsx("h3", { children: "\u0417\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044C \u0444\u0430\u0439\u043B" }), _jsx("input", { type: "file", accept: ".xml,.xlsx,.mxl", onChange: (e) => void handleUpload(e.target.files?.[0] || undefined), disabled: uploading }), uploading && _jsx("small", { children: "\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430..." })] }), files.map((file) => (_jsxs("div", { className: "card", children: [_jsx("strong", { children: file.filename }), _jsx("p", { children: formatBytes(file.file_size) }), _jsxs("small", { children: ["\u0414\u0430\u0442\u0430: ", dayjs(file.upload_date).format("DD.MM HH:mm")] }), _jsxs("div", { className: "task-actions", children: [_jsx("button", { onClick: async () => {
                                    const { data } = await api.get(`/files/${file.id}/download`);
                                    window.open(data.url, "_blank");
                                }, children: "\u0421\u043A\u0430\u0447\u0430\u0442\u044C" }), _jsx("button", { onClick: () => void handleDeleteFile(file.id), children: "\u0423\u0434\u0430\u043B\u0438\u0442\u044C" })] })] }, file.id)))] }));
    const renderDashboard = () => (_jsxs("div", { className: "grid", children: [_jsxs("div", { className: "card", children: [_jsx("h2", { children: "\u0414\u043E\u0431\u0440\u043E \u043F\u043E\u0436\u0430\u043B\u043E\u0432\u0430\u0442\u044C \uD83D\uDC4B" }), _jsxs("p", { children: [user?.first_name || user?.username, ", \u0437\u0430\u043F\u0443\u0441\u043A\u0430\u0439\u0442\u0435 \u0437\u0430\u0434\u0430\u0447\u0438 \u043F\u0430\u0440\u0441\u0438\u043D\u0433\u0430 \u0438 \u043E\u0442\u0441\u043B\u0435\u0436\u0438\u0432\u0430\u0439\u0442\u0435 \u043F\u0440\u043E\u0433\u0440\u0435\u0441\u0441 \u0432 \u0440\u0435\u0430\u043B\u044C\u043D\u043E\u043C \u0432\u0440\u0435\u043C\u0435\u043D\u0438."] })] }), tasks.slice(0, 3).map((task) => (_jsxs("div", { className: "card", children: [_jsx("strong", { children: task.task_type }), _jsxs("p", { children: ["\u0421\u0442\u0430\u0442\u0443\u0441: ", task.status] }), _jsxs("p", { children: ["\u041F\u0440\u043E\u0433\u0440\u0435\u0441\u0441: ", task.progress_percentage, "%"] })] }, task.id)))] }));
    const renderAdmin = () => (_jsxs("div", { className: "grid", children: [stats && (_jsxs("div", { className: "grid two", children: [_jsxs("div", { className: "card", children: [_jsx("span", { children: "\u0410\u043A\u0442\u0438\u0432\u043D\u044B\u0435 \u043F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u0438" }), _jsx("strong", { children: stats.active_users })] }), _jsxs("div", { className: "card", children: [_jsx("span", { children: "\u0417\u0430\u0434\u0430\u0447 \u0432\u044B\u043F\u043E\u043B\u043D\u0435\u043D\u043E" }), _jsx("strong", { children: stats.completed_tasks })] }), _jsxs("div", { className: "card", children: [_jsx("span", { children: "\u0412\u0441\u0435\u0433\u043E \u0437\u0430\u0434\u0430\u0447" }), _jsx("strong", { children: stats.total_tasks })] }), _jsxs("div", { className: "card", children: [_jsx("span", { children: "\u0425\u0440\u0430\u043D\u0438\u043B\u0438\u0449\u0435" }), _jsxs("strong", { children: [stats.storage_usage_mb.toFixed(1), " MB"] })] })] })), _jsxs("div", { className: "card", children: [_jsx("h3", { children: "\u041F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u0438" }), userList.map((u) => (_jsxs("div", { className: "user-row", children: [_jsxs("span", { children: [u.username || u.first_name, " \u00B7 ", u.role] }), _jsx("button", { onClick: async () => {
                                    const nextRole = u.role === "ADMIN" ? "USER" : "ADMIN";
                                    if (!(await confirmAction(`Изменить роль пользователя на ${nextRole}?`))) {
                                        return;
                                    }
                                    await api.put(`/admin/users/${u.telegram_id}`, { role: nextRole });
                                    await fetchAdminData();
                                }, children: u.role === "ADMIN" ? "Назначить USER" : "Назначить ADMIN" })] }, u.telegram_id)))] }), _jsxs("div", { className: "card", children: [_jsx("h3", { children: "\u0417\u0430\u0434\u0430\u0447\u0438 \u0441\u0438\u0441\u0442\u0435\u043C\u044B" }), adminTasks.slice(0, 5).map((task) => (_jsxs("div", { className: "task-head", children: [_jsx("span", { children: task.task_type }), _jsx("span", { children: task.status })] }, task.id)))] }), _jsxs("div", { className: "card", children: [_jsx("h3", { children: "\u041B\u043E\u0433\u0438" }), systemLogs.map((log) => (_jsxs("div", { className: "log-row", children: [_jsxs("span", { children: ["[", log.level, "] ", log.message] }), _jsx("small", { children: dayjs(log.created_at).format("DD.MM HH:mm") })] }, log.id)))] }), _jsxs("div", { className: "card", children: [_jsx("h3", { children: "\u0414\u0438\u043D\u0430\u043C\u0438\u043A\u0430 \u043F\u043E\u043B\u044C\u0437\u043E\u0432\u0430\u0442\u0435\u043B\u0435\u0439" }), userStats.slice(-7).map((point) => (_jsxs("div", { className: "task-head", children: [_jsx("span", { children: dayjs(point.date).format("DD.MM") }), _jsxs("small", { children: ["+", point.new_users, " / \u0430\u043A\u0442\u0438\u0432\u043D\u044B\u0445 ", point.active_users] })] }, point.date)))] })] }));
    if (loading) {
        return (_jsx("div", { className: "card", style: { margin: 16 }, children: "\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430..." }));
    }
    if (error) {
        return (_jsxs("div", { className: "card", style: { margin: 16 }, children: [_jsx("h3", { children: "\u041E\u0448\u0438\u0431\u043A\u0430" }), _jsx("p", { children: error })] }));
    }
    const tabs = [
        { id: "dashboard", label: "Главная" },
        { id: "tasks", label: "Задачи" },
        { id: "files", label: "Файлы" },
    ];
    if (user?.role === "ADMIN") {
        tabs.push({ id: "admin", label: "Админ" });
    }
    return (_jsxs("div", { className: clsx("app", colorScheme), children: [_jsxs("header", { className: "card", style: { margin: 16 }, children: [_jsxs("div", { children: [_jsx("h2", { children: "Parser BestMoto" }), _jsx("p", { children: user?.username || user?.first_name })] }), _jsxs("small", { children: ["\u0421\u0442\u0430\u0442\u0443\u0441: ", user?.role] })] }), _jsx("nav", { className: "tab-bar", children: tabs.map((tab) => (_jsx("button", { className: clsx("tab", activeTab === tab.id && "tab--active"), onClick: () => setActiveTab(tab.id), children: tab.label }, tab.id))) }), _jsxs("main", { style: { padding: 16 }, children: [activeTab === "dashboard" && renderDashboard(), activeTab === "tasks" && renderTasks(), activeTab === "files" && renderFiles(), activeTab === "admin" && user?.role === "ADMIN" && renderAdmin()] })] }));
};
export default App;
