"use client";

import {FormEvent, useState} from "react";

import type {
  Candidate,
  CandidateDetail,
  ContentPack,
  MediaManifest,
  Microniche,
  PackItem,
  SelectedAcquisition,
  WatchStatus,
} from "../../lib/content-types";

type Notice = {kind: "ok" | "error"; text: string};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/content/${path}`, {...init, cache: "no-store"});
  if (!response.ok) {
    let detail = `Erro ${response.status}`;
    try {
      const body = (await response.json()) as {detail?: unknown};
      if (typeof body.detail === "string") detail = body.detail;
      else if (
        body.detail &&
        typeof body.detail === "object" &&
        "message" in body.detail &&
        typeof body.detail.message === "string"
      ) detail = body.detail.message;
    } catch {}
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

function formatBytes(size: number | null) {
  if (size === null) return "—";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function metadataText(item: PackItem) {
  const metadata = {...item.asset.metadata_json, ...item.metadata};
  return Object.keys(metadata).length ? JSON.stringify(metadata) : "Sem metadata adicional";
}

export default function ContentManager({
  initialCandidates,
  initialMicroniches,
  initialWatchStatus,
}: {
  initialCandidates: Candidate[];
  initialMicroniches: Microniche[];
  initialWatchStatus: WatchStatus | null;
}) {
  const [candidates, setCandidates] = useState(initialCandidates);
  const [candidate, setCandidate] = useState<CandidateDetail | null>(null);
  const [pack, setPack] = useState<ContentPack | null>(null);
  const [items, setItems] = useState<PackItem[]>([]);
  const [tags, setTags] = useState("");
  const [micronicheIds, setMicronicheIds] = useState<string[]>([]);
  const [watchStatus, setWatchStatus] = useState(initialWatchStatus);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [dedupeResult, setDedupeResult] = useState<string | null>(null);
  const [eromeUrl, setEromeUrl] = useState("");
  const [eromeManifest, setEromeManifest] = useState<MediaManifest | null>(null);

  const selectedCount = items.reduce((total, item) => total + Number(item.selected), 0);
  const physicalCount = watchStatus
    ? (watchStatus.counts.processing ?? 0) + (watchStatus.counts.ready ?? 0)
    : null;

  const applyPack = (nextPack: ContentPack) => {
    setPack(nextPack);
    setItems(nextPack.items);
    setTags(nextPack.tags.join(", "));
    setMicronicheIds(nextPack.microniche_ids);
  };

  const refreshOverview = async () => {
    const [nextCandidates, nextStatus] = await Promise.all([
      request<Candidate[]>("candidates"),
      request<WatchStatus>("watch-folder/status"),
    ]);
    setCandidates(nextCandidates);
    setWatchStatus(nextStatus);
  };

  const openCandidate = async (candidateId: string) => {
    setBusy("open");
    setNotice(null);
    try {
      const detail = await request<CandidateDetail>(`candidates/${candidateId}`);
      const nextPack = await request<ContentPack>(`packs/${detail.pack_id}`);
      setCandidate(detail);
      applyPack(nextPack);
      setDedupeResult(null);
    } catch (error) {
      setNotice({kind: "error", text: (error as Error).message});
    } finally {
      setBusy(null);
    }
  };

  const upload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.elements.namedItem("files") as HTMLInputElement;
    const fileCount = input.files?.length ?? 0;
    if (!fileCount) return;
    setBusy("upload");
    setNotice(null);
    try {
      const imported = await request<CandidateDetail>("manual-import", {
        method: "POST",
        body: new FormData(form),
      });
      await refreshOverview();
      await openCandidate(imported.id);
      form.reset();
      setNotice({
        kind: "ok",
        text: `${imported.pack_id}: ${fileCount} itens importados (${imported.import_classification}).`,
      });
    } catch (error) {
      setNotice({kind: "error", text: (error as Error).message});
    } finally {
      setBusy(null);
    }
  };

  const inspectErome = async () => {
    setBusy("erome-inspect");
    setNotice(null);
    try {
      const manifest = await request<MediaManifest>("erome/inspect", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({locator: eromeUrl.trim()}),
      });
      setEromeManifest(manifest);
      setNotice({kind: "ok", text: `Inspect concluído: ${manifest.media.length} itens, sem download.`});
    } catch (error) {
      setEromeManifest(null);
      setNotice({kind: "error", text: (error as Error).message});
    } finally {
      setBusy(null);
    }
  };

  const importErome = async () => {
    setBusy("erome-import");
    setNotice(null);
    try {
      const imported = await request<CandidateDetail>("erome/import", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({locator: eromeUrl.trim()}),
      });
      await Promise.all([refreshOverview(), openCandidate(imported.id)]);
      setNotice({kind: "ok", text: `Erome importado: ${imported.import_classification}.`});
    } catch (error) {
      setNotice({kind: "error", text: (error as Error).message});
    } finally {
      setBusy(null);
    }
  };

  const toggleItem = (itemId: string) => {
    setItems(current =>
      current.map(item => (item.id === itemId ? {...item, selected: !item.selected} : item)),
    );
  };

  const moveItem = (index: number, direction: -1 | 1) => {
    setItems(current => {
      const target = index + direction;
      if (target < 0 || target >= current.length) return current;
      const reordered = [...current];
      [reordered[index], reordered[target]] = [reordered[target], reordered[index]];
      return reordered.map((item, position) => ({...item, position: position + 1}));
    });
  };

  const toggleMicroniche = (id: string) => {
    setMicronicheIds(current =>
      current.includes(id) ? current.filter(item => item !== id) : [...current, id],
    );
  };

  const saveReview = async () => {
    if (!pack) throw new Error("Nenhum pack aberto.");
    await request<ContentPack>(`packs/${pack.id}/order`, {
      method: "PUT",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({item_ids: items.map(item => item.id)}),
    });
    const selectedPositions = items
      .map((item, index) => (item.selected ? index + 1 : null))
      .filter((position): position is number => position !== null);
    const tagNames = tags.split(",").map(tag => tag.trim()).filter(Boolean);
    const [savedPack] = await Promise.all([
      request<ContentPack>(`packs/${pack.id}/selection`, {
        method: "PUT",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({selected_positions: selectedPositions}),
      }),
      request<ContentPack>(`packs/${pack.id}`, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({tags: tagNames, microniche_ids: micronicheIds}),
      }),
    ]);
    const refreshed = await request<ContentPack>(`packs/${savedPack.id}`);
    applyPack(refreshed);
    return {selectedPositions};
  };

  const save = async () => {
    setBusy("save");
    setNotice(null);
    try {
      await saveReview();
      setNotice({kind: "ok", text: "Revisão salva."});
    } catch (error) {
      setNotice({kind: "error", text: (error as Error).message});
    } finally {
      setBusy(null);
    }
  };

  const decide = async (decision: "approve" | "reject" | "defer") => {
    if (!candidate) return;
    setBusy(decision);
    setNotice(null);
    try {
      const {selectedPositions} = await saveReview();
      if (decision === "approve" && selectedPositions.length === 0) {
        throw new Error("Selecione ao menos um item antes de aprovar.");
      }
      await request(`candidates/${candidate.id}/${decision}`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({selected_positions: selectedPositions, microniche_ids: micronicheIds}),
      });
      await Promise.all([openCandidate(candidate.id), refreshOverview()]);
      setNotice({kind: "ok", text: `Decisão registrada: ${decision}.`});
    } catch (error) {
      setNotice({kind: "error", text: (error as Error).message});
    } finally {
      setBusy(null);
    }
  };

  const classifyDuplicate = async () => {
    if (!candidate) return;
    setBusy("dedupe");
    try {
      const result = await request<{classification: string}>("duplicates/classify", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({source_id: candidate.source_id, manifest: candidate.manifest}),
      });
      setDedupeResult(result.classification);
    } catch (error) {
      setNotice({kind: "error", text: (error as Error).message});
    } finally {
      setBusy(null);
    }
  };

  const waitForAcquisition = async (packId: string) => {
    for (let attempt = 0; attempt < 120; attempt += 1) {
      const current = await request<ContentPack>(`packs/${packId}`);
      applyPack(current);
      const selected = current.items.filter(item => item.selected);
      if (selected.every(item => ["LOCAL_READY", "FAILED"].includes(item.asset.status))) {
        return current;
      }
      await new Promise(resolve => setTimeout(resolve, 250));
    }
    throw new Error("Aquisição ainda não terminou; consulte novamente o status.");
  };

  const acquireSelected = async () => {
    if (!pack || !candidate) return;
    setBusy("acquire");
    setNotice(null);
    try {
      const {selectedPositions} = await saveReview();
      if (!selectedPositions.length) throw new Error("Selecione ao menos um item para adquirir.");
      const queued = await request<SelectedAcquisition>(`packs/${pack.id}/acquire-selected`, {
        method: "POST",
      });
      const acquired = await waitForAcquisition(pack.id);
      applyPack(acquired);
      const [detail, nextCandidates, nextStatus] = await Promise.all([
        request<CandidateDetail>(`candidates/${candidate.id}`),
        request<Candidate[]>("candidates"),
        request<WatchStatus>("watch-folder/status"),
      ]);
      setCandidate(detail);
      setCandidates(nextCandidates);
      setWatchStatus(nextStatus);
      const failed = acquired.items.filter(
        item => item.selected && item.asset.status === "FAILED",
      );
      if (failed.length) throw new Error(`${failed.length} item(ns) falharam na aquisição.`);
      setNotice({kind: "ok", text: `Aquisição concluída (${queued.jobs.length} job(s) novo(s)).`});
    } catch (error) {
      setNotice({kind: "error", text: (error as Error).message});
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="content-workflow">
      <section className="card erome-import">
        <div className="row">
          <div><h2>Erome público</h2><p className="muted">Inspecione o manifesto primeiro; nenhum arquivo de mídia é baixado nesta etapa.</p></div>
        </div>
        <div className="erome-controls">
          <label><span>URL do álbum</span><input data-testid="erome-url" type="url" value={eromeUrl} onChange={event => setEromeUrl(event.target.value)} placeholder="https://www.erome.com/a/..." /></label>
          <button className="button secondary" type="button" onClick={inspectErome} disabled={busy !== null || !eromeUrl.trim()}>{busy === "erome-inspect" ? "Inspecionando…" : "Inspect"}</button>
          <button className="button primary" type="button" onClick={importErome} disabled={busy !== null || !eromeManifest || eromeManifest.source_url !== eromeUrl.trim()}>{busy === "erome-import" ? "Importando…" : "Importar manifesto"}</button>
        </div>
        {eromeManifest ? (
          <div className="manifest-result" data-testid="erome-manifest">
            <div className="row"><strong>{eromeManifest.title ?? eromeManifest.source_external_id}</strong><span className="pill" data-testid="manifest-count">{eromeManifest.media.length} itens</span></div>
            <ol>{eromeManifest.media.map((item, index) => <li key={item.external_item_id ?? `${item.source_reference}-${index}`}><span>{index + 1}</span><strong>{item.media_type}</strong><span>{item.original_filename ?? "sem nome"}</span></li>)}</ol>
          </div>
        ) : null}
      </section>
      <section className="card content-import">
        <div className="row">
          <div><h2>Importação manual</h2><p className="muted">Envie imagens e vídeos juntos para criar um único pack.</p></div>
          <button className="button secondary" type="button" onClick={refreshOverview}>Atualizar</button>
        </div>
        <form className="upload-form" onSubmit={upload}>
          <label><span>Título opcional</span><input name="title" placeholder="Identifique este pack" /></label>
          <label className="file-input"><span>Arquivos</span><input name="files" type="file" accept="image/*,video/*" multiple required /></label>
          <button className="button primary" disabled={busy !== null}>{busy === "upload" ? "Importando…" : "Importar arquivos"}</button>
        </form>
        {notice ? <div className={`notice ${notice.kind}`} role={notice.kind === "error" ? "alert" : "status"}>{notice.text}</div> : null}
        <div className="physical-summary" data-testid="physical-count">
          <span>Processing: {watchStatus?.counts.processing ?? "—"}</span><span>Ready: {watchStatus?.counts.ready ?? "—"}</span><span>Blobs físicos: {physicalCount ?? "—"}</span>
        </div>
      </section>

      <div className="content-columns">
        <section className="card candidate-queue">
          <div className="row"><h2>Candidates</h2><span className="pill">{candidates.length}</span></div>
          <div className="candidate-list" data-testid="candidate-list">
            {candidates.map(row => (
              <button type="button" className={candidate?.id === row.id ? "candidate active" : "candidate"} key={row.id} onClick={() => openCandidate(row.id)}>
                <strong>{row.title ?? row.id}</strong><span>{row.status}</span><small>{row.duplicate_classification}</small>
              </button>
            ))}
            {!candidates.length ? <div className="empty">Nenhum candidate.</div> : null}
          </div>
        </section>

        <section className="card pack-review" aria-busy={busy === "open"}>
          {!candidate || !pack ? <div className="empty">Selecione um candidate para revisar.</div> : (
            <>
              <header className="review-header">
                <div><div className="eyebrow">Candidate / ContentPack</div><h2 data-testid="pack-title">{pack.title ?? candidate.id}</h2><p className="muted">{candidate.caption ?? "Sem legenda"}</p></div>
                <div className="review-statuses"><span className={`status-chip ${pack.status.toLowerCase()}`} data-testid="pack-status">{pack.status}</span><span className="status-chip" data-testid="duplicate-classification">{candidate.duplicate_classification}</span></div>
              </header>
              <dl className="candidate-facts">
                <div><dt>Origem</dt><dd>{String(candidate.manifest.source ?? candidate.source_url ?? "manual")}</dd></div>
                <div><dt>Source item</dt><dd>{candidate.source_item_id}</dd></div>
                <div><dt>Itens</dt><dd data-testid="item-count">{items.length}</dd></div>
                <div><dt>Selecionados</dt><dd>{selectedCount}</dd></div>
              </dl>
              <div className="review-fields">
                <label><span>Tags, separadas por vírgula</span><input data-testid="tags-input" value={tags} onChange={event => setTags(event.target.value)} /></label>
                <fieldset><legend>Microniches</legend><div className="microniche-options">
                  {initialMicroniches.map(option => <label key={option.id}><input type="checkbox" checked={micronicheIds.includes(option.id)} onChange={() => toggleMicroniche(option.id)} data-testid={`microniche-${option.slug}`} />{option.name}</label>)}
                  {!initialMicroniches.length ? <span className="muted">Nenhum microniche ativo.</span> : null}
                </div></fieldset>
              </div>
              <div className="pack-items" data-testid="pack-items">
                {items.map((item, index) => {
                  const filename = item.original_filename ?? item.asset.original_filename ?? item.id;
                  const previewUrl = `/api/content/assets/${item.asset.id}/original`;
                  return <article className={item.selected ? "pack-item selected" : "pack-item"} key={item.id} data-item-id={item.id}>
                    <div className="media-preview">{item.asset.status !== "LOCAL_READY" ? <div className="media-pending" data-testid="media-pending">{item.asset.status}</div> : item.asset.media_type === "VIDEO" ? <video controls preload="metadata" src={previewUrl} data-testid="video-preview" /> : <img src={previewUrl} alt={`Preview de ${filename}`} data-testid="image-preview" />}</div>
                    <div className="item-toolbar"><label><input type="checkbox" checked={item.selected} onChange={() => toggleItem(item.id)} data-testid="item-selected" />Selecionado</label><div><button type="button" onClick={() => moveItem(index, -1)} disabled={index === 0} aria-label={`Mover ${filename} para cima`}>↑</button><button type="button" onClick={() => moveItem(index, 1)} disabled={index === items.length - 1} aria-label={`Mover ${filename} para baixo`}>↓</button></div></div>
                    <h3 data-testid="item-filename">{filename}</h3>
                    <dl className="asset-facts"><div><dt>Ordem</dt><dd data-testid="item-position">{index + 1}</dd></div><div><dt>Tipo</dt><dd>{item.asset.media_type}</dd></div><div><dt>Tamanho</dt><dd>{formatBytes(item.asset.size)}</dd></div><div><dt>Físico</dt><dd>{item.asset.status}</dd></div></dl>
                    <details><summary>Metadata e origem</summary><code>{metadataText(item)}</code><code>{item.source_reference ?? "—"}</code></details>
                  </article>;
                })}
              </div>
              <div className="review-actions">
                <button className="button secondary" type="button" onClick={classifyDuplicate} disabled={busy !== null}>Classificar duplicate</button>
                {dedupeResult ? <strong data-testid="dedupe-result">{dedupeResult}</strong> : null}<span className="action-spacer" />
                <button className="button secondary" type="button" onClick={save} disabled={busy !== null}>Salvar revisão</button>
                {candidate.manifest.source === "erome" ? <button className="button secondary" type="button" onClick={acquireSelected} disabled={busy !== null || selectedCount === 0} data-testid="acquire-selected">{busy === "acquire" ? "Adquirindo…" : "Acquire Selected"}</button> : null}
                <button className="button secondary" type="button" onClick={() => decide("defer")} disabled={busy !== null}>Deferir</button>
                <button className="button danger-button" type="button" onClick={() => decide("reject")} disabled={busy !== null}>Rejeitar</button>
                <button className="button primary" type="button" onClick={() => decide("approve")} disabled={busy !== null || selectedCount === 0}>Aprovar</button>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
