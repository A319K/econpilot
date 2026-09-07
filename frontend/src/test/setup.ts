import "@testing-library/jest-dom/vitest"

// Node 22+'s experimental built-in `localStorage` global shadows jsdom's
// proper Storage implementation (its prototype ends up as bare
// Object.prototype, missing getItem/setItem/clear). Replace it with a real
// in-memory Storage-like polyfill so tests can rely on standard behavior.
class MemoryStorage implements Storage {
  private store = new Map<string, string>()

  get length(): number {
    return this.store.size
  }

  clear(): void {
    this.store.clear()
  }

  getItem(key: string): string | null {
    return this.store.has(key) ? this.store.get(key)! : null
  }

  key(index: number): string | null {
    return Array.from(this.store.keys())[index] ?? null
  }

  removeItem(key: string): void {
    this.store.delete(key)
  }

  setItem(key: string, value: string): void {
    this.store.set(key, String(value))
  }
}

const memoryStorage = new MemoryStorage()
Object.defineProperty(window, "localStorage", { value: memoryStorage, configurable: true })
Object.defineProperty(globalThis, "localStorage", { value: memoryStorage, configurable: true })
