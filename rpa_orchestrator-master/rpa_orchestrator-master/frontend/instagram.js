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
        throw new Error(data?.detail || `HTTP ${response.status}`);
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
    if (document.getElementById("instagram-dashboard-styles")) {
        return;
    }

    const style = document.createElement("style");
    style.id = "instagram-dashboard-styles";

    style.textContent = `
        #view-instagram .ig-grid {
            display: grid;
            grid-template-columns: minmax(320px, 1fr) minmax(420px, 1.4fr);
            gap: 16px;
        }

        #view-instagram .ig-card {
            padding: 18px;
            margin-bottom: 16px;
        }

        #view-instagram .ig-row {
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }

        #view-instagram .ig-field {
            display: flex;
            flex-direction: column;
            gap: 6px;
            margin: 14px 0;
        }

        #view-instagram .ig-field > label,
        #view-instagram .ig-field > span:first-child {
            font-weight: 600;
        }

        #view-instagram .ig-field input,
        #view-instagram .ig-field select,
        #view-instagram .ig-field textarea {
            width: 100%;
            box-sizing: border-box;
        }

        #view-instagram .ig-field select,
        #view-instagram .ig-field input,
        #view-instagram .ig-field textarea {
            min-height: 40px;
        }

        /* =====================================================
           MULTISELECT DE TAREAS
           ===================================================== */

        #view-instagram .ig-multiselect {
            position: relative;
            width: 100%;
        }

        #view-instagram .ig-multiselect-trigger {
            width: 100%;
            min-height: 42px;
            border: 1px solid var(--border, #d7dce3);
            border-radius: 7px;
            background: var(--surface, #fff);
            color: inherit;
            padding: 9px 12px;
            box-sizing: border-box;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            cursor: pointer;
            text-align: left;
            font: inherit;
        }

        #view-instagram .ig-multiselect-trigger:hover {
            border-color: #9aa7b5;
        }

        #view-instagram .ig-multiselect-trigger:focus {
            outline: 2px solid rgba(0, 123, 255, 0.18);
            outline-offset: 1px;
        }

        #view-instagram .ig-multiselect-value {
            flex: 1;
            overflow: hidden;
            white-space: nowrap;
            text-overflow: ellipsis;
        }

        #view-instagram .ig-multiselect-arrow {
            font-size: 12px;
            opacity: .65;
            transition: transform .15s ease;
        }

        #view-instagram .ig-multiselect.open .ig-multiselect-arrow {
            transform: rotate(180deg);
        }

        #view-instagram .ig-multiselect-menu {
            display: none;
            position: absolute;
            left: 0;
            right: 0;
            top: calc(100% + 4px);
            z-index: 1000;
            background: var(--surface, #fff);
            border: 1px solid var(--border, #d7dce3);
            border-radius: 8px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, .12);
            overflow: hidden;
        }

        #view-instagram .ig-multiselect.open .ig-multiselect-menu {
            display: block;
        }

        #view-instagram .ig-task-search-wrap {
            padding: 9px;
            border-bottom: 1px solid var(--border, #e4e7eb);
        }

        #view-instagram .ig-task-search {
            width: 100%;
            min-height: 36px !important;
            padding: 7px 10px;
            border: 1px solid var(--border, #d7dce3);
            border-radius: 6px;
            box-sizing: border-box;
        }

        #view-instagram .ig-task-options {
            max-height: 270px;
            overflow-y: auto;
            padding: 5px 0;
        }

        #view-instagram .ig-task-option {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 9px 12px;
            cursor: pointer;
            user-select: none;
        }

        #view-instagram .ig-task-option:hover {
            background: rgba(127, 127, 127, .08);
        }

        #view-instagram .ig-task-option input {
            width: 16px !important;
            min-height: auto !important;
            height: 16px;
            margin: 0;
            flex: 0 0 auto;
        }

        #view-instagram .ig-task-option-content {
            display: flex;
            flex-direction: column;
            gap: 2px;
            min-width: 0;
        }

        #view-instagram .ig-task-option-name {
            font-size: 14px;
        }

        #view-instagram .ig-task-option-meta {
            font-size: 11px;
            opacity: .62;
        }

        #view-instagram .ig-task-empty {
            padding: 14px 12px;
            opacity: .65;
        }

        #view-instagram .ig-selected-summary {
            font-size: 12px;
            opacity: .72;
            margin-top: 2px;
        }

        /* =====================================================
           CUENTAS
           ===================================================== */

        #view-instagram .ig-checks {
            max-height: 180px;
            overflow: auto;
            border: 1px solid var(--border, #ddd);
            padding: 8px;
            border-radius: 8px;
        }

        #view-instagram .ig-check {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 5px 2px;
        }

        #view-instagram .ig-check input {
            width: auto;
            min-height: auto;
        }

        /* =====================================================
           RESTO DEL DASHBOARD
           ===================================================== */

        #view-instagram .ig-status {
            font-weight: 700;
            text-transform: uppercase;
        }

        #view-instagram .ig-muted {
            opacity: .7;
        }

        #view-instagram .ig-table {
            width: 100%;
            border-collapse: collapse;
        }

        #view-instagram .ig-table th,
        #view-instagram .ig-table td {
            padding: 7px;
            border-bottom: 1px solid var(--border, #ddd);
            text-align: left;
            vertical-align: top;
        }

        #view-instagram .ig-events {
            max-height: 220px;
            overflow: auto;
            font-family: monospace;
            font-size: 12px;
            white-space: pre-wrap;
        }

        #view-instagram .ig-result {
            max-height: 340px;
            overflow: auto;
            font-family: monospace;
            font-size: 12px;
            white-space: pre-wrap;
        }

        @media (max-width: 900px) {
            #view-instagram .ig-grid {
                grid-template-columns: 1fr;
            }
        }
    `;

    document.head.appendChild(style);
}


/* =========================================================
   MONTAJE DE LA PESTAÑA
   ========================================================= */

function mount() {
    ensureStyles();

    const tabs = document.querySelector(".workspace-tabs");
    const views = document.querySelector("main.shell");

    if (
        !tabs ||
        !views ||
        document.getElementById("view-instagram")
    ) {
        return;
    }

    const tab = document.createElement("button");
    tab.className = "workspace-tab";
    tab.dataset.view = "instagram";
    tab.textContent = "Instagram";

    tabs.appendChild(tab);

    const section = document.createElement("div");
    section.id = "view-instagram";
    section.className = "workspace-view";

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
                        placeholder='{"campaign_id":10}'
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
                        disabled
                    >
                        Cancelar
                    </button>

                </div>

                <div
                    id="ig-current"
                    class="ig-muted"
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

        </section>
    `;

    views.appendChild(section);

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
        .addEventListener("click", loadHistory);

    document.addEventListener("click", handleOutsideTaskDropdown);
    document.addEventListener("click", handleOutsideAccountDropdown);

    updateTargetFields();
    loadCatalog();

    const existing =
        new URLSearchParams(location.search).get("execution_id");

    if (
        existing &&
        /^[0-9a-f-]{36}$/i.test(existing)
    ) {
        startPolling(existing);
    }
}


/* =========================================================
   ACTIVAR PESTAÑA
   ========================================================= */

function activate() {
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
                throw new Error(
                    "object required"
                );
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
        options.bot_executor =
            executor;
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

        document.getElementById(
            "ig-cancel"
        ).disabled =
            ![
                "queued",
                "running",
            ].includes(
                execution.status
            );

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
        message.textContent =
            `Error: ${error.message}`;

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

            document.getElementById(
                "ig-cancel"
            ).disabled =
                ![
                    "queued",
                    "running",
                ].includes(
                    execution.status
                );

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

                document.getElementById(
                    "ig-cancel"
                ).disabled = true;

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

function renderExecution(execution) {
    const id =
        execution.id ||
        execution.execution_id ||
        state.executionId;

    document.getElementById(
        "ig-current"
    ).innerHTML = `
        <div class="ig-status">
            ${esc(execution.status)}
        </div>

        <div>
            ${esc(id)}
        </div>

        <div class="ig-muted">
            ${esc(
                execution.requested_capability ||
                execution.capability ||
                "Instagram"
            )}
        </div>
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

async function loadResult(id) {
    try {
        const result =
            await api(
                `/executions/${encodeURIComponent(id)}/result`
            );

        if (
            state.executionId !== id
        ) {
            return;
        }

        const payload =
            result.payload ||
            result;

        const totals =
            payload.totals || {};

        const summary =
            `Creadas: ${totals.created ?? "-"} | ` +
            `Correctas: ${totals.ok ?? "-"} | ` +
            `Errores: ${totals.error ?? "-"} | ` +
            `Canceladas: ${totals.cancelled ?? "-"}`;

        document.getElementById(
            "ig-result"
        ).textContent =
            summary +
            "\n\n" +
            JSON.stringify(
                payload,
                null,
                2
            );

        const container =
            document.getElementById(
                "ig-task-table"
            );

        container.replaceChildren();

        if (
            Array.isArray(
                payload.tasks
            ) &&
            payload.tasks.length
        ) {
            const table =
                document.createElement(
                    "table"
                );

            table.className =
                "ig-table";

            const head =
                document.createElement(
                    "tr"
                );

            for (
                const label of [
                    "TaskBot",
                    "Cuenta",
                    "Estado",
                    "Ejecutor",
                    "Finalizada",
                    "Detalle",
                ]
            ) {
                const cell =
                    document.createElement(
                        "th"
                    );

                cell.textContent =
                    label;

                head.appendChild(
                    cell
                );
            }

            table.appendChild(
                head
            );

            for (
                const task of
                payload.tasks.slice(
                    0,
                    100
                )
            ) {
                const row =
                    document.createElement(
                        "tr"
                    );

                for (
                    const key of [
                        "task_bot_id",
                        "account_id",
                        "status",
                        "bot_executor",
                        "end_date",
                        "comment",
                    ]
                ) {
                    const cell =
                        document.createElement(
                            "td"
                        );

                    const value =
                        task[key];

                    cell.textContent =
                        typeof value ===
                        "object"
                            ? JSON.stringify(
                                  value
                              )
                            : String(
                                  value ?? ""
                              );

                    row.appendChild(
                        cell
                    );
                }

                table.appendChild(
                    row
                );
            }

            container.appendChild(
                table
            );

            if (
                payload.tasks.length >
                100
            ) {
                const note =
                    document.createElement(
                        "p"
                    );

                note.textContent =
                    `Mostrando 100 de ${payload.tasks.length} tareas. El JSON conserva el resultado completo.`;

                container.appendChild(
                    note
                );
            }
        }

    } catch (error) {
        if (
            state.executionId === id
        ) {
            document.getElementById(
                "ig-result"
            ).textContent =
                error.message;
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
            "¿Cancelar la ejecución de Instagram?"
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
        document.getElementById(
            "ig-current"
        ).textContent =
            `Cancelación: ${error.message}`;
    }
}


/* =========================================================
   HISTORIAL
   ========================================================= */

async function loadHistory() {
    const body =
        document.getElementById(
            "ig-history"
        );

    if (!body) {
        return;
    }

    try {
        const data =
            await api(
                "/executions?bot_type=instagram&limit=50"
            );

        const items =
            data.items || [];

        body.innerHTML =
            items
                .map((item) => {
                    const id =
                        item.id ||
                        item.execution_id;

                    return `
                        <tr>

                            <td>
                                <code>
                                    ${esc(id)}
                                </code>
                            </td>

                            <td>
                                ${esc(
                                    item.requested_capability ||
                                    item.capability
                                )}
                            </td>

                            <td>
                                ${esc(
                                    item.status
                                )}
                            </td>

                            <td>
                                ${esc(
                                    item.created_at
                                )}
                            </td>

                            <td>
                                <button
                                    class="button ghost ig-open"
                                    data-id="${esc(id)}"
                                >
                                    Abrir
                                </button>
                            </td>

                        </tr>
                    `;
                })
                .join("") ||
            `
                <tr>
                    <td
                        colspan="5"
                        class="ig-muted"
                    >
                        Sin ejecuciones Instagram.
                    </td>
                </tr>
            `;

        body
            .querySelectorAll(
                ".ig-open"
            )
            .forEach(
                (button) =>
                    button.addEventListener(
                        "click",
                        () => {
                            state.executionId =
                                button.dataset.id;

                            startPolling(
                                state.executionId
                            );
                        }
                    )
            );

    } catch (error) {
        body.innerHTML = `
            <tr>
                <td colspan="5">
                    ${esc(error.message)}
                </td>
            </tr>
        `;
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
