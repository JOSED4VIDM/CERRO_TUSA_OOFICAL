const formMessage = (form, message, error = false) => {
  const element = form.querySelector(".form-message");
  element.textContent = message;
  element.classList.toggle("error", error);
};

const request = async (url, options = {}) => {
  const response = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const body = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) throw new Error(body?.detail || "No fue posible completar la solicitud.");
  return body;
};

const menuButton = document.querySelector(".menu-toggle");
const navigation = document.querySelector("#main-nav");
menuButton.addEventListener("click", () => {
  const expanded = menuButton.getAttribute("aria-expanded") === "true";
  menuButton.setAttribute("aria-expanded", String(!expanded));
  menuButton.setAttribute("aria-label", expanded ? "Abrir menú" : "Cerrar menú");
  navigation.classList.toggle("open", !expanded);
});
navigation.addEventListener("click", (event) => {
  if (event.target.closest("a")) {
    navigation.classList.remove("open");
    menuButton.setAttribute("aria-expanded", "false");
    menuButton.setAttribute("aria-label", "Abrir menú");
  }
});

const experienceList = document.querySelector("#experience-list");
const experienceSelect = document.querySelector('[name="experiencia_id"]');
const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[character]));

async function loadPublicContent() {
  try {
    const [experiences, config] = await Promise.all([
      request("/api/experiencias"),
      request("/api/configuracion"),
    ]);
    document.querySelectorAll("[data-business-name]").forEach((node) => {
      node.textContent = config.nombre_comercial;
    });
    const cards = experiences.map((experience) => {
      const option = document.createElement("option");
      option.value = experience.id;
      option.textContent = experience.nombre;
      experienceSelect.append(option);
      const details = [experience.duracion, experience.dificultad].filter(Boolean);
      const price = experience.precio == null ? "Consultar tarifa" : `${new Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 }).format(experience.precio)} COP`;
      const imageLabel = experience.imagen ? "Imagen referencial" : "Ilustración conceptual";
      return `<article class="experience-card"><div class="experience-visual" role="img" aria-label="${imageLabel} de paisaje de montaña"><small>${imageLabel.toUpperCase()}</small></div><div class="experience-copy"><h3>${escapeHtml(experience.nombre)}</h3><p>${escapeHtml(experience.descripcion)}</p><div class="experience-meta">${details.map(escapeHtml).join(" · ")}</div><p class="experience-meta">${escapeHtml(price)}</p><a class="button" href="#reservar" data-experience="${escapeHtml(experience.id)}">Consultar experiencia <span aria-hidden="true">→</span></a></div></article>`;
    });
    experienceList.innerHTML = cards.length
      ? cards.join("")
      : '<div class="empty-experiences">Aún no hay experiencias publicadas. Escríbenos para consultar las opciones que el operador tenga habilitadas.</div>';
    experienceList.querySelectorAll("[data-experience]").forEach((link) => {
      link.addEventListener("click", () => { experienceSelect.value = link.dataset.experience; });
    });
    const contactParts = [];
    if (config.whatsapp) {
      const digits = config.whatsapp.replace(/\D/g, "");
      if (digits) contactParts.push(`<a href="https://wa.me/${digits}" target="_blank" rel="noopener noreferrer">Consultar por WhatsApp ↗</a>`);
    }
    if (config.email_contacto) contactParts.push(`<a href="mailto:${encodeURIComponent(config.email_contacto)}">${escapeHtml(config.email_contacto)}</a>`);
    document.querySelector("#booking-contact").innerHTML = contactParts.join("<br>");
  } catch {
    experienceList.innerHTML = '<div class="empty-experiences">No pudimos cargar las experiencias en este momento. Intenta nuevamente más tarde o escríbenos.</div>';
  }
}

async function prefillCustomerDetails() {
  try {
    const customer = await request("/api/clientes/auth/me");
    document.querySelector('[name="nombre_completo"]').value = customer.nombre;
    document.querySelector('[name="email"]').value = customer.email;
  } catch (error) {
    if (error.message !== "Autenticación requerida." && error.message !== "La sesión no es válida o expiró.") {
      formMessage(document.querySelector("#booking-form"), error.message, true);
    }
  }
}

document.querySelector("#booking-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  if (!form.reportValidity()) return;
  const data = new FormData(form);
  const payload = Object.fromEntries(data.entries());
  payload.numero_participantes = Number(payload.numero_participantes);
  payload.aceptacion_privacidad = data.get("aceptacion_privacidad") === "on";
  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    const result = await request("/api/reservas", { method: "POST", body: JSON.stringify(payload) });
    formMessage(form, `Solicitud ${result.codigo_reserva} registrada. El operador debe confirmar disponibilidad; aún no es una reserva confirmada.`);
    form.reset();
  } catch (error) {
    formMessage(form, error.message, true);
  } finally {
    button.disabled = false;
  }
});

document.querySelector("#contact-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  if (!form.reportValidity()) return;
  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    await request("/api/contacto", { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(form).entries())) });
    formMessage(form, "Mensaje enviado. Gracias por escribirnos.");
    form.reset();
  } catch (error) {
    formMessage(form, error.message, true);
  } finally {
    button.disabled = false;
  }
});

document.querySelector("#year").textContent = new Date().getFullYear();
const bookingDate = document.querySelector('[name="fecha_solicitada"]');
bookingDate.min = new Date().toISOString().slice(0, 10);
loadPublicContent();
prefillCustomerDetails();

const galleryDialog = document.querySelector("#gallery-dialog");
const galleryDialogImage = document.querySelector("#gallery-dialog-image");
document.querySelectorAll("[data-gallery-image]").forEach((button) => {
  button.addEventListener("click", () => {
    galleryDialogImage.src = button.dataset.galleryImage;
    galleryDialogImage.alt = button.dataset.galleryAlt;
    galleryDialog.showModal();
  });
});
document.querySelector(".gallery-dialog-close").addEventListener("click", () => galleryDialog.close());
galleryDialog.addEventListener("click", (event) => {
  if (event.target === galleryDialog) galleryDialog.close();
});
