# Руководство по репозиторию

## Структура проекта

`marketplace_connector/` содержит общий контракт товара и коннектор Ozon. В `price_analyzer/` находятся доменная модель, сервис сбора, маршруты FastAPI, worker и работа с PostgreSQL; миграции Alembic — в `price_analyzer/infrastructure/postgres/alembic/`. `ozon_article_json/` предоставляет CLI для одного товара. Интерфейс React расположен в `frontend/src/`, оболочка Tauri и иконки — в `frontend/src-tauri/`. Тесты Python находятся в `tests/`, компонентные тесты — рядом с компонентами, браузерные — в `frontend/e2e/`. Начните с `README.md` и `docs/guide/`; планы записаны в `docs/FUTURE_CHANGES.md`.

## Запуск, сборка и проверки

- `python -m venv .venv && .venv/bin/pip install -r requirements.txt` — подготовить окружение Python.
- `docker compose up -d db` и `.venv/bin/python main.py db migrate` — запустить PostgreSQL и применить миграции. Сначала создайте `.env` по образцу `.env.example`.
- `npm --prefix frontend install` и `npm --prefix frontend run dev:demo` — запустить интерфейс с тестовыми данными. Для реального API используйте `npm --prefix frontend run dev`.
- `npm --prefix frontend run build` — проверить типы и собрать web-интерфейс. `npm --prefix frontend run desktop:build` собирает исполняемый файл Tauri без установочного пакета.

## Стиль кода и имена

Следуйте существующему коду: Python — отступ четыре пробела и `snake_case`; TypeScript — два пробела, `camelCase` для значений и `PascalCase` для компонентов React. Доменную логику размещайте вне маршрутов API и компонентов интерфейса. Изменения схемы БД оформляйте новой миграцией Alembic. Команда `npm run lint` проверяет сборку TypeScript; общего форматтера в проекте нет.

## Тестирование

Для Python и API запускайте `.venv/bin/python -m unittest discover -s tests -v`. Новые файлы называйте `test_*.py`, методы — `test_*`. При изменении интерфейса запускайте `npm --prefix frontend test`, `npm --prefix frontend run test:e2e` и `npm --prefix frontend run lint`; модульные тесты frontend имеют суффикс `*.test.ts(x)`. Интеграционные тесты PostgreSQL требуют отдельной базы в `TEST_DATABASE_URL`: не указывайте рабочую БД. Числовой порог покрытия не задан.

## Коммиты и pull request

В истории используются короткие повелительные заголовки с префиксами `feat:` и `docs:`; придерживайтесь этого формата. В pull request опишите изменение поведения, укажите связанную задачу или пункт плана и перечислите выполненные проверки. Для изменений интерфейса приложите скриншоты. Отдельно отметьте миграции, новые настройки и ручную проверку браузера, если они нужны.

## Конфигурация и безопасность

Храните учётные данные в локальном `.env`, не добавляйте их в коммиты. Не коммитьте профили браузера, логи и экспортированные данные товаров. Для разработки desktop-версии нужны Docker, PostgreSQL и системный Google Chrome. Перед изменением портов или запуска браузера прочитайте `docs/guide/CURRENT_NUANCES.md`.
