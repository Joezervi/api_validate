import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// ── Backend URL ─────────────────────────────────────────────────────
// Docker dev:    Vite proxy below handles /api/v1/* → backend:9000
// Vercel prod:   Set VITE_API_BASE_URL at build time:
//                VITE_API_BASE_URL=https://api.example.vercel.app npm run build
// Local dev:     VITE_API_BASE_URL=http://localhost:8000 npm run dev
//
// The proxy below is only active in dev mode (npm run dev).

const BACKEND = process.env.VITE_API_BASE_URL || 'http://localhost:8000'

export default defineConfig({
	plugins: [react()],
	server: {
		host: true,
		port: 5100,
		proxy: {
			'/api/v1': {
				target: BACKEND,
				changeOrigin: true,
			},
		},
	},
});
