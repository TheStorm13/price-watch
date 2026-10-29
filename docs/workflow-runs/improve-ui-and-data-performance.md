# Производительность UI и рост данных

## Объём и разрешение

2026-10-29 пользователь после исследования разрешил: «Все задачи кроме ускорения озон можно брать в работу. Вперед», затем «Продолжи» после прерывания. Объём: PERF-02/03/04/05, связанная часть ARCH-02 и пять предложенных улучшений UI. Самостоятельные ARCH-01/04/05 не были предложены как задачи производительности и в этот change не добавлены. Ускорение Ozon исключено явно.

Первое разрешение охватывает направление работ. Конкретная архитектура миграции диагностики, владения журналами живых процессов и виртуализации ранее не была представлена. Согласно проектному требованию согласовать ADR до значимого изменения архитектуры подготовлен [ADR 0010](../adr/0010-bounded-ui-diagnostics-and-logs.md), статус Proposed. Одобрение ADR пока не получено; код приложения и пользовательские данные не менялись. Отдельная приёмка будущей реализации также ещё не получена.

## План

[OpenSpec proposal](../../openspec/changes/improve-ui-and-data-performance/proposal.md), [design](../../openspec/changes/improve-ui-and-data-performance/design.md), [tasks](../../openspec/changes/improve-ui-and-data-performance/tasks.md).

1. Release baseline UI/API/error/export на изолированных данных.
2. Стабильные команды сбора отдельно от прогресса; модель каталога и memo boundaries; виртуализация списка, сетки, больших групп и редактора групп.
3. Переиспользование Intl, подготовка графика без повторных сортировок и лишних повторных вычислений, точная SQL-проекция истории.
4. Ошибки запусков — отдельные append-only строки; компактные чтения; атомарный проверяемый перенос старого массива с удалением старого runtime пути.
5. Единая bounded size/age политика журналов Rust/Python через pipes, включая общий ChromeSession и numeric mode.
6. Экспорт только нужных полей истории и индекс состава групп; сравнение canonical JSON и памяти.
7. Общие проверки, native WebView, отдельная приёмка; затем документы/backlog/spec sync/archive и task commits без push.

## Исследование и ограничения инструментов

CodeGraph вернул текущий source для UI, queries, adapters и Rust/Python logging. Repowise local state соответствует HEAD `49c0473db4432eb777910b83c7146a157d250802`, но MCP overview/risk возвращает `9f3876d9ba3f`, возраст 5 дней, старые пути `price_analyzer`. Это уже наблюдалось в предыдущем workflow; индексные оценки не считаются текущим доказательством. Критические утверждения проверены по current source. Новый индекс не создавался, model-backed generation не запускалась.

Context7: React memo/context/deferred rendering, TanStack Query referential identity/structural sharing, TanStack Virtual variable measurement/rangeExtractor/scroll restoration. Это документация выбора подхода, не доказательство работы будущего кода.

Browser plugin not available (нет browser skill/runtime в каталоге). Использован установленный Playwright Chromium, viewport 1440×1000, локальный mock fixture http://127.0.0.1:5175/cards. Node v26.12.1. Production desktop сборка из предыдущего исследовательского шага прошла; после неё application source не менялся.

## Выполненный UI diagnostic

Временный harness `/tmp/pw-ui-baseline.mjs`; raw `/tmp/pw-ui-baseline.json`, screenshot `/tmp/pw-ui-baseline.png`. Harness импортирует существующий mockApi/queryClient через Vite, создаёт только in-memory каталог из шаблона карточки с новыми ID, без групп/картинок/deals. До установки синтетики дожидается загрузки исходного fixture. Полный query snapshot заменяется одной операцией; БД, пользовательские XDG и Chrome profile не используются.

Один sample на размер, development-сборка, последовательный запуск. Mount — от setQueryData до двух requestAnimationFrame; selection/search — wall clock Playwright action с ожиданием результата. Они включают автоматизацию, доступность target и планирование кадра; это не чистое CPU-time и не production p95. Время взаимодействия нельзя переносить в продуктовые обещания. Число DOM-узлов — после полного mount.

| Карточки | Mount, мс | DOM-узлы | Строки tbody | Выбор, мс | Поиск, мс |
| --- | --- | --- | --- | --- | --- |
| 100 | 1093.7 | 2853 | 100 | 1066.7 | 1498.3 |
| 1000 | 6605.2 | 27153 | 1000 | 3823.3 | 3671.1 |
| 5000 | 35307.3 | 135153 | 5000 | 13284.6 | 13476.3 |

Выбор проверял появление панели массовых действий. Поиск `Тестовый товар 4999` проверял сокращение tbody до ≤1 строки (на меньших наборах ожидается пустой результат). В каждом новом page открывалось исходное fixture; прежний выбор не переносился. В трёх успешных samples `pageerror` отсутствовали. Полная console warning/visual/mobile/native матрица не выполнялась; screenshot сделан уже после поиска, не является доказательством большого каталога.

Первый запуск harness ошибочно выбрал первый checkbox страницы (фильтр выгодных), затем ожидание панели выбора истекло. Он не входит в результаты. Селектор исправлен на checkbox внутри tbody; успешная серия выполнена заново целиком.

Вывод, который подтверждён: DOM и число строк линейно растут с каталогом; на данном dev fixture полный большой каталог дорог. Проценты ускорения будущей реализации, production p95, API latency, native CPU/RSS и качество виртуализации ещё не измерены.

## Проверки и текущее состояние

- `openspec validate improve-ui-and-data-performance --strict` — passed.
- `openspec status --change improve-ui-and-data-performance` — 4/4 planning artifacts complete; это не завершение реализации.
- Development mock diagnostic — 3/3 sizes завершены, pageerror нет; ограничения выше.
- Python/Rust/frontend regression suites и новые release/backend benchmarks ещё не запускались: application implementation пока отсутствует.
- Пользовательские данные и профили не затрагивались. Схема БД не менялась. Backlog не закрывался, main specs не синхронизировались, change не архивировался.

## Следующее действие

Получить согласование конкретного ADR/плана: виртуализация при сохранении snapshot, отдельные строки ошибок с проверяемым переносом, pipes/ротация 10 MiB ×4 и 14 дней. После согласования использовать openspec-apply-change improve-ui-and-data-performance, записать одобрение и выполнить оставшиеся tasks без повторного согласования уже принятых решений. Перед финальным завершением реализации обязательна отдельная приёмка по vibe-flow.
