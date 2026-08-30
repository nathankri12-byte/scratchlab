const app = document.querySelector("#app");
const authAction = document.querySelector("#authAction");

const state = {
  user: null,
  courses: [],
  progress: { completed: [], badges: [], courseProgress: [], projects: [] },
  projects: { own: [], public: [] },
  pricing: null
};

const completedIds = () => new Set(state.progress.completed.map(item => item.lesson_id));
const allLessons = () => state.courses.flatMap(course => course.lessons.map(lesson => ({ ...lesson, courseId: course.id, courseTitle: course.title })));

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    credentials: "same-origin",
    ...options
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Etwas ist schiefgelaufen.");
  return data;
}

async function refresh() {
  const [me, courses, pricing] = await Promise.all([api("/api/me"), api("/api/courses"), api("/api/pricing")]);
  state.user = me.user;
  state.courses = courses.courses;
  state.pricing = pricing;
  authAction.textContent = state.user ? "Logout" : "Einloggen";
  if (state.user) {
    state.progress = await api("/api/progress");
  } else {
    state.progress = { completed: [], badges: [], courseProgress: [], projects: [] };
  }
}

function setView(html) {
  app.innerHTML = html;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function renderLanding() {
  setView(`
    <section class="hero">
      <div class="hero-copy">
        <p class="eyebrow">Scratch lernen, ohne Schulgefuehl</p>
        <h1>ScratchLab</h1>
        <p class="lead">Programmieren lernen. Scratch verstehen. Eigene Ideen bauen.</p>
        <div class="hero-actions">
          <a class="primary-button" href="#/signup">Kostenlos starten</a>
          <a class="secondary-button" href="#/learn">Kurse ansehen</a>
        </div>
      </div>
      <div class="play-stage" aria-label="ScratchLab Vorschau">
        <div class="stage-header"><span></span><span></span><span></span></div>
        <div class="sprite"></div>
        <div class="speech">Ich baue mein erstes Spiel!</div>
        <div class="blocks"><span>Wenn Flagge geklickt</span><span>bewege Figur</span><span>+ XP</span></div>
      </div>
    </section>
    <section class="feature-band">
      <article><strong>1. Kurz verstehen</strong><span>Jede Lektion startet mit einem klaren Lernziel.</span></article>
      <article><strong>2. Selbst bauen</strong><span>Du probierst direkt in Scratch und siehst ein Ergebnis.</span></article>
      <article><strong>3. Weiter wachsen</strong><span>XP, Badges, Projekte und KI-Hilfe halten dich im Flow.</span></article>
    </section>
    <section class="screen landing-grid">
      <div class="panel">
        <h3>${state.courses.length} Kurse, ${allLessons().length} Lektionen</h3>
        <p>Von der ersten sprechenden Figur bis zum eigenen Mini-Spiel.</p>
        <a class="secondary-button" href="#/learn">Kursuebersicht</a>
      </div>
      <div class="panel">
        <h3>KI-Tutor</h3>
        <p>Gemini hilft mit Fragen, Tipps und kleinen Denkanstoessen, ohne dir sofort alles fertig zu loesen.</p>
      </div>
      <div class="panel">
        <h3>Projektpruefung</h3>
        <p>Lade spaeter deine `.sb3`-Datei hoch und ScratchLab prueft wichtige Bloecke automatisch.</p>
      </div>
    </section>
  `);
}

function renderAuth(mode = "signup") {
  const isSignup = mode === "signup";
  setView(`
    <section class="screen grid two">
      <div>
        <p class="eyebrow">${isSignup ? "Kostenlos starten" : "Willkommen zurueck"}</p>
        <h2>${isSignup ? "In 60 Sekunden bereit fuer die erste Scratch-Aufgabe." : "Weiterlernen, wo du aufgehoert hast."}</h2>
        <p>Dein Fortschritt, XP, Badges und Projekte werden gespeichert.</p>
      </div>
      <div class="panel">
        <form id="authForm">
          ${isSignup ? `<label>Benutzername<input name="username" autocomplete="nickname" required minlength="3"></label>` : ""}
          <label>E-Mail<input name="email" type="email" autocomplete="email" required></label>
          <label>Passwort<input name="password" type="password" autocomplete="${isSignup ? "new-password" : "current-password"}" required minlength="8"></label>
          <button class="primary-button" type="submit">${isSignup ? "Account erstellen" : "Einloggen"}</button>
          <p class="muted">${isSignup ? `Schon dabei? <a href="#/login">Einloggen</a>` : `Neu hier? <a href="#/signup">Kostenlos starten</a>`}</p>
          <p id="authError" class="error"></p>
        </form>
      </div>
    </section>
  `);
  document.querySelector("#authForm").addEventListener("submit", async event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const result = await api(isSignup ? "/api/auth/register" : "/api/auth/login", {
        method: "POST",
        body: JSON.stringify(Object.fromEntries(form.entries()))
      });
      state.user = result.user;
      location.hash = "#/dashboard";
    } catch (error) {
      document.querySelector("#authError").textContent = error.message;
    }
  });
}

function renderDashboard() {
  if (!state.user) {
    location.hash = "#/signup";
    return;
  }
  const next = state.progress.nextLesson || allLessons()[0];
  const totalLessons = allLessons().length;
  const doneCount = state.progress.completed.length;
  const percent = totalLessons ? Math.round(doneCount / totalLessons * 100) : 0;
  setView(`
    <section class="screen">
      <div class="screen-header">
        <div>
          <p class="eyebrow">Dashboard</p>
          <h2>Hi ${escapeHtml(state.user.username)}, weiter geht's.</h2>
          <p>Dein naechster sinnvoller Schritt ist schon bereit.</p>
        </div>
        ${statsHtml()}
      </div>
      <div class="panel">
        <div class="progress-row"><strong>Gesamtfortschritt</strong><span>${doneCount}/${totalLessons} Lektionen</span></div>
        <div class="progress-track"><span style="width:${percent}%"></span></div>
      </div>
      <div class="grid two dashboard-grid">
        <div class="panel">
          <h3>Weiterlernen</h3>
          <p><strong>${next.title}</strong><br><span class="muted">${next.summary}</span></p>
          <a class="primary-button" href="${next.premium && state.user.premiumStatus !== "premium" ? `#/locked/${next.id}` : `#/lesson/${next.id}`}">Weiterlernen</a>
        </div>
        <div class="panel">
          <h3>Badges</h3>
          ${badgeHtml()}
        </div>
      </div>
      <div class="grid two dashboard-grid">
        <div class="panel">
          <h3>Kursfortschritt</h3>
          ${courseProgressHtml()}
        </div>
        <div class="panel">
          <h3>Letzte Aktivitaeten</h3>
          ${activityHtml()}
        </div>
      </div>
    </section>
  `);
}

function renderLearn() {
  const done = completedIds();
  setView(`
    <section class="screen">
      <div class="screen-header">
        <div>
          <p class="eyebrow">Kurse</p>
          <h2>Scratch Schritt fuer Schritt</h2>
          <p>Alle Kurse bauen logisch aufeinander auf. Die ersten Grundlagen sind kostenlos.</p>
        </div>
        ${state.user ? statsHtml() : `<a class="primary-button" href="#/signup">Fortschritt speichern</a>`}
      </div>
      <div class="course-list">
        ${state.courses.map(course => courseCard(course, done)).join("")}
      </div>
    </section>
  `);
}

function courseCard(course, done) {
  const completed = course.lessons.filter(lesson => done.has(lesson.id)).length;
  const percent = Math.round(completed / course.lessons.length * 100);
  return `
    <article class="panel course-card">
      <div>
        <span class="pill">${course.difficulty || "Anfaenger"}</span>
        <h3>${course.title}</h3>
        <p>${course.description}</p>
        <div class="progress-row"><span>${completed}/${course.lessons.length} Lektionen</span><span>${percent}%</span></div>
        <div class="progress-track"><span style="width:${percent}%"></span></div>
      </div>
      <div class="lesson-list compact">
        ${course.lessons.map(lesson => lessonRow(lesson, done)).join("")}
      </div>
    </article>
  `;
}

function lessonRow(lesson, done) {
  const locked = lesson.premium && (!state.user || state.user.premiumStatus !== "premium");
  return `
    <article class="lesson-card ${done.has(lesson.id) ? "completed" : ""} ${locked ? "locked" : ""}">
      <div>
        <span class="pill">${locked ? "Premium" : `${lesson.xp} XP`}</span>
        <h3>${lesson.title}</h3>
        <p>${lesson.summary}</p>
      </div>
      <a class="secondary-button" href="${locked ? `#/locked/${lesson.id}` : `#/lesson/${lesson.id}`}">${locked ? "Freischalten" : (done.has(lesson.id) ? "Wiederholen" : "Starten")}</a>
    </article>
  `;
}

function statsHtml() {
  return `
    <div class="stats">
      <div class="stat"><span>XP</span><strong>${state.user.xp}</strong></div>
      <div class="stat"><span>Level</span><strong>${state.user.level}</strong></div>
      <div class="stat"><span>Status</span><strong>${state.user.premiumStatus}</strong></div>
    </div>
  `;
}

function badgeHtml() {
  if (!state.progress.badges.length) return `<p class="muted">Dein erstes Badge wartet nach der ersten abgeschlossenen Lektion.</p>`;
  return state.progress.badges.map(badge => `<p><span class="pill">${escapeHtml(badge.icon)}</span> <strong>${escapeHtml(badge.name)}</strong><br><span class="muted">${escapeHtml(badge.description)}</span></p>`).join("");
}

function courseProgressHtml() {
  if (!state.progress.courseProgress.length) return `<p class="muted">Noch kein Kurs gestartet.</p>`;
  return state.progress.courseProgress.map(course => `
    <div class="mini-progress">
      <div class="progress-row"><strong>${escapeHtml(course.title)}</strong><span>${course.completedCount}/${course.lessonCount}</span></div>
      <div class="progress-track"><span style="width:${course.percent}%"></span></div>
    </div>
  `).join("");
}

function activityHtml() {
  if (!state.progress.recentActivity?.length) return `<p class="muted">Schliesse deine erste Lektion ab, dann erscheint sie hier.</p>`;
  return state.progress.recentActivity.map(item => `<p><span class="pill">+${item.xp_awarded} XP</span> ${escapeHtml(item.lesson_id)}</p>`).join("");
}

function lessonById(id) {
  for (const course of state.courses) {
    const lesson = course.lessons.find(item => item.id === id);
    if (lesson) return { course, lesson };
  }
  return {};
}

function renderLesson(id) {
  const { lesson } = lessonById(id);
  const done = completedIds();
  if (!lesson) {
    setView(`<section class="screen"><h2>Lektion nicht gefunden</h2></section>`);
    return;
  }
  const locked = lesson.premium && (!state.user || state.user.premiumStatus !== "premium");
  if (locked) {
    renderLockedLesson(id);
    return;
  }
  const isCompleted = done.has(id);
  setView(`
    <section class="screen lesson-layout">
      <article class="panel">
        <a class="secondary-button back-button" href="#/learn">Zurueck zum Kurs</a>
        <p class="eyebrow">${lesson.xp} XP</p>
        <h2>${lesson.title}</h2>
        <div class="goal-box"><strong>Lernziel</strong><p>${escapeHtml(lesson.learning_goal || lesson.summary)}</p></div>
        <h3>Erklaerung</h3>
        <p>${escapeHtml(lesson.explanation)}</p>
        <div class="panel"><h3>Beispiel</h3><p>${escapeHtml(lesson.example || lesson.demo)}</p></div>
        <div class="panel task-box">
          <h3>Deine Aufgabe</h3>
          <p>${escapeHtml(lesson.task.prompt)}</p>
          <ol class="steps">${lesson.task.steps.map(step => `<li>${escapeHtml(step)}</li>`).join("")}</ol>
          <h3>Challenge</h3>
          <p>${escapeHtml(lesson.challenge || "Verbessere dein Projekt mit einer eigenen Idee.")}</p>
          <details><summary>Hinweise anzeigen</summary><ul>${(lesson.hints || []).map(hint => `<li>${escapeHtml(hint)}</li>`).join("")}</ul></details>
          <button id="completeLesson" class="${isCompleted ? "secondary-button" : "primary-button"}">${state.user ? (isCompleted ? "Schon geschafft" : "Lektion abschliessen") : "Zum Speichern anmelden"}</button>
          <p id="lessonResult" class="success">${isCompleted ? "Diese Lektion ist gespeichert. Wiederholen ist jederzeit moeglich." : ""}</p>
        </div>
      </article>
      <aside class="panel">
        <h3>KI-Hilfe</h3>
        <p class="muted">Frag nach einem Hinweis. ScratchLab hilft beim Denken, nicht beim Abschreiben.</p>
        <div class="quick-actions">
          <button class="secondary-button ai-quick" data-question="Gib mir einen Tipp zu dieser Aufgabe.">Tipp</button>
          <button class="secondary-button ai-quick" data-question="Erklaere diese Aufgabe einfacher.">Einfacher</button>
          <button class="secondary-button ai-quick" data-question="Warum funktioniert das bei mir nicht?">Fehlerhilfe</button>
          <button class="secondary-button ai-quick" data-question="Was ist der naechste kleine Schritt?">Naechster Schritt</button>
        </div>
        <form id="assistantForm">
          <textarea name="message" placeholder="Warum bewegt sich meine Figur nicht?"></textarea>
          <button class="secondary-button" type="submit">Fragen</button>
        </form>
        <div id="assistantAnswer" class="assistant-chat"></div>
      </aside>
    </section>
  `);
  document.querySelector("#completeLesson").addEventListener("click", async () => completeLesson(lesson));
  document.querySelector("#assistantForm").addEventListener("submit", event => {
    event.preventDefault();
    askAssistant(lesson.id, event.currentTarget.querySelector("textarea").value, event.currentTarget);
  });
  document.querySelectorAll(".ai-quick").forEach(button => {
    button.addEventListener("click", () => askAssistant(lesson.id, button.dataset.question, document.querySelector("#assistantForm")));
  });
}

async function completeLesson(lesson) {
  if (!state.user) {
    location.hash = "#/signup";
    return;
  }
  const result = await api(`/api/lessons/${lesson.id}/complete`, { method: "POST", body: "{}" });
  state.user = result.user;
  state.progress = await api("/api/progress");
  const button = document.querySelector("#completeLesson");
  button.textContent = "Schon geschafft";
  button.className = "secondary-button";
  document.querySelector("#lessonResult").textContent = result.awardedXp
    ? `Lektion abgeschlossen! +${result.awardedXp} XP.`
    : "Diese Lektion war schon gespeichert. XP gibt es nur einmal.";
}

async function askAssistant(lessonId, question, form) {
  const text = String(question || "").trim();
  if (!text) return;
  const answerBox = document.querySelector("#assistantAnswer");
  answerBox.insertAdjacentHTML("beforeend", `<div class="chat-turn user-turn">${escapeHtml(text)}</div>`);
  try {
    const result = await api("/api/assistant", {
      method: "POST",
      body: JSON.stringify({ message: text, lessonId })
    });
    answerBox.insertAdjacentHTML("beforeend", `<div class="chat-turn coach-turn">${escapeHtml(result.response)}</div>`);
    form.querySelector("textarea").value = "";
  } catch (error) {
    answerBox.insertAdjacentHTML("beforeend", `<div class="chat-turn coach-turn">Die KI ist gerade nicht erreichbar. Versuch es gleich noch einmal.</div>`);
  }
}

function renderPremium() {
  setView(`
    <section class="screen grid two">
      <div>
        <p class="eyebrow">Weiterlernen</p>
        <h2>Alle Lektionen freischalten.</h2>
        <p>Einzelne Premium-Lektion fuer ${state.pricing.singleLessonPriceEur} EUR oder Premium fuer ${state.pricing.premiumMonthlyPriceEur} EUR im Monat.</p>
        <a class="secondary-button" href="#/learn">Zurueck zum Kurs</a>
      </div>
      <div class="panel premium-panel">
        <h3>Premium</h3>
        <div class="price">${state.pricing.premiumMonthlyPriceEur} EUR <span>/ Monat</span></div>
        <p>Alle aktuellen und spaeteren Scratch-Lektionen, mehr KI-Hilfe und Belohnungen.</p>
        <button id="upgradePremium" class="primary-button" type="button">Jetzt auf Premium upgraden</button>
        <p id="premiumMessage" class="muted">${state.pricing.checkoutReady ? "Stripe ist konfiguriert." : "Stripe Checkout ist noch nicht vollstaendig konfiguriert."}</p>
      </div>
    </section>
  `);
  document.querySelector("#upgradePremium").addEventListener("click", async () => {
    const message = document.querySelector("#premiumMessage");
    try {
      await api("/api/checkout/premium", { method: "POST", body: "{}" });
    } catch (error) {
      message.textContent = error.message;
    }
  });
}

function renderLockedLesson(id) {
  const { lesson } = lessonById(id);
  if (!lesson) {
    setView(`<section class="screen"><h2>Lektion nicht gefunden</h2></section>`);
    return;
  }
  setView(`
    <section class="screen grid two">
      <div>
        <a class="secondary-button back-button" href="#/learn">Zurueck zum Kurs</a>
        <p class="eyebrow">Premium-Lektion</p>
        <h2>${escapeHtml(lesson.title)}</h2>
        <p>${escapeHtml(lesson.summary)}</p>
      </div>
      <div class="panel premium-panel">
        <h3>Freischalten</h3>
        <div class="price">${lesson.price_eur || state.pricing.singleLessonPriceEur} EUR <span>einmalig</span></div>
        <p>Nur diese Lektion dauerhaft freischalten.</p>
        <button id="buyLesson" class="secondary-button" type="button">Diese Lektion kaufen</button>
        <hr>
        <div class="price">${state.pricing.premiumMonthlyPriceEur} EUR <span>/ Monat</span></div>
        <p>Alle Lektionen und spaeteren Premium-Inhalte freischalten.</p>
        <a class="primary-button" href="#/premium">Jetzt auf Premium upgraden</a>
        <p id="purchaseMessage" class="muted"></p>
      </div>
    </section>
  `);
  document.querySelector("#buyLesson").addEventListener("click", async () => {
    const message = document.querySelector("#purchaseMessage");
    try {
      await api("/api/checkout/lesson", { method: "POST", body: JSON.stringify({ lessonId: lesson.id }) });
    } catch (error) {
      message.textContent = error.message;
    }
  });
}

async function renderProjects() {
  if (!state.user) {
    location.hash = "#/signup";
    return;
  }
  state.projects = await api("/api/projects");
  setView(`
    <section class="screen">
      <div class="screen-header">
        <div>
          <p class="eyebrow">Deine Werkstatt</p>
          <h2>Scratch-Projekte</h2>
          <p>Speichere Ideen, veroeffentliche spaeter ausgewaehlte Projekte und pruefe `.sb3`-Dateien sicher ohne Scratch-Login.</p>
        </div>
      </div>
      <div class="grid two">
        <form id="projectForm" class="panel">
          <h3>Projekt speichern</h3>
          <label>Titel<input name="title" required minlength="3"></label>
          <label>Beschreibung<textarea name="description"></textarea></label>
          <label>Scratch-Link<input name="scratchUrl" placeholder="https://scratch.mit.edu/projects/..."></label>
          <label class="inline-label"><input name="isPublic" type="checkbox"> Oeffentlich sichtbar machen</label>
          <button class="primary-button" type="submit">Speichern</button>
          <p id="projectError" class="error"></p>
        </form>
        <form id="checkForm" class="panel">
          <h3>.sb3 pruefen</h3>
          <label>Lektion<select name="lessonId">${allLessons().map(lesson => `<option value="${lesson.id}">${escapeHtml(lesson.title)}</option>`).join("")}</select></label>
          <label>Scratch-Datei<input name="sb3" type="file" accept=".sb3" required></label>
          <button class="secondary-button" type="submit">Projekt pruefen</button>
          <div id="checkResult" class="check-result"></div>
        </form>
      </div>
      <div class="project-list" style="margin-top:16px">
        ${state.projects.own.map(projectCard).join("") || `<div class="panel"><p class="muted">Dein erstes Projekt wartet.</p></div>`}
      </div>
    </section>
  `);
  document.querySelector("#projectForm").addEventListener("submit", saveProject);
  document.querySelector("#checkForm").addEventListener("submit", checkProject);
}

async function saveProject(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  try {
    await api("/api/projects", {
      method: "POST",
      body: JSON.stringify({
        title: form.get("title"),
        description: form.get("description"),
        scratchUrl: form.get("scratchUrl"),
        isPublic: form.get("isPublic") === "on"
      })
    });
    renderProjects();
  } catch (error) {
    document.querySelector("#projectError").textContent = "Deine Aenderungen konnten nicht gespeichert werden.";
  }
}

async function checkProject(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const file = form.get("sb3");
  const resultBox = document.querySelector("#checkResult");
  if (!file) return;
  resultBox.textContent = "Pruefung laeuft...";
  try {
    const dataBase64 = await fileToBase64(file);
    const result = await api("/api/projects/check", {
      method: "POST",
      body: JSON.stringify({ lessonId: form.get("lessonId"), dataBase64 })
    });
    resultBox.innerHTML = `<p class="success">${escapeHtml(result.result.feedback)}</p>${result.result.details.map(item => `<p>${item.passed ? "OK" : "Fehlt"}: ${escapeHtml(item.message)}</p>`).join("")}`;
  } catch (error) {
    resultBox.textContent = "Dein Projekt konnte noch nicht geprueft werden.";
  }
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function projectCard(project) {
  return `
    <article class="project-card">
      <h3>${escapeHtml(project.title)}</h3>
      <p>${escapeHtml(project.description || "Keine Beschreibung")}</p>
      ${project.scratch_url ? `<a class="secondary-button" href="${escapeHtml(project.scratch_url)}" target="_blank" rel="noreferrer">Scratch oeffnen</a>` : ""}
      ${project.is_public ? `<span class="pill">Oeffentlich</span>` : `<span class="pill">Privat</span>`}
    </article>
  `;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char]));
}

async function router() {
  await refresh();
  const [route, id] = location.hash.replace("#/", "").split("/");
  if (!route) renderLanding();
  else if (route === "signup") renderAuth("signup");
  else if (route === "login") renderAuth("login");
  else if (route === "dashboard") renderDashboard();
  else if (route === "learn") renderLearn();
  else if (route === "lesson") renderLesson(id);
  else if (route === "locked") renderLockedLesson(id);
  else if (route === "projects") await renderProjects();
  else if (route === "premium") renderPremium();
  else renderLanding();
}

authAction.addEventListener("click", async () => {
  if (state.user) {
    await api("/api/auth/logout", { method: "POST", body: "{}" });
    state.user = null;
    location.hash = "#/";
    router();
  } else {
    location.hash = "#/login";
  }
});

window.addEventListener("hashchange", router);
router().catch(error => setView(`<section class="screen"><h2>ScratchLab braucht kurz Hilfe</h2><p class="error">${escapeHtml(error.message)}</p></section>`));
