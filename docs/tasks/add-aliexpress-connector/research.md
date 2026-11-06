# AliExpress.ru: пробный товарный JSON

Исследование 2026-10-26. Это evidence этапа планирования, не реализация коннектора.

## Проверенная ручка

```http
GET https://aliexpress.ru/aer-jsonapi/v1/bx/pdp/web/productData?productId=1005009868651525&sourceId=0&sku_id=12000061135122688
```

Маршрут найден в JavaScript самой витрины:
`https://st.aestatic.net/mixer/widgets/bx/GlowAsyncProductContextWidget/0.15.1/system/GlowAsyncProductContextWidget.js?cache=0`.
Код виджета вызывает `fetch` с productId/sourceId/sku_id. Для Choice-канала
добавляет `channel=choice`; этот режим здесь не проверялся.

Успешный запрос выполнен через `page.evaluate` в существующей Chrome-сессии
профиля price-watch после ручного прохождения CAPTCHA пользователем. Вызов:

```javascript
const response = await fetch(
  '/aer-jsonapi/v1/bx/pdp/web/productData?productId=1005009868651525&sourceId=0&sku_id=12000061135122688',
  { credentials: 'include', signal: AbortSignal.timeout(30000) },
);
const raw = await response.text();
```

HTTP 200, Content-Type `application/json`, длина текста 23 257 символов.
Корень — `{ "data": { ... } }`. `hasUserPersonalData=false`.
Секреты, cookies, заголовки авторизации, адрес доставки и полный session state
в evidence не сохраняются. Временный диагностический скрипт не является частью
приложения.

## Доступ и ручная проверка

Прямой HTTP GET карточки и первые браузерные попытки вернули CAPTCHA:
документ HTTP 200 перенаправляет на `_____tmd_____/punish`, проверка — HTTP 429.
Это не отсутствие товара. Первоначальная ручная проверка в браузере,
запущенном Playwright launch_persistent_context, не прошла. Затем Chrome
запущен существующим lifecycle AsyncOzonClient: обычный внешний процесс,
профиль price-watch и подключение CDP с no_defaults. Пользователь подтвердил:
«Вот теперь прошло». Из одного опыта нельзя доказать причину различия.

Первоначальная карточка содержит `window.__AER_DATA__`, в том числе
GlowAsyncProductContextWidget с id/name/activeSkuId/sourceId. В этом bootstrap
price/quantity/skuInfo/rating были null — полноценные данные пришли из ручки.

## Повторение без открытия карточек

В той же сессии открыта отдельная главная страница `https://aliexpress.ru/`
(HTTP 200). С неё последовательно выполнены три fetch:

| sku_id | HTTP | data.activeSkuId | Число SKU |
| --- | --- | --- | --- |
| 12000061135122688 | 200 | 12000061135122688 | 2 |
| 12000061135122692 | 200 | 12000061135122692 | 2 |
| параметр отсутствует | 200 | 12000061135122688 | 2 |

Network listener после открытия главной зафиксировал 3 productData-запроса и
0 навигаций к `/item/`. Это подтверждает возможность session JSON transport
для данного товара. Параллелизм, восстановление после перезапуска, другие
товары, удалённые/недоступные товары и CAPTCHA на самой ручке пока не проверены.
Постоянство выбора SKU при отсутствии параметра не гарантируется.

## Фактические поля

Товар `1005009868651525`:
«Смартфон OnePlus 16, 12/256ГБ, 12/512ГБ, 16/512ГБ, 16ГБ/1ТБ, china».
Выбранный SKU `12000061135122688`, sellerId `250824946`, sourceId `0`.

| Поле | Наблюдение |
| --- | --- |
| skuInfo.priceList[].activityAmount | 79 316 RUB, cents="7931600" |
| skuInfo.priceList[].amount | 122 312 RUB, cents="12231200" |
| skuInfo.priceList[].priceWithCoupon.amount | 77 648 RUB, cents="7764800" |
| priceWithCoupon.isCouponAssigned | false |
| skuInfo.priceList[].availQuantity | 1 для каждого из двух SKU |
| quantity.totalCount | "2" — общий остаток, не остаток выбранного SKU |
| rating.middle | 4.8 |
| reviews | "22" |
| characteristics | [] |
| gallery | массив изображений |
| description | короткий SEO-текст, не полное описание |
| storeUrl | null в productData; информация магазина есть в bootstrap |
| itemStatus | 0; значения других состояний не исследованы |

Оба SKU имеют одинаковые наблюдавшиеся цены, но разные идентификаторы.
У выбранного SKU skuPropIds="337903,357418". В propertyList встречается
расхождение: name="Красный", displayName="Black"; комплект name="Комплект 1",
displayName="12GB 256GB". Второй цвет displayName="Silver Gray".
Нельзя исправлять или выводить характеристики из названия товара; нужно
согласовать использование исходных displayName для названий вариантов.

Поле customsFee содержит отдельную строку «Таможенная пошлина ≈8 041 ₽».
Это текст витрины, не вычисление приложения и не юридическая оценка. Не
прибавлять его к товарной цене без согласованного требования.

## Решения перед планированием

Пользователь определил цену: возвращать и сохранять **только одну** цену,
выбирая по наличию источника в следующем порядке для выбранного SKU:
`priceWithCoupon.amount` → `activityAmount` → `amount`.
Не вводить дополнительные публичные/исторические цены или отдельное хранение
купонной цены. Значение `isCouponAssigned=false` не исключает купонную цену;
получение/применение купона не является действием коннектора. Для пробного
ответа единственная выбранная цена — 77 648.00 RUB. Точность — из cents через
Decimal. Отсутствие поля допускает следующий источник; повреждённые значения
нельзя молча маскировать другим источником. Существующее правило отсутствия
текущей цены при OUT_OF_STOCK сохраняется.

Пользователь выбрал «Конкретного SKU». Автоматическая подмена отсутствующего
SKU соседним недопустима. Предлагаемая идентичность external_id — productId:skuId;
детали в ADR 0008 и OpenSpec add-aliexpress-connector. Это проект технического
решения, а не одобрение реализации. Имя seller не приходит из productData:
план использует seller=null без дополнительных навигаций ради обогащения.
Код приложения и пользовательская БД не изменялись.
