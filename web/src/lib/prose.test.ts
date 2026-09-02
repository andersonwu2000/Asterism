import { describe, expect, it } from 'vitest'
import type { ReactElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { renderProse } from './prose'

/*
 * The block engine's one law under test: a heading is a heading
 * because of what the LINE says, not because of what precedes it.
 *
 * The renderer splits on blank lines and matched the heading pattern
 * against a paragraph's first line only, so a `# Title` written flush
 * against `## Argument` rendered the second as literal text — three of
 * the 188 PROGRAMME.md bodies on disk are written that way, and every
 * one of them showed its first section heading as `## …`.
 */

const html = (src: string, mode: 'chat' | 'document' = 'document') =>
  renderToStaticMarkup(renderProse(src, { mode }) as ReactElement)

describe('renderProse headings', () => {
  it('makes a heading of every heading line, blank line or not', () => {
    const out = html('# The claim\n## Argument\nthe body of it.')
    expect(out).not.toContain('## Argument')
    expect(out).toContain('The claim')
    expect(out).toContain('Argument')
    // the title voice and the section voice, both real headings
    expect(out).toMatch(/<h3[^>]*>.*The claim/)
    expect(out).toMatch(/<h4[^>]*>.*Argument/)
    expect(out).toContain('the body of it.')
  })

  it('a heading flush under running prose still opens a section', () => {
    const out = html('a sentence of prose.\n## What remains\nand more.')
    expect(out).not.toContain('## What remains')
    expect(out).toMatch(/<h4[^>]*>.*What remains/)
    expect(out).toContain('a sentence of prose.')
    expect(out).toContain('and more.')
  })

  it('three headings in a row all land', () => {
    const out = html('# A\n## B\n### C\ntail')
    expect(out).not.toContain('## B')
    expect(out).not.toContain('### C')
    expect(out).toMatch(/<h3[^>]*>.*A</)
    expect(out).toMatch(/<h4[^>]*>.*B</)
    expect(out).toMatch(/<h5[^>]*>.*C</)
  })

  it('chat mode strips the marks from every heading line', () => {
    const out = html('# Title\n## Section\nbody', 'chat')
    expect(out).not.toContain('#')
    expect(out).toContain('Title')
    expect(out).toContain('Section')
  })

  it('blank-line separated headings are unchanged', () => {
    const out = html('# The claim\n\n## Argument\n\nthe body of it.')
    expect(out).toMatch(/<h3[^>]*>.*The claim/)
    expect(out).toMatch(/<h4[^>]*>.*Argument/)
    expect(out).toContain('the body of it.')
  })

  it('a hash inside a fence is code, not a heading', () => {
    const out = html('before\n\n```\n# not a heading\n```\n\nafter')
    expect(out).toContain('# not a heading')
    expect(out).not.toMatch(/<h[345][^>]*>.*not a heading/)
  })

  it('a rule and a table still read as their own shapes', () => {
    expect(html('---')).toContain('<hr')
    expect(html('| a | b |\n|---|---|\n| 1 | 2 |')).toContain('<table')
  })
})
