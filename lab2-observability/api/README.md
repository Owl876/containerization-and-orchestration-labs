# api — сервис для лабы по observability

Маленький FastAPI-сервис, специально созданный для провоцирования ситуаций
под наблюдение: метрики, логи, трейсы.

## Эндпоинты

- `GET /health` — возвращает `ok`.
- `GET /fail` — всегда отвечает 500, помечает текущий трейс-спан как ошибочный
  ("панда уронила бамбук"), инкрементит счётчик ошибок.
- `GET /slow` — спит случайные 1–3 секунды внутри отдельного спана `nap-time`,
  тратит энергию панды.
- `GET /load?n=&concurrency=&target=` — делает `n` запросов к `SELF_URL{target}`
  с ограничением параллелизма `concurrency`, чтобы спровоцировать всплеск RPS.
- `GET /metrics` — метрики в формате Prometheus.

## Метрики (RED)

- `http_requests_total{method,path,status}` — счётчик запросов.
- `http_errors_total{method,path}` — счётчик 5xx-ответов.
- `http_request_duration_seconds{method,path}` — гистограмма времени ответа.

Плюс два шуточных, но настоящих кастомных метрики:

- `panda_energy_level` — гейдж энергии панды (0–100), падает от `/slow` и
  `/load`, сама восстанавливается со временем.
- `panda_naps_total` — счётчик "сончасов" панды (вызовов `/slow`).

## Логи

Структурированные JSON-логи в stdout, каждая запись содержит `trace_id`
текущего спана (если есть активный трейс).

## Трейсинг

Инструментирован через OpenTelemetry (auto-instrumentation FastAPI + httpx).
Адрес OTLP-коллектора задаётся переменной окружения
`OTEL_EXPORTER_OTLP_ENDPOINT` (по умолчанию `http://otel-collector:4317`).

## Переменные окружения

| Переменная                    | По умолчанию                     | Назначение                                   |
|--------------------------------|-----------------------------------|-----------------------------------------------|
| `PORT`                         | `8000`                            | Порт, на котором слушает uvicorn              |
| `SELF_URL`                     | `http://127.0.0.1:{PORT}`         | Куда стучится `/load` (в кластере — DNS Service) |
| `OTEL_EXPORTER_OTLP_ENDPOINT`  | `http://otel-collector:4317`      | Куда экспортировать трейсы                    |

## Локальный запуск без Docker

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Сборка образа

```bash
docker build -t panda-api:local .
```
