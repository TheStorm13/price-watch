# Проверки и диагностика

[К содержанию](README.md)

## Быстрая проверка сервисов

```bash
docker compose ps -a
curl -fsS http://127.0.0.1:8000/api/health
docker compose logs --tail=100 api migrate
tail -100 output/desktop-worker.log
```

Ответ API `{"status":"ok"}` подтверждает, что HTTP сервис доступен. При
desktop запуске контейнерные `frontend` и `worker` должны быть остановлены:
вместо них работают Tauri и локальный Python worker. Лог последнего передаётся
в Dozzle через сервис `desktop-worker-logs` и доступен в файле
`output/desktop-worker.log`.

## Автоматические проверки

Python unit-тесты и тесты API без внешних сервисов:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Интеграционный тест PostgreSQL работает только с отдельной тестовой БД.
Создайте её один раз и запустите тест, не используя рабочую базу:

```bash
docker compose exec db createdb -U price_analyzer price_analyzer_test
TEST_DATABASE_URL='postgresql://price_analyzer:price_analyzer@127.0.0.1:5432/price_analyzer_test' \
  .venv/bin/python -m unittest tests.test_postgres_integration -v
```

Если тестовая БД уже существует, пропустите `createdb`. Тест применяет к ней
миграции, создаёт временные карточки и удаляет свои данные после проверки.

Frontend и Rust:

```bash
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run test:e2e
cargo check --locked --manifest-path frontend/src-tauri/Cargo.toml
```

Playwright E2E тесты сами запускают Vite на `127.0.0.1:5175` в demo режиме.
Они проверяют интерфейс и взаимодействия с mock API, но не подтверждают
работу живого Ozon или сохранение в PostgreSQL. Для этого нужны отдельные
интеграционные и ручные проверки. Команда `cargo check` проверяет Rust код и
не собирает AppImage.

## Типовые проблемы

| Симптом | Что проверить |
| --- | --- |
| `./price-watch` сообщает, что приложение не собрано | Запустить `npm --prefix frontend run desktop:build` |
| Не найден `.venv/bin/python` | Создать `.venv` и установить `requirements.txt` |
| Старт зависает или API не отвечает | `docker compose ps -a`, миграции, занятость портов 8000 и 5432 |
| Нет Chrome | Проверить `google-chrome-stable --version`; desktop требует системный Google Chrome |
| Chrome просит проверку Ozon | Пройти проверку в его окне и продолжить запуск в приложении |
| Карточка Ozon не обновилась | Проверить `output/desktop-worker.log`; исчезнувший товар может вести на страницу предложений |
| Код API изменился, а ответ старый | Пересобрать и перезапустить контейнеры API и миграций по инструкции запуска |
| Удаление карточки в Tauri не проходит | Проверить, что API пересобран с миграцией и разрешённым методом `DELETE` в CORS |

Логи контейнеров доступны также в Dozzle на `http://127.0.0.1:8080`.
