# Tasks

## 1. Идентичность и сохранённые данные

- [x] 1.1 Добавить WildberriesRef nmId:optionId и общий application validator, обновить все consumers прежнего Ali entry point и удалить его; identity/API unit tests проверяют ASCII, безопасный JS-диапазон, size URL, несовпадения и дубликаты без регрессий Ali/Ozon.
- [x] 1.2 Добавить data-only migration с preflight и обновить create/update/import/export WB validation; disposable PostgreSQL tests доказывают сохранение ID/history/settings/run targets, конфликт до UPDATE и неизменность записей без размера. Подготовить заметку миграции для review.

## 2. WB JSON и одна цена

- [x] 2.1 Добавить WB client/transport с homepage bootstrap и подтверждённой готовностью grade для текущего auth-состояния; browser tests проверяют cold/stale cache и исключают нулевую скидку до готовности, HTTP/schema ошибки не подменяются обычной ценой.
- [x] 2.2 Добавить WB runtime bridge с detail JSON, per-request AbortSignal, deadline, общим лимитом фактических попыток и Retry-After cooldown, включая повторы витрины; transport/browser tests проверяют 403/498/429, malformed/HTML, отмену одной цели, восстановление и отсутствие product goto.
- [x] 2.3 Реализовать parser/mapper/connector для точного nmId/optionId, наличия и единственной wallet→ordinary цены; очищенные fixtures и tests проверяют 1056−32=1024, иной процент/округление, неприменимость/лимит/флаги, стороннюю банковскую скидку, null/zero/malformed/non-RUB и несколько размеров. Serialization test исключает вторую цену и её копии в extensions/snapshot.
- [x] 2.4 Подключить доступные title/seller/reviewRating/feedbacks/attributes и варианты размеров из источников WB; tests проверяют пустые optional fields, выбранный вариант и уникальные ref, а исследовательская заметка фиксирует фактически полученные metadata без угадывания basket-хостов.

## 3. Пути сбора и интерфейс

- [x] 3.1 Зарегистрировать WB в builder и убрать из pending, проверить single/mixed Ozon+Ali+WB lifecycle; tests доказывают один Chrome, независимую отмену/проверки и сохранение профиля. Direct collect и queued worker integration tests дают одинаковую одну цену без дублирования history.
- [x] 3.2 Добавить ввод артикула/кода размера и разбор ссылки ?size=, включить WB single/bulk refresh в UI и обновить mock; frontend unit и demo E2E проверяют точный размер, URL mismatch, ошибки и доступность действий. Подготовить изменения руководства WB для review.
- [x] 3.3 Проверить schedule/retry/API/transfer и старую WB-карточку без размера в смешанном запуске; disposable integration tests доказывают индивидуальную ошибку до сети, неизменную историю/поля и успешные соседние цели.

## 4. Интеграционная проверка и review

- [x] 4.1 Выполнить Python suite, applicable frontend lint/unit/build/demo E2E, numeric Ozon CLI без DATABASE_URL и оба CLI imports; записать выполненные команды, реальные результаты и недоступные проверки в verification.md.
- [x] 4.2 Выполнить isolated native desktop single/mixed smoke, live WB с выбранным размером и сравнением кошелёчной цены с витриной, live Ozon/Ali regression smoke; подтвердить штатное освобождение профиля, не использовать рабочую БД для тестов.
- [x] 4.3 Проверить diff, контракты/миграцию, новые test gaps и ограничения Repowise; представить изменённые файлы, evidence, риски и подготовленные документы пользователю для второго review. Реализация остаётся непринятой до явного ответа.

## Workflow follow-up

- После явной приёмки обновить только затронутые руководства, принять ADR 0009,
  синхронизировать delta specs и архивировать change по vibe-flow.
- Проверить staged diff, включить все task-only изменения и создать Git commit(s),
  проверить хеши; не выполнять push/merge без отдельного разрешения.
