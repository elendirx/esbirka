type Cell = string | null
type Row = Cell[] | Record<string, Cell>

type Segment =
  | { kind: 'text'; line: number; text: string }
  | { kind: 'table'; line: number; depth: number; rows: Row[] }

// A table is stored as a JSON array starting with a line "[" and ending with
// "]" at the same indentation. Anything that does not parse stays as text.
function segments(text: string): Segment[] {
  const lines = text.split('\n')
  const result: Segment[] = []
  let buffer: string[] = []
  let bufferStart = 0
  const flush = () => {
    if (buffer.length)
      result.push({ kind: 'text', line: bufferStart, text: buffer.join('\n') })
    buffer = []
  }
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    if (line.trim() === '[') {
      const indent = line.slice(0, line.length - line.trimStart().length)
      const end = lines.findIndex((l, j) => j > i && l === `${indent}]`)
      if (end > i) {
        try {
          const rows = JSON.parse(lines.slice(i, end + 1).join('\n'))
          if (Array.isArray(rows)) {
            flush()
            result.push({ kind: 'table', line: i, depth: indent.length, rows })
            i = end
            continue
          }
        } catch {
          // Not JSON, keep the lines as text.
        }
      }
    }
    if (!buffer.length) bufferStart = i
    buffer.push(line)
  }
  flush()
  return result
}

// null marks a cell covered by the merged cell above it.
function LawTable({ rows }: { rows: Row[] }) {
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
    <table className="table table-sm table-bordered align-top my-2">
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
                  {cell}
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
// continuations stay at the line's level instead of the left edge.
function LawLines({ start, text }: { start: number; text: string }) {
  return (
    <div className="zakon-radky">
      {text.split('\n').map((line, i) => {
        const content = line.replace(/^\t+/, '')
        const depth = line.length - content.length
        return (
          // biome-ignore lint/suspicious/noArrayIndexKey: the line number is the line's identity
          <div key={start + i} style={{ paddingLeft: `${depth * 4}ch` }}>
            {content}
          </div>
        )
      })}
    </div>
  )
}

export function LawText({ text }: { text: string }) {
  return (
    <div className="zakon-text">
      {segments(text).map((segment) =>
        segment.kind === 'text' ? (
          <LawLines key={segment.line} start={segment.line} text={segment.text} />
        ) : (
          <div
            key={segment.line}
            className="zakon-tabulka"
            style={{ marginLeft: `${segment.depth * 4}ch` }}
          >
            <LawTable rows={segment.rows} />
          </div>
        ),
      )}
    </div>
  )
}
