import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/')({ component: Home })

function Home() {
  return (
    <div className="container py-5">
      <h1 className="fw-bold">Welcome to TanStack Start</h1>
      <p className="mt-4 lead">
        Edit <code>src/routes/index.tsx</code> to get started.
      </p>
    </div>
  )
}
