const api = async (url, options = {}) => {
  const response = await fetch(url, {
    ...options,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-Requested-With": "fetch", ...(options.headers || {}) },
  });
  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) throw new Error(data?.detail || "No se pudo completar la operación.");
  return data;
};

const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[character]));
const shortDate = (value) => {
  if (!value) return "—";
  const date = new Date(`${String(value).slice(0, 10)}T12:00:00`);
  return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat("es-CO", { day: "numeric", month: "short", year: "numeric" }).format(date);
};
const longDate = (value) => {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat("es-CO", { dateStyle: "medium", timeStyle: "short" }).format(date);
};
const initials = (name) => String(name || "CT").trim().split(/\s+/).slice(0, 2).map((part) => part[0]?.toLocaleUpperCase("es")).join("") || "CT";
const statusLabel = { pendiente: "Pendiente", confirmada: "Confirmada", rechazada: "Rechazada", cancelada: "Cancelada" };
const contactStatusLabel = { nuevo: "Nuevo", contactado: "Contactado", archivado: "Archivado" };
const formatPrice = (amount) => amount == null ? "Por confirmar" : `${new Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 }).format(amount)} COP`;
const loginView = document.querySelector("#login-view");
const dashboardView = document.querySelector("#dashboard-view");
const sectionNames = { overview: "Resumen", reservations: "Reservas", contacts: "Mensajes", experiences: "Experiencias" };
let stats = {};
let bookings = [];
let contacts = [];
let experiences = [];
let bookingOffset = 0;
let bookingTotal = 0;
let reservationQuery = {};
let contactQuery = {};

function announce(selector, text, isError = false) {
  const element = document.querySelector(selector);
  element.textContent = text;
  element.classList.toggle("is-error", isError);
}

function showSection(name) {
  for (const section of Object.keys(sectionNames)) {
    document.querySelector(`#section-${section}`).hidden = section !== name;
  }
  document.querySelectorAll(".sidebar-link").forEach((button) => {
    const active = button.dataset.section === name;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-current", active ? "page" : "false");
  });
  document.querySelector("#current-section-name").textContent = sectionNames[name];
  if (name === "reservations") loadReservations().catch(showError);
  if (name === "contacts") loadContacts().catch(showError);
  if (name === "experiences") loadExperiences().catch(showError);
}

function showError(error) {
  const alert = document.querySelector("#admin-error");
  alert.textContent = error.message || "Ocurrió un error al cargar la información.";
  alert.hidden = false;
}

function clearError() {
  const alert = document.querySelector("#admin-error");
  alert.textContent = "";
  alert.hidden = true;
}

function renderStatCards(items, selector) {
  document.querySelector(selector).innerHTML = items.map((item) => `
    <article class="stat-card ${item.tone}">
      <div class="stat-top"><span>${item.label}</span><span class="stat-icon" aria-hidden="true">${item.icon}</span></div>
      <div class="stat-value">${Number(item.value || 0).toLocaleString("es-CO")}</div>
      <div class="stat-hint">${item.hint}</div>
    </article>`).join("");
}

function reservationStats() {
  renderStatCards([
    { label: "Solicitudes totales", value: stats.solicitudes, icon: "▤", tone: "stat-lime", hint: "Historial recibido" },
    { label: "Pendientes", value: stats.pendientes, icon: "◷", tone: "stat-orange", hint: "Esperan tu respuesta" },
    { label: "Confirmadas", value: stats.confirmadas, icon: "✓", tone: "stat-blue", hint: "Listas para el recorrido" },
    { label: "Canceladas", value: stats.canceladas, icon: "↺", tone: "stat-pink", hint: "No siguen activas" },
    { label: "Experiencias", value: stats.experiencias, icon: "✳", tone: "stat-purple", hint: "En tu catálogo" },
  ], "#reservation-stats");
}

async function loadOverview() {
  stats = await api("/api/admin/dashboard");
  const recentData = await api("/api/reservas?limit=5");
  const cards = [
    { label: "Todas las solicitudes", value: stats.solicitudes, icon: "▤", tone: "stat-lime", hint: "Reservas recibidas" },
    { label: "Por responder", value: stats.pendientes, icon: "◷", tone: "stat-orange", hint: "Requieren seguimiento" },
    { label: "Confirmadas", value: stats.confirmadas, icon: "✓", tone: "stat-blue", hint: "Experiencias acordadas" },
    { label: "Mensajes nuevos", value: stats.contactos_nuevos, icon: "✉", tone: "stat-pink", hint: "Desde el formulario" },
    { label: "Experiencias", value: stats.experiencias, icon: "✳", tone: "stat-purple", hint: "En tu catálogo" },
  ];
  renderStatCards(cards, "#metrics");
  document.querySelector("#pending-badge").textContent = Number(stats.pendientes || 0).toLocaleString("es-CO");
  document.querySelector("#contact-badge").textContent = Number(stats.contactos_nuevos || 0).toLocaleString("es-CO");
  renderRecentBookings(recentData.items);
  renderStatusBreakdown();
  reservationStats();
}

function renderRecentBookings(items) {
  document.querySelector("#recent-booking-rows").innerHTML = items.map((booking) => `
    <tr>
      <td><div class="visitor-cell"><span class="visitor-avatar">${escapeHtml(initials(booking.nombre_completo))}</span><span><strong class="visitor-name">${escapeHtml(booking.nombre_completo)}</strong><small class="visitor-email">${escapeHtml(booking.email)}</small></span></div></td>
      <td class="experience-cell">${escapeHtml(booking.experiencia_nombre)}</td>
      <td class="date-cell">${escapeHtml(shortDate(booking.fecha_solicitada))}</td>
      <td><span class="status-pill status-${escapeHtml(booking.estado)}">${escapeHtml(statusLabel[booking.estado] || booking.estado)}</span></td>
      <td><button class="row-action" type="button" data-booking-detail="${escapeHtml(booking.id)}">Ver</button></td>
    </tr>`).join("") || '<tr><td colspan="5"><div class="empty-state">Aún no hay solicitudes. Cuando llegue la primera, aparecerá aquí.</div></td></tr>';
  document.querySelectorAll("[data-booking-detail]").forEach((button) => {
    button.addEventListener("click", () => openBookingDetail(button.dataset.bookingDetail));
  });
}

function renderStatusBreakdown() {
  const total = Number(stats.solicitudes || 0);
  const rows = [
    { name: "Pendientes", key: "pendientes", color: "#ff8154" },
    { name: "Confirmadas", key: "confirmadas", color: "#43ae78" },
    { name: "Canceladas", key: "canceladas", color: "#a7b1a9" },
  ];
  document.querySelector("#status-breakdown").innerHTML = rows.map((row) => {
    const value = Number(stats[row.key] || 0);
    const width = total ? Math.min(100, Math.round(value / total * 100)) : 0;
    return `<div><div class="status-line-top"><span>${row.name}</span><strong>${value} <span>${width}%</span></strong></div><div class="status-track"><div class="status-fill" style="--fill-color:${row.color};width:${width}%"></div></div></div>`;
  }).join("");
}

function renderBookings(items) {
  document.querySelector("#booking-rows").innerHTML = items.map((booking) => {
    const action = booking.estado === "pendiente"
      ? `<button class="row-action" type="button" data-booking-detail="${escapeHtml(booking.id)}">Revisar</button>`
      : `<button class="row-action" type="button" data-booking-detail="${escapeHtml(booking.id)}">Detalle</button>`;
    return `<tr>
      <td><strong>${escapeHtml(booking.codigo_reserva)}</strong></td>
      <td><div class="visitor-cell"><span class="visitor-avatar">${escapeHtml(initials(booking.nombre_completo))}</span><span><strong class="visitor-name">${escapeHtml(booking.nombre_completo)}</strong><small class="visitor-email">${escapeHtml(booking.email)}<br>${escapeHtml(booking.telefono)}</small></span></div></td>
      <td class="experience-cell">${escapeHtml(booking.experiencia_nombre)}</td>
      <td class="date-cell">${escapeHtml(shortDate(booking.fecha_solicitada))}</td>
      <td>${Number(booking.numero_participantes)}</td>
      <td><span class="status-pill status-${escapeHtml(booking.estado)}">${escapeHtml(statusLabel[booking.estado] || booking.estado)}</span></td>
      <td>${action}</td>
    </tr>`;
  }).join("") || '<tr><td colspan="7"><div class="empty-state">No hay solicitudes que coincidan con estos filtros.</div></td></tr>';
  document.querySelectorAll("[data-booking-detail]").forEach((button) => {
    button.addEventListener("click", () => openBookingDetail(button.dataset.bookingDetail));
  });
  document.querySelector("#booking-count").textContent = `${bookingTotal} ${bookingTotal === 1 ? "solicitud" : "solicitudes"}`;
  const page = Math.floor(bookingOffset / 20) + 1;
  document.querySelector("#page-label").textContent = `Página ${page}`;
  document.querySelector("#previous-page").disabled = bookingOffset <= 0;
  document.querySelector("#next-page").disabled = bookingOffset + 20 >= bookingTotal;
}

async function loadReservations() {
  const params = new URLSearchParams({ limit: "20", offset: String(bookingOffset) });
  for (const [key, value] of Object.entries(reservationQuery)) if (value) params.set(key, value);
  const [result, latestStats] = await Promise.all([
    api(`/api/reservas?${params.toString()}`),
    api("/api/admin/dashboard"),
  ]);
  stats = latestStats;
  bookings = result.items;
  bookingTotal = result.total;
  reservationStats();
  renderBookings(bookings);
}

async function openBookingDetail(bookingId) {
  try {
    const booking = await api(`/api/reservas/${bookingId}`);
    const allowed = {
      pendiente: ["confirmada", "rechazada", "cancelada"],
      confirmada: ["cancelada"],
      rechazada: [],
      cancelada: [],
    }[booking.estado] || [];
    document.querySelector("#booking-detail").innerHTML = `
      <span class="detail-kicker">SOLICITUD · ${escapeHtml(booking.codigo_reserva)}</span>
      <h2 class="detail-heading">${escapeHtml(booking.nombre_completo)}</h2>
      <p class="detail-subtitle">Recibida el ${escapeHtml(longDate(booking.fecha_creacion))} · <span class="status-pill status-${escapeHtml(booking.estado)}">${escapeHtml(statusLabel[booking.estado] || booking.estado)}</span></p>
      <div class="detail-grid">
        <div class="detail-box"><span>EXPERIENCIA</span><strong>${escapeHtml(booking.experiencia_nombre)}</strong></div>
        <div class="detail-box"><span>FECHA SOLICITADA</span><strong>${escapeHtml(shortDate(booking.fecha_solicitada))}</strong></div>
        <div class="detail-box"><span>PARTICIPANTES</span><strong>${Number(booking.numero_participantes)}</strong></div>
        <div class="detail-box"><span>TELÉFONO</span><strong><a href="tel:${escapeHtml(booking.telefono)}">${escapeHtml(booking.telefono)}</a></strong></div>
        <div class="detail-box"><span>CORREO</span><strong><a href="mailto:${escapeHtml(booking.email)}">${escapeHtml(booking.email)}</a></strong></div>
        <div class="detail-box"><span>PRIVACIDAD</span><strong>${booking.aceptacion_privacidad ? "Aceptada" : "No consta"}</strong></div>
      </div>
      <div class="detail-message"><strong>Comentario del visitante</strong><br>${escapeHtml(booking.comentarios || "Sin comentarios adicionales.")}</div>
      <label class="detail-kicker" for="booking-note">NOTA INTERNA (solo visible para el equipo)</label>
      <textarea id="booking-note" class="detail-note" maxlength="2000" placeholder="Añade información para dar seguimiento…">${escapeHtml(booking.notas_administrativas || "")}</textarea>
      <div class="detail-actions">
        <button type="button" data-save-note="${escapeHtml(booking.id)}" class="admin-primary">Guardar nota</button>
        ${allowed.map((state) => `<button type="button" data-update-booking="${escapeHtml(booking.id)}" data-status="${state}">${state === "confirmada" ? "✓ Confirmar solicitud" : state === "rechazada" ? "Rechazar" : "Cancelar solicitud"}</button>`).join("")}
      </div>`;
    const dialog = document.querySelector("#booking-dialog");
    dialog.showModal();
    dialog.querySelector("[data-save-note]").addEventListener("click", async (event) => {
      const note = dialog.querySelector("#booking-note").value;
      try {
        await api(`/api/reservas/${event.currentTarget.dataset.saveNote}/notas`, {
          method: "PATCH",
          body: JSON.stringify({ notas_administrativas: note }),
        });
        announce("#booking-message", "Nota interna guardada.");
        if (!document.querySelector("#section-overview").hidden) await loadOverview();
        else await loadReservations();
      } catch (error) {
        announce("#booking-message", error.message, true);
      }
    });
    dialog.querySelectorAll("[data-update-booking]").forEach((button) => {
      button.addEventListener("click", async () => {
        const nextState = button.dataset.status;
        if (!window.confirm(`¿Confirmas el cambio de esta solicitud a “${statusLabel[nextState]}”?`)) return;
        try {
          await api(`/api/reservas/${button.dataset.updateBooking}/estado`, {
            method: "PATCH",
            body: JSON.stringify({ estado: nextState }),
          });
          dialog.close();
          await loadOverview();
          if (!document.querySelector("#section-reservations").hidden) await loadReservations();
          announce("#booking-message", `Solicitud actualizada: ${statusLabel[nextState]}.`);
        } catch (error) {
          announce("#booking-message", error.message, true);
        }
      });
    });
  } catch (error) {
    showError(error);
  }
}

async function exportBookings() {
  const params = new URLSearchParams({ limit: "100", offset: "0" });
  for (const [key, value] of Object.entries(reservationQuery)) if (value) params.set(key, value);
  const firstPage = await api(`/api/reservas?${params.toString()}`);
  const rows = [...firstPage.items];
  for (let offset = 100; offset < firstPage.total; offset += 100) {
    params.set("offset", String(offset));
    const page = await api(`/api/reservas?${params.toString()}`);
    rows.push(...page.items);
  }
  const csvValue = (value) => {
    let safeValue = String(value ?? "");
    if (/^[\s]*[=+\-@]/.test(safeValue)) safeValue = `'${safeValue}`;
    return `"${safeValue.replace(/"/g, '""')}"`;
  };
  const columns = ["codigo_reserva", "nombre_completo", "email", "telefono", "experiencia_nombre", "fecha_solicitada", "numero_participantes", "estado", "comentarios", "notas_administrativas"];
  const csv = [columns, ...rows.map((booking) => columns.map((key) => booking[key] ?? ""))]
    .map((row) => row.map(csvValue).join(";")).join("\r\n");
  const blob = new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `solicitudes-cerro-tusa-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(url);
  announce("#booking-message", `Se exportaron ${rows.length} solicitudes.`);
}

async function loadContacts() {
  const params = new URLSearchParams({ limit: "100", offset: "0" });
  for (const [key, value] of Object.entries(contactQuery)) if (value) params.set(key, value);
  const result = await api(`/api/contactos?${params.toString()}`);
  contacts = result.items;
  document.querySelector("#contact-count").textContent = `${result.total} ${result.total === 1 ? "mensaje" : "mensajes"}`;
  document.querySelector("#contact-list").innerHTML = contacts.map((contact) => `
    <article class="contact-item">
      <span class="contact-avatar">${escapeHtml(initials(contact.nombre))}</span>
      <div class="contact-main">
        <div class="contact-top"><strong>${escapeHtml(contact.nombre)}</strong><span class="status-pill ${contact.estado === "nuevo" ? "status-pendiente" : contact.estado === "contactado" ? "status-confirmada" : "status-cancelada"}">${escapeHtml(contactStatusLabel[contact.estado] || contact.estado)}</span></div>
        <h3 class="contact-subject">${escapeHtml(contact.asunto)}</h3>
        <p class="contact-excerpt">${escapeHtml(contact.mensaje)}</p>
        <div class="contact-meta"><a href="mailto:${escapeHtml(contact.email)}">${escapeHtml(contact.email)}</a>${contact.telefono ? `<a href="tel:${escapeHtml(contact.telefono)}">${escapeHtml(contact.telefono)}</a>` : ""}<span>${escapeHtml(longDate(contact.fecha_creacion))}</span></div>
      </div>
      <div class="contact-actions">
        <button class="contact-open" type="button" data-open-contact="${escapeHtml(contact.id)}">Ver detalle</button>
        <select aria-label="Cambiar estado del mensaje de ${escapeHtml(contact.nombre)}" data-contact-status="${escapeHtml(contact.id)}">
          ${Object.entries(contactStatusLabel).map(([value, label]) => `<option value="${value}" ${contact.estado === value ? "selected" : ""}>${label}</option>`).join("")}
        </select>
      </div>
    </article>`).join("") || '<div class="empty-state">No hay mensajes para mostrar. Los mensajes del formulario de contacto llegarán aquí.</div>';
  document.querySelectorAll("[data-open-contact]").forEach((button) => {
    button.addEventListener("click", () => openContactDetail(button.dataset.openContact));
  });
  document.querySelectorAll("[data-contact-status]").forEach((select) => {
    select.addEventListener("change", async () => {
      try {
        await api(`/api/contactos/${select.dataset.contactStatus}/estado`, {
          method: "PATCH",
          body: JSON.stringify({ estado: select.value }),
        });
        await loadContacts();
        stats = await api("/api/admin/dashboard");
        document.querySelector("#contact-badge").textContent = Number(stats.contactos_nuevos || 0).toLocaleString("es-CO");
        announce("#contact-message", "Estado del mensaje actualizado.");
      } catch (error) {
        announce("#contact-message", error.message, true);
      }
    });
  });
}

function openContactDetail(contactId) {
  const contact = contacts.find((item) => item.id === contactId);
  if (!contact) return;
  document.querySelector("#contact-detail").innerHTML = `
    <span class="detail-kicker">MENSAJE · ${escapeHtml(contactStatusLabel[contact.estado] || contact.estado)}</span>
    <h2 class="detail-heading">${escapeHtml(contact.asunto)}</h2>
    <p class="detail-subtitle">Enviado el ${escapeHtml(longDate(contact.fecha_creacion))}</p>
    <div class="detail-grid">
      <div class="detail-box"><span>NOMBRE</span><strong>${escapeHtml(contact.nombre)}</strong></div>
      <div class="detail-box"><span>CORREO</span><strong><a href="mailto:${escapeHtml(contact.email)}">${escapeHtml(contact.email)}</a></strong></div>
      <div class="detail-box"><span>TELÉFONO</span><strong>${contact.telefono ? `<a href="tel:${escapeHtml(contact.telefono)}">${escapeHtml(contact.telefono)}</a>` : "No indicado"}</strong></div>
    </div>
    <div class="dialog-contact-message">${escapeHtml(contact.mensaje)}</div>
    <div class="detail-actions"><a class="admin-primary" href="mailto:${escapeHtml(contact.email)}?subject=${encodeURIComponent(`Re: ${contact.asunto}`)}">Responder por correo ↗</a></div>`;
  document.querySelector("#contact-dialog").showModal();
}

async function loadExperiences() {
  experiences = await api("/api/admin/experiencias");
  document.querySelector("#experience-cards").innerHTML = experiences.map((experience) => `
    <article class="experience-admin-card">
      <div class="experience-admin-top"><span class="card-eyebrow">EXPERIENCIA</span><span class="status-pill ${experience.activa ? "status-confirmada" : "status-cancelada"}">${experience.activa ? "Publicada" : "Oculta"}</span></div>
      <h3>${escapeHtml(experience.nombre)}</h3>
      <p>${escapeHtml(experience.descripcion)}</p>
      <div class="experience-admin-meta"><span>${escapeHtml(experience.duracion || "Duración por confirmar")}</span><span>·</span><span>${escapeHtml(experience.dificultad || "Dificultad por confirmar")}</span></div>
      <div class="experience-admin-meta"><strong>${escapeHtml(formatPrice(experience.precio))}</strong></div>
      <div class="experience-admin-actions"><button type="button" data-edit-experience="${escapeHtml(experience.id)}">Editar</button>${experience.activa ? `<button type="button" data-toggle-experience="${escapeHtml(experience.id)}" data-active="false">Desactivar</button>` : `<button type="button" data-toggle-experience="${escapeHtml(experience.id)}" data-active="true">Publicar</button>`}</div>
    </article>`).join("") || '<div class="dash-card empty-state">Todavía no hay experiencias. Usa el formulario para crear la primera.</div>';
  document.querySelectorAll("[data-edit-experience]").forEach((button) => {
    button.addEventListener("click", () => {
      const experience = experiences.find((item) => item.id === button.dataset.editExperience);
      if (!experience) return;
      const form = document.querySelector("#experience-form");
      for (const key of ["id", "nombre", "slug", "precio", "duracion", "dificultad", "imagen", "descripcion", "requisitos", "activa"]) {
        const field = form.elements.namedItem(key);
        if (!field) continue;
        if (field.type === "checkbox") field.checked = Boolean(experience[key]);
        else field.value = experience[key] ?? "";
      }
      form.scrollIntoView({ behavior: "smooth", block: "center" });
      form.elements.nombre.focus();
    });
  });
  document.querySelectorAll("[data-toggle-experience]").forEach((button) => {
    button.addEventListener("click", async () => {
      const experience = experiences.find((item) => item.id === button.dataset.toggleExperience);
      if (!experience) return;
      const active = button.dataset.active === "true";
      if (!active && !window.confirm(`¿Desactivar “${experience.nombre}”? Ya no aparecerá en el sitio público.`)) return;
      try {
        await api(`/api/experiencias/${experience.id}`, {
          method: "PUT",
          body: JSON.stringify({ ...experience, activa: active }),
        });
        await loadExperiences();
        stats = await api("/api/admin/dashboard");
        renderStatCards([
          { label: "Todas las solicitudes", value: stats.solicitudes, icon: "▤", tone: "stat-lime", hint: "Reservas recibidas" },
          { label: "Por responder", value: stats.pendientes, icon: "◷", tone: "stat-orange", hint: "Requieren seguimiento" },
          { label: "Confirmadas", value: stats.confirmadas, icon: "✓", tone: "stat-blue", hint: "Experiencias acordadas" },
          { label: "Mensajes nuevos", value: stats.contactos_nuevos, icon: "✉", tone: "stat-pink", hint: "Desde el formulario" },
          { label: "Experiencias", value: stats.experiencias, icon: "✳", tone: "stat-purple", hint: "En tu catálogo" },
        ], "#metrics");
        announce("#experience-message", active ? "Experiencia publicada." : "Experiencia desactivada.");
      } catch (error) {
        announce("#experience-message", error.message, true);
      }
    });
  });
}

async function refreshCurrentSection() {
  clearError();
  try {
    await loadOverview();
    if (!document.querySelector("#section-reservations").hidden) await loadReservations();
    if (!document.querySelector("#section-contacts").hidden) await loadContacts();
    if (!document.querySelector("#section-experiences").hidden) await loadExperiences();
  } catch (error) {
    showError(error);
  }
}

async function showAuthenticatedDashboard() {
  try {
    const admin = await api("/api/auth/me");
    loginView.hidden = true;
    dashboardView.hidden = false;
    document.querySelector("#admin-user").textContent = admin.nombre || admin.email;
    clearError();
    await loadOverview();
  } catch (error) {
    loginView.hidden = false;
    dashboardView.hidden = true;
    if (error.message.includes("Autenticación") || error.message.includes("sesión")) return;
    announce("#login-form .admin-message", "No se pudo conectar con el panel. Comprueba que MongoDB esté configurado y disponible.", true);
  }
}

document.querySelectorAll("[data-section]").forEach((button) => {
  button.addEventListener("click", () => {
    clearError();
    showSection(button.dataset.section);
  });
});
document.querySelectorAll("[data-go]").forEach((button) => {
  button.addEventListener("click", () => showSection(button.dataset.go));
});
document.querySelector("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  announce("#login-form .admin-message", "");
  try {
    await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(Object.fromEntries(new FormData(form).entries())),
    });
    await showAuthenticatedDashboard();
  } catch (error) {
    announce("#login-form .admin-message", error.message, true);
  } finally {
    button.disabled = false;
  }
});
document.querySelector("#logout-button").addEventListener("click", async () => {
  try {
    await api("/api/auth/logout", { method: "POST" });
  } catch (error) {
    showError(error);
  } finally {
    loginView.hidden = false;
    dashboardView.hidden = true;
  }
});
document.querySelector("#refresh-button").addEventListener("click", refreshCurrentSection);
document.querySelector("#reservations-refresh").addEventListener("click", () => loadReservations().catch(showError));
document.querySelector("#contacts-refresh").addEventListener("click", () => loadContacts().catch(showError));
document.querySelector("#booking-filters").addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  reservationQuery = Object.fromEntries([...formData.entries()].filter(([, value]) => value));
  bookingOffset = 0;
  try { await loadReservations(); announce("#booking-message", `${bookingTotal} solicitudes encontradas.`); }
  catch (error) { announce("#booking-message", error.message, true); }
});
document.querySelector("#clear-filters").addEventListener("click", async () => {
  document.querySelector("#booking-filters").reset();
  reservationQuery = {};
  bookingOffset = 0;
  try { await loadReservations(); announce("#booking-message", "Filtros eliminados."); }
  catch (error) { announce("#booking-message", error.message, true); }
});
document.querySelector("#previous-page").addEventListener("click", () => {
  bookingOffset = Math.max(0, bookingOffset - 20);
  loadReservations().catch((error) => announce("#booking-message", error.message, true));
});
document.querySelector("#next-page").addEventListener("click", () => {
  bookingOffset += 20;
  loadReservations().catch((error) => announce("#booking-message", error.message, true));
});
document.querySelector("#export-bookings").addEventListener("click", () => {
  exportBookings().catch((error) => announce("#booking-message", error.message, true));
});
document.querySelector("#contact-filters").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(event.currentTarget);
  contactQuery = Object.fromEntries([...data.entries()].filter(([, value]) => value));
  try { await loadContacts(); announce("#contact-message", `${contacts.length} mensajes en esta vista.`); }
  catch (error) { announce("#contact-message", error.message, true); }
});
document.querySelector("#clear-contact-filters").addEventListener("click", async () => {
  document.querySelector("#contact-filters").reset();
  contactQuery = {};
  try { await loadContacts(); announce("#contact-message", "Filtros eliminados."); }
  catch (error) { announce("#contact-message", error.message, true); }
});
document.querySelector("#experience-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const values = Object.fromEntries(new FormData(form).entries());
  const payload = {
    nombre: values.nombre,
    slug: values.slug,
    descripcion: values.descripcion,
    precio: values.precio === "" ? null : Number(values.precio),
    duracion: values.duracion,
    dificultad: values.dificultad,
    requisitos: values.requisitos,
    imagen: values.imagen || null,
    activa: form.elements.activa.checked,
  };
  const id = form.elements.id.value;
  try {
    await api(id ? `/api/experiencias/${id}` : "/api/experiencias", {
      method: id ? "PUT" : "POST",
      body: JSON.stringify(payload),
    });
    form.reset();
    form.elements.id.value = "";
    announce("#experience-message", "Experiencia guardada.");
    await loadExperiences();
    await loadOverview();
  } catch (error) {
    announce("#experience-message", error.message, true);
  }
});
document.querySelector("#cancel-edit").addEventListener("click", () => {
  const form = document.querySelector("#experience-form");
  form.reset();
  form.elements.id.value = "";
  announce("#experience-message", "");
});
document.querySelector("#booking-dialog").addEventListener("click", (event) => {
  if (event.target === event.currentTarget) event.currentTarget.close();
});
document.querySelector("#contact-dialog").addEventListener("click", (event) => {
  if (event.target === event.currentTarget) event.currentTarget.close();
});
showAuthenticatedDashboard();
