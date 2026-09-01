const app = document.querySelector("#app");

const authAction = document.querySelector("#authAction");


const EMPTY_PROGRESS = {

  completed: [],

  badges: [],

  courseProgress: [],

  projects: [],

  recentActivity: []

};


const state = {

  user: null,

  courses: [],

  progress: { ...EMPTY_PROGRESS },

  projectVerificationTokens: {},

  projects: { own: [], public: [] },

  pricing: {

    singleLessonPriceEur: 5,

    premiumMonthlyPriceEur: 15,

    checkoutReady: false

  }

};


function escapeHtml(value) {

  return String(value ?? "").replace(

    /[&<>"']/g,

    char => ({

      "&": "&amp;",

      "<": "&lt;",

      ">": "&gt;",

      '"': "&quot;",

      "'": "&#039;"

    })[char]

  );

}


function completedIds() {

  return new Set(

    Array.isArray(state.progress.completed)

      ? state.progress.completed.map(item => String(item.lesson_id))

      : []

  );

}


function allLessons() {

  return Array.isArray(state.courses)

    ? state.courses.flatMap(course =>

        Array.isArray(course.lessons)

          ? course.lessons.map(lesson => ({

              ...lesson,

              courseId: course.id,

              courseTitle: course.title

            }))

          : []

      )

    : [];

}


function setView(html) {

  app.innerHTML = html;

  window.scrollTo({ top: 0, behavior: "smooth" });

}


async function api(path, options = {}) {

  const controller = new AbortController();

  const timeoutMs = options.timeoutMs || 30000;

  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const config = {

    credentials: "same-origin",

    ...options,

    signal: controller.signal,

    headers: {

      Accept: "application/json",

      ...(options.body ? { "Content-Type": "application/json" } : {}),

      ...(options.headers || {}),

    },

  };

  delete config.timeoutMs;

  try {

    const response = await fetch(path, config);

    let data = {};

    try { data = await response.json(); } catch {}

    if (!response.ok) {

      throw new Error(data?.error || data?.message || `Serverfehler (${response.status})`);

    }

    return data;

  } catch (error) {

    if (error?.name === "AbortError") {

      throw new Error("Die Anfrage dauert zu lange. Bitte versuche es erneut.");

    }

    throw error;

  } finally {

    clearTimeout(timer);

  }

}

let refreshInFlight = null;

let refreshAt = 0;

let publicDataAt = 0;

let progressAt = 0;

const ME_CACHE_MS = 15000;

const PUBLIC_CACHE_MS = 300000;

const PROGRESS_CACHE_MS = 10000;


async function refresh(force = false) {

  const now = Date.now();


  if (!force && refreshInFlight) {

    return refreshInFlight;

  }


  refreshInFlight = (async () => {

    const requests = [];


    if (

      force ||

      now - refreshAt >= ME_CACHE_MS

    ) {

      requests.push(

        api("/api/me").then(data => {

          state.user = data?.user || null;

          refreshAt = Date.now();

        })

      );

    }


    if (

      force ||

      now - publicDataAt >= PUBLIC_CACHE_MS

    ) {

      requests.push(

        Promise.all([

          api("/api/courses"),

          api("/api/pricing"),

        ]).then(([courses, pricing]) => {

          state.courses = Array.isArray(courses?.courses)

            ? courses.courses

            : [];


          state.pricing = {

            ...state.pricing,

            ...(pricing || {}),

          };


          publicDataAt = Date.now();

        })

      );

    }


    if (requests.length) {

      await Promise.all(requests);

    }


    if (state.user) {

      if (

        force ||

        now - progressAt >= PROGRESS_CACHE_MS

      ) {

        try {

          state.progress = {

            ...EMPTY_PROGRESS,

            ...(await api("/api/progress")),

          };

          progressAt = Date.now();

        } catch {

          // Keep last known progress instead of wiping the dashboard.

        }

      }

    } else {

      state.progress = { ...EMPTY_PROGRESS };

    }


    if (authAction) {

      authAction.textContent =

        state.user ? "Logout" : "Einloggen";

    }


    updateAdminNavigation();

  })();


  try {

    await refreshInFlight;

  } finally {

    refreshInFlight = null;

  }

}


function updateAdminNavigation() {

  const nav = document.querySelector(".nav");

  if (!nav) return;


  let link = document.querySelector("#adminFeedbackNav");


  if (state.user?.isAdmin) {

    if (!link) {

      link = document.createElement("a");

      link.id = "adminFeedbackNav";

      link.href = "#/admin-feedback";

      link.textContent = "Betreiber";

      nav.insertBefore(link, authAction || null);

    }

  } else if (link) {

    link.remove();

  }

}


function renderLanding() {

  const lessons = allLessons();


  setView(`

    <section class="hero">

      <div class="hero-copy">

        <p class="eyebrow">Scratch lernen, ohne Schulgefühl</p>

        <h1>ScratchLab</h1>

        <p class="lead">

          Programmieren lernen. Scratch verstehen. Eigene Ideen bauen.

        </p>

        <div class="hero-actions">

          <a class="primary-button" href="#/signup">Kostenlos starten</a>

          <a class="secondary-button" href="#/learn">Kurse ansehen</a>

        </div>

      </div>


      <div class="play-stage" aria-label="ScratchLab Vorschau">

        <div class="stage-header"><span></span><span></span><span></span></div>

        <div class="sprite"></div>

        <div class="speech">Ich baue mein erstes Spiel!</div>

        <div class="blocks">

          <span>Wenn Flagge geklickt</span>

          <span>bewege Figur</span>

          <span>+ XP</span>

        </div>

      </div>

    </section>


    <section class="feature-band">

      <article>

        <strong>1. Kurz verstehen</strong>

        <span>Jede Lektion startet mit einem klaren Lernziel.</span>

      </article>

      <article>

        <strong>2. Selbst bauen</strong>

        <span>Du probierst direkt in Scratch und siehst ein Ergebnis.</span>

      </article>

      <article>

        <strong>3. Weiter wachsen</strong>

        <span>XP, Badges, Projekte und KI-Hilfe halten dich im Flow.</span>

      </article>

    </section>


    <section class="screen landing-grid">

      <div class="panel">

        <h3>${state.courses.length} Kurse, ${lessons.length} Lektionen</h3>

        <p>Von der ersten Figur bis zum eigenen Mini-Spiel.</p>

        <a class="secondary-button" href="#/learn">Kursübersicht</a>

      </div>

      <div class="panel">

        <h3>KI-Tutor</h3>

        <p>Die KI hilft mit Denkanstößen und Screenshot-Analyse.</p>

      </div>

      <div class="panel">

        <h3>Projektprüfung</h3>

        <p>Lade deine .sb3-Datei hoch und ScratchLab prüft die Anforderungen.</p>

      </div>

    </section>

  `);

}


function renderAuth(mode = "signup") {

  const isSignup = mode === "signup";


  setView(`

    <section class="screen grid two">

      <div>

        <p class="eyebrow">${isSignup ? "Kostenlos starten" : "Willkommen zurück"}</p>

        <h2>${isSignup ? "Erstelle deinen ScratchLab-Account." : "Weiterlernen, wo du aufgehört hast."}</h2>

        <p>Dein Fortschritt und deine Projekte werden dauerhaft gespeichert.</p>

      </div>


      <div class="panel">

        <form id="authForm">

          ${

            isSignup

              ? `<label>Benutzername

                  <input name="username" autocomplete="nickname" required minlength="3">

                </label>`

              : ""

          }


          <label>E-Mail

            <input name="email" type="email" autocomplete="email" required>

          </label>


          <label>Passwort

            <input

              name="password"

              type="password"

              autocomplete="${isSignup ? "new-password" : "current-password"}"

              required

              minlength="8"

            >

          </label>


          <button class="primary-button" type="submit">

            ${isSignup ? "Account erstellen" : "Einloggen"}

          </button>


          <p class="muted">

            ${

              isSignup

                ? `Schon dabei? <a href="#/login">Einloggen</a>`

                : `Neu hier? <a href="#/signup">Kostenlos starten</a>`

            }

          </p>


          <p id="authError" class="error"></p>

        </form>

      </div>

    </section>

  `);


  document.querySelector("#authForm")?.addEventListener("submit", async event => {

    event.preventDefault();


    const form = event.currentTarget;

    const button = form.querySelector("button");

    const errorBox = form.querySelector("#authError");


    button.disabled = true;

    errorBox.textContent = "";


    try {

      const result = await api(

        isSignup ? "/api/auth/register" : "/api/auth/login",

        {

          method: "POST",

          body: JSON.stringify(Object.fromEntries(new FormData(form).entries()))

        }

      );


      state.user = result.user || null;

      await refresh(true);


      if (!state.user) {

        throw new Error("Die Anmeldung wurde nicht übernommen.");

      }


      location.hash = "#/dashboard";

    } catch (error) {

      errorBox.textContent = error.message;

      button.disabled = false;

    }

  });

}


function statsHtml() {

  return `

    <div class="stats">

      <div class="stat"><span>XP</span><strong>${state.user?.xp ?? 0}</strong></div>

      <div class="stat"><span>Level</span><strong>${state.user?.level ?? 1}</strong></div>

      <div class="stat"><span>Status</span><strong>${escapeHtml(state.user?.premiumStatus || "free")}</strong></div>

    </div>

  `;

}


function badgeHtml() {

  const badges = Array.isArray(state.progress.badges) ? state.progress.badges : [];

  if (!badges.length) {

    return `<p class="muted">Dein erstes Badge wartet nach der ersten abgeschlossenen Lektion.</p>`;

  }


  return badges.map(badge => `

    <p>

      <span class="pill">${escapeHtml(badge.icon || "🏆")}</span>

      <strong>${escapeHtml(badge.name || "")}</strong><br>

      <span class="muted">${escapeHtml(badge.description || "")}</span>

    </p>

  `).join("");

}


function courseProgressHtml() {

  const courses = Array.isArray(state.progress.courseProgress)

    ? state.progress.courseProgress

    : [];


  if (!courses.length) {

    return `<p class="muted">Noch kein Kurs gestartet.</p>`;

  }


  return courses.map(course => `

    <div class="mini-progress">

      <div class="progress-row">

        <strong>${escapeHtml(course.title)}</strong>

        <span>${course.completedCount}/${course.lessonCount}</span>

      </div>

      <div class="progress-track">

        <span style="width:${Number(course.percent) || 0}%"></span>

      </div>

    </div>

  `).join("");

}


function activityHtml() {

  const activity = Array.isArray(state.progress.recentActivity)

    ? state.progress.recentActivity

    : [];


  if (!activity.length) {

    return `<p class="muted">Schließe deine erste Lektion ab, dann erscheint sie hier.</p>`;

  }


  return activity.map(item => `

    <p>

      <span class="pill">+${Number(item.xp_awarded) || 0} XP</span>

      ${escapeHtml(item.lesson_id || "")}

    </p>

  `).join("");

}


function renderDashboard() {

  if (!state.user) {

    location.hash = "#/login";

    return;

  }


  const lessons = allLessons();

  const done = completedIds();

  const next = state.progress.nextLesson || lessons.find(item => !done.has(item.id)) || null;

  const total = lessons.length;

  const completed = done.size;

  const percent = total ? Math.round(completed / total * 100) : 0;


  setView(`

    <section class="screen">

      <div class="screen-header">

        <div>

          <p class="eyebrow">Dashboard</p>

          <h2>Hi ${escapeHtml(state.user.username)}, weiter geht's.</h2>

          <p>Dein Fortschritt bleibt dauerhaft gespeichert.</p>

        </div>

        ${statsHtml()}

      </div>


      <div class="panel">

        <div class="progress-row">

          <strong>Gesamtfortschritt</strong>

          <span>${completed}/${total} Lektionen</span>

        </div>

        <div class="progress-track"><span style="width:${percent}%"></span></div>

      </div>


      <div class="grid two dashboard-grid">

        <div class="panel">

          <h3>Weiterlernen</h3>

          ${

            next

              ? `<p><strong>${escapeHtml(next.title)}</strong><br><span class="muted">${escapeHtml(next.summary || "")}</span></p>

                 <a class="primary-button" href="#/lesson/${encodeURIComponent(next.id)}">Weiterlernen</a>`

              : `<p class="success">🎉 Alle verfügbaren Lektionen abgeschlossen!</p>`

          }

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

          <h3>Letzte Aktivitäten</h3>

          ${activityHtml()}

        </div>

      </div>

    </section>

  `);

}


function renderLearn() {

  const done = completedIds();

  const lessons = allLessons();


  setView(`

    <section class="screen">

      <div class="screen-header">

        <div>

          <p class="eyebrow">Kurse</p>

          <h2>Scratch Schritt für Schritt</h2>

          <p>${state.courses.length} Kurse mit ${lessons.length} Lektionen.</p>

        </div>

        ${state.user ? statsHtml() : `<a class="primary-button" href="#/signup">Fortschritt speichern</a>`}

      </div>


      <div class="course-list">

        ${

          state.courses.length

            ? state.courses.map(course => courseCard(course, done)).join("")

            : `<div class="panel"><p class="error">Die Kursdaten konnten nicht geladen werden.</p></div>`

        }

      </div>

    </section>

  `);

}


function courseCard(course, done) {

  const lessons = Array.isArray(course.lessons) ? course.lessons : [];

  const completed = lessons.filter(lesson => done.has(lesson.id)).length;

  const percent = lessons.length ? Math.round(completed / lessons.length * 100) : 0;


  return `

    <article class="panel course-card">

      <div>

        <span class="pill">${escapeHtml(course.difficulty || "Anfänger")}</span>

        <h3>${escapeHtml(course.title)}</h3>

        <p>${escapeHtml(course.description || "")}</p>


        <div class="progress-row">

          <span>${completed}/${lessons.length} Lektionen</span>

          <span>${percent}%</span>

        </div>


        <div class="progress-track"><span style="width:${percent}%"></span></div>

      </div>


      <div class="lesson-list compact">

        ${lessons.map(lesson => lessonRow(lesson, done)).join("")}

      </div>

    </article>

  `;

}


function lessonRow(lesson, done) {

  const locked = lesson.premium &&

    (!state.user || state.user.premiumStatus !== "premium");


  const completed = done.has(lesson.id);


  return `

    <article class="lesson-card ${completed ? "completed" : ""} ${locked ? "locked" : ""}">

      <div>

        <span class="pill">${locked ? "Premium" : `${lesson.xp || 0} XP`}</span>

        <h3>${escapeHtml(lesson.title)}</h3>

        <p>${escapeHtml(lesson.summary || "")}</p>

      </div>


      <a

        class="secondary-button"

        href="${locked ? `#/locked/${encodeURIComponent(lesson.id)}` : `#/lesson/${encodeURIComponent(lesson.id)}`}"

      >

        ${locked ? "Freischalten" : completed ? "Wiederholen" : "Starten"}

      </a>

    </article>

  `;

}


function lessonById(id) {

  return allLessons().reduce(

    (found, lesson) => found || (String(lesson.id) === String(id) ? lesson : null),

    null

  )

    ? { lesson: allLessons().find(lesson => String(lesson.id) === String(id)) }

    : {};

}


function renderLesson(id) {

  const lesson = allLessons().find(item => String(item.id) === String(id));


  if (!lesson) {

    setView(`

      <section class="screen">

        <h2>Lektion nicht gefunden</h2>

        <a class="secondary-button" href="#/learn">Zurück zu den Kursen</a>

      </section>

    `);

    return;

  }


  if (

    lesson.premium &&

    (!state.user || state.user.premiumStatus !== "premium")

  ) {

    renderLockedLesson(id);

    return;

  }


  const completed = completedIds().has(lesson.id);


  setView(`

    <section class="screen lesson-layout">

      <article class="panel">

        <a class="secondary-button back-button" href="#/learn">Zurück zum Kurs</a>

        <p class="eyebrow">${lesson.xp || 0} XP</p>

        <h2>${escapeHtml(lesson.title)}</h2>


        <div class="goal-box">

          <strong>Lernziel</strong>

          <p>${escapeHtml(lesson.learning_goal || lesson.summary || "")}</p>

        </div>


        <h3>Erklärung</h3>

        <p>${escapeHtml(lesson.explanation || "")}</p>


        <div class="panel">

          <h3>Beispiel</h3>

          <p>${escapeHtml(lesson.example || lesson.demo || "")}</p>

        </div>


        <div class="panel task-box">

          <h3>Deine Aufgabe</h3>

          <p>${escapeHtml(lesson.task?.prompt || "Bearbeite diese Aufgabe in Scratch.")}</p>


          ${

            Array.isArray(lesson.task?.steps) && lesson.task.steps.length

              ? `<ol class="steps">${lesson.task.steps.map(step => `<li>${escapeHtml(step)}</li>`).join("")}</ol>`

              : ""

          }


          <h3>Challenge</h3>

          <p>${escapeHtml(lesson.challenge || "Verbessere dein Projekt mit einer eigenen Idee.")}</p>


          ${

            Array.isArray(lesson.hints) && lesson.hints.length

              ? `<details><summary>Hinweise anzeigen</summary><ul>${lesson.hints.map(hint => `<li>${escapeHtml(hint)}</li>`).join("")}</ul></details>`

              : ""

          }


          <div class="project-check-box">

            <h3>Dein Scratch-Projekt</h3>


            <p class="muted">

              Prüfe deine Aufgabe direkt hier. Du kannst entweder

              deinen Scratch-Projekt-Link einfügen oder deine

              Scratch-Datei auswählen.

            </p>


            <label>

              🔗 Scratch-Projekt-Link

              <input

                id="scratchProjectUrl"

                type="url"

                placeholder="https://scratch.mit.edu/projects/123456789/"

                autocomplete="off"

              >

            </label>


            <button

              id="checkScratchLink"

              class="secondary-button"

              type="button"

            >

              🔍 Scratch-Link prüfen

            </button>


            <div class="muted" style="margin:16px 0;text-align:center;">

              ───────── oder ─────────

            </div>


            <div

              id="scratchDropZone"

              class="scratch-upload-zone"

              tabindex="0"

              role="button"

              aria-label="Scratch-Datei auswählen"

            >

              <div style="font-size:2rem;">📁</div>

              <strong>Deine Scratch-Datei hier hineinziehen</strong>

              <span class="muted">oder hier klicken und auswählen</span>

              <small>Scratch-Datei (.sb3) · maximal 10 MB</small>


              <input

                id="lessonSb3"

                type="file"

                accept=".sb3,application/zip"

                hidden

              >

            </div>


            <p id="selectedScratchFile" class="muted">

              Noch keine Scratch-Datei ausgewählt.

            </p>


            <button

              id="checkLessonProject"

              class="primary-button"

              type="button"

            >

              ✅ Scratch-Datei prüfen

            </button>


            <div

              id="lessonCheckResult"

              class="check-result"

            ></div>

          </div>



          <button

            id="completeLesson"

            class="${completed ? "secondary-button" : "primary-button"}"

            type="button"

            ${completed ? "" : "disabled"}

          >

            ${completed ? "Schon geschafft" : "🔒 Erst Projekt prüfen"}

          </button>


          <p id="lessonResult" class="success">

            ${completed ? "Diese Lektion ist gespeichert." : "Bestehe zuerst die Projektprüfung."}

          </p>

        </div>

      </article>


      <aside class="panel">

        <h3>KI-Lernassistent</h3>

        <p class="muted">Frag jederzeit etwas zur Lektion. Die KI hilft mit Denkanstößen und kann deinen Screenshot analysieren.</p>


        <form id="assistantForm">

          <textarea name="message" placeholder="Stelle deine Frage..."></textarea>


          <label class="file-upload">

            📷 Screenshot hinzufügen

            <input id="assistantImage" type="file" accept="image/png,image/jpeg,image/webp">

          </label>


          <button class="secondary-button" type="submit">Fragen</button>

        </form>


        <p id="assistantStatus" class="muted"></p>

        <div id="assistantAnswer" class="assistant-chat"></div>

      </aside>

    </section>

  `);


  const scratchInput = document.querySelector("#lessonSb3");

  const scratchDropZone = document.querySelector("#scratchDropZone");

  const selectedScratchFile = document.querySelector("#selectedScratchFile");


  const showScratchFile = () => {

    const file = scratchInput?.files?.[0];

    if (!selectedScratchFile) return;

    selectedScratchFile.textContent = file

      ? `Ausgewählt: ${file.name} (${formatBytes(file.size)})`

      : "Noch keine Scratch-Datei ausgewählt.";

  };


  scratchDropZone?.addEventListener("click", () => scratchInput?.click());

  scratchDropZone?.addEventListener("keydown", event => {

    if (event.key === "Enter" || event.key === " ") {

      event.preventDefault();

      scratchInput?.click();

    }

  });


  ["dragenter", "dragover"].forEach(type => {

    scratchDropZone?.addEventListener(type, event => {

      event.preventDefault();

      event.stopPropagation();

      scratchDropZone.classList.add("is-dragging");

    });

  });


  ["dragleave", "drop"].forEach(type => {

    scratchDropZone?.addEventListener(type, event => {

      event.preventDefault();

      event.stopPropagation();

      scratchDropZone.classList.remove("is-dragging");

    });

  });


  scratchDropZone?.addEventListener("drop", event => {

    const files = event.dataTransfer?.files;

    if (!files?.length || !scratchInput) return;

    scratchInput.files = files;

    showScratchFile();

  });


  scratchInput?.addEventListener("change", showScratchFile);


  document.querySelector("#checkLessonProject")?.addEventListener("click", () => checkLessonProject(lesson));

  document.querySelector("#checkScratchLink")?.addEventListener("click", () => checkScratchLink(lesson));

  document.querySelector("#completeLesson")?.addEventListener("click", () => completeLesson(lesson));

  document.querySelector("#assistantForm")?.addEventListener("submit", event => {

    event.preventDefault();

    askAssistant(lesson.id, event.currentTarget);

  });

}


async function checkLessonProject(lesson) {

  const fileInput = document.querySelector("#lessonSb3");

  const resultBox = document.querySelector("#lessonCheckResult");

  const completeButton = document.querySelector("#completeLesson");

  const file = fileInput?.files?.[0];


  if (!file) {

    resultBox.innerHTML = `<p class="error">Bitte wähle zuerst eine .sb3-Datei aus.</p>`;

    return;

  }


  if (!file.name.toLowerCase().endsWith(".sb3")) {

    resultBox.innerHTML = `<p class="error">Bitte lade eine echte Scratch-.sb3-Datei hoch.</p>`;

    return;

  }


  if (file.size > 10 * 1024 * 1024) {

    resultBox.innerHTML = `<p class="error">Die .sb3-Datei darf maximal 10 MB groß sein.</p>`;

    return;

  }


  delete state.projectVerificationTokens[lesson.id];

  resultBox.innerHTML = `<p class="muted">🔎 Deine Scratch-Datei wird geprüft...</p>`;

  completeButton.disabled = true;

  completeButton.textContent = "🔒 Erst Projekt prüfen";


  try {

    const dataBase64 = await fileToBase64(file);


    const result = await api("/api/projects/check", { timeoutMs: 25000,

      method: "POST",

      body: JSON.stringify({

        lessonId: lesson.id,

        dataBase64

      })

    });


    const check = result?.result || {};


    if (

      check.passed &&

      result?.verificationToken

    ) {

      state.projectVerificationTokens[lesson.id] =

        result.verificationToken;

    } else {

      delete state.projectVerificationTokens[lesson.id];

    }


    resultBox.innerHTML = `

      <div class="${check.passed ? "success" : "error"}">

        <strong>${check.passed ? "✅ Aufgabe erfüllt!" : "❌ Noch nicht erfüllt"}</strong>

        <p>${escapeHtml(check.feedback || "")}</p>

        ${

          Array.isArray(check.details)

            ? `<div class="check-details">

                ${check.details.map(item => `

                  <p>${item.passed ? "✅" : "❌"} ${escapeHtml(item.message || "")}</p>

                `).join("")}

              </div>`

            : ""

        }

      </div>

    `;


    if (check.passed) {

      completeButton.disabled = false;

      completeButton.textContent = "Lektion abschließen";

      completeButton.className = "primary-button";

      document.querySelector("#lessonResult").textContent =

        "Projekt erfolgreich geprüft. Jetzt kannst du die Lektion abschließen.";

    } else {

      completeButton.disabled = true;

      completeButton.textContent = "🔒 Erst Projekt prüfen";

      document.querySelector("#lessonResult").textContent =

        "Achte noch einmal auf die fehlenden Anforderungen.";

    }

  } catch (error) {

    resultBox.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;

    completeButton.disabled = true;

  }

}


async function checkScratchLink(lesson) {

  const input = document.querySelector("#scratchProjectUrl");

  const resultBox = document.querySelector("#lessonCheckResult");

  const completeButton = document.querySelector("#completeLesson");

  const button = document.querySelector("#checkScratchLink");


  const url = String(input?.value || "").trim();


  if (!url) {

    resultBox.innerHTML = `<p class="error">Bitte füge zuerst deinen Scratch-Projekt-Link ein.</p>`;

    return;

  }


  button.disabled = true;

  button.textContent = "Projekt wird geprüft...";

  completeButton.disabled = true;

  delete state.projectVerificationTokens[lesson.id];

  resultBox.innerHTML = `<p class="muted">🔎 Dein Scratch-Projekt wird geprüft...</p>`;


  try {

    const result = await api("/api/projects/check-link", { timeoutMs: 25000,

      method: "POST",

      body: JSON.stringify({

        lessonId: lesson.id,

        scratchUrl: url

      })

    });


    const check = result?.result || {};


    resultBox.innerHTML = `

      <div class="${check.passed ? "success" : "error"}">

        <strong>${check.passed ? "✅ Aufgabe erfüllt!" : "❌ Noch nicht erfüllt"}</strong>

        <p>${escapeHtml(check.feedback || "")}</p>

        ${

          Array.isArray(check.details)

            ? `<div class="check-details">

                ${check.details.map(item =>

                  `<p>${item.passed ? "✅" : "❌"} ${escapeHtml(item.message || "")}</p>`

                ).join("")}

              </div>`

            : ""

        }

      </div>

    `;


    if (check.passed && result.verificationToken) {

      state.projectVerificationTokens[lesson.id] = result.verificationToken;

      completeButton.disabled = false;

      completeButton.textContent = "Lektion abschließen";

      completeButton.className = "primary-button";

      document.querySelector("#lessonResult").textContent =

        "Projekt erfolgreich geprüft. Jetzt kannst du die Lektion abschließen.";

    } else {

      delete state.projectVerificationTokens[lesson.id];

      completeButton.disabled = true;

      completeButton.textContent = "🔒 Erst Projekt prüfen";

      document.querySelector("#lessonResult").textContent =

        "Achte noch einmal auf die fehlenden Anforderungen.";

    }

  } catch (error) {

    delete state.projectVerificationTokens[lesson.id];

    resultBox.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;

    completeButton.disabled = true;

    completeButton.textContent = "🔒 Erst Projekt prüfen";

  } finally {

    button.disabled = false;

    button.textContent = "Scratch-Projekt prüfen";

  }

}


async function completeLesson(lesson) {

  if (!state.user) {

    location.hash = "#/login";

    return;

  }


  const button = document.querySelector("#completeLesson");

  const resultBox = document.querySelector("#lessonResult");


  button.disabled = true;

  button.textContent = "Wird gespeichert...";


  try {

    const result = await api(

      `/api/lessons/${encodeURIComponent(lesson.id)}/complete`,

      { method: "POST", body: "{}" }

    );


    state.user = result.user || state.user;

    state.progress = { ...EMPTY_PROGRESS, ...(await api("/api/progress")) };


    button.textContent = "Schon geschafft";

    button.className = "secondary-button";

    resultBox.textContent = result.awardedXp

      ? `Lektion erfolgreich abgeschlossen! +${result.awardedXp} XP.`

      : "Diese Lektion war schon gespeichert.";

  } catch (error) {

    button.disabled = false;

    button.textContent = "Lektion abschließen";

    resultBox.textContent = error.message;

  }

}


async function askAssistant(lessonId, form) {

  const textarea = form.querySelector('textarea[name="message"]');

  const imageInput = form.querySelector("#assistantImage");

  const answerBox = document.querySelector("#assistantAnswer");

  const statusBox = document.querySelector("#assistantStatus");

  const button = form.querySelector('button[type="submit"]');

  const text = String(textarea?.value || "").trim();

  const image = imageInput?.files?.length ? imageInput.files[0] : null;

  const hasImage = image instanceof File && image.size > 0;


  if (!text && !hasImage) return;


  answerBox.insertAdjacentHTML(

    "beforeend",

    `<div class="chat-turn user-turn">${escapeHtml(text || "Screenshot hochgeladen")}</div>`

  );

  if (button) { button.disabled = true; button.textContent = "KI antwortet..."; }

  if (statusBox) statusBox.textContent = "KI denkt nach...";


  try {

    const body = {

      message: text || "Analysiere meinen Screenshot und hilf mir bei dieser Scratch-Lektion.",

      lessonId,

    };


    if (hasImage) {

      let mimeType = image.type;

      if (!mimeType && image.name.toLowerCase().endsWith(".jpg")) mimeType = "image/jpeg";

      if (!mimeType && image.name.toLowerCase().endsWith(".jpeg")) mimeType = "image/jpeg";

      if (!mimeType && image.name.toLowerCase().endsWith(".png")) mimeType = "image/png";

      if (!mimeType && image.name.toLowerCase().endsWith(".webp")) mimeType = "image/webp";

      if (!["image/png", "image/jpeg", "image/webp"].includes(mimeType)) throw new Error("Bitte nutze PNG, JPG/JPEG oder WebP.");

      if (image.size > 5 * 1024 * 1024) throw new Error("Der Screenshot darf maximal 5 MB groÃŸ sein.");

      body.imageBase64 = await fileToBase64(image);

      body.imageMimeType = mimeType;

    }


    const result = await api("/api/assistant", {

      timeoutMs: 40000,

      method: "POST",

      body: JSON.stringify(body),

    });


    answerBox.insertAdjacentHTML(

      "beforeend",

      `<div class="chat-turn coach-turn">${escapeHtml(result?.response || "Gemini hat keine Antwort geliefert.")}</div>`

    );

    textarea.value = "";

    if (imageInput) imageInput.value = "";

    if (statusBox) statusBox.textContent = "";

    answerBox.scrollTop = answerBox.scrollHeight;

  } catch (error) {

    answerBox.insertAdjacentHTML(

      "beforeend",

      `<div class="chat-turn coach-turn">âš ï¸ ${escapeHtml(error?.message || "Die KI konnte gerade nicht antworten.")}</div>`

    );

    if (statusBox) statusBox.textContent = "";

  } finally {

    if (button) { button.disabled = false; button.textContent = "Fragen"; }

  }

}

function formatBytes(bytes) {

  if (bytes < 1024) return `${bytes} B`;

  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;

  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;

}


function fileToBase64(file) {

  return new Promise((resolve, reject) => {

    const reader = new FileReader();

    reader.onload = () => {

      const value = String(reader.result);

      const comma = value.indexOf(",");

      resolve(comma >= 0 ? value.slice(comma + 1) : value);

    };

    reader.onerror = () => reject(new Error("Die Datei konnte nicht gelesen werden."));

    reader.readAsDataURL(file);

  });

}


function renderFeedback() {

  setView(`

    <section class="screen grid two">

      <div>

        <p class="eyebrow">Feedback & Hilfe</p>

        <h2>Hilf uns, ScratchLab besser zu machen.</h2>

        <p>Was gefällt dir? Was fehlt? Oder ist etwas kaputt?</p>

      </div>


      <div class="panel">

        <form id="feedbackForm">

          <label>Bewertung

            <select name="rating" required>

              <option value="">Bitte auswählen</option>

              <option value="5">⭐⭐⭐⭐⭐ – Sehr gut</option>

              <option value="4">⭐⭐⭐⭐ – Gut</option>

              <option value="3">⭐⭐⭐ – Okay</option>

              <option value="2">⭐⭐ – Könnte besser sein</option>

              <option value="1">⭐ – Nicht gut</option>

            </select>

          </label>


          <label>Kategorie

            <select name="type" required>

              <option value="Lob">Lob</option>

              <option value="Verbesserung">Verbesserung</option>

              <option value="Fehler">Fehler</option>

              <option value="Hilfe">Hilfe</option>

            </select>

          </label>


          <label>Dein Feedback

            <textarea name="message" required minlength="5" placeholder="Schreib hier dein Feedback..."></textarea>

          </label>


          <label>E-Mail (optional)

            <input name="email" type="email" placeholder="Nur wenn wir antworten sollen">

          </label>


          <button class="primary-button" type="submit">Feedback senden</button>

          <p id="feedbackResult" class="success"></p>

        </form>

      </div>

    </section>

  `);


  document.querySelector("#feedbackForm")?.addEventListener("submit", async event => {

    event.preventDefault();

    const form = event.currentTarget;

    const resultBox = document.querySelector("#feedbackResult");

    const button = form.querySelector("button");


    button.disabled = true;

    resultBox.textContent = "";


    try {

      const data = Object.fromEntries(new FormData(form).entries());

      await api("/api/feedback", {

        method: "POST",

        body: JSON.stringify(data)

      });


      form.reset();

      resultBox.textContent = "Danke! Dein Feedback wurde gespeichert.";

    } catch (error) {

      resultBox.textContent = error.message;

    } finally {

      button.disabled = false;

    }

  });

}


async function renderAdminFeedback() {

  if (!state.user?.isAdmin) {

    setView(`

      <section class="screen">

        <div class="panel">

          <p class="eyebrow">Betreiber</p>

          <h2>Kein Zugriff</h2>

          <p>Diese Seite ist nur für den ScratchLab-Betreiber verfügbar.</p>

          <a class="secondary-button" href="#/dashboard">Zum Dashboard</a>

        </div>

      </section>

    `);

    return;

  }


  setView(`

    <section class="screen">

      <div class="screen-header">

        <div>

          <p class="eyebrow">Betreiberbereich</p>

          <h2>Feedback</h2>

          <p>Hier siehst du die Rückmeldungen, die über ScratchLab eingesendet wurden.</p>

        </div>

        <button id="refreshAdminFeedback" class="secondary-button" type="button">Aktualisieren</button>

      </div>


      <div class="panel">

        <div id="adminFeedbackStatus" class="muted">Feedback wird geladen...</div>

        <div id="adminFeedbackList"></div>

      </div>

    </section>

  `);


  async function loadAdminFeedback() {

    const status = document.querySelector("#adminFeedbackStatus");

    const list = document.querySelector("#adminFeedbackList");


    status.textContent = "Feedback wird geladen...";

    list.innerHTML = "";


    try {

      const data = await api("/api/admin/feedback", { timeoutMs: 15000 });

      const items = Array.isArray(data?.feedback) ? data.feedback : [];


      if (!items.length) {

        status.textContent = "Noch kein Feedback vorhanden.";

        return;

      }


      status.textContent = `${items.length} Feedback${items.length === 1 ? "" : "s"} gefunden.`;


      list.innerHTML = items.map(item => {

        const stars = item.rating

          ? "⭐".repeat(Math.max(1, Math.min(5, Number(item.rating))))

          : "Keine Bewertung";


        const date = item.created_at

          ? new Date(item.created_at).toLocaleString("de-DE")

          : "Unbekannt";


        return `

          <article class="panel" style="margin-top:16px;">

            <div class="progress-row">

              <strong>${escapeHtml(item.type || "Feedback")}</strong>

              <span>${escapeHtml(date)}</span>

            </div>

            <p>${escapeHtml(item.message || "")}</p>

            <p class="muted">

              ${escapeHtml(stars)}

              ${item.email ? ` · ${escapeHtml(item.email)}` : " · Keine E-Mail angegeben"}

            </p>

          </article>

        `;

      }).join("");

    } catch (error) {

      status.innerHTML = `<span class="error">${escapeHtml(error.message)}</span>`;

    }

  }


  document.querySelector("#refreshAdminFeedback")?.addEventListener("click", loadAdminFeedback);

  await loadAdminFeedback();

}


function renderPremium() {

  const pricing = state.pricing;


  setView(`

    <section class="screen grid two">

      <div>

        <p class="eyebrow">Weiterlernen</p>

        <h2>Alle Lektionen freischalten.</h2>

        <p>Eine Premium-Lektion kostet ${pricing.singleLessonPriceEur} € oder Premium kostet ${pricing.premiumMonthlyPriceEur} € im Monat.</p>

        <a class="secondary-button" href="#/learn">Zurück zu den Kursen</a>

      </div>


      <div class="panel premium-panel">

        <h3>Premium</h3>

        <div class="price">${pricing.premiumMonthlyPriceEur} € <span>/ Monat</span></div>

        <p>Alle aktuellen und späteren Scratch-Lektionen freischalten.</p>

        <button id="upgradePremium" class="primary-button" type="button">Jetzt auf Premium upgraden</button>

        <p id="premiumMessage" class="muted">

          ${pricing.checkoutReady ? "Stripe ist konfiguriert." : "Stripe ist noch nicht vollständig konfiguriert."}

        </p>

      </div>

    </section>

  `);


  document.querySelector("#upgradePremium")?.addEventListener("click", async () => {

    const message = document.querySelector("#premiumMessage");

    try {

      const result = await api("/api/checkout/premium", {

        method: "POST",

        body: "{}"

      });


      if (result.checkoutUrl) {

        window.location.href = result.checkoutUrl;

      } else {

        message.textContent = result.error || "Checkout konnte nicht gestartet werden.";

      }

    } catch (error) {

      message.textContent = error.message;

    }

  });


  const cancelButton = document.querySelector("#cancelPremium");
  if (cancelButton) {
    cancelButton.addEventListener("click", async () => {
      const message = document.querySelector("#cancelPremiumMessage");
      const confirmed = window.confirm(
        "MÃ¶chtest du Premium wirklich kÃ¼ndigen? Dein Premium bleibt bis zum Ende des bereits bezahlten Zeitraums aktiv."
      );
      if (!confirmed) return;

      cancelButton.disabled = true;
      cancelButton.textContent = "Wird gekÃ¼ndigt...";

      try {
        const result = await api("/api/premium/cancel", {
          method: "POST",
          body: "{}",
        });

        message.textContent = result?.alreadyScheduled
          ? "Premium ist bereits zum Ende des Zeitraums gekÃ¼ndigt."
          : "Premium wurde gekÃ¼ndigt. Es bleibt bis zum Ende des bereits bezahlten Zeitraums aktiv.";
        cancelButton.textContent = "Premium gekÃ¼ndigt";
      } catch (error) {
        cancelButton.disabled = false;
        cancelButton.textContent = "Premium kÃ¼ndigen";
        message.textContent = error?.message || "Die KÃ¼ndigung konnte nicht durchgefÃ¼hrt werden.";
      }
    });
  }}


function renderLockedLesson(id) {

  const lesson = allLessons().find(item => String(item.id) === String(id));


  if (!lesson) {

    setView(`<section class="screen"><h2>Lektion nicht gefunden</h2></section>`);

    return;

  }


  setView(`

    <section class="screen grid two">

      <div>

        <a class="secondary-button back-button" href="#/learn">Zurück zum Kurs</a>

        <p class="eyebrow">Premium-Lektion</p>

        <h2>${escapeHtml(lesson.title)}</h2>

        <p>${escapeHtml(lesson.summary || "")}</p>

      </div>


      <div class="panel premium-panel">

        <h3>Freischalten</h3>

        <div class="price">${lesson.price_eur || state.pricing.singleLessonPriceEur} € <span>einmalig</span></div>

        <button id="buyLesson" class="secondary-button" type="button">Diese Lektion kaufen</button>

        <hr>

        <div class="price">${state.pricing.premiumMonthlyPriceEur} € <span>/ Monat</span></div>

        <a class="primary-button" href="#/premium">Jetzt auf Premium upgraden</a>

        <p id="purchaseMessage" class="muted"></p>

      </div>

    </section>

  `);


  document.querySelector("#buyLesson")?.addEventListener("click", async () => {

    const message = document.querySelector("#purchaseMessage");

    try {

      const result = await api("/api/checkout/lesson", {

        method: "POST",

        body: JSON.stringify({ lessonId: lesson.id })

      });


      if (result.checkoutUrl) {

        window.location.href = result.checkoutUrl;

      } else {

        message.textContent = result.error || "Checkout konnte nicht gestartet werden.";

      }

    } catch (error) {

      message.textContent = error.message;

    }

  });

}


function projectCard(project) {

  return `

    <article class="project-card">

      <h3>${escapeHtml(project.title)}</h3>

      <p>${escapeHtml(project.description || "Keine Beschreibung")}</p>

      ${

        project.scratch_url

          ? `<a class="secondary-button" href="${escapeHtml(project.scratch_url)}" target="_blank" rel="noopener noreferrer">Scratch öffnen</a>`

          : ""

      }

      <span class="pill">${project.is_public ? "Öffentlich" : "Privat"}</span>

    </article>

  `;

}


async function renderProjects() {

  if (!state.user) {

    location.hash = "#/login";

    return;

  }


  try {

    state.projects = await api("/api/projects");

  } catch {

    state.projects = { own: [], public: [] };

  }


  setView(`

    <section class="screen">

      <div class="screen-header">

        <div>

          <p class="eyebrow">Deine Werkstatt</p>

          <h2>Scratch-Projekte</h2>

          <p>Speichere deine Ideen und prüfe deine .sb3-Dateien.</p>

        </div>

        <a class="secondary-button" href="#/feedback">Feedback & Hilfe</a>

      </div>


      <div class="grid two">

        <form id="projectForm" class="panel">

          <h3>Projekt speichern</h3>


          <label>Titel

            <input name="title" required minlength="3">

          </label>


          <label>Beschreibung

            <textarea name="description"></textarea>

          </label>


          <label>Scratch-Link

            <input name="scratchUrl" placeholder="https://scratch.mit.edu/projects/...">

          </label>


          <label class="inline-label">

            <input name="isPublic" type="checkbox">

            Öffentlich sichtbar machen

          </label>


          <button class="primary-button" type="submit">Speichern</button>

          <p id="projectError" class="error"></p>

        </form>


        <form id="checkForm" class="panel">

          <h3>.sb3 prüfen</h3>


          <label>Lektion

            <select name="lessonId">

              ${allLessons().map(lesson =>

                `<option value="${escapeHtml(lesson.id)}">${escapeHtml(lesson.title)}</option>`

              ).join("")}

            </select>

          </label>


          <label>Scratch-Datei

            <input name="sb3" type="file" accept=".sb3,application/zip" required>

          </label>


          <button class="secondary-button" type="submit">Projekt prüfen</button>

          <div id="checkResult" class="check-result"></div>

        </form>

      </div>


      <div class="project-list" style="margin-top:16px">

        ${

          Array.isArray(state.projects.own) && state.projects.own.length

            ? state.projects.own.map(projectCard).join("")

            : `<div class="panel"><p class="muted">Dein erstes Projekt wartet.</p></div>`

        }

      </div>

    </section>

  `);


  document.querySelector("#projectForm")?.addEventListener("submit", saveProject);

  document.querySelector("#checkForm")?.addEventListener("submit", checkProject);

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


    await renderProjects();

  } catch (error) {

    document.querySelector("#projectError").textContent = error.message;

  }

}


async function checkProject(event) {

  event.preventDefault();


  const form = new FormData(event.currentTarget);

  const file = form.get("sb3");

  const resultBox = document.querySelector("#checkResult");


  if (!file || !(file instanceof File) || !file.size) {

    resultBox.innerHTML = `<p class="error">Bitte wähle eine .sb3-Datei aus.</p>`;

    return;

  }


  if (!file.name.toLowerCase().endsWith(".sb3")) {

    resultBox.innerHTML = `<p class="error">Bitte lade eine echte Scratch-.sb3-Datei hoch.</p>`;

    return;

  }


  if (file.size > 10 * 1024 * 1024) {

    resultBox.innerHTML = `<p class="error">Die Datei darf maximal 10 MB groß sein.</p>`;

    return;

  }


  resultBox.innerHTML = `<p class="muted">🔎 Projekt wird geprüft...</p>`;


  try {

    const result = await api("/api/projects/check", { timeoutMs: 25000,

      method: "POST",

      body: JSON.stringify({

        lessonId: form.get("lessonId"),

        dataBase64: await fileToBase64(file)

      })

    });


    const check = result?.result || {};


    resultBox.innerHTML = `

      <div class="${check.passed ? "success" : "error"}">

        <strong>${check.passed ? "✅ Aufgabe erfüllt!" : "❌ Noch nicht erfüllt"}</strong>

        <p>${escapeHtml(check.feedback || "")}</p>

        ${

          Array.isArray(check.details)

            ? check.details.map(item =>

                `<p>${item.passed ? "✅" : "❌"} ${escapeHtml(item.message || "")}</p>`

              ).join("")

            : ""

        }

      </div>

    `;

  } catch (error) {

    resultBox.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;

  }

}


async function renderRouter() {

  await refresh();


  const hash = location.hash.replace(/^#\/?/, "");

  const [route, id] = hash.split("/");


  switch (route) {

    case "":

      renderLanding();

      break;

    case "signup":

      renderAuth("signup");

      break;

    case "login":

      renderAuth("login");

      break;

    case "dashboard":

      renderDashboard();

      break;

    case "learn":

      renderLearn();

      break;

    case "lesson":

      renderLesson(id);

      break;

    case "locked":

      renderLockedLesson(id);

      break;

    case "projects":

      await renderProjects();

      break;

    case "premium":

      renderPremium();

      break;

    case "feedback":

      renderFeedback();

      break;

    case "admin-feedback":

      await renderAdminFeedback();

      break;

    default:

      renderLanding();

  }

}


if (authAction) {

  authAction.addEventListener("click", async () => {

    if (!state.user) {

      location.hash = "#/login";

      return;

    }


    try {

      await api("/api/auth/logout", {

        method: "POST",

        body: "{}"

      });

    } catch {

      // Cookie wird trotzdem lokal gelöscht.

    }


    state.user = null;

    state.progress = { ...EMPTY_PROGRESS };

    location.hash = "#/";

    await renderRouter();

  });

}


window.addEventListener("hashchange", () => {

  renderRouter().catch(error => {

    setView(`

      <section class="screen">

        <h2>ScratchLab braucht kurz Hilfe</h2>

        <p class="error">${escapeHtml(error.message)}</p>

        <a class="secondary-button" href="#/">Zur Startseite</a>

      </section>

    `);

  });

});


renderRouter().catch(error => {

  setView(`

    <section class="screen">

      <h2>ScratchLab braucht kurz Hilfe</h2>

      <p class="error">${escapeHtml(error.message)}</p>

      <a class="secondary-button" href="#/">Zur Startseite</a>

    </section>

  `);

});