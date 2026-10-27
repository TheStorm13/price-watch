# Design

## Context

Мотивация и требования — proposal.md и два delta specs. Общая модель принимает
строковый ProductRef, одну Decimal price и уникальные ref вариантов. Builder
создаёт один ChromeSession для Ozon/Ali; обе CLI-фабрики используют его.
WB входит в PENDING_CONNECTOR_MARKETPLACES, а UI разрешает обновление только
Ozon/Ali в CardsPage, CardDetailsPage и связанных действиях.

Live evidence — docs/workflow-runs/add-wildberries-connector/research.md.
Прямые HTTP не работают. JSON с профилем и заголовками витрины работает.
Runtime главной `wb.xnm` нормализует per-size price; обычный fetch без полного
контекста возвращает 403. После явной готовности условий кошелька нормализатор
даёт скидку 32 ₽ на исходные 1056 ₽. Без готовности даёт ложный ноль.

## Goals / Non-Goals

**Goals:** определённый размер и один точный результат, shared профиль,
явные ошибки, сохранение данных, проверяемый путь с главной без product goto.

**Non-Goals:** агрегат минимальной цены по размерам, поиск, покупки/открытие
кошелька, автоматическое решение CAPTCHA, новый standalone CLI, новая версия
общего JSON или отдельный профиль. Не добавлять предпросмотр с запуском Chrome
из API: профиль остаётся ресурсом запуска сбора. UI принимает ссылку с size
либо явный код размера; для probe это `179224846:296499716`.

## Decisions

### Идентичность

Proposed ADR 0009 сравнивает numeric-only, URL-owned, новую общую колонку и
каноническую пару. Выбран `nmId:optionId`. WildberriesRef валидирует ASCII
digits, положительные идентификаторы, HTTPS storefront URL и единственный
size; неизвестные tracking query не определяют идентичность. Дубликаты size,
несовпадение nm/size и неподдерживаемые хосты отклоняются. Canonical URL:
`https://www.wildberries.ru/catalog/{nmId}/detail.aspx?size={optionId}`.

Общую validate_card_identity переместить из Ali adapter в application-level
модуль. Обновить schemas, repositories и transfer напрямую без shim. AliExpress
ref остаётся внутри своего адаптера. UI добавляет поле кода размера по образцу
SKU Ali, разбор ссылки и подсказку получения ссылки выбранного размера.
API/CLI/transfer принимают пару. Строковые ID не проходят через JS Number
без проверки безопасного диапазона при передаче runtime WB.

### Chrome и storefront runtime

WB client/transport входят в builder и используют отдельную страницу общей
ChromeSession. Bootstrap главной ограничен таймаутом, проверяет фактический
origin и runtime. Подготовка условий использует штатный user/grade lifecycle
витрины с учётом авторизации, проверкой успешного ответа/валидного свежего
состояния. Не подменять условия авторизованного профиля общими unauth-скидками.
Не сбрасывать cookies/регион и не подставлять probe dest=1259570991.

WB-specific bridge вызывает товарный JSON через `wb.xnm.getXnmProducts` в
detail-режиме с AbortSignal и проверяет транспортные события и возвращённую
структуру. Этот путь использует собственный HTTP-клиент площадки и нормализатор;
принимается только совпадающий nmId, затем ровно один optionId. Товарный helper
может скрывать ошибку пустым результатом: пустой/замещённый товар не успешен.
Часть цен верхнего уровня агрегирована по размерам и не используется.

Запросы имеют requestId/AbortController и ограниченный общий deadline;
частота/параллелизм/число фактических сетевых попыток контролируются, включая
повторы самой витрины. Перехват запросов/ответов на WB-странице ограничивает
товарные и grade-ручки; cookies/JWT/заголовки не записываются. HTTP 429 ставит
общий cooldown до следующих попыток. Восстановление ждёт активные запросы,
не перезагружает страницу под соседней целью. Превышение бюджета даёт ошибку.
Один запрос отменяется своим signal; последний consumer закрывает Chrome.

### Цена и схема

Для выбранного размера bridge получает priceToShow (копейки) и отдельную
кошелёчную paymentDiscountAmount (рубли) после готовности условий. Возвращает
в адаптер точные строки денежных значений и статус готовности/применимости.
Итог = priceToShow/100 минус кошелёчная скидка. Доказанный ноль/неприменимость
даёт обычную цену; null/отсутствующая скидка допустимы как отсутствие только
при валидном полном расчёте. Схема с неизвестным состоянием — ошибка.
Не использовать priceWithDiscount: он может выбрать другую банковскую скидку.
Не использовать raw wallet как готовую кошелёчную цену и не вычислять min цен.

Суммы неотрицательны, конечны, RUB; priceToShow — безопасные целые копейки.
Из JSON строки читаются через Decimal. При наличии скидки её повреждение
не маскируется обычной ценой. Публичные MarketplaceCard/serialization/history
не получают обычную цену, скидку или дополнительные цены в extensions.

Наличие — выбранный size.stocks и подтверждённая семантика соответствующего
ответа. Пустой достоверный stocks → out_of_stock/null; отсутствующая информация
→ unknown. Отсутствующий выбранный optionId — ошибка схемы до доказательства
удаления. Не брать totalQuantity другого размера или root вместо nmId.

Название, продавец и рейтинг берутся из совпадающего товара; reviewRating —
рейтинг отзывов, feedbacks — их число. Варианты размеров имеют ref nmId:optionId.
Опциональные metadata доступны через штатный static-product путь WB, включая
`getProductColorsByNmIdsAsync` для характеристик. Использовать только поля,
предоставленные доступным источником; при отсутствии изображения/описания
оставить null/пустую строку, без угадывания basket-хостов и nav к товару.

### Consumers

WB убрать из pending connectors и зарегистрировать в builder; проверить
direct collect, queued API/desktop worker, расписание и retry. В UI обновить
single/bulk refresh и карточку деталей; mock отражает пары размеров, но его
E2E не считается проверкой live. API create/update URL/import используют общий
validator. ProductService lookup остаётся database-free. Rust invoke/lifecycle
не требуют смены интерфейса: Python builder использует существующий session.
Числовой Ozon main.py, raw/output и оба CLI imports проверяются отдельно.

## Migration Plan

Data-only Alembic revision без сетевых запросов: preflight всех WB numeric
строк, валидные пары вычислять только из соответствующей сохранённой ссылки
с единственным size. Уже канонические пары сохраняются. Конфликты вычисленных
ключей проверяются до UPDATE. Неопределённые строки пропускаются; get_product
сообщает «Не указан размер» до сети. Они не превращаются в успешный out_of_stock.

Не менять локальные IDs/FK, истории, snapshots, группы, теги и run targets.
Старый numeric-only импорт отклоняется, legacy fallback не добавляется.
Проверять миграцию только на disposable TEST_DATABASE_URL. Исправлять вперёд,
не сохранять старое решение как rollback и не удалять пользовательские данные.
Рабочая БД не используется для исследования/проверок.

## Risks / Trade-offs

- Внутренние функции WB меняются → изолированный bridge, version-independent
  feature detection, fixtures и явная schema error; нет fallback к DOM-цене.
- Ложный ноль при старте → readiness barrier и отдельные ошибки grade;
  проверить cold/stale cache и авторизованное состояние синтетически.
- Site retries и AbortSignal → перехват/учёт фактических попыток, synthetic
  tests cooldown/cancel/deadline до признания транспорта готовым.
- Новая размерная идентичность → безопасный preflight, никакого угадывания.
- Не все optional metadata доступны → общий контракт допускает пустые поля;
  отсутствие описания не должно менять цену и её источник.
- Repowise MCP/CLI risk продолжают возвращать старый индекс другого проекта
  даже после локального index-only update → риск не считается оценённым;
  критичные пути проверены CodeGraph/current source, fallback явно фиксируется.

## Verification

Очищенные fixtures + parser/mapper/identity tests: wallet/ordinary/zero/null,
неприменимость/лимиты/флаги, незавершённая загрузка, malformed/non-RUB,
несколько размеров/одинаковые подписи, mismatch/duplicate, stocks и optional.
Browser synthetic tests используют настоящий Chrome и управляемые ответы;
проверяют site retries, HTTP 498/403/429, отмену, готовность скидки, shared
Ozon/Ali/WB session и сохранение synthetic cookie после штатного закрытия.

Disposable PostgreSQL: migration preflight/all-or-nothing, неразрешимые старые
карточки без изменений, API validation/duplicates/transfer, смешанный запуск,
неизменная цена без дубля истории. Frontend unit/lint/build/demo E2E; Python
suite, numeric CLI без DATABASE_URL, оба imports. Проверить native desktop
single/mixed collection в изолированном окружении. Live probe WB с выбранным
размером и сравнение одной цены с витриной; Ozon/Ali smoke для регрессии.
Проверки, которые недоступны, явно перечислить. Второй review — до финализации.
