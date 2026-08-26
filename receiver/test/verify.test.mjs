import assert from "node:assert/strict";
import crypto from "node:crypto";
import test from "node:test";
import { bodyDigest, parseVerifiedPayload, validSignature } from "../lib/verify.js";

const secret = "test-only-secret-not-a-live-credential";
const payload = {
  action: "created",
  repository: {
    id: 1347005783,
    full_name: "Yatsuiii/custody-external-validity-sandbox",
  },
  installation: { id: 156728027 },
  issue: { id: 5254158748, number: 1 },
  sender: { id: 155452778 },
  comment: { id: 7000000001, user: { id: 155452778 }, body: "custody: activate" },
};

function signed(body) {
  return `sha256=${crypto.createHmac("sha256", secret).update(body).digest("hex")}`;
}

test("verifies the exact raw bytes before JSON parsing", () => {
  const body = Buffer.from(JSON.stringify(payload));
  assert.equal(validSignature(body, signed(body), secret), true);
  assert.equal(validSignature(Buffer.from(body.toString() + " "), signed(body), secret), false);
  const result = parseVerifiedPayload({
    rawBody: body,
    signature: signed(body),
    secret,
    event: "issue_comment",
  });
  assert.equal(result.accepted, true);
  assert.equal(result.payload.comment.id, 7000000001);
  assert.equal(bodyDigest(body).length, 64);
});

test("fails closed for malformed or out-of-scope deliveries", () => {
  const malformed = Buffer.from("{not-json");
  assert.deepEqual(
    parseVerifiedPayload({
      rawBody: malformed,
      signature: signed(malformed),
      secret,
      event: "issue_comment",
    }),
    { accepted: false, status: 400, code: "invalid_json" },
  );
  const wrong = { ...payload, repository: { ...payload.repository, id: 9 } };
  const body = Buffer.from(JSON.stringify(wrong));
  assert.deepEqual(
    parseVerifiedPayload({
      rawBody: body,
      signature: signed(body),
      secret,
      event: "issue_comment",
    }),
    { accepted: false, status: 202, code: "rejected_scope" },
  );
});
