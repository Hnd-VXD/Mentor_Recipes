// A Mentor whose user says something does not work as expected sends a report here, after the user
// has read exactly what is sent and said yes. It becomes an issue in a private repository that only
// Mentor's maker reads (GITHUB_REPORTS_REPO, default Mentor_Reports), labelled "pending"; an update
// that fixes it names its number, and that Mentor then tells its user (distro/rootfs/etc/mentor/UPDATES.md).
//
// The report names no one: the Mentor's own key signs it (it tells reports apart, it is not a person),
// home folders are ~ and anything that looks like a password or key is taken out before the user sees
// it. The token (GITHUB_REPORTS_TOKEN) may only write issues of that one repository.
const { createIssue } = require("./lib/github.js");
const { verify, problemFields } = require("./lib/verify.js");

const MAX_TITLE = 120;
const MAX_TEXT = 24000;

function reply(status, body) {
  return { statusCode: status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" }, body: JSON.stringify(body) };
}

exports.handler = async (event) => {
  if (event.httpMethod !== "POST") return reply(405, { error: "POST only" });
  if (!(event.headers["content-type"] || "").includes("application/json")) return reply(415, { error: "JSON only" });
  if (Buffer.byteLength(event.body || "", "utf-8") > MAX_TEXT + 4000) return reply(413, { error: "too long" });
  let body;
  try {
    body = JSON.parse(event.body || "");
  } catch (e) {
    return reply(400, { error: "not JSON" });
  }
  const title = typeof body.title === "string" ? body.title.trim() : "";
  const text = typeof body.text === "string" ? body.text : "";
  const version = typeof body.version === "string" ? body.version.slice(0, 20) : "";
  if (!title || title.length > MAX_TITLE || !text.trim() || text.length > MAX_TEXT) return reply(422, { error: "not a report" });
  if (!/^[0-9.]*$/.test(version)) return reply(422, { error: "not a report" });

  const who = verify("problem", body, problemFields({ title, text, version }));
  if (!who.ok) return reply(who.status, { error: who.reason });

  const footer = `\n\n---\nMentor ${version || "(version unknown)"} · sender ${who.keyId} · request ${who.sigId}`;
  try {
    const issue = await createIssue(`[${version || "?"}] ${title}`, text + footer, ["pending"]);
    return reply(201, { ok: true, id: issue.number });
  } catch (e) {
    return reply(502, { error: "it could not be filed; try again later" });
  }
};
