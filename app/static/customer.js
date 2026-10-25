const request = async (url, options = {}) => {
  const response = await fetch(url, {
    ...options,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-Requested-With": "fetch", ...(options.headers || {}) },
  });
  const body = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) throw new Error(body?.detail || "No fue posible completar la solicitud.");
  return body;
};

const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[character]));
const statusNames = { pendiente: "Pendiente", confirmada: "Confirmada", rechazada: "No confirmada", cancelada: "Cancelada" };
const authView = document.querySelector("#auth-view");
const accountView = document.querySelector("#account-view");

function showMessage(form, message, isError = false) {
  const element = form.querySelector(".form-message");
  element.textContent = message;
  element.classList.toggle("error", isError);
}

function formatDate(value) {
  const date = new Date(`${String(value).slice(0, 10)}T12:00:00`);
  return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat("es-CO", {
    day: "numeric", month: "long", year: "numeric",
  }).format(date);
}

async function openAccount(customer) {
  const reservations = await request("/api/clientes/me/reservas");
  authView.hidden = true;
  accountView.hidden = false;
  document.querySelector("#customer-name").textContent = customer.nombre || customer.email;
  document.querySelector("#reservations").innerHTML = reservations.map((booking) => `
    <article class="reservation-card">
      <div class="reservation-top"><div><span class="reservation-code">${escapeHtml(booking.codigo_reserva)}</span><h2>${escapeHtml(booking.experiencia_nombre)}</h2></div>
      <span class="status status-${escapeHtml(booking.estado)}">${escapeHtml(statusNames[booking.estado] || booking.estado)}</span></div>
      <p>${escapeHtml(formatDate(booking.fecha_solicitada))} · ${escapeHtml(booking.numero_participantes)} participante${booking.numero_participantes === 1 ? "" : "s"}</p>
    </article>`).join("") || '<div class="empty-state">Todavía no tienes solicitudes asociadas a tu cuenta. Envía una consulta para ver su estado aquí.</div>';
}

async function authenticate(form, endpoint) {
  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  showMessage(form, "");
  try {
    const customer = await request(endpoint, {
      method: "POST",
      body: JSON.stringify(Object.fromEntries(new FormData(form).entries())),
    });
    await openAccount(customer);
  } catch (error) {
    showMessage(form, error.message, true);
  } finally {
    button.disabled = false;
  }
}

document.querySelector("#customer-login-form").addEventListener("submit", (event) => {
  event.preventDefault();
  authenticate(event.currentTarget, "/api/clientes/auth/login");
});
document.querySelector("#customer-register-form").addEventListener("submit", (event) => {
  event.preventDefault();
  authenticate(event.currentTarget, "/api/clientes/auth/registro");
});
document.querySelector("#logout-button").addEventListener("click", async () => {
  try {
    await request("/api/clientes/auth/logout", { method: "POST" });
    accountView.hidden = true;
    authView.hidden = false;
  } catch (error) {
    window.alert(error.message);
  }
});

request("/api/clientes/auth/me")
  .then(openAccount)
  .catch((error) => {
    if (error.message !== "Autenticación requerida." && error.message !== "La sesión no es válida o expiró.") {
      showMessage(document.querySelector("#customer-login-form"), error.message, true);
    }
  });
