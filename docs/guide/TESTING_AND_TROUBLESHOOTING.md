# Проверки и диагностика

[К содержанию](README.md)

## Локальные службы

После запуска desktop логи находятся в
`$XDG_STATE_HOME/price-watch/` (обычно `~/.local/state/price-watch/`):
`postgres.log`, `api.log`, `xvfb.log` и `desktop-worker.log`.
Сообщение об ошибке запуска указывает соответствующий файл.
API слушает свободный локальный порт и требует секрет, который Tauri передаёт
интерфейсу. Фиксированного адреса для ручного `curl` нет.

## Автоматические проверки

```bash
.venv/bin/python -m unittest discover -s tests -v
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run test:e2e
cargo test --locked --manifest-path frontend/src-tauri/Cargo.toml
```

Интеграционный тест PostgreSQL запускается только с `TEST_DATABASE_URL`,
указывающим на **отдельную тестовую базу**. Создайте её на доступном
PostgreSQL и запустите:

```bash
TEST_DATABASE_URL='postgresql://user:password@localhost:5432/price_watch_test' \
  .venv/bin/python -m unittest tests.test_postgres_integration -v
```

Тест применяет миграции и изменяет данные этой базы. Не указывайте здесь
рабочую базу приложения. E2E тесты сами запускают Vite в demo режиме;
они проверяют интерфейс, но не живое соединение с Ozon.

## Типовые проблемы

| Симптом | Что проверить |
| --- | --- |
| `./price-watch` сообщает, что приложение не собрано | Запустить `npm --prefix frontend run desktop:build` |
| Не найден Python или Python модули | Создать `.venv` и установить `requirements.txt` |
| PostgreSQL не стартует | Открыть `postgres.log`; проверить установленную версию и права на каталог `$XDG_DATA_HOME/price-watch/postgres` |
| API не отвечает | Открыть `api.log`; проверить ошибки миграций и запуска Python |
| Нет Chrome | Проверить `google-chrome-stable --version` |
| Скрытый дисплей недоступен | Открыть `xvfb.log`; проверить установку `Xvfb` и `xauth` |
| Ozon запросил проверку при фоновом сборе | После завершения запуска открыть Chrome кнопкой, пройти проверку и повторить сбор |
| Карточка Ozon не обновилась | Открыть `desktop-worker.log`; исчезнувший товар может вести на страницу предложений |
