export function number(value: number | null | undefined, digits = 2): string {
  return value == null || !Number.isFinite(value)
    ? '—'
    : new Intl.NumberFormat('ru-RU', { maximumFractionDigits: digits }).format(value);
}
export function percent(value: number | null | undefined): string {
  return value == null ? '—' : number(value * 100, 1) + ' %';
}
