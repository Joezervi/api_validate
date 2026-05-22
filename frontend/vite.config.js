import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
	plugins: [react()],
	server: {
		host: true,
		port: 5100,
		proxy: {
			'/extract-po':   'http://backend:9000',
			'/extract-file': 'http://backend:9000',
			'/verify-po':    'http://backend:9000',
			'/upload-po':  'http://backend:9000',
			'/download':   'http://backend:9000',
			'/cleanup':    'http://backend:9000',
			'/health':     'http://backend:9000',
		},
	},
});
