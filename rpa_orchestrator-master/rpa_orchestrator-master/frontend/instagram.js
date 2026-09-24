const API = "/api/v1";

const state = {
    executionId: null,
    timer: null,
    catalog: null,
    events: [],
    afterSequence: 0,
    controller: null,
    creating: false,
    selectedTaskTypes: new Set(),
    selectedAccountIds: new Set(),
    adminAccounts: [],
    provisioning: false,
    historyCursor: null,
    currentExecution: null,
    currentResult: null,
    resultPage: 0,
    creationUncertain: false,
};

const esc = (value) =>
    String(value ?? "").replace(
        /[&<>\"']/g,
        (c) =>
            ({
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                "\"": "&quot;",
                "'": "&#39;",
            })[c]
    );

const api = async (path, options = {}) => {
    const response = await fetch(API + path, {
        credentials: "same-origin",
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {}),
        },
        ...options,
    });

    const text = await response.text();
    let data = null;

    try {
        data = text ? JSON.parse(text) : null;
    } catch {
        data = { detail: text };
    }

    if (!response.ok) {
        const detail = data?.detail || data?.error || (data && typeof data === "object" ? JSON.stringify(data) : null);
        const error = new Error(detail || `HTTP ${response.status}`);
        error.status = response.status;
        error.payload = data;
        throw error;
    }

    return data;
};


/* =========================================================
   NOMBRES AMIGABLES DE LAS TAREAS
   ========================================================= */

const TASK_LABELS = {
    1: "Interactuar con el último post del owner",
    2: "Revisar notificaciones",
    3: "Interactuar con seguidores de Instagram",
    4: "Compartir / publicar historia",
    5: "Compartir / publicar post",
    6: "Followback de Instagram",
    7: "Interactuar con posts donde etiquetaron al owner",
    8: "Interactuar con posts propios",
    9: "Interactuar con mensajes no leídos",
    10: "Descubrir prospectos",
    11: "Comentar prospectos",
    12: "Monitorear respuestas de prospectos",
    13: "Compartir / publicar post de followback",
    14: "Compartir / publicar contenido curado",
    15: "Contenido de campaña / servicio",
    16: "Prospecto sin respuesta",
};

function getTaskLabel(task) {
    return (
        TASK_LABELS[Number(task.id)] ||
        task.descripcion ||
        task.task_name ||
        `Tarea ${task.id}`
    );
}


/* =========================================================
   ESTILOS
   ========================================================= */

function ensureStyles() {
    // Los estilos de Instagram viven en frontend/styles.css, junto al sistema visual existente.
}

/* =========================================================
   MONTAJE DE LA PESTAÑA
   ========================================================= */

function mount() {
    ensureStyles();

    const tabs = document.querySelector(".workspace-tabs");
    const views = document.querySelector("main.shell");

    if (!tabs || !views) return;

    let tab = tabs.querySelector('.workspace-tab[data-view="instagram"]');
    if (!tab) {
        tab = document.createElement("button");
        tab.className = "workspace-tab";
        tab.dataset.view = "instagram";
        tab.textContent = "Instagram";
        tabs.appendChild(tab);
    }

    let section = document.getElementById("view-instagram");
    if (!section) {
        section = document.createElement("div");
        section.id = "view-instagram";
        section.className = "workspace-view";
        views.appendChild(section);
    }
    if (section.dataset.instagramMounted === "1") return;
    section.dataset.instagramMounted = "1";

    section.innerHTML = `
        <div class="ig-grid">

            <section class="card ig-card">

                <div class="panel-head">
                    <h2>Instagram · Nueva ejecución</h2>
                </div>

                <!-- OPERACIÓN -->

                <div class="ig-field">
                    <label for="ig-capability">Operación</label>

                    <select id="ig-capability">
                        <option value="instagram.maduracion">
                            Maduración
                        </option>

                        <option value="instagram.prospecting">
                            Prospección
                        </option>
                    </select>
                </div>


                <!-- TIPOS DE TAREA -->

                <div class="ig-field">

                    <label id="ig-task-types-label">
                        Tipos de tarea
                    </label>

                    <div
                        id="ig-task-multiselect"
                        class="ig-multiselect"
                    >

                        <button
                            id="ig-task-trigger"
                            class="ig-multiselect-trigger"
                            type="button"
                            aria-haspopup="true"
                            aria-expanded="false"
                        >
                            <span
                                id="ig-task-value"
                                class="ig-multiselect-value"
                            >
                                Selecciona una o varias tareas
                            </span>

                            <span class="ig-multiselect-arrow">
                                ▼
                            </span>
                        </button>

                        <div
                            id="ig-task-menu"
                            class="ig-multiselect-menu"
                        >

                            <div class="ig-task-search-wrap">
                                <input
                                    id="ig-task-search"
                                    class="ig-task-search"
                                    type="search"
                                    placeholder="Buscar tarea..."
                                    autocomplete="off"
                                >
                            </div>

                            <div
                                id="ig-task-types"
                                class="ig-task-options"
                                role="group"
                                aria-labelledby="ig-task-types-label"
                            >
                                <div class="ig-task-empty">
                                    Cargando catálogo…
                                </div>
                            </div>

                        </div>

                    </div>

                    <div
                        id="ig-task-summary"
                        class="ig-selected-summary"
                    ></div>

                </div>


                <!-- DESTINO -->

                <div class="ig-field">

                    <label for="ig-target-mode">
                        Destino
                    </label>

                    <select id="ig-target-mode">

                        <option value="accounts">
                            Cuentas seleccionadas
                        </option>

                        <option value="owner">
                            Propietario
                        </option>

                        <option value="all">
                            Todas las cuentas Instagram
                        </option>

                    </select>

                </div>


                <!-- CUENTAS -->

                <div
                    class="ig-field"
                    id="ig-accounts-field"
                >

                    <label id="ig-accounts-label">
                        Cuentas Instagram
                    </label>

                    <div
                        id="ig-account-multiselect"
                        class="ig-multiselect"
                    >
                        <button
                            id="ig-account-trigger"
                            class="ig-multiselect-trigger"
                            type="button"
                            aria-haspopup="true"
                            aria-expanded="false"
                        >
                            <span
                                id="ig-account-value"
                                class="ig-multiselect-value"
                            >
                                Selecciona una o varias cuentas
                            </span>

                            <span class="ig-multiselect-arrow">
                                ▼
                            </span>
                        </button>

                        <div
                            id="ig-account-menu"
                            class="ig-multiselect-menu"
                        >
                            <div class="ig-task-search-wrap">
                                <input
                                    id="ig-account-search"
                                    class="ig-task-search"
                                    type="search"
                                    placeholder="Buscar cuenta..."
                                    autocomplete="off"
                                >
                            </div>

                            <div
                                id="ig-accounts"
                                class="ig-task-options"
                                role="group"
                                aria-labelledby="ig-accounts-label"
                            >
                                <div class="ig-task-empty">
                                    Cargando catálogo…
                                </div>
                            </div>
                        </div>
                    </div>

                    <div
                        id="ig-account-summary"
                        class="ig-selected-summary"
                    ></div>

                </div>


                <!-- OWNER -->

                <div
                    class="ig-field"
                    id="ig-owner-field"
                    hidden
                >

                    <label for="ig-owner">
                        Propietario
                    </label>

                    <select id="ig-owner"></select>

                </div>


                <!-- PROGRAMACIÓN -->

                <div class="ig-field">

                    <label for="ig-schedule">
                        Inicio programado (opcional)
                    </label>

                    <input
                        id="ig-schedule"
                        type="datetime-local"
                    >

                </div>


                <!-- CUSTOM TASK -->

                <div class="ig-field">

                    <label for="ig-custom">
                        Tarea personalizada (JSON opcional)
                    </label>

                    <textarea
                        id="ig-custom"
                        rows="3"
                        placeholder='{"campaign_id":10,"post":"texto opcional","links_image":["https://..."]}'
                    ></textarea>

                </div>


                <!-- AVANZADO -->

                <details class="ig-field">

                    <summary>
                        Opciones avanzadas
                    </summary>

                    <label for="ig-executor">
                        Bot executor (opcional)
                    </label>

                    <input
                        id="ig-executor"
                        placeholder="Se resuelve en el backend si se deja vacío"
                    >

                    <label for="ig-max-accounts">
                        Máximo de cuentas procesadas en esta ejecución (opcional)
                    </label>
                    <input
                        id="ig-max-accounts"
                        type="number"
                        min="1"
                        step="1"
                        placeholder="50"
                    >

                </details>


                <!-- CREAR -->

                <div class="ig-row">

                    <button
                        id="ig-run"
                        class="button primary"
                    >
                        Crear ejecución
                    </button>

                    <span
                        id="ig-create-message"
                        class="ig-muted"
                        aria-live="polite"
                    ></span>

                </div>

            </section>


            <!-- SEGUIMIENTO -->

            <section class="card ig-card">

                <div class="panel-head">

                    <h2>
                        Seguimiento
                    </h2>

                    <button
                        id="ig-cancel"
                        class="button danger"
                        hidden
                        disabled
                    >
                        Cancelar
                    </button>

                </div>

                <div
                    id="ig-current"
                    class="ig-muted"
                    aria-live="polite"
                >
                    No hay ejecución seleccionada.
                </div>

                <div
                    id="ig-events"
                    class="ig-events"
                ></div>

                <div class="panel-head">
                    <h2>
                        Resultado
                    </h2>
                </div>

                <div
                    id="ig-task-table"
                    class="table-wrap"
                ></div>

                <pre
                    id="ig-result"
                    class="ig-result"
                >Sin resultado.</pre>

            </section>

        </div>


        <!-- ADMINISTRACIÓN DE CUENTAS -->

        <section class="card ig-card" id="ig-admin-card">
            <div class="panel-head">
                <div>
                    <h2>Administración de cuentas Instagram</h2>
                    <div class="ig-muted">Provisionamiento completo: personalidad → owner → proxy opcional → cuenta → campaña → asignación.</div>
                </div>
                <button id="ig-admin-refresh" class="button secondary" type="button">Recargar</button>
            </div>

            <details class="ig-step" open>
                <summary>Crear cuenta lista para prospectar</summary>

                <details class="ig-step" open>
                    <summary>1. Personalidad</summary>
                    <div class="ig-admin-grid">
                        <div class="ig-field"><label>Nombre</label><input id="ig-p-name"></div>
                        <div class="ig-field"><label>Ubicación</label><input id="ig-p-location"></div>
                        <div class="ig-field"><label>Idioma</label><input id="ig-p-language" value="ESPAÑOL"></div>
                        <div class="ig-field"><label>Estilo de comunicación</label><input id="ig-p-style"></div>
                        <div class="ig-field full"><label>Bio</label><textarea id="ig-p-bio" rows="2"></textarea></div>
                        <div class="ig-field"><label>Valores</label><textarea id="ig-p-values" rows="2"></textarea></div>
                        <div class="ig-field"><label>Preferencias</label><textarea id="ig-p-preferences" rows="2"></textarea></div>
                        <div class="ig-field"><label>Dislikes</label><textarea id="ig-p-dislikes" rows="2"></textarea></div>
                        <div class="ig-field"><label>Respuestas de ejemplo</label><textarea id="ig-p-examples" rows="2"></textarea></div>
                        <div class="ig-field"><label>Conocimiento especial</label><textarea id="ig-p-knowledge" rows="2"></textarea></div>
                        <div class="ig-field"><label>Referencias culturales</label><textarea id="ig-p-cultural" rows="2"></textarea></div>
                        <div class="ig-field"><label>Fraseología</label><textarea id="ig-p-phraseology" rows="2"></textarea></div>
                        <div class="ig-field"><label>Interacciones pasadas</label><textarea id="ig-p-past" rows="2"></textarea></div>
                        <div class="ig-field"><label>Reacciones emocionales</label><textarea id="ig-p-emotional" rows="2"></textarea></div>
                        <div class="ig-field"><label>Objetivos</label><textarea id="ig-p-objectives" rows="2"></textarea></div>
                        <div class="ig-field"><label>Tendencias de comportamiento</label><textarea id="ig-p-behavior" rows="2"></textarea></div>
                    </div>
                </details>

                <details class="ig-step" open>
                    <summary>2. Owner</summary>
                    <div class="ig-admin-grid">
                        <div class="ig-field"><label>Nombre *</label><input id="ig-o-name" required></div>
                        <div class="ig-field"><label>Email *</label><input id="ig-o-email" type="email" required></div>
                        <div class="ig-field"><label>Teléfono *</label><input id="ig-o-phone" required></div>
                        <div class="ig-field"><label>URLs (JSON)</label><textarea id="ig-o-urls" rows="2">[]</textarea></div>
                        <div class="ig-field full"><label>Servicios (JSON)</label><textarea id="ig-o-services" rows="2">[]</textarea></div>
                    </div>
                </details>

                <details class="ig-step">
                    <summary>3. Proxy (opcional)</summary>
                    <div class="ig-admin-grid">
                        <div class="ig-field"><label>IP</label><input id="ig-x-ip"></div>
                        <div class="ig-field"><label>Puerto</label><input id="ig-x-port" type="number" min="1"></div>
                        <div class="ig-field"><label>Usuario</label><input id="ig-x-user"></div>
                        <div class="ig-field"><label>Contraseña</label><input id="ig-x-password" type="password"></div>
                    </div>
                </details>

                <details class="ig-step" open>
                    <summary>4. Cuenta Instagram</summary>
                    <div class="ig-admin-grid">
                        <div class="ig-field"><label>Usuario / account_name *</label><input id="ig-a-name" required></div>
                        <div class="ig-field"><label>Tipo</label><select id="ig-a-kind"><option value="business">Business</option><option value="personal">Personal</option></select></div>
                        <div class="ig-field full"><label>Group (JSON) *</label><textarea id="ig-a-group" rows="2">["grupo_1"]</textarea></div>
                        <div class="ig-field"><label>Usuario credencial *</label><input id="ig-a-user" required></div>
                        <div class="ig-field"><label>Contraseña *</label><input id="ig-a-password" type="password" required></div>
                        <div class="ig-field full"><label>Cookies (JSON array)</label><textarea id="ig-a-cookie" rows="3">[]</textarea></div>
                    </div>
                </details>

                <details class="ig-step" open>
                    <summary>5. Campaña de prospección</summary>
                    <div class="ig-admin-grid">
                        <div class="ig-field"><label>Nombre *</label><input id="ig-c-name" required></div>
                        <div class="ig-field"><label>Estado</label><select id="ig-c-status"><option value="active">Active</option><option value="draft">Draft</option><option value="paused">Paused</option><option value="completed">Completed</option><option value="cancelled">Cancelled</option></select></div>
                        <div class="ig-field full"><label>Servicios snapshot (JSON)</label><textarea id="ig-c-services" rows="2">[]</textarea></div>
                        <div class="ig-field full"><label>Estrategia snapshot (JSON)</label><textarea id="ig-c-strategy" rows="3">{}</textarea></div>
                        <div class="ig-field full"><label>Descripción del negocio</label><textarea id="ig-c-description" rows="2"></textarea></div>
                        <div class="ig-field"><label>Horario</label><input id="ig-c-hours"></div>
                        <div class="ig-field"><label>Teléfono seguimiento</label><input id="ig-c-phone"></div>
                        <div class="ig-field"><label>Email seguimiento</label><input id="ig-c-email" type="email"></div>
                        <div class="ig-field"><label>Instagram del owner</label><input id="ig-c-owner-url"></div>
                    </div>
                </details>

                <details class="ig-step" open>
                    <summary>6. Asignación cuenta ↔ campaña</summary>
                    <div class="ig-admin-grid">
                        <div class="ig-field"><label for="ig-as-daily">Prospectos por día (opcional)</label><input id="ig-as-daily" type="number" min="1" placeholder="Vacío = sin límite configurado"><small>Control anti-spam por cuenta. Puede dejarse vacío.</small></div>
                        <div class="ig-field"><label for="ig-as-total">Prospectos históricos (opcional)</label><input id="ig-as-total" type="number" min="1" placeholder="Vacío = sin límite configurado"><small>Máximo histórico de prospectos identificados por esta cuenta/campaña. Puede dejarse vacío.</small></div>
                        <div class="ig-field"><label>Activa</label><select id="ig-as-active"><option value="true">Sí</option><option value="false">No</option></select></div>
                    </div>
                </details>

                <div class="ig-row">
                    <button id="ig-provision" class="button primary" type="button">Crear y verificar cuenta</button>
                    <span id="ig-admin-message" class="ig-admin-message ig-muted" aria-live="polite"></span>
                </div>
            </details>

            <details class="ig-step">
                <summary>Administración avanzada de recursos</summary>
                <div class="ig-muted">CRUD directo sobre personalidad, owner, proxy, cuenta, campaña y asignación. Para crear o editar, usa JSON válido.</div>
                <div class="ig-admin-grid">
                    <div class="ig-field"><label for="ig-resource-kind">Recurso</label><select id="ig-resource-kind">
                        <option value="personalities">Personalidades</option>
                        <option value="owners">Owners</option>
                        <option value="proxies">Proxies</option>
                        <option value="accounts">Cuentas</option>
                        <option value="campaigns">Campañas</option>
                        <option value="assignments">Asignaciones</option>
                    </select></div>
                    <div class="ig-field"><label for="ig-resource-id">ID (obligatorio para obtener, editar o eliminar)</label><input id="ig-resource-id" type="number" min="1"></div>
                    <div class="ig-field full"><label for="ig-resource-json">JSON para crear / PATCH</label><textarea id="ig-resource-json" rows="8">{}</textarea></div>
                </div>
                <div class="ig-row">
                    <button id="ig-resource-list" class="button secondary" type="button">Listar</button>
                    <button id="ig-resource-get" class="button secondary" type="button">Obtener</button>
                    <button id="ig-resource-create" class="button primary" type="button">Crear</button>
                    <button id="ig-resource-patch" class="button secondary" type="button">Editar (PATCH)</button>
                    <button id="ig-resource-delete" class="button danger" type="button">Eliminar</button>
                </div>
                <pre id="ig-resource-output" class="ig-result" aria-live="polite">Sin operación.</pre>
            </details>

            <div class="panel-head"><h2>Cuentas registradas</h2></div>
            <div class="table-wrap">
                <table class="ig-table">
                    <thead><tr><th>ID</th><th>Cuenta</th><th>Tipo</th><th>Owner</th><th>Acciones</th></tr></thead>
                    <tbody id="ig-admin-accounts"><tr><td colspan="5">Cargando…</td></tr></tbody>
                </table>
            </div>
        </section>


        <!-- HISTORIAL -->

        <section class="card ig-card">

            <div class="panel-head">

                <h2>
                    Historial Instagram
                </h2>

                <button
                    id="ig-refresh-history"
                    class="button secondary"
                >
                    Recargar
                </button>

            </div>

            <div class="table-wrap">

                <table class="ig-table">

                    <thead>
                        <tr>
                            <th>Execution</th>
                            <th>Capability</th>
                            <th>Estado</th>
                            <th>Creada</th>
                            <th>Acciones</th>
                        </tr>
                    </thead>

                    <tbody id="ig-history"></tbody>

                </table>

            </div>
            <div class="ig-row">
                <button id="ig-history-more" class="button secondary" type="button" hidden>Cargar más</button>
            </div>

        </section>
    `;

    // Accessibility: every native form control gets an associated label and
    // an aria-describedby target. This also covers the provisioning wizard.
    section.querySelectorAll("input[id], select[id], textarea[id]").forEach((control) => {
        let label = section.querySelector(`label[for="${control.id}"]`);
        if (!label) {
            const wrapper = control.closest(".ig-field");
            label = wrapper?.querySelector("label");
            if (label) label.htmlFor = control.id;
        }
        const describedBy = control.getAttribute("aria-describedby");
        if (!describedBy) {
            const hint = document.createElement("span");
            hint.id = `${control.id}-help`;
            hint.className = "ig-field-help";
            hint.textContent = "";
            control.insertAdjacentElement("afterend", hint);
            control.setAttribute("aria-describedby", hint.id);
        }
        const globalMessageId = control.closest("#ig-admin-card") ? "ig-admin-message" : "ig-create-message";
        const ids = new Set((control.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean));
        ids.add(globalMessageId);
        control.setAttribute("aria-describedby", [...ids].join(" "));
    });

    document.getElementById("ig-events").setAttribute("aria-live", "polite");
    document.getElementById("ig-result").setAttribute("aria-live", "polite");

    tab.addEventListener("click", activate);

    document
        .getElementById("ig-target-mode")
        .addEventListener("change", updateTargetFields);

    document
        .getElementById("ig-capability")
        .addEventListener("change", handleOperationChange);

    document
        .getElementById("ig-task-trigger")
        .addEventListener("click", toggleTaskDropdown);

    document
        .getElementById("ig-task-search")
        .addEventListener("input", renderTaskTypes);

    document
        .getElementById("ig-account-trigger")
        .addEventListener("click", toggleAccountDropdown);

    document
        .getElementById("ig-account-search")
        .addEventListener("input", renderAccounts);

    document
        .getElementById("ig-run")
        .addEventListener("click", createExecution);

    document
        .getElementById("ig-cancel")
        .addEventListener("click", cancelExecution);

    document
        .getElementById("ig-refresh-history")
        .addEventListener("click", () => loadHistory(false));

    document
        .getElementById("ig-history-more")
        .addEventListener("click", () => loadHistory(true));

    document
        .getElementById("ig-provision")
        .addEventListener("click", provisionInstagramAccount);

    document
        .getElementById("ig-admin-refresh")
        .addEventListener("click", loadAdminAccounts);

    document.getElementById("ig-resource-list").addEventListener("click", () => manageInstagramResource("list"));
    document.getElementById("ig-resource-get").addEventListener("click", () => manageInstagramResource("get"));
    document.getElementById("ig-resource-create").addEventListener("click", () => manageInstagramResource("create"));
    document.getElementById("ig-resource-patch").addEventListener("click", () => manageInstagramResource("patch"));
    document.getElementById("ig-resource-delete").addEventListener("click", () => manageInstagramResource("delete"));

    document.addEventListener("click", handleOutsideTaskDropdown);
    document.addEventListener("click", handleOutsideAccountDropdown);
    document.addEventListener("click", (event) => {
        const workspaceTab = event.target.closest?.(".workspace-tab");
        if (workspaceTab && workspaceTab.dataset.view !== "instagram") {
            stopInstagramPolling();
        }
    });

    updateTargetFields();
    loadCatalog();
    loadAdminAccounts();

    const existing =
        new URLSearchParams(location.search).get("execution_id");

    const requestedView = new URLSearchParams(location.search).get("view");
    if (requestedView === "instagram" || (existing && /^[0-9a-f-]{36}$/i.test(existing))) {
        activate();
    }
    if (existing && /^[0-9a-f-]{36}$/i.test(existing)) {
        startPolling(existing);
    }
}


/* =========================================================
   ACTIVAR PESTAÑA
   ========================================================= */

function stopInstagramPolling() {
    clearTimeout(state.timer);
    state.timer = null;
    state.controller?.abort();
    state.controller = null;
}

function activate() {
    const url = new URL(location.href);
    url.searchParams.set("view", "instagram");
    history.replaceState(null, "", url);

    document
        .querySelectorAll(".workspace-tab")
        .forEach((button) =>
            button.classList.toggle(
                "active",
                button.dataset.view === "instagram"
            )
        );

    document
        .querySelectorAll(".workspace-view")
        .forEach((view) =>
            view.classList.toggle(
                "active",
                view.id === "view-instagram"
            )
        );

    loadHistory();
}


/* =========================================================
   CATÁLOGO
   ========================================================= */

async function loadCatalog() {
    try {
        state.catalog = await api("/instagram/catalog");

        renderTaskTypes();

        renderAccounts();

        document.getElementById("ig-owner").innerHTML =
            `
                <option value="">
                    Seleccionar…
                </option>
            ` +
            (state.catalog.owners || [])
                .map(
                    (item) => `
                        <option value="${esc(item.id)}">
                            ${esc(
                                item.owner_name ||
                                item.id
                            )}
                        </option>
                    `
                )
                .join("");

    } catch (error) {
        document.getElementById(
            "ig-create-message"
        ).textContent =
            `Catálogo: ${error.message}`;
    }
}


/* =========================================================
   ADMINISTRACIÓN DE CUENTAS INSTAGRAM
   ========================================================= */

function adminValue(id) {
    return document.getElementById(id)?.value?.trim() || "";
}

function parseAdminJson(id, fallback) {
    const raw = adminValue(id);
    if (!raw) return fallback;
    try {
        return JSON.parse(raw);
    } catch {
        throw new Error(`JSON inválido en ${id}.`);
    }
}

function normalizeAdminList(payload) {
    if (Array.isArray(payload)) return payload;
    if (Array.isArray(payload?.results)) return payload.results;
    return [];
}

async function manageInstagramResource(action) {
    const resource = document.getElementById("ig-resource-kind").value;
    const idRaw = document.getElementById("ig-resource-id").value.trim();
    const id = idRaw ? Number(idRaw) : null;
    const output = document.getElementById("ig-resource-output");
    if (["get", "patch", "delete"].includes(action) && (!Number.isSafeInteger(id) || id <= 0)) {
        output.textContent = "Indica un ID entero positivo.";
        return;
    }

    let path = `/instagram/admin/${resource}`;
    if (id) path += `/${id}`;
    const options = {};
    if (action === "create" || action === "patch") {
        let payload;
        try {
            payload = JSON.parse(document.getElementById("ig-resource-json").value || "{}");
            if (!payload || Array.isArray(payload) || typeof payload !== "object") throw new Error();
        } catch {
            output.textContent = "El JSON debe ser un objeto válido.";
            return;
        }
        options.method = action === "create" ? "POST" : "PATCH";
        options.body = JSON.stringify(payload);
    } else if (action === "delete") {
        if (!window.confirm(`¿Eliminar ${resource} #${id}? Esta operación puede tener efectos en cascada.`)) return;
        options.method = "DELETE";
    }

    try {
        const result = await api(path, options);
        output.textContent = result == null ? "Operación completada." : safeInstagramJson(result);
        if (resource === "accounts") await Promise.all([loadAdminAccounts(), loadCatalog()]);
    } catch (error) {
        output.textContent = `Error: ${error.message}`;
    }
}

async function loadAdminAccounts() {
    const body = document.getElementById("ig-admin-accounts");
    if (!body) return;
    try {
        const payload = await api("/instagram/admin/accounts");
        state.adminAccounts = normalizeAdminList(payload);
        if (!state.adminAccounts.length) {
            body.innerHTML = '<tr><td colspan="5" class="ig-muted">No hay cuentas registradas.</td></tr>';
            return;
        }
        body.innerHTML = state.adminAccounts.map((account) => `
            <tr>
                <td>${esc(account.id)}</td>
                <td>${esc(account.account_name || "")}</td>
                <td>${esc(account.account_kind || "")}</td>
                <td>${esc(account.owner || "")}</td>
                <td>
                    <div class="ig-row">
                        <button class="button secondary ig-admin-detail" data-id="${esc(account.id)}" type="button">Detalle</button>
                        <button class="button secondary ig-admin-verify" data-id="${esc(account.id)}" type="button">Verificar</button>
                        <button class="button secondary ig-admin-cookie" data-id="${esc(account.id)}" type="button">Cookies</button>
                        <button class="button danger ig-admin-delete" data-id="${esc(account.id)}" data-name="${esc(account.account_name || account.id)}" type="button">Eliminar</button>
                    </div>
                </td>
            </tr>
        `).join("");

        body.querySelectorAll(".ig-admin-detail").forEach((button) =>
            button.addEventListener("click", () => showExpandedAdminAccount(Number(button.dataset.id)))
        );
        body.querySelectorAll(".ig-admin-verify").forEach((button) =>
            button.addEventListener("click", () => verifyAdminAccount(Number(button.dataset.id)))
        );
        body.querySelectorAll(".ig-admin-cookie").forEach((button) =>
            button.addEventListener("click", () => updateAdminCookie(Number(button.dataset.id)))
        );
        body.querySelectorAll(".ig-admin-delete").forEach((button) =>
            button.addEventListener("click", () => deleteAdminAccount(Number(button.dataset.id), button.dataset.name))
        );
    } catch (error) {
        body.innerHTML = `<tr><td colspan="5">Error: ${esc(error.message)}</td></tr>`;
    }
}

async function verifyAdminAccount(accountId) {
    const message = document.getElementById("ig-admin-message");
    try {
        const result = await api(`/instagram/admin/accounts/${accountId}/verify`);
        message.textContent = `Cuenta #${accountId} lista para prospectar. Campaña activa #${result?.campaign?.id ?? "?"}.`;
    } catch (error) {
        message.textContent = `Cuenta #${accountId} no está lista: ${error.message}`;
    }
}

async function updateAdminCookie(accountId) {
    const raw = window.prompt("Pega el array JSON de cookies:", "[]");
    if (raw === null) return;
    const message = document.getElementById("ig-admin-message");
    try {
        const cookies = JSON.parse(raw);
        if (!Array.isArray(cookies)) throw new Error("Las cookies deben ser un array JSON.");
        await api(`/instagram/admin/accounts/${accountId}/cookie`, {
            method: "PATCH",
            body: JSON.stringify(cookies),
        });
        message.textContent = `Cookies de la cuenta #${accountId} actualizadas.`;
    } catch (error) {
        message.textContent = `No se pudieron actualizar cookies: ${error.message}`;
    }
}

async function deleteAdminAccount(accountId, name) {
    if (!window.confirm(`¿Eliminar la cuenta "${name}"? Esta acción puede eliminar datos relacionados por cascada.`)) return;
    const message = document.getElementById("ig-admin-message");
    try {
        await api(`/instagram/admin/accounts/${accountId}`, { method: "DELETE" });
        state.selectedAccountIds.delete(accountId);
        message.textContent = `Cuenta #${accountId} eliminada.`;
        await Promise.all([loadAdminAccounts(), loadCatalog()]);
    } catch (error) {
        message.textContent = `No se pudo eliminar la cuenta: ${error.message}`;
    }
}

async function provisionInstagramAccount() {
    if (state.provisioning) return;
    const button = document.getElementById("ig-provision");
    const message = document.getElementById("ig-admin-message");
    const required = [
        ["ig-o-name", "Nombre del owner"],
        ["ig-o-email", "Email del owner"],
        ["ig-o-phone", "Teléfono del owner"],
        ["ig-a-name", "account_name"],
        ["ig-a-user", "Usuario credencial"],
        ["ig-a-password", "Contraseña"],
        ["ig-c-name", "Nombre de campaña"],
    ];
    for (const [id, label] of required) {
        if (!adminValue(id)) {
            message.textContent = `${label} es obligatorio.`;
            document.getElementById(id)?.focus();
            return;
        }
    }

    state.provisioning = true;
    button.disabled = true;
    const created = {};
    try {
        message.textContent = "1/7 Creando personalidad…";
        const personality = await api("/instagram/admin/personalities", {
            method: "POST",
            body: JSON.stringify({
                name: adminValue("ig-p-name") || null,
                bio: adminValue("ig-p-bio") || null,
                location: adminValue("ig-p-location") || null,
                language: adminValue("ig-p-language") || "ESPAÑOL",
                communication_style: adminValue("ig-p-style") || null,
                values: adminValue("ig-p-values") || null,
                preferences: adminValue("ig-p-preferences") || null,
                dislikes: adminValue("ig-p-dislikes") || null,
                example_responses: adminValue("ig-p-examples") || null,
                special_knowledge: adminValue("ig-p-knowledge") || null,
                cultural_references: adminValue("ig-p-cultural") || null,
                phraseology: adminValue("ig-p-phraseology") || null,
                past_interactions: adminValue("ig-p-past") || null,
                emotional_reactions: adminValue("ig-p-emotional") || null,
                objectives: adminValue("ig-p-objectives") || null,
                behavioral_tendencies: adminValue("ig-p-behavior") || null,
            }),
        });
        created.personality = personality.id;

        message.textContent = "2/7 Creando owner…";
        const owner = await api("/instagram/admin/owners", {
            method: "POST",
            body: JSON.stringify({
                owner_name: adminValue("ig-o-name"),
                owner_email: adminValue("ig-o-email"),
                owner_phone: adminValue("ig-o-phone"),
                owner_urls: parseAdminJson("ig-o-urls", []),
                services: parseAdminJson("ig-o-services", []),
            }),
        });
        created.owner = owner.id;

        let proxyId = null;
        if (adminValue("ig-x-ip") || adminValue("ig-x-port")) {
            if (!adminValue("ig-x-ip") || !adminValue("ig-x-port")) {
                throw new Error("Para usar proxy debes indicar IP y puerto.");
            }
            message.textContent = "3/7 Creando proxy…";
            const proxy = await api("/instagram/admin/proxies", {
                method: "POST",
                body: JSON.stringify({
                    ip_address: adminValue("ig-x-ip"),
                    port: Number(adminValue("ig-x-port")),
                    username: adminValue("ig-x-user") || null,
                    password: adminValue("ig-x-password") || null,
                }),
            });
            proxyId = proxy.id;
            created.proxy = proxy.id;
        }

        message.textContent = "4/7 Creando cuenta…";
        const accountPayload = {
            account_name: adminValue("ig-a-name"),
            group: parseAdminJson("ig-a-group", []),
            owner: owner.id,
            bot_personality: personality.id,
            proxy: proxyId,
            account_kind: adminValue("ig-a-kind") || "business",
            other_credentials: {
                user: adminValue("ig-a-user"),
                password: adminValue("ig-a-password"),
                cookie: parseAdminJson("ig-a-cookie", []),
            },
        };
        const account = await api("/instagram/admin/accounts", {
            method: "POST",
            body: JSON.stringify(accountPayload),
        });
        created.account = account.id;

        message.textContent = "5/7 Creando campaña…";
        const campaign = await api("/instagram/admin/campaigns", {
            method: "POST",
            body: JSON.stringify({
                social_media_account: account.id,
                name: adminValue("ig-c-name"),
                platform: "instagram",
                status: adminValue("ig-c-status") || "active",
                services_snapshot: parseAdminJson("ig-c-services", []),
                strategy_snapshot: parseAdminJson("ig-c-strategy", {}),
                business_description: adminValue("ig-c-description") || null,
                business_hours: adminValue("ig-c-hours") || null,
                follow_up_phone: adminValue("ig-c-phone") || null,
                follow_up_email: adminValue("ig-c-email") || null,
                owner_instagram_profile_url: adminValue("ig-c-owner-url") || null,
            }),
        });
        created.campaign = campaign.id;

        message.textContent = "6/7 Creando asignación…";
        const assignment = await api("/instagram/admin/assignments", {
            method: "POST",
            body: JSON.stringify({
                campaign: campaign.id,
                social_media_account: account.id,
                platform: "instagram",
                role: "prospecting",
                is_active: adminValue("ig-as-active") !== "false",
                daily_limit: adminValue("ig-as-daily") ? Number(adminValue("ig-as-daily")) : null,
                total_limit: adminValue("ig-as-total") ? Number(adminValue("ig-as-total")) : null,
            }),
        });
        created.assignment = assignment.id;

        message.textContent = "7/7 Verificando campaña activa…";
        const verification = await api(`/instagram/admin/accounts/${account.id}/verify`);
        document.getElementById("ig-a-password").value = "";
        document.getElementById("ig-x-password").value = "";
        message.textContent = `Cuenta creada correctamente. account=${account.id}, campaign=${campaign.id}, assignment=${assignment.id}. Verificación: ${verification?.ok === true ? "OK" : "sin confirmar"}.`;
        await Promise.all([loadAdminAccounts(), loadCatalog()]);
    } catch (error) {
        message.textContent = `Provisionamiento detenido: ${error.message}\nCreados hasta ahora: ${JSON.stringify(created)}`;
    } finally {
        state.provisioning = false;
        button.disabled = false;
    }
}


/* =========================================================
   OPERACIÓN -> TAREAS DEPENDIENTES
   ========================================================= */

function handleOperationChange() {
    /*
     * Una tarea seleccionada en Maduración nunca debe
     * permanecer seleccionada al cambiar a Prospección,
     * y viceversa.
     */
    state.selectedTaskTypes.clear();

    const search =
        document.getElementById("ig-task-search");

    if (search) {
        search.value = "";
    }

    renderTaskTypes();
    updateTaskSelectionLabel();
}


/* =========================================================
   DROPDOWN DE TAREAS
   ========================================================= */

function toggleTaskDropdown(event) {
    event.stopPropagation();

    const dropdown =
        document.getElementById("ig-task-multiselect");

    const trigger =
        document.getElementById("ig-task-trigger");

    const opening =
        !dropdown.classList.contains("open");

    dropdown.classList.toggle("open", opening);

    trigger.setAttribute(
        "aria-expanded",
        opening ? "true" : "false"
    );

    if (opening) {
        setTimeout(() => {
            document
                .getElementById("ig-task-search")
                ?.focus();
        }, 0);
    }
}


function handleOutsideTaskDropdown(event) {
    const dropdown =
        document.getElementById("ig-task-multiselect");

    if (
        !dropdown ||
        !dropdown.classList.contains("open")
    ) {
        return;
    }

    if (!dropdown.contains(event.target)) {
        dropdown.classList.remove("open");

        document
            .getElementById("ig-task-trigger")
            ?.setAttribute(
                "aria-expanded",
                "false"
            );
    }
}


/* =========================================================
   RENDERIZAR TAREAS SEGÚN OPERACIÓN
   ========================================================= */

function renderTaskTypes() {
    const box =
        document.getElementById("ig-task-types");

    if (
        !box ||
        !state.catalog
    ) {
        return;
    }

    const capability =
        document.getElementById(
            "ig-capability"
        ).value;

    const operation =
        capability.split(".").pop();

    const search =
        (
            document.getElementById(
                "ig-task-search"
            )?.value || ""
        )
            .trim()
            .toLowerCase();

    /*
     * FILTRO ESTRICTO.
     *
     * Maduración solo muestra task.operation === "maduracion"
     * Prospección solo muestra task.operation === "prospecting"
     *
     * No existe fallback para tareas sin categoría.
     */
    let tasks =
        (state.catalog.task_types || [])
            .filter(
                (task) =>
                    task.operation === operation
            );

    if (search) {
        tasks = tasks.filter((task) => {
            const haystack = [
                task.id,
                getTaskLabel(task),
                task.task_name,
                task.descripcion,
            ]
                .filter(Boolean)
                .join(" ")
                .toLowerCase();

            return haystack.includes(search);
        });
    }

    if (!tasks.length) {
        box.innerHTML = `
            <div class="ig-task-empty">
                ${
                    search
                        ? "No se encontraron tareas."
                        : "No hay tipos de tarea configurados para esta operación."
                }
            </div>
        `;

        updateTaskSelectionLabel();
        return;
    }

    box.innerHTML =
        tasks
            .map((task) => {
                const id = Number(task.id);

                const checked =
                    state.selectedTaskTypes.has(id)
                        ? "checked"
                        : "";

                return `
                    <label
                        class="ig-task-option"
                        data-task-id="${esc(id)}"
                    >

                        <input
                            type="checkbox"
                            value="${esc(id)}"
                            ${checked}
                        >

                        <span class="ig-task-option-content">

                            <span class="ig-task-option-name">
                                ${esc(getTaskLabel(task))}
                            </span>

                            <span class="ig-task-option-meta">
                                Tarea ${esc(id)}
                            </span>

                        </span>

                    </label>
                `;
            })
            .join("");

    box
        .querySelectorAll(
            'input[type="checkbox"]'
        )
        .forEach((checkbox) => {
            checkbox.addEventListener(
                "change",
                handleTaskSelection
            );
        });

    updateTaskSelectionLabel();
}


/* =========================================================
   SELECCIÓN DE TAREAS
   ========================================================= */

function handleTaskSelection(event) {
    const id =
        Number(event.target.value);

    if (
        !Number.isSafeInteger(id) ||
        id <= 0
    ) {
        return;
    }

    if (event.target.checked) {
        state.selectedTaskTypes.add(id);
    } else {
        state.selectedTaskTypes.delete(id);
    }

    updateTaskSelectionLabel();
}


function updateTaskSelectionLabel() {
    const value =
        document.getElementById(
            "ig-task-value"
        );

    const summary =
        document.getElementById(
            "ig-task-summary"
        );

    if (
        !value ||
        !summary
    ) {
        return;
    }

    const ids =
        [...state.selectedTaskTypes];

    if (!ids.length) {
        value.textContent =
            "Selecciona una o varias tareas";

        summary.textContent = "";

        return;
    }

    const catalog =
        state.catalog?.task_types || [];

    const selectedTasks =
        ids
            .map((id) =>
                catalog.find(
                    (task) =>
                        Number(task.id) === id
                )
            )
            .filter(Boolean);

    if (selectedTasks.length === 1) {
        value.textContent =
            getTaskLabel(
                selectedTasks[0]
            );
    } else {
        value.textContent =
            `${selectedTasks.length} tareas seleccionadas`;
    }

    summary.textContent =
        selectedTasks
            .map((task) =>
                getTaskLabel(task)
            )
            .join(", ");
}


/* =========================================================
   DROPDOWN DE CUENTAS
   ========================================================= */

function toggleAccountDropdown(event) {
    event.stopPropagation();

    const dropdown =
        document.getElementById("ig-account-multiselect");

    const trigger =
        document.getElementById("ig-account-trigger");

    const opening =
        !dropdown.classList.contains("open");

    dropdown.classList.toggle("open", opening);

    trigger.setAttribute(
        "aria-expanded",
        opening ? "true" : "false"
    );

    if (opening) {
        setTimeout(() => {
            document
                .getElementById("ig-account-search")
                ?.focus();
        }, 0);
    }
}


function handleOutsideAccountDropdown(event) {
    const dropdown =
        document.getElementById("ig-account-multiselect");

    if (
        !dropdown ||
        !dropdown.classList.contains("open")
    ) {
        return;
    }

    if (!dropdown.contains(event.target)) {
        dropdown.classList.remove("open");

        document
            .getElementById("ig-account-trigger")
            ?.setAttribute(
                "aria-expanded",
                "false"
            );
    }
}


function renderAccounts() {
    const box =
        document.getElementById("ig-accounts");

    if (
        !box ||
        !state.catalog
    ) {
        return;
    }

    const search =
        (
            document.getElementById(
                "ig-account-search"
            )?.value || ""
        )
            .trim()
            .toLowerCase();

    let accounts =
        state.catalog.accounts || [];

    if (search) {
        accounts = accounts.filter((account) => {
            const haystack = [
                account.id,
                account.account_name,
                account.owner__owner_name,
                account.owner_name,
            ]
                .filter(Boolean)
                .join(" ")
                .toLowerCase();

            return haystack.includes(search);
        });
    }

    if (!accounts.length) {
        box.innerHTML = `
            <div class="ig-task-empty">
                ${
                    search
                        ? "No se encontraron cuentas."
                        : "No hay cuentas Instagram disponibles."
                }
            </div>
        `;

        updateAccountSelectionLabel();
        return;
    }

    box.innerHTML =
        accounts
            .map((account) => {
                const id = Number(account.id);

                const checked =
                    state.selectedAccountIds.has(id)
                        ? "checked"
                        : "";

                const owner =
                    account.owner__owner_name ||
                    account.owner_name ||
                    "";

                return `
                    <label
                        class="ig-task-option"
                        data-account-id="${esc(id)}"
                    >
                        <input
                            type="checkbox"
                            value="${esc(id)}"
                            ${checked}
                        >

                        <span class="ig-task-option-content">
                            <span class="ig-task-option-name">
                                ${esc(
                                    account.account_name ||
                                    `Cuenta ${id}`
                                )}
                            </span>

                            <span class="ig-task-option-meta">
                                ID ${esc(id)}
                                ${owner ? ` · ${esc(owner)}` : ""}
                            </span>
                        </span>
                    </label>
                `;
            })
            .join("");

    box
        .querySelectorAll(
            'input[type="checkbox"]'
        )
        .forEach((checkbox) => {
            checkbox.addEventListener(
                "change",
                handleAccountSelection
            );
        });

    updateAccountSelectionLabel();
}


function handleAccountSelection(event) {
    const id =
        Number(event.target.value);

    if (
        !Number.isSafeInteger(id) ||
        id <= 0
    ) {
        return;
    }

    if (event.target.checked) {
        state.selectedAccountIds.add(id);
    } else {
        state.selectedAccountIds.delete(id);
    }

    updateAccountSelectionLabel();
}


function updateAccountSelectionLabel() {
    const value =
        document.getElementById(
            "ig-account-value"
        );

    const summary =
        document.getElementById(
            "ig-account-summary"
        );

    if (
        !value ||
        !summary
    ) {
        return;
    }

    const ids =
        [...state.selectedAccountIds];

    if (!ids.length) {
        value.textContent =
            "Selecciona una o varias cuentas";

        summary.textContent = "";
        return;
    }

    const catalog =
        state.catalog?.accounts || [];

    const selectedAccounts =
        ids
            .map((id) =>
                catalog.find(
                    (account) =>
                        Number(account.id) === id
                )
            )
            .filter(Boolean);

    if (selectedAccounts.length === 1) {
        value.textContent =
            selectedAccounts[0].account_name ||
            `Cuenta ${selectedAccounts[0].id}`;
    } else {
        value.textContent =
            `${selectedAccounts.length} cuentas seleccionadas`;
    }

    summary.textContent =
        selectedAccounts
            .map(
                (account) =>
                    account.account_name ||
                    `Cuenta ${account.id}`
            )
            .join(", ");
}


/* =========================================================
   DESTINO
   ========================================================= */

function updateTargetFields() {
    const mode =
        document.getElementById(
            "ig-target-mode"
        ).value;

    document.getElementById(
        "ig-accounts-field"
    ).hidden =
        mode !== "accounts";

    document.getElementById(
        "ig-owner-field"
    ).hidden =
        mode !== "owner";

    const accountDropdown =
        document.getElementById(
            "ig-account-multiselect"
        );

    if (
        accountDropdown &&
        mode !== "accounts"
    ) {
        accountDropdown.classList.remove("open");

        document
            .getElementById("ig-account-trigger")
            ?.setAttribute(
                "aria-expanded",
                "false"
            );
    }
}


/* =========================================================
   VALORES SELECCIONADOS
   ========================================================= */

function selectedValues(selector) {
    return [
        ...new Set(
            [
                ...document.querySelectorAll(
                    selector +
                    " input:checked"
                ),
            ]
                .map((el) =>
                    Number(el.value)
                )
                .filter(
                    (id) =>
                        Number.isSafeInteger(id) &&
                        id > 0
                )
        ),
    ];
}


/* =========================================================
   CREAR EJECUCIÓN
   ========================================================= */

async function createExecution() {
    const message =
        document.getElementById(
            "ig-create-message"
        );

    if (state.creationUncertain) {
        const retry = window.confirm(
            "La solicitud anterior terminó con una respuesta incierta y pudo haber creado una ejecución. Reintentar puede duplicarla. ¿Deseas crear otra ejecución?"
        );
        if (!retry) return;
        state.creationUncertain = false;
    }

    const mode =
        document.getElementById(
            "ig-target-mode"
        ).value;

    /*
     * Ahora las tareas vienen del estado del multiselect,
     * no de los checkboxes visibles.
     *
     * Esto permite buscar dentro del dropdown sin perder
     * tareas previamente seleccionadas.
     */
    const taskTypes =
        [...state.selectedTaskTypes]
            .filter(
                (id) =>
                    Number.isSafeInteger(id) &&
                    id > 0
            );

    if (!taskTypes.length) {
        message.textContent =
            "Selecciona al menos un tipo de tarea.";
        return;
    }

    const capability =
        document.getElementById(
            "ig-capability"
        ).value;

    const operation =
        capability.split(".").pop();

    /*
     * Validación adicional en frontend.
     * Aunque el backend también valida esto,
     * evitamos enviar una combinación incorrecta.
     */
    const allowedIds =
        new Set(
            (state.catalog?.task_types || [])
                .filter(
                    (task) =>
                        task.operation === operation
                )
                .map(
                    (task) =>
                        Number(task.id)
                )
        );

    const invalidTasks =
        taskTypes.filter(
            (id) =>
                !allowedIds.has(id)
        );

    if (invalidTasks.length) {
        message.textContent =
            "La selección contiene tareas que no pertenecen a la operación elegida.";

        return;
    }


    /* ---------------- DESTINO ---------------- */

    const targets = { mode };

    if (mode === "accounts") {
        targets.account_ids =
            [...state.selectedAccountIds]
                .filter(
                    (id) =>
                        Number.isSafeInteger(id) &&
                        id > 0
                );

        if (
            !targets.account_ids.length
        ) {
            message.textContent =
                "Selecciona al menos una cuenta.";
            return;
        }
    }

    if (mode === "owner") {
        const owner =
            document.getElementById(
                "ig-owner"
            ).value;

        if (
            !owner ||
            !Number.isSafeInteger(
                Number(owner)
            ) ||
            Number(owner) <= 0
        ) {
            message.textContent =
                "Selecciona un propietario válido.";
            return;
        }

        targets.owner_id =
            Number(owner);
    }


    /* ---------------- CUSTOM TASK ---------------- */

    let customTask = {};

    const custom =
        document.getElementById(
            "ig-custom"
        ).value.trim();

    if (custom) {
        try {
            customTask =
                JSON.parse(custom);

            if (
                !customTask ||
                Array.isArray(customTask) ||
                typeof customTask !== "object"
            ) {
                throw new Error("object required");
            }

            if (customTask.links_image !== undefined) {
                if (!Array.isArray(customTask.links_image)) {
                    throw new Error("links_image must be an array");
                }
                customTask.links_image = customTask.links_image
                    .map((value) => String(value).trim())
                    .filter(Boolean);
                for (const value of customTask.links_image) {
                    const parsed = new URL(value);
                    if (parsed.protocol !== "https:") {
                        throw new Error("links_image only accepts https URLs");
                    }
                }
            }

        } catch {
            message.textContent =
                "El JSON de tarea personalizada no es válido.";

            return;
        }
    }


    /* ---------------- OPCIONES ---------------- */

    const options = {};

    const executor =
        document.getElementById(
            "ig-executor"
        ).value.trim();

    if (executor) {
        options.bot_executor = executor;
    }

    const maxAccountsRaw = document.getElementById("ig-max-accounts").value.trim();
    if (maxAccountsRaw) {
        const maxAccounts = Number(maxAccountsRaw);
        if (!Number.isSafeInteger(maxAccounts) || maxAccounts <= 0) {
            message.textContent = "Máximo de cuentas debe ser un entero positivo.";
            return;
        }
        options.max_accounts = maxAccounts;
    }


    /* ---------------- PAYLOAD ---------------- */

    const payload = {
        schema_version:
            `${capability}.input.v1`,

        stage:
            capability ===
            "instagram.maduracion"
                ? "instagram_maduracion"
                : "instagram_prospecting",

        capability,

        task_types:
            taskTypes,

        targets,
    };

    if (
        customTask &&
        Object.keys(customTask).length
    ) {
        payload.custom_task =
            customTask;
    }

    if (
        Object.keys(options).length
    ) {
        payload.options =
            options;
    }


    /* ---------------- PROGRAMACIÓN ---------------- */

    const scheduled =
        document.getElementById(
            "ig-schedule"
        ).value;

    if (scheduled) {
        const start =
            new Date(scheduled);

        if (
            Number.isNaN(
                start.getTime()
            )
        ) {
            message.textContent =
                "La fecha programada no es válida.";

            return;
        }

        payload.schedule = {
            start_date:
                start.toISOString(),
        };
    }


    /* ---------------- TODAS LAS CUENTAS ---------------- */

    if (
        mode === "all" &&
        !window.confirm(
            "Se crearán tareas para todas las cuentas Instagram autorizadas. ¿Continuar?"
        )
    ) {
        return;
    }


    /* ---------------- CREACIÓN ---------------- */

    if (state.creating) {
        return;
    }

    state.creating = true;

    document.getElementById(
        "ig-run"
    ).disabled = true;

    try {
        message.textContent =
            "Creando…";

        const execution =
            await api(
                "/executions/standalone/instagram",
                {
                    method: "POST",
                    body:
                        JSON.stringify(
                            payload
                        ),
                }
            );

        const id =
            execution.id ||
            execution.execution_id;

        if (!id) {
            throw new Error(
                "La API no devolvió el id de ejecución"
            );
        }

        state.executionId = id;

        const createdCancel = document.getElementById("ig-cancel");
        const createdCanCancel = ["queued", "running"].includes(execution.status);
        createdCancel.hidden = !createdCanCancel;
        createdCancel.disabled = !createdCanCancel;

        message.textContent =
            `Creada: ${id}`;

        document.getElementById(
            "ig-current"
        ).textContent =
            `Execution: ${id}`;

        document.getElementById(
            "ig-events"
        ).textContent = "";

        document.getElementById(
            "ig-result"
        ).textContent =
            "Esperando resultado…";

        startPolling(id);

        await loadHistory();

    } catch (error) {
        const status = Number(error.status) || null;
        state.creationUncertain = status === null || status >= 500;
        if (status === 401) {
            message.textContent = "La sesión del operador no es válida. Autentícate nuevamente.";
        } else if (status === 403) {
            message.textContent = "El operador no tiene permisos para crear esta ejecución.";
        } else if (status === 422) {
            message.textContent = `Revisa los campos del formulario: ${error.message}`;
        } else if (status === 503) {
            message.textContent = `Servicio temporalmente no disponible: ${error.message}`;
        } else {
            message.textContent = `Error: ${error.message}`;
        }

    } finally {
        state.creating = false;

        document.getElementById(
            "ig-run"
        ).disabled = false;
    }
}


/* =========================================================
   POLLING
   ========================================================= */

function startPolling(id) {
    clearTimeout(state.timer);

    state.controller?.abort();

    state.executionId = id;
    state.events = [];
    state.afterSequence = 0;

    const controller =
        new AbortController();

    state.controller =
        controller;

    const url =
        new URL(location.href);

    url.searchParams.set(
        "execution_id",
        id
    );

    history.replaceState(
        null,
        "",
        url
    );

    const poll = async () => {
        if (
            controller.signal.aborted
        ) {
            return;
        }

        try {
            const execution =
                await api(
                    `/executions/${encodeURIComponent(id)}`,
                    {
                        signal:
                            controller.signal,
                    }
                );

            if (
                controller.signal.aborted
            ) {
                return;
            }

            renderExecution(
                execution
            );

            const cancelButton = document.getElementById("ig-cancel");
            const canCancel = ["queued", "running"].includes(execution.status);
            cancelButton.hidden = !canCancel;
            cancelButton.disabled = !canCancel;

            await loadEvents(
                id,
                controller.signal
            );

            if (
                controller.signal.aborted
            ) {
                return;
            }

            if (
                [
                    "succeeded",
                    "failed",
                    "cancelled",
                ].includes(
                    execution.status
                )
            ) {
                await loadResult(id);

                const terminalCancel = document.getElementById("ig-cancel");
                terminalCancel.disabled = true;
                terminalCancel.hidden = true;

                return;
            }

        } catch (error) {
            if (
                controller.signal.aborted
            ) {
                return;
            }

            document.getElementById(
                "ig-current"
            ).textContent =
                `Error: ${error.message}`;

            state.timer =
                setTimeout(
                    poll,
                    10000
                );

            return;
        }

        state.timer =
            setTimeout(
                poll,
                4000
            );
    };

    poll();
}


/* =========================================================
   EJECUCIÓN
   ========================================================= */

function formatInstagramDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

function instagramElapsed(execution) {
    const start = execution.started_at || execution.created_at;
    if (!start) return "—";
    const startMs = new Date(start).getTime();
    const endMs = execution.completed_at ? new Date(execution.completed_at).getTime() : Date.now();
    if (!Number.isFinite(startMs) || !Number.isFinite(endMs)) return "—";
    const seconds = Math.max(0, Math.floor((endMs - startMs) / 1000));
    const minutes = Math.floor(seconds / 60);
    return minutes ? `${minutes}m ${seconds % 60}s` : `${seconds}s`;
}

const INSTAGRAM_STATUS_TEXT = {
    pending: "Esperando capacidad del bot",
    queued: "Trabajo enviado al adaptador",
    running: "Procesando cuentas de Instagram",
    succeeded: "Ejecución finalizada",
    failed: "Ejecución fallida",
    cancelled: "Ejecución cancelada",
    cancelling: "Cancelación solicitada",
};

function renderExecution(execution) {
    state.currentExecution = execution;
    const id = execution.id || execution.execution_id || state.executionId;
    const cancel = document.getElementById("ig-cancel");
    const cancellable = ["queued", "running"].includes(execution.status);
    cancel.hidden = !cancellable;
    cancel.disabled = !cancellable;

    document.getElementById("ig-current").innerHTML = `
        <div class="ig-status">${esc(INSTAGRAM_STATUS_TEXT[execution.status] || execution.status)}</div>
        <dl class="ig-execution-detail">
            <dt>UUID</dt><dd><code>${esc(id)}</code></dd>
            <dt>Capability</dt><dd>${esc(execution.requested_capability || execution.capability || "Instagram")}</dd>
            <dt>Bot asignado</dt><dd>${esc(execution.bot_id || "—")}</dd>
            <dt>Creación</dt><dd>${esc(formatInstagramDate(execution.created_at))}</dd>
            <dt>Inicio</dt><dd>${esc(formatInstagramDate(execution.started_at))}</dd>
            <dt>Finalización</dt><dd>${esc(formatInstagramDate(execution.completed_at))}</dd>
            <dt>Tiempo transcurrido</dt><dd>${esc(instagramElapsed(execution))}</dd>
        </dl>
        ${execution.error_message ? `<div class="ig-error"><strong>Error terminal:</strong> ${esc(execution.error_message)}</div>` : ""}
    `;
}


/* =========================================================
   EVENTOS
   ========================================================= */

async function loadEvents(
    id,
    signal
) {
    try {
        const events =
            await api(
                `/executions/${encodeURIComponent(id)}/events?after_sequence=${state.afterSequence}&limit=100`,
                { signal }
            );

        if (signal.aborted) {
            return;
        }

        const fresh =
            Array.isArray(events)
                ? events
                : events.items || [];

        state.events.push(
            ...fresh
        );

        for (
            const event of fresh
        ) {
            state.afterSequence =
                Math.max(
                    state.afterSequence,
                    Number(
                        event.sequence
                    ) || 0
                );
        }

        document.getElementById(
            "ig-events"
        ).textContent =
            state.events
                .map(
                    (event) =>
                        `[${event.sequence ?? "-"}] ${event.event_type || "event"}: ${event.summary || ""}`
                )
                .join("\n");

    } catch (error) {
        if (
            error.name ===
            "AbortError"
        ) {
            return;
        }
    }
}


/* =========================================================
   RESULTADO
   ========================================================= */

function safeInstagramJson(value) {
    return JSON.stringify(
        value,
        (_key, item) => {
            if (Array.isArray(item) && item.length > 100) {
                return [...item.slice(0, 100), `… ${item.length - 100} elementos adicionales omitidos de la vista`];
            }
            return item;
        },
        2
    );
}

function renderInstagramTaskPage(payload) {
    const container = document.getElementById("ig-task-table");
    container.replaceChildren();
    const tasks = Array.isArray(payload?.tasks) ? payload.tasks : [];
    if (!tasks.length) return;

    const pageSize = 50;
    const pages = Math.max(1, Math.ceil(tasks.length / pageSize));
    state.resultPage = Math.min(Math.max(0, state.resultPage), pages - 1);
    const from = state.resultPage * pageSize;
    const shown = tasks.slice(from, from + pageSize);

    const table = document.createElement("table");
    table.className = "ig-table";
    const head = document.createElement("tr");
    for (const label of ["TaskBot", "Cuenta", "Estado", "Ejecutor", "Finalizada", "Detalle"]) {
        const cell = document.createElement("th");
        cell.textContent = label;
        head.appendChild(cell);
    }
    table.appendChild(head);

    for (const task of shown) {
        const row = document.createElement("tr");
        for (const key of ["task_bot_id", "account_id", "status", "bot_executor", "end_date", "comment"]) {
            const cell = document.createElement("td");
            const value = task[key];
            cell.textContent = typeof value === "object" ? safeInstagramJson(value) : String(value ?? "");
            row.appendChild(cell);
        }
        table.appendChild(row);
    }
    container.appendChild(table);

    if (pages > 1) {
        const controls = document.createElement("div");
        controls.className = "ig-row";
        const previous = document.createElement("button");
        previous.className = "button secondary";
        previous.type = "button";
        previous.textContent = "Anterior";
        previous.disabled = state.resultPage === 0;
        previous.addEventListener("click", () => {
            state.resultPage -= 1;
            renderInstagramTaskPage(payload);
        });
        const label = document.createElement("span");
        label.className = "ig-muted";
        label.textContent = `Página ${state.resultPage + 1} de ${pages} · ${tasks.length} tareas`;
        const next = document.createElement("button");
        next.className = "button secondary";
        next.type = "button";
        next.textContent = "Siguiente";
        next.disabled = state.resultPage >= pages - 1;
        next.addEventListener("click", () => {
            state.resultPage += 1;
            renderInstagramTaskPage(payload);
        });
        controls.append(previous, label, next);
        container.appendChild(controls);
    }
}

function renderInstagramResultEnvelope(result) {
    const payload = result?.payload || result || {};
    state.currentResult = payload;
    state.resultPage = 0;

    const totals = payload.totals || {};
    const duration = payload.duration ?? payload.duration_seconds ?? (state.currentExecution ? instagramElapsed(state.currentExecution) : "—");
    const summary =
        `Creadas: ${totals.created ?? "-"} | ` +
        `Correctas: ${totals.ok ?? "-"} | ` +
        `Errores: ${totals.error ?? "-"} | ` +
        `Canceladas: ${totals.cancelled ?? "-"} | ` +
        `Duración: ${duration}`;

    const knownSchema = new Set([
        "instagram.maduracion.result.v1",
        "instagram.prospecting.result.v1",
    ]).has(payload.schema_version);

    const preview = knownSchema
        ? { ...payload, tasks: Array.isArray(payload.tasks) ? `[${payload.tasks.length} tareas; ver tabla paginada]` : payload.tasks }
        : payload;

    document.getElementById("ig-result").textContent = summary + "\n\n" + safeInstagramJson(preview);
    renderInstagramTaskPage(payload);
}

async function loadResult(id) {
    try {
        const result = await api(`/executions/${encodeURIComponent(id)}/result`);
        if (state.executionId !== id) return;
        renderInstagramResultEnvelope(result);
    } catch (error) {
        if (state.executionId === id) {
            const terminalError = state.currentExecution?.error_message;
            document.getElementById("ig-result").textContent =
                [terminalError ? `Error terminal: ${terminalError}` : "", `Resultado: ${error.message}`]
                    .filter(Boolean)
                    .join("\n");
        }
    }
}

/* =========================================================
   CANCELAR
   ========================================================= */

async function cancelExecution() {
    if (
        !state.executionId
    ) {
        return;
    }

    const cancelId =
        state.executionId;

    document.getElementById(
        "ig-cancel"
    ).disabled = true;

    if (
        !window.confirm(
            "La cancelación puede tardar mientras el bot termina una operación atómica. ¿Deseas continuar?"
        )
    ) {
        document.getElementById(
            "ig-cancel"
        ).disabled = false;

        return;
    }

    try {
        await api(
            `/executions/${encodeURIComponent(cancelId)}/cancel`,
            {
                method: "POST",
                body: "{}",
            }
        );

        if (
            state.executionId ===
            cancelId
        ) {
            startPolling(
                cancelId
            );
        }

    } catch (error) {
        document.getElementById("ig-current").textContent = `Cancelación: ${error.message}`;
        const cancelButton = document.getElementById("ig-cancel");
        const canRetryCancel = ["queued", "running"].includes(state.currentExecution?.status);
        cancelButton.hidden = !canRetryCancel;
        cancelButton.disabled = !canRetryCancel;
    }
}


/* =========================================================
   HISTORIAL
   ========================================================= */

async function loadHistory(append = false) {
    const body = document.getElementById("ig-history");
    const more = document.getElementById("ig-history-more");
    if (!body) return;

    try {
        const cursor = append ? state.historyCursor : null;
        const query = new URLSearchParams({ bot_type: "instagram", limit: "50" });
        if (cursor) query.set("cursor", cursor);
        const data = await api(`/executions?${query}`);
        const items = data.items || [];
        state.historyCursor = data.next_cursor || null;

        const rows = items.map((item) => {
            const id = item.id || item.execution_id;
            return `
                <tr>
                    <td><code>${esc(id)}</code></td>
                    <td>${esc(item.requested_capability || item.capability)}</td>
                    <td>${esc(INSTAGRAM_STATUS_TEXT[item.status] || item.status)}</td>
                    <td>${esc(formatInstagramDate(item.created_at))}</td>
                    <td><button class="button ghost ig-open" data-id="${esc(id)}">Abrir</button></td>
                </tr>`;
        }).join("");

        if (append) body.insertAdjacentHTML("beforeend", rows);
        else body.innerHTML = rows || '<tr><td colspan="5" class="ig-muted">Sin ejecuciones Instagram.</td></tr>';

        more.hidden = !state.historyCursor;
        body.querySelectorAll(".ig-open").forEach((button) => {
            if (button.dataset.bound) return;
            button.dataset.bound = "1";
            button.addEventListener("click", () => startPolling(button.dataset.id));
        });
    } catch (error) {
        if (!append) body.innerHTML = `<tr><td colspan="5">${esc(error.message)}</td></tr>`;
    }
}

/* =========================================================
   INICIALIZACIÓN
   ========================================================= */

if (
    document.readyState ===
    "loading"
) {
    document.addEventListener(
        "DOMContentLoaded",
        mount
    );
} else {
    mount();
}
