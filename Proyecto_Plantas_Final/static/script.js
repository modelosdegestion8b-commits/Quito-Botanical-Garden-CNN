// script.js

// 🔍 Saber si hay conexión
function estaOffline() {
  return !navigator.onLine;
}

// 🔹 Definición de niveles y mensajes
function obtenerNivelUsuario(v) {
  if (v >= 60) return 4;
  if (v >= 30) return 3;
  if (v >= 10) return 2;
  return 1;
}

const titleMap = {
  1: 'El Primer Brote',
  2: 'La Senda Espinosa',
  3: 'El Corazón Silvestre',
  4: 'El Legado Verde'
};

const milestoneMsgs = {
  2: "🎉 ¡Nivel 2 desbloqueado! ¡Superaste El Primer Brote! Reclama El primer premio en la tienda.",
  3: "🌿 ¡Nivel 3 desbloqueado! ¡Superaste La Senda Espinosa! Reclama El segundo premio en la tienda.",
  4: "🌟 ¡Nivel 4 desbloqueado! ¡Superaste El Corazón Silvestre! Reclama El tercer premio en la tienda."
};

let nivelActual = 1;
let progresoFirestore = {};  // Guarda el progreso leído de Firestore

// 🔹 Lee el progreso del usuario y ajusta nivelActual
async function cargarProgresoDesdeFirestore(uid) {
  if (!uid) return;
  try {
    const doc = await db.collection("usuarios").doc(uid).get();
    progresoFirestore = doc.exists ? (doc.data().progreso || {}) : {};
    const vistas = Object.keys(progresoFirestore).length;
    nivelActual = obtenerNivelUsuario(vistas);
    console.log("🔄 Nivel restaurado:", nivelActual, "vistas=", vistas);
  } catch (e) {
    console.error("❌ Error cargando progreso:", e);
  }
}

// 🔹 Guarda el progreso (y el email) en Firestore
async function guardarProgreso(uid, planta) {
  const user = firebase.auth().currentUser;
  if (!uid || !user) return;

  await db.collection("usuarios").doc(uid).set(
    {
      email: user.email,              // <— grabamos aquí su correo
      progreso: { [planta]: "Visto" }
    },
    { merge: true }
  );
  console.log(`✅ Progreso y email guardados para ${planta}`);
}

// 🔹 Guarda localmente si está offline
function guardarProgresoOffline(planta, img64) {
  const pendientes = JSON.parse(localStorage.getItem("progresoPendiente") || "[]");
  if (!pendientes.find(p => p.planta === planta)) {
    pendientes.push({ planta, imagen: img64 });
    localStorage.setItem("progresoPendiente", JSON.stringify(pendientes));
    console.log(`📦 Guardado localmente: ${planta}`);
  }
}

// 🔹 Sincroniza progresos pendientes cuando vuelve internet
async function sincronizarProgresoPendiente() {
  const pendientes = JSON.parse(localStorage.getItem("progresoPendiente") || "[]");
  if (pendientes.length === 0) return;

  const user = firebase.auth().currentUser;
  if (!user) return;

  const nuevosPendientes = [];
  for (const item of pendientes) {
    try {
      const blob = await fetch(item.imagen).then(r => r.blob());
      const fd = new FormData();
      fd.append("imagen", blob, "offline.jpg");
      fd.append("planta_esperada", item.planta);

      const resp = await fetch("/api/analizar_foto", { method: "POST", body: fd });
      const data = await resp.json();
      if (data.confianza >= 80 && data.coincide) {
        await guardarProgreso(user.uid, item.planta);
      }
    } catch (e) {
      console.warn(`⚠️ No se pudo sincronizar ${item.planta}`, e);
      nuevosPendientes.push(item);
    }
  }

  localStorage.setItem("progresoPendiente", JSON.stringify(nuevosPendientes));
  actualizarProgreso();
}

// 🔹 Renderiza TODAS las tarjetas según nivelActual y progresoFirestore
async function cargarPlantasYProgreso(uid) {
  const cont = document.getElementById("listaPlantas");
  if (!cont) return;
  cont.innerHTML = "";

  const resp = await fetch("/api/plantas");
  const plantas = await resp.json();

  Object.keys(plantas).forEach(key => {
    const dato = plantas[key];
    const dif = dato.dificultad || 1;
    if (dif > nivelActual) return;

    const visto = progresoFirestore[key] === "Visto";
    const estadoInicial = visto ? "🟢 Visto" : "🔴 A la espera";

    const card = document.createElement("div");
    card.className = "planta";
    card.innerHTML = `
      <div class="info-principal">
        <span class="nombre-planta">${key}</span>
        <span class="estado">${estadoInicial}</span>
        <button class="toggle-info">Detalles</button>
        <button class="btn-camara" data-planta="${key}">Tomar Foto</button>
      </div>
      <div class="info-extra" id="${key}">
        <p>🌍 <strong>Ubicación:</strong> ${dato.otros_detalles}</p>
        <p>📘 <strong>Características:</strong> ${dato.descripcion}</p>
        <div class="fotos-planta">
          <img src="${dato.fotos[0]}" alt="Foto 1 de ${key}">
          ${ dato.fotos[1] ? `<img src="${dato.fotos[1]}" alt="Foto 2 de ${key}">` : `` }
        </div>
      </div>
    `;
    card.querySelector(".toggle-info")
        .addEventListener("click", () => toggleInfo(key, card.querySelector(".toggle-info")));
    cont.appendChild(card);
  });

  // Una vez creadas todas las tarjetas, actualizamos barra, título e hitos
  actualizarProgreso();
}

// 🔹 Actualiza barra, título y chequea hitos
function actualizarProgreso() {
  const estados = document.querySelectorAll(".estado");
  let vistas = 0;
  estados.forEach(e => { if (e.textContent.includes("🟢")) vistas++; });

  const total = estados.length;
  const pct   = total ? Math.round((vistas / total) * 100) : 0;

  document.getElementById("contador-progreso").textContent =
    `Progreso: ${vistas} de ${total} plantas`;
  document.getElementById("barra-llena").style.width = pct + "%";
  document.getElementById("titulo-nivel").textContent = titleMap[nivelActual];

  const nuevoNivel = obtenerNivelUsuario(vistas);
  if (nuevoNivel > nivelActual) {
    nivelActual = nuevoNivel;
    if (milestoneMsgs[nuevoNivel]) alert(milestoneMsgs[nuevoNivel]);
    cargarPlantasYProgreso(firebase.auth().currentUser?.uid || null);
  }
}

// 🔹 Maneja evento "Tomar Foto"
document.addEventListener("click", async e => {
  if (!e.target.classList.contains("btn-camara")) return;

  const planta = e.target.dataset.planta;
  const estadoEl = e.target.closest(".planta").querySelector(".estado");
  const inp = document.createElement("input");
  inp.type = "file";
  inp.accept = "image/*";
  inp.capture = "environment";

  inp.onchange = async () => {
    const file = inp.files[0];
    if (!file) return;

    if (estaOffline()) {
      const reader = new FileReader();
      reader.onloadend = () => {
        guardarProgresoOffline(planta, reader.result);
        estadoEl.textContent = "🟡 Offline";
        alert("📴 Sin conexión: se guardará al reconectar.");
      };
      reader.readAsDataURL(file);
      return;
    }

    estadoEl.textContent = "⏳ Verificando...";
    const fd = new FormData();
    fd.append("imagen", file);
    fd.append("planta_esperada", planta);

    try {
      const res = await fetch("/api/analizar_foto", { method: "POST", body: fd });
      const j   = await res.json();
      const ok  = j.confianza >= 80 && j.coincide;
      estadoEl.textContent = ok ? "🟢 Visto" : "🔴 A la espera";

      alert((ok ? "✅ ¡Correcto!" : `❌ No es la planta correcta, más bien se parece a ${j.planta_predicha} (${j.confianza}%)`));

      if (ok) {
        const u = firebase.auth().currentUser;
        if (u) await guardarProgreso(u.uid, planta);
      }

      actualizarProgreso();
    } catch (err) {
      console.error(err);
      estadoEl.textContent = "🔴 Error";
      alert("❌ Error al analizar la imagen.");
    }
  };

  inp.click();
});

// 🔹 Mostrar/ocultar detalles de planta
function toggleInfo(id, boton) {
  const info = document.getElementById(id);
  if (!info) return;
  document.querySelectorAll(".info-extra").forEach(el => {
    if (el !== info) el.classList.remove("mostrar");
  });
  info.classList.toggle("mostrar");
  boton.textContent = info.classList.contains("mostrar") ? "Ocultar" : "Detalles";
}

// 🔹 Inicialización principal
document.addEventListener("DOMContentLoaded", () => {
  firebase.auth().onAuthStateChanged(async user => {
    const uid = user?.uid || null;
    await cargarProgresoDesdeFirestore(uid);
    await cargarPlantasYProgreso(uid);
    sincronizarProgresoPendiente();
  });
});

// 🔹 Detecta reconexión
window.addEventListener("online", sincronizarProgresoPendiente);
