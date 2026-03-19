// ThreeWordsDaily Mini App
// Telegram WebApp SDK + backend API

const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  tg.setHeaderColor('#0f0f13');
  tg.setBackgroundColor('#0f0f13');
}

// ===== STATE =====
const API_URL = window.location.origin; // той самий хост де хостимо mini app
// або хардкод: const API_URL = 'https://your-backend.vercel.app';

const state = {
  userId: tg?.initDataUnsafe?.user?.id || 'demo',
  firstName: tg?.initDataUnsafe?.user?.first_name || 'Друже',
  lesson: null,
  streak: 0,
  xp: 0,
  wordsLearned: [],
  level: 'A2',
  topic: 'everyday',
  tasksCompleted: [],
  currentTab: 'lesson',
  quizActive: false,
};

// ===== LOCAL STORAGE =====
function saveState() {
  localStorage.setItem('twd_state', JSON.stringify({
    streak: state.streak,
    xp: state.xp,
    wordsLearned: state.wordsLearned,
    level: state.level,
    topic: state.topic,
    tasksCompleted: state.tasksCompleted,
    lastLesson: state.lastLesson,
  }));
}

function loadState() {
  const saved = localStorage.getItem('twd_state');
  if (saved) {
    const s = JSON.parse(saved);
    Object.assign(state, s);
  }
}

// ===== RANKS =====
function getRank(xp) {
  if (xp >= 1000) return { rank: '👑 Майстер', next: 9999 };
  if (xp >= 500)  return { rank: '💎 Експерт', next: 1000 };
  if (xp >= 200)  return { rank: '🔥 Практик', next: 500 };
  if (xp >= 50)   return { rank: '⚡ Учень', next: 200 };
  return { rank: '🌱 Новачок', next: 50 };
}

// ===== MOCK LESSON DATA (fallback if no backend) =====
const MOCK_LESSONS = [
  {
    words: [
      { word: 'resilient', transcription: '/rɪˈzɪliənt/', translation: 'стійкий', example: "She's incredibly resilient under pressure.", example_ua: 'Вона неймовірно стійка під тиском.' },
      { word: 'ambitious', transcription: '/æmˈbɪʃəs/', translation: 'амбітний', example: "He's ambitious about his career goals.", example_ua: 'Він амбітний щодо своїх кар\'єрних цілей.' },
      { word: 'persistent', transcription: '/pərˈsɪstənt/', translation: 'наполегливий', example: 'Persistent effort leads to success.', example_ua: 'Наполеглива праця веде до успіху.' },
    ],
    idiom: { text: 'break a leg', translation: 'ні пуху ні пера (удачі)', example: 'Break a leg in your presentation!', example_ua: 'Удачі на презентації!' },
    quiz: { question: 'Що означає "resilient"?', answers: ['стійкий', 'розслаблений', 'швидкий', 'щасливий'], correct: 0 },
    mini_story: "Alex was resilient and ambitious. Despite failures, he remained persistent.",
    mini_story_ua: "Алекс був стійким та амбітним. Незважаючи на невдачі, він залишався наполегливим.",
  },
  {
    words: [
      { word: 'thrive', transcription: '/θraɪv/', translation: 'процвітати', example: 'Plants thrive in sunlight.', example_ua: 'Рослини процвітають на сонці.' },
      { word: 'genuine', transcription: '/ˈdʒɛnjuɪn/', translation: 'щирий, справжній', example: 'Her smile was genuine.', example_ua: 'Її посмішка була щирою.' },
      { word: 'overwhelmed', transcription: '/ˌoʊvərˈwɛlmd/', translation: 'перевантажений', example: 'I feel overwhelmed with work.', example_ua: 'Я почуваюся перевантаженим роботою.' },
    ],
    idiom: { text: 'go the extra mile', translation: 'докласти додаткових зусиль', example: 'She always goes the extra mile for clients.', example_ua: 'Вона завжди докладає додаткових зусиль для клієнтів.' },
    quiz: { question: 'Що означає "overwhelmed"?', answers: ['перевантажений', 'щасливий', 'амбітний', 'сміливий'], correct: 0 },
    mini_story: "Sarah thrived in her new job. She was genuine and never overwhelmed.",
    mini_story_ua: "Сара процвітала на новій роботі. Вона була щирою і ніколи не перевантажувалась.",
  },
];

const TASKS = [
  { id: 'lesson_today', icon: '📚', title: 'Пройти урок дня', desc: 'Вивчи 3 нових слова', reward: '+15 XP', xp: 15 },
  { id: 'quiz_pass', icon: '🧠', title: 'Пройти тест', desc: 'Дай правильну відповідь', reward: '+10 XP', xp: 10 },
  { id: 'mark_learned', icon: '✅', title: 'Позначити слова', desc: 'Натисни "Вивчив"', reward: '+20 XP', xp: 20 },
  { id: 'streak_3', icon: '🔥', title: '3 дні поспіль', desc: 'Тримай streak 3 дні', reward: '+50 XP', xp: 50 },
  { id: 'words_10', icon: '📖', title: '10 слів у словнику', desc: 'Вивчи 10 слів загалом', reward: '+30 XP', xp: 30 },
];

const REWARDS = [
  { icon: '🌱', name: 'Початківець', req: 'XP 0', xp: 0 },
  { icon: '⚡', name: 'Учень', req: 'XP 50', xp: 50 },
  { icon: '🔥', name: 'Практик', req: 'XP 200', xp: 200 },
  { icon: '💎', name: 'Експерт', req: 'XP 500', xp: 500 },
  { icon: '👑', name: 'Майстер', req: 'XP 1000', xp: 1000 },
  { icon: '🏆', name: 'Легенда', req: '30д streak', xp: 0, streakReq: 30 },
];

const MOCK_LEADERBOARD = [
  { name: 'Олена К.', xp: 840, streak: 12, me: false },
  { name: 'Максим В.', xp: 720, streak: 8, me: false },
  { name: 'Аня Т.', xp: 650, streak: 15, me: false },
];

const TOPICS = [
  { key: 'everyday', label: 'Повсякденне', icon: '💬' },
  { key: 'work', label: 'Робота', icon: '💼' },
  { key: 'travel', label: 'Подорожі', icon: '✈️' },
  { key: 'emotions', label: 'Емоції', icon: '❤️' },
  { key: 'technology', label: 'Технології', icon: '💻' },
  { key: 'mixed', label: 'Мікс', icon: '🎲' },
];

const LEVELS = [
  { key: 'A1', label: 'A1', icon: '🟢' },
  { key: 'A2', label: 'A2', icon: '🔵' },
  { key: 'B1', label: 'B1', icon: '🟡' },
  { key: 'B2', label: 'B2', icon: '🟠' },
];

// ===== API CALLS =====
async function fetchLesson() {
  try {
    const res = await fetch(`${API_URL}/api/lesson?level=${state.level}&topic=${state.topic}&user_id=${state.userId}`);
    if (res.ok) return await res.json();
  } catch (e) {}
  // fallback to mock
  return MOCK_LESSONS[Math.floor(Math.random() * MOCK_LESSONS.length)];
}

async function fetchLeaderboard() {
  try {
    const res = await fetch(`${API_URL}/api/leaderboard`);
    if (res.ok) return await res.json();
  } catch (e) {}
  return MOCK_LEADERBOARD;
}

// ===== UI UPDATES =====
function updateHeader() {
  document.getElementById('streakCount').textContent = state.streak;
  document.getElementById('xpCount').textContent = state.xp;
  const { rank, next } = getRank(state.xp);
  document.getElementById('rankLabel').textContent = rank;
  const pct = Math.min(100, (state.xp / next) * 100);
  document.getElementById('xpFill').style.width = pct + '%';
}

function renderWordCards(lesson) {
  const container = document.getElementById('wordCards');
  container.innerHTML = lesson.words.map((w, i) => `
    <div class="word-card">
      <div class="word-main">
        <div>
          <div class="word-text">${w.word}</div>
          <div class="word-transcription">${w.transcription}</div>
        </div>
        <div class="word-num">${i + 1}/3</div>
      </div>
      <div class="word-translation">${w.translation}</div>
      <div class="word-example">"${w.example}"</div>
      <div class="word-example-ua">${w.example_ua}</div>
    </div>
  `).join('');
}

function renderIdiom(lesson) {
  const { idiom } = lesson;
  document.getElementById('idiomCard').innerHTML = `
    <div class="idiom-text">"${idiom.text}"</div>
    <div class="idiom-translation">🇺🇦 ${idiom.translation}</div>
    <div class="idiom-example">"${idiom.example}"</div>
    <div class="word-example-ua">${idiom.example_ua}</div>
  `;
}

function renderTasks() {
  const container = document.getElementById('tasksList');
  container.innerHTML = TASKS.map(t => {
    const done = state.tasksCompleted.includes(t.id);
    return `
      <div class="task-item ${done ? 'done' : ''}">
        <div class="task-icon">${t.icon}</div>
        <div class="task-info">
          <div class="task-title">${t.title}</div>
          <div class="task-desc">${t.desc}</div>
        </div>
        ${done
          ? '<div class="task-done-mark">✅</div>'
          : `<div class="task-reward">${t.reward}</div>`
        }
      </div>`;
  }).join('');

  const rewards = document.getElementById('rewardsGrid');
  rewards.innerHTML = REWARDS.map(r => {
    const unlocked = state.xp >= (r.xp || 0) && (!r.streakReq || state.streak >= r.streakReq);
    return `
      <div class="reward-item ${unlocked ? '' : 'locked'}">
        <div class="reward-icon">${r.icon}</div>
        <div class="reward-name">${r.name}</div>
        <div class="reward-req">${r.req}</div>
      </div>`;
  }).join('');
}

async function renderLeaderboard() {
  const lb = await fetchLeaderboard();
  const myEntry = { name: state.firstName, xp: state.xp, streak: state.streak, me: true };
  const all = [...lb, myEntry].sort((a, b) => b.xp - a.xp);

  const medals = ['🥇', '🥈', '🥉'];
  document.getElementById('leaderboard').innerHTML = all.map((u, i) => `
    <div class="leader-item ${u.me ? 'me' : ''}">
      <div class="leader-rank">${medals[i] || `#${i + 1}`}</div>
      <div>
        <div class="leader-name">${u.me ? '👤 ' + u.name + ' (ти)' : u.name}</div>
        <div class="leader-sub">🔥 ${u.streak} днів streak</div>
      </div>
      <div class="leader-xp">⭐ ${u.xp}</div>
    </div>
  `).join('');
}

function renderProfile() {
  const { rank } = getRank(state.xp);
  document.getElementById('profileCard').innerHTML = `
    <div class="profile-avatar">👤</div>
    <div class="profile-name">${state.firstName}</div>
    <div class="profile-rank">${rank}</div>
    <div class="profile-stats">
      <div class="stat-box">
        <div class="stat-num">🔥 ${state.streak}</div>
        <div class="stat-label">Streak</div>
      </div>
      <div class="stat-box">
        <div class="stat-num">📚 ${state.wordsLearned.length}</div>
        <div class="stat-label">Слів</div>
      </div>
      <div class="stat-box">
        <div class="stat-num">⭐ ${state.xp}</div>
        <div class="stat-label">XP</div>
      </div>
    </div>
  `;

  const words = document.getElementById('learnedWords');
  words.innerHTML = state.wordsLearned.length
    ? state.wordsLearned.map(w => `<span class="word-chip">${w}</span>`).join('')
    : '<span style="color:var(--text2);font-size:13px">Ще немає вивчених слів</span>';

  // Topics
  document.getElementById('topicGrid').innerHTML = TOPICS.map(t => `
    <div class="topic-btn ${state.topic === t.key ? 'active' : ''}" onclick="setTopic('${t.key}')">
      <span>${t.icon}</span>${t.label}
    </div>
  `).join('');

  // Levels
  document.getElementById('levelGrid').innerHTML = LEVELS.map(l => `
    <div class="level-btn ${state.level === l.key ? 'active' : ''}" onclick="setLevel('${l.key}')">
      <span>${l.icon}</span>${l.label}
    </div>
  `).join('');
}

// ===== ACTIONS =====
function switchTab(tab) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
  document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
  document.getElementById(`tab-${tab}`).classList.remove('hidden');
  state.currentTab = tab;

  if (tab === 'top') renderLeaderboard();
  if (tab === 'profile') renderProfile();
  if (tab === 'tasks') renderTasks();
}

function startQuiz() {
  const lesson = state.lesson;
  if (!lesson) return;
  document.getElementById('quizBlock').classList.remove('hidden');
  document.getElementById('quizQuestion').textContent = '❓ ' + lesson.quiz.question;

  const answersEl = document.getElementById('quizAnswers');
  answersEl.innerHTML = lesson.quiz.answers.map((a, i) => `
    <button class="quiz-answer" onclick="checkAnswer(${i})">${a}</button>
  `).join('');
}

function checkAnswer(idx) {
  const lesson = state.lesson;
  const correct = lesson.quiz.correct;
  const btns = document.querySelectorAll('.quiz-answer');

  btns.forEach((btn, i) => {
    btn.onclick = null;
    if (i === correct) btn.classList.add('correct');
    else if (i === idx && i !== correct) btn.classList.add('wrong');
  });

  if (idx === correct) {
    addXP(15);
    completeTask('quiz_pass');
    tg?.HapticFeedback?.impactOccurred('medium');
    showResult('success', '✅ Правильно! +15 XP');
  } else {
    tg?.HapticFeedback?.impactOccurred('light');
    showResult('fail', '❌ Не вірно. Правильна: ' + lesson.quiz.answers[correct]);
  }
}

function showResult(type, text) {
  const old = document.querySelector('.result-banner');
  if (old) old.remove();
  const el = document.createElement('div');
  el.className = `result-banner ${type}`;
  el.innerHTML = text;
  document.getElementById('quizBlock').after(el);
  setTimeout(() => el.remove(), 3000);
}

function markLearned() {
  const lesson = state.lesson;
  if (!lesson) return;
  lesson.words.forEach(w => {
    if (!state.wordsLearned.includes(w.word)) {
      state.wordsLearned.push(w.word);
    }
  });
  addXP(20);
  completeTask('mark_learned');
  completeTask('lesson_today');
  tg?.HapticFeedback?.notificationOccurred('success');
  saveState();

  if (state.wordsLearned.length >= 10) completeTask('words_10');

  showResult('success', `✅ Збережено! +20 XP | Слів: ${state.wordsLearned.length}`);
}

function addXP(amount) {
  state.xp += amount;
  saveState();
  updateHeader();
}

function completeTask(id) {
  if (!state.tasksCompleted.includes(id)) {
    state.tasksCompleted.push(id);
    saveState();
  }
}

function setTopic(topic) {
  state.topic = topic;
  saveState();
  renderProfile();
}

function setLevel(level) {
  state.level = level;
  saveState();
  renderProfile();
}

// ===== INIT =====
async function init() {
  loadState();
  updateHeader();

  // Load lesson
  const lesson = await fetchLesson();
  state.lesson = lesson;
  renderWordCards(lesson);
  renderIdiom(lesson);

  // Update streak
  const today = new Date().toDateString();
  if (state.lastLesson !== today) {
    const yesterday = new Date(Date.now() - 86400000).toDateString();
    state.streak = state.lastLesson === yesterday ? state.streak + 1 : 1;
    state.lastLesson = today;
    saveState();
    updateHeader();
    if (state.streak >= 3) completeTask('streak_3');
  }
}

init();
