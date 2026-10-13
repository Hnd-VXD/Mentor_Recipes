// A Mentor that has used a recipe from this site says whether it worked: up or down.
// Like a report, a vote is signed by the sender's own key, names the recipe and the checksum of the
// exact text that was used, and is queued as a branch. tools/vote.py counts it: one vote for each key
// and recipe (a later one replaces an earlier one), a limit a day for each key, and only for the text
// that is published now.
const { branchWithFile } = require("./lib/github.js");
const { verify, rateFields } = require("./lib/verify.js");

function reply(status, body) {
  return { statusCode: status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" }, body: JSON.stringify(body) };
}

exports.handler = async (event) => {
  if (event.httpMethod !== "POST") return reply(405, { error: "POST only" });
  if (!(event.headers["content-type"] || "").includes("application/json")) return reply(415, { error: "JSON only" });
  if (Buffer.byteLength(event.body || "", "utf-8") > 2000) return reply(413, { error: "too long" });
  let body;
  try {
    body = JSON.parse(event.body || "");
  } catch (e) {
    return reply(400, { error: "not JSON" });
  }
  const id = typeof body.id === "string" ? body.id : "";
  const sha = typeof body.sha256 === "string" ? body.sha256.toLowerCase() : "";
  const vote = body.vote === "up" ? "up" : body.vote === "down" ? "down" : "";
  if (!/^[a-z0-9][a-z0-9-]{0,80}$/.test(id) || !/^[0-9a-f]{64}$/.test(sha) || !vote) return reply(422, { error: "not a vote" });

  const who = verify("rate", body, rateFields({ id, sha256: sha, vote }));
  if (!who.ok) return reply(who.status, { error: who.reason });

  const entry = { id, sha256: sha, vote, source: who.keyId, time: new Date().toISOString() };
  const name = `${Date.now().toString(36)}-${who.sigId.slice(0, 8)}`;
  try {
    // A report/ branch: the workflow already watches those; the file's folder says what it is.
    await branchWithFile(`report/${Math.floor(Date.now() / 1000)}-${who.sigId}`, `votes/${name}.json`, JSON.stringify(entry), `Vote ${name}`);
  } catch (e) {
    return reply(e && e.exists ? 409 : 502, { error: e && e.exists ? "that request was already made" : "it could not be queued; try again later" });
  }
  return reply(202, { ok: true, status: "queued" });
};
