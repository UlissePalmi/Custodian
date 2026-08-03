import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import fs from 'node:fs'

export default defineConfig(({ mode }) => {
  // '' prefix (unlike import.meta.env's VITE_-only rule) also picks up
  // TAILSCALE_CERT_FILE/TAILSCALE_KEY_FILE from frontend/.env — set once
  // `tailscale cert` has produced a cert for the Pi's Tailscale hostname (see
  // DEPLOY.md's "Plaid bank sync" section). Plaid's OAuth handoff with Chase
  // requires an HTTPS redirect URI. Unset in local/mock dev, which keeps
  // plain HTTP.
  const env = loadEnv(mode, process.cwd(), '')
  const certFile = env.TAILSCALE_CERT_FILE
  const keyFile = env.TAILSCALE_KEY_FILE
  const https =
    certFile && keyFile ? { cert: fs.readFileSync(certFile), key: fs.readFileSync(keyFile) } : undefined

  return {
    plugins: [react(), tailwindcss()],
    server: {
      // Reachable over LAN / Tailscale.
      host: true,
      // Vite rejects requests whose Host header it does not recognise; the app
      // is opened by IP and by Tailscale name, so accept whatever it is
      // reached as.
      allowedHosts: true,
      https,
    },
  }
})
