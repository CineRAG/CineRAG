import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendTarget = env.VITE_BACKEND_PROXY_TARGET || 'http://127.0.0.1:8000'
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
    base: './',
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
