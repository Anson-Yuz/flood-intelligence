# Security Policy

## Public showcase boundary

The GitHub Pages build is a static, read-only showcase. It does not connect to
the FastAPI backend, database, edge adapters, cameras, LiDAR devices, or field
control equipment. Actions shown in the interface are browser-local simulations.

Do not deploy the development account or password to a public backend. A real
deployment must replace all development credentials, enable HTTPS and Secure
cookies, restrict CORS, add device authentication, and independently review
every write or control endpoint.

## Reporting

Please report suspected credential exposure or security issues privately to the
repository owner through GitHub rather than opening a public issue containing
sensitive details.
