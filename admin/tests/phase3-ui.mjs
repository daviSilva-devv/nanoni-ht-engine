import {existsSync} from "node:fs";
import process from "node:process";

import {chromium} from "playwright-core";

const adminUrl = process.env.NANONI_ADMIN_URL ?? "http://127.0.0.1:3100";
const backendUrl = process.env.NANONI_BACKEND_URL ?? "http://127.0.0.1:8010";
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

async function waitForNotice(page, kind, text) {
  await page.locator(`.notice.${kind}`).filter({hasText: text}).waitFor({state: "visible"});
}

function physicalCount(text) {
  const match = text.match(/Blobs físicos:\s*(\d+)/);
  if (!match) throw new Error(`Contagem física indisponível: ${text}`);
  return Number(match[1]);
}

async function networkStatus(page) {
  const response = await page.request.get(`${backendUrl}/__test__/network-status`);
  assert(response.ok(), `Status do servidor fixture retornou ${response.status()}.`);
  return response.json();
}

async function inspect(page, locator) {
  await page.getByTestId("erome-url").fill(locator);
  await page.getByRole("button", {name: "Inspect", exact: true}).click();
  await waitForNotice(page, "ok", "sem download");
  assert((await page.getByTestId("manifest-count").textContent()) === "4 itens", "Manifest não contém quatro itens.");
  const types = await page.getByTestId("erome-manifest").locator("li strong").allTextContents();
  assert(types.join(",") === "IMAGE,VIDEO,IMAGE,VIDEO", `Ordem/tipos inesperados: ${types}`);
}

async function importManifest(page, classification) {
  await page.getByRole("button", {name: "Importar manifesto"}).click();
  await waitForNotice(page, "ok", classification);
  assert((await page.getByTestId("item-count").textContent()) === "4", "Pack importado não contém quatro itens.");
}

async function selectPositions(page, positions) {
  const selected = page.getByTestId("item-selected");
  for (let index = 0; index < await selected.count(); index += 1) {
    if (positions.includes(index + 1)) await selected.nth(index).check();
    else await selected.nth(index).uncheck();
  }
}

async function acquire(page) {
  await page.getByTestId("acquire-selected").click();
  await waitForNotice(page, "ok", "Aquisição concluída");
}

const browser = await chromium.launch({headless: true, executablePath});
const page = await browser.newPage();
const browserErrors = [];
page.on("pageerror", error => browserErrors.push(error.message));

try {
  await page.goto(`${adminUrl}/content`);
  await page.waitForFunction(() => /Blobs físicos:\s*\d+/.test(
    document.querySelector('[data-testid="physical-count"]')?.textContent ?? "",
  ));
  const initialCandidates = await page.locator(".candidate-list .candidate").count();
  const initialPhysical = physicalCount(await page.getByTestId("physical-count").innerText());

  await inspect(page, "https://www.erome.com/a/phase3b-one");
  assert((await page.locator(".candidate-list .candidate").count()) === initialCandidates, "Inspect criou Candidate indevidamente.");
  let network = await networkStatus(page);
  assert(network.media === 0, `Inspect baixou mídia: ${network.media} request(s).`);

  await importManifest(page, "NEW");
  assert((await page.locator(".candidate-list .candidate").count()) === initialCandidates + 1, "Import não criou exatamente um Candidate.");
  assert((await page.getByTestId("media-pending").allTextContents()).every(status => status === "DISCOVERED"), "Item remoto não iniciou como DISCOVERED.");
  assert(physicalCount(await page.getByTestId("physical-count").innerText()) === initialPhysical, "Inspect/import criou blob antes da aquisição.");

  await selectPositions(page, [1, 2]);
  await acquire(page);
  let statuses = await page.getByTestId("pack-items").locator(".asset-facts div:nth-child(4) dd").allTextContents();
  assert(statuses.join(",") === "LOCAL_READY,LOCAL_READY,DISCOVERED,DISCOVERED", `Subset incorreto: ${statuses}`);
  assert((await page.getByTestId("pack-items").locator(".pack-item").count()) === 4, "Itens não selecionados desapareceram.");
  const image = page.getByTestId("image-preview").first();
  await image.waitFor();
  assert(await image.evaluate(element => element.complete && element.naturalWidth > 0), "Preview local não carregou.");
  network = await networkStatus(page);
  assert(network.media === 3, `Retry esperado deveria totalizar três requests, recebeu ${network.media}.`);
  const physicalAfterFirst = physicalCount(await page.getByTestId("physical-count").innerText());
  assert(physicalAfterFirst === initialPhysical + 2, "Subset não criou exatamente dois blobs físicos.");

  await acquire(page);
  assert((await networkStatus(page)).media === network.media, "Retry idempotente baixou mídia novamente.");
  assert(physicalCount(await page.getByTestId("physical-count").innerText()) === physicalAfterFirst, "Retry idempotente duplicou blob.");

  await importManifest(page, "SAME_SOURCE_ITEM");
  await inspect(page, "https://www.erome.com/a/phase3b-two");
  await importManifest(page, "NEW");
  await selectPositions(page, [1]);
  await acquire(page);
  await page.getByTestId("duplicate-classification").filter({hasText: "SAME_SHA256"}).waitFor();
  assert(physicalCount(await page.getByTestId("physical-count").innerText()) === physicalAfterFirst, "SAME_SHA256 duplicou blob físico.");

  await page.getByTestId("erome-url").fill("http://127.0.0.1/private");
  await page.getByRole("button", {name: "Inspect", exact: true}).click();
  await waitForNotice(page, "error", "unsupported Erome");
  assert(browserErrors.length === 0, `Erros no browser: ${browserErrors.join("; ")}`);
  console.log("PHASE 3B UI GATE = GREEN");
  console.log("INSPECT ZERO DOWNLOAD = GREEN");
  console.log("SELECTIVE ACQUISITION + RETRY + DEDUPE = GREEN");
} finally {
  await browser.close();
}
