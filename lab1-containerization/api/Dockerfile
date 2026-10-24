FROM golang:1.27.3-bookworm AS build

WORKDIR /app
COPY go.mod main.go ./
RUN CGO_ENABLED=0 go build -o api .

FROM scratch

WORKDIR /app
COPY --from=build /app/api ./api

EXPOSE 8080
CMD ["./api"]
