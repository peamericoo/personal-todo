FROM rust:1-slim-bookworm AS build
WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release --locked
FROM debian:bookworm-slim
COPY --from=build /app/target/release/personal-todo /usr/local/bin/personal-todo
ENV DATABASE_PATH=/data/todo.sqlite3
CMD ["personal-todo"]
