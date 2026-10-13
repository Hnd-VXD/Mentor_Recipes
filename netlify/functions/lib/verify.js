// Who is asking, and whether the request is whole. A Mentor signs what it sends with its own
// key (Ed25519, made on its machine, never sent anywhere). The site checks:
//   - the signature, over the exact things that matter (the recipe's checksum, the category, or
//     the recipe and checksum reported), so that nothing can be changed on the way;
//   - the time: a request older than ten minutes is refused, and the name of the branch it makes
//     comes from the signature, so that the same request cannot be made twice;
//   - a small proof of work, which costs a Mentor about a second and a flood a great deal.
// Nothing here says the sender is a good person: it says the request is one that this key made,
// once, a moment ago, and that the key paid a little to make it. What the key may do is limited
// again where the recipes are decided (tools/accept.py): a number a day for each key.
const crypto = require("crypto");

const SPKI_PREFIX = Buffer.from("302a300506032b6570032100", "hex"); // an Ed25519 public key, in the form Node reads
const POW_BITS = 20;
const MAX_SKEW_SECONDS = 600;

function sha256hex(text) {
  return crypto.createHash("sha256").update(text).digest("hex");
}

function leadingZeroBits(buf) {
  let bits = 0;
  for (const byte of buf) {
    if (byte === 0) {
      bits += 8;
      continue;
    }
    bits += Math.clz32(byte) - 24;
    break;
  }
  return bits;
}

// The string that is signed. The client builds exactly the same one.
function signingString(kind, ts, fields) {
  return ["mentor-recipes-v1", kind, String(ts)].concat(fields).join("\n");
}

function submitFields(body) {
  const n = body.new_category && typeof body.new_category === "object" ? body.new_category : null;
  const proposed = n ? [n.id, n.parent, n.name, n.description].map((x) => String(x || "")).join("|") : "";
  return [sha256hex(body.recipe), String(body.category || ""), proposed];
}

function reportFields(body) {
  return [String(body.id || ""), String(body.sha256 || "").toLowerCase(), body.kind === "rules" ? "rules" : "reading"];
}

// -> { ok: true, keyId } or { ok: false, status, reason }
function verify(kind, body, fields, now) {
  const fail = (status, reason) => ({ ok: false, status, reason });
  if (!body || body.v !== 1) return fail(400, "unknown version");
  const ts = Number(body.ts);
  if (!Number.isFinite(ts) || Math.abs((now || Date.now()) / 1000 - ts) > MAX_SKEW_SECONDS) return fail(400, "the time is wrong");
  let raw;
  try {
    raw = Buffer.from(String(body.key || ""), "base64");
  } catch (e) {
    return fail(400, "bad key");
  }
  if (raw.length !== 32) return fail(400, "bad key");
  const pow = String(body.pow || "");
  if (pow.length > 40 || leadingZeroBits(crypto.createHash("sha256").update(`${raw.toString("hex")}:${ts}:${pow}`).digest()) < POW_BITS) {
    return fail(429, "the proof of work is missing");
  }
  let ok = false;
  try {
    const key = crypto.createPublicKey({ key: Buffer.concat([SPKI_PREFIX, raw]), format: "der", type: "spki" });
    ok = crypto.verify(null, Buffer.from(signingString(kind, ts, fields), "utf-8"), key, Buffer.from(String(body.sig || ""), "base64"));
  } catch (e) {
    ok = false;
  }
  if (!ok) return fail(401, "the signature is not right");
  return { ok: true, keyId: sha256hex(raw).slice(0, 16), sigId: sha256hex(String(body.sig)).slice(0, 16) };
}

module.exports = { verify, submitFields, reportFields, signingString, sha256hex, POW_BITS };
