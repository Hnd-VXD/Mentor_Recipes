// Puts one file on a new branch of the recipes repository, through the GitHub API.
// The token comes from the site's environment (GITHUB_SUBMIT_TOKEN): a fine-grained token for
// this one repository, with permission to write contents. It is never in the code.
const OWNER = "Hnd-VXD";
const REPO = "Mentor_Recipes";
const API = "https://api.github.com";

async function call(path, options = {}) {
  const token = process.env.GITHUB_SUBMIT_TOKEN;
  if (!token) throw new Error("the site has no token for GitHub");
  const response = await fetch(API + path, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "mentor-recipes-site",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
    },
  });
  if (!response.ok) {
    const e = new Error(`GitHub answered ${response.status}`);
    e.exists = response.status === 422; // a branch of that name is there already
    throw e;
  }
  return response.json();
}

// A new branch from main with one file on it. GitHub then runs .github/workflows/accept.yml.
// Each step is tried up to three times: GitHub now and then refuses a call for a moment (on
// 2026-10-15 a withdrawal was answered "could not be queued" and went through when sent again).
// A 422 on a second try means the first did happen and only its answer was lost.
async function retried(step) {
  for (let attempt = 1; ; attempt++) {
    try {
      return await step();
    } catch (e) {
      if (e.exists && attempt > 1) return null;
      if (e.exists || attempt >= 3) throw e;
      await new Promise(resolve => setTimeout(resolve, 700 * attempt));
    }
  }
}

async function branchWithFile(branch, file, text, message) {
  const main = await retried(() => call(`/repos/${OWNER}/${REPO}/git/ref/heads/main`));
  await retried(() => call(`/repos/${OWNER}/${REPO}/git/refs`, {
    method: "POST",
    body: JSON.stringify({ ref: `refs/heads/${branch}`, sha: main.object.sha }),
  }));
  await retried(() => call(`/repos/${OWNER}/${REPO}/contents/${file}`, {
    method: "PUT",
    body: JSON.stringify({
      message,
      content: Buffer.from(text, "utf-8").toString("base64"),
      branch,
    }),
  }));
}

module.exports = { branchWithFile };
