export function time(ms: number | null | undefined): string {
  return ms == null
    ? '—'
    : new Intl.DateTimeFormat('ru-RU', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      }).format(ms);
}
export function dateTime(ms: number | null | undefined): string {
  return ms == null
    ? '—'
    : new Intl.DateTimeFormat('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      }).format(ms);
}
