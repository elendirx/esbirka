import { readdir, readFile } from 'node:fs/promises'
import path from 'node:path'
import { createServerFn } from '@tanstack/react-start'
import { notFound } from '@tanstack/react-router'

// Laws are read from the repository on every request, so a newly added file
// shows up after a page refresh. ZAKONY_DIR overrides the default ../sb.
function lawsDir() {
  return process.env.ZAKONY_DIR ?? path.resolve(process.cwd(), '..', 'sb')
}

export type Law = {
  rok: string
  cislo: string
  nazev: string
}

const NUMBER = /^\d+$/

// Builds the name from the file header: number, kind, then either
// "ze dne …" followed by the title, or the author (a Constitutional Court ruling).
function lawName(rok: string, cislo: string, text: string) {
  const header = text.split('\n\n', 1)[0].split('\n')
  const kind = header[1] ?? ''
  const kindName = kind.charAt(0) + kind.slice(1).toLowerCase()
  const code = `č. ${cislo}/${rok} Sb.`
  const third = header[2] ?? ''
  if (third.startsWith('ze dne')) {
    const title = header[3]
    return title && !title.endsWith(':')
      ? `${kindName} ${code}, ${title}`
      : `${kindName} ${code}`
  }
  return `${kindName} ${third} ${code}`.replace(/\s+/g, ' ')
}

export const listLaws = createServerFn({ method: 'GET' }).handler(
  async (): Promise<Law[]> => {
    const dir = lawsDir()
    const laws: Law[] = []
    for (const rok of await readdir(dir)) {
      if (!NUMBER.test(rok)) continue
      for (const file of await readdir(path.join(dir, rok))) {
        const cislo = file.replace(/\.txt$/, '')
        if (cislo === file || !NUMBER.test(cislo)) continue
        const text = await readFile(path.join(dir, rok, file), 'utf8')
        laws.push({ rok, cislo, nazev: lawName(rok, cislo, text) })
      }
    }
    return laws.sort(
      (a, b) => Number(a.rok) - Number(b.rok) || Number(a.cislo) - Number(b.cislo),
    )
  },
)

export const getLaw = createServerFn({ method: 'GET' })
  .validator((data: { rok: string; cislo: string }) => {
    // Only digits, so the parameters cannot point outside the laws directory.
    if (!NUMBER.test(data.rok) || !NUMBER.test(data.cislo)) throw notFound()
    return data
  })
  .handler(async ({ data }) => {
    const file = path.join(lawsDir(), data.rok, `${data.cislo}.txt`)
    let text: string
    try {
      text = await readFile(file, 'utf8')
    } catch {
      throw notFound()
    }
    return { ...data, nazev: lawName(data.rok, data.cislo, text), text }
  })
