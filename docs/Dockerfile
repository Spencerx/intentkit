FROM gohugoio/hugo:0.155.3-ext-alpine AS builder

RUN apk add --no-cache git

WORKDIR /src

COPY . .
RUN hugo --minify

FROM caddy:2-alpine AS runner

WORKDIR /srv
COPY --from=builder /src/public /srv

EXPOSE 80
CMD ["caddy", "file-server", "--root", "/srv", "--listen", ":80"]
