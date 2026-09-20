// bulkwatch-upload: accepts a CSV from the site's upload form (no auth) and
// commits it to inbox/<person>/ on GitHub; the merge action takes it from there.
// Secret required: GITHUB_TOKEN (fine-grained PAT, contents:write on lcvaleski/bulkwatch only).

const REPO = "lcvaleski/bulkwatch";
const PEOPLE = ["logan", "felix"];
const ORIGINS = ["https://logan.valeski.org", "https://lcvaleski.github.io", "http://localhost:8749"];
const MAX_BYTES = 2_000_000;

function cors(req) {
  const origin = req.headers.get("origin");
  return {
    "access-control-allow-origin": ORIGINS.includes(origin) ? origin : ORIGINS[0],
    "access-control-allow-methods": "POST, OPTIONS",
    "access-control-allow-headers": "content-type",
  };
}

function reply(req, status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...cors(req), "content-type": "application/json" },
  });
}

export default {
  async fetch(req, env) {
    if (req.method === "OPTIONS") return new Response(null, { headers: cors(req) });
    if (req.method !== "POST") return reply(req, 405, { error: "POST only" });

    let form;
    try {
      form = await req.formData();
    } catch {
      return reply(req, 400, { error: "expected multipart form data" });
    }
    const person = form.get("person");
    const file = form.get("file");
    if (!PEOPLE.includes(person)) return reply(req, 400, { error: "pick logan or felix" });

    // manual weigh-in (with optional backfill date) instead of a file
    const weight = form.get("weight");
    if (weight !== null && weight !== "") {
      const w = parseFloat(weight);
      const date = form.get("date") || "";
      if (!(w >= 80 && w <= 400)) return reply(req, 400, { error: "weight looks wrong (80-400 lb)" });
      if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return reply(req, 400, { error: "bad date" });
      if (date > new Date().toISOString().slice(0, 10)) return reply(req, 400, { error: "no future weigh-ins" });
      const csv = `date,type,entry,calories\n${date},weight,${w},\n`;
      const path = `inbox/${person}/weight-${Date.now()}.csv`;
      const r = await fetch(`https://api.github.com/repos/${REPO}/contents/${path}`, {
        method: "PUT",
        headers: {
          authorization: `Bearer ${env.GITHUB_TOKEN}`,
          "user-agent": "bulkwatch-upload-worker",
          accept: "application/vnd.github+json",
        },
        body: JSON.stringify({ message: `weigh-in for ${person}: ${w} lb on ${date}`, content: btoa(csv) }),
      });
      if (!r.ok) return reply(req, 502, { error: `github said ${r.status}` });
      return reply(req, 200, { ok: true });
    }

    if (!file || typeof file === "string") return reply(req, 400, { error: "no file attached" });
    if (file.size > MAX_BYTES) return reply(req, 400, { error: "file too big (2MB max)" });

    const buf = new Uint8Array(await file.arrayBuffer());
    const isZip = buf[0] === 0x50 && buf[1] === 0x4b;
    if (!isZip) {
      const head = new TextDecoder().decode(buf.slice(0, 300)).toLowerCase();
      if (!head.includes("date") || !head.includes("calories")) {
        return reply(req, 400, { error: "that doesn't look like a mist export" });
      }
    }

    let bin = "";
    for (let i = 0; i < buf.length; i += 8192) {
      bin += String.fromCharCode(...buf.subarray(i, i + 8192));
    }
    const path = `inbox/${person}/web-${Date.now()}.${isZip ? "zip" : "csv"}`;
    const r = await fetch(`https://api.github.com/repos/${REPO}/contents/${path}`, {
      method: "PUT",
      headers: {
        authorization: `Bearer ${env.GITHUB_TOKEN}`,
        "user-agent": "bulkwatch-upload-worker",
        accept: "application/vnd.github+json",
      },
      body: JSON.stringify({ message: `web upload for ${person}`, content: btoa(bin) }),
    });
    if (!r.ok) return reply(req, 502, { error: `github said ${r.status}` });
    return reply(req, 200, { ok: true });
  },
};
