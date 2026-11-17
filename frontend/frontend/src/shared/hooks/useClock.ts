import { useEffect, useState } from 'react';
import { settings } from '../../config/constants';
export function useClock() {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), settings.clockMs);
    return () => clearInterval(id);
  }, []);
  return now;
}
