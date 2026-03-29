const PREFIX = 'basao_'

export const storage = {
  get<T>(key: string, fallback: T | null = null): T | null {
    try {
      const raw = localStorage.getItem(PREFIX + key)
      return raw ? JSON.parse(raw) : fallback
    } catch {
      return fallback
    }
  },

  set(key: string, value: unknown): void {
    localStorage.setItem(PREFIX + key, JSON.stringify(value))
  },

  remove(key: string): void {
    localStorage.removeItem(PREFIX + key)
  },

  getString(key: string, fallback = ''): string {
    return localStorage.getItem(PREFIX + key) ?? fallback
  },

  setString(key: string, value: string): void {
    localStorage.setItem(PREFIX + key, value)
  },
}
