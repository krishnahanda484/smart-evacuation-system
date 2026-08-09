import { createRoot } from 'react-dom/client';
import { setBaseUrl } from '@workspace/api-client-react';

import App from './App';

if (import.meta.env.VITE_API_URL) {
  setBaseUrl(import.meta.env.VITE_API_URL);
} else if (import.meta.env.DEV) {
  // Default to localhost:8080 for local development if not specified
  setBaseUrl('http://localhost:8080');
}

import './index.css';

createRoot(document.getElementById('root')!).render(<App />);
