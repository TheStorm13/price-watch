# Переход на shadcn/ui

Дата: 2026-10-21. Стадия: реализация подготовлена к приёмке; задача 5.3 открыта до явного принятия пользователем.

## Запрос и согласование

Переход с собственного React UI на shadcn/ui через Codex со skills и MCP.
Пользователь согласовал план и ADR 0003 ответом «Да, давай»: официальный
`@shadcn`, Radix, светлая компактная тема с синим акцентом, поэтапный перенос.
Повторное согласование этого плана не требуется. Приёмка реализации ещё не получена.

Change: `openspec/changes/migrate-ui-to-shadcn/`; ADR:
`docs/adr/0003-shadcn-ui-primitives.md` остаётся Proposed до финализации после
приёмки. Дельты specs отсутствуют по `skip_specs`.

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

## Следующее действие

Представить результат и изображения пользователю; получить явную приёмку по
vibe-flow. Затем завершить 5.3, применить подготовленное описание UI-слоя
(`/tmp/shadcn-architecture-after-acceptance.patch`), финализировать
frontend/AGENTS.md и статус ADR, архивировать change. Sync specs не нужен.
Пользователь отдельно поручил сделать коммит текущей реализации: «Короче забей, ладно. Просто коммит сделай». Исследование размера bundle остановлено по этому указанию; оптимизация в коммит не входит. Push и merge не разрешены. Архивирование change и формальная финализация документации в этот коммит не входят.
