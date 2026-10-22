# Проверки REL-01–REL-05

Статус: реализация проверена и принята пользователем («Хорошо», 2026-10-22).

## Производительность

Один стенд: Python 3.14.8, PostgreSQL в отдельном Unix socket, ASGI HTTP с сериализацией. S: 100 карточек/10 000 точек истории; M: 1000/100 000; L: 5000/500 000. Пять прогревов, 30 измерений на комбинацию. Writer: synthetic connector с задержкой 10 мс, реальная запись результатов. RSS — максимальное значение VmRSS, снятое после запросов; это выборочные измерения, не непрерывный мониторинг.

| Набор | p95 до → после, мс | SQL до → после | RSS до → после, МиБ | Запись до → после, карточек/с |
|---|---:|---:|---:|---:|
| S_idle | 106.0 → 63.6 | 9 → 3 | 99.0 → 98.5 | — |
| S_writer | 97.0 → 59.1 | 9 → 3 | 101.0 → 100.3 | 76.4 → 73.8 |
| M_idle | 444.0 → 342.6 | 9 → 3 | 111.4 → 120.0 | — |
| M_writer | 523.5 → 315.0 | 9 → 3 | 117.0 → 122.9 | 99.3 → 81.0 |
| L_idle | 2063.2 → 1220.9 | 9 → 3 | 148.1 → 151.0 | — |
| L_writer | 2245.1 → 1242.2 | 9 → 3 | 164.5 → 174.2 | 95.5 → 79.4 |

Все согласованные пороги пройдены: HTTP ≤ max(1.20 × baseline, baseline + 50 мс), SQL ≤5; RSS ≤ max(1.20 × baseline, baseline + 25 МиБ); write-throughput ≥80% baseline. На M/L фиксация результатов медленнее на 18.4%/16.8%; это измеренная цена дополнительного атомарного журнала, в пределах одобренного порога. HTTP p95 лучше на 23–45%.

Raw-данные: [baseline](baseline.json), [after](after.json). Старые runtime-пути не сохранены ради повторения baseline. Harness после перехода проверяет новый endpoint.

## Review

Repowise обновлён с --working-tree; get_change_risk указывает сложность get_catalog, ActiveCollectionPanel и execute. Источник проверен: catalog строит существующие правила представителя/выгоды из трёх запросов одного снимка; панель меняет только условие повтора и предупреждение; execute закрывает сеансы/отменяет fetch при потере lease. Поведение покрывают DB, unit и E2E проверки. Сигналы сложности не являются обнаруженными функциональными ошибками.

Проверены порядок блокировок run → target → card, атомарность rollback, уникальность retry, сохранение истории и невозможность записей от отозванного владельца. Поиск runtime-потребителей target_card_ids/save_observation и старых list hooks/methods не нашёл совпадений. OpenAPI не содержит заменённых GET списков.

## Выполненные проверки

- `TEST_DATABASE_URL=<отдельная disposable БД> .venv/bin/python -m unittest discover -s tests -v`: 104/104 passed. После добавления проверок ожидания browser challenge и terminal input: `python -m unittest tests.test_run_reliability tests.test_analyzer_cli -v` — 17/17 passed, включая эти две новые проверки.
- `npm --prefix frontend test`: 54/54 passed.
- `npm --prefix frontend run test:e2e`: 38/38 passed (5.3 мин). Проверяет mock API; live службы этим не подтверждаются.
- `cargo test --locked --manifest-path frontend/src-tauri/Cargo.toml`: 8 passed, 3 ignored. Игнорируемые Rust smoke-тесты автоматически не запускались; отдельный live smoke описан ниже.
- `npm --prefix frontend run desktop:build`: TypeScript, Vite и Rust release успешно собраны.
- Без DATABASE_URL: оба CLI-импорта и `main.py --help`/`main.py 123 --help`; numeric JSON выполняется в subprocess с fake product service, проверен JSON в stdout. Прямой collect отдельно проверен с fake connector, включая убийство только тестового subprocess и recovery.
- Ожидание проверки: живой lease и heartbeat во время waiting_for_user, продолжение через API/repository и запрет воскресить отозванный запуск; terminal handler ожидает input. Реальная CAPTCHA Ozon не вызывалась.
- `openspec validate harden-collection-reliability --strict` и `git diff --check`: passed.

## Native desktop smoke

Изолированная Xvfb/D-Bus сессия, собственные XDG-каталоги, PostgreSQL/API/worker под управлением release-приложения. Fake connector сначала падает при открытии сеанса, затем возвращает 100 ₽. Кнопка повтора нажата через AT-SPI в настоящем WebView. Проверены успешная запись через live API и отображение 100 ₽ на снимке интерфейса. Затем остановлен только дочерний API этого теста: Tauri запустил новый API, каталог и цена восстановились. Снимки просмотрены вручную. Пользовательские данные/профили и реальный Ozon не используются.

[Отчёт](native-smoke.json), [до повтора](native-before.png), [после повтора и перезапуска API](native-after.png). Harness: `dbus-run-session -- xvfb-run -a -s '-screen 0 1440x1000x24' python scripts/smoke_reliability_desktop.py` (system Python с gi/Atspi, ImageMagick; release binary уже собран). Первые попытки automation не прошли из-за изолированного accessibility bus и отсутствия цены в AT-SPI names; финальная проверка использует собственный bus, а цену сверяет через live API и screenshot.

## Переход и границы

Перед обновлением схемы остановить старые API/worker/CLI. Миграция 0014 forward-only: переносит известные цели, сохраняет карточки и историю, затем удаляет старый массив. Старые GET списков удалены; все потребители проекта переведены на /api/catalog. Смешанные версии не поддерживаются. Для неполных старых запусков доступен повтор только известных существующих целей с предупреждением в UI.

Приёмка получена 2026-10-22. ADR 0004 принят, затронутые guides и specs обновлены, REL-01–REL-05 отмечены выполненными; оставшиеся десять задач backlog открыты. Все 23 задачи закрыты, change архивирован в `openspec/changes/archive/2026-10-22-harden-collection-reliability/`. Принятые изменения сохраняются отдельным commit; исходный аудит backlog — commit bdbc318.
