const app = document.querySelector("#app");
const authAction = document.querySelector("#authAction");

const state = {
  user: null,
  courses: [],
  progress: { completed: [], badges: [] },
  projects: { own: [], public: [] },
  pricing: null
};

const completedIds = () => new Set(state.progress.completed.map(item => item.lesson_id));

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
  }
}

function setView(html) {
  app.innerHTML = html;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function renderLanding() {
  setView(document.querySelector("#landingTemplate").innerHTML);
}

function renderAuth(mode = "signup") {
  const isSignup = mode === "signup";
  setView(`
    <section class="screen grid two">
      <div>
        <p class="eyebrow">${isSignup ? "Kostenlos starten" : "Willkommen zurueck"}</p>
        <h2>${isSignup ? "In 60 Sekunden bereit fuer die erste Scratch-Aufgabe." : "Weiterlernen, wo du aufgehoert hast."}</h2>
        <p>Dein Fortschritt, XP und Projekte werden gespeichert. Keine festen Lernzeiten, kein Druck.</p>
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
      const payload = Object.fromEntries(form.entries());
      const result = await api(isSignup ? "/api/auth/register" : "/api/auth/login", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      state.user = result.user;
      location.hash = "#/learn";
    } catch (error) {
      document.querySelector("#authError").textContent = error.message;
    }
  });
}

function renderLearn() {
  const course = state.courses[0];
  const done = completedIds();
  const freeLessons = course.lessons.filter(lesson => !lesson.premium);
  const firstOpen = freeLessons.find(lesson => !done.has(lesson.id));
  const allFreeDone = freeLessons.every(lesson => done.has(lesson.id));
  setView(`
    <section class="screen">
      <div class="screen-header">
        <div>
          <p class="eyebrow">Dein Lernlabor</p>
          <h2>${course.title}</h2>
          <p>${course.description}</p>
        </div>
        ${state.user ? statsHtml() : `<a class="primary-button" href="#/signup">Fortschritt speichern</a>`}
      </div>
      <div class="grid two">
        <div class="panel">
          <h3>${allFreeDone ? "Kostenlose Grundlagen geschafft" : "Naechster guter Schritt"}</h3>
          <p>${allFreeDone ? "Die naechsten Lektionen sind sichtbar, aber gesperrt: einzeln fuer 5 EUR oder alle mit Premium fuer 15 EUR/Monat." : firstOpen.summary}</p>
          <a class="primary-button" href="${allFreeDone ? "#/premium" : `#/lesson/${firstOpen.id}`}">${allFreeDone ? "Premium ansehen" : "Lektion starten"}</a>
        </div>
        <div class="panel">
          <h3>Badges</h3>
          ${state.user ? badgeHtml() : `<p class="muted">Melde dich an, um Badges zu sammeln.</p>`}
        </div>
      </div>
      <div class="lesson-list" style="margin-top:16px">
        ${course.lessons.map(lesson => `
          <article class="lesson-card ${done.has(lesson.id) ? "completed" : ""} ${lesson.premium ? "locked" : ""}">
            <div>
              <span class="pill">${lesson.premium ? "Premium" : `${lesson.xp} XP`}</span>
              <h3>${lesson.title}</h3>
              <p>${lesson.summary}</p>
              ${lesson.premium ? `<p class="muted">Einzeln ${lesson.price_eur || state.pricing.singleLessonPriceEur} EUR oder mit Premium ${state.pricing.premiumMonthlyPriceEur} EUR/Monat.</p>` : ""}
            </div>
            <a class="secondary-button" href="${lesson.premium ? `#/locked/${lesson.id}` : `#/lesson/${lesson.id}`}">${lesson.premium ? "Freischalten" : (done.has(lesson.id) ? "Wiederholen" : "Starten")}</a>
          </article>
        `).join("")}
      </div>
    </section>
  `);
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
  return state.progress.badges.map(badge => `<p><span class="pill">${badge.icon}</span> <strong>${badge.name}</strong><br><span class="muted">${badge.description}</span></p>`).join("");
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
  const isCompleted = done.has(id);
  if (!lesson) {
    setView(`<section class="screen"><h2>Lektion nicht gefunden</h2></section>`);
    return;
  }
  setView(`
    <section class="screen lesson-layout">
      <article class="panel">
        <a class="secondary-button back-button" href="#/learn">Zurueck zum Kurs</a>
        <p class="eyebrow">${lesson.xp} XP</p>
        <h2>${lesson.title}</h2>
        <p>${lesson.explanation}</p>
        <div class="panel">
          <h3>Demo</h3>
          <p>${lesson.demo}</p>
        </div>
        <div class="panel task-box">
          <h3>Deine Aufgabe</h3>
          <p>${lesson.task.prompt}</p>
          <ol class="steps">${lesson.task.steps.map(step => `<li>${step}</li>`).join("")}</ol>
          <button id="completeLesson" class="${isCompleted ? "secondary-button" : "primary-button"}">${state.user ? (isCompleted ? "Schon geschafft" : "Geschafft, XP holen") : "Zum Speichern anmelden"}</button>
          <p id="lessonResult" class="success">${isCompleted ? "Diese Lektion ist gespeichert. Du kannst sie jederzeit wiederholen, ohne neue XP zu verlieren oder doppelt zu bekommen." : ""}</p>
        </div>
      </article>
      <aside class="panel">
        <h3>KI-Hilfe</h3>
        <p class="muted">Frag nach einem Hinweis. ScratchLab hilft dir beim Denken, nicht beim Abschreiben.</p>
        <form id="assistantForm">
          <textarea name="message" placeholder="Warum bewegt sich meine Figur nicht?"></textarea>
          <button class="secondary-button" type="submit">Hinweis bekommen</button>
        </form>
        <div id="assistantAnswer" class="assistant-chat"></div>
      </aside>
    </section>
  `);
  document.querySelector("#completeLesson").addEventListener("click", async () => {
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
      ? `${result.message} +${result.awardedXp} XP`
      : "Diese Lektion war schon gespeichert. Du kannst sie wiederholen, aber XP gibt es nur einmal.";
  });
  document.querySelector("#assistantForm").addEventListener("submit", async event => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const textarea = event.currentTarget.querySelector("textarea");
    const question = String(form.get("message") || "").trim();
    if (!question) return;
    const submit = event.currentTarget.querySelector("button");
    submit.disabled = true;
    const result = await api("/api/assistant", {
      method: "POST",
      body: JSON.stringify({ message: question, lessonId: lesson.id })
    });
    document.querySelector("#assistantAnswer").insertAdjacentHTML("beforeend", `
      <div class="chat-turn user-turn">${escapeHtml(question)}</div>
      <div class="chat-turn coach-turn">${escapeHtml(result.response)}</div>
    `);
    textarea.value = "";
    textarea.focus();
    submit.disabled = false;
  });
}

function renderPremium() {
  setView(`
    <section class="screen grid two">
      <div>
        <p class="eyebrow">Weiterlernen</p>
        <h2>Alle Lektionen freischalten.</h2>
        <p>Nach den kostenlosen Grundlagen kannst du einzelne Lektionen kaufen oder direkt Premium holen. Premium schaltet alle aktuellen und spaeteren Scratch-Lektionen frei.</p>
        <a class="primary-button" href="#/learn">Zurueck zum Kurs</a>
      </div>
      <div class="panel premium-panel">
        <h3>Premium</h3>
        <div class="price">${state.pricing.premiumMonthlyPriceEur} EUR <span>/ Monat</span></div>
        <p>Alle Lektionen, alle Premium-Kurse, mehr KI-Hilfe und Belohnungen.</p>
        <button id="upgradePremium" class="primary-button" type="button">Jetzt auf Premium upgraden</button>
        <p id="premiumMessage" class="muted">Der Preis ist jetzt im Produkt sichtbar. Der echte Zahlungsanbieter wird im naechsten Schritt angebunden.</p>
      </div>
    </section>
  `);
  document.querySelector("#upgradePremium").addEventListener("click", () => {
    document.querySelector("#premiumMessage").textContent = "Checkout wird vorbereitet. Als naechster Schritt wird hier Stripe, Paddle oder ein anderer Zahlungsanbieter angebunden.";
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
        <h2>${lesson.title}</h2>
        <p>${lesson.summary}</p>
        <p>Diese Lektion ist schon sichtbar, aber noch nicht freigeschaltet. Du kannst sie einzeln kaufen oder mit Premium alle Lektionen freischalten.</p>
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
      </div>
    </section>
  `);
  document.querySelector("#buyLesson").addEventListener("click", () => {
    document.querySelector("#buyLesson").textContent = "Checkout wird vorbereitet";
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
          <p>Speichere Ideen, beschreibe sie und veroeffentliche nur, was du wirklich zeigen willst.</p>
        </div>
      </div>
      <div class="grid two">
        <form id="projectForm" class="panel">
          <h3>Projekt speichern</h3>
          <label>Titel<input name="title" required minlength="3"></label>
          <label>Beschreibung<textarea name="description"></textarea></label>
          <label>Scratch-Link<input name="scratchUrl" placeholder="https://scratch.mit.edu/projects/..."></label>
          <label><input name="isPublic" type="checkbox"> Oeffentlich sichtbar machen</label>
          <button class="primary-button" type="submit">Speichern</button>
          <p id="projectError" class="error"></p>
        </form>
        <div class="panel">
          <h3>Community-Vorschau</h3>
          <p class="muted">Oeffentliche Projekte werden spaeter moderiert. Im MVP ist die Struktur vorbereitet.</p>
          ${state.projects.public.map(projectCard).join("") || `<p class="muted">Noch keine oeffentlichen Projekte.</p>`}
        </div>
      </div>
      <div class="project-list" style="margin-top:16px">
        ${state.projects.own.map(projectCard).join("") || `<div class="panel"><p class="muted">Dein erstes Projekt wartet.</p></div>`}
      </div>
    </section>
  `);
  document.querySelector("#projectForm").addEventListener("submit", async event => {
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
      document.querySelector("#projectError").textContent = error.message;
    }
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
router().catch(error => setView(`<section class="screen"><h2>ScratchLab braucht kurz Hilfe</h2><p class="error">${error.message}</p></section>`));
