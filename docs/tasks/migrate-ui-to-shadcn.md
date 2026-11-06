# Переход на shadcn/ui

Дата: 2026-10-21. Завершено и принято пользователем: 2026-10-26.

## Запрос и согласование

Переход с собственного React UI на shadcn/ui через Codex со skills и MCP.
Пользователь согласовал план и ADR 0003 ответом «Да, давай»: официальный
`@shadcn`, Radix, светлая компактная тема с синим акцентом, поэтапный перенос.
Повторное согласование этого плана не требуется. Приёмка реализации получена 2026-10-26: «Миграция UI на shadcn завершена, все окей».

Change: `openspec/changes/archive/2026-10-26-migrate-ui-to-shadcn/`; ADR:
`docs/adr/0003-shadcn-ui-primitives.md` — Accepted. Дельты specs отсутствуют по `skip_specs`.

## Реализация

- Проектный shadcn MCP настроен с cwd frontend, остальные серверы сохранены.
  После перезапуска tools доступны: выполнены поиск button в @shadcn, запрос
  примеров dialog и итоговый audit checklist. Использованы project skill shadcn,
  Context7, vibe-flow, openspec-apply-change, react-best-practices и
  frontend-testing-debugging.
- Tailwind 4 через Vite, aliases TS/Vite, components.json (`radix-nova`, Radix,
  Lucide), локальная утилита cn. Зависимости закреплены, package.json согласован
  с lockfile. CLI info подтверждает base radix, Tailwind v4 и корректные пути.
- Примитивы добавлены через CLI из @shadcn. Исправлены генерируемые импорты cn
  на @/lib/utils; state-селекторы приведены к реальным data-state Radix.
  Локальные изменения: компактные размеры, варианты статусов/тегов, Card asChild,
  русские подписи закрытия, ширина Sheet и акцент выбранного ToggleGroup.
- Тема в tokens.css, semantic mappings и явный порядок layers в global.css.
  Удалены стили старых кнопок/overlays, предметная геометрия каталога сохранена.
- Контролы, формы, выбор, статусы, загрузка, каталог, детали/история, shell,
  панель сбора, настройки фона и импорт перенесены на shadcn. Меню использует
  DropdownMenu, добавление — Sheet, группа/импорт — Dialog, удаления — AlertDialog.
  Добавлены проверки клавиатуры/фокуса и fallback после удаления trigger.
- Предметные компоненты вынесены в src/components/product; старый Button удалён.
  frontend/AGENTS.md подготовлен для дальнейшей работы и приёмки.
- API inputs, Tauri invoke, backend/worker/CLI/JSON mode не менялись; diff этих
  областей пуст. Миграций и операций над пользовательскими данными не было.

## Baseline до миграции

- Unit: 9 файлов / 20 тестов passed.
- Mock E2E: 27 passed, 1 failed — сценарий тегов не находил option «дом».
  Этот сбой больше не воспроизводится после переноса диалога; API/mock не менялись.
- Снимки каталога, деталей, группы и добавления при 1024/1440:
  `/tmp/price-watch-shadcn-before/`.
- Исходные E2E артефакты: `/tmp/price-watch-shadcn-baseline-results/`.

## Проверки реализации

- `npm --prefix frontend run lint` — passed.
- `npm --prefix frontend test` — 9 файлов / 20 тестов passed.
- `npm --prefix frontend run test:e2e` — 30/30 passed, включая два новых
  сценария Tab/Shift+Tab/Escape, возврат фокуса и отмену удаления.
- После последнего изменения только цветов ToggleGroup — дополнительно passed
  2 E2E фильтров/переключения вида, lint и повторная сборка desktop.
- `npm --prefix frontend run build:desktop` — passed отдельно и как шаг Tauri.
- `npm --prefix frontend run desktop:build` — passed; release binary:
  `frontend/src-tauri/target/release/price-watch-desktop`.
- `git diff --check`, проверка деклараций lockfile и
  `openspec validate migrate-ui-to-shadcn --strict` — passed.
- Browser plugin отсутствует; использован существующий Playwright/Chromium,
  URL `http://127.0.0.1:5175/cards`, 1024/1440 px. Page identity и содержимое
  подтверждены; framework overlay и ошибок JS/console.error нет, overflow нет.
  Снимки после миграции: `/tmp/price-watch-shadcn-after/`.
- Настоящий Tauri WebView/WebKitGTK 2.54.1: smoke через tauri-driver и
  WebKitWebDriver прошёл при 1024/1440. Проверены тема, каталог, сетка, Sheet,
  Dialog, переход menu→AlertDialog, Escape и возврат фокуса; overflow нет.
  Сценарии использовали mock-данные через dev URL внутри WebView. XDG и
  PRICE_ANALYZER_PROJECT_DIR указывали в `/tmp/price-watch-tauri-smoke/`;
  пустой project dir намеренно исключал запуск backend/worker и доступ к
  пользовательскому профилю. Драйвер установлен только в /tmp и остановлен.
  Скрипт, логи и изображения: `/tmp/price-watch-tauri-smoke/`.
- Repowise обновлён до HEAD d6dd5f34 и working tree; change risk не выявил
  новых/ухудшенных findings в проанализированных файлах. Анализ частичный:
  CSS не поддерживается, часть графа может отставать от последних правок.
  CSS и критичные пути проверены по текущему source, тестам и изображениям.

## Ограничения

Mock E2E и WebView smoke не проверяют живые API, PostgreSQL, сбор Ozon и worker.
Полная интеграция с пользовательскими данными не запускалась. Vite сообщает
о main chunk около 594 kB; исходное предупреждение React Router HydrateFallback
также сохраняется. Непроверенные платформы: Windows/macOS WebView.

## Финализация

2026-10-26 пользователь явно принял миграцию. Задача 5.3 закрыта на основании
ранее записанных проверок, обзора diff/risk и текущей приёмки. Финализированы
frontend/AGENTS.md, описание UI-слоя и ADR 0003. Change архивирован; sync specs
не нужен (`skip_specs`, дельты отсутствуют). Запись об ожидании приёмки удалена
из backlog. При финализации менялись только документы и OpenSpec; проверки
приложения повторно не запускались. Исследование размера bundle ранее
остановлено по указанию пользователя; оптимизация в миграцию не входила.
Push и merge не выполнялись.

## Исправление выпадающих списков после обратной связи

Пользователь указал на устаревший вид фильтра «Состояние» и остальных списков.
Причина: NativeSelect оформлял поле, но раскрытая часть оставалась системной.
Все шесть потребителей переведены на Radix/shadcn Select: четыре фильтра,
сортировка в GroupDialog и выбор группы в BulkCardActions. NativeSelect удалён.
Добавлен Select через официальный CLI; исправлены импорт cn и state-селекторы
под установленный Radix. Новых npm-зависимостей не осталось. API, URL-параметры,
сортировка, сохранение групп и данные не менялись. Значения тегов в Select
имеют префикс, чтобы настоящий тег не пересекался с пунктом «Все теги».

Проверки: lint, 20 unit-тестов, build:desktop и desktop:build passed.
Полный E2E: 29 passed, один тест требовал ожидания завершения закрытия Select
перед чтением диалога. После добавления ожидания этот сценарий и новый тест
оформления/клавиатуры прошли (2/2); всего проверен 31 сценарий.
Browser plugin отсутствует, использован существующий Playwright/Chromium на
http://127.0.0.1:5175/cards с mock-данными при 1024/1440 px. Проверены открытие
всех фильтров, тема панели, границы окна, Escape, возврат фокуса, End/Enter,
фильтрация и сброс. Ошибок JS нет. Снимки:
`/tmp/price-watch-select-state-1440.png`, `/tmp/price-watch-select-state-1024.png`.
Реальный Tauri WebView для этой правки повторно не запускался; исполняемый файл
пересобран. Предупреждение Router HydrateFallback сохраняется; main chunk теперь
616.85 kB (gzip 187.37 kB), оптимизация bundle не выполнялась по указанию пользователя.

## Визуальное отделение групп в списке

По запросу пользователя группы в таблице получили акцентный фон заголовка,
синюю полосу слева и границы блока; вложенные товары — слабую заливку и
сохраняющийся отступ. Выделение и hover остаются заметнее обычного фона.
Изменён только CSS каталога, логика групп и сетка не менялись.
Lint и два существующих E2E выбора/сценария группы passed. Playwright/Chromium
на mock dev URL проверил две соседние группы, одиночные товары и выделение
вложенной карточки при 1024/1440 px: overflow и ошибок JS нет.
После последней правки фона ячеек повторена визуальная проверка тем же скриптом.
Снимки: `/tmp/price-watch-group-separation-1440.png`,
`/tmp/price-watch-group-separation-1024.png`,
`/tmp/price-watch-group-separation-selected.png`.
Финальная desktop:build passed; настоящий Tauri WebView для CSS-правки повторно не запускался.

## Коррекция оформления групп по уточнению пользователя

Синяя полоса, акцентные границы и голубая заливка групп удалены.
Вместо них добавлены отступы по 8 px перед и после каждой группы
(включая свёрнутые), слегка серый фон заголовка и вложенных товаров.
Пустые строки-отступы скрыты от accessibility tree. Обычное выделение
выбранных карточек сохранено. Lint и 2 целевых E2E passed;
визуально проверены 2 группы и отдельные товары при 1024/1440 px,
ошибок JS и горизонтального overflow нет. Скриншоты обновлены
в `/tmp/price-watch-group-separation-1440.png` и соответствующих вариантах.
Desktop:build после коррекции passed; реальный WebView повторно не запускался.
