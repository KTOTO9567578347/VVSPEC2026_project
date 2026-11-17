import { useEffect, useRef, useState } from 'react';
import { preferencesRepository } from '../../db/preferencesRepository';
import { ru } from '../lib/ru';
export function usePreference(key: string, fallback: string) {
  const [value, setValue] = useState(fallback);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const touched = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    let active = true;
    void preferencesRepository
      .get(key)
      .then((stored) => {
        if (active && !touched.current && stored !== undefined) setValue(stored);
      })
      .catch(() => {
        if (active) setError(ru.storageError);
      })
      .finally(() => {
        if (active) setReady(true);
      });
    return () => {
      active = false;
      mounted.current = false;
    };
  }, [key]);
  const update = (next: string) => {
    touched.current = true;
    setValue(next);
    void preferencesRepository.set(key, next).catch(() => {
      if (mounted.current) setError(ru.storageError);
    });
  };
  return { value, setValue: update, ready, error };
}
