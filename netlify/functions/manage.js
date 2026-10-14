// The author of a recipe changes it: a new text ("update") or taking it off the site ("withdraw").
// Like everything else, the request is signed by the sender's own key and only queued here.
// tools/author.py then checks that this key is the one that published the recipe, puts a new text
// through the same rules as a new recipe, and applies it. Nobody can change a recipe that is not theirs.
const { branchWithFile } = require("./lib/github.js");
const { verify, updateFields, withdrawFields } = require("./lib/verify.js");

const MAX_BYTES = 120000;

function reply(status, body) {
  return { statusCode: status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" }, body: JSON.stringify(body) };
}

exports.handler = async (event) => {
  if (event.httpMethod !== "POST") return reply(405, { error: "POST only" });
  if (!(event.headers["content-type"] || "").includes("application/json")) return reply(415, { error: "JSON only" });
  if (Buffer.byteLength(event.body || "", "utf-8") > MAX_BYTES + 4000) return reply(413, { error: "too long" });
  let body;
  try {
    body = JSON.parse(event.body || "");
  } catch (e) {
    return reply(400, { error: "not JSON" });
  }
  const action = body.action === "update" ? "update" : body.action === "withdraw" ? "withdraw" : "";
  const id = typeof body.id === "string" ? body.id : "";
  if (!action || !/^[a-z0-9][a-z0-9-]{0,80}$/.test(id)) return reply(422, { error: "not a change" });
  let who;
  const change = { action, id };
  if (action === "update") {
    const recipe = typeof body.recipe === "string" ? body.recipe : "";
    if (!recipe.includes("## Steps") || !recipe.includes("## Check that it works")) return reply(422, { error: "not in the form of a recipe" });
    if (Buffer.byteLength(recipe, "utf-8") > MAX_BYTES) return reply(413, { error: "too long" });
    who = verify("update", body, updateFields({ id, recipe }));
    change.recipe = recipe;
  } else {
    who = verify("withdraw", body, withdrawFields({ id }));
  }
  if (!who.ok) return reply(who.status, { error: who.reason });
  change.source = who.keyId;
  change.time = new Date().toISOString();
  const name = `${Date.now().toString(36)}-${who.sigId.slice(0, 8)}`;
  try {
    await branchWithFile(`submit/${Math.floor(Date.now() / 1000)}-${who.sigId}`, `changes/${name}.json`, JSON.stringify(change), `Change ${name}`);
  } catch (e) {
    return reply(e && e.exists ? 409 : 502, { error: e && e.exists ? "that request was already made" : "it could not be queued; try again later" });
  }
  return reply(202, { ok: true, status: "queued", note: action === "update"
    ? "The new text replaces the old one after the same automatic check, usually within minutes."
    : "It is taken off the site within minutes." });
};
