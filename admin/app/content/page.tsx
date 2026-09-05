import ContentManager from "./content-manager";
import {api} from "../../lib/api";
import type {Candidate, Microniche, WatchStatus} from "../../lib/content-types";

export const dynamic = "force-dynamic";

export default async function ContentPage() {
  const [candidates, microniches, watchStatus] = await Promise.all([
    api<Candidate[]>("/api/v1/content/candidates"),
    api<Microniche[]>("/api/v1/admin-config/microniches"),
    api<WatchStatus>("/api/v1/content/watch-folder/status"),
  ]);
  return (
    <>
      <div className="eyebrow">Content Engine</div>
      <h1 className="title">Revisão de conteúdo</h1>
      <ContentManager
        initialCandidates={candidates ?? []}
        initialMicroniches={(microniches ?? []).filter(item => item.active)}
        initialWatchStatus={watchStatus}
      />
    </>
  );
}
