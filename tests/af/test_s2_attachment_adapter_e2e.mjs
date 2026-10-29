import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

const repoRoot = fileURLToPath(new URL("../../", import.meta.url));
const adapterUrl = pathToFileURL(path.join(repoRoot, "tools", "af_attachment_review.mjs")).href;
const pmBridgeRoot = "D:/Repo/pm-bridge/src";
const projectId = "vst-attachment-fixture";
const conversationId = "conversation-fixture";
const fakeAuthToken = "fixture-only-token-never-a-real-credential";
const sha256 = (value) => crypto.createHash("sha256").update(value).digest("hex");

function git(repo, args, input = undefined) {
  return execFileSync("git", ["-C", repo, ...args], {
    input,
    encoding: "utf8",
    windowsHide: true,
  }).trim();
}

function commitFixture(repo, content, parent, message) {
  const blob = git(repo, ["hash-object", "-w", "--stdin"], content);
  const tree = git(repo, ["mktree"], `100644 blob ${blob}\tfixture.txt\n`);
  const parentLine = parent ? `parent ${parent}\n` : "";
  const raw = `tree ${tree}\n${parentLine}author Fixture <fixture@example.invalid> 1793232000 +0000\ncommitter Fixture <fixture@example.invalid> 1793232000 +0000\n\n${message}\n`;
  return git(repo, ["hash-object", "-t", "commit", "-w", "--stdin"], raw);
}

function createFixtureRepo(root) {
  const repo = path.join(root, "repo");
  fs.mkdirSync(repo, { recursive: true });
  execFileSync("git", ["init", "--quiet", "--initial-branch=main", repo], { windowsHide: true });
  fs.mkdirSync(path.join(repo, "docs", "sdlc"), { recursive: true });
  const baseSha = commitFixture(repo, "before\n", null, "fixture base");
  const headSha = commitFixture(repo, "after\n", baseSha, "fixture head");
  git(repo, ["update-ref", "refs/heads/base", baseSha]);
  git(repo, ["update-ref", "refs/heads/main", headSha]);
  return { repo, baseSha, headSha };
}

async function readJson(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

async function listen(server) {
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  return server.address().port;
}

test("AF attachment adapter sends >4 MiB canonical input through the authenticated loopback client and accepts only its durable receipt", async (t) => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "vst-af-attachment-e2e-"));
  t.after(() => fs.rmSync(tempRoot, { recursive: true, force: true }));

  const { repo, baseSha, headSha } = createFixtureRepo(tempRoot);
  const largePayload = "x".repeat(4 * 1024 * 1024 + 37);
  const nativePrompt = Buffer.from(
    `# Synthetic PM review input\nReviewed range: ${baseSha}...${headSha}\nExact HEAD under review: ${headSha}\n\n` +
    "Diff:\n```diff\n--- a/fixture.txt\n+++ b/fixture.txt\n" + largePayload + "\n```\n",
    "utf8",
  );
  const inputHash = sha256(nativePrompt);
  const userTurnId = "turn-fixture-1";
  let durableJob = null;
  let sendCount = 0;
  let receivedAttachmentBytes = 0;
  let receivedTextBytes = 0;
  let wireModule;

  const server = http.createServer(async (req, res) => {
    try {
      assert.equal(req.headers.authorization, `Bearer ${fakeAuthToken}`);
      const body = await readJson(req);
      if (req.url === "/job_status") {
        if (!durableJob) {
          res.writeHead(404, { "content-type": "application/json" });
          res.end(JSON.stringify({ ok: false, code: "JOB_NOT_FOUND", error: "fixture has no durable job yet" }));
          return;
        }
        res.writeHead(200, { "content-type": "application/json" });
        res.end(JSON.stringify({ ok: true, job: durableJob }));
        return;
      }
      if (req.url !== "/send_and_await") {
        res.writeHead(404, { "content-type": "application/json" });
        res.end(JSON.stringify({ ok: false, code: "NOT_FOUND" }));
        return;
      }

      sendCount += 1;
      assert.equal(sendCount, 1, "the adapter must submit one durable send only");
      assert.equal(body.waitForCompletionControls, true);
      assert.equal(body.requestId, body.reviewRequestId);
      assert.equal(body.idempotencyKey, `${body.requestId}:send-and-await`);
      assert.equal(body.attachments?.length, 1);
      assert.equal(typeof body.text, "string");
      receivedTextBytes = Buffer.byteLength(JSON.stringify(body), "utf8");
      assert.ok(receivedTextBytes < 100_000, "the large canonical prompt must not be in the HTTP JSON body");
      assert.ok(!body.text.includes(largePayload), "the short instruction must not substitute for the attachment");

      const attachmentPath = body.attachments[0];
      const attachment = fs.readFileSync(attachmentPath);
      receivedAttachmentBytes = attachment.length;
      assert.equal(sha256(attachment), body.reviewInputHash);
      assert.equal(body.reviewInputHash, inputHash);
      assert.deepEqual(attachment, nativePrompt, "transport must carry the complete canonical bytes unchanged");

      const identityBinding = { projectId, conversationId };
      const descriptor = wireModule.describeWireTransforms({
        requestId: body.requestId,
        header: { project: projectId, repo },
      });
      const wireText = wireModule.applyWireTransforms(body.text, descriptor, {});
      const replyId = "reply-fixture-1";
      const reply = [
        "VERDICT: APPROVE",
        "Fixture-only acceptance; this is not a GPT review.",
        `REVIEW_INPUT_SHA256:${inputHash}`,
        `REVIEW_HEAD:${headSha}`,
        `REVIEW_REQUEST_ID:${body.requestId}`,
      ].join("\n");
      durableJob = {
        jobId: "job-fixture-1",
        idempotencyKey: body.idempotencyKey,
        operation: "send-and-await",
        projectId: identityBinding.projectId,
        conversationId: identityBinding.conversationId,
        requestId: body.requestId,
        status: "succeeded",
        sendPhase: "sent",
        userTurnId,
        replyId,
        correlated: true,
        result: { reply, replyId, correlated: true },
        sendSnapshot: {
          text: wireText,
          logicalText: body.text,
          conversationId,
          attachments: [{
            name: path.basename(attachmentPath),
            path: attachmentPath,
            size: attachment.length,
            sha256: inputHash,
          }],
          baseline: {
            userTurnId,
            wireEvidence: {
              wireProtocolVersion: descriptor.protocolVersion,
              wireRequestId: descriptor.requestId,
              wireDescriptor: descriptor,
              wireHash: sha256(wireText),
            },
          },
        },
      };

      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ ok: true, requestId: body.requestId, reply, replyId, correlated: true }));
    } catch (error) {
      res.writeHead(500, { "content-type": "application/json" });
      res.end(JSON.stringify({ ok: false, error: error.message }));
    }
  });

  const port = await listen(server);
  t.after(() => new Promise((resolve) => server.close(resolve)));
  const active = { port, authToken: fakeAuthToken, capabilities: ["file-attachments"] };
  const [clientModule, routingModule, identityModule, verdictModuleLoaded, wireModuleLoaded] = await Promise.all([
    import(pathToFileURL(path.join(pmBridgeRoot, "orchestratorClient.js")).href),
    import(pathToFileURL(path.join(pmBridgeRoot, "callerRouting.js")).href),
    import(pathToFileURL(path.join(pmBridgeRoot, "projectAutoRegister.js")).href),
    import(pathToFileURL(path.join(pmBridgeRoot, "reviewVerdict.js")).href),
    import(pathToFileURL(path.join(pmBridgeRoot, "wireEnvelope.js")).href),
  ]);
  wireModule = wireModuleLoaded;
  const bridge = {
    ...clientModule,
    ...routingModule,
    ...identityModule,
    ...verdictModuleLoaded,
    ...wireModule,
    resolveIdentityAssertedBinding: async () => ({ identityBinding: { projectId, conversationId } }),
    isOrchestratorActive: async () => active,
    daemonRouting: (_project, { repoPath }) => ({ project: projectId, repoPath }),
  };
  const { runAdapter } = await import(adapterUrl);
  const result = await runAdapter(
    ["--cwd", repo, "--base", baseSha, "--project", projectId, "--final"],
    {
      bridgeLoader: async () => bridge,
      nativeDump: (_args, dumpPath) => fs.writeFileSync(dumpPath, nativePrompt),
    },
  );

  assert.equal(result.ok, true);
  assert.equal(result.final, true);
  assert.equal(result.verdict, "APPROVE");
  assert.equal(result.correlated, true);
  assert.equal(result.reviewInputHash, inputHash);
  assert.equal(result.headSha, headSha);
  assert.equal(result.attachment.size, nativePrompt.length);
  assert.equal(result.attachment.sha256, inputHash);
  assert.equal(sendCount, 1);
  assert.equal(receivedAttachmentBytes, nativePrompt.length);
  assert.ok(receivedTextBytes < 100_000);
  assert.ok(!fs.existsSync(path.join(repo, "docs", "sdlc", "gate-approval.md")));
  assert.ok(!fs.existsSync(path.join(repo, "docs", "sdlc", ".pm-review", "approval.json")));
});

test("native review.js dump-only mode writes the exact canonical prompt and exits before any transport", (t) => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "vst-native-review-dump-e2e-"));
  t.after(() => fs.rmSync(tempRoot, { recursive: true, force: true }));

  const { repo, baseSha, headSha } = createFixtureRepo(tempRoot);
  const configDir = path.join(tempRoot, "pm-config");
  const stateDir = path.join(tempRoot, "pm-state");
  const runtimeDir = path.join(tempRoot, "pm-runtime");
  const packetPath = path.join(tempRoot, "scope-packet.md");
  const dumpPath = path.join(tempRoot, "canonical-prompt.txt");
  const receiptsPath = path.join(tempRoot, "receipts.jsonl");
  const registryPath = path.join(configDir, "projects.json");
  const project = {
    projectId,
    displayName: "Synthetic AF attachment review fixture",
    repoUrl: null,
    repoRoots: [repo],
    conversationId: "33333333-3333-4333-8333-333333333333",
    createdAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:00:00.000Z",
  };
  fs.mkdirSync(configDir, { recursive: true });
  fs.writeFileSync(registryPath, `${JSON.stringify({ version: 1, projects: [project] }, null, 2)}\n`);
  const scopeNote = "Synthetic scope packet: prove the native prompt dump path and stop before transport.";
  fs.writeFileSync(packetPath, `${scopeNote}\n`, "utf8");

  const nativeReview = "D:/Repo/pm-bridge/src/cli/review.js";
  const command = [
    nativeReview,
    "--cwd", repo,
    "--base", baseSha,
    "--project", projectId,
    "--final",
    "--scope-note-file", packetPath,
  ];
  const env = {
    PATH: process.env.PATH ?? "",
    SystemRoot: process.env.SystemRoot ?? "",
    WINDIR: process.env.WINDIR ?? "",
    TEMP: tempRoot,
    TMP: tempRoot,
    USERPROFILE: tempRoot,
    HOME: tempRoot,
    PM_BRIDGE_EXECUTION_ROOT: "D:/Repo/pm-bridge",
    PM_BRIDGE_SOURCE_ROOT: "D:/Repo/pm-bridge",
    PM_BRIDGE_RUNTIME_ROOT: runtimeDir,
    PM_BRIDGE_CONFIG_DIR: configDir,
    PM_BRIDGE_STATE_DIR: stateDir,
    PM_BRIDGE_GENERATIONS_DIR: path.join(runtimeDir, "generations"),
    PM_BRIDGE_RECEIPTS_FILE: receiptsPath,
    PM_BRIDGE_BROWSER_LOCK_PATH: path.join(runtimeDir, "browser.lock"),
    PM_BRIDGE_DEBUG_DUMP_PROMPT: dumpPath,
    PM_BRIDGE_DEBUG_DUMP_PROMPT_ONLY: "1",
    PM_BRIDGE_NO_EXECUTION_AUTHORITY: "1",
    PM_BRIDGE_BREAK_GLASS_DIRECT: "0",
  };
  const processResult = execFileSync(process.execPath, command, {
    cwd: tempRoot,
    env,
    encoding: "utf8",
    windowsHide: true,
    timeout: 30000,
  });
  const diagnostic = JSON.parse(processResult.trim().split(/\r?\n/).at(-1));
  assert.equal(diagnostic.diagnostic, true);
  assert.match(diagnostic.error, /dumped prompt, skipped transport/);
  assert.equal(diagnostic.ok, false, "dump-only is preflight evidence, not a successful review");

  const actualBytes = fs.readFileSync(dumpPath);
  const actualHash = sha256(actualBytes);
  const diff = execFileSync("git", ["-C", repo, "diff", `${baseSha}...${headSha}`, "--", ".", ":(exclude)reports"], {
    encoding: "utf8",
    windowsHide: true,
  });
  const scopeBlock =
    `Scope of THIS round -- read before reviewing:\n${scopeNote}\n\n` +
    "Findings outside that scope are still welcome, but mark them explicitly as out-of-scope " +
    "and do NOT let them set the VERDICT line: the verdict must answer the scoped question. " +
    "If the scoped question is genuinely satisfied, say APPROVE even when out-of-scope work " +
    "remains -- an unrelated open item is not a reason to withhold a verdict on this one.\n\n";
  const expectedPrompt =
    `Code review request for project "${projectId}".\n\n` +
    scopeBlock +
    "Reply with a VERDICT line first (APPROVE, or BLOCKER/MAJOR/MINOR findings), then " +
    "each finding as: severity | claim | evidence | failure scenario | required change.\n\n" +
    "Apply a devil's-advocate stance throughout: actively look for reasons this change " +
    "is wrong, unsafe, incomplete, or will break something, rather than defaulting to " +
    "approval. This does not license inventing problems that aren't real: every " +
    "objection still needs the same real file/line evidence required above -- if after " +
    "genuinely trying to find a problem there is none, say so plainly rather than " +
    "manufacturing a NIT to seem thorough.\n\n" +
    "Diff:\n```diff\n" + diff + "\n```";
  const expectedBytes = Buffer.from(expectedPrompt, "utf8");
  const expectedHash = sha256(expectedBytes);
  assert.deepEqual(actualBytes, expectedBytes, "native dump must byte-match the independently assembled canonical prompt");
  assert.equal(actualHash, expectedHash, "dump hash must match the canonical expected prompt hash");
  assert.ok(actualBytes.includes(Buffer.from(scopeNote, "utf8")));
  assert.ok(actualBytes.includes(Buffer.from(diff, "utf8")));
  assert.equal(fs.readFileSync(registryPath, "utf8"), `${JSON.stringify({ version: 1, projects: [project] }, null, 2)}\n`, "dump-only identity resolution must not auto-register or mutate fixture project metadata");
  assert.equal(fs.existsSync(receiptsPath), false, "preflight dump-only mode must not write a review receipt");
  assert.equal(fs.existsSync(path.join(runtimeDir, "browser.lock")), false, "dump-only mode must not touch the browser lock");
  assert.equal(fs.existsSync(path.join(stateDir, "orchestrator.json")), false, "test isolation must not create daemon state");
});
