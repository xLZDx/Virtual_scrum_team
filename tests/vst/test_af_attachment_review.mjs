import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { test } from "node:test";

import {
  assertPromptBinding,
  nativePromptWasTruncated,
  parseAcknowledgements,
  runAdapter,
  validateCompletedJob,
  validateTopLevelVerdict,
  verifyRegularAttachment,
} from "../../tools/af_attachment_review.mjs";

const sha256 = (value) => crypto.createHash("sha256").update(value).digest("hex");
const UUID = "f1b3a0cd-1c44-4c60-a153-c397e41fe223";
const OTHER_UUID = "f1b3a0cd-1c44-4c60-a153-c397e41fe224";
const PROJECT_ID = "virtual_scrum_team-test";
const CONVERSATION_ID = "conversation-test-01";

function git(cwd, ...args) {
  const result = spawnSync("git", ["-C", cwd, ...args], { encoding: "utf8", windowsHide: true });
  assert.equal(result.status, 0, `git ${args.join(" ")} failed: ${result.stderr}`);
  return result.stdout.trim();
}

function makeRepo(t) {
  const cwd = fs.mkdtempSync(path.join(os.tmpdir(), "vst-af-attachment-test-"));
  t.after(() => fs.rmSync(cwd, { recursive: true, force: true }));
  fs.mkdirSync(path.join(cwd, "docs", "sdlc"), { recursive: true });
  git(cwd, "init", "--quiet");
  git(cwd, "config", "user.name", "Functional Test Fixture");
  git(cwd, "config", "user.email", "fixture@example.invalid");
  fs.writeFileSync(path.join(cwd, "fixture.txt"), "base\n", "utf8");
  git(cwd, "add", "fixture.txt");
  git(cwd, "commit", "--quiet", "-m", "fixture base");
  const baseSha = git(cwd, "rev-parse", "HEAD");
  fs.writeFileSync(path.join(cwd, "fixture.txt"), "changed\n", "utf8");
  git(cwd, "add", "fixture.txt");
  git(cwd, "commit", "--quiet", "-m", "fixture change");
  const headSha = git(cwd, "rev-parse", "HEAD");
  return { cwd, baseSha, headSha };
}

function promptFor({ baseSha, headSha, body = "+synthetic review fixture\n" }) {
  return Buffer.from(
    `# PM-GPT code review request\n` +
      `Reviewed range: ${baseSha}...${headSha}\n` +
      `Exact HEAD under review: ${headSha}\n` +
      `Reply format: first line VERDICT.\n\n` +
      `Diff:\n\`\`\`diff\n${body}\n\`\`\`\n\n---\n\nsynthetic authority footer\n`,
    "utf8",
  );
}

function verdictParser(reply) {
  const matches = [...String(reply ?? "").matchAll(/^\s*[#*>\- ]*VERDICT\s*:\s*(.*)$/gim)];
  const line = matches[0]?.[1]?.trim() ?? null;
  const severity = /^(APPROVE|MINOR|MAJOR|BLOCKER)\b/i.exec(line ?? "")?.[1]?.toUpperCase() ?? "UNRECOGNIZED";
  return { found: matches.length > 0, line, verdictCount: matches.length, severity, contradiction: false };
}

function makeHarness({ repo, prompt, capability = true, jobMutation = (job) => job, failAfterSend = false, mutateAttachmentAfterSend = false } = {}) {
  const calls = [];
  let job = null;
  let sendCount = 0;
  let observedIntent = null;
  const bridge = {
    async resolveIdentityAssertedBinding() {
      return { identityBinding: { projectId: PROJECT_ID, conversationId: CONVERSATION_ID } };
    },
    async isOrchestratorActive() {
      return { capabilities: capability ? ["file-attachments"] : [] };
    },
    daemonRouting(project, options) {
      return { project, repoPath: options.repoPath };
    },
    assertCanonicalDescriptor(descriptor) {
      assert.equal(descriptor.requestId, job.requestId);
      assert.ok(Array.isArray(descriptor.steps));
      assert.ok(descriptor.steps.every((step) => step.kind !== "rotation-title"));
      return descriptor;
    },
    applyWireTransforms(logicalText, descriptor) {
      return `PROJECT: ${PROJECT_ID} | REPO: ${repo.cwd}\nREQUEST_ID: ${descriptor.requestId}\n${logicalText}`;
    },
    parseVerdict: verdictParser,
    decideReviewFinal({ requestedFinal, reviewStatus, parsedVerdict, truncated, correlated }) {
      const final = requestedFinal && reviewStatus === "RAN" && !truncated && correlated &&
        ["APPROVE", "MINOR"].includes(parsedVerdict.severity);
      return { final, finalOverridden: requestedFinal && !final };
    },
    async callOrchestrator(_active, endpoint, body, timeout) {
      calls.push({ endpoint, body, timeout });
      if (endpoint === "/job_status") {
        if (job) return { ok: true, job };
        throw Object.assign(new Error("fixture job not found"), { code: "JOB_NOT_FOUND" });
      }
      if (endpoint !== "/send_and_await") throw new Error(`unexpected endpoint: ${endpoint}`);
      sendCount += 1;
      const filePath = body.attachments?.[0];
      assert.ok(filePath, "adapter must submit the full prompt as an attachment");
      const bytes = fs.readFileSync(filePath);
      const intentPath = path.join(repo.cwd, "docs", "sdlc", ".pm-review", `intent-${body.reviewInputHash}.json`);
      observedIntent = JSON.parse(fs.readFileSync(intentPath, "utf8"));
      assert.equal(observedIntent.phase, "sending", "durable intent must be fsynced before the send boundary");
      assert.equal(observedIntent.requestId, body.requestId);
      assert.equal(observedIntent.inputHash, body.reviewInputHash);
      assert.equal(observedIntent.size, bytes.length);
      assert.equal(observedIntent.instruction, body.text);
      if (failAfterSend) throw Object.assign(new Error("simulated ambiguous transport response"), { code: "ECONNRESET" });
      const wireDescriptor = {
        requestId: body.requestId,
        steps: [{ kind: "project-header" }, { kind: "request-envelope" }],
      };
      const wireText = bridge.applyWireTransforms(body.text, wireDescriptor);
      const inputHash = body.reviewInputHash;
      const headSha = repo.headSha;
      const reply = [
        "VERDICT: APPROVE",
        `REVIEW_INPUT_SHA256:${inputHash}`,
        `REVIEW_HEAD:${headSha}`,
        `REVIEW_REQUEST_ID:${body.requestId}`,
      ].join("\n");
      job = {
        jobId: "job-fixture-01",
        idempotencyKey: `${body.requestId}:send-and-await`,
        operation: "send-and-await",
        projectId: PROJECT_ID,
        conversationId: CONVERSATION_ID,
        requestId: body.requestId,
        status: "succeeded",
        sendPhase: "sent",
        userTurnId: "turn-fixture-01",
        replyId: "reply-fixture-01",
        correlated: true,
        result: { reply, replyId: "reply-fixture-01", correlated: true },
        sendSnapshot: {
          text: wireText,
          logicalText: body.text,
          attachments: [{ name: path.basename(filePath), path: filePath, size: bytes.length, sha256: sha256(bytes) }],
          conversationId: CONVERSATION_ID,
          baseline: {
            userTurnId: "turn-fixture-01",
            wireEvidence: {
              wireProtocolVersion: 2,
              wireRequestId: body.requestId,
              wireDescriptor,
              wireHash: sha256(Buffer.from(wireText, "utf8")),
            },
          },
        },
      };
      job = jobMutation(job);
      if (mutateAttachmentAfterSend) {
        bytes[0] ^= 1;
        fs.writeFileSync(filePath, bytes);
      }
      return { ok: true, job };
    },
  };
  const adapterOptions = {
    bridgeLoader: async () => bridge,
    nativeDump(_args, dumpPath) {
      if (typeof prompt === "function") prompt = prompt();
      fs.writeFileSync(dumpPath, prompt);
      return { diagnostic: true };
    },
  };
  return { bridge, calls, adapterOptions, get sendCount() { return sendCount; }, get job() { return job; }, get observedIntent() { return observedIntent; } };
}

function adapterArgs(repo) {
  return ["--cwd", repo.cwd, "--base", repo.baseSha, "--project", PROJECT_ID, "--final"];
}

function withDebugDumpDisabled(fn) {
  const previous = process.env.PM_BRIDGE_DEBUG_DUMP_PROMPT_ONLY;
  delete process.env.PM_BRIDGE_DEBUG_DUMP_PROMPT_ONLY;
  return Promise.resolve().then(fn).finally(() => {
    if (previous === undefined) delete process.env.PM_BRIDGE_DEBUG_DUMP_PROMPT_ONLY;
    else process.env.PM_BRIDGE_DEBUG_DUMP_PROMPT_ONLY = previous;
  });
}

test("AFAT-01/02/03/11/12: runAdapter sends the unchanged full synthetic prompt as one attachment and never writes AF approval", async (t) => {
  const repo = makeRepo(t);
  const prompt = promptFor({
    ...repo,
    body: `+${"x".repeat(4 * 1024 * 1024 + 123)}\n`,
  });
  const harness = makeHarness({ repo, prompt });
  const result = await withDebugDumpDisabled(() => runAdapter(adapterArgs(repo), harness.adapterOptions));
  assert.equal(result.ok, true);
  assert.equal(result.final, true);
  assert.equal(result.truncated, false);
  assert.equal(harness.sendCount, 1);
  assert.equal(harness.observedIntent.phase, "sending");
  assert.equal(harness.observedIntent.requestId, result.reviewRequestId);
  const send = harness.calls.find((call) => call.endpoint === "/send_and_await");
  assert.ok(send);
  assert.equal(send.timeout, null, "the completion-control wait must remain unbounded");
  assert.equal(send.body.waitForCompletionControls, true);
  assert.equal(send.body.attachments.length, 1);
  assert.equal(send.body.reviewInputHash, sha256(prompt));
  assert.notEqual(send.body.text, prompt.toString("utf8"), "the inline body must not substitute for the full attachment");
  assert.deepEqual(fs.readFileSync(send.body.attachments[0]), prompt);
  assert.deepEqual(result.attachment, {
    path: send.body.attachments[0],
    name: path.basename(send.body.attachments[0]),
    size: prompt.length,
    sha256: sha256(prompt),
  });
  assert.equal(fs.existsSync(path.join(repo.cwd, "gate-approval.md")), false);
  assert.equal(fs.existsSync(path.join(repo.cwd, "docs", "sdlc", ".pm-review", "approval.json")), false);
});

test("AFAT-01: native dump failure stops before any transport", async (t) => {
  const repo = makeRepo(t);
  const harness = makeHarness({ repo, prompt: promptFor(repo) });
  harness.adapterOptions.nativeDump = () => { throw new Error("synthetic dump failure"); };
  await withDebugDumpDisabled(() => assert.rejects(runAdapter(adapterArgs(repo), harness.adapterOptions), /synthetic dump failure/));
  assert.equal(harness.sendCount, 0);
});

test("AFAT-05: a daemon without the file-attachments capability fails closed before sending", async (t) => {
  const repo = makeRepo(t);
  const harness = makeHarness({ repo, prompt: promptFor(repo), capability: false });
  await withDebugDumpDisabled(() => assert.rejects(runAdapter(adapterArgs(repo), harness.adapterOptions), /does not advertise file-attachments/));
  assert.equal(harness.sendCount, 0);
});

test("AFAT-04: replay of a completed exact prompt reuses the same durable request without a second send", async (t) => {
  const repo = makeRepo(t);
  const harness = makeHarness({ repo, prompt: promptFor(repo) });
  const first = await withDebugDumpDisabled(() => runAdapter(adapterArgs(repo), harness.adapterOptions));
  const second = await withDebugDumpDisabled(() => runAdapter(adapterArgs(repo), harness.adapterOptions));
  assert.equal(first.reviewRequestId, second.reviewRequestId);
  assert.equal(second.recovered, true);
  assert.equal(harness.sendCount, 1);
});

test("AFAT-04/08: ambiguous delivery without a durable job is never resent under a new ID", async (t) => {
  const repo = makeRepo(t);
  const prompt = promptFor(repo);
  const harness = makeHarness({ repo, prompt, failAfterSend: true });
  await withDebugDumpDisabled(() => assert.rejects(runAdapter(adapterArgs(repo), harness.adapterOptions), /send response was ambiguous/));
  assert.equal(harness.sendCount, 1);
  await withDebugDumpDisabled(() => assert.rejects(runAdapter(adapterArgs(repo), harness.adapterOptions), /already marked sending/));
  assert.equal(harness.sendCount, 1);
  const intentPath = path.join(repo.cwd, "docs", "sdlc", ".pm-review", `intent-${sha256(prompt)}.json`);
  const intent = JSON.parse(fs.readFileSync(intentPath, "utf8"));
  intent.size += 1;
  fs.writeFileSync(intentPath, JSON.stringify(intent), "utf8");
  await withDebugDumpDisabled(() => assert.rejects(runAdapter(adapterArgs(repo), harness.adapterOptions), /immutable identity fields/));
  assert.equal(harness.sendCount, 1);
});

test("AFAT-03/04: concurrent identical inputs have one durable send claim", async (t) => {
  const repo = makeRepo(t);
  const harness = makeHarness({ repo, prompt: promptFor(repo) });
  const originalCall = harness.bridge.callOrchestrator;
  let initialStatusCount = 0;
  let releaseStatuses;
  const bothStatuses = new Promise((resolve) => { releaseStatuses = resolve; });
  harness.bridge.callOrchestrator = async (active, endpoint, body, timeout) => {
    if (endpoint === "/job_status" && !harness.job) {
      initialStatusCount += 1;
      if (initialStatusCount === 2) releaseStatuses();
      await bothStatuses;
    }
    return originalCall(active, endpoint, body, timeout);
  };
  const results = await withDebugDumpDisabled(() => Promise.allSettled([
    runAdapter(adapterArgs(repo), harness.adapterOptions),
    runAdapter(adapterArgs(repo), harness.adapterOptions),
  ]));
  assert.equal(harness.sendCount, 1);
  assert.equal(results.filter((result) => result.status === "fulfilled").length, 1);
  assert.equal(results.filter((result) => result.status === "rejected").length, 1);
});

test("AFAT-07: local attachment changes after the send are detected before acceptance", async (t) => {
  const repo = makeRepo(t);
  const harness = makeHarness({ repo, prompt: promptFor(repo), mutateAttachmentAfterSend: true });
  await withDebugDumpDisabled(() => assert.rejects(runAdapter(adapterArgs(repo), harness.adapterOptions), /review attachment bytes do not match/));
  assert.equal(harness.sendCount, 1);
});

test("AFAT-06/08/09: durable job identity, correlation, attachment manifest, and acknowledgments are mandatory", async (t) => {
  const cases = [
    ["wrong project", (job) => ({ ...job, projectId: "other-project" })],
    ["wrong conversation", (job) => ({ ...job, conversationId: "other-conversation" })],
    ["wrong request id", (job) => ({ ...job, requestId: "other-request" })],
    ["wrong idempotency key", (job) => ({ ...job, idempotencyKey: "other-idempotency-key" })],
    ["terminal failure", (job) => ({ ...job, status: "failed" })],
    ["send not recorded", (job) => ({ ...job, sendPhase: "sending" })],
    ["uncorrelated", (job) => ({ ...job, correlated: false })],
    ["missing user turn", (job) => ({ ...job, userTurnId: null })],
    ["missing reply ID", (job) => ({ ...job, replyId: null })],
    ["reply ID mismatch", (job) => ({ ...job, result: { ...job.result, replyId: "other-reply" } })],
    ["result uncorrelated", (job) => ({ ...job, result: { ...job.result, correlated: false } })],
    ["wrong snapshot conversation", (job) => ({ ...job, sendSnapshot: { ...job.sendSnapshot, conversationId: "other-conversation" } })],
    ["wrong attachment path", (job) => ({ ...job, sendSnapshot: { ...job.sendSnapshot, attachments: [{ ...job.sendSnapshot.attachments[0], path: "D:/other/prompt.txt" }] } })],
    ["wrong attachment name", (job) => ({ ...job, sendSnapshot: { ...job.sendSnapshot, attachments: [{ ...job.sendSnapshot.attachments[0], name: "other.txt" }] } })],
    ["wrong attachment size", (job) => ({ ...job, sendSnapshot: { ...job.sendSnapshot, attachments: [{ ...job.sendSnapshot.attachments[0], size: job.sendSnapshot.attachments[0].size + 1 }] } })],
    ["wrong attachment hash", (job) => ({ ...job, sendSnapshot: { ...job.sendSnapshot, attachments: [{ ...job.sendSnapshot.attachments[0], sha256: "0".repeat(64) }] } })],
    ["extra attachment", (job) => ({ ...job, sendSnapshot: { ...job.sendSnapshot, attachments: [...job.sendSnapshot.attachments, job.sendSnapshot.attachments[0]] } })],
    ["missing acknowledgement", (job) => ({ ...job, result: { ...job.result, reply: "VERDICT: APPROVE\nREVIEW_HEAD: stale\nREVIEW_REQUEST_ID: stale" } })],
    ["wrong head acknowledgment", (job) => ({ ...job, result: { ...job.result, reply: job.result.reply.replace(/REVIEW_HEAD:[^\n]*/, "REVIEW_HEAD:stale") } })],
    ["false echoed acknowledgment", (job) => ({ ...job, result: { ...job.result, reply: `VERDICT: APPROVE\n> REVIEW_INPUT_SHA256:${job.sendSnapshot.attachments[0].sha256}\nREVIEW_HEAD: stale\nREVIEW_REQUEST_ID: stale` } })],
  ];
  for (const [name, jobMutation] of cases) {
    await t.test(name, async (t) => {
      const repo = makeRepo(t);
      const harness = makeHarness({ repo, prompt: promptFor(repo), jobMutation });
      await withDebugDumpDisabled(() => assert.rejects(runAdapter(adapterArgs(repo), harness.adapterOptions)));
      assert.equal(harness.sendCount, 1);
    });
  }
});

test("AFAT-09: acknowledgments must be unique exact standalone lines outside code fences", () => {
  const expected = { inputHash: "a".repeat(64), headSha: "b".repeat(40), requestId: UUID };
  const good = `VERDICT: APPROVE\nREVIEW_INPUT_SHA256:${expected.inputHash}\nREVIEW_HEAD:${expected.headSha}\nREVIEW_REQUEST_ID:${UUID}`;
  assert.equal(parseAcknowledgements(good, expected), true);
  assert.throws(() => parseAcknowledgements(`${good}\nREVIEW_HEAD:${expected.headSha}`, expected), /unique standalone/);
  assert.throws(() => parseAcknowledgements(good.replace(`REVIEW_HEAD:${expected.headSha}`, `> REVIEW_HEAD:${expected.headSha}`), expected), /unique standalone/);
  assert.throws(() => parseAcknowledgements(good.replace(`REVIEW_HEAD:${expected.headSha}`, `\`\`\`text\nREVIEW_HEAD:${expected.headSha}\n\`\`\``), expected), /unique standalone/);
});

test("AFAT-10: verdict must be a single top-level first line before native verdict parsing", () => {
  const parse = (reply) => verdictParser(reply);
  assert.equal(validateTopLevelVerdict("VERDICT: APPROVE\nNo findings.", parse).severity, "APPROVE");
  assert.throws(() => validateTopLevelVerdict("Quoted: VERDICT: APPROVE\n", parse), /begin with/);
  assert.throws(() => validateTopLevelVerdict("VERDICT: APPROVE\nVERDICT: BLOCKER\n", parse), /repeated/);
  assert.equal(validateTopLevelVerdict("VERDICT: HOLD\n", parse).severity, "UNRECOGNIZED");
});

test("AFAT-10: correlated REQUEST_ID header is accepted only once before the verdict", () => {
  const parse = (reply) => verdictParser(reply);
  const matching = `REQUEST_ID: ${UUID}\nVERDICT: APPROVE\nNo findings.`;
  const matchingWithBlankLine = `REQUEST_ID: ${UUID}\n\nVERDICT: APPROVE\nNo findings.`;

  assert.equal(validateTopLevelVerdict(matching, parse, UUID).severity, "APPROVE");
  assert.equal(validateTopLevelVerdict(matchingWithBlankLine, parse, UUID).severity, "APPROVE");
  assert.throws(
    () => validateTopLevelVerdict(`REQUEST_ID: ${OTHER_UUID}\nVERDICT: APPROVE`, parse, UUID),
    /does not match/,
  );
  assert.throws(
    () => validateTopLevelVerdict(`REQUEST_ID: ${UUID}\nREQUEST_ID: ${UUID}\nVERDICT: APPROVE`, parse, UUID),
    /begin with/,
  );
  assert.throws(
    () => validateTopLevelVerdict(`REQUEST_ID: not-a-uuid\nVERDICT: APPROVE`, parse, UUID),
    /begin with/,
  );
  assert.throws(
    () => validateTopLevelVerdict(`Preamble\nREQUEST_ID: ${UUID}\nVERDICT: APPROVE`, parse, UUID),
    /begin with/,
  );
  assert.throws(
    () => validateTopLevelVerdict("ChatGPT said:\n\nVERDICT: APPROVE", parse, UUID),
    /REQUEST_ID|begin with/,
  );
  assert.throws(
    () => validateTopLevelVerdict(`Assistant said:\n\nREQUEST_ID: ${UUID}\n\nVERDICT: APPROVE`, parse, UUID),
    /begin with/,
  );
});

test("AFAT-10: runAdapter binds a matching leading REQUEST_ID to the persisted intent", async (t) => {
  const repo = makeRepo(t);
  const harness = makeHarness({
    repo,
    prompt: promptFor(repo),
    jobMutation(job) {
      const reply = [
        "ChatGPT said:",
        "",
        `REQUEST_ID: ${job.requestId}`,
        "",
        "VERDICT: APPROVE",
        `REVIEW_INPUT_SHA256:${job.sendSnapshot.attachments[0].sha256}`,
        `REVIEW_HEAD:${repo.headSha}`,
        `REVIEW_REQUEST_ID:${job.requestId}`,
      ].join("\n");
      return { ...job, result: { ...job.result, reply } };
    },
  });

  const result = await withDebugDumpDisabled(() => runAdapter(adapterArgs(repo), harness.adapterOptions));
  const send = harness.calls.find((call) => call.endpoint === "/send_and_await");
  assert.ok(send);
  assert.equal(result.final, true);
  assert.equal(result.reviewRequestId, harness.observedIntent.requestId);
  assert.equal(send.body.requestId, harness.observedIntent.requestId);
  assert.match(result.reply, new RegExp(`^ChatGPT said:\\n\\nREQUEST_ID: ${harness.observedIntent.requestId}\\n\\nVERDICT: APPROVE`));
});

test("AFAT-10: runAdapter rejects a mismatched leading REQUEST_ID without emitting an acceptance receipt", async (t) => {
  const repo = makeRepo(t);
  const harness = makeHarness({
    repo,
    prompt: promptFor(repo),
    jobMutation(job) {
      const reply = [
        "ChatGPT said:",
        "",
        `REQUEST_ID: ${OTHER_UUID}`,
        "VERDICT: APPROVE",
        `REVIEW_INPUT_SHA256:${job.sendSnapshot.attachments[0].sha256}`,
        `REVIEW_HEAD:${repo.headSha}`,
        `REVIEW_REQUEST_ID:${job.requestId}`,
      ].join("\n");
      return { ...job, result: { ...job.result, reply } };
    },
  });
  const output = [];
  const originalLog = console.log;
  console.log = (...args) => output.push(args.join(" "));
  try {
    await withDebugDumpDisabled(() => assert.rejects(
      runAdapter(adapterArgs(repo), harness.adapterOptions),
      /leading REQUEST_ID does not match/,
    ));
  } finally {
    console.log = originalLog;
  }

  assert.equal(harness.sendCount, 1);
  assert.equal(harness.job.requestId, harness.observedIntent.requestId);
  assert.equal(output.length, 0, "rejected correlation must not emit the success/receipt JSON");
  const artifacts = fs.readdirSync(path.join(repo.cwd, "docs", "sdlc", ".pm-review"));
  assert.equal(artifacts.some((name) => /receipt|approval/i.test(name)), false);
});

test("AFAT-10/11: a HOLD response is returned as non-final and cannot become an approval", async (t) => {
  const repo = makeRepo(t);
  const harness = makeHarness({
    repo,
    prompt: promptFor(repo),
    jobMutation(job) {
      const reply = job.result.reply.replace("VERDICT: APPROVE", "VERDICT: HOLD");
      return { ...job, result: { ...job.result, reply } };
    },
  });
  const result = await withDebugDumpDisabled(() => runAdapter(adapterArgs(repo), harness.adapterOptions));
  assert.equal(result.ok, true);
  assert.equal(result.verdict, "UNRECOGNIZED");
  assert.equal(result.final, false);
  assert.equal(fs.existsSync(path.join(repo.cwd, "gate-approval.md")), false);
});

test("AFAT-01: exact prompt scope must bind the selected base and HEAD before the diff", () => {
  const baseSha = "a".repeat(40);
  const headSha = "b".repeat(40);
  const prompt = `Reviewed range: ${baseSha}...${headSha}\nExact HEAD under review: ${headSha}\nDiff:\n\`\`\`diff\n+fixture\n\`\`\``;
  assert.doesNotThrow(() => assertPromptBinding(prompt, { baseSha, headSha, baseRef: baseSha }));
  assert.throws(() => assertPromptBinding(prompt.replace(baseSha, "wrong-base"), { baseSha, headSha, baseRef: baseSha }), /does not bind/);
  assert.throws(() => assertPromptBinding(`Diff:\n\`\`\`diff\nExact HEAD under review: ${headSha}\nReviewed range: ${baseSha}...${headSha}`, { baseSha, headSha, baseRef: baseSha }), /before the diff/);
});

test("AFAT-01: final native prompt rejects its exact truncation marker", () => {
  const prefix = "before\nDiff:\n\`\`\`diff\n+body";
  const marker = "\n[... truncated, 100000001 chars total ...]\n\`\`\`\n\n---\n\nfooter";
  assert.throws(() => nativePromptWasTruncated(prefix + marker, { requestedFinal: true }), /final review prompt contains/);
  assert.equal(nativePromptWasTruncated(prefix + "\n+complete\n\`\`\`\n\n---\n\nfooter", { requestedFinal: true }), false);
});

test("AFAT-07: attachment reader rejects changed bytes and non-canonical UTF-8", (t) => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "vst-af-attachment-bytes-"));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const filePath = path.join(dir, "prompt.txt");
  const bytes = Buffer.from("synthetic prompt\n", "utf8");
  fs.writeFileSync(filePath, bytes);
  assert.deepEqual(verifyRegularAttachment(filePath, sha256(bytes), bytes.length), bytes);
  const changed = Buffer.from(bytes);
  changed[0] = "S".charCodeAt(0);
  fs.writeFileSync(filePath, changed);
  assert.throws(() => verifyRegularAttachment(filePath, sha256(bytes), bytes.length), /bytes do not match/);
});

test("AFAT-06/07/08/09: direct durable-job validator rejects false correlation and attachment mismatch", (t) => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "vst-af-attachment-job-"));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const filePath = path.join(dir, "prompt.txt");
  const promptBytes = Buffer.from("synthetic canonical prompt", "utf8");
  fs.writeFileSync(filePath, promptBytes);
  const intent = {
    requestId: UUID,
    operation: "send-and-await",
    inputHash: sha256(promptBytes),
    headSha: "b".repeat(40),
    baseSha: "a".repeat(40),
    projectId: PROJECT_ID,
    conversationId: CONVERSATION_ID,
    size: promptBytes.length,
    attachmentPath: filePath,
    instruction: "synthetic instruction",
  };
  const wireText = `REQUEST_ID: ${UUID}\n${intent.instruction}`;
  const reply = `VERDICT: APPROVE\nREVIEW_INPUT_SHA256:${intent.inputHash}\nREVIEW_HEAD:${intent.headSha}\nREVIEW_REQUEST_ID:${UUID}`;
  const job = {
    requestId: UUID,
    operation: "send-and-await",
    projectId: PROJECT_ID,
    conversationId: CONVERSATION_ID,
    idempotencyKey: `${UUID}:send-and-await`,
    status: "succeeded",
    sendPhase: "sent",
    userTurnId: "turn-01",
    replyId: "reply-01",
    correlated: true,
    result: { reply, replyId: "reply-01", correlated: true },
    sendSnapshot: {
      text: wireText,
      logicalText: intent.instruction,
      conversationId: CONVERSATION_ID,
      attachments: [{ name: "prompt.txt", path: filePath, size: promptBytes.length, sha256: intent.inputHash }],
      baseline: { userTurnId: "turn-01", wireEvidence: { wireRequestId: UUID, wireDescriptor: { requestId: UUID }, wireHash: sha256(Buffer.from(wireText)) } },
    },
  };
  assert.equal(validateCompletedJob({ job, intent, filePath, promptBytes }).replyId, "reply-01");
  assert.throws(() => validateCompletedJob({ job: { ...job, correlated: false }, intent, filePath, promptBytes }), /lacks sent-turn and correlated reply evidence/);
  assert.throws(() => validateCompletedJob({ job: { ...job, sendSnapshot: { ...job.sendSnapshot, logicalText: "other" } }, intent, filePath, promptBytes }), /logical sent text differs/);
});
