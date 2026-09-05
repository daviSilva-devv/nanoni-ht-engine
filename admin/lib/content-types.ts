export type Candidate = {
  id: string;
  source_id: string;
  source_item_id: string;
  source_url: string | null;
  title: string | null;
  caption: string | null;
  status: string;
  duplicate_classification: string;
  manifest: {
    source?: string;
    context?: string | null;
    source_url?: string | null;
    metadata?: Record<string, unknown>;
  } & Record<string, unknown>;
};

export type CandidateDetail = Candidate & {
  pack_id: string;
  import_classification: string;
};

export type MediaAsset = {
  id: string;
  media_type: string;
  original_filename: string | null;
  mime_type: string | null;
  duration: number | null;
  width: number | null;
  height: number | null;
  size: number | null;
  sha256: string | null;
  status: string;
  metadata_json: Record<string, unknown>;
};

export type PackItem = {
  id: string;
  position: number;
  selected: boolean;
  role: string;
  source_id: string | null;
  source_external_id: string | null;
  source_reference: string | null;
  original_filename: string | null;
  metadata: Record<string, unknown>;
  asset: MediaAsset;
};

export type ContentPack = {
  id: string;
  candidate_id: string | null;
  title: string | null;
  caption: string | null;
  status: string;
  approved: boolean;
  archived: boolean;
  metadata: Record<string, unknown>;
  tags: string[];
  microniche_ids: string[];
  items: PackItem[];
};

export type Microniche = {
  id: string;
  name: string;
  slug: string;
  active: boolean;
};

export type WatchStatus = {
  folders: Record<string, string>;
  counts: Record<string, number>;
};
