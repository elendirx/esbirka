import { createFileRoute, Link } from '@tanstack/react-router'
import { listLaws } from '../server/zakony'

export const Route = createFileRoute('/')({
  loader: () => listLaws(),
  component: Home,
})

function Home() {
  const laws = Route.useLoaderData()
  return (
    <div className="container py-5">
      <h1 className="fw-bold">Zákony</h1>
      <div className="list-group mt-4">
        {laws.map((law) => (
          <Link
            key={`${law.rok}/${law.cislo}`}
            to="/zakon/$rok/$cislo"
            params={{ rok: law.rok, cislo: law.cislo }}
            className="list-group-item list-group-item-action"
          >
            {law.nazev}
          </Link>
        ))}
      </div>
    </div>
  )
}
