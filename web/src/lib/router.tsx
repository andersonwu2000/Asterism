import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode, AnchorHTMLAttributes } from 'react'

/*
 * Minimal hash router. The charter freezes dependencies to
 * Vite/React/TS/Tailwind, so routing is hand-rolled: routes are hash
 * paths like "#/", "#/inbox", "#/problems/Logic.toy_tree_mirror".
 */

export interface Route {
  /** Path segments after "#/", already URL-decoded. */
  segments: string[]
  path: string
}

function parseHash(): Route {
  const raw = window.location.hash.replace(/^#\/?/, '')
  const segments = raw === '' ? [] : raw.split('/').map(decodeURIComponent)
  return { segments, path: '/' + raw }
}

const RouteContext = createContext<Route>({ segments: [], path: '/' })

export function RouterProvider({ children }: { children: ReactNode }) {
  const [route, setRoute] = useState<Route>(parseHash)
  useEffect(() => {
    const onChange = () => setRoute(parseHash())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return <RouteContext.Provider value={route}>{children}</RouteContext.Provider>
}

export function useRoute(): Route {
  return useContext(RouteContext)
}

export function navigate(path: string) {
  window.location.hash = '#' + (path.startsWith('/') ? path : '/' + path)
}

type LinkProps = { to: string } & Omit<AnchorHTMLAttributes<HTMLAnchorElement>, 'href'>

export function Link({ to, children, ...rest }: LinkProps) {
  const href = '#' + (to.startsWith('/') ? to : '/' + to)
  return (
    <a href={href} {...rest}>
      {children}
    </a>
  )
}
