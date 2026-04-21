# Changelog

## Custom Traefik Error Pages

### Original behavior

The original reverse proxy setup only used Traefik and its built-in default error handling.

- Traefik terminated TLS and handled certificate issuance and renewal.
- Application routing came from Docker labels on the app containers.
- When an application backend became unavailable, users could end up seeing Traefik's default `404 page not found`.
- There was no dedicated custom error page service in the proxy stack.

### Final behavior

The proxy stack now includes a dedicated static error page service and Traefik is configured to keep empty Docker services addressable so custom error handling can apply.

- Added an `error-pages` nginx container in [docker-compose.yml](/Users/rien/Documents/Pycharm/reverse_project/docker-compose.yml:99).
- Added custom page assets in [error-pages/default.conf](/Users/rien/Documents/Pycharm/reverse_project/error-pages/default.conf:1) and [error-pages/404.html](/Users/rien/Documents/Pycharm/reverse_project/error-pages/404.html:1).
- Enabled `providers.docker.allowEmptyServices: true` in [traefik.yml](/Users/rien/Documents/Pycharm/reverse_project/traefik.yml:33).
- Applied a global Traefik error middleware on the HTTPS entrypoint in [traefik.yml](/Users/rien/Documents/Pycharm/reverse_project/traefik.yml:47).
- Added the `global-errors` middleware and `error-pages` backend service in [server/dynamic.yaml](/Users/rien/Documents/Pycharm/reverse_project/server/dynamic.yaml:9).

### Practical effect

- TLS, certificates, and existing application routers remain handled by Traefik.
- When a Docker-backed service becomes unavailable, Traefik should keep the route alive as an empty service instead of dropping immediately to its stock 404.
- That backend failure can then be rendered through the custom error page service.
- The custom HTML is served from the shared proxy stack rather than from the application containers.

### Notes

- The final approach replaced an earlier fallback-router attempt.
- The fallback-router version depended on per-application host rules and was not the right fit for the observed failure mode.
- The current design is based on Traefik keeping empty services available and handling the resulting upstream error with a custom error middleware.
