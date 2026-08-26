import crypto from "node:crypto";

export const SCOPE = Object.freeze({
  repositoryId: 1347005783,
  repositoryFullName: "Yatsuiii/custody-external-validity-sandbox",
  installationId: 156728027,
  issueId: 5254158748,
  issueNumber: 1,
  ownerId: 155452778,
  redTeamId: 191570034,
});

export function validSignature(rawBody, supplied, secret) {
  if (typeof supplied !== "string" || !supplied.startsWith("sha256=")) {
    return false;
  }
  const expected = Buffer.from(
    "sha256=" + crypto.createHmac("sha256", secret).update(rawBody).digest("hex"),
    "utf8",
  );
  const actual = Buffer.from(supplied, "utf8");
  return actual.length === expected.length && crypto.timingSafeEqual(actual, expected);
}

export function payloadAllowed(payload) {
  const repository = payload.repository;
  const issue = payload.issue;
  const installation = payload.installation;
  const sender = payload.sender;
  const comment = payload.comment;
  return (
    repository &&
    repository.id === SCOPE.repositoryId &&
    repository.full_name === SCOPE.repositoryFullName &&
    installation &&
    installation.id === SCOPE.installationId &&
    issue &&
    issue.id === SCOPE.issueId &&
    issue.number === SCOPE.issueNumber &&
    !Object.prototype.hasOwnProperty.call(issue, "pull_request") &&
    sender &&
    (sender.id === SCOPE.ownerId || sender.id === SCOPE.redTeamId) &&
    comment &&
    Number.isSafeInteger(comment.id) &&
    comment.user &&
    comment.user.id === sender.id &&
    typeof comment.body === "string"
  );
}

export function parseVerifiedPayload({ rawBody, signature, secret, event }) {
  if (!validSignature(rawBody, signature, secret)) {
    return { accepted: false, status: 401, code: "invalid_signature" };
  }
  if (event !== "issue_comment") {
    return { accepted: false, status: 202, code: "ignored_event" };
  }
  let payload;
  try {
    payload = JSON.parse(rawBody.toString("utf8"));
  } catch {
    return { accepted: false, status: 400, code: "invalid_json" };
  }
  if (payload.action !== "created") {
    return { accepted: false, status: 202, code: "ignored_action" };
  }
  if (!payloadAllowed(payload)) {
    return { accepted: false, status: 202, code: "rejected_scope" };
  }
  return { accepted: true, payload };
}

export function bodyDigest(rawBody) {
  return crypto.createHash("sha256").update(rawBody).digest("hex");
}
