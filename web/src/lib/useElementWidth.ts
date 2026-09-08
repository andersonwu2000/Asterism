import { useCallback, useState } from 'react'

/** Measure the reading area, including space taken by neighbouring panels. */
export function useElementWidth<T extends HTMLElement>() {
  const [width, setWidth] = useState(0)
  const ref = useCallback((element: T | null) => {
    if (element === null) return
    setWidth(element.clientWidth)
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  return { ref, width }
}
