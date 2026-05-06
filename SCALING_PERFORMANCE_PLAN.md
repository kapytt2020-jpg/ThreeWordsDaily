# Spaceland Mini App Scaling & Performance Plan (80k users, 100k stores, ads, social + chat + web3)

## 1) Target SLOs (what “flies” means)

- **Cold start (no cache):** first meaningful paint < 1.2s, interactive < 2.0s.
- **Warm start (with cache):** first meaningful paint < 500ms, interactive < 1.2s.
- **Map pan/zoom latency:** new markers visible < 300ms median, < 800ms p95.
- **API p95:** bootstrap < 250ms, viewport query < 400ms.
- **Crash-free sessions:** > 99.8%.
- **Target load:** 80k real users, 100k stores, 100k+ events/promos/ads, realtime location/social/chat traffic.
- **WebView long tasks (>50ms):** < 5 per first 10s.

## 2) Architecture principle

- Shell-first rendering.
- Load only current screen.
- Fetch details on click.
- Realtime sends deltas, not full snapshots.
- All heavy modules (chat history, wallet SDK, market, 3D, NFT metadata) are lazy and never block map first render.

## 3) Frontend loading strategy

### 3.1 Critical path (strict)
Only this can block first render:

1. Session validation/light auth.
2. Feature flags/config (small payload).
3. Current location state (or fallback city).
4. Map shell + placeholders + cached viewport.
5. First viewport query (limited points/clusters).

### 3.2 Warm path (after first render)
- Nearby friends previews.
- Event previews.
- Notification count refresh.
- Non-critical analytics dispatch.

### 3.3 Cold path (on user intent)
- Chat list and message history.
- Wallet SDK initialization + balances.
- NFT metadata.
- Market product feeds.
- Full profile and group feeds.

## 4) API contracts

### 4.1 Bootstrap
`GET /bootstrap`

Return only:
- user id/name/avatar thumb
- tab badge counts (unread/cart/notifications)
- feature flags
- minimal config versions

Hard limit: **<= 50 KB JSON compressed**.

### 4.2 Viewport data
`GET /map/viewport?bbox=...&zoom=...&types=stores,events,friends&limit=120&cursor=...`

Rules:
- Never return “all stores/events”.
- Server-side clustering when zoomed out.
- Cursor pagination for dense areas.
- Distinct summary DTO for list/map (no heavy descriptions).

Hard limit: **<= 200 KB JSON compressed**.

### 4.3 Details on click
`GET /places/:id`, `GET /events/:id`, `GET /users/:id`

Full payload only here.

## 5) Backend data & indexing

- PostGIS (or equivalent) for geospatial index.
- BTree/GIN for common filters (category/time/open_now).
- Tile/grid cache (Redis) keyed by `(zoom, tile_x, tile_y, filters_hash)`.
- TTL 30–120s for viewport hot tiles.
- Invalidation pipeline on place/event changes.

### Query model
- `bbox + limit + cursor` as default.
- `radius` mode for “near me” fallback.
- Cluster aggregation query for low zoom.

## 6) Realtime architecture

- Topic-based subscriptions:
  - `user:{id}:notifications`
  - `user:{id}:chat-deltas`
  - `map:{tile-or-geohash}:delta`
- Push only diffs:
  - entity created/updated/deleted
  - unread count changed
- Client applies incremental updates to local cache.

## 7) Media pipeline

- Upload original once.
- Generate variants: 64/128/256/512/1024.
- Convert to WebP/AVIF.
- CDN delivery + immutable cache headers.
- API returns thumb URLs for lists/maps.
- Preload only above-the-fold assets.

## 8) Frontend performance engineering

- Route-level code splitting for every tab.
- Dynamic import for wallet/chat/market/3D.
- Virtualized lists everywhere.
- Map markers rendered via canvas/WebGL layer (not hundreds of rich DOM nodes).
- Debounced viewport fetch (e.g., 120–200ms after movement ends).
- Request cancellation with AbortController on rapid pan/zoom.
- Memoization + stable keys to prevent full rerenders.

## 9) Guardrails & budgets in CI/CD

Fail pipeline if exceeded:
- Initial JS bundle > 500KB gzip.
- Bootstrap endpoint > 50KB compressed.
- Viewport payload > 200KB compressed.
- First screen image bytes > 2MB total.
- Main thread long tasks budget exceeded in synthetic run.

## 10) Observability

### Frontend RUM
- FCP, LCP, INP, TTI, long tasks, JS heap.
- Per-screen timings (map/chat/wallet/market).
- “blank screen duration” metric.

### Backend APM
- p50/p95/p99 latency by endpoint.
- DB query timing + rows scanned.
- Cache hit ratio for tiles/viewport.
- Websocket message volume per topic.

### Alerting
- Error rate > 1% for 5 min.
- p95 viewport latency > 700ms.
- Blank screen metric > 1s p95.

## 11) Security/perf for Web3

- Wallet connect not in startup path.
- Batch RPC calls.
- Cache balances/NFT summaries with TTL.
- Timeout + fallback provider strategy.
- Never block core UX on chain/RPC delays.

## 12) Rollout plan (6 weeks)

### Week 1: Baseline & bottlenecks
- Record real WebView traces.
- Add RUM + APM dashboards.
- Freeze current budgets and set red lines.

### Week 2: Startup path refactor
- Implement shell-first boot.
- Move non-critical modules to lazy imports.
- Add skeletons and cached last viewport rendering.

### Week 3: Map API refactor
- Introduce viewport endpoint + cursor.
- Implement clustering + geospatial indexes.
- Add tile/viewport Redis cache.

### Week 4: Media + rendering
- Deploy media variants/CDN strategy.
- Replace heavy DOM marker rendering with canvas/WebGL markers.
- Add virtualized lists.

### Week 5: Social/chat/web3 isolation
- Delta-based realtime channels.
- Chat unread-only on startup.
- Wallet startup isolation + deferred RPC.

### Week 6: Hardening & load test
- Load tests at target scale (10k stores / 100k events / high concurrent users).
- Tune DB indexes and cache TTL.
- Canary rollout 10% -> 50% -> 100%.

## 13) Acceptance checklist

- [ ] No blank content screen on startup.
- [ ] Map usable before chat/wallet/market initialization.
- [ ] Viewport requests return only visible data and are paginated.
- [ ] Cluster mode active on low zoom.
- [ ] Cold and warm start SLOs met in production-like tests.
- [ ] CI blocks regressions on bundle/payload/perf budgets.

## 14) Anti-patterns to ban

- `loadEverything()` in app root.
- Importing wallet/chat/market SDKs in entrypoint.
- Returning full entity payloads in list endpoints.
- Rendering hundreds of rich DOM markers.
- Full refresh websocket events that resend large collections.


## 15) Spaceland-specific execution (https://spaceland.ink)

Because this plan is for **Spaceland**, enforce these product-level rules immediately:

- **Map tab is the only startup-critical tab** in the mini app shell.
- **Chat, Market, Profile, Groups, Wallet/Web3 are deferred** until the user opens them.
- If viewport API is slow, show:
  1) last cached viewport markers/clusters,
  2) skeleton cards,
  3) stale badge (“Updating nearby data…”).
- Never show an empty white content area while waiting for network.

### 15.1 Spaceland startup contract (hard)

On open, allow only:
1. `GET /bootstrap` (user + counters + flags)
2. `GET /map/viewport` for current map window
3. static shell assets (icons/fonts already cached where possible)

Disallow on startup:
- wallet SDK init
- chat inbox/history fetch
- market feed fetch
- NFT metadata fetch
- group feed fetch
- full friends/profiles fetch

### 15.2 Spaceland API envelope targets

For real-world mobile WebView reliability, set these strict ceilings:

- `/bootstrap` <= **30KB compressed**
- `/map/viewport` <= **150KB compressed**
- first-screen images <= **1.2MB total transferred**
- max entities returned per viewport response: **120** (clusters + points total)

### 15.3 Spaceland release gates (must pass before deploy)

- p95 cold-start interactive <= 2.0s on iPhone mid-tier device over 4G.
- p95 blank-screen duration <= 200ms.
- p95 viewport refresh <= 700ms.
- JS entry bundle <= 450KB gzip.
- No startup network calls to wallet/chat/market endpoints (verified by trace).

### 15.4 72-hour emergency stabilization plan

**Day 1**
- Add startup request allowlist and block all non-critical fetches.
- Render shell + skeleton immediately.
- Add AbortController cancellation for map movement fetches.

**Day 2**
- Switch map endpoint to strict bbox + limit + cursor.
- Enable server-side clustering for zoomed-out levels.
- Return thumb-only images in list/map payloads.

**Day 3**
- Add cached viewport restore on launch.
- Enable perf dashboards/alerts for blank-screen and startup latency.
- Run canary (10%) and compare p95 before full rollout.


## 16) Current failure mode from screenshots: zoom-out + shop-open freeze

The screenshots show two separate bugs that must be treated as production blockers, not just “slow loading”:

### 16.1 Zoom-out map collapse

Symptoms:
- When the user zooms out, markers, labels, banners, and event cards overlap until the map becomes unreadable.
- Sometimes the map turns into an almost empty/dark shell with only side buttons and bottom navigation visible.
- Data eventually appears again, which means the UI is probably waiting for a heavy viewport refresh or losing the render layer during map state changes.

Likely root causes:
- Too many rich DOM markers/labels rendered at the same zoom level.
- No hard zoom-level density rules (points vs clusters vs heatmap vs hidden labels).
- Multiple map requests racing; an old slow response overwrites a newer viewport state.
- No request cancellation when the user pans/zooms rapidly.
- Map layer state is replaced with “empty loading” instead of keeping last good data until new data arrives.
- Banner/ad overlays are treated like normal points and fight with stores/events for z-index and space.

Required fixes:
- Use a **map render state machine**: `ready`, `refreshing`, `stale`, `error`, never `blank` after the first successful viewport.
- Keep the **last good viewport** visible while the next viewport is loading.
- Cancel old viewport requests with `AbortController` and ignore stale responses by `requestId`.
- At zoomed-out levels, show clusters/heatmap only; hide individual labels and cards.
- Only render a full rich card for the selected item; all non-selected stores/events are lightweight points or clusters.
- Put ads/promos into a separate quota-limited layer, not the same pool as stores/events.

### 16.2 Shop-open freeze / navigation lock

Symptoms:
- Opening Shop/Market can make the app feel frozen.
- Buttons become unclickable until the user switches through bottom navigation to Profile/Hub and back.

Likely root causes:
- Market module blocks the main thread with image/product rendering or synchronous state initialization.
- A modal/overlay/backdrop remains above the app with wrong `z-index` or `pointer-events` after shop transition.
- Tab transition waits on market data before releasing navigation interactions.
- Market fetch/render shares global loading state with Map and disables controls.

Required fixes:
- Navigation must never be disabled by screen data loading.
- Market screen loads as `shell -> skeleton -> data`; it must not block bottom bar taps.
- Every overlay must have an owner and cleanup on route change.
- Add an automated check: after opening Market, all bottom nav buttons must still receive pointer events.
- Move product image decode/rendering off the critical interaction path; virtualize product grids.

## 17) Spaceland map density rules

For 100k stores + ads + events, the map cannot display every label/card. Use zoom-based rendering contracts:

| Zoom / density | Stores/events | Labels | Ads/banners | People | Route trails |
| --- | --- | --- | --- | --- | --- |
| City / far zoom | clusters + heatmap | hidden | max 1–3 sponsored regional banners | hidden or aggregate counts | hidden |
| Neighborhood | clusters + top N points | only selected/high-priority | max 3–5 per viewport | friends clusters only | selected friends only |
| Street / close zoom | visible points up to cap | labels for top priority + selected | max 1–2 per screen area | allowed by privacy ACL | selected users/routes |
| Detail selected | selected card only | selected label | contextual ad if relevant | selected profile/route | selected route segment |

Hard caps per viewport response:
- max total map drawables: **120**
- max rich cards: **1 selected + 2 previews**
- max visible text labels: **30**
- max ad banners: **5**
- max people markers: **50** after privacy filtering

If the backend has more entities than the cap, it must return clusters, ranked summaries, or cursors — never dump all entities.

## 18) Social platform scale: 80k users without freezing

### 18.1 Service boundaries

Spaceland should be logically split even if deployed as a modular monolith first:

- **Identity/Profile service:** user profile, avatar, privacy settings.
- **Map/Discovery service:** stores, events, ads, clusters, viewport queries.
- **Location service:** live location, route sharing, place history, privacy filtering.
- **Chat service:** conversations, messages, attachments, unread counters.
- **Social graph service:** friends, follows, blocks, close friends, groups.
- **Ads service:** sponsored placements, frequency caps, targeting, reporting.
- **Media service:** upload, variants, CDN URLs.
- **Realtime gateway:** websocket sessions, topic subscriptions, fanout.
- **Notification service:** push/in-app counters and delivery receipts.

The frontend can still look like one app, but data ownership and realtime fanout cannot be one giant endpoint.

### 18.2 Capacity assumptions

For 80k users, design for:
- 10k–25k concurrent online users at peak.
- 5k–15k concurrent websocket connections.
- 1k–5k viewport queries per minute during movement/zoom bursts.
- 500–2k location updates per second if many users share live location.
- 100–1k chat messages per second during peaks.

These numbers require:
- stateless API workers behind a load balancer,
- Redis for hot cache/rate limits/presence,
- a durable event bus (Kafka/PubSub/NATS/RabbitMQ) for chat/location/notification fanout,
- horizontally scaled websocket gateways,
- database read replicas for heavy read paths.

## 19) User location privacy and route sharing

Spaceland needs privacy as a first-class data filter before anything reaches the map.

### 19.1 Visibility modes

Each user controls map visibility:

- `everyone`: visible to nearby users after safety/rate-limit rules.
- `friends`: visible only to accepted friends.
- `nobody`: not visible on public/friend maps.

Also support per-surface overrides:
- visible in People Nearby,
- visible on Map,
- visible in Groups,
- visible to selected friends only.

### 19.2 Route sharing modes

Route sharing must be explicit and scoped:

- **Live route now:** user chooses recipients and duration (e.g., 15 min / 1 hour / until stopped).
- **Daily path/history:** user chooses recipients and date range.
- **Favorite places:** user chooses visibility per place category (gym/work/home must be protected by default).
- **One-time share link:** optional, expiring, revocable.

Default must be privacy-safe:
- home/work/gym inference is private until user explicitly shares it,
- exact live coordinates are never exposed to unauthorised users,
- route history has TTL/retention limits,
- users can revoke sharing and delete location history.

### 19.3 Backend ACL rule

Every location/route query must apply this order:

1. requester identity
2. target user privacy mode
3. friend/block relationship
4. route share grant and expiry
5. geofence/safety rules
6. precision reduction if needed (exact vs approximate)

The map API must never return location data first and “hide it in frontend” later. Privacy filtering is server-side only.

### 19.4 Suggested data model

- `user_privacy_settings(user_id, map_visibility, people_visibility, route_visibility_default, updated_at)`
- `friend_edges(user_id, friend_id, status, created_at)`
- `blocked_users(user_id, blocked_user_id, created_at)`
- `live_locations(user_id, geog, accuracy_m, heading, speed, updated_at, expires_at)`
- `route_share_grants(id, owner_id, recipient_id_or_group_id, mode, starts_at, expires_at, revoked_at)`
- `route_points(owner_id, route_id, geog, recorded_at, precision, retention_expires_at)`
- `favorite_places(owner_id, place_id_or_geog, category, visibility, created_at)`

## 20) Chat must not interfere with map/social UX

Chat is a separate realtime product surface:

- Startup loads only unread counters.
- Chat tab loads conversation list with `limit=30`.
- Conversation opens last 30–50 messages.
- Attachments lazy-load thumbnails first.
- Sending a message is optimistic with server acknowledgement.
- Websocket events are small deltas (`message.created`, `message.read`, `conversation.updated`).
- Chat backpressure must never block map viewport requests or map controls.

Hard rule: if chat service is degraded, Map/Stores/Events still work.

## 21) Load testing matrix before real launch

Run these before claiming the platform is ready:

1. **Map zoom storm:** 2k virtual users pan/zoom repeatedly for 10 minutes; verify no blank map state and p95 viewport < 700ms.
2. **Dense city test:** 100k stores + 100k events/promos in one metro area; verify clusters/caps prevent label/card explosion.
3. **Market open test:** open/close Market 1k times on mobile WebView; verify bottom nav remains clickable and memory does not grow unbounded.
4. **Realtime location test:** 10k online users, 2k sharing live location; verify websocket gateway CPU/memory and Redis/event bus throughput.
5. **Privacy ACL test:** prove `nobody`, `friends`, blocks, revoked grants, and expired route shares never leak into map responses.
6. **Chat burst test:** 1k messages/sec; verify unread counters update and map interactions stay responsive.
7. **Ad layer test:** ads/banners have frequency caps, viewport caps, and never cover selected map cards or navigation.

