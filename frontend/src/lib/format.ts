import { formatDistanceToNow, format, isToday, isYesterday, isThisWeek } from 'date-fns'
import { vi } from 'date-fns/locale'

export function timeAgo(date: string | Date): string {
  return formatDistanceToNow(new Date(date), { addSuffix: true, locale: vi })
}

export function formatDate(date: string | Date): string {
  return format(new Date(date), 'dd/MM/yyyy HH:mm', { locale: vi })
}

export function groupDateLabel(date: string | Date): string {
  const d = new Date(date)
  if (isToday(d)) return 'Hôm nay'
  if (isYesterday(d)) return 'Hôm qua'
  if (isThisWeek(d)) return 'Tuần này'
  return format(d, 'dd/MM/yyyy', { locale: vi })
}

export function truncate(str: string, len: number): string {
  if (str.length <= len) return str
  return str.slice(0, len) + '...'
}

export function extractDomain(url: string): string {
  try {
    const m = url.match(/https?:\/\/(?:www\.)?([^/]+)/)
    if (m) return m[1].replace(/\.(com|vn|org|net|gov|edu).*$/, '').replace(/\./g, ' ')
  } catch { /* ignore */ }
  return url
}
