import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendTarget = env.VITE_BACKEND_PROXY_TARGET || 'http://127.0.0.1:8000'
  // Nuvolos serves the dev server behind a path-prefixed HTTPS proxy
  // (e.g. /proxy/5173/). Vite ignores `base: './'` in dev and injects
  // /@vite/client and /@react-refresh as absolute paths that the proxy
  // cannot route. Setting VITE_BASE_PATH=/proxy/5173/ makes Vite emit
  // those injected scripts with the proxy prefix already applied.
  const basePath = env.VITE_BASE_PATH || './'
  // On Nuvolos the dev server is reached through an HTTPS proxy at port
  // 443; Vite's default HMR WebSocket points at the dev port directly,
  // which fails. Setting these two env vars makes the HMR client connect
  // back through the public proxy.
  const hmr = env.VITE_HMR_PORT
    ? {
        clientPort: parseInt(env.VITE_HMR_PORT, 10),
        protocol: env.VITE_HMR_PROTOCOL || 'wss',
      }
    : undefined
  return {
    base: basePath,
    plugins: [react(), tailwindcss()],
    server: {
      allowedHosts: true,
      ...(hmr ? { hmr } : {}),
      proxy: {
        '/api': {
          target: backendTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
