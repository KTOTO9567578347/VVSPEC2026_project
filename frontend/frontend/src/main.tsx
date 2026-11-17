import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './app/App';
import { Providers } from './app/providers';
import { configError } from './config/env';
import { ru } from './shared/lib/ru';
import './styles.css';
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {configError ? (
      <main className="fatal">
        <h1>{ru.config}</h1>
        <p role="alert">{configError}</p>
      </main>
    ) : (
      <Providers>
        <App />
      </Providers>
    )}
  </StrictMode>,
);
