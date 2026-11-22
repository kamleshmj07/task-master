import { useCallback, useEffect, useState } from 'react'

/** Load data on mount and on demand; screens call `reload` after changes. */
export function useResource<T>(load: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    try {
      setData(await load())
      setError(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not load data')
    }
  }, [load])

  useEffect(() => {
    void reload()
  }, [reload])

  return { data, error, reload }
}
