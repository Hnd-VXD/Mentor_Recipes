// A Mentor posts a recipe here. Nothing is decided in this function: it checks that the thing is
// shaped like a submission and hands it to GitHub, where tools/accept.py looks at it with the
// rules, and publishes it or drops it, by itself. The categories are decided there too.
const crypto = require("crypto");
const { branchWithFile } = require("./lib/github.js");
const { verify, submitFields } = require("./lib/verify.js");

const MAX_BYTES = 120000;

function reply(status, body) {
  return { statusCode: status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" }, body: JSON.stringify(body) };
}

function text(value, most) {
  return typeof value === "string" ? value.trim().slice(0, most) : "";
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
  const recipe = typeof body.recipe === "string" ? body.recipe : "";
  if (!recipe.includes("## Steps") || !recipe.includes("## Check that it works")) {
    return reply(422, { error: "not in the form of a recipe" });
  }
  if (Buffer.byteLength(recipe, "utf-8") > MAX_BYTES) return reply(413, { error: "too long" });

  // Whose it is: the key that signed it. Nothing of the sender's address is kept.
  const who = verify("submit", body, submitFields({ ...body, recipe }));
  if (!who.ok) return reply(who.status, { error: who.reason });

  // Named from the signature: the same request made twice finds the branch already there.
  const id = `${Date.now().toString(36)}-${who.sigId.slice(0, 8)}`;
  const proposed = body.new_category && typeof body.new_category === "object" ? body.new_category : null;
  const submission = {
    recipe,
    category: text(body.category, 30),
    new_category: proposed
      ? { id: text(proposed.id, 30), parent: text(proposed.parent, 30), name: text(proposed.name, 40), description: text(proposed.description, 140) }
      : null,
    source: who.keyId,
    key: body.key,
    sig: body.sig,
    time: new Date().toISOString(),
  };
  try {
    await branchWithFile(`submit/${Math.floor(Date.now() / 1000)}-${who.sigId}`, `incoming/${id}.json`, JSON.stringify(submission), `Submission ${id}`);
  } catch (e) {
    return reply(e && e.exists ? 409 : 502, { error: e && e.exists ? "that request was already made" : "it could not be queued; try again later" });
  }
  return reply(202, { ok: true, id, status: "queued", note: "It is published after an automatic check, usually within minutes. If it does not appear, it did not pass." });
};
