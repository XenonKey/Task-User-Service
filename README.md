# Task Marketplace

Учебный монорепозиторий из двух независимых FastAPI-сервисов (`user-service`,
`task-service`) с отдельными PostgreSQL, асинхронной интеграцией через Kafka
(outbox pattern), идемпотентной обработкой событий и optimistic concurrency
на claim задачи. Фронтенда нет — всё тестируется через Swagger UI каждого
сервиса.

## Архитектура

```
user-service          task-service           outbox-relay
   (user_db)              (task_db)          (читает task_db)
      ▲                       │  approve()          │
      │ балансы          пишет outbox в той же   читает outbox,
      │                  транзакции, что и        публикует в Kafka,
      │                  смену статуса            помечает published_at
      │                                                │
      └──────────── Kafka topic "task-events" ◄────────┘
        consumer: task.completed -> balance += reward
        (идемпотентно через processed_events)
```

- **user-service** — регистрация/логин, выпуск JWT (HS256, общий секрет
  `JWT_SECRET_KEY`), баланс пользователя, Kafka consumer, начисляющий баланс
  по событию `task.completed`.
- **task-service** — задачи и их жизненный цикл (`OPEN -> IN_PROGRESS -> DONE
  -> APPROVED/REJECTED`), локальная валидация JWT тем же общим секретом
  `JWT_SECRET_KEY` (без похода в user-service на каждый запрос), запись в
  outbox в той же транзакции, что и `approve`.
- **outbox-relay** — отдельный процесс, каждые N секунд читает неотправленные
  строки `outbox` из `task_db`, публикует их в Kafka (`key = task_id`, чтобы
  сохранить порядок по задаче) и помечает `published_at`. At-least-once
  доставка: consumer в user-service идемпотентен через таблицу
  `processed_events`.

## Технологии

Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async) + Alembic,
PostgreSQL 16 (два инстанса), Kafka через Redpanda, JWT HS256 (общий секрет),
Docker Compose, pytest + httpx.

Подробное объяснение того, как устроена аутентификация/авторизация в этом
проекте (хэширование паролей, JWT, HS256 vs RS256 и что вообще выбирают в
индустрии) — см. [`AUTH.md`](./AUTH.md).

## Как поднять

```bash
cp .env.example .env
docker compose up -d --build
```

Сервисы поднимутся в таком порядке: `user-db`/`task-db`/`redpanda` (пока не
станут healthy) → `user-service` → `task-service`/`outbox-relay`. Миграции
Alembic применяются автоматически при старте каждого сервиса
(`alembic upgrade head`, см. `CMD` в `Dockerfile`).

Swagger UI:
- user-service: http://localhost:8001/docs
- task-service: http://localhost:8002/docs

Redpanda Console (просмотр топика `task-events`): http://localhost:8090

Остановить и убрать volume'ы (сброс баз данных):

```bash
docker compose down -v
```

## Сценарий: потыкать через Swagger

Все шаги ниже выполняются через Swagger UI (`/docs`) соответствующего
сервиса. Значение `X-Admin-Secret` — это `ADMIN_BOOTSTRAP_SECRET` из `.env`
(по умолчанию `change-me-super-secret`).

1. **Регистрация исполнителя** — `POST /auth/register` на user-service
   (порт 8001): `{"email": "performer@example.com", "password": "pass1234"}`.
   Роль всегда `performer`.
2. **Регистрация админа** — `POST /auth/admin/register` на user-service, с
   заголовком `X-Admin-Secret: change-me-super-secret`:
   `{"email": "admin@example.com", "password": "pass1234"}`.
3. **Логин** обоих — `POST /auth/login` для performer и для admin. Каждый
   ответ содержит `access_token` (HS256 JWT с `sub`=user_id, `role`),
   подписанный общим секретом `JWT_SECRET_KEY`, который знают оба сервиса.
   В Swagger UI task-service нажмите "Authorize" и вставьте
   `Bearer <access_token>` соответствующего пользователя перед вызовом
   защищённых эндпоинтов.
4. **Admin создаёт задачу** — `POST /tasks` на task-service (порт 8002),
   авторизовавшись токеном admin:
   `{"title": "Написать статью", "description": "...", "reward": 50.00}`.
   Статус задачи — `OPEN`.
5. **Performer берёт задачу** — `POST /tasks/{id}/claim`, авторизовавшись
   токеном performer. Статус меняется на `IN_PROGRESS`, `performer_id`
   проставляется. Если выполнить `claim` повторно (или параллельно другим
   пользователем) — второй вызов получит `409 Conflict`: это и есть
   демонстрация optimistic concurrency при гонке за задачу (атомарный
   `UPDATE ... WHERE status='OPEN'`, побеждает тот, чей запрос выполнится
   первым).
6. **Performer завершает задачу** — `POST /tasks/{id}/complete` тем же
   токеном performer. Статус -> `DONE`. Попытка вызвать от чужого
   `performer_id` вернёт `403`.
7. **Admin подтверждает задачу** — `POST /tasks/{id}/approve` токеном admin.
   Статус -> `APPROVED`, и в той же транзакции создаётся строка в `outbox`
   (`event_type=task.completed`, `payload={task_id, performer_id, reward}`).
8. **outbox-relay** в фоне (обычно в течение нескольких секунд) подхватит
   эту строку, опубликует событие в топик `task-events` и проставит
   `published_at`. Убедиться, что событие ушло, можно в Redpanda Console
   (http://localhost:8090) или в логах `docker compose logs outbox-relay`.
9. **user-service consumer** получает событие, вставляет `event_id` в
   `processed_events` (`ON CONFLICT DO NOTHING`) и, если вставка реально
   произошла, начисляет `balance += reward` исполнителю. Если событие
   придёт повторно (at-least-once доставка), вставка конфликтнёт и баланс
   не изменится второй раз.
10. **Проверка баланса** — `GET /users/{performer_id}/balance` на
    user-service, авторизовавшись токеном performer (или admin). Баланс
    должен увеличиться на `reward` из шага 4.

Альтернативный путь: `POST /tasks/{id}/reject` вместо `approve` — статус
уходит в `REJECTED`, событие в outbox не пишется, баланс не меняется.

## Тесты

В каждом сервисе — базовые pytest+httpx тесты (health-check, JWT
подпись/верификация, сериализация outbox-события), не требующие поднятого
docker-compose:

```bash
cd services/user-service && pip install -r requirements.txt && pytest
cd services/task-service && pip install -r requirements.txt && pytest
cd services/outbox-relay && pip install -r requirements.txt && pytest
```

## На потом (не реализовано в этой итерации)

- Redis (кэш списка открытых задач, distributed lock)
- DLQ / retry-политики для Kafka consumer
- API Gateway, rate limiting
- Observability (Prometheus/Grafana, structured logging)
