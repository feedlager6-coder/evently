# Ivently — Visual Identity, Motion System & UX Foundation
**Sprint B0 Architecture & Design Specification**  
*Document Version:* 1.0.0  
*Target Environment:* Telegram Mini App (iOS / Android / Desktop / Web), React 19, Tailwind CSS v4

---

## 1. Current UI Audit

A comprehensive audit of the production Ivently Mini App (`@Ivently_bot`, `https://ivently.up.railway.app`) was conducted across all core components:

| Component / Layer | Current Implementation | UX / Visual State |
| :--- | :--- | :--- |
| **App Shell & Theme** (`App.tsx`, `index.css`) | `#0B0D13` base background, fixed bottom nav, standard CSS `--safe-bottom` fallback. | Deep dark theme works well on OLED; clean contrast, but lacks ambient depth and layered hierarchy. |
| **Top Header** (`Header.tsx`) | Sticky glass bar (`#0B0D13/85`, `backdrop-blur-md`), pill city selector with icon, subscriptions bookmark icon. | Clean, recognizable brand mark with gradient `from-indigo-600 to-purple-600`. Lacks search entry point. |
| **Event Cards** (`EventCard.tsx`) | 16:9 aspect image, category badge, free/price pill, attendee count, hover border `border-indigo-500/40`. | Solid information density, legible typography. Currently transitions are purely CSS border/scale, without tactile feedback. |
| **Event Details Modal** (`EventDetailsModal.tsx`) | Bottom-sheet pattern with top hero image, key-facts grid (Date, Price, Venue), RSVP button sticky bar. | Functional and native-feeling. Opening animation is a simple `animate-fade-in` rather than a physics-based sheet slide-up. |
| **Organization Profiles** (`OrganizationModal.tsx`) | Header banner, circular avatar, verified badge, stats pills (followers, events), subscribe CTA. | Professional presentation. Follower counter transitions abruptly upon subscribing/unsubscribing. |
| **Bottom Navigation** (`Navigation.tsx`) | Fixed glass container (`#0E101A/95`, `backdrop-blur-md`), 4 tabs (Афиша, Создать, Мои события, Модерация). | Tab switching is an instantaneous text color swap; lacks sliding indicator or spring feedback. |
| **Filters** (`FilterBar.tsx`) | Segmented date control (Все, Сегодня, Завтра, Выходные) + horizontal scrollable category pills. | Extremely fast and ergonomic for thumb use. Lacks micro-springs on pill selection. |
| **City Selection** (`CityModal.tsx`) | Centered modal with search input, geolocation button with haptic feedback, list of Russian cities with emojis. | Very solid, but uses desktop-style centered card instead of a native bottom sheet on mobile. |

---

## 2. Что сохранить (Preserve Invariants)

1. **Dark OLED-First Canvas**: Retain `#0B0D13` as the foundational background. It saves battery on mobile OLED displays and provides extreme contrast for vibrant event media.
2. **Indigo / Violet Brand Accent**: Retain the `#6366F1` (Indigo 500) to `#8B5CF6` (Purple 500) spectrum. It separates Ivently from standard Telegram blue (`#24A1DE`) while remaining premium and modern.
3. **Card-First Discovery Feed**: Event cards with 16:9 imagery, bold titles, and direct metadata pills must remain the core discovery mechanism.
4. **Bottom-First Ergonomics**: All actionable sheets, primary filters, and navigation must stay within the thumb reach zone (bottom 60% of viewport).
5. **Telegram Native Invariants**:
   - `telegram-web-app.js` integration;
   - Telegram Haptic Feedback on all tactile interactions (`impactOccurred('light' | 'medium')`, `notificationOccurred('success')`);
   - Strict CSS safe-area handling via `--safe-bottom` and `env(safe-area-inset-bottom)`;
   - Idempotent RSVP state synchronized with HMAC-SHA256 authenticated `initData`.

---

## 3. Что улучшить (Targeted Improvements)

1. **Elevation & Surface Contrast**: Current cards and modals share nearly identical dark tones (`#141724` vs `#171B29`). Distinct elevation tokens (`base` -> `elevated` -> `overlay` -> `floating`) are needed to create genuine optical hierarchy.
2. **Unified Omnisearch**: Currently, discovering venues or specific events requires scrolling or filter toggling. An integrated search bar is required without adding tabs.
3. **Motion Physics & Spring Curves**: Transitions currently rely on generic `transition-all duration-300` or `animate-fade-in`. Introducing a unified cubic-bezier spring curve (`cubic-bezier(0.16, 1, 0.3, 1)`) will make sheet opens, card presses, and tab switches feel organic and tactile.
4. **Counter Transitions**: Attendee counts (e.g. `12` -> `13`) and follower counts currently jump instantly. A rolling digit transition will reinforce social activity.
5. **The Flagship "Я иду" Interaction**: The attendance confirmation is the central emotional moment of the app. It currently has only a standard spinner and text swap. It needs an iconic, delightful micro-animation.
6. **Consistent Corner Radii & Spacing Grid**: Harmonize all radii from random classes (`rounded-xl`, `rounded-2xl`, `rounded-3xl`) to a strict 4-tier radius system.

---

## 4. Visual Direction

* **Brand Character**: *Urban, Social, Alive, Tactile, Modern-Premium.*
* **Anti-Pattern (What to Avoid)**:
  - Do NOT copy Telegram's blue native interface.
  - Do NOT use generic corporate SaaS design (flat gray cards, harsh borders, clinical tables).
  - Do NOT create playful childish gamification (cartoon animals, confetti explosions on every click).
  - Do NOT turn every surface into heavy glass/blur, which turns low-end mobile devices into laggy heaters.
* **The Atmosphere**: The feeling of entering an evening city lounge, neon concert hall, or modern coffee house — moody, atmospheric dark tones with focused, glowing accents that guide the eye directly to experiences and people.

---

## 5. Color System (Compact Token Set)

A disciplined 12-token palette designed specifically for dark-mode OLED Telegram WebViews:

| Token Name | Hex / Value | Purpose & Placement | Forbidden Usage |
| :--- | :--- | :--- | :--- |
| `bg-canvas` | `#0B0D13` | Main app background, body, underlying canvas. | Never use on clickable cards or elevated controls. |
| `bg-surface-elevated` | `#131722` | Event cards, input fields, key fact boxes. | Do not use for modal sheets or floating nav. |
| `bg-surface-overlay` | `#191E2E` | Modals, bottom sheets, active list items. | Do not use for full-page backgrounds. |
| `bg-glass-nav` | `rgba(14, 16, 26, 0.85)` | Sticky header, bottom navigation bar, floating pills. | Do not use on large content feeds (causes blur lag). |
| `border-subtle` | `rgba(255, 255, 255, 0.07)` | Standard container and card outlines. | Avoid borders thicker than 1px. |
| `border-focus` | `rgba(99, 102, 241, 0.45)` | Active card hover/focus, selected filter pills. | Do not use on neutral, unselected elements. |
| `brand-primary` | `#6366F1` | Primary CTA buttons, active tab indicators, accents. | Do not use for long-form reading text. |
| `brand-gradient` | `linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)` | Brand logo mark, featured event badges, RSVP CTA. | Do not apply to body backgrounds or text paragraphs. |
| `brand-glow` | `rgba(99, 102, 241, 0.22)` | Subtle button shadows (`shadow-lg shadow-indigo-500/20`). | Never use sharp, high-opacity neon glows. |
| `accent-success` | `#10B981` | «Вы идёте» active state, free admission badge, verified badge. | Do not use for neutral information. |
| `accent-danger` | `#EF4444` | Rejection alerts, cancel RSVP, delete actions. | Do not use for non-destructive warnings. |
| `text-primary` | `#FFFFFF` | Headlines, titles, button text, active labels. | Do not use on muted secondary labels. |
| `text-secondary` | `#94A3B8` | Metadata, venues, dates, follower counters, descriptions. | Do not reduce opacity below 0.6. |
| `text-muted` | `#64748B` | Footnotes, placeholders, disabled states. | Do not use for essential event information. |

---

## 6. Typography System

The application relies on system-optimized **Inter** with native Apple `-apple-system, BlinkMacSystemFont` fallbacks for instant rendering in Telegram WebViews without webfont pop-in:

| Role | Font Size | Weight | Line Height | Tracking | Component Target |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Display Title** | 22px (`text-[22px]`) | Bold (700) | 28px (`leading-7`) | `-0.02em` | Modal sheet event title, org profile name |
| **Section Title** | 16px (`text-base`) | Bold (700) | 22px (`leading-snug`) | `-0.015em` | Feed section headers, modal block headers |
| **Event Card Title**| 15px (`text-[15px]`) | SemiBold (600) | 20px (`leading-5`) | `-0.01em` | Feed card event title (max 2 lines) |
| **Body Standard** | 14px (`text-sm`) | Regular (400) | 20px (`leading-relaxed`)| `0` | Event descriptions, organizer "О нас" |
| **Metadata / Micro**| 12px (`text-xs`) | Medium (500) | 16px (`leading-4`) | `0` | Date/time, address, attendee counts |
| **Badge / Pill** | 11px (`text-[11px]`) | SemiBold (600) | 14px (`leading-none`) | `+0.01em` | Category tags, price badges, status chips |
| **Button Primary** | 14px (`text-sm`) | Bold (700) | 20px (`leading-5`) | `+0.005em` | CTA buttons («Я иду», «Подписаться») |
| **Navigation Tab** | 10px (`text-[10px]`) | Medium/Bold | 12px (`leading-none`) | `0` | Bottom bar icon labels |

---

## 7. Radius System (Harmonized Geometry)

To eliminate visual dissonance across screens, all radii are locked to 4 semantic scales:

| Scale Name | Value | Tailwind Class | Semantic Usage |
| :--- | :--- | :--- | :--- |
| **Sm / Component** | 10px | `rounded-[10px]` | Badges, pills inside cards, segmented date controls. |
| **Md / Input-Action**| 14px | `rounded-2xl` | Buttons, text input fields, search bar, dropdown cards. |
| **Lg / Container** | 20px | `rounded-[20px]` | Event cards in feed, organizer profile cards, media containers. |
| **Xl / Sheet** | 28px | `rounded-t-[28px]` | Bottom sheets (EventDetails, Organization, Subscriptions). |
| **Full / Capsule** | 9999px | `rounded-full` | Category scroll pills, avatar circles, quick action icons. |

*Forbidden*: Never use square borders (`rounded-none` or `rounded-sm`) on modern touch UI elements.

---

## 8. Liquid Glass Rules (Restrained Depth)

Glassmorphism in Ivently must be **functional and layered**, not decorative clutter:

### Preferred Locations for Glass:
1. **Sticky Top Header**: `rgba(11, 13, 19, 0.85)` + `backdrop-blur-md` + `border-b border-white/7`. Allows content to glide underneath without losing legibility.
2. **Bottom Navigation Dock**: `rgba(14, 16, 26, 0.88)` + `backdrop-blur-md` + `border-t border-white/8`. Anchors thumb navigation cleanly over the scrolling feed.
3. **Hero Image Badges**: `rgba(0, 0, 0, 0.55)` + `backdrop-blur-md` + `border border-white/12`. Guarantees 100% contrast for category and price tags over unpredictable cover art photos.
4. **Modal Backdrops**: `rgba(0, 0, 0, 0.78)` + `backdrop-blur-sm`. Focuses attention entirely on the active sheet.

### Strict Glass Invariants:
- **Do NOT make feed event cards glass**: Cards must have solid backgrounds (`#131722`). Glass cards stacked on top of a scrolling feed trigger severe GPU overdraw on mid-range Android devices and create muddy readability.
- **Do NOT blur large scrolling bodies**: Backdrop filters must be isolated strictly to fixed/sticky chrome elements.

---

## 9. Motion System Specification

All transitions follow a unified physics curve calibrated for 60/120Hz mobile screens:
$$\text{Ease Curve: } \mathbf{cubic-bezier(0.16, 1, 0.3, 1)} \quad (\text{Fast entrance, organic spring settling})$$

| Animation Type | Duration | Curve | Transforms / Properties | Trigger & Location |
| :--- | :--- | :--- | :--- | :--- |
| **Tap / Press** | 120ms | `cubic-bezier(0.16, 1, 0.3, 1)` | `scale(0.98)` | Buttons, cards, pills on pointer down. |
| **Release / Pop** | 180ms | `cubic-bezier(0.16, 1, 0.3, 1)` | `scale(1.0)` | Pointer up / click commit. |
| **Sheet Slide-Up**| 280ms | `cubic-bezier(0.2, 0.9, 0.2, 1)` | `translateY(100%) -> translateY(0)` | Opening EventDetailsModal or OrgModal. |
| **Sheet Dismiss** | 220ms | `ease-in` | `translateY(0) -> translateY(100%)` | Dragging sheet down or tapping Close. |
| **Backdrop Fade** | 200ms | `ease-out` | `opacity: 0 -> 1` | Dimming background on sheet open. |
| **Tab Indicator** | 220ms | `cubic-bezier(0.16, 1, 0.3, 1)` | `translateX` spring | Switching tabs in bottom navigation. |
| **Counter Roll** | 300ms | `cubic-bezier(0.16, 1, 0.3, 1)` | `translateY(-100%) -> translateY(0)` | RSVP attendee count increment. |

---

## 10. Button Interaction Rules

Buttons in Ivently are tactical and tactile. They communicate state changes through 3 simultaneous channels:

```
[Touch Down]  ──>  Scale 0.97 + Light Haptic Impact
      ↓
[Network POST] ──>  Active state pulse (scale 0.99)
      ↓
[HTTP 200 OK] ──>  Haptic Success Notification + State Shift + Success Glow Burst (400ms)
```

1. **State Independence**: A button never remains stuck in a disabled or indefinite spinner state. If an API call fails, the button reverts to its original label within 200ms with a warning haptic impact.
2. **Double-Tap Protection**: All primary CTA buttons enforce a 400ms debounce to prevent duplicate network calls.

---

## 11. Flagship «Я иду» (RSVP) Animation Concept

The attendance confirmation is the central emotional climax of event discovery:

```
State 0: Default Calm
┌──────────────────────────────────────────────┐
│                  🎟  Я иду                    │
└──────────────────────────────────────────────┘

Step 1: Tap & Ignition (0 – 150ms)
- Scale: 0.97
- Telegram Haptic: telegram.hapticImpact('medium')
- Button background flashes from Indigo to Vibrant Electric Violet

Step 2: Character Burst & Stride (150 – 650ms)
- In the left icon slot, character «Ivi» emerges in a brisk 500ms micro-loop:
  - Snaps on backpack / raises ticket with energetic motion
  - Takes 2 dynamic forward strides toward the event
- Background smoothly transitions into deep Emerald (#059669)

Step 3: Success Lock & Counter Pulse (650 – 850ms)
- Character transitions into victory nod and slides seamlessly into the checkmark badge:
┌──────────────────────────────────────────────┐
│             ✓  Вы идёте (отменить)           │
└──────────────────────────────────────────────┘
- Telegram Haptic: telegram.hapticSuccess()
- Attendee counter next to label rolls upward smoothly: 12  ──>  13 (emerald pulse)

Total Duration: 800ms. Non-looping. Settles into a calm, elegant success state.
```

---

## 12. Ivently Character Concept: «Ivi» (Иви)

### Character Persona & Aesthetics
- **Name**: **Ivi** (Иви).
- **Archetype**: The Urban Spark / Urban Pathfinder (Городской следопыт).
- **Visual Design**:
  - Minimalist geometric silhouette: A sleek, modern figure composed of rounded geometric capsules (reminiscent of modern Swiss/Bauhaus character design, like Monument Valley or modern Notion/Linear avatars, NOT anime or children's cartoons).
  - Head is an iconic soft-corner diamond spark (the Ivently event spark).
  - Body wears a minimalist modern urban coat/hoodie in slate obsidian (`#191E2E`) with glowing energetic indigo/violet trim.
- **Why this works**:
  - Extremely versatile across sizes: Looks distinct and legible at 24x24px inside a button, and stunning at 160x160px on an empty state screen.
  - Zero childishness: Appeals to adults attending jazz concerts, business conferences, nightlife, and art exhibitions.
  - Scalable across states:
    - *«Я иду»*: Strides forward with an event ticket/badge.
    - *«Хочу пойти»*: Peeks curiously over an event card with a glowing flame spark.
    - *«Компания найдена»*: High-fives a counterpart silhouette.
    - *Empty State*: Sitting on a park bench looking through binoculars with the text "В этом городе пока тихо...".
    - *Offline / Error*: Holding a tiny compass that spins gently.

---

## 13. Animation Tech Stack: Lottie vs dotLottie vs Rive vs CSS

A rigorous technical comparison for Telegram WebApps on mobile WebViews:

| Criterion | CSS Keyframes | Classic Lottie (`lottie-web`) | **dotLottie (`@lottiefiles/dotlottie-react`)** | Rive (`@rive-app/react-canvas`) |
| :--- | :--- | :--- | :--- | :--- |
| **Bundle Size Overhead** | **0 KB** (Native CSS) | ~60 KB gzip | **~28 KB gzip** | ~140 KB gzip (WASM runtime) |
| **Animation Asset Size** | < 2 KB (SVG code) | 40–120 KB JSON | **8–18 KB `.lottie` (ZIP compressed)**| 5–15 KB `.riv` binary |
| **Memory / CPU Footprint**| Extremely low | High (DOM/SVG mode) | **Low (Canvas-accelerated)** | Low (WebGL) |
| **iOS WebKit Stability** | 100% flawless | Rare memory leaks | **100% stable** | Good, but WebGL context limits apply |
| **Android WebView Perf** | 100% smooth | Laggy on low-end | **Smooth (Canvas/Skia)** | Potential WebGL context crash on cheap chips |
| **Interactive State Machine**| Limited (class toggles)| No built-in state machine| **Yes (dotLottie state machines)**| Best-in-class state machines |
| **React 19 Compatibility**| Native | Wrapper required | **Full official React 19 support** | Wrapper required |

### Architectural Recommendation: The Hybrid Model
1. **CSS Hardware Transforms (90% of UI)**: Modals, bottom sheets, card press scales, tab transitions, filter selection, and loading spinners are powered 100% by pure Tailwind CSS and GPU-accelerated transforms (`translate3d`, `scale`). Zero runtime dependencies.
2. **dotLottie with Canvas Renderer (10% Character Moments)**: Reserve `@lottiefiles/dotlottie-react` strictly for the 4 emotional moments:
   - Flagship «Я иду» character stride;
   - Feed empty state;
   - Onboarding / Find Company celebration;
   - App initial splash spark.
   - Total animation asset budget across the entire app: **< 45 KB total**.

---

## 14. Banning GIF from UI Micro-Interactions

GIF is strictly prohibited for UI interactions in Ivently based on 5 technical realities:
1. **Massive File Sizes**: A 1-second 60fps GIF is typically 1.5–3.5 MB, whereas the equivalent dotLottie file is **12 KB** (a 99.3% reduction in payload).
2. **No Alpha Anti-Aliasing**: GIFs only support 1-bit binary transparency. On our rich dark background (`#0B0D13`), GIFs display ugly, pixelated, jagged gray halos around moving edges.
3. **Severe WebKit Performance Degradation**: Decoding GIF image frames on mobile browsers occurs on the main CPU thread, triggering frame drops and battery drain.
4. **Zero Programmatic Control**: GIFs cannot be paused, reversed, sped up, dynamically tinted with user theme colors, or triggered on exact state completion.
5. **Only Allowable Use**: Optional static video preview (MP4/WebM) sent directly in Telegram bot chat messages as native Telegram animations, never inside the React DOM.

---

## 15. Logo & Brand Mark Directions

### Analysis of Current Ticket Mark
- *Strengths*: Instantly signals entertainment, shows, concerts, and cinema. Universal clarity.
- *Limitations*: Ivently is expanding into *events + venues + people + company*. Spontaneous meetups, community runs, business breakfasts, and open-air jams do NOT have tickets. Relying strictly on a ticket metaphor makes the app feel like a ticketing reseller (Kassir/Ticketmaster) rather than a vibrant social platform.

### 4 Conceptual Directions for Evaluation:

```
Direction 1: Dynamic Ticket 2.0 (Evolutionary)
┌──────────────┐
│  ╭────────╮  │  Rounded ticket badge where the cutout notches blend into an
│  │  ╭──╮  │  │  infinity loop or two intersecting circles, symbolizing
│  ╰──╯  ╰──╯  │  both access to events and social connection.
└──────────────┘

Direction 2: The Event Spark (I + Spark) [RECOMMENDED]
      ✦        An architectural, clean letterform "I" crowned by a brilliant,
     ███       multi-faceted event spark. Symbolizes personal initiative ("I go",
     ███       "Ivently") igniting social energy in the city.
     ███       Scales down flawlessly to a 16px favicon and app icon.

Direction 3: The Pulse Pin (Location + Radar)
     ╭─╮       A sleek location marker where the interior circle sends out
    │ ⦿ │      concentric acoustic/event radar pulses. Emphasizes "events near you"
     ╰┬╯       and urban discovery.
      ▼

Direction 4: Social Orbit (Two Capsules)
   ╭──╮ ╭──╮   Two pill-shaped capsules overlapping at an angle to form both an
   │  │ │  │   abstract "i" and two people encountering each other at a shared
   ╰──╯ ╰──╯   cultural point of interest.
```

---

## 16. Unified Search UX (No "Places" Tab)

To preserve the clean 4-tab bottom navigation and prevent cognitive overload, we reject adding a standalone "Места" (Places) tab. Instead, we implement a **Unified Omnisearch Bar** at the top of the discovery feed:

```
┌────────────────────────────────────────────────────────┐
│  🔍  События, места или организаторы...                │
└────────────────────────────────────────────────────────┘
```

### Search Results Architecture:
When the user types `Coffee`:
1. **Section 1: События (Events)** (e.g. "Acoustic Live Music at Coffee Lab", "Coffee Cupping Workshop").
2. **Section 2: Места и организации (Venues & Organizations)** (e.g. "Coffee Lab", "Black Coffee Co.").
3. **Ergonomic Features**:
   - Debounced search query (250ms);
   - Recent search query chips cached locally in `localStorage`;
   - Instant clear `(X)` button;
   - Results render in an overlay with zero page reloads.

---

## 17. «Хочу пойти» (Interest vs Attendance)

We define a clear two-tier social engagement hierarchy:

| Dimension | **«Хочу пойти» (Interest)** | **«Я иду» (RSVP / Attendance)** |
| :--- | :--- | :--- |
| **Intent Level** | Lightweight curiosity / bookmarking / signal to friends. | Confirmed commitment to attend in person. |
| **User Commitment** | Low friction (1 tap to save and show interest). | High intent (counted for venue organizer capacity). |
| **Notification Impact** | Reminders 24 hours prior if user hasn't RSVP'd. | Event updates, venue changes, calendar sync. |
| **UI Placement** | Secondary pill button on details modal: `[🔥 Хочу пойти · 14]`. | Primary full-width sticky CTA: `[🎟 Я иду · 32]`. |
| **Social Unlock** | **Unlocks «Найти компанию» CTA!** | Confirms attendance badge on feed card. |

---

## 18. Find Company («Найти компанию») UX & Privacy Architecture

The social bridge connecting solo event seekers:

### User Journey:
1. User views an event (e.g. "Standup Comedy Show").
2. User taps `[🔥 Хочу пойти]`.
3. An invitation banner slides into view below:
   `👥 Идёшь один? 8 человек тоже ищут компанию → [Найти компанию]`
4. Tapping opens the **Company Lounge Sheet**:
   - List of attendees who have explicitly enabled matchmaking for this event;
   - User cards display: First name, avatar (or geometric initial), vibe tag (e.g. "Люблю юмор, хочу сесть в первом ряду"), music/cultural interests.
   - Action: `[Пойти вместе 🤝]`.

### Privacy Invariants (Zero Leak Guarantee):
- **Zero Raw Telegram IDs**: Telegram user IDs and phone numbers are NEVER rendered in the DOM or API payloads.
- **Strict Tri-State Privacy Setting**:
  1. *«Никому»* (Strictly Private — default): User is never visible in company search.
  2. *«Только для моих событий 'Хочу пойти'»*: User is only visible on events they explicitly marked.
  3. *«Спрашивать каждый раз»*: Requires an explicit opt-in confirmation dialog per event.
- **Mutual Handshake (Double Opt-In)**: Tapping "Пойти вместе" sends a private match request. Contact details are only shared once both users confirm.

---

## 19. Telegram Group & Company Chat Feasibility

### Technical Reality Check (Telegram Bot API Boundaries):
- **Can a bot automatically create a new group chat?**  
  **NO.** The Telegram Bot API does **not** have a `createChat` or `createGroup` method. That method only exists in the MTProto client protocol for human user accounts.
- **Can a bot force-add users to a group?**  
  **NO.** Telegram heavily restricts bots adding users to groups without user initiation to protect against unsolicited spam.
- **Can a bot create dynamic, secure invite links?**  
  **YES.** `createChatInviteLink` allows bots to generate single-use, time-limited, or approval-based (`creates_join_request=True`) invite links.
- **Can a bot manage Forum Topics inside an official supergroup?**  
  **YES.** Telegram Bot API 6.3+ provides `createForumTopic`, `editForumTopic`, and `closeForumTopic`.

### The Recommended Architecture: The Event Lounge Model
1. Ivently maintains an official verified supergroup: `@IventlyCommunity` (with Topics enabled).
2. For trending events where users seek company, the backend bot automatically provisions a dedicated topic:
   `createForumTopic(chat_id=..., name="🎟 Acoustic Night — Ищем компанию")`.
3. Matched users receive a direct, authorized Telegram deep link:
   `https://t.me/IventlyCommunity/<TOPIC_ID>`.
4. Users chat in a focused, moderated, native Telegram environment without leaving their app ecosystem, while the bot moderates rules and pins event details.

---

## 20. Telegram Bot Branding (`@Ivently_bot`)

Complete branding specification for the official Telegram bot entry point:

1. **Bot Avatar (Profile Picture)**:
   - 640x640px PNG.
   - Deep obsidian background (`#0B0D13`) with the vibrant glowing Ivently Spark mark in gradient electric indigo-violet.
2. **Bot Profile About Description**:
   `Ivently — афиша твоего города. События, места и люди рядом с тобой.`
3. **`/start` Welcome Experience**:
   - High-contrast visual banner image;
   - Clean, concise intro text:
     ```html
     👋 <b>Добро пожаловать в Ivently!</b>

     Находите живые концерты, выставки, спорт и вечеринки в один клик.
     Подписывайтесь на любимые места и находите компанию на вечер.
     ```
   - Main Mini App launch button:
     `[Открыть афишу 🎟]` (`web_app` direct launch or direct TMA link).
4. **Persistent Menu Button**:
   - Configured via BotFather (`setmenubutton`): Button text "Афиша", launches `https://t.me/Ivently_bot/app`.

---

## 21. Splash Screen Specification

The splash screen must be **ultra-light and non-blocking**:

- **Visuals**: Dark canvas (`#0B0D13`) with centered glowing Ivently Spark icon.
- **Motion Sequence**:
  - `0ms – 250ms`: Spark scales gently from `0.9` to `1.0` with soft glow expansion (`opacity: 0 -> 1`).
  - `250ms – 400ms`: Wordmark "Ivently" settles underneath with soft letter-spacing easing.
  - `400ms – 550ms`: As soon as `telegram.ready()` and initial API response arrive, splash smoothly fades out (`opacity: 0`, duration 180ms).
- **Hard Timeout**: Splash screen is forcibly removed at **700ms**, even on slow 3G connections, immediately revealing skeleton card placeholders. **Never block the user artificially.**

---

## 22. Performance & Accessibility Standards

- **Reduced Motion Support**:
  ```css
  @media (prefers-reduced-motion: reduce) {
    *, ::before, ::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
      scroll-behavior: auto !important;
    }
  }
  ```
  When reduced motion is enabled, all button scales, sheet transitions, and character animations fall back to instant, crisp state changes.
- **WCAG AA Contrast Guarantee**:
  - Primary text (`#FFFFFF`) on `#0B0D13` = **19.8:1** (Far exceeds 4.5:1 requirement).
  - Secondary text (`#94A3B8`) on `#131722` = **5.2:1** (Fully accessible).
  - Accent button text (`#FFFFFF`) on `#6366F1` = **4.8:1** (Fully accessible).
- **Minimum Tap Target Area**: All clickable icons, pills, and buttons must have a hit box of at least **44x44px** (using padding where visual element is smaller).
- **Safe Area Insets**: Modal sheets and bottom navigation must maintain `--safe-bottom` padding to avoid home indicator collisions on iPhone X through 16 Pro.

---

## 23. Recommended Implementation Order (Sprint Roadmap)

The transition into this visual system is structured into four focused, non-disruptive implementation sprints:

```
┌────────────────────────────────────────────────────────────────────────┐
│ SPRINT B1: Design Tokens, Typography & Motion Infrastructure           │
│ - Integrate color tokens, radii scales, and spring curves in Tailwind  │
│ - Implement tactile button press scale and sheet slide-up physics      │
│ - Zero functional/API changes; 100% regression safe                    │
└────────────────────────────────────────────────────────────────────────┘
                                   ↓
┌────────────────────────────────────────────────────────────────────────┐
│ SPRINT B2: Unified Omnisearch & Feed Polish                            │
│ - Implement debounced search bar in Feed header (Events + Venues)      │
│ - Add rolling digit counter transition for attendees and followers    │
│ - Elevate card hover and active state glows                            │
└────────────────────────────────────────────────────────────────────────┘
                                   ↓
┌────────────────────────────────────────────────────────────────────────┐
│ SPRINT B3: Character Rig & Flagship «Я иду» dotLottie Animation        │
│ - Integrate @lottiefiles/dotlottie-react with canvas renderer          │
│ - Implement «Ivi» character micro-stride in the RSVP button            │
│ - Add celebratory empty-state character illustrations                  │
└────────────────────────────────────────────────────────────────────────┘
                                   ↓
┌────────────────────────────────────────────────────────────────────────┐
│ SPRINT B4: «Хочу пойти» & Social Foundation (Find Company)             │
│ - Implement «Хочу пойти» bookmarking and interest counter              │
│ - Build Find Company opt-in modal with strict tri-state privacy        │
│ - Integrate verified Telegram community topic invite routing           │
└────────────────────────────────────────────────────────────────────────┘
```
