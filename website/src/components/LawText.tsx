import { Link } from '@tanstack/react-router'
import type { ReactNode } from 'react'

type Cell = string | null
type Row = Cell[] | Record<string, Cell>

// A reference to a law in the Collection, e.g. "106/1999 Sb." in "zákon č.
// 106/1999 Sb."; the "č." stays outside the link. "Sb. m. s." is the separate
// Collection of treaties. Or a footnote reference such as "[16]".
const REFERENCE = /(\d+)\/(\d{4}) Sb\.(?! ?m\. ?s\.)|\[(\w+)\]/g

// Footnote references link only to footnotes this law actually has; the set is
// missing inside cited text, whose footnotes belong to the cited law.
function withLinks(text: string, footnotes?: Set<string>): ReactNode {
  const parts: ReactNode[] = []
  let last = 0
  for (const match of text.matchAll(REFERENCE)) {
    const [whole, cislo, rok, footnote] = match
    if (footnote !== undefined && !footnotes?.has(footnote)) continue
    const start = match.index
    parts.push(text.slice(last, start))
    parts.push(
      footnote !== undefined ? (
        <a key={start} href={`#pozn-${footnote}`}>
          {whole}
        </a>
      ) : (
        <Link key={start} to="/zakon/$rok/$cislo" params={{ rok, cislo }}>
          {whole}
        </Link>
      ),
    )
    last = start + whole.length
  }
  if (!parts.length) return text
  parts.push(text.slice(last))
  return parts
}

type Item =
  | { kind: 'line'; line: number; depth: number; content: string }
  | { kind: 'table'; line: number; depth: number; rows: Row[] }

type Node =
  | Item
  | { kind: 'citation'; line: number; depth: number; items: Item[] }

// Splits the text into lines and tables. A table is stored as a JSON array
// starting with a line "[" and ending with "]" at the same indentation.
// Anything that does not parse stays as text.
function items(text: string): Item[] {
  const lines = text.split('\n')
  const result: Item[] = []
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const content = line.replace(/^\t+/, '')
    const depth = line.length - content.length
    if (content === '[') {
      const end = lines.findIndex(
        (l, j) => j > i && l === `${'\t'.repeat(depth)}]`,
      )
      if (end > i) {
        try {
          const rows = JSON.parse(lines.slice(i, end + 1).join('\n'))
          if (Array.isArray(rows)) {
            result.push({ kind: 'table', line: i, depth, rows })
            i = end
            continue
          }
        } catch {
          // Not JSON, keep the lines as text.
        }
      }
    }
    result.push({ kind: 'line', line: i, depth, content })
  }
  return result
}

// A citation starts with „ at the beginning of a line and ends with “ at the end
// of a line, usually followed by the full stop of the amending sentence.
const OPEN = '„'
const CLOSE = /“[.,;:]*$/

function stringCells(rows: Row[]) {
  const cells: { row: number; key: string | number; value: string }[] = []
  rows.forEach((row, r) => {
    for (const [key, value] of Object.entries(row)) {
      if (typeof value === 'string')
        cells.push({ row: r, key: Array.isArray(row) ? Number(key) : key, value })
    }
  })
  return cells
}

function edgeText(item: Item, edge: 'first' | 'last') {
  if (item.kind === 'line') return item.content
  const cells = stringCells(item.rows)
  return (edge === 'first' ? cells[0] : cells.at(-1))?.value ?? ''
}

function editEdge(item: Item, edge: 'first' | 'last', edit: (s: string) => string): Item {
  if (item.kind === 'line') return { ...item, content: edit(item.content) }
  const cells = stringCells(item.rows)
  const target = edge === 'first' ? cells[0] : cells.at(-1)
  if (!target) return item
  const rows = item.rows.map((row, r) => {
    if (r !== target.row) return row
    const copy: Row = Array.isArray(row) ? [...row] : { ...row }
    ;(copy as Record<string | number, Cell>)[target.key] = edit(target.value)
    return copy
  })
  return { ...item, rows }
}

// Groups cited items into citations and drops their enclosing quotes. A citation
// that never closes, or whose lines fall below its starting level, stays text.
function citations(list: Item[]): Node[] {
  const result: Node[] = []
  for (let i = 0; i < list.length; i++) {
    const start = list[i]
    if (!edgeText(start, 'first').startsWith(OPEN)) {
      result.push(start)
      continue
    }
    let end = -1
    for (let j = i; j < list.length; j++) {
      const item = list[j]
      const blank = item.kind === 'line' && item.content === ''
      if (j > i && !blank && item.depth < start.depth) break
      const text = edgeText(item, 'last')
      if (CLOSE.test(text) && (j > i || text.length > 1)) {
        end = j
        break
      }
    }
    if (end < 0) {
      result.push(start)
      continue
    }
    const cited = list.slice(i, end + 1)
    cited[0] = editEdge(cited[0], 'first', (s) => s.slice(OPEN.length))
    cited[cited.length - 1] = editEdge(cited[cited.length - 1], 'last', (s) =>
      s.replace(CLOSE, ''),
    )
    // Lines that held only a quote, like the ones around a cited table, go away.
    const kept = cited.filter(
      (item, k) =>
        !(item.kind === 'line' && item.content === '' && (k === 0 || k === cited.length - 1)),
    )
    result.push({ kind: 'citation', line: start.line, depth: start.depth, items: kept })
    i = end
  }
  return result
}

// null marks a cell covered by the merged cell above it.
function LawTable({
  rows,
  footnotes,
}: {
  rows: Row[]
  footnotes?: Set<string>
}) {
  const header =
    rows.length > 0 && !Array.isArray(rows[0]) ? Object.keys(rows[0]) : null
  const grid: Cell[][] = rows.map((row) =>
    Array.isArray(row) ? row : (header ?? []).map((key) => row[key] ?? null),
  )
  const span = (r: number, c: number) => {
    let n = 1
    while (r + n < grid.length && grid[r + n][c] === null) n++
    return n
  }
  return (
    <table className="table table-sm table-bordered align-top my-2 w-auto text-wrap">
      {header && (
        <thead>
          <tr>
            {header.map((name) => (
              <th key={name}>{name}</th>
            ))}
          </tr>
        </thead>
      )}
      <tbody>
        {grid.map((cells, r) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: static rows, never reordered
          <tr key={r}>
            {cells.map((cell, c) =>
              cell === null && r > 0 ? null : (
                // biome-ignore lint/suspicious/noArrayIndexKey: static cells, never reordered
                <td key={c} rowSpan={span(r, c)}>
                  {cell && withLinks(cell, footnotes)}
                </td>
              ),
            )}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// Each line is its own block indented by its leading tabs, so wrapped
// continuations stay at the line's level instead of the left edge. Depth is
// relative to the enclosing citation, whose bar sits at the citation's level.
// Top-level lines that get an anchor: parts and their subdivisions ("ČÁST
// DRUHÁ", "HLAVA II", "Díl 3"), paragraphs and articles ("§ 5a", "Čl. IV"),
// annexes, and footnotes ("[12]"). The label becomes a link to its own anchor.
const UPPER = 'A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ'
const SECTION = new RegExp(
  `^((?:ČÁST|HLAVA|DÍL|ODDÍL|PODODDÍL)(?: [${UPPER}0-9]+(?=\\s|$))+|(?:Díl|Oddíl|Pododdíl) \\d+|§ \\d+[a-z]*|Čl\\. (?:[IVXLCDM]+|\\d+)[a-z]*|Příloha(?: č\\. \\d+)?)`,
)
const FOOTNOTE = /^\[(\w+)\]/

function anchor(content: string) {
  const footnote = content.match(FOOTNOTE)
  if (footnote) return { id: `pozn-${footnote[1]}`, label: footnote[0] }
  const section = content.match(SECTION)
  if (!section) return null
  const id = section[1]
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .replace('§', 'par')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
  return { id, label: section[1] }
}

function LawNodes({
  nodes,
  base,
  footnotes,
}: {
  nodes: Node[]
  base: number
  footnotes?: Set<string>
}) {
  // Anchors and footnote links only for the law's own text, not cited text.
  const anchors = footnotes !== undefined
  return nodes.map((node) => {
    const indent = `${Math.max(node.depth - base, 0) * 4}ch`
    if (node.kind === 'line') {
      // Only the law's own top-level lines, not text cited by an amendment.
      const target = anchors && node.depth === 0 ? anchor(node.content) : null
      return (
        <div
          key={node.line}
          id={target?.id}
          className="zakon-radek"
          style={{ paddingLeft: indent }}
        >
          {target ? (
            <>
              <a
                href={`#${target.id}`}
                className="link-body-emphasis link-underline-opacity-0 link-underline-opacity-100-hover"
              >
                {target.label}
              </a>
              {withLinks(node.content.slice(target.label.length), footnotes)}
            </>
          ) : (
            withLinks(node.content, footnotes)
          )}
        </div>
      )
    }
    if (node.kind === 'table')
      return (
        <div key={node.line} className="zakon-tabulka" style={{ marginLeft: indent }}>
          <LawTable rows={node.rows} footnotes={footnotes} />
        </div>
      )
    return (
      <div
        key={node.line}
        className="border-start border-3 border-dark-subtle ps-2 my-1 text-body-secondary"
        style={{ marginLeft: indent }}
      >
        <LawNodes nodes={node.items} base={node.depth} />
      </div>
    )
  })
}

export function LawText({ text }: { text: string }) {
  const nodes = citations(items(text))
  const footnotes = new Set<string>()
  for (const node of nodes) {
    const footnote = node.kind === 'line' && node.depth === 0 && node.content.match(FOOTNOTE)
    if (footnote) footnotes.add(footnote[1])
  }
  return (
    <div className="zakon-text font-monospace small">
      <LawNodes nodes={nodes} base={0} footnotes={footnotes} />
    </div>
  )
}
