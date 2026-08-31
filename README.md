const app = document.querySelector("#app");
const authAction = document.querySelector("#authAction");

const state = {
  user: null,
  courses: [],
  progress: {
    completed: [],
    badges: [],
    courseProgress: [],
    projects: [],
    recentActivity: [],
    nextLesson: null
  },
  projects: {
    own: [],
    public: []
  },
  pricing: {
    singleLessonPriceEur: 5,
    premiumMonthlyPriceEur: 15,
    checkoutReady: false
  }
};

/* =========================================================
   HILFSFUNKTIONEN
========================================================= */

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  })[char]);
}

function normalizeLessons(lessons) {
  if (Array.isArray(lessons)) return lessons;

  if (lessons && typeof lessons === "object") {
    return Object.values(lessons);
  }

  return [];
}

function normalizeCourses(courses) {
  if (!Array.isArray(courses)) return [];

  return courses.map((course, index) => ({
    ...course,
    id: course.id || `course-${index + 1}`,
    title: course.title || `Kurs ${index + 1}`,
    description: course.description || "",
    difficulty: course.difficulty || "Anfänger",
    lessons: normalizeLessons(course.lessons)
  }));
}

function completedIds() {
  const completed = Array.isArray(state.progress.completed)
    ? state.progress.completed
    : [];

  return new Set(
    completed
      .map(item => {
        if (typeof item === "string") return item;
        return item?.lesson_id || item?.lessonId || item?.id;
      })
      .filter(Boolean)
  );
}

function allLessons() {
  const result = [];

  for (const course of state.courses) {
    const lessons = normalizeLessons(course.lessons);

    for (const lesson of lessons) {
      if (!lesson || typeof lesson !== "object") continue;

      result.push({
        ...lesson,
        id: lesson.id || "",
        courseId: course.id,
        courseTitle: course.title
      });
    }
  }

  return result;
}

function findLesson(id) {
  if (!id) return null;

  return allLessons().find(
    lesson => String(lesson.id) === String(id)
  ) || null;
}

function lessonById(id) {
  for (const course of state.courses) {
    const lessons = normalizeLessons(course.lessons);

    const lesson = lessons.find(
      item => String(item.id) === String(id)
    );

    if (lesson) {
      return { course, lesson };
    }
  }

  return {};
}

/* =========================================================
   API
========================================================= */

async function api(path, options = {}) {
  const config = {
    credentials: "same-origin",
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {})
    }
  };

  const response = await fetch(path, config);

  let data = null;

  try {
    data = await response.json();
  } catch {
    data = {};
  }

  if (!response.ok) {
    throw new Error(
      data?.error ||
      data?.message ||
      `Serverfehler (${response.status})`
    );
  }

  return data;
}

/* =========================================================
   DATEN LADEN
========================================================= */

async function refresh() {
  /*
   * Jeder Bereich wird einzeln geladen.
   * Dadurch zerstört ein Fehler bei Pricing z.B. nicht
   * mehr die komplette Startseite.
   */

  try {
    const me = await api("/api/me");
    state.user = me?.user || null;
  } catch {
    state.user = null;
  }

  try {
    const courses = await api("/api/courses");
    state.courses = normalizeCourses(courses?.courses);
  } catch (error) {
    console.error("Kurse konnten nicht geladen werden:", error);
    state.courses = [];
  }

  try {
    const pricing = await api("/api/pricing");

    state.pricing = {
      ...state.pricing,
      ...(pricing || {})
    };
  } catch (error) {
    console.warn("Pricing konnte nicht geladen werden:", error);
  }

  if (state.user) {
    try {
      const progress = await api("/api/progress");

      state.progress = {
        ...state.progress,
        ...(progress || {})
      };
    } catch (error) {
      console.warn("Fortschritt konnte nicht geladen werden:", error);
    }
  } else {
    state.progress = {
      completed: [],
      badges: [],
      courseProgress: [],
      projects: [],
      recentActivity: [],
      nextLesson: null
    };
  }

  if (authAction) {
    authAction.textContent = state.user
      ? "Logout"
      : "Einloggen";
  }
}

/* =========================================================
   VIEW
========================================================= */

function setView(html) {
  app.innerHTML = html;

  window.scrollTo({
    top: 0,
    behavior: "smooth"
  });
}

/* =========================================================
   STARTSEITE
========================================================= */

function renderLanding() {
  const courseCount = state.courses.length;
  const lessonCount = allLessons().length;

  setView(`
    <section class="hero">
      <div class="hero-copy">
        <p class="eyebrow">
          Scratch lernen, ohne Schulgefühl
        </p>

        <h1>ScratchLab</h1>

        <p class="lead">
          Programmieren lernen. Scratch verstehen.
          Eigene Ideen bauen.
        </p>

        <div class="hero-actions">
          <a class="primary-button" href="#/signup">
            Kostenlos starten
          </a>

          <a class="secondary-button" href="#/learn">
            Kurse ansehen
          </a>
        </div>
      </div>

      <div class="play-stage" aria-label="ScratchLab Vorschau">
        <div class="stage-header">
          <span></span>
          <span></span>
          <span></span>
        </div>

        <div class="sprite"></div>

        <div class="speech">
          Ich baue mein erstes Spiel!
        </div>

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
        <span>
          Jede Lektion startet mit einem klaren Lernziel.
        </span>
      </article>

      <article>
        <strong>2. Selbst bauen</strong>
        <span>
          Du probierst direkt in Scratch und siehst ein Ergebnis.
        </span>
      </article>

      <article>
        <strong>3. Weiter wachsen</strong>
        <span>
          XP, Badges, Projekte und KI-Hilfe halten dich im Flow.
        </span>
      </article>
    </section>

    <section class="screen landing-grid">

      <div class="panel">
        <h3>
          ${courseCount} Kurse,
          ${lessonCount} Lektionen
        </h3>

        <p>
          Von der ersten sprechenden Figur
          bis zum eigenen Mini-Spiel.
        </p>

        <a class="secondary-button" href="#/learn">
          Kursübersicht
        </a>
      </div>

      <div class="panel">
        <h3>KI-Tutor</h3>

        <p>
          Gemini hilft mit Fragen, Tipps und kleinen
          Denkanstößen, ohne dir sofort alles fertig zu lösen.
        </p>
      </div>

      <div class="panel">
        <h3>Projektprüfung</h3>

        <p>
          Lade später deine .sb3-Datei hoch und
          ScratchLab prüft wichtige Blöcke automatisch.
        </p>
      </div>

    </section>
  `);
}

/* =========================================================
   LOGIN / REGISTER
========================================================= */

function renderAuth(mode = "signup") {
  const isSignup = mode === "signup";

  setView(`
    <section class="screen grid two">

      <div>
        <p class="eyebrow">
          ${isSignup ? "Kostenlos starten" : "Willkommen zurück"}
        </p>

        <h2>
          ${
            isSignup
              ? "In 60 Sekunden bereit für die erste Scratch-Aufgabe."
              : "Weiterlernen, wo du aufgehört hast."
          }
        </h2>

        <p>
          Dein Fortschritt, XP, Badges und Projekte
          werden gespeichert.
        </p>
      </div>

      <div class="panel">

        <form id="authForm">

          ${
            isSignup
              ? `
                <label>
                  Benutzername
                  <input
                    name="username"
                    autocomplete="username"
                    required
                    minlength="3"
                  >
                </label>
              `
              : ""
          }

          <label>
            E-Mail
            <input
              name="email"
              type="email"
              autocomplete="email"
              required
            >
          </label>

          <label>
            Passwort
            <input
              name="password"
              type="password"
              autocomplete="${
                isSignup ? "new-password" : "current-password"
              }"
              required
              minlength="8"
            >
          </label>

          <button
            id="authSubmit"
            class="primary-button"
            type="submit"
          >
            ${isSignup ? "Account erstellen" : "Einloggen"}
          </button>

          <p class="muted">
            ${
              isSignup
                ? `Schon dabei?
                   <a href="#/login">Einloggen</a>`
                : `Neu hier?
                   <a href="#/signup">Kostenlos starten</a>`
            }
          </p>

          <p id="authError" class="error"></p>

        </form>

      </div>
    </section>
  `);

  const form = document.querySelector("#authForm");
  const submitButton = document.querySelector("#authSubmit");
  const errorBox = document.querySelector("#authError");

  form.addEventListener("submit", async event => {
    event.preventDefault();

    errorBox.textContent = "";

    const formData = new FormData(form);

    const payload = Object.fromEntries(
      formData.entries()
    );

    submitButton.disabled = true;
    submitButton.textContent = isSignup
      ? "Account wird erstellt..."
      : "Einloggen...";

    try {
      const endpoint = isSignup
        ? "/api/auth/register"
        : "/api/auth/login";

      const result = await api(endpoint, {
        method: "POST",
        body: JSON.stringify(payload)
      });

      /*
       * Wichtig:
       * User direkt aus der Login-Antwort übernehmen.
       */
      if (result?.user) {
        state.user = result.user;
      }

      /*
       * Danach Serverzustand erneut laden.
       */
      await refresh();

      if (!state.user) {
        throw new Error(
          "Login wurde akzeptiert, aber der Benutzer konnte nicht geladen werden."
        );
      }

      location.hash = "#/dashboard";

    } catch (error) {
      console.error("Auth-Fehler:", error);

      errorBox.textContent =
        error?.message ||
        "Anmeldung fehlgeschlagen.";

      submitButton.disabled = false;

      submitButton.textContent = isSignup
        ? "Account erstellen"
        : "Einloggen";
    }
  });
}

/* =========================================================
   DASHBOARD
========================================================= */

function renderDashboard() {
  if (!state.user) {
    location.hash = "#/login";
    return;
  }

  const lessons = allLessons();

  const next =
    state.progress.nextLesson ||
    lessons.find(
      lesson => !completedIds().has(lesson.id)
    ) ||
    lessons[0];

  const totalLessons = lessons.length;

  const doneCount = completedIds().size;

  const percent = totalLessons
    ? Math.round((doneCount / totalLessons) * 100)
    : 0;

  setView(`
    <section class="screen">

      <div class="screen-header">

        <div>
          <p class="eyebrow">Dashboard</p>

          <h2>
            Hi ${escapeHtml(state.user.username)},
            weiter geht's.
          </h2>

          <p>
            Dein nächster sinnvoller Schritt ist schon bereit.
          </p>
        </div>

        ${statsHtml()}
      </div>

      <div class="panel">

        <div class="progress-row">
          <strong>Gesamtfortschritt</strong>
          <span>
            ${doneCount}/${totalLessons} Lektionen
          </span>
        </div>

        <div class="progress-track">
          <span style="width:${percent}%"></span>
        </div>

      </div>

      <div class="grid two dashboard-grid">

        <div class="panel">
          <h3>Weiterlernen</h3>

          ${
            next
              ? `
                <p>
                  <strong>${escapeHtml(next.title)}</strong>
                  <br>
                  <span class="muted">
                    ${escapeHtml(next.summary || "")}
                  </span>
                </p>

                <a
                  class="primary-button"
                  href="${
                    next.premium &&
                    state.user.premiumStatus !== "premium"
                      ? `#/locked/${encodeURIComponent(next.id)}`
                      : `#/lesson/${encodeURIComponent(next.id)}`
                  }"
                >
                  Weiterlernen
                </a>
              `
              : `
                <p class="muted">
                  Noch keine Lektionen vorhanden.
                </p>

                <a
                  class="secondary-button"
                  href="#/learn"
                >
                  Kurse ansehen
                </a>
              `
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

/* =========================================================
   KURSE
========================================================= */

function renderLearn() {
  const done = completedIds();

  setView(`
    <section class="screen">

      <div class="screen-header">

        <div>
          <p class="eyebrow">Kurse</p>

          <h2>
            Scratch Schritt für Schritt
          </h2>

          <p>
            Alle Kurse bauen logisch aufeinander auf.
            Die ersten Grundlagen sind kostenlos.
          </p>
        </div>

        ${
          state.user
            ? statsHtml()
            : `
              <a
                class="primary-button"
                href="#/signup"
              >
                Fortschritt speichern
              </a>
            `
        }

      </div>

      <div class="course-list">

        ${
          state.courses.length
            ? state.courses
                .map(course => courseCard(course, done))
                .join("")
            : `
              <div class="panel">
                <h3>Noch keine Kurse geladen</h3>
                <p class="muted">
                  Bitte Seite neu laden.
                </p>
              </div>
            `
        }

      </div>

    </section>
  `);
}

function courseCard(course, done) {
  const lessons = normalizeLessons(course.lessons);

  const completed = lessons.filter(
    lesson => done.has(lesson.id)
  ).length;

  const percent = lessons.length
    ? Math.round((completed / lessons.length) * 100)
    : 0;

  return `
    <article class="panel course-card">

      <div>

        <span class="pill">
          ${escapeHtml(course.difficulty || "Anfänger")}
        </span>

        <h3>
          ${escapeHtml(course.title)}
        </h3>

        <p>
          ${escapeHtml(course.description)}
        </p>

        <div class="progress-row">
          <span>
            ${completed}/${lessons.length} Lektionen
          </span>

          <span>
            ${percent}%
          </span>
        </div>

        <div class="progress-track">
          <span style="width:${percent}%"></span>
        </div>

      </div>

      <div class="lesson-list compact">

        ${
          lessons.length
            ? lessons
                .map(lesson => lessonRow(lesson, done))
                .join("")
            : `
              <p class="muted">
                Keine Lektionen vorhanden.
              </p>
            `
        }

      </div>

    </article>
  `;
}

function lessonRow(lesson, done) {
  const locked =
    Boolean(lesson.premium) &&
    (!state.user ||
      state.user.premiumStatus !== "premium");

  const completed = done.has(lesson.id);

  return `
    <article
      class="
        lesson-card
        ${completed ? "completed" : ""}
        ${locked ? "locked" : ""}
      "
    >

      <div>

        <span class="pill">
          ${
            locked
              ? "Premium"
              : `${Number(lesson.xp || 0)} XP`
          }
        </span>

        <h3>
          ${escapeHtml(lesson.title)}
        </h3>

        <p>
          ${escapeHtml(lesson.summary || "")}
        </p>

      </div>

      <a
        class="secondary-button"
        href="${
          locked
            ? `#/locked/${encodeURIComponent(lesson.id)}`
            : `#/lesson/${encodeURIComponent(lesson.id)}`
        }"
      >
        ${
          locked
            ? "Freischalten"
            : completed
              ? "Wiederholen"
              : "Starten"
        }
      </a>

    </article>
  `;
}

/* =========================================================
   STATS
========================================================= */

function statsHtml() {
  if (!state.user) return "";

  return `
    <div class="stats">

      <div class="stat">
        <span>XP</span>
        <strong>
          ${Number(state.user.xp || 0)}
        </strong>
      </div>

      <div class="stat">
        <span>Level</span>
        <strong>
          ${Number(state.user.level || 1)}
        </strong>
      </div>

      <div class="stat">
        <span>Status</span>
        <strong>
          ${escapeHtml(
            state.user.premiumStatus || "free"
          )}
        </strong>
      </div>

    </div>
  `;
}

/* =========================================================
   BADGES
========================================================= */

function badgeHtml() {
  const badges = Array.isArray(
    state.progress.badges
  )
    ? state.progress.badges
    : [];

  if (!badges.length) {
    return `
      <p class="muted">
        Dein erstes Badge wartet nach
        der ersten abgeschlossenen Lektion.
      </p>
    `;
  }

  return badges
    .map(badge => `
      <p>
        <span class="pill">
          ${escapeHtml(badge.icon || "🏆")}
        </span>

        <strong>
          ${escapeHtml(badge.name || "Badge")}
        </strong>

        <br>

        <span class="muted">
          ${escapeHtml(badge.description || "")}
        </span>
      </p>
    `)
    .join("");
}

/* =========================================================
   KURSFORTSCHRITT
========================================================= */

function courseProgressHtml() {
  const progress = Array.isArray(
    state.progress.courseProgress
  )
    ? state.progress.courseProgress
    : [];

  if (!progress.length) {
    return `
      <p class="muted">
        Noch kein Kurs gestartet.
      </p>
    `;
  }

  return progress
    .map(course => `
      <div class="mini-progress">

        <div class="progress-row">

          <strong>
            ${escapeHtml(course.title || "Kurs")}
          </strong>

          <span>
            ${Number(course.completedCount || 0)}/
            ${Number(course.lessonCount || 0)}
          </span>

        </div>

        <div class="progress-track">
          <span
            style="width:${Math.min(
              100,
              Math.max(0, Number(course.percent || 0))
            )}%"
          ></span>
        </div>

      </div>
    `)
    .join("");
}

/* =========================================================
   AKTIVITÄTEN
========================================================= */

function activityHtml() {
  const activities =
    state.progress.recentActivity;

  if (!Array.isArray(activities) || !activities.length) {
    return `
      <p class="muted">
        Schließe deine erste Lektion ab,
        dann erscheint sie hier.
      </p>
    `;
  }

  return activities
    .map(item => `
      <p>
        <span class="pill">
          +${Number(item.xp_awarded || 0)} XP
        </span>

        ${escapeHtml(
          item.lesson_id ||
          item.lessonId ||
          "Lektion"
        )}
      </p>
    `)
    .join("");
}

/* =========================================================
   LEKTION
========================================================= */

function renderLesson(id) {
  const { lesson } = lessonById(id);

  if (!lesson) {
    setView(`
      <section class="screen">
        <h2>Lektion nicht gefunden</h2>
        <a
          class="secondary-button"
          href="#/learn"
        >
          Zurück zu den Kursen
        </a>
      </section>
    `);

    return;
  }

  const locked =
    Boolean(lesson.premium) &&
    (!state.user ||
      state.user.premiumStatus !== "premium");

  if (locked) {
    renderLockedLesson(id);
    return;
  }

  const done = completedIds();
  const isCompleted = done.has(lesson.id);

  const task =
    lesson.task &&
    typeof lesson.task === "object"
      ? lesson.task
      : {
          prompt: "Bearbeite die Aufgabe in Scratch.",
          steps: []
        };

  const steps = Array.isArray(task.steps)
    ? task.steps
    : [];

  const hints = Array.isArray(lesson.hints)
    ? lesson.hints
    : [];

  setView(`
    <section class="screen lesson-layout">

      <article class="panel">

        <a
          class="secondary-button back-button"
          href="#/learn"
        >
          Zurück zum Kurs
        </a>

        <p class="eyebrow">
          ${Number(lesson.xp || 0)} XP
        </p>

        <h2>
          ${escapeHtml(lesson.title)}
        </h2>

        <div class="goal-box">

          <strong>Lernziel</strong>

          <p>
            ${escapeHtml(
              lesson.learning_goal ||
              lesson.summary ||
              ""
            )}
          </p>

        </div>

        <h3>Erklärung</h3>

        <p>
          ${escapeHtml(
            lesson.explanation || ""
          )}
        </p>

        <div class="panel">

          <h3>Beispiel</h3>

          <p>
            ${escapeHtml(
              lesson.example ||
              lesson.demo ||
              ""
            )}
          </p>

        </div>

        <div class="panel task-box">

          <h3>Deine Aufgabe</h3>

          <p>
            ${escapeHtml(
              task.prompt ||
              "Bearbeite diese Aufgabe in Scratch."
            )}
          </p>

          ${
            steps.length
              ? `
                <ol class="steps">
                  ${steps
                    .map(step => `
                      <li>
                        ${escapeHtml(step)}
                      </li>
                    `)
                    .join("")}
                </ol>
              `
              : ""
          }

          <h3>Challenge</h3>

          <p>
            ${escapeHtml(
              lesson.challenge ||
              "Verbessere dein Projekt mit einer eigenen Idee."
            )}
          </p>

          ${
            hints.length
              ? `
                <details>
                  <summary>
                    Hinweise anzeigen
                  </summary>

                  <ul>
                    ${hints
                      .map(hint => `
                        <li>
                          ${escapeHtml(hint)}
                        </li>
                      `)
                      .join("")}
                  </ul>
                </details>
              `
              : ""
          }

          <button
            id="completeLesson"
            class="${
              isCompleted
                ? "secondary-button"
                : "primary-button"
            }"
            type="button"
          >
            ${
              state.user
                ? isCompleted
                  ? "Schon geschafft"
                  : "Lektion abschließen"
                : "Zum Speichern anmelden"
            }
          </button>

          <p
            id="lessonResult"
            class="success"
          >
            ${
              isCompleted
                ? "Diese Lektion ist gespeichert."
                : ""
            }
          </p>

        </div>

      </article>

      <aside class="panel">

        <h3>KI-Hilfe</h3>

        <p class="muted">
          Frag nach einem Hinweis.
          ScratchLab hilft beim Denken,
          nicht beim Abschreiben.
        </p>

        <div class="quick-actions">

          <button
            class="secondary-button ai-quick"
            data-question="Gib mir einen Tipp zu dieser Aufgabe."
          >
            Tipp
          </button>

          <button
            class="secondary-button ai-quick"
            data-question="Erkläre diese Aufgabe einfacher."
          >
            Einfacher
          </button>

          <button
            class="secondary-button ai-quick"
            data-question="Warum funktioniert das bei mir nicht?"
          >
            Fehlerhilfe
          </button>

          <button
            class="secondary-button ai-quick"
            data-question="Was ist der nächste kleine Schritt?"
          >
            Nächster Schritt
          </button>

        </div>

        <form id="assistantForm">

          <textarea
            name="message"
            placeholder="Stelle deine eigene Frage..."
            required
          ></textarea>

          <button
            class="secondary-button"
            type="submit"
          >
            Fragen
          </button>

        </form>

        <div
          id="assistantAnswer"
          class="assistant-chat"
        ></div>

      </aside>

    </section>
  `);

  document
    .querySelector("#completeLesson")
    .addEventListener(
      "click",
      () => completeLesson(lesson)
    );

  document
    .querySelector("#assistantForm")
    .addEventListener(
      "submit",
      event => {
        event.preventDefault();

        const form = event.currentTarget;
        const textarea =
          form.querySelector("textarea");

        askAssistant(
          lesson.id,
          textarea.value,
          form
        );
      }
    );

  document
    .querySelectorAll(".ai-quick")
    .forEach(button => {
      button.addEventListener("click", () => {
        askAssistant(
          lesson.id,
          button.dataset.question,
          document.querySelector(
            "#assistantForm"
          )
        );
      });
    });
}

/* =========================================================
   LEKTION ABSCHLIESSEN
========================================================= */

async function completeLesson(lesson) {
  if (!state.user) {
    location.hash = "#/login";
    return;
  }

  const button =
    document.querySelector(
      "#completeLesson"
    );

  const resultBox =
    document.querySelector(
      "#lessonResult"
    );

  button.disabled = true;
  button.textContent =
    "Wird gespeichert...";

  try {
    const result = await api(
      `/api/lessons/${encodeURIComponent(
        lesson.id
      )}/complete`,
      {
        method: "POST",
        body: "{}"
      }
    );

    if (result?.user) {
      state.user = result.user;
    }

    try {
      state.progress =
        await api("/api/progress");
    } catch {
      // Fortschritt ist bereits lokal aktualisiert.
    }

    button.disabled = false;
    button.textContent =
      "Schon geschafft";

    button.className =
      "secondary-button";

    resultBox.textContent =
      result?.awardedXp
        ? `Lektion abgeschlossen! +${result.awardedXp} XP.`
        : "Diese Lektion war schon gespeichert.";

  } catch (error) {
    button.disabled = false;
    button.textContent =
      "Lektion abschließen";

    resultBox.textContent =
      error?.message ||
      "Die Lektion konnte nicht gespeichert werden.";
  }
}

/* =========================================================
   KI ASSISTENT
========================================================= */

async function askAssistant(
  lessonId,
  question,
  form
) {
  const text = String(
    question || ""
  ).trim();

  if (!text) return;

  const answerBox =
    document.querySelector(
      "#assistantAnswer"
    );

  if (!answerBox) return;

  /*
   * Eigene Frage sofort anzeigen.
   */
  answerBox.insertAdjacentHTML(
    "beforeend",
    `
      <div class="chat-turn user-turn">
        ${escapeHtml(text)}
      </div>
    `
  );

  /*
   * Ladeanzeige.
   */
  const loadingId =
    `ai-loading-${Date.now()}`;

  answerBox.insertAdjacentHTML(
    "beforeend",
    `
      <div
        id="${loadingId}"
        class="chat-turn coach-turn"
      >
        KI denkt nach...
      </div>
    `
  );

  try {
    const result = await api(
      "/api/assistant",
      {
        method: "POST",
        body: JSON.stringify({
          message: text,
          lessonId
        })
      }
    );

    /*
     * Unterschiedliche mögliche API-Formate
     * werden unterstützt.
     */
    const answer =
      result?.response ??
      result?.answer ??
      result?.message ??
      result?.text ??
      result?.data?.response ??
      result?.data?.answer ??
      "";

    const loading =
      document.getElementById(
        loadingId
      );

    if (loading) {
      loading.remove();
    }

    if (!answer) {
      throw new Error(
        "Die KI hat keine Antwort zurückgegeben."
      );
    }

    answerBox.insertAdjacentHTML(
      "beforeend",
      `
        <div class="chat-turn coach-turn">
          ${escapeHtml(answer)}
        </div>
      `
    );

    /*
     * Textfeld nur nach erfolgreicher Antwort leeren.
     */
    if (form) {
      const textarea =
        form.querySelector("textarea");

      if (textarea) {
        textarea.value = "";
      }
    }

  } catch (error) {
    console.error(
      "KI-Fehler:",
      error
    );

    const loading =
      document.getElementById(
        loadingId
      );

    if (loading) {
      loading.remove();
    }

    answerBox.insertAdjacentHTML(
      "beforeend",
      `
        <div class="chat-turn coach-turn">
          Die KI ist gerade nicht erreichbar.
          Bitte versuche es gleich noch einmal.
        </div>
      `
    );
  }

  answerBox.scrollTop =
    answerBox.scrollHeight;
}

/* =========================================================
   PREMIUM
========================================================= */

function renderPremium() {
  const singlePrice =
    Number(
      state.pricing.singleLessonPriceEur || 5
    );

  const monthlyPrice =
    Number(
      state.pricing.premiumMonthlyPriceEur || 15
    );

  setView(`
    <section class="screen grid two">

      <div>

        <p class="eyebrow">
          Weiterlernen
        </p>

        <h2>
          Alle Lektionen freischalten.
        </h2>

        <p>
          Einzelne Premium-Lektion für
          ${singlePrice} EUR oder Premium für
          ${monthlyPrice} EUR im Monat.
        </p>

        <a
          class="secondary-button"
          href="#/learn"
        >
          Zurück zum Kurs
        </a>

      </div>

      <div class="panel premium-panel">

        <h3>Premium</h3>

        <div class="price">
          ${monthlyPrice} EUR
          <span>/ Monat</span>
        </div>

        <p>
          Alle aktuellen und späteren
          Scratch-Lektionen, mehr KI-Hilfe
          und Belohnungen.
        </p>

        <button
          id="upgradePremium"
          class="primary-button"
          type="button"
        >
          Jetzt auf Premium upgraden
        </button>

        <p
          id="premiumMessage"
          class="muted"
        >
          ${
            state.pricing.checkoutReady
              ? "Stripe ist konfiguriert."
              : "Stripe Checkout ist noch nicht vollständig konfiguriert."
          }
        </p>

      </div>

    </section>
  `);

  document
    .querySelector("#upgradePremium")
    .addEventListener(
      "click",
      async () => {
        const message =
          document.querySelector(
            "#premiumMessage"
          );

        try {
          await api(
            "/api/checkout/premium",
            {
              method: "POST",
              body: "{}"
            }
          );

          message.textContent =
            "Checkout wurde gestartet.";
        } catch (error) {
          message.textContent =
            error?.message ||
            "Checkout konnte nicht gestartet werden.";
        }
      }
    );
}

/* =========================================================
   GESPERRTE LEKTION
========================================================= */

function renderLockedLesson(id) {
  const { lesson } =
    lessonById(id);

  if (!lesson) {
    setView(`
      <section class="screen">
        <h2>
          Lektion nicht gefunden
        </h2>
      </section>
    `);

    return;
  }

  const singlePrice =
    Number(
      lesson.price_eur ||
      state.pricing.singleLessonPriceEur ||
      5
    );

  const monthlyPrice =
    Number(
      state.pricing.premiumMonthlyPriceEur ||
      15
    );

  setView(`
    <section class="screen grid two">

      <div>

        <a
          class="secondary-button back-button"
          href="#/learn"
        >
          Zurück zum Kurs
        </a>

        <p class="eyebrow">
          Premium-Lektion
        </p>

        <h2>
          ${escapeHtml(lesson.title)}
        </h2>

        <p>
          ${escapeHtml(lesson.summary || "")}
        </p>

      </div>

      <div class="panel premium-panel">

        <h3>
          Freischalten
        </h3>

        <div class="price">
          ${singlePrice} EUR
          <span>einmalig</span>
        </div>

        <p>
          Nur diese Lektion dauerhaft freischalten.
        </p>

        <button
          id="buyLesson"
          class="secondary-button"
          type="button"
        >
          Diese Lektion kaufen
        </button>

        <hr>

        <div class="price">
          ${monthlyPrice} EUR
          <span>/ Monat</span>
        </div>

        <p>
          Alle Lektionen und spätere
          Premium-Inhalte freischalten.
        </p>

        <a
          class="primary-button"
          href="#/premium"
        >
          Jetzt auf Premium upgraden
        </a>

        <p
          id="purchaseMessage"
          class="muted"
        ></p>

      </div>

    </section>
  `);

  document
    .querySelector("#buyLesson")
    .addEventListener(
      "click",
      async () => {
        const message =
          document.querySelector(
            "#purchaseMessage"
          );

        try {
          await api(
            "/api/checkout/lesson",
            {
              method: "POST",
              body: JSON.stringify({
                lessonId: lesson.id
              })
            }
          );

          message.textContent =
            "Checkout wurde gestartet.";
        } catch (error) {
          message.textContent =
            error?.message ||
            "Kauf konnte nicht gestartet werden.";
        }
      }
    );
}

/* =========================================================
   PROJEKTE
========================================================= */

async function renderProjects() {
  if (!state.user) {
    location.hash = "#/login";
    return;
  }

  try {
    state.projects =
      await api("/api/projects");
  } catch (error) {
    console.error(
      "Projekte konnten nicht geladen werden:",
      error
    );

    state.projects = {
      own: [],
      public: []
    };
  }

  setView(`
    <section class="screen">

      <div class="screen-header">

        <div>

          <p class="eyebrow">
            Deine Werkstatt
          </p>

          <h2>
            Scratch-Projekte
          </h2>

          <p>
            Speichere Ideen, veröffentliche später
            ausgewählte Projekte und prüfe
            .sb3-Dateien sicher.
          </p>

        </div>

      </div>

      <div class="grid two">

        <form
          id="projectForm"
          class="panel"
        >

          <h3>
            Projekt speichern
          </h3>

          <label>
            Titel
            <input
              name="title"
              required
              minlength="3"
            >
          </label>

          <label>
            Beschreibung
            <textarea
              name="description"
            ></textarea>
          </label>

          <label>
            Scratch-Link
            <input
              name="scratchUrl"
              placeholder="https://scratch.mit.edu/projects/..."
            >
          </label>

          <label class="inline-label">
            <input
              name="isPublic"
              type="checkbox"
            >
            Öffentlich sichtbar machen
          </label>

          <button
            class="primary-button"
            type="submit"
          >
            Speichern
          </button>

          <p
            id="projectError"
            class="error"
          ></p>

        </form>

        <form
          id="checkForm"
          class="panel"
        >

          <h3>
            .sb3 prüfen
          </h3>

          <label>
            Lektion

            <select name="lessonId">

              ${allLessons()
                .map(lesson => `
                  <option
                    value="${escapeHtml(lesson.id)}"
                  >
                    ${escapeHtml(lesson.title)}
                  </option>
                `)
                .join("")}

            </select>

          </label>

          <label>
            Scratch-Datei

            <input
              name="sb3"
              type="file"
              accept=".sb3"
              required
            >
          </label>

          <button
            class="secondary-button"
            type="submit"
          >
            Projekt prüfen
          </button>

          <div
            id="checkResult"
            class="check-result"
          ></div>

        </form>

      </div>

      <div
        class="project-list"
        style="margin-top:16px"
      >

        ${
          Array.isArray(state.projects.own) &&
          state.projects.own.length
            ? state.projects.own
                .map(projectCard)
                .join("")
            : `
              <div class="panel">
                <p class="muted">
                  Dein erstes Projekt wartet.
                </p>
              </div>
            `
        }

      </div>

    </section>
  `);

  document
    .querySelector("#projectForm")
    .addEventListener(
      "submit",
      saveProject
    );

  document
    .querySelector("#checkForm")
    .addEventListener(
      "submit",
      checkProject
    );
}

/* =========================================================
   PROJEKT SPEICHERN
========================================================= */

async function saveProject(event) {
  event.preventDefault();

  const form =
    new FormData(
      event.currentTarget
    );

  try {
    await api(
      "/api/projects",
      {
        method: "POST",
        body: JSON.stringify({
          title: form.get("title"),
          description:
            form.get("description"),
          scratchUrl:
            form.get("scratchUrl"),
          isPublic:
            form.get("isPublic") === "on"
        })
      }
    );

    await renderProjects();

  } catch (error) {
    const box =
      document.querySelector(
        "#projectError"
      );

    if (box) {
      box.textContent =
        error?.message ||
        "Deine Änderungen konnten nicht gespeichert werden.";
    }
  }
}

/* =========================================================
   SB3 PRÜFUNG
========================================================= */

async function checkProject(event) {
  event.preventDefault();

  const form =
    new FormData(
      event.currentTarget
    );

  const file =
    form.get("sb3");

  const resultBox =
    document.querySelector(
      "#checkResult"
    );

  if (
    !file ||
    !(file instanceof File) ||
    !file.name.toLowerCase().endsWith(".sb3")
  ) {
    resultBox.textContent =
      "Bitte wähle eine .sb3-Datei aus.";

    return;
  }

  resultBox.textContent =
    "Prüfung läuft...";

  try {
    const dataBase64 =
      await fileToBase64(file);

    const result =
      await api(
        "/api/projects/check",
        {
          method: "POST",
          body: JSON.stringify({
            lessonId:
              form.get("lessonId"),
            dataBase64
          })
        }
      );

    const check =
      result?.result || {};

    const details =
      Array.isArray(check.details)
        ? check.details
        : [];

    resultBox.innerHTML = `
      <p class="success">
        ${escapeHtml(
          check.feedback ||
          "Prüfung abgeschlossen."
        )}
      </p>

      ${details
        .map(item => `
          <p>
            ${
              item.passed
                ? "OK"
                : "Fehlt"
            }:

            ${escapeHtml(
              item.message || ""
            )}
          </p>
        `)
        .join("")}
    `;

  } catch (error) {
    console.error(
      "SB3-Prüfung:",
      error
    );

    resultBox.textContent =
      error?.message ||
      "Dein Projekt konnte noch nicht geprüft werden.";
  }
}

function fileToBase64(file) {
  return new Promise(
    (resolve, reject) => {
      const reader =
        new FileReader();

      reader.onload = () => {
        const result =
          String(reader.result || "");

        resolve(
          result.includes(",")
            ? result.split(",")[1]
            : result
        );
      };

      reader.onerror =
        () =>
          reject(
            new Error(
              "Datei konnte nicht gelesen werden."
            )
          );

      reader.readAsDataURL(file);
    }
  );
}

/* =========================================================
   PROJEKT CARD
========================================================= */

function projectCard(project) {
  return `
    <article class="project-card">

      <h3>
        ${escapeHtml(project.title)}
      </h3>

      <p>
        ${escapeHtml(
          project.description ||
          "Keine Beschreibung"
        )}
      </p>

      ${
        project.scratch_url
          ? `
            <a
              class="secondary-button"
              href="${escapeHtml(
                project.scratch_url
              )}"
              target="_blank"
              rel="noopener noreferrer"
            >
              Scratch öffnen
            </a>
          `
          : ""
      }

      ${
        project.is_public
          ? `
            <span class="pill">
              Öffentlich
            </span>
          `
          : `
            <span class="pill">
              Privat
            </span>
          `
      }

    </article>
  `;
}

/* =========================================================
   ROUTER
========================================================= */

async function router() {
  await refresh();

  const cleanHash =
    location.hash
      .replace(/^#\/?/, "");

  const parts =
    cleanHash
      .split("/")
      .filter(Boolean);

  const route =
    parts[0] || "";

  const id =
    parts.length > 1
      ? decodeURIComponent(parts.slice(1).join("/"))
      : null;

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

    default:
      renderLanding();
      break;
  }
}

/* =========================================================
   LOGIN / LOGOUT BUTTON
========================================================= */

if (authAction) {
  authAction.addEventListener(
    "click",
    async event => {
      event.preventDefault();

      if (state.user) {
        try {
          await api(
            "/api/auth/logout",
            {
              method: "POST",
              body: "{}"
            }
          );
        } catch (error) {
          console.error(
            "Logout-Fehler:",
            error
          );
        }

        state.user = null;

        location.hash = "#/";
        await router();

      } else {
        location.hash = "#/login";
      }
    }
  );
}

/* =========================================================
   START
========================================================= */

window.addEventListener(
  "hashchange",
  () => {
    router().catch(error => {
      console.error(
        "Router-Fehler:",
        error
      );

      setView(`
        <section class="screen">

          <h2>
            ScratchLab braucht kurz Hilfe
          </h2>

          <p class="error">
            ${escapeHtml(
              error?.message ||
              "Unbekannter Fehler"
            )}
          </p>

          <a
            class="secondary-button"
            href="#/"
          >
            Zur Startseite
          </a>

        </section>
      `);
    });
  }
);

router().catch(error => {
  console.error(
    "Startfehler:",
    error
  );

  setView(`
    <section class="screen">

      <h2>
        ScratchLab braucht kurz Hilfe
      </h2>

      <p class="error">
        ${escapeHtml(
          error?.message ||
          "Unbekannter Fehler"
        )}
      </p>

    </section>
  `);
});