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

/** The address as it stands, for code that is not a component.
 *
 * `renderProse` is a plain function called from a dozen places, and a
 * bare `g<id>` mention needs to know which task the reader is standing
 * on. The hash IS that answer, and reading it here keeps one parser. */
export function currentSegments(): string[] {
  return parseHash().segments
}

export function navigate(path: string) {
  window.location.hash = '#' + (path.startsWith('/') ? path : '/' + path)
}

/** The same address change, without a stop on the back button.
 *
 * `navigate` is for a MOVE — the reader asked to be somewhere else, and
 * Back should undo it. This is for an address that is merely keeping up
 * with what is already on screen: the star the Sky has open lives in
 * the hash so a reload or a mailed link shows it, but clicking around a
 * constellation must not fill the history with one entry per star and
 * make Back a slow rewind of the reader's own browsing. Back has to
 * leave the section, the way it did before the address learned to say
 * which star is open.
 *
 * `location.replace` on a hash-only URL still fires `hashchange`, so
 * `useRoute` follows it exactly as it follows `navigate`. */
export function replace(path: string) {
  window.location.replace('#' + (path.startsWith('/') ? path : '/' + path))
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
