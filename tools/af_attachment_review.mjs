#!/usr/bin/env node
/**
 * PROJECT-OWNED AF adapter for the native PM Bridge review CLI.
 *
 * The native CLI remains the authority for prompt construction, routing, daemon
 * authentication and verdict parsing. This adapter only replaces its inline send
 * with the daemon's existing real-file-attachment path so complete S2 inputs can
 * exceed the HTTP JSON body limit without changing the review bytes.
 */
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { pathToFileURL } from "node:url";

const NATIVE_REVIEW = "D:/Repo/pm-bridge/src/cli/review.js";
const BRIDGE_ROOT = "D:/Repo/pm-bridge/src";
const MAX_PROMPT_BYTES = 64 * 1024 * 1024;
const NATIVE_MAX_DIFF_CHARS = 100_000_000;
const OPERATION = "send-and-await";
const ATTACHMENT_PREFIX = "s2-review-input-";

const sha256 = (bytes) => crypto.createHash("sha256").update(bytes).digest("hex");
const canonicalPath = (p) => path.resolve(p);

export function validateCommitRange({ cwd, base, head }) {
  const git = (...args) => {
    const r = spawnSync("git", ["-C", cwd, ...args], { encoding: "utf8", windowsHide: true });
    if (r.status !== 0) throw new Error(`git ${args.join(" ")} failed: ${(r.stderr || "").trim()}`);
    return r.stdout.trim();
  };
  const headSha = git("rev-parse", "--verify", `${head || "HEAD"}^{commit}`);
  const baseSha = git("rev-parse", "--verify", `${base}^{commit}`);
  const ancestor = spawnSync("git", ["-C", cwd, "merge-base", "--is-ancestor", baseSha, headSha], { windowsHide: true });
  if (ancestor.status !== 0) throw new Error(`base ${baseSha} is not an ancestor of HEAD ${headSha}`);
  const diff = spawnSync("git", ["-C", cwd, "diff", "--quiet", `${baseSha}...${headSha}`], { windowsHide: true });
  if (diff.status === 0) throw new Error("review range is empty");
  if (diff.status !== 1) throw new Error("git diff range validation failed");
  return { baseSha, headSha };
}

export function verifyRegularAttachment(filePath, expectedSha, expectedSize) {
  const st = fs.lstatSync(filePath);
  if (!st.isFile() || st.isSymbolicLink() || st.nlink !== 1) throw new Error("review attachment must be a regular single-link file");
  if (st.size <= 0 || st.size > MAX_PROMPT_BYTES || st.size !== expectedSize) throw new Error("review attachment size is invalid or changed");
  const bytes = fs.readFileSync(filePath);
  if (bytes.length !== st.size || sha256(bytes) !== expectedSha) throw new Error("review attachment bytes do not match the canonical prompt hash");
  const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  if (!Buffer.from(text, "utf8").equals(bytes)) throw new Error("review prompt is not canonical UTF-8");
  return bytes;
}

export function assertPromptBinding(prompt, { headSha, baseSha, baseRef }) {
  const diffAt = prompt.indexOf("Diff:\n```diff\n");
  if (diffAt < 0) throw new Error("native prompt is missing the complete diff envelope");
  const preDiff = prompt.slice(0, diffAt).split(/\r?\n/);
  if (!preDiff.includes(`Exact HEAD under review: ${headSha}`) ||
      !(preDiff.includes(`Reviewed range: ${baseSha}...${headSha}`) ||
        preDiff.includes(`Reviewed range: ${baseRef}...${headSha}`))) {
    throw new Error("native scope prompt does not bind the exact HEAD and reviewed base range before the diff");
  }
}

function parseArgs(argv) {
  const out = { argv: [...argv], cwd: null, base: null, head: "HEAD", project: null, final: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--cwd") out.cwd = argv[++i];
    else if (a === "--base") out.base = argv[++i];
    else if (a === "--head") out.head = argv[++i];
    else if (a === "--project") out.project = argv[++i];
    else if (a === "--final") out.final = true;
  }
  if (!out.cwd || !out.base || argv.includes("--uncommitted") || argv.includes("--commit")) {
    throw new Error("AF attachment review requires native --cwd and --base commit-range arguments");
  }
  out.cwd = canonicalPath(out.cwd);
  return out;
}

function runNativeDump(args, dumpPath, env = process.env) {
  const result = spawnSync(process.execPath, [NATIVE_REVIEW, ...args.argv], {
    cwd: args.cwd,
    encoding: "utf8",
    windowsHide: true,
    env: { ...env, PM_BRIDGE_DEBUG_DUMP_PROMPT: dumpPath, PM_BRIDGE_DEBUG_DUMP_PROMPT_ONLY: "1" },
    maxBuffer: 2 * 1024 * 1024,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`native review dump exited ${result.status}: ${(result.stderr || result.stdout || "").slice(-1500)}`);
  if (!fs.existsSync(dumpPath)) throw new Error(`native review dump failed (exit ${result.status}): ${(result.stderr || result.stdout || "").slice(-1500)}`);
  const diagnostic = [...(result.stdout || "").trim().split(/\r?\n/)].reverse().find((line) => line.startsWith("{"));
  if (!diagnostic) throw new Error("native review dump did not return its diagnostic JSON");
  const parsed = JSON.parse(diagnostic);
  if (parsed.diagnostic !== true) throw new Error(`native review preflight failed: ${parsed.error || "unknown failure"}`);
  return parsed;
}

function artifactDirectory(cwd) {
  return path.join(cwd, "docs", "sdlc", ".pm-review");
}

function ensurePrivateArtifactDirectory(cwd) {
  const target = artifactDirectory(cwd);
  fs.mkdirSync(target, { recursive: true });
  for (const candidate of [path.join(cwd, "docs"), path.join(cwd, "docs", "sdlc"), target]) {
    const st = fs.lstatSync(candidate);
    if (!st.isDirectory() || st.isSymbolicLink()) throw new Error(`review artifact directory is not a real directory: ${candidate}`);
  }
  return target;
}

function publishPrompt(dir, promptBytes, inputHash) {
  fs.mkdirSync(dir, { recursive: true });
  const filePath = path.join(dir, `${ATTACHMENT_PREFIX}${inputHash}.txt`);
  if (fs.existsSync(filePath)) {
    verifyRegularAttachment(filePath, inputHash, promptBytes.length);
  } else {
    const temporary = path.join(dir, `.${ATTACHMENT_PREFIX}${crypto.randomUUID()}.tmp`);
    const fd = fs.openSync(temporary, "wx", 0o600);
    try { fs.writeFileSync(fd, promptBytes); fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
    try { fs.linkSync(temporary, filePath); }
    catch (err) {
      if (err.code !== "EEXIST") throw err;
      verifyRegularAttachment(filePath, inputHash, promptBytes.length);
    } finally { fs.unlinkSync(temporary); }
    verifyRegularAttachment(filePath, inputHash, promptBytes.length);
  }
  return filePath;
}

function atomicJson(filePath, value) {
  const temporary = `${filePath}.${crypto.randomUUID()}.tmp`;
  const fd = fs.openSync(temporary, "wx", 0o600);
  try { fs.writeFileSync(fd, `${JSON.stringify(value, null, 2)}\n`, "utf8"); fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
  fs.renameSync(temporary, filePath);
}

function readOwnedIntent(filePath) {
  const st = fs.lstatSync(filePath);
  if (!st.isFile() || st.isSymbolicLink() || st.nlink !== 1 || st.size > 64 * 1024) throw new Error("persisted review intent is not a bounded regular single-link file");
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function createIntentExclusive(filePath, candidate) {
  const fd = fs.openSync(filePath, "wx", 0o600);
  try {
    fs.writeFileSync(fd, `${JSON.stringify(candidate, null, 2)}\n`, "utf8");
    fs.fsyncSync(fd);
  } finally { fs.closeSync(fd); }
  return candidate;
}

function validateIntent(intent, expected) {
  if (!intent || intent.operation !== OPERATION ||
      typeof intent.requestId !== "string" || !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(intent.requestId) ||
      intent.inputHash !== expected.inputHash || intent.headSha !== expected.headSha || intent.baseSha !== expected.baseSha ||
      intent.projectId !== expected.projectId || intent.conversationId !== expected.conversationId ||
      intent.size !== expected.size || canonicalPath(intent.attachmentPath) !== canonicalPath(expected.attachmentPath) ||
      !["prepared", "sending", "succeeded"].includes(intent.phase)) {
    throw new Error("persisted review intent schema or immutable identity fields do not match this canonical request");
  }
  if ((intent.instruction !== undefined && typeof intent.instruction !== "string") ||
      (intent.instructionSha256 !== undefined && (typeof intent.instruction !== "string" ||
       intent.instructionSha256 !== sha256(Buffer.from(intent.instruction, "utf8"))))) {
    throw new Error("persisted review intent instruction hash does not match its immutable instruction");
  }
  return intent;
}

export function parseAcknowledgements(reply, expected) {
  const fields = [
    ["REVIEW_INPUT_SHA256", expected.inputHash],
    ["REVIEW_HEAD", expected.headSha],
    ["REVIEW_REQUEST_ID", expected.requestId],
  ];
  const lines = String(reply ?? "").split(/\r?\n/);
  const outsideFence = [];
  let fence = null;
  for (const line of lines) {
    const fenceMatch = /^\s{0,3}(`{3,}|~{3,})/.exec(line);
    if (fenceMatch) {
      const marker = fenceMatch[1][0];
      if (fence === null) fence = marker;
      else if (fence === marker) fence = null;
      continue;
    }
    if (fence === null) outsideFence.push(line);
  }
  for (const [label, value] of fields) {
    const token = `${label}:`;
    const occurrences = String(reply ?? "").split(token).length - 1;
    const exact = outsideFence.filter((line) => line === `${token}${value}`);
    if (occurrences !== 1 || exact.length !== 1) throw new Error(`GPT reply lacks one unique standalone ${label} acknowledgment or contains conflicting/quoted/code-fenced copies`);
  }
  return true;
}

export function validateTopLevelVerdict(reply, parseVerdict, expectedRequestId) {
  const lines = String(reply ?? "").split(/\r?\n/);
  let verdictIndex = 0;
  const requestIdHeader = /^REQUEST_ID: ([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})$/i.exec(lines[0] ?? "");
  if (requestIdHeader) {
    if (!expectedRequestId || requestIdHeader[1] !== expectedRequestId) {
      throw new Error("GPT reply leading REQUEST_ID does not match the persisted request identity");
    }
    verdictIndex = lines[1] === "" ? 2 : 1;
  }
  const verdictLine = lines[verdictIndex] ?? "";
  if (!/^VERDICT: [^\r\n]+$/.test(verdictLine)) {
    throw new Error("GPT reply must begin with one unquoted top-level VERDICT line, optionally after its matching REQUEST_ID");
  }
  const parsed = parseVerdict(reply);
  if (!parsed?.found || parsed.verdictCount !== 1 || verdictLine !== `VERDICT: ${String(parsed.line ?? "").trim()}`) {
    throw new Error("GPT reply contains a missing, repeated, echoed, or conflicting VERDICT line");
  }
  return parsed;
}

export function nativePromptWasTruncated(prompt, { requestedFinal }) {
  // review.js's --final path refuses before prompt emission when buildDiff exceeds
  // MAX_DIFF_CHARS. Non-final reviews use this exact marker only after slicing that
  // diff to MAX_DIFF_CHARS; require the native shape and an over-limit total.
  const open = "Diff:\n```diff\n";
  const openAt = prompt.indexOf(open);
  if (openAt < 0) throw new Error("native prompt is missing the diff envelope");
  const footerAt = prompt.lastIndexOf("\n\n---\n\n");
  const closeSearchEnd = footerAt > openAt ? footerAt : prompt.length;
  const closeAt = prompt.lastIndexOf("\n```", closeSearchEnd);
  if (closeAt < openAt + open.length) throw new Error("native prompt diff envelope is incomplete");
  const diffTail = prompt.slice(openAt + open.length, closeAt);
  const marker = /\n\[\.\.\. truncated, ([1-9]\d*) chars total \.\.\.\]$/.exec(diffTail);
  if (!marker) return false;
  if (Number(marker[1]) <= NATIVE_MAX_DIFF_CHARS) throw new Error("prompt contains a truncation marker inconsistent with native review.js limits");
  if (requestedFinal) throw new Error("native final review prompt contains its non-final truncation marker");
  return true;
}

function assertManifest(job, filePath, inputHash, size, expectedText) {
  const snapshot = job?.sendSnapshot;
  const entries = snapshot?.attachments;
  if (!Array.isArray(entries) || entries.length !== 1) throw new Error("durable send snapshot lacks exactly one attachment descriptor");
  const entry = entries[0];
  if (entry.name !== path.basename(filePath) || entry.size !== size || entry.sha256 !== inputHash || canonicalPath(entry.path) !== canonicalPath(filePath)) {
    throw new Error("durable daemon attachment manifest differs from the canonical prompt file");
  }
  if (snapshot.logicalText !== expectedText) throw new Error("durable logical sent text differs from the persisted short instruction");
  const wire = snapshot.baseline?.wireEvidence;
  if (!snapshot.baseline?.userTurnId || snapshot.baseline.userTurnId !== job.userTurnId || !wire || wire.wireRequestId !== job.requestId ||
      wire.wireDescriptor?.requestId !== job.requestId || wire.wireHash !== sha256(Buffer.from(snapshot.text ?? "", "utf8")) ||
      typeof snapshot.text !== "string" || !snapshot.text.includes(job.requestId)) {
    throw new Error("durable wire text lacks the native request-ID and user-turn evidence contract");
  }
  return entry;
}

export function validateCompletedJob({ job, intent, filePath, promptBytes }) {
  if (!job || job.status !== "succeeded" || job.operation !== OPERATION || job.sendPhase !== "sent") throw new Error("durable review job is not a completed sent send-and-await");
  if (job.requestId !== intent.requestId || job.projectId !== intent.projectId || job.conversationId !== intent.conversationId) throw new Error("durable job identity does not match persisted intent");
  const snapshot = job.sendSnapshot;
  if (!snapshot || !job.userTurnId || !job.replyId || job.result?.replyId !== job.replyId || job.correlated !== true || job.result?.correlated !== true) throw new Error("durable job lacks sent-turn and correlated reply evidence");
  if (job.idempotencyKey !== `${intent.requestId}:send-and-await`) throw new Error("durable job idempotency key differs from persisted intent");
  if (snapshot.conversationId !== intent.conversationId) throw new Error("durable sent snapshot conversation differs from persisted intent");
  const descriptor = assertManifest(job, filePath, intent.inputHash, promptBytes.length, intent.instruction);
  const reply = job.result.reply;
  if (typeof reply !== "string") throw new Error("durable review result has no textual reply");
  parseAcknowledgements(reply, { inputHash: intent.inputHash, headSha: intent.headSha, requestId: intent.requestId });
  return { descriptor, reply, replyId: job.result.replyId };
}

async function loadBridge() {
  const at = (name) => pathToFileURL(path.join(BRIDGE_ROOT, name)).href;
  const [client, routing, identity, verdict, wireEnvelope] = await Promise.all([
    import(at("orchestratorClient.js")), import(at("callerRouting.js")),
    import(at("projectAutoRegister.js")), import(at("reviewVerdict.js")), import(at("wireEnvelope.js")),
  ]);
  return { ...client, ...routing, ...identity, ...verdict, ...wireEnvelope };
}

async function runAdapter(argv, { bridgeLoader = loadBridge, nativeDump = runNativeDump } = {}) {
  if (process.env.PM_BRIDGE_DEBUG_DUMP_PROMPT_ONLY) {
    const forwarded = spawnSync(process.execPath, [NATIVE_REVIEW, ...argv], {
      cwd: process.cwd(), encoding: "utf8", windowsHide: true,
      env: process.env, maxBuffer: 2 * 1024 * 1024,
    });
    if (forwarded.error) throw forwarded.error;
    if (forwarded.stdout) process.stdout.write(forwarded.stdout);
    if (forwarded.stderr) process.stderr.write(forwarded.stderr);
    process.exitCode = forwarded.status ?? 2;
    return null;
  }
  const args = parseArgs(argv);
  const initial = validateCommitRange(args);
  const dir = ensurePrivateArtifactDirectory(args.cwd);
  const dump = path.join(dir, `.prompt-${crypto.randomUUID()}.tmp`);
  let promptBytes;
  let inputHash;
  let truncated = false;
  try {
    nativeDump(args, dump);
    promptBytes = fs.readFileSync(dump);
    if (!promptBytes.length || promptBytes.length > MAX_PROMPT_BYTES) throw new Error("canonical prompt is empty or exceeds 64 MiB");
    const prompt = new TextDecoder("utf-8", { fatal: true }).decode(promptBytes);
    if (!Buffer.from(prompt, "utf8").equals(promptBytes)) throw new Error("native prompt dump is not canonical UTF-8");
    inputHash = sha256(promptBytes);
    assertPromptBinding(prompt, { ...initial, baseRef: args.base });
    truncated = nativePromptWasTruncated(prompt, { requestedFinal: args.final });
  } finally { if (fs.existsSync(dump)) fs.unlinkSync(dump); }
  const rangeAfterDump = validateCommitRange(args);
  if (rangeAfterDump.headSha !== initial.headSha || rangeAfterDump.baseSha !== initial.baseSha) throw new Error("repository HEAD/base moved while building the canonical review input");

  const attachmentPath = publishPrompt(dir, promptBytes, inputHash);
  const intentPath = path.join(dir, `intent-${inputHash}.json`);
  const bridge = await bridgeLoader();
  const { identityBinding } = await bridge.resolveIdentityAssertedBinding(args.cwd, "--cwd", args.project, "--project", "AF attachment review routing");
  const active = await bridge.isOrchestratorActive();
  if (!active) throw new Error("no compatible PM Bridge daemon is active; attachment review refuses direct transport");
  if (!Array.isArray(active.capabilities) || !active.capabilities.includes("file-attachments")) throw new Error("active PM Bridge daemon does not advertise file-attachments capability");

  let intent;
  const expectedIntent = { inputHash, headSha: initial.headSha, baseSha: initial.baseSha,
    projectId: identityBinding.projectId, conversationId: identityBinding.conversationId,
    size: promptBytes.length, attachmentPath };
  if (fs.existsSync(intentPath)) {
    const prior = readOwnedIntent(intentPath);
    intent = validateIntent(prior, expectedIntent);
  } else {
    const requestId = crypto.randomUUID();
    const candidate = { requestId, operation: OPERATION, inputHash, headSha: initial.headSha, baseSha: initial.baseSha, size: promptBytes.length, attachmentPath, projectId: identityBinding.projectId, conversationId: identityBinding.conversationId, createdAt: new Date().toISOString(), phase: "prepared" };
    try { intent = validateIntent(createIntentExclusive(intentPath, candidate), expectedIntent); }
    catch (err) {
      if (err.code !== "EEXIST") throw err;
      intent = validateIntent(readOwnedIntent(intentPath), expectedIntent);
    }
  }
  verifyRegularAttachment(attachmentPath, inputHash, promptBytes.length);
  const instruction = [
    "Review the attached complete canonical PM Bridge input as one adversarial S2 code-and-tests review, including its evidence. Do not claim review of historical documentation lines outside the attached input. Put the VERDICT line first, then the findings, then the three exact acknowledgement lines below.",
    `Exact HEAD under review: ${intent.headSha}`, `Reviewed range: ${intent.baseSha}...${intent.headSha}`,
    `Full attachment SHA-256: ${inputHash}`, `Attachment bytes: ${promptBytes.length}`,
    `Request ID: ${intent.requestId}`,
    "Your reply must include exactly identifiable acknowledgements on separate lines:",
    `REVIEW_INPUT_SHA256:${inputHash}`, `REVIEW_HEAD:${intent.headSha}`, `REVIEW_REQUEST_ID:${intent.requestId}`,
  ].join("\n");
  if (intent.instruction && intent.instruction !== instruction) throw new Error("persisted short instruction differs from this request");
  if (!intent.instruction) {
    intent = { ...intent, instruction, instructionSha256: sha256(Buffer.from(instruction, "utf8")) };
    atomicJson(intentPath, intent);
  }
  intent = validateIntent(intent, expectedIntent);

  const status = async () => bridge.callOrchestrator(active, "/job_status", { requestId: intent.requestId, operation: OPERATION }, 10000);
  let durable;
  let recovered = false;
  try {
    const previous = await status();
    if (previous.job) { durable = previous.job; recovered = true; }
  } catch (err) { if (err.code !== "JOB_NOT_FOUND") throw err; }
  const claimPath = path.join(dir, `claim-${inputHash}.json`);
  if (!durable && (intent.phase !== "prepared" || fs.existsSync(claimPath))) {
    throw new Error(`request ${intent.requestId} was already marked sending but has no visible durable job; refusing to resend or mint a new ID, reconcile this exact request via job status`);
  }
  if (!durable) {
    try {
      createIntentExclusive(claimPath, { requestId: intent.requestId, inputHash, createdAt: new Date().toISOString() });
    } catch (err) {
      if (err.code !== "EEXIST") throw err;
      throw new Error(`another invocation already claimed send boundary for request ${intent.requestId}; reconcile this exact request via job status`);
    }
    intent = { ...intent, phase: "sending" };
    atomicJson(intentPath, intent);
    try {
      await bridge.callOrchestrator(active, "/send_and_await", {
        ...bridge.daemonRouting(args.project, { repoPath: args.cwd }),
        text: instruction, attachments: [attachmentPath], waitForCompletionControls: true,
        reviewInputHash: inputHash, reviewRequestId: intent.requestId,
        requestId: intent.requestId, idempotencyKey: `${intent.requestId}:send-and-await`,
      }, null);
    } catch (sendError) {
      try { durable = (await status()).job; }
      catch (recoveryError) { throw new Error(`send response was ambiguous (${sendError.message}); durable status unavailable (${recoveryError.message}); resume same request ${intent.requestId}`); }
      if (!durable) throw new Error(`send response was ambiguous (${sendError.message}); no durable job exists; retry same intent ${intent.requestId}`);
    }
  }
  if (!durable || !["succeeded", "failed", "cancelled", "uncertain"].includes(durable.status)) durable = (await status()).job;
  if (!durable || durable.status !== "succeeded") throw new Error(`durable review request ${intent.requestId} is ${durable?.status ?? "unknown"}; inspect/resume this same request, never create another one`);
  verifyRegularAttachment(attachmentPath, inputHash, promptBytes.length);
  const proof = validateCompletedJob({ job: durable, intent, filePath: attachmentPath, promptBytes });
  const wireDescriptor = durable.sendSnapshot.baseline.wireEvidence.wireDescriptor;
  bridge.assertCanonicalDescriptor(wireDescriptor);
  if (wireDescriptor.steps.some((step) => step.kind === "rotation-title")) throw new Error("conversation-rotation wire snapshots are outside this adapter's authorized recovery contract");
  const reproducedWireText = bridge.applyWireTransforms(intent.instruction, wireDescriptor, {});
  if (reproducedWireText !== durable.sendSnapshot.text) throw new Error("durable wire text does not reproduce from logical instruction and canonical native descriptor");
  if (validateCommitRange(args).headSha !== intent.headSha) throw new Error("repository HEAD changed while PM Bridge review was running");
  intent = { ...intent, phase: "succeeded", jobId: durable.jobId, replyId: proof.replyId };
  atomicJson(intentPath, intent);

  const parsed = validateTopLevelVerdict(proof.reply, bridge.parseVerdict, intent.requestId);
  const finalDecision = bridge.decideReviewFinal({ requestedFinal: args.final, reviewStatus: "RAN", reply: proof.reply, parsedVerdict: parsed, truncated, correlated: true });
  const result = {
    ok: true, error: null, review_status: "RAN", round: 1,
    final: finalDecision.final, truncated, final_overridden: finalDecision.finalOverridden,
    verdict: parsed.severity, verdict_contradiction: parsed.contradiction === true,
    correlated: true, replyId: proof.replyId, reviewRequestId: intent.requestId,
    reviewInputHash: proof.descriptor.sha256, conversation: identityBinding.conversationId,
    recovered, reply: proof.reply, receipt_written: durable.sendPhase === "sent",
    attachment: { path: attachmentPath, name: proof.descriptor.name, size: proof.descriptor.size, sha256: proof.descriptor.sha256 },
    durableJobId: durable.jobId, projectId: identityBinding.projectId, baseSha: intent.baseSha, headSha: intent.headSha,
  };
  console.log(JSON.stringify(result));
  return result;
}

export { runAdapter };

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  runAdapter(process.argv.slice(2)).catch((err) => {
    console.log(JSON.stringify({ ok: false, error: err.message, review_status: "NOT_RUN", final: false, truncated: false, final_overridden: false, verdict: "UNRECOGNIZED", correlated: false, receipt_written: false }));
    process.exitCode = 2;
  });
}
