import {existsSync} from "node:fs";
import {mkdir, readFile, writeFile} from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import {fileURLToPath} from "node:url";

import {chromium} from "playwright-core";

const verifyOnly = process.argv.includes("--verify");
const adminUrl = process.env.NANONI_ADMIN_URL ?? "http://127.0.0.1:3100";
const testDirectory = path.dirname(fileURLToPath(import.meta.url));
const statePath = path.resolve(testDirectory, "../../runtime/phase2-ui-state.json");
const browserPaths = [
  process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
].filter(Boolean);
const executablePath = browserPaths.find(candidate => existsSync(candidate));

if (!executablePath) throw new Error("Nenhum Edge/Chrome local foi encontrado para o Playwright.");

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function imageFixture(page, color) {
  const base64 = await page.evaluate(value => {
    const canvas = document.createElement("canvas");
    canvas.width = 48;
    canvas.height = 48;
    const context = canvas.getContext("2d");
    context.fillStyle = value;
    context.fillRect(0, 0, 48, 48);
    return canvas.toDataURL("image/png").split(",")[1];
  }, color);
  return Buffer.from(base64, "base64");
}

async function videoFixture(page, color) {
  const bytes = await page.evaluate(async value => {
    const canvas = document.createElement("canvas");
    canvas.width = 96;
    canvas.height = 64;
    const context = canvas.getContext("2d");
    const stream = canvas.captureStream(12);
    const mimeType = MediaRecorder.isTypeSupported("video/webm;codecs=vp8")
      ? "video/webm;codecs=vp8"
      : "video/webm";
    const chunks = [];
    const recorder = new MediaRecorder(stream, {mimeType});
    recorder.ondataavailable = event => {
      if (event.data.size) chunks.push(event.data);
    };
    const stopped = new Promise(resolve => {
      recorder.onstop = resolve;
    });
    recorder.start();
    for (let frame = 0; frame < 12; frame += 1) {
      context.fillStyle = value;
      context.fillRect(0, 0, 96, 64);
      context.fillStyle = "white";
      context.font = "20px sans-serif";
      context.fillText(String(frame), 38, 38);
      await new Promise(resolve => setTimeout(resolve, 35));
    }
    recorder.stop();
    await stopped;
    stream.getTracks().forEach(track => track.stop());
    return Array.from(new Uint8Array(await new Blob(chunks, {type: mimeType}).arrayBuffer()));
  }, color);
  return Buffer.from(bytes);
}

async function waitForNotice(page, text) {
  await page.locator(".notice.ok").filter({hasText: text}).waitFor({state: "visible"});
}

async function phase1CreateAndEdit(page, state) {
  await page.goto(`${adminUrl}/configuration`);
  await page.locator(".admin-form").waitFor();
  const form = page.locator(".admin-form");
  await form.locator('input[type="text"]').nth(0).fill(state.nicheName);
  await form.locator('input[type="text"]').nth(1).fill(state.nicheSlug);
  await form.locator("textarea").fill("Criado pelo gate Phase 1");
  await form.locator('input[type="number"]').fill("90");
  await form.getByRole("button", {name: "Criar"}).click();
  await waitForNotice(page, "salvo com sucesso");

  const nicheRow = page.locator("tbody tr").filter({hasText: state.nicheName});
  await nicheRow.getByRole("button", {name: "Editar"}).click();
  await form.locator("textarea").fill(state.nicheDescription);
  await form.getByRole("button", {name: "Salvar alterações"}).click();
  await waitForNotice(page, "salvo com sucesso");

  await page.locator(".config-nav").getByRole("button", {name: /Micronichos/}).click();
  await form.locator("select").selectOption({label: state.nicheName});
  await form.locator('input[type="text"]').nth(0).fill(state.micronicheName);
  await form.locator('input[type="text"]').nth(1).fill(state.micronicheSlug);
  await form.locator("textarea").fill("Micronicho do gate E2E");
  await form.locator('input[type="number"]').fill("90");
  await form.getByRole("button", {name: "Criar"}).click();
  await waitForNotice(page, "salvo com sucesso");
  await page.reload();
  await page.locator("tbody tr").filter({hasText: state.nicheName}).waitFor();
  await page.locator("tbody tr").filter({hasText: state.nicheDescription}).waitFor();
}

async function phase1Verify(page, state) {
  await page.goto(`${adminUrl}/configuration`);
  await page.locator("tbody tr").filter({hasText: state.nicheName}).waitFor();
  await page.locator("tbody tr").filter({hasText: state.nicheDescription}).waitFor();
}

async function assertPreviewsAndRange(page) {
  const image = page.getByTestId("image-preview").first();
  await image.waitFor();
  assert(await image.evaluate(element => element.complete && element.naturalWidth > 0), "Preview de imagem não carregou.");

  const video = page.getByTestId("video-preview").first();
  await video.waitFor();
  await video.evaluate(async element => {
    element.muted = true;
    await element.play();
    await new Promise(resolve => setTimeout(resolve, 80));
    element.pause();
  });
  const source = await video.getAttribute("src");
  const response = await page.request.get(new URL(source, adminUrl).toString(), {
    headers: {Range: "bytes=0-31"},
  });
  assert(response.status() === 206, `Range do vídeo retornou ${response.status()}, esperado 206.`);
  assert(Boolean(response.headers()["content-range"]), "Range do vídeo não retornou Content-Range.");
}

function physicalCount(text) {
  const match = text.match(/Blobs físicos:\s*(\d+)/);
  if (!match) throw new Error(`Contagem física indisponível: ${text}`);
  return Number(match[1]);
}

async function phase2Run(page, state) {
  await page.goto("about:blank");
  const fixtures = [
    {name: "image-a.png", mimeType: "image/png", buffer: await imageFixture(page, "#dc2626")},
    {name: "image-b.png", mimeType: "image/png", buffer: await imageFixture(page, "#2563eb")},
    {name: "video-a.webm", mimeType: "video/webm", buffer: await videoFixture(page, "#15803d")},
    {name: "video-b.webm", mimeType: "video/webm", buffer: await videoFixture(page, "#7e22ce")},
  ];

  await page.goto(`${adminUrl}/content`);
  await page.locator('input[name="title"]').fill(state.packTitle);
  await page.locator('input[name="files"]').setInputFiles(fixtures);
  await page.getByRole("button", {name: "Importar arquivos"}).click();
  await waitForNotice(page, "4 itens importados");
  assert((await page.locator(".candidate-list .candidate").count()) === 1, "A operação não criou exatamente um Candidate.");
  assert((await page.getByTestId("item-count").textContent()) === "4", "O Pack não contém quatro itens.");
  assert((await page.getByTestId("pack-items").locator(".pack-item").count()) === 4, "A UI não preservou os quatro PackItems.");
  await assertPreviewsAndRange(page);

  const selected = page.getByTestId("item-selected");
  await selected.nth(1).uncheck();
  await selected.nth(3).uncheck();
  await page.getByRole("button", {name: "Mover video-b.webm para cima"}).click();
  await page.getByRole("button", {name: "Mover video-b.webm para cima"}).click();
  await page.getByTestId(`microniche-${state.micronicheSlug}`).check();
  await page.getByTestId("tags-input").fill(state.tag);
  await page.getByRole("button", {name: "Salvar revisão"}).click();
  await waitForNotice(page, "Revisão salva");

  const orderedNames = await page.getByTestId("item-filename").allTextContents();
  assert(orderedNames.join("|") === "image-a.png|video-b.webm|image-b.png|video-a.webm", `Ordem inesperada: ${orderedNames.join("|")}`);
  assert((await page.getByTestId("pack-items").locator(".pack-item").count()) === 4, "Itens não selecionados desapareceram.");
  const selection = await page.getByTestId("item-selected").evaluateAll(inputs => inputs.map(input => input.checked));
  assert(selection.join(",") === "true,false,false,true", `Seleção inesperada: ${selection.join(",")}`);

  await page.getByRole("button", {name: "Classificar duplicate"}).click();
  await page.getByTestId("dedupe-result").filter({hasText: "SAME_SOURCE_ITEM"}).waitFor();
  await page.getByRole("button", {name: "Aprovar"}).click();
  await page.getByTestId("pack-status").filter({hasText: "READY"}).waitFor();
  const blobsBeforeDuplicate = physicalCount(await page.getByTestId("physical-count").innerText());

  await page.locator('input[name="title"]').fill(`${state.packTitle} SHA duplicate`);
  await page.locator('input[name="files"]').setInputFiles([fixtures[0]]);
  await page.getByRole("button", {name: "Importar arquivos"}).click();
  await waitForNotice(page, "SAME_SHA256");
  await page.getByTestId("duplicate-classification").filter({hasText: "SAME_SHA256"}).waitFor();
  assert((await page.getByTestId("item-count").textContent()) === "1", "A relação editorial SHA duplicate não foi criada.");
  const blobsAfterDuplicate = physicalCount(await page.getByTestId("physical-count").innerText());
  assert(blobsAfterDuplicate === blobsBeforeDuplicate, "SAME_SHA256 criou uma cópia física desnecessária.");
  await page.getByRole("button", {name: "Deferir"}).click();
  await waitForNotice(page, "defer");
  await page.getByRole("button", {name: "Rejeitar"}).click();
  await page.getByTestId("pack-status").filter({hasText: "REJECTED"}).waitFor();

  state.order = orderedNames;
  state.selection = selection;
  await mkdir(path.dirname(statePath), {recursive: true});
  await writeFile(statePath, `${JSON.stringify(state, null, 2)}\n`, "utf8");
}

async function phase2Verify(page, state) {
  await page.goto(`${adminUrl}/content`);
  await page.getByText(state.packTitle, {exact: true}).click();
  await page.getByTestId("pack-status").filter({hasText: "READY"}).waitFor();
  assert((await page.getByTestId("item-count").textContent()) === "4", "Pack não persistiu quatro itens após restart.");
  const order = await page.getByTestId("item-filename").allTextContents();
  assert(order.join("|") === state.order.join("|"), "Ordem não persistiu após restart.");
  const selection = await page.getByTestId("item-selected").evaluateAll(inputs => inputs.map(input => input.checked));
  assert(selection.join(",") === state.selection.join(","), "Seleção não persistiu após restart.");
  assert((await page.getByTestId("tags-input").inputValue()) === state.tag, "Tag não persistiu após restart.");
  assert(await page.getByTestId(`microniche-${state.micronicheSlug}`).isChecked(), "Microniche não persistiu após restart.");
  await assertPreviewsAndRange(page);
}

const browser = await chromium.launch({headless: true, executablePath});
const page = await browser.newPage();
const browserErrors = [];
page.on("pageerror", error => browserErrors.push(error.message));

try {
  if (verifyOnly) {
    const state = JSON.parse(await readFile(statePath, "utf8"));
    await phase1Verify(page, state);
    await phase2Verify(page, state);
    console.log("PHASE 1 UI RELOAD = GREEN");
    console.log("PHASE 2 RESTART VERIFY = GREEN");
  } else {
    const suffix = Date.now().toString(36);
    const state = {
      nicheName: `Gate Niche ${suffix}`,
      nicheSlug: `gate-niche-${suffix}`,
      nicheDescription: `Persisted edit ${suffix}`,
      micronicheName: `Gate Micro ${suffix}`,
      micronicheSlug: `gate-micro-${suffix}`,
      packTitle: `Phase 2 Pack ${suffix}`,
      tag: `phase2-${suffix}`,
    };
    await phase1CreateAndEdit(page, state);
    await phase2Run(page, state);
    console.log("PHASE 1 UI GATE = GREEN");
    console.log("PHASE 2 UI GATE = GREEN");
    console.log("DEDUPE SOURCE + SHA256 = GREEN");
  }
  assert(browserErrors.length === 0, `Erros no browser: ${browserErrors.join("; ")}`);
} finally {
  await browser.close();
}
