import { createFileRoute } from '@tanstack/react-router'
import { LawText } from '../components/LawText'
import { getLaw } from '../server/zakony'

export const Route = createFileRoute('/zakon/$rok/$cislo')({
  loader: ({ params }) => getLaw({ data: params }),
  head: ({ loaderData }) => ({
    meta: [{ title: loaderData ? `${loaderData.nazev} – esbirka` : 'esbirka' }],
  }),
  component: LawDetail,
  notFoundComponent: () => (
    <div className="container py-5">
      <h1 className="fw-bold">Zákon nenalezen</h1>
    </div>
  ),
})

function LawDetail() {
  const law = Route.useLoaderData()
  return (
    <div className="container py-5">
      <h1 className="h3 fw-bold">{law.nazev}</h1>
      {law.text === null ? (
        <div className="alert alert-warning mt-4">
          Tento předpis zatím v repozitáři nemáme. Jeho text najdete v{' '}
          <a
            className="alert-link"
            href={`https://e-sbirka.gov.cz/sb/${law.rok}/${law.cislo}`}
          >
            e-Sbírce
          </a>
          .
        </div>
      ) : (
        <div className="mt-4">
          <LawText text={law.text} />
        </div>
      )}
    </div>
  )
}
