// A Mentor that has looked at a recipe from this site and found it harmful reports it here.
// Nothing is taken on trust: the report names the recipe and its checksum, and tools/takedown.py
// looks at that exact text again with the same rules. One that fails them goes at once; a
// suspicion that rules cannot show needs several different sources, and is undone as easily.
const { branchWithFile } = require("./lib/github.js");
const { verify, reportFields } = require("./lib/verify.js");

function reply(status, body) {
  return { statusCode: status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" }, body: JSON.stringify(body) };
}

exports.handler = async (event) => {
  if (event.httpMethod !== "POST") return reply(405, { error: "POST only" });
  if (!(event.headers["content-type"] || "").includes("application/json")) return reply(415, { error: "JSON only" });
  if (Buffer.byteLength(event.body || "", "utf-8") > 8000) return reply(413, { error: "too long" });
  let body;
  try {
    body = JSON.parse(event.body || "");
  } catch (e) {
    return reply(400, { error: "not JSON" });
  }
  const id = typeof body.id === "string" ? body.id : "";
  const sha = typeof body.sha256 === "string" ? body.sha256.toLowerCase() : "";
  const kind = body.kind === "rules" ? "rules" : "reading";
  if (!/^[a-z0-9][a-z0-9-]{0,80}$/.test(id) || !/^[0-9a-f]{64}$/.test(sha)) return reply(422, { error: "not a report" });

  const who = verify("report", body, reportFields({ id, sha256: sha, kind }));
  if (!who.ok) return reply(who.status, { error: who.reason });

  const findings = body.findings && typeof body.findings === "object" ? body.findings : {};
  const report = {
    id,
    sha256: sha,
    kind,
    findings: { high: Number(findings.high) || 0, medium: Number(findings.medium) || 0 },
    // What the rules called it, in their own words: a short list, nothing of the user's.
    rules: Array.isArray(body.rules) ? body.rules.slice(0, 8).map((r) => String(r).slice(0, 120)) : [],
    source: who.keyId,
    time: new Date().toISOString(),
  };
  const name = `${Date.now().toString(36)}-${who.sigId.slice(0, 8)}`;
  try {
    await branchWithFile(`report/${Math.floor(Date.now() / 1000)}-${who.sigId}`, `reports/${name}.json`, JSON.stringify(report), `Report ${name}`);
  } catch (e) {
    return reply(e && e.exists ? 409 : 502, { error: e && e.exists ? "that request was already made" : "it could not be queued; try again later" });
  }
  return reply(202, { ok: true, status: "queued" });
};
