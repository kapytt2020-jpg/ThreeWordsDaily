"""
content_plan_9months.py — ThreeWordsDaily 9-Month English Curriculum

Structured lesson plan: April 2026 – December 2026
Used by teacher_bot.py (Лекс) to deliver structured weekly content.

Each week has:
  - theme       : overall topic
  - grammar     : grammar focus
  - words       : 15 vocabulary items (3 per weekday)
  - idiom       : idiom of the week
  - mini_story  : short story prompt using the week's words

Usage:
    from content_plan_9months import get_week, get_month_overview
"""

from __future__ import annotations
from typing import TypedDict

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class WeekPlan(TypedDict):
    month: int          # 1-12
    week: int           # week number within month (1-4)
    theme: str
    grammar: str
    words: list[dict]   # {en, ua, example}
    idiom: str
    idiom_meaning: str
    mini_story_prompt: str


# ---------------------------------------------------------------------------
# Full 9-Month Curriculum  (April = month 4  →  December = month 12)
# ---------------------------------------------------------------------------

CURRICULUM: list[WeekPlan] = [

    # ═══════════════════════════════════════════════════════════════════
    # APRIL — Everyday Life & Introductions
    # ═══════════════════════════════════════════════════════════════════
    {
        "month": 4, "week": 1,
        "theme": "Introductions & Small Talk",
        "grammar": "Present Simple — be, have, do",
        "words": [
            {"en": "introduce",   "ua": "представляти",    "example": "Let me introduce myself — I'm Alex."},
            {"en": "profession",  "ua": "професія",        "example": "What's your profession?"},
            {"en": "hobby",       "ua": "хобі",            "example": "My hobby is photography."},
            {"en": "neighbour",   "ua": "сусід",           "example": "My neighbour is very friendly."},
            {"en": "routine",     "ua": "розпорядок дня",  "example": "I have a morning routine."},
            {"en": "commute",     "ua": "їздити на роботу","example": "I commute by subway every day."},
            {"en": "schedule",    "ua": "розклад",         "example": "My schedule is very busy."},
            {"en": "appointment", "ua": "зустріч/запис",   "example": "I have a doctor's appointment."},
            {"en": "deadline",    "ua": "дедлайн",         "example": "The deadline is Friday."},
            {"en": "manage",      "ua": "справлятися",     "example": "Can you manage the project?"},
            {"en": "colleague",   "ua": "колега",          "example": "My colleague is helpful."},
            {"en": "suggest",     "ua": "пропонувати",     "example": "I suggest we meet at 3pm."},
            {"en": "accept",      "ua": "приймати",        "example": "She accepted the invitation."},
            {"en": "refuse",      "ua": "відмовляти",      "example": "He refused to comment."},
            {"en": "polite",      "ua": "ввічливий",       "example": "Always be polite at work."},
        ],
        "idiom": "Break the ice",
        "idiom_meaning": "Зняти напругу / почати розмову в незнайомій компанії",
        "mini_story_prompt": "Write a short story about someone's first day at a new job using: introduce, colleague, routine, polite.",
    },
    {
        "month": 4, "week": 2,
        "theme": "Home & Living",
        "grammar": "There is / There are — кількість та розташування",
        "words": [
            {"en": "furniture",   "ua": "меблі",           "example": "The furniture is modern."},
            {"en": "rent",        "ua": "орендувати",      "example": "We rent a flat in the city."},
            {"en": "landlord",    "ua": "орендодавець",    "example": "The landlord raised the rent."},
            {"en": "utilities",   "ua": "комунальні",      "example": "Utilities are included in the price."},
            {"en": "cluttered",   "ua": "захаращений",     "example": "The room was cluttered with boxes."},
            {"en": "tidy",        "ua": "прибирати/охайний","example": "Please tidy your room."},
            {"en": "storage",     "ua": "сховище",         "example": "We need more storage space."},
            {"en": "renovate",    "ua": "ремонтувати",     "example": "They plan to renovate the kitchen."},
            {"en": "cosy",        "ua": "затишний",        "example": "The flat is small but cosy."},
            {"en": "balcony",     "ua": "балкон",          "example": "I drink coffee on the balcony."},
            {"en": "lease",       "ua": "договір оренди",  "example": "Sign the lease before moving in."},
            {"en": "deposit",     "ua": "завдаток",        "example": "The deposit is two months' rent."},
            {"en": "maintenance", "ua": "обслуговування",  "example": "Maintenance costs can be high."},
            {"en": "appliance",   "ua": "побутова техніка","example": "The appliances are brand new."},
            {"en": "mortgage",    "ua": "іпотека",         "example": "They took out a mortgage."},
        ],
        "idiom": "Home is where the heart is",
        "idiom_meaning": "Дім там, де твоє серце — найкраще місце там, де тобі комфортно",
        "mini_story_prompt": "Describe moving into a new apartment using: rent, landlord, cosy, renovate, utilities.",
    },
    {
        "month": 4, "week": 3,
        "theme": "Shopping & Money",
        "grammar": "Countable vs Uncountable nouns — much/many/a lot of",
        "words": [
            {"en": "budget",      "ua": "бюджет",          "example": "We need to stick to our budget."},
            {"en": "receipt",     "ua": "чек",             "example": "Keep your receipt for returns."},
            {"en": "discount",    "ua": "знижка",          "example": "There's a 20% discount today."},
            {"en": "refund",      "ua": "повернення коштів","example": "I got a full refund."},
            {"en": "bargain",     "ua": "вигідна покупка", "example": "That coat was a real bargain."},
            {"en": "afford",      "ua": "дозволити собі",  "example": "Can you afford it?"},
            {"en": "invest",      "ua": "інвестувати",     "example": "Invest in your education."},
            {"en": "savings",     "ua": "заощадження",     "example": "My savings are growing."},
            {"en": "currency",    "ua": "валюта",          "example": "The local currency is euro."},
            {"en": "transaction", "ua": "транзакція",      "example": "The transaction was declined."},
            {"en": "cashless",    "ua": "безготівковий",   "example": "Most shops are cashless now."},
            {"en": "overpriced",  "ua": "завищена ціна",   "example": "That restaurant is overpriced."},
            {"en": "purchase",    "ua": "покупка",         "example": "Make a purchase online."},
            {"en": "vendor",      "ua": "продавець",       "example": "The street vendor sold fruit."},
            {"en": "installment", "ua": "розстрочка",      "example": "Pay in monthly installments."},
        ],
        "idiom": "Cost an arm and a leg",
        "idiom_meaning": "Коштувати дуже дорого",
        "mini_story_prompt": "Tell a story about finding a great bargain at a market using: discount, afford, receipt, bargain.",
    },
    {
        "month": 4, "week": 4,
        "theme": "Food & Restaurants",
        "grammar": "Ordering & requests — Would like / Could I have / I'll have",
        "words": [
            {"en": "ingredient",  "ua": "інгредієнт",      "example": "The main ingredient is garlic."},
            {"en": "cuisine",     "ua": "кухня (страви)",  "example": "I love Italian cuisine."},
            {"en": "appetizer",   "ua": "закуска",         "example": "We ordered an appetizer first."},
            {"en": "portion",     "ua": "порція",          "example": "The portion was huge."},
            {"en": "reservation", "ua": "бронювання",      "example": "Do you have a reservation?"},
            {"en": "chef",        "ua": "кухар/шеф",       "example": "The chef is from France."},
            {"en": "allergic",    "ua": "алергічний",      "example": "I'm allergic to nuts."},
            {"en": "vegetarian",  "ua": "вегетаріанський", "example": "Is there a vegetarian option?"},
            {"en": "flavour",     "ua": "смак/аромат",     "example": "The soup has a rich flavour."},
            {"en": "garnish",     "ua": "прикраса страви", "example": "Add a garnish of parsley."},
            {"en": "menu",        "ua": "меню",            "example": "Could I see the menu?"},
            {"en": "tip",         "ua": "чайові",          "example": "Leave a 15% tip."},
            {"en": "takeaway",    "ua": "їжа з собою",     "example": "I'll order a takeaway tonight."},
            {"en": "digest",      "ua": "перетравлювати",  "example": "Heavy food is hard to digest."},
            {"en": "delicious",   "ua": "смачний",         "example": "This pizza is delicious!"},
        ],
        "idiom": "You are what you eat",
        "idiom_meaning": "Те, що ти їси, впливає на твоє здоров'я і самопочуття",
        "mini_story_prompt": "Write about a dinner at a fancy restaurant using: reservation, cuisine, allergic, chef, tip.",
    },

    # ═══════════════════════════════════════════════════════════════════
    # MAY — Work, Career & Communication
    # ═══════════════════════════════════════════════════════════════════
    {
        "month": 5, "week": 1,
        "theme": "Job Interviews",
        "grammar": "Past Simple — talking about experience",
        "words": [
            {"en": "candidate",   "ua": "кандидат",        "example": "She's the best candidate."},
            {"en": "resume",      "ua": "резюме",          "example": "Update your resume."},
            {"en": "reference",   "ua": "рекомендація",    "example": "Can you provide a reference?"},
            {"en": "salary",      "ua": "зарплата",        "example": "What's the expected salary?"},
            {"en": "negotiate",   "ua": "переговори",      "example": "Negotiate your contract."},
            {"en": "recruit",     "ua": "наймати",         "example": "We recruit twice a year."},
            {"en": "probation",   "ua": "випробувальний термін","example": "3-month probation period."},
            {"en": "promote",     "ua": "підвищувати",     "example": "She was promoted to manager."},
            {"en": "resign",      "ua": "звільнятися",     "example": "He resigned last week."},
            {"en": "freelance",   "ua": "фрілансер",       "example": "I work as a freelancer."},
            {"en": "remote",      "ua": "дистанційний",    "example": "Remote work is common now."},
            {"en": "overtime",    "ua": "надурочні",       "example": "I worked overtime this month."},
            {"en": "benefit",     "ua": "пільга/перевага", "example": "Health insurance is a benefit."},
            {"en": "performance", "ua": "результати роботи","example": "Her performance was excellent."},
            {"en": "feedback",    "ua": "зворотній зв'язок","example": "Give constructive feedback."},
        ],
        "idiom": "Land a job",
        "idiom_meaning": "Отримати роботу",
        "mini_story_prompt": "Write about a job interview that went surprisingly well using: candidate, negotiate, promote, feedback.",
    },
    {
        "month": 5, "week": 2,
        "theme": "Emails & Business Writing",
        "grammar": "Formal vs Informal register — modal verbs (would, could, should)",
        "words": [
            {"en": "attach",      "ua": "додавати (файл)", "example": "I've attached the document."},
            {"en": "regarding",   "ua": "стосовно",        "example": "Regarding your request..."},
            {"en": "clarify",     "ua": "уточнити",        "example": "Could you clarify this point?"},
            {"en": "agenda",      "ua": "порядок денний",  "example": "The agenda is attached."},
            {"en": "confirm",     "ua": "підтвердити",     "example": "Please confirm the meeting."},
            {"en": "postpone",    "ua": "відкласти",       "example": "We need to postpone the call."},
            {"en": "forward",     "ua": "пересилати",      "example": "I'll forward the email to you."},
            {"en": "brief",       "ua": "стислий / брифувати","example": "Keep the email brief."},
            {"en": "urgent",      "ua": "терміновий",      "example": "This is urgent — reply ASAP."},
            {"en": "proposal",    "ua": "пропозиція",      "example": "Send us your proposal by Friday."},
            {"en": "invoice",     "ua": "рахунок-фактура", "example": "The invoice is overdue."},
            {"en": "deadline",    "ua": "дедлайн",         "example": "The deadline is end of week."},
            {"en": "apologize",   "ua": "вибачатися",      "example": "I apologize for the delay."},
            {"en": "enclose",     "ua": "додавати (лист)", "example": "Please find enclosed the report."},
            {"en": "sincerely",   "ua": "щиро",            "example": "Yours sincerely, John."},
        ],
        "idiom": "Touch base",
        "idiom_meaning": "Зв'язатися / перевірити як справи",
        "mini_story_prompt": "Write a formal email declining a meeting and proposing a new time using: postpone, agenda, confirm, apologize.",
    },
    {
        "month": 5, "week": 3,
        "theme": "Meetings & Presentations",
        "grammar": "Future forms — will / going to / Present Continuous for plans",
        "words": [
            {"en": "summarize",   "ua": "підсумовувати",   "example": "Let me summarize the key points."},
            {"en": "highlight",   "ua": "виділяти",        "example": "I want to highlight this trend."},
            {"en": "audience",    "ua": "аудиторія",       "example": "Know your audience."},
            {"en": "slide",       "ua": "слайд",           "example": "Go to the next slide please."},
            {"en": "objective",   "ua": "мета",            "example": "What's the main objective?"},
            {"en": "strategy",    "ua": "стратегія",       "example": "Our strategy for Q3 is growth."},
            {"en": "outcome",     "ua": "результат",       "example": "What outcome do we expect?"},
            {"en": "milestone",   "ua": "ключовий етап",   "example": "We hit a major milestone."},
            {"en": "delegate",    "ua": "делегувати",      "example": "Delegate tasks to your team."},
            {"en": "collaborate", "ua": "співпрацювати",   "example": "We collaborate across teams."},
            {"en": "implement",   "ua": "впроваджувати",   "example": "We'll implement the plan next week."},
            {"en": "launch",      "ua": "запускати",       "example": "The product launches in May."},
            {"en": "stakeholder", "ua": "зацікавлена сторона","example": "Present to all stakeholders."},
            {"en": "timeline",    "ua": "часовий графік",  "example": "Stick to the project timeline."},
            {"en": "budget",      "ua": "бюджет",          "example": "We're under budget this quarter."},
        ],
        "idiom": "Think outside the box",
        "idiom_meaning": "Мислити нестандартно / творчо",
        "mini_story_prompt": "Describe a team meeting where someone presents a creative idea using: strategy, audience, collaborate, launch.",
    },
    {
        "month": 5, "week": 4,
        "theme": "Problem Solving at Work",
        "grammar": "Conditionals — If + Present, will (First Conditional)",
        "words": [
            {"en": "issue",       "ua": "проблема",        "example": "There's an issue with the system."},
            {"en": "resolve",     "ua": "вирішувати",      "example": "We resolved the issue quickly."},
            {"en": "priority",    "ua": "пріоритет",       "example": "This is our top priority."},
            {"en": "deadline",    "ua": "дедлайн",         "example": "Missing a deadline is costly."},
            {"en": "bottleneck",  "ua": "вузьке місце",    "example": "Find and fix the bottleneck."},
            {"en": "escalate",    "ua": "ескалувати",      "example": "Escalate the issue to management."},
            {"en": "workaround",  "ua": "тимчасове рішення","example": "Use a workaround for now."},
            {"en": "root cause",  "ua": "першопричина",    "example": "Find the root cause of the bug."},
            {"en": "risk",        "ua": "ризик",           "example": "Assess the risks carefully."},
            {"en": "contingency", "ua": "запасний план",   "example": "We need a contingency plan."},
            {"en": "efficient",   "ua": "ефективний",      "example": "Find a more efficient method."},
            {"en": "brainstorm",  "ua": "мозковий штурм",  "example": "Let's brainstorm solutions."},
            {"en": "deadline",    "ua": "дедлайн",         "example": "The deadline is tomorrow."},
            {"en": "track",       "ua": "відстежувати",    "example": "Track your progress daily."},
            {"en": "solution",    "ua": "рішення",         "example": "We found a simple solution."},
        ],
        "idiom": "Back to square one",
        "idiom_meaning": "Починати з нуля / повернутися до початку",
        "mini_story_prompt": "Write about a team solving a production bug under time pressure using: escalate, root cause, priority, workaround.",
    },

    # ═══════════════════════════════════════════════════════════════════
    # JUNE — Travel & Culture
    # ═══════════════════════════════════════════════════════════════════
    {
        "month": 6, "week": 1,
        "theme": "Planning a Trip",
        "grammar": "Future with 'going to' vs 'will' — plans vs spontaneous decisions",
        "words": [
            {"en": "itinerary",   "ua": "маршрут/план",    "example": "I made a detailed itinerary."},
            {"en": "destination", "ua": "пункт призначення","example": "Paris is our destination."},
            {"en": "luggage",     "ua": "багаж",           "example": "Don't lose your luggage."},
            {"en": "passport",    "ua": "паспорт",         "example": "Check your passport validity."},
            {"en": "visa",        "ua": "віза",            "example": "Apply for a visa in advance."},
            {"en": "hostel",      "ua": "хостел",          "example": "We stayed at a cheap hostel."},
            {"en": "check-in",    "ua": "реєстрація",      "example": "Online check-in saves time."},
            {"en": "departure",   "ua": "відправлення",    "example": "Departure is at 6 AM."},
            {"en": "layover",     "ua": "пересадка",       "example": "A 3-hour layover in Dubai."},
            {"en": "customs",     "ua": "митниця",         "example": "Declare goods at customs."},
            {"en": "currency",    "ua": "валюта",          "example": "Exchange currency at the airport."},
            {"en": "souvenir",    "ua": "сувенір",         "example": "I bought souvenirs for everyone."},
            {"en": "jet lag",     "ua": "часова різниця",  "example": "I suffered from jet lag."},
            {"en": "backpacker",  "ua": "мандрівник",      "example": "He's been a backpacker for years."},
            {"en": "explore",     "ua": "досліджувати",    "example": "Let's explore the old town."},
        ],
        "idiom": "The world is your oyster",
        "idiom_meaning": "Весь світ у тебе в руках — все можливо",
        "mini_story_prompt": "Write about planning a solo trip to Japan using: itinerary, visa, layover, explore, jet lag.",
    },
    {
        "month": 6, "week": 2,
        "theme": "At the Airport & Hotel",
        "grammar": "Passive Voice — Present Simple (is made, is located, is included)",
        "words": [
            {"en": "terminal",    "ua": "термінал",        "example": "Go to Terminal 2."},
            {"en": "boarding",    "ua": "посадка",         "example": "Boarding starts at 14:00."},
            {"en": "gate",        "ua": "вихід/гейт",      "example": "The gate changed to B7."},
            {"en": "overhead",    "ua": "верхня полиця",   "example": "Put bags in the overhead bin."},
            {"en": "turbulence",  "ua": "турбулентність",  "example": "Fasten belts during turbulence."},
            {"en": "reception",   "ua": "ресепшн",         "example": "Check in at the reception."},
            {"en": "amenities",   "ua": "зручності",       "example": "Hotel amenities include a spa."},
            {"en": "concierge",   "ua": "консьєрж",        "example": "Ask the concierge for help."},
            {"en": "checkout",    "ua": "виїзд",           "example": "Checkout is at noon."},
            {"en": "complimentary","ua": "безкоштовний",   "example": "Breakfast is complimentary."},
            {"en": "suite",       "ua": "люкс",            "example": "We upgraded to a suite."},
            {"en": "housekeeping","ua": "прибирання",      "example": "Housekeeping comes at 10 AM."},
            {"en": "minibar",     "ua": "міні-бар",        "example": "Don't touch the minibar!"},
            {"en": "reservation", "ua": "бронювання",      "example": "I have a reservation for 2 nights."},
            {"en": "porter",      "ua": "носильник",       "example": "The porter took our bags."},
        ],
        "idiom": "Smooth sailing",
        "idiom_meaning": "Все йде гладко, без проблем",
        "mini_story_prompt": "Describe arriving at a hotel after a chaotic flight using: turbulence, boarding, reception, complimentary.",
    },
    {
        "month": 6, "week": 3,
        "theme": "Culture & Traditions",
        "grammar": "Comparatives and Superlatives",
        "words": [
            {"en": "tradition",   "ua": "традиція",        "example": "It's a local tradition."},
            {"en": "custom",      "ua": "звичай",          "example": "Respect local customs."},
            {"en": "heritage",    "ua": "спадщина",        "example": "A UNESCO World Heritage site."},
            {"en": "diverse",     "ua": "різноманітний",   "example": "The city is culturally diverse."},
            {"en": "ritual",      "ua": "ритуал",          "example": "A wedding ritual from the 1800s."},
            {"en": "festival",    "ua": "фестиваль",       "example": "The music festival attracts thousands."},
            {"en": "indigenous",  "ua": "корінний",        "example": "Indigenous art is beautiful."},
            {"en": "landmark",    "ua": "пам'ятна місцина","example": "The Eiffel Tower is a landmark."},
            {"en": "artifact",    "ua": "артефакт",        "example": "Ancient artifacts in the museum."},
            {"en": "pilgrim",     "ua": "прочанин",        "example": "Pilgrims visit the site annually."},
            {"en": "colonialism", "ua": "колоніалізм",     "example": "Colonialism shaped many cultures."},
            {"en": "dialect",     "ua": "діалект",         "example": "Each region has its dialect."},
            {"en": "folklore",    "ua": "фольклор",        "example": "Ukrainian folklore is rich."},
            {"en": "mythology",   "ua": "міфологія",       "example": "Greek mythology is fascinating."},
            {"en": "gastronomy",  "ua": "гастрономія",     "example": "French gastronomy is world-famous."},
        ],
        "idiom": "When in Rome, do as the Romans do",
        "idiom_meaning": "У чужому монастирі зі своїм статутом не ходять",
        "mini_story_prompt": "Write about a traveller learning about local traditions in a small village using: custom, ritual, folklore, heritage.",
    },
    {
        "month": 6, "week": 4,
        "theme": "Describing Places & Giving Directions",
        "grammar": "Prepositions of place and movement — in, on, at, next to, across from",
        "words": [
            {"en": "intersection","ua": "перехрестя",      "example": "Turn left at the intersection."},
            {"en": "roundabout",  "ua": "кільце",          "example": "Go around the roundabout."},
            {"en": "avenue",      "ua": "проспект",        "example": "Walk down the main avenue."},
            {"en": "district",    "ua": "район",           "example": "The arts district is lively."},
            {"en": "pedestrian",  "ua": "пішохід",         "example": "Use the pedestrian crossing."},
            {"en": "navigate",    "ua": "орієнтуватись",   "example": "I use GPS to navigate."},
            {"en": "shortcut",    "ua": "коротший шлях",   "example": "Take the shortcut through the park."},
            {"en": "suburb",      "ua": "передмістя",      "example": "They live in the suburbs."},
            {"en": "vicinity",    "ua": "околиця",         "example": "Hotels in the vicinity of the station."},
            {"en": "landmark",    "ua": "орієнтир",        "example": "Use the clock tower as a landmark."},
            {"en": "route",       "ua": "маршрут",         "example": "Which route do you recommend?"},
            {"en": "detour",      "ua": "об'їзд",          "example": "There's a detour due to roadworks."},
            {"en": "uphill",      "ua": "вгору по схилу",  "example": "It's a steep uphill walk."},
            {"en": "opposite",    "ua": "навпроти",        "example": "The museum is opposite the park."},
            {"en": "remote",      "ua": "віддалений",      "example": "A remote village in the mountains."},
        ],
        "idiom": "Off the beaten track",
        "idiom_meaning": "Далеко від туристичних маршрутів / незвичне місце",
        "mini_story_prompt": "Give directions from the train station to a hidden café using: intersection, shortcut, vicinity, navigate.",
    },

    # ═══════════════════════════════════════════════════════════════════
    # JULY — Technology & Digital Life
    # ═══════════════════════════════════════════════════════════════════
    {
        "month": 7, "week": 1,
        "theme": "Technology & Gadgets",
        "grammar": "Present Perfect — have/has + past participle (experience, recent events)",
        "words": [
            {"en": "device",      "ua": "пристрій",        "example": "My device ran out of battery."},
            {"en": "software",    "ua": "програмне забезпечення","example": "Update your software."},
            {"en": "hardware",    "ua": "залізо/обладнання","example": "The hardware is outdated."},
            {"en": "bandwidth",   "ua": "пропускна здатність","example": "Low bandwidth causes lag."},
            {"en": "backup",      "ua": "резервна копія",  "example": "Always back up your data."},
            {"en": "encrypt",     "ua": "шифрувати",       "example": "Encrypt sensitive files."},
            {"en": "interface",   "ua": "інтерфейс",       "example": "The interface is user-friendly."},
            {"en": "algorithm",   "ua": "алгоритм",        "example": "The algorithm sorts data fast."},
            {"en": "glitch",      "ua": "збій",            "example": "There's a glitch in the app."},
            {"en": "wireless",    "ua": "бездротовий",     "example": "Connect via wireless network."},
            {"en": "upgrade",     "ua": "оновлення",       "example": "It's time to upgrade your phone."},
            {"en": "server",      "ua": "сервер",          "example": "The server is down."},
            {"en": "pixel",       "ua": "піксель",         "example": "High pixel count = better photo."},
            {"en": "reboot",      "ua": "перезавантажити", "example": "Try rebooting the device."},
            {"en": "prototype",   "ua": "прототип",        "example": "We built a prototype in a week."},
        ],
        "idiom": "On the cutting edge",
        "idiom_meaning": "На передовій / найновіші технології",
        "mini_story_prompt": "Write about a developer dealing with a major server glitch before a product launch using: backup, encrypt, glitch, reboot.",
    },
    {
        "month": 7, "week": 2,
        "theme": "Social Media & Online Communication",
        "grammar": "Reported Speech — say, tell, ask",
        "words": [
            {"en": "engagement",  "ua": "залученість",     "example": "High engagement = more reach."},
            {"en": "follower",    "ua": "підписник",       "example": "She gained 10k followers."},
            {"en": "viral",       "ua": "вірусний",        "example": "The video went viral."},
            {"en": "caption",     "ua": "підпис",          "example": "Write a catchy caption."},
            {"en": "hashtag",     "ua": "хештег",          "example": "Use relevant hashtags."},
            {"en": "influencer",  "ua": "інфлюенсер",      "example": "Partner with an influencer."},
            {"en": "algorithm",   "ua": "алгоритм",        "example": "Beat the algorithm with good content."},
            {"en": "niche",       "ua": "ніша",            "example": "Find your niche audience."},
            {"en": "authentic",   "ua": "автентичний",     "example": "Be authentic online."},
            {"en": "misinformation","ua": "дезінформація", "example": "Misinformation spreads fast."},
            {"en": "privacy",     "ua": "конфіденційність","example": "Protect your privacy online."},
            {"en": "unfollow",    "ua": "відписатися",     "example": "I unfollowed that account."},
            {"en": "stream",      "ua": "стримити",        "example": "She streams every Saturday."},
            {"en": "monetize",    "ua": "монетизувати",    "example": "You can monetize your channel."},
            {"en": "analytics",   "ua": "аналітика",       "example": "Check your analytics weekly."},
        ],
        "idiom": "Go viral",
        "idiom_meaning": "Стати вірусним — дуже швидко поширитися в інтернеті",
        "mini_story_prompt": "Write about a small creator whose video suddenly went viral using: engagement, authentic, algorithm, monetize.",
    },
    {
        "month": 7, "week": 3,
        "theme": "AI & The Future",
        "grammar": "Second Conditional — If + Past, would (hypothetical present/future)",
        "words": [
            {"en": "artificial",  "ua": "штучний",         "example": "Artificial intelligence is growing."},
            {"en": "automate",    "ua": "автоматизувати",  "example": "We automate repetitive tasks."},
            {"en": "data",        "ua": "дані",            "example": "Data is the new oil."},
            {"en": "bias",        "ua": "упередженість",   "example": "AI can have built-in bias."},
            {"en": "neural",      "ua": "нейронний",       "example": "Neural networks mimic the brain."},
            {"en": "simulate",    "ua": "симулювати",      "example": "Simulate human behaviour."},
            {"en": "ethical",     "ua": "етичний",         "example": "Is it ethical to replace humans?"},
            {"en": "disruption",  "ua": "революційні зміни","example": "AI causes market disruption."},
            {"en": "predict",     "ua": "передбачати",     "example": "AI can predict trends."},
            {"en": "obsolete",    "ua": "застарілий",      "example": "Some jobs will become obsolete."},
            {"en": "innovation",  "ua": "інновація",       "example": "Innovation drives growth."},
            {"en": "deployment",  "ua": "розгортання",     "example": "AI deployment takes time."},
            {"en": "sentient",    "ua": "свідомий",        "example": "Will AI ever be sentient?"},
            {"en": "collaborate", "ua": "співпрацювати",   "example": "Humans and AI collaborate."},
            {"en": "augment",     "ua": "покращувати",     "example": "AI augments human abilities."},
        ],
        "idiom": "The tip of the iceberg",
        "idiom_meaning": "Лише верхівка айсберга — лише мала частина проблеми",
        "mini_story_prompt": "Discuss a debate about AI replacing teachers using: ethical, automate, bias, augment, obsolete.",
    },
    {
        "month": 7, "week": 4,
        "theme": "Online Shopping & E-Commerce",
        "grammar": "Present Perfect vs Past Simple",
        "words": [
            {"en": "checkout",    "ua": "оформлення замовлення","example": "Proceed to checkout."},
            {"en": "cart",        "ua": "кошик",           "example": "Add items to your cart."},
            {"en": "subscription","ua": "підписка",        "example": "Cancel the subscription anytime."},
            {"en": "tracking",    "ua": "відстеження",     "example": "Track your parcel online."},
            {"en": "review",      "ua": "відгук",          "example": "Leave a positive review."},
            {"en": "rating",      "ua": "рейтинг",         "example": "Five-star rating."},
            {"en": "counterfeit", "ua": "підробка",        "example": "Beware of counterfeit goods."},
            {"en": "warranty",    "ua": "гарантія",        "example": "The warranty lasts 2 years."},
            {"en": "marketplace", "ua": "маркетплейс",     "example": "Sell on an online marketplace."},
            {"en": "logistics",   "ua": "логістика",       "example": "Logistics are complex."},
            {"en": "courier",     "ua": "кур'єр",          "example": "The courier delivered late."},
            {"en": "retailer",    "ua": "роздрібний продавець","example": "A major online retailer."},
            {"en": "packaging",   "ua": "упаковка",        "example": "Eco-friendly packaging."},
            {"en": "dispatch",    "ua": "відправка",       "example": "Dispatched within 24 hours."},
            {"en": "bulk",        "ua": "оптом",           "example": "Buy in bulk for discounts."},
        ],
        "idiom": "Shop till you drop",
        "idiom_meaning": "Купувати до знемоги / дуже багато шопінгу",
        "mini_story_prompt": "Tell a story about ordering something online that arrived wrong and dealing with the return using: tracking, warranty, courier, dispatch.",
    },

    # ═══════════════════════════════════════════════════════════════════
    # AUGUST — Health, Wellbeing & Fitness
    # ═══════════════════════════════════════════════════════════════════
    {
        "month": 8, "week": 1,
        "theme": "Health & Medical",
        "grammar": "Should / Shouldn't / Had better — advice and recommendations",
        "words": [
            {"en": "symptom",     "ua": "симптом",         "example": "List your symptoms to the doctor."},
            {"en": "diagnosis",   "ua": "діагноз",         "example": "The diagnosis was a surprise."},
            {"en": "prescription","ua": "рецепт",          "example": "Get a prescription from the GP."},
            {"en": "chronic",     "ua": "хронічний",       "example": "Chronic back pain is common."},
            {"en": "immune",      "ua": "імунний",         "example": "Boost your immune system."},
            {"en": "surgeon",     "ua": "хірург",          "example": "The surgeon performed the operation."},
            {"en": "therapy",     "ua": "терапія",         "example": "Physical therapy helps recovery."},
            {"en": "vaccine",     "ua": "вакцина",         "example": "Get vaccinated every year."},
            {"en": "allergic",    "ua": "алергія",         "example": "She's allergic to penicillin."},
            {"en": "pharmacy",    "ua": "аптека",          "example": "The pharmacy is open 24/7."},
            {"en": "insurance",   "ua": "страхування",     "example": "Health insurance is essential."},
            {"en": "outbreak",    "ua": "спалах",          "example": "A flu outbreak in the city."},
            {"en": "contagious",  "ua": "заразний",        "example": "Is it contagious?"},
            {"en": "recovery",    "ua": "одужання",        "example": "Full recovery takes 2 weeks."},
            {"en": "dosage",      "ua": "дозування",       "example": "Take the correct dosage."},
        ],
        "idiom": "Under the weather",
        "idiom_meaning": "Нездужати / погано почуватися",
        "mini_story_prompt": "Write about visiting a doctor for the first time in a foreign country using: symptom, diagnosis, prescription, pharmacy.",
    },
    {
        "month": 8, "week": 2,
        "theme": "Fitness & Sport",
        "grammar": "Gerunds and Infinitives — I enjoy running / I want to run",
        "words": [
            {"en": "stamina",     "ua": "витривалість",    "example": "Build stamina with cardio."},
            {"en": "flexibility", "ua": "гнучкість",       "example": "Yoga improves flexibility."},
            {"en": "endurance",   "ua": "витривалість",    "example": "Cycling builds endurance."},
            {"en": "workout",     "ua": "тренування",      "example": "A 30-minute workout is enough."},
            {"en": "rep",         "ua": "повторення",      "example": "Do 3 sets of 12 reps."},
            {"en": "hydrate",     "ua": "зволожувати",     "example": "Hydrate before exercising."},
            {"en": "stretch",     "ua": "розтягуватися",   "example": "Always stretch after a workout."},
            {"en": "coach",       "ua": "тренер",          "example": "Hire a personal coach."},
            {"en": "plateau",     "ua": "плато",           "example": "Hit a fitness plateau."},
            {"en": "metabolism",  "ua": "метаболізм",      "example": "Improve your metabolism."},
            {"en": "protein",     "ua": "протеїн",         "example": "Eat enough protein daily."},
            {"en": "interval",    "ua": "інтервал",        "example": "HIIT = high-intensity interval training."},
            {"en": "posture",     "ua": "постава",         "example": "Good posture prevents back pain."},
            {"en": "calorie",     "ua": "калорія",         "example": "Count calories if needed."},
            {"en": "sprint",      "ua": "спринт",          "example": "End each run with a sprint."},
        ],
        "idiom": "No pain, no gain",
        "idiom_meaning": "Без праці нічого не буде / потрібно докласти зусиль",
        "mini_story_prompt": "Write about training for a 10km run as a beginner using: stamina, coach, plateau, hydrate, interval.",
    },
    {
        "month": 8, "week": 3,
        "theme": "Mental Health & Emotions",
        "grammar": "Adjectives vs Adverbs — feel good / feel well / work hard / hardly work",
        "words": [
            {"en": "anxiety",     "ua": "тривога",         "example": "Anxiety affects many people."},
            {"en": "mindfulness", "ua": "усвідомленість",  "example": "Practice mindfulness daily."},
            {"en": "burnout",     "ua": "вигорання",       "example": "I experienced burnout last year."},
            {"en": "resilience",  "ua": "стресостійкість", "example": "Build emotional resilience."},
            {"en": "cope",        "ua": "справлятися",     "example": "How do you cope with stress?"},
            {"en": "overwhelmed", "ua": "переповнений",    "example": "I feel overwhelmed today."},
            {"en": "therapist",   "ua": "терапевт",        "example": "See a therapist if needed."},
            {"en": "self-care",   "ua": "самоздоров'я",    "example": "Self-care is not selfish."},
            {"en": "gratitude",   "ua": "вдячність",       "example": "Practice daily gratitude."},
            {"en": "trigger",     "ua": "тригер",          "example": "Identify your stress triggers."},
            {"en": "vent",        "ua": "виговоритися",    "example": "I need to vent about my day."},
            {"en": "empower",     "ua": "надихати",        "example": "Good leaders empower their teams."},
            {"en": "solitude",    "ua": "самотність",      "example": "I enjoy peaceful solitude."},
            {"en": "detox",       "ua": "детокс",          "example": "A social media detox helps."},
            {"en": "balance",     "ua": "баланс",          "example": "Work-life balance is key."},
        ],
        "idiom": "Take it with a grain of salt",
        "idiom_meaning": "Ставитися скептично / не приймати все буквально",
        "mini_story_prompt": "Write about someone recovering from burnout and learning to set boundaries using: overwhelmed, resilience, cope, self-care, mindfulness.",
    },
    {
        "month": 8, "week": 4,
        "theme": "Nature & Environment",
        "grammar": "Passive Voice — Past Simple (was built, were destroyed)",
        "words": [
            {"en": "ecosystem",   "ua": "екосистема",      "example": "Protect the local ecosystem."},
            {"en": "sustainable", "ua": "сталий",          "example": "Sustainable energy is the future."},
            {"en": "deforestation","ua": "вирубка лісів",  "example": "Deforestation harms biodiversity."},
            {"en": "emission",    "ua": "викиди",          "example": "Reduce carbon emissions."},
            {"en": "renewable",   "ua": "відновлювальний", "example": "Renewable energy sources."},
            {"en": "drought",     "ua": "посуха",          "example": "A severe drought hit the region."},
            {"en": "biodiversity","ua": "біорізноманіття", "example": "Protect biodiversity at all costs."},
            {"en": "recycle",     "ua": "переробляти",     "example": "Recycle plastic and glass."},
            {"en": "habitat",     "ua": "середовище проживання","example": "Natural habitat destruction."},
            {"en": "conservation","ua": "охорона природи", "example": "Wildlife conservation is vital."},
            {"en": "glacier",     "ua": "льодовик",        "example": "Glaciers are melting rapidly."},
            {"en": "fossil fuel", "ua": "викопне паливо",  "example": "Fossil fuels pollute the air."},
            {"en": "carbon",      "ua": "вуглець",         "example": "Reduce your carbon footprint."},
            {"en": "erosion",     "ua": "ерозія",          "example": "Soil erosion is a big problem."},
            {"en": "species",     "ua": "вид",             "example": "Many species face extinction."},
        ],
        "idiom": "Save the planet",
        "idiom_meaning": "Рятувати планету — турбуватися про довкілля",
        "mini_story_prompt": "Write about a young activist fighting deforestation using: ecosystem, biodiversity, sustainable, emission, conservation.",
    },

    # ═══════════════════════════════════════════════════════════════════
    # SEPTEMBER — Education & Self-Development
    # ═══════════════════════════════════════════════════════════════════
    {
        "month": 9, "week": 1,
        "theme": "Learning & Education",
        "grammar": "Used to / Would — past habits",
        "words": [
            {"en": "curriculum",  "ua": "навчальна програма","example": "Update the curriculum yearly."},
            {"en": "tuition",     "ua": "навчання/оплата",  "example": "Tuition fees are rising."},
            {"en": "lecture",     "ua": "лекція",           "example": "The lecture lasted 2 hours."},
            {"en": "thesis",      "ua": "дипломна робота",  "example": "Submit your thesis by June."},
            {"en": "scholarship", "ua": "стипендія",        "example": "She won a full scholarship."},
            {"en": "semester",    "ua": "семестр",          "example": "The new semester starts Monday."},
            {"en": "dropout",     "ua": "той, хто покинув навчання","example": "Famous dropouts: Gates, Zuckerberg."},
            {"en": "mentor",      "ua": "наставник",        "example": "Find a good mentor."},
            {"en": "discipline",  "ua": "дисципліна",       "example": "Academic discipline is key."},
            {"en": "certificate", "ua": "сертифікат",       "example": "Get an online certificate."},
            {"en": "plagiarism",  "ua": "плагіат",          "example": "Plagiarism is strictly forbidden."},
            {"en": "internship",  "ua": "стажування",       "example": "Apply for a summer internship."},
            {"en": "extracurricular","ua": "позакласний",   "example": "Join extracurricular activities."},
            {"en": "peer",        "ua": "однолітки/колеги", "example": "Learn from your peers."},
            {"en": "critical thinking","ua": "критичне мислення","example": "Develop critical thinking."},
        ],
        "idiom": "Hit the books",
        "idiom_meaning": "Сісти за книжки / старанно вчитися",
        "mini_story_prompt": "Write about a first-generation university student adjusting to campus life using: scholarship, mentor, peer, curriculum.",
    },
    {
        "month": 9, "week": 2,
        "theme": "Language Learning",
        "grammar": "Relative clauses — who, which, that, where",
        "words": [
            {"en": "fluent",      "ua": "вільно (мова)",   "example": "She speaks fluent Spanish."},
            {"en": "accent",      "ua": "акцент",          "example": "He has a strong French accent."},
            {"en": "bilingual",   "ua": "двомовний",       "example": "Bilingual children think faster."},
            {"en": "immersion",   "ua": "занурення",       "example": "Language immersion works best."},
            {"en": "native",      "ua": "рідний/носій",    "example": "My native language is Ukrainian."},
            {"en": "vocabulary",  "ua": "словниковий запас","example": "Expand your vocabulary daily."},
            {"en": "grammar",     "ua": "граматика",       "example": "Grammar rules can be complex."},
            {"en": "translate",   "ua": "перекладати",     "example": "Don't just translate — think in English."},
            {"en": "idiom",       "ua": "ідіома",          "example": "Idioms are hard to translate."},
            {"en": "pronunciation","ua": "вимова",         "example": "Work on your pronunciation."},
            {"en": "context",     "ua": "контекст",        "example": "Learn words in context."},
            {"en": "phrasebook",  "ua": "розмовник",       "example": "A phrasebook is useful abroad."},
            {"en": "dialect",     "ua": "діалект",         "example": "British and American dialects differ."},
            {"en": "cognate",     "ua": "спорідненe слово", "example": "Cognates help beginners a lot."},
            {"en": "acquire",     "ua": "засвоювати",      "example": "Children acquire language naturally."},
        ],
        "idiom": "It's all Greek to me",
        "idiom_meaning": "Це для мене незрозуміло / китайська грамота",
        "mini_story_prompt": "Write about someone learning Ukrainian during a trip to Kyiv using: immersion, accent, bilingual, context, acquire.",
    },
    {
        "month": 9, "week": 3,
        "theme": "Goal Setting & Productivity",
        "grammar": "Will vs Going to vs Present Continuous — future intentions",
        "words": [
            {"en": "procrastinate","ua": "відкладати",     "example": "Stop procrastinating!"},
            {"en": "prioritize",  "ua": "розставляти пріоритети","example": "Prioritize your top 3 tasks."},
            {"en": "accomplish",  "ua": "досягати",        "example": "What did you accomplish today?"},
            {"en": "consistent",  "ua": "послідовний",     "example": "Be consistent with your habits."},
            {"en": "accountability","ua": "відповідальність","example": "Find an accountability partner."},
            {"en": "momentum",    "ua": "імпульс/розгін",  "example": "Keep the momentum going."},
            {"en": "setback",     "ua": "невдача",         "example": "A setback is not a failure."},
            {"en": "discipline",  "ua": "дисципліна",      "example": "Discipline beats motivation."},
            {"en": "milestone",   "ua": "ключова ціль",    "example": "Celebrate each milestone."},
            {"en": "intention",   "ua": "намір",           "example": "Set clear daily intentions."},
            {"en": "focus",       "ua": "зосередженість",  "example": "Deep focus = better output."},
            {"en": "habit",       "ua": "звичка",          "example": "Build good habits slowly."},
            {"en": "vision",      "ua": "бачення/мрія",    "example": "Have a long-term vision."},
            {"en": "delegate",    "ua": "делегувати",      "example": "Delegate non-critical tasks."},
            {"en": "review",      "ua": "аналізувати",     "example": "Review your week every Sunday."},
        ],
        "idiom": "Rome wasn't built in a day",
        "idiom_meaning": "Рим не відразу будувався — великі речі потребують часу",
        "mini_story_prompt": "Write about someone building a new daily routine from scratch using: habit, consistent, procrastinate, momentum, milestone.",
    },
    {
        "month": 9, "week": 4,
        "theme": "Books, Films & Art",
        "grammar": "Past Perfect — had + past participle (sequence of events)",
        "words": [
            {"en": "plot",        "ua": "сюжет",           "example": "The plot had a surprise twist."},
            {"en": "protagonist", "ua": "головний герой",  "example": "The protagonist is relatable."},
            {"en": "genre",       "ua": "жанр",            "example": "What's your favourite genre?"},
            {"en": "critique",    "ua": "критика",         "example": "Write a film critique."},
            {"en": "narrate",     "ua": "розповідати",     "example": "She narrates the audiobook."},
            {"en": "metaphor",    "ua": "метафора",        "example": "Use a metaphor to explain it."},
            {"en": "sequel",      "ua": "продовження",     "example": "The sequel was even better."},
            {"en": "adapt",       "ua": "адаптувати",      "example": "The book was adapted for film."},
            {"en": "abstract",    "ua": "абстрактний",     "example": "I don't understand abstract art."},
            {"en": "exhibition",  "ua": "виставка",        "example": "Visit the art exhibition."},
            {"en": "compose",     "ua": "складати (музику)","example": "He composed the soundtrack."},
            {"en": "interpret",   "ua": "інтерпретувати",  "example": "How do you interpret this painting?"},
            {"en": "masterpiece", "ua": "шедевр",          "example": "The Mona Lisa is a masterpiece."},
            {"en": "bestseller",  "ua": "бестселер",       "example": "It became an instant bestseller."},
            {"en": "inspiration", "ua": "натхнення",       "example": "What's your inspiration?"},
        ],
        "idiom": "Judge a book by its cover",
        "idiom_meaning": "Судити про щось за зовнішнім виглядом (зазвичай: не роби цього)",
        "mini_story_prompt": "Write a review of a book that changed your perspective using: plot, protagonist, metaphor, masterpiece, interpret.",
    },

    # ═══════════════════════════════════════════════════════════════════
    # OCTOBER — Business & Entrepreneurship
    # ═══════════════════════════════════════════════════════════════════
    {
        "month": 10, "week": 1,
        "theme": "Starting a Business",
        "grammar": "Modal verbs for possibility — might, may, could",
        "words": [
            {"en": "startup",     "ua": "стартап",         "example": "Launch your startup this year."},
            {"en": "founder",     "ua": "засновник",       "example": "She's the co-founder."},
            {"en": "pitch",       "ua": "презентація для інвестора","example": "A 3-minute investor pitch."},
            {"en": "venture",     "ua": "підприємство",    "example": "A bold business venture."},
            {"en": "revenue",     "ua": "дохід",           "example": "Monthly recurring revenue."},
            {"en": "scalable",    "ua": "масштабований",   "example": "Build a scalable product."},
            {"en": "niche",       "ua": "ніша",            "example": "Find a profitable niche."},
            {"en": "competitor",  "ua": "конкурент",       "example": "Know your competitors well."},
            {"en": "market fit",  "ua": "відповідність ринку","example": "Find product-market fit first."},
            {"en": "bootstrap",   "ua": "розвиватися без інвестицій","example": "We bootstrapped for 2 years."},
            {"en": "pivot",       "ua": "змінити напрямок","example": "We had to pivot our model."},
            {"en": "equity",      "ua": "частка",          "example": "Give equity to early employees."},
            {"en": "investor",    "ua": "інвестор",        "example": "Angel investor funded us."},
            {"en": "runway",      "ua": "запас коштів",    "example": "We have 8 months of runway."},
            {"en": "exit",        "ua": "вихід (з бізнесу)","example": "Plan your exit strategy."},
        ],
        "idiom": "The ball is in your court",
        "idiom_meaning": "М'яч на твоєму боці — твоя черга діяти",
        "mini_story_prompt": "Tell the story of a founder who had to pivot their startup after a failed product launch using: pitch, pivot, market fit, investor, runway.",
    },
    {
        "month": 10, "week": 2,
        "theme": "Marketing & Branding",
        "grammar": "Imperatives and persuasive language",
        "words": [
            {"en": "brand",       "ua": "бренд",           "example": "Build a strong brand identity."},
            {"en": "target",      "ua": "цільова аудиторія","example": "Define your target audience."},
            {"en": "campaign",    "ua": "кампанія",        "example": "Launch a social media campaign."},
            {"en": "conversion",  "ua": "конверсія",       "example": "Improve your conversion rate."},
            {"en": "funnel",      "ua": "воронка",         "example": "Top of the marketing funnel."},
            {"en": "retention",   "ua": "утримання",       "example": "Retention beats acquisition."},
            {"en": "testimonial", "ua": "відгук клієнта",  "example": "Add testimonials to your site."},
            {"en": "USP",         "ua": "унікальна торгова пропозиція","example": "What's your USP?"},
            {"en": "organic",     "ua": "органічний",      "example": "Organic reach is shrinking."},
            {"en": "paid ads",    "ua": "платна реклама",  "example": "Run paid ads on Instagram."},
            {"en": "demographics","ua": "демографія",      "example": "Understand your demographics."},
            {"en": "outreach",    "ua": "охоплення",       "example": "Cold outreach still works."},
            {"en": "CTA",         "ua": "заклик до дії",   "example": "Every post needs a clear CTA."},
            {"en": "persona",     "ua": "персонаж-покупець","example": "Create a detailed buyer persona."},
            {"en": "ROI",         "ua": "рентабельність інвестицій","example": "Measure the ROI of each campaign."},
        ],
        "idiom": "Word of mouth",
        "idiom_meaning": "Сарафанне радіо — розповсюдження через особисті рекомендації",
        "mini_story_prompt": "Write about a small business that grew entirely through word of mouth using: brand, testimonial, retention, organic, persona.",
    },
    {
        "month": 10, "week": 3,
        "theme": "Leadership & Management",
        "grammar": "Third Conditional — If + Past Perfect, would have (regrets, hypotheticals)",
        "words": [
            {"en": "motivate",    "ua": "мотивувати",      "example": "How do you motivate your team?"},
            {"en": "empower",     "ua": "надавати повноваження","example": "Empower people to decide."},
            {"en": "micromanage", "ua": "мікроменеджмент", "example": "Don't micromanage your team."},
            {"en": "vision",      "ua": "бачення",         "example": "Share your long-term vision."},
            {"en": "trust",       "ua": "довіра",          "example": "Trust is earned not given."},
            {"en": "conflict",    "ua": "конфлікт",        "example": "Resolve team conflicts early."},
            {"en": "accountability","ua": "відповідальність","example": "Leaders take accountability."},
            {"en": "transparent", "ua": "прозорий",        "example": "Be transparent about problems."},
            {"en": "succession",  "ua": "наступність",     "example": "Plan for leadership succession."},
            {"en": "burnout",     "ua": "вигорання",       "example": "Prevent team burnout proactively."},
            {"en": "inclusive",   "ua": "інклюзивний",     "example": "Build an inclusive culture."},
            {"en": "inspire",     "ua": "надихати",        "example": "Great leaders inspire, not just manage."},
            {"en": "hierarchy",   "ua": "ієрархія",        "example": "Flat hierarchy = faster decisions."},
            {"en": "autonomy",    "ua": "автономія",       "example": "Give your team autonomy."},
            {"en": "KPI",         "ua": "KPI / ключовий показник","example": "Set clear KPIs for everyone."},
        ],
        "idiom": "Lead by example",
        "idiom_meaning": "Показувати приклад своїми діями, а не словами",
        "mini_story_prompt": "Write about a new manager who had to rebuild team trust after a crisis using: trust, transparent, empower, accountability.",
    },
    {
        "month": 10, "week": 4,
        "theme": "Finance & Investment",
        "grammar": "Expressing large numbers, percentages and trends",
        "words": [
            {"en": "portfolio",   "ua": "портфель",        "example": "Diversify your portfolio."},
            {"en": "dividend",    "ua": "дивіденд",        "example": "Quarterly dividend payments."},
            {"en": "asset",       "ua": "актив",           "example": "Property is a great asset."},
            {"en": "liability",   "ua": "пасив/борг",      "example": "Minimize your liabilities."},
            {"en": "inflation",   "ua": "інфляція",        "example": "Inflation erodes savings."},
            {"en": "compound",    "ua": "складні відсотки","example": "Compound interest is powerful."},
            {"en": "liquidity",   "ua": "ліквідність",     "example": "Always maintain liquidity."},
            {"en": "hedge",       "ua": "хеджування",      "example": "Hedge against currency risk."},
            {"en": "volatile",    "ua": "волатильний",     "example": "Crypto is highly volatile."},
            {"en": "index fund",  "ua": "індексний фонд",  "example": "Invest in index funds long-term."},
            {"en": "yield",       "ua": "дохідність",      "example": "What's the annual yield?"},
            {"en": "bear market", "ua": "ведмежий ринок",  "example": "Stay calm in a bear market."},
            {"en": "bull market", "ua": "бичачий ринок",   "example": "Bull markets don't last forever."},
            {"en": "diversify",   "ua": "диверсифікувати", "example": "Never put all eggs in one basket."},
            {"en": "net worth",   "ua": "чиста вартість активів","example": "Calculate your net worth."},
        ],
        "idiom": "Don't put all your eggs in one basket",
        "idiom_meaning": "Не ризикуй всім одразу — диверсифікуй",
        "mini_story_prompt": "Write about someone learning to invest after losing money in crypto using: volatile, diversify, compound, portfolio, inflation.",
    },

    # ═══════════════════════════════════════════════════════════════════
    # NOVEMBER — Society, News & Current Affairs
    # ═══════════════════════════════════════════════════════════════════
    {
        "month": 11, "week": 1,
        "theme": "News & Media",
        "grammar": "Expressing opinions — In my view / I believe / It seems to me",
        "words": [
            {"en": "headline",    "ua": "заголовок",       "example": "The headline was misleading."},
            {"en": "journalist",  "ua": "журналіст",       "example": "An investigative journalist."},
            {"en": "editorial",   "ua": "редакційна стаття","example": "Read the editorial section."},
            {"en": "bias",        "ua": "упередженість",   "example": "Media bias is widespread."},
            {"en": "credible",    "ua": "достовірний",     "example": "Use credible sources only."},
            {"en": "propaganda",  "ua": "пропаганда",      "example": "Recognize propaganda tactics."},
            {"en": "censorship",  "ua": "цензура",         "example": "Censorship limits free speech."},
            {"en": "breaking",    "ua": "термінові новини","example": "Breaking news from Kyiv."},
            {"en": "paparazzi",   "ua": "папараці",        "example": "The paparazzi followed her."},
            {"en": "anonymous",   "ua": "анонімний",       "example": "An anonymous source leaked it."},
            {"en": "exclusive",   "ua": "ексклюзивний",    "example": "An exclusive interview."},
            {"en": "subscription","ua": "передплата",      "example": "Digital news subscription."},
            {"en": "verify",      "ua": "перевіряти",      "example": "Always verify the facts."},
            {"en": "tabloid",     "ua": "таблоїд",         "example": "Tabloids love celebrity gossip."},
            {"en": "correspondent","ua": "кореспондент",   "example": "Foreign correspondent in Gaza."},
        ],
        "idiom": "Read between the lines",
        "idiom_meaning": "Читати між рядків — розуміти прихований смисл",
        "mini_story_prompt": "Write about a journalist who exposes a cover-up story using: credible, bias, verify, anonymous, exclusive.",
    },
    {
        "month": 11, "week": 2,
        "theme": "Politics & Society",
        "grammar": "Passive Voice — used to describe laws, policies, decisions",
        "words": [
            {"en": "democracy",   "ua": "демократія",      "example": "Democracy requires participation."},
            {"en": "policy",      "ua": "політика/закон",  "example": "The new energy policy."},
            {"en": "parliament",  "ua": "парламент",       "example": "Parliament debated the bill."},
            {"en": "corruption",  "ua": "корупція",        "example": "Fight corruption at every level."},
            {"en": "protest",     "ua": "протест",         "example": "A peaceful protest in the capital."},
            {"en": "reform",      "ua": "реформа",         "example": "Educational reform is overdue."},
            {"en": "sanction",    "ua": "санкція",         "example": "Economic sanctions were imposed."},
            {"en": "treaty",      "ua": "угода/договір",   "example": "Sign an international treaty."},
            {"en": "sovereignty", "ua": "суверенітет",     "example": "Defend national sovereignty."},
            {"en": "lobbying",    "ua": "лобіювання",      "example": "Corporate lobbying influences laws."},
            {"en": "constitution","ua": "конституція",     "example": "Amend the constitution."},
            {"en": "referendum",  "ua": "референдум",      "example": "Hold a referendum."},
            {"en": "coalition",   "ua": "коаліція",        "example": "Form a coalition government."},
            {"en": "opposition",  "ua": "опозиція",        "example": "The opposition challenged the bill."},
            {"en": "election",    "ua": "вибори",          "example": "The election results were disputed."},
        ],
        "idiom": "Bite the bullet",
        "idiom_meaning": "Стиснути зуби і зробити щось неприємне, але необхідне",
        "mini_story_prompt": "Write about a politician making an unpopular but necessary reform using: policy, opposition, reform, protest, parliament.",
    },
    {
        "month": 11, "week": 3,
        "theme": "Human Rights & Equality",
        "grammar": "Should have / Could have / Would have — past regrets and criticism",
        "words": [
            {"en": "equality",    "ua": "рівність",        "example": "Fight for equality."},
            {"en": "diversity",   "ua": "різноманіття",    "example": "Diversity strengthens teams."},
            {"en": "privilege",   "ua": "привілей",        "example": "Acknowledge your privilege."},
            {"en": "discrimination","ua": "дискримінація", "example": "Discrimination is illegal."},
            {"en": "minority",    "ua": "меншина",         "example": "Protect minority rights."},
            {"en": "refugee",     "ua": "біженець",        "example": "Refugee status under international law."},
            {"en": "asylum",      "ua": "притулок",        "example": "Apply for asylum."},
            {"en": "empower",     "ua": "розширити права", "example": "Empower marginalized groups."},
            {"en": "stereotype",  "ua": "стереотип",       "example": "Challenge gender stereotypes."},
            {"en": "advocate",    "ua": "захищати/адвокат","example": "Be an advocate for change."},
            {"en": "inclusive",   "ua": "інклюзивний",     "example": "Create inclusive spaces."},
            {"en": "barrier",     "ua": "бар'єр",          "example": "Break barriers to education."},
            {"en": "dignity",     "ua": "гідність",        "example": "Every person has dignity."},
            {"en": "tolerance",   "ua": "толерантність",   "example": "Promote tolerance in schools."},
            {"en": "solidarity",  "ua": "солідарність",    "example": "Show solidarity with Ukraine."},
        ],
        "idiom": "Level the playing field",
        "idiom_meaning": "Вирівняти умови — дати всім рівні можливості",
        "mini_story_prompt": "Write about a refugee who builds a new life in a foreign country using: asylum, dignity, barrier, advocate, solidarity.",
    },
    {
        "month": 11, "week": 4,
        "theme": "Debates & Argumentation",
        "grammar": "Concession clauses — Although / Even though / Despite / However",
        "words": [
            {"en": "argument",    "ua": "аргумент",        "example": "A strong argument wins debates."},
            {"en": "evidence",    "ua": "докази",          "example": "Provide concrete evidence."},
            {"en": "counterargument","ua": "контраргумент","example": "Address every counterargument."},
            {"en": "perspective", "ua": "точка зору",      "example": "Consider all perspectives."},
            {"en": "controversial","ua": "суперечливий",   "example": "A controversial topic."},
            {"en": "neutral",     "ua": "нейтральний",     "example": "Stay neutral in debates."},
            {"en": "convince",    "ua": "переконувати",    "example": "She convinced the jury."},
            {"en": "rebut",       "ua": "спростовувати",   "example": "Rebut the opponent's claim."},
            {"en": "assumption",  "ua": "припущення",      "example": "Don't make assumptions."},
            {"en": "fallacy",     "ua": "помилкова думка", "example": "Spot logical fallacies."},
            {"en": "debate",      "ua": "дискусія",        "example": "Win debates with logic."},
            {"en": "stance",      "ua": "позиція",         "example": "What's your stance on this?"},
            {"en": "consensus",   "ua": "консенсус",       "example": "Reach a consensus."},
            {"en": "compromise",  "ua": "компроміс",       "example": "Compromise is not weakness."},
            {"en": "rhetoric",    "ua": "риторика",        "example": "Master the art of rhetoric."},
        ],
        "idiom": "The devil is in the details",
        "idiom_meaning": "Проблема в деталях — саме деталі визначають успіх чи невдачу",
        "mini_story_prompt": "Write about a student preparing for a university debate on AI ethics using: argument, evidence, counterargument, fallacy, convince.",
    },

    # ═══════════════════════════════════════════════════════════════════
    # DECEMBER — Review, Reflection & Future
    # ═══════════════════════════════════════════════════════════════════
    {
        "month": 12, "week": 1,
        "theme": "Celebrations & Holidays",
        "grammar": "Wishes and hypotheticals — I wish / If only",
        "words": [
            {"en": "celebrate",   "ua": "святкувати",      "example": "Let's celebrate together!"},
            {"en": "tradition",   "ua": "традиція",        "example": "Keep family traditions alive."},
            {"en": "ceremony",    "ua": "церемонія",       "example": "A graduation ceremony."},
            {"en": "toast",       "ua": "тост",            "example": "Let's make a toast!"},
            {"en": "countdown",   "ua": "зворотній відлік","example": "The New Year countdown begins."},
            {"en": "reunion",     "ua": "возз'єднання",    "example": "A family reunion dinner."},
            {"en": "festive",     "ua": "святковий",       "example": "A festive atmosphere."},
            {"en": "fireworks",   "ua": "феєрверк",        "example": "Watch the fireworks display."},
            {"en": "carol",       "ua": "колядка",         "example": "Sing Christmas carols."},
            {"en": "resolution",  "ua": "рішення/ціль",    "example": "New Year's resolution."},
            {"en": "gratitude",   "ua": "вдячність",       "example": "Express gratitude to loved ones."},
            {"en": "nostalgia",   "ua": "ностальгія",      "example": "Feel nostalgia for childhood."},
            {"en": "cherish",     "ua": "дорожити",        "example": "Cherish every moment."},
            {"en": "memorable",   "ua": "незабутній",      "example": "A truly memorable evening."},
            {"en": "generous",    "ua": "щедрий",          "example": "Be generous during the holidays."},
        ],
        "idiom": "Once in a blue moon",
        "idiom_meaning": "Дуже рідко / раз на рік",
        "mini_story_prompt": "Write about a family reunion after years apart during the New Year holidays using: reunion, nostalgia, cherish, toast, festive.",
    },
    {
        "month": 12, "week": 2,
        "theme": "Review: Year in Review",
        "grammar": "Mixed tenses revision — telling a complete story",
        "words": [
            {"en": "reflect",     "ua": "рефлексувати",    "example": "Reflect on your achievements."},
            {"en": "accomplish",  "ua": "досягнути",       "example": "What did you accomplish this year?"},
            {"en": "overcome",    "ua": "подолати",        "example": "You overcame so many obstacles."},
            {"en": "growth",      "ua": "ріст",            "example": "Personal growth takes courage."},
            {"en": "challenge",   "ua": "виклик",          "example": "Every challenge made you stronger."},
            {"en": "regret",      "ua": "жалкувати",       "example": "No regrets — only lessons."},
            {"en": "grateful",    "ua": "вдячний",         "example": "Be grateful for small things."},
            {"en": "milestone",   "ua": "важливий момент", "example": "Celebrate every milestone."},
            {"en": "evolve",      "ua": "еволюціонувати",  "example": "You've evolved so much."},
            {"en": "inspire",     "ua": "надихати",        "example": "Your story inspires others."},
            {"en": "persistence", "ua": "наполегливість",  "example": "Persistence pays off."},
            {"en": "journey",     "ua": "шлях/подорож",    "example": "Life is a journey, enjoy it."},
            {"en": "breakthrough","ua": "прорив",          "example": "A major career breakthrough."},
            {"en": "resilient",   "ua": "стійкий",         "example": "You're more resilient than you think."},
            {"en": "vision",      "ua": "бачення",         "example": "Keep the vision alive."},
        ],
        "idiom": "Every cloud has a silver lining",
        "idiom_meaning": "В кожній темній хмарі є срібна підкладка — у кожній біді є щось добре",
        "mini_story_prompt": "Write a personal year-in-review letter using: reflect, overcome, growth, breakthrough, resilient, grateful.",
    },
    {
        "month": 12, "week": 3,
        "theme": "New Year Goals & Dreams",
        "grammar": "Future Perfect — will have done (predictions about completed actions)",
        "words": [
            {"en": "aspire",      "ua": "прагнути",        "example": "Aspire to be better each day."},
            {"en": "ambition",    "ua": "амбіція",         "example": "Ambition drives success."},
            {"en": "blueprint",   "ua": "план/схема",      "example": "Create a blueprint for the year."},
            {"en": "transform",   "ua": "трансформуватися","example": "Transform your mindset."},
            {"en": "commit",      "ua": "зобов'язатися",   "example": "Commit to your goals fully."},
            {"en": "dedicate",    "ua": "присвячувати",    "example": "Dedicate time to what matters."},
            {"en": "persist",     "ua": "наполягати",      "example": "Persist even when it's hard."},
            {"en": "envision",    "ua": "уявляти",         "example": "Envision your ideal future."},
            {"en": "intention",   "ua": "намір",           "example": "Set powerful daily intentions."},
            {"en": "discipline",  "ua": "дисципліна",      "example": "Discipline is freedom."},
            {"en": "abundance",   "ua": "достаток",        "example": "Live with an abundance mindset."},
            {"en": "manifest",    "ua": "проявляти",       "example": "Manifest your dreams with action."},
            {"en": "legacy",      "ua": "спадщина",        "example": "What legacy will you leave?"},
            {"en": "horizon",     "ua": "горизонт",        "example": "New horizons await you."},
            {"en": "purpose",     "ua": "мета/призначення","example": "Live with purpose."},
        ],
        "idiom": "The sky is the limit",
        "idiom_meaning": "Немає меж — можна досягнути всього",
        "mini_story_prompt": "Write a New Year vision letter for 2027 using: aspire, transform, commit, legacy, vision, abundance.",
    },
    {
        "month": 12, "week": 4,
        "theme": "English Fluency Celebration",
        "grammar": "All tenses revision — telling your language learning story",
        "words": [
            {"en": "fluent",      "ua": "вільно (мова)",   "example": "I speak fluent English now!"},
            {"en": "confident",   "ua": "впевнений",       "example": "Speak confidently, not perfectly."},
            {"en": "progress",    "ua": "прогрес",         "example": "Track your language progress."},
            {"en": "consistent",  "ua": "послідовний",     "example": "Stay consistent for 9 months."},
            {"en": "community",   "ua": "спільнота",       "example": "Our community helped me grow."},
            {"en": "vocabulary",  "ua": "словниковий запас","example": "1000+ new words learned!"},
            {"en": "grammar",     "ua": "граматика",       "example": "Grammar feels natural now."},
            {"en": "practice",    "ua": "практикувати",    "example": "Daily practice = real results."},
            {"en": "celebrate",   "ua": "святкувати",      "example": "Celebrate every win!"},
            {"en": "dedicate",    "ua": "присвячувати",    "example": "I dedicated 9 months."},
            {"en": "achieve",     "ua": "досягати",        "example": "You achieved something amazing."},
            {"en": "proud",       "ua": "гордий",          "example": "Be proud of yourself."},
            {"en": "journey",     "ua": "шлях",            "example": "The learning journey continues."},
            {"en": "inspire",     "ua": "надихати",        "example": "Inspire others to start."},
            {"en": "continue",    "ua": "продовжувати",    "example": "Never stop learning."},
        ],
        "idiom": "Practice makes perfect",
        "idiom_meaning": "Повторення — мати навчання",
        "mini_story_prompt": "Write a celebration post about completing 9 months of daily English learning using: fluent, confident, community, journey, proud.",
    },
]

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_week(month: int, week: int) -> WeekPlan | None:
    """Return the plan for a given month (4-12) and week (1-4)."""
    for plan in CURRICULUM:
        if plan["month"] == month and plan["week"] == week:
            return plan
    return None


def get_month(month: int) -> list[WeekPlan]:
    """Return all 4 weeks for a given month."""
    return [p for p in CURRICULUM if p["month"] == month]


def get_month_overview(month: int) -> str:
    """Return a formatted text overview of the month for the teacher bot."""
    month_names = {
        4: "April", 5: "May", 6: "June", 7: "July",
        8: "August", 9: "September", 10: "October",
        11: "November", 12: "December"
    }
    weeks = get_month(month)
    if not weeks:
        return "No content for this month."

    name = month_names.get(month, str(month))
    lines = [f"<b>📅 {name} — Content Overview</b>\n"]
    for w in weeks:
        lines.append(
            f"<b>Week {w['week']}: {w['theme']}</b>\n"
            f"  📚 Grammar: {w['grammar']}\n"
            f"  💬 Idiom: <i>{w['idiom']}</i> — {w['idiom_meaning']}\n"
        )
    return "\n".join(lines)


def get_daily_words(month: int, week: int, day: int) -> list[dict]:
    """
    Return 3 words for a specific day (1=Mon … 5=Fri).
    Words are split across weekdays: day1=[0,1,2], day2=[3,4,5], ...
    """
    plan = get_week(month, week)
    if not plan:
        return []
    start = (day - 1) * 3
    return plan["words"][start:start + 3]


def get_current_week_plan() -> WeekPlan | None:
    """Return the plan for the current week based on today's date."""
    from datetime import date
    today = date.today()
    month = today.month
    # Week 1=days 1-7, week 2=8-14, week 3=15-21, week 4=22-31
    week = min((today.day - 1) // 7 + 1, 4)
    return get_week(month, week)


if __name__ == "__main__":
    # Quick test
    plan = get_current_week_plan()
    if plan:
        print(f"Current week: Month {plan['month']}, Week {plan['week']}")
        print(f"Theme: {plan['theme']}")
        print(f"Grammar: {plan['grammar']}")
        print(f"Today's words: {get_daily_words(plan['month'], plan['week'], 1)}")
    else:
        print("No plan for current week.")
