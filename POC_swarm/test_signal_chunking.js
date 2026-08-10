// Round-trip tests for the IRC signalling transport in app.js.
//
// app.js is a browser script, so it is loaded into a vm context with the
// minimum DOM surface stubbed out. Script-level `let`/`const` bindings live in
// the shared global lexical scope of the realm, so the assertions below can
// reach SIGNAL_PREFIX, ircClient and localPeerId directly.
//
// Run:  node test_signal_chunking.js

const fs = require("fs");
const path = require("path");
const vm = require("vm");

function stubElement() {
    return {
        textContent: "",
        innerHTML: "",
        id: "",
        addEventListener() {},
        appendChild() {},
        removeChild() {},
        remove() {},
    };
}

const sandbox = {
    document: {
        getElementById: () => stubElement(),
        createElement: () => stubElement(),
        addEventListener() {},
    },
    window: { addEventListener() {} },
    console: { log() {}, warn() {}, error() {} },
    setInterval: () => 0,
    clearInterval() {},
    setTimeout: () => 0,
    RTCPeerConnection: function () {},
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

vm.runInContext(fs.readFileSync(path.join(__dirname, "app.js"), "utf8"), sandbox, {
    filename: "app.js",
});

const harness = `
(() => {
    const results = [];
    const check = (name, fn) => {
        try { fn(); results.push({ name, ok: true }); }
        catch (e) { results.push({ name, ok: false, error: e.message }); }
    };
    const assert = (cond, msg) => { if (!cond) throw new Error(msg || "assertion failed"); };

    let sent = [];
    localPeerId = "user-testpeer";
    ircClient = { connected: true, say: (target, msg) => sent.push(msg) };

    const deliver = (lines) => {
        let last = null;
        for (const line of lines) last = receiveSignalChunk(line);
        return last;
    };

    check("small signal round-trips in one chunk", () => {
        sent = [];
        const signal = { type: "candidate", senderPeerId: localPeerId, data: { candidate: "abc" } };
        assert(sendSignal("bob", signal) === true, "sendSignal should succeed");
        assert(sent.length === 1, "expected 1 chunk, got " + sent.length);
        const out = deliver(sent);
        assert(JSON.stringify(out) === JSON.stringify(signal), "payload changed in transit");
    });

    check("4KB SDP offer round-trips across many chunks", () => {
        sent = [];
        const sdp = "v=0\\r\\n" + "a=candidate:xyz ".repeat(250);
        const signal = { type: "offer", senderPeerId: localPeerId, data: { type: "offer", sdp } };
        sendSignal("bob", signal);
        assert(sent.length > 10, "expected many chunks, got " + sent.length);
        const out = deliver(sent);
        assert(out !== null, "reassembly returned null");
        assert(out.data.sdp === sdp, "SDP was corrupted or truncated");
    });

    check("every emitted IRC line stays well under the 512-byte limit", () => {
        sent = [];
        const signal = { type: "offer", senderPeerId: localPeerId, data: { sdp: "x".repeat(4000) } };
        sendSignal("bob", signal);
        const longest = Math.max(...sent.map((l) => l.length));
        assert(longest < 400, "longest line was " + longest + " chars");
    });

    check("chunks arriving out of order still reassemble", () => {
        sent = [];
        const signal = { type: "offer", senderPeerId: localPeerId, data: { sdp: "y".repeat(2000) } };
        sendSignal("bob", signal);
        const shuffled = sent.slice().reverse();
        const out = deliver(shuffled);
        assert(out !== null, "out-of-order reassembly failed");
        assert(out.data.sdp === "y".repeat(2000), "payload wrong after reorder");
    });

    check("duplicate chunks do not corrupt reassembly", () => {
        sent = [];
        const signal = { type: "offer", senderPeerId: localPeerId, data: { sdp: "z".repeat(1200) } };
        sendSignal("bob", signal);
        const withDupes = [sent[0], sent[0], ...sent];
        const out = deliver(withDupes);
        assert(out !== null, "reassembly failed with duplicates present");
        assert(out.data.sdp === "z".repeat(1200), "payload wrong with duplicates");
    });

    check("incomplete signal yields null, not a partial object", () => {
        sent = [];
        const signal = { type: "offer", senderPeerId: localPeerId, data: { sdp: "w".repeat(2000) } };
        sendSignal("bob", signal);
        const partial = deliver(sent.slice(0, sent.length - 1));
        assert(partial === null, "expected null for an incomplete signal");
    });

    check("malformed header is rejected", () => {
        assert(receiveSignalChunk(SIGNAL_PREFIX + "garbage-without-indices") === null,
               "malformed chunk should return null");
    });

    check("out-of-range chunk index is rejected", () => {
        assert(receiveSignalChunk(SIGNAL_PREFIX + "user-x-1:5:2:payload") === null,
               "index beyond total should return null");
    });

    check("sendSignal refuses when IRC is down", () => {
        const saved = ircClient;
        ircClient = { connected: false, say: () => { throw new Error("must not send"); } };
        const ok = sendSignal("bob", { type: "candidate", senderPeerId: localPeerId });
        ircClient = saved;
        assert(ok === false, "sendSignal should return false when disconnected");
    });

    return results;
})();
`;

const results = vm.runInContext(harness, sandbox, { filename: "harness.js" });

let failed = 0;
for (const r of results) {
    if (r.ok) {
        console.log(`  ok    ${r.name}`);
    } else {
        failed += 1;
        console.log(`  FAIL  ${r.name}\n        ${r.error}`);
    }
}
console.log(`\n${results.length - failed}/${results.length} passed`);
process.exit(failed ? 1 : 0);
