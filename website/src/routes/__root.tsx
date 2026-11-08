import {
  HeadContent,
  Link,
  Scripts,
  createRootRoute,
} from '@tanstack/react-router'
import { TanStackRouterDevtoolsPanel } from '@tanstack/react-router-devtools'
import { TanStackDevtools } from '@tanstack/react-devtools'

// The unminified file: the minified one has an unquoted font @import URL that Vite cannot parse.
import themeCss from 'bootswatch/dist/simplex/bootstrap.css?url'
import appCss from '../styles.css?url'

export const Route = createRootRoute({
  head: () => ({
    meta: [
      {
        charSet: 'utf-8',
      },
      {
        name: 'viewport',
        content: 'width=device-width, initial-scale=1',
      },
      {
        title: 'esbirka',
      },
    ],
    links: [
      {
        rel: 'stylesheet',
        href: themeCss,
      },
      {
        rel: 'stylesheet',
        href: appCss,
      },
    ],
  }),
  shellComponent: RootDocument,
})

function Navbar() {
  return (
    <nav className="navbar navbar-expand bg-dark" data-bs-theme="dark">
      <div className="container-fluid">
        <Link to="/" className="navbar-brand">
          esbirka
        </Link>
        <ul className="navbar-nav me-auto">
          <li className="nav-item">
            <Link
              to="/"
              className="nav-link"
              activeOptions={{ exact: true }}
              activeProps={{ className: 'active' }}
            >
              Home
            </Link>
          </li>
        </ul>
      </div>
    </nav>
  )
}

function RootDocument({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body>
        <Navbar />
        {children}
        <TanStackDevtools
          config={{
            position: 'bottom-right',
          }}
          plugins={[
            {
              name: 'Tanstack Router',
              render: <TanStackRouterDevtoolsPanel />,
            },
          ]}
        />
        <Scripts />
      </body>
    </html>
  )
}
