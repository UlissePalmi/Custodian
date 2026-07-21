import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Reachable over LAN / Tailscale.
    host: true,
    // Vite rejects requests whose Host header it does not recognise; the app is
    // opened by IP and by Tailscale name, so accept whatever it is reached as.
    allowedHosts: true,
  },
})
