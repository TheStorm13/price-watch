# Проверка реализации Wildberries

2026-10-27. План одобрен пользователем: «Переходи к реализации».
Второй review пройден: пользователь подтвердил «Все хорошо. Коммиты и завершай».
Руководства обновлены, ADR 0009 принят; спецификации синхронизированы, change архивирован.

## Результат

- Выбранный размер имеет `nmId:optionId`, независимую карточку и историю.
- Только одна Decimal цена WB Кошелёк → обычная при подтверждённой
  неприменимости. Загрузка условий и готовность контекста профиля обязательны.
- Shared ChromeSession Ozon/Ali/WB, отдельные страницы; WB runtime-запросы
  сериализованы для безопасной работы изменяемых условий витрины. Общий предел
  сбора в пять карточек сохранён. До трёх фактических попыток на detail/grade
  для одной цели, включая повторы витрины и восстановление; внешнего умножающего
  слоя повторов нет. 429 использует общий cooldown.
- Отмена/таймаут закрывает только WB-страницу, если helper не принимает signal;
  соседние площадки и общий Chrome остаются. Необязательная static metadata
  имеет свой ограниченный срок; зависший запрос останавливается перед
  следующей целью, уже подтверждённая цена сохраняется.
- Миграция 0016 только для однозначного размера в сохранённой ссылке;
  preflight, сохранение ID/history/snapshot/групп/тегов/настроек/run targets.

## Выполненные проверки

| Проверка | Результат |
| --- | --- |
| `TEST_DATABASE_URL=<disposable> .venv/bin/python -m unittest discover -s tests -v` | **208 passed**, 32.322 s |
| Отдельный regression `tests.test_wildberries_transport` | **1 passed** (добавлен после начала discovery полного набора) |
| WB synthetic Chrome suite | **17 passed**, также входит в полный набор |
| WB mapper/identity/API/migration/integration/transport | В полном наборе; PostgreSQL private schemas; direct CLI и queued worker дают 1024.00 и одну запись истории; schedule/retry exact size |
| `npm --prefix frontend test` | **66 passed**, 17 files |
| `npm --prefix frontend run lint` | passed |
| `npm --prefix frontend run test:e2e` | **41 passed**, 2.6 min, только demo/mock |
| `npm --prefix frontend run desktop:build` | passed, release binary построен |
| `cargo test --locked --manifest-path frontend/src-tauri/Cargo.toml` | **8 passed, 3 ignored**; ignored проверки требуют иных условий |
| Numeric Ozon без DATABASE_URL, оба CLI imports | passed в `test_price_watch_cli` полного набора |
| Native Tauri/WebView только WB | passed: повтор после искусственной ошибки запуска, сохранение цены, восстановление каталога после перезапуска тестового API |
| Native Tauri/WebView Ozon+Ali+WB | те же три проверки passed, все три карточки в каталоге |
| Live Ozon+Ali+WB одним Chrome/профилем | successful для всех трёх; получены Ozon 884.00, Ali 65375.00, WB 1015.00 |
| Live WB vs storefront | connector 1015.00; диалог витрины: 1015 ₽ с кошельком, 1047 ₽ без; размер 58–60 |
| `git diff --check` | passed |

Логи выполненных команд остались в `/tmp/wb-*`; в репозиторий не копировались
cookies, JWT, служебные headers, адрес доставки или содержимое личного профиля.
Временный PostgreSQL запущен исключительно для этой задачи на порту 55438,
базы `price_watch_wb_test` и `price_watch_wb_suite`; пользовательская БД не
открывалась и не мигрировалась. Native harness создавал отдельные XDG/службы/БД.
После проверки временный PostgreSQL штатно остановлен.

Первые прогоны выявили и исправили:

- старые assertions, считавшие WB pending connector, и numeric WB fixtures;
- слишком раннюю готовность runtime: getXinfo может отклоняться до инициализации
  host; Xnm скрывает это зависшей Promise. Введён ограниченный readiness barrier;
- гонку очистки уже завершённых response tasks: gather может не отдать управление
  queued callbacks; snapshot удаляется до gather. Отдельный regression test.

После этих исправлений полный Python и соответствующие браузерные проверки
прошли. Первый E2E прогон: 40/41; после обновления старого pending-WB теста
повторный полный прогон 41/41.

## Review рисков

Repowise `get_change_risk` подтвердил текущий working-tree root/HEAD и прочитал
новые файлы через live Git. Его история/test reach всё ещё опираются на старый
индекс `9f3876d9ba3f` другого проекта: утверждение про изменённый package-lock
не соответствует текущему diff. Для зависимостей использованы текущий source,
CodeGraph и полный набор проверок. Не считать старую историю доказательством.

Live structural analysis указал сложность mapper/runtime. Проверки разделены
на небольшие функции profile/wallet, parse/variants/price/rating/metadata;
после этого повторены mapper и actual Chrome tests, затем полный Python suite.
Критичные runtime-границы дополнительно проверены вручную по diff.
Повторный narrow analysis оставляет один структурный сигнал сложности внешней
JS closure (45): bridge обязан передаваться в page.evaluate самодостаточным
выражением с локальными helpers. Сам сигнал не доказывает runtime-дефект;
readiness, grade, transport и cancel ветви покрыты actual Chrome tests.

Оставшиеся ограничения: WB использует внутренний runtime, который может
измениться; это приводит к явной ошибке схемы. Live авторизованный WB-профиль
не проверен, соответствующий grade lifecycle проверен synthetic Chrome test.
Полное описание/картинки не предоставляются выбранным compact metadata helper;
они остаются пустыми. Старые WB карточки без размера требуют добавления
конкретного размера пользователем, их старая история остаётся доступной.

Документация для приёмки: [черновик](documentation-draft.md).
После приёмки обновлены руководства и принят ADR 0009. Финализация включает
sync/archive OpenSpec и task-only Git commit после проверки staged diff. Push не выполняется.
