const $ = (id) => document.getElementById(id);

async function load() {
  const config = await chrome.storage.local.get(["backend", "source", "secret"]);
  $("backend").value = config.backend || "http://127.0.0.1:8010";
  $("source").value = config.source || "";
  $("secret").value = config.secret || "";
}

async function sign(secret, text) {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(text));
  return [...new Uint8Array(signature)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function backendUrl() {
  return $("backend").value.trim().replace(/\/$/, "");
}

$("save").onclick = async () => {
  await chrome.storage.local.set({
    backend: backendUrl(),
    source: $("source").value.trim(),
    secret: $("secret").value,
  });
  $("status").textContent = "Configuração salva.";
};

$("send").onclick = async () => {
  try {
    if (!$("secret").value) throw new Error("Configure o token do helper.");
    $("status").textContent = "Capturando contexto…";
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const context = await chrome.tabs.sendMessage(tab.id, { type: "NANONI_CONTEXT" });
    if (!context?.ok) throw new Error(context?.error || "Contexto indisponível.");

    const body = JSON.stringify({
      source_id: $("source").value.trim() || null,
      manifest: context.manifest,
    });
    const signature = await sign($("secret").value, body);
    const response = await fetch(`${backendUrl()}/api/v1/content/helper/manifest`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Nanoni-Signature": signature },
      body,
    });
    if (!response.ok) throw new Error(`Contexto: HTTP ${response.status} — ${await response.text()}`);
    const candidate = await response.json();

    const selectedFiles = [...$("files").files];
    if (selectedFiles.length) {
      $("status").textContent = "Enviando arquivos autorizados…";
      const timestamp = Math.floor(Date.now() / 1000).toString();
      const uploadSignature = await sign(
        $("secret").value,
        `${timestamp}:${candidate.id}`,
      );
      const form = new FormData();
      selectedFiles.forEach((file) => form.append("files", file, file.name));
      const upload = await fetch(
        `${backendUrl()}/api/v1/content/helper/candidates/${candidate.id}/files`,
        {
          method: "POST",
          headers: {
            "X-Nanoni-Timestamp": timestamp,
            "X-Nanoni-Signature": uploadSignature,
          },
          body: form,
        },
      );
      if (!upload.ok) throw new Error(`Arquivos: HTTP ${upload.status} — ${await upload.text()}`);
      const imported = await upload.json();
      $("status").textContent = `Candidate ${candidate.id}\n${imported.asset_ids.length} arquivo(s) associado(s).`;
      return;
    }
    $("status").textContent = `Candidate ${candidate.id} criado. Adicione arquivos se necessário.`;
  } catch (error) {
    $("status").textContent = String(error);
  }
};

load();
