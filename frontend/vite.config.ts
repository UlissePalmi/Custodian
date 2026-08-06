import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Vite serves plain HTTP: TLS is terminated upstream by `tailscale serve`,
// which proxies https://<pi>.ts.net/ here and /api to the backend. See
// backend/deploy/DEPLOY.md.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Reachable over LAN / Tailscale.
    host: true,
    // Vite rejects requests whose Host header it does not recognise; the app is
    // opened by IP, by Tailscale name and through the serve proxy, so accept
    // whatever it is reached as.
    allowedHosts: true,
  },
})
