
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
	plugins: [react()],
	server: {
		host: true,
		port: 5100,
		proxy: {
			'/upload-po': 'http://backend:9000',
			'/task': 'http://backend:9000',
			'/download': 'http://backend:9000',
		},
	},
});
