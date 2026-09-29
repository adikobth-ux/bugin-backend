# Bugin API v1 — контракт

Единственный источник правды для сервера (`bugin-backend`) и приложения (`bugin`, папка
`lib/services/api`). Меняется только вместе с тестами на обеих сторонах.

Места и события приходят из каталога, который ведётся в админке (`/admin`). В пустую базу
сервер один раз заводит тестовые данные прототипа (8 мест, 8 событий); их удаляют в админке.
Входа и личных данных пока нет: избранное, профиль и история поиска хранятся на телефоне;
`/v1/me/*` и вход появятся позже.

## Общее

- Базовый адрес: `https://<хост>/v1`. Всё — JSON в UTF-8, ключи в `camelCase`
  (совпадают с `toJson()` моделей приложения).
- Язык ответа — заголовок `Accept-Language`: значение, начинающееся с `kk`, → казахский,
  всё остальное (или нет заголовка) → русский. Тексты контента (названия, описания,
  причины, подписи плана) приходят на этом языке. Коды (`category`, `code`, `role` …) от языка
  не зависят.
- Где пользователь — заголовок `X-Bugin-Location: <широта>,<долгота>` (например
  `51.128,71.430`, приложение округляет до ~100 м). Тогда `distanceKm` и `taxiMinutes` во всех
  ответах, «рядом», подбор и план вечера считаются от него. Нет заголовка, он непонятный или
  точка дальше 60 км от города — от центра Астаны. Заголовок, а не параметры адреса: координаты
  не попадают в журналы запросов.
- Время — местное время города (Asia/Almaty, UTC+5) **без смещения**:
  `"2026-10-03T20:00:00"`. Приложение показывает его как есть.
- Даты без времени — `YYYY-MM-DD`.
- Ошибки: HTTP-статус + тело `{"error": {"code": "not_found", "message": "…"}}`.
  Коды: `not_found` (404), `bad_request` (400, 422), `internal` (500).
- `GET /health` → `{"status": "ok", "storage": "postgres"}` (без `/v1`; `storage: memory` —
  база не подключена). Базу не трогает, поэтому годится для частых проверок.
- Интерактивная документация сервера: `/docs`, схема: `/openapi.json`.

## Модели

### Place

```json
{
  "id": "the_garden",
  "name": "The Garden",
  "subtitle": "Европейская кухня и завтраки весь день",
  "description": "…",
  "category": "cafe",
  "categoryDetail": "европейская кухня",
  "address": "ул. Абая, 57",
  "phone": "+7 700 123 45 67",
  "rating": 4.8,
  "reviewsCount": 1540,
  "priceLevel": 2,
  "averageCheck": 6000,
  "openingHours": {"opensAt": 480, "closesAt": 1380},
  "photos": ["assets/images/place_the_garden.jpg"],
  "tags": ["Европейская кухня", "Завтраки"],
  "amenities": [{"type": "wifi", "value": "Бесплатный"}],
  "distanceKm": 1.5,
  "taxiMinutes": 6,
  "bookingType": "table",
  "bookingUrl": null,
  "pitch": "Уютно, живая зелень и тихая музыка",
  "goodFor": ["date", "friends"],
  "vibes": ["beautiful", "calm"],
  "location": {"lat": 51.1283, "lng": 71.4305},
  "reviews": [{"author": "Алина", "rating": 5.0, "text": "…", "date": "2026-09-27T12:00:00"}]
}
```

- `category`: `cafe | coffeeShop | restaurant | bowling | cinema | park | gallery | studio`.
- `amenities[].type`: `wifi | sockets | pets | smoking | payment | parking`.
- `bookingType`: `table | ticket | lane | none`. `bookingUrl` — где купить билет
  (Kino.kz, Ticketon) или забронировать; Bugin сам ничего не продаёт.
- `openingHours` — минуты от начала суток; `closesAt` > 1440, если закрывается после полуночи.
- `goodFor`: `date | friends | work | family | solo`; `vibes`: `beautiful | calm | active | novelty`.
- `photos` — https-ссылки на фото из админки (`https://<хост>/v1/images/<id>.jpg`); у тестовых
  данных — пути к картинкам внутри приложения (`assets/images/...`). Первое фото — главное.
- `distanceKm` и `taxiMinutes` сервер считает от пользователя (`X-Bugin-Location`), без него —
  от центра Астаны (Байтерек). `priceLevel` (1–4) — по `averageCheck`: до 3 000, 7 000, 15 000 ₸.

### Event

```json
{
  "id": "neon_nights",
  "title": "Neon Nights",
  "subtitle": "…",
  "description": "…",
  "category": "concert",
  "startsAt": "2026-10-03T20:00:00",
  "durationMinutes": 180,
  "venueName": "…",
  "address": "…",
  "location": {"lat": 51.09, "lng": 71.41},
  "distanceKm": 2.4,
  "priceFrom": 12000,
  "image": "assets/images/event_neon_nights.jpg",
  "tags": ["…"],
  "ageLimit": 16,
  "tickets": [{"name": "Танцпартер", "price": 12000}],
  "pitch": "…",
  "reasons": ["…"],
  "occasions": ["friends", "date"],
  "vibes": ["active"],
  "venuePlaceId": null,
  "ticketUrl": "https://ticketon.kz/astana",
  "isFeatured": true
}
```

- `category`: `concert | cinema | theatre | exhibition | workshop | standup`.
- `image` может быть пустой строкой (нет картинки); фото из админки — https-ссылка, как у мест.
- `priceFrom` — самая дешёвая категория `tickets` (если категорий нет — задаётся в админке).
- `venuePlaceId` — место из каталога; если его удалили или скрыли, приходит `null`.
- `ticketUrl` — страница покупки у оператора; `null` — билеты ещё не продаются.

### SearchIntent и IntentParam

```json
{
  "query": "Свидание вечером до 10 000",
  "params": [
    {"type": "occasion", "code": "date", "inferred": false},
    {"type": "time", "code": "evening", "inferred": false},
    {"type": "budget", "code": "10000", "inferred": false},
    {"type": "location", "code": "near", "inferred": true}
  ]
}
```

- `type`: `occasion | time | budget | mood | location`.
- Коды: `occasion` — как `goodFor`; `time` — `morning | day | evening | night`;
  `budget` — сумма в тенге строкой или `any`; `mood` — `beautiful | calm | active | novelty`;
  `location` — `near | center | any`.
- `inferred: true` — параметра не было в запросе, сервер додумал его сам.
- Порядок параметров — occasion, time, budget, mood, location (отсутствующие пропускаются).

### Recommendation

```json
{
  "kind": "place",
  "place": { …Place… },
  "event": null,
  "reason": "Уютно, живая зелень и тихая музыка — в рамках бюджета",
  "details": ["…", "…"],
  "score": 58.0
}
```

- `kind`: `place | event`; заполнено ровно одно из `place` / `event`.

### EveningRequest, Scenario, PlanStop, TravelLeg

Как `toJson()` в `lib/models/evening_request.dart` и `lib/models/scenario.dart`:

```json
{
  "company": "pair", "day": "today", "date": null, "startMinutes": 1140,
  "budget": 15000, "mood": "calm", "wishes": ""
}
```

- `company`: `solo | pair | friends | family`; `day`: `today | tomorrow | weekend | date`;
  `date` — `YYYY-MM-DDT00:00:00` или `null`; `budget` — число или `null` («не важен»);
  `mood`: `calm | active | novelty | culture`.

```json
{
  "id": "plan_1790626000000",
  "title": "Спокойный вечер вдвоём",
  "subtitle": null,
  "image": null,
  "stops": [
    {
      "role": "coffee", "placeId": "coffee_lab", "kind": "coffee",
      "title": "Coffee Lab", "kindLabel": "Кофе и десерт",
      "startMinutes": 1140, "durationMinutes": 60, "cost": 4500,
      "routeLabel": null, "rating": 4.7, "image": "assets/images/place_coffee_lab.jpg"
    }
  ],
  "legs": [{"mode": "walk", "minutes": 10}],
  "tags": [],
  "request": { …EveningRequest… }
}
```

- `role`: `coffee | walk | dinner | activity | culture | novelty | work`.
- `kind` — код занятия: `coffee | walk | dinner | dinner_view | bowling | cinema | exhibition |
  workshop | coffee_work`; `kindLabel` — его подпись на языке ответа.
- `legs[i]` — переезд от `stops[i]` к `stops[i+1]`; `mode`: `walk | taxi`.
- `rating` у бесплатных мест (набережная) — `null`.

## Запросы

| Метод и путь | Параметры / тело | Ответ |
|---|---|---|
| `GET /v1/places/nearby` | `limit` (по умолчанию 6); `lat`, `lng` — вместо заголовка `X-Bugin-Location`, необязательно | `Place[]` от ближайшего |
| `GET /v1/places` | `ids=a,b,c` | `Place[]` в порядке `ids`, неизвестные пропускаются |
| `GET /v1/places/{id}` | — | `Place` или 404 |
| `GET /v1/events` | `day=today\|tomorrow\|weekend\|date`, `date=YYYY-MM-DD` (для `day=date`), `category` — необязательно | `Event[]` по времени начала |
| `GET /v1/events` | `ids=a,b,c` (вместо `day`) | `Event[]` в порядке `ids` |
| `GET /v1/events/featured` | — | `Event[]`: `isFeatured` в ближайшие 7 дней |
| `GET /v1/events/{id}` | — | `Event` или 404 |
| `GET /v1/events/{id}/similar` | `limit` (по умолчанию 4) | `Event[]`: сначала той же категории, затем по времени; без самого события |
| `POST /v1/search/understand` | `{"query": "…"}` | `SearchIntent` |
| `POST /v1/search/recommend` | `{"intent": SearchIntent}` | `Recommendation[]` по убыванию `score` |
| `GET /v1/search/surprise` | — | `Recommendation` — случайный хороший вариант |
| `POST /v1/evening/plan` | `EveningRequest` | `Scenario` |
| `POST /v1/evening/alternatives` | `{"scenario": Scenario, "index": 0}` | `PlanStop[]` — замены точки в рамках бюджета |
| `POST /v1/evening/replace` | `{"scenario": Scenario, "index": 0, "stop": PlanStop}` | `Scenario` с пересчитанным временем |
| `GET /v1/evening/featured` | — | `Scenario` для блока «Для тебя сегодня» |
| `POST /v1/evening/localize` | `{"scenario": Scenario}` | тот же `Scenario` на языке запроса |
| `GET /v1/images/{id}.jpg` | — | JPEG до 1600 px; `Cache-Control: immutable` — ссылка не меняется |

### Правила

- **Дни афиши** (`day`), считая от сегодняшней даты в Asia/Almaty: `today` — сегодня; `tomorrow` —
  завтра; `weekend` — суббота и воскресенье от сегодня до ближайшего воскресенья включительно;
  `date` — указанная дата.
- **Понимание запроса** — `MockSearchService.parse` (ключевые слова на русском и казахском).
  Если время не названо, `time` = `evening` при часе ≥ 16, иначе `day`, `inferred: true`.
  Если место не названо, `location` = `near`, `inferred: true`.
- **Подбор** — `MockSearchService.rank`: парки не выдаются; фильтры по бюджету, поводу,
  часам работы; события — только сегодняшние; счёт: рейтинг×10, +10 за повод, +8 за
  настроение, −4×км при `near`.
- **Скрытые** в админке места и события не приходят ни в одном запросе, в том числе по `ids`.
- **Вечер** — шаблоны по настроению (как `MockEveningPlanner`), места на роли подбираются
  из каталога по категории: кофе — кофейни, затем кафе; ужин — кафе и рестораны (ресторан
  с отметкой «красиво» — «ужин с видом»); прогулка — парки; активность — боулинг и кино;
  культура — галереи, затем кино; новое — студии, затем боулинг; рабочий день — кофейни и кафе
  с Wi-Fi и розетками. Внутри роли — по рейтингу и близости, до 5 вариантов. Перебор в рамках
  бюджета, расписание с округлением до 15 минут, переезды пешком (≤ 0,8 км по улицам) или на такси.
  Если для «Для тебя сегодня» в каталоге не нашлось ни одного места — 404 `not_found`.
