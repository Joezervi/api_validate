
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
	plugins: [react()],
	server: {
		host: true,
		port: 5100,
		proxy: {
			'/upload-po': 'http://backend:8000',
			'/download': 'http://backend:8000',
		},
	},
});
