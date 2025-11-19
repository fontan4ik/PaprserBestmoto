import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig(function (_a) {
    var mode = _a.mode;
    var env = loadEnv(mode, process.cwd(), "");
    return {
        base: "/PaprserBestmoto/",
        plugins: [react()],
        define: {
            __APP_VERSION__: JSON.stringify(process.env.npm_package_version || "dev"),
        },
        server: {
            port: Number(env.VITE_DEV_PORT || 5173),
        },
        build: {
            outDir: "../docs",
            sourcemap: true,
        },
    };
});
